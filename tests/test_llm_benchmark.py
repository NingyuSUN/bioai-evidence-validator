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


def test_ask_retries_once_on_tool_use_and_records_it():
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
    pid, text = papers[task["pmid"]][0]
    assert f"[{pid}] {text}" in suite.prompt(task, "with_source", papers)
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
    pid, text = max(papers[task["pmid"]], key=lambda p: len(p[1]))
    sentence = " ".join(text.split()[:20])
    real = {"decision": "supports", "quotes": [{"paragraph": pid, "text": sentence}], "rationale": ""}
    assert literature_checker.check(task, real)["status"] == "admitted"
    assert score_lit.in_paper(sentence, papers[task["pmid"]])
    altered = {**real, "quotes": [{"paragraph": pid, "text": sentence.replace(" ", "  ", 1) + " strongly"}]}
    assert literature_checker.check(task, altered)["status"] == "rejected"
    assert literature_checker.check(task, {**real, "decision": "stop"})["status"] == "not_submitted"
