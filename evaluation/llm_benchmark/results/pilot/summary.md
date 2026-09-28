# LLM benchmark: models alone vs. with bioevidence (pilot set)

30 ClinVar tasks; reference: NCBI's 2023-09 review status. Models: Claude (`claude-opus-5-5`), GPT (`gpt-6-astra`), Gemini (`gemini-3.1-pro-high`).

| Model | Configuration | Correct decision | Correct STOP | False STOP | Conflict detected | Citation grounded | Hallucination |
|---|---|---:|---:|---:|---:|---:|---:|
| Claude | LLM only | 73% | 100% | 100% | 0% | N/A | N/A |
| Claude | LLM only + bioevidence | 73% | 100% | 100% | 0% | N/A | N/A |
| Claude | LLM + source | 100% | 100% | 0% | 100% | 100% | 0% |
| Claude | LLM + source + bioevidence | 100% | 100% | 0% | 100% | 100% | 0% |
| GPT | LLM only | 73% | 100% | 100% | 0% | N/A | N/A |
| GPT | LLM only + bioevidence | 73% | 100% | 100% | 0% | N/A | N/A |
| GPT | LLM + source | 100% | 100% | 0% | 100% | 100% | 0% |
| GPT | LLM + source + bioevidence | 100% | 100% | 0% | 100% | 100% | 0% |
| Gemini | LLM only | 73% | 100% | 100% | 0% | N/A | N/A |
| Gemini | LLM only + bioevidence | 73% | 100% | 100% | 0% | N/A | N/A |
| Gemini | LLM + source | 100% | 100% | 0% | 100% | 100% | 0% |
| Gemini | LLM + source + bioevidence | 100% | 100% | 0% | 100% | 100% | 0% |

Correct STOP: share of tasks that should not be admitted (insufficient evidence, conflict, variant not in ClinVar) that were not admitted. False STOP: share of admissible tasks that were not admitted. Conflict detected: share of conflicting variants whose conflict was reported. Citation grounded: share of cited submissions matching the source exactly, among delivered answers. Hallucination: share of delivered answers citing at least one submission that does not exist for the variant or is misstated. Delivered: every model answer; with bioevidence, only admitted records (the rest go to a human with the validator's findings).

Wilson 95% intervals, counts and per-task rows are in `summary.json` and `rows.jsonl`.
