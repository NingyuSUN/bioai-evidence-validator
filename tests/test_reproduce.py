"""tools/reproduce.py covers every committed result and figure (running it is a CI job of its own)."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reproduce", ROOT / "tools" / "reproduce.py")
reproduce = importlib.util.module_from_spec(spec)
sys.modules["reproduce"] = reproduce  # dataclasses look their module up while the class is built
spec.loader.exec_module(reproduce)


def covered() -> set[Path]:
    return {committed for step in reproduce.STEPS for committed in step.outputs}


def test_every_committed_result_is_regenerated():
    results = [p for d in [*ROOT.glob("examples/*/results"), *(ROOT / "evaluation/llm_benchmark/results").iterdir()]
               for p in d.iterdir() if p.is_file()]
    inputs = {p for step in reproduce.STEPS for p in step.inputs}  # replayed from, not regenerated
    missing = [str(p.relative_to(ROOT)) for p in results if p not in covered() and p not in inputs]
    assert results and not missing, missing


def test_every_figure_is_regenerated():
    figures = sorted((ROOT / "docs" / "assets").glob("*.svg"))
    assert figures and all(f in covered() for f in figures), [f.name for f in figures if f not in covered()]


def test_list_and_unknown_steps(capsys):
    assert reproduce.main(["--list"]) == 0
    listed = capsys.readouterr().out
    assert all(step.name in listed for step in reproduce.STEPS)
    with pytest.raises(SystemExit):
        reproduce.main(["--only", "no-such-step"])


def test_text_comparison_ignores_line_endings_only(tmp_path):
    a, b, c = tmp_path / "a.svg", tmp_path / "b.svg", tmp_path / "c.svg"
    a.write_bytes(b"<svg>\n</svg>\n")
    b.write_bytes(b"<svg>\r\n</svg>\r\n")
    c.write_bytes(b"<svg>\n<g/></svg>\n")
    assert reproduce.same(a, b) and not reproduce.same(a, c)


def test_a_check_only_step_runs(capsys):
    assert reproduce.main(["--only", "error-taxonomy"]) == 0
    assert "identical  error-taxonomy" in capsys.readouterr().out
