"""The single-cell cell-type annotation case: pinned sources, tasks, records and scoring."""
import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest

from bioevidence_validator.feedback import reasons, to_expert

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "examples" / "singlecell_celltype"


def load(name):
    spec = importlib.util.spec_from_file_location(f"bench_{name}", ROOT / "evaluation" / "llm_benchmark" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


loop = load("celltype_loop")


@pytest.fixture(scope="module")
def case():
    return loop.Case()


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_snapshots_match_the_manifest(case):
    manifest = case.manifest
    hashes = [manifest["cell_ontology"]["sha256"], manifest["hgnc"]["sha256"], manifest["asctb"]["sha256"],
              *(d["markers_sha256"] for d in manifest["datasets"])]
    assert all(case.store.verified(h) for h in hashes)
    assert case.ontology.prefix == "CL" and manifest["cell_ontology"]["version"] == case.ontology.version
    assert len(case.genes.approved) > 40_000 and manifest["asctb"]["assertions"] > 1000


def test_tasks_hide_the_answer_and_split_per_dataset(case):
    tasks, truth = jsonl(CASE / "sources/tasks.jsonl"), jsonl(CASE / "sources/truth.jsonl")
    assert [t["task_id"] for t in tasks] == [t["task_id"] for t in truth] and len({t["task_id"] for t in tasks}) == len(tasks)
    assert all(not {"term", "label", "author_term", "author_label"} & set(t) for t in tasks)
    assert set(Counter(t["dataset"] for t in tasks if t["split"] == "pilot").values()) == {4}
    for task, answer in zip(tasks, truth, strict=True):
        text = json.dumps(task).casefold()
        assert answer["term"].casefold() not in text and answer["label"].casefold() not in text
        assert answer["term"] in case.ontology.terms and not case.ontology.terms[answer["term"]].obsolete


def test_task_markers_are_the_top_rows_of_the_pinned_table(case):
    for task in case.tasks.values():
        rows = [r for r in case.tables[task["markers_sha256"]] if r["cluster"] == task["cluster"]]
        assert [m["gene"] for m in task["markers"]] == [r["gene"] for r in rows[:20]]
        assert all(g in case.genes.approved for g in (r["gene"] for r in rows))


def hepatocytes(case):
    return next(t for t in case.tasks.values() if t["dataset"] == "liver" and t["cluster"] == "c01")


def answer(term, label, *genes, against=()):
    return {"decision": "annotate", "cell_type_id": term, "cell_type_label": label, "rationale": "",
            "markers": [{"gene": g, "stance": "supports"} for g in genes] + [{"gene": g, "stance": "contradicts"}
                                                                          for g in against]}


def test_validator_admits_a_grounded_answer_and_explains_errors(case):
    validator, task = case.validator(), hepatocytes(case)
    report = validator.validate(loop.record(case, task, answer("CL:0000182", "hepatocytes", "APOC3", "TTR")))
    assert report["overall_status"] == "admitted"
    record = loop.record(case, task, answer("CL:0000092", "hepatocyte", "APOC3", "CD20"))
    report = validator.validate(record)
    assert report["overall_status"] == "rejected"
    text = " ".join(reasons(record, report))
    assert "'hepatocyte' is the name of CL:0000182" in text and "alias of MS4A1" in text and "No row" in text
    lymphocyte = loop.record(case, task, answer("CL:0000084", "T cell", "APOC3", against=["TTR"]))
    assert to_expert(validator.validate(lymphocyte))  # its own evidence disagrees
    assert loop.record(case, task, {**answer("", "", "APOC3"), "decision": "uncertain"}) is None


def test_reference_cross_check_uses_disjointness(case):
    validator, task = case.validator(protocol=1), hepatocytes(case)
    grounder = next(g for g in validator.grounders if g.name == "reference:ASCT+B")
    record = loop.record(case, task, answer("CL:0000182", "hepatocyte", "APOC3"))
    listed = {row["subject"] for row in grounder.assertions if row["object"] == "CL:0000236"}  # B cell markers
    assert "MS4A1" in listed or "CD19" in listed or "CD79A" in listed
    record["evidence_items"][0]["locator"] = "cluster=c01;gene=" + sorted(listed & {"MS4A1", "CD19", "CD79A"})[0]
    assert [f.rule_id for f in grounder.check(record)] == ["BEV025"]  # a B cell marker for an epithelial cell


@pytest.mark.parametrize("term,expected", [("CL:0000182", "exact"), ("CL:0000066", "coarser"), ("CL:0000084", "wrong"),
                                           ("CL:9999999", "invalid"), ("UBERON:0002107", "invalid")])
def test_outcomes_follow_the_ontology(case, term, expected):
    assert loop.outcome(case, "CL:0000182", answer(term, "x")) == expected
    assert loop.outcome(case, "CL:0000625", answer("CL:0000084", "T cell")) == "coarser"
    assert loop.outcome(case, "CL:0000084", answer("CL:0000625", "CD8-positive, alpha-beta T cell")) == "finer"


def test_problems_are_looked_up_directly(case):
    task = hepatocytes(case)
    assert loop.problems(case, task, answer("CL:0000182", "hepatocyte", "APOC3")) == []
    assert loop.problems(case, task, answer("CL:0000182", "liver cell", "CD20", "APOC3")) == [
        "label_mismatch", "unapproved_symbol", "marker_not_in_data"]
    assert loop.problems(case, task, answer("CL:9999999", "x")) == ["unknown_id", "no_markers"]
    with pytest.raises(ValueError):
        loop.check_answer({"decision": "annotate"})
    assert loop.gene_token(" CD3E;x=1 ") == "CD3E_x_1"


@pytest.mark.parametrize("folder", ["celltype-pilot", "celltype-test"])
def test_scores_replay_from_committed_episodes(folder, tmp_path):
    committed = ROOT / "evaluation" / "llm_benchmark" / "results" / folder
    (tmp_path / "episodes.jsonl").write_bytes((committed / "episodes.jsonl").read_bytes())
    loop.score(tmp_path)
    for name in ("summary.json", "summary.md"):
        assert (tmp_path / name).read_bytes() == (committed / name).read_bytes(), name


def test_views_follow_the_attempts():
    row = {"calls": [{"answer": answer("CL:0000084", "B cell", "CD3E")}, {"answer": answer("CL:0000084", "T cell", "CD3E")}],
           "attempts": [{"status": "rejected", "to_expert": False}, {"status": "admitted", "to_expert": False}]}
    assert loop.view(row, "model")["answer"]["cell_type_label"] == "B cell"
    assert loop.view(row, "gate") == {"answer": None, "routed": True, "expert": False}
    assert loop.view(row, "loop")["answer"]["cell_type_label"] == "T cell"
    assert loop.view({"calls": [{"answer": None}], "attempts": []}, "gate") == {"answer": None, "routed": False,
                                                                                "expert": False}


def test_protocol_2_drops_the_reference_check_and_narrows_contradicting_markers(case):
    task = hepatocytes(case)
    assert [g.name for g in case.validator(protocol=1).grounders][-1] == "reference:ASCT+B"
    assert not any(g.name.startswith("reference:") for g in case.validator().grounders)
    assert "any that argue against it" in loop.prompt(task, 1) and "Only if some of its markers" in loop.prompt(task)
    assert loop.prompt(task, 1).split("Which cell type")[0] == loop.prompt(task).split("Which cell type")[0]


def test_protocol_3_adds_the_definition_check(case):
    assert case.validator(protocol=3).grounders[-1].name.startswith("definitions:CL@")
    assert not any(g.name.startswith("definitions:") for g in case.validator(protocol=2).grounders)
    task = hepatocytes(case)
    record = loop.record(case, task, answer("CL:0000182", "hepatocyte", "APOC3"))
    panel = case.measure(record)
    assert panel and all(0 <= pct <= 1 for pct, _ in panel.values())
    t_cell = loop.record(case, task, answer("CL:0000625", "CD8-positive, alpha-beta T cell", "APOC3"))
    findings = case.validator(protocol=3).grounders[-1].check(t_cell)
    assert [f.rule_id for f in findings] == ["BEV026"] and "CD8" in findings[0].message  # no CD8 in hepatocytes
    assert {t["split"] for t in case.tasks.values()} == {"pilot", "test", "external"}
    assert loop.prompt(task, 3) == loop.prompt(task, 2)


def test_gate_without_definitions_admits_what_only_the_definition_check_stopped():
    row = {"calls": [{"answer": answer("CL:0000625", "CD8-positive, alpha-beta T cell", "CD8A")}],
           "attempts": [{"status": "review_required", "codes": ["BEV026"], "to_expert": False}]}
    assert loop.view(row, "gate")["answer"] is None
    assert loop.view(row, "gate_without_definitions")["answer"]["cell_type_id"] == "CL:0000625"
    row["attempts"][0]["codes"] = ["BEV017", "BEV026"]
    assert loop.view(row, "gate_without_definitions")["answer"] is None
    assert [n for n, _ in loop.views_for(3)] == ["model", "gate", "gate_without_definitions", "loop"]
    assert loop.views_for(2) == loop.VIEWS
