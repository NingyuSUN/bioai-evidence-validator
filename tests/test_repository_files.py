"""Repository configuration files must parse; GitHub silently skips a workflow it cannot read."""
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
FILES = sorted([*(ROOT / ".github" / "workflows").glob("*.yml"), *(ROOT / ".github" / "ISSUE_TEMPLATE").glob("*.yml"),
                ROOT / "action.yml", ROOT / "mkdocs.yml"])


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_yaml_parses(path):
    # BaseLoader accepts mkdocs.yml's !!python/name tag while still rejecting malformed YAML.
    assert isinstance(yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader), dict)


@pytest.mark.parametrize("path", sorted((ROOT / ".github" / "workflows").glob("*.yml")), ids=lambda p: p.name)
def test_workflow_has_name_and_jobs(path):
    workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert workflow.get("name") and workflow.get("jobs")
