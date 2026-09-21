from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import yaml

from .engine import default_schema_path, generate_json_schema, validate_record, profile_path, list_profiles


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="bioevidence")
    commands = result.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate one biological evidence record")
    validate.add_argument("input", type=Path)
    validate.add_argument("--output", type=Path)
    validate.add_argument("--schema", type=Path, default=default_schema_path())
    validate.add_argument("--profile", default="general", help="Built-in profile name or YAML file path")
    generate = commands.add_parser("generate-schema", help="Generate JSON Schema from LinkML")
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--schema", type=Path, default=default_schema_path())
    commands.add_parser("profiles", help="List built-in profiles and their use contracts")
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
        if args.output.resolve() in {args.schema.resolve(), default_schema_path().resolve()}:
            raise ValueError("Output must not overwrite the schema")
        _write_json(args.output, generate_json_schema(args.schema))
        return 0

    if args.command == "profiles":
        print(json.dumps(list_profiles(), indent=2))
        return 0

    selected_profile = profile_path(args.profile)
    protected = [args.input, args.schema, selected_profile, default_schema_path()]
    if args.output and args.output.resolve() in {p.resolve() for p in protected}:
        raise ValueError("Output must not overwrite an input, schema, or profile")
    record = json.loads(args.input.read_text(encoding="utf-8"),
                        object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
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


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return _run(args)
    except (OSError, UnicodeError, ValueError, RecursionError, yaml.YAMLError) as exc:
        print(json.dumps({"error": "input_or_execution_error", "message": str(exc)}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
