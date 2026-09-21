# ADR-002: Domain-neutral main, canine specialization on a branch

Status: accepted for 0.4; supersedes ADR-001 as the main-branch architecture.

## Context

The portfolio project's intended scope is evidence validation across BioAI applications.
The canine MVP demonstrated the pattern but made its entity model, rule IDs, allowed
uses, default schema, and CLI specific to one domain.

## Decision

Keep the operational canine implementation on `canine-breed`. Main uses a common model:
typed entities, a scoped relation, located evidence, versioned source artifacts, and
statement/use-bound adjudications. Fixed code checks structural integrity and evidence
consistency. Strict YAML profiles declare type/relation allowlists and per-use evidence
and human-review requirements. The engine does not dispatch on domain/profile IDs.

Ship general, literature-claim, dataset-label, and standalone assay examples. A regression
constructs a novel organoid/imaging profile using only configuration to verify that
extensibility is real. Admission always names and hashes the selected contract.

## Consequences

- Main has no breed-specific default, adapter, schema, or hidden genotype checks.
- Existing canine consumers use the preserved branch; migration is explicit and breaking.
- New domains can reuse the admission machinery without borrowing canine semantics.
- Declarative profiles do not encode arbitrary scientific reasoning. Complex interpretation,
  numerical analysis, ontology reasoning, and source authentication remain upstream concerns.
- Examples demonstrate behavior on synthetic records, not clinical validation or model accuracy.
