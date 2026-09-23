# Profiles: add a domain without changing the engine

The record schema describes an assertion, its evidence, source snapshots, and
adjudications. A profile defines the admission contract for a domain. Use a built-in
name (`general`, `literature-claim`, `dataset-label`) or an explicit YAML path.
The record's `profile_id` must match the selected profile. Selection is explicit;
a record never silently chooses a weaker profile.

## Minimal custom profile

```yaml
id: assay-review
version: "1.0.0"
description: Review compound response evidence in an assay.
predicates: [measured_response]
subject_types: [compound]
object_types: [assay_readout]
uses:
  assay_curation:
    required_evidence_types: [assay_measurement]
    require_human_acceptance: false
    allow_llm_only: false
    allow_string_match_only: false
```

Run the [complete fixture](../examples/custom_profile/assay_record.json):

```bash
uv run bioevidence validate examples/custom_profile/assay_record.json --profile examples/custom_profile/assay.yaml
```

All seven top-level fields and all four fields in each use contract are required.
Unknown fields, duplicate YAML keys, non-string keys, string-valued booleans,
empty use mappings, blank values, and duplicate list entries are configuration errors.
Quote versions so YAML loads them as strings. Empty predicate/type lists mean
unrestricted nonblank values; an empty evidence-type list does not waive the
requirement for supporting evidence.

## Record contract

- `record_id` identifies the record; `profile_id` binds it to the selected contract.
- `statement` contains an `id`, typed `subject` and `object` (each with `id`, `label`,
  `entity_type`), `predicate`, `statement_status`, `scope`, and `evidence_lines`.
- `source_artifacts` describes versioned sources with retrieval time and SHA-256.
- `evidence_items` binds located evidence to a source, extraction method, evidence
  type, and scope. Lines refer to item IDs and declare support, contradiction, or neutrality.
- `requested_uses` is a nonempty list of distinct profile-defined uses.
- Optional `adjudications` include decision, reviewer, rationale, time, target
  `statement_id`, and nonempty `applies_to_uses`.

Scope is an explicit set of literal tokens, such as a taxon and cohort identifier.
Supporting evidence must have exactly the same token set as the statement. No
ontology inference, hierarchy expansion, or extrapolation across cohorts occurs.
Duplicate scope tokens are rejected. Keep assertions at the scope of their evidence.

Only resolved, supporting, scope-matched items satisfy required evidence types.
Since 0.4.1, extraction-method quality checks run **separately for every required
evidence type**. A manually curated auxiliary note cannot strengthen an LLM-only
publication result or sample link. The existing per-use permissions apply to each
group; if a use declares no required types, its gate applies to all supporting evidence.
Method labels are supplied metadata, not authenticated evidence of human verification.
Neutral or contradicting items cannot fill a missing evidence requirement. Required
evidence types express presence, not minimum source counts, statistical quality,
independence, or mechanistic plausibility. Profiles are trusted configuration and
must be scientifically reviewed for the intended application.

Human acceptance counts only for the same statement and listed uses. Software
acceptance cannot fulfill a human requirement. Accepting training use does not
approve external validation. Rejection and deferral remain effective even when an
acceptance is also present; no list ordering or timestamp supersedes them.

## Python batches and schema restrictions

```python
from bioevidence_validator.engine import RecordValidator

validator = RecordValidator(profile="literature-claim")
reports = [validator.validate(record) for record in records]
```

The context snapshots profile bytes and compiles schemas once. Recreate it after
configuration changes. `validate_record(record, profile=...)` is the single-record
convenience API. Reports retain the exact profile-byte hash and the compiled schema
hash, including imported definitions, so changed configurations are distinguishable.

An optional trusted LinkML `--schema path.yaml` adds structural constraints; the
built-in baseline still runs. Extensions may restrict baseline fields but cannot
replace required fields or add arbitrary fields prohibited by the closed baseline.
LinkML import resolution is trusted configuration, not a sandbox for untrusted schemas.

## Boundaries

Profiles can express type/predicate allowlists and per-use evidence/review requirements.
They do not implement disease-specific interpretation guidelines, numeric effect-size
thresholds, source credibility rankings, review authentication, or experimental validation.
Add such analysis upstream and provide its evidence with clear provenance. Never treat
`external_validation` admission as proof that independent validation was performed.
