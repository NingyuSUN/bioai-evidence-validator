# BioAI Evidence Validator — project index

## Publication round — 2026-11-10 (UTC)

The owner authorized publishing the independent evidence layer as
[EvidPort](https://github.com/NingyuSUN/evidport), followed by this integration
branch and CI monitoring/fixes. This round starts from local candidate
`331e91264c0edcf69179479162b062bc15e86cf6`. Publication naming and CI checkout
addresses are updated; the optional `--evidence-library` contract remains unchanged.
The workflow now also runs on pushes to `codex/evidence-library-integration-public`
so the requested branch checks do not depend on opening or merging a pull request.

The exact companion revision `ed5dd1826becca992a7e9f0bf5474f90b9c1df4d` was
verified on the EvidPort remote main before this branch's publication and is pinned
in `.github/workflows/ci.yml`. Its first remote run is
[EvidPort checks](https://github.com/NingyuSUN/evidport/actions/runs/42782858570).
Remote CI completion is not yet verified at this record; inspect
[Actions](https://github.com/NingyuSUN/bioai-evidence-validator/actions)
for the actual head. This is a branch publication, not a main-branch merge.
No new scientific input, raw paper, local database, or review approval is included.
Earlier completed checks and their limitations are preserved below.

Updated: 2026-11-10T07:47:06.073273+00:00 (UTC). Validation evidence was finalized on 2026-11-10.

## Current objective and code provenance

Add the optional, read-only `--evidence-library` consumer without importing the
unpublished embedded-database prototype or changing existing validation contracts.
The execution location is this checkout; the evidence library is a user-selected
local path. Cloud delivery is not applicable to this round.

- Repository URL: https://github.com/NingyuSUN/bioai-evidence-validator .
- Independently verified live upstream `main` baseline:
  `8ebc4b14316d0ef9f3d248e62ac8b4521e82810e`. Online verification was performed during this round; it is
  a time-bound baseline, not a claim that the remote will remain unchanged.
- Development source baseline: `df6318eb1a2c2a37aad0ec7be7c273dbd5d8270e`; reviewed
  working-tree changes supplied the new adapter and tests. Only the integration
  delta was transferred to the verified upstream baseline. The five intervening
  local legacy commits were not added to this publication branch.
- Final development source commit after the frozen tests: `54b5f736b5e6a3f2c88dfce1e005b5439170154d`.
  The earlier baseline and private population hashes above are preserved as provenance.
- Publication branch: `codex/evidence-library-integration-public`. Existing upstream history is preserved.
- Changes: optional adapter, minimal CLI wiring, matching tests, public guide/README,
  portable project entry points, and CI installation of an exact evidence commit.
  The private receipt records the intentional CLI/document/test transformations.
- The companion evidence candidate was committed locally as
  `d7c93cf8fb6c2dd1d44ea931908caec8fb3817f8`; CI is pinned to that exact revision.
  The companion repository and revision must be published before this branch's CI runs.
- Public entry points: [README](README.md), [integration guide](docs/EVIDENCE_LIBRARY.md),
  `src/bioevidence_validator/evidence_library.py` and `tests/test_evidence_library.py`.

## Verified engineering results

| Scope | Result |
|---|---|
| Independent evidence library, complete local test suite | 256 passed; 0 failed, 0 errors, 0 skipped |
| New validator integration tests with synthetic originals and reviews | 44 passed; 0 failed, 0 errors, 0 skipped |
| Selected existing validator core and repository checks | 220 passed; 0 failed, 0 errors, 0 skipped |

The test processes explicitly prioritized the two candidate source directories.
Both candidates passed Ruff; the validator passed mypy across 16 source files.
Both built a wheel and source archive offline. Separate wheel installation directories
passed import-location assertions and four CLI checks, using the existing validator
dependency environment. The checks covered library help, validator profiles, one
accepted record and one rejected record. No historical large benchmark was replayed.

These are engineering checks. They do not establish transcription accuracy across
papers, scientific support for a claim, hallucination reduction, or clinical validity.
Synthetic review approvals are test fixtures, not human approval of real evidence.

## Limits and publication state

- A fresh environment with the complete frozen production dependency set was **not
  verified**: required versions were unavailable in the offline cache. No network
  installation was used to bypass that limitation.
- CI YAML structure, the explicit dependency-import guard and locked PDF dependency
  export were checked locally. GitHub workflows and the remote platform matrix have
  **not run** in this round. No remote CI success or remote synchronization is claimed.
- Builds and wheel checks preceded the final index update and CI commit-pin replacement.
  Runtime code is unchanged. Rebuild source archives before distributing artifacts
  that must include the final index and pinned CI configuration.
- No push or remote publication was performed in this preparation/validation round.
  Publish the evidence repository and pinned revision first, then publish this
  integration branch. The local pin is not evidence of remote availability.
- Detailed test logs, package hashes, source/candidate checksums and preparation
  receipts are private records outside these public checkouts. Runtime originals,
  local stores and parser output belong in ignored directories.

## Validation scope and inherited artifacts

The 220 existing tests came from `test_cli.py`, `test_grounding.py`,
`test_fail_closed.py`, `test_engine.py`, `test_profiles.py`, `test_literature.py`,
`test_repository_files.py`, and `test_github_action.py`. The older full development
suite was stopped before completion and is not reported as a full-suite pass.
The 44 integration tests are additional to that selected core scope.

Existing upstream source collections and benchmark records remain upstream artifacts;
this integration did not add new paper bodies or rerun those scientific workflows.
The built source archive retains 209 inherited members matching paper-content suffixes
(`.xml.gz` or `papers.json.gz`). Both wheels contain no paper-content members.
This engineering check is not a new licensing or scientific validation of upstream data.

## Git status and next action

At this record, the candidate still rests on the verified upstream commit and its
integration changes await a scoped local commit. The companion candidate is locally
committed and its exact 40-character revision is set in `.github/workflows/ci.yml`.
After the integration commit, use `git log -1 --format=%H` for its actual SHA and
`git log -1 --format=%H -- PROJECT_INDEX.md` for this index's revision. Do not edit an
index repeatedly to include its own future hash. Verify remote synchronization and
CI results separately after any subsequently authorized publication.

## Preparation history — 2026-11-10

The initial candidate was created as a worktree from the live upstream baseline above.
The first copy had not yet run tests. It kept public upstream history while excluding
the local legacy prototype, private machine index and planning/pipeline investigation
from the integration delta. The final frozen snapshot then passed the tests and builds
recorded above. Final documentation and CI pin changes have separate private receipts.
