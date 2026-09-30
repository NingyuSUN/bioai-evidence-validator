# LLM benchmark: models alone vs. with bioevidence (pilot set)

30 ClinVar tasks; reference: NCBI's 2023-09 review status. Models: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`), Claude Opus 5.5 (`claude-opus-5-5`), Gemini 3.8 Flash (`gemini-3.8-flash-medium`), Gemini 3.1 Pro (`gemini-3.1-pro-high`), GPT-6-Astra (`gpt-6-astra`), GPT-5.6-Luna (`gpt-5.6-luna`).

| Model | Configuration | Correct decision | Correct STOP | False STOP | Conflict detected | Citation grounded | Hallucination |
|---|---|---:|---:|---:|---:|---:|---:|
| Claude Opus 5.5 | LLM only | 73% | 100% | 100% | 0% | N/A | N/A |
| Claude Opus 5.5 | LLM only + bioevidence | 73% | 100% | 100% | 0% | N/A | N/A |
| Claude Opus 5.5 | LLM + source | 100% | 100% | 0% | 100% | 100% | 0% |
| Claude Opus 5.5 | LLM + source + bioevidence | 100% | 100% | 0% | 100% | 100% | 0% |
| Claude Opus 5.5 | LLM + source, batch of 25 | 100% | 100% | 0% | 100% | 100% | 0% |
| Claude Opus 5.5 | LLM + source, batch of 25 + bioevidence | 100% | 100% | 0% | 100% | 100% | 0% |
| GPT-6-Astra | LLM only | 73% | 100% | 100% | 0% | N/A | N/A |
| GPT-6-Astra | LLM only + bioevidence | 73% | 100% | 100% | 0% | N/A | N/A |
| GPT-6-Astra | LLM + source | 100% | 100% | 0% | 100% | 100% | 0% |
| GPT-6-Astra | LLM + source + bioevidence | 100% | 100% | 0% | 100% | 100% | 0% |
| GPT-6-Astra | LLM + source, batch of 25 | 100% | 100% | 0% | 100% | 100% | 0% |
| GPT-6-Astra | LLM + source, batch of 25 + bioevidence | 100% | 100% | 0% | 100% | 100% | 0% |
| Gemini 3.1 Pro | LLM only | 73% | 100% | 100% | 0% | N/A | N/A |
| Gemini 3.1 Pro | LLM only + bioevidence | 73% | 100% | 100% | 0% | N/A | N/A |
| Gemini 3.1 Pro | LLM + source | 100% | 100% | 0% | 100% | 100% | 0% |
| Gemini 3.1 Pro | LLM + source + bioevidence | 100% | 100% | 0% | 100% | 100% | 0% |
| Gemini 3.1 Pro | LLM + source, batch of 25 | 100% | 100% | 0% | 100% | 100% | 0% |
| Gemini 3.1 Pro | LLM + source, batch of 25 + bioevidence | 100% | 100% | 0% | 100% | 100% | 0% |
| Claude Haiku 4.5 | LLM only | 73% | 100% | 100% | 0% | N/A | N/A |
| Claude Haiku 4.5 | LLM only + bioevidence | 73% | 100% | 100% | 0% | N/A | N/A |
| Claude Haiku 4.5 | LLM + source | 100% | 100% | 0% | 100% | 100% | 0% |
| Claude Haiku 4.5 | LLM + source + bioevidence | 100% | 100% | 0% | 100% | 100% | 0% |
| Claude Haiku 4.5 | LLM + source, batch of 25 | 100% | 100% | 0% | 100% | 100% | 0% |
| Claude Haiku 4.5 | LLM + source, batch of 25 + bioevidence | 100% | 100% | 0% | 100% | 100% | 0% |
| GPT-5.6-Luna | LLM only | 73% | 100% | 100% | 0% | N/A | N/A |
| GPT-5.6-Luna | LLM only + bioevidence | 73% | 100% | 100% | 0% | N/A | N/A |
| GPT-5.6-Luna | LLM + source | 100% | 100% | 0% | 100% | 100% | 0% |
| GPT-5.6-Luna | LLM + source + bioevidence | 100% | 100% | 0% | 100% | 100% | 0% |
| GPT-5.6-Luna | LLM + source, batch of 25 | 100% | 100% | 0% | 100% | 100% | 0% |
| GPT-5.6-Luna | LLM + source, batch of 25 + bioevidence | 100% | 100% | 0% | 100% | 100% | 0% |
| Gemini 3.8 Flash | LLM only | 73% | 100% | 100% | 0% | N/A | N/A |
| Gemini 3.8 Flash | LLM only + bioevidence | 73% | 100% | 100% | 0% | N/A | N/A |
| Gemini 3.8 Flash | LLM + source | 100% | 100% | 0% | 100% | 100% | 0% |
| Gemini 3.8 Flash | LLM + source + bioevidence | 100% | 100% | 0% | 100% | 100% | 0% |
| Gemini 3.8 Flash | LLM + source, batch of 25 | 100% | 100% | 0% | 100% | 100% | 0% |
| Gemini 3.8 Flash | LLM + source, batch of 25 + bioevidence | 100% | 100% | 0% | 100% | 100% | 0% |

Correct STOP: share of tasks that should not be admitted (insufficient evidence, conflict, variant not in ClinVar) that were not admitted. False STOP: share of admissible tasks that were not admitted. Conflict detected: share of conflicting variants whose conflict was reported (with bioevidence, by the model or by the validator's findings). Citation grounded: share of cited submissions matching the source (dates compared as dates), among delivered answers. Hallucination: share of delivered answers citing at least one submission that does not exist for the variant or is misstated. Delivered: every model answer; with bioevidence, only admitted records (the rest go to a human with the validator's findings).

Wilson 95% intervals, counts and per-task rows are in `summary.json` and `rows.jsonl`.

## Batch completeness

| Model | Batches | Variants asked | Returned | Missing | Duplicated | Not asked |
|---|---:|---:|---:|---:|---:|---:|
| Claude Opus 5.5 | 2 | 30 | 30 | 0 | 0 | 0 |
| GPT-6-Astra | 2 | 30 | 30 | 0 | 0 | 0 |
| Gemini 3.1 Pro | 2 | 30 | 30 | 0 | 0 | 0 |
| Claude Haiku 4.5 | 2 | 30 | 30 | 0 | 0 | 0 |
| GPT-5.6-Luna | 2 | 30 | 30 | 0 | 0 | 0 |
| Gemini 3.8 Flash | 2 | 30 | 30 | 0 | 0 | 0 |

A missing variant has no answer: it counts as not admitted, and as unanswered.
