# Canine-panel read-only adapter

## Purpose

The adapter converts the current private canine breed SQLite inventory into
`CanineBreedRecord` objects without changing the database. It is a translation
and validation boundary, not a new source of biological truth.

## Required database contract

The adapter requires:

- `source_records` with record key, source label, candidate concepts, and the
  existing resolution status;
- `concepts` with stable concept identifier and source name;
- `resolved_source_names`, preserving source-scoped overrides;
- optional `name_link_overrides`, used as evidence of an existing reviewed rule.

The database is opened with SQLite URI `mode=ro&immutable=1`,
`PRAGMA query_only=ON`, and a read transaction. Use a standalone, closed snapshot:
WAL, SHM and rollback-journal sidecars are rejected before access and again after
validation. The adapter never checkpoints, deletes sidecars, or modifies the
source database. Its SHA-256 is checked before and after export; a detected
change aborts before any output directory is created.

All four tables/views must have unique nonblank identity keys. Duplicate
source, concept, resolution or override IDs abort instead of silently retaining
the last row. `resolved_source_names` must expose `record_key` and
`source_concept_id`; an override table must expose `record_key`.
Known boolean spellings are parsed explicitly; unknown values fail instead of
being treated as false. Resolved rows scoped to a different source are skipped
with `RESOLVED_SOURCE_SCOPE_MISMATCH`.

## Deliberate non-inferences

- A `name_link_overrides` row is not converted into a completed human
  adjudication because the current table does not contain reviewer identity and
  decision time.
- A missing selected concept is not guessed from the first candidate.
- A selected concept absent from the concept catalog is not fabricated.
- Unknown genotype membership is not interpreted as verified.
- The local database path is not written into exported evidence; the immutable
  database is identified using a SHA-256 URN.

Skipped rows are retained in `skipped.jsonl` with machine-readable reasons.

## Outputs

- `records.jsonl`: exported schema-validatable records;
- `validation_reports.jsonl`: policy findings and use decisions;
- `skipped.jsonl`: records that could not be represented safely;
- `manifest.snapshot.yaml`: exact export assumptions;
- `summary.json`: input/output hashes and counts.

The output directory must be new, preventing accidental overwrite of a prior
validation run.

## Manifest and completion

Required nonblank text fields are `database_title`, `database_version`,
`retrieved_at` (RFC 3339 string), and `ontology_version`. Optional fields are
`ontology`, `expected_database_sha256`, `concept_status_default`,
`breed_scope_default`, `source_scope_hint_default`, `requested_uses_default`,
and `requested_uses_by_source`. Unknown or duplicate keys and malformed enums,
use lists or hashes fail before output creation. Quote YAML timestamps.

The selected concept comes from the resolved view; it is retained alongside
original candidates in the exported candidate set. Source-row and resolved-row
evidence preserve the original candidates and selection for audit. This does
not constitute human acceptance or verification of biological membership.

A single validator context is used across the export. The summary includes
policy/schema hashes, total input rows, limit, considered rows, exported/skipped
counts and output hashes. `summary.json` with `status: complete` is the final
completion marker. Partial directories without it are failed runs; do not use
them as completed exports or overwrite them on retry.
