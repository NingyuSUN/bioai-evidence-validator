"""Build the literature tasks from the pinned CIViC corpus (examples/civic_literature), deterministically.

    uv run --frozen python evaluation/llm_benchmark/tasks_literature.py            # write literature_tasks/
    uv run --frozen python evaluation/llm_benchmark/tasks_literature.py --check    # fail if out of date

Each task pairs one open-access paper with one CIViC-style claim. The reference answer is CIViC's own
curation of that paper, not this repository's rules:
  supports          a CIViC item from this paper with direction "Supports"            -> supports
  does_not_support  a CIViC item from this paper with direction "Does Not Support"    -> does_not_support
  unrelated         a claim from another paper whose gene this paper never mentions  -> stop
Pilot and test tasks use different papers. `papers.json.gz` holds each paper's titles and paragraphs as
[id, kind, text], with the ids the literature grounder uses, so the model runner needs no parser.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = REPO / "examples" / "civic_literature"
OUT = ROOT / "literature_tasks"
KEY = "bioai-llm-literature-v1"
SIZES = {"pilot": {"supports": 8, "does_not_support": 4, "unrelated": 6},
         "test": {"supports": 50, "does_not_support": 16, "unrelated": 30}}  # 20 openly licensed papers have a DNS item


def keyed(text: str) -> str:
    return hashlib.sha256(f"{KEY}:{text}".encode()).hexdigest()


def corpus():
    sys.path.insert(0, str(CASE))
    try:
        spec = importlib.util.spec_from_file_location("llm_literature_pipeline", CASE / "pipeline.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module.Corpus()


def claim(row: dict) -> dict:
    return {"molecular_profile": row["molecular_profile"], "disease": row["disease"],
            "evidence_type": row["evidence_type"], "significance": row["significance"], "therapies": row["therapies"]}


def build() -> dict[str, object]:
    source = corpus()
    papers = sorted(source.manifest["corpus"], key=keyed)
    rows: dict[str, list[dict]] = {}
    for row in source.evidence:
        rows.setdefault(row["citation_id"], []).append(row)
    text = {pmid: source.blocks(pmid) for pmid in papers}  # (id, "title" or "p", text)
    joined = {pmid: "\n".join(t for _, _, t in blocks) for pmid, blocks in text.items()}
    seen: dict[tuple[str, str], bool] = {}

    def mentioned(pmid: str, gene: str) -> bool:
        if (pmid, gene) not in seen:
            seen[pmid, gene] = bool(re.search(rf"\b{re.escape(gene)}\b", joined[pmid]))
        return seen[pmid, gene]

    splits: dict[str, list[dict]] = {"pilot": [], "test": []}
    references, used = [], {"pilot": set(), "test": set()}
    for split in ("pilot", "test"):
        other = used["pilot"] if split == "test" else set()
        for category in ("does_not_support", "supports", "unrelated"):
            wanted, chosen = SIZES[split][category], 0
            for pmid in papers:
                if chosen == wanted:
                    break
                if pmid in other or pmid in used[split]:
                    continue
                if category == "unrelated":
                    donors = [r for p in papers if p != pmid for r in rows[p]
                              if not mentioned(pmid, r["molecular_profile"].split()[0])]
                    candidates = sorted(donors, key=lambda r: keyed(pmid + ":" + r["evidence_id"]))[:1]
                else:
                    direction = "Supports" if category == "supports" else "Does Not Support"
                    candidates = sorted((r for r in rows[pmid] if r["evidence_direction"] == direction),
                                        key=lambda r: keyed(r["evidence_id"]))[:1]
                if not candidates:
                    continue
                row = candidates[0]
                task_id = "l-" + keyed(f"{split}:{pmid}:{row['evidence_id']}")[:10]
                splits[split].append({"task_id": task_id, "pmid": pmid, "title": source.title(pmid), "claim": claim(row)})
                references.append({"task_id": task_id, "split": split, "category": category, "pmid": pmid,
                                   "expected_decision": "stop" if category == "unrelated" else category,
                                   "civic_evidence_id": row["evidence_id"], "claim_from_pmid": row["citation_id"]})
                used[split].add(pmid)
                chosen += 1
            if chosen < wanted:
                raise ValueError(f"only {chosen} {category} tasks for the {split} set")
    for tasks in splits.values():
        tasks.sort(key=lambda task: task["task_id"])
    references.sort(key=lambda r: (r["split"], r["task_id"]))
    needed = sorted({task["pmid"] for tasks in splits.values() for task in tasks}, key=int)
    papers_blob = json.dumps({pmid: [list(p) for p in text[pmid]] for pmid in needed}, ensure_ascii=False,
                             sort_keys=True).encode("utf-8")
    return {"pilot.jsonl": splits["pilot"], "test.jsonl": splits["test"], "references.jsonl": references,
            "papers.json.gz": gzip.compress(papers_blob, mtime=0)}


def render(rows: list[dict]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    check = parser.parse_args().check
    OUT.mkdir(exist_ok=True)
    stale = []
    for name, content in build().items():
        data = content if isinstance(content, bytes) else render(content).encode("utf-8")
        path = OUT / name
        if check:
            if not path.exists() or path.read_bytes() != data:
                stale.append(name)
        else:
            path.write_bytes(data)
            print(f"{path}: {len(content) if isinstance(content, list) else len(data)}")
    if stale:
        print(f"out of date: {', '.join(stale)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
