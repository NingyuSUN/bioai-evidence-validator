# Migrating from the canine 0.3 package

Version 0.4 is a breaking change: `main` now contains the domain-neutral framework.
The full 0.3 canine schema, all historical policies, fixtures, regression tests, and
read-only SQLite adapter remain on the
[`canine-breed` branch](https://github.com/NingyuSUN/bioai-evidence-validator/tree/canine-breed).
Use a separate checkout if you need both:

```bash
git clone --branch canine-breed https://github.com/NingyuSUN/bioai-evidence-validator.git bioai-canine
cd bioai-canine
uv sync --frozen --extra dev
uv run bioevidence validate examples/canine_breed/valid_labrador.json
```

| 0.3 canine package | 0.4 main |
|---|---|
| Canine breed default schema and CBR rules | BioEvidenceRecord core and BEV rules |
| `subject_label`, `object_breed`, canine statement types | Typed `subject`, `predicate`, `object`, explicit `scope` |
| `--policy path.yaml` / Python `policy_path=` | `--profile name-or-path` / Python `profile=` |
| `policy_id`, `policy_version`, `policy_sha256` report fields | `profile_id`, `profile_version`, `profile_sha256` |
| Unscoped adjudication | Required `statement_id` and `applies_to_uses` |
| `export-canine-panel` | Available only on `canine-breed` |

Canine records are intentionally not auto-converted. Generic provenance checks cannot
substitute for breed ambiguity, ontology status, regional scope, or genotype membership
checks. Continue using the branch for those guarantees. A new generic integration should
map source records into the core schema and define a scientifically reviewed profile;
see [profile authoring](PROFILES.md).

The package name remains the same. Install branch 0.3 and main 0.4 in separate virtual
environments; downstream consumers must update their record builders and report parsers.
