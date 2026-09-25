# Security policy

## Supported versions

Security fixes are released for the latest minor version on PyPI. Please upgrade before
reporting.

## Reporting a vulnerability

Report privately through GitHub:
[**Report a vulnerability**](https://github.com/NingyuSUN/bioai-evidence-validator/security/advisories/new).
Please do not open a public issue.

Include the version, the command or API call, and the smallest input that reproduces the
problem. **Do not include real patient data or other sensitive records**; a synthetic record
that shows the same behavior is enough.

You can expect an acknowledgement within 7 days and a status update within 30 days. Fixed
issues are credited in the release notes unless you prefer otherwise.

## What counts

In scope, for example:

- a record that is **admitted** although a documented rule should reject it or send it to
  review (a fail-open bug);
- input that makes the CLI write outside the requested output path, overwrite its inputs,
  or leave a partial report;
- crashes or unbounded resource use from crafted records, drafts or profiles;
- the GitHub Action executing or exposing more than it documents.

Documented limits are not vulnerabilities: the engine trusts supplied metadata and does not
authenticate sources, hashes or reviewer identities (see the *trust boundary* cohorts in the
benchmarks and [docs/ENGINEERING.md](docs/ENGINEERING.md)). Reports that show a practical
exploit of those limits are still welcome.
