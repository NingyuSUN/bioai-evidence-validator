"""Render the ClinVar benchmark figure from the committed results.

    uv run --with matplotlib python examples/clinvar_germline/plot.py

Reads results/summary.json and writes docs/assets/clinvar_germline_benchmark.svg. Output is
deterministic for a given matplotlib version (fixed SVG ids, no timestamp).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]

# Colors validated with the dataviz palette checks on the #fafbfc surface (all pairs:
# CVD dE 10.6, normal-vision dE 16.6). Gray is a neutral baseline, labeled on every bar.
SURFACE, GRID = "#fafbfc", "#e1e7eb"
INK, TEXT, MUTED = "#152d3d", "#405464", "#687b89"
BASELINE, BLUE, VALIDATOR = "#9aa8b7", "#2a78d6", "#199e70"

TIERS = [("single_submitter", "1★ single submitter"), ("multiple_submitters", "2★ multiple submitters"),
         ("expert_panel", "3★ expert panel"), ("no_criteria", "0★ no assertion criteria")]
METHODS = [("schema_only", "Schema only", BASELINE), ("aggregate_quality", "Aggregate quality", BLUE),
           ("full", "Full validator", VALIDATOR)]


def style(ax, xmax: float, ticks: list[float], fmt) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_xlim(0, xmax)
    ax.set_xticks(ticks, [fmt(t) for t in ticks])
    ax.tick_params(axis="x", colors=TEXT, labelsize=9, length=0, pad=6)
    ax.tick_params(axis="y", colors=TEXT, labelsize=9.5, length=0, pad=8)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)


def panel_title(ax, title: str, subtitle: str) -> None:
    ax.text(0, 1.21, title, transform=ax.transAxes, fontsize=12, fontweight="bold", color=INK, va="bottom")
    ax.text(0, 1.145, subtitle, transform=ax.transAxes, fontsize=8, color=MUTED, va="bottom")


def stability_panel(ax, population: dict) -> None:
    height, gap = 0.34, 0.03  # a small surface gap between paired bars
    groups = [("without_dissenting_submission", BASELINE, -1), ("with_dissenting_submission", VALIDATOR, 1)]
    for row, (key, _) in enumerate(TIERS):
        present = [g for g in groups if population[key][g[0]]["evaluable"]]
        for group, color, side in present:
            stats = population[key][group]
            y = row + (side * (height + gap) / 2 if len(present) == 2 else 0)
            rate, (low, high) = 100 * stats["rate"], (100 * v for v in stats["wilson_95"])
            ax.barh(y, rate, height=height, color=color, zorder=2)
            ax.errorbar(rate, y, xerr=[[rate - low], [high - rate]], fmt="none", ecolor=INK,
                        elinewidth=1, capsize=2.5, capthick=1, zorder=3)
            value = ax.annotate(f"{rate:.2f}%" if rate < 1 else f"{rate:.1f}%", xy=(high, y), xytext=(5, 0),
                                textcoords="offset points", va="center", fontsize=9, fontweight="bold", color=INK)
            # Anchored to the value label's box, so the count never collides with it.
            ax.annotate(f"n={stats['evaluable']:,}", xy=(1, 0.5), xycoords=value, xytext=(4, 0),
                        textcoords="offset points", va="center", fontsize=7.5, color=MUTED)
    ax.set_yticks(range(len(TIERS)), [label for _, label in TIERS])
    ax.invert_yaxis()
    style(ax, 20, [0, 5, 10, 15, 20], lambda t: f"{t:.0f}%")
    panel_title(ax, "Reclassified or conflicting three years later",
                "All 218,920 germline P/LP variants in ClinVar 2023-09 · outcome in 2026-09 · Wilson 95% CI")
    ax.legend(handles=[Patch(color=BASELINE, label="No dissenting submission"),
                       Patch(color=VALIDATOR, label="Dissenting submission: validator holds for review")],
              loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, borderaxespad=0.3, frameon=False, fontsize=8.5,
              labelcolor=TEXT, handlelength=1.2, handleheight=0.9, columnspacing=1.6)


def fault_panel(ax, cohort: dict, title: str, subtitle: str, show_labels: bool) -> None:
    for row, (key, _, color) in enumerate(METHODS):
        stats = cohort[key]
        share = 100 * stats["false_admissions"] / stats["expected_non_admitted"]
        ax.barh(row, share, height=0.52, color=color, zorder=2)
        ax.text(share + 3 if share else 3, row, f"{stats['false_admissions']}/{stats['expected_non_admitted']}",
                va="center", fontsize=9, fontweight="bold", color=INK)
    ax.set_yticks(range(len(METHODS)), [label for _, label, _ in METHODS] if show_labels else [""] * len(METHODS))
    ax.invert_yaxis()
    style(ax, 100, [0, 50, 100], lambda t: f"{t:.0f}%")
    panel_title(ax, title, subtitle)


def render(summary: dict, output: Path) -> None:
    plt.rcParams.update({"svg.hashsalt": "bioai-clinvar-v1", "font.family": "DejaVu Sans"})
    fig = plt.figure(figsize=(13.6, 5.9), facecolor=SURFACE)
    grid = fig.add_gridspec(1, 3, width_ratios=[2.35, 1, 1], left=0.135, right=0.95, top=0.70, bottom=0.22, wspace=0.32)
    stability_panel(fig.add_subplot(grid[0]), summary["population_stability"])
    faults = summary["faults"]
    fault_panel(fig.add_subplot(grid[1]), faults["controlled_fault"], "Controlled faults",
                "False admissions · 16 seeds × 10 faults", True)
    fault_panel(fig.add_subplot(grid[2]), faults["trust_boundary"], "Trust boundary",
                "False admissions · fabricated expert reviews", False)

    reproduction = summary["policy_reproduction"]
    agreement = " · ".join(f"{100 * reproduction[use]['agreement'] / reproduction[use]['n']:.1f}% {use.split('_')[0]}"
                           for use in ["research_summary", "clinical_reference", "expert_reference"])
    n = summary["variants"]
    fig.text(0.02, 0.945, "ClinVar germline benchmark · 2023 decisions, 2026 outcomes",
             fontsize=15, fontweight="bold", color=INK)
    fig.text(0.02, 0.895, f"Agreement with NCBI's own 2023-09 review status ({n:,} sampled variants): {agreement}",
             fontsize=9.5, color=TEXT)
    notes = [
        "Reclassified or conflicting = 2026-09 aggregate classification is conflicting, or includes VUS, likely benign or benign. "
        "False admission = admitted despite a rejected or review-required expected status. Lower is better.",
        "Stability is not correctness: an observational association, not for clinical use. "
        "Trust-boundary failures show why ingestion must be source-grounded.",
    ]
    for i, note in enumerate(notes):
        fig.text(0.02, 0.11 - 0.04 * i, note, fontsize=8.5, color=TEXT)
    fig.text(0.02, 0.025, f"Source: NingyuSUN/bioai-evidence-validator v{summary['validator_version']} · "
                          f"ClinVar 2023-09 and 2026-09 releases (NCBI) · examples/clinvar_germline/results/summary.json",
             fontsize=7.5, color=MUTED)
    output.parent.mkdir(parents=True, exist_ok=True)
    svg = output.suffix == ".svg"
    fig.savefig(output, facecolor=SURFACE, dpi=110, **({"metadata": {"Date": None}} if svg else {}))
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--summary", type=Path, default=ROOT / "results/summary.json")
    parser.add_argument("--output", type=Path, default=REPO / "docs/assets/clinvar_germline_benchmark.svg")
    args = parser.parse_args()
    render(json.loads(args.summary.read_text(encoding="utf-8")), args.output)
    print(args.output)
