"""Check intended public Git files without scanning ignored local material.

This is a portable publication guard, not a credential or history scanner.
Diagnostics never reproduce matched text. Standalone compressed scientific data
and figures remain allowed; raw papers, databases and archive containers do not.
"""
import argparse
import posixpath
import re
import subprocess
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

PRIVATE_ROOTS = {"artifacts", "data", ".venv", "build", "dist", "__pycache__"}
PRIVATE_NAMES = {".mcp.json", ".claude.json", "settings.local.json", ".env"}
PRIVATE_SUFFIXES = (".pdf", ".db", ".sqlite", ".sqlite3", ".zip", ".tar", ".tar.gz", ".tgz", ".7z", ".whl")
PRIVATE_HEADERS = (b"%PDF-", b"SQLite format 3\x00", b"PK\x03\x04", b"7z\xbc\xaf\x27\x1c")
PERSONAL_PATHS = (
    re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]+(?:Users|Documents and Settings)[\\/]+", re.IGNORECASE),
    re.compile(r"(?<![\w/:])/(?:home|Users)/[^/\s<>\"'`]+", re.IGNORECASE),
    re.compile(r"(?<![\w/:])/mnt/[A-Za-z]/(?:Users|Documents and Settings)/", re.IGNORECASE),
    re.compile(r"\bfile:///(?:[A-Za-z]:|home/|Users/|mnt/)", re.IGNORECASE),
)
INLINE_LINK = re.compile(r"\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+[\"'][^\"']*[\"'])?\)")


def public_paths(root):
    """Include tracked files even if ignored, plus non-ignored new files."""
    process = subprocess.run(
        ["git", "-c", "safe.directory=" + root.as_posix(), "-C", str(root),
         "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True, check=False,
    )
    if process.returncode:
        raise ValueError("Cannot enumerate the Git publication tree")
    return sorted({name.decode("utf8", errors="surrogateescape") for name in process.stdout.split(b"\0") if name})


def private_file(name):
    parts = PurePosixPath(name).parts
    return (parts[0] in PRIVATE_ROOTS or any(part in PRIVATE_NAMES or part.startswith(".env.") for part in parts)
            or name == ".codex/config.toml" or "__pycache__" in parts or name.endswith(".pyc"))


def linked_path(name, target):
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    if any(value in target for value in ("<", ">", "{", "}", "$")):
        return None
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("/"):
        return None
    return posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(parsed.path)))


def check(root, *, check_links=True):
    root = Path(root).resolve()
    names = public_paths(root)
    published = set(names)
    directories = {str(parent) for name in names for parent in PurePosixPath(name).parents}
    findings = []

    def report(name, code, line=0):
        findings.append({"path": name, "line": line, "code": code})

    for name in names:
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts:
            report(name, "unsafe-path")
            continue
        path = root.joinpath(*relative.parts)
        chain = [path, *[parent for parent in path.parents if parent != root and root in parent.parents]]
        if any(item.is_symlink() or (item.exists() and getattr(item.lstat(), "st_file_attributes", 0) & 0x400)
               for item in chain):
            report(name, "symlink")
            continue
        if private_file(name):
            report(name, "private-file")
            continue
        if not path.is_file():
            report(name, "missing-file")
            continue
        if name.lower().endswith(PRIVATE_SUFFIXES):
            report(name, "private-binary")
            continue
        try:
            data = path.read_bytes()
        except OSError:
            report(name, "unreadable-file")
            continue
        if data.startswith(PRIVATE_HEADERS):
            report(name, "private-binary")
            continue
        text = data.decode("utf8", errors="replace")
        fence = None
        for line_number, line in enumerate(text.splitlines(), 1):
            if any(pattern.search(line) for pattern in PERSONAL_PATHS):
                report(name, "personal-path", line_number)
            if not check_links or not name.lower().endswith(".md"):
                continue
            marker = re.match(r"^\s*(`{3,}|~{3,})", line)
            if marker:
                value = marker[1]
                if fence is None:
                    fence = value
                elif value[0] == fence[0] and len(value) >= len(fence):
                    fence = None
                continue
            if fence is not None:
                continue
            prose = re.sub(r"`+[^`]*`+", "", line)
            for target in INLINE_LINK.findall(prose):
                linked = linked_path(name, target)
                if linked is not None and linked not in published and linked not in directories:
                    report(name, "missing-link", line_number)
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--skip-markdown-links", action="store_true",
                        help="Defer links to an existing strict documentation build that generates target pages")
    args = parser.parse_args(argv)
    try:
        findings = check(args.root, check_links=not args.skip_markdown_links)
    except (OSError, ValueError):
        print("Public-tree check could not inspect the repository")
        return 2
    for finding in findings:
        print(f"{finding['path']}:{finding['line']}: {finding['code']}")
    if not findings:
        print("Public-tree check passed")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
