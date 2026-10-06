# Software check receipts

`actual154.json` is the replay of the source-derived development fixture. It
binds final source modules and 94 declared snapshot dependencies. The report
retains assay, phase, causality and capture-performance limits.

`full_suite.txt`, `ruff.txt`, `mypy.txt`, `wheel_build.txt`, `wheel_install.txt`
and `distribution.txt` record final software verification. `validation.json`
summarizes commands, exit codes, counts and file hashes. The package version is
still the inherited 0.8.0; implementation hashes distinguish this local branch.

Historical development receipts are retained explicitly:

- `red_run.txt`: initial 17 counterexamples failed because the entry did not exist.
- `green_initial.txt`: those 17 initial cases passed after first implementation.
- `focused.txt`: an intermediate failure identified how missing reference bytes
  were wrongly compared with an empty WT string; the comparison now waits for
  actual flanks. A changed assertion was also read during that running session.
- `focused_final.txt`: 105 expanded cases passed before the final payload-hold
  guard and its new case were added. The final suite supersedes this receipt.
- `full_suite_before_final_guards.txt` and
  `distribution_before_final_guards.txt`: preliminary 653-test and installed-wheel
  verification before explicit JSON-null and component-derived payload guards.

These are engineering tests on authored counterexamples and reused development
sources, not a held-out biological, clinical or sample-performance study.
