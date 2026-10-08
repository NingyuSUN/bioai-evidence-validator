"""Real AI extraction (#21): six models extract clinical evidence claims from the full text of openly licensed
papers, and every claim goes through bioevidence's whole chain.

    uv run --frozen python evaluation/llm_benchmark/extraction_loop.py run --split pilot --output C:/t/extraction-pilot
    uv run --frozen python evaluation/llm_benchmark/extraction_loop.py review --output C:/t/extraction-pilot
    uv run --frozen python evaluation/llm_benchmark/extraction_loop.py collect --output C:/t/extraction-pilot \
        --results evaluation/llm_benchmark/results/extraction-pilot
    uv run --frozen python evaluation/llm_benchmark/extraction_loop.py score --results evaluation/llm_benchmark/results/extraction-pilot

The corpus is `examples/civic_extraction`: papers that PMC lists under CC BY or CC0 and that CIViC curated, none
used by any earlier benchmark. Each episode shows one model one paper, paragraph by paragraph, and asks for every
clinical evidence claim about a cancer gene the paper itself reports. A claim is the part of a bioevidence draft
that carries information: its statement (an HGNC gene, a CIViC-style evidence type, a Disease Ontology term) and
its evidence (verbatim quotes, each at its paragraph). Field names and choices come from `draft-schema`; the
fields a model should not decide (the source, its hash, the extraction method, the scope) are added from the
pinned corpus. The variant and therapies are recorded with each claim but are not part of the validated record.

The chain, stage by stage:
1. extracted: a reply that matches the schema;
2. provenance: the claim builds into a record (`build_record`) that traces to the pinned paper;
3. rules: the profile's deterministic rules;
4. grounding: every quote is in the paper (at its paragraph), the gene is an approved HGNC symbol with its own
   identifier, the disease a current Disease Ontology term with its own name;
5. feedback: fixable findings go back to the model, one revision call per paper and round, at most three
   attempts per claim; evidence that contradicts the claim goes to a person as it is;
6. model review: a fast model of another vendor reads each admitted claim's quotes without seeing the extractor's
   reasoning (the reviewer prompt of the semantic checks), and its reading is recorded as a non-human review;
7. human review: the knowledge-base use needs a person's acceptance. No expert has reviewed these claims; a
   seeded sample with a labelling kit is prepared instead.

Scoring is independent of the grounders: identifiers and quotes are looked up directly, and claims are compared
with CIViC's curation of the same paper (gene, and the disease or a broader or narrower one).
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import copy
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import random
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from bioevidence_validator import feedback
from bioevidence_validator.draft import build_record, draft_json_schema
from bioevidence_validator.engine import RecordValidator
from bioevidence_validator.grounding import SnapshotStore, SourceBytesGrounder
from bioevidence_validator.identifiers import GeneGrounder, Genes, Ontology, OntologyGrounder, _label_key
from bioevidence_validator.literature import normalize, quote_in

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
import agent_loop  # noqa: E402
import review_suite  # noqa: E402
import run_models  # noqa: E402
import score_claims  # noqa: E402

CASE = REPO / "examples" / "civic_extraction"
SOURCES = CASE / "sources"
PROFILE = CASE / "profile.yaml"
SCOPE = ["NCBITaxon:9606"]
ROUNDS = 3
USES = ["research_summary", "curation_queue", "knowledge_base"]
# Reviewers are fast models of another vendor, rotating as in the semantic checks.
REVIEWER = {"claude": "gemini-flash", "gpt": "claude-haiku", "gemini": "gpt-luna"}
# Predicate -> CIViC evidence type and clinical significance, for the reviewer and the comparison with CIViC.
KINDS = {"predicts_sensitivity_in": ("Predictive", "Sensitivity/Response"),
         "predicts_resistance_in": ("Predictive", "Resistance"),
         "poor_outcome_in": ("Prognostic", "Poor Outcome"), "better_outcome_in": ("Prognostic", "Better Outcome"),
         "diagnostic_of": ("Diagnostic", "Positive"), "predisposes_to": ("Predisposing", "Predisposition")}
CIVIC_TYPES = {"Predictive", "Prognostic", "Diagnostic", "Predisposing"}
STRICT_DROP = {"minLength", "minItems", "uniqueItems", "description", "format", "pattern"}
TAXONOMY = REPO / "evaluation" / "error_taxonomy.yaml"
SAMPLE_SEED, PER_GROUP = 20261006, 20
LABEL_COLUMNS = ["sample_id", "pmid", "claim_correct", "error_codes", "rationale", "reviewer_id",
                 "reviewer_qualification", "annotated_at", "minutes_spent"]


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _strict(node: Any) -> Any:
    """A JSON Schema the model CLIs accept in strict mode: every property required, no length or format rules."""
    if isinstance(node, dict):
        out = {k: _strict(v) for k, v in node.items() if k not in STRICT_DROP}
        if out.get("type") == "object" and "properties" in out:
            out["required"] = list(out["properties"])
        return out
    if isinstance(node, list):
        return [_strict(v) for v in node]
    return node


def claim_schema() -> dict:
    """One claim: the statement and evidence parts of a draft (`draft-schema` for the case profile), plus the
    variant and therapies, which the record does not hold."""
    draft = draft_json_schema(PROFILE)
    statement = _strict(draft["properties"]["statement"])
    del statement["properties"]["scope"]  # set from the corpus: human, like every CIViC item
    statement["required"] = list(statement["properties"])
    item = _strict(draft["properties"]["evidence"]["items"])
    item["properties"] = {"locator": {"type": "string"}, "text": {"type": "string"},
                          "direction": {"type": "string", "enum": ["supports", "contradicts"]}}
    item["required"] = list(item["properties"])
    return {"type": "object", "additionalProperties": False, "required": ["statement", "variant", "therapies", "evidence"],
            "properties": {"statement": statement, "variant": {"type": "string"},
                           "therapies": {"type": "array", "items": {"type": "string"}},
                           "evidence": {"type": "array", "items": item}}}


SCHEMA = {"type": "object", "additionalProperties": False, "required": ["claims"],
          "properties": {"claims": {"type": "array", "items": claim_schema()}}}
REVISION_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["revisions"],
                   "properties": {"revisions": {"type": "array", "items": {
                       **claim_schema(), "required": ["claim", "action", *claim_schema()["required"]],
                       "properties": {"claim": {"type": "integer"},
                                      "action": {"type": "string", "enum": ["revise", "withdraw"]},
                                      **claim_schema()["properties"]}}}}}

PROMPT = """You are extracting clinical evidence for a cancer variant knowledge base from the paper below.

List every clinical evidence claim that this paper itself reports from its own results (not results it only \
cites from other work), of these kinds:
- predicts_sensitivity_in: a gene variant or alteration predicts response or sensitivity to a therapy in a disease;
- predicts_resistance_in: it predicts resistance or no response to a therapy in a disease;
- poor_outcome_in / better_outcome_in: it is associated with worse or better outcome (survival, progression) in a \
disease;
- diagnostic_of: it helps diagnose or classify a disease;
- predisposes_to: a germline variant predisposes to a disease.

For each claim:
- statement.subject: the gene, as its HGNC identifier ("HGNC:" and the number) and approved symbol as label, \
type "gene";
- statement.predicate: one of the kinds above;
- statement.object: the disease, as its Disease Ontology identifier ("DOID:" and the number) and the term's name \
as label, type "disease";
- variant: the variant or alteration as the paper names it (for example "V600E", "exon 19 deletion", \
"amplification", "overexpression"), or "" if the claim is about the gene as a whole;
- therapies: the therapies of a predictive claim, as the paper names them; [] for other kinds;
- evidence: one to three sentences of the paper that state the result, each copied exactly as it appears \
(text) with the id of its paragraph, the text in square brackets (locator); direction "supports", or \
"contradicts" for a sentence that reports evidence against the claim.

Make one claim per gene, variant, kind and disease. If the paper reports no such claim, return an empty list. Do \
not use tools, files or the web. Reply with one JSON object matching the required schema and nothing else.

<paper pmid="{pmid}">
Title: {title}
{body}
</paper>"""
REVISION = """{prompt}

You extracted claims from this paper. A validator checked each one against the paper's text, the HGNC gene \
symbols and the Disease Ontology release, and did not accept the claims below:

{pending}

For each claim listed, return a revision with its number (claim): action "revise" with the corrected claim, or \
"withdraw" if the paper does not report it as stated. The claims not listed were accepted and stay as they are."""


def paragraph_id(locator: str) -> str:
    """The paragraph id in a locator. Models copy it as shown, "[p12]", or bare; the pilot's locators all named real
    paragraphs once the brackets were removed, and with them the grounder checks each quote at its paragraph."""
    return locator.strip().strip("#[]").strip()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class Case:
    """The pinned corpus, the references the grounders and the scorer read, and the validator."""

    def __init__(self) -> None:
        pipeline = load_module("civic_literature_pipeline", REPO / "examples" / "civic_literature" / "pipeline.py")
        self.corpus = pipeline.Corpus(SOURCES)
        self.manifest = self.corpus.manifest
        self.tasks = {t["task_id"]: t for t in load_jsonl(SOURCES / "tasks.jsonl")}
        self.papers: dict[str, list[list[str]]] = json.loads(gzip.decompress((SOURCES / "papers.json.gz").read_bytes()))
        self.doid = Ontology.from_obo(self.corpus.store.get(self.manifest["disease_ontology"]["sha256"]) or b"")
        hgnc = self.manifest["hgnc"]
        store = SnapshotStore.from_directory(REPO / hgnc["snapshot_dir"])
        self.genes = Genes.from_hgnc(store.get(hgnc["sha256"]) or b"", hgnc["retrieved"])
        self.civic = self.corpus.evidence
        self.validator = RecordValidator(profile=PROFILE, grounders=[
            SourceBytesGrounder(self.corpus.store), self.corpus.grounder(), GeneGrounder(self.genes),
            OntologyGrounder([self.doid], roots={"disease": ["DOID:4"]})])

    def body(self, pmid: str) -> str:
        # Paragraphs carry their ids; titles are headings without one (the literature pilot showed models citing a
        # heading's id for the paragraph beneath it).
        return "\n".join(f"[{pid}] {text}" if kind == "p" else f"## {text}" for pid, kind, text in self.papers[pmid])

    def paragraph(self, pmid: str, locator: str, quote: str) -> str:
        anchor = paragraph_id(locator)
        texts = [t for pid, kind, t in self.papers[pmid] if kind == "p" and pid == anchor]
        texts = texts or [t for _, kind, t in self.papers[pmid] if kind == "p" and quote_in(quote, t)]
        return texts[0] if texts else ""


def prompt(case: Case, task: dict) -> str:
    return PROMPT.format(pmid=task["pmid"], title=task["title"], body=case.body(task["pmid"]))


def _strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def check_claim(claim: Any) -> dict:
    statement = claim.get("statement") if isinstance(claim, dict) else None
    if (not isinstance(statement, dict) or set(claim) != {"statement", "variant", "therapies", "evidence"}
            or set(statement) != {"subject", "predicate", "object"} or statement["predicate"] not in KINDS
            or not isinstance(claim["variant"], str) or not _strings(claim["therapies"])
            or not isinstance(claim["evidence"], list)):
        raise ValueError("invalid claim")
    for part, kind in (("subject", "gene"), ("object", "disease")):
        entity = statement[part]
        if not isinstance(entity, dict) or set(entity) != {"id", "label", "type"} or entity["type"] != kind \
                or not all(isinstance(entity[k], str) for k in ("id", "label")):
            raise ValueError(f"invalid {part}")
    for item in claim["evidence"]:
        if not isinstance(item, dict) or set(item) != {"locator", "text", "direction"} \
                or item["direction"] not in ("supports", "contradicts") \
                or not all(isinstance(item[k], str) for k in ("locator", "text")):
            raise ValueError("invalid evidence")
    return claim


def check_answer(answer: Any) -> dict:
    if not isinstance(answer, dict) or set(answer) != {"claims"} or not isinstance(answer["claims"], list):
        raise ValueError("invalid answer")
    for claim in answer["claims"]:
        check_claim(claim)
    return answer


def check_revision(answer: Any) -> dict:
    if not isinstance(answer, dict) or set(answer) != {"revisions"} or not isinstance(answer["revisions"], list):
        raise ValueError("invalid revision")
    for rev in answer["revisions"]:
        if not isinstance(rev, dict) or not isinstance(rev.get("claim"), int) or rev.get("action") not in ("revise", "withdraw"):
            raise ValueError("invalid revision")
        check_claim({k: rev[k] for k in ("statement", "variant", "therapies", "evidence") if k in rev})
    return answer


def draft(case: Case, task: dict, claim: dict, ident: str) -> dict:
    """The claim as a bioevidence draft: the model's statement and evidence, the pinned paper as the source."""
    entry = case.corpus.catalog["works"][f"pmid:{task['pmid']}"]
    return {
        "id": ident, "profile": "civic-extraction", "uses": ["research_summary"],
        "statement": {**copy.deepcopy(claim["statement"]), "scope": list(SCOPE)},
        "sources": [{"id": "paper", "title": task["title"], "type": "publication", "uri": f"pmid:{task['pmid']}",
                     "version": "PMC JATS", "retrieved_at": entry["retrieved_at"],
                     "sha256": entry["fulltext_sha256"]}],
        "evidence": [{"source": "paper", "locator": "#" + paragraph_id(item["locator"]), "text": item["text"],
                      "type": "publication_result", "method": "llm_extraction", "scope": list(SCOPE),
                      "direction": item["direction"]} for item in claim["evidence"]],
    }


def build(case: Case, task: dict, claim: dict, ident: str) -> tuple[dict | None, str | None]:
    try:
        return case.corpus.pin(build_record(draft(case, task, claim, ident))), None
    except (ValueError, KeyError, TypeError) as exc:
        return None, str(exc)[:300]


def evaluate(case: Case, task: dict, claim: dict, ident: str, previous: dict | None, verified: set[str]):
    """(attempt summary, record or None, verified evidence ids, reasons to feed back) for one version of a claim."""
    record, error = build(case, task, claim, ident)
    if record is None:
        return ({"claim": claim, "status": "not_built", "error": error, "codes": [], "findings": [],
                 "to_expert": False}, None, set(), [f"the claim could not be built into a record: {error}"])
    if previous is not None:
        record = feedback.carry(previous, verified, record)
    report = case.validator.validate(record)
    sound = not {f["rule_id"] for f in report["findings"]} & {"SCHEMA", "RECORD_INTEGRITY"}
    return ({"claim": claim, "status": report["overall_status"], "error": None,
             "codes": sorted({f["rule_id"] for f in report["findings"]}), "to_expert": feedback.to_expert(report),
             "findings": [{"rule_id": f["rule_id"], "where": feedback.where(record, f["field_path"]),
                           "message": f["message"]} for f in report["findings"]],
             "evidence": len(record["evidence_items"])},
            record, feedback.verified_items(case.validator, record) if sound else set(),
            feedback.reasons(record, report) or ["not admitted"])


# A CLI whose account is out of quota answers every call at once with this; the pilot recorded 20 such "episodes".
LIMIT = re.compile(r"hit your (?:session |usage |weekly )?limit|usage limit|rate[- ]limit|quota", re.I)


class QuotaExceeded(RuntimeError):
    """The model's account is out of quota: stop that model and leave its episodes to a later run."""


def slots_for(keys: list[str], workers: int) -> dict[str, threading.Semaphore]:
    claude = threading.Semaphore(1)  # every Claude model draws on the operator's one Claude quota
    return {k: claude if run_models.MODELS[k]["cli"] == "claude" else threading.Semaphore(workers) for k in keys}


def call(key: str, text: str, schema: dict, check) -> tuple[dict | None, dict]:
    started, answer, error, tools = time.monotonic(), None, None, []
    for _ in range(2):  # one retry on an invalid answer or a tool call of the CLI's own
        try:
            answer, tools = agent_loop.call_model(key, text, timeout=900, schema=schema)
            answer = check(answer)
            if not tools:
                break
        except (ValueError, KeyError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            answer, error = None, f"{type(exc).__name__}: {exc}"[:300]
            if LIMIT.search(error):
                raise QuotaExceeded(f"{key}: {error}") from None
    return answer, {"error": error if answer is None else None, "cli_tools": tools,
                    "seconds": round(time.monotonic() - started, 1)}


def pending_text(states: list[dict], reasons: dict[int, list[str]]) -> str:
    blocks = []
    for n, lines in reasons.items():
        shown = json.dumps(states[n]["claim"], ensure_ascii=False)
        blocks.append(f"Claim {n}: {shown}\nNot accepted because:\n" + "\n".join(f"- {r}" for r in lines))
    return "\n\n".join(blocks)


def episode(key: str, task: dict, case: Case) -> dict:
    calls: list[dict] = []
    answer, meta = call(key, prompt(case, task), SCHEMA, check_answer)
    calls.append({"kind": "extract", "answer": answer, **meta})
    claims: list[dict] = []
    if answer is None:
        return {"model": key, "task_id": task["task_id"], "calls": calls, "claims": claims,
                "finished_at": dt.datetime.now(dt.UTC).isoformat()}
    states = [{"claim": c, "attempts": [], "record": None, "verified": set(), "done": False, "withdrawn": False}
              for c in answer["claims"]]
    for round_ in range(ROUNDS):
        reasons: dict[int, list[str]] = {}
        for n, state in enumerate(states):
            if state["done"]:
                continue
            ident = f"bioev:x-{task['task_id']}-{key}-{n}"
            summary, record, verified, why = evaluate(case, task, state["claim"], ident, state["record"],
                                                      state["verified"])
            state["attempts"].append(summary)
            if summary["status"] == "admitted" or summary["to_expert"]:
                state["done"] = True
                continue
            if record is not None:
                state["record"], state["verified"] = record, verified
            reasons[n] = why
        if not reasons or round_ == ROUNDS - 1:
            break
        revision, meta = call(key, REVISION.format(prompt=prompt(case, task), pending=pending_text(states, reasons)),
                              REVISION_SCHEMA, check_revision)
        calls.append({"kind": "revise", "answer": revision, "feedback": {str(n): r for n, r in reasons.items()}, **meta})
        if revision is None:
            break
        revised = set()
        for rev in revision["revisions"]:
            n = rev["claim"]
            if n not in reasons or n in revised:
                continue
            revised.add(n)
            if rev["action"] == "withdraw":
                states[n].update(done=True, withdrawn=True)
            else:
                states[n]["claim"] = {k: rev[k] for k in ("statement", "variant", "therapies", "evidence")}
        for n in set(reasons) - revised:  # left as it was: nothing more to try
            states[n]["done"] = True
    claims = [{"attempts": s["attempts"], "withdrawn": s["withdrawn"]} for s in states]
    return {"model": key, "task_id": task["task_id"], "calls": calls, "claims": claims,
            "finished_at": dt.datetime.now(dt.UTC).isoformat()}


def run(output: Path, split: str, models: list[str], workers: int, limit: int | None) -> int:
    case = Case()
    tasks = [t for t in case.tasks.values() if t["split"] == split][:limit]
    Path("C:/t/agent-work").mkdir(parents=True, exist_ok=True)
    jobs = [(key, task, output / "episodes" / key / f"{task['task_id']}.json") for task in tasks for key in models]
    jobs = [job for job in jobs if not job[2].exists()]
    print(f"{len(jobs)} episode(s) to run", flush=True)
    slots, stopped = slots_for(models, workers), set()

    def work(job):
        key, task, path = job
        with slots[key]:
            if key in stopped:
                return None
            try:
                result = episode(key, task, case)
            except QuotaExceeded as exc:
                stopped.add(key)
                print(f"stopping {key}, out of quota: {exc}", flush=True)
                return None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers * len(models)) as pool:
        for n, result in enumerate(pool.map(work, jobs), start=1):
            if result is None:
                continue
            finals = collections.Counter(final_state(c) for c in result["claims"])
            errors = sum(c["error"] is not None for c in result["calls"])
            print(f"[{n}/{len(jobs)}] {result['model']} {result['task_id']}: {len(result['calls'])} call(s), "
                  f"{len(result['claims'])} claim(s) {dict(finals)}, {errors} error(s)", flush=True)
    if stopped:
        print(f"not finished, out of quota: {', '.join(sorted(stopped))}; run again later to resume", flush=True)
    return 1 if stopped else 0


def final_state(claim: dict) -> str:
    last = claim["attempts"][-1] if claim["attempts"] else None
    if claim["withdrawn"]:
        return "withdrawn"
    if last and last["status"] == "admitted":
        return "admitted"
    return "to a person" if last and last["to_expert"] else "not fixed"


# Model review: an independent reading of each admitted claim's quotes.

def review_unit(case: Case, task: dict, claim: dict) -> dict:
    statement = claim["statement"]
    kind, significance = KINDS[statement["predicate"]]
    quotes = [{"text": e["text"], "context": case.paragraph(task["pmid"], e["locator"], e["text"])}
              for e in claim["evidence"]]
    return {"claim": {"molecular_profile": f"{statement['subject']['label']} {claim['variant']}".strip(),
                      "disease": statement["object"]["label"], "evidence_type": kind, "significance": significance,
                      "therapies": ", ".join(claim["therapies"])},
            "title": task["title"], "quotes": quotes}


def reviewer_for(key: str) -> str:
    return REVIEWER[run_models.MODELS[key]["cli"].replace("codex", "gpt").replace("agy", "gemini")]


def review(output: Path, workers: int, models: list[str] | None = None) -> int:
    """Review the admitted claims of every finished episode (of `models`, the extractors, if given)."""
    case = Case()
    jobs = []
    for path in sorted((output / "episodes").glob("*/*.json")):
        if models and path.parent.name not in models:
            continue
        row = json.loads(path.read_text(encoding="utf-8"))
        target = output / "reviews" / row["model"] / path.name
        if target.exists():
            continue
        admitted = {n: c["attempts"][-1]["claim"] for n, c in enumerate(row["claims"]) if final_state(c) == "admitted"}
        jobs.append((row, admitted, target))
    print(f"{len(jobs)} episode(s) to review", flush=True)
    reviewers = sorted({reviewer_for(row["model"]) for row, _, _ in jobs})
    slots, stopped = slots_for(reviewers, workers), set()

    def work(job):
        row, admitted, target = job
        key, task = reviewer_for(row["model"]), case.tasks[row["task_id"]]
        readings = {}
        for n, claim in admitted.items():
            with slots[key]:
                if key in stopped:
                    return row["model"], row["task_id"], None
                try:
                    reading, meta = call(key, review_suite.prompt(review_unit(case, task, claim)), review_suite.SCHEMA,
                                         review_suite.validate)
                except QuotaExceeded as exc:
                    stopped.add(key)
                    print(f"stopping {key}, out of quota: {exc}", flush=True)
                    return row["model"], row["task_id"], None
            readings[str(n)] = {"reviewer": key, "reading": reading, **meta}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"model": row["model"], "task_id": row["task_id"], "reviews": readings},
                                     indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return row["model"], row["task_id"], len(readings)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers * len(reviewers))) as pool:
        for n, (model, task_id, count) in enumerate(pool.map(work, jobs), start=1):
            if count is not None:
                print(f"[{n}/{len(jobs)}] {model} {task_id}: {count} review(s)", flush=True)
    return 1 if stopped else 0


def collect(output: Path, results: Path) -> None:
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((output / "episodes").glob("*/*.json"))]
    reviews = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((output / "reviews").glob("*/*.json"))]
    for row in rows:
        row.pop("finished_at", None)
    results.mkdir(parents=True, exist_ok=True)
    score_claims.write_jsonl(results / "episodes.jsonl", rows)
    score_claims.write_jsonl(results / "reviews.jsonl", reviews)
    score(results)


# Scoring, independent of the grounders: direct lookups in the pinned releases and the paper.

def problems(case: Case, task: dict, claim: dict) -> list[str]:
    found = []
    subject, disease = claim["statement"]["subject"], claim["statement"]["object"]
    row = case.genes.by_id.get(subject["id"].strip())
    if row is None:
        found.append("unknown_gene_id")
    elif row["symbol"] != subject["label"].strip():
        found.append("gene_label_mismatch")
    term = case.doid.terms.get(disease["id"].strip())
    if term is None:
        found.append("unknown_disease_id")
    elif term.obsolete:
        found.append("obsolete_disease_id")
    elif "DOID:4" not in case.doid.ancestors(term.id) and term.id != "DOID:4":
        found.append("not_a_disease")
    elif _label_key(disease["label"]) not in {_label_key(t) for t in [term.name, *term.synonyms]}:
        found.append("disease_label_mismatch")
    paragraphs = [normalize(t) for _, kind, t in case.papers[task["pmid"]] if kind == "p"]
    if not claim["evidence"]:
        found.append("no_evidence")
    elif any(not any(quote_in(normalize(e["text"]), p) for p in paragraphs) for e in claim["evidence"]):
        found.append("quote_not_in_paper")
    return found


def civic_genes(case: Case, profile: str) -> set[str]:
    words = re.split(r"\s+(?:AND|OR)\s+|\s+", profile)
    return {w for w in words if w in case.genes.approved}


def compatible(case: Case, a: str, b: str) -> bool:
    return a == b or a in case.doid.ancestors(b) or b in case.doid.ancestors(a)


def matches(case: Case, claim: dict, item: dict, kind: bool = False) -> bool:
    statement = claim["statement"]
    same = (statement["subject"]["label"].strip() in civic_genes(case, item["molecular_profile"])
            and compatible(case, statement["object"]["id"].strip(), f"DOID:{item['doid']}"))
    return same and (not kind or KINDS.get(statement["predicate"]) == (item["evidence_type"], item["significance"]))


def first_stage(attempt: dict) -> str:
    """What the checks found in a claim's first version, most decisive first."""
    if attempt["status"] == "not_built":
        return "provenance"
    if attempt["status"] == "admitted":
        return "passed"
    codes = set(attempt["codes"])
    fixable = codes - feedback.EXPERT
    if fixable & {"SCHEMA", "RECORD_INTEGRITY", "BEV001", "BEV002", "BEV003", "BEV005", "BEV006", "BEV007"}:
        return "rules"
    if any(f["rule_id"] in ("BEV016", "BEV017", "BEV023", "BEV024") and f["where"].startswith(("subject", "object"))
           for f in attempt["findings"]):
        return "identifier"
    if fixable:
        return "quote"
    return "conflict, to a person" if attempt["to_expert"] else "other"


def score(results: Path) -> dict:
    case = Case()
    rows = load_jsonl(results / "episodes.jsonl")
    reviews = {(r["model"], r["task_id"]): r["reviews"] for r in load_jsonl(results / "reviews.jsonl")} \
        if (results / "reviews.jsonl").exists() else {}
    models = [m for m in score_claims.MODEL_NAMES if any(r["model"] == m for r in rows)]
    rate = score_claims.rate
    items = [i for i in case.civic if i["evidence_type"] in CIVIC_TYPES]
    split = case.tasks[rows[0]["task_id"]]["split"] if rows else "pilot"

    def metrics(mine: list[dict]) -> dict:
        tasks = {r["task_id"] for r in mine}
        claims, first, gate, admitted, reviewed = [], [], [], [], []
        stages, finals, verdicts = collections.Counter(), collections.Counter(), collections.Counter()
        readings = collections.Counter()  # what the reviewer says about accepted claims' evidence
        for r in mine:
            task = case.tasks[r["task_id"]]
            for n, c in enumerate(r["claims"]):
                claims.append((task, c))
                if c["attempts"]:
                    first.append((task, c["attempts"][0]["claim"]))
                    stages[first_stage(c["attempts"][0])] += 1
                    if c["attempts"][0]["status"] == "admitted":  # what a gate without feedback would admit
                        gate.append((task, c["attempts"][0]["claim"]))
                state = final_state(c)
                finals[state] += 1
                if state == "admitted":
                    claim = c["attempts"][-1]["claim"]
                    admitted.append((task, claim))
                    review_ = reviews.get((r["model"], r["task_id"]), {}).get(str(n))
                    reading = review_ and review_["reading"]
                    verdict = "no review" if not reading else "accepted" if reading["verdict"] == "supports" else "deferred"
                    verdicts[verdict] += 1
                    if verdict == "accepted":
                        reviewed.append((task, claim))
                        readings[f"evidence from {reading['evidence_from']}"] += 1
                        readings[reading["certainty"]] += 1
        with_problem = sum(bool(problems(case, t, c)) for t, c in first)
        admitted_problem = sum(bool(problems(case, t, c)) for t, c in admitted)
        mine_items = [i for i in items if any(case.tasks[t]["pmid"] == i["citation_id"] for t in tasks)]

        def recall(pool: list[tuple[dict, dict]], kind: bool = False) -> dict:
            hit = sum(any(t["pmid"] == i["citation_id"] and matches(case, c, i, kind) for t, c in pool) for i in mine_items)
            return rate(hit, len(mine_items))

        def beyond_civic(pool: list[tuple[dict, dict]]) -> int:
            return sum(not any(t["pmid"] == i["citation_id"] and matches(case, c, i) for i in items) for t, c in pool)

        beyond = beyond_civic(admitted)
        kinds = collections.Counter(problem for t, c in first for problem in problems(case, t, c))
        return {
            "papers": len(tasks), "episodes": len(mine), "claims": len(claims),
            "failed_extractions": sum(not r["calls"] or r["calls"][0]["answer"] is None for r in mine),
            "first_stage": dict(sorted(stages.items())), "final": dict(sorted(finals.items())),
            "model_review": dict(sorted(verdicts.items())), "accepted_evidence": dict(sorted(readings.items())),
            "first_with_identifier_or_quote_error": rate(with_problem, len(first)),
            "admitted_with_identifier_or_quote_error": rate(admitted_problem, len(admitted)),
            "first_error_kinds": dict(sorted(kinds.items())),
            "civic_items": len(mine_items), "admitted_first_version": rate(len(gate), len(first)),
            "admitted_after_feedback": rate(len(admitted), len(first)),
            "recall_first_answers": recall(first), "recall_gate": recall(gate), "recall_admitted": recall(admitted),
            "recall_admitted_same_kind": recall(admitted, kind=True), "recall_after_model_review": recall(reviewed),
            "admitted_beyond_civic": rate(beyond, len(admitted)),
            "accepted_beyond_civic": rate(beyond_civic(reviewed), len(reviewed)),
        }

    summary = {"benchmark": "civic-extraction-v1", "split": split, "episodes": len(rows),
               "results": {m: metrics([r for r in rows if r["model"] == m]) for m in models},
               "pooled": metrics(rows), "calls": sum(len(r["calls"]) for r in rows),
               "failed_calls": sum(c["error"] is not None for r in rows for c in r["calls"]),
               "codes": dict(sorted(collections.Counter(code for r in rows for c in r["claims"]
                                                        for a in c["attempts"] for code in a["codes"]).items())),
               "episodes_sha256": hashlib.sha256((results / "episodes.jsonl").read_bytes().replace(b"\r\n", b"\n")).hexdigest()}
    (results / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8",
                                          newline="\n")
    (results / "summary.md").write_text(render(summary), encoding="utf-8", newline="\n")
    expert_sample(case, rows, results / "expert_sample")
    print(render(summary))
    return summary


def expert_sample(case: Case, rows: list[dict], out: Path) -> None:
    """A seeded sample for expert labelling with the error taxonomy, in three groups of up to PER_GROUP claims:
    first versions the chain stopped, admitted claims with no CIViC counterpart, and admitted claims that match
    CIViC. The packet and sheet show neither the model, the group nor the stage; the key holds them."""
    items = [i for i in case.civic if i["evidence_type"] in CIVIC_TYPES]
    groups: dict[str, list[tuple[str, dict, dict]]] = {"stopped by the chain": [], "admitted, beyond CIViC": [],
                                                       "admitted, matches CIViC": []}
    for r in rows:
        task = case.tasks[r["task_id"]]
        for n, c in enumerate(r["claims"]):
            if not c["attempts"]:
                continue
            ident = f"{r['model']}|{r['task_id']}|{n}"
            if first_stage(c["attempts"][0]) in ("provenance", "rules", "identifier", "quote"):
                groups["stopped by the chain"].append((ident, task, c["attempts"][0]["claim"]))
            if final_state(c) == "admitted":
                claim = c["attempts"][-1]["claim"]
                hit = any(i["citation_id"] == task["pmid"] and matches(case, claim, i) for i in items)
                groups["admitted, matches CIViC" if hit else "admitted, beyond CIViC"].append((ident, task, claim))
    rng = random.Random(SAMPLE_SEED)
    chosen = [(name, *entry) for name, pool in groups.items()
              for entry in rng.sample(sorted(pool, key=lambda e: e[0]), min(PER_GROUP, len(pool)))]
    rng.shuffle(chosen)
    out.mkdir(parents=True, exist_ok=True)
    key, sheet = [], []
    for number, (group, ident, task, claim) in enumerate(chosen, start=1):
        sample_id = f"s{number:03d}"
        model, task_id, index = ident.split("|")
        key.append({"sample_id": sample_id, "group": group, "model": model, "task_id": task_id, "claim": int(index),
                    "problems": problems(case, task, claim)})
        sheet.append({**dict.fromkeys(LABEL_COLUMNS, ""), "sample_id": sample_id, "pmid": task["pmid"]})
    score_claims.write_jsonl(out / "key.jsonl", key)
    with (out / "labels.csv").open("w", encoding="utf-8", newline="") as handle:
        handle.write(",".join(LABEL_COLUMNS) + "\n")
        handle.writelines(",".join(row[c] for c in LABEL_COLUMNS) + "\n" for row in sheet)
    (out / "packet.md").write_text(packet(case, chosen), encoding="utf-8", newline="\n")


def packet(case: Case, chosen: list[tuple[str, str, dict, dict]]) -> str:
    import yaml
    taxonomy = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    codes = [m for m in taxonomy["failure_modes"] if m["stage"] in ("source", "extraction", "provenance", "aggregation")]
    lines = ["# Expert sample: claims extracted by models", "",
             "For each claim, read the quoted sentences in their paragraphs (and the paper, linked, if you need more) and "
             "fill one row of `labels.csv`:", "",
             "- `claim_correct`: `yes` if the paper reports this claim as stated (gene, kind, disease, variant and "
             "therapies), `no` if not, `unsure` if you cannot tell.",
             "- `error_codes`: for `no`, every code below that applies, separated by `;`; empty for `yes`.",
             "- `rationale`, `reviewer_id`, `reviewer_qualification`, `annotated_at` (ISO 8601) and `minutes_spent`.", "",
             "Claims are in random order. Which model made a claim, and whether the validator accepted it, are withheld.",
             "", "| Code | Failure | Definition |", "|---|---|---|"]
    lines += [f"| {m['id']} | {m['name']} | {m['definition']} |" for m in codes]
    words = {"predicts_sensitivity_in": "predicts sensitivity or response, in",
             "predicts_resistance_in": "predicts resistance, in", "poor_outcome_in": "is associated with poor outcome in",
             "better_outcome_in": "is associated with better outcome in", "diagnostic_of": "is diagnostic of",
             "predisposes_to": "predisposes to"}
    for number, (_, _, task, claim) in enumerate(chosen, start=1):
        statement = claim["statement"]
        subject = f"{statement['subject']['label']} ({statement['subject']['id']})"
        variant = f" {claim['variant']}" if claim["variant"] else ""
        therapies = f"; therapies: {', '.join(claim['therapies'])}" if claim["therapies"] else ""
        lines += ["", f"## s{number:03d} · [PMID {task['pmid']}](https://pubmed.ncbi.nlm.nih.gov/{task['pmid']}/)", "",
                  f"**Claim:** {subject}{variant} {words.get(statement['predicate'], statement['predicate'])} "
                  f"{statement['object']['label']} ({statement['object']['id']}){therapies}", ""]
        for item in claim["evidence"] or [{"locator": "", "text": "(no quote given)", "direction": "supports"}]:
            context = case.paragraph(task["pmid"], item["locator"], item["text"]) if item["locator"] else ""
            stance = "" if item["direction"] == "supports" else " (cited as evidence against the claim)"
            lines.append(f"- Quote at `{item['locator'] or '–'}`{stance}: \"{item['text']}\"")
            if context and normalize(context) != normalize(item["text"]):
                lines.append(f"  - Paragraph: {context}")
    return "\n".join(lines) + "\n"


def render(summary: dict) -> str:
    f = score_claims.fraction
    lines = [f"# Real AI extraction ({summary['split']} split, {summary['episodes']} episodes)", "",
             "Claims: what the model extracted. Gate: admitted as first extracted. Loop: admitted after feedback.", "",
             "| Model | Claims | First version: identifier or quote error | Admitted, gate | Admitted, loop | "
             "Admitted with an error | CIViC items found: model alone | Gate | Loop | Loop, same kind | "
             "After model review |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    blocks = [(score_claims.MODEL_NAMES[m], v) for m, v in summary["results"].items()] + [("All models", summary["pooled"])]
    for name, m in blocks:
        lines.append(f"| {name} | {m['claims']} | {f(m['first_with_identifier_or_quote_error'])} | "
                     f"{f(m['admitted_first_version'])} | {f(m['admitted_after_feedback'])} | "
                     f"{f(m['admitted_with_identifier_or_quote_error'])} | {f(m['recall_first_answers'])} | "
                     f"{f(m['recall_gate'])} | {f(m['recall_admitted'])} | {f(m['recall_admitted_same_kind'])} | "
                     f"{f(m['recall_after_model_review'])} |")
    p = summary["pooled"]

    def listed(counts: dict) -> str:
        return ", ".join(f"{k} {n}" for k, n in counts.items()) or "none"

    lines += ["", f"Funnel (all models). First version of each claim: {listed(p['first_stage'])}. Final: "
              f"{listed(p['final'])}. Model review of the admitted: {listed(p['model_review'])}; the accepted, as "
              f"the reviewer reads their evidence: {listed(p['accepted_evidence'])}. Human review: not yet run. "
              f"First-version error kinds: {listed(p['first_error_kinds'])}. Admitted claims with no CIViC "
              f"counterpart (same gene, compatible disease): {f(p['admitted_beyond_civic'])}.", "",
              f"Calls: {summary['calls']}, failed {summary['failed_calls']}. Finding codes over all versions: "
              f"{listed(summary['codes'])}.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    steps = parser.add_subparsers(dest="step", required=True)
    r = steps.add_parser("run")
    r.add_argument("--output", type=Path, required=True)
    r.add_argument("--split", choices=["pilot", "test"], default="pilot")
    r.add_argument("--models", nargs="+", choices=list(run_models.MODELS), default=list(run_models.MODELS))
    r.add_argument("--workers", type=int, default=2)
    r.add_argument("--limit", type=int)
    v = steps.add_parser("review")
    v.add_argument("--output", type=Path, required=True)
    v.add_argument("--workers", type=int, default=2)
    v.add_argument("--models", nargs="+", choices=list(run_models.MODELS), help="Extractors whose claims to review")
    c = steps.add_parser("collect")
    c.add_argument("--output", type=Path, required=True)
    c.add_argument("--results", type=Path, required=True)
    s = steps.add_parser("score")
    s.add_argument("--results", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.step == "review":
        return review(args.output, args.workers, args.models)
    if args.step == "collect":
        collect(args.output, args.results)
        return 0
    if args.step == "score":
        score(args.results)
        return 0
    return run(args.output, args.split, args.models, args.workers, args.limit)


if __name__ == "__main__":
    sys.exit(main())
