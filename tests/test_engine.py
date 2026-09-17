import copy
import json
from pathlib import Path

from bioevidence_validator.engine import generate_json_schema, validate_record


ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    return json.loads((ROOT / "examples" / "canine_breed" / name).read_text())


def test_linkml_schema_generation_has_profile_root():
    schema = generate_json_schema()
    assert "CanineBreedRecord" in schema["$defs"]


def test_valid_catalog_record_is_admitted():
    report = validate_record(load("valid_labrador.json"))
    assert report["schema_valid"] is True
    assert report["overall_status"] == "admitted"
    assert report["findings"] == []
    assert {x["admission_status"] for x in report["use_decisions"]} == {"admitted"}


def test_ambiguous_source_label_is_not_admitted():
    report = validate_record(load("ambiguous_boxer.json"))
    assert report["schema_valid"] is True
    assert report["overall_status"] == "rejected"
    codes = {x["rule_id"] for x in report["findings"]}
    assert {"CBR004", "CBR005", "CBR006", "CBR008", "CBR010", "CBR014"} <= codes
    assert {x["use"]: x["admission_status"] for x in report["use_decisions"]} == {
        "source_sample_mapping": "rejected",
        "training_label": "rejected",
    }


def test_changed_source_bytes_are_rejected():
    record = load("valid_labrador.json")
    record["source_artifacts"][0]["observed_sha256"] = "d" * 64
    report = validate_record(record)
    assert report["overall_status"] == "rejected"
    assert "CBR009" in {x["rule_id"] for x in report["findings"]}


def test_missing_required_schema_field_stops_policy_evaluation():
    record = load("valid_labrador.json")
    del record["statement"]["object_breed"]["concept_id"]
    report = validate_record(record)
    assert report["schema_valid"] is False
    assert {x["rule_id"] for x in report["findings"]} == {"SCHEMA"}


def test_contradictory_evidence_requires_review_for_catalog_use():
    record = load("valid_labrador.json")
    line = copy.deepcopy(record["statement"]["evidence_lines"][0])
    line["id"] = "bioev:line-labrador-contradiction"
    line["direction"] = "contradicts"
    record["statement"]["evidence_lines"].append(line)
    report = validate_record(record)
    assert report["overall_status"] == "review_required"
    assert {"CBR010", "CBR012"} <= {x["rule_id"] for x in report["findings"]}
