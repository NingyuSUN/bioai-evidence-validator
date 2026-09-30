"""Render evaluation/error_taxonomy.yaml and the committed benchmark results into docs/ERROR_TAXONOMY.md.

    uv run --frozen python tools/render_taxonomy.py          # write the page
    uv run --frozen python tools/render_taxonomy.py --check  # fail if the page is out of date

Admission counts for every negative control come from the committed results, not from the YAML.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TAXONOMY = ROOT / "evaluation" / "error_taxonomy.yaml"
PAGE = ROOT / "docs" / "ERROR_TAXONOMY.md"
RESULTS = {"vbo": ROOT / "examples/vbo_canine/results/decisions.jsonl",
           "clinvar": ROOT / "examples/clinvar_germline/results/faults.jsonl"}
CASE_PAGES = {"vbo": "../examples/vbo_canine/README.md", "clinvar": "../examples/clinvar_germline/README.md"}
ISSUES = "https://github.com/NingyuSUN/bioai-evidence-validator/issues/"
SYMBOL = {"caught": "✅ caught", "partial": "🟡 partial", "exposed": "❌ exposed", "uncovered": "⬜ uncovered"}
LAYER_SHORT = {"deterministic": "Rules", "grounding": "Grounding", "model_review": "Models", "human_review": "Experts",
               "attestation": "Attestation", "process": "Design"}


def load_taxonomy() -> dict:
    return yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))


def control_results() -> dict[str, Counter]:
    """Per negative control ("case:category"): how many cases each method admitted."""
    stats: dict[str, Counter] = defaultdict(Counter)
    for case, path in RESULTS.items():
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["cohort"] == "real_source":
                continue
            counts = stats[f"{case}:{row['category']}"]
            counts["n"] += 1
            for method in ("schema_only", "aggregate_quality", "full", "grounded"):
                counts[method] += row[method] == "admitted"
    return dict(stats)


def admitted(s: Counter) -> str:
    rules = f" (rules alone: {s['full']})" if s["full"] != s["grounded"] else ""
    return f"{s['grounded']}/{s['n']}{rules}"


def planned(items: list[str]) -> str:
    return ", ".join(f"[{i}]({ISSUES}{i[1:]})" if i.startswith("#") else i for i in items) or "—"


def render() -> str:
    tax, stats = load_taxonomy(), control_results()
    modes = tax["failure_modes"]
    counts = Counter(m["status"] for m in modes)
    out = [
        "# Error taxonomy",
        "",
        "How AI-assisted biological curation goes wrong, which layer is expected to catch each failure, and what the",
        "benchmarks show today. Generated from `evaluation/error_taxonomy.yaml` and the committed benchmark results by",
        "`tools/render_taxonomy.py`; a test fails if this page, the benchmark faults and the rule codes drift apart.",
        "Part of the [AI validation roadmap](AI_VALIDATION_ROADMAP.md).",
        "",
        f"**{len(modes)} failure modes:** " + " · ".join(f"{SYMBOL[s]} {counts.get(s, 0)}" for s in SYMBOL),
        "",
        "## Coverage matrix",
        "",
        "Negative controls show how many injected cases the validator with grounding admitted (0 is the goal); where",
        "the rules alone admit a different number, it follows in parentheses.",
        "",
        "| ID | Failure mode | Origin | Expected to catch it | Status | Negative controls: admitted / cases | Next |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in modes:
        controls = "<br>".join(f"`{c}` {admitted(stats[c])}" for c in m["negative_controls"]) or "—"
        layers = ", ".join(LAYER_SHORT[layer] for layer in m["catch_layers"])
        out.append(f"| {m['id']} | {m['name']} | {m['stage']} | {layers} | {SYMBOL[m['status']]} | {controls} | "
                   f"{planned(m['planned'])} |")
    out += ["", "## Legend", "", "| Status | Meaning |", "|---|---|"]
    out += [f"| {SYMBOL[s]} | {text} |" for s, text in tax["statuses"].items()]
    out += ["", "| Layer | Meaning |", "|---|---|"]
    out += [f"| {LAYER_SHORT[layer]} (`{layer}`) | {text} |" for layer, text in tax["layers"].items()]
    out += ["", "| Origin | Meaning |", "|---|---|"]
    out += [f"| {stage} | {text} |" for stage, text in tax["stages"].items()]
    out += ["", "## Failure modes"]
    for m in modes:
        out += ["", f"### {m['id']} · {m['name']}", "", f"**{SYMBOL[m['status']]}** · origin: {m['stage']} · "
                f"expected layer: {', '.join(LAYER_SHORT[layer] for layer in m['catch_layers'])}", "",
                m["definition"], "", f"*Example:* {m['example']}"]
        if m["rule_codes"]:
            out += ["", "Rule codes: " + ", ".join(f"`{code}`" for code in m["rule_codes"])]
        for key, label in (("uncovered_form", "Not yet covered"), ("note", "Note")):
            if m.get(key):
                out += ["", f"*{label}:* {m[key]}"]
        if m["negative_controls"]:
            out += ["", "| Negative control | Cases | Schema-only admitted | Aggregate gate admitted | Rules admitted | "
                    "Rules + grounding admitted |", "|---|---:|---:|---:|---:|---:|"]
            for c in m["negative_controls"]:
                s = stats[c]
                case, category = c.split(":")
                out.append(f"| [{case}]({CASE_PAGES[case]}) `{category}` | {s['n']} | {s['schema_only']} | "
                           f"{s['aggregate_quality']} | {s['full']} | {s['grounded']} |")
        if m["planned"]:
            out += ["", f"Planned: {planned(m['planned'])}"]
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    page = render()
    if parser.parse_args().check:
        current = PAGE.read_text(encoding="utf-8") if PAGE.exists() else ""
        if current != page:
            print(f"{PAGE} is out of date; run tools/render_taxonomy.py", file=sys.stderr)
            return 1
        return 0
    PAGE.write_text(page, encoding="utf-8", newline="\n")
    print(PAGE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
