# ClinVar expert-review kit

Status: **ready for reviewers; no reviews collected yet.**

The [ClinVar case](../../examples/clinvar_germline/README.md) found 95 sampled variants where
the validator and NCBI's own 2023-09 review status disagree, almost always because the
validator holds back a pathogenic classification that carries a dissenting submission. Three
years later those classifications were markedly less stable, but *stability is not
correctness*. This kit asks domain experts directly, following the project's
[gold-standard protocol](../../docs/GOLD_STANDARD.md):

> Given only the submissions ClinVar held in September 2023, is a pathogenic / likely
> pathogenic classification sufficient for each intended use?

## What reviewers get, and what they do not

| Reviewers see | Hidden from reviewers |
|---|---|
| An opaque case code (e.g. `C3F9A21`) and the gene symbol | VariationID and submission accessions (they would reveal the current ClinVar record) |
| Every 2023-09 submission: submitter, assertion criteria / expert panel / practice guideline, classification, collection method, date last evaluated | ClinVar's aggregate review status and stars |
| The [rubric](RUBRIC.md) defining the three uses in curation terms | Validator decisions, reason codes and which cases are "divergent" |
| | 2026-09 outcomes |

Cases: all **95 divergent** variants plus **95 agreeing controls** matched by review-status
stratum, so reviewers cannot tell which is which. The first 20 cases in code order form a
**calibration** set (split `development`), which is discussed and excluded from scoring; the
other 170 are the **test** set. Each case needs one statement label and three use labels.

**Time.** Plan for roughly 3–6 minutes per case, i.e. about 10–19 hours per reviewer for all
190. Sizes are adjustable (`--controls-per-divergent`, `--calibration`).

## Steps

Run from the repository root after `uv sync --frozen --extra dev`.

**1. Prepare packets** (once):

```bash
uv run --frozen python evaluation/clinvar_review/prepare_packets.py --output artifacts/clinvar-review
```

- `artifacts/clinvar-review/reviewer_packet/`: send **the same folder to every reviewer**
  (`review_workbook.xlsx` with dropdowns, `labels.csv` / `evidence.csv` as a fallback, `RUBRIC.md`).
- `artifacts/clinvar-review/maintainer/`: **keep private** until all reviews are in. `key.json`
  maps codes to variants and holds the secret salt; `predictions.csv` holds the validator and
  NCBI decisions to be scored; `manifest.draft.json` starts the reference-set manifest.

**2. Calibration round.** Reviewers label only the `calibration` rows, independently, and
return their workbooks. Import them (step 4; blank rows are skipped), run the agreement
report (step 5), then meet to discuss the calibration cases and clarify the rubric. If the
rubric wording changes, raise its version in `RUBRIC.md` and `prepare_packets.py`.

**3. Test round.** Reviewers complete the `test` rows independently, without discussion.

**4. Import each reviewer's workbook:**

```bash
uv run --frozen python evaluation/clinvar_review/import_sheets.py reviewer_R1.xlsx \
  --key artifacts/clinvar-review/maintainer/key.json --reviewer-id R1 \
  --qualification "Clinical molecular geneticist, 8 years of variant curation" \
  --annotated-at 2026-10-15 --output artifacts/clinvar-review/annotations.csv
```

Each case becomes three rows (one per use) in the protocol's
[annotation format](../gold_standard/README.md). A half-filled row, an unknown code or a
second import of the same reviewer is rejected, and the file is left unchanged.

**5. Agreement before adjudication:**

```bash
uv run --frozen bioevidence review agreement artifacts/clinvar-review/annotations.csv \
  --output artifacts/clinvar-review/agreement.json
```

Krippendorff's α (with a bootstrap 95% interval), Cohen's κ for two reviewers, and raw
agreement, per use. Report these whatever they are.

**6. Adjudicate disagreements:**

```bash
uv run --frozen bioevidence review adjudication-sheet artifacts/clinvar-review/annotations.csv \
  --output artifacts/clinvar-review/adjudications.csv
```

One blank row per disagreeing case-use. A third expert, or the reviewers together, fills in
the final labels, adjudicator ID, time and reasons, using both reviewers' rows in
`annotations.csv` (linked by `annotation_ids_json`). Original reviews are never edited.

**7. Score** the validator and NCBI's review status against the resolved labels (test split):

```bash
uv run --frozen bioevidence review score --annotations artifacts/clinvar-review/annotations.csv \
  --adjudications artifacts/clinvar-review/adjudications.csv \
  --predictions artifacts/clinvar-review/maintainer/predictions.csv \
  --output artifacts/clinvar-review/score.json
```

Results are reported for all cases and separately for `divergent` and `control` cases. The
key number is on the divergent subset: where the two disagree, which one do experts side with?

**8. Freeze and publish:**

```bash
uv run --frozen bioevidence review freeze --manifest artifacts/clinvar-review/maintainer/manifest.draft.json \
  --annotations artifacts/clinvar-review/annotations.csv \
  --adjudications artifacts/clinvar-review/adjudications.csv \
  --file artifacts/clinvar-review/maintainer/predictions.csv --file artifacts/clinvar-review/maintainer/key.json \
  --dataset-id clinvar-germline-expert-review --version 1 --frozen-at 2026-11-01T00:00:00Z \
  --output artifacts/clinvar-review/manifest.json
```

Then commit `annotations.csv`, `adjudications.csv`, `agreement.json`, `score.json`,
`manifest.json` and the key into `evaluation/clinvar_review/results/`, and update the ClinVar
case README, which currently states that no independent expert annotation exists.

## Model reviewers (optional)

The same packet can be given to LLMs, to measure which parts of expert review they could take
over. `model_reviewers.py` drives three command-line agents: Claude Code (`claude`), Codex
(`codex`) and Antigravity (`agy`, for Gemini). Each model gets exactly what a human reviewer
gets: the rubric and one case under its code. It answers through a JSON schema.

```bash
# Where the CLIs are installed (e.g. WSL); reads only reviewer_packet/, never the key
python3 evaluation/clinvar_review/model_reviewers.py run \
  --packet artifacts/clinvar-review/reviewer_packet --output artifacts/clinvar-review/models \
  --set calibration                     # start small; --limit N, --codes, --backends

# Maintainer, with the key: protocol annotations + predictions for scoring
uv run --frozen python evaluation/clinvar_review/model_reviewers.py export \
  --output artifacts/clinvar-review/models --key artifacts/clinvar-review/maintainer/key.json
uv run --frozen bioevidence review agreement artifacts/clinvar-review/models/model_annotations.csv
```

- **Isolation.** One case per call. Every call is a fresh, non-interactive session in an empty
  temporary directory, so the model cannot read the key or other cases.
- **No lookups.**
  - Claude Code runs with every tool disabled.
  - Codex runs without browser tools or your user config and MCP servers, in a read-only sandbox.
  - Antigravity cannot switch off web search. Its tool calls are detected from the event stream.
  - A case answered after a tool call is retried once. If a tool is used again, the case is kept
    but marked `later_information_seen = yes`.
- **Record.** `manifest.json` records model IDs, CLI versions and hashes of the rubric, prompt
  and schema. `raw/` keeps every answer. `runs.csv` lists time, tokens and tool use per call.
  Re-running resumes, so cases already answered are skipped.
- **Cost, from a pilot run.** Per case: Claude Opus 5.5 took about 10 s and 7k input tokens;
  GPT-6-Astra about 23 s and 24k; Gemini 3.1 Pro about 15 s and 7k. With the default two
  concurrent calls per model, all 190 cases take roughly 40 minutes.
- **Comparison.**
  - `model_predictions.csv` can be passed to `bioevidence review score` in place of, or merged
    with, `maintainer/predictions.csv`. Each model is then scored against the expert labels,
    per subset.
  - Agreement among the models alone shows how much they overlap. It is not a measure of
    correctness.

Model labels are **not independent human annotations**. Keep them in their own files, never in
`annotations.csv`, and never use them to resolve an expert disagreement.

## Interpreting the result

- With two independent reviewers and adjudication this is an **independently reviewed
  reference set** for this task. With one reviewer, `freeze` labels it a **single-reviewer
  reference set**; say so wherever the numbers are quoted.
- It measures agreement with expert judgment of *evidence sufficiency for a use*, on one
  sample of one registry. It does not establish variant pathogenicity or clinical validity.
- Do not change the profile in response to the test-set labels. Any later profile version needs
  a separately reported evaluation.
- Publish reviewer IDs and one-line qualifications only with each reviewer's consent.
