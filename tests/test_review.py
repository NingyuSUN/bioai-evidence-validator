"""Independent-review tooling: statistics, strict formats, and the adjudicate -> score -> freeze path."""
import csv
import json

import pytest

from bioevidence_validator import review
from bioevidence_validator.cli import main

H1, H2 = "a" * 64, "b" * 64


def test_krippendorff_alpha_hand_example():
    # Coincidences: a-b once each way; n_a=3, n_b=3, n_c=2, n=8 -> alpha = 1 - 7*2/42 = 2/3.
    assert review.krippendorff_alpha_nominal([["a", "a"], ["a", "b"], ["b", "b"], ["c", "c"]]) == pytest.approx(2 / 3)
    assert review.krippendorff_alpha_nominal([["a", "a"], ["a", "a"]]) is None  # no variation to measure against
    assert review.krippendorff_alpha_nominal([["a"], ["b", "b"], ["a", "a", "b"]]) is not None  # single ratings ignored


def test_cohen_kappa_textbook_example():
    pairs = [("y", "y")] * 20 + [("n", "n")] * 15 + [("y", "n")] * 5 + [("n", "y")] * 10
    assert review.cohen_kappa(pairs) == pytest.approx(0.4)  # po 0.7, pe 0.5
    assert review.cohen_kappa([]) is None and review.cohen_kappa([("y", "y")] * 3) is None


def row(case, use, reviewer, admission, mapping="correct", **extra):
    base = {"annotation_id": f"{reviewer}:{case}:{use}", "case_id": case, "record_sha256": H1, "profile_id": "p",
            "profile_sha256": H2, "requested_use": use, "group_id": case, "split": "test", "reviewer_id": reviewer,
            "reviewer_qualification": "curator", "annotated_at": "2026-10-01", "mapping_label": mapping,
            "mapping_rationale": "", "admission_label": admission, "admission_rationale": "",
            "evidence_refs_json": '["packet"]'}
    return {**base, **extra}


def write(path, rows, columns):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.mark.parametrize("change,message", [
    ({"admission_label": "maybe"}, "admission_label"), ({"mapping_label": "yes"}, "mapping_label"),
    ({"split": "train"}, "split"), ({"record_sha256": "XYZ"}, "record_sha256"),
    ({"annotated_at": "last week"}, "ISO 8601"), ({"evidence_refs_json": "packet"}, "JSON"),
    ({"evidence_refs_json": "[]"}, None), ({"reviewer_id": ""}, "blank"),
])
def test_annotation_format_is_strict(tmp_path, change, message):
    rows = [row("c1", "u", "R1", "admitted", **change)]
    path = write(tmp_path / "a.csv", rows, review.ANNOTATION_COLUMNS)
    if message is None:
        review.load_annotations(path)  # an empty reference list is valid JSON; nonblank entries are checked
        return
    with pytest.raises(ValueError, match=message):
        review.load_annotations(path)


def test_duplicate_review_and_mismatched_record_are_rejected(tmp_path):
    dup = [row("c1", "u", "R1", "admitted"), {**row("c1", "u", "R1", "rejected"), "annotation_id": "other"}]
    with pytest.raises(ValueError, match="twice"):
        review.load_annotations(write(tmp_path / "a.csv", dup, review.ANNOTATION_COLUMNS))
    mixed = [row("c1", "u", "R1", "admitted"), row("c1", "u", "R2", "admitted", record_sha256="c" * 64)]
    with pytest.raises(ValueError, match="different record"):
        review.load_annotations(write(tmp_path / "b.csv", mixed, review.ANNOTATION_COLUMNS))


def test_unknown_columns_are_rejected_but_documented_optional_ones_allowed(tmp_path):
    ok = [{**row("c1", "u", "R1", "admitted"), "later_information_seen": "no", "minutes_spent": "4"}]
    review.load_annotations(write(tmp_path / "ok.csv", ok, review.ANNOTATION_COLUMNS + review.OPTIONAL_ANNOTATION_COLUMNS))
    with pytest.raises(ValueError, match="unknown columns"):
        review.load_annotations(write(tmp_path / "bad.csv", [{**ok[0], "score": "1"}],
                                      review.ANNOTATION_COLUMNS + review.OPTIONAL_ANNOTATION_COLUMNS + ["score"]))


@pytest.fixture
def study(tmp_path):
    """Two reviewers, four cases, one use; they disagree on c3 and c4."""
    labels = {"c1": ("admitted", "admitted"), "c2": ("rejected", "rejected"),
              "c3": ("admitted", "review_required"), "c4": ("review_required", "rejected")}
    rows = [row(c, "u", r, lab) for c, pair in labels.items() for r, lab in zip(["R1", "R2"], pair, strict=True)]
    annotations = write(tmp_path / "annotations.csv", rows, review.ANNOTATION_COLUMNS)
    predictions = write(tmp_path / "predictions.csv", [
        {"case_id": c, "requested_use": "u", "record_sha256": H1, "profile_sha256": H2, "method": m,
         "predicted_status": s, "subset": "divergent" if c in ("c3", "c4") else "control"}
        for m, statuses in {"tool": ["admitted", "rejected", "review_required", "rejected"],
                            "baseline": ["admitted", "not_admitted", "admitted", "admitted"]}.items()
        for c, s in zip(["c1", "c2", "c3", "c4"], statuses, strict=True)], review.PREDICTION_COLUMNS + ["subset"])
    return tmp_path, annotations, predictions


def test_agreement_report(study):
    _, annotations, _ = study
    report = review.agreement(review.load_annotations(annotations), resamples=200)
    entry = report["uses"]["u"]["admission_label"]
    assert entry["units_with_2plus_reviews"] == 4 and entry["percent_agreement"] == 0.5
    assert entry["cohen_kappa"] == pytest.approx(review.cohen_kappa(
        [("admitted", "admitted"), ("rejected", "rejected"), ("admitted", "review_required"), ("review_required", "rejected")]), abs=1e-4)
    assert report == review.agreement(review.load_annotations(annotations), resamples=200)  # seeded bootstrap


def test_disagreements_must_be_adjudicated_before_scoring(study):
    tmp_path, annotations, _ = study
    rows = review.load_annotations(annotations)
    sheet, incomplete = review.adjudication_sheet(rows)
    assert [r["case_id"] for r in sheet] == ["c3", "c4"] and incomplete == []
    with pytest.raises(ValueError, match="no adjudication"):
        review.resolve(rows, [])


def fill_adjudications(path, rows):
    for r, label in zip(rows, ["review_required", "rejected"], strict=True):
        r.update(mapping_label="correct", admission_label=label, adjudicator_id="A1", adjudicated_at="2026-10-05",
                 mapping_rationale="agreed", admission_rationale="discussed", evidence_refs_json='["packet"]')
    return write(path, rows, review.ADJUDICATION_COLUMNS)


def test_score_against_resolved_labels(study):
    tmp_path, annotations, predictions = study
    rows = review.load_annotations(annotations)
    adjudications = fill_adjudications(tmp_path / "adj.csv", review.adjudication_sheet(rows)[0])
    final = review.resolve(rows, review.load_adjudications(adjudications, rows))
    report = review.score(final, review.load_predictions(predictions))
    tool, baseline = report["methods"]["tool"]["all"], report["methods"]["baseline"]["all"]
    # Reference: c1 admitted, c2 rejected, c3 review_required, c4 rejected.
    assert tool["exact_matches"] == 4 and tool["false_admissions"] == 0
    assert baseline["false_admissions"] == 2 and baseline["false_blocks"] == 0
    assert report["methods"]["baseline"]["divergent"]["n"] == 2


def test_scoring_refuses_mismatched_or_missing_predictions(study):
    tmp_path, annotations, predictions = study
    rows = review.load_annotations(annotations)
    final = review.resolve(rows, review.load_adjudications(
        fill_adjudications(tmp_path / "adj.csv", review.adjudication_sheet(rows)[0]), rows))
    preds = review.load_predictions(predictions)
    with pytest.raises(ValueError, match="different record"):
        review.score(final, [{**preds[0], "record_sha256": "c" * 64}, *preds[1:]])
    with pytest.raises(ValueError, match="Missing predictions"):
        review.score(final, preds[1:])


def test_cli_review_workflow(study, capsys):
    tmp_path, annotations, predictions = study
    assert main(["review", "check", str(annotations)]) == 0
    assert main(["review", "agreement", str(annotations), "--output", str(tmp_path / "agree.json")]) == 0
    assert "Krippendorff" in capsys.readouterr().out
    sheet = tmp_path / "adjudications.csv"
    assert main(["review", "adjudication-sheet", str(annotations), "--output", str(sheet)]) == 0
    assert main(["review", "adjudication-sheet", str(annotations), "--output", str(sheet)]) == 3  # never overwrites
    with sheet.open(encoding="utf-8") as handle:
        blank = list(csv.DictReader(handle))
    fill_adjudications(sheet, blank)
    assert main(["review", "score", "--annotations", str(annotations), "--adjudications", str(sheet),
                 "--predictions", str(predictions), "--output", str(tmp_path / "score.json")]) == 0
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"status": "draft"}), encoding="utf-8")
    out = tmp_path / "frozen.json"
    assert main(["review", "freeze", "--manifest", str(manifest), "--annotations", str(annotations),
                 "--adjudications", str(sheet), "--file", str(predictions), "--dataset-id", "demo",
                 "--version", "1", "--frozen-at", "2026-10-06T00:00:00Z", "--output", str(out)]) == 0
    frozen = json.loads(out.read_text(encoding="utf-8"))
    assert frozen["status"] == "frozen" and frozen["reviewed_case_use_count"] == 4
    assert frozen["independent_human_reviewer_count"] == 2 and set(frozen["files"]) == {
        "annotations.csv", "adjudications.csv", "predictions.csv"}
    assert frozen["resolution_counts"] == {"adjudicated": 2, "unanimous": 2}


@pytest.mark.parametrize("change,message", [
    ({"admission_label": ""}, "blank"),
    ({"admission_label": "maybe"}, "labels must be"),
    ({"annotation_ids_json": '["R1:c1:u"]'}, "is not an annotation of"),
    ({"annotation_ids_json": '["nope"]'}, "is not an annotation of"),
    ({"record_sha256": "c" * 64}, "hash differs"),
    ({"adjudicated_at": "soon"}, "ISO 8601"),
    ({"evidence_refs_json": "{}"}, "JSON array"),
])
def test_adjudication_format_is_strict(study, change, message):
    tmp_path, annotations, _ = study
    rows = review.load_annotations(annotations)
    sheet = review.adjudication_sheet(rows)[0]
    good = fill_adjudications(tmp_path / "good.csv", [dict(r) for r in sheet])
    review.load_adjudications(good, rows)
    filled = list(csv.DictReader(good.open(encoding="utf-8")))
    bad = write(tmp_path / "bad.csv", [{**filled[0], **change}, filled[1]], review.ADJUDICATION_COLUMNS)
    with pytest.raises(ValueError, match=message):
        review.load_adjudications(bad, rows)
    twice = write(tmp_path / "twice.csv", [filled[0], filled[0]], review.ADJUDICATION_COLUMNS)
    with pytest.raises(ValueError, match="adjudicated twice"):
        review.load_adjudications(twice, rows)


def test_resolution_needs_enough_reviews_and_real_cases(study):
    tmp_path, annotations, _ = study
    rows = review.load_annotations(annotations)
    solo = [r for r in rows if r["reviewer_id"] == "R1"]
    assert review.adjudication_sheet(solo)[1] == [("c1", "u"), ("c2", "u"), ("c3", "u"), ("c4", "u")]
    with pytest.raises(ValueError, match="1 review"):
        review.resolve(solo, [])
    single = review.resolve(solo, [], min_reviewers=1)  # an explicit single-reviewer reference set
    assert {v["resolution"] for v in single.values()} == {"unanimous"}
    ghost = {"case_id": "c9", "requested_use": "u", "admission_label": "admitted", "mapping_label": "correct"}
    with pytest.raises(ValueError, match="never reviewed"):
        review.resolve(rows, [ghost])


def test_prediction_format_and_split_are_checked(study):
    tmp_path, annotations, predictions = study
    rows = list(csv.DictReader(predictions.open(encoding="utf-8")))
    columns = review.PREDICTION_COLUMNS + ["subset"]
    with pytest.raises(ValueError, match="duplicate prediction"):
        review.load_predictions(write(tmp_path / "dup.csv", [rows[0], rows[0]], columns))
    with pytest.raises(ValueError, match="predicted_status"):
        review.load_predictions(write(tmp_path / "bad.csv", [{**rows[0], "predicted_status": "maybe"}], columns))
    labels = review.load_annotations(annotations)
    final = review.resolve(labels, review.load_adjudications(
        fill_adjudications(tmp_path / "adj.csv", review.adjudication_sheet(labels)[0]), labels))
    with pytest.raises(ValueError, match="No reference labels in split 'development'"):
        review.score(final, review.load_predictions(predictions), split="development")


def test_freeze_refuses_unresolved_disagreements(study):
    tmp_path, annotations, _ = study
    empty = write(tmp_path / "adj.csv", [], review.ADJUDICATION_COLUMNS)
    manifest = tmp_path / "m.json"
    manifest.write_text("{}", encoding="utf-8")
    assert main(["review", "freeze", "--manifest", str(manifest), "--annotations", str(annotations),
                 "--adjudications", str(empty), "--dataset-id", "d", "--version", "1",
                 "--frozen-at", "2026-10-06", "--output", str(tmp_path / "f.json")]) == 3
    assert not (tmp_path / "f.json").exists()
