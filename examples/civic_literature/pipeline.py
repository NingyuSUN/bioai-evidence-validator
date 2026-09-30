"""CIViC literature case: records citing pinned papers, and the negative controls of issue #20."""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import re
from pathlib import Path

from bioevidence_validator.grounding import SnapshotStore
from bioevidence_validator.literature import CATALOG, LiteratureGrounder, identifier, jats_blocks, jats_paragraphs

ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / "sources"
KEY = "bioai-civic-literature-v1"
SCOPE = ["NCBITaxon:9606"]
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
AUXILIARIES = ("was", "were", "is", "are", "did", "does", "do", "could", "can", "may", "might", "would", "will",
               "had", "has", "have")
SPECIES = {"patients": "mice", "patient": "mouse", "humans": "mice", "human": "murine", "mice": "patients",
           "mouse": "human", "murine": "human", "rats": "patients", "rat": "human"}


def keyed(text: str) -> str:
    return hashlib.sha256(f"{KEY}:{text}".encode()).hexdigest()


class Corpus:
    """The pinned snapshots, catalog and CIViC projection, all hash-checked on load."""

    def __init__(self, root: Path = SOURCES):
        self.manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        projection = gzip.decompress((root / "civic-evidence.jsonl.gz").read_bytes())
        if hashlib.sha256(projection).hexdigest() != self.manifest["civic"]["projection_sha256"]:
            raise ValueError("CIViC projection hash mismatch")
        self.evidence = [json.loads(line) for line in projection.decode("utf-8").splitlines()]
        self.store = SnapshotStore.from_directory(root / "snapshots")
        self.catalog = json.loads((root / "snapshots" / CATALOG).read_text(encoding="utf-8"))
        for key, entry in self.catalog["works"].items():
            for sha in (entry["metadata_sha256"], entry["fulltext_sha256"]):
                if sha and not self.store.verified(sha):
                    raise ValueError(f"Snapshot for {key} is missing or changed")

    def grounder(self) -> LiteratureGrounder:
        return LiteratureGrounder(self.store, self.catalog)

    def blocks(self, pmid: str) -> list[tuple[str, str, str]]:
        entry = self.catalog["works"][f"pmid:{pmid}"]
        return jats_blocks(self.store.get(entry["fulltext_sha256"]) or b"")

    def paragraphs(self, pmid: str) -> list[tuple[str, str]]:
        entry = self.catalog["works"][f"pmid:{pmid}"]
        return jats_paragraphs(self.store.get(entry["fulltext_sha256"]) or b"")

    def title(self, pmid: str) -> str:
        from bioevidence_validator.literature import parse_metadata
        entry = self.catalog["works"][f"pmid:{pmid}"]
        return parse_metadata(entry["resolver"], self.store.get(entry["metadata_sha256"]) or b"")["title"]

    def pin(self, record: dict) -> dict:
        """What `bioevidence ground` does, offline, for identifiers already in the catalog."""
        record = copy.deepcopy(record)
        for source in record["source_artifacts"]:
            entry = self.catalog["works"].get(identifier(source["uri"]) or "")
            if entry:
                source["sha256"] = source["observed_sha256"] = entry["fulltext_sha256"] or entry["metadata_sha256"]
                source["retrieved_at"] = entry["retrieved_at"]
        return record


def attribution(corpus: Corpus) -> str:
    """Credits for every pinned paper (CC BY requires attribution), from the pinned NCBI metadata."""
    lines = ["# Attribution", "",
             "The full texts in `snapshots/` are open-access articles from PubMed Central, redistributed unchanged "
             "(gzip-compressed) under the licences listed. CIViC evidence (`civic-evidence.jsonl.gz`) is CC0 "
             "(https://civicdb.org). NCBI metadata responses are public.", "",
             "| PMID | Article | Licence |", "|---|---|---|"]
    for group in ("corpus", "retracted"):
        for pmid in sorted(corpus.manifest[group], key=int):
            entry = corpus.catalog["works"][f"pmid:{pmid}"]
            meta = json.loads(corpus.store.get(entry["metadata_sha256"]) or b"{}")["result"][pmid]
            authors = [a["name"] for a in meta.get("authors", []) if a.get("authtype") == "Author"]
            who = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
            article = f"{who.rstrip('.')}. {meta.get('title', '').rstrip('.')}. *{meta.get('source', '')}* {meta.get('pubdate', '')}"
            note = " (retracted; kept as a negative control)" if group == "retracted" else ""
            lines.append(f"| [{pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/) | {article.replace('|', '/')} | "
                         f"{entry['license'].upper()}{note} |")
    return "\n".join(lines) + "\n"


def quote_for(corpus: Corpus, pmid: str, gene: str | None) -> tuple[str, str] | None:
    """A real sentence of 12-60 words from the paper's body, preferring one naming the gene; keyed-hash order."""
    candidates = []
    for pid, text in corpus.paragraphs(pmid):
        for sentence in SENTENCE.split(text):
            words = sentence.split()
            if 12 <= len(words) <= 60 and sentence in text:
                candidates.append((not (gene and re.search(rf"\b{re.escape(gene)}\b", sentence)), keyed(pid + sentence),
                                   pid, sentence))
    if not candidates:
        return None
    _, _, pid, sentence = min(candidates)
    return pid, sentence


def record(pmid: str, title: str, item: dict, quote: tuple[str, str], method: str = "manual_curation") -> dict:
    pid, text = quote
    direction = "supports" if item["evidence_direction"] == "Supports" else "does_not_support"
    return {
        "record_id": f"bioev:civic-{item['evidence_id']}", "profile_id": "civic-literature",
        "statement": {"id": f"bioev:civic-statement-{item['evidence_id']}",
                      "subject": {"id": f"civic.mp:{item['molecular_profile_id']}", "label": item["molecular_profile"],
                                  "entity_type": "molecular_profile"},
                      "predicate": f"{direction}_significance",
                      "object": {"id": f"civic.eid:{item['evidence_id']}",
                                 "label": f"{item['significance']} in {item['disease']}"
                                          + (f" ({item['therapies']})" if item["therapies"] else ""),
                                 "entity_type": "clinical_significance"},
                      "scope": list(SCOPE), "statement_status": "proposed",
                      "evidence_lines": [{"id": "bioev:quote-line", "direction": "supports",
                                          "evidence_item_ids": ["bioev:quote-1"]}]},
        "source_artifacts": [{"id": "bioev:paper", "title": title, "source_type": "publication", "uri": f"pmid:{pmid}",
                              "version": "PMC JATS", "retrieved_at": "2026-01-01T00:00:00Z", "sha256": "0" * 64}],
        "evidence_items": [{"id": "bioev:quote-1", "source_artifact_id": "bioev:paper", "locator": f"#{pid}",
                            "extracted_text": text, "evidence_type": "publication_quote", "extraction_method": method,
                            "scope": list(SCOPE)}],
        "adjudications": [], "requested_uses": ["research_summary"],
    }


def negate(text: str) -> str | None:
    if re.search(r"\bnot\b", text):
        return re.sub(r"\s*\bnot\b", "", text, count=1)
    match = re.search(rf"\b({'|'.join(AUXILIARIES)})\b", text)
    return text[:match.end()] + " not" + text[match.end():] if match else None


def swap_species(text: str) -> str | None:
    match = re.search(rf"\b({'|'.join(SPECIES)})\b", text, flags=re.IGNORECASE)
    if not match:
        return None
    word = match.group(0)
    new = SPECIES[word.lower()]
    return text[:match.start()] + (new.capitalize() if word[0].isupper() else new) + text[match.end():]


def drop_word(text: str) -> str:
    words = text.split()
    return " ".join(words[:len(words) // 2] + words[len(words) // 2 + 1:])


def controls(base: dict, other_pmid: str, fake_pmid: str) -> dict[str, dict | None]:
    """The AI-specific negative controls of issue #20, derived from one verified base record."""
    quote = base["evidence_items"][0]["extracted_text"]

    def with_uri(uri: str) -> dict:
        changed = copy.deepcopy(base)
        changed["source_artifacts"][0]["uri"] = uri
        return changed

    def with_quote(text: str | None) -> dict | None:
        if text is None:
            return None
        changed = copy.deepcopy(base)
        changed["evidence_items"][0]["extracted_text"] = text
        return changed

    return {"fabricated_identifier": with_uri(f"pmid:{fake_pmid}"),
            "real_identifier_wrong_paper": with_uri(f"pmid:{other_pmid}"),
            "altered_quote": with_quote(drop_word(quote)),
            "negation_flip": with_quote(negate(quote)),
            "species_swap": with_quote(swap_species(quote))}
