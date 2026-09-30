# Single-cell cell-type annotation (pilot set)

Each model annotates one cluster from its top 20 marker genes with a Cell Ontology term and the markers that support it. Compared with the authors' term: exact, coarser (an ancestor), finer (a descendant) or wrong; an identifier that is not a current cell type term is invalid.

| Model | View | Answered | Exact | Coarser | Finer | Wrong | Invalid ID | Answers with an identifier or marker error | Routed to a person |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude Opus 5.5 | Model alone (first answer) | 23/24 | 9/24 | 2/24 | 5/24 | 7/24 | 0/24 | 1/23 | 0/24 |
| Claude Opus 5.5 | Model + bioevidence gate (first answer) | 9/24 | 5/24 | 2/24 | 1/24 | 1/24 | 0/24 | 0/9 | 14/24 |
| Claude Opus 5.5 | Model + bioevidence feedback loop (last answer) | 9/24 | 5/24 | 2/24 | 1/24 | 1/24 | 0/24 | 0/9 | 14/24 |
| GPT-6-Astra | Model alone (first answer) | 23/24 | 9/24 | 3/24 | 2/24 | 8/24 | 1/24 | 2/23 | 0/24 |
| GPT-6-Astra | Model + bioevidence gate (first answer) | 16/24 | 8/24 | 3/24 | 0/24 | 5/24 | 0/24 | 0/16 | 7/24 |
| GPT-6-Astra | Model + bioevidence feedback loop (last answer) | 16/24 | 8/24 | 3/24 | 0/24 | 5/24 | 0/24 | 0/16 | 7/24 |
| Gemini 3.1 Pro | Model alone (first answer) | 23/24 | 8/24 | 5/24 | 3/24 | 7/24 | 0/24 | 4/23 | 0/24 |
| Gemini 3.1 Pro | Model + bioevidence gate (first answer) | 14/24 | 8/24 | 4/24 | 0/24 | 2/24 | 0/24 | 0/14 | 9/24 |
| Gemini 3.1 Pro | Model + bioevidence feedback loop (last answer) | 17/24 | 8/24 | 4/24 | 1/24 | 4/24 | 0/24 | 0/17 | 6/24 |
| Claude Haiku 4.5 | Model alone (first answer) | 23/24 | 6/24 | 3/24 | 2/24 | 12/24 | 0/24 | 12/23 | 0/24 |
| Claude Haiku 4.5 | Model + bioevidence gate (first answer) | 3/24 | 3/24 | 0/24 | 0/24 | 0/24 | 0/24 | 0/3 | 20/24 |
| Claude Haiku 4.5 | Model + bioevidence feedback loop (last answer) | 4/24 | 3/24 | 0/24 | 0/24 | 1/24 | 0/24 | 0/4 | 19/24 |
| GPT-5.6-Luna | Model alone (first answer) | 23/24 | 3/24 | 4/24 | 2/24 | 13/24 | 1/24 | 12/23 | 0/24 |
| GPT-5.6-Luna | Model + bioevidence gate (first answer) | 5/24 | 3/24 | 1/24 | 0/24 | 1/24 | 0/24 | 0/5 | 18/24 |
| GPT-5.6-Luna | Model + bioevidence feedback loop (last answer) | 10/24 | 5/24 | 1/24 | 2/24 | 2/24 | 0/24 | 0/10 | 13/24 |
| Gemini 3.8 Flash | Model alone (first answer) | 23/24 | 6/24 | 4/24 | 3/24 | 9/24 | 1/24 | 7/23 | 0/24 |
| Gemini 3.8 Flash | Model + bioevidence gate (first answer) | 9/24 | 5/24 | 3/24 | 0/24 | 1/24 | 0/24 | 0/9 | 14/24 |
| Gemini 3.8 Flash | Model + bioevidence feedback loop (last answer) | 11/24 | 6/24 | 3/24 | 0/24 | 2/24 | 0/24 | 0/11 | 12/24 |
| All models | Model alone (first answer) | 138/144 | 41/144 | 21/144 | 17/144 | 56/144 | 3/144 | 38/138 | 0/144 |
| All models | Model + bioevidence gate (first answer) | 56/144 | 32/144 | 13/144 | 1/144 | 10/144 | 0/144 | 0/56 | 82/144 |
| All models | Model + bioevidence feedback loop (last answer) | 67/144 | 35/144 | 13/144 | 4/144 | 15/144 | 0/144 | 0/67 | 71/144 |

Errors in the models' first answers (all models): label mismatch 35/138, marker not in data 3/138, no markers 0/138, not a cell type 0/138, obsolete id 2/138, unapproved symbol 0/138, unknown id 1/138.

144 episodes, 185 model calls (0 failed), 38 revised after feedback. Rule codes raised across all records: BEV004 87, BEV016 4, BEV017 39, BEV023 2, BEV025 29.
