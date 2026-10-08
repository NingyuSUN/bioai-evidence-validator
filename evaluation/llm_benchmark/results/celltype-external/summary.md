# Single-cell cell-type annotation (external set, protocol 3)

Each model annotates one cluster from its top 20 marker genes with a Cell Ontology term and the markers that support it. Compared with the authors' term: exact, coarser (an ancestor), finer (a descendant) or wrong; an identifier that is not a current cell type term is invalid.

| Model | View | Answered | Exact | Coarser | Finer | Wrong | Invalid ID | Answers with an identifier or marker error | Routed to a person |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude Opus 5.5 | Model alone (first answer) | 79/81 | 35/81 | 12/81 | 8/81 | 24/81 | 0/81 | 0/79 | 0/81 |
| Claude Opus 5.5 | Model + bioevidence gate (first answer) | 62/81 | 24/81 | 12/81 | 8/81 | 18/81 | 0/81 | 0/62 | 17/81 |
| Claude Opus 5.5 | Model + gate without the definition check (first answer) | 75/81 | 34/81 | 12/81 | 8/81 | 21/81 | 0/81 | 0/75 | 4/81 |
| Claude Opus 5.5 | Model + bioevidence feedback loop (last answer) | 70/81 | 24/81 | 15/81 | 8/81 | 23/81 | 0/81 | 0/70 | 9/81 |
| GPT-6-Astra | Model alone (first answer) | 79/81 | 33/81 | 11/81 | 5/81 | 30/81 | 0/81 | 2/79 | 0/81 |
| GPT-6-Astra | Model + bioevidence gate (first answer) | 63/81 | 25/81 | 11/81 | 5/81 | 22/81 | 0/81 | 0/63 | 16/81 |
| GPT-6-Astra | Model + gate without the definition check (first answer) | 74/81 | 32/81 | 11/81 | 5/81 | 26/81 | 0/81 | 0/74 | 5/81 |
| GPT-6-Astra | Model + bioevidence feedback loop (last answer) | 67/81 | 26/81 | 11/81 | 5/81 | 25/81 | 0/81 | 0/67 | 12/81 |
| Gemini 3.1 Pro | Model alone (first answer) | 80/81 | 32/81 | 16/81 | 1/81 | 31/81 | 0/81 | 6/80 | 0/81 |
| Gemini 3.1 Pro | Model + bioevidence gate (first answer) | 55/81 | 23/81 | 15/81 | 1/81 | 16/81 | 0/81 | 0/55 | 25/81 |
| Gemini 3.1 Pro | Model + gate without the definition check (first answer) | 65/81 | 29/81 | 15/81 | 1/81 | 20/81 | 0/81 | 0/65 | 15/81 |
| Gemini 3.1 Pro | Model + bioevidence feedback loop (last answer) | 70/81 | 23/81 | 20/81 | 2/81 | 25/81 | 0/81 | 0/70 | 10/81 |
| Claude Haiku 4.5 | Model alone (first answer) | 81/81 | 17/81 | 18/81 | 5/81 | 40/81 | 1/81 | 23/81 | 0/81 |
| Claude Haiku 4.5 | Model + bioevidence gate (first answer) | 40/81 | 9/81 | 18/81 | 1/81 | 12/81 | 0/81 | 0/40 | 41/81 |
| Claude Haiku 4.5 | Model + gate without the definition check (first answer) | 45/81 | 14/81 | 18/81 | 1/81 | 12/81 | 0/81 | 0/45 | 36/81 |
| Claude Haiku 4.5 | Model + bioevidence feedback loop (last answer) | 59/81 | 13/81 | 21/81 | 5/81 | 20/81 | 0/81 | 0/59 | 22/81 |
| GPT-5.6-Luna | Model alone (first answer) | 80/81 | 20/81 | 10/81 | 7/81 | 43/81 | 0/81 | 33/80 | 0/81 |
| GPT-5.6-Luna | Model + bioevidence gate (first answer) | 31/81 | 11/81 | 3/81 | 1/81 | 16/81 | 0/81 | 0/31 | 49/81 |
| GPT-5.6-Luna | Model + gate without the definition check (first answer) | 42/81 | 17/81 | 3/81 | 1/81 | 21/81 | 0/81 | 0/42 | 38/81 |
| GPT-5.6-Luna | Model + bioevidence feedback loop (last answer) | 64/81 | 16/81 | 6/81 | 9/81 | 33/81 | 0/81 | 0/64 | 16/81 |
| Gemini 3.8 Flash | Model alone (first answer) | 80/81 | 32/81 | 13/81 | 3/81 | 32/81 | 0/81 | 6/80 | 0/81 |
| Gemini 3.8 Flash | Model + bioevidence gate (first answer) | 51/81 | 22/81 | 11/81 | 2/81 | 16/81 | 0/81 | 0/51 | 29/81 |
| Gemini 3.8 Flash | Model + gate without the definition check (first answer) | 61/81 | 28/81 | 11/81 | 2/81 | 20/81 | 0/81 | 0/61 | 19/81 |
| Gemini 3.8 Flash | Model + bioevidence feedback loop (last answer) | 60/81 | 23/81 | 12/81 | 3/81 | 22/81 | 0/81 | 0/60 | 20/81 |
| All models | Model alone (first answer) | 479/486 | 169/486 | 80/486 | 29/486 | 200/486 | 1/486 | 70/479 | 0/486 |
| All models | Model + bioevidence gate (first answer) | 302/486 | 114/486 | 70/486 | 18/486 | 100/486 | 0/486 | 0/302 | 177/486 |
| All models | Model + gate without the definition check (first answer) | 362/486 | 154/486 | 70/486 | 18/486 | 120/486 | 0/486 | 0/362 | 117/486 |
| All models | Model + bioevidence feedback loop (last answer) | 390/486 | 125/486 | 85/486 | 32/486 | 148/486 | 0/486 | 0/390 | 89/486 |

Errors in the models' first answers (all models): label mismatch 69/479, marker not in data 0/479, no markers 0/479, not a cell type 0/479, obsolete id 1/479, unapproved symbol 0/479, unknown id 0/479.

486 episodes, 673 model calls (0 failed), 131 revised after feedback. Rule codes raised across all records: BEV004 69, BEV016 7, BEV017 95, BEV023 1, BEV026 140.

First answers the definition check flagged, by comparison with the authors' term: exact 43, finer 4, wrong 41.

Funnel. First answers: conflict, to a person 36, definition contradicted 71, identifier error 70, no annotation 7, passed 302. Answers with a fixable finding, after feedback: admitted 88, to a person 53. Final: admitted 390, no annotation 7, to a person 89. Admitted, against the authors' term: compatible 242, disagrees 148. Expert audit of admitted records: not yet run.
