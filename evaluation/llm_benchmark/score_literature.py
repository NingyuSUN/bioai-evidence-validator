"""Score the literature benchmark: the models alone versus the same answers checked by bioevidence.

    uv run --frozen python evaluation/llm_benchmark/score_literature.py --split pilot \
        --answers artifacts/llm-benchmark --output evaluation/llm_benchmark/results/literature-pilot
    (omit --answers to replay the committed answers.jsonl)

Four configurations per model, from two model calls per task:
  LLM only                     the claim, PMID and title, without the paper; the model's own decision
  LLM only + bioevidence       the same answer as a record; the validator decides
  LLM + paper                  the paper's paragraphs in the prompt; the model's own decision
  LLM + paper + bioevidence    the same answer as a record; the validator decides

"+ bioevidence" makes no extra model call. The model's quotes become evidence items of a record citing the
task's PMID (examples/civic_literature/profile.yaml), pinned to the paper's snapshot as `bioevidence ground`
does, and checked by the literature grounder. An admitted record keeps the model's decision; anything else
goes to a human with the findings. Whether a quote is in the paper is measured here, with its own simple
normalisation, independently of the grounder.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import importlib.util
import json
import math
import sys
import unicodedata
from pathlib import Path

from bioevidence_validator.engine import RecordValidator
from bioevidence_validator.grounding import SourceBytesGrounder

ROOT = Path(__file__).resolve().parent
TASKS = ROOT / "literature_tasks"
CASE = ROOT.parents[1] / "examples" / "civic_literature"
CONFIGS = [("llm", "no_source", False, "LLM only"), ("llm_bioevidence", "no_source", True, "LLM only + bioevidence"),
           ("llm_paper", "with_source", False, "LLM + paper"),
           ("llm_paper_bioevidence", "with_source", True, "LLM + paper + bioevidence")]
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


def plain(text: str) -> str:
    """Independent of the grounder: NFKC, straight quotes and dashes, single spaces, no space just inside
    brackets or before punctuation (JATS writes `( Figure 2 )`), case kept."""
    text = unicodedata.normalize("NFKC", text)
    for fancy, simple in (("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"'), ("\u2013", "-"),
                          ("\u2014", "-"), ("\u2212", "-")):
        text = text.replace(fancy, simple)
    words = " ".join(text.split())
    for gap, joined in ((" )", ")"), (" ]", "]"), ("( ", "("), ("[ ", "["), (" ,", ","), (" .", "."), (" ;", ";"),
                        (" :", ":")):
        while gap in words:
            words = words.replace(gap, joined)
    return words


def in_paper(quote: str, paragraphs: list[list[str]]) -> bool:
    """A quote counts as found if it occurs verbatim, or would if its final punctuation came after a
    parenthetical reference the quote leaves out ('... group.' for '... group (Table 2).')."""
    needle = plain(quote)
    if not needle:
        return False
    stem = needle.rstrip(" .;:")
    for block in paragraphs:
        text = plain(block[-1])
        if needle in text:
            return True
        at = text.find(stem)
        while stem and at >= 0:
            rest = text[at + len(stem):].lstrip()
            while rest.startswith("(") and ")" in rest:
                rest = rest[rest.index(")") + 1:].lstrip()
            if rest == "" or rest[0] in ".;:":
                return True
            at = text.find(stem, at + 1)
    return False


class Checker:
    def __init__(self):
        sys.path.insert(0, str(CASE))
        try:
            spec = importlib.util.spec_from_file_location("llm_literature_score_pipeline", CASE / "pipeline.py")
            self.pipeline = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.pipeline)
        finally:
            sys.path.pop(0)
        self.corpus = self.pipeline.Corpus()
        self.validator = RecordValidator(profile=CASE / "profile.yaml", grounders=[
            SourceBytesGrounder(self.corpus.store), self.corpus.grounder()])

    def check(self, task: dict, answer: dict | None) -> dict:
        if not answer or answer["decision"] == "stop" or not answer["quotes"]:
            return {"status": "not_submitted", "codes": []}
        claim = task["claim"]
        item = {"evidence_id": task["task_id"], "molecular_profile_id": "0", "molecular_profile": claim["molecular_profile"],
                "evidence_direction": "Supports" if answer["decision"] == "supports" else "Does Not Support",
                "significance": claim["significance"], "disease": claim["disease"], "therapies": claim["therapies"]}
        first = answer["quotes"][0]
        record = self.pipeline.record(task["pmid"], task["title"], item, (first["paragraph"], first["text"]),
                                      method="llm_extraction")
        template = record["evidence_items"][0]
        record["evidence_items"] = []
        for n, quote in enumerate(answer["quotes"], start=1):
            evidence = copy.deepcopy(template)
            evidence.update(id=f"bioev:quote-{n}", locator=f"#{quote['paragraph'].strip().strip('[]#')}",
                            extracted_text=quote["text"])
            record["evidence_items"].append(evidence)
        record["statement"]["evidence_lines"][0]["evidence_item_ids"] = [e["id"] for e in record["evidence_items"]]
        report = self.validator.validate(self.corpus.pin(record))
        return {"status": report["overall_status"], "codes": sorted({f["rule_id"] for f in report["findings"]})}


def score_rows(tasks, references, answers, papers, checker) -> list[dict]:
    rows = []
    for backend in [m for m in MODEL_NAMES if m in {key[0] for key in answers}]:
        for task in tasks:
            reference = references[task["task_id"]]
            for config, condition, gated, _ in CONFIGS:
                if not any(key[:2] == (backend, condition) for key in answers):
                    continue
                result = answers.get((backend, condition, task["task_id"]))
                answer = result["answer"] if result and result["ok"] else None
                quotes = (answer or {}).get("quotes") or []
                found = sum(in_paper(q["text"], papers[task["pmid"]]) for q in quotes)
                if gated:
                    checked = checker.check(task, answer)
                    final = answer["decision"] if checked["status"] == "admitted" else "stop"
                    codes = checked["codes"]
                else:
                    final = answer["decision"] if answer else "stop"
                    codes = []
                rows.append({"backend": backend, "config": config, "task_id": task["task_id"],
                             "category": reference["category"], "expected": reference["expected_decision"],
                             "answered": answer is not None, "tools_used": bool(result and result["tools_used"]),
                             "model_decision": answer["decision"] if answer else None, "final": final,
                             "delivered": final != "stop", "quotes": len(quotes), "quotes_in_paper": found,
                             "reason_codes": codes})
    return rows


def rate(events: int, n: int) -> dict:
    return {"events": events, "n": n, "rate": round(events / n, 4) if n else None, "wilson_95": wilson(events, n)}


def metrics(rows: list[dict]) -> dict:
    stop = [r for r in rows if r["expected"] == "stop"]
    answerable = [r for r in rows if r["expected"] != "stop"]
    negative = [r for r in rows if r["expected"] == "does_not_support"]
    delivered = [r for r in rows if r["delivered"]]
    return {"tasks": len(rows), "answered": sum(r["answered"] for r in rows), "tool_use": sum(r["tools_used"] for r in rows),
            "correct_decision": rate(sum(r["final"] == r["expected"] for r in rows), len(rows)),
            "correct_stop": rate(sum(r["final"] == "stop" for r in stop), len(stop)),
            "false_stop": rate(sum(r["final"] == "stop" for r in answerable), len(answerable)),
            "negative_detected": rate(sum(r["final"] == "does_not_support" for r in negative), len(negative)),
            "wrong_direction": rate(sum(r["final"] not in ("stop", r["expected"]) for r in answerable), len(answerable)),
            "citation_grounded": rate(sum(r["quotes_in_paper"] for r in delivered), sum(r["quotes"] for r in delivered)),
            "hallucination": rate(sum(r["quotes_in_paper"] < r["quotes"] or not r["quotes"] for r in delivered),
                                  len(delivered))}


def pct(m: dict) -> str:
    return "N/A" if m["rate"] is None else f"{100 * m['rate']:.0f}%"


def render(summary: dict) -> str:
    lines = [f"# Literature benchmark: models alone vs. with bioevidence ({summary['split']} set)", "",
             f"{summary['tasks']} tasks on open-access CIViC papers; reference: CIViC's curation of each paper. Models: "
             + ", ".join(f"{MODEL_NAMES[b]} (`{m['model']}`)" for b, m in summary["models"].items()) + ".", "",
             "| Model | Configuration | Correct decision | Correct STOP | False STOP | Negative finding detected | "
             "Wrong direction | Citation grounded | Hallucination |", "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for backend, configs in summary["results"].items():
        for config, _, _, label in CONFIGS:
            if config in configs:
                m = configs[config]
                lines.append(f"| {MODEL_NAMES[backend]} | {label} | {pct(m['correct_decision'])} | {pct(m['correct_stop'])} | "
                             f"{pct(m['false_stop'])} | {pct(m['negative_detected'])} | {pct(m['wrong_direction'])} | "
                             f"{pct(m['citation_grounded'])} | {pct(m['hallucination'])} |")
    lines += ["", "Correct STOP: share of unrelated claims (the paper never mentions the gene) not answered. False STOP: "
              "share of answerable tasks not answered. Negative finding detected: share of CIViC \"Does Not Support\" "
              "items answered as such. Wrong direction: share of answerable tasks answered the opposite way. Citation "
              "grounded: share of quotes found verbatim in the paper, among delivered answers. Hallucination: share of "
              "delivered answers with a quote not in the paper (or no quote). Delivered: every non-stop model answer; "
              "with bioevidence, only admitted records.", "",
              "Wilson 95% intervals and per-task rows are in `summary.json` and `rows.jsonl`.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=["pilot", "test"], required=True)
    parser.add_argument("--answers", type=Path, help="Raw run_models.py output; omit to replay answers.jsonl")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    tasks = load_jsonl(TASKS / f"{args.split}.jsonl")
    references = {r["task_id"]: r for r in load_jsonl(TASKS / "references.jsonl") if r["split"] == args.split}
    papers = json.loads(gzip.decompress((TASKS / "papers.json.gz").read_bytes()))
    args.output.mkdir(parents=True, exist_ok=True)
    answers_path = args.output / "answers.jsonl"
    if args.answers:
        folder = args.answers / f"literature-{args.split}"
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        kept = []
        for path in sorted(folder.glob("*/*/*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            kept.append({k: raw[k] for k in ("model", "condition", "task_id", "prompt_sha256", "ok", "answer", "tools_used")}
                        | {"backend": path.parent.parent.name, "attempts": len(raw["attempts"]),
                           "seconds": round(sum(a["seconds"] for a in raw["attempts"]), 1)})
        models = {b: {"model": v["model"], "cli_version": v["cli_version"], "tier": v.get("tier")}
                  for b, v in manifest["backends"].items()}
        answers_path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in kept)
                                + json.dumps({"models": models}, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    lines = load_jsonl(answers_path)
    models = lines[-1]["models"]
    answers = {(r["backend"], r["condition"], r["task_id"]): r for r in lines[:-1]}
    rows = score_rows(tasks, references, answers, papers, Checker())
    results = {backend: {config: metrics(mine) for config, *_ in CONFIGS
                         if (mine := [r for r in rows if r["backend"] == backend and r["config"] == config])}
               for backend in [m for m in MODEL_NAMES if any(r["backend"] == m for r in rows)]}
    summary = {"benchmark": "llm-literature-benchmark-v1", "split": args.split, "tasks": len(tasks), "models": models,
               "answers_sha256": hashlib.sha256(answers_path.read_bytes()).hexdigest(), "results": results}
    (args.output / "rows.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows),
                                            encoding="utf-8", newline="\n")
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                                              encoding="utf-8", newline="\n")
    (args.output / "summary.md").write_text(render(summary), encoding="utf-8", newline="\n")
    print(render(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
