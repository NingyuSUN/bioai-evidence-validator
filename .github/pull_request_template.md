## What and why

<!-- One purpose per pull request. Link the issue: "Closes #123". -->

## Admission boundary

<!-- Does this change what gets admitted, sent to review or rejected? If yes, say which
     records move and why, and point to the tests that pin the new boundary. -->

- [ ] No change to admission decisions
- [ ] Changes admission decisions (explained above; tests on both sides of the boundary)

## Checklist

- [ ] `uv run --frozen ruff check .`, `uv run --frozen mypy` and `uv run --frozen pytest --cov` pass
- [ ] Committed benchmark results regenerated if report contents changed
- [ ] `CHANGELOG.md` updated if users will notice
- [ ] New third-party data has its license, attribution and exact version recorded
