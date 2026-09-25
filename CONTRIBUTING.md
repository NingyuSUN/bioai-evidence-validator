# Contributing

Thanks for helping make AI-assisted biocuration safer. Contributions of every size are
welcome: a typo fix, a bug report with a failing record, a new domain profile, or a new
real-data benchmark.

By participating you agree to follow the [code of conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

| You have… | Start here |
|---|---|
| A record the validator judges wrongly | [Bug report](https://github.com/NingyuSUN/bioai-evidence-validator/issues/new?template=bug_report.yml); attach the smallest record or draft that reproduces it |
| An admission policy for your domain | [Profile proposal](https://github.com/NingyuSUN/bioai-evidence-validator/issues/new?template=profile_proposal.yml), then a pull request to [`community/profiles/`](community/profiles/README.md) |
| An idea for the engine, CLI or formats | [Feature request](https://github.com/NingyuSUN/bioai-evidence-validator/issues/new?template=feature_request.yml) first, so we can agree on the contract before code |
| A security problem | Do **not** open an issue; see [SECURITY.md](SECURITY.md) |

Issues labelled [`good first issue`](https://github.com/NingyuSUN/bioai-evidence-validator/labels/good%20first%20issue)
are scoped to be finished in an afternoon.

## Development setup

Python 3.11+ and [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/NingyuSUN/bioai-evidence-validator.git
cd bioai-evidence-validator
uv sync --frozen --extra dev
```

Before opening a pull request, run what CI runs:

```bash
uv run --frozen ruff check .
uv run --frozen mypy
uv run --frozen pytest --cov
```

CI also runs the tests on Linux (Python 3.11–3.13) and Windows, builds the wheel and
smoke-tests it outside the source tree, and runs the GitHub Action. Coverage must stay at
or above the minimum in `pyproject.toml`.

## Ground rules for changes

This project's value is that it **fails closed** and **says exactly what it checked**.
Changes are reviewed against that:

- **No silent weakening.** A change that admits something previously rejected needs an
  explicit reason in the pull request and a test that shows the new boundary.
- **Every rule has a test on both sides**: a record that passes and a minimal one that fails.
- **Reports stay reproducible.** If a change alters report contents, the committed benchmark
  results must be regenerated in the same pull request, and the diff explained.
- **Domain logic stays out of the engine.** New domains are profiles and importers, not
  special cases in `engine.py`.
- **Honest limits.** Benchmarks state what their labels are (source-derived, authored, or
  independently reviewed) and what they do not measure.
- Match the surrounding style; ruff enforces correctness rules, not formatting.

## Contributing a domain profile

Community profiles live in [`community/profiles/`](community/profiles/README.md). Each one is
a folder with a profile, a short README and example cases whose expected outcomes are
checked by the test suite. Copy `community/profiles/_template/` to get started.

## Pull requests

- Keep each pull request to one purpose; link the issue it resolves.
- Update `CHANGELOG.md` under a new heading if users will notice the change.
- New third-party data needs its license, attribution and exact source version recorded,
  as in `examples/*/sources/README.md`.

## Releases

Maintainers release by bumping the version in `pyproject.toml` and
`src/bioevidence_validator/__init__.py`, adding a `CHANGELOG.md` section, and pushing a
`vX.Y.Z` tag. The release workflow tests, publishes to PyPI and creates the GitHub release.
