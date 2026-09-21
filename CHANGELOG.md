# Changelog

## Unreleased

- Version schema/policy 0.2; preserve policy 0.1 and record generated-schema hashes.
- Prevent withdrawn statements or conflicting human judgments from silently being admitted.

- Reject missing, empty, malformed, duplicated or unknown requested uses.
- Make structural and identity errors block the entire record, including unknown uses.
- Require evidence collections and reject duplicate IDs before dictionary lookup.
- Return structured operational CLI errors; parse UTF-8 strictly and write reports atomically.
- Add regression tests, a Linux/Windows CI workflow and an installed-wheel smoke check.
- Include the Apache-2.0 license already declared in project metadata.
