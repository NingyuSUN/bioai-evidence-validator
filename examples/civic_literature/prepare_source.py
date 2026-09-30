"""Build the pinned CIViC literature corpus from CIViC and NCBI (uses the network; run once).

    uv run --frozen python examples/civic_literature/prepare_source.py --civic /path/to/nightly.tsv

Steps, all recorded in sources/manifest.json:
1. CIViC's nightly accepted evidence (CC0), pinned by SHA-256; only PubMed-sourced items with a direction.
2. Candidate papers: those PMC lists under a CC BY or CC0 licence (one batched licence-filter search, so that
   only redistributable full texts are downloaded), in keyed-hash order, in two strata: papers with a
   "Does Not Support" item, and the rest. Each is resolved with NCBI E-utilities
   (`bioevidence_validator.literature.resolve`) and kept only if its own JATS licence is CC BY or CC0, it has a
   body, and it is not retracted, until each stratum is full.
3. Retracted open-access papers on cancer variants (PubMed "Retracted Publication"), kept under the same
   licence rule, and PMIDs that do not exist, for the negative controls of issue #20.

Everything the offline steps need is written to sources/: gzip-compressed snapshots named by the SHA-256 of
their uncompressed bytes, the catalog `snapshots/literature.json`, and a projection of the CIViC rows used.
Rejected downloads are deleted. Re-running later gives a different corpus as the sources change; the
committed snapshots are the reference.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from bioevidence_validator import literature

ROOT = Path(__file__).resolve().parent
CIVIC_URL = "https://civicdb.org/downloads/nightly/nightly-ClinicalEvidenceSummaries.tsv"
KEY = "bioai-civic-literature-v1"
TARGETS = {"does_not_support": 50, "supports_only": 100}
RETRACTED_TARGET = 20
FAKE_PMIDS = [str(99_000_001 + n) for n in range(20)]  # PubMed IDs are far below 99 million in 2026
RETRACTED_QUERY = ('"retracted publication"[pt] AND "pubmed pmc open access"[filter] AND cancer[tiab] '
                   'AND (mutation[tiab] OR variant[tiab])')
LICENCE_FILTER = '("cc by license"[filter] OR "cc0 license"[filter])'


def pmc_uids(pmids: list[str], fetch) -> dict[str, str]:
    """PubMed ID -> PMC UID (numeric), from batched esummary calls."""
    found = {}
    for start in range(0, len(pmids), 200):
        url = literature._eutils("esummary", db="pubmed", id=",".join(pmids[start:start + 200]), retmode="json")
        result = json.loads(fetch(url))["result"]
        for uid in result.get("uids", []):
            ids = {a["idtype"]: a["value"] for a in result[uid].get("articleids", [])}
            if ids.get("pmc", "").upper().startswith("PMC"):
                found[uid] = ids["pmc"][3:]
    return found


def openly_licensed(uids: list[str], fetch) -> set[str]:
    """The PMC UIDs that PMC itself lists under CC BY or CC0."""
    hits: set[str] = set()
    for start in range(0, len(uids), 150):
        term = "(" + " OR ".join(f"{u}[uid]" for u in uids[start:start + 150]) + ") AND " + LICENCE_FILTER
        url = literature._eutils("esearch", db="pmc", term=term, retmax="1000", retmode="json")
        hits |= set(json.loads(fetch(url))["esearchresult"]["idlist"])
    return hits
OPEN_LICENSES = {"cc by", "cc0"}


def keyed(text: str) -> str:
    return hashlib.sha256(f"{KEY}:{text}".encode()).hexdigest()


def civic_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle, delimiter="\t")
                if row["source_type"] == "PubMed" and row["evidence_status"] == "accepted"
                and row["evidence_direction"] in ("Supports", "Does Not Support") and row["is_flagged"] == "false"]


def keep(entry: dict, snapshots: Path) -> bool:
    if not entry["fulltext_sha256"] or entry["license"] not in OPEN_LICENSES:
        return False
    meta = literature.parse_metadata(entry["resolver"], gzip.decompress(
        (snapshots / f"{entry['metadata_sha256']}.json.gz").read_bytes()))
    return meta["found"] and not meta["retracted"]


def discard(entry: dict, snapshots: Path, pinned: set[str]) -> None:
    for sha, suffix in ((entry["metadata_sha256"], ".json.gz"), (entry["fulltext_sha256"], ".xml.gz")):
        if sha and sha not in pinned:
            (snapshots / f"{sha}{suffix}").unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--civic", type=Path, help="A downloaded nightly TSV; fetched from CIViC if omitted")
    parser.add_argument("--email", help="Contact address for NCBI's User-Agent")
    args = parser.parse_args()
    now = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    sources, snapshots = ROOT / "sources", ROOT / "sources" / "snapshots"
    if snapshots.exists() and any(snapshots.iterdir()):
        raise SystemExit("sources/snapshots is not empty; remove it to rebuild")
    snapshots.mkdir(parents=True, exist_ok=True)
    raw = args.civic.read_bytes() if args.civic else urllib.request.urlopen(CIVIC_URL, timeout=300).read()
    tsv = sources / "civic-nightly.tsv"
    tsv.write_bytes(raw)
    rows = civic_rows(tsv)
    plain = literature.http_fetch(args.email)

    def fetch(url: str) -> bytes:
        for attempt in range(4):  # NCBI answers 429 or 5xx under load; back off and retry
            try:
                time.sleep(0.15)
                return plain(url)
            except urllib.error.HTTPError as exc:
                if exc.code < 429 or attempt == 3:
                    raise
                time.sleep(2 ** (attempt + 1))
        raise AssertionError("unreachable")

    works: dict[str, dict] = {}
    pinned: set[str] = set()

    def resolve(pmid: str) -> dict:
        entry = literature.resolve(f"pmid:{pmid}", snapshots, fetch, now, resolver="ncbi", compress=True)
        print(f"pmid:{pmid} fulltext={bool(entry['fulltext_sha256'])} license={entry['license']}", flush=True)
        return entry

    by_paper: dict[str, list[dict]] = {}
    for row in rows:
        by_paper.setdefault(row["citation_id"], []).append(row)
    uids = pmc_uids(sorted(by_paper, key=int), fetch)
    licensed = openly_licensed(sorted(set(uids.values()), key=int), fetch)
    print(f"{len(by_paper)} papers, {len(uids)} in PMC, {len(licensed)} under CC BY or CC0", flush=True)
    strata = {"does_not_support": [], "supports_only": []}
    for pmid, items in by_paper.items():
        if uids.get(pmid) not in licensed:
            continue
        dissent = any(r["evidence_direction"] == "Does Not Support" for r in items)
        strata["does_not_support" if dissent else "supports_only"].append(pmid)
    corpus: dict[str, str] = {}
    for name, pmids in strata.items():
        for pmid in sorted(pmids, key=keyed):
            if sum(s == name for s in corpus.values()) >= TARGETS[name]:
                break
            entry = resolve(pmid)
            if keep(entry, snapshots):
                works[f"pmid:{pmid}"] = entry
                pinned |= {entry["metadata_sha256"], entry["fulltext_sha256"]}
                corpus[pmid] = name
            else:
                discard(entry, snapshots, pinned)

    search = literature._eutils("esearch", db="pubmed", term=RETRACTED_QUERY, retmax="200", retmode="json")
    found = json.loads(fetch(search))["esearchresult"]["idlist"]
    retracted_uids = pmc_uids(found, fetch)
    retracted_licensed = openly_licensed(sorted(set(retracted_uids.values()), key=int), fetch)
    candidates = [pmid for pmid in found if retracted_uids.get(pmid) in retracted_licensed]
    retracted: list[str] = []
    for pmid in sorted(candidates, key=keyed):
        if len(retracted) >= RETRACTED_TARGET:
            break
        entry = resolve(pmid)
        meta = literature.parse_metadata("ncbi", gzip.decompress((snapshots / f"{entry['metadata_sha256']}.json.gz").read_bytes()))
        if entry["fulltext_sha256"] and entry["license"] in OPEN_LICENSES and meta["retracted"]:
            works[f"pmid:{pmid}"] = entry
            pinned |= {entry["metadata_sha256"], entry["fulltext_sha256"]}
            retracted.append(pmid)
        else:
            discard(entry, snapshots, pinned)
    for pmid in FAKE_PMIDS:
        entry = resolve(pmid)
        works[f"pmid:{pmid}"] = entry
        pinned.add(entry["metadata_sha256"])

    catalog = {"version": 1, "works": dict(sorted(works.items()))}
    (snapshots / literature.CATALOG).write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n",
                                                encoding="utf-8", newline="\n")
    kept_rows = [r for r in rows if r["citation_id"] in corpus]
    projection = "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n"
                         for r in sorted(kept_rows, key=lambda r: int(r["evidence_id"]))).encode()
    (sources / "civic-evidence.jsonl.gz").write_bytes(gzip.compress(projection, mtime=0))
    tsv.unlink()
    manifest = {
        "civic": {"url": CIVIC_URL, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "retrieved_at": now,
                  "license": "CC0 1.0", "rows_used": len(kept_rows),
                  "projection_sha256": hashlib.sha256(projection).hexdigest()},
        "resolver": "NCBI E-utilities (esummary, esearch, efetch db=pmc)", "retrieved_at": now,
        "selection": {"key": KEY, "targets": TARGETS, "retracted_target": RETRACTED_TARGET,
                      "licence_filter": LICENCE_FILTER, "papers_in_pmc": len(uids), "papers_openly_licensed": len(licensed),
                      "retracted_query": RETRACTED_QUERY, "licences_kept": sorted(OPEN_LICENSES)},
        "corpus": {pmid: {"stratum": corpus[pmid], "license": works[f"pmid:{pmid}"]["license"]} for pmid in sorted(corpus, key=int)},
        "retracted": {pmid: {"license": works[f"pmid:{pmid}"]["license"]} for pmid in sorted(retracted, key=int)},
        "nonexistent_pmids": FAKE_PMIDS,
    }
    (sources / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"corpus {len(corpus)} papers ({sum(s == 'does_not_support' for s in corpus.values())} with dissent), "
          f"{len(retracted)} retracted, {len(FAKE_PMIDS)} nonexistent PMIDs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
