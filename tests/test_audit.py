"""Audit sampling: exact bounds, a seeded blind sample, and per-route error rates (#24)."""
import csv
import json
import math

import pytest

from bioevidence_validator import audit, review
from bioevidence_validator.cli import main

H2 = "b" * 64


def binomial_cdf(errors, n, p):
    return sum(math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(errors + 1))


def test_zero_error_bound_has_the_closed_form():
    for n in (1, 10, 59, 299, 300, 1000):
        assert audit.upper_bound(0, n) == pytest.approx(1 - 0.05 ** (1 / n), abs=2e-6)
    assert audit.upper_bound(0, 299) < 0.01 <= audit.upper_bound(0, 298)
    assert audit.upper_bound(0, 0) is None and audit.upper_bound(5, 5) == 1.0


@pytest.mark.parametrize("errors,n", [(1, 300), (3, 59), (14, 59), (50, 255)])
def test_bound_with_errors_is_exact_and_conservative(errors, n):
    bound = audit.upper_bound(errors, n)
    assert binomial_cdf(errors, n, bound) <= 0.05 < binomial_cdf(errors, n, bound - 1e-5)
    assert bound > errors / n
    assert audit.upper_bound(errors, n, 0.99) > bound


def test_bound_rejects_impossible_counts():
    for errors, n, confidence in ((3, 2, 0.95), (-1, 5, 0.95), (1, 5, 1.0)):
        with pytest.raises(ValueError):
            audit.upper_bound(errors, n, confidence)


def test_sample_size():
    assert audit.sample_size(0.01) == 299 and audit.sample_size(0.05) == 59 and audit.sample_size(0.10) == 29
    n = audit.sample_size(0.01, errors=1)
    assert audit.upper_bound(1, n) < 0.01 <= audit.upper_bound(1, n - 1)
    assert audit.sample_size(0.01, confidence=0.99) > 299
    with pytest.raises(ValueError):
        audit.sample_size(0)


def prediction(case, status, method="loop", use="u"):
    digest = f"{int(case[1:]):064x}"
    return {"case_id": case, "requested_use": use, "record_sha256": digest, "profile_sha256": H2,
            "method": method, "predicted_status": status}


PREDICTIONS = ([prediction(f"c{i:03d}", "admitted") for i in range(100)]
               + [prediction(f"c{i:03d}", "review_required") for i in range(100, 120)]
               + [prediction(f"c{i:03d}", "rejected") for i in range(120, 125)]
               + [prediction("c000", "admitted", method="other")])


def test_sample_is_seeded_blind_and_only_of_the_method_and_use():
    sheet, manifest = audit.audit_sample(PREDICTIONS, method="loop", use="u", size=30, seed=7, controls=5,
                                         profile_id="p")
    again, _ = audit.audit_sample(list(reversed(PREDICTIONS)), method="loop", use="u", size=30, seed=7, controls=5,
                                  profile_id="p")
    other, _ = audit.audit_sample(PREDICTIONS, method="loop", use="u", size=30, seed=8, controls=5, profile_id="p")
    assert sheet == again and sheet != other
    assert manifest["population"] == {"admitted": 100, "rejected": 5, "review_required": 20}
    assert manifest["sample"] == {"admitted": 30, "controls": 5} and len(sheet) == 35
    routes = [manifest["sampled"][row["case_id"]]["route"] for row in sheet]
    assert routes.count("admitted") == 30
    assert routes != sorted(routes, key=lambda r: r != "admitted")  # controls are shuffled in, not appended
    assert set(sheet[0]) == set(review.ANNOTATION_COLUMNS)  # nothing on the sheet names the route
    assert all(row["mapping_label"] == "" and row["profile_id"] == "p" for row in sheet)
    assert manifest["if_no_errors_admitted_error_below"] == audit.upper_bound(0, 30)


def test_sample_is_capped_and_refuses_nothing_to_audit():
    _, manifest = audit.audit_sample(PREDICTIONS, method="loop", use="u", size=500, seed=1, controls=500,
                                     profile_id="p")
    assert manifest["sample"] == {"admitted": 100, "controls": 25}
    with pytest.raises(ValueError, match="No predictions"):
        audit.audit_sample(PREDICTIONS, method="loop", use="other", size=5, seed=1, profile_id="p")
    with pytest.raises(ValueError, match="Nothing to audit"):
        audit.audit_sample([prediction("c1", "rejected")], method="loop", use="u", size=5, seed=1, profile_id="p")


def label(row, admission, mapping, minutes=""):
    return {**row, "annotation_id": f"a:{row['case_id']}", "reviewer_id": "R1", "reviewer_qualification": "curator",
            "annotated_at": "2026-10-06", "admission_label": admission, "mapping_label": mapping,
            "evidence_refs_json": '["packet"]', "minutes_spent": minutes}


def test_score_counts_errors_per_route_with_bounds_and_expert_time():
    sheet, manifest = audit.audit_sample(PREDICTIONS, method="loop", use="u", size=40, seed=3, controls=10,
                                         profile_id="p")
    route = {row["case_id"]: manifest["sampled"][row["case_id"]]["route"] for row in sheet}
    rows, wrong_admitted = [], 0
    for row in sheet[:-1]:  # the last record is not yet audited
        if route[row["case_id"]] == "admitted":
            wrong = wrong_admitted < 2
            wrong_admitted += wrong
            rows.append(label(row, "rejected" if wrong else "admitted", "incorrect" if wrong else "correct", "2"))
        else:  # a routed record that could have been admitted as it was is a wasted review
            rows.append(label(row, "admitted", "correct", "6"))
    final = review.resolve(rows, [], min_reviewers=1)
    report = audit.audit_score(manifest, final, rows)
    admitted = report["routes"]["admitted"]
    assert len(report["not_yet_audited"]) == 1
    assert admitted["errors"] == 2 and admitted["error_rate_upper_bound"] == audit.upper_bound(2, admitted["audited"])
    assert report["admitted_error_upper_bound"] == admitted["error_rate_upper_bound"]
    assert admitted["share_of_records"] == 0.8
    assert admitted["errors_in_route_at_most"] == math.ceil(admitted["error_rate_upper_bound"] * 100)
    others = [s for r, s in report["routes"].items() if r != "admitted"]
    assert all(s["errors"] == s["audited"] for s in others)
    # Expert time: the audit's own minutes on the admitted route; every record at the audited mean on review.
    assert admitted["expert_minutes_estimated"] == 2 * admitted["audited"]
    assert report["routes"]["review_required"]["expert_minutes_estimated"] == 6 * 20
    assert sum(s["share_of_expert_time"] for s in report["routes"].values()) == pytest.approx(1, abs=1e-3)
    text = audit.render_audit(report)
    assert "auto-admitted error rate is below" in text and "not yet audited" in text


def test_score_refuses_a_different_record_or_a_record_not_sampled():
    sheet, manifest = audit.audit_sample(PREDICTIONS, method="loop", use="u", size=5, seed=3, profile_id="p")
    changed = [label({**sheet[0], "record_sha256": "f" * 64}, "admitted", "correct")]
    with pytest.raises(ValueError, match="differs"):
        audit.audit_score(manifest, review.resolve(changed, [], min_reviewers=1))
    stray = [label({**sheet[0], "case_id": "c124"}, "admitted", "correct")]
    with pytest.raises(ValueError, match="not in the audit sample"):
        audit.audit_score(manifest, review.resolve(stray, [], min_reviewers=1))


def test_cli_audit_sample_and_score(tmp_path, capsys):
    predictions = tmp_path / "predictions.csv"
    review.write_csv(predictions, PREDICTIONS, review.PREDICTION_COLUMNS)
    out = tmp_path / "audit"
    args = ["review", "audit-sample", "--predictions", str(predictions), "--method", "loop", "--use", "u",
            "--target", "0.05", "--controls", "4", "--seed", "11", "--profile-id", "p", "--output-dir", str(out)]
    assert main(args) == 0
    assert "59 auto-admitted, 4 controls" in capsys.readouterr().out
    assert main(args) == 3  # never overwrites an audit (input error)
    assert "refusing to overwrite" in capsys.readouterr().err
    manifest = json.loads((out / "audit_manifest.json").read_text(encoding="utf-8"))
    assert manifest["predictions_sha256"] == review.sha256_file(predictions)
    with (out / "audit_sheet.csv").open(encoding="utf-8", newline="") as handle:
        sheet = list(csv.DictReader(handle))
    filled = [label(row, "admitted", "correct", "3") for row in sheet]
    review.write_csv(tmp_path / "labels.csv", filled, review.ANNOTATION_COLUMNS + review.OPTIONAL_ANNOTATION_COLUMNS)
    assert main(["review", "audit-score", "--manifest", str(out / "audit_manifest.json"), "--annotations",
                 str(tmp_path / "labels.csv"), "--output", str(tmp_path / "report.json")]) == 0
    printed = capsys.readouterr().out
    assert "0 error(s) in 59 audited auto-admitted records" in printed and "below 4.95%" in printed
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["admitted_error_upper_bound"] < 0.05
