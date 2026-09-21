from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Any

from jsonschema import FormatChecker

from . import __version__
from .engine import ALL_USES, RecordValidator
from .config import load_mapping, nonblank


REQUIRED_TABLES = {"source_records", "concepts", "resolved_source_names"}
REQUIRED_SOURCE_COLUMNS = {
    "record_key",
    "source",
    "source_raw_labels",
    "source_concept_id",
    "source_name_status",
    "candidate_concept_ids",
}
REQUIRED_CONCEPT_COLUMNS = {"source_concept_id", "source_name"}

REQUIRED_RESOLVED_COLUMNS = {"record_key", "source_concept_id"}
SCOPES = {"breed", "regional_population", "variety", "landrace", "mixed_breed", "extinct_breed", "unknown"}


def _uses(value, field):
    if (not isinstance(value, list) or not value
            or any(not isinstance(use, str) or use not in ALL_USES for use in value)
            or len(set(value)) != len(value)):
        raise ValueError(f"{field} must be a nonempty list of distinct supported uses")


def _manifest(data: bytes) -> dict[str, Any]:
    manifest = load_mapping(data, "Adapter manifest")
    required = {"database_title", "database_version", "retrieved_at", "ontology_version"}
    allowed = required | {"ontology", "expected_database_sha256", "concept_status_default", "breed_scope_default",
                          "source_scope_hint_default", "requested_uses_default", "requested_uses_by_source"}
    if set(manifest) - allowed:
        raise ValueError("Unknown adapter manifest fields: " + ", ".join(sorted(set(manifest) - allowed)))
    for field in required | ({"ontology"} if "ontology" in manifest else set()):
        if not nonblank(manifest.get(field)):
            raise ValueError(f"Adapter manifest requires a nonblank string: {field}")
    if not FormatChecker().conforms(manifest["retrieved_at"], "date-time"):
        raise ValueError("Adapter retrieved_at must be an RFC 3339 timestamp")
    if "expected_database_sha256" in manifest and (
            not isinstance(manifest["expected_database_sha256"], str)
            or not re.fullmatch("[0-9a-f]{64}", manifest["expected_database_sha256"])):
        raise ValueError("expected_database_sha256 must contain 64 lowercase hex characters")
    for field, choices in (("concept_status_default", {"current", "obsolete", "unresolved"}),
                           ("breed_scope_default", SCOPES), ("source_scope_hint_default", SCOPES)):
        if field in manifest and (not isinstance(manifest[field], str) or manifest[field] not in choices):
            raise ValueError(f"Invalid adapter manifest enum: {field}")
    if "requested_uses_default" in manifest:
        _uses(manifest["requested_uses_default"], "requested_uses_default")
    by_source = manifest.get("requested_uses_by_source", {})
    if not isinstance(by_source, dict):
        raise ValueError("requested_uses_by_source must be a mapping")
    for source, uses in by_source.items():
        if not nonblank(source):
            raise ValueError("Source keys must be nonblank strings")
        _uses(uses, f"requested_uses_by_source[{source!r}]")
    return manifest


def _require_standalone_snapshot(database: Path) -> None:
    # A main-file hash cannot bind pages still held in a WAL/journal. Never
    # checkpoint or remove sidecars here: the adapter is strictly read-only.
    if any(Path(str(database) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
        raise ValueError("A standalone SQLite snapshot is required; WAL/SHM/journal sidecar detected")


def _index(rows: list[dict[str, Any]], key: str, table: str) -> dict[str, dict[str, Any]]:
    result = {}
    for row in rows:
        identity = row.get(key)
        if not nonblank(identity):
            raise ValueError(f"Invalid or empty {key} in {table}")
        if identity in result:
            raise ValueError(f"Duplicate {key} in {table}: {identity!r}")
        result[identity] = row
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _rows(db: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    return [dict(row) for row in db.execute(f'SELECT * FROM "{table}"')]


def _table_names(db: sqlite3.Connection) -> set[str]:
    return {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}


def _columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}


def _split(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    if isinstance(value, list) and all(nonblank(item) for item in value):
        return [item.strip() for item in value]
    raise ValueError("Expected semicolon-delimited text or a list of nonblank strings")


def _truthy(value: Any) -> bool:
    if value is None:
        return False
    token = str(value).strip().casefold()
    if token in {"true", "1", "yes", "verified", "pass"}:
        return True
    if token in {"false", "0", "no", "unverified", "fail", ""}:
        return False
    raise ValueError(f"Unrecognized boolean evidence value: {value!r}")


def _stable_id(kind: str, value: str) -> str:
    token = hashlib.sha256(value.encode()).hexdigest()[:20]
    return f"bioev:{kind}-{token}"


def _requested_uses(manifest: dict[str, Any], source: str) -> list[str]:
    by_source = manifest.get("requested_uses_by_source", {})
    uses = by_source.get(source, manifest.get("requested_uses_default", ["source_sample_mapping"]))
    _uses(uses, f"requested uses for {source!r}")
    return list(uses)


def _concept_status(concept: dict[str, Any], manifest: dict[str, Any]) -> str:
    for key in ("obsolete", "source_obsolete_flag"):
        if key in concept and _truthy(concept[key]):
            return "obsolete"
    return manifest.get("concept_status_default", "unresolved")


def _scope_flags(concept: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for key in ("scope_flags", "source_scope_flags"):
        result.extend(_split(concept.get(key)))
    if _truthy(concept.get("source_extinct_flag")):
        result.append("extinct")
    if _truthy(concept.get("source_mixed_flag")):
        result.append("mixed")
    return sorted(set(result))


def _make_record(source: dict[str, Any], resolved: dict[str, Any], concept: dict[str, Any],
                 override: dict[str, Any] | None, artifact: dict[str, Any],
                 manifest: dict[str, Any]) -> dict[str, Any]:
    record_key = source["record_key"]
    selected = resolved["source_concept_id"]
    candidates = _split(source.get("candidate_concept_ids"))
    if selected not in candidates:
        candidates.append(selected)
    base = _stable_id("canine-source-record", record_key)
    source_item_id = _stable_id("evidence-source-row", record_key)
    concept_item_id = _stable_id("evidence-concept-row", selected)
    evidence_items = [
        {
            "id": source_item_id,
            "source_artifact_id": artifact["id"],
            "locator": f"source_records:{record_key}",
            "extracted_text": json.dumps({key: source.get(key) for key in (
                "record_key", "source", "source_raw_labels", "source_concept_id",
                "source_name_status", "candidate_concept_ids", "audit_source_genotype_membership_rechecked")},
                sort_keys=True, ensure_ascii=False, allow_nan=False),
            "evidence_type": "source_record_row",
            "extraction_method": "deterministic_parser",
        },
        {
            "id": concept_item_id,
            "source_artifact_id": artifact["id"],
            "locator": f"concepts:{selected}",
            "extracted_text": f"concept_id={selected}; source_name={concept['source_name']}",
            "evidence_type": "canonical_concept_row",
            "extraction_method": "deterministic_parser",
        },
    ]
    resolved_item_id = _stable_id("evidence-resolved-row", record_key)
    evidence_items.append({
        "id": resolved_item_id, "source_artifact_id": artifact["id"],
        "locator": f"resolved_source_names:{record_key}",
        "extracted_text": json.dumps(resolved, sort_keys=True, ensure_ascii=False, allow_nan=False),
        "evidence_type": "resolved_source_name_row", "extraction_method": "deterministic_parser",
    })
    evidence_ids = [source_item_id, concept_item_id, resolved_item_id]
    if override:
        override_item_id = _stable_id("evidence-name-override", record_key)
        evidence_items.append({
            "id": override_item_id,
            "source_artifact_id": artifact["id"],
            "locator": f"name_link_overrides:{record_key}",
            "extracted_text": override.get("rationale") or override.get("rule_id") or "reviewed name override",
            "evidence_type": "reviewed_source_scoped_name_rule",
            "extraction_method": "manual_curation",
        })
        evidence_ids.append(override_item_id)

    verified = _truthy(source.get("audit_source_genotype_membership_rechecked"))
    return {
        "record_id": base,
        "statement": {
            "id": _stable_id("statement", record_key),
            "statement_type": "source_label_assignment",
            "subject_label": {
                "value": source["source_raw_labels"],
                "source_name": source["source"],
                "source_record_ids": [record_key],
                "candidate_concept_ids": candidates,
                "source_scope": [source["source"]],
                "scope_hint": manifest.get("source_scope_hint_default", "breed"),
                "genotype_membership_verified": verified,
            },
            "predicate": "maps_to_breed",
            "object_breed": {
                "concept_id": selected,
                "preferred_name": concept["source_name"],
                "ontology": manifest.get("ontology", selected.split(":", 1)[0]),
                "ontology_version": manifest["ontology_version"],
                "concept_status": _concept_status(concept, manifest),
                "breed_scope": manifest.get("breed_scope_default", "unknown"),
                "scope_flags": _scope_flags(concept),
            },
            "evidence_lines": [{
                "id": _stable_id("evidence-line", record_key),
                "direction": "supports",
                "evidence_item_ids": evidence_ids,
                "rationale": "Read-only replay of the source record, resolved name view, and concept catalog.",
            }],
            "statement_status": "proposed",
            "created_by": {
                "id": "bioev:canine-panel-readonly-adapter",
                "name": "canine-panel read-only adapter",
                "agent_type": "software",
            },
        },
        "source_artifacts": [artifact],
        "evidence_items": evidence_items,
        "adjudications": [],
        "requested_uses": _requested_uses(manifest, source["source"]),
    }


def export_canine_panel(database: Path, manifest_path: Path, output_dir: Path,
                        *, limit: int | None = None) -> dict[str, Any]:
    database = database.resolve()
    manifest_path = manifest_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise ValueError(f"Output directory must not already exist: {output_dir}")
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("limit must be positive")
    manifest_bytes = manifest_path.read_bytes()
    manifest = _manifest(manifest_bytes)
    _require_standalone_snapshot(database)
    validator = RecordValidator()

    before_hash = sha256_file(database)
    expected = manifest.get("expected_database_sha256")
    if expected and expected != before_hash:
        raise ValueError("Database hash differs from expected_database_sha256")
    artifact = {
        "id": f"bioev:canine-database-{before_hash[:20]}",
        "title": manifest["database_title"],
        "source_type": "dataset_snapshot",
        "uri": f"urn:sha256:{before_hash}",
        "version": manifest["database_version"],
        "retrieved_at": manifest["retrieved_at"],
        "sha256": before_hash,
        "observed_sha256": before_hash,
    }

    with closing(sqlite3.connect(database.as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        if db.execute("PRAGMA query_only").fetchone()[0] != 1:
            raise RuntimeError("SQLite connection is not query-only")
        db.execute("BEGIN")
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("SQLite quick_check failed")
        tables = _table_names(db)
        missing_tables = REQUIRED_TABLES - tables
        if missing_tables:
            raise ValueError("Database is missing required tables/views: " + ", ".join(sorted(missing_tables)))
        required_columns = {"source_records": REQUIRED_SOURCE_COLUMNS, "concepts": REQUIRED_CONCEPT_COLUMNS,
                            "resolved_source_names": REQUIRED_RESOLVED_COLUMNS}
        if "name_link_overrides" in tables:
            required_columns["name_link_overrides"] = {"record_key"}
        for table, columns in required_columns.items():
            missing = columns - _columns(db, table)
            if missing:
                raise ValueError(f"Database schema is missing required columns in {table}: " + ", ".join(sorted(missing)))
        source_index = _index(_rows(db, "source_records"), "record_key", "source_records")
        resolved = _index(_rows(db, "resolved_source_names"), "record_key", "resolved_source_names")
        concepts = _index(_rows(db, "concepts"), "source_concept_id", "concepts")
        overrides = (_index(_rows(db, "name_link_overrides"), "record_key", "name_link_overrides")
                     if "name_link_overrides" in tables else {})
        for table, rows, fields in (("source_records", source_index.values(), {"source", "source_raw_labels", "source_name_status"}),
                                    ("concepts", concepts.values(), {"source_name"})):
            for row in rows:
                if any(not nonblank(row.get(field)) for field in fields):
                    raise ValueError(f"Invalid required text in {table}")
        for row in resolved.values():
            selected = row["source_concept_id"]
            if selected is not None and not isinstance(selected, str):
                raise ValueError("Invalid selected concept identifier in resolved_source_names")
        sources = sorted(source_index.values(), key=lambda row: row["record_key"])
        total_records = len(sources)
        if limit is not None:
            sources = sources[:limit]

    records: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for source in sources:
        key = source["record_key"]
        resolution = resolved.get(key)
        selected = resolution.get("source_concept_id") if resolution else None
        if not nonblank(selected):
            skipped.append({"record_key": key, "reason": "UNRESOLVED_NO_SELECTED_CONCEPT"})
            continue
        concept = concepts.get(selected)
        if concept is None:
            skipped.append({"record_key": key, "reason": "SELECTED_CONCEPT_MISSING_FROM_CATALOG"})
            continue
        if resolution.get("source", source["source"]) != source["source"]:
            skipped.append({"record_key": key, "reason": "RESOLVED_SOURCE_SCOPE_MISMATCH"})
            continue
        record = _make_record(source, resolution, concept, overrides.get(key), artifact, manifest)
        records.append(record)
        report = validator.validate(record)
        reports.append({"record_id": record["record_id"], **report})

    _require_standalone_snapshot(database)
    after_hash = sha256_file(database)
    if after_hash != before_hash:
        raise ValueError("Input database changed during export")

    output_dir.mkdir(parents=True)
    payloads = {
        "records.jsonl": b"".join(
            (json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode() for row in records
        ),
        "validation_reports.jsonl": b"".join(
            (json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode() for row in reports
        ),
        "skipped.jsonl": b"".join(
            (json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode() for row in skipped
        ),
        "manifest.snapshot.yaml": manifest_bytes,
    }
    for name, data in payloads.items():
        (output_dir / name).write_bytes(data)

    status_counts = Counter(report["overall_status"] for report in reports)
    skip_counts = Counter(row["reason"] for row in skipped)
    summary = {
        "status": "complete",
        "adapter": "canine-panel-readonly",
        "total_input_records": total_records,
        "limit": limit,
        "policy_sha256": validator.policy_sha256,
        "schema_sha256": validator.schema_sha256,
        "adapter_version": __version__,
        "database_sha256": before_hash,
        "database_unchanged": True,
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "input_records_considered": len(sources),
        "exported_records": len(records),
        "skipped_records": len(skipped),
        "validation_statuses": dict(sorted(status_counts.items())),
        "skip_reasons": dict(sorted(skip_counts.items())),
        "outputs": {name: sha256_bytes(data) for name, data in payloads.items()},
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    return summary
