"""Run the frozen real-source case and separately labeled controlled perturbations."""
import argparse
import csv
import json
from pathlib import Path

from pipeline import DogNames, ROOT, FAULTS, perturb, metrics, digest, aggregate_quality_ablation
from bioevidence_validator.engine import RecordValidator


def run(output: Path):
    if output.exists():
        raise ValueError("Use a new output directory to preserve previous evidence")
    source = DogNames()
    cases_raw = (ROOT / "reference_cases.json").read_bytes()
    cases = json.loads(cases_raw)
    context = RecordValidator(profile=ROOT / "profile.yaml")
    inputs, reports, rows = [], [], []

    def evaluate(record, case_id, cohort, category, expected, expected_code=None):
        report = context.validate(record)
        # Timestamps are omitted from replay artifacts so repeated runs are byte-identical.
        report.pop("validated_at")
        row = {"case_id":case_id, "cohort":cohort, "category":category, "expected_status":expected,
               "schema_only":"admitted" if report["schema_valid"] else "rejected",
               "aggregate_quality":aggregate_quality_ablation(record,report), "full":report["overall_status"],
               "reason_codes":sorted({f["rule_id"] for f in report["findings"]}),"input_sha256":report["input_sha256"]}
        if expected_code and expected_code not in row["reason_codes"]:
            raise AssertionError((case_id,expected_code,row))
        if cohort != "trust_boundary" and row["full"] != expected:
            raise AssertionError((case_id,expected,row))
        inputs.append(record); reports.append(report); rows.append(row)

    bases = []
    for case in cases:
        actual = source.candidates(case["query"])
        if actual != case["expected_candidates"]:
            raise ValueError(f"Source/reference candidate drift: {case['case_id']}")
        record = source.record(case["query"],case["case_id"])
        evaluate(record,case["case_id"],"real_source",case["stratum"],case["expected_status"])
        if case["expected_status"] == "admitted":bases.append((case,record))
    # Deterministic seed selection; all mutations of a seed remain grouped by case ID.
    for case,record in bases[::3]:
        for kind,(expected,code) in FAULTS.items():
            evaluate(perturb(record,kind),case["case_id"]+":"+kind,"controlled_fault",kind,expected,code)
        evaluate(perturb(record,"falsified_target"),case["case_id"]+":falsified_target",
                 "trust_boundary","falsified_target","rejected")
    cohorts = {cohort:{method:metrics([r for r in rows if r['cohort']==cohort],method)
                      for method in ["schema_only","aggregate_quality","full"]}
               for cohort in ["real_source","controlled_fault","trust_boundary"]}
    summary={"benchmark":"vbo-canine-v1", "validator_version":reports[0]["validator_version"],
             "source_release":source.manifest["release"], "source_sha256":source.manifest["projection_sha256"],
             "reference_sha256":digest(cases_raw), "profile_sha256":context.profile_sha256,
             "schema_sha256":context.schema_sha256,"source_terms":len(source.terms),"cohorts":cohorts,
             "label_origin":"Source-derived contract expectations and authored fault specifications; no independent human annotations.",
             "limitation":"No biological accuracy estimate. Correlated names and injected faults are not independent observations. Falsified targets expose the generic engine's trust in supplied metadata."}
    output.mkdir(parents=True)
    for name,values in [("records.jsonl",inputs),("reports.jsonl",reports),("decisions.jsonl",rows)]:
        (output/name).write_text(''.join(json.dumps(v,sort_keys=True,ensure_ascii=False)+'\n' for v in values),encoding='utf-8',newline='\n')
    (output/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    lines=['# VBO canine evidence benchmark','','Source-derived reference labels; no independent expert annotation.','',
           '| Cohort | Method | n | False admission | False block | Review |','|---|---|---:|---:|---:|---:|']
    def ratio(num,den):return f'{num}/{den}' if den else 'N/A'
    for cohort,methods in cohorts.items():
        for method,m in methods.items():
            lines.append(f"| {cohort} | {method} | {m['n']} | {ratio(m['false_admissions'],m['expected_non_admitted'])} | {ratio(m['false_blocks'],m['expected_admitted'])} | {m['status_counts'].get('review_required',0)}/{m['n']} |")
    lines += ['',summary['limitation'],'','Schema-only validates record shape. Aggregate-quality ablation restores the old all-support method grouping while holding other checks fixed. Full uses per-required-type quality checks.','']
    (output/'summary.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    with (output/'review_queue.csv').open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,lineterminator='\n',fieldnames=['case_id','query','candidate_ids','decision','reviewer','rationale','decided_at'])
        writer.writeheader()
        for case in cases:
            if case['stratum']=='ambiguous_name':
                writer.writerow({'case_id':case['case_id'],'query':case['query'],
                                 'candidate_ids':';'.join(case['expected_candidates'])})
    manifest={p.name:digest(p.read_bytes()) for p in sorted(output.iterdir()) if p.is_file()}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(summary,indent=2))
    return summary


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.output)
