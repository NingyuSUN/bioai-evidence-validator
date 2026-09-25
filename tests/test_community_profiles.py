"""Every community profile folder is complete, and each example case meets its expected outcome."""
from pathlib import Path

import pytest
import yaml

from bioevidence_validator import build_record, load_draft, validate_record
from bioevidence_validator.engine import load_profile

GALLERY = Path(__file__).resolve().parents[1] / "community" / "profiles"
FOLDERS = sorted(p.parent for p in GALLERY.glob("*/profile.yaml"))
CASES = [(folder, case) for folder in FOLDERS
         for case in yaml.safe_load((folder / "expected.yaml").read_text(encoding="utf-8"))]


def test_gallery_is_not_empty():
    assert FOLDERS, "expected at least the _template profile"


@pytest.mark.parametrize("folder", FOLDERS, ids=lambda p: p.name)
def test_profile_folder_is_complete(folder):
    load_profile((folder / "profile.yaml").read_bytes())  # raises on any invalid field
    assert (folder / "README.md").is_file()
    expected = yaml.safe_load((folder / "expected.yaml").read_text(encoding="utf-8"))
    on_disk = {p.relative_to(folder).as_posix() for p in (folder / "cases").glob("*.yaml")}
    assert set(expected) == on_disk, "every case needs an expected outcome, and vice versa"
    outcomes = {entry["overall"] for entry in expected.values()}
    assert "admitted" in outcomes and outcomes - {"admitted"}, "include admitted and non-admitted examples"


@pytest.mark.parametrize("folder,case", CASES, ids=lambda v: v if isinstance(v, str) else v.name)
def test_case_meets_expected_outcome(folder, case):
    expected = yaml.safe_load((folder / "expected.yaml").read_text(encoding="utf-8"))[case]
    draft_path = folder / case
    report = validate_record(build_record(load_draft(draft_path), base_dir=draft_path.parent),
                             profile=folder / "profile.yaml")
    assert report["overall_status"] == expected["overall"]
    actual = {d["use"]: {"status": d["admission_status"], "reasons": d["reason_codes"]} for d in report["use_decisions"]}
    assert actual == {use: {"status": v["status"], "reasons": sorted(v["reasons"])} for use, v in expected["uses"].items()}
