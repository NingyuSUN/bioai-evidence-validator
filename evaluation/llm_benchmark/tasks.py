"""Build the LLM benchmark tasks from the pinned ClinVar sample, deterministically.

    uv run --frozen python evaluation/llm_benchmark/tasks.py            # write tasks/
    uv run --frozen python evaluation/llm_benchmark/tasks.py --check    # fail if tasks/ is out of date

Each task asks whether one variant's germline P/LP classification may enter a clinical reference.
The reference answer is NCBI's own 2023-09 aggregate review status, not this repository's rules:
admit at two stars or more (several criteria-based submitters, expert panel or practice guideline)
without conflict; stop otherwise. Variants where the two policies differ (a dissenting submission
that NCBI ignores or lets an expert panel override) are left out, so the reference is unambiguous.

Categories:
  admit          2-4 star P/LP, no dissenting submission                -> admit
  insufficient   0-1 star P/LP (no criteria, or a single submitter)     -> stop
  conflict       NCBI "conflicting interpretations"                     -> stop, and flag the conflict
  unanswerable   a VariationID ClinVar never assigned                   -> stop

Tasks are ordered by a keyed SHA-256, and the pilot set (used to check prompts and scoring) never
overlaps the test set. `tasks/*.jsonl` holds what the models see; `references.jsonl` the answers.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CLINVAR = REPO / "examples" / "clinvar_germline"
KEY = "bioai-llm-benchmark-v1"
SIZES = {"pilot": {"admit": 8, "insufficient": 8, "conflict": 8, "unanswerable": 6},
         "test": {"admit": 40, "insufficient": 40, "conflict": 40, "unanswerable": 30}}
MAX_SUBMISSIONS = 10  # keeps prompts and answers short; stated in the protocol
FAKE_ID_BASE = 90_000_000  # far above any VariationID ClinVar has assigned (2.6 million in 2023-09)


def clinvar_pipeline():
    spec = importlib.util.spec_from_file_location("llm_benchmark_clinvar_pipeline", CLINVAR / "pipeline.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def keyed(text: str) -> str:
    return hashlib.sha256(f"{KEY}:{text}".encode()).hexdigest()


def category(case: dict, direction) -> str | None:
    dissent = any(direction(s["ClinicalSignificance"]) == "contradicts" for s in case["submissions"])
    if case["stratum"] == "conflicting":
        return "conflict"
    if dissent:
        return None  # NCBI and the repository's policy disagree here: not a clean reference
    if case["stratum"] in ("multiple_submitters", "expert_panel", "practice_guideline"):
        return "admit"
    if case["stratum"] in ("no_criteria", "single_submitter"):
        return "insufficient"
    return None


def source_rows(case: dict) -> list[dict[str, str]]:
    return [{"scv": s["SCV"], "submitter": s["Submitter"], "classification": s["ClinicalSignificance"],
             "review_status": s["ReviewStatus"], "collection_method": s["CollectionMethod"],
             "date_last_evaluated": s["DateLastEvaluated"]} for s in case["submissions"]]


def build() -> dict[str, list[dict]]:
    pipeline = clinvar_pipeline()
    sample = pipeline.ClinVarSample()
    pools: dict[str, list[dict]] = {name: [] for name in SIZES["test"]}
    for case in sample.cases:
        name = category(case, pipeline.direction)
        if name and len(case["submissions"]) <= MAX_SUBMISSIONS:
            pools[name].append({"variation_id": case["variation_id"], "gene": case["gene"], "stratum": case["stratum"],
                                "ncbi_2023_09": case["clinvar_2023_09"], "source": source_rows(case)})
    genes = sorted({case["gene"] for case in sample.cases})
    fakes: dict[str, str] = {}
    n = 0
    while len(fakes) < SIZES["pilot"]["unanswerable"] + SIZES["test"]["unanswerable"]:
        digest = keyed(f"unanswerable:{n}")
        fakes.setdefault(str(FAKE_ID_BASE + int(digest[:12], 16) % 9_000_000), genes[int(digest[12:20], 16) % len(genes)])
        n += 1
    pools["unanswerable"] = [{"variation_id": vid, "gene": gene, "stratum": "not_in_clinvar", "ncbi_2023_09": None,
                              "source": []} for vid, gene in fakes.items()]
    for name in pools:
        pools[name].sort(key=lambda row: keyed(row["variation_id"]))
    splits: dict[str, list[dict]] = {"pilot": [], "test": []}
    references = []
    for name, pool in pools.items():
        start = 0
        for split in ("pilot", "test"):
            chosen = pool[start:start + SIZES[split][name]]
            if len(chosen) < SIZES[split][name]:
                raise ValueError(f"not enough {name} variants")
            start += SIZES[split][name]
            for row in chosen:
                task_id = "t-" + keyed("task:" + row["variation_id"])[:10]
                splits[split].append({"task_id": task_id, "variation_id": row["variation_id"], "gene": row["gene"],
                                      "source": row["source"]})
                references.append({"task_id": task_id, "split": split, "category": name,
                                   "expected_decision": "admit" if name == "admit" else "stop",
                                   "conflict_in_source": name == "conflict", "stratum": row["stratum"],
                                   "ncbi_2023_09": row["ncbi_2023_09"]})
    for split in splits.values():
        split.sort(key=lambda row: row["task_id"])
    references.sort(key=lambda row: (row["split"], row["task_id"]))
    return {"pilot.jsonl": splits["pilot"], "test.jsonl": splits["test"], "references.jsonl": references}


def render(rows: list[dict]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    check = parser.parse_args().check
    folder = ROOT / "tasks"
    folder.mkdir(exist_ok=True)
    stale = []
    for name, rows in build().items():
        path, text = folder / name, render(rows)
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(name)
        else:
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"{path}: {len(rows)} rows")
    if stale:
        print(f"out of date: {', '.join(stale)}; run evaluation/llm_benchmark/tasks.py", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
