"""Render the AI validation figure from the committed benchmark results.

    uv run --with matplotlib python evaluation/llm_benchmark/plot.py

Reads results/*/summary.json and writes docs/assets/ai_validation_results.svg. Output is deterministic for a given
matplotlib version (fixed SVG ids, no timestamp).
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

# The first three slots of the dataviz reference categorical palette, validated in this order on this surface
# (all checks pass; the aqua is below 3:1 against the surface, so every segment carries a direct label).
SURFACE, GRID = "#fcfcfb", "#e4e4e0"
INK, TEXT, MUTED = "#0b0b0b", "#52514e", "#7a7974"
GOOD, BAD, PERSON = "#2a78d6", "#eb6834", "#1baf7a"


def load(name: str) -> dict:
    return json.loads((ROOT / "results" / name / "summary.json").read_text(encoding="utf-8"))


def events(metric: dict) -> tuple[int, int]:
    return metric["events"], metric["n"]


def outcome_panel(ax, pooled: dict) -> None:
    rows = [("model", "Model alone"), ("gate", "+ bioevidence gate"), ("loop", "+ feedback loop")]
    for y, (key, _) in enumerate(rows):
        m = pooled[key]
        compatible, wrong = m["compatible"]["events"], m["wrong"]["events"] + m["invalid"]["events"]
        person, total = m["routed_to_a_person"]["events"], m["tasks"]
        left = 0
        for value, color in ((compatible, GOOD), (wrong, BAD), (person, PERSON)):
            if value:
                ax.barh(y, value, left=left, height=0.56, color=color, edgecolor=SURFACE, linewidth=2)
                ax.text(left + value / 2, y, str(value), ha="center", va="center", fontsize=9, color=INK,
                        fontweight="bold")
            left += value
        ax.text(total + 4, y, f"of {total}", va="center", fontsize=8, color=MUTED)
    ax.set_yticks(range(len(rows)), [label for _, label in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, 300)
    ax.set_xticks([0, 69, 138, 207, 276], ["0", "25%", "50%", "75%", "100%"])
    style(ax)
    ax.text(0, 1.22, "Single-cell annotation, held-out clusters", transform=ax.transAxes, fontsize=12,
            fontweight="bold", color=INK)
    ax.text(0, 1.12, "6 models × 46 clusters, protocol frozen before the run. With bioevidence, only admitted answers count as answers",
            transform=ax.transAxes, fontsize=8, color=MUTED)
    ax.legend(handles=[Patch(color=GOOD, label="Compatible with the authors' term"),
                       Patch(color=BAD, label="Wrong or invalid"),
                       Patch(color=PERSON, label="Sent to a person")],
              loc="upper left", bbox_to_anchor=(0, -0.16), ncol=3, frameon=False, fontsize=8, labelcolor=TEXT,
              handlelength=1.2, columnspacing=1.4)


def error_panel(ax) -> None:
    test, external = load("celltype-test")["pooled"], load("celltype-external")["pooled"]
    claims, agent = load("literature-claims-pilot")["pooled"], load("agent-pilot")["pooled"]
    rows = [
        ("Literature, claim only, no source", events(claims["llm"]["invalid_citation"]),
         events(claims["llm_bioevidence"]["invalid_citation"])),
        ("Single-cell, held-out", events(test["model"]["with_identifier_or_marker_error"]),
         events(test["loop"]["with_identifier_or_marker_error"])),
        ("Single-cell, external studies", events(external["model"]["with_identifier_or_marker_error"]),
         events(external["loop"]["with_identifier_or_marker_error"])),
        ("Literature agent with PubMed", events(agent["agent"]["invalid_citation"]), events(agent["loop"]["invalid_citation"])),
    ]
    for y, (_, (bad, n), (after, admitted)) in enumerate(rows):
        share = 100 * bad / n
        ax.barh(y, share, height=0.56, color=BAD, edgecolor=SURFACE, linewidth=2)
        ax.text(share + 1.5, y, f"{bad}/{n} ({share:.0f}%)", va="center", fontsize=9, color=INK, fontweight="bold")
        ax.text(101, y, f"→ {after} of {admitted} admitted", va="center", fontsize=9, color=TEXT)
    ax.set_yticks(range(len(rows)), [label for label, _, _ in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100], ["0", "25%", "50%", "75%", "100%"])
    style(ax)
    ax.text(0, 1.22, "Answers with an invalid identifier or citation", transform=ax.transAxes, fontsize=12,
            fontweight="bold", color=INK)
    ax.text(0, 1.12, "Model's own answers, and how many bioevidence admitted (every model, all three vendors)",
            transform=ax.transAxes, fontsize=8, color=MUTED)


def style(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.tick_params(axis="x", colors=MUTED, labelsize=8, length=0, pad=5)
    ax.tick_params(axis="y", colors=TEXT, labelsize=9.5, length=0, pad=8)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO / "docs" / "assets" / "ai_validation_results.svg")
    args = parser.parse_args(argv)
    plt.rcParams.update({"svg.hashsalt": "bioevidence", "font.family": "DejaVu Sans"})
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(9.6, 6.6), gridspec_kw={"hspace": 1.05})
    fig.patch.set_facecolor(SURFACE)
    outcome_panel(top, load("celltype-test")["pooled"])
    error_panel(bottom)
    fig.subplots_adjust(left=0.27, right=0.82, top=0.88, bottom=0.07)
    fig.savefig(args.output, format="svg", facecolor=SURFACE, metadata={"Date": None})
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
