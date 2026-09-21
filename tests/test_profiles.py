import copy
from pathlib import Path

import pytest
import yaml
from bioevidence_validator.engine import load_profile, profile_path, validate_record
from test_engine import load, ROOT


@pytest.mark.parametrize("case", ["missing_field", "unknown_field", "empty_uses", "missing_flag", "string_bool", "string_types", "duplicate_type", "unknown_option", "blank_use", "duplicate_yaml", "numeric_key", "yaml_list", "bad_yaml"])
def test_invalid_profiles_fail_explicitly(tmp_path, case):
    profile = load_profile(profile_path().read_bytes())
    if case == "missing_field": del profile["version"]
    elif case == "unknown_field": profile["typo"] = True
    elif case == "empty_uses": profile["uses"] = {}
    elif case == "missing_flag": del profile["uses"]["training_data"]["require_human_acceptance"]
    elif case == "string_bool": profile["uses"]["training_data"]["require_human_acceptance"] = "false"
    elif case == "string_types": profile["subject_types"] = "gene"
    elif case == "duplicate_type": profile["object_types"] = ["disease", "disease"]
    elif case == "unknown_option": profile["uses"]["training_data"]["disabled"] = True
    elif case == "blank_use": profile["uses"][" "] = profile["uses"]["training_data"]
    elif case == "numeric_key": profile[42] = True
    text = yaml.safe_dump(profile)
    if case == "duplicate_yaml": text += "\nid: overridden\n"
    if case == "yaml_list": text = "- general\n"
    if case == "bad_yaml": text = "broken: ["
    path = tmp_path / "profile.yaml"; path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError): validate_record(load(), profile=path)


def test_profile_cannot_be_silently_downgraded():
    record = load("dataset_label/missing_sample_link.json")
    report = validate_record(record)  # Caller forgot --profile dataset-label.
    assert report["overall_status"] == "rejected"
    assert "RECORD_INTEGRITY" in {f["rule_id"] for f in report["findings"]}


@pytest.mark.parametrize("field,value", [("predicate", "invented"), ("subject", "compound"), ("object", "assay_readout")])
def test_profile_restricts_statement_types(field, value):
    record = load("literature_claim/curated_association.json")
    if field == "predicate": record["statement"][field] = value
    else: record["statement"][field]["entity_type"] = value
    assert validate_record(record, profile="literature-claim")["overall_status"] == "rejected"


def test_new_domain_is_config_only_and_enforces_its_contract(tmp_path):
    # These types and this use are neither canine nor one of the shipped profiles.
    profile = load_profile((ROOT / "examples/custom_profile/assay.yaml").read_bytes())
    profile.update(id="novel-domain", predicates=["has_measurement"], subject_types=["organoid"], object_types=["imaging_feature"])
    contract = copy.deepcopy(profile["uses"]["assay_curation"])
    contract["required_evidence_types"] = ["microscopy_measurement"]
    profile["uses"] = {"screening_curation": contract}
    path = tmp_path / "novel.yaml"; path.write_text(yaml.safe_dump(profile), encoding="utf-8")
    record = load(); record.update(profile_id="novel-domain", requested_uses=["screening_curation"])
    record["statement"]["predicate"] = "has_measurement"
    record["statement"]["subject"]["entity_type"] = "organoid"
    record["statement"]["object"]["entity_type"] = "imaging_feature"
    record["evidence_items"][0]["evidence_type"] = "microscopy_measurement"
    assert validate_record(record, profile=path)["overall_status"] == "admitted"
    record["evidence_items"][0]["evidence_type"] = "irrelevant"
    assert validate_record(record, profile=path)["overall_status"] == "rejected"


def test_explicit_profile_override_of_llm_gate_is_auditable(tmp_path):
    profile = load_profile(profile_path("literature-claim").read_bytes())
    profile["uses"]["research_summary"]["allow_llm_only"] = True
    path = tmp_path / "profile.yaml"; path.write_text(yaml.safe_dump(profile), encoding="utf-8")
    record = load("literature_claim/llm_only.json")
    original = validate_record(record, profile="literature-claim")
    changed = validate_record(record, profile=path)
    assert changed["overall_status"] == "admitted"
    assert original["overall_status"] == "review_required"
    assert changed["profile_sha256"] != original["profile_sha256"]


def test_unknown_profile_never_falls_back_to_general():
    with pytest.raises(ValueError, match="Unknown profile"):
        validate_record(load(), profile="misspelled-profile")
