"""Inspect built wheels and source archives without extracting their contents."""
import argparse
import re
import stat
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from check_public_tree import PERSONAL_PATHS, PRIVATE_HEADERS, PRIVATE_SUFFIXES, private_file


def check(archive):
    """Return only archive/member locations and categories, never matched text."""
    archive = Path(archive)
    findings = []

    def report(name, code, line=0):
        findings.append({"archive": archive.name, "path": name, "line": line, "code": code})

    def inspect(name, data=None, *, link=False, special=False, sdist=False):
        parts = PurePosixPath(name).parts
        if (not parts or PurePosixPath(name).is_absolute() or ".." in parts
                or "\\" in name or "\x00" in name or re.match(r"^[A-Za-z]:", name)
                or any(pattern.search(name) for pattern in PERSONAL_PATHS)):
            report("<unsafe-member>", "unsafe-member")
            return
        if link or special:
            report(name, "link-member" if link else "special-member")
            return
        relative = "/".join(parts[1:]) if sdist and len(parts) > 1 else name
        if private_file(name) or private_file(relative):
            report(name, "private-file")
            return
        if data is None:
            return
        if name.lower().endswith(PRIVATE_SUFFIXES) or data.startswith(PRIVATE_HEADERS):
            report(name, "private-binary")
            return
        for number, line in enumerate(data.decode("utf8", errors="replace").splitlines(), 1):
            if any(pattern.search(line) for pattern in PERSONAL_PATHS):
                report(name, "personal-path", number)

    try:
        if archive.is_symlink():
            report("<archive>", "link-member")
        elif archive.name.endswith(".whl"):
            with zipfile.ZipFile(archive) as package:
                for member in package.infolist():
                    link = stat.S_ISLNK(member.external_attr >> 16)
                    inspect(member.filename, None if member.is_dir() or link else package.read(member), link=link)
        elif archive.name.endswith(".tar.gz"):
            with tarfile.open(archive, "r:gz") as package:
                for member in package:
                    link = member.issym() or member.islnk()
                    data = None
                    if member.isfile():
                        with package.extractfile(member) as stream:
                            data = stream.read()
                    inspect(member.name, data, link=link,
                            special=not (member.isfile() or member.isdir() or link), sdist=True)
        else:
            report("<archive>", "unsupported-archive")
    except (OSError, ValueError, EOFError, RuntimeError, NotImplementedError, zipfile.BadZipFile, tarfile.TarError):
        report("<archive>", "invalid-archive")
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path("dist"))
    args = parser.parse_args(argv)
    archives = sorted([*args.directory.glob("*.whl"), *args.directory.glob("*.tar.gz")])
    if not archives:
        print("No built distributions found")
        return 2
    findings = [finding for archive in archives for finding in check(archive)]
    for finding in findings:
        print(f"{finding['archive']}:{finding['path']}:{finding['line']}: {finding['code']}")
    if not findings:
        print(f"Public distribution check passed ({len(archives)} archives)")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
