# Canine panel reference validation — specialization branch

The local `canine-panel-validation` branch extends 0.8.0. It adds an offline
reference-consistency report and keeps the generic evidence-admission engine
unchanged. No release or merge to main is implied.

```bash
bioevidence canine-panel examples/canine_panel/panel.json \
  --snapshot-dir examples/canine_panel/sources \
  --output canine-panel-report.json
```

Exit codes are 0 for engineering checks verified, 2 for review required, 1 for
contradictions/malformed supported input and 3 for invalid input/configuration.
**A zero exit code does not admit evidence or establish a usable assay.**

## What it checks

- The exact SHA-256 of every reference snapshot, including unused references.
- NCBI interval FASTA accession versions, forward genomic bounds, actual sequence
  length and alphabet, canine species text and the exact assembly name in the
  header. Embedded EFetch JSON is checked against its actual FASTA bytes.
- Entire absolute RefSeq `g.` descriptions in a deliberately limited subset:
  substitutions, deletions, tandem duplications, inversions, insertions and
  deletion-insertions; non-overlapping components on one bracketed allele.
  Both endpoints, insertion adjacency, inclusive deletion length, redundant
  historical suffixes, actual REF bases and supplied unanchored event alleles
  are checked. `N[223]` remains 223 unknown bases, not a recovered insert.
  Numeric coordinate/length fields are bounded to 18 digits; oversized values
  and malformed reference JSON yield findings instead of escaping a per-event
  report. Compound supplied REF/ALT are retained with an explicit unchecked
  status because complete compound-allele reconstruction is unavailable.
- A source/target comparison uses the **whole supplied context**, strand and
  event offset. Matching a base or mapped endpoint alone cannot pass. Each
  source/target slice must cover the complete event span.
- An original HGVS and reviewed candidate stay separate. A correction or an
  explicitly held source issue continues to require review, even when the
  candidate's sequence checks succeed. Compound phase is not inferred.

Reference receipts are useful when a custom target genome is too large to ship.
The snapshot hash pins a producer's receipt, which binds the claimed whole-genome
hash, slice sequence hash and interval. This command **does not independently
re-hash the whole genome or authenticate that producer**. The report calls this
`PINNED_PRODUCER_RECEIPT_ASSERTION`; upstream execution receipts and the trusted
producer remain part of the provenance contract.

## What remains outside the check

This is not a full HGVS grammar or a normalization tool. Transcript coordinates,
intronic offsets, uncertain breakpoints, reference-derived insert sequences,
repeat-number notation, overlapping components and other accession families go
to review. It does not prove the HGVS 3′ rule, physical breakpoint uniqueness,
allele phase, disease association, penetrance, germline origin, breed scope,
copy-number baseline, capture/PCR specificity, mosaic sensitivity or assay
performance. Reference identity is conditional on the supplied trusted snapshots;
content hashes do not authenticate the public database or a remote execution.
Reports bind the exact `canine.py` and snapshot-loader implementation bytes as
well as their input and reference hashes. `package_base_version=0.8.0` identifies
the base version; the implementation hashes distinguish this local specialization
from the released 0.8.0 package.

The real source-based example contains six candidate events, not independent
clinical labels. It preserves DLL3's original missing `g.` and its separate
reviewed candidate. Its sequence checks are source-derived engineering evidence,
not disease/clinical validation. Authored unit-test controls are explicitly
synthetic; no benchmark accuracy or true positive rate is claimed.

This branch also repairs a 0.8.0 assembly bug: `CanFam3.1` and
`UU_Cfam_GSD_1.0` were truncated at their first decimal point. Decimal names are
now retained, while `GRCh38.p14` still maps to `GRCh38`. A genome build named in
the pinned reports is recognized even when it is not in the common-name list.

## Input contract

Use `format_version: canine-panel-1` and `taxon: NCBITaxon:9615`. References have
unique IDs, exact assembly/sequence IDs, snapshot hashes and one of
`ncbi_fasta`, `ncbi_efetch_json`, `reference_receipt_json`. Receipt references also
declare the query key and expected whole-reference hash. Snapshots are files
named by their SHA-256 (optionally compressed as supported by `SnapshotStore`).

Each event retains `source_hgvs` and `source_assembly`; optional `reviewed_hgvs`
is an explicit correction. Link `source_reference` and, for portability,
`target_reference`, `target_assembly`, inclusive `target_start1`/`target_end1` and
`target_strand`. Optional `event_ref`/`event_alt` are unanchored event alleles,
**not normalized VCF**. `held_reasons` records unresolved source issues.
Unknown keys, duplicate IDs and false declarations such as `reportable: true`
are rejected by the input contract. Findings never overwrite source descriptions.

The report always declares admission not assessed, whole-reference specificity
not performed, and `assay_validated=false`, `reportable=false`, `probe_ready=false`.
Retain the generic evidence profile and original-paper review alongside this
report; a reference match is a different question from whether the evidence
supports a biological or clinical claim.
