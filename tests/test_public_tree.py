"""Publication checks inspect intended Git files without exposing private text."""
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


def checker():
    path = Path(__file__).parents[1] / "tools" / "check_public_tree.py"
    assert path.exists(), "The public-tree guard has not been implemented"
    spec = importlib.util.spec_from_file_location("public_tree_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(root, *arguments):
    return subprocess.run(["git", "-c", "safe.directory=" + root.as_posix(), "-C", str(root), *arguments],
                          check=True, capture_output=True, text=True)


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, "init", "-q")
    return tmp_path


@pytest.mark.parametrize("kind", ["windows", "windows_json", "wsl", "unix", "mac", "unix_root", "mac_root"])
def test_personal_paths_are_rejected_without_echoing_their_contents(repository, kind):
    slash = chr(92)
    user_parts = ("audit_user", "notes.txt")
    samples = {
        "windows": "C" + ":" + slash + slash.join(("Users", *user_parts)),
        "windows_json": "C" + ":" + slash * 2 + (slash * 2).join(("Users", *user_parts)),
        "wsl": "/" + "/".join(("mnt", "c", "Users", *user_parts)),
        "unix": "/" + "/".join(("home", *user_parts)),
        "mac": "/" + "/".join(("Users", *user_parts)),
        "unix_root": "/" + "/".join(("home", user_parts[0])),
        "mac_root": "/" + "/".join(("Users", user_parts[0])),
    }
    (repository / "README.md").write_text("Private input: " + samples[kind], encoding="utf8")
    findings = checker().check(repository)
    assert {row["code"] for row in findings} == {"personal-path"}
    assert findings[0]["path"] == "README.md" and findings[0]["line"] == 1
    assert "audit_user" not in json.dumps(findings)


def test_urls_relative_paths_figures_and_synthetic_sentinels_are_allowed(repository):
    (repository / "docs").mkdir()
    (repository / "docs" / "guide.md").write_text("Guide", encoding="utf8")
    (repository / "figure.png").write_bytes(b"\x89PNG\r\n\x1a\nsynthetic")
    (repository / "README.md").write_text(
        "[Guide](docs/guide.md#setup) [Web](https://example.org/home/research/page)\n"
        "![Figure](figure.png) [Contact](mailto:reader@example.org)\n"
        "Synthetic native location: " + "C" + ":/private/native.json\n"
        "```markdown\n[Example only](not-a-real-file.md)\n```\n", encoding="utf8")
    assert checker().check(repository) == []


def test_ignored_material_is_not_read_but_force_added_private_files_are_rejected(repository):
    (repository / ".gitignore").write_text("data/\n.mcp.json\n", encoding="utf8")
    (repository / "data").mkdir()
    (repository / "data" / "paper.pdf").write_bytes(b"%PDF-synthetic")
    (repository / ".mcp.json").write_text("{}", encoding="utf8")
    assert checker().check(repository) == []
    git(repository, "add", "-f", "data/paper.pdf", ".mcp.json")
    assert {row["path"] for row in checker().check(repository)} == {"data/paper.pdf", ".mcp.json"}


@pytest.mark.parametrize("name,body", [("paper.pdf", b"sample"), ("db.sqlite3", b"sample"),
    ("bundle.zip", b"sample"), ("renamed.txt", b"SQLite format 3\x00synthetic"),
    ("original.txt", b"%PDF-synthetic"), ("archive.txt", b"PK\x03\x04synthetic")])
def test_raw_documents_databases_and_archives_are_rejected(repository, name, body):
    (repository / name).write_bytes(body)
    assert checker().check(repository)[0]["code"] == "private-binary"


def test_broken_and_ignored_markdown_targets_are_not_public_links(repository):
    (repository / ".gitignore").write_text("private/\n", encoding="utf8")
    (repository / "private").mkdir()
    (repository / "private" / "result.md").write_text("Not published", encoding="utf8")
    (repository / "README.md").write_text(
        "[Missing](missing.md)\n[Private](private/result.md)\n", encoding="utf8")
    findings = checker().check(repository)
    assert [(row["code"], row["line"]) for row in findings] == [("missing-link", 1), ("missing-link", 2)]


def test_symlink_detection_prevents_reading_the_target(repository, monkeypatch):
    path = repository / "link.txt"
    path.write_text("unread", encoding="utf8")
    original_is_symlink, original_open = Path.is_symlink, Path.open
    monkeypatch.setattr(Path, "is_symlink", lambda value: value == path or original_is_symlink(value))

    def guarded_open(value, *args, **kwargs):
        assert value != path, "A symlink target must not be read"
        return original_open(value, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    assert checker().check(repository) == [{"path": "link.txt", "line": 0, "code": "symlink"}]


def test_command_reports_only_relative_locations_and_fails_closed(repository, capsys):
    (repository / "README.md").write_text("[Missing](missing.md)", encoding="utf8")
    assert checker().main([str(repository)]) == 1
    output = capsys.readouterr().out
    assert "README.md:1: missing-link" in output
    assert str(repository) not in output


def test_skip_markdown_links_keeps_personal_path_and_private_file_checks(repository, capsys):
    home_parts = ("home", "audit_user")
    (repository / "README.md").write_text("[Generated](generated.md)\n" + "/" + "/".join(home_parts), encoding="utf8")
    (repository / ".mcp.json").write_text("{}", encoding="utf8")
    assert checker().main([str(repository), "--skip-markdown-links"]) == 1
    output = capsys.readouterr().out
    assert "personal-path" in output and "private-file" in output
    assert "missing-link" not in output and "audit_user" not in output
