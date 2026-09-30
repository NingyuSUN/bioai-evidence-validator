# VBO canine evidence benchmark

Source-derived reference labels; no independent expert annotation.

| Cohort | Method | n | False admission | False block | Review |
|---|---|---:|---:|---:|---:|
| real_source | schema_only | 72 | 24/24 | 0/48 | 0/72 |
| real_source | aggregate_quality | 72 | 0/24 | 0/48 | 0/72 |
| real_source | full | 72 | 0/24 | 0/48 | 0/72 |
| real_source | grounded | 72 | 0/24 | 0/48 | 0/72 |
| controlled_fault | schema_only | 160 | 160/160 | N/A | 0/160 |
| controlled_fault | aggregate_quality | 160 | 64/160 | N/A | 16/160 |
| controlled_fault | full | 160 | 0/160 | N/A | 80/160 |
| controlled_fault | grounded | 160 | 0/160 | N/A | 80/160 |
| trust_boundary | schema_only | 48 | 48/48 | N/A | 0/48 |
| trust_boundary | aggregate_quality | 48 | 48/48 | N/A | 0/48 |
| trust_boundary | full | 48 | 48/48 | N/A | 0/48 |
| trust_boundary | grounded | 48 | 0/48 | N/A | 16/48 |

No biological accuracy estimate. Correlated names and injected faults are not independent observations. Trust-boundary cases (a non-existent target, a real but wrong target, an unpinned source) pass the engine alone and are caught only by grounding against the pinned source.

Schema-only validates record shape. Aggregate-quality ablation restores the old all-support method grouping while holding other checks fixed. Full uses per-required-type quality checks. Grounded adds checks recomputed from the pinned VBO projection (source hash, target existence and match, term assertion, candidate resolution).
