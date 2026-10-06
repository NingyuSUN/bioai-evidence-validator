# Source-derived canine NGS draft example

This example replays the 154 selected source routes in Canine panel draft v5.
They are source IDs, not 154 independent samples, loci or validated diseases.
The source scope includes 151 genomic candidates, two RNA-only records and one
lesion/somatic record. None has germline admission or assay approval.

```bash
bioevidence canine-capture examples/canine_capture/panel.json \
  --snapshot-dir examples/canine_capture/sources --output /tmp/capture-report.json
```

Expected exit is 2 (`review_required`). 154 requirements are consistent with
their pinned originals. Of 25 source context rows, 19 are compared: eight complete
windows match, 11 retain differences and six lack executable genomic anchors.
Six WT template strings are reconstructed; 12 proposed mutant strings remain
under review. This is not an off-target screen or experimental validation.

The 94 gzip snapshots total approximately 1.18 MB. Their filenames are hashes of
decompressed original bytes. `provenance.json` lists original paths, sizes and
the exact source project commit `14735e23fdd288c56b2cabf54120edb7722dbce6`.
Original source packages remain unchanged. No entire genome, chain, primary
publication full text or sample dataset is bundled.

## Sources and reuse boundaries

The source project is the user's Canine research checkout, development draft v5
dated 2026-10-06. Draft requirements and proposed template metadata are project
research outputs. Source plans retain original publication/OMIA identifiers and
source URLs; those references do not confer clinical acceptance.

The 18 distinct source FASTA slices come from versioned NCBI RefSeq canine
accessions. Their exact accession.version, assembly, interval and retrieval URLs
are preserved in the frozen context-check snapshot, with original retrieval
receipts. For example: [NC_006600.3](https://www.ncbi.nlm.nih.gov/nuccore/NC_006600.3)
and [NC_006595.2](https://www.ncbi.nlm.nih.gov/nuccore/NC_006595.2).
NCBI sequence data retain NCBI/source attribution; this code's Apache-2.0 license
does not relicense external database data or imply rights to a commercial assay.
The target receipt contains selected custom ROSY reference slices; the full
reference is not redistributed and its producer hash is only an assertion here.

This is a frozen **development fixture** reused while developing the checker.
It is not a held-out assay study, independent biological truth or completeness
audit of all canine CNV/SV. See the [contract and limits](../../docs/CANINE_CAPTURE_VALIDATION.md).
