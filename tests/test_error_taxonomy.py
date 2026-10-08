"""The error taxonomy must stay true: every benchmark fault mapped once, statuses matching the committed results."""
import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("render_taxonomy", ROOT / "tools" / "render_taxonomy.py")
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)
TAX = render.load_taxonomy()
MODES = TAX["failure_modes"]
STATS = render.control_results()
# Controls only grounding can catch; they are run outside FAULTS, as their own benchmark cohort.
TRUST_BOUNDARY = {"vbo:falsified_target", "vbo:wrong_existing_target", "vbo:unpinned_source",
                  "clinvar:fabricated_expert_review", "clinvar:omitted_dissent"}


def pipeline_faults(case, folder, module):
    sys.path.insert(0, str(ROOT / "examples" / folder))
    try:
        spec = importlib.util.spec_from_file_location(module, ROOT / "examples" / folder / "pipeline.py")
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
    finally:
        sys.path.pop(0)
    return {f"{case}:{name}" for name in loaded.FAULTS}


def test_entries_are_well_formed():
    ids = [m["id"] for m in MODES]
    assert len(ids) == len(set(ids)) and all(re.fullmatch(r"(SRC|EXT|PRV|AGG|REV)-\d+", i) for i in ids)
    for m in MODES:
        assert m["stage"] in TAX["stages"] and m["status"] in TAX["statuses"], m["id"]
        assert m["catch_layers"] and set(m["catch_layers"]) <= set(TAX["layers"]), m["id"]
        assert all(m[k].strip() for k in ("name", "definition", "example")), m["id"]
        if m["status"] != "caught":
            assert m["planned"], f"{m['id']}: say what will close the gap"


def literature_controls():
    folder = ROOT / "examples" / "civic_literature"
    sys.path.insert(0, str(folder))
    try:
        spec = importlib.util.spec_from_file_location("tax_civic_run", folder / "run.py")
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
    finally:
        sys.path.pop(0)
    return {f"civic:{name}" for name in loaded.EXPECTED if name != "base"}


def test_every_benchmark_fault_is_mapped_exactly_once():
    mapped = [c for m in MODES for c in m["negative_controls"]]
    assert len(mapped) == len(set(mapped)), "a negative control is mapped to two failure modes"
    in_code = (pipeline_faults("vbo", "vbo_canine", "tax_vbo_pipeline")
               | pipeline_faults("clinvar", "clinvar_germline", "tax_clinvar_pipeline") | TRUST_BOUNDARY
               | literature_controls())
    assert set(mapped) == in_code == set(STATS)


@pytest.mark.parametrize("mode", MODES, ids=lambda m: m["id"])
def test_status_agrees_with_committed_results(mode):
    controls = mode["negative_controls"]
    admitted = {c: STATS[c]["grounded"] for c in controls}
    if mode["status"] == "caught":
        assert controls and not any(admitted.values()), admitted
    elif mode["status"] == "partial":
        assert not any(admitted.values()) and mode.get("uncovered_form"), mode["id"]
    elif mode["status"] == "exposed":
        assert controls and all(admitted[c] == STATS[c]["n"] for c in controls), admitted
        assert set(controls) <= TRUST_BOUNDARY
    else:
        assert not controls, "an uncovered failure mode has no negative control by definition"


def test_cited_rule_codes_exist():
    table = (ROOT / "docs" / "ENGINEERING.md").read_text(encoding="utf-8")
    known = set(re.findall(r"^\| (SCHEMA|RECORD_INTEGRITY|BEV\d{3}) \|", table, re.MULTILINE))
    cited = {code for m in MODES for code in m["rule_codes"]}
    assert cited and cited <= known, cited - known


def test_rendered_page_is_up_to_date():
    assert (ROOT / "docs" / "ERROR_TAXONOMY.md").read_text(encoding="utf-8") == render.render(), \
        "run: uv run --frozen python tools/render_taxonomy.py"
