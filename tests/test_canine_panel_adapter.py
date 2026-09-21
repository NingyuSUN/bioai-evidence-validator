import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
import yaml

from bioevidence_validator.canine_panel_adapter import export_canine_panel, sha256_file


def make_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript("""
        CREATE TABLE source_records (
          record_key TEXT PRIMARY KEY,
          source TEXT NOT NULL,
          source_raw_labels TEXT NOT NULL,
          source_concept_id TEXT NOT NULL,
          source_name_status TEXT NOT NULL,
          candidate_concept_ids TEXT NOT NULL,
          audit_source_genotype_membership_rechecked TEXT NOT NULL
        );
        CREATE TABLE concepts (
          source_concept_id TEXT PRIMARY KEY,
          source_name TEXT NOT NULL,
          source_obsolete_flag TEXT NOT NULL DEFAULT 'False',
          source_scope_flags TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE name_link_overrides (
          record_key TEXT PRIMARY KEY,
          rule_id TEXT NOT NULL,
          selected_concept_id TEXT,
          name_link_status TEXT,
          rationale TEXT
        );
        CREATE VIEW resolved_source_names AS
          SELECT sr.record_key, sr.source, sr.source_raw_labels,
          COALESCE(n.selected_concept_id, sr.source_concept_id) AS source_concept_id,
          COALESCE(n.name_link_status, sr.source_name_status) AS name_link_status,
          n.rule_id
          FROM source_records sr LEFT JOIN name_link_overrides n USING(record_key);
        INSERT INTO concepts VALUES
          ('VBO:LAB', 'Labrador Retriever', 'False', ''),
          ('VBO:BOX', 'Boxer', 'False', '');
        INSERT INTO source_records VALUES
          ('Dog10K:labrador-1', 'Dog10K', 'Labrador Retriever', 'VBO:LAB', 'UNIQUE_SOURCE_CONCEPT', 'VBO:LAB', 'True'),
          ('Dog10K:boxer-1', 'Dog10K', 'Boxer', '', 'RAW_LABEL_AMBIGUOUS_SOURCE_CONCEPT', 'VBO:BOX;VBO:REGIONAL_BOX', 'True'),
          ('Dog10K:unknown-1', 'Dog10K', 'Unknown Dog', '', 'NO_EXACT_SOURCE_CONCEPT', '', 'True'),
          ('Dog10K:missing-1', 'Dog10K', 'Missing Concept', 'VBO:MISSING', 'UNIQUE_SOURCE_CONCEPT', 'VBO:MISSING', 'True');
        INSERT INTO name_link_overrides VALUES
          ('Dog10K:boxer-1', 'rule-boxer', 'VBO:BOX', 'RESOLVED_SOURCE_SCOPED_NAME', 'Official scope review retained.');
        """)


def make_manifest(path: Path, expected_hash: str | None = None) -> None:
    data = {
        "database_title": "Synthetic canine breed inventory",
        "database_version": "synthetic-v1",
        "retrieved_at": "2026-09-17T00:00:00Z",
        "ontology": "VBO",
        "ontology_version": "synthetic-vbo-snapshot",
        "concept_status_default": "current",
        "breed_scope_default": "breed",
        "source_scope_hint_default": "breed",
        "requested_uses_default": ["source_sample_mapping"],
    }
    if expected_hash:
        data["expected_database_sha256"] = expected_hash
    path.write_text(yaml.safe_dump(data, sort_keys=True))


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_export_is_read_only_and_preserves_unresolved_ledger(tmp_path):
    database = tmp_path / "canine.sqlite"
    manifest = tmp_path / "manifest.yaml"
    output = tmp_path / "export"
    make_database(database)
    before = sha256_file(database)
    make_manifest(manifest, before)

    summary = export_canine_panel(database, manifest, output)

    assert sha256_file(database) == before
    assert summary["database_unchanged"] is True
    assert summary["input_records_considered"] == 4
    assert summary["exported_records"] == 2
    assert summary["skipped_records"] == 2
    assert summary["skip_reasons"] == {
        "SELECTED_CONCEPT_MISSING_FROM_CATALOG": 1,
        "UNRESOLVED_NO_SELECTED_CONCEPT": 1,
    }
    assert len(read_jsonl(output / "records.jsonl")) == 2
    assert len(read_jsonl(output / "skipped.jsonl")) == 2


def test_override_is_exported_but_not_silently_treated_as_human_acceptance(tmp_path):
    database = tmp_path / "canine.sqlite"
    manifest = tmp_path / "manifest.yaml"
    output = tmp_path / "export"
    make_database(database)
    make_manifest(manifest)

    export_canine_panel(database, manifest, output)
    reports = {row["record_id"]: row for row in read_jsonl(output / "validation_reports.jsonl")}
    records = read_jsonl(output / "records.jsonl")
    boxer = next(row for row in records if row["statement"]["subject_label"]["value"] == "Boxer")
    report = reports[boxer["record_id"]]
    assert report["overall_status"] == "review_required"
    assert {"CBR004", "CBR010"} <= {item["rule_id"] for item in report["findings"]}
    assert boxer["adjudications"] == []


def test_hash_mismatch_fails_before_output_creation(tmp_path):
    database = tmp_path / "canine.sqlite"
    manifest = tmp_path / "manifest.yaml"
    output = tmp_path / "export"
    make_database(database)
    make_manifest(manifest, "0" * 64)
    with pytest.raises(ValueError, match="Database hash differs"):
        export_canine_panel(database, manifest, output)
    assert not output.exists()


def test_existing_output_directory_is_never_overwritten(tmp_path):
    database = tmp_path / "canine.sqlite"
    manifest = tmp_path / "manifest.yaml"
    output = tmp_path / "export"
    make_database(database)
    make_manifest(manifest)
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("unchanged")
    with pytest.raises(ValueError, match="must not already exist"):
        export_canine_panel(database, manifest, output)
    assert sentinel.read_text() == "unchanged"
