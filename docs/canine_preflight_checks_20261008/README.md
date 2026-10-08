# 2026-10-08 branch preparation validation

The final machine-readable record is `validation.json`. It binds the actual
implementation files, example, source branch baseline and tested wheel.
`full_tests.log` is the final-code full regression/coverage run;
`targeted_tests.log` is the 52-check new-entry run; `review_red.log` preserves
five deliberately failing regressions before the coordinate and diagnostic fixes.
`wheel.log`, `lint.log`, `mypy.log`, and `build.log` preserve completed checks.

The initial unsupported CLI test failed before implementation. The initial full
suite had 708 passing tests while follow-up corrections were being developed;
it is superseded by the final-code full suite, not used as final-code coverage.
The read-only internal code review reproduced the float-coordinate defect, then
verified its fix. It is not an external model/clinical review.

The wheel was installed without dependencies into a temporary environment, with
only dependencies supplied from the existing Python 3.12 environment via
`PYTHONPATH`. `tools/check_distribution.py` asserts the imported package comes
from outside the editable source. A prior fully isolated offline dependency
resolution failed because registry cache entries were unavailable; this is an
environment limitation, not a successful fresh dependency installation.

No current 629-event production adapter or new biological validation was run.
The six real source records are historical development cases. Authored faults
measure engineering error detection, not clinical sensitivity/specificity.
