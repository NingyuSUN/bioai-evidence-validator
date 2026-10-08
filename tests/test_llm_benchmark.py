"""The LLM benchmark: deterministic tasks, stdlib runner plumbing, and scoring on hand-made answers."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "evaluation" / "llm_benchmark"
sys.path.insert(0, str(BENCH))


def load(name):
    spec = importlib.util.spec_from_file_location(f"bench_{name}", BENCH / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_models, score, score_lit, suite = load("run_models"), load("score"), load("score_literature"), load("literature_suite")


@pytest.mark.parametrize("script", ["tasks.py", "tasks_literature.py"])
def test_tasks_are_up_to_date(script):
    done = subprocess.run([sys.executable, str(BENCH / script), "--check"], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_splits_are_disjoint_and_references_hidden():
    for folder, key in ((BENCH / "tasks", "variation_id"), (BENCH / "literature_tasks", "pmid")):
        pilot, test = jsonl(folder / "pilot.jsonl"), jsonl(folder / "test.jsonl")
        assert not {t[key] for t in pilot} & {t[key] for t in test}
        assert all("expected_decision" not in json.dumps(t) and "category" not in t for t in pilot + test)


class Done:
    def __init__(self, stdout, returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, "", returncode


def claude_reply(answer):
    return Done(json.dumps({"structured_output": answer, "usage": {"input_tokens": 5, "output_tokens": 2}}))


def test_ask_retries_once_on_tool_use_and_records_it(monkeypatch):
    monkeypatch.setattr(run_models, "find_executable", lambda name: f"/usr/bin/{name}")  # no CLI needed
    task = jsonl(BENCH / "tasks" / "pilot.jsonl")[0]
    answer = {"decision": "stop", "conflict": "unknown", "submissions": [], "rationale": "x"}
    calls = []

    def runner(argv, stdin, workdir, timeout):
        calls.append(argv)
        reply = {"structured_output": answer, "usage": {"server_tool_use": {"web_search_requests": len(calls) == 1}}}
        return Done(json.dumps(reply))

    result = run_models.ask("claude-opus", task, "no_source", 60, runner=runner)
    assert result["ok"] and len(result["attempts"]) == 2 and result["tools_used"] == []
    assert "--tools" in calls[0] and calls[0][calls[0].index("--model") + 1] == "claude-opus-5-5"


def test_batch_prompt_and_validation():
    tasks = jsonl(BENCH / "tasks" / "pilot.jsonl")
    batches = run_models.batches(tasks)
    assert [len(b["tasks"]) for b in batches] == [25, 5]
    prompt = run_models.batch_prompt(batches[0]["tasks"])
    assert prompt.count("<variant index=") == 25 and "exactly one result per variant" in prompt
    item = {"variation_id": "1", "decision": "stop", "conflict": "no", "submissions": [], "rationale": ""}
    assert run_models.validate_batch({"results": [item]})
    with pytest.raises(ValueError):
        run_models.validate_batch({"results": [{**item, "decision": "maybe"}]})


def test_codex_failure_is_reported(tmp_path):
    stdout = json.dumps({"type": "turn.failed", "error": {"message": "model not supported"}})
    with pytest.raises(ValueError, match="model not supported"):
        run_models.codex_parse(stdout, tmp_path)


def test_literature_prompt_and_validation():
    task, papers = jsonl(BENCH / "literature_tasks" / "pilot.jsonl")[0], suite.load_papers()
    assert suite.NO_TEXT in suite.prompt(task, "no_source", papers)
    prompt = suite.prompt(task, "with_source", papers)
    pid, _, text = next(block for block in papers[task["pmid"]] if block[1] == "p")
    assert f"[{pid}] {text}" in prompt
    title = next(block for block in papers[task["pmid"]] if block[1] == "title")
    assert f"## {title[2]}" in prompt and f"[{title[0]}]" not in prompt
    assert suite.validate({"decision": "stop", "quotes": [], "rationale": ""})
    with pytest.raises(ValueError):
        suite.validate({"decision": "stop", "quotes": [{"paragraph": "p1"}], "rationale": ""})


def test_clinvar_citations_compare_dates_as_dates():
    source = [{"scv": "SCV1.1", "submitter": "Lab", "classification": "Pathogenic", "review_status": "x",
               "collection_method": "clinical testing", "date_last_evaluated": "Sep 08, 2016"},
              {"scv": "SCV2.1", "submitter": "Lab B", "classification": "Benign", "review_status": "x",
               "collection_method": "clinical testing", "date_last_evaluated": "-"}]
    cited = [{**source[0], "date_last_evaluated": "2016-09-08"}, {**source[1], "date_last_evaluated": ""},
             {**source[0], "scv": "SCV9.1"}, {**source[0], "classification": "Likely pathogenic"}]
    result = score.citations({"submissions": cited}, source)
    assert (result["exact"], result["fabricated"], result["misstated"]) == (2, 1, 1)
    assert score.citations({"submissions": cited[:1]}, source)["omitted_dissent"] == ["SCV2.1"]


@pytest.fixture(scope="module")
def clinvar_checker():
    return score.Checker()


def test_clinvar_checker_admits_a_faithful_answer_and_blocks_a_fabricated_one(clinvar_checker):
    task = next(t for t in jsonl(BENCH / "tasks" / "pilot.jsonl")
                if t["source"] and t["task_id"] in {r["task_id"] for r in jsonl(BENCH / "tasks" / "references.jsonl")
                                                    if r["category"] == "admit"})
    faithful = {"decision": "admit", "conflict": "no", "submissions": task["source"], "rationale": ""}
    assert clinvar_checker.check(task, faithful)["status"] == "admitted"
    invented = {**faithful, "submissions": [{**task["source"][0], "scv": "SCV999999999.1"}]}
    assert clinvar_checker.check(task, invented)["status"] == "rejected"
    assert clinvar_checker.check(task, {**faithful, "submissions": []})["codes"] == ["NO_EVIDENCE"]


@pytest.fixture(scope="module")
def literature_checker():
    return score_lit.Checker()


def test_literature_checker_verifies_quotes(literature_checker):
    task, papers = jsonl(BENCH / "literature_tasks" / "pilot.jsonl")[0], suite.load_papers()
    pid, _, text = max(papers[task["pmid"]], key=lambda p: len(p[2]))
    sentence = " ".join(text.split()[:20])
    real = {"decision": "supports", "quotes": [{"paragraph": pid, "text": sentence}], "rationale": ""}
    assert literature_checker.check(task, real)["status"] == "admitted"
    assert score_lit.in_paper(sentence, papers[task["pmid"]])
    altered = {**real, "quotes": [{"paragraph": pid, "text": sentence.replace(" ", "  ", 1) + " strongly"}]}
    assert literature_checker.check(task, altered)["status"] == "rejected"
    assert literature_checker.check(task, {**real, "decision": "stop"})["status"] == "not_submitted"


@pytest.mark.parametrize("module,folder", [("score", "pilot"), ("score_literature", "literature-pilot")])
def test_committed_pilot_results_replay_byte_for_byte(module, folder, tmp_path):
    committed = BENCH / "results" / folder
    (tmp_path / "answers.jsonl").write_bytes((committed / "answers.jsonl").read_bytes())
    scorer = score if module == "score" else score_lit
    assert scorer.main(["--split", "pilot", "--output", str(tmp_path)]) == 0
    for name in ("rows.jsonl", "summary.json", "summary.md"):
        assert (tmp_path / name).read_bytes() == (committed / name).read_bytes(), name


def test_semantic_units_are_up_to_date():
    done = subprocess.run([sys.executable, str(BENCH / "semantic_eval.py"), "units", "--split", "pilot", "--check"],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def test_units_hide_the_extractor_decision():
    units = jsonl(BENCH / "semantic" / "pilot-units.jsonl")
    assert units and all(set(u) == {"task_id", "claim", "title", "quotes"} for u in units)


def test_semantic_results_replay_byte_for_byte(tmp_path):
    semantic = load("semantic_eval")
    committed = BENCH / "results" / "semantic-pilot"
    (tmp_path / "answers.jsonl").write_bytes((committed / "answers.jsonl").read_bytes())
    semantic.score("pilot", None, tmp_path)
    for name in ("rows.jsonl", "summary.json", "summary.md"):
        assert (tmp_path / name).read_bytes() == (committed / name).read_bytes(), name


def test_claims_scenario_replays_from_committed_verification(tmp_path):
    claims = load("score_claims")
    committed = BENCH / "results" / "literature-claims-pilot"
    for name in ("answers.jsonl", "verification.jsonl"):
        (tmp_path / name).write_bytes((committed / name).read_bytes())
    claims.score(tmp_path)
    for name in ("rows.jsonl", "summary.json", "summary.md"):
        assert (tmp_path / name).read_bytes() == (committed / name).read_bytes(), name


def test_claims_pmids_and_titles():
    claims = load("score_claims")
    assert claims.pmid_of("PMID: 28284557") == "pmid:28284557" and claims.pmid_of("unknown") is None
    assert claims.same_title("Binimetinib versus dacarbazine in NRAS-mutant melanoma (NEMO)",
                             "Binimetinib versus dacarbazine in patients with advanced NRAS-mutant melanoma (NEMO)")
    assert not claims.same_title("Loss of the VHL tumor-suppressor gene in renal carcinomas",
                                 "Signal transduction in endocrine tissues.")


def test_claim_records_are_schema_valid():
    """Regression: an empty locator once made every scenario-1b record fail the schema before any grounding."""
    from bioevidence_validator.engine import RecordValidator

    claims = load("score_claims")
    verifier = claims.Verifier.__new__(claims.Verifier)
    verifier.catalog = {"works": {}}
    task = jsonl(BENCH / "literature_tasks" / "pilot.jsonl")[0]
    answer = {"decision": "supports", "rationale": "",
              "citations": [{"pmid": "PMID 123", "title": "A title", "quote": "A quote of more than five words here."}]}
    report = RecordValidator(profile=claims.CASE / "profile.yaml").validate(verifier.record(task, answer))
    assert "SCHEMA" not in {f["rule_id"] for f in report["findings"]}


@pytest.mark.parametrize("folder", ["agent-pilot", "agent-stance-pilot"])
def test_agent_scenario_replays_from_committed_episodes(folder, tmp_path):
    agent = load("agent_loop")
    committed = BENCH / "results" / folder
    (tmp_path / "episodes.jsonl").write_bytes((committed / "episodes.jsonl").read_bytes())
    agent.score(tmp_path)
    for name in ("summary.json", "summary.md"):
        assert (tmp_path / name).read_bytes() == (committed / name).read_bytes(), name


def test_agent_views_gate_and_loop():
    agent = load("agent_loop")
    first = {"decision": "supports", "status": "rejected", "categories": ["quote_not_found"]}
    last = {"decision": "supports", "status": "admitted", "categories": ["quote_found"]}
    row = {"submissions": [first, last]}
    assert agent.view(row, "agent") == {"final": "supports", "categories": ["quote_not_found"], "routed": False}
    assert agent.view(row, "gate") == {"final": "stop", "categories": [], "routed": True}
    assert agent.view(row, "loop") == {"final": "supports", "categories": ["quote_found"], "routed": False}
    assert agent.view({"submissions": []}, "loop") == {"final": "stop", "categories": [], "routed": False}
    stop = {"decision": "stop", "status": "rejected", "categories": []}
    assert agent.view({"submissions": [stop]}, "gate")["routed"] is False


def test_agent_steps_and_history():
    agent = load("agent_loop")
    assert agent.wsl_path(Path("C:/t/agent-work/x")) == "/mnt/c/t/agent-work/x"
    step = dict.fromkeys(agent.FIELDS, "")
    step.update(action="search", query="BRAF V600E vemurafenib", citations=[])
    assert agent.check_step(step) is step
    with pytest.raises(ValueError, match="decision"):
        agent.check_step({**step, "action": "submit"})
    with pytest.raises(ValueError, match="invalid step"):
        agent.check_step({**step, "action": "browse"})
    history = [f"[{n}] read pmid:{n}\n→ " + "x" * 1000 for n in range(1, 4)]
    short = agent.compact(list(history))
    assert short[0].endswith("read again if needed)") and short[1:] == history[1:]


def test_stances_become_evidence_lines():
    from bioevidence_validator.engine import RecordValidator

    claims = load("score_claims")
    verifier = claims.Verifier.__new__(claims.Verifier)
    verifier.catalog = {"works": {}}
    task = jsonl(BENCH / "literature_tasks" / "pilot.jsonl")[0]
    cite = {"pmid": "PMID 1", "title": "A title", "quote": "A quote of more than five words here."}

    def lines(decision, *stances):
        record = verifier.record(task, {"decision": decision, "rationale": "",
                                        "citations": [{**cite, "stance": s} for s in stances]})
        return record, {line["direction"]: line["evidence_item_ids"] for line in record["statement"]["evidence_lines"]}

    record, by = lines("supports", "supports", "contradicts", "neutral")
    assert record["statement"]["predicate"] == "supports_significance"
    assert by == {"supports": ["bioev:quote-1"], "contradicts": ["bioev:quote-2"], "neutral": ["bioev:quote-3"]}
    codes = {f["rule_id"] for f in RecordValidator(profile=claims.CASE / "profile.yaml").validate(record)["findings"]}
    assert "BEV004" in codes and "SCHEMA" not in codes
    record, by = lines("does_not_support", "contradicts", "supports")
    assert record["statement"]["predicate"] == "does_not_support_significance"
    assert by == {"supports": ["bioev:quote-1"], "contradicts": ["bioev:quote-2"]}
    record, by = lines("conflicting", "supports", "contradicts")
    assert record["statement"]["predicate"] == "supports_significance" and set(by) == {"supports", "contradicts"}


def test_agent_keeps_verified_citations_and_sends_conflicts_to_an_expert():
    agent = load("agent_loop")
    against = {"pmid": "PMID: 1", "title": "T", "quote": "Against the claim.", "stance": "contradicts"}
    wrong = {"pmid": "PMID: 2", "title": "T", "quote": "Not in the paper.", "stance": "supports"}
    first = {"submission": {"decision": "conflicting", "citations": [wrong, against]},
             "verdict": {"citations": [{"category": "quote_not_found"}, {"category": "quote_found"}]}}
    fixed = {**wrong, "quote": "In the paper."}
    assert agent.carried([first], [fixed]) == [against]
    assert agent.carried([first], [{**against, "pmid": "1", "quote": "Against  the claim."}]) == []
    assert agent.to_expert({"status": "review_required", "codes": ["BEV004"]})
    assert not agent.to_expert({"status": "review_required", "codes": ["BEV004", "BEV006"]})
    row = {"submissions": [{"decision": "supports", "status": "review_required", "codes": ["BEV004"],
                            "categories": ["quote_found", "quote_found"]}]}
    assert agent.view(row, "agent")["final"] == "supports"
    assert agent.view(row, "loop") == {"final": "conflicting", "categories": ["quote_found", "quote_found"],
                                       "routed": True}
    step = dict.fromkeys(agent.FIELDS, "")
    step.update(action="submit", decision="conflicting", citations=[{**against, "stance": "unclear"}])
    with pytest.raises(ValueError, match="stance"):
        agent.check_step(step)
    assert agent.check_step({**step, "citations": [against]})["decision"] == "conflicting"
