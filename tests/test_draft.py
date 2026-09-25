import copy
import hashlib
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from bioevidence_validator import build_record, draft_json_schema, load_draft, validate_record
from bioevidence_validator.cli import main

ROOT = Path(__file__).resolve().parents[1]
DRAFTS = ROOT / "examples" / "drafts"
SOURCE_SHA256 = hashlib.sha256((DRAFTS / "synthetic_paper.txt").read_bytes()).hexdigest()


def draft(name="llm_claim.yaml"):
    return load_draft(DRAFTS / name)


def build(value):
    return build_record(value, base_dir=DRAFTS)


def statuses(value):
    report = validate_record(build(value), profile=value["profile"])
    return report["overall_status"], {d["use"]: d["admission_status"] for d in report["use_decisions"]}, report


def test_llm_only_draft_requires_review():
    overall, uses, report = statuses(draft())
    assert overall == "review_required" and uses == {"research_summary": "review_required"}
    assert [f["rule_id"] for f in report["findings"]] == ["BEV008"]


def test_reviewed_draft_is_admitted_for_both_uses():
    overall, uses, _ = statuses(draft("reviewed_claim.yaml"))
    assert overall == "admitted" and uses == {"research_summary": "admitted", "knowledge_base": "admitted"}


def test_dataset_label_reference_draft_is_admitted():
    overall, uses, _ = statuses(draft("dataset_label_reference.yaml"))
    assert overall == "admitted"
    assert uses == {"reference_annotation": "admitted"}


def test_dataset_label_training_draft_requires_human_acceptance():
    overall, uses, report = statuses(draft("dataset_label_training_unreviewed.yaml"))
    assert overall == "rejected"
    assert uses == {"training_data": "rejected"}
    assert {f["rule_id"] for f in report["findings"]} == {"BEV010"}


def test_build_expands_structure_and_hashes_local_file():
    record = build(draft())
    source, = record["source_artifacts"]
    assert source["sha256"] == SOURCE_SHA256 and "observed_sha256" not in source
    item, = record["evidence_items"]
    assert item["source_artifact_id"] == source["id"]
    line, = record["statement"]["evidence_lines"]
    assert line["direction"] == "supports" and line["evidence_item_ids"] == [item["id"]]
    assert record["statement"]["statement_status"] == "proposed" and record["adjudications"] == []


def test_record_id_is_explicit_or_deterministic():
    assert build(draft())["record_id"] == build(draft())["record_id"]
    assert build(draft())["record_id"].startswith("bioev:draft-")
    changed = draft(); changed["statement"]["predicate"] = "contributes_to"
    assert build(changed)["record_id"] != build(draft())["record_id"]
    named = draft(); named["id"] = "lab:claim-7"
    record = build(named)
    assert record["record_id"] == "lab:claim-7" and record["statement"]["id"] == "lab:claim-7/statement"


@pytest.mark.parametrize("stated,expect_observed,expected", [
    (SOURCE_SHA256, True, "review_required"),
    (SOURCE_SHA256.upper(), True, "review_required"),
    ("0" * 64, True, "rejected"),
])
def test_stated_hash_is_checked_against_file(stated, expect_observed, expected):
    value = draft(); value["sources"][0]["sha256"] = stated
    record = build(value)
    assert ("observed_sha256" in record["source_artifacts"][0]) is expect_observed
    report = validate_record(record, profile="literature-claim")
    assert report["overall_status"] == expected
    if expected == "rejected":
        assert "BEV002" in {f["rule_id"] for f in report["findings"]}


def test_stated_hash_without_file_is_frozen_reference_only():
    value = draft(); del value["sources"][0]["file"]; value["sources"][0]["sha256"] = "a" * 64
    source = build(value)["source_artifacts"][0]
    assert source["sha256"] == "a" * 64 and "observed_sha256" not in source


def test_contradicting_evidence_gets_its_own_line():
    value = draft("reviewed_claim.yaml")
    value["evidence"].append({**value["evidence"][0], "direction": "contradicts", "locator": "Table 3"})
    record = build(value)
    assert [line["direction"] for line in record["statement"]["evidence_lines"]] == ["supports", "contradicts"]
    overall, _, report = statuses(value)
    assert overall == "review_required" and "BEV004" in {f["rule_id"] for f in report["findings"]}


def test_unquoted_yaml_timestamps_become_iso_strings(tmp_path):
    text = (DRAFTS / "llm_claim.yaml").read_text(encoding="utf-8").replace('"2026-09-21T00:00:00Z"', "2026-09-21T00:00:00Z")
    path = tmp_path / "draft.yaml"; path.write_text(text, encoding="utf-8")
    (tmp_path / "synthetic_paper.txt").write_bytes((DRAFTS / "synthetic_paper.txt").read_bytes())
    record = build_record(load_draft(path), base_dir=tmp_path)
    assert record["source_artifacts"][0]["retrieved_at"] == "2026-09-21T00:00:00+00:00"
    assert validate_record(record, profile="literature-claim")["schema_valid"]


def _mutate(value, case):
    source, evidence = value["sources"][0], value["evidence"][0]
    if case == "unknown_top": value["typo"] = 1
    elif case == "missing_uses": del value["uses"]
    elif case == "empty_evidence": value["evidence"] = []
    elif case == "unknown_evidence_field": evidence["confidence"] = 0.9
    elif case == "missing_evidence_scope": del evidence["scope"]
    elif case == "missing_method": del evidence["method"]
    elif case == "bad_method": evidence["method"] = "guess"
    elif case == "bad_direction": evidence["direction"] = "maybe"
    elif case == "undeclared_source": evidence["source"] = "other"
    elif case == "numeric_version": source["version"] = 1.0
    elif case == "blank_label": value["statement"]["subject"]["label"] = " "
    elif case == "repeated_scope": value["statement"]["scope"] = ["a", "a"]
    elif case == "no_hash": del source["file"]
    elif case == "missing_file": source["file"] = "absent.txt"
    elif case == "repeated_source": value["sources"].append(copy.deepcopy(source))
    elif case == "bad_review": value["reviews"] = [{"reviewer": {"id": "x", "type": "robot"}, "decision": "accept",
                                                   "uses": ["research_summary"], "rationale": "r", "decided_at": "2026-01-01T00:00:00Z"}]
    elif case == "not_mapping": return ["profile"]
    return value


@pytest.mark.parametrize("case", ["unknown_top", "missing_uses", "empty_evidence", "unknown_evidence_field",
                                  "missing_evidence_scope", "missing_method", "bad_method", "bad_direction",
                                  "undeclared_source", "numeric_version", "blank_label", "repeated_scope",
                                  "no_hash", "missing_file", "repeated_source", "bad_review", "not_mapping"])
def test_malformed_drafts_fail_explicitly(case):
    with pytest.raises(ValueError):
        build(_mutate(draft(), case))


@pytest.mark.parametrize("profile", ["general", "literature-claim", "dataset-label"])
def test_draft_schema_is_valid_json_schema(profile):
    schema = draft_json_schema(profile)
    Draft202012Validator.check_schema(schema)
    assert schema["properties"]["profile"] == {"const": profile}


@pytest.mark.parametrize(
    "name,profile",
    [
        ("llm_claim.yaml", "literature-claim"),
        ("reviewed_claim.yaml", "literature-claim"),
        ("dataset_label_reference.yaml", "dataset-label"),
        ("dataset_label_training_unreviewed.yaml", "dataset-label"),
    ],
)
def test_example_drafts_match_their_profile_schema(name, profile):
    Draft202012Validator(draft_json_schema(profile)).validate(draft(name))


def test_draft_schema_turns_profile_allowlists_into_enums():
    statement = draft_json_schema("literature-claim")["properties"]["statement"]["properties"]
    assert statement["predicate"]["enum"] == ["associated_with", "contributes_to"]
    assert statement["subject"]["properties"]["type"]["enum"] == ["gene", "variant"]
    general = draft_json_schema("general")["properties"]["statement"]["properties"]
    assert "enum" not in general["predicate"]


def test_cli_build_and_draft_schema(tmp_path, capsys):
    assert main(["build", str(DRAFTS / "llm_claim.yaml")]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["source_artifacts"][0]["sha256"] == SOURCE_SHA256
    record = tmp_path / "record.json"
    assert main(["build", str(DRAFTS / "llm_claim.yaml"), "--output", str(record)]) == 0
    assert json.loads(record.read_text(encoding="utf-8")) == printed
    assert main(["validate", str(record), "--profile", "literature-claim"]) == 2
    schema = tmp_path / "schema.json"
    assert main(["draft-schema", "--profile", "literature-claim", "--output", str(schema)]) == 0
    assert json.loads(schema.read_text(encoding="utf-8"))["properties"]["profile"]["const"] == "literature-claim"


def test_cli_build_errors_are_structured(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"; bad.write_text(yaml.safe_dump({"profile": "general"}), encoding="utf-8")
    assert main(["build", str(bad)]) == 3
    assert json.loads(capsys.readouterr().err)["error"] == "input_or_execution_error"
    draft_path = tmp_path / "draft.yaml"; draft_path.write_text("profile: general\n", encoding="utf-8")
    assert main(["build", str(draft_path), "--output", str(draft_path)]) == 3
    assert draft_path.read_text(encoding="utf-8") == "profile: general\n"
    assert main(["draft-schema", "--profile", "no-such-profile"]) == 3
