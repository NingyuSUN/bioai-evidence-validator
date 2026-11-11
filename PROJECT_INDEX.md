# BioAI Evidence Validator — project index

## Current release work: local EvidPort MCP consumer — 2026-11-11

The optional local stdio bridge is prepared for publication from the reviewed
public main baseline `992b0c73c8b9de7096fee3495e0a57e0ad7dcb0a`. It retrieves an exact
citation and checks the response against the original library. Existing scoring,
profiles, source review gates and frozen benchmark inputs remain unchanged.

| Field | Scope and evidence |
|---|---|
| Date | 2026-11-11, Asia/Tokyo; complete local suite verified at 17:02 JST; package-boundary checks verified at 17:08 JST; interpreter regressions verified at 17:20 JST. Exact Git and remote CI times are available from the revision and its Actions runs. |
| Purpose | Publish the local MCP consumer and its tests with portable instructions, while keeping source papers, databases and machine configuration outside the repository. Replace benchmark CLI calls' fixed temporary directory with the operating system's temporary directory and quote WSL arguments safely. |
| Inputs and code | Public main baseline above; the reviewed MCP consumer, synthetic tests and SDK 2.3.0. The independent EvidPort dependency is pinned to `65c8626185eaa3c3e9e7b60db4c17b43a545d394` in CI and the installation guides. Execution occurs in this checkout; runtime inputs remain operator-selected. Existing benchmark inputs and accepted result files are unchanged; new temporary-path tests mock every model invocation. |
| Result and checks | The public candidate passed all 42 MCP consumer cases with the locked SDK and a separately installed public EvidPort candidate, including real stdio round trips. The real-paper engineering acceptance in EvidPort covered nine distinct papers, including three manual re-imports: exact unreviewed quotations stayed review-required, while fabricated quotations and wrong source hashes were rejected. This public candidate passed all 35 offline benchmark regression cases, including eight special-character path and cleanup cases, plus 19 public-tree guard cases, the public-tree scan, Ruff, type checking (17 source files), dependency compatibility, lock consistency and the strict documentation build. The guard skips only generated Markdown links; MkDocs checks those links and private-file/path checks remain enabled. The original complete candidate suite passed 611/611 tests, with zero failures, errors, skips or test warnings and 96.20% branch-aware coverage (95% minimum). Eight later portability cases, 19 publication-tree cases and seven package cases passed separately, covering 645 distinct cases before the interpreter fix. The three added interpreter cases and all 45 MCP cases then passed, bringing the expected full matrix to 648 tests. Exact-revision remote CI remains a separate check. |
| Cross-platform correction | The first [PR run](https://github.com/NingyuSUN/bioai-evidence-validator/actions/runs/42984772162) passed 645 tests on Windows, while each of four Linux environments passed 644 and failed the real stdio case. Resolving the virtual-environment Python symlink selected the base interpreter. Both command-path entry points now preserve the selected executable; three real-venv subprocess regressions cover absolute, PATH and config-relative commands. Configuration-file and working-directory resolution remain unchanged. No test was skipped or weakened; the corrected revision requires new CI. |
| Package cleanup | An initial local source archive included 103 private execution-file members despite Git ignore rules. No affected package was uploaded. Explicit build exclusions removed them; the new archive gate rejects the original source archive and accepts both corrected archives. Git-tree and archive checks are separate CI gates. |
| Evidence locations | [MCP guide](docs/EVIDENCE_MCP.md), [library contract](docs/EVIDENCE_LIBRARY.md), [synthetic tests](tests/test_evidence_mcp.py), [sanitized real-paper acceptance](https://github.com/NingyuSUN/evidport/blob/main/evaluation/mcp-local-20261111.json) and [Actions](https://github.com/NingyuSUN/bioai-evidence-validator/actions). Private runtime receipts are not published. Cloud delivery is not applicable. |
| Git / synchronization | Prepared on `codex/local-mcp-public`; publication and exact-revision CI are still pending at this record. No private development history is imported or rewritten. Query this index's commit through Git rather than embedding its own future hash. |
| Limits | Known-positive retrieval and synthetic boundary tests establish engineering behavior, not full transcription accuracy, scientific support, clinical validity or a hallucination rate. Historical metadata was reused for the real-paper check; no new live-network acquisition was tested. Human review remains separate. |

The historical entries below retain the evidence for earlier public revisions.

## Historical implementation: EvidPort integration on main — 2026-11-11

This revision merges the reviewed public EvidPort integration into `main`, preserving
its four commits. [PR #46](https://github.com/NingyuSUN/bioai-evidence-validator/pull/46)
records the integration. Private development commits, papers, databases and parser
outputs are outside this merge. The optional CLI remains `validate --evidence-library`.

| Field | Verified basis and scope |
|---|---|
| Date | 2026-11-11, Asia/Tokyo; exact commit and CI timestamps are recorded by GitHub. |
| Purpose | Integrate the published evidence-library adapter into main and verify the merged revision. |
| Inputs and code | Main parent `8ebc4b14316d0ef9f3d248e62ac8b4521e82810e`; integration parent `f5d340054d80bc12d4990e554ed2f5740cbc776e`; EvidPort pinned to `a6f26ff29c966109e707cce180794731a7af9e8a`. Runtime, tests, workflows and frozen evaluation inputs are identical to the integration parent; only this index is updated during the merge. |
| Checks | The exact integration parent passed all nine jobs in [run 42788543540](https://github.com/NingyuSUN/bioai-evidence-validator/actions/runs/42788543540): each of five environments passed 569 tests with zero failures, skips or test warnings and 97.66% coverage; 22 frozen result groups reproduced identically. These are pre-merge results. The merged revision has its own main push checks, linked below. |
| Results and locations | Optional source/version/excerpt/review-state checks are documented in [EVIDENCE_LIBRARY.md](docs/EVIDENCE_LIBRARY.md). [Main repository checks](https://github.com/NingyuSUN/bioai-evidence-validator/actions/workflows/ci.yml?query=branch%3Amain) and [main documentation build/deployment](https://github.com/NingyuSUN/bioai-evidence-validator/actions/workflows/docs.yml?query=branch%3Amain) record the actual post-merge result for each exact commit. |
| Git / synchronization | Regular two-parent merge; no squash, rebase or rewritten history. The public main commit is available through PR #46 and the main branch. Use `git log -1 -- PROJECT_INDEX.md` for this index's commit rather than embedding its own future hash. Private working records are retained separately. |
| Limitations and next scope | CI checks engineering behavior and frozen-output reproducibility, not scientific validity, overall transcription accuracy or independent human review. Actual evidence still requires the recorded review gates. MCP and package-registry publication remain outside this merge. No scientific inputs, review decisions or scoring rules are changed. |

## Historical integration-branch verification

The dated records below describe the branch before its main merge; references to
an unmerged integration branch in those entries are historical.

## Strict resource-check fixes — 2026-11-10 (UTC)

The stricter [run for 35c6e2f](https://github.com/NingyuSUN/bioai-evidence-validator/actions/runs/42786495582)
correctly failed on pre-existing resource warnings: Python 3.14 reported 544 passing
and 13 failing tests, and fail-fast cancelled the other four verification jobs.
Those 13 failures include parameterized repetitions; they are not 13 changed
scientific results. The reproduction job still matched all 22 frozen output groups.

This follow-up closes CSV files, loaded workbooks and consumed HTTPError responses,
and limits the temporary semantic profile directory to validator initialization.
Read values, error/fallback classification, scientific inputs and scoring logic are
preserved. Nine real HTTP-response tests and three normal/error temporary-directory
tests were added. The respective strict local scopes passed 64 literature tests,
31 CSV/workbook tests and five semantic tests, with original frozen outputs unchanged.
Source and public candidate bytes for the changed files match.

The three warning classes remain errors. Verification jobs no longer cancel each
other, so all supported environments produce diagnostics. EvidPort stays pinned
to `a6f26ff29c966109e707cce180794731a7af9e8a`, whose two remote environments passed
265 tests with no test warnings. Full verification of this new validator revision
is recorded by [Actions](https://github.com/NingyuSUN/bioai-evidence-validator/actions?query=branch%3Acodex%2Fevidence-library-integration-public).
The source/candidate preparation records and prior failed logs remain archived.

## CI warning follow-up — 2026-11-10 (UTC)

The first published integration `f6bf5d21eb7936b471d3dff1b0f0d12bb8e9ead6`
passed [all nine jobs](https://github.com/NingyuSUN/bioai-evidence-validator/actions/runs/42783160589):
five environments each passed 557 tests, with no skips and 97.69% coverage;
22 frozen result/figure groups reproduced identically. This is engineering
reproducibility, not independent scientific validation.

Inspection of the passing logs revealed two concrete issues: unclosed acquisition
connections in EvidPort, and a Windows subprocess output-decoding exception in a
frozen-result test. The follow-up pins the resource-cleanup revision of EvidPort,
explicitly requests UTF-8 from that subprocess, and checks its complete output
against the existing frozen summary even under an inherited non-UTF-8 setting.
Frozen inputs, metrics and output files are unchanged.

The affected Windows Python 3.12 test module passed all 11 tests locally with
unhandled-thread warnings treated as errors. Source and candidate test bytes match.
The fixed EvidPort revision `a6f26ff29c966109e707cce180794731a7af9e8a` is already
published and pinned in this workflow. Its stricter matrix is tracked by
[EvidPort checks](https://github.com/NingyuSUN/evidport/actions/runs/42786324296).

ResourceWarning and unhandled thread/destructor warnings now fail CI instead of
leaving a passing test with lost output or leaked resources. Inspect
[the branch runs](https://github.com/NingyuSUN/bioai-evidence-validator/actions?query=branch%3Acodex%2Fevidence-library-integration-public)
for the current revision. This remains an integration branch, not a main merge.

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
