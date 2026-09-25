"""VBO-specific ingestion and benchmark helpers, deliberately outside the generic engine."""
from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from bioevidence_validator.engine import Finding, decide_uses

ROOT = Path(__file__).resolve().parent
QUALITY_CODES = {"BEV008", "BEV009", "BEV013"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalized(name: str) -> str:
    return " ".join(name.casefold().split())


class DogNames:
    def __init__(self, root: Path = ROOT):
        self.root = root
        self.manifest = json.loads((root / "sources/manifest.json").read_text(encoding="utf-8"))
        raw = (root / "sources/vbo-dogs.json").read_bytes()
        if digest(raw) != self.manifest["projection_sha256"]:
            raise ValueError("Frozen VBO projection hash mismatch")
        rows = json.loads(raw)
        self.terms = {row["id"]: row for row in rows}
        if len(self.terms) != len(rows) or len(rows) != self.manifest["term_count"]:
            raise ValueError("Duplicate IDs or incorrect VBO term count")
        self.index = defaultdict(set)
        for row in rows:
            for label in [row["name"], *row["exact_synonyms"]]:
                self.index[normalized(label)].add(row["id"])

    def candidates(self, query: str) -> list[str]:
        return sorted(self.index.get(normalized(query), set()))

    def record(self, query: str, case_id: str) -> dict:
        candidates = self.candidates(query)
        if not candidates:
            raise ValueError(f"No exact VBO dog-name candidate for {query!r}")
        # The first candidate only fills the proposed object; ambiguous mappings lack
        # uniqueness evidence and cannot be automatically admitted by this profile.
        target = self.terms[candidates[0]]
        scope = ["NCBITaxon:9615", "VBO:" + self.manifest["release"]]
        source_id = "bioev:vbo-dog-projection"
        method = "deterministic_parser"  # Exact retrieval of ontology assertions, not biological verification.
        base = {"source_artifact_id": source_id, "extraction_method": method,
                "created_by": {"id": "bioev:vbo-importer", "agent_type": "software"}, "scope": scope}
        term_item = {**copy.deepcopy(base), "id": "bioev:term", "evidence_type": "ontology_name_assertion",
                     "locator": f"term:{target['id']};upstream-line:{target['upstream_line']}",
                     "extracted_text": json.dumps({"query": query, "id": target["id"], "name": target["name"]}, ensure_ascii=False)}
        resolution = {**copy.deepcopy(base), "id": "bioev:resolution",
                      "evidence_type": "unique_label_resolution" if len(candidates) == 1 else "ambiguous_label_resolution",
                      "locator": "name-index:" + normalized(query),
                      "extracted_text": json.dumps({"candidate_ids": candidates, "matching": "casefold+whitespace; names and EXACT synonyms"})}
        return {
            "record_id": "bioev:" + case_id, "profile_id": "vbo-canine-name",
            "statement": {"id": "bioev:statement-" + case_id,
                          "subject": {"id": "bioev:name-" + digest(query.encode())[:16], "label": query, "entity_type": "source_name"},
                          "predicate": "maps_to_ontology_term",
                          "object": {"id": target["id"], "label": target["name"], "entity_type": "ontology_term"},
                          "scope": scope, "statement_status": "proposed",
                          "evidence_lines": [
                              {"id": "bioev:term-line", "direction": "supports", "evidence_item_ids": ["bioev:term"]},
                              {"id": "bioev:resolution-line", "direction": "supports" if len(candidates) == 1 else "neutral", "evidence_item_ids": ["bioev:resolution"]}]},
            "source_artifacts": [{"id": source_id, "title": "VBO dog-name projection (CC BY 4.0)",
                                  "source_type": "ontology_snapshot", "uri": "urn:sha256:" + self.manifest["projection_sha256"],
                                  "version": self.manifest["release"] + ":dog-name-projection-v1",
                                  "retrieved_at": self.manifest["retrieved_at"],
                                  "sha256": self.manifest["projection_sha256"],
                                  "observed_sha256": digest((self.root / "sources/vbo-dogs.json").read_bytes())}],
            "evidence_items": [term_item, resolution], "adjudications": [], "requested_uses": ["reference_catalog"],
        }


def add_note(record: dict, method="manual_curation"):
    note = copy.deepcopy(record["evidence_items"][0])
    note.update(id="bioev:aux-note", evidence_type="curator_note", extraction_method=method,
                extracted_text="Synthetic auxiliary note for controlled fault injection.")
    record["evidence_items"].append(note)
    record["statement"]["evidence_lines"].append({"id": "bioev:note-line", "direction": "supports", "evidence_item_ids": [note["id"]]})


FAULTS = {
    "required_llm_plus_note": ("review_required", "BEV008"),
    "required_string_plus_note": ("review_required", "BEV009"),
    "required_mixed_weak_plus_note": ("review_required", "BEV013"),
    "weak_unique_resolution": ("review_required", "BEV008"),
    "missing_uniqueness": ("rejected", "BEV007"),
    "source_hash_mismatch": ("rejected", "BEV002"),
    "scope_mismatch": ("rejected", "BEV005"),
    "dangling_reference": ("rejected", "RECORD_INTEGRITY"),
    "explicit_contradiction": ("review_required", "BEV004"),
    "withdrawn_statement": ("rejected", "BEV001"),
}


def perturb(record: dict, kind: str) -> dict:
    record = copy.deepcopy(record)
    record["record_id"] += ":" + kind
    term, resolution = record["evidence_items"][:2]
    if kind.startswith("required_"):
        term["extraction_method"] = "normalized_string_match" if kind == "required_string_plus_note" else "llm_extraction"
        if kind == "required_mixed_weak_plus_note":
            other = copy.deepcopy(term); other.update(id="bioev:weak2", extraction_method="normalized_string_match")
            record["evidence_items"].append(other)
            record["statement"]["evidence_lines"][0]["evidence_item_ids"].append(other["id"])
        add_note(record)
    elif kind == "weak_unique_resolution": resolution["extraction_method"] = "llm_extraction"
    elif kind == "missing_uniqueness":
        record["statement"]["evidence_lines"][1]["direction"] = "neutral"
    elif kind == "source_hash_mismatch": record["source_artifacts"][0]["observed_sha256"] = "0" * 64
    elif kind == "scope_mismatch": term["scope"] = ["NCBITaxon:9685"]
    elif kind == "dangling_reference": term["source_artifact_id"] = "bioev:absent"
    elif kind == "explicit_contradiction":
        record["statement"]["evidence_lines"].append({"id":"bioev:contradiction","direction":"contradicts","evidence_item_ids":[term["id"]]})
    elif kind == "withdrawn_statement": record["statement"]["statement_status"] = "superseded"
    elif kind == "falsified_target":
        # Deliberately beyond the generic validator's supplied-metadata trust boundary.
        record["statement"]["object"] = {"id":"VBO:NOT_A_REAL_TERM","label":"Synthetic nonexistent target","entity_type":"ontology_term"}
    else: raise ValueError(f"Unknown perturbation: {kind}")
    return record


def aggregate_quality_ablation(record: dict, report: dict) -> str:
    """Reproduce the previous aggregate quality gate, leaving other current checks fixed.

    This is an ablation, not an independent implementation or a biological truth model.
    """
    if not report["schema_valid"] or any(f["rule_id"] == "RECORD_INTEGRITY" for f in report["findings"]):
        return report["overall_status"]
    findings = [Finding(**f) for f in report["findings"] if f["rule_id"] not in QUALITY_CODES]
    ids = {i for line in record["statement"]["evidence_lines"] if line["direction"] == "supports" for i in line["evidence_item_ids"]}
    methods = {i["extraction_method"] for i in record["evidence_items"] if i["id"] in ids and set(i["scope"]) == set(record["statement"]["scope"])}
    if methods and methods <= {"llm_extraction", "normalized_string_match"}:
        findings.append(Finding("AGGREGATE_WEAK", "review", "Aggregate weak support", "$.evidence_items", record["requested_uses"]))
    states = [x["admission_status"] for x in decide_uses(record["requested_uses"], findings)]
    return "rejected" if "rejected" in states else "review_required" if "review_required" in states else "admitted"


def metrics(rows: list[dict], method: str) -> dict:
    positive = [r for r in rows if r["expected_status"] == "admitted"]
    negative = [r for r in rows if r["expected_status"] != "admitted"]
    false_admissions = sum(r[method] == "admitted" for r in negative)
    false_blocks = sum(r[method] != "admitted" for r in positive)
    return {"n":len(rows), "expected_admitted":len(positive), "expected_non_admitted":len(negative),
            "false_admissions":false_admissions, "false_admission_rate":false_admissions/len(negative) if negative else None,
            "false_blocks":false_blocks, "false_block_rate":false_blocks/len(positive) if positive else None,
            "review_rate":sum(r[method] == "review_required" for r in rows)/len(rows) if rows else None,
            "exact_status_matches":sum(r[method] == r["expected_status"] for r in rows),
            "status_counts":dict(sorted(Counter(r[method] for r in rows).items()))}
