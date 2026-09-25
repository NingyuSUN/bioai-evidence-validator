# Data attribution and provenance

`clinvar-sample.jsonl.gz` and `population_outcomes.json` are derived from **ClinVar**,
National Center for Biotechnology Information (NCBI), U.S. National Library of Medicine:
https://www.ncbi.nlm.nih.gov/clinvar/

Upstream files, from the monthly archive at
https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/archive/ :

| File | Bytes | SHA-256 |
|---|---:|---|
| `2023/submission_summary_2023-09.txt.gz` | 201,026,694 | `71c799c2d1bf5dbd4ffffdfc8e3d743093e5ee0c24ba9544ec0cb654ac8141ca` |
| `2023/variant_summary_2023-09.txt.gz` | 210,839,206 | `3c224263fbe8ade318c4bdbfda0e4cef4d449470ad6467bdc504171dc9a1a4e3` |
| `variant_summary_2026-09.txt.gz` | 442,495,433 | `186ad2838a138f0bc7a79b1b7b6dde5533b105175d293e1131652889529804c9` |

NCBI publishes no checksums for archived files; the byte counts matched the server's
`Content-Length` and each file passed a full gzip integrity check when downloaded.

**Terms.** ClinVar states that the information it archives "is freely available to users and
organizations" ([ClinVar intro](https://www.ncbi.nlm.nih.gov/clinvar/intro/)). ClinVar is
not intended for direct diagnostic use or medical decision-making without review by a
genetics professional, and NIH does not independently verify submitted information
([maintenance and use](https://www.ncbi.nlm.nih.gov/clinvar/docs/maintenance_use/)).
To reference a submission or aggregate record, cite its SCV or VCV accession and version.
No endorsement by NCBI or by any submitter is implied.

**Changes.** Selection and stratified sampling are described in `manifest.json`. Only
structured fields are kept (VariationID, gene symbol, aggregate classification, review status
and submitter count; per submission: SCV, submitter, review status, classification,
collection method, date last evaluated). Submitters' free-text descriptions are **not**
redistributed. Submitter names are organization names as published by ClinVar.
`../prepare_source.py` rebuilds both files byte-for-byte (decompressed content) from the
pinned upstream files. Project Python code remains Apache-2.0.
