# Expert review, round 1

One workbook that experts fill in, for the three reviews that wait on them (#23). Each expert does the parts in
their field:

| Part | Items | For | Feeds |
|---|---:|---|---|
| A · Variants | 40 ClinVar germline classifications (September 2023): 20 where the validator and NCBI's review status disagree, 20 where they agree, unmarked | Clinical or molecular geneticists | The [ClinVar review kit](../clinvar_review/README.md), and the scoring of the six model reviewers (#22) |
| B · Paper claims | The 60-claim expert sample of the [extraction experiment](../../examples/civic_extraction/README.md) | Cancer genomics, variant curation | Natural extraction errors, labelled with the [error taxonomy](../../docs/ERROR_TAXONOMY.md) (#21) |
| C · Single-cell | A fresh audit sample: 59 auto-admitted cluster annotations and 10 others, unmarked | Single-cell biologists | The [audit](../../docs/GOLD_STANDARD.md#auditing-what-is-admitted-automatically) of what bioevidence admits (#24) |

Every answer is a dropdown with plain options ("yes / no / unsure", "usable as is / needs a curator's check / not
usable"); a comment is optional. The start sheet gives six rules in English and Chinese.

## For the maintainer

```bash
# Build the round. Keep the seed and maintainer/ private: they unblind the items.
uv run --frozen python evaluation/expert_round/make_round.py \
  --clinvar-packet artifacts/clinvar-review/reviewer_packet \
  --clinvar-key artifacts/clinvar-review/maintainer/key.json \
  --seed <private number> --output artifacts/expert-round-1

# Import each returned workbook (one per expert)
uv run --frozen python evaluation/expert_round/import_round.py returned_R1.xlsx \
  --key artifacts/expert-round-1/maintainer/round_key.json \
  --clinvar-key artifacts/clinvar-review/maintainer/key.json --output artifacts/expert-round-1/returned
```

Then each part goes on in its own tools:
- **Part A:** `bioevidence review agreement` and `adjudication-sheet` on `clinvar_annotations.csv`; `bioevidence
  review score` against `maintainer/predictions.csv`; `analyze_models.py` with the expert labels.
- **Part B:** `extraction_labels.csv`, joined with `results/extraction-test/expert_sample/key.jsonl`.
- **Part C:** `bioevidence review audit-score --manifest maintainer/singlecell_audit_manifest.json` on
  `singlecell_annotations.csv`.

Blinding. The workbook shows no model, no route, no validator decision and no reference label. Parts B and C get
new item codes, so the public results cannot be looked up by code. The experts are also asked not to look at this
project's results until they are done.

Strictness. The importer rejects:
- a half-answered row;
- an answer that is not a dropdown option;
- a missing reviewer ID or qualification;
- a second import of the same reviewer.

Nothing is written unless every part is clean.
