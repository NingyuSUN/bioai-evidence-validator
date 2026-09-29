"""Score the LLM benchmark: the models alone versus the same answers checked by bioevidence.

    uv run --frozen python evaluation/llm_benchmark/score.py --split pilot \
        --answers artifacts/llm-benchmark --output evaluation/llm_benchmark/results/pilot
    uv run --frozen python evaluation/llm_benchmark/score.py --split pilot \
        --output evaluation/llm_benchmark/results/pilot      # replay from the committed answers.jsonl

Six configurations per model, from three kinds of model answer:
  LLM only                          no source; the model's own decision
  LLM only + bioevidence            the same answer, built into a record; the validator decides
  LLM + source                      the variant's ClinVar submissions in the prompt; the model's own decision
  LLM + source + bioevidence        the same answer, built into a record; the validator decides
  LLM + source, batch               25 variants per prompt; the model's own decisions
  LLM + source, batch + bioevidence the same answers, each built into a record; the validator decides

"+ bioevidence" makes no extra model call. The model's claimed submissions become an evidence record
(the ClinVar importer's format); the record is validated with the ClinVar profile and grounded against
the pinned sample, and its clinical_reference decision replaces the model's. Citation correctness is
measured by exact comparison with the source rows given to the task, in this file, independently of
the repository's grounder.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

from bioevidence_validator.engine import RecordValidator
from bioevidence_validator.grounding import SnapshotStore, SourceBytesGrounder

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CLINVAR = REPO / "examples" / "clinvar_germline"
USE = "clinical_reference"
FIELDS = ["scv", "submitter", "classification", "review_status", "collection_method", "date_last_evaluated"]
DISSENT = {"uncertain significance", "likely benign", "benign", "benign/likely benign"}
CONFIGS = [("llm", "no_source", False, "LLM only"),
           ("llm_bioevidence", "no_source", True, "LLM only + bioevidence"),
           ("llm_source", "with_source", False, "LLM + source"),
           ("llm_source_bioevidence", "with_source", True, "LLM + source + bioevidence"),
           ("llm_batch", "with_source_batch", False, "LLM + source, batch of 25"),
           ("llm_batch_bioevidence", "with_source_batch", True, "LLM + source, batch of 25 + bioevidence")]
MODEL_NAMES = {"claude-opus": "Claude Opus 5.5", "gpt-astra": "GPT-6-Astra", "gemini-pro": "Gemini 3.1 Pro",
               "claude-haiku": "Claude Haiku 4.5", "gpt-luna": "GPT-5.6-Luna", "gemini-flash": "Gemini 3.8 Flash"}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def wilson(events: int, n: int, z: float = 1.959963984540054) -> list[float] | None:
    if not n:
        return None
    p = events / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def clean(value: str) -> str:
    return " ".join(value.split())


def clinvar_date(value: str) -> str:
    """A date in ClinVar's own form ('Sep 08, 2016'; '-' for none). The pilot showed models rewriting
    dates as ISO dates or blanks; that is a change of format, not of content, so it is not held against them."""
    text = clean(value)
    if text.lower() in ("", "-", "none", "n/a", "not provided", "unknown"):
        return "-"
    for pattern in ("%b %d, %Y", "%Y-%m-%d", "%B %d, %Y", "%d %b %Y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(text, pattern).strftime("%b %d, %Y")
        except ValueError:
            continue
    return text


def same(field: str, cited: str, truth: str) -> bool:
    if field == "date_last_evaluated":
        return clinvar_date(cited) == clinvar_date(truth)
    return clean(cited) == truth


def citations(answer: dict | None, source: list[dict]) -> dict:
    """Exact comparison of each cited submission with the task's source rows."""
    rows = {row["scv"]: row for row in source}
    cited = (answer or {}).get("submissions") or []
    exact = fabricated = misstated = 0
    for row in cited:
        truth = rows.get(clean(row["scv"]))
        if truth is None:
            fabricated += 1
        elif all(same(f, row[f], truth[f]) for f in FIELDS):
            exact += 1
        else:
            misstated += 1
    cited_scvs = {clean(row["scv"]) for row in cited}
    dissent = {row["scv"] for row in source if row["classification"].lower() in DISSENT}
    return {"cited": len(cited), "exact": exact, "fabricated": fabricated, "misstated": misstated,
            "complete": bool(source) and set(rows) <= cited_scvs, "omitted_dissent": sorted(dissent - cited_scvs)}


class Checker:
    """Build a record from a model answer and validate it with grounding, as the pipeline would."""

    def __init__(self):
        spec = importlib.util.spec_from_file_location("llm_benchmark_score_clinvar", CLINVAR / "pipeline.py")
        self.pipeline = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.pipeline)
        self.sample = self.pipeline.ClinVarSample()
        manifest = self.sample.manifest
        store = SnapshotStore({manifest["projection_sha256"]:
                               lambda: gzip.decompress((CLINVAR / manifest["projection_file"]).read_bytes())})
        self.validator = RecordValidator(profile=CLINVAR / "profile.yaml", grounders=[
            SourceBytesGrounder(store), self.pipeline.ClinVarGrounder(self.sample)])

    def check(self, task: dict, answer: dict | None) -> dict:
        if not answer or not answer["submissions"]:
            return {"status": "rejected", "codes": ["NO_EVIDENCE"]}  # nothing to build a record from
        case = {"variation_id": task["variation_id"], "gene": task["gene"], "submissions": [
            {"SCV": clean(s["scv"]), "Submitter": s["submitter"], "ClinicalSignificance": s["classification"],
             "ReviewStatus": s["review_status"], "CollectionMethod": s["collection_method"],
             "DateLastEvaluated": clinvar_date(s["date_last_evaluated"])} for s in answer["submissions"]]}
        try:
            record = self.sample.record(case)
        except ValueError:
            return {"status": "rejected", "codes": ["UNMAPPED_REVIEW_STATUS"]}  # the importer fails closed
        report = self.validator.validate(record)
        decision = next(d for d in report["use_decisions"] if d["use"] == USE)
        return {"status": decision["admission_status"], "codes": sorted({f["rule_id"] for f in report["findings"]})}


def score_rows(tasks: list[dict], references: dict[str, dict], answers: dict, checker: Checker) -> list[dict]:
    rows = []
    for backend in [m for m in MODEL_NAMES if m in {key[0] for key in answers}]:
        for task in tasks:
            reference = references[task["task_id"]]
            for config, condition, gated, _ in CONFIGS:
                result = answers.get((backend, condition, task["task_id"]))
                if result is None and not any(key[:2] == (backend, condition) for key in answers):
                    continue  # this model was not run in this condition
                answer = result["answer"] if result and result["ok"] else None
                cite = citations(answer, task["source"])
                if gated:
                    checked = checker.check(task, answer)
                    admitted = checked["status"] == "admitted"
                    # The model's own answer still reaches the reviewer: the validator adds findings, hides nothing.
                    flagged = ("BEV004" in checked["codes"] or ("BEV018" in checked["codes"] and bool(cite["omitted_dissent"]))
                               or (bool(answer) and answer["conflict"] == "yes"))
                    delivered = admitted  # anything else goes to a human with the findings
                    codes = checked["codes"]
                else:
                    admitted = bool(answer) and answer["decision"] == "admit"
                    flagged = bool(answer) and answer["conflict"] == "yes"
                    delivered = bool(answer)
                    codes = []
                rows.append({"backend": backend, "config": config, "task_id": task["task_id"],
                             "category": reference["category"], "expected": reference["expected_decision"],
                             "answered": answer is not None, "tools_used": bool(result and result["tools_used"]),
                             "admitted": admitted, "conflict_flagged": flagged, "delivered": delivered,
                             "reason_codes": codes, **{k: cite[k] for k in ("cited", "exact", "fabricated", "misstated")},
                             "complete": cite["complete"]})
    return rows


def rate(events: int, n: int) -> dict:
    return {"events": events, "n": n, "rate": round(events / n, 4) if n else None, "wilson_95": wilson(events, n)}


def metrics(rows: list[dict]) -> dict:
    stop = [r for r in rows if r["expected"] == "stop"]
    admit = [r for r in rows if r["expected"] == "admit"]
    conflict = [r for r in rows if r["category"] == "conflict"]
    delivered = [r for r in rows if r["delivered"] and r["cited"]]
    cited = sum(r["cited"] for r in delivered)
    return {
        "tasks": len(rows), "answered": sum(r["answered"] for r in rows), "tool_use": sum(r["tools_used"] for r in rows),
        "correct_decision": rate(sum(r["admitted"] == (r["expected"] == "admit") for r in rows), len(rows)),
        "correct_stop": rate(sum(not r["admitted"] for r in stop), len(stop)),
        "false_stop": rate(sum(not r["admitted"] for r in admit), len(admit)),
        "conflict_detected": rate(sum(r["conflict_flagged"] for r in conflict), len(conflict)),
        "citation_grounded": rate(sum(r["exact"] for r in delivered), cited),
        "hallucination": rate(sum(bool(r["fabricated"] or r["misstated"]) for r in delivered), len(delivered)),
        "fabricated_citations": sum(r["fabricated"] for r in delivered),
        "misstated_citations": sum(r["misstated"] for r in delivered),
    }


def pct(m: dict) -> str:
    return "N/A" if m["rate"] is None else f"{100 * m['rate']:.0f}%"


def expand_batch(raw: dict, tasks: dict[str, dict]) -> tuple[list[dict], dict]:
    """One normalized answer per task in a batch, matched on VariationID; omissions stay unanswered."""
    results = (raw["answer"] or {}).get("results", []) if raw["ok"] else []
    by_id: dict[str, dict] = {}
    duplicates = 0
    for result in results:
        vid = clean(result["variation_id"])
        if vid in by_id:
            duplicates += 1
        else:
            by_id[vid] = {k: v for k, v in result.items() if k != "variation_id"}
    wanted = {tasks[task_id]["variation_id"] for task_id in raw["task_ids"]}
    stats = {"batch_id": raw["batch_id"], "backend": raw["backend"], "size": len(raw["task_ids"]), "call_ok": raw["ok"],
             "returned": len(results), "duplicates": duplicates, "extra": len(set(by_id) - wanted),
             "missing": len(wanted - set(by_id)), "seconds": round(sum(a["seconds"] for a in raw["attempts"]), 1)}
    rows = []
    for task_id in raw["task_ids"]:
        answer = by_id.get(tasks[task_id]["variation_id"])
        rows.append({"backend": raw["backend"], "model": raw["model"], "condition": raw["condition"], "task_id": task_id,
                     "batch_id": raw["batch_id"], "prompt_sha256": raw["prompt_sha256"], "ok": answer is not None,
                     "answer": answer, "tools_used": raw["tools_used"]})
    return rows, stats


def render(summary: dict) -> str:
    lines = [f"# LLM benchmark: models alone vs. with bioevidence ({summary['split']} set)", "",
             f"{summary['tasks']} ClinVar tasks; reference: NCBI's 2023-09 review status. Models: "
             + ", ".join(f"{MODEL_NAMES[b]} (`{m['model']}`)" for b, m in summary["models"].items()) + ".", "",
             "| Model | Configuration | Correct decision | Correct STOP | False STOP | Conflict detected | "
             "Citation grounded | Hallucination |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for backend, configs in summary["results"].items():
        for config, _, _, label in CONFIGS:
            if config not in configs:
                continue
            m = configs[config]
            lines.append(f"| {MODEL_NAMES[backend]} | {label} | {pct(m['correct_decision'])} | {pct(m['correct_stop'])} | "
                         f"{pct(m['false_stop'])} | {pct(m['conflict_detected'])} | {pct(m['citation_grounded'])} | "
                         f"{pct(m['hallucination'])} |")
    lines += ["", "Correct STOP: share of tasks that should not be admitted (insufficient evidence, conflict, "
              "variant not in ClinVar) that were not admitted. False STOP: share of admissible tasks that were not "
              "admitted. Conflict detected: share of conflicting variants whose conflict was reported (with bioevidence, by the model or by the validator's findings). Citation "
              "grounded: share of cited submissions matching the source (dates compared as dates), among delivered answers. "
              "Hallucination: share of delivered answers citing at least one submission that does not exist for "
              "the variant or is misstated. Delivered: every model answer; with bioevidence, only admitted records "
              "(the rest go to a human with the validator's findings).", "",
              "Wilson 95% intervals, counts and per-task rows are in `summary.json` and `rows.jsonl`.", ""]
    if summary["batches"]:
        lines += ["## Batch completeness", "", "| Model | Batches | Variants asked | Returned | Missing | Duplicated | "
                  "Not asked |", "|---|---:|---:|---:|---:|---:|---:|"]
        for backend in [m for m in MODEL_NAMES if any(b["backend"] == m for b in summary["batches"])]:
            mine = [b for b in summary["batches"] if b["backend"] == backend]
            lines.append(f"| {MODEL_NAMES[backend]} | {len(mine)} | {sum(b['size'] for b in mine)} | "
                         f"{sum(b['returned'] for b in mine)} | {sum(b['missing'] for b in mine)} | "
                         f"{sum(b['duplicates'] for b in mine)} | {sum(b['extra'] for b in mine)} |")
        lines += ["", "A missing variant has no answer: it counts as not admitted, and as unanswered.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=["pilot", "test"], required=True)
    parser.add_argument("--answers", type=Path, help="Raw run_models.py output; omit to replay answers.jsonl")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    tasks = load_jsonl(ROOT / "tasks" / f"{args.split}.jsonl")
    references = {r["task_id"]: r for r in load_jsonl(ROOT / "tasks" / "references.jsonl") if r["split"] == args.split}
    args.output.mkdir(parents=True, exist_ok=True)
    answers_path = args.output / "answers.jsonl"
    if args.answers:
        folder = args.answers / args.split
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        kept, batch_stats = [], []
        by_task = {task["task_id"]: task for task in tasks}
        for path in sorted(folder.glob("*/*/*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["backend"] = path.parent.parent.name  # the model key; early pilot files used the CLI name
            if raw["condition"] == "with_source_batch":
                rows_, stats = expand_batch(raw, by_task)
                kept += rows_
                batch_stats.append(stats)
                continue
            kept.append({k: raw[k] for k in ("backend", "model", "condition", "task_id", "prompt_sha256", "ok",
                                             "answer", "tools_used")}
                        | {"seconds": round(sum(a["seconds"] for a in raw["attempts"]), 1),
                           "attempts": len(raw["attempts"])})
        models = {b: {"model": v["model"], "cli_version": v["cli_version"], "tier": v.get("tier")}
                  for b, v in manifest["backends"].items()}
        answers_path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in kept)
                                + json.dumps({"models": models, "batches": batch_stats}, sort_keys=True) + "\n",
                                encoding="utf-8", newline="\n")
    lines = load_jsonl(answers_path)
    models, batch_stats = lines[-1]["models"], lines[-1].get("batches", [])
    answers = {(r["backend"], r["condition"], r["task_id"]): r for r in lines[:-1]}
    rows = score_rows(tasks, references, answers, Checker())
    results = {backend: {config: metrics(mine) for config, *_ in CONFIGS
                         if (mine := [r for r in rows if r["backend"] == backend and r["config"] == config])}
               for backend in [m for m in MODEL_NAMES if any(r["backend"] == m for r in rows)]}
    summary = {"benchmark": "llm-benchmark-v1", "split": args.split, "tasks": len(tasks), "use": USE, "models": models,
               "answers_sha256": hashlib.sha256(answers_path.read_bytes()).hexdigest(), "results": results,
               "batches": batch_stats}
    (args.output / "rows.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows),
                                            encoding="utf-8", newline="\n")
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                                              encoding="utf-8", newline="\n")
    (args.output / "summary.md").write_text(render(summary), encoding="utf-8", newline="\n")
    print(render(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
