"""Local MCP consumption followed by independent, read-only evidence validation.

The MCP response is an additional object to verify, never a substitute for the
source-bound publication and original-page review checks in EvidenceLibraryGrounder.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import math
import re
import shutil
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from .engine import RecordValidator, default_schema_path, profile_path
from .evidence_library import EvidenceLibraryGrounder
from .grounding import finding

GET_TOOL = "evidport_evidence_get"
CHECK_TOOL = "evidport_evidence_check_quote"
CITATION = re.compile(r"evidence:cv_[0-9a-f]{64}#[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}")
MAX_RECORD_BYTES = 8 * 1024 * 1024
MAX_RESULT_BYTES = 1024 * 1024
MAX_ITEMS = 100


def _unique(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number: {value}")


def _read_json(path: Path) -> Any:
    with path.open("rb") as stream:
        data = stream.read(MAX_RECORD_BYTES + 1)
    if len(data) > MAX_RECORD_BYTES:
        raise ValueError("JSON input exceeds the 8 MiB local bridge limit")
    return json.loads(data.decode("utf-8-sig"), object_pairs_hook=_unique, parse_constant=_invalid_constant)


def _connection_config(command: str, args: list[str], cwd: Path | None, env: dict | None) -> dict:
    if not isinstance(command, str) or not command.strip() or "\0" in command or "://" in command:
        raise ValueError("A local executable is required; remote MCP transports are not supported")
    if not isinstance(args, list) or any(not isinstance(arg, str) or "\0" in arg for arg in args):
        raise ValueError("MCP args must be a list of strings without NUL characters")
    if len(args) > 100 or sum(len(arg) for arg in args) > 32768:
        raise ValueError("MCP subprocess arguments exceed the local configuration limit")
    executable = Path(command)
    if not executable.is_absolute():
        located = shutil.which(command)
        if not located:
            raise ValueError("Configured MCP executable was not found")
        executable = Path(located)
    if not executable.is_file():
        raise ValueError("Configured MCP executable does not exist")
    directory = Path(cwd).resolve() if cwd is not None else None
    if directory is not None and not directory.is_dir():
        raise ValueError("Configured MCP cwd must be an existing directory")
    environment = {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    if env is not None:
        if not isinstance(env, dict) or any(environment.get(key) != value for key, value in env.items()):
            raise ValueError("Only PYTHONIOENCODING=utf-8 and PYTHONUTF8=1 may be configured")
    return {"command": str(executable.resolve()), "args": list(args), "cwd": directory, "env": environment}


def load_server_config(path: Path) -> dict:
    """Read a user-owned local stdio configuration, never an agent tool argument."""
    path = Path(path).resolve()
    config = _read_json(path)
    if not isinstance(config, dict) or set(config) - {"command", "args", "cwd", "env"}:
        raise ValueError("Server configuration accepts only command, args, cwd and the two UTF-8 env fields")
    command = config.get("command")
    arguments = config.get("args")
    if not isinstance(command, str) or not isinstance(arguments, list):
        raise ValueError("Server configuration requires a command string and args array")
    if isinstance(command, str) and not Path(command).is_absolute() and any(c in command for c in ("/", "\\")):
        command = str((path.parent / command).resolve())
    cwd = config.get("cwd")
    if cwd is not None:
        if not isinstance(cwd, str) or not cwd:
            raise ValueError("MCP cwd must be a nonempty path string")
        cwd = (path.parent / cwd).resolve()
    return _connection_config(command, arguments, cwd, config.get("env"))


@asynccontextmanager
async def _stdio_client(config: dict) -> AsyncIterator[Any]:
    try:
        sdk = importlib.import_module("mcp")
    except ImportError as exc:
        raise ValueError("Install the pinned optional MCP dependency to use the local evidence bridge") from exc
    server = sdk.StdioServerParameters(**config)
    async with sdk.Client(server) as client:
        yield client


class _ProtocolError(ValueError):
    pass


def _payload(result: Any) -> dict:
    if getattr(result, "is_error", None) is not False:
        raise _ProtocolError("MCP tool returned an error or omitted its error status")
    payload = getattr(result, "structured_content", None)
    if not isinstance(payload, dict):
        raise _ProtocolError("MCP tool must return a structured JSON object; text fallback is not accepted")
    try:
        encoded = json.dumps(payload, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise _ProtocolError("MCP result is not finite JSON") from exc
    if len(encoded) > MAX_RESULT_BYTES:
        raise _ProtocolError("MCP result exceeds the 1 MiB bridge limit")
    return json.loads(encoded)


def _compare(received: dict, expected: dict, *, label: str) -> None:
    for key, value in expected.items():
        # Python containers equate True, 1 and 1.0; source-bound JSON does not.
        if key not in received or json.dumps(received[key], sort_keys=True, allow_nan=False) != json.dumps(
            value, sort_keys=True, allow_nan=False
        ):
            raise _ProtocolError(f"MCP {label} disagrees with the local evidence library: {key}")


def _compare_item(retrieved: dict, checked: dict, original: dict, local_check: dict) -> None:
    source, block = original["source"], original["block"]
    native_locator = block["locator"]
    locator = {key: native_locator[key] for key in ("page", "pages", "bbox", "unlocated") if key in native_locator}
    if "regions" in native_locator:
        locator["regions"] = [{key: region[key] for key in ("page", "bbox") if key in region}
                              for region in native_locator["regions"]]
    locator_sha256 = hashlib.sha256(json.dumps(native_locator, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    binding = {"citation": original["citation"], "source_id": source["source_id"],
               "source_sha256": source["sha256"], "conversion_id": original["conversion_id"],
               "locator": locator, "locator_sha256": locator_sha256, "scientifically_verified": False}
    _compare(retrieved, {**binding, "document_id": source["document_id"]}, label="retrieval")
    text = retrieved.get("text")
    truncated = retrieved.get("text_truncated")
    if not isinstance(text, str) or type(truncated) is not bool:
        raise _ProtocolError("MCP retrieval must label its text and truncation state")
    _compare(retrieved, {"text_characters": len(block["text"])}, label="retrieval")
    if truncated:
        if not text or len(text) >= len(block["text"]) or not block["text"].startswith(text):
            raise _ProtocolError("MCP truncated text is not the exact declared block prefix")
    elif text != block["text"]:
        raise _ProtocolError("MCP full text differs from the exact archived block")
    nested = retrieved.get("source")
    if not isinstance(nested, dict):
        raise _ProtocolError("MCP retrieval omitted the structured source identity")
    _compare(nested, {key: source[key] for key in ("source_id", "sha256", "document_id", "role")}, label="source")
    _compare(checked, binding, label="quote check")
    _compare(checked, {key: local_check[key] for key in (
        "quote", "quote_matches", "admitted", "reason", "review_status", "review_id")}, label="quote check")


class _BridgeGrounder:
    name = "evidport-mcp-local-comparison"

    def __init__(self, errors: list[tuple[str, str, str]]):
        self.errors = errors

    def check(self, record: dict) -> list:
        return [finding(record, rule, message, path) for rule, message, path in self.errors]


async def validate_via_mcp(record: Any, *, command: str, args: list[str], library_path: Path,
                           cwd: Path | None = None, env: dict | None = None, timeout: float = 60,
                           profile: str | Path = "literature-claim", schema_path: Path | None = None) -> dict:
    """Read exact citations over stdio MCP, then validate against the local originals.

    Connections/configuration are supplied by the local operator. The remote tool
    response cannot replace local source hashing, publication identity or human review.
    Every transport/protocol disagreement blocks admission for the complete record.
    """
    encoded = json.dumps(record, allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_RECORD_BYTES:
        raise ValueError("Record exceeds the 8 MiB local bridge limit")
    record = json.loads(encoded)
    validator = RecordValidator(profile=profile, schema_path=schema_path)
    preflight = validator.validate(record)
    metadata: dict = {"contract_version": 1, "transport": "stdio", "status": "not_attempted",
                      "checks": [], "scientifically_verified": False,
                      "admission_authority": "local-source-and-original-page-review"}
    if any(item["severity"] == "error" for item in preflight["findings"]):
        return {**preflight, "evidence_mcp": {**metadata, "status": "invalid_record"}}
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 300:
        raise ValueError("MCP timeout must be a finite number greater than 0 and at most 300 seconds")
    config = _connection_config(command, args, cwd, env)
    errors: list[tuple[str, str, str]] = []
    local: EvidenceLibraryGrounder | None = None
    if len(record["evidence_items"]) > MAX_ITEMS:
        errors.append(("BEV014", "Record exceeds the 100-item local MCP bridge limit", "$.evidence_items"))
    try:
        local = EvidenceLibraryGrounder(Path(library_path))
    except (ValueError, OSError) as exc:
        errors.append(("BEV014", "Local evidence library is unavailable: " + str(exc), "$.evidence_items"))
    if local is not None and not errors:
        try:
            async with asyncio.timeout(timeout), _stdio_client(config) as client:
                retrieved_cache: dict[str, dict] = {}
                checked_cache: dict[tuple[str, str], dict] = {}
                for index, item in enumerate(record["evidence_items"]):
                    citation, quote = item.get("locator", ""), item.get("extracted_text", "")
                    path = f"$.evidence_items[{index}]"
                    if not CITATION.fullmatch(citation) or not quote.strip():
                        errors.append(("BEV015", "An exact library citation and quotation are required", path))
                        continue
                    try:
                        if citation not in retrieved_cache:
                            retrieved_cache[citation] = _payload(await client.call_tool(GET_TOOL, {"citation": citation}))
                        key = citation, quote
                        if key not in checked_cache:
                            checked_cache[key] = _payload(await client.call_tool(
                                CHECK_TOOL, {"citation": citation, "quote": quote}))
                        original = local.store.get(citation)
                        checked = local.store.check(citation, quote, require_review=True)
                        _compare_item(retrieved_cache[citation], checked_cache[key], original, checked)
                        metadata["checks"].append({"evidence_item_id": item["id"], "citation": citation,
                            "source_sha256": original["source"]["sha256"], "conversion_id": original["conversion_id"],
                            "locator": original["block"]["locator"], "mcp_matches_local": True,
                            "block_issues": original["block"].get("issues", []),
                            "conversion_issues": original.get("conversion_issues", []),
                            "conversion_status": original.get("conversion_status"),
                            "quote_matches": checked["quote_matches"], "admitted": checked["admitted"],
                            "reason": checked["reason"], "scientifically_verified": False})
                    except _ProtocolError as exc:
                        errors.append(("BEV017", str(exc), path))
                    except (ValueError, OSError, KeyError, TypeError) as exc:
                        errors.append(("BEV014", "MCP/local comparison failed: " + str(exc), path))
        except Exception as exc:
            errors.append(("BEV014", f"Local MCP session failed ({type(exc).__name__}); no transport fallback",
                           "$.evidence_items"))
        metadata["status"] = "comparison_failed" if errors else "completed"
    elif errors:
        metadata["status"] = "unavailable"
    grounders: list = [local] if local is not None else []
    grounders.append(_BridgeGrounder(errors))
    validator.grounders = grounders
    report = validator.validate(record)
    report["evidence_mcp"] = metadata
    if local is not None:
        report["evidence_library"] = {"contract_version": 1, "checks": local.last_checks,
                                      "scientifically_verified": False}
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check local MCP evidence against the original EvidPort library")
    parser.add_argument("--server-config", type=Path, required=True)
    parser.add_argument("--evidence-library", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--profile", default="literature-claim")
    parser.add_argument("--schema", type=Path)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    protected = [args.server_config, args.record, args.schema or default_schema_path(), profile_path(args.profile)]
    if args.output is not None:
        destination = args.output.resolve()
        if destination in {path.resolve() for path in protected}:
            parser.error("Output must not overwrite configuration, record, schema or profile")
        if destination.is_relative_to(args.evidence_library.resolve()):
            parser.error("Output must be outside the read-only evidence library")
    try:
        config = load_server_config(args.server_config)
        report = asyncio.run(validate_via_mcp(_read_json(args.record), library_path=args.evidence_library,
            timeout=args.timeout, profile=args.profile, schema_path=args.schema, **config))
    except (OSError, ValueError, RecursionError) as exc:
        parser.error(str(exc))
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 1 if report["overall_status"] == "rejected" else 2 if report["overall_status"] == "review_required" else 0


if __name__ == "__main__":
    sys.exit(main())
