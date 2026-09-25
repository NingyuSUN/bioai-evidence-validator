# Changelog

## Unreleased — Quality checks, community and documentation site

- CI runs ruff and mypy, and enforces a 95% test-coverage minimum (currently 98%).
- Add CONTRIBUTING, CODE_OF_CONDUCT (Contributor Covenant 2.1), SECURITY, issue forms and a
  pull request template.
- Add `community/profiles/`: contributed domain profiles whose example cases are built,
  validated and checked against expected outcomes in CI; `_template/` to copy.
- Add a documentation site (MkDocs, strict link checking) published to GitHub Pages.
- The canine 0.3 implementation is also preserved at the `canine-0.3` tag.
- No change to validation behavior or report contents.

## 0.6.0 — ClinVar case and standards alignment

- Add a second real-data case: ClinVar germline classifications. 5,026 sampled variants
  from the 2023-09 release are built from per-submission evidence and validated with a
  ClinVar-style profile; decisions are compared with NCBI's own 2023-09 review status and
  with each classification's 2026-09 outcome, plus controlled faults and a trust-boundary
  cohort. Frozen, hash-pinned sample; rebuild script verifies the three upstream files.
- Add `docs/STANDARDS.md`, mapping the record model to ECO, Biolink 4.4.4, GA4GH VA-Spec
  1.0.1 and PROV-O, with mapping strength and caveats.
- Annotate `ExtractionMethod` values with ECO meanings in the LinkML schema. The compiled
  JSON Schema, and therefore every report's `schema_sha256`, is unchanged.
- The VBO benchmark summary changes only `validator_version`.

## 0.5.0 — Drafts, LLM draft schema and GitHub Action

- Add compact YAML/JSON drafts: `bioevidence build` and `build_record()` derive identifiers,
  group evidence lines and hash named local files, without supplying scope, method, times
  or review decisions. Strict parsing rejects unknown, missing and out-of-choice fields.
- Add `bioevidence draft-schema` and `draft_json_schema()`: a per-profile JSON Schema for
  drafts, e.g. for LLM structured output.
- Add a composite GitHub Action that validates records or drafts in pull requests, with a
  job summary, file annotations and count outputs.
- Add a Colab quickstart notebook and draft examples.
- Export `build_record`, `load_draft`, `draft_json_schema` and `validate_record` from the package root.

## 0.4.1 — Required-evidence quality and real-source evaluation

- Apply extraction-method quality gates to each required evidence type independently.
- Prevent unrelated manual/parser evidence from admitting an LLM-only required result.
- Add an attributed, frozen VBO canine name-mapping case and source rebuild script.
- Evaluate 72 real-source names, 160 controlled faults, and 16 explicit trust-boundary cases separately.
- Preserve generic main and the legacy canine-breed branch.
- Publish to PyPI from version tags; add package metadata and citation file.
- Reject CLI input nested deeper than 100 levels (exit 3) on every platform and Python version.

## 0.4.0 — Domain-neutral main

- Preserve canine 0.3 functionality on the `canine-breed` branch.
- Replace canine defaults with a generic entity/relation/evidence schema and strict YAML profiles.
- Add general, literature-claim, dataset-label, and custom assay examples.
- Bind human adjudications to statements and uses; enforce evidence scope and reference integrity.
- Replace `--policy` with `--profile`; add profile discovery and generic audit fields.
- Remove the canine SQLite command from main. See `docs/MIGRATION-0.4.md` for breaking changes.

## 0.3.0 — Evidence and snapshot contract hardening

- Require resolved supporting evidence, selected-candidate consistency and
  compatible claim predicates; block relationship claims from sample/frequency label use.
- Enforce scope exclusions from concept scope, use only supporting scope evidence,
  reject blank provenance and unresolved references in unused evidence.
- Reject incomplete/duplicate/unknown policy configuration; custom schemas cannot
  relax the packaged structural baseline. Snapshot validation context per batch.
- Reject duplicate database IDs, WAL/SHM/journal sidecars, malformed manifests
  and unrecognized boolean evidence. Include resolution-row provenance,
  limits/accounting and batch hashes; publish the completion summary last.
- Preserve earlier policy files, synthetic examples and operational CLI exit codes.

## 0.2.0 — Evidence admission contracts and reproducible CLI

- Version schema/policy 0.2; preserve policy 0.1 and record generated-schema hashes.
- Prevent withdrawn statements or conflicting human judgments from silently being admitted.
- Reject missing, empty, malformed, duplicated or unknown requested uses.
- Make structural and identity errors block the entire record, including unknown uses.
- Require evidence collections and reject duplicate IDs before dictionary lookup.
- Return structured operational CLI errors; parse UTF-8 strictly and write reports atomically.
- Add regression tests, a Linux/Windows CI workflow and an installed-wheel smoke check.
- Include the Apache-2.0 license already declared in project metadata.
