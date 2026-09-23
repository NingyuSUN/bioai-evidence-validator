# Engineering contract — 0.4.1

## Validation stages

1. Parse one JSON record. The CLI rejects duplicate keys, nonfinite numbers, malformed
   UTF-8/JSON, and excessive parser recursion as operational errors.
2. Validate against the packaged LinkML core compiled to JSON Schema, plus any
   explicitly selected extension. Structural failures stop semantic evaluation.
3. Check profile binding, supported/distinct uses, IDs and references, and review targets.
   Integrity failures stop profile evaluation and reject all requested uses.
4. Apply fixed evidence checks and the selected profile's declarative use contracts.
5. Return findings and a decision for each use. Any rejection makes the overall status
   rejected; otherwise any review requirement makes it review_required.

Unsupported uses, absent/empty required lists, broken references (including unused
evidence items), and duplicate source/item/line/adjudication IDs cannot be admitted.

## Rules

| Code | Condition | Result |
|---|---|---|
| SCHEMA | Structural/type/date/required-field violation | Reject all uses |
| RECORD_INTEGRITY | Profile/use/ID/reference/review-target mismatch | Reject all uses |
| BEV001 | Rejected or superseded statement | Reject |
| BEV002 | Supplied observed and frozen source hashes differ | Reject |
| BEV003 | Entity type or predicate outside profile allowlist | Reject |
| BEV004 | Contradicting evidence line | Review |
| BEV005 | Supporting evidence and statement scopes differ | Reject |
| BEV006 | No resolved scope-matched support | Review |
| BEV007 | Required supporting evidence type absent | Reject affected use |
| BEV008 | LLM-only support within a required evidence type without profile permission | Review affected use |
| BEV009 | String-match-only support within a required evidence type without profile permission | Review affected use |
| BEV010 | Required human acceptance absent for this use | Reject affected use |
| BEV011 | Human rejection present for this use | Reject affected use |
| BEV012 | Human deferral present for this use | Review affected use |
| BEV013 | Only LLM and string-match support mixed within a required type, without both permissions | Review affected use |

A human acceptance does not erase contradictions, missing evidence, source mismatches,
or other human rejection/deferral. Low-strength extraction permissions are explicit
profile choices; they cannot disable structural or integrity checks.

## Audit and trust

Reports contain canonical input SHA-256; exact profile-byte SHA-256 and version;
compiled schema SHA-256 and versions/roles for baseline and extensions; validator
version; UTC validation time; findings; and per-use reason codes. The timestamp changes
between runs. Hashes identify inputs/configuration; they do not sign records or prove
that a source, source hash, label, or reviewer identity is authentic.

Source artifacts require a declared version, retrieval time, and frozen hash. The optional
observed hash is compared to that hash; this package does not retrieve source bytes or
calculate their hashes. A profile can require a declared `independent_cohort_review`
evidence item, but the engine cannot establish independence or evaluation validity.

Report writes use a temporary file and atomic replacement. Input, selected profile,
selected schema, and baseline schema paths cannot be the report destination. Operational
failures leave no completed new report and preserve an existing report if replacement fails.
CLI configuration is trusted, including schema import paths.

`validate`: 0 admitted, 1 rejected, 2 review_required, 3 input/configuration/execution error.
Argparse usage errors also exit 2, with usage text rather than a validation report.
`profiles` prints all built-in contracts; `generate-schema --output schema.json`
exports the compiled core schema. Custom schema export exports that selected schema;
validation still applies the baseline independently.

## Reproduction

```bash
uv sync --frozen --extra dev
uv run --frozen pytest
uv build
uv run --isolated --no-project --with ./dist/bioai_evidence_validator-0.4.1-py3-none-any.whl python tools/check_distribution.py
```

CI runs on Linux/Python 3.11 and Windows/Python 3.13. Tests cover multi-domain acceptance,
negative evidence cases, use-specific human review, strict configuration/JSON parsing,
baseline enforcement, context snapshots, audit digests, and CLI report behavior. The wheel
smoke test imports outside editable source, checks packaged profiles/schema, and exercises
accepted, rejected, review-required, and custom-domain records. It does not assess
biological correctness, model calibration, or predictive performance.

The [VBO case](../examples/vbo_canine/README.md) adds offline source verification and a
separate real-source/controlled-fault evaluation. Its trust-boundary failures remain visible.
