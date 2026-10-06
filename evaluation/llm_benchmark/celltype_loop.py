"""Single-cell cell-type annotation by six models, alone and in bioevidence's feedback loop.

    uv run --frozen python evaluation/llm_benchmark/celltype_loop.py run --split pilot --output C:/t/celltype-pilot
    uv run --frozen python evaluation/llm_benchmark/celltype_loop.py collect --output C:/t/celltype-pilot \
        --results evaluation/llm_benchmark/results/celltype-pilot
    uv run --frozen python evaluation/llm_benchmark/celltype_loop.py score --results evaluation/llm_benchmark/results/celltype-pilot

Each task shows a model the top 20 marker genes of one cluster of a real single-cell dataset (the cell types
its authors annotated, from `examples/singlecell_celltype`) and asks for the cluster's Cell Ontology term and
the marker genes that support or argue against it. The answer is built into an evidence record and validated
with five grounders: the pinned marker table (a cited marker must be one of this cluster's), the Cell Ontology
release (the term exists, is current, is a cell type and matches its label), HGNC (approved symbols), the
source bytes, and HuBMAP ASCT+B (a supporting marker that the reference assigns only to unrelated cell
types sends the record to an expert). The episode is `bioevidence_validator.feedback.revise`: fixable
findings go back to the model, at most three answers; conflicts go to an expert unchanged.

Two protocols, each fixed before the split it was run on. Protocol 1 (the pilot) asked for markers that argue
against the answer and cross-checked supporting markers with ASCT+B. Protocol 2 (the held-out test split), from
what the pilot showed, asks for contradicting markers only when some clearly point to another cell type (a mixed
cluster, doublets), and leaves out the ASCT+B cross-check, whose biomarker lists are not specificity statements.
Protocol 3 (the external split, six datasets from other studies) keeps protocol 2 and adds the Cell Ontology
definition check (`bioevidence_validator.definitions`): a claimed term whose defining markers the cluster's
measurements contradict (a CD8 T cell in which CD4 is detected in most cells) goes back to the model with the
measurement, as a finding to review (BEV026). Its thresholds were set on the first six datasets.

One run gives three views: the model alone (its first answer as given), behind a bioevidence gate (its first
answer, validated) and in the feedback loop (its last answer, validated). Scoring is independent of the
grounders: each answer is compared with the authors' term using the ontology (exact, coarser, finer or
wrong), and its identifiers and markers are looked up directly.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import datetime as dt
import hashlib
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from bioevidence_validator import feedback
from bioevidence_validator.crosscheck import ReferenceGrounder
from bioevidence_validator.definitions import DefinitionGrounder, MarkerDefinitions
from bioevidence_validator.engine import RecordValidator
from bioevidence_validator.grounding import SnapshotStore, SourceBytesGrounder
from bioevidence_validator.identifiers import GeneGrounder, Genes, Ontology, OntologyGrounder, _label_key
from bioevidence_validator.tables import TableGrounder, parse_table

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import agent_loop  # noqa: E402
import run_models  # noqa: E402
import score_claims  # noqa: E402

CASE = ROOT.parents[1] / "examples" / "singlecell_celltype"
SOURCES = CASE / "sources"
ROUNDS = 3
DECISIONS, STANCES = ["annotate", "uncertain"], ["supports", "contradicts"]
FIELDS = ["decision", "cell_type_id", "cell_type_label", "markers", "rationale"]
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": FIELDS,
    "properties": {
        "decision": {"type": "string", "enum": DECISIONS},
        "cell_type_id": {"type": "string"}, "cell_type_label": {"type": "string"},
        "markers": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                               "required": ["gene", "stance"],
                                               "properties": {"gene": {"type": "string"},
                                                              "stance": {"type": "string", "enum": STANCES}}}},
        "rationale": {"type": "string"},
    },
}
PROMPT_V1 = """This cluster comes from a single-cell RNA-seq dataset of {species} {tissue} ({assay}). Its top marker \
genes, ranked by log fold change against all other cells of the dataset (logfc: difference of mean log-normalised \
expression; pct_in and pct_out: fraction of cells expressing the gene inside and outside the cluster):

gene\tlogfc\tpct_in\tpct_out
{table}

Which cell type is this cluster? Give its Cell Ontology term (the CL identifier and the term's name) and the \
marker genes of this cluster that support it, and any that argue against it. If the markers do not identify a \
cell type, set "decision" to "uncertain". Answer from what you know: do not run commands, search the web or read \
files."""
PROMPT = """This cluster comes from a single-cell RNA-seq dataset of {species} {tissue} ({assay}). Its top marker \
genes, ranked by log fold change against all other cells of the dataset (logfc: difference of mean log-normalised \
expression; pct_in and pct_out: fraction of cells expressing the gene inside and outside the cluster):

gene\tlogfc\tpct_in\tpct_out
{table}

Which cell type is this cluster? Give its Cell Ontology term (the CL identifier and the term's name) and the \
marker genes of this cluster that support it (stance "supports"). Only if some of its markers clearly point to a \
different cell type, for example in a mixed cluster or doublets, list those with stance "contradicts". If the \
markers do not identify a cell type, set "decision" to "uncertain". Answer from what you know: do not run \
commands, search the web or read files."""
PROMPTS = {1: PROMPT_V1, 2: PROMPT, 3: PROMPT}
REVISION = """{prompt}

Your previous answer:
{previous}

A validator checked it against the pinned Cell Ontology release, the HGNC gene symbols and this cluster's marker \
table, and did not accept it:
{reasons}

Revise your answer."""


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class Case:
    """The pinned case: tasks, snapshots, and the references the grounders and the scorer read."""

    def __init__(self) -> None:
        self.manifest = json.loads((SOURCES / "manifest.json").read_text(encoding="utf-8"))
        self.store = SnapshotStore.from_directory(SOURCES / "snapshots")
        self.ontology = Ontology.from_obo(self.store.get(self.manifest["cell_ontology"]["sha256"]) or b"")
        self.genes = Genes.from_hgnc(self.store.get(self.manifest["hgnc"]["sha256"]) or b"",
                                     self.manifest["hgnc"]["retrieved"])
        self.reference = self.store.get(self.manifest["asctb"]["sha256"]) or b""
        self.tasks = {t["task_id"]: t for t in load_jsonl(SOURCES / "tasks.jsonl")}
        self.versions = {d["markers_sha256"]: d["dataset_version_id"] for d in self.manifest["datasets"]}
        self.tables = {sha: parse_table(self.store.get(sha) or b"")[1] for sha in self.versions}
        self.panels: dict[str, dict[str, dict[str, tuple[float, float]]]] = {}
        for dataset in self.manifest["datasets"]:
            for row in parse_table(self.store.get(dataset["panel_sha256"]) or b"")[1]:
                cluster = self.panels.setdefault(dataset["name"], {}).setdefault(row["cluster"], {})
                cluster[row["gene"]] = (float(row["pct_in"]), float(row["logfc"]))

    def measure(self, record: dict) -> dict[str, tuple[float, float]] | None:
        """The definition panel of the record's cluster (`cluster:<dataset>/<cluster>`)."""
        dataset, _, cluster = record["statement"]["subject"]["id"].removeprefix("cluster:").partition("/")
        return self.panels.get(dataset, {}).get(cluster)

    def validator(self, protocol: int = 2) -> RecordValidator:
        grounders: list = [SourceBytesGrounder(self.store), TableGrounder(self.store, ["marker_gene"]),
                           OntologyGrounder([self.ontology], roots={"cell_type": ["CL:0000000"]}), GeneGrounder(self.genes)]
        if protocol == 1:
            grounders.append(ReferenceGrounder.from_table(self.reference, label="ASCT+B", evidence_key="gene",
                                                          relation="marker_of", ontology=self.ontology,
                                                          conflict="disjoint"))
        if protocol >= 3:
            grounders.append(DefinitionGrounder(MarkerDefinitions(self.ontology, self.genes), self.measure))
        return RecordValidator(profile=CASE / "profile.yaml", grounders=grounders)

    def markers(self, task: dict) -> set[str]:
        return {r["gene"] for r in self.tables[task["markers_sha256"]] if r["cluster"] == task["cluster"]}


def prompt(task: dict, protocol: int = 2) -> str:
    table = "\n".join(f"{m['gene']}\t{m['logfc']}\t{m['pct_in']}\t{m['pct_out']}" for m in task["markers"])
    return PROMPTS[protocol].format(species=task["species"], tissue=task["tissue"], assay=task["assay"], table=table)


def check_answer(answer: Any) -> dict:
    if not isinstance(answer, dict) or set(answer) != set(FIELDS) or answer["decision"] not in DECISIONS:
        raise ValueError("invalid answer")
    if not isinstance(answer["markers"], list) or not all(
            isinstance(m, dict) and set(m) == {"gene", "stance"} and isinstance(m["gene"], str) and m["stance"] in STANCES
            for m in answer["markers"]):
        raise ValueError("invalid markers")
    return answer


def gene_token(text: str) -> str:
    return text.strip().replace(";", "_").replace("=", "_") or "_"


def record(case: Case, task: dict, answer: dict) -> dict | None:
    """The answer as an evidence record, or None when the model does not annotate."""
    if answer["decision"] != "annotate" or not answer["cell_type_id"].strip():
        return None
    sha = task["markers_sha256"]
    items, lines = [], {}
    for n, marker in enumerate(answer["markers"], start=1):
        items.append({"id": f"bioev:marker-{n}", "source_artifact_id": "bioev:markers",
                      "locator": f"cluster={task['cluster']};gene={gene_token(marker['gene'])}",
                      "evidence_type": "marker_gene", "extraction_method": "llm_extraction", "scope": ["NCBITaxon:9606"]})
        lines.setdefault(marker["stance"], []).append(items[-1]["id"])
    return {
        "record_id": f"bioev:celltype-{task['task_id']}", "profile_id": "singlecell-celltype",
        "statement": {"id": f"bioev:celltype-statement-{task['task_id']}",
                      "subject": {"id": f"cluster:{task['dataset']}/{task['cluster']}",
                                  "label": f"cluster {task['cluster']} of the {task['tissue']} dataset",
                                  "entity_type": "cell_cluster"},
                      "predicate": "has_cell_type",
                      "object": {"id": answer["cell_type_id"].strip(), "label": answer["cell_type_label"].strip(),
                                 "entity_type": "cell_type"},
                      "scope": ["NCBITaxon:9606"], "statement_status": "proposed",
                      "evidence_lines": [{"id": f"bioev:line-{d}", "direction": d, "evidence_item_ids": ids}
                                         for d, ids in lines.items()]},
        "source_artifacts": [{"id": "bioev:markers", "title": f"Marker table of the {task['dataset']} dataset",
                              "source_type": "dataset_snapshot", "uri": f"urn:sha256:{sha}",
                              "version": case.versions[sha], "retrieved_at": "2026-09-30T00:00:00Z",
                              "sha256": sha, "observed_sha256": sha}],
        "evidence_items": items, "adjudications": [], "requested_uses": ["research_summary"],
    }


def episode(key: str, task: dict, case: Case, protocol: int = 2) -> dict:
    validator, calls, last = case.validator(protocol), [], {}

    def propose(reasons: list[str]) -> dict | None:
        text = prompt(task, protocol) if not reasons else REVISION.format(
            prompt=prompt(task, protocol), previous=json.dumps(last["answer"], ensure_ascii=False),
            reasons="\n".join(f"- {r}" for r in reasons))
        started, answer, error, tools = time.monotonic(), None, None, []
        for _ in range(2):  # one retry on an invalid answer or a tool call of the CLI's own
            try:
                answer, tools = agent_loop.call_model(key, text, schema=SCHEMA)
                answer = check_answer(answer)
                if not tools:
                    break
            except (ValueError, KeyError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                answer, error = None, f"{type(exc).__name__}: {exc}"[:300]
        calls.append({"answer": answer, "error": error if answer is None else None, "cli_tools": tools,
                      "feedback": reasons, "seconds": round(time.monotonic() - started, 1)})
        if answer is None:
            return None
        last["answer"] = answer
        return record(case, task, answer)

    attempts = feedback.revise(propose, validator, rounds=ROUNDS)
    return {"model": key, "task_id": task["task_id"], **({"protocol": protocol} if protocol != 1 else {}), "calls": calls,
            "attempts": [{"status": a.report["overall_status"],
                          "codes": sorted({f["rule_id"] for f in a.report["findings"]}),
                          "to_expert": feedback.to_expert(a.report),
                          "findings": [{"rule_id": f["rule_id"], "where": feedback.where(a.record, f["field_path"]),
                                        "message": f["message"]} for f in a.report["findings"]],
                          "evidence": len(a.record["evidence_items"])} for a in attempts],
            "finished_at": dt.datetime.now(dt.UTC).isoformat()}


def run(output: Path, split: str, models: list[str], workers: int, limit: int | None, protocol: int = 2) -> int:
    case = Case()
    tasks = [t for t in case.tasks.values() if t["split"] == split][:limit]
    Path("C:/t/agent-work").mkdir(parents=True, exist_ok=True)
    jobs = [(key, task, output / "episodes" / key / f"{task['task_id']}.json") for task in tasks for key in models]
    jobs = [job for job in jobs if not job[2].exists()]
    print(f"{len(jobs)} episode(s) to run", flush=True)
    # Claude models share the operator's Claude usage limit: one episode at a time.
    slots = {key: threading.Semaphore(1 if run_models.MODELS[key]["cli"] == "claude" else workers) for key in models}

    def work(job):
        key, task, path = job
        with slots[key]:
            result = episode(key, task, case, protocol)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers * len(models)) as pool:
        for n, result in enumerate(pool.map(work, jobs), start=1):
            final = result["attempts"][-1]["status"] if result["attempts"] else "no record"
            errors = sum(c["error"] is not None for c in result["calls"])
            print(f"[{n}/{len(jobs)}] {result['model']} {result['task_id']}: {len(result['calls'])} call(s), "
                  f"{len(result['attempts'])} record(s), final {final}, {errors} error(s)", flush=True)
    return 0


def collect(output: Path, results: Path) -> None:
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((output / "episodes").glob("*/*.json"))]
    for row in rows:
        row.pop("finished_at", None)
    results.mkdir(parents=True, exist_ok=True)
    score_claims.write_jsonl(results / "episodes.jsonl", rows)
    score(results)


# Scoring, independent of the grounders: direct lookups in the pinned releases and the marker table.

def outcome(case: Case, truth: str, answer: dict) -> str:
    term = case.ontology.terms.get(answer["cell_type_id"].strip())
    if term is None or term.obsolete or "CL:0000000" not in case.ontology.ancestors(term.id):
        return "invalid"
    if term.id == truth:
        return "exact"
    if term.id in case.ontology.ancestors(truth):
        return "coarser"
    if truth in case.ontology.ancestors(term.id):
        return "finer"
    return "wrong"


def problems(case: Case, task: dict, answer: dict) -> list[str]:
    found = []
    term = case.ontology.terms.get(answer["cell_type_id"].strip())
    if term is None:
        found.append("unknown_id")
    elif term.obsolete:
        found.append("obsolete_id")
    elif "CL:0000000" not in case.ontology.ancestors(term.id):
        found.append("not_a_cell_type")
    elif _label_key(answer["cell_type_label"]) not in {_label_key(t) for t in [term.name, *term.synonyms]}:
        found.append("label_mismatch")
    markers = case.markers(task)
    genes = [m["gene"].strip() for m in answer["markers"]]
    if any(g not in case.genes.approved for g in genes):
        found.append("unapproved_symbol")
    if any(g not in markers for g in genes):
        found.append("marker_not_in_data")
    if not genes:
        found.append("no_markers")
    return found


VIEWS = [("model", "Model alone (first answer)"), ("gate", "Model + bioevidence gate (first answer)"),
         ("loop", "Model + bioevidence feedback loop (last answer)")]
# Protocol 3 only: the gate as protocol 2 would have it, on the same first answers (the prompts are the same).
WITHOUT_DEFINITIONS = ("gate_without_definitions", "Model + gate without the definition check (first answer)")


def views_for(protocol: int) -> list[tuple[str, str]]:
    return VIEWS[:2] + [WITHOUT_DEFINITIONS] + VIEWS[2:] if protocol >= 3 else VIEWS


def view(row: dict, name: str) -> dict:
    """What a view delivers: an answer (or none), and whether it went to a person."""
    calls, attempts = row["calls"], row["attempts"]
    answered = [c["answer"] for c in calls if c["answer"] is not None]
    if name == "model":
        first = calls[0]["answer"] if calls else None
        return {"answer": first if first and first["decision"] == "annotate" else None, "routed": False, "expert": False}
    if not attempts:
        return {"answer": None, "routed": False, "expert": False}
    first = name in ("gate", WITHOUT_DEFINITIONS[0])
    chosen = attempts[0] if first else attempts[-1]
    index = 0 if first else len(attempts) - 1
    annotating = [a for a in answered if a["decision"] == "annotate" and a["cell_type_id"].strip()]
    if chosen["status"] == "admitted" or (name == WITHOUT_DEFINITIONS[0] and set(chosen["codes"]) == {"BEV026"}):
        return {"answer": annotating[index], "routed": False, "expert": False}
    return {"answer": None, "routed": True, "expert": chosen["to_expert"]}


def score(results: Path) -> dict:
    case = Case()
    truth = {t["task_id"]: t for t in load_jsonl(SOURCES / "truth.jsonl")}
    rows = load_jsonl(results / "episodes.jsonl")
    models = [m for m in score_claims.MODEL_NAMES if any(r["model"] == m for r in rows)]

    def metrics(mine: list[dict], name: str) -> dict:
        views = [(r, view(r, name)) for r in mine]
        delivered = [(r, v) for r, v in views if v["answer"] is not None]
        kinds = [outcome(case, truth[r["task_id"]]["term"], v["answer"]) for r, v in delivered]
        issues = [problems(case, case.tasks[r["task_id"]], v["answer"]) for r, v in delivered]
        rate = score_claims.rate
        return {"tasks": len(mine), "answered": rate(len(delivered), len(mine)),
                **{k: rate(kinds.count(k), len(mine)) for k in ("exact", "coarser", "finer", "wrong", "invalid")},
                "compatible": rate(sum(k in ("exact", "coarser", "finer") for k in kinds), len(mine)),
                "with_identifier_or_marker_error": rate(sum(bool(i) for i in issues), len(delivered)),
                **{f"error_{p}": rate(sum(p in i for i in issues), len(delivered))
                   for p in ("unknown_id", "obsolete_id", "not_a_cell_type", "label_mismatch", "unapproved_symbol",
                             "marker_not_in_data", "no_markers")},
                "routed_to_a_person": rate(sum(v["routed"] for _, v in views), len(mine)),
                "to_an_expert_as_conflict": rate(sum(v["expert"] for _, v in views), len(mine))}

    split = case.tasks[rows[0]["task_id"]]["split"] if rows else "pilot"
    protocol = rows[0].get("protocol", 1) if rows else 2
    names = views_for(protocol)
    summary = {"benchmark": f"singlecell-celltype-v{protocol}", "split": split,
               "results": {m: {n: metrics([r for r in rows if r["model"] == m], n) for n, _ in names} for m in models},
               "pooled": {n: metrics(rows, n) for n, _ in names}, "episodes": len(rows),
               "calls": sum(len(r["calls"]) for r in rows), "failed_calls": sum(c["error"] is not None
                                                                              for r in rows for c in r["calls"]),
               "revised": sum(len(r["attempts"]) > 1 for r in rows),
               "codes": {c: sum(c in a["codes"] for r in rows for a in r["attempts"])
                         for c in sorted({c for r in rows for a in r["attempts"] for c in a["codes"]})},
               "episodes_sha256": hashlib.sha256((results / "episodes.jsonl").read_bytes()).hexdigest()}
    if protocol >= 3:  # first answers the definition check flagged, by how they compare with the authors' term
        flagged = collections.Counter()
        for r in rows:
            got = [c["answer"] for c in r["calls"] if c["answer"] and c["answer"]["decision"] == "annotate"]
            if r["attempts"] and "BEV026" in r["attempts"][0]["codes"]:
                flagged[outcome(case, truth[r["task_id"]]["term"], got[0])] += 1
        summary["definition_flags_on_first_answers"] = dict(sorted(flagged.items()))
    summary["funnel"] = funnel(case, truth, rows)
    (results / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8",
                                          newline="\n")
    (results / "summary.md").write_text(render(summary), encoding="utf-8", newline="\n")
    print(render(summary))
    return summary


def first_answer_stage(attempt: dict) -> str:
    """What the checks found in an episode's first record, most decisive first."""
    if attempt["status"] == "admitted":
        return "passed"
    fixable = [f for f in attempt["findings"] if f["rule_id"] not in feedback.EXPERT]
    if any(f["rule_id"] in ("BEV017", "BEV023", "BEV024") or (f["rule_id"] == "BEV016" and f["where"].startswith("object"))
           for f in fixable):
        return "identifier error"
    if any(f["rule_id"] == "BEV016" for f in fixable):
        return "marker not in the data"
    if any(f["rule_id"] == "BEV026" for f in fixable):
        return "definition contradicted"
    return "conflict, to a person" if attempt["to_expert"] else "other finding"


def funnel(case: Case, truth: dict, rows: list[dict]) -> dict:
    """Stage by stage: the first answer's checks, what feedback did with the fixable ones, and how the admitted
    annotations compare with the authors' terms. The expert audit of admitted records is not yet run (#24)."""
    first, final, fixed, reference = (collections.Counter() for _ in range(4))
    for r in rows:
        if not r["attempts"]:
            first["no annotation"] += 1
            final["no annotation"] += 1
            continue
        stage = first_answer_stage(r["attempts"][0])
        first[stage] += 1
        last = r["attempts"][-1]
        final["admitted" if last["status"] == "admitted" else "to a person"] += 1
        if stage not in ("passed", "conflict, to a person"):
            fixed["admitted" if last["status"] == "admitted" else "to a person"] += 1
        if last["status"] == "admitted":
            got = [c["answer"] for c in r["calls"] if c["answer"] and c["answer"]["decision"] == "annotate"]
            kind = outcome(case, truth[r["task_id"]]["term"], got[len(r["attempts"]) - 1])
            reference["compatible" if kind in ("exact", "coarser", "finer") else "disagrees"] += 1
    return {"first_answer": dict(sorted(first.items())), "fixable_after_feedback": dict(sorted(fixed.items())),
            "final": dict(sorted(final.items())), "admitted_against_reference": dict(sorted(reference.items()))}


def render(summary: dict) -> str:
    f = score_claims.fraction
    protocol = int(summary["benchmark"].rsplit("v", 1)[1])
    lines = [f"# Single-cell cell-type annotation ({summary['split']} set"
             + (f", protocol {protocol})" if protocol != 1 else ")"), "",
             "Each model annotates one cluster from its top 20 marker genes with a Cell Ontology term and the markers "
             "that support it. Compared with the authors' term: exact, coarser (an ancestor), finer (a descendant) or "
             "wrong; an identifier that is not a current cell type term is invalid.", "",
             "| Model | View | Answered | Exact | Coarser | Finer | Wrong | Invalid ID | Answers with an identifier "
             "or marker error | Routed to a person |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    blocks = [(score_claims.MODEL_NAMES[m], v) for m, v in summary["results"].items()] + [("All models", summary["pooled"])]
    for name, views in blocks:
        for key, label in views_for(protocol):
            m = views[key]
            lines.append(f"| {name} | {label} | {f(m['answered'])} | {f(m['exact'])} | {f(m['coarser'])} | "
                         f"{f(m['finer'])} | {f(m['wrong'])} | {f(m['invalid'])} | "
                         f"{f(m['with_identifier_or_marker_error'])} | {f(m['routed_to_a_person'])} |")
    p = summary["pooled"]["model"]
    lines += ["", "Errors in the models' first answers (all models): "
              + ", ".join(f"{k.removeprefix('error_').replace('_', ' ')} {f(p[k])}" for k in sorted(p)
                          if k.startswith("error_")) + ".",
              "", f"{summary['episodes']} episodes, {summary['calls']} model calls ({summary['failed_calls']} failed), "
              f"{summary['revised']} revised after feedback. Rule codes raised across all records: "
              + ", ".join(f"{c} {n}" for c, n in summary["codes"].items()) + ".", ""]
    if "definition_flags_on_first_answers" in summary:
        lines[-1:] = ["", "First answers the definition check flagged, by comparison with the authors' term: "
                      + ", ".join(f"{k} {n}" for k, n in summary["definition_flags_on_first_answers"].items()) + ".", ""]
    if "funnel" in summary:
        stages = summary["funnel"]

        def listed(counts: dict) -> str:
            return ", ".join(f"{k} {n}" for k, n in counts.items())
        lines[-1:] = ["", f"Funnel. First answers: {listed(stages['first_answer'])}. Answers with a fixable finding, after "
                      f"feedback: {listed(stages['fixable_after_feedback'])}. Final: {listed(stages['final'])}. Admitted, "
                      f"against the authors' term: {listed(stages['admitted_against_reference'])}. Expert audit of "
                      "admitted records: not yet run.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    steps = parser.add_subparsers(dest="step", required=True)
    r = steps.add_parser("run")
    r.add_argument("--output", type=Path, required=True)
    r.add_argument("--split", choices=["pilot", "test", "external"], default="pilot")
    r.add_argument("--models", nargs="+", choices=list(run_models.MODELS), default=list(run_models.MODELS))
    r.add_argument("--workers", type=int, default=2)
    r.add_argument("--limit", type=int)
    r.add_argument("--protocol", type=int, choices=sorted(PROMPTS), default=3)
    c = steps.add_parser("collect")
    c.add_argument("--output", type=Path, required=True)
    c.add_argument("--results", type=Path, required=True)
    s = steps.add_parser("score")
    s.add_argument("--results", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.step == "collect":
        collect(args.output, args.results)
        return 0
    if args.step == "score":
        score(args.results)
        return 0
    return run(args.output, args.split, args.models, args.workers, args.limit, args.protocol)


if __name__ == "__main__":
    sys.exit(main())
