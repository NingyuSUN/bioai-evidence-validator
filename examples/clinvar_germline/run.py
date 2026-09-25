"""Run the frozen ClinVar case: policy reproduction, three-year stability, controlled faults and trust boundary."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from bioevidence_validator import __version__
from bioevidence_validator.engine import RecordValidator
from pipeline import (FAULTS, ROOT, STARS, USES, ClinVarSample, aggregate_quality_ablation, digest, metrics,
                      ncbi_expected, outcome_rate, perturb, stability)

SEEDS = 16


def run(output: Path) -> dict:
    if output.exists():
        raise ValueError("Use a new output directory to preserve previous evidence")
    source = ClinVarSample()
    context = RecordValidator(profile=ROOT / "profile.yaml")
    decisions, divergences, fault_rows = [], [], []

    # A. Policy reproduction and B. stability share one validation per sampled variant.
    for case in source.cases:
        record = source.record(case)
        report = context.validate(record)
        status = {d["use"]: d["admission_status"] for d in report["use_decisions"]}
        codes = {d["use"]: d["reason_codes"] for d in report["use_decisions"]}
        decisions.append({"case": case, "record": record, "status": status})
        for use in USES:
            expected = ncbi_expected(case["stratum"], use)
            if (status[use] == "admitted") != (expected == "admitted"):
                divergences.append({"variation_id": case["variation_id"], "stratum": case["stratum"], "use": use,
                                    "ncbi_2023_09": expected, "validator": status[use], "reason_codes": ";".join(codes[use])})

    reproduction = {}
    for use in USES:
        rows = [(ncbi_expected(d["case"]["stratum"], use) == "admitted", d["status"][use] == "admitted") for d in decisions]
        stricter = [x for x in divergences if x["use"] == use and x["ncbi_2023_09"] == "admitted"]
        looser = [x for x in divergences if x["use"] == use and x["ncbi_2023_09"] != "admitted"]
        reproduction[use] = {
            "n": len(rows), "agreement": sum(a == b for a, b in rows),
            "ncbi_admitted": sum(a for a, _ in rows), "validator_admitted": sum(b for _, b in rows),
            "validator_stricter": len(stricter), "validator_looser": len(looser),
            "stricter_by_reason": dict(sorted(Counter(x["reason_codes"] for x in stricter).items())),
            "stricter_by_stratum": dict(sorted(Counter(x["stratum"] for x in stricter).items())),
            "looser_by_stratum": dict(sorted(Counter(x["stratum"] for x in looser).items())),
        }

    plp = [d for d in decisions if d["case"]["stratum"] in STARS]
    stability_by_use = {use: {state: stability([d["case"] for d in plp if (d["status"][use] == "admitted") == (state == "admitted")])
                              for state in ["admitted", "not_admitted"]} for use in USES}
    stability_by_stratum = {name: stability([d["case"] for d in plp if d["case"]["stratum"] == name]) for name in STARS}

    # C. Controlled faults and D. trust boundary, as in the VBO case.
    def evaluate(record, case_id, cohort, category, expected, code=None):
        report = context.validate(record)
        row = {"case_id": case_id, "cohort": cohort, "category": category, "expected_status": expected,
               "schema_only": "admitted" if report["schema_valid"] else "rejected",
               "aggregate_quality": aggregate_quality_ablation(record, report), "full": report["overall_status"],
               "reason_codes": sorted({f["rule_id"] for f in report["findings"]})}
        if code and code not in row["reason_codes"]:
            raise AssertionError((case_id, code, row))
        if cohort != "trust_boundary" and row["full"] != expected:
            raise AssertionError((case_id, expected, row))
        fault_rows.append(row)

    admitted_all = [d for d in decisions if all(s == "admitted" for s in d["status"].values())]
    step = max(1, len(admitted_all) // SEEDS)
    for d in admitted_all[::step][:SEEDS]:
        for kind, (expected, code) in FAULTS.items():
            evaluate(perturb(d["record"], kind), f"{d['case']['variation_id']}:{kind}", "controlled_fault", kind, expected, code)
    uncurated = [d for d in decisions if d["case"]["stratum"] == "no_criteria"][:SEEDS]
    for d in uncurated:
        evaluate(perturb(d["record"], "fabricated_expert_review"), f"{d['case']['variation_id']}:fabricated_expert_review",
                 "trust_boundary", "fabricated_expert_review", "rejected")
    faults = {cohort: {method: metrics([r for r in fault_rows if r["cohort"] == cohort], method)
                       for method in ["schema_only", "aggregate_quality", "full"]}
              for cohort in ["controlled_fault", "trust_boundary"]}

    # Whole-population context computed by prepare_source.py from the pinned upstream files.
    population_raw = (ROOT / source.manifest["population_file"]).read_bytes()
    if digest(population_raw) != source.manifest["population_sha256"]:
        raise ValueError("Frozen ClinVar population table hash mismatch")
    population = {name: {group: outcome_rate(values if group == "all" else values[group])
                         for group in ["all", "with_dissenting_submission", "without_dissenting_submission"]}
                  for name, values in json.loads(population_raw)["population_2023_09_germline_plp"].items()}

    summary = {
        "benchmark": "clinvar-germline-v1", "validator_version": __version__,
        "source_release": "ClinVar 2023-09 (evidence) / 2026-09 (outcome)",
        "source_sha256": source.manifest["projection_sha256"], "profile_sha256": context.profile_sha256,
        "schema_sha256": context.schema_sha256, "variants": len(decisions),
        "strata": dict(sorted(Counter(d["case"]["stratum"] for d in decisions).items())),
        "policy_reproduction": reproduction, "stability_by_use": stability_by_use,
        "stability_by_stratum": stability_by_stratum, "population_stability": population, "faults": faults,
        "label_origin": ("Policy reproduction compares with NCBI's own 2023-09 aggregate review status; stability uses "
                         "NCBI's 2026-09 aggregate classification; faults are authored specifications. "
                         "No independent human annotation."),
        "limitation": ("Stability is not correctness, and ClinVar's own review tiers influence later submissions. "
                       "Strata are equal-sized, so pooled sample rates are not population rates. "
                       "Observational; not for clinical use."),
    }

    output.mkdir(parents=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    with (output / "divergences.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, lineterminator="\n",
                                fieldnames=["variation_id", "stratum", "use", "ncbi_2023_09", "validator", "reason_codes"])
        writer.writeheader()
        writer.writerows(sorted(divergences, key=lambda x: (x["use"], x["stratum"], int(x["variation_id"]))))
    (output / "decisions.jsonl").write_text("".join(
        json.dumps({"variation_id": d["case"]["variation_id"], "stratum": d["case"]["stratum"], **d["status"]}, sort_keys=True) + "\n"
        for d in decisions), encoding="utf-8", newline="\n")
    (output / "faults.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in fault_rows),
                                         encoding="utf-8", newline="\n")
    (output / "summary.md").write_text(render(summary), encoding="utf-8", newline="\n")
    manifest = {p.name: digest(p.read_bytes()) for p in sorted(output.iterdir()) if p.is_file()}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def pct(stats: dict) -> str:
    if not stats["evaluable"]:
        return "N/A"
    low, high = stats["wilson_95"]
    return f"{stats['destabilized']}/{stats['evaluable']} = {100 * stats['rate']:.2f}% ({100 * low:.2f}–{100 * high:.2f})"


def render(summary: dict) -> str:
    lines = ["# ClinVar germline evidence benchmark", "",
             "Evidence: ClinVar 2023-09 submissions. Outcome: ClinVar 2026-09 aggregate classification. "
             "No independent expert annotation.", "",
             "## A. Policy reproduction against NCBI's 2023-09 review status", "",
             "| Use | n | Agreement | NCBI admitted | Validator admitted | Validator stricter | Validator looser |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for use, r in summary["policy_reproduction"].items():
        lines.append(f"| {use} | {r['n']} | {r['agreement']}/{r['n']} | {r['ncbi_admitted']} | {r['validator_admitted']} | "
                     f"{r['validator_stricter']} | {r['validator_looser']} |")
    lines += ["", "## B. Three-year stability of 2023-09 P/LP classifications (destabilized = conflicting or downgraded by 2026-09; Wilson 95% CI)", "",
              "| Use | Admitted in 2023 | Not admitted in 2023 |", "|---|---|---|"]
    for use, groups in summary["stability_by_use"].items():
        lines.append(f"| {use} | {pct(groups['admitted'])} | {pct(groups['not_admitted'])} |")
    lines += ["", "| 2023-09 review status stratum | Destabilized by 2026-09 |", "|---|---|"]
    for name, stats in summary["stability_by_stratum"].items():
        lines.append(f"| {name} | {pct(stats)} |")
    lines += ["", "## Whole-population context: all 2023-09 germline P/LP variants", "",
              "Validator routes a variant with any dissenting (VUS/LB/B) submission to review (BEV004); NCBI's aggregate may still admit it.", "",
              "| 2023-09 review status | All | With a dissenting submission | Without |", "|---|---|---|---|"]
    for name, groups in summary["population_stability"].items():
        lines.append(f"| {name} | " + " | ".join(pct(groups[g]) for g in
                     ["all", "with_dissenting_submission", "without_dissenting_submission"]) + " |")
    lines += ["", "## C/D. Controlled faults and trust boundary (false admissions)", "",
              "| Cohort | Schema-only | Aggregate-quality ablation | Full |", "|---|---:|---:|---:|"]
    for cohort, methods in summary["faults"].items():
        cells = [f"{m['false_admissions']}/{m['expected_non_admitted']}" for m in methods.values()]
        lines.append(f"| {cohort} | " + " | ".join(cells) + " |")
    lines += ["", summary["limitation"], ""]
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
