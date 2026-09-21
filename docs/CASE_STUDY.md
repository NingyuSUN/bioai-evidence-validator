# Case study: evidence admission beyond schema validity

## Problem

A source label can be structurally valid yet insufficient for training labels or
sample membership. The same mapping may be usable for catalog display while
requiring verified genotype membership and human review for more demanding uses.

The project implements a deterministic evidence-validation layer with a narrow
canine-breed profile. Public inputs are synthetic. It is not a breed classifier,
a truth-verification service or an LLM judge.

## System design

- **LinkML schema:** typed statements, source snapshots, evidence references,
  adjudications and intended uses; required evidence collections are explicit.
- **Versioned policy:** source scope, ambiguous names, source hashes, membership
  requirements and review status. Policy 0.1 is retained alongside default 0.2.
- **Admission engine:** per-use decisions plus a record-wide structural/integrity
  gate, so malformed requests cannot bypass the policy layer.
- **Read-only adapter:** export an existing SQLite snapshot, preserve unresolved
  rows in a separate ledger and verify the database hash before/after export.
- **Audit report:** findings, reason codes, versions and input/schema/policy hashes.

## A concrete engineering failure and its regression

Originally, an empty `requested_uses` list produced zero decisions, so the final
status fell through to `admitted`. An unknown use could also escape findings that
blocked only the six recognized uses. The fix validates the request contract and
makes structural errors reject the entire record. Regression tests also cover
mixed known/unknown uses, non-object JSON, missing evidence and duplicate IDs.

Human acceptance is not allowed to erase a coexisting rejection or deferral.
This preserves conflicting evidence instead of resolving it by list order.

## Validation evidence

The current suite contains 58 tests, run locally on Windows with Python 3.11 and
3.13. Coverage includes schema and policy decisions, CLI exit codes, input/output
preservation, Unicode, simulated write failure and SQLite snapshot integrity.
An isolated wheel installation runs both documented CLI examples and the invalid
use guard, verifying that YAML resources ship with the package. Linux/Windows CI
is defined; remote CI execution is only established by a subsequent Actions run.

## Tradeoffs to explain in an interview

The profile is intentionally narrow because evidence rules depend on the intended
use. LinkML captures structure; the policy engine captures evidence sufficiency.
A successful export and an admitted record are separate outcomes. Audit hashes
support replay and change detection but do not authenticate the human reviewer
or independently verify biological claims. Immutable database snapshots are a
precondition; concurrent database export is outside the adapter contract.

See [engineering contract](ENGINEERING.md) for reproducible commands and error semantics.
