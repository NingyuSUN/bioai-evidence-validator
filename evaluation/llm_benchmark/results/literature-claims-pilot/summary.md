# Literature benchmark, scenario 1b: the claim only (pilot set)

The model is asked, as a user would ask a chatbot, what the literature says about a CIViC-style claim, and to cite papers (PMID, title, quote). No curation rules, no source, no tools.

| Model | Configuration | Answered | Correct decision | Wrong direction | Answers with an invalid citation | Answers with only verified citations | Answers without a citation |
|---|---|---:|---:|---:|---:|---:|---:|
| Claude Opus 5.5 | LLM alone | 13/18 | 11/18 | 2/18 | 10/13 | 0/13 | 3/13 |
| Claude Opus 5.5 | + bioevidence | 0/18 | 0/18 | 0/18 | N/A | N/A | N/A |
| GPT-6-Astra | LLM alone | 11/18 | 11/18 | 0/18 | 3/11 | 3/11 | 5/11 |
| GPT-6-Astra | + bioevidence | 3/18 | 3/18 | 0/18 | 0/3 | 3/3 | 0/3 |
| Gemini 3.1 Pro | LLM alone | 11/18 | 11/18 | 0/18 | 10/11 | 0/11 | 1/11 |
| Gemini 3.1 Pro | + bioevidence | 0/18 | 0/18 | 0/18 | N/A | N/A | N/A |
| Claude Haiku 4.5 | LLM alone | 2/18 | 1/18 | 1/18 | 2/2 | 0/2 | 0/2 |
| Claude Haiku 4.5 | + bioevidence | 0/18 | 0/18 | 0/18 | N/A | N/A | N/A |
| GPT-5.6-Luna | LLM alone | 2/18 | 2/18 | 0/18 | 2/2 | 0/2 | 0/2 |
| GPT-5.6-Luna | + bioevidence | 0/18 | 0/18 | 0/18 | N/A | N/A | N/A |
| Gemini 3.8 Flash | LLM alone | 11/18 | 10/18 | 1/18 | 11/11 | 0/11 | 0/11 |
| Gemini 3.8 Flash | + bioevidence | 0/18 | 0/18 | 0/18 | N/A | N/A | N/A |
| All six models | LLM alone | 50/108 | 46/108 | 4/108 | 38/50 | 3/50 | 9/50 |
| All six models | + bioevidence | 3/108 | 3/108 | 0/108 | 0/3 | 3/3 | 0/3 |

Citations given by the models alone: no_pmid 1, not_found 2, quote_found 6, quote_not_found 29, wrong_paper 28.

Invalid: no PMID, a PMID that does not exist, a retracted paper, a title that does not match the PMID, or a quote not in the open full text. Unverifiable: no open full text (sent to review, never counted as verified). With bioevidence, only admitted records are answers; the rest go to a human.
