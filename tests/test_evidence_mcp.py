"""Local source authority survives hostile, missing and inconsistent MCP results.

Every original and human review in these tests is explicitly synthetic. Most
protocol calls are injected; a separate-process stdio case exercises the real SDK.
"""
import asyncio
import copy
import hashlib
import importlib.util
import json
import sys
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from test_evidence_library import QUOTE, acquisition, approve, record_for
from test_evidence_library import fixture as fixture

from bioevidence_validator import evidence_mcp as bridge


class Client:
    def __init__(self, store, change=None):
        self.store = store
        self.change = change
        self.calls = []
        self.closed = False

    async def call_tool(self, name, arguments):
        self.calls.append((name, copy.deepcopy(arguments)))
        original = self.store.get(arguments["citation"])
        source, block = original["source"], original["block"]
        locator = {key: block["locator"][key] for key in ("page", "pages", "bbox", "unlocated")
                   if key in block["locator"]}
        if "regions" in block["locator"]:
            locator["regions"] = [{key: region[key] for key in ("page", "bbox") if key in region}
                                  for region in block["locator"]["regions"]]
        locator_hash = hashlib.sha256(json.dumps(block["locator"], ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        shared = {"citation": original["citation"], "source_id": source["source_id"],
                  "source_sha256": source["sha256"], "conversion_id": original["conversion_id"],
                  "locator": locator, "locator_sha256": locator_hash, "scientifically_verified": False}
        if name == bridge.GET_TOOL:
            data = {**shared, "document_id": source["document_id"], "text": block["text"],
                    "text_truncated": False, "text_characters": len(block["text"]),
                    "source": {k: source[k] for k in ("source_id", "sha256", "document_id", "role")}}
        else:
            assert name == bridge.CHECK_TOOL
            data = {**self.store.check(arguments["citation"], arguments["quote"], require_review=True), **shared}
        result = SimpleNamespace(is_error=False, structured_content=data)
        if self.change:
            result = self.change(name, result)
        return result


def connect(monkeypatch, client):
    @asynccontextmanager
    async def connection(config):
        assert config["env"] == {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        try:
            yield client
        finally:
            client.closed = True
    monkeypatch.setattr(bridge, "_stdio_client", connection)


def run(fixture, monkeypatch, *, record=None, change=None, **kwargs):
    client = Client(fixture["store"], change)
    connect(monkeypatch, client)
    report = asyncio.run(bridge.validate_via_mcp(record or fixture["record"], command=sys.executable,
        args=["-c", "raise SystemExit(0)"], library_path=fixture["store"].root, **kwargs))
    assert client.closed
    return report, client


def rules(report):
    return {item["rule_id"] for item in report["findings"]}


def test_matching_unreviewed_original_remains_review_required(fixture, monkeypatch):
    report, client = run(fixture, monkeypatch)
    assert report["overall_status"] == "review_required"
    assert report["evidence_mcp"]["status"] == "completed"
    assert report["evidence_mcp"]["checks"][0]["quote_matches"] is True
    assert report["evidence_mcp"]["checks"][0]["admitted"] is False
    assert report["evidence_library"]["checks"][0]["verified"] is False
    assert [name for name, _ in client.calls] == [bridge.GET_TOOL, bridge.CHECK_TOOL]
    assert rules(report) == {"BEV015"}


@pytest.mark.parametrize("quote", ["Invented scientific result absent from this synthetic original.", "dose 1"])
def test_false_quote_cannot_pass_even_when_protocol_results_are_consistent(fixture, monkeypatch, quote):
    record = copy.deepcopy(fixture["record"])
    record["evidence_items"][0]["extracted_text"] = quote
    report, _ = run(fixture, monkeypatch, record=record)
    assert report["overall_status"] == "rejected" and "BEV017" in rules(report)
    assert report["evidence_mcp"]["checks"][0]["quote_matches"] is False


def test_wrong_record_hash_is_rejected_after_successful_mcp_retrieval(fixture, monkeypatch):
    record = copy.deepcopy(fixture["record"])
    record["source_artifacts"][0].update(sha256="a" * 64, observed_sha256="a" * 64)
    report, _ = run(fixture, monkeypatch, record=record)
    assert report["evidence_mcp"]["status"] == "completed"
    assert report["overall_status"] == "rejected" and "BEV017" in rules(report)


def test_server_cannot_manufacture_an_original_page_review(fixture, monkeypatch):
    def change(name, result):
        if name == bridge.CHECK_TOOL:
            result.structured_content.update(admitted=True, reason="human_reviewed_extraction")
        return result
    report, _ = run(fixture, monkeypatch, change=change)
    assert report["overall_status"] == "rejected"
    assert "BEV017" in rules(report)
    assert fixture["store"].reviews(fixture["citation"]) == []


@pytest.mark.parametrize(("field", "value"), [
    ("source_sha256", "a" * 64), ("source_id", "src_" + "0" * 64),
    ("conversion_id", "cv_" + "0" * 64), ("citation", "evidence:cv_" + "0" * 64 + "#b1"),
    ("locator", {"page": 2}), ("locator_sha256", "0" * 64), ("document_id", "some-other-paper"),
    ("text", "Substituted scientific content"), ("text_characters", 99999),
    ("text_truncated", "false"), ("scientifically_verified", True),
])
def test_disagreement_in_server_source_or_text_blocks_admission(fixture, monkeypatch, field, value):
    approve(fixture)
    def change(name, result):
        if name == bridge.GET_TOOL:
            result.structured_content[field] = value
        return result
    report, _ = run(fixture, monkeypatch, change=change)
    assert report["overall_status"] == "rejected" and "BEV017" in rules(report)


@pytest.mark.parametrize("page", [True, 1.0], ids=["boolean-page", "float-page"])
def test_numeric_coercion_in_nested_locator_cannot_match_original(fixture, monkeypatch, page):
    approve(fixture)
    def change(name, result):
        if name == bridge.GET_TOOL:
            assert result.structured_content["locator"] == {"page": 1}
            result.structured_content["locator"]["page"] = page
        return result
    report, _ = run(fixture, monkeypatch, change=change)
    assert report["overall_status"] == "rejected" and "BEV017" in rules(report)
    assert report["evidence_mcp"]["status"] == "comparison_failed"


def test_matching_synthetic_review_admits_only_reviewed_extraction(fixture, monkeypatch):
    approve(fixture)
    report, _ = run(fixture, monkeypatch)
    assert report["overall_status"] == "admitted"
    assert report["evidence_mcp"]["checks"][0]["admitted"] is True
    assert report["evidence_mcp"]["scientifically_verified"] is False
    assert report["evidence_library"]["checks"][0]["scientifically_verified"] is False


@pytest.mark.parametrize("mode", ["tool_error", "unstructured", "boolean_integer", "oversized", "nonfinite"])
def test_bad_response_never_falls_back_to_local_approval(fixture, monkeypatch, mode):
    approve(fixture)
    def change(name, result):
        if mode == "tool_error":
            result.is_error = True
        elif mode == "unstructured":
            result.structured_content = None
            result.content = [SimpleNamespace(text='{"admitted":true}')]
        elif mode == "boolean_integer":
            result.structured_content["scientifically_verified"] = 0
        elif mode == "oversized":
            result.structured_content["unused"] = "x" * bridge.MAX_RESULT_BYTES
        elif mode == "nonfinite":
            result.structured_content["unused"] = float("nan")
        return result
    report, _ = run(fixture, monkeypatch, change=change)
    assert report["overall_status"] == "rejected" and "BEV017" in rules(report)


def test_transport_failure_cannot_fall_back_to_an_approved_local_quote(fixture, monkeypatch):
    approve(fixture)
    @asynccontextmanager
    async def broken(config):
        raise OSError("Synthetic connection unavailable")
        yield
    monkeypatch.setattr(bridge, "_stdio_client", broken)
    report = asyncio.run(bridge.validate_via_mcp(fixture["record"], command=sys.executable,
        args=[], library_path=fixture["store"].root))
    assert report["overall_status"] == "rejected" and "BEV014" in rules(report)
    assert report["evidence_mcp"]["status"] == "comparison_failed"


def test_timeout_closes_connection_and_blocks_local_approval(fixture, monkeypatch):
    approve(fixture)
    client = Client(fixture["store"])
    async def stalled(*args):
        await asyncio.sleep(30)
    client.call_tool = stalled
    connect(monkeypatch, client)
    report = asyncio.run(bridge.validate_via_mcp(fixture["record"], command=sys.executable,
        args=[], library_path=fixture["store"].root, timeout=0.02))
    assert client.closed
    assert report["overall_status"] == "rejected" and "BEV014" in rules(report)


def test_repeated_identical_citation_and_quote_use_one_pair_of_tool_calls(fixture, monkeypatch):
    record = copy.deepcopy(fixture["record"])
    another = {**record["evidence_items"][0], "id": "bioev:item-2"}
    record["evidence_items"].append(another)
    record["statement"]["evidence_lines"][0]["evidence_item_ids"].append(another["id"])
    report, client = run(fixture, monkeypatch, record=record)
    assert len(client.calls) == 2 and len(report["evidence_mcp"]["checks"]) == 2
    assert report["overall_status"] == "review_required"


def test_declared_prefix_truncation_does_not_impersonate_a_full_quote(fixture, monkeypatch):
    def change(name, result):
        if name == bridge.GET_TOOL:
            result.structured_content.update(text=result.structured_content["text"][:12], text_truncated=True)
        return result
    report, _ = run(fixture, monkeypatch, change=change)
    assert report["evidence_mcp"]["status"] == "completed"
    assert report["evidence_mcp"]["checks"][0]["quote_matches"] is True
    assert report["overall_status"] == "review_required"


def test_review_revocation_during_call_fails_closed(fixture, monkeypatch):
    approve(fixture)
    def change(name, result):
        if name == bridge.CHECK_TOOL:
            fixture["store"].review(fixture["citation"], QUOTE, decision="revoke",
                reviewer="SYNTHETIC TEST FIXTURE", reviewer_kind="human", note="Synthetic revocation race")
        return result
    report, _ = run(fixture, monkeypatch, change=change)
    assert report["overall_status"] == "rejected" and "BEV017" in rules(report)


def test_profile_is_frozen_before_waiting_for_mcp(fixture, monkeypatch, tmp_path):
    profile = tmp_path / "profile.yaml"
    original = bridge.profile_path("literature-claim").read_bytes()
    profile.write_bytes(original)
    def change(name, result):
        if name == bridge.GET_TOOL:
            profile.write_text("invalid: [", encoding="utf8")
        return result
    report, _ = run(fixture, monkeypatch, profile=profile, change=change)
    assert report["profile_sha256"] == hashlib.sha256(original).hexdigest()
    assert report["evidence_mcp"]["status"] == "completed"
    assert report["overall_status"] == "review_required"


def test_native_locator_annotations_stay_local_but_are_hash_bound(fixture, monkeypatch):
    conversion = fixture["store"].add_conversion(fixture["source"]["source_id"], parser="synthetic_fixture",
        parser_version="native-locator", blocks=[{"id": "b1", "kind": "paragraph", "text": QUOTE,
            "locator": {"page": 1, "native": {"synthetic_path": "C:/local/synthetic-parser-output.json"}}}])
    record = record_for(fixture["source"], conversion["citations"][0])
    report, _ = run(fixture, monkeypatch, record=record)
    assert report["evidence_mcp"]["status"] == "completed"
    assert report["overall_status"] == "review_required"


def test_mcp_cannot_hide_the_local_ocr_and_conversion_warnings(fixture, monkeypatch):
    warning = {"code": "synthetic_ocr_disagreement", "message": "Synthetic unresolved OCR disagreement"}
    converted = fixture["store"].add_conversion(fixture["source"]["source_id"], parser="synthetic_fixture",
        parser_version="warning", status="partial", issues=[warning],
        blocks=[{"id": "b1", "kind": "paragraph", "text": QUOTE, "locator": {"page": 1}, "issues": [warning]}])
    record = record_for(fixture["source"], converted["citations"][0])
    report, _ = run(fixture, monkeypatch, record=record)
    checked = report["evidence_mcp"]["checks"][0]
    assert warning in checked["block_issues"] and warning in checked["conversion_issues"]
    assert checked["conversion_status"] == "partial"
    assert report["overall_status"] == "review_required"


def test_structurally_invalid_record_never_starts_mcp(fixture, monkeypatch):
    record = record_for(fixture["source"], fixture["citation"])
    record["evidence_items"][0]["source_artifact_id"] = "missing-reference"
    def unexpected(config):
        raise AssertionError("MCP must not launch for an invalid record")
    monkeypatch.setattr(bridge, "_stdio_client", unexpected)
    report = asyncio.run(bridge.validate_via_mcp(record, command="missing-executable", args=[],
        library_path=fixture["store"].root))
    assert report["overall_status"] == "rejected"
    assert report["evidence_mcp"]["status"] == "invalid_record"


@pytest.mark.parametrize("extra", [{"url": "https://example.invalid/mcp"}, {"env": {"TOKEN": "synthetic"}},
                                   {"env": {"PYTHONUTF8": "0"}}, {"args": "not-an-array"}])
def test_configuration_rejects_remote_transport_and_unscoped_environment(tmp_path, extra):
    path = tmp_path / "server.json"
    path.write_text(json.dumps({"command": sys.executable, "args": [], **extra}), encoding="utf8")
    with pytest.raises(ValueError):
        bridge.load_server_config(path)


def test_configuration_uses_utf8_and_config_relative_working_directory(tmp_path):
    config = tmp_path / "server.json"
    config.write_text(json.dumps({"command": sys.executable, "args": ["-m", "example"], "cwd": "."}), encoding="utf8")
    parsed = bridge.load_server_config(config)
    assert parsed["cwd"] == tmp_path.resolve()
    assert parsed["env"] == {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def test_duplicate_json_keys_are_rejected_before_process_start(tmp_path):
    path = tmp_path / "server.json"
    path.write_text('{"command":"first", "command":"second", "args":[]}', encoding="utf8")
    with pytest.raises(ValueError, match="Duplicate"):
        bridge.load_server_config(path)


def test_cli_cannot_write_into_library_or_overwrite_input(fixture, tmp_path):
    for output in [fixture["store"].root / "report.json", tmp_path / "input.json", tmp_path / "server.json"]:
        with pytest.raises(SystemExit) as caught:
            bridge.main(["--server-config", str(tmp_path / "server.json"), "--evidence-library",
                         str(fixture["store"].root), "--record", str(tmp_path / "input.json"), "--output", str(output)])
        assert caught.value.code == 2


def test_cli_writes_report_and_preserves_review_required_exit_code(fixture, monkeypatch, tmp_path):
    client = Client(fixture["store"])
    connect(monkeypatch, client)
    config, record, output = (tmp_path / name for name in ("server.json", "record.json", "report.json"))
    config.write_text(json.dumps({"command": sys.executable, "args": []}), encoding="utf8")
    record.write_text(json.dumps(fixture["record"]), encoding="utf8")
    code = bridge.main(["--server-config", str(config), "--evidence-library", str(fixture["store"].root),
                        "--record", str(record), "--output", str(output)])
    assert code == 2
    report = json.loads(output.read_text(encoding="utf8"))
    assert report["evidence_mcp"]["status"] == "completed" and report["overall_status"] == "review_required"


@pytest.mark.skipif(importlib.util.find_spec("mcp") is None
                    or importlib.util.find_spec("evidence_database.mcp_server") is None,
                    reason="Requires the optional MCP SDK and the local EvidPort MCP implementation")
def test_actual_stdio_server_round_trip_preserves_quote_and_review_gates(fixture):
    directory, store = fixture["tmp"], fixture["store"]
    queue = acquisition.AcquisitionQueue(directory / "queue", store)
    state = queue.list()[0]
    queue.bind_conversion(state["paper_id"], fixture["conversion"]["conversion_id"])
    (directory / "inbox").mkdir()
    project = directory / "project.json"
    project.write_text(json.dumps({"schema": 1, "project_id": "synthetic-validator-mcp",
        "store": "library", "queue": "queue", "inbox": "inbox", "runs": "runs",
        "papers": [{"metadata": fixture["metadata"]["literature"],
                    "conversion_id": fixture["conversion"]["conversion_id"]}]}), encoding="utf8")
    async def scenario():
        params = {"command": sys.executable, "args": ["-m", "evidence_database.mcp_server",
                   "--project-config", str(project)], "library_path": store.root, "timeout": 60}
        valid = await bridge.validate_via_mcp(fixture["record"], **params)
        assert valid["evidence_mcp"]["status"] == "completed", valid
        assert valid["overall_status"] == "review_required"
        assert valid["evidence_mcp"]["checks"][0]["quote_matches"] is True
        fabricated = copy.deepcopy(fixture["record"])
        fabricated["evidence_items"][0]["extracted_text"] = "This fabricated result is not present in the synthetic paper."
        invalid = await bridge.validate_via_mcp(fabricated, **params)
        assert invalid["evidence_mcp"]["status"] == "completed", invalid
        assert invalid["overall_status"] == "rejected" and "BEV017" in rules(invalid)
        assert store.reviews(fixture["citation"]) == []
    asyncio.run(scenario())
