"""Render the VBO benchmark figure from the committed results.

    uv run --with matplotlib python examples/vbo_canine/plot.py

Reads results/summary.json and writes docs/assets/vbo_canine_benchmark.svg. Output is
deterministic for a given matplotlib version (fixed SVG ids, no timestamp).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]

# The ClinVar figure's palette (validated on the #fafbfc surface); the grounded bar uses the ink
# color, far darker than every other bar, and every bar is labeled.
SURFACE, GRID = "#fafbfc", "#e1e7eb"
INK, TEXT, MUTED = "#152d3d", "#405464", "#687b89"
BASELINE, BLUE, VALIDATOR = "#9aa8b7", "#2a78d6", "#199e70"
METHODS = [("schema_only", "Schema only", BASELINE), ("aggregate_quality", "Aggregate quality", BLUE),
           ("full", "Full validator", VALIDATOR), ("grounded", "Full + grounding", INK)]
COHORTS = [("real_source", "Real source", "{n} cases · {neg} not to be admitted"),
           ("controlled_fault", "Controlled faults", "{n} cases · 16 seeds × 10 mutations"),
           ("trust_boundary", "Trust boundary", "{n} forged targets and sources")]


def panel(ax, cohort: dict, title: str, subtitle: str, show_labels: bool) -> None:
    for row, (key, _, color) in enumerate(METHODS):
        stats = cohort[key]
        share = 100 * stats["false_admissions"] / stats["expected_non_admitted"]
        ax.barh(row, share, height=0.52, color=color, zorder=2)
        ax.text(share + 3 if share else 3, row, f"{stats['false_admissions']}/{stats['expected_non_admitted']}",
                va="center", fontsize=9, fontweight="bold", color=INK)
    ax.set_yticks(range(len(METHODS)), [label for _, label, _ in METHODS] if show_labels else [""] * len(METHODS))
    ax.invert_yaxis()
    ax.set_facecolor(SURFACE)
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
    ax.tick_params(axis="x", colors=TEXT, labelsize=9, length=0, pad=6)
    ax.tick_params(axis="y", colors=TEXT, labelsize=9.5, length=0, pad=8)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.text(0, 1.16, title, transform=ax.transAxes, fontsize=12, fontweight="bold", color=INK, va="bottom")
    ax.text(0, 1.06, subtitle, transform=ax.transAxes, fontsize=8, color=MUTED, va="bottom")


def render(summary: dict, output: Path) -> None:
    plt.rcParams.update({"svg.hashsalt": "bioai-vbo-v1", "font.family": "DejaVu Sans"})
    fig = plt.figure(figsize=(13.6, 5.4), facecolor=SURFACE)
    grid = fig.add_gridspec(1, 3, left=0.12, right=0.94, top=0.70, bottom=0.25, wspace=0.3)
    for index, (key, title, subtitle) in enumerate(COHORTS):
        cohort = summary["cohorts"][key]
        panel(fig.add_subplot(grid[index]), cohort, title,
              subtitle.format(n=cohort["full"]["n"], neg=cohort["full"]["expected_non_admitted"]), index == 0)
    fig.text(0.02, 0.93, "VBO canine benchmark · false admissions", fontsize=15, fontweight="bold", color=INK)
    fig.text(0.02, 0.875, f"72 real dog names, 160 injected faults and 48 trust-boundary forgeries against the pinned VBO "
                          f"{summary['source_release']} dog-term projection ({summary['source_terms']:,} terms)", fontsize=9.5, color=TEXT)
    notes = [
        "False admission = admitted despite a rejected or review-required reference status. Lower is better.",
        "Source-derived labels; controlled faults are correlated. Trust-boundary forgeries pass the rules alone; "
        "grounding against the pinned ontology catches them.",
    ]
    for i, note in enumerate(notes):
        fig.text(0.02, 0.13 - 0.045 * i, note, fontsize=8.5, color=TEXT)
    fig.text(0.02, 0.025, f"Source: NingyuSUN/bioai-evidence-validator v{summary['validator_version']} · "
                          f"VBO {summary['source_release']} · examples/vbo_canine/results/summary.json",
             fontsize=7.5, color=MUTED)
    output.parent.mkdir(parents=True, exist_ok=True)
    svg = output.suffix == ".svg"
    fig.savefig(output, facecolor=SURFACE, dpi=110, **({"metadata": {"Date": None}} if svg else {}))
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--summary", type=Path, default=ROOT / "results/summary.json")
    parser.add_argument("--output", type=Path, default=REPO / "docs/assets/vbo_canine_benchmark.svg")
    args = parser.parse_args()
    render(json.loads(args.summary.read_text(encoding="utf-8")), args.output)
    print(args.output)
