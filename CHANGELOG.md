# Changelog

## 0.4.1 — Required-evidence quality and real-source evaluation

- Apply extraction-method quality gates to each required evidence type independently.
- Prevent unrelated manual/parser evidence from admitting an LLM-only required result.
- Add an attributed, frozen VBO canine name-mapping case and source rebuild script.
- Evaluate 72 real-source names, 160 controlled faults, and 16 explicit trust-boundary cases separately.
- Preserve generic main and the legacy canine-breed branch.
- Publish to PyPI from version tags; add package metadata and citation file.

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
