# Literature benchmark, scenario 2: an agent that searches and reads (pilot set)

The agent gets the claim and three tools (PubMed search, read a paper, submit). Bioevidence checks each submission; in the loop, its reasons go back to the agent, which may revise (at most three submissions, eight actions).

| Model | View | Answered | Correct decision | Wrong direction | Conflicting | Answers with an invalid citation | Answers with only verified citations | Routed to a human |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Claude Opus 5.5 | Agent alone (first submission) | 13/18 | 10/18 | 3/18 | 0/18 | 0/13 | 13/13 | 0/18 |
| Claude Opus 5.5 | Agent + bioevidence gate (first submission) | 13/18 | 10/18 | 3/18 | 0/18 | 0/13 | 13/13 | 0/18 |
| Claude Opus 5.5 | Agent + bioevidence feedback loop (final submission) | 13/18 | 10/18 | 3/18 | 0/18 | 0/13 | 13/13 | 0/18 |
| GPT-6-Astra | Agent alone (first submission) | 15/18 | 13/18 | 2/18 | 0/18 | 0/15 | 15/15 | 0/18 |
| GPT-6-Astra | Agent + bioevidence gate (first submission) | 15/18 | 13/18 | 2/18 | 0/18 | 0/15 | 15/15 | 0/18 |
| GPT-6-Astra | Agent + bioevidence feedback loop (final submission) | 15/18 | 13/18 | 2/18 | 0/18 | 0/15 | 15/15 | 0/18 |
| Gemini 3.1 Pro | Agent alone (first submission) | 10/18 | 8/18 | 2/18 | 0/18 | 0/10 | 10/10 | 0/18 |
| Gemini 3.1 Pro | Agent + bioevidence gate (first submission) | 10/18 | 8/18 | 2/18 | 0/18 | 0/10 | 10/10 | 0/18 |
| Gemini 3.1 Pro | Agent + bioevidence feedback loop (final submission) | 10/18 | 8/18 | 2/18 | 0/18 | 0/10 | 10/10 | 0/18 |
| Claude Haiku 4.5 | Agent alone (first submission) | 16/18 | 12/18 | 4/18 | 0/18 | 8/16 | 8/16 | 0/18 |
| Claude Haiku 4.5 | Agent + bioevidence gate (first submission) | 8/18 | 5/18 | 3/18 | 0/18 | 0/8 | 8/8 | 8/18 |
| Claude Haiku 4.5 | Agent + bioevidence feedback loop (final submission) | 12/18 | 8/18 | 4/18 | 0/18 | 0/12 | 12/12 | 4/18 |
| GPT-5.6-Luna | Agent alone (first submission) | 11/18 | 10/18 | 1/18 | 0/18 | 0/11 | 11/11 | 0/18 |
| GPT-5.6-Luna | Agent + bioevidence gate (first submission) | 11/18 | 10/18 | 1/18 | 0/18 | 0/11 | 11/11 | 0/18 |
| GPT-5.6-Luna | Agent + bioevidence feedback loop (final submission) | 11/18 | 10/18 | 1/18 | 0/18 | 0/11 | 11/11 | 0/18 |
| Gemini 3.8 Flash | Agent alone (first submission) | 12/18 | 9/18 | 3/18 | 0/18 | 0/12 | 12/12 | 0/18 |
| Gemini 3.8 Flash | Agent + bioevidence gate (first submission) | 12/18 | 9/18 | 3/18 | 0/18 | 0/12 | 12/12 | 0/18 |
| Gemini 3.8 Flash | Agent + bioevidence feedback loop (final submission) | 12/18 | 9/18 | 3/18 | 0/18 | 0/12 | 12/12 | 0/18 |
| All models | Agent alone (first submission) | 77/108 | 62/108 | 15/108 | 0/108 | 8/77 | 69/77 | 0/108 |
| All models | Agent + bioevidence gate (first submission) | 69/108 | 55/108 | 14/108 | 0/108 | 0/69 | 69/69 | 8/108 |
| All models | Agent + bioevidence feedback loop (final submission) | 73/108 | 58/108 | 15/108 | 0/108 | 0/73 | 73/73 | 4/108 |

108 episodes; 317 searches, 163 reads, 117 submissions, 4 failed steps; median 106.5 s per episode. 6 episodes revised after feedback, 4 of them from not admitted to admitted.

Invalid citation: no PMID, a PMID that does not exist, a retracted paper, a title that does not match the PMID, or a quote not in the paper (checked against its open full text, else its PubMed abstract).
