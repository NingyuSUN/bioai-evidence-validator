from __future__ import annotations

import argparse
import json
from pathlib import Path

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


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "generate-schema":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(generate_json_schema(args.schema), indent=2) + "\n")
        return 0

    if args.command == "export-canine-panel":
        summary = export_canine_panel(args.database, args.manifest, args.output, limit=args.limit)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    record = json.loads(args.input.read_text())
    report = validate_record(record, schema_path=args.schema, policy_path=args.policy)
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    if report["overall_status"] == "rejected":
        return 1
    if report["overall_status"] == "review_required":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
