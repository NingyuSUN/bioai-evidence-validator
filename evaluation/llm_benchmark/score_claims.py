"""Scenario 1b: the claim only. The model picks the papers (PMID, title) and quotes them; score them alone
and after bioevidence.

    # network: resolve every cited PMID with NCBI and pin its metadata and any open full text (outside the repo)
    uv run --frozen python evaluation/llm_benchmark/score_claims.py ground --answers artifacts/llm-benchmark \
        --snapshots artifacts/claim-snapshots
    # offline, needs the snapshots: check every citation and every record, write verification.jsonl
    uv run --frozen python evaluation/llm_benchmark/score_claims.py verify --answers artifacts/llm-benchmark \
        --snapshots artifacts/claim-snapshots --output evaluation/llm_benchmark/results/literature-claims-pilot
    # offline, replayable from the committed files alone
    uv run --frozen python evaluation/llm_benchmark/score_claims.py score \
        --output evaluation/llm_benchmark/results/literature-claims-pilot

Most cited papers are not openly licensed, so their full text stays in the local snapshot directory; the
repository keeps the answers and, per citation and per record, what was verified (verification.jsonl).

Each citation falls into one category, checked by this file's own code (the resolver's metadata and the
article's paragraphs are read with the library's parsers): no_pmid, not_found (NCBI has no such PMID),
retracted, wrong_paper (the title given does not match the PMID's), quote_found, quote_not_found (open full
text, quote absent), unverifiable (no open full text). With bioevidence, the answer becomes a record citing
each paper with its quote, grounded with `LiteratureGrounder` under the CIViC literature profile: only an
admitted record keeps the model's decision.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import re
import sys
import time
import urllib.error
from pathlib import Path

from bioevidence_validator import literature
from bioevidence_validator.engine import RecordValidator
from bioevidence_validator.grounding import SnapshotStore, SourceBytesGrounder

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import literature_suite  # noqa: E402
import score_literature  # noqa: E402

CASE = score_literature.CASE
CONDITION = "naive_claim"
INVALID = {"no_pmid", "not_found", "retracted", "wrong_paper", "quote_not_found"}
MODEL_NAMES = score_literature.MODEL_NAMES


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def raw_answers(folder: Path) -> list[dict]:
    rows = []
    for path in sorted(folder.glob(f"*/{CONDITION}/*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows.append({"backend": path.parent.parent.name, "task_id": raw["task_id"], "model": raw["model"],
                     "ok": raw["ok"], "answer": raw["answer"], "tools_used": raw["tools_used"],
                     "prompt_sha256": raw["prompt_sha256"]})
    return rows


def pmid_of(text: str) -> str | None:
    return literature.identifier(f"pmid:{re.sub(r'[^0-9]', '', text)}") if re.search(r"\d", text) else None


def ground(answers_dir: Path, snapshots: Path) -> None:
    folder = answers_dir / "literature-pilot"
    keys = sorted({key for row in raw_answers(folder) if row["ok"]
                   for c in row["answer"]["citations"] if (key := pmid_of(c["pmid"]))})
    snapshots.mkdir(parents=True, exist_ok=True)
    path = snapshots / literature.CATALOG
    catalog = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"version": 1, "works": {}}
    plain = literature.http_fetch()

    def fetch(url: str) -> bytes:
        for attempt in range(4):
            try:
                time.sleep(0.2)
                return plain(url)
            except urllib.error.HTTPError as exc:
                if exc.code < 429 or attempt == 3:
                    raise
                time.sleep(2 ** (attempt + 1))
        raise AssertionError("unreachable")

    now = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    for key in keys:
        if key not in catalog["works"]:
            catalog["works"][key] = literature.resolve(key, snapshots, fetch, now, resolver="ncbi", compress=True)
            entry = catalog["works"][key]
            print(f"{key} fulltext={bool(entry['fulltext_sha256'])} license={entry['license']}", flush=True)
    path.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(keys)} cited PMIDs in {path}")


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def same_title(given: str, actual: str) -> bool:
    """Independent of the grounder: at least half of the two titles' words shared."""
    a, b = words(given), words(actual)
    return bool(a and b) and len(a & b) / len(a | b) >= 0.5


class Verifier:
    def __init__(self, snapshots: Path):
        self.store = SnapshotStore.from_directory(snapshots)
        self.catalog = json.loads((snapshots / literature.CATALOG).read_text(encoding="utf-8"))
        self.validator = RecordValidator(profile=CASE / "profile.yaml", grounders=[
            SourceBytesGrounder(self.store), literature.LiteratureGrounder(self.store, self.catalog)])

    def citation(self, cited: dict) -> dict:
        key = pmid_of(cited["pmid"])
        entry = self.catalog["works"].get(key or "")
        if not key or not entry:
            return {"pmid": key, "category": "no_pmid"}
        meta = literature.parse_metadata(entry["resolver"], self.store.get(entry["metadata_sha256"]) or b"")
        facts = {"pmid": key, "license": entry["license"], "open_text": bool(entry["fulltext_sha256"])}
        if not meta["found"]:
            return {**facts, "category": "not_found"}
        facts["title_matches"] = same_title(cited["title"], meta["title"])
        if meta["retracted"]:
            return {**facts, "category": "retracted"}
        if not facts["title_matches"]:
            return {**facts, "category": "wrong_paper"}
        if not entry["fulltext_sha256"]:
            return {**facts, "category": "unverifiable"}
        blocks = literature.jats_blocks(self.store.get(entry["fulltext_sha256"]) or b"")
        found = score_literature.in_paper(cited["quote"], [list(b) for b in blocks])
        return {**facts, "category": "quote_found" if found else "quote_not_found"}

    def record(self, task: dict, answer: dict) -> dict | None:
        if answer["decision"] == "stop" or not answer["citations"]:
            return None
        claim = task["claim"]
        direction = "supports" if answer["decision"] == "supports" else "does_not_support"
        sources, items = [], []
        for n, cited in enumerate(answer["citations"], start=1):
            key = pmid_of(cited["pmid"]) or f"unparsable:{n}"
            entry = self.catalog["works"].get(key, {})
            sha = entry.get("fulltext_sha256") or entry.get("metadata_sha256") or "0" * 64
            sources.append({"id": f"bioev:paper-{n}", "title": cited["title"] or "(no title)", "source_type": "publication",
                            "uri": key if key.startswith("pmid:") else f"urn:unparsable:{n}", "version": "cited by the model",
                            "retrieved_at": entry.get("retrieved_at", "2026-01-01T00:00:00Z"), "sha256": sha,
                            "observed_sha256": sha})
            items.append({"id": f"bioev:quote-{n}", "source_artifact_id": f"bioev:paper-{n}", "locator": "",
                          "extracted_text": cited["quote"], "evidence_type": "publication_quote",
                          "extraction_method": "llm_extraction", "scope": ["NCBITaxon:9606"]})
        return {
            "record_id": f"bioev:claim-{task['task_id']}", "profile_id": "civic-literature",
            "statement": {"id": f"bioev:claim-statement-{task['task_id']}",
                          "subject": {"id": "civic.mp:0", "label": claim["molecular_profile"], "entity_type": "molecular_profile"},
                          "predicate": f"{direction}_significance",
                          "object": {"id": f"civic.claim:{task['task_id']}", "entity_type": "clinical_significance",
                                     "label": f"{claim['significance']} in {claim['disease']}"},
                          "scope": ["NCBITaxon:9606"], "statement_status": "proposed",
                          "evidence_lines": [{"id": "bioev:quote-line", "direction": "supports",
                                              "evidence_item_ids": [i["id"] for i in items]}]},
            "source_artifacts": sources, "evidence_items": items, "adjudications": [],
            "requested_uses": ["research_summary"],
        }

    def check(self, task: dict, answer: dict) -> dict:
        record = self.record(task, answer)
        if record is None:
            return {"status": "not_submitted", "codes": []}
        report = self.validator.validate(record)
        return {"status": report["overall_status"], "codes": sorted({f["rule_id"] for f in report["findings"]})}


def verify(answers_dir: Path, snapshots: Path, output: Path) -> None:
    tasks = {t["task_id"]: t for t in load_jsonl(literature_suite.TASKS / "pilot.jsonl")}
    folder = answers_dir / "literature-pilot"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    verifier = Verifier(snapshots)
    answers, verification = raw_answers(folder), []
    for row in answers:
        answer = row["answer"] if row["ok"] else None
        verification.append({"backend": row["backend"], "task_id": row["task_id"],
                             "citations": [verifier.citation(c) for c in (answer or {}).get("citations", [])],
                             "bioevidence": verifier.check(tasks[row["task_id"]], answer) if answer
                             else {"status": "not_submitted", "codes": []}})
    output.mkdir(parents=True, exist_ok=True)
    models = {b: {"model": v["model"], "cli_version": v["cli_version"]} for b, v in manifest["backends"].items()}
    write_jsonl(output / "answers.jsonl", answers + [{"models": models}])
    write_jsonl(output / "verification.jsonl", verification)
    score(output)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
                    encoding="utf-8", newline="\n")


def expected_directions() -> dict[str, str]:
    """The claim's own CIViC direction (for an 'unrelated' task, the donor claim's)."""
    rows = {json.loads(line)["evidence_id"]: json.loads(line) for line in
            gzip.decompress((CASE / "sources/civic-evidence.jsonl.gz").read_bytes()).decode("utf-8").splitlines()}
    return {r["task_id"]: "supports" if rows[r["civic_evidence_id"]]["evidence_direction"] == "Supports"
            else "does_not_support"
            for r in load_jsonl(literature_suite.TASKS / "references.jsonl") if r["split"] == "pilot"}


def rate(events: int, n: int) -> dict:
    return {"events": events, "n": n, "rate": round(events / n, 4) if n else None,
            "wilson_95": score_literature.wilson(events, n)}


def score(output: Path) -> dict:
    answers = load_jsonl(output / "answers.jsonl")
    models = answers[-1]["models"]
    verification = {(v["backend"], v["task_id"]): v for v in load_jsonl(output / "verification.jsonl")}
    references = {r["task_id"]: r for r in load_jsonl(literature_suite.TASKS / "references.jsonl") if r["split"] == "pilot"}
    expected = expected_directions()
    rows = []
    for row in answers[:-1]:
        v = verification[row["backend"], row["task_id"]]
        answer = row["answer"] if row["ok"] else None
        decision = answer["decision"] if answer else "stop"
        categories = [c["category"] for c in v["citations"]]
        for config, final in (("llm", decision),
                              ("llm_bioevidence", decision if v["bioevidence"]["status"] == "admitted" else "stop")):
            rows.append({"backend": row["backend"], "task_id": row["task_id"], "config": config,
                         "expected": expected[row["task_id"]], "final": final, "citations": categories,
                         "cites_curated_paper": any(c.get("pmid") == f"pmid:{references[row['task_id']]['claim_from_pmid']}"
                                                    for c in v["citations"]),
                         "reason_codes": v["bioevidence"]["codes"] if config == "llm_bioevidence" else []})
    results = {}
    for backend in [m for m in MODEL_NAMES if m in models]:
        results[backend] = {}
        for config in ("llm", "llm_bioevidence"):
            mine = [r for r in rows if r["backend"] == backend and r["config"] == config]
            delivered = [r for r in mine if r["final"] != "stop"]
            results[backend][config] = metrics(mine, delivered)
    pooled = {config: metrics([r for r in rows if r["config"] == config],
                              [r for r in rows if r["config"] == config and r["final"] != "stop"])
              for config in ("llm", "llm_bioevidence")}
    citations = [c for r in rows if r["config"] == "llm" for c in r["citations"]]
    summary = {"benchmark": "llm-literature-claims-v1", "split": "pilot", "condition": CONDITION, "models": models,
               "results": results, "pooled": pooled,
               "citation_categories": {k: citations.count(k) for k in sorted(set(citations))},
               "verification_sha256": hashlib.sha256((output / "verification.jsonl").read_bytes()).hexdigest()}
    write_jsonl(output / "rows.jsonl", rows)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8",
                                         newline="\n")
    (output / "summary.md").write_text(render(summary), encoding="utf-8", newline="\n")
    print(render(summary))
    return summary


def metrics(mine: list[dict], delivered: list[dict]) -> dict:
    return {"tasks": len(mine),
            "answered": rate(len(delivered), len(mine)),
            "correct_decision": rate(sum(r["final"] == r["expected"] for r in mine), len(mine)),
            "wrong_direction": rate(sum(r["final"] not in ("stop", r["expected"]) for r in mine), len(mine)),
            "invalid_citation": rate(sum(any(c in INVALID for c in r["citations"]) for r in delivered), len(delivered)),
            "only_verified_citations": rate(sum(bool(r["citations"]) and all(c == "quote_found" for c in r["citations"])
                                                for r in delivered), len(delivered)),
            "no_citation": rate(sum(not r["citations"] for r in delivered), len(delivered)),
            "cites_curated_paper": rate(sum(r["cites_curated_paper"] for r in delivered), len(delivered))}


def fraction(m: dict) -> str:
    return f"{m['events']}/{m['n']}" if m["n"] else "N/A"


def render(summary: dict) -> str:
    lines = ["# Literature benchmark, scenario 1b: the claim only (pilot set)", "",
             "The model is asked, as a user would ask a chatbot, what the literature says about a CIViC-style claim, "
             "and to cite papers (PMID, title, quote). No curation rules, no source, no tools.", "",
             "| Model | Configuration | Answered | Correct decision | Wrong direction | Answers with an invalid citation | "
             "Answers with only verified citations | Answers without a citation |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    blocks = [(MODEL_NAMES[b], c) for b, c in summary["results"].items()] + [("All six models", summary["pooled"])]
    for name, configs in blocks:
        for config, label in (("llm", "LLM alone"), ("llm_bioevidence", "+ bioevidence")):
            m = configs[config]
            lines.append(f"| {name} | {label} | {fraction(m['answered'])} | {fraction(m['correct_decision'])} | "
                         f"{fraction(m['wrong_direction'])} | {fraction(m['invalid_citation'])} | "
                         f"{fraction(m['only_verified_citations'])} | {fraction(m['no_citation'])} |")
    cats = ", ".join(f"{k} {v}" for k, v in summary["citation_categories"].items())
    lines += ["", f"Citations given by the models alone: {cats}.", "",
              "Invalid: no PMID, a PMID that does not exist, a retracted paper, a title that does not match the PMID, or "
              "a quote not in the open full text. Unverifiable: no open full text (sent to review, never counted as "
              "verified). With bioevidence, only admitted records are answers; the rest go to a human.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    steps = parser.add_subparsers(dest="step", required=True)
    g = steps.add_parser("ground")
    g.add_argument("--answers", type=Path, required=True)
    g.add_argument("--snapshots", type=Path, required=True)
    v = steps.add_parser("verify")
    v.add_argument("--answers", type=Path, required=True)
    v.add_argument("--snapshots", type=Path, required=True)
    v.add_argument("--output", type=Path, required=True)
    s = steps.add_parser("score")
    s.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.step == "ground":
        ground(args.answers, args.snapshots)
    elif args.step == "verify":
        verify(args.answers, args.snapshots, args.output)
    else:
        score(args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
