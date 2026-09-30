# Literature benchmark, scenario 2b: an agent that searches and reads, with stances (pilot set)

The agent gets the claim and three tools (PubMed search, read a paper, submit). Bioevidence checks each submission; in the loop, its reasons go back to the agent, which may revise (at most three submissions, eight actions). Each citation carries its stance toward the claim, and the agent may decide "conflicting"; behind bioevidence, a record whose evidence lines disagree goes to an expert as conflicting.

| Model | View | Answered | Correct decision | Wrong direction | Conflicting | Answers with an invalid citation | Answers with only verified citations | Routed to a human |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Claude Opus 5.5 | Agent alone (first submission) | 15/18 | 13/18 | 1/18 | 1/18 | 0/15 | 15/15 | 0/18 |
| Claude Opus 5.5 | Agent + bioevidence gate (first submission) | 15/18 | 12/18 | 1/18 | 2/18 | 0/15 | 15/15 | 2/18 |
| Claude Opus 5.5 | Agent + bioevidence feedback loop (final submission) | 15/18 | 12/18 | 1/18 | 2/18 | 0/15 | 15/15 | 2/18 |
| GPT-6-Astra | Agent alone (first submission) | 14/18 | 11/18 | 2/18 | 1/18 | 0/14 | 14/14 | 0/18 |
| GPT-6-Astra | Agent + bioevidence gate (first submission) | 14/18 | 11/18 | 2/18 | 1/18 | 0/14 | 14/14 | 1/18 |
| GPT-6-Astra | Agent + bioevidence feedback loop (final submission) | 14/18 | 11/18 | 2/18 | 1/18 | 0/14 | 14/14 | 1/18 |
| Gemini 3.1 Pro | Agent alone (first submission) | 12/18 | 9/18 | 2/18 | 1/18 | 0/12 | 12/12 | 0/18 |
| Gemini 3.1 Pro | Agent + bioevidence gate (first submission) | 12/18 | 9/18 | 2/18 | 1/18 | 0/12 | 12/12 | 1/18 |
| Gemini 3.1 Pro | Agent + bioevidence feedback loop (final submission) | 12/18 | 9/18 | 2/18 | 1/18 | 0/12 | 12/12 | 1/18 |
| Claude Haiku 4.5 | Agent alone (first submission) | 17/18 | 10/18 | 4/18 | 3/18 | 7/17 | 10/17 | 0/18 |
| Claude Haiku 4.5 | Agent + bioevidence gate (first submission) | 10/18 | 5/18 | 2/18 | 3/18 | 0/10 | 10/10 | 10/18 |
| Claude Haiku 4.5 | Agent + bioevidence feedback loop (final submission) | 11/18 | 6/18 | 2/18 | 3/18 | 0/11 | 11/11 | 9/18 |
| GPT-5.6-Luna | Agent alone (first submission) | 11/18 | 6/18 | 2/18 | 3/18 | 3/11 | 8/11 | 0/18 |
| GPT-5.6-Luna | Agent + bioevidence gate (first submission) | 8/18 | 5/18 | 1/18 | 2/18 | 0/8 | 8/8 | 5/18 |
| GPT-5.6-Luna | Agent + bioevidence feedback loop (final submission) | 11/18 | 6/18 | 2/18 | 3/18 | 0/11 | 11/11 | 3/18 |
| Gemini 3.8 Flash | Agent alone (first submission) | 11/18 | 10/18 | 1/18 | 0/18 | 0/11 | 11/11 | 0/18 |
| Gemini 3.8 Flash | Agent + bioevidence gate (first submission) | 11/18 | 10/18 | 1/18 | 0/18 | 0/11 | 11/11 | 0/18 |
| Gemini 3.8 Flash | Agent + bioevidence feedback loop (final submission) | 11/18 | 10/18 | 1/18 | 0/18 | 0/11 | 11/11 | 0/18 |
| All models | Agent alone (first submission) | 80/108 | 59/108 | 12/108 | 9/108 | 10/80 | 70/80 | 0/108 |
| All models | Agent + bioevidence gate (first submission) | 70/108 | 52/108 | 9/108 | 9/108 | 0/70 | 70/70 | 19/108 |
| All models | Agent + bioevidence feedback loop (final submission) | 74/108 | 54/108 | 10/108 | 10/108 | 0/74 | 74/74 | 16/108 |

108 episodes; 331 searches, 209 reads, 117 submissions, 2 failed steps; median 129.0 s per episode. 8 episodes revised after feedback, 3 of them from not admitted to admitted.

Invalid citation: no PMID, a PMID that does not exist, a retracted paper, a title that does not match the PMID, or a quote not in the paper (checked against its open full text, else its PubMed abstract).
