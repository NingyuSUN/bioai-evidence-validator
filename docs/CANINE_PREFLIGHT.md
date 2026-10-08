# Canine preflight: branch preparation before full-panel integration

`canine-preflight` is additive on the local `canine-panel-validation` branch.
The existing `canine-panel` and `canine-capture` commands and their stored examples
retain their contracts. The new command uses those same pinned reference formats.

```bash
bioevidence canine-preflight examples/canine_preflight/panel.json \
  --snapshot-dir examples/canine_panel/sources --output /tmp/canine-preflight.json
```

The bundled example has six historical source cases, not the current project's
629 events. It deliberately requests target equivalence without supplying target
VCF alleles: that missing work remains visible. Expected exit is 2 (review).
The legacy six-event source snapshots are reused without copying or changing them.

## Purpose and input

The public entry is `validate_canine_preflight(document, store)`. Input has:

- `format_version: canine-preflight-1`, `taxon: NCBITaxon:9615`;
- `catalogue`: every expected event, each with `id` and nonempty `required_checks`;
- optional `panel`: an existing `canine-panel-1` document for executable events;
- optional `allele_requests`: per-event requests with `event_id` and one or both
  of `source_mutant_snapshot_sha256` and `target_variant`;
- optional `previous_report_sha256`: exact bytes of a prior preflight report.

No coordinates or reference names need to be invented for unresolved events:
include them in `catalogue` and omit them from `panel`. All catalogue events are
returned. Duplicate IDs, panel events outside the catalogue, requests without
panel events, unknown checks and unsupported readiness assertions are input errors.
Catalogue completeness is relative to the supplied list; this command cannot
prove that the literature or project inventory is exhaustive.

Checks are `source_reference`, `allele_reconstruction`, `target_equivalence`,
`capture_specificity`, `dosage`, `phase`, and `assay_performance`. The last four
are explicitly **not implemented** here and return `not_assessed`. Existing
specialized capture scripts and `canine-capture` are still separate; their
reports are not imported as proof of these checks. A missing required check
prevents the event and aggregate report from being `verified`.

## Complete allele replay

All supported genomic edits are applied in original source coordinates to the
entire pinned source slice, preserving unchanged flanks and intervening bases.
Supported operations are substitutions, deletions, tandem duplications,
inversions, insertions, deletion-insertions and nonoverlapping combinations.
An insertion goes after its left flank. Supplied compound `event_ref`/`event_alt`
are compared with the outer event span, including unchanged intervening bases.

Unknown inserted bases (`N[length]`), ambiguous reference bases, overlapping edits,
repeat-count notation, transcript coordinates and unsupported forms remain under
review. Unknown payloads are never expanded into apparently recovered sequence.
Reconstructing a proposed compound allele does not verify physical phase.
Source corrections, source holds and original WT-context mismatches remain visible.

`source_mutant_snapshot_sha256` binds **exact uppercase raw ACGT sequence bytes**,
without FASTA header or trailing newline, spanning the entire source context.
Its content is compared with the freshly reconstructed string, not only its hash.
It is a supplied candidate, not evidence of an observed mutant sample.

`target_variant` has `chrom`, one-based `pos1`, and nonempty uppercase ACGT `ref`
and `alt` representing one biallelic VCF edit on the forward target reference.
The command checks target REF, applies the edit to the full target context, orients
that context, and compares it with the full reconstructed source mutant. Symbolic,
multiallelic, empty and ambiguous alleles are unsupported. Source and target WT
contexts must first pass the existing complete-context check. VCF normalization
is not performed; equivalent normalized or unnormalized edits may compare equal.

## Prior-report applicability

Every event fingerprints its catalogue requirements, full source event, allele
request, and referenced snapshot specifications (including assembly, accession,
query key and whole-reference hash). Unrelated events do not invalidate that
fingerprint. The report also hashes the replay implementation and reference loader.
Changes in these dependencies invalidate applicability. Missing or invalid current
reference bytes prevent a historical passing report from claiming applicability.

`same_inputs_and_implementation` means the pinned report claims the same inputs
and implementation. It does **not** authenticate the old producer or its result.
All currently supported inexpensive checks are recomputed on every invocation;
`prior_results_used_to_skip_checks` is always false. No older status can promote
an event. Reuse of expensive server calculations is a later adapter concern and
must bind the actual execution evidence, scope and applicable implementation.

## Output, limits and integration acceptance

Per-check statuses are `verified`, `review_required`, `rejected`, `not_assessed`.
Per-event and aggregate statuses use the first three; required `not_assessed`
checks yield `review_required`. Counts include all catalogue events, with the
executable panel count reported separately. Exit codes are 0 for these engineering
checks verified, 2 for review, 1 for contradictions and 3 for invalid input/configuration.

Assay validation, ordering, reporting and evidence admission remain false. The
command does not measure breed accuracy, authenticate whole-reference receipts,
establish disease causality, freeze loci, or replace laboratory validation.

Before production integration, the canine adapter must supply the full current
event catalogue and correct route-specific required checks, export actual pinned
reference slices and target edits, preserve unresolved events and original evidence,
and reconcile all returned IDs. This branch development does not change the canine
current-draft pointers or declare those 629 events newly validated.

Engineering controls include hand-derived sequences for each operation, reversed
compound order, intervening bases, reverse strand, wrong REF and mutant payload,
unknown inserted length, duplicate/orphan events, missing evidence, old-report
compatibility, changed source holds, and CLI input overwrite protection. These
controls and reused real cases provide software evidence, not independent clinical
labels or an estimate of sensitivity/specificity.

Final branch validation receipts: [2026-10-08 checks](canine_preflight_checks_20261008/README.md).
