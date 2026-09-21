# Changelog

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

## Unreleased

- Version schema/policy 0.2; preserve policy 0.1 and record generated-schema hashes.
- Prevent withdrawn statements or conflicting human judgments from silently being admitted.

- Reject missing, empty, malformed, duplicated or unknown requested uses.
- Make structural and identity errors block the entire record, including unknown uses.
- Require evidence collections and reject duplicate IDs before dictionary lookup.
- Return structured operational CLI errors; parse UTF-8 strictly and write reports atomically.
- Add regression tests, a Linux/Windows CI workflow and an installed-wheel smoke check.
- Include the Apache-2.0 license already declared in project metadata.
