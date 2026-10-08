"""Which signals that send a record to a person actually predict a wrong answer (#24).

Routing should rest on evidence. For every first answer in the committed runs, this compares how often the answer
was wrong when a signal fired and when it did not, with Wilson 95% intervals and a risk ratio (Katz 95% interval).
Wrong means: for single-cell annotation, a cell type the authors' term rules out (wrong or invalid); for the
literature claims, a decision other than the expected one. The criterion was set in this analysis, after the runs
(each run's protocol was frozen before it): a risk signal is *shown* when the risk ratio's interval lies above 1 on
a held-out or external split and no such split points the other way; *indicative* when that holds only on a pilot;
otherwise *not shown*.

    python evaluation/llm_benchmark/risk_signals.py --output evaluation/llm_benchmark/results/risk-signals
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import celltype_loop  # noqa: E402
import score_claims  # noqa: E402

RESULTS = ROOT / "results"
Z = 1.959963984540054

# Signals that send a record to a person because it may be wrong. Rules that route because a record cannot be
# verified (BEV006, BEV015, BEV018, BEV020) or because the use requires a person (BEV008-BEV013, BEV021) need no
# such evidence: they are admission policy, not predictions.
RISK = {
    "BEV004": ("Contradicting evidence line (the answer's own evidence disagrees with it)", "on: engine rule"),
    "BEV022": ("Semantic cue: negated, hedged or non-human quote", "opt-in: `semantic` cues"),
    "BEV025": ("A pinned reference resource contradicts the claim (ASCT+B)",
               "opt-in: `ReferenceGrounder`; dropped from the cell-type validator after the pilot"),
    "BEV026": ("Measurements contradict the ontology's definition",
               "opt-in, experimental: `DefinitionGrounder`; fed back to the model"),
}
# Fixable findings, fed back to the model rather than routed; shown for comparison.
FIXABLE = {
    "BEV016": "A cited identifier or marker does not exist in the source",
    "BEV017": "The record disagrees with the source (e.g. a label that is not the term's name)",
    "BEV023": "An obsolete identifier or a previous gene symbol",
}
SPLITS = [  # (results, kind, what)
    ("celltype-pilot", "pilot", "Single-cell annotation, pilot (protocol 1, with ASCT+B)"),
    ("celltype-test", "held-out", "Single-cell annotation, held-out clusters (protocol 2)"),
    ("celltype-external", "external", "Single-cell annotation, external studies (protocol 3, with definitions)"),
    ("agent-stance-pilot", "pilot", "Literature claims, agent with stances (scenario 2b)"),
    ("semantic-pilot", "pilot", "Literature claims, answers with the paper (semantic cues)"),
]


def wilson(events: int, n: int) -> list[float] | None:
    if n == 0:
        return None
    p = events / n
    centre = (p + Z * Z / (2 * n)) / (1 + Z * Z / n)
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / (1 + Z * Z / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def risk_ratio(a: int, n1: int, c: int, n2: int) -> dict:
    """Wrong among flagged (a of n1) over wrong among the rest (c of n2), Katz interval; 0.5 added to every cell
    when one is empty."""
    if not n1 or not n2:
        return {"ratio": None, "ci_95": None}
    b, d = n1 - a, n2 - c
    if 0 in (a, b, c, d):
        a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    ratio = (a / (a + b)) / (c / (c + d))
    se = math.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
    return {"ratio": round(ratio, 2), "ci_95": [round(ratio * math.exp(-Z * se), 2), round(ratio * math.exp(Z * se), 2)]}


def first_answers(name: str) -> list[tuple[set[str], bool]]:
    """(codes on the first record, wrong?) for every first answer the checks saw."""
    out = []
    if name.startswith("celltype"):
        case = celltype_loop.Case()
        truth = {t["task_id"]: t["term"] for t in celltype_loop.load_jsonl(celltype_loop.SOURCES / "truth.jsonl")}
        for row in celltype_loop.load_jsonl(RESULTS / name / "episodes.jsonl"):
            if row["attempts"]:
                got = [c["answer"] for c in row["calls"] if c["answer"] and c["answer"]["decision"] == "annotate"]
                kind = celltype_loop.outcome(case, truth[row["task_id"]], got[0])
                out.append((set(row["attempts"][0]["codes"]), kind in ("wrong", "invalid")))
    elif name == "agent-stance-pilot":
        expected = score_claims.expected_directions()
        for row in score_claims.load_jsonl(RESULTS / name / "episodes.jsonl"):
            first = row["submissions"][0] if row["submissions"] else None
            if first and first["decision"] != "stop":
                out.append((set(first["codes"]), first["decision"] != expected[row["task_id"]]))
    else:  # semantic cues: what the cues stopped beyond grounding, from the committed summary
        pipeline = json.loads((RESULTS / name / "summary.json").read_text(encoding="utf-8"))["pipeline"]
        cues, grounded = pipeline["cues"], pipeline["grounded"]
        flagged_right = cues["correct_answers_stopped"]["events"] - grounded["correct_answers_stopped"]["events"]
        flagged_wrong = cues["wrong_answers_stopped"]["events"] - grounded["wrong_answers_stopped"]["events"]
        right, wrong = cues["correct_answers_stopped"]["n"], cues["wrong_answers_stopped"]["n"]
        out += [({"BEV022"}, False)] * flagged_right + [({"BEV022"}, True)] * flagged_wrong
        out += [(set(), False)] * (right - flagged_right) + [(set(), True)] * (wrong - flagged_wrong)
    return out


def table(answers: list[tuple[set[str], bool]], code: str) -> dict:
    flagged = [wrong for codes, wrong in answers if code in codes]
    rest = [wrong for codes, wrong in answers if code not in codes]
    a, c = sum(flagged), sum(rest)
    return {"flagged": len(flagged), "flagged_wrong": a, "flagged_wrong_rate": round(a / len(flagged), 4) if flagged else None,
            "flagged_wrong_wilson_95": wilson(a, len(flagged)), "unflagged": len(rest), "unflagged_wrong": c,
            "unflagged_wrong_rate": round(c / len(rest), 4) if rest else None,
            "unflagged_wrong_wilson_95": wilson(c, len(rest)), "risk_ratio": risk_ratio(a, len(flagged), c, len(rest))}


def verdict(rows: list[dict]) -> str:
    def above(r: dict) -> bool:
        ci = r["risk_ratio"]["ci_95"]
        return bool(ci) and ci[0] > 1

    def below(r: dict) -> bool:
        ci = r["risk_ratio"]["ci_95"]
        return bool(ci) and ci[1] < 1

    held = [r for r in rows if r["kind"] != "pilot"]
    if any(above(r) for r in held) and not any(below(r) for r in held):
        return "shown"
    if any(above(r) for r in rows) and not any(below(r) for r in rows):
        return "indicative"
    return "not shown"


def analyse() -> dict:
    answers = {name: first_answers(name) for name, _, _ in SPLITS}
    signals = {}
    for code, label in [*((c, v[0]) for c, v in RISK.items()), *FIXABLE.items()]:
        rows = [{"results": name, "kind": kind, "what": what, **table(answers[name], code)}
                for name, kind, what in SPLITS if any(code in codes for codes, _ in answers[name])]
        signals[code] = {"signal": label, "role": "risk" if code in RISK else "fixable",
                         "routing": RISK[code][1] if code in RISK else "fed back to the model",
                         "verdict": verdict(rows), "evidence": rows}
    return {"analysis": "risk signals against wrong first answers",
            "first_answers": {name: len(a) for name, a in answers.items()},
            "wrong_first_answers": {name: sum(w for _, w in a) for name, a in answers.items()}, "signals": signals}


def render(summary: dict) -> str:
    def pct(events: int, n: int) -> str:
        return f"{events}/{n} ({100 * events / n:.0f}%)" if n else "–"

    lines = ["# Risk signals: which routing signals predict a wrong answer", "",
             "First answers only, before any feedback. *Shown*: the risk ratio's 95% interval lies above 1 on a "
             "held-out or external split, and no such split points the other way. *Indicative*: that holds only on a "
             "pilot. The criterion was set after the runs.", "",
             "| Signal | Role | Default routing | Split | Wrong when flagged | Wrong otherwise | Risk ratio (95% CI) | "
             "Verdict |", "|---|---|---|---|---:|---:|---:|---|"]
    for code, s in summary["signals"].items():
        for i, r in enumerate(s["evidence"]):
            rr = r["risk_ratio"]
            ratio = "–" if rr["ratio"] is None else f"{rr['ratio']} ({rr['ci_95'][0]}–{rr['ci_95'][1]})"
            head = (f"**{code}** {s['signal']}", s["role"], s["routing"]) if i == 0 else ("", "", "")
            lines.append(f"| {head[0]} | {head[1]} | {head[2]} | {r['results']} ({r['kind']}) | "
                         f"{pct(r['flagged_wrong'], r['flagged'])} | {pct(r['unflagged_wrong'], r['unflagged'])} | "
                         f"{ratio} | {s['verdict'] if i == 0 else ''} |")
    risk = {c: s for c, s in summary["signals"].items() if s["role"] == "risk"}

    def listed(codes: list[str]) -> str:
        return ", ".join(f"{c} ({risk[c]['verdict']})" for c in codes) or "none"

    lines += ["", f"Risk signals that route by default: {listed([c for c, s in risk.items() if s['routing'].startswith('on')])}. "
              f"Opt-in: {listed([c for c, s in risk.items() if not s['routing'].startswith('on')])}; a signal that is "
              "not shown stays off by default. BEV026 is fed back to the model first; a record it still flags after "
              "feedback goes to a person, which is why it is experimental. Fixable findings predict wrong answers too, "
              "partly by construction (an unknown identifier is an invalid answer); they go back to the model.",
              "", "Rules that route a record because it cannot be verified (BEV006, BEV015, BEV018, BEV020) or because "
              "the use requires a person (BEV008–BEV013, BEV021) are admission policy, not predictions, and are not "
              "listed."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    options = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    options.add_argument("--output", type=Path, required=True)
    args = options.parse_args(argv)
    summary = analyse()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8",
                                              newline="\n")
    (args.output / "summary.md").write_text(render(summary), encoding="utf-8", newline="\n")
    print(render(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
