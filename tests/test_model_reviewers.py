"""Model reviewers: prompts stay blinded, answers are validated, tool use is caught, export matches the protocol."""
import csv
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from bioevidence_validator import review

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "evaluation" / "clinvar_review"
sys.path.insert(0, str(KIT))  # export imports its sibling import_sheets


def load(name):
    spec = importlib.util.spec_from_file_location(f"mr_{name}", KIT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mr, prepare, importer = load("model_reviewers"), load("prepare_packets"), load("import_sheets")
ANSWER = {"statement_label": "correct", "statement_rationale": "two labs agree",
          "research_summary": "admitted", "research_summary_rationale": "criteria provided",
          "clinical_reference": "review_required", "clinical_reference_rationale": "dissent",
          "expert_reference": "rejected", "expert_reference_rationale": "no expert panel",
          "later_information_seen": "no"}
CASE = {"case_code": "CABC123", "set": "calibration", "gene": "GENE1", "submissions": "2",
        "summary": "1) Pathogenic · Assertion criteria provided · clinical testing · evaluated Jan 01, 2020 · Lab A"}


@pytest.fixture(autouse=True)
def fake_executables(monkeypatch):
    monkeypatch.setattr(mr, "find_executable", lambda name: name)


def test_schema_and_import_agree_on_labels():
    assert set(mr.CHOICES) == set(importer.CHOICES)
    assert all(set(mr.CHOICES[k]) == importer.CHOICES[k] for k in mr.CHOICES)
    assert set(mr.SCHEMA["required"]) == set(mr.ANSWER_FIELDS) and mr.SCHEMA["additionalProperties"] is False


def done(stdout="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


def test_claude_parser_reports_server_tool_use():
    out = json.dumps({"structured_output": ANSWER, "is_error": False, "total_cost_usd": 0.02,
                      "usage": {"input_tokens": 5, "output_tokens": 7, "server_tool_use": {"web_search_requests": 1}}})
    answer, tools, usage = mr.claude_parse(out, Path("."))
    assert answer == ANSWER and tools == ["web_search_requests"] and usage["output_tokens"] == 7
    with pytest.raises(ValueError):
        mr.claude_parse(json.dumps({"is_error": True, "subtype": "error"}), Path("."))


def test_codex_parser_separates_errors_from_tool_calls(tmp_path):
    (tmp_path / "last.json").write_text(json.dumps(ANSWER), encoding="utf-8")
    events = [{"type": "item.completed", "item": {"type": "error", "message": "MCP auth"}},
              {"type": "item.completed", "item": {"type": "command_execution"}},
              {"type": "item.completed", "item": {"type": "agent_message"}},
              {"type": "turn.completed", "usage": {"input_tokens": 3, "output_tokens": 4}}]
    answer, tools, usage = mr.codex_parse("\n".join(map(json.dumps, events)), tmp_path)
    assert answer == ANSWER and tools == ["command_execution"] and usage["warnings"] == 1


def test_gemini_parser_finds_nested_answer_and_web_search():
    events = [{"event": "step_update", "step_update": {"step_type": "tool_call", "tool_name": "search_web"}},
              {"event": "step_update", "step_update": {"step_type": "finish", "tool_name": "finish"}},
              {"event": "result", "result": {"structured_output": ANSWER, "usage": {"input_tokens": 9}}}]
    answer, tools, usage = mr.gemini_parse("\n".join(map(json.dumps, events)), Path("."))
    assert answer == ANSWER and tools == ["search_web"] and usage["input_tokens"] == 9
    with pytest.raises(ValueError, match="no structured output"):
        mr.gemini_parse(json.dumps({"event": "result", "result": {"status": "FAILED"}}), Path("."))


def test_prompt_contains_only_packet_material():
    seen = {}

    def runner(argv, stdin, workdir, timeout):
        seen["argv"], seen["stdin"], seen["files"] = argv, stdin, sorted(p.name for p in workdir.iterdir())
        return done(json.dumps({"structured_output": ANSWER, "usage": {}}))

    result = mr.review_case("claude", "claude-test", CASE, "RUBRIC TEXT", 60, runner=runner)
    assert result["ok"] and "CABC123" in seen["stdin"] and "RUBRIC TEXT" in seen["stdin"] and "Lab A" in seen["stdin"]
    assert seen["files"] == ["schema.json"]  # the model's working directory holds nothing else
    assert seen["argv"][seen["argv"].index("--tools") + 1] == ""  # Claude runs with every tool disabled


def gemini_runner(tool_uses):
    calls = iter(tool_uses)

    def runner(argv, stdin, workdir, timeout):
        tool = next(calls)
        events = ([{"step_update": {"tool_name": tool}}] if tool else []) + [{"result": {"structured_output": ANSWER}}]
        return done("\n".join(map(json.dumps, events)))
    return runner


def test_tool_use_is_retried_once_then_flagged():
    clean = mr.review_case("gemini", "g", CASE, "R", 60, runner=gemini_runner(["search_web", None]))
    assert clean["ok"] and clean["tools_used"] == [] and len(clean["attempts"]) == 2
    assert clean["labels"]["later_information_seen"] == "no"
    flagged = mr.review_case("gemini", "g", CASE, "R", 60, runner=gemini_runner(["search_web", "search_web"]))
    assert flagged["ok"] and flagged["tools_used"] == ["search_web"]
    assert flagged["labels"]["later_information_seen"] == "yes"  # a lookup may have reached later information


def test_invalid_answers_fail_after_retry():
    bad = {**ANSWER, "research_summary": "probably"}
    result = mr.review_case("claude", "c", CASE, "R", 60,
                            runner=lambda *a: done(json.dumps({"structured_output": bad, "usage": {}})))
    assert not result["ok"] and len(result["attempts"]) == 2 and "invalid" in result["attempts"][-1]["error"]


def test_run_resumes_and_export_writes_protocol_files(tmp_path, monkeypatch):
    kit = tmp_path / "kit"
    prepare.prepare(kit, salt="test-salt", calibration=4)
    calls = []

    def fake_review(backend, model, case, rubric, timeout):
        calls.append((backend, case["case_code"]))
        return {"code": case["case_code"], "backend": backend, "model": model, "prompt_sha256": "x", "ok": True,
                "labels": dict(ANSWER), "tools_used": [], "attempts": [{"seconds": 1.0, "error": None, "usage": {}}],
                "finished_at": "2026-09-28T00:00:00+00:00"}

    monkeypatch.setattr(mr, "review_case", fake_review)
    monkeypatch.setattr(mr, "cli_version", lambda name: f"{name} 1.0")
    out = tmp_path / "models"
    args = ["run", "--packet", str(kit / "reviewer_packet"), "--output", str(out), "--set", "calibration",
            "--backends", "claude", "gemini"]
    assert mr.main(args) == 0 and len(calls) == 8
    assert mr.main(args) == 0 and len(calls) == 8  # resumed: nothing asked twice
    with (out / "claude" / "labels.csv").open(encoding="utf-8") as handle:
        filled = [r for r in csv.DictReader(handle) if r["statement_label"]]
    assert len(filled) == 4 and filled[0]["sources_consulted"] == "model knowledge only; no tools"

    assert mr.main(["export", "--output", str(out), "--key", str(kit / "maintainer" / "key.json"),
                    "--annotated-at", "2026-09-28"]) == 0
    annotations = review.load_annotations(out / "model_annotations.csv")
    assert {a["reviewer_id"] for a in annotations} == {"model:claude-opus-5-5", "model:gemini-3.1-pro-high"}
    assert len(annotations) == 2 * 4 * 3 and all(a["split"] == "development" for a in annotations)
    predictions = review.load_predictions(out / "model_predictions.csv")
    assert {p["subset"] for p in predictions} <= {"divergent", "control"} and len(predictions) == 24
