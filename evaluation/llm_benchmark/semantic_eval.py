"""Issue #31: semantic checks on the literature benchmark: build review units, then score them.

    uv run --frozen python evaluation/llm_benchmark/semantic_eval.py units --split pilot
    python3 evaluation/llm_benchmark/run_models.py --suite review --split pilot \
        --models gpt-luna gemini-flash --output artifacts/llm-benchmark
    uv run --frozen python evaluation/llm_benchmark/semantic_eval.py score --split pilot \
        --answers artifacts/llm-benchmark --output evaluation/llm_benchmark/results/semantic-pilot

Units (`semantic/<split>-units.jsonl`, what reviewers see) and their hidden labels (`<split>-labels.jsonl`):
  natural          every non-stop answer of the literature benchmark (with the paper): claim and quotes
  unrelated_claim  a correct answer's quotes paired with another task's claim, whose gene they never name
  species          a real sentence about animals or cell lines only, paired with the paper's claim
  hedged           a real hedged sentence ("may", "suggest" …), paired with the paper's claim
A direction flip needs no unit of its own: reviewers never see the claimed direction, so a reviewer that
reads a correct answer's quotes the right way also exposes the same quotes offered for the opposite direction.

Scoring runs the actual engine: each natural answer becomes the record score_literature.py builds, plus the
reviewer's reading as a non-human adjudication (accept if it matches the extractor's decision, defer
otherwise) under a profile with `require_independent_review`, and/or the deterministic `CueChecker`.
Reviewers always come from other vendors than the extractor: one (rotating) or both of the other two.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

import yaml

from bioevidence_validator.engine import RecordValidator
from bioevidence_validator.grounding import SourceBytesGrounder
from bioevidence_validator.semantic import HEDGE, HUMAN, NEGATION, NON_HUMAN, CueChecker

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import literature_suite  # noqa: E402
import score_literature  # noqa: E402

UNITS = ROOT / "semantic"
KEY = "bioai-semantic-v1"
# Independent reviewers come from the other two vendors' fast models. With one reviewer, the vendors rotate.
OTHER_VENDORS = {"claude": ["gpt-luna", "gemini-flash"], "gpt": ["claude-haiku", "gemini-flash"],
                 "gemini": ["claude-haiku", "gpt-luna"]}
ONE_REVIEWER = {"claude": "gemini-flash", "gpt": "claude-haiku", "gemini": "gpt-luna"}
NEGATIVE = {"does_not_support_significance"}
CONFIGS = [("grounded", 0, False, "LLM + paper + bioevidence (grounding)"),
           ("cues", 0, True, "+ semantic cues"),
           ("review", 1, False, "+ one independent reviewer"),
           ("review_cues", 1, True, "+ one independent reviewer + cues"),
           ("two_reviews", 2, False, "+ two independent reviewers"),
           ("two_reviews_cues", 2, True, "+ two independent reviewers + cues")]


def keyed(text: str) -> str:
    return hashlib.sha256(f"{KEY}:{text}".encode()).hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def context(quote: str, cited: str, blocks: list[list[str]]) -> str:
    """The paragraph a quote comes from: the cited one if it holds the quote, else the first that does."""
    holding = [text for pid, kind, text in blocks if score_literature.in_paper(quote, [[pid, kind, text]])]
    cited_text = [text for pid, _, text in blocks if pid == cited.strip().strip("[]#")]
    if cited_text and cited_text[0] in holding:
        return cited_text[0]
    return holding[0] if holding else ""


def sentences(blocks: list[list[str]], pattern, exclude=None) -> list[str]:
    found = []
    for _, kind, text in blocks:
        if kind != "p":
            continue
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text):
            if 12 <= len(sentence.split()) <= 60 and pattern.search(sentence) and not (exclude and exclude.search(sentence)):
                found.append(sentence)
    return sorted(found, key=keyed)


def build_units(split: str) -> tuple[list[dict], list[dict]]:
    tasks = {t["task_id"]: t for t in load_jsonl(literature_suite.TASKS / f"{split}.jsonl")}
    references = {r["task_id"]: r for r in load_jsonl(literature_suite.TASKS / "references.jsonl") if r["split"] == split}
    papers = literature_suite.load_papers()
    answers = load_jsonl(ROOT / "results" / f"literature-{split}" / "answers.jsonl")[:-1]
    units, labels = [], []

    def add(unit_id, kind, task, quotes, label):
        units.append({"task_id": unit_id, "claim": task["claim"], "title": task["title"], "quotes": quotes})
        labels.append({"unit_id": unit_id, "kind": kind, "task_id": task["task_id"], **label})

    order = list(score_literature.MODEL_NAMES)
    bases = {}
    for answer in sorted(answers, key=lambda a: (order.index(a["backend"]), a["task_id"])):
        result = answer["answer"]
        if answer["condition"] != "with_source" or not answer["ok"] or result["decision"] == "stop" or not result["quotes"]:
            continue
        task, reference = tasks[answer["task_id"]], references[answer["task_id"]]
        blocks = papers[task["pmid"]]
        quotes = [{"text": q["text"], "context": context(q["text"], q["paragraph"], blocks)} for q in result["quotes"]]
        found = all(score_literature.in_paper(q["text"], blocks) for q in result["quotes"])
        add(f"n-{answer['backend']}-{task['task_id']}", "natural", task, quotes,
            {"extractor": answer["backend"], "extractor_decision": result["decision"],
             "expected": reference["expected_decision"], "quotes_found": found})
        if found and result["decision"] == reference["expected_decision"] and task["task_id"] not in bases:
            bases[task["task_id"]] = (task, quotes)
    base_list = [bases[k] for k in sorted(bases, key=keyed)]
    for n, (task, quotes) in enumerate(base_list):
        text = " ".join(q["text"] + " " + q["context"] for q in quotes)
        donors = [t for t, _ in base_list[n + 1:] + base_list[:n]
                  if t["claim"]["molecular_profile"].split()[0] not in text]
        if donors:
            donor = donors[0]
            add(f"u-{task['task_id']}", "unrelated_claim", {**task, "claim": donor["claim"]}, quotes,
                {"expected_verdict": "not_addressed", "claim_from": donor["task_id"]})
    for task in sorted(tasks.values(), key=lambda t: keyed(t["task_id"])):
        if references[task["task_id"]]["category"] == "unrelated":
            continue
        blocks = papers[task["pmid"]]
        for kind, pattern, exclude, label in (("species", NON_HUMAN, HUMAN, {"expected_evidence_from": "non_human"}),
                                              ("hedged", HEDGE, NEGATION, {"expected_certainty": "hedged"})):
            found = sentences(blocks, pattern, exclude)
            if found:
                add(f"{kind[0]}-{task['task_id']}", kind, task, [{"text": found[0], "context": ""}], label)
    return units, labels


def write_units(split: str, check: bool = False) -> int:
    UNITS.mkdir(exist_ok=True)
    units, labels = build_units(split)
    stale = []
    for name, rows in ((f"{split}-units.jsonl", units), (f"{split}-labels.jsonl", labels)):
        text = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
        if check:
            if not (UNITS / name).exists() or (UNITS / name).read_text(encoding="utf-8") != text:
                stale.append(name)
        else:
            (UNITS / name).write_text(text, encoding="utf-8", newline="\n")
    if stale:
        print(f"out of date: {', '.join(stale)}", file=sys.stderr)
        return 1
    kinds = {k: sum(label["kind"] == k for label in labels) for k in ("natural", "unrelated_claim", "species", "hedged")}
    print(f"{len(units)} units: {kinds}")
    return 0


class Pipeline:
    """The record score_literature.py builds, validated with grounding plus the semantic layers asked for."""

    def __init__(self):
        self.base = score_literature.Checker()
        profile = yaml.safe_load((score_literature.CASE / "profile.yaml").read_text(encoding="utf-8"))
        for use in profile["uses"].values():
            use["require_independent_review"] = True
        self.folder = tempfile.TemporaryDirectory()
        path = Path(self.folder.name) / "reviewed.yaml"
        path.write_text(yaml.safe_dump(profile), encoding="utf-8")
        grounders = [SourceBytesGrounder(self.base.corpus.store), self.base.corpus.grounder()]
        cues = CueChecker(negative_predicates=NEGATIVE)
        self.validators = {
            (False, False): self.base.validator,
            (False, True): RecordValidator(profile=score_literature.CASE / "profile.yaml", grounders=[*grounders, cues]),
            (True, False): RecordValidator(profile=path, grounders=grounders),
            (True, True): RecordValidator(profile=path, grounders=[*grounders, cues]),
        }

    def decide(self, task: dict, answer: dict, readings: dict[str, dict | None], cues: bool):
        """`readings`: reviewer -> its reading (None if it gave none); empty for no independent review."""
        record = self.base.build(task, answer)
        if record is None:
            return "stop", []
        record["adjudications"] = [
            {"id": f"bioev:review-{reviewer}", "statement_id": record["statement"]["id"],
             "applies_to_uses": list(record["requested_uses"]),
             "decision": "accept" if reading["verdict"] == answer["decision"] else "defer",
             "reviewer": {"id": f"model:{reviewer}", "agent_type": "software"},
             "rationale": reading["rationale"] or "(none given)", "decided_at": "2026-09-29T00:00:00Z"}
            for reviewer, reading in readings.items() if reading]
        report = self.validators[bool(readings), cues].validate(self.base.corpus.pin(record))
        codes = sorted({f["rule_id"] for f in report["findings"]})
        return (answer["decision"] if report["overall_status"] == "admitted" else "stop"), codes


def rate(events: int, n: int) -> dict:
    return {"events": events, "n": n, "rate": round(events / n, 4) if n else None,
            "wilson_95": score_literature.wilson(events, n)}


def score(split: str, answers_dir: Path | None, output: Path) -> dict:
    tasks = {t["task_id"]: t for t in load_jsonl(literature_suite.TASKS / f"{split}.jsonl")}
    units = {u["task_id"]: u for u in load_jsonl(UNITS / f"{split}-units.jsonl")}
    labels = load_jsonl(UNITS / f"{split}-labels.jsonl")
    extractor = {(a["backend"], a["task_id"]): a for a in
                 load_jsonl(ROOT / "results" / f"literature-{split}" / "answers.jsonl")[:-1]
                 if a["condition"] == "with_source"}
    output.mkdir(parents=True, exist_ok=True)
    answers_path = output / "answers.jsonl"
    if answers_dir:
        folder = answers_dir / f"review-{split}"
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        kept = []
        for path in sorted(folder.glob("*/review/*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            kept.append({"reviewer": path.parent.parent.name, "unit_id": raw["task_id"], "ok": raw["ok"],
                         "answer": raw["answer"], "tools_used": raw["tools_used"], "prompt_sha256": raw["prompt_sha256"]})
        models = {b: {"model": v["model"], "cli_version": v["cli_version"]} for b, v in manifest["backends"].items()}
        answers_path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in kept)
                                + json.dumps({"models": models}, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    rows = load_jsonl(answers_path)
    models = rows[-1]["models"]
    reading = {(r["reviewer"], r["unit_id"]): r["answer"] for r in rows[:-1] if r["ok"]}
    reviewers = sorted(models)

    controls: dict = {}
    cue_checker = CueChecker(negative_predicates=NEGATIVE)
    natural = [lab for lab in labels if lab["kind"] == "natural"]
    bases = [lab for lab in natural if lab["quotes_found"] and lab["extractor_decision"] == lab["expected"]]
    for reviewer in reviewers:
        def got(unit_id, field, reviewer=reviewer):
            answer = reading.get((reviewer, unit_id))
            return answer[field] if answer else None
        controls[reviewer] = {
            "base_read_correctly (direction flip exposed)": rate(sum(got(b["unit_id"], "verdict") == b["expected"] for b in bases), len(bases)),
            "unrelated_claim_not_addressed": rate(*count(labels, "unrelated_claim", lambda lab: got(lab["unit_id"], "verdict") == "not_addressed")),
            "species_seen_as_non_human": rate(*count(labels, "species", lambda lab: got(lab["unit_id"], "evidence_from") == "non_human")),
            "hedged_seen_as_hedged": rate(*count(labels, "hedged", lambda lab: got(lab["unit_id"], "certainty") == "hedged")),
        }
    checker = Pipeline()

    def cue_flags(unit_id, predicate_negative):
        unit = units[unit_id]
        record = {"statement": {"predicate": "does_not_support_significance" if predicate_negative else "supports_significance",
                                "evidence_lines": [{"direction": "supports", "evidence_item_ids": ["q"]}]},
                  "evidence_items": [{"id": "q", "extracted_text": " ".join(q["text"] for q in unit["quotes"]),
                                      "scope": ["NCBITaxon:9606"]}], "requested_uses": ["research_summary"]}
        return bool(cue_checker.check(record))
    controls["semantic cues"] = {
        "base_flagged (false review)": rate(sum(cue_flags(b["unit_id"], b["expected"] == "does_not_support") for b in bases), len(bases)),
        "direction_flip_flagged": rate(sum(cue_flags(b["unit_id"], b["expected"] != "does_not_support") for b in bases), len(bases)),
        "species_flagged": rate(*count(labels, "species", lambda lab: cue_flags(lab["unit_id"], False))),
    }

    results, per_answer = {}, []
    for lab in natural:
        task = tasks[lab["task_id"]]
        answer = extractor[(lab["extractor"], lab["task_id"])]["answer"]
        vendor = lab["extractor"].split("-")[0]
        for config, count_reviewers, cues, _ in CONFIGS:
            chosen = [] if not count_reviewers else [ONE_REVIEWER[vendor]] if count_reviewers == 1 else OTHER_VENDORS[vendor]
            final, codes = checker.decide(task, answer, {r: reading.get((r, lab["unit_id"])) for r in chosen}, cues)
            per_answer.append({"unit_id": lab["unit_id"], "extractor": lab["extractor"], "reviewers": chosen,
                               "config": config, "expected": lab["expected"], "model_decision": lab["extractor_decision"],
                               "final": final, "reason_codes": codes})
    for config, *_ in CONFIGS:
        mine = [r for r in per_answer if r["config"] == config]
        answerable = [r for r in mine if r["expected"] != "stop"]
        results[config] = {
            "answers": len(mine),
            "wrong_direction_admitted": rate(sum(r["final"] not in ("stop", r["expected"]) for r in answerable), len(answerable)),
            "correct_answers_stopped": rate(sum(r["final"] == "stop" and r["model_decision"] == r["expected"] for r in answerable),
                                            sum(r["model_decision"] == r["expected"] for r in answerable)),
            "wrong_answers_stopped": rate(sum(r["final"] == "stop" and r["model_decision"] != r["expected"] for r in mine),
                                          sum(r["model_decision"] != r["expected"] for r in mine)),
        }
    summary = {"benchmark": "llm-semantic-checks-v1", "split": split, "reviewers": models, "controls": controls,
               "pipeline": results, "answers_sha256": hashlib.sha256(answers_path.read_bytes()).hexdigest()}
    (output / "rows.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in per_answer),
                                       encoding="utf-8", newline="\n")
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (output / "summary.md").write_text(render(summary), encoding="utf-8", newline="\n")
    print(render(summary))
    return summary


def count(labels, kind, hit) -> tuple[int, int]:
    mine = [lab for lab in labels if lab["kind"] == kind]
    return sum(bool(hit(lab)) for lab in mine), len(mine)


def fraction(m: dict) -> str:
    return "N/A" if not m["n"] else f"{m['events']}/{m['n']}"


def render(summary: dict) -> str:
    lines = [f"# Semantic checks on the literature benchmark ({summary['split']} set)", "",
             "## Controls", "", "| Checker | Control | Result |", "|---|---|---:|"]
    for checker, controls in summary["controls"].items():
        name = score_literature.MODEL_NAMES.get(checker, checker)
        lines += [f"| {name} | {control} | {fraction(m)} |" for control, m in controls.items()]
    lines += ["", "## Natural answers (every non-stop answer with the paper, all six extractors)", "",
              "| Pipeline | Wrong direction admitted | Correct answers stopped | Wrong answers stopped |",
              "|---|---:|---:|---:|"]
    for config, _, _, label in CONFIGS:
        m = summary["pipeline"][config]
        lines.append(f"| {label} | {fraction(m['wrong_direction_admitted'])} | {fraction(m['correct_answers_stopped'])} | "
                     f"{fraction(m['wrong_answers_stopped'])} |")
    lines += ["", "Reviewers are the fast models of the other two vendors (Claude Haiku 4.5, GPT-5.6-Luna, Gemini 3.8 "
              "Flash) and never see the extractor's decision. With one reviewer, Gemini reviews Claude, Claude reviews "
              "GPT and GPT reviews Gemini; with two, both other vendors must accept. A reviewer or cue can only send a "
              "record to a human. Wilson 95% intervals are in `summary.json`.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    steps = parser.add_subparsers(dest="step", required=True)
    units = steps.add_parser("units")
    units.add_argument("--split", choices=["pilot", "test"], required=True)
    units.add_argument("--check", action="store_true", help="Fail if the committed units are out of date")
    scoring = steps.add_parser("score")
    scoring.add_argument("--split", choices=["pilot", "test"], required=True)
    scoring.add_argument("--answers", type=Path)
    scoring.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.step == "units":
        return write_units(args.split, args.check)
    else:
        score(args.split, args.answers, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
