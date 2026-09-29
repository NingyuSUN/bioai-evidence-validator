"""Literature grounding: resolve cited papers, pin their metadata and open-access full text, check quotes.

Two steps, as for every source (docs/ENGINEERING.md#source-grounding):

- `ground_record` (uses the network; `bioevidence ground`) resolves each cited PMID, PMCID or DOI with
  Europe PMC (Crossref for a DOI Europe PMC does not know) or with NCBI E-utilities. It stores the
  resolver's response and, for open-access papers, the JATS full text in a snapshot directory under their
  SHA-256, maps each identifier to those snapshots in `literature.json`, and pins the record's source hash.
- `LiteratureGrounder` (offline, during validation) recomputes everything from those snapshot bytes: whether
  the identifier resolved, the paper's title and retraction status, and whether each quote appears in the
  full text (at its paragraph, when the locator names one). The catalog only says which bytes to read.

Findings: BEV015 review (cannot be verified: not grounded, not open access, or no usable quote),
BEV016 error (the identifier does not resolve), BEV017 error (different paper, or the quote is not in it),
BEV019 error (the paper is retracted). Only items whose quote was verified count as verified evidence.
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import __version__
from .engine import Finding
from .grounding import SnapshotStore, finding

CATALOG = "literature.json"
EUROPE_PMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
CROSSREF = "https://api.crossref.org/works/"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
MIN_QUOTE_WORDS = 5  # shorter quotes match almost anywhere and prove little
TITLE_OVERLAP = 0.5  # word-set Jaccard below which a supplied title names a different paper
_PUNCTUATION = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-",
                              "—": "-", "−": "-", " ": " ", " ": " ", " ": " "})


def normalize(text: str) -> str:
    """Unicode NFKC, plain quotes and dashes, single spaces. Case is kept: gene symbols depend on it."""
    return " ".join(unicodedata.normalize("NFKC", text).translate(_PUNCTUATION).split())


def identifier(uri: str) -> str | None:
    """Canonical `pmid:`, `pmcid:` or `doi:` key for a publication URI, or None."""
    value = uri.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/"):
        if value.lower().startswith(prefix):
            value = "doi:" + value[len(prefix):]
    scheme, _, rest = value.partition(":")
    scheme, rest = scheme.lower(), rest.strip()
    if scheme == "pmid" and rest.isdigit():
        return f"pmid:{int(rest)}"
    if scheme == "pmcid" and re.fullmatch(r"(?i)pmc\d+", rest):
        return "pmcid:" + rest.upper()
    if scheme == "doi" and rest.startswith("10."):
        return "doi:" + rest.lower()
    return None


def jats_blocks(data: bytes) -> list[tuple[str, str, str]]:
    """(id, kind, text) for every title ("title") and paragraph ("p") of a JATS article, in document
    order; ids fall back to the element's position. Showing only paragraph ids to a model keeps it from
    citing a section heading instead of the paragraph under it."""
    root = ET.fromstring(data)  # ElementTree never resolves external entities
    out = []
    for n, element in enumerate(root.iter()):
        tag = element.tag.rsplit("}", 1)[-1] if isinstance(element.tag, str) else ""
        if tag in ("p", "title", "article-title"):
            out.append((element.get("id") or f"n{n}", "p" if tag == "p" else "title",
                        normalize("".join(element.itertext()))))
    return out


def jats_paragraphs(data: bytes) -> list[tuple[str, str]]:
    """(id, text) for every title and paragraph of a JATS article, as the grounder checks them."""
    return [(pid, text) for pid, _, text in jats_blocks(data)]


def jats_license(data: bytes) -> str:
    """'cc by', 'cc0' or 'other', from the article's own license statement."""
    root = ET.fromstring(data)
    texts = []
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1] if isinstance(element.tag, str) else ""
        if tag in ("license", "license_ref", "ext-link"):
            texts += [str(v) for v in element.attrib.values()] + ["".join(element.itertext())]
    text = " ".join(texts).lower()
    if "publicdomain/zero" in text or "cc0" in text:
        return "cc0"
    restricted = ("by-nc", "by-nd", "by-sa", "noncommercial", "non-commercial", "noderiv", "sharealike")
    if ("creativecommons.org/licenses/by/" in text or "creative commons attribution" in text) \
            and not any(word in text for word in restricted):
        return "cc by"
    return "other"


def jats_open(data: bytes) -> bool:
    """Whether a JATS document carries the article body (PMC marks restricted articles `restricted-by`)."""
    root = ET.fromstring(data)
    tags = {element.tag.rsplit("}", 1)[-1] for element in root.iter() if isinstance(element.tag, str)}
    return "body" in tags and "restricted-by" not in tags


def parse_metadata(resolver: str, data: bytes) -> dict[str, Any]:
    """What a resolver response says about the paper; recomputed offline from the pinned bytes."""
    body = json.loads(data)
    if resolver == "ncbi":  # an E-utilities esummary (or an empty esearch for an unknown DOI)
        result = body.get("result") or {}
        uids = result.get("uids") or []
        if not uids or "error" in result.get(uids[0], {"error": True}):
            return {"found": False}
        doc = result[uids[0]]
        ids = {a["idtype"]: a["value"] for a in doc.get("articleids", [])}
        pmcid = ids.get("pmc") or ids.get("pmcid")
        return {"found": True, "title": doc.get("title", ""), "pmid": ids.get("pubmed") or ids.get("pmid") or uids[0],
                "pmcid": pmcid.upper() if pmcid else None, "doi": ids.get("doi"),
                "retracted": "Retracted Publication" in doc.get("pubtype", []), "open_access": None, "license": None}
    if resolver == "europepmc":
        results = body.get("resultList", {}).get("result", [])
        if not results:
            return {"found": False}
        hit = results[0]
        types = {t.lower() for t in hit.get("pubTypeList", {}).get("pubType", [])}
        notes = hit.get("commentCorrectionList", {}).get("commentCorrection", [])
        retracted = "retracted publication" in types or any(
            str(c.get("type", "")).lower().startswith("retraction in") for c in notes)
        return {"found": True, "title": hit.get("title", ""), "pmid": hit.get("pmid"), "pmcid": hit.get("pmcid"),
                "doi": hit.get("doi"), "retracted": retracted, "open_access": hit.get("isOpenAccess") == "Y",
                "license": hit.get("license")}
    message = body.get("message") or {}
    if not message:
        return {"found": False}
    updates = message.get("updated-by", []) + message.get("update-to", [])
    return {"found": True, "title": (message.get("title") or [""])[0], "pmid": None, "pmcid": None,
            "doi": message.get("DOI"), "retracted": any(str(u.get("type", "")).lower() == "retraction" for u in updates),
            "open_access": False, "license": None}


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", normalize(text).lower()))


def same_title(supplied: str, pinned: str) -> bool:
    a, b = _words(supplied), _words(pinned)
    return bool(a and b) and len(a & b) / len(a | b) >= TITLE_OVERLAP


class LiteratureGrounder:
    """Check cited publications and their quotes against pinned metadata and full text."""

    name = "literature"

    def __init__(self, store: SnapshotStore, catalog: dict[str, Any]):
        self.store = store
        self.catalog = catalog.get("works", {})

    @classmethod
    def from_directory(cls, directory: Path) -> LiteratureGrounder:
        catalog = json.loads((Path(directory) / CATALOG).read_text(encoding="utf-8"))
        return cls(SnapshotStore.from_directory(directory), catalog)

    def _paper(self, source: dict[str, Any]) -> tuple[dict | None, list[tuple[str, str]], list[tuple[str, str]]]:
        """(metadata, paragraphs, problems) for one publication artifact, all from pinned bytes."""
        key = identifier(source["uri"])
        entry = self.catalog.get(key) if key else None
        if key is None:
            return None, [], [("BEV015", "The publication has no PMID, PMCID or DOI to check.")]
        if entry is None:
            return None, [], [("BEV015", "The publication is not grounded yet; run `bioevidence ground`.")]
        if not self.store.verified(entry["metadata_sha256"]):
            return None, [], [("BEV015", "The pinned resolver response is not in the snapshot store.")]
        meta = parse_metadata(entry["resolver"], self.store.get(entry["metadata_sha256"]) or b"")
        if not meta["found"]:
            return meta, [], [("BEV016", f"{key} does not resolve to a publication.")]
        problems = []
        if meta["retracted"]:
            problems.append(("BEV019", f"{key} is retracted."))
        if source.get("title") and not same_title(source["title"], meta["title"]):
            problems.append(("BEV017", f"{key} is a different paper: {meta['title']!r}."))
        pinned = entry.get("fulltext_sha256") or entry["metadata_sha256"]
        if source["sha256"] != pinned:
            problems.append(("BEV017", "The record's source hash is not the pinned snapshot of this publication."))
        paragraphs: list[tuple[str, str]] = []
        if entry.get("fulltext_sha256") and self.store.verified(entry["fulltext_sha256"]):
            paragraphs = jats_paragraphs(self.store.get(entry["fulltext_sha256"]) or b"")
        return meta, paragraphs, problems

    def _evaluate(self, record: dict[str, Any]) -> tuple[list[Finding], set[str]]:
        findings, verified, papers = [], set(), {}
        for index, source in enumerate(record["source_artifacts"]):
            if source["source_type"] != "publication":
                continue
            meta, paragraphs, problems = self._paper(source)
            papers[source["id"]] = (meta, paragraphs, not problems)
            findings += [finding(record, code, message, f"$.source_artifacts[{index}]") for code, message in problems]
        for index, item in enumerate(record["evidence_items"]):
            if item["source_artifact_id"] not in papers:
                continue
            meta, paragraphs, sound = papers[item["source_artifact_id"]]
            path = f"$.evidence_items[{index}]"
            if not meta or not meta["found"]:
                continue  # already reported on the source
            quote = normalize(item.get("extracted_text") or "")
            if not paragraphs:
                findings.append(finding(record, "BEV015", "No open-access full text is pinned; the quote cannot be "
                                                          "verified.", path))
            elif len(quote.split()) < MIN_QUOTE_WORDS:
                findings.append(finding(record, "BEV015", f"A quote of fewer than {MIN_QUOTE_WORDS} words cannot be "
                                                          "verified meaningfully.", path))
            else:
                anchor = (item.get("locator") or "").rpartition("#")[2]
                located = [text for pid, text in paragraphs if pid == anchor]
                where = located or [text for _, text in paragraphs]
                if any(quote in text for text in where):
                    if sound:
                        verified.add(item["id"])
                elif located and any(quote in text for _, text in paragraphs):
                    findings.append(finding(record, "BEV017", f"The quote is in the paper but not at #{anchor}.", path))
                else:
                    findings.append(finding(record, "BEV017", "The quote does not appear in the cited paper.", path))
        return findings, verified

    def check(self, record: dict[str, Any]) -> list[Finding]:
        return self._evaluate(record)[0]

    def verified_items(self, record: dict[str, Any]) -> set[str]:
        return self._evaluate(record)[1]


# The network step. `fetch` is injectable so that tests never touch the network.

def http_fetch(email: str | None = None) -> Callable[[str], bytes]:
    agent = f"bioai-evidence-validator/{__version__}" + (f" (mailto:{email})" if email else "")

    def fetch(url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": agent, "Accept": "application/json, */*"})
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - fixed https hosts
            data = response.read()
        time.sleep(0.2)  # stay well below the resolvers' rate limits
        return data
    return fetch


def _search_url(key: str) -> str:
    kind, _, value = key.partition(":")
    query = {"pmid": f"EXT_ID:{value} AND SRC:MED", "pmcid": f"PMCID:{value}", "doi": f'DOI:"{value}"'}[kind]
    return f"{EUROPE_PMC}/search?" + urllib.parse.urlencode({"query": query, "resultType": "core", "format": "json",
                                                             "pageSize": 1})


def _eutils(tool: str, **params: str) -> str:
    return f"{EUTILS}/{tool}.fcgi?" + urllib.parse.urlencode({**params, "tool": "bioai-evidence-validator"})


def _save(directory: Path, data: bytes, suffix: str, compress: bool = False) -> str:
    """Content-addressed by the uncompressed bytes; optionally stored gzip-compressed (`<sha>.xml.gz`)."""
    sha = hashlib.sha256(data).hexdigest()
    path = directory / (f"{sha}{suffix}.gz" if compress else f"{sha}{suffix}")
    if not path.exists():
        path.write_bytes(gzip.compress(data, mtime=0) if compress else data)
    return sha


def _metadata(key: str, resolver: str, fetch: Callable[[str], bytes]) -> tuple[str, bytes, list[str]]:
    kind, _, value = key.partition(":")
    if resolver == "ncbi":
        if kind == "doi":
            url = _eutils("esearch", db="pubmed", term=f"{value}[doi]", retmode="json")
            hits = json.loads(fetch(url)).get("esearchresult", {}).get("idlist", [])
            if not hits:
                return "ncbi", b'{"result": {"uids": []}}', [url]
            kind, value, urls = "pmid", hits[0], [url]
        else:
            urls = []
        url = _eutils("esummary", db="pmc" if kind == "pmcid" else "pubmed",
                      id=value[3:] if kind == "pmcid" else value, retmode="json")
        return "ncbi", fetch(url), [*urls, url]
    url = _search_url(key)
    data, urls = fetch(url), [url]
    if not parse_metadata("europepmc", data)["found"] and kind == "doi":
        url = CROSSREF + urllib.parse.quote(value)
        urls.append(url)
        try:
            return "crossref", fetch(url), urls
        except OSError:  # includes HTTP 404 for an unknown DOI
            return "crossref", b'{"message": null}', urls
    return "europepmc", data, urls


def resolve(key: str, directory: Path, fetch: Callable[[str], bytes], now: str, resolver: str = "europepmc",
            compress: bool = False) -> dict[str, Any]:
    """Resolve one identifier, pin the response and any open-access full text, and return its catalog entry.

    `resolver` is "europepmc" (Crossref for DOIs it does not know) or "ncbi" (E-utilities)."""
    used, data, urls = _metadata(key, resolver, fetch)
    entry = {"resolver": used, "metadata_sha256": _save(directory, data, ".json", compress), "fulltext_sha256": None,
             "license": None, "retrieved_at": now, "urls": urls}
    meta = parse_metadata(used, data)
    if meta.get("pmcid") and (used == "ncbi" or meta.get("open_access")):
        url = (_eutils("efetch", db="pmc", id=meta["pmcid"][3:], retmode="xml") if used == "ncbi"
               else f"{EUROPE_PMC}/{meta['pmcid']}/fullTextXML")
        try:
            text = fetch(url)
            if jats_open(text):  # PMC returns only the front matter of articles outside the open-access subset
                entry.update(fulltext_sha256=_save(directory, text, ".xml", compress), license=jats_license(text))
                urls.append(url)
        except (OSError, ET.ParseError):
            pass  # stays unverifiable (BEV015), never silently admitted
    return entry


def ground_record(record: dict[str, Any], directory: Path, fetch: Callable[[str], bytes],
                  now: str | None = None, refresh: bool = False, resolver: str = "europepmc",
                  compress: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve every cited publication, update the directory's catalog, and pin the record's hashes."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / CATALOG
    catalog: dict[str, Any] = (json.loads(path.read_text(encoding="utf-8")) if path.exists()
                               else {"version": 1, "works": {}})
    works: dict[str, Any] = catalog["works"]
    now = now or dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    grounded = json.loads(json.dumps(record))
    for source in grounded["source_artifacts"]:
        key = identifier(source["uri"]) if source["source_type"] == "publication" else None
        if key is None:
            continue
        if refresh or key not in works:
            works[key] = resolve(key, directory, fetch, now, resolver, compress)
        entry = works[key]
        source["sha256"] = source["observed_sha256"] = entry["fulltext_sha256"] or entry["metadata_sha256"]
        source["retrieved_at"] = entry["retrieved_at"]
    path.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return grounded, catalog
