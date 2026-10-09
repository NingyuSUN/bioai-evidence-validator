"""What model review can and cannot replace (#22): the six models' labels on the blinded ClinVar packet, compared
with each other, and with the experts' labels once those exist.

    uv run --frozen python evaluation/clinvar_review/analyze_models.py \
        --models artifacts/clinvar-review/models --output artifacts/clinvar-review/models/analysis \
        [--annotations annotations.csv --adjudications adjudications.csv \
         --predictions artifacts/clinvar-review/maintainer/predictions.csv]

Run by the maintainer after `model_reviewers.py export`. Without expert labels it reports what needs no reference:
how each model answered (tool use, later information) and how much the six models agree with each other per use
(Krippendorff's alpha). With the resolved expert labels it adds, on the test split:

- each model, their majority, the validator and NCBI's review status, scored per use and per subset (divergent,
  control), as `bioevidence review score` does;
- error correlation: for each pair of models, how often one model's miss is also the other's;
- whether agreement means correctness: how often the six models are wrong when they all agree;
- the decision statement, by the rule below, fixed before any expert label exists.

Decision rule, per use. A decision may be left to models alone when their majority's false-admission rate (cases
experts would not admit, admitted anyway) has an exact one-sided 95% upper bound below 5%, and its false-block rate
is below 20%, on the divergent and the control subset each. It may be left to deterministic rules when the validator
meets the same two conditions. Otherwise it needs an expert. The majority is at least four of the six models; with no
such majority the case counts as sent to review.

`--public` writes only what cannot unblind a reviewer (no case, no label, nothing compared with the hidden key, the
validator or NCBI's status), for publication while the expert review is still running.
"""
from __future__ import annotations

import argparse
import collections
import csv
import itertools
import json
import statistics
import sys
from pathlib import Path
from typing import Any

from bioevidence_validator import review
from bioevidence_validator.audit import upper_bound

USES = ["research_summary", "clinical_reference", "expert_reference"]
MAJORITY = "model:majority"
FALSE_ADMISSION_BOUND, FALSE_BLOCK_RATE, CONFIDENCE = 0.05, 0.20, 0.95


def reviewer_runs(models: Path) -> dict[str, dict[str, Any]]:
    """Per reviewer: cases answered, failures, tool use and time, from runs.csv and the filled labels."""
    manifest = json.loads((models / "manifest.json").read_text(encoding="utf-8"))
    with (models / "runs.csv").open(encoding="utf-8", newline="") as handle:
        runs = list(csv.DictReader(handle))
    out = {}
    for reviewer, info in manifest["reviewers"].items():
        mine = [r for r in runs if r["reviewer"] == reviewer]
        with (models / reviewer / "labels.csv").open(encoding="utf-8", newline="") as handle:
            labels = [r for r in csv.DictReader(handle) if r.get("statement_label")]
        out[reviewer] = {"model": info["model"], "cli_version": info["cli_version"], "calls": len(mine),
                         "answered": sum(r["ok"] == "True" for r in mine),
                         "with_tool_use": sum(bool(r["tools_used"]) for r in mine),
                         "later_information_seen": sum(r.get("later_information_seen") == "yes" for r in labels),
                         "retried": sum(int(r["attempts"]) > 1 for r in mine),
                         "median_seconds": round(statistics.median(float(r["seconds"]) for r in mine), 1) if mine else None}
    return out


def inter_model(annotations: list[dict[str, str]], split: str = "test") -> dict[str, Any]:
    """Agreement among the models before any reference: alpha per use for admission, and for the statement label."""
    report = review.agreement([a for a in annotations if a["split"] == split])
    return {"reviewers": report["reviewers"], "split": split,
            "admission": {use: report["uses"][use]["admission_label"] for use in USES if use in report["uses"]},
            "statement": report["uses"][USES[0]]["mapping_label"] if USES[0] in report["uses"] else None}


def majority(predictions: list[dict[str, str]], quorum: int = 4) -> list[dict[str, str]]:
    """The models' majority per case and use: a status at least `quorum` models chose, else review_required."""
    grouped: dict[tuple[str, str], list[dict[str, str]]] = collections.defaultdict(list)
    for p in predictions:
        if p["method"].startswith("model:") and p["method"] != MAJORITY:
            grouped[(p["case_id"], p["requested_use"])].append(p)
    out = []
    for rows in grouped.values():
        status, votes = collections.Counter(r["predicted_status"] for r in rows).most_common(1)[0]
        out.append({**rows[0], "method": MAJORITY, "predicted_status": status if votes >= quorum else "review_required"})
    return out


def errors(final: dict[review.Unit, dict[str, str]], predictions: list[dict[str, str]]) -> dict[str, dict]:
    """method -> unit -> whether its admission decision differs from the reference, on the test split."""
    out: dict[str, dict] = collections.defaultdict(dict)
    for p in predictions:
        unit = (p["case_id"], p["requested_use"])
        if unit in final and final[unit]["split"] == "test":
            out[p["method"]][unit] = p["predicted_status"] != final[unit]["admission_label"]
    return out


def correlation(missed: dict[str, dict]) -> dict[str, Any]:
    """For each pair of models: misses of each, misses shared, P(B misses | A misses), and Cohen's kappa of the miss
    indicators. Independent errors would make a second opinion worth something; shared ones make it worth little."""
    models = sorted(m for m in missed if m.startswith("model:") and m != MAJORITY)
    pairs = {}
    for a, b in itertools.combinations(models, 2):
        units = sorted(set(missed[a]) & set(missed[b]))
        both = sum(missed[a][u] and missed[b][u] for u in units)
        n_a, n_b = sum(missed[a][u] for u in units), sum(missed[b][u] for u in units)
        kappa = review.cohen_kappa([(missed[a][u], missed[b][u]) for u in units])
        pairs[f"{a} | {b}"] = {"units": len(units), "misses_a": n_a, "misses_b": n_b, "shared": both,
                               "p_b_misses_given_a": round(both / n_a, 4) if n_a else None,
                               "p_a_misses_given_b": round(both / n_b, 4) if n_b else None,
                               "kappa": None if kappa is None else round(kappa, 4)}
    rates = [missed[m] for m in models]
    units = sorted(set.intersection(*(set(r) for r in rates))) if rates else []
    base = statistics.mean(sum(r[u] for u in units) / len(units) for r in rates) if units else None
    return {"pairs": pairs, "mean_miss_rate": None if base is None else round(base, 4),
            "units": len(units)}


def consensus(final: dict[review.Unit, dict[str, str]], predictions: list[dict[str, str]]) -> dict[str, Any]:
    """Does agreement mean correctness? Among case-uses where every model gave the same status, how often is that
    status wrong; and the same for split decisions."""
    grouped: dict[review.Unit, list[str]] = collections.defaultdict(list)
    for p in predictions:
        if p["method"].startswith("model:") and p["method"] != MAJORITY:
            grouped[(p["case_id"], p["requested_use"])].append(p["predicted_status"])
    unanimous = wrong_unanimous = split = wrong_split = 0
    for unit, statuses in grouped.items():
        if unit not in final or final[unit]["split"] != "test":
            continue
        top = collections.Counter(statuses).most_common(1)[0][0]
        wrong = top != final[unit]["admission_label"]
        if len(set(statuses)) == 1:
            unanimous, wrong_unanimous = unanimous + 1, wrong_unanimous + wrong
        else:
            split, wrong_split = split + 1, wrong_split + wrong
    return {"unanimous": unanimous, "unanimous_wrong": wrong_unanimous,
            "unanimous_wrong_rate_wilson_95": review.wilson(wrong_unanimous, unanimous),
            "split": split, "split_plurality_wrong": wrong_split,
            "split_plurality_wrong_rate_wilson_95": review.wilson(wrong_split, split)}


def decide(scores: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The pre-registered rule, per use, from per-use scores of the majority and the validator."""
    def meets(method: str, use: str) -> tuple[bool, dict]:
        detail = {}
        ok = True
        for subset in ("divergent", "control"):
            m = scores.get(use, {}).get(method, {}).get(subset)
            if not m or not m["reference_not_admitted"] or not m["reference_admitted"]:
                ok = False
                detail[subset] = "too few cases"
                continue
            bound = upper_bound(m["false_admissions"], m["reference_not_admitted"], CONFIDENCE)
            block = m["false_blocks"] / m["reference_admitted"]
            detail[subset] = {"false_admission_upper_bound": bound, "false_block_rate": round(block, 4)}
            ok = ok and bound is not None and bound < FALSE_ADMISSION_BOUND and block < FALSE_BLOCK_RATE
        return ok, detail

    out = {}
    for use in USES:
        models_ok, models_detail = meets(MAJORITY, use)
        rules_ok, rules_detail = meets("validator", use)
        out[use] = {"decision": "models alone" if models_ok else "deterministic rules" if rules_ok else "experts",
                    "models": models_detail, "validator": rules_detail}
    return out


def analyze(models: Path, annotations: Path | None, adjudications: Path | None,
            predictions: Path | None) -> dict[str, Any]:
    model_annotations = review.load_annotations(models / "model_annotations.csv")
    report: dict[str, Any] = {"runs": reviewer_runs(models), "inter_model_agreement": inter_model(model_annotations),
                              # the withheld per-case files, so that what is published later can be checked against them
                              "files_sha256": {name: review.sha256_file(models / name)
                                               for name in ("model_annotations.csv", "model_predictions.csv")},
                              "decision_rule": {"false_admission_upper_bound_below": FALSE_ADMISSION_BOUND,
                                                "false_block_rate_below": FALSE_BLOCK_RATE, "confidence": CONFIDENCE,
                                                "majority": "at least 4 of the models"}}
    if not (annotations and adjudications):
        report["reference"] = "none yet: no expert labels (#23)"
        return report
    experts = review.load_annotations(annotations)
    final = review.resolve(experts, review.load_adjudications(adjudications, experts))
    model_predictions = review.load_predictions(models / "model_predictions.csv")
    rows = model_predictions + majority(model_predictions)
    if predictions:
        rows += review.load_predictions(predictions)
    by_use: dict[str, dict] = {use: {} for use in USES}
    for method in sorted({p["method"] for p in rows}):
        for use in USES:  # each method on the cases it answered: a model that failed a case is not scored on it
            mine = [p for p in rows if p["method"] == method and p["requested_use"] == use]
            answered = {(p["case_id"], use) for p in mine}
            reference = {u: v for u, v in final.items() if u in answered}
            if any(v["split"] == "test" for v in reference.values()):
                by_use[use][method] = review.score(reference, mine, split="test")["methods"][method]
    missed = errors(final, rows)
    report.update(reference="independently reviewed expert labels, test split", scores=by_use,
                  error_correlation=correlation(missed), consensus=consensus(final, model_predictions),
                  decisions=decide(by_use))
    return report


def public(report: dict[str, Any]) -> dict[str, Any]:
    """Only what cannot unblind a reviewer: how the models ran and how much they agree with each other."""
    return {k: report[k] for k in ("runs", "inter_model_agreement", "decision_rule", "files_sha256")}


def render(report: dict[str, Any]) -> str:
    lines = ["# Model reviewers on the blinded ClinVar packet", "",
             "| Model | Calls | Answered | With tool use | Later information seen | Median seconds |",
             "|---|---:|---:|---:|---:|---:|"]
    for r in report["runs"].values():
        lines.append(f"| {r['model']} | {r['calls']} | {r['answered']} | {r['with_tool_use']} | "
                     f"{r['later_information_seen']} | {r['median_seconds']} |")
    agreement = report["inter_model_agreement"]
    lines += ["", f"Agreement among the {len(agreement['reviewers'])} models on the {agreement['split']} split, before "
              "any reference (Krippendorff's alpha, bootstrap 95% interval):", "",
              "| Label | Units | All agree | Alpha (95% CI) |", "|---|---:|---:|---|"]
    for name, entry in [*agreement["admission"].items(), ("statement", agreement["statement"])]:
        if not entry:
            continue
        ci = entry["alpha_95_bootstrap"]
        alpha = f"{entry['krippendorff_alpha']}" + (f" ({ci[0]}–{ci[1]})" if ci else "")
        lines.append(f"| {name} | {entry['units_with_2plus_reviews']} | {entry['percent_agreement']} | {alpha} |")
    if "decisions" in report:
        lines += ["", "| Use | Decision |", "|---|---|"]
        lines += [f"| {use} | {d['decision']} |" for use, d in report["decisions"].items()]
        c = report["consensus"]
        lines += ["", f"When all models agreed ({c['unanimous']} case-uses), they were wrong {c['unanimous_wrong']} times; "
                  f"when they split ({c['split']}), the plurality was wrong {c['split_plurality_wrong']} times."]
    else:
        lines += ["", f"Reference: {report.get('reference', 'none')}. Scores, error correlation and the decision "
                  "statement follow once the expert labels are resolved."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", type=Path, required=True, help="The model_reviewers.py output, after export")
    parser.add_argument("--annotations", type=Path, help="Expert annotations")
    parser.add_argument("--adjudications", type=Path, help="Expert adjudications")
    parser.add_argument("--predictions", type=Path, help="The maintainer's validator and NCBI predictions")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--public", action="store_true", help="Write only what cannot unblind a reviewer")
    args = parser.parse_args(argv)
    report = analyze(args.models, args.annotations, args.adjudications, args.predictions)
    if args.public:
        report = public(report)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8",
                                              newline="\n")
    (args.output / "summary.md").write_text(render(report), encoding="utf-8", newline="\n")
    print(render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
