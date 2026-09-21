# ADR-001: Start with the canine breed catalog profile

## Status

Accepted for MVP 0.1.

## Context

The initial idea covered arbitrary biological claims. That scope would force
unrelated policies for traits, inherited disease, somatic cancer, breed catalogs,
and vendor coverage into one validator. The existing private canine project has
an immediate need for auditable breed concept and source-label decisions.

## Decision

The first profile validates four statement types:

1. breed catalog membership;
2. breed name equivalence;
3. source-label assignment;
4. explicitly typed breed relationships.

The semantic schema is authored in LinkML. Deterministic policy checks are
versioned separately. Human adjudication never overwrites source evidence or
automated findings. Admission is decided per intended use.

The public package contains only synthetic fixtures. A private canine-panel
adapter may later export evidence bundles without moving company data into this
repository.

The read-only adapter described above was implemented in package 0.2; see
[adapter documentation](CANINE_PANEL_ADAPTER.md).

## Consequences

- Disease, trait, cancer, and vendor policies are deferred.
- Marker discrimination and classifier accuracy are explicitly out of scope.
- A source-label mapping may be admitted for one dataset while remaining
  inadmissible as a training or external-validation label.
- The validator records exact input and policy hashes for replay.
