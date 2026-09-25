"""ClinVar real-source integration and replay tests; no live network required."""
import functools
import gzip
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from bioevidence_validator.engine import RecordValidator

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/clinvar_germline"
spec = importlib.util.spec_from_file_location("clinvar_pipeline", EXAMPLE / "pipeline.py")
pipeline = importlib.util.module_from_spec(spec); spec.loader.exec_module(pipeline)


@functools.cache
def sample():
    return pipeline.ClinVarSample()


@functools.cache
def validator():
    return RecordValidator(profile=EXAMPLE / "profile.yaml")


def validate(record):
    report = validator().validate(record)
    return {d["use"]: d["admission_status"] for d in report["use_decisions"]}, {f["rule_id"] for f in report["findings"]}


def submission(scv, submitter, status, classification):
    return {"SCV": scv, "Submitter": submitter, "ReviewStatus": status, "ClinicalSignificance": classification,
            "CollectionMethod": "clinical testing", "DateLastEvaluated": "Jan 01, 2023"}


def case(*subs):
    return {"variation_id": "1", "gene": "SYN", "stratum": "synthetic", "submissions": list(subs)}


CRIT, NONE, EXPERT = "criteria provided, single submitter", "no assertion criteria provided", "reviewed by expert panel"


def test_frozen_sample_is_hash_checked(tmp_path):
    assert len(sample().cases) == 5026
    (tmp_path / "sources").mkdir()
    shutil.copy(EXAMPLE / "sources/manifest.json", tmp_path / "sources/manifest.json")
    raw = gzip.decompress((EXAMPLE / "sources/clinvar-sample.jsonl.gz").read_bytes())
    (tmp_path / "sources/clinvar-sample.jsonl.gz").write_bytes(gzip.compress(raw.replace(b"Pathogenic", b"Benign", 1)))
    with pytest.raises(ValueError, match="hash mismatch"):
        pipeline.ClinVarSample(tmp_path)


@pytest.mark.parametrize("subs,expected", [
    ([submission("SCV1", "Lab A", NONE, "Pathogenic")],
     {"research_summary": "rejected", "clinical_reference": "rejected", "expert_reference": "rejected"}),
    ([submission("SCV1", "Lab A", CRIT, "Pathogenic")],
     {"research_summary": "admitted", "clinical_reference": "rejected", "expert_reference": "rejected"}),
    ([submission("SCV1", "Lab A", CRIT, "Pathogenic"), submission("SCV2", "Lab B", CRIT, "Likely pathogenic")],
     {"research_summary": "admitted", "clinical_reference": "admitted", "expert_reference": "rejected"}),
    ([submission("SCV1", "Lab A", CRIT, "Pathogenic"), submission("SCV2", "Lab A", CRIT, "Pathogenic")],
     {"research_summary": "admitted", "clinical_reference": "rejected", "expert_reference": "rejected"}),
    ([submission("SCV1", "Panel", EXPERT, "Pathogenic")],
     {"research_summary": "admitted", "clinical_reference": "admitted", "expert_reference": "admitted"}),
])
def test_importer_maps_review_tiers_to_uses(subs, expected):
    statuses, _ = validate(sample().record(case(*subs)))
    assert statuses == expected


@pytest.mark.parametrize("dissent_status", [CRIT, NONE])
def test_any_dissent_is_visible_and_sends_every_use_to_review(dissent_status):
    subs = [submission("SCV1", "Panel", EXPERT, "Pathogenic"), submission("SCV2", "Lab B", dissent_status, "Uncertain significance")]
    statuses, codes = validate(sample().record(case(*subs)))
    assert set(statuses.values()) == {"review_required"} and "BEV004" in codes


def test_neutral_classifications_do_not_support_or_contradict():
    record = sample().record(case(submission("SCV1", "Lab A", CRIT, "Pathogenic"),
                                  submission("SCV2", "Lab B", CRIT, "Uncertain risk allele")))
    directions = {line["direction"]: line["evidence_item_ids"] for line in record["statement"]["evidence_lines"]}
    assert directions["neutral"] == ["bioev:SCV2"] and "contradicts" not in directions


def test_unknown_review_status_fails_the_import():
    with pytest.raises(ValueError, match="Unmapped ClinVar review status"):
        sample().record(case(submission("SCV1", "Lab A", "flagged submission", "Pathogenic")))


def test_outcome_categories():
    assert pipeline.outcome("Pathogenic/Likely pathogenic/Pathogenic, low penetrance") == "stable_plp"
    assert pipeline.outcome("Conflicting classifications of pathogenicity") == "conflicting"
    assert pipeline.outcome("Uncertain significance") == "downgraded"
    assert pipeline.outcome("not provided") == "other" and pipeline.outcome(None) == "missing"
    assert pipeline.wilson(0, 0) is None and pipeline.wilson(0, 10)[0] == 0.0


def test_full_case_replays_committed_results(tmp_path):
    output = tmp_path / "run"
    result = subprocess.run([sys.executable, str(EXAMPLE / "run.py"), "--output", str(output)],
                            capture_output=True, text=True, encoding="utf-8", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    for expected in (EXAMPLE / "results").iterdir():
        assert expected.read_bytes() == (output / expected.name).read_bytes(), expected.name
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    for use, stats in summary["policy_reproduction"].items():
        assert stats["agreement"] / stats["n"] > 0.98, use
    assert summary["policy_reproduction"]["research_summary"]["validator_looser"] == 1
    faults, boundary = summary["faults"]["controlled_fault"], summary["faults"]["trust_boundary"]
    assert faults["full"]["false_admissions"] == 0 and faults["full"]["n"] == 160
    assert faults["aggregate_quality"]["false_admissions"] == 64
    assert boundary["full"]["false_admissions"] == 16  # measured trust limit, reported rather than hidden
    single = summary["population_stability"]["single_submitter"]
    assert single["with_dissenting_submission"]["rate"] > 4 * single["without_dissenting_submission"]["rate"]
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest.items():
        assert pipeline.digest((output / name).read_bytes()) == digest
