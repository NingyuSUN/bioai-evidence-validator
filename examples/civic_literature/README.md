# Real-source case: CIViC literature grounding

AI tools that cite literature fail in recognisable ways: they invent PMIDs, cite a real paper that
says something else, alter a quote, flip its polarity, change its species, or rely on a retracted
paper. This case measures whether [literature grounding](../../docs/ENGINEERING.md#source-grounding)
catches each of those on **real papers**, and whether it leaves genuine quotes alone.

## Sources

- **CIViC** accepted clinical evidence (CC0), nightly export pinned by SHA-256 in
  [sources/manifest.json](sources/manifest.json); only PubMed-sourced, unflagged items with a direction.
- **PubMed Central** full texts (JATS) of CIViC's papers, kept only when PMC lists them under
  **CC BY or CC0**, so they can be redistributed here unchanged. Of 2,150 CIViC papers, 1,174 are in
  PMC and 315 are CC BY or CC0; 120 were selected in keyed-hash order (all 20 with a
  "Does Not Support" item, then 100 more). Credits: [sources/ATTRIBUTION.md](sources/ATTRIBUTION.md).
- **20 retracted** open-access papers on cancer variants (PubMed "Retracted Publication"), and
  **20 PMIDs that do not exist**, for the negative controls.

Everything was resolved once with NCBI E-utilities by [prepare_source.py](prepare_source.py) and is
committed as gzip-compressed snapshots named by the SHA-256 of their bytes, with the catalog
`sources/snapshots/literature.json`. Validation and the controls run offline from those bytes; the
pipeline refuses a snapshot whose bytes no longer match its name.

## Controls

For each paper, a base record quotes one real sentence (12–60 words, preferring one that names the
gene of a CIViC item) at its paragraph. The [profile](profile.yaml) allows model-extracted quotes but
requires them to be verified against the pinned full text (`verified_evidence_types`). Five controls
change the base record the way an AI citation goes wrong; retracted papers get base records of their own.

| Control | Change | Expected finding |
|---|---|---|
| Fabricated identifier | The PMID does not exist | BEV016 |
| Real identifier, wrong paper | The PMID of another corpus paper | BEV017 |
| Altered quote | One word removed from the middle | BEV017 |
| Negation flip | "not" inserted after the first auxiliary verb, or removed | BEV017 |
| Species swap | patients ↔ mice, human ↔ mouse, … | BEV017 |
| Retracted source | A real quote from a retracted paper | BEV019 |

```bash
uv run python examples/civic_literature/run.py --output artifacts/civic-literature
```

## Results

| Control | Records | Detected (Wilson 95%) | Admitted |
|---|---:|---:|---:|
| Fabricated identifier | 120 | 120 (96.9–100%) | 0 |
| Real identifier, wrong paper | 120 | 120 (96.9–100%) | 0 |
| Altered quote | 120 | 120 (96.9–100%) | 0 |
| Negation flip | 82 | 82 (95.5–100%) | 0 |
| Species swap | 27 | 27 (87.5–100%) | 0 |
| Retracted source | 20 | 20 (83.9–100%) | 0 |

Genuine quotes: **0/120 blocked** (Wilson 95% 0–3.1%). Controls that a sentence does not allow (no
auxiliary verb to negate, no species word) are skipped and counted in [results/summary.md](results/summary.md).

## What this does not show

- The controls alter text; grounding compares text. A **verbatim quote read the wrong way** (a
  negative finding reported as support, a mouse result used for a human claim) passes, and so
  does a real quote that does not support the claim. That needs semantic review, which the
  [LLM benchmark](../../evaluation/llm_benchmark) measures separately.
- Papers without open full text cannot be checked: they go to review (BEV015), never admitted.
- Retraction status is as PubMed recorded it on the retrieval date; later retractions are seen only
  after grounding again (`bioevidence ground --refresh`).
- Controls on one paper are correlated, and the corpus is limited to openly licensed papers.
