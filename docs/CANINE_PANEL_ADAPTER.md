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

The database is opened with SQLite URI `mode=ro` and `PRAGMA query_only=ON`.
Its SHA-256 is computed before and after export. A changed input aborts the run.

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
