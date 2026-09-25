"""Validate records or drafts for the GitHub Action, annotate failures, and write a job summary."""
from __future__ import annotations

import argparse
import contextlib
import glob
import io
import json
import os
import sys
import tempfile
from pathlib import Path

from bioevidence_validator.cli import main as cli

STATUS = {0: "admitted", 1: "rejected", 2: "review_required"}
ICON = {"admitted": "✅", "review_required": "🟡", "rejected": "❌", "error": "⚠️"}


def matched(patterns: str) -> list[str]:
    paths = {path for pattern in patterns.split() for path in glob.glob(pattern, recursive=True)}
    return sorted(Path(path).as_posix() for path in paths if Path(path).is_file())


def run(*args: str) -> tuple[int, str]:
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
        code = cli(list(args))
    try:
        message = json.loads(stderr.getvalue())["message"]
    except (ValueError, KeyError, TypeError):
        message = stderr.getvalue().strip()
    return code, message


def check(path: str, profile: str, draft: bool, workdir: Path) -> tuple[str, str]:
    record = path
    if draft:
        record = str(workdir / "record.json")
        code, message = run("build", path, "--output", record)
        if code:
            return "error", message
    report = workdir / "report.json"
    code, message = run("validate", record, "--profile", profile, "--output", str(report))
    if code not in STATUS:
        return "error", message
    decisions = json.loads(report.read_text(encoding="utf-8"))["use_decisions"]
    detail = "; ".join(f"{d['use']}: {d['admission_status']}" + (f" ({', '.join(d['reason_codes'])})" if d["reason_codes"] else "")
                       for d in decisions)
    return STATUS[code], detail


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", required=True)
    parser.add_argument("--profile", default="general")
    parser.add_argument("--format", choices=["record", "draft"], default="record")
    parser.add_argument("--fail-on", choices=["review", "rejected"], default="review")
    args = parser.parse_args()

    paths = matched(args.files)
    if not paths:
        print(f"::error::No files matched: {args.files}")
        return 1
    rows = []
    for path in paths:
        with tempfile.TemporaryDirectory() as directory:
            status, detail = check(path, args.profile, args.format == "draft", Path(directory))
        rows.append((path, status, detail))
        failing = status in {"rejected", "error"} or (args.fail_on == "review" and status == "review_required")
        level = "error" if failing else "notice" if status != "admitted" else None
        if level:
            print(f"::{level} file={path}::{status}: {detail}")
        print(f"{ICON[status]} {path}: {status}" + (f" — {detail}" if detail else ""))

    counts = {status: sum(row[1] == status for row in rows) for status in ICON}
    lines = [f"### BioAI evidence validation (`{args.profile}` profile)", "",
             " · ".join(f"{ICON[s]} {s}: {n}" for s, n in counts.items()), "",
             "| File | Status | Decisions |", "|---|---|---|"]
    lines += [f"| `{path}` | {ICON[status]} {status} | {detail.replace('|', '/')} |" for path, status, detail in rows]
    for variable, text in [("GITHUB_STEP_SUMMARY", "\n".join(lines) + "\n"),
                           ("GITHUB_OUTPUT", "".join(f"{s}={n}\n" for s, n in counts.items()))]:
        if os.environ.get(variable):
            with open(os.environ[variable], "a", encoding="utf-8") as handle:
                handle.write(text)
    failed = counts["rejected"] + counts["error"] + (counts["review_required"] if args.fail_on == "review" else 0)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
