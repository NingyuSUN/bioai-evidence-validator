"""Audit dry run (#24): what an audit of the auto-admitted single-cell annotations would report.

No expert has audited these records. This dry run runs the audit procedure end to end on the held-out results
(protocol 2: 6 models x 46 clusters) and checks its statistics against a census:

1. export each episode's final route (auto-admitted, to a person) as a predictions file, one record per model and
   cluster, under an opaque case id;
2. draw a seeded random sample with `bioevidence review audit-sample`: enough auto-admitted records to bound their
   error rate below 5% if none is wrong, and 10 records from the other route mixed in;
3. write the auditors' packet: each record's cluster, marker table and claim, in shuffled order, without its route,
   model or the authors' label;
4. fill the audit sheet with a stand-in auditor, the dataset authors' own cluster labels: a claim is correct when it is
   the authors' term, a coarser or a finer one, and admissible when it is correct and passes the identifier checks;
5. score it with `bioevidence review audit-score`, and compare with the census of all auto-admitted records, which
   the authors' labels allow here and a real audit does not.

The stand-in is not an expert, and it records no time, so the expert-time columns stay empty.

    python evaluation/llm_benchmark/audit_celltype.py --output <new directory>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import celltype_loop as cl  # noqa: E402

from bioevidence_validator import audit, cli, review  # noqa: E402

RESULTS = ROOT / "results"
METHOD, USE, PROFILE = "llm-feedback-loop", "research_summary", "singlecell-celltype"
SEED, TARGET, CONTROLS = 20261006, 0.05, 10
STAND_IN = "stand-in: the dataset authors' cluster labels (not an expert)"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def export(case: cl.Case) -> dict[str, dict]:
    """case id -> the episode's final record, its route and what the stand-in needs."""
    profile = sha256_text((cl.CASE / "profile.yaml").read_text(encoding="utf-8").replace("\r\n", "\n"))
    cases = {}
    for row in cl.load_jsonl(RESULTS / "celltype-test" / "episodes.jsonl"):
        if not row["attempts"]:
            continue  # no annotation, no record
        task = case.tasks[row["task_id"]]
        got = [c["answer"] for c in row["calls"] if c["answer"] and c["answer"]["decision"] == "annotate"]
        answer = got[len(row["attempts"]) - 1]
        record = cl.record(case, task, answer)
        case_id = "sc-" + sha256_text(f"{row['task_id']}|{row['model']}")[:12]
        cases[case_id] = {"task": task, "answer": answer, "route": row["attempts"][-1]["status"], "profile": profile,
                          "record_sha256": sha256_text(json.dumps(record, sort_keys=True, separators=(",", ":")))}
    return cases


def packet(case: cl.Case, cases: dict[str, dict], sheet: list[dict[str, str]]) -> str:
    lines = ["# Audit packet: single-cell annotations for research summaries", "",
             "For each record, decide from the cluster's markers:", "",
             "- `mapping_label`: is the claimed cell type right for this cluster? `correct`, `incorrect` or `uncertain`. "
             "A correct but coarser type is `correct`.",
             "- `admission_label`: should the record be admitted for a research summary as it stands? `admitted`, "
             "`review_required` or `rejected`.", "",
             "Write both, with a short rationale, your reviewer id and qualification, the time and `minutes_spent`, in "
             "`audit_sheet.csv`. Records are in random order; their route, model and the authors' label are withheld.",
             ""]
    for number, row in enumerate(sheet, start=1):
        c = cases[row["case_id"]]
        task, answer = c["task"], c["answer"]
        markers = ", ".join(f"{m['gene']} ({float(m['logfc']):.1f}; {float(m['pct_in']):.0%} vs {float(m['pct_out']):.0%})"
                            for m in task["markers"])
        cited = ", ".join(f"{m['gene']} ({m['stance'].replace('_', ' ')})" for m in answer["markers"]) or "none"
        lines += [f"## {number}. `{row['case_id']}`", "",
                  f"- Cluster `{task['cluster']}` of a {task['species']} {task['tissue']} dataset ({task['assay']})",
                  f"- Top markers (log fold change; share of cells in vs out of the cluster): {markers}",
                  f"- **Claim:** {answer['cell_type_id']} *{answer['cell_type_label']}*",
                  f"- Cited markers: {cited}", ""]
    return "\n".join(lines)


def stand_in(case: cl.Case, truth: dict[str, dict], c: dict) -> dict[str, str]:
    """The labels the authors' term implies for one record."""
    kind = cl.outcome(case, truth[c["task"]["task_id"]]["term"], c["answer"])
    issues = cl.problems(case, c["task"], c["answer"])
    correct = kind in ("exact", "coarser", "finer")
    t = truth[c["task"]["task_id"]]
    return {"mapping_label": "correct" if correct else "incorrect",
            "mapping_rationale": f"authors' term {t['term']} ({t['label']}); the claim is {kind}",
            "admission_label": "admitted" if correct and not issues else "rejected",
            "admission_rationale": "; ".join(issues) or ("passes the identifier checks" if correct else "wrong cell type")}


def main(argv: list[str] | None = None) -> int:
    options = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    options.add_argument("--output", type=Path, required=True, help="A new directory")
    args = options.parse_args(argv)
    out: Path = args.output
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty; refusing to overwrite an audit")
    out.mkdir(parents=True, exist_ok=True)
    case = cl.Case()
    truth = {t["task_id"]: t for t in cl.load_jsonl(cl.SOURCES / "truth.jsonl")}
    cases = export(case)

    predictions = [{"case_id": k, "requested_use": USE, "record_sha256": c["record_sha256"],
                    "profile_sha256": c["profile"], "method": METHOD, "predicted_status": c["route"]}
                   for k, c in sorted(cases.items())]
    review.write_csv(out / "predictions.csv", predictions, review.PREDICTION_COLUMNS)
    sampled = out / "sample"
    status = cli.main(["review", "audit-sample", "--predictions", str(out / "predictions.csv"), "--method", METHOD,
                       "--use", USE, "--target", str(TARGET), "--controls", str(CONTROLS), "--seed", str(SEED),
                       "--profile-id", PROFILE, "--output-dir", str(sampled)])
    if status:
        return status
    sheet = list(review._read_csv(sampled / "audit_sheet.csv", review.ANNOTATION_COLUMNS,
                                  review.OPTIONAL_ANNOTATION_COLUMNS))
    (out / "audit_packet.md").write_text(packet(case, cases, sheet), encoding="utf-8", newline="\n")

    filled = [{**row, "annotation_id": f"stand-in:{row['case_id']}", "reviewer_id": "stand-in-authors-labels",
               "reviewer_qualification": STAND_IN, "annotated_at": "2026-10-06T00:00:00Z",
               "evidence_refs_json": json.dumps([f"authors-label:{cases[row['case_id']]['task']['task_id']}"]),
               **stand_in(case, truth, cases[row["case_id"]])} for row in sheet]
    review.write_csv(out / "stand_in_annotations.csv", filled,
                     review.ANNOTATION_COLUMNS + review.OPTIONAL_ANNOTATION_COLUMNS)
    status = cli.main(["review", "audit-score", "--manifest", str(sampled / "audit_manifest.json"), "--annotations",
                       str(out / "stand_in_annotations.csv"), "--output", str(out / "audit_report.json")])
    if status:
        return status

    report = json.loads((out / "audit_report.json").read_text(encoding="utf-8"))
    census: dict[str, Counter] = {}
    for c in cases.values():
        labels = stand_in(case, truth, c)
        census.setdefault(c["route"], Counter())["errors" if audit._is_error(c["route"], labels) else "fine"] += 1
    checks = {}
    for route, s in report["routes"].items():
        errors, n = census[route]["errors"], sum(census[route].values())
        rate = errors / n
        checks[route] = {"census_errors": errors, "census_records": n, "census_error_rate": round(rate, 4),
                         "audit_error_rate": s["error_rate"], "audit_wilson_95": s["error_rate_wilson_95"],
                         "audit_upper_bound": s["error_rate_upper_bound"],
                         "census_within_wilson": s["error_rate_wilson_95"][0] <= rate <= s["error_rate_wilson_95"][1],
                         "census_below_upper_bound": rate <= s["error_rate_upper_bound"]}
    summary = {"dry_run": "audit of the single-cell held-out results with a stand-in auditor (#24)",
               "stand_in": STAND_IN, "seed": SEED, "target": TARGET, "controls": CONTROLS, "audit": report,
               "census": checks, "episodes_sha256": hashlib.sha256((RESULTS / "celltype-test" / "episodes.jsonl")
                                                                   .read_bytes().replace(b"\r\n", b"\n")).hexdigest()}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8",
                                      newline="\n")
    (out / "summary.md").write_text(render(summary), encoding="utf-8", newline="\n")
    print(render(summary))
    return 0


def render(summary: dict) -> str:
    report = summary["audit"]
    admitted = report["routes"]["admitted"]
    check = summary["census"]["admitted"]
    lines = ["# Audit dry run: single-cell held-out annotations", "",
             f"**Not an expert audit.** The auditor is a stand-in: {summary['stand_in'].removeprefix('stand-in: ')}. "
             "It shows what the audit procedure reports, and checks its statistics against a census.", "",
             audit.render_audit(report).split("\n", 2)[2].rstrip(), "",
             "## Against the census", "",
             "The authors' labels cover every record, so here the error rate of the whole route is known:", "",
             "| Route | Census error rate | Audit estimate | Wilson 95% | Upper bound (95%) | Census inside |",
             "|---|---:|---:|---|---:|---|"]
    for route, c in summary["census"].items():
        low, high = c["audit_wilson_95"]
        inside = "yes" if c["census_within_wilson"] and c["census_below_upper_bound"] else "no"
        lines.append(f"| {audit.ROUTES[route]} | {c['census_errors']}/{c['census_records']} "
                     f"({100 * c['census_error_rate']:.1f}%) | {100 * c['audit_error_rate']:.1f}% | "
                     f"{100 * low:.1f}%–{100 * high:.1f}% | {100 * c['audit_upper_bound']:.1f}% | {inside} |")
    verdict = "meets" if report["admitted_error_upper_bound"] < summary["target"] else "does not meet"
    lines += ["", f"The audit was sized to show an auto-admitted error rate below {100 * summary['target']:.0f}% if "
              f"none of {admitted['audited']} sampled records was wrong. It found {admitted['errors']}, so this route "
              f"{verdict} a {100 * summary['target']:.0f}% target: the census rate is "
              f"{100 * check['census_error_rate']:.1f}%. An audit is how a deployment would learn that these "
              "annotations need review, or a better model, before research summaries rely on them.", "",
              f"Seed {summary['seed']}; `sample/audit_manifest.json` holds the routes and stays with the maintainer. "
              "Expert time is not measured: the stand-in records none."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
