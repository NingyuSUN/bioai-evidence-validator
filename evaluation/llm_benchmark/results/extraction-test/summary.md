# Real AI extraction (test split, 240 episodes)

Claims: what the model extracted. Gate: admitted as first extracted. Loop: admitted after feedback.

| Model | Claims | First version: identifier or quote error | Admitted, gate | Admitted, loop | Admitted with an error | CIViC items found: model alone | Gate | Loop | Loop, same kind | After model review |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude Opus 5.5 | 143 | 4/143 | 129/143 | 133/143 | 0/133 | 65/87 | 63/87 | 64/87 | 62/87 | 63/87 |
| GPT-6-Astra | 133 | 23/133 | 97/133 | 111/133 | 0/111 | 57/87 | 46/87 | 55/87 | 53/87 | 55/87 |
| Gemini 3.1 Pro | 106 | 31/106 | 74/106 | 100/106 | 0/100 | 56/87 | 42/87 | 59/87 | 59/87 | 59/87 |
| Claude Haiku 4.5 | 133 | 64/133 | 68/133 | 124/133 | 0/124 | 67/87 | 44/87 | 75/87 | 75/87 | 75/87 |
| GPT-5.6-Luna | 166 | 62/166 | 103/166 | 163/166 | 0/163 | 56/87 | 51/87 | 73/87 | 73/87 | 73/87 |
| Gemini 3.8 Flash | 33 | 14/33 | 18/33 | 32/33 | 0/32 | 24/87 | 12/87 | 30/87 | 19/87 | 30/87 |
| All models | 714 | 198/714 | 489/714 | 663/714 | 0/663 | 77/87 | 67/87 | 77/87 | 77/87 | 77/87 |

Funnel (all models). First version of each claim: conflict, to a person 20, identifier 179, passed 489, quote 12, rules 14. Final: admitted 663, to a person 26, withdrawn 25. Model review of the admitted: accepted 628, deferred 35; the accepted, as the reviewer reads their evidence: evidence from non_human 300, evidence from patients 325, evidence from unclear 3, finding 596, hedged 32. Human review: not yet run. First-version error kinds: disease_label_mismatch 113, gene_label_mismatch 58, obsolete_disease_id 5, quote_not_in_paper 13, unknown_disease_id 13, unknown_gene_id 7. Admitted claims with no CIViC counterpart (same gene, compatible disease): 205/663.

Calls: 327, failed 1. Finding codes over all versions: BEV004 46, BEV006 14, BEV007 14, BEV016 20, BEV017 181, BEV020 11, BEV023 5.
