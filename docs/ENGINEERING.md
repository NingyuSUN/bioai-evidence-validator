# Engineering contract

## Deterministic admission with explicit failure states

The LinkML schema checks structure; versioned rules check supplied evidence; the
engine decides each requested use. The package does not establish biological
truth, genotype membership or reviewer identity on its own.

Record-wide structural errors and ambiguous duplicate evidence identifiers block
all use decisions. Requested uses must be a nonempty list of distinct supported
values. A JSON object with no valid requested uses cannot be admitted. Evidence
and source collections and their reference lists are required, not optional
inputs silently defaulted to empty evidence.

An invalid record produces an audit report. A malformed JSON document, missing
file, invalid policy configuration or I/O failure is an operational error.
The validation CLI returns 0 for admission, 1 for rejection, 2 for required
review and 3 for operational errors. Argument syntax errors use argparse's code 2
and do not produce a validation report. Export success means that the export
completed, not that its records were admitted.

Input JSON rejects duplicate keys and non-finite constants. Files use UTF-8;
report writes replace the destination only after a complete temporary file has
been written. An output path cannot overwrite the input, schema or policy.

## Reproducibility and verification

```bash
uv sync --frozen --extra dev
uv run --frozen pytest
uv build
uv run --isolated --no-project --with ./dist/bioai_evidence_validator-0.3.0-py3-none-any.whl python tools/check_distribution.py
```

The wheel check runs both documented CLI examples and the invalid-use guard from
an isolated installation, verifying packaged LinkML and policy resources without
an editable-source fallback. CI defines Linux/Python 3.11 and Windows/Python 3.13
jobs using the same commands. A committed workflow is not evidence that a remote
GitHub run has passed; inspect the Actions result after publication.

Regression coverage includes empty/unknown/malformed uses, required evidence,
identifier collisions, schema errors, admission/rejection/review outcomes,
UTF-8, duplicate JSON keys, failed writes and preservation of existing reports.
SQLite adapter tests verify source hashes, read-only export, unresolved-row
accounting and refusal to overwrite output directories.

## Scope and tradeoffs

Human adjudications and source metadata are supplied evidence, not cryptographic
proof. The SQLite adapter requires an immutable standalone snapshot and rejects WAL,
SHM and journal sidecars. A database that is concurrently changing is outside
its contract; detected hash changes abort before publication. Schema and
policy evolution require new fixtures and review of admission semantics.

## Policy 0.2 changes

The original policy 0.1 file is retained. Default policy 0.2 blocks rejected or
superseded statements and human rejections, and requires review for unresolved
concepts or deferred human decisions. An acceptance record cannot cancel a
coexisting rejection or deferral. Conflicting adjudications must be resolved in
a new reviewed evidence record; list order does not decide which judgment wins.
Reports include a hash of the generated schema, including imported definitions.

## Policy 0.3

Default policy 0.3 adds four explicit contracts:

| Rule | Contract | Default outcome |
|---|---|---|
| CBR019 | At least one resolved supporting evidence item | Review when absent |
| CBR020 | Selected concept belongs to the declared candidates | Reject mismatch |
| CBR021 | Predicate agrees with statement type | Reject mismatch |
| CBR022 | Breed relationships are not equivalent sample/frequency labels | Reject those uses |

The supported type/predicate pairs are: `breed_catalog` / `denotes_breed`;
`name_equivalence` / `exact_synonym_of`, `official_rename_of`, `translation_of`;
`source_label_assignment` / `maps_to_breed`, `represented_by`; and
`breed_relationship` / `regional_population_of`, `variety_of`, `related_but_not_equivalent`.
These are this profile's admission rules, not a universal biological ontology.

Only supporting evidence can supply official scope evidence or strengthen a
string-only match. Mixed/extinct `breed_scope` values enforce CBR007 even if a
redundant scope flag is absent. Every evidence item's source must resolve,
including items not used by the statement. Required text and supplied rationale
must contain a non-whitespace character.

Policy YAML rejects duplicate keys, unknown rules/options, incomplete rule
rosters and malformed flag lists. Disabling a known rule explicitly remains a
trusted configuration choice and changes the recorded policy hash. Policies and
custom LinkML schemas are trusted local configuration, not sandboxed programs.
Archived policy 0.1/0.2 files still load with their declared rosters; exact
historical replay also requires the historical engine/schema and environment.

## Batch and extension contracts

`RecordValidator` compiles the effective schema and snapshots the policy once;
`validate_record` remains the single-record convenience API. Custom `--schema`
constraints run in addition to the packaged baseline, so they cannot remove the
structural requirements the policy engine assumes. Reports list each effective
schema's role, version and hash; the combined hash binds their ordered schemas.
A batch keeps its loaded schema/policy even if the configuration file changes.

The adapter snapshots one database in a read transaction, records the source
and resolved-view rows used to choose the concept, and reports total/considered
row counts when `--limit` is supplied. Summary hashes bind each output and all
reports share the batch policy/schema hashes. `summary.json` with
`status: complete` is written last. A write failure may leave partial files,
but does not publish completion; use a fresh directory for a retry.

Hashes establish consistency with supplied inputs, not source authenticity or
independent human review. A complete export can contain rejected records.
