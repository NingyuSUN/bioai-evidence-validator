# Single-cell cell-type annotation (test set, protocol 2)

Each model annotates one cluster from its top 20 marker genes with a Cell Ontology term and the markers that support it. Compared with the authors' term: exact, coarser (an ancestor), finer (a descendant) or wrong; an identifier that is not a current cell type term is invalid.

| Model | View | Answered | Exact | Coarser | Finer | Wrong | Invalid ID | Answers with an identifier or marker error | Routed to a person |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude Opus 5.5 | Model alone (first answer) | 46/46 | 26/46 | 4/46 | 7/46 | 9/46 | 0/46 | 4/46 | 0/46 |
| Claude Opus 5.5 | Model + bioevidence gate (first answer) | 38/46 | 25/46 | 3/46 | 6/46 | 4/46 | 0/46 | 0/38 | 8/46 |
| Claude Opus 5.5 | Model + bioevidence feedback loop (last answer) | 42/46 | 27/46 | 3/46 | 7/46 | 5/46 | 0/46 | 0/42 | 4/46 |
| GPT-6-Astra | Model alone (first answer) | 46/46 | 24/46 | 6/46 | 6/46 | 10/46 | 0/46 | 1/46 | 0/46 |
| GPT-6-Astra | Model + bioevidence gate (first answer) | 44/46 | 24/46 | 6/46 | 6/46 | 8/46 | 0/46 | 0/44 | 2/46 |
| GPT-6-Astra | Model + bioevidence feedback loop (last answer) | 45/46 | 25/46 | 6/46 | 6/46 | 8/46 | 0/46 | 0/45 | 1/46 |
| Gemini 3.1 Pro | Model alone (first answer) | 46/46 | 20/46 | 9/46 | 3/46 | 14/46 | 0/46 | 10/46 | 0/46 |
| Gemini 3.1 Pro | Model + bioevidence gate (first answer) | 33/46 | 18/46 | 8/46 | 1/46 | 6/46 | 0/46 | 0/33 | 13/46 |
| Gemini 3.1 Pro | Model + bioevidence feedback loop (last answer) | 43/46 | 22/46 | 8/46 | 6/46 | 7/46 | 0/46 | 0/43 | 3/46 |
| Claude Haiku 4.5 | Model alone (first answer) | 46/46 | 13/46 | 3/46 | 2/46 | 27/46 | 1/46 | 23/46 | 0/46 |
| Claude Haiku 4.5 | Model + bioevidence gate (first answer) | 20/46 | 13/46 | 2/46 | 1/46 | 4/46 | 0/46 | 0/20 | 26/46 |
| Claude Haiku 4.5 | Model + bioevidence feedback loop (last answer) | 41/46 | 20/46 | 4/46 | 4/46 | 13/46 | 0/46 | 0/41 | 5/46 |
| GPT-5.6-Luna | Model alone (first answer) | 46/46 | 13/46 | 5/46 | 3/46 | 23/46 | 2/46 | 16/46 | 0/46 |
| GPT-5.6-Luna | Model + bioevidence gate (first answer) | 30/46 | 13/46 | 4/46 | 2/46 | 11/46 | 0/46 | 0/30 | 16/46 |
| GPT-5.6-Luna | Model + bioevidence feedback loop (last answer) | 44/46 | 19/46 | 6/46 | 6/46 | 13/46 | 0/46 | 0/44 | 2/46 |
| Gemini 3.8 Flash | Model alone (first answer) | 46/46 | 21/46 | 6/46 | 5/46 | 14/46 | 0/46 | 9/46 | 0/46 |
| Gemini 3.8 Flash | Model + bioevidence gate (first answer) | 33/46 | 20/46 | 4/46 | 5/46 | 4/46 | 0/46 | 0/33 | 13/46 |
| Gemini 3.8 Flash | Model + bioevidence feedback loop (last answer) | 40/46 | 25/46 | 4/46 | 7/46 | 4/46 | 0/46 | 0/40 | 6/46 |
| All models | Model alone (first answer) | 276/276 | 117/276 | 33/276 | 26/276 | 97/276 | 3/276 | 63/276 | 0/276 |
| All models | Model + bioevidence gate (first answer) | 198/276 | 113/276 | 27/276 | 21/276 | 37/276 | 0/276 | 0/198 | 78/276 |
| All models | Model + bioevidence feedback loop (last answer) | 255/276 | 138/276 | 31/276 | 36/276 | 50/276 | 0/276 | 0/255 | 21/276 |

Errors in the models' first answers (all models): label mismatch 59/276, marker not in data 1/276, no markers 0/276, not a cell type 0/276, obsolete id 1/276, unapproved symbol 0/276, unknown id 2/276.

276 episodes, 344 model calls (0 failed), 63 revised after feedback. Rule codes raised across all records: BEV004 21, BEV016 4, BEV017 65, BEV023 1.
