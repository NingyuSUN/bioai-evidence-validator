"""ClinVar-specific ingestion and benchmark helpers, deliberately outside the generic engine."""
from __future__ import annotations

import copy
import gzip
import hashlib
import importlib.util
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from bioevidence_validator.engine import Finding, decide_uses
from bioevidence_validator.grounding import finding

ROOT = Path(__file__).resolve().parent
# Load the sibling module by path: another example also has a prepare_source.py.
_spec = importlib.util.spec_from_file_location("clinvar_prepare_source", ROOT / "prepare_source.py")
_prepare = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_prepare)
DOWNGRADE_TERMS, PLP_TERMS, outcome = _prepare.DOWNGRADE_TERMS, _prepare.PLP_TERMS, _prepare.outcome
USES = ["research_summary", "clinical_reference", "expert_reference"]
QUALITY_CODES = {"BEV008", "BEV009", "BEV013"}
SCOPE = ["NCBITaxon:9606", "origin:germline"]
EVIDENCE_TYPE = {  # per-submission review status -> evidence type; unknown statuses fail closed
    "criteria provided, single submitter": "criteria_based_classification",
    "reviewed by expert panel": "criteria_based_classification",
    "practice guideline": "criteria_based_classification",
    "no assertion criteria provided": "classification_without_criteria",
    "no assertion provided": "record_without_classification",
}
EXPERT_STATUSES = {"reviewed by expert panel", "practice guideline"}
SUBMISSION_TYPES = set(EVIDENCE_TYPE.values())
DERIVED_TYPES = {"multi_submitter_or_expert_review", "expert_review"}
# Minimum aggregate star level NCBI assigned in 2023-09 for each use to count as admitted.
STARS = {"no_criteria": 0, "single_submitter": 1, "multiple_submitters": 2, "expert_panel": 3, "practice_guideline": 4}
USE_MIN_STARS = {"research_summary": 1, "clinical_reference": 2, "expert_reference": 3}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ncbi_expected(stratum: str, use: str) -> str:
    """Admission implied by NCBI's own 2023-09 aggregate review status (an independent implementation)."""
    stars = STARS.get(stratum)  # conflicting interpretations are never admitted
    return "admitted" if stars is not None and stars >= USE_MIN_STARS[use] else "not_admitted"


def direction(classification: str) -> str:
    if classification in PLP_TERMS:
        return "supports"
    return "contradicts" if classification in DOWNGRADE_TERMS else "neutral"


class ClinVarSample:
    def __init__(self, root: Path = ROOT):
        self.root = root
        self.manifest = json.loads((root / "sources/manifest.json").read_text(encoding="utf-8"))
        raw = gzip.decompress((root / self.manifest["projection_file"]).read_bytes())
        self.observed_sha256 = digest(raw)
        if self.observed_sha256 != self.manifest["projection_sha256"] or len(raw) != self.manifest["projection_bytes"]:
            raise ValueError("Frozen ClinVar projection hash mismatch")
        self.cases = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
        if len(self.cases) != self.manifest["variant_count"] or len({c["variation_id"] for c in self.cases}) != len(self.cases):
            raise ValueError("Duplicate variants or incorrect ClinVar sample size")

    def record(self, case: dict) -> dict:
        vid = case["variation_id"]
        base = {"source_artifact_id": "bioev:clinvar-sample", "extraction_method": "deterministic_parser",
                "created_by": {"id": "bioev:clinvar-importer", "agent_type": "software"}, "scope": list(SCOPE)}
        items, lines = [], {"supports": [], "contradicts": [], "neutral": []}
        for sub in case["submissions"]:
            if sub["ReviewStatus"] not in EVIDENCE_TYPE:
                raise ValueError(f"Unmapped ClinVar review status {sub['ReviewStatus']!r} in {sub['SCV']}")
            item = {**copy.deepcopy(base), "id": "bioev:" + sub["SCV"], "evidence_type": EVIDENCE_TYPE[sub["ReviewStatus"]],
                    "locator": f"{sub['SCV']};VariationID:{vid}",
                    "extracted_text": json.dumps({"submitter": sub["Submitter"], "classification": sub["ClinicalSignificance"],
                                                  "review_status": sub["ReviewStatus"], "collection_method": sub["CollectionMethod"],
                                                  "date_last_evaluated": sub["DateLastEvaluated"]}, ensure_ascii=False, sort_keys=True)}
            items.append(item)
            lines[direction(sub["ClinicalSignificance"])].append(item["id"])

        # Transparent importer aggregates, analogous to the VBO uniqueness item: which submissions
        # jointly satisfy "several independent submitters" or "expert review". Dissent stays visible
        # as contradicting lines; the engine, not the importer, decides what dissent means.
        supporting = [s for s in case["submissions"] if s["ClinicalSignificance"] in PLP_TERMS
                      and EVIDENCE_TYPE[s["ReviewStatus"]] == "criteria_based_classification"]
        experts = [s for s in supporting if s["ReviewStatus"] in EXPERT_STATUSES]
        submitters = sorted({s["Submitter"] for s in supporting})
        derived = []
        if experts or len(submitters) >= 2:
            basis = experts or supporting
            derived.append(("bioev:derived-multi", "multi_submitter_or_expert_review", basis,
                            "expert or practice-guideline review" if experts else f"{len(submitters)} distinct submitters"))
        if experts:
            derived.append(("bioev:derived-expert", "expert_review", experts, "expert or practice-guideline review"))
        for item_id, kind, basis, text in derived:
            items.append({**copy.deepcopy(base), "id": item_id, "evidence_type": kind,
                          "locator": "derived:" + ";".join(s["SCV"] for s in basis), "extracted_text": text})
            lines["supports"].append(item_id)

        return {
            "record_id": "bioev:clinvar-" + vid, "profile_id": "clinvar-germline",
            "statement": {"id": "bioev:clinvar-statement-" + vid,
                          "subject": {"id": "clinvar:" + vid, "label": f"ClinVar VariationID {vid} ({case['gene']})",
                                      "entity_type": "sequence_variant"},
                          "predicate": "has_germline_classification",
                          "object": {"id": "bioev:germline-plp", "label": "Pathogenic or likely pathogenic (germline)",
                                     "entity_type": "germline_classification"},
                          "scope": list(SCOPE), "statement_status": "proposed",
                          "evidence_lines": [{"id": f"bioev:{name}-line", "direction": name, "evidence_item_ids": ids}
                                             for name, ids in lines.items() if ids]},
            "source_artifacts": [{"id": "bioev:clinvar-sample", "title": "ClinVar germline classification sample (NCBI)",
                                  "source_type": "registry_snapshot", "uri": "urn:sha256:" + self.manifest["projection_sha256"],
                                  "version": "2023-09:germline-sample-v1", "retrieved_at": self.manifest["retrieved_at"],
                                  "sha256": self.manifest["projection_sha256"], "observed_sha256": self.observed_sha256}],
            "evidence_items": items, "adjudications": [], "requested_uses": list(USES),
        }


def add_note(record: dict) -> None:
    note = {**copy.deepcopy(record["evidence_items"][0]), "id": "bioev:aux-note", "evidence_type": "curator_note",
            "extraction_method": "manual_curation", "extracted_text": "Synthetic auxiliary note for controlled fault injection."}
    record["evidence_items"].append(note)
    record["statement"]["evidence_lines"].append({"id": "bioev:note-line", "direction": "supports", "evidence_item_ids": [note["id"]]})


FAULTS = {
    "llm_classification_plus_note": ("review_required", "BEV008"),
    "string_match_classification_plus_note": ("review_required", "BEV009"),
    "mixed_weak_classification_plus_note": ("review_required", "BEV013"),
    "llm_derived_review": ("review_required", "BEV008"),
    "missing_derived_review": ("rejected", "BEV007"),
    "source_hash_mismatch": ("rejected", "BEV002"),
    "somatic_scope": ("rejected", "BEV005"),
    "dangling_reference": ("rejected", "RECORD_INTEGRITY"),
    "injected_dissent": ("review_required", "BEV004"),
    "withdrawn_statement": ("rejected", "BEV001"),
}


def perturb(record: dict, kind: str) -> dict:
    record = copy.deepcopy(record)
    record["record_id"] += ":" + kind
    items = record["evidence_items"]
    classified = [i for i in items if i["evidence_type"] == "criteria_based_classification"]
    derived = [i for i in items if i["id"].startswith("bioev:derived-")]
    if kind.endswith("_plus_note"):
        for index, item in enumerate(classified):
            if kind.startswith("llm"): item["extraction_method"] = "llm_extraction"
            elif kind.startswith("string"): item["extraction_method"] = "normalized_string_match"
            else: item["extraction_method"] = "llm_extraction" if index % 2 == 0 else "normalized_string_match"
        if kind.startswith("mixed") and len(classified) == 1:
            twin = {**copy.deepcopy(classified[0]), "id": classified[0]["id"] + ":twin", "extraction_method": "normalized_string_match"}
            items.append(twin)
            record["statement"]["evidence_lines"][0]["evidence_item_ids"].append(twin["id"])
        add_note(record)
    elif kind == "llm_derived_review":
        for item in derived: item["extraction_method"] = "llm_extraction"
    elif kind == "missing_derived_review":
        removed = {i["id"] for i in derived}
        record["evidence_items"] = [i for i in items if i["id"] not in removed]
        for line in record["statement"]["evidence_lines"]:
            line["evidence_item_ids"] = [i for i in line["evidence_item_ids"] if i not in removed]
    elif kind == "source_hash_mismatch": record["source_artifacts"][0]["observed_sha256"] = "0" * 64
    elif kind == "somatic_scope": classified[0]["scope"] = ["NCBITaxon:9606", "origin:somatic"]
    elif kind == "dangling_reference": classified[0]["source_artifact_id"] = "bioev:absent"
    elif kind == "injected_dissent":
        dissent = {**copy.deepcopy(classified[0]), "id": "bioev:synthetic-dissent", "locator": "synthetic",
                   "extracted_text": "Synthetic criteria-based 'Uncertain significance' submission."}
        items.append(dissent)
        record["statement"]["evidence_lines"].append({"id": "bioev:synthetic-dissent-line", "direction": "contradicts",
                                                      "evidence_item_ids": [dissent["id"]]})
    elif kind == "withdrawn_statement": record["statement"]["statement_status"] = "superseded"
    elif kind == "omitted_dissent":
        # Beyond the trust boundary: the record stays consistent, but the submissions that disagree are gone.
        dropped = {i for line in record["statement"]["evidence_lines"] if line["direction"] == "contradicts"
                   for i in line["evidence_item_ids"]}
        record["evidence_items"] = [i for i in items if i["id"] not in dropped]
        record["statement"]["evidence_lines"] = [line for line in record["statement"]["evidence_lines"]
                                                 if line["direction"] != "contradicts"]
    elif kind == "fabricated_expert_review":
        # Deliberately beyond the generic validator's trust boundary: an importer that mislabels
        # uncurated submissions and invents an expert review is not detectable from the record alone.
        for item in items: item["evidence_type"] = "criteria_based_classification"
        for item_id, kind_name in [("bioev:fake-multi", "multi_submitter_or_expert_review"), ("bioev:fake-expert", "expert_review")]:
            items.append({**copy.deepcopy(items[0]), "id": item_id, "evidence_type": kind_name, "locator": "fabricated"})
            record["statement"]["evidence_lines"][0]["evidence_item_ids"].append(item_id)
    else:
        raise ValueError(f"Unknown perturbation: {kind}")
    return record


class ClinVarGrounder:
    """Rebuild a variant's evidence from the pinned ClinVar sample and compare the record with it, item by item.

    Extraction methods are not compared: they describe how the record was made, not what the source says.
    """

    name = "clinvar-snapshot"

    def __init__(self, source: ClinVarSample):
        self.source = source
        self.cases = {case["variation_id"]: case for case in source.cases}

    def check(self, record: dict) -> list:
        ours = {a["id"] for a in record["source_artifacts"] if a["sha256"] == self.source.manifest["projection_sha256"]}
        if not ours:
            return []  # the record cites no ClinVar sample; other grounders may apply
        subject = record["statement"]["subject"]["id"]
        case = self.cases.get(subject.removeprefix("clinvar:")) if subject.startswith("clinvar:") else None
        if case is None:
            return [finding(record, "BEV016", "The variant is not in the pinned ClinVar sample.", "$.statement.subject.id")]
        rebuilt = self.source.record(case)["evidence_items"]
        submissions = {i["locator"]: i for i in rebuilt if i["evidence_type"] in SUBMISSION_TYPES}
        derived = {i["evidence_type"]: i for i in rebuilt if i["evidence_type"] in DERIVED_TYPES}
        directions = defaultdict(set)
        for line in record["statement"]["evidence_lines"]:
            for item_id in line["evidence_item_ids"]:
                directions[item_id].add(line["direction"])
        out, cited = [], set()
        for index, item in enumerate(record["evidence_items"]):
            if item["source_artifact_id"] not in ours:
                continue
            path, kind = f"$.evidence_items[{index}]", item["evidence_type"]
            if kind in DERIVED_TYPES:
                want = derived.get(kind)
                if want is None:
                    out.append(finding(record, "BEV017", f"The source submissions do not support {kind} for this variant.", path))
                elif (item["locator"], item["extracted_text"]) != (want["locator"], want["extracted_text"]):
                    out.append(finding(record, "BEV017", "The derived evidence differs from the aggregate recomputed from "
                                                          "the source.", path))
            elif kind in SUBMISSION_TYPES:
                want = submissions.get(item["locator"])
                if want is None:
                    out.append(finding(record, "BEV016", "The cited submission does not exist for this variant in the source.",
                                       path))
                    continue
                cited.add(item["locator"])
                text = json.loads(want["extracted_text"])
                if (kind != want["evidence_type"] or parsed(item.get("extracted_text")) != text
                        or set(item["scope"]) != set(want["scope"])
                        or directions[item["id"]] - {direction(text["classification"])}):
                    out.append(finding(record, "BEV017", "The submission differs from the source (review status, content, "
                                                          "scope or direction).", path))
            else:
                out.append(finding(record, "BEV015", "The ClinVar source cannot confirm this type of evidence item.", path))
        for locator in sorted(set(submissions) - cited):
            out.append(finding(record, "BEV018", f"The source holds a submission the record leaves out ({locator}).",
                               "$.evidence_items"))
        return out


def parsed(text: str | None):
    try:
        return json.loads(text or "null")
    except json.JSONDecodeError:
        return None


def aggregate_quality_ablation(record: dict, report: dict) -> str:
    """The pre-0.4.1 aggregate extraction-method gate with all other current checks fixed (same as the VBO case)."""
    if not report["schema_valid"] or any(f["rule_id"] == "RECORD_INTEGRITY" for f in report["findings"]):
        return report["overall_status"]
    findings = [Finding(**f) for f in report["findings"] if f["rule_id"] not in QUALITY_CODES]
    ids = {i for line in record["statement"]["evidence_lines"] if line["direction"] == "supports" for i in line["evidence_item_ids"]}
    methods = {i["extraction_method"] for i in record["evidence_items"]
               if i["id"] in ids and set(i["scope"]) == set(record["statement"]["scope"])}
    if methods and methods <= {"llm_extraction", "normalized_string_match"}:
        findings.append(Finding("AGGREGATE_WEAK", "review", "Aggregate weak support", "$.evidence_items", record["requested_uses"]))
    states = [x["admission_status"] for x in decide_uses(record["requested_uses"], findings)]
    return "rejected" if "rejected" in states else "review_required" if "review_required" in states else "admitted"


def wilson(events: int, n: int, z: float = 1.959963984540054) -> list[float] | None:
    if not n:
        return None
    p = events / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 6), round(min(1.0, centre + half), 6)]


def outcome_rate(group: dict) -> dict:
    """Destabilization among evaluable outcomes; 'missing' and 'other' are reported but excluded from the denominator."""
    counts = Counter(group["outcomes_2026_09"])
    evaluable = counts["stable_plp"] + counts["conflicting"] + counts["downgraded"]
    events = counts["conflicting"] + counts["downgraded"]
    return {"n": group["n"], "evaluable": evaluable, "destabilized": events,
            "rate": round(events / evaluable, 6) if evaluable else None, "wilson_95": wilson(events, evaluable),
            "outcomes": dict(sorted(counts.items()))}


def stability(cases: list[dict]) -> dict:
    counts = Counter(outcome(c["clinvar_2026_09"]["classification"] if c["clinvar_2026_09"] else None) for c in cases)
    return outcome_rate({"n": len(cases), "outcomes_2026_09": counts})


def metrics(rows: list[dict], method: str) -> dict:
    positive = [r for r in rows if r["expected_status"] == "admitted"]
    negative = [r for r in rows if r["expected_status"] != "admitted"]
    false_admissions = sum(r[method] == "admitted" for r in negative)
    false_blocks = sum(r[method] != "admitted" for r in positive)
    return {"n": len(rows), "expected_admitted": len(positive), "expected_non_admitted": len(negative),
            "false_admissions": false_admissions, "false_blocks": false_blocks,
            "review": sum(r[method] == "review_required" for r in rows),
            "status_counts": dict(sorted(Counter(r[method] for r in rows).items()))}
