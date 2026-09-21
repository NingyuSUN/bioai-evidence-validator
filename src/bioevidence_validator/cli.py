from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import yaml

from .canine_panel_adapter import export_canine_panel
from .engine import default_policy_path, default_schema_path, generate_json_schema, validate_record


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="bioevidence")
    commands = result.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate one canine breed evidence record")
    validate.add_argument("input", type=Path)
    validate.add_argument("--output", type=Path)
    validate.add_argument("--schema", type=Path, default=default_schema_path())
    validate.add_argument("--policy", type=Path, default=default_policy_path())
    generate = commands.add_parser("generate-schema", help="Generate JSON Schema from LinkML")
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--schema", type=Path, default=default_schema_path())
    export = commands.add_parser("export-canine-panel", help="Export and validate an existing canine-panel SQLite database")
    export.add_argument("database", type=Path)
    export.add_argument("--manifest", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--limit", type=int)
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
        if args.output.resolve() == args.schema.resolve():
            raise ValueError("Output must not overwrite the schema")
        _write_json(args.output, generate_json_schema(args.schema))
        return 0

    if args.command == "export-canine-panel":
        summary = export_canine_panel(args.database, args.manifest, args.output, limit=args.limit)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    if args.output and args.output.resolve() in {p.resolve() for p in [args.input, args.schema, args.policy]}:
        raise ValueError("Output must not overwrite an input, schema, or policy")
    record = json.loads(args.input.read_text(encoding="utf-8"),
                        object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    report = validate_record(record, schema_path=args.schema, policy_path=args.policy)
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


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return _run(args)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError, sqlite3.Error) as exc:
        print(json.dumps({"error": "input_or_execution_error", "message": str(exc)}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
