"""Regenerate every committed benchmark result and figure, offline, and compare them with the repository.

    uv run --frozen --with matplotlib==3.11.2 python tools/reproduce.py            # check; exit 1 on any difference
    uv run --frozen --with matplotlib==3.11.2 python tools/reproduce.py --write    # update the committed files
    uv run --frozen --with matplotlib==3.11.2 python tools/reproduce.py --only celltype-test figures
    uv run --frozen python tools/reproduce.py --list

Model calls, agent runs and downloads are not repeated. What they produced is committed: model answers, agent
episodes, the verification of cited papers, and content-addressed source snapshots. Every table, summary and figure is
recomputed from them. Each step runs in a scratch directory and its outputs are compared with the committed files:
text with line endings normalised (the repository stores LF), everything else byte for byte. The figures are
byte-stable for one matplotlib version, so the command pins it.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "evaluation" / "llm_benchmark"
RESULTS = BENCH / "results"
ASSETS = REPO / "docs" / "assets"
MATPLOTLIB = "3.11.2"
TEXT = {".json", ".jsonl", ".md", ".csv", ".svg", ".txt", ".tsv"}


@dataclass
class Step:
    name: str
    what: str
    commands: list[list[str]]  # run in order; "{out}" is replaced by the scratch directory
    inputs: list[Path] = field(default_factory=list)  # committed files the step replays from, copied into scratch
    outputs: dict[Path, str] = field(default_factory=dict)  # committed file -> name in scratch
    check_only: bool = False  # a self-checking command (exit status only)
    write_commands: list[list[str]] | None = None
    figures: bool = False


def folder(path: Path, skip: tuple[str, ...] = ()) -> dict[Path, str]:
    return {p: p.name for p in sorted(path.iterdir()) if p.is_file() and p.name not in skip}


def py(script: Path, *args: str) -> list[str]:
    return [sys.executable, str(script), *args]


def replay(name: str, what: str, script: str, args: list[str], inputs: list[str], outputs: list[str]) -> Step:
    base = RESULTS / name
    return Step(name, what, [py(BENCH / script, *args)], [base / i for i in inputs], {base / o: o for o in outputs})


def case(name: str, what: str) -> Step:
    """A real-data case: run.py writes a fresh directory (it refuses to overwrite earlier evidence)."""
    results = REPO / "examples" / name / "results"
    return Step(name.replace("_", "-"), what, [py(REPO / "examples" / name / "run.py", "--output", "{out}/run")],
                outputs={p: f"run/{n}" for p, n in folder(results).items()})


STEPS = [
    Step("error-taxonomy", "Error taxonomy page from evaluation/error_taxonomy.yaml and the case results",
         [py(REPO / "tools" / "render_taxonomy.py", "--check")], check_only=True,
         write_commands=[py(REPO / "tools" / "render_taxonomy.py")]),
    Step("llm-tasks", "LLM benchmark task files from the pinned ClinVar and CIViC sources",
         [py(BENCH / "tasks.py", "--check")], check_only=True),
    Step("literature-tasks", "Literature task files", [py(BENCH / "tasks_literature.py", "--check")], check_only=True),
    Step("semantic-units", "Semantic-check units",
         [py(BENCH / "semantic_eval.py", "units", "--split", "pilot", "--check")], check_only=True),
    case("vbo_canine", "VBO canine name mapping: decisions, controlled faults, trust boundary"),
    case("clinvar_germline", "ClinVar germline: policy reproduction, stability 2023 to 2026, faults"),
    case("civic_literature", "CIViC literature grounding: negative controls on pinned papers"),
    replay("pilot", "LLM benchmark, ClinVar tasks", "score.py", ["--split", "pilot", "--output", "{out}"],
           ["answers.jsonl"], ["rows.jsonl", "summary.json", "summary.md"]),
    replay("literature-pilot", "LLM benchmark, literature tasks with the source", "score_literature.py",
           ["--split", "pilot", "--output", "{out}"], ["answers.jsonl"], ["rows.jsonl", "summary.json", "summary.md"]),
    replay("literature-plain-pilot", "Scenario 1a: plain questions with PMID and title", "score_literature.py",
           ["--split", "pilot", "--output", "{out}"], ["answers.jsonl"], ["rows.jsonl", "summary.json", "summary.md"]),
    replay("literature-claims-pilot", "Scenario 1b: plain questions, the model picks the papers", "score_claims.py",
           ["score", "--output", "{out}"], ["answers.jsonl", "verification.jsonl"],
           ["rows.jsonl", "summary.json", "summary.md"]),
    replay("semantic-pilot", "Semantic checks: independent review and cues", "semantic_eval.py",
           ["score", "--split", "pilot", "--output", "{out}"], ["answers.jsonl"],
           ["rows.jsonl", "summary.json", "summary.md"]),
    replay("agent-pilot", "Scenario 2: agent with PubMed tools and feedback", "agent_loop.py",
           ["score", "--results", "{out}"], ["episodes.jsonl"], ["summary.json", "summary.md"]),
    replay("agent-stance-pilot", "Scenario 2b: stances and a conflicting outcome", "agent_loop.py",
           ["score", "--results", "{out}"], ["episodes.jsonl"], ["summary.json", "summary.md"]),
    replay("celltype-pilot", "Scenario 3: single-cell annotation, pilot (protocol 1)", "celltype_loop.py",
           ["score", "--results", "{out}"], ["episodes.jsonl"], ["summary.json", "summary.md"]),
    replay("celltype-test", "Scenario 3: single-cell annotation, held-out (protocol 2)", "celltype_loop.py",
           ["score", "--results", "{out}"], ["episodes.jsonl"], ["summary.json", "summary.md"]),
    replay("celltype-external", "Scenario 3: single-cell annotation, external studies (protocol 3)", "celltype_loop.py",
           ["score", "--results", "{out}"], ["episodes.jsonl"], ["summary.json", "summary.md"]),
    replay("extraction-pilot", "Scenario 4: claims extracted from openly licensed papers, pilot", "extraction_loop.py",
           ["score", "--results", "{out}"], ["episodes.jsonl", "reviews.jsonl"],
           ["summary.json", "summary.md", "expert_sample/key.jsonl", "expert_sample/labels.csv",
            "expert_sample/packet.md"]),
    Step("risk-signals", "Which routing signals predict a wrong answer, from the committed runs",
         [py(BENCH / "risk_signals.py", "--output", "{out}")],
         outputs={RESULTS / "risk-signals" / n: n for n in ("summary.json", "summary.md")}),
    Step("celltype-audit", "Audit dry run of the auto-admitted single-cell annotations, with a stand-in auditor",
         [py(BENCH / "audit_celltype.py", "--output", "{out}/run")],
         outputs={RESULTS / "celltype-audit" / n: f"run/{n}" for n in (
             "predictions.csv", "sample/audit_sheet.csv", "sample/audit_manifest.json", "audit_packet.md",
             "stand_in_annotations.csv", "audit_report.json", "summary.json", "summary.md")}),
    Step("figures", "Figures in docs/assets, from the committed summaries",
         [py(REPO / "examples" / "clinvar_germline" / "plot.py", "--output", "{out}/clinvar_germline_benchmark.svg"),
          py(REPO / "examples" / "vbo_canine" / "plot.py", "--output", "{out}/vbo_canine_benchmark.svg"),
          py(BENCH / "plot.py", "--output", "{out}/ai_validation_results.svg", "--funnel", "{out}/ai_validation_funnel.svg")],
         outputs={ASSETS / n: n for n in ("clinvar_germline_benchmark.svg", "vbo_canine_benchmark.svg",
                                          "ai_validation_results.svg", "ai_validation_funnel.svg")}, figures=True),
]


def same(committed: Path, produced: Path) -> bool:
    a, b = committed.read_bytes(), produced.read_bytes()
    if committed.suffix in TEXT:
        a, b = a.replace(b"\r\n", b"\n"), b.replace(b"\r\n", b"\n")
    return a == b


def run(step: Step, write: bool) -> tuple[str, str]:
    """(status, detail) for one step."""
    if step.figures:
        try:
            import matplotlib
        except ImportError:
            return "skipped", f"needs matplotlib=={MATPLOTLIB} (uv run --with matplotlib=={MATPLOTLIB})"
        if matplotlib.__version__ != MATPLOTLIB:
            return "skipped", f"needs matplotlib=={MATPLOTLIB}, found {matplotlib.__version__}"
    with tempfile.TemporaryDirectory(prefix=f"reproduce-{step.name}-") as scratch:
        out = Path(scratch)
        for source in step.inputs:
            shutil.copyfile(source, out / source.name)
        for command in (step.write_commands if write and step.write_commands else step.commands):
            done = subprocess.run([part.replace("{out}", scratch) for part in command], cwd=out, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace")
            if done.returncode != 0:
                message = (done.stderr or done.stdout).strip().splitlines()
                return "failed", message[-1] if message else f"exit {done.returncode}"
        if step.check_only:
            return ("written" if write and step.write_commands else "identical"), ""
        different = [c for c, name in step.outputs.items() if not (out / name).exists() or not same(c, out / name)]
        if write:
            for committed, name in step.outputs.items():
                if (out / name).exists() and not same(committed, out / name):
                    committed.write_bytes((out / name).read_bytes().replace(b"\r\n", b"\n")
                                          if committed.suffix in TEXT else (out / name).read_bytes())
            return ("written" if different else "identical"), ", ".join(c.name for c in different)
        if different:
            return "different", ", ".join(str(c.relative_to(REPO)) for c in different)
        return "identical", f"{len(step.outputs)} file(s)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="update the committed files with what is regenerated")
    parser.add_argument("--only", nargs="+", metavar="STEP", help="run only these steps")
    parser.add_argument("--list", action="store_true", help="list the steps and exit")
    args = parser.parse_args(argv)
    if args.list:
        for step in STEPS:
            print(f"{step.name:24} {step.what}")
        return 0
    unknown = set(args.only or []) - {s.name for s in STEPS}
    if unknown:
        parser.error(f"unknown step(s): {', '.join(sorted(unknown))}")
    failures = 0
    for step in (s for s in STEPS if not args.only or s.name in args.only):
        started = time.monotonic()
        status, detail = run(step, args.write)
        failures += status in ("failed", "different", "skipped")
        print(f"{status:10} {step.name:24} {time.monotonic() - started:6.1f}s  {detail}", flush=True)
    print("all reproduced" if not failures else f"{failures} step(s) not reproduced")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
