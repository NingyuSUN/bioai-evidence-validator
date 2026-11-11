"""Build archives must preserve the public-tree privacy boundary."""
import importlib.util
import io
import json
import stat
import tarfile
import zipfile
from pathlib import Path

import pytest


def checker(monkeypatch):
    path = Path(__file__).parents[1] / "tools" / "check_public_distribution.py"
    assert path.exists(), "The distribution guard has not been implemented"
    monkeypatch.syspath_prepend(str(path.parent))
    spec = importlib.util.spec_from_file_location("public_distribution_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def archive(tmp_path, kind, entries):
    path = tmp_path / ("example-1.0-py3-none-any.whl" if kind == "wheel" else "example-1.0.tar.gz")
    if kind == "wheel":
        with zipfile.ZipFile(path, "w") as package:
            for name, data, link in entries:
                member = zipfile.ZipInfo(name)
                if link:
                    member.create_system = 3
                    member.external_attr = (stat.S_IFLNK | 0o777) << 16
                package.writestr(member, data)
    else:
        with tarfile.open(path, "w:gz") as package:
            for name, data, link in entries:
                member = tarfile.TarInfo("example-1.0/" + name)
                if link:
                    member.type = tarfile.SYMTYPE
                    member.linkname = "unread-private-target"
                    package.addfile(member)
                else:
                    member.size = len(data)
                    package.addfile(member, io.BytesIO(data))
    return path


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_public_packages_pass_without_extracting(tmp_path, monkeypatch, kind):
    path = archive(tmp_path, kind, [("example/__init__.py", b"VALUE = 1\n", False),
                                   ("README.md", b"See https://example.org/home/research and docs/guide.md", False),
                                   ("sources/frozen.tsv.gz", b"\x1f\x8bscientific snapshot", False)])
    monkeypatch.setattr(zipfile.ZipFile, "extractall", lambda *a, **k: pytest.fail("must not extract"))
    monkeypatch.setattr(tarfile.TarFile, "extractall", lambda *a, **k: pytest.fail("must not extract"))
    assert checker(monkeypatch).check(path) == []
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_private_artifacts_and_content_are_rejected_without_echo(tmp_path, monkeypatch, kind):
    user_parts = ("home", "archive_user", "notes.txt")
    private = "/" + "/".join(user_parts)
    path = archive(tmp_path, kind, [("artifacts/build.log", b"private receipt", False),
                                   ("README.md", private.encode(), False),
                                   ("renamed.txt", b"%PDF-synthetic", False)])
    findings = checker(monkeypatch).check(path)
    assert {row["code"] for row in findings} == {"private-file", "personal-path", "private-binary"}
    assert private not in json.dumps(findings) and "private receipt" not in json.dumps(findings)


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_unsafe_members_and_links_are_rejected(tmp_path, monkeypatch, kind):
    path = archive(tmp_path, kind, [("../../outside.txt", b"unsafe", False),
                                   ("reference.txt", b"unread-private-target", True)])
    assert {row["code"] for row in checker(monkeypatch).check(path)} == {"unsafe-member", "link-member"}


def test_cli_fails_for_missing_or_invalid_builds(tmp_path, monkeypatch, capsys):
    module = checker(monkeypatch)
    assert module.main([str(tmp_path)]) == 2
    (tmp_path / "broken.whl").write_bytes(b"not an archive")
    assert module.main([str(tmp_path)]) == 1
    assert str(tmp_path) not in capsys.readouterr().out
