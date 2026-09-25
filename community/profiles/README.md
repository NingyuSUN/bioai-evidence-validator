# Community profiles

Domain admission profiles contributed by the community. Each folder is self-contained and
tested in CI: every example case is built, validated against the folder's profile, and
compared with its expected outcome.

| Profile | Domain | Maintainer |
|---|---|---|
| [`_template`](_template/) | Synthetic protein–protein interaction example to copy | project |

## Add a profile

1. Copy `_template/` to a new folder named after your profile id, e.g. `ppi-curation/`.
2. Edit `profile.yaml`: the entity types, predicates and, for each intended use, the
   required evidence types and whether LLM-only evidence or human acceptance is allowed.
   See [docs/PROFILES.md](../../docs/PROFILES.md) for every field.
3. Replace the cases in `cases/` with **at least one admitted and one non-admitted** example
   as [drafts](../../docs/DRAFTS.md). Use synthetic or openly licensed data only.
4. Record each case's expected outcome in `expected.yaml`.
5. Describe the policy and its basis (guideline, database policy, or your own proposal) in
   the folder's `README.md`, and add a row to the table above.
6. Run `uv run --frozen pytest tests/test_community_profiles.py` and open a pull request.

## Folder layout

```text
my-profile/
├── README.md        # domain, intended uses, basis for the policy, maintainer
├── profile.yaml     # the admission contract
├── expected.yaml    # case file -> expected overall status and per-use statuses
└── cases/
    ├── *.yaml       # drafts, one claim each
    └── ...          # local source files the drafts hash (synthetic or openly licensed)
```

A profile here is a proposal for its community, not an endorsement of a clinical or
regulatory standard by this project.
