"""The extraction experiment (#21), offline: schema, drafts, the chain, the revision loop and the scoring helpers."""
import copy
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "evaluation" / "llm_benchmark"
sys.path.insert(0, str(BENCH))
spec = importlib.util.spec_from_file_location("extraction_loop", BENCH / "extraction_loop.py")
x = importlib.util.module_from_spec(spec)
sys.modules["extraction_loop"] = x
spec.loader.exec_module(x)


@pytest.fixture(scope="module")
def case():
    return x.Case()


@pytest.fixture(scope="module")
def example(case):
    """A correct claim built from CIViC's own curation of the first pilot paper."""
    task = sorted((t for t in case.tasks.values() if t["split"] == "pilot"), key=lambda t: t["task_id"])[0]
    item = next(i for i in case.civic if i["citation_id"] == task["pmid"] and i["evidence_type"] in x.CIVIC_TYPES)
    gene = sorted(x.civic_genes(case, item["molecular_profile"]))[0]
    hgnc = next(k for k, v in case.genes.by_id.items() if v["symbol"] == gene)
    pid, text = next((pid, t) for pid, kind, t in case.papers[task["pmid"]] if kind == "p" and gene in t)
    sentence = next(s for s in re.split(r"(?<=[.!?])\s+", text) if gene in s and len(s.split()) >= 6)
    doid = f"DOID:{item['doid']}"
    predicate = next(p for p, kind in x.KINDS.items() if kind == (item["evidence_type"], item["significance"]))
    claim = {"statement": {"subject": {"id": hgnc, "label": gene, "type": "gene"}, "predicate": predicate,
                           "object": {"id": doid, "label": case.doid.terms[doid].name, "type": "disease"}},
             "variant": "", "therapies": [], "evidence": [{"locator": pid, "text": sentence, "direction": "supports"}]}
    return task, item, claim


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def test_schema_comes_from_the_draft_schema_and_is_strict():
    import yaml
    profile = yaml.safe_load((x.PROFILE).read_text(encoding="utf-8"))
    statement = x.SCHEMA["properties"]["claims"]["items"]["properties"]["statement"]
    assert statement["properties"]["predicate"]["enum"] == profile["predicates"] == list(x.KINDS)
    assert statement["properties"]["subject"]["properties"]["type"]["enum"] == ["gene"]
    for schema in (x.SCHEMA, x.REVISION_SCHEMA):
        for node in walk(schema):
            assert not set(node) & x.STRICT_DROP
            if node.get("type") == "object":
                assert node["additionalProperties"] is False and node["required"] == list(node["properties"])


def test_answers_are_checked(example):
    _, _, claim = example
    assert x.check_answer({"claims": [claim]})
    for broken in ({"claims": [{**claim, "extra": 1}]}, {"claims": "none"}, {},
                   {"claims": [{**claim, "statement": {**claim["statement"], "predicate": "causes"}}]}):
        with pytest.raises(ValueError):
            x.check_answer(broken)
    with pytest.raises(ValueError):
        x.check_revision({"revisions": [{**claim, "claim": "1", "action": "revise"}]})


def test_the_chain_admits_a_correct_claim_and_names_each_fault(case, example):
    task, item, claim = example
    summary, record, verified, _ = x.evaluate(case, task, claim, "bioev:x-test", None, set())
    assert summary["status"] == "admitted" and verified and x.problems(case, task, claim) == []
    assert record["source_artifacts"][0]["sha256"] == case.corpus.catalog["works"][f"pmid:{task['pmid']}"]["fulltext_sha256"]
    assert x.matches(case, claim, item) and x.matches(case, claim, item, kind=True)
    faults = {
        "provenance": lambda c: c.update(evidence=[]),
        "identifier": lambda c: c["statement"]["subject"].update(label=c["statement"]["subject"]["label"].lower()),
        "quote": lambda c: c["evidence"][0].update(text=c["evidence"][0]["text"] + " in mice"),
    }
    for stage, change in faults.items():
        bad = copy.deepcopy(claim)
        change(bad)
        summary, _, _, why = x.evaluate(case, task, bad, "bioev:x-test", None, set())
        assert x.first_stage(summary) == stage and summary["status"] != "admitted" and why
        assert x.problems(case, task, bad)
    mixed = copy.deepcopy(claim)
    mixed["evidence"].append({**claim["evidence"][0], "direction": "contradicts"})
    summary, _, _, _ = x.evaluate(case, task, mixed, "bioev:x-test", None, set())
    assert summary["to_expert"] and x.first_stage(summary) == "conflict, to a person"


def test_revision_loop(case, example, monkeypatch):
    task, _, claim = example
    wrong = copy.deepcopy(claim)
    wrong["statement"]["subject"]["label"] = claim["statement"]["subject"]["label"].lower()
    invented = copy.deepcopy(claim)
    invented["evidence"][0]["text"] = "This sentence is not anywhere in the paper at all."
    replies = [{"claims": [claim, wrong, invented]},
               {"revisions": [{"claim": 1, "action": "revise", **claim},
                              {"claim": 2, "action": "withdraw", **invented},
                              {"claim": 7, "action": "revise", **claim}]}]
    prompts = []

    def fake(key, text, timeout=600, schema=None):
        prompts.append((text, schema))
        return replies.pop(0), []

    monkeypatch.setattr(x.agent_loop, "call_model", fake)
    result = x.episode("claude-haiku", task, case)
    assert [x.final_state(c) for c in result["claims"]] == ["admitted", "admitted", "withdrawn"]
    assert [len(c["attempts"]) for c in result["claims"]] == [1, 2, 1]
    assert [c["kind"] for c in result["calls"]] == ["extract", "revise"]
    assert prompts[1][1] is x.REVISION_SCHEMA and "Claim 1:" in prompts[1][0] and "Claim 0:" not in prompts[1][0]
    assert set(result["calls"][1]["feedback"]) == {"1", "2"}
    json.dumps(result)  # episodes are written as JSON


def test_a_failed_extraction_is_recorded(case, example, monkeypatch):
    task, _, _ = example
    monkeypatch.setattr(x.agent_loop, "call_model", lambda *a, **k: ({"claims": "oops"}, []))
    result = x.episode("gpt-luna", task, case)
    assert result["claims"] == [] and result["calls"][0]["answer"] is None and "invalid answer" in result["calls"][0]["error"]


def test_reviewers_come_from_another_vendor():
    assert x.reviewer_for("claude-opus") == "gemini-flash"
    assert x.reviewer_for("gpt-astra") == "claude-haiku"
    assert x.reviewer_for("gemini-pro") == "gpt-luna"


def test_scoring_and_expert_sample_on_synthetic_episodes(case, example, monkeypatch, tmp_path):
    task, _, claim = example
    wrong = copy.deepcopy(claim)
    wrong["statement"]["object"]["label"] = "not a disease name"
    replies = {"claude-haiku": [{"claims": [claim, wrong]}, {"revisions": [{"claim": 1, "action": "revise", **claim}]}],
               "gpt-luna": [{"claims": [wrong]}, {"revisions": [{"claim": 0, "action": "withdraw", **wrong}]}]}
    current = {}
    monkeypatch.setattr(x.agent_loop, "call_model", lambda *a, **k: (replies[current["key"]].pop(0), []))
    rows = []
    for key in replies:
        current["key"] = key
        row = x.episode(key, task, case)
        row.pop("finished_at")
        rows.append(row)
    (tmp_path / "episodes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    reading = {"verdict": "supports", "evidence_from": "patients", "certainty": "finding", "rationale": "ok"}
    (tmp_path / "reviews.jsonl").write_text(json.dumps({"model": "claude-haiku", "task_id": task["task_id"], "reviews": {
        "0": {"reviewer": "gemini-flash", "reading": reading}, "1": {"reviewer": "gemini-flash", "reading": None}}}) + "\n",
        encoding="utf-8")
    summary = x.score(tmp_path)
    pooled = summary["pooled"]
    assert pooled["claims"] == 3 and pooled["final"] == {"admitted": 2, "withdrawn": 1}
    assert pooled["first_stage"] == {"identifier": 2, "passed": 1}
    assert pooled["model_review"] == {"accepted": 1, "no review": 1}
    assert pooled["admitted_with_identifier_or_quote_error"]["events"] == 0
    assert pooled["first_with_identifier_or_quote_error"]["events"] == 2
    assert pooled["recall_admitted"]["events"] >= 1 and pooled["recall_after_model_review"]["events"] >= 1
    key = [json.loads(line) for line in (tmp_path / "expert_sample" / "key.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {k["group"] for k in key} == {"stopped by the chain", "admitted, matches CIViC"} and len(key) == 4
    packet = (tmp_path / "expert_sample" / "packet.md").read_text(encoding="utf-8")
    assert "EXT-1" in packet and "claude" not in packet.lower() and "stopped" not in packet
    assert (tmp_path / "expert_sample" / "labels.csv").read_text(encoding="utf-8").splitlines()[0].startswith("sample_id,")


def test_out_of_quota_stops_the_model_and_leaves_its_episodes_to_resume(case, monkeypatch, tmp_path):
    def limited(key, text, timeout=600, schema=None):
        if key.startswith("claude"):
            raise ValueError("Claude returned no structured output: success: You've hit your session limit · resets 6pm")
        return {"claims": []}, []

    monkeypatch.setattr(x.agent_loop, "call_model", limited)
    assert x.run(tmp_path, "pilot", ["claude-haiku", "claude-opus", "gpt-luna"], 2, limit=3) == 1
    written = sorted(p.parent.name for p in (tmp_path / "episodes").glob("*/*.json"))
    assert written == ["gpt-luna"] * 3  # nothing recorded for the models that ran out
    slots = x.slots_for(["claude-haiku", "claude-opus", "gpt-luna"], 2)
    assert slots["claude-haiku"] is slots["claude-opus"] and slots["claude-opus"] is not slots["gpt-luna"]


def test_locators_name_the_paragraph(case, example):
    task, _, claim = example
    pid = claim["evidence"][0]["locator"]
    assert {x.paragraph_id(v) for v in (pid, f"[{pid}]", f"#{pid}", f" [{pid}] ")} == {pid}
    bracketed = copy.deepcopy(claim)
    bracketed["evidence"][0]["locator"] = f"[{pid}]"
    record, _ = x.build(case, task, bracketed, "bioev:x-test")
    assert record["evidence_items"][0]["locator"] == f"#{pid}"
    elsewhere = copy.deepcopy(claim)  # a real quote cited at another paragraph is caught
    other = next(p for p, kind, _ in case.papers[task["pmid"]] if kind == "p" and p != pid)
    elsewhere["evidence"][0]["locator"] = other
    summary, _, _, why = x.evaluate(case, task, elsewhere, "bioev:x-test", None, set())
    assert summary["status"] == "rejected" and any("not at #" in w for w in why)
