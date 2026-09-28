from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import yaml

from . import review as review_module
from .draft import build_record, draft_json_schema, load_draft
from .engine import default_schema_path, generate_json_schema, list_profiles, profile_path, validate_record


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="bioevidence")
    commands = result.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate one biological evidence record")
    validate.add_argument("input", type=Path)
    validate.add_argument("--output", type=Path)
    validate.add_argument("--schema", type=Path, default=default_schema_path())
    validate.add_argument("--profile", default="general", help="Built-in profile name or YAML file path")
    build = commands.add_parser("build", help="Expand a compact YAML/JSON draft into a full record")
    build.add_argument("draft", type=Path)
    build.add_argument("--output", type=Path)
    draft_schema = commands.add_parser("draft-schema", help="JSON Schema for drafts under one profile")
    draft_schema.add_argument("--profile", default="general", help="Built-in profile name or YAML file path")
    draft_schema.add_argument("--output", type=Path)
    generate = commands.add_parser("generate-schema", help="Generate JSON Schema from LinkML")
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--schema", type=Path, default=default_schema_path())
    commands.add_parser("profiles", help="List built-in profiles and their use contracts")

    review = commands.add_parser("review", help="Independent human review: agreement, adjudication, scoring")
    steps = review.add_subparsers(dest="step", required=True)
    check = steps.add_parser("check", help="Check annotations (and adjudications) against the protocol format")
    check.add_argument("annotations", type=Path)
    check.add_argument("--adjudications", type=Path)
    agree = steps.add_parser("agreement", help="Inter-reviewer agreement per use, before adjudication")
    agree.add_argument("annotations", type=Path)
    agree.add_argument("--output", type=Path)
    sheet = steps.add_parser("adjudication-sheet", help="Blank adjudication rows for every disagreement")
    sheet.add_argument("annotations", type=Path)
    sheet.add_argument("--output", type=Path, required=True)
    sheet.add_argument("--min-reviewers", type=int, default=2)
    scoring = steps.add_parser("score", help="Compare predictions with the resolved reference labels")
    scoring.add_argument("--annotations", type=Path, required=True)
    scoring.add_argument("--adjudications", type=Path, required=True)
    scoring.add_argument("--predictions", type=Path, required=True)
    scoring.add_argument("--split", default="test", choices=sorted(review_module.SPLITS))
    scoring.add_argument("--min-reviewers", type=int, default=2)
    scoring.add_argument("--output", type=Path)
    frozen = steps.add_parser("freeze", help="Write a frozen manifest for a completed reference set")
    frozen.add_argument("--manifest", type=Path, required=True, help="Draft manifest to complete")
    frozen.add_argument("--annotations", type=Path, required=True)
    frozen.add_argument("--adjudications", type=Path, required=True)
    frozen.add_argument("--file", type=Path, action="append", default=[], help="Extra file to hash (repeatable)")
    frozen.add_argument("--dataset-id", required=True)
    frozen.add_argument("--version", required=True)
    frozen.add_argument("--frozen-at", required=True, help="ISO 8601 time of the freeze")
    frozen.add_argument("--min-reviewers", type=int, default=2)
    frozen.add_argument("--output", type=Path, required=True)
    return result


def _unique_object(pairs):
    record = {}
    for key, value in pairs:
        if key in record:
            raise ValueError(f"Duplicate JSON key: {key!r}")
        record[key] = value
    return record


def _invalid_constant(value):
    raise ValueError(f"Non-finite JSON constant is not supported: {value}")


MAX_JSON_DEPTH = 100


def _check_depth(value) -> None:
    """Reject over-nested input explicitly; the parser's own recursion limit varies by platform."""
    stack = [(value, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > MAX_JSON_DEPTH:
            raise ValueError(f"JSON nesting exceeds {MAX_JSON_DEPTH} levels")
        children = node.values() if isinstance(node, dict) else node if isinstance(node, list) else ()
        stack.extend((child, depth + 1) for child in children if isinstance(child, (dict, list)))


def _write_json(path: Path, value: dict) -> None:
    """Replace the report only after the complete UTF-8 payload is written."""
    payload = json.dumps(value, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=path.parent, delete=False) as handle:
            temp_path = Path(handle.name)
            handle.write(payload)
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _run(args) -> int:
    if args.command == "generate-schema":
        if args.output.resolve() in {args.schema.resolve(), default_schema_path().resolve()}:
            raise ValueError("Output must not overwrite the schema")
        _write_json(args.output, generate_json_schema(args.schema))
        return 0

    if args.command == "profiles":
        print(json.dumps(list_profiles(), indent=2))
        return 0

    if args.command == "review":
        return _review(args)

    if args.command in {"build", "draft-schema"}:
        if args.command == "build":
            if args.output and args.output.resolve() == args.draft.resolve():
                raise ValueError("Output must not overwrite the draft")
            draft = load_draft(args.draft)
            _check_depth(draft)
            result = build_record(draft, base_dir=args.draft.parent)
        else:
            result = draft_json_schema(args.profile)
        if args.output:
            _write_json(args.output, result)
        else:
            print(json.dumps(result, indent=2))
        return 0

    selected_profile = profile_path(args.profile)
    protected = [args.input, args.schema, selected_profile, default_schema_path()]
    if args.output and args.output.resolve() in {p.resolve() for p in protected}:
        raise ValueError("Output must not overwrite an input, schema, or profile")
    record = json.loads(args.input.read_text(encoding="utf-8"),
                        object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    _check_depth(record)
    report = validate_record(record, schema_path=args.schema, profile=args.profile)
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        _write_json(args.output, report)
    else:
        print(rendered, end="")
    if report["overall_status"] == "rejected":
        return 1
    if report["overall_status"] == "review_required":
        return 2
    return 0


def _review(args) -> int:
    rv = review_module
    annotations = rv.load_annotations(args.annotations)
    if args.step == "check":
        adjudications = rv.load_adjudications(args.adjudications, annotations) if args.adjudications else []
        units = {(a["case_id"], a["requested_use"]) for a in annotations}
        print(f"OK: {len(annotations)} annotations, {len(units)} case-use units, "
              f"{len({a['reviewer_id'] for a in annotations})} reviewers, {len(adjudications)} adjudications")
        return 0
    if args.step == "agreement":
        report = rv.agreement(annotations)
        if args.output:
            _write_json(args.output, report)
        print(rv.render_agreement(report), end="")
        return 0
    if args.step == "adjudication-sheet":
        if args.output.exists():
            raise ValueError(f"{args.output} exists; refusing to overwrite adjudication work")
        rows, incomplete = rv.adjudication_sheet(annotations, min_reviewers=args.min_reviewers)
        rv.write_csv(args.output, rows, rv.ADJUDICATION_COLUMNS)
        print(f"{len(rows)} disagreement(s) to adjudicate; {len(incomplete)} unit(s) with too few reviews")
        return 0
    adjudications = rv.load_adjudications(args.adjudications, annotations)
    final = rv.resolve(annotations, adjudications, min_reviewers=args.min_reviewers)
    if args.step == "score":
        report = rv.score(final, rv.load_predictions(args.predictions), split=args.split)
        if args.output:
            _write_json(args.output, report)
        print(rv.render_score(report), end="")
        return 0
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    files = [args.annotations, args.adjudications, *args.file]
    if args.output.resolve() in {f.resolve() for f in [args.manifest, *files]}:
        raise ValueError("Output must not overwrite an input")
    frozen = rv.freeze(manifest, final, annotations, files, dataset_id=args.dataset_id,
                       version=args.version, frozen_at=args.frozen_at)
    _write_json(args.output, frozen)
    print(f"Frozen {frozen['reviewed_case_use_count']} case-use labels from "
          f"{frozen['independent_human_reviewer_count']} reviewers ({frozen['reference_type']})")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return _run(args)
    except (OSError, UnicodeError, ValueError, RecursionError, yaml.YAMLError) as exc:
        print(json.dumps({"error": "input_or_execution_error", "message": str(exc)}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
