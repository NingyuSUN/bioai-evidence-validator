"""Model review analysis (#22): agreement before any reference, then scores, error correlation, consensus and the
pre-registered decision rule against expert labels."""
import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "evaluation" / "clinvar_review"
sys.path.insert(0, str(KIT))


def load(name):
    spec = importlib.util.spec_from_file_location(f"am_{name}", KIT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mr, prepare, importer, am = load("model_reviewers"), load("prepare_packets"), load("import_sheets"), load("analyze_models")
USES = am.USES


def answer(statuses):
    return {"statement_label": "correct", "statement_rationale": "r", "later_information_seen": "no",
            **{u: s for u, s in zip(USES, statuses, strict=True)}, **{f"{u}_rationale": "r" for u in USES}}


@pytest.fixture
def study(tmp_path, monkeypatch):
    """The real packet (2 calibration cases), six fake model reviewers and two agreeing experts."""
    kit = tmp_path / "kit"
    prepare.prepare(kit, salt="test-salt", calibration=2, controls_per_divergent=1)
    cases, _ = mr.read_packet(kit / "reviewer_packet")
    codes = [c["case_code"] for c in cases]
    truth = {code: ("admitted" if i % 2 else "rejected") for i, code in enumerate(codes)}

    def fake_review(backend, model, case, rubric, timeout):
        status = truth[case["case_code"]]
        if model in ("gpt-5.6-luna", "gemini-3.8-flash-medium") and codes.index(case["case_code"]) % 3 == 0:
            status = "admitted"  # two models share the same misses on every third case
        return {"code": case["case_code"], "backend": backend, "model": model, "prompt_sha256": "x", "ok": True,
                "labels": answer([status] * 3), "tools_used": [],
                "attempts": [{"seconds": 2.0, "error": None, "usage": {}}], "finished_at": "2026-10-08T00:00:00+00:00"}

    monkeypatch.setattr(mr, "review_case", fake_review)
    monkeypatch.setattr(mr, "cli_version", lambda name: f"{name} 1.0")
    monkeypatch.setattr(mr, "find_executable", lambda name: name)
    models = tmp_path / "models"
    assert mr.main(["run", "--packet", str(kit / "reviewer_packet"), "--output", str(models)]) == 0
    assert mr.main(["export", "--output", str(models), "--key", str(kit / "maintainer" / "key.json"),
                    "--annotated-at", "2026-10-08"]) == 0
    key = json.loads((kit / "maintainer" / "key.json").read_text(encoding="utf-8"))
    experts = []
    for reviewer in ("R1", "R2"):
        labels = [{"case_code": c, "statement_label": "correct", **{u: truth[c] for u in USES}} for c in codes]
        rows, _ = importer.convert(labels, key, reviewer_id=reviewer, qualification="curator", annotated_at="2026-10-08")
        experts += rows
    annotations = tmp_path / "annotations.csv"
    importer.append(annotations, experts)
    adjudications = tmp_path / "adjudications.csv"
    with adjudications.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerow(am.review.ADJUDICATION_COLUMNS)
    return models, annotations, adjudications, kit / "maintainer" / "predictions.csv"


def test_without_a_reference_only_runs_and_agreement(study, tmp_path):
    models, *_ = study
    report = am.analyze(models, None, None, None)
    total = len(mr.read_packet(models.parent / "kit" / "reviewer_packet")[0])
    assert set(report["runs"]) == set(mr.REVIEWERS) and all(r["answered"] == total for r in report["runs"].values())
    assert len(report["inter_model_agreement"]["reviewers"]) == 6
    assert report["inter_model_agreement"]["admission"]["research_summary"]["units_with_2plus_reviews"] == total - 2
    assert "scores" not in report and "no expert labels" in report["reference"]
    assert am.main(["--models", str(models), "--output", str(tmp_path / "out"), "--public"]) == 0
    public = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    assert set(public) == {"runs", "inter_model_agreement", "decision_rule", "files_sha256"}


def test_with_expert_labels(study):
    models, annotations, adjudications, predictions = study
    report = am.analyze(models, annotations, adjudications, predictions)
    scores = report["scores"]["research_summary"]
    assert {"model:claude-opus-5-5", am.MAJORITY, "validator", "ncbi_review_status"} <= set(scores)
    assert scores["model:claude-opus-5-5"]["all"]["false_admissions"] == 0
    luna = scores["model:gpt-5.6-luna"]["all"]
    assert luna["false_admissions"] > 0
    pair = report["error_correlation"]["pairs"]["model:gemini-3.8-flash-medium | model:gpt-5.6-luna"]
    assert pair["shared"] == pair["misses_a"] == pair["misses_b"] > 0 and pair["p_b_misses_given_a"] == 1.0
    assert report["consensus"]["unanimous_wrong"] == 0  # the four others outvote the two that share their misses
    assert set(report["decisions"]) == set(USES)
    assert all(d["decision"] in ("models alone", "deterministic rules", "experts") for d in report["decisions"].values())
    public = am.public(report)
    assert "scores" not in public and "decisions" not in public and "consensus" not in public


def test_majority_needs_four_votes():
    rows = [{"case_id": "c", "requested_use": "u", "record_sha256": "a", "profile_sha256": "b",
             "method": f"model:m{i}", "predicted_status": s}
            for i, s in enumerate(["admitted"] * 3 + ["rejected"] * 3)]
    assert am.majority(rows)[0]["predicted_status"] == "review_required"
    rows[3]["predicted_status"] = "admitted"
    assert am.majority(rows)[0]["predicted_status"] == "admitted"


def test_decision_rule_is_the_preregistered_one():
    def metrics(false_admissions, negatives, false_blocks, positives):
        return {"false_admissions": false_admissions, "reference_not_admitted": negatives,
                "false_blocks": false_blocks, "reference_admitted": positives}

    good = {s: metrics(0, 80, 5, 60) for s in ("divergent", "control")}  # bound 3.7% < 5%, blocks 8% < 20%
    leaky = {s: metrics(3, 80, 5, 60) for s in ("divergent", "control")}  # bound 10%
    small = {s: metrics(0, 20, 0, 20) for s in ("divergent", "control")}  # 0 of 20 bounds only below 14%
    scores = {"research_summary": {am.MAJORITY: good, "validator": good},
              "clinical_reference": {am.MAJORITY: leaky, "validator": good},
              "expert_reference": {am.MAJORITY: small, "validator": leaky}}
    decisions = am.decide(scores)
    assert [decisions[u]["decision"] for u in USES] == ["models alone", "deterministic rules", "experts"]
