# Canine capture draft consistency

`canine-capture` is opt-in on the local `canine-panel-validation` branch. It
extends the canine source/reference checks with a separate requirements contract.
It does not change the generic admission engine or release package version.

```bash
bioevidence canine-capture examples/canine_capture/panel.json \
  --snapshot-dir examples/canine_capture/sources --output capture-report.json
```

The public Python entry is
`bioevidence_validator.canine_capture.validate_canine_capture(document, store)`.
The document uses `format_version: canine-capture-1`, canine taxon 9615 and
SHA-256 bindings for `requirements` and `method_constraints`. Optional
`context_mapping`, `context_checks`, `target_reference_receipt` and `templates`
have the same snapshot binding convention. Context checks require mappings and
the target receipt; templates require all three. Snapshots named `HASH.gz` are
decompressed before verification; hashes refer to the original bytes.

Checks performed:

- Source-ID count/uniqueness, frozen per-event plans or exact registry/component
  rows, source gene/route identity and method snapshot binding.
- NGS with preferred hybrid capture, PE300 with two nominal 300 bp ends, explicit
  denial of guaranteed contiguous 600 bp and unsupported readiness claims.
- X calibration, reciprocal inversion junctions, deletion sequence evidence,
  compound component phase, germline/RNA/somatic scope and retained interpretation
  conflicts. These check the written requirements, not actual event structure.
- Signed endpoint span and insertion adjacency recomputed from mapped points;
  source TSD length remains a producer assertion. No TSD supplied establishes
  boundary consistency only, not biological absence of a TSD.
- Exact source FASTA header/version/assembly/interval and receipt sequence hashes,
  oriented whole-window equality and 100 bp flanks. Local agreement never clears
  a complete-window hold. A null original accession may use an explicit follow-up
  assertion to compare bytes, but its assembly mapping remains under review.
- WT template alphabet/length/hash and sequence reconstructed from actual target
  flanks. Every linked source ID must be replayed. Mutant payload reconstruction
  is not independently performed and always remains under review.

`requirements_consistency_counts.verified` means the requirements faithfully
follow their declared source and these checks. It is distinct from
`events[].design_status`, which stays `review_required`. Overall status is
`review_required` for a consistent draft, `rejected` for contradictions; malformed
input is an explicit input error. CLI exits are 2, 1 and 3 respectively.

Every report hashes input and implementation files, lists declared snapshot
dependencies (not a claim that every dependency was verified), and returns
`assay_validated`, `probe_ready`, `orderable` and `reportable` as false. No samples
are experimentally evaluated. Whole-genome/chain receipts are producer
assertions; their authenticity and whole-reference specificity are outside this
entry. It does not establish causality, population risk, true phase, repeat
length, capture chemistry or performance. Authored counterexamples and the frozen
development data are engineering tests, not independent clinical labels.
