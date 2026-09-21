import copy
import hashlib
import json
from pathlib import Path

import pytest
import yaml
from bioevidence_validator.engine import RecordValidator, generate_json_schema, validate_record, profile_path

ROOT = Path(__file__).resolve().parents[1]


def load(path="general/curated_assertion.json"):
    return json.loads((ROOT / "examples" / path).read_text(encoding="utf-8"))


@pytest.mark.parametrize("path,profile,status", [
    ("general/curated_assertion.json", "general", "admitted"),
    ("literature_claim/curated_association.json", "literature-claim", "admitted"),
    ("literature_claim/llm_only.json", "literature-claim", "review_required"),
    ("dataset_label/curated_sample_label.json", "dataset-label", "admitted"),
    ("dataset_label/missing_sample_link.json", "dataset-label", "rejected"),
    ("custom_profile/assay_record.json", ROOT / "examples/custom_profile/assay.yaml", "admitted"),
])
def test_domain_examples(path, profile, status):
    report = validate_record(load(path), profile=profile)
    assert report["schema_valid"]
    assert report["overall_status"] == status


def test_schema_has_generic_root_and_no_breed_contract():
    schema = generate_json_schema()
    assert "BioEvidenceRecord" in schema["$defs"]
    assert "breed" not in json.dumps(schema).lower()


@pytest.mark.parametrize("case,code,status", [
    ("changed_hash", "BEV002", "rejected"),
    ("contradiction", "BEV004", "review_required"),
    ("no_support", "BEV006", "review_required"),
    ("scope_mismatch", "BEV005", "rejected"),
    ("llm", "BEV008", "review_required"),
    ("string_match", "BEV009", "review_required"),
    ("mixed_weak", "BEV013", "review_required"),
    ("dangling_unused_item", "RECORD_INTEGRITY", "rejected"),
    ("dangling_line", "RECORD_INTEGRITY", "rejected"),
    ("duplicate_line_ref", "RECORD_INTEGRITY", "rejected"),
    ("duplicate_scope", "RECORD_INTEGRITY", "rejected"),
    ("blank_label", "SCHEMA", "rejected"),
    ("blank_locator", "SCHEMA", "rejected"),
    ("bad_timestamp", "SCHEMA", "rejected"),
    ("missing_id", "SCHEMA", "rejected"),
])
def test_evidence_faults(case, code, status):
    record = load()
    item = record["evidence_items"][0]
    line = record["statement"]["evidence_lines"][0]
    if case == "changed_hash": record["source_artifacts"][0]["observed_sha256"] = "b" * 64
    elif case == "contradiction":
        extra = copy.deepcopy(line); extra.update(id="bioev:contradiction", direction="contradicts")
        record["statement"]["evidence_lines"].append(extra)
    elif case == "no_support": line["direction"] = "neutral"
    elif case == "scope_mismatch": item["scope"].append("cohort:another")
    elif case == "llm": item["extraction_method"] = "llm_extraction"
    elif case == "string_match": item["extraction_method"] = "normalized_string_match"
    elif case == "mixed_weak":
        item["extraction_method"] = "llm_extraction"
        extra = copy.deepcopy(item); extra.update(id="bioev:extra", extraction_method="normalized_string_match")
        record["evidence_items"].append(extra); line["evidence_item_ids"].append(extra["id"])
    elif case == "dangling_unused_item":
        extra = copy.deepcopy(item); extra.update(id="bioev:unused", source_artifact_id="bioev:absent")
        record["evidence_items"].append(extra)
    elif case == "dangling_line": line["evidence_item_ids"] = ["bioev:absent"]
    elif case == "duplicate_line_ref": line["evidence_item_ids"] *= 2
    elif case == "duplicate_scope": item["scope"] *= 2
    elif case == "blank_label": record["statement"]["subject"]["label"] = "  "
    elif case == "blank_locator": item["locator"] = " "
    elif case == "bad_timestamp": record["source_artifacts"][0]["retrieved_at"] = "yesterday"
    elif case == "missing_id": del record["statement"]["object"]["id"]
    report = validate_record(record)
    assert report["overall_status"] == status
    assert code in {x["rule_id"] for x in report["findings"]}


@pytest.mark.parametrize("direction", ["neutral", "contradicts"])
def test_non_supporting_evidence_does_not_satisfy_required_types(direction):
    record = load("dataset_label/curated_sample_label.json")
    line = record["statement"]["evidence_lines"][0]
    link = line["evidence_item_ids"].pop()
    record["statement"]["evidence_lines"].append({"id": "bioev:extra", "direction": direction, "evidence_item_ids": [link]})
    report = validate_record(record, profile="dataset-label")
    assert "BEV007" in {f["rule_id"] for f in report["findings"]}
    assert report["overall_status"] == "rejected"


def test_unrelated_manual_item_does_not_hide_llm_only_support():
    record = load("literature_claim/llm_only.json")
    extra = copy.deepcopy(record["evidence_items"][0]); extra.update(id="bioev:unused", extraction_method="manual_curation")
    record["evidence_items"].append(extra)
    assert validate_record(record, profile="literature-claim")["overall_status"] == "review_required"


def test_admission_is_per_use_and_human_acceptance_is_scoped():
    record = load("dataset_label/curated_sample_label.json")
    record["requested_uses"] = ["reference_annotation", "training_data", "external_validation"]
    # Independence evidence alone cannot extend training approval to external validation.
    item = copy.deepcopy(record["evidence_items"][0]); item.update(id="bioev:independence", evidence_type="independent_cohort_review")
    record["evidence_items"].append(item)
    record["statement"]["evidence_lines"][0]["evidence_item_ids"].append(item["id"])
    report = validate_record(record, profile="dataset-label")
    assert {d["use"]: d["admission_status"] for d in report["use_decisions"]} == {
        "reference_annotation": "admitted", "training_data": "admitted", "external_validation": "rejected"}
    assert next(d for d in report["use_decisions"] if d["use"] == "external_validation")["reason_codes"] == ["BEV010"]


@pytest.mark.parametrize("case", ["wrong_statement", "unknown_use", "duplicate_use", "software", "blank_rationale", "missing_time"])
def test_unqualified_adjudication_never_counts_as_human_acceptance(case):
    record = load("dataset_label/curated_sample_label.json")
    review = record["adjudications"][0]
    if case == "wrong_statement": review["statement_id"] = "bioev:another"
    elif case == "unknown_use": review["applies_to_uses"] = ["anything"]
    elif case == "duplicate_use": review["applies_to_uses"] *= 2
    elif case == "software": review["reviewer"]["agent_type"] = "software"
    elif case == "blank_rationale": review["rationale"] = " "
    else: del review["decided_at"]
    assert validate_record(record, profile="dataset-label")["overall_status"] == "rejected"


def test_scoped_rejection_does_not_block_unrelated_use():
    record = load("dataset_label/curated_sample_label.json")
    record["adjudications"][0]["decision"] = "reject"
    record["requested_uses"] = ["training_data", "reference_annotation"]
    report = validate_record(record, profile="dataset-label")
    assert [d["admission_status"] for d in report["use_decisions"]] == ["rejected", "admitted"]


def test_input_digest_covers_canonical_record():
    record = load(); report = validate_record(record)
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert report["input_sha256"] == hashlib.sha256(encoded).hexdigest()
    record["record_id"] += "-changed"
    assert validate_record(record)["input_sha256"] != report["input_sha256"]


def test_context_compiles_once_and_snapshots_profile(tmp_path, monkeypatch):
    from bioevidence_validator import engine
    calls = []; original = engine.generate_json_schema
    def counted(*a, **kw):
        calls.append(1); return original(*a, **kw)
    monkeypatch.setattr(engine, "generate_json_schema", counted)
    path = tmp_path / "profile.yaml"; path.write_bytes(profile_path().read_bytes())
    context = RecordValidator(profile=path); first = context.validate(load())
    path.write_text("broken: profile", encoding="utf-8")
    first["schema_sources"][0]["sha256"] = "tampered"
    after = context.validate(load())
    assert len(calls) == 1
    assert after["overall_status"] == "admitted"
    assert after["profile_sha256"] == first["profile_sha256"]
    assert after["schema_sources"][0]["sha256"] != "tampered"


def test_custom_schema_cannot_relax_baseline(tmp_path):
    schema = tmp_path / "loose.yaml"
    schema.write_text("id: https://example.org/loose\nname: loose\nprefixes:\n  linkml: https://w3id.org/linkml/\nimports: [linkml:types]\ndefault_range: string\nclasses:\n  Loose:\n    tree_root: true\n    attributes:\n      requested_uses:\n        multivalued: true\n", encoding="utf-8")
    report = RecordValidator(schema_path=schema).validate({"requested_uses": ["knowledge_base"]})
    assert report["overall_status"] == "rejected"
    assert [s["role"] for s in report["schema_sources"]] == ["baseline", "extension"]


def test_schema_extension_adds_constraints_and_changes_audit_hash(tmp_path):
    from bioevidence_validator.engine import default_schema_path
    schema = yaml.safe_load(default_schema_path().read_bytes())
    schema["slots"]["predicate"]["pattern"] = "^custom_relation$"
    path = tmp_path / "restricted.yaml"; path.write_text(yaml.safe_dump(schema), encoding="utf-8")
    report = validate_record(load(), schema_path=path)
    assert report["overall_status"] == "rejected"
    assert report["schema_sha256"] != validate_record(load())["schema_sha256"]
