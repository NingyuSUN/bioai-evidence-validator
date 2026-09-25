"""MkDocs hooks: publish selected repository files as pages and keep every link working.

Pages outside docs/ are added with their real location remembered. Relative links are
resolved against that real location: a target that is also a site page stays an internal
link; anything else (code, data, results) becomes a GitHub link, and images a raw URL.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from mkdocs.structure.files import File

REPO = Path(__file__).resolve().parents[1]
BLOB = "https://github.com/NingyuSUN/bioai-evidence-validator/blob/main/"
RAW = "https://raw.githubusercontent.com/NingyuSUN/bioai-evidence-validator/main/"
EXTRA_PAGES = {  # repository path -> site path
    "examples/clinvar_germline/README.md": "benchmarks/clinvar.md",
    "examples/vbo_canine/README.md": "benchmarks/vbo-canine.md",
    "community/profiles/README.md": "community-profiles.md",
    "CONTRIBUTING.md": "contributing.md",
    "CHANGELOG.md": "changelog.md",
}
LINK = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)((?:\s+\"[^\"]*\")?)\)")


def on_files(files, config):
    for source, dest in EXTRA_PAGES.items():
        files.append(File.generated(config, dest, abs_src_path=str(REPO / source)))
    return files


def _repo_path(src_uri: str) -> str:
    """Where a site page really lives in the repository."""
    for source, dest in EXTRA_PAGES.items():
        if dest == src_uri:
            return source
    return f"docs/{src_uri}"


def _site_path(repo_path: str) -> str | None:
    if repo_path in EXTRA_PAGES:
        return EXTRA_PAGES[repo_path]
    if repo_path.startswith("docs/") and repo_path.endswith(".md"):
        return repo_path.removeprefix("docs/")
    return None


def on_page_markdown(markdown, page, config, files):
    here = _repo_path(page.file.src_uri)

    def rewrite(match: re.Match) -> str:
        bang, text, target, title = match.groups()
        if re.match(r"^[a-z][a-z0-9+.-]*:|^#|^/", target):
            return match.group(0)  # absolute URL, anchor, or site-absolute path
        path, _, anchor = target.partition("#")
        resolved = os.path.normpath(os.path.join(os.path.dirname(here), path)).replace(os.sep, "/")
        if resolved.startswith(".."):
            return match.group(0)
        site = _site_path(resolved)
        if site is None and resolved.startswith("docs/") and bang:
            site = resolved.removeprefix("docs/")  # images under docs/ are copied into the site
        if site:
            new = os.path.relpath(site, os.path.dirname(page.file.src_uri) or ".").replace(os.sep, "/")
        else:
            new = (RAW if bang else BLOB) + resolved
        return f"{bang}[{text}]({new}{'#' + anchor if anchor else ''}{title})"

    return LINK.sub(rewrite, markdown)
