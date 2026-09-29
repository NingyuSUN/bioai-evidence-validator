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
| Literature | Does this open-access paper support a CIViC-style claim, report evidence against it, or not address it? Quote the sentences that show it. | CIViC's curation of that paper; unrelated claims (gene never mentioned) should stop | 18 / 92 |

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

## Scenario 1: the way people actually ask

The pilots above give models the source and the curation rules ("never invent", "stop if you cannot
verify"). Here the same 18 literature tasks are asked as a user would ask a chatbot: no rules, no source,
no tools. Whatever changes comes from the workflow, not from model capability.

1a. The claim, the paper's PMID and title ([results](results/literature-plain-pilot/summary.md)); six models pooled:

| Configuration | Correct decision | Answers with an invented quote | Answers without a quote | Quotes found in the paper | Wrong direction |
|---|---:|---:|---:|---:|---:|
| LLM alone | 75/108 | 32/49 | 12/49 | 11/69 | 4/72 |
| LLM + bioevidence | 41/108 | 0/5 | 0/5 | 5/5 | 0/72 |

1b. The claim only; the model picks the papers and gives PMID, title and quote
([results](results/literature-claims-pilot/summary.md), [score_claims.py](score_claims.py)). The 50 cited
PMIDs were resolved with NCBI; full texts that are not openly licensed stay outside the repository, which
keeps what was verified (`verification.jsonl`).

| Configuration | Answered | Correct decision | Answers with an invalid citation | Answers with only verified citations | Answers without a citation |
|---|---:|---:|---:|---:|---:|
| LLM alone | 50/108 | 46/108 | 34/50 | 1/50 | 9/50 |
| LLM + bioevidence | 1/108 | 1/108 | 0/1 | 1/1 | 0/1 |

Of the 66 citations the models gave: 28 had a real PMID that belongs to an unrelated paper (the title
cited is often a real paper, with a mistyped or invented PMID: 28284562 for the NEMO trial, whose PMID is
28284557), 16 quoted text absent from the open full text, 16 had no open full text, 2 PMIDs did not
exist, 1 had no PMID, and 3 were verified.

What this shows: asked without the source and without the rules, every model, frontier or fast, cites
papers and quotes that do not check out. Bioevidence admits none of them: it admitted the one answer
whose citations all verified (and whose decision was right), rejected 33 for a wrong paper, a quote not in
the paper or a PMID that does not exist, and sent 7 with no open full text to review. It cannot turn these answers
into good ones; that takes the source (the pilots above) or a curator.

## Semantic checks (#31)

Grounding cannot tell whether a verbatim quote supports the claim, so two semantic layers were
measured on the same pilot ([semantic_eval.py](semantic_eval.py), [results](results/semantic-pilot/summary.md)):

- **Independent review.** A fast model from another vendor (Claude Haiku 4.5, GPT-5.6-Luna or
  Gemini 3.8 Flash) sees the claim, the quotes and their paragraphs, never the extractor's decision.
  Its reading becomes a non-human adjudication under `require_independent_review` (BEV021): accept if it
  matches the extractor, defer otherwise. With two reviewers, both other vendors must accept.
- **Semantic cues** (`CueChecker`, BEV022): negation against a positive claim, and animal or in-vitro
  quotes for a human-scoped item.

Controls (reviewers see only the claim and quotes):

| Control | Claude Haiku 4.5 | GPT-5.6-Luna | Gemini 3.8 Flash | Cues |
|---|---:|---:|---:|---:|
| Correct answers read the right way (so a flipped direction is exposed) | 59/63 | 63/63 | 62/63 | flip flagged 28/63 |
| Another task's claim recognised as not addressed | 7/12 | 11/12 | 12/12 | — |
| Animal or cell-line sentence recognised as such | 7/8 | 7/8 | 7/8 | 8/8 |
| Hedged sentence recognised as hedged | 8/12 | 9/12 | 8/12 | — |
| Correct answers flagged (cost) | — | — | — | 22/63 |

The 68 natural answers with the paper, 5 of them in the wrong direction:

| Pipeline | Wrong direction admitted | Correct answers sent to a human |
|---|---:|---:|
| Grounding | 5/68 | 0/63 |
| + cues | 4/68 | 23/63 |
| + one independent reviewer | 4/68 | 2/63 |
| + two independent reviewers | 4/68 | 4/63 |

What this shows:

- **Reviewers catch clear misreadings cheaply.** On controls, a reviewer from another vendor almost
  always reads a correct answer's quotes the right way, so a flipped direction on clear text is
  exposed, at a cost of 2–4 of 63 correct answers sent to a human.
- **They do not catch the misreadings that actually happened.** The five natural errors sit on two
  tasks where the evidence is mixed: a CD166 (ALCAM) paper reporting no significant association with
  pathologic response although CIViC curates it as supporting resistance, and a meta-analysis whose
  secondary endpoint is positive while its conclusion is negative. There the reviewers mostly agreed
  with the extractors (1 of 5 caught): the errors are correlated across vendors, and agreement between
  models is not evidence.
- **Cues are too noisy to gate on.** They flagged 22 of 63 correct answers and caught 1 of 5 errors.

Which semantic decisions can be automated: flagging a direction, claim or species that clearly does
not match the quoted text (independent review, as a route to a human, never an admission on its own).
Which need experts: evidence that is mixed, depends on the endpoint, or where the curated label and
every model disagree; these are exactly the cases the expert review (#23) is for. Five errors on two
tasks are too few for rates; the held-out test set would measure them with intervals.

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
