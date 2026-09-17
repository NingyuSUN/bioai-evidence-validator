# bioai-evidence-validator

A standards-aligned validation and policy layer for AI-assisted biological
curation. Version 0.2 focuses on canine breed catalog evidence and includes a
read-only adapter for an existing canine-panel SQLite inventory.

The project separates three questions that are often conflated:

1. **Schema validity** — is the record structurally well formed?
2. **Evidence policy** — is the claim sufficiently supported for this domain?
3. **Use admission** — may the record be used in a catalog, sample mapping,
   training set, or external validation set?

## Current scope

The canine breed profile supports:

- breed catalog statements;
- official aliases, renames, and translations;
- source-specific label assignments;
- regional population, variety, and related-but-not-equivalent relationships;
- immutable source hashes;
- deterministic findings;
- human adjudication;
- use-specific admission decisions.

It does **not** establish breed-identification accuracy, marker suitability, or
independent biological validation.

## Architecture

```text
JSON record
  -> LinkML-derived JSON Schema
  -> versioned canine breed policy
  -> findings
  -> human adjudication
  -> per-use admission decision
```

`bioevidence_core.yaml` provides reusable operational objects.
`canine_breed.yaml` is the first domain profile. The policy file is separate so
that a rule change does not silently redefine the data model.

## Quick start

```bash
uv sync --extra dev

uv run bioevidence validate \
  examples/canine_breed/valid_labrador.json \
  --output validation_report.json

uv run bioevidence generate-schema \
  --output dist/canine_breed.schema.json

uv run bioevidence export-canine-panel canine_breed.sqlite \
  --manifest adapter_manifest.yaml \
  --output validation_run_001

uv run pytest
```

Exit codes:

- `0`: all requested uses admitted;
- `1`: at least one requested use rejected;
- `2`: no rejection, but at least one use requires review.

## Privacy boundary

The repository is designed for public code and synthetic examples. Company
records, sample identifiers, internal paths, frozen source files, and private
adjudications should remain in the private canine project. A future adapter will
export only the structured evidence bundle required by this validator.

The adapter opens SQLite in read-only/query-only mode, hashes the database
before and after export, and refuses to overwrite an existing output directory.
Unresolved records are written to a skipped ledger instead of being guessed or
silently discarded. See `docs/CANINE_PANEL_ADAPTER.md` for the exact contract.

## Standards direction

The core terminology is designed to remain compatible with SEPIO-style
statements/evidence and W3C PROV-style entities and agents. LinkML is the
canonical schema source; generated JSON Schema is a build artifact rather than
a separately maintained model.
