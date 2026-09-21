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
uv run --isolated --no-project --with ./dist/bioai_evidence_validator-0.2.0-py3-none-any.whl python tools/check_distribution.py
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
proof. The SQLite adapter should receive an immutable snapshot; a database that
is concurrently changing is outside its reproducibility contract. Schema and
policy evolution require new fixtures and review of admission semantics.

## Policy 0.2 changes

The original policy 0.1 file is retained. Default policy 0.2 blocks rejected or
superseded statements and human rejections, and requires review for unresolved
concepts or deferred human decisions. An acceptance record cannot cancel a
coexisting rejection or deferral. Conflicting adjudications must be resolved in
a new reviewed evidence record; list order does not decide which judgment wins.
Reports include a hash of the generated schema, including imported definitions.
