import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("github_action", ROOT / "tools" / "github_action.py")
action = importlib.util.module_from_spec(spec); spec.loader.exec_module(action)


def run(monkeypatch, tmp_path, *args):
    summary, output = tmp_path / "summary.md", tmp_path / "output.txt"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.chdir(ROOT)
    monkeypatch.setattr(sys, "argv", ["github_action.py", *args])
    code = action.main()
    counts = dict(line.split("=") for line in output.read_text(encoding="utf-8").split())
    return code, summary.read_text(encoding="utf-8"), {k: int(v) for k, v in counts.items()}


@pytest.mark.parametrize("fail_on,expected", [("review", 1), ("rejected", 0)])
def test_drafts_fail_on_review_only_when_asked(monkeypatch, tmp_path, fail_on, expected):
    code, summary, counts = run(monkeypatch, tmp_path, "--files", "examples/drafts/*.yaml",
                                "--profile", "literature-claim", "--format", "draft", "--fail-on", fail_on)
    assert code == expected
    assert counts == {"admitted": 1, "review_required": 1, "rejected": 0, "error": 0}
    assert "| `examples/drafts/llm_claim.yaml` | 🟡 review_required | research_summary: review_required (BEV008) |" in summary


def test_rejected_records_and_build_errors_always_fail(monkeypatch, tmp_path, capsys):
    bad = tmp_path / "bad.yaml"; bad.write_text("profile: general\n", encoding="utf-8")
    code, summary, counts = run(monkeypatch, tmp_path, "--files", f"{bad.as_posix()} examples/dataset_label/*.json",
                                "--profile", "dataset-label", "--format", "record", "--fail-on", "rejected")
    assert code == 1 and counts["rejected"] == 1 and counts["error"] == 1
    assert "::error file=examples/dataset_label/missing_sample_link.json::rejected" in capsys.readouterr().out


def test_no_matching_files_fails(monkeypatch, tmp_path):
    monkeypatch.chdir(ROOT)
    monkeypatch.setattr(sys, "argv", ["github_action.py", "--files", "no/such/*.json"])
    assert action.main() == 1
