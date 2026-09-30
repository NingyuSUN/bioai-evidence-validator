# Literature benchmark: models alone vs. with bioevidence (pilot set)

18 tasks on open-access CIViC papers; reference: CIViC's curation of each paper. Models: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`), Claude Opus 5.5 (`claude-opus-5-5`), Gemini 3.8 Flash (`gemini-3.8-flash-medium`), Gemini 3.1 Pro (`gemini-3.1-pro-high`), GPT-6-Astra (`gpt-6-astra`), GPT-5.6-Luna (`gpt-5.6-luna`).

| Model | Configuration | Correct decision | Correct STOP | False STOP | Negative finding detected | Wrong direction | Citation grounded | Invented quote | No quote |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude Opus 5.5 | LLM only | 44% | 100% | 83% | 0% | 0% | 50% | 50% | 0% |
| Claude Opus 5.5 | LLM only + bioevidence | 39% | 100% | 92% | 0% | 0% | 100% | 0% | 0% |
| Claude Opus 5.5 | LLM + paper | 89% | 100% | 17% | 75% | 0% | 100% | 0% | 0% |
| Claude Opus 5.5 | LLM + paper + bioevidence | 89% | 100% | 17% | 75% | 0% | 100% | 0% | 0% |
| GPT-6-Astra | LLM only | 33% | 100% | 100% | 0% | 0% | N/A | N/A | N/A |
| GPT-6-Astra | LLM only + bioevidence | 33% | 100% | 100% | 0% | 0% | N/A | N/A | N/A |
| GPT-6-Astra | LLM + paper | 89% | 100% | 0% | 75% | 17% | 100% | 0% | 0% |
| GPT-6-Astra | LLM + paper + bioevidence | 89% | 100% | 0% | 75% | 17% | 100% | 0% | 0% |
| Gemini 3.1 Pro | LLM only | 39% | 100% | 92% | 0% | 0% | 100% | 0% | 0% |
| Gemini 3.1 Pro | LLM only + bioevidence | 39% | 100% | 92% | 0% | 0% | 100% | 0% | 0% |
| Gemini 3.1 Pro | LLM + paper | 94% | 100% | 8% | 75% | 0% | 100% | 0% | 0% |
| Gemini 3.1 Pro | LLM + paper + bioevidence | 94% | 100% | 8% | 75% | 0% | 100% | 0% | 0% |
| Claude Haiku 4.5 | LLM only | 33% | 100% | 100% | 0% | 0% | N/A | N/A | N/A |
| Claude Haiku 4.5 | LLM only + bioevidence | 33% | 100% | 100% | 0% | 0% | N/A | N/A | N/A |
| Claude Haiku 4.5 | LLM + paper | 94% | 100% | 8% | 100% | 0% | 100% | 0% | 0% |
| Claude Haiku 4.5 | LLM + paper + bioevidence | 94% | 100% | 8% | 100% | 0% | 100% | 0% | 0% |
| GPT-5.6-Luna | LLM only | 33% | 100% | 100% | 0% | 0% | N/A | N/A | N/A |
| GPT-5.6-Luna | LLM only + bioevidence | 33% | 100% | 100% | 0% | 0% | N/A | N/A | N/A |
| GPT-5.6-Luna | LLM + paper | 89% | 100% | 0% | 75% | 17% | 100% | 0% | 0% |
| GPT-5.6-Luna | LLM + paper + bioevidence | 89% | 100% | 0% | 75% | 17% | 100% | 0% | 0% |
| Gemini 3.8 Flash | LLM only | 33% | 100% | 100% | 0% | 0% | N/A | N/A | N/A |
| Gemini 3.8 Flash | LLM only + bioevidence | 33% | 100% | 100% | 0% | 0% | N/A | N/A | N/A |
| Gemini 3.8 Flash | LLM + paper | 94% | 100% | 0% | 100% | 8% | 100% | 0% | 0% |
| Gemini 3.8 Flash | LLM + paper + bioevidence | 94% | 100% | 0% | 100% | 8% | 100% | 0% | 0% |

Correct STOP: share of unrelated claims (the paper never mentions the gene) not answered. False STOP: share of answerable tasks not answered. Negative finding detected: share of CIViC "Does Not Support" items answered as such. Wrong direction: share of answerable tasks answered the opposite way. Citation grounded: share of quotes found verbatim in the paper, among delivered answers. Invented quote: share of delivered answers with at least one quote not in the paper (the `hallucination` metric). No quote: share of delivered answers that give a decision without any quote. Delivered: every non-stop model answer; with bioevidence, only admitted records.

Wilson 95% intervals and per-task rows are in `summary.json` and `rows.jsonl`.
