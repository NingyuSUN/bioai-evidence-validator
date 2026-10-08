"""Build the pinned corpus for the extraction experiment (#21) from CIViC, NCBI and the Disease Ontology (uses the
network; run once).

    uv run --frozen python examples/civic_extraction/prepare_source.py --email you@example.org

Steps, all recorded in sources/manifest.json:
1. CIViC's nightly accepted evidence (CC0), pinned by SHA-256: PubMed-sourced, unflagged items with a direction.
2. Papers PMC lists under CC BY or CC0, minus every paper already pinned by the CIViC literature case (its papers
   make up the literature benchmark's unrun test set). In keyed-hash order, each is resolved with NCBI E-utilities
   and kept if its own JATS licence is CC BY or CC0, it has a body, it is not retracted, and its text is at most
   MAX_WORDS words, until there are PILOT + TEST papers. The first PILOT in keyed order form the pilot split.
3. The Disease Ontology release (CC0), pinned by SHA-256. Gene symbols are checked against the HGNC snapshot
   already pinned by the single-cell case, by hash.

Everything the offline steps need is written to sources/: gzip-compressed snapshots named by the SHA-256 of their
uncompressed bytes, the catalog `snapshots/literature.json`, the CIViC rows of the chosen papers, the papers' text
as the models see it, the tasks and the attribution. Downloads stop at a 100 MB cap.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from bioevidence_validator import literature

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
LITERATURE_CASE = REPO / "examples" / "civic_literature"
SINGLECELL_SOURCES = REPO / "examples" / "singlecell_celltype" / "sources"
DOID_URL = "http://purl.obolibrary.org/obo/doid.obo"
KEY = "bioai-civic-extraction-v1"
PILOT, TEST = 10, 40
MAX_WORDS = 12_000  # the longest papers would dominate the model calls; recorded, applied before any result
CAP = 100 * 1024 * 1024


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def keyed(text: str) -> str:
    return hashlib.sha256(f"{KEY}:{text}".encode()).hexdigest()


def save(directory: Path, data: bytes, suffix: str) -> str:
    sha = hashlib.sha256(data).hexdigest()
    (directory / f"{sha}{suffix}.gz").write_bytes(gzip.compress(data, mtime=0))
    return sha


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--civic", type=Path, help="A downloaded nightly TSV; fetched from CIViC if omitted")
    parser.add_argument("--email", help="Contact address for NCBI's User-Agent")
    args = parser.parse_args()
    earlier = load("civic_literature_prepare", LITERATURE_CASE / "prepare_source.py")
    pipeline = load("civic_literature_pipeline", LITERATURE_CASE / "pipeline.py")
    now = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    sources, snapshots = ROOT / "sources", ROOT / "sources" / "snapshots"
    if snapshots.exists() and any(snapshots.iterdir()):
        raise SystemExit("sources/snapshots is not empty; remove it to rebuild")
    snapshots.mkdir(parents=True, exist_ok=True)
    downloaded = 0

    def counted(data: bytes) -> bytes:
        nonlocal downloaded
        downloaded += len(data)
        if downloaded > CAP:
            raise SystemExit(f"download cap of {CAP} bytes reached")
        return data

    plain = literature.http_fetch(args.email)

    def fetch(url: str) -> bytes:
        for attempt in range(4):  # NCBI answers 429 or 5xx under load; back off and retry
            try:
                time.sleep(0.15)
                return counted(plain(url))
            except urllib.error.HTTPError as exc:
                if exc.code < 429 or attempt == 3:
                    raise
                time.sleep(2 ** (attempt + 1))
        raise AssertionError("unreachable")

    raw = args.civic.read_bytes() if args.civic else counted(urllib.request.urlopen(earlier.CIVIC_URL, timeout=300).read())
    tsv = sources / "civic-nightly.tsv"
    tsv.write_bytes(raw)
    rows = earlier.civic_rows(tsv)
    tsv.unlink()
    excluded = set(json.loads((LITERATURE_CASE / "sources" / "manifest.json").read_text(encoding="utf-8"))["corpus"])
    excluded |= set(json.loads((LITERATURE_CASE / "sources" / "manifest.json").read_text(encoding="utf-8"))["retracted"])
    by_paper: dict[str, list[dict]] = {}
    for row in rows:
        by_paper.setdefault(row["citation_id"], []).append(row)
    uids = earlier.pmc_uids(sorted(by_paper, key=int), fetch)
    licensed = earlier.openly_licensed(sorted(set(uids.values()), key=int), fetch)
    candidates = sorted((p for p in by_paper if uids.get(p) in licensed and p not in excluded), key=keyed)
    print(f"{len(by_paper)} papers, {len(uids)} in PMC, {len(licensed)} under CC BY or CC0, "
          f"{len(candidates)} not pinned before", flush=True)

    works: dict[str, dict] = {}
    pinned: set[str] = set()
    chosen: list[str] = []
    skipped: dict[str, int] = {"not open or retracted": 0, "too long": 0}
    for pmid in candidates:
        if len(chosen) == PILOT + TEST:
            break
        entry = literature.resolve(f"pmid:{pmid}", snapshots, fetch, now, resolver="ncbi", compress=True)
        if not earlier.keep(entry, snapshots):
            skipped["not open or retracted"] += 1
            earlier.discard(entry, snapshots, pinned)
            continue
        text = literature.jats_blocks(gzip.decompress((snapshots / f"{entry['fulltext_sha256']}.xml.gz").read_bytes()))
        words = sum(len(t.split()) for _, _, t in text)
        if words > MAX_WORDS:
            skipped["too long"] += 1
            earlier.discard(entry, snapshots, pinned)
            continue
        print(f"pmid:{pmid} kept ({words} words, {entry['license']})", flush=True)
        works[f"pmid:{pmid}"] = entry
        pinned |= {entry["metadata_sha256"], entry["fulltext_sha256"]}
        chosen.append(pmid)
    if len(chosen) < PILOT + TEST:
        raise SystemExit(f"only {len(chosen)} papers qualify")

    doid = counted(urllib.request.urlopen(DOID_URL, timeout=300).read())
    doid_sha = save(snapshots, doid, ".obo")
    version = re.search(rb"^data-version:\s*(\S+)", doid, re.M)
    hgnc = json.loads((SINGLECELL_SOURCES / "manifest.json").read_text(encoding="utf-8"))["hgnc"]

    (snapshots / literature.CATALOG).write_text(json.dumps({"version": 1, "works": dict(sorted(works.items()))},
                                                           indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    kept_rows = sorted((r for r in rows if r["citation_id"] in set(chosen)), key=lambda r: int(r["evidence_id"]))
    projection = "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in kept_rows).encode()
    (sources / "civic-evidence.jsonl.gz").write_bytes(gzip.compress(projection, mtime=0))
    split = {pmid: "pilot" if n < PILOT else "test" for n, pmid in enumerate(chosen)}
    manifest = {
        "civic": {"url": earlier.CIVIC_URL, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                  "retrieved_at": now, "license": "CC0 1.0", "rows_used": len(kept_rows),
                  "projection_sha256": hashlib.sha256(projection).hexdigest()},
        "resolver": "NCBI E-utilities (esummary, esearch, efetch db=pmc)", "retrieved_at": now,
        "selection": {"key": KEY, "pilot": PILOT, "test": TEST, "max_words": MAX_WORDS,
                      "licence_filter": earlier.LICENCE_FILTER, "licences_kept": sorted(earlier.OPEN_LICENSES),
                      "excluded": "papers pinned by examples/civic_literature (the literature benchmark's corpus)",
                      "papers_in_pmc": len(uids), "papers_openly_licensed": len(licensed),
                      "candidates_not_pinned_before": len(candidates), "skipped": skipped},
        "corpus": {pmid: {"split": split[pmid], "license": works[f"pmid:{pmid}"]["license"]}
                   for pmid in sorted(chosen, key=int)},
        "retracted": {},
        "disease_ontology": {"url": DOID_URL, "sha256": doid_sha, "version": version.group(1).decode() if version else None,
                             "retrieved_at": now, "license": "CC0 1.0"},
        "hgnc": {**hgnc, "snapshot_dir": "examples/singlecell_celltype/sources/snapshots"},
        "downloaded_bytes": downloaded,
    }
    (sources / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    corpus = pipeline.Corpus(sources)
    papers = {pmid: [list(b) for b in corpus.blocks(pmid)] for pmid in sorted(chosen, key=int)}
    (sources / "papers.json.gz").write_bytes(gzip.compress(json.dumps(papers, ensure_ascii=False, sort_keys=True)
                                                           .encode("utf-8"), mtime=0))
    tasks = [{"task_id": "x-" + keyed(pmid)[:10], "pmid": pmid, "split": split[pmid], "title": corpus.title(pmid)}
             for pmid in chosen]
    (sources / "tasks.jsonl").write_text("".join(json.dumps(t, ensure_ascii=False) + "\n" for t in tasks),
                                         encoding="utf-8", newline="\n")
    (sources / "ATTRIBUTION.md").write_text(pipeline.attribution(corpus).replace(
        "| PMID | Article | Licence |", "The Disease Ontology (`*.obo.gz`) is CC0 (https://disease-ontology.org).\n\n"
        "| PMID | Article | Licence |"), encoding="utf-8", newline="\n")
    print(f"corpus {len(chosen)} papers ({PILOT} pilot, {TEST} test), {len(kept_rows)} CIViC items, "
          f"DOID {manifest['disease_ontology']['version']}, {downloaded / 1e6:.1f} MB downloaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
