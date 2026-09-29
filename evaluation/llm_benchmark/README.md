# LLM benchmark: what bioevidence adds to a model

The question is practical: **if a curation team already uses an LLM, what does putting this validator
behind it change?** Each model answers each task once per condition. The same answer is then scored
twice: as the model gave it, and after bioevidence has built it into an evidence record, validated it
with the case's profile and grounded it against the pinned source. The "+ bioevidence" rows therefore
make no extra model call; every difference between a pair of rows comes from the validator.

## Tasks

| Suite | Task | Reference answer | Sizes (pilot / test) |
|---|---|---|---|
| ClinVar (structured) | May this variant's P/LP classification enter a clinical reference set? List the ClinVar submissions behind the answer. | NCBI's own 2023-09 review status (not this repository's rules) | 30 / 150 |
| Literature | Does this open-access paper support a CIViC-style claim, report evidence against it, or not address it? Quote the sentences that show it. | CIViC's curation of that paper; unrelated claims (gene never mentioned) should stop | 18 / 96 |

Tasks are built deterministically ([tasks.py](tasks.py), [tasks_literature.py](tasks_literature.py))
from the pinned [ClinVar sample](../../examples/clinvar_germline) and the pinned
[CIViC literature corpus](../../examples/civic_literature). Pilot and test sets share no variant and no paper.
The runner reads only the task files, never the references.

## Conditions and configurations

| Configuration | What the model sees | Who decides |
|---|---|---|
| LLM only | The variant ID and gene, or the claim with the paper's PMID and title | The model |
| LLM only + bioevidence | Same answer | The validator (the model's answer is still shown to the reviewer) |
| LLM + source | The variant's ClinVar submissions, or the paper's full text with paragraph ids | The model |
| LLM + source + bioevidence | Same answer | The validator |
| LLM + source, batch of 25 (ClinVar only) | 25 variants and their submissions in one prompt | The model, then the validator |

Models: each vendor's most capable model and its small, fast tier, through their CLIs in a fresh
session per call with tools disabled where the CLI allows it (tool use is detected and reported):
Claude Opus 5.5 and Claude Haiku 4.5, GPT-6-Astra and GPT-5.6-Luna (GPT-5.4-Mini is not available to
ChatGPT accounts), Gemini 3.1 Pro and Gemini 3.8 Flash.

## Metrics

- **Correct decision**: the final decision equals the reference.
- **Correct STOP**: tasks that should not be answered (insufficient or conflicting evidence, a variant
  ClinVar never assigned, a paper that never mentions the gene) that were not answered.
- **False STOP**: answerable tasks that were not answered. A validator that blocks everything would
  score perfectly on Correct STOP and fail here.
- **Conflict detected** (ClinVar) / **Negative finding detected** (literature).
- **Citation grounded**: cited submissions matching the source, or quotes found verbatim in the paper,
  among delivered answers. Measured by the scoring code's own comparison, independent of the grounder.
- **Hallucination**: delivered answers with at least one citation that does not exist, is misstated,
  or is not in the paper.

"Delivered" means every answer the model gave (excluding stops); with bioevidence, only admitted
records. Everything else goes to a human with the validator's findings. All rates come with Wilson
95% intervals in `summary.json`.

## What the pilot changed

The pilot sets exist to find problems in the protocol before the test run:

- ClinVar dates: models rewrote `Sep 08, 2016` as `2016-09-08`, or `-` as an empty string. That is a
  change of format, not of content, so dates are compared as dates, and the record builder normalises them.
- With bioevidence, the model's own conflict flag still counts: the validator adds findings and hides nothing.
- GPT-5.4-Mini is refused for ChatGPT accounts, so GPT-5.6-Luna is the fast GPT model.
- Literature prompts first gave section headings paragraph ids, and models cited a heading's id for
  the paragraph under it; headings are now shown without ids.
- Genuine quotes failed on JATS spacing (`( Figure 2 )`) and on a trailing `(Table 2)` the quote left
  out. Both the grounder and the scoring code (separately) now tolerate exactly these two differences.
  Of the quotes the first pilot flagged, most were these; one remained a real error (two
  non-adjacent sentences stitched into one quote).
- Two kinds of literature task could not be answered from what the models see, and are now left out:
  CIViC items whose clinical significance is "N/A" (the claim states no hypothesis: every model and
  every reviewer "misread" one), and claims whose gene or specific protein change the paper's text
  never names (the evidence is in a figure; every model rightly stopped). Seven pilot tasks were
  replaced and rerun; the replaced answers are kept outside the repository, not scored.
- ClinVar result: with the source in the prompt, all six models were perfect on every metric, in
  single and batch mode; without it, all six stopped on every task. On clean structured data the
  validator adds a guarantee and an audit trail, not a measurable accuracy gain. The literature suite
  was added because free text is where models are expected to go wrong.

Prompts, schemas, tasks and scoring are fixed by hash in each run's `manifest.json` before the test run;
any change after that is reported as a separate run.

## Pilot results

These are the pilot sets only (six models; ClinVar 30 tasks, literature 18 tasks). The held-out test
sets are built but have not been run. Per-model tables with Wilson intervals:
[ClinVar](results/pilot/summary.md), [literature](results/literature-pilot/summary.md).

Literature, six models pooled (108 answers; 72 answerable, 24 of them CIViC "does not support"):

| Configuration | Correct decision | False STOP | Negative finding detected | Wrong direction | Quotes found in the paper | Answers with a quote not in the paper |
|---|---:|---:|---:|---:|---:|---:|
| LLM only (no paper) | 39/108 | 69/72 | 0/24 | 0/72 | 2/3 | 1/3 |
| LLM only + bioevidence | 38/108 | 70/72 | 0/24 | 0/72 | 2/2 | 0/2 |
| LLM + paper | 99/108 | 4/72 | 20/24 | 5/72 | 165/165 | 0/68 |
| LLM + paper + bioevidence | 99/108 | 4/72 | 20/24 | 5/72 | 165/165 | 0/68 |

ClinVar: with the submissions in the prompt, every model answered all 30 tasks correctly with exact
citations, alone and in batches of 25; without them, every model stopped on every task. The
validator changed no decision.

What this shows:

- **With the source, current models quote faithfully; without it, they almost always abstain.**
  All 165 quotes given with the paper were in it. Without the paper, three answers quoted the title
  from the prompt; one of those (Claude Opus 5.5) had reworded it, and grounding stopped that answer.
- **The errors that remain are semantic.** 5 of 72 answers took the wrong direction, all with
  verbatim quotes, on 2 of 12 answerable tasks: ALCAM (CD166) expression and fluorouracil resistance
  in colorectal cancer (three models), and a CYP2D6 meta-analysis whose headline conclusion is
  negative while a secondary endpoint is positive (two models). Text grounding cannot see these.
- **The validator's value is a guarantee, not an average.** When a citation is invented, altered,
  retracted or points at the wrong paper, it is stopped: 100% on the real-paper controls of the
  [CIViC case](../../examples/civic_literature) and on the injected faults of the
  [ClinVar](../../examples/clinvar_germline) and [VBO](../../examples/vbo_canine) cases, with no false
  blocks on real sources. Every admission comes with a report of what was checked.

Next: a semantic check for whether a verbatim quote supports the claim's direction
([#31](https://github.com/NingyuSUN/bioai-evidence-validator/issues/31)), which is where the remaining
errors are.

## Run

```bash
python3 evaluation/llm_benchmark/run_models.py --split pilot --output artifacts/llm-benchmark
python3 evaluation/llm_benchmark/run_models.py --suite literature --split pilot --output artifacts/llm-benchmark
uv run --frozen python evaluation/llm_benchmark/score.py --split pilot --answers artifacts/llm-benchmark \
    --output evaluation/llm_benchmark/results/pilot
uv run --frozen python evaluation/llm_benchmark/score_literature.py --split pilot --answers artifacts/llm-benchmark \
    --output evaluation/llm_benchmark/results/literature-pilot
```

The runner needs only the standard library and the model CLIs (run it where they are installed, e.g.
WSL). Scoring replays the committed `answers.jsonl` byte for byte when `--answers` is omitted.

## Limits

- Model outputs vary between runs and versions; the committed answers are one run.
- References are CIViC's and NCBI's curation, not independent expert labels (#23).
- The literature corpus is limited to openly licensed papers, and unrelated claims are an easy
  kind of STOP. Grounding checks that quotes are real, not that they support the decision.
