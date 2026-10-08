# Real AI extraction (pilot split, 60 episodes)

Claims: what the model extracted. Gate: admitted as first extracted. Loop: admitted after feedback.

| Model | Claims | First version: identifier or quote error | Admitted, gate | Admitted, loop | Admitted with an error | CIViC items found: model alone | Gate | Loop | Loop, same kind | After model review |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude Opus 5.5 | 25 | 4/25 | 20/25 | 24/25 | 0/24 | 10/17 | 10/17 | 10/17 | 10/17 | 10/17 |
| GPT-6-Astra | 49 | 27/49 | 22/49 | 44/49 | 0/44 | 8/17 | 7/17 | 10/17 | 10/17 | 10/17 |
| Gemini 3.1 Pro | 32 | 20/32 | 11/32 | 30/32 | 0/30 | 7/17 | 7/17 | 10/17 | 10/17 | 10/17 |
| Claude Haiku 4.5 | 21 | 20/21 | 1/21 | 12/21 | 0/12 | 8/17 | 6/17 | 9/17 | 9/17 | 9/17 |
| GPT-5.6-Luna | 29 | 18/29 | 11/29 | 25/29 | 0/25 | 8/17 | 7/17 | 8/17 | 8/17 | 8/17 |
| Gemini 3.8 Flash | 11 | 6/11 | 5/11 | 11/11 | 0/11 | 9/17 | 6/17 | 9/17 | 9/17 | 9/17 |
| All models | 167 | 95/167 | 70/167 | 146/167 | 0/146 | 10/17 | 10/17 | 10/17 | 10/17 | 10/17 |

Funnel (all models). First version of each claim: identifier 93, passed 70, quote 1, rules 3. Final: admitted 146, not fixed 10, to a person 4, withdrawn 7. Model review of the admitted: accepted 141, deferred 5; the accepted, as the reviewer reads their evidence: evidence from non_human 24, evidence from patients 115, evidence from unclear 2, finding 134, hedged 7. Human review: not yet run. First-version error kinds: disease_label_mismatch 61, gene_label_mismatch 14, obsolete_disease_id 17, quote_not_in_paper 2, unknown_disease_id 11, unknown_gene_id 2. Admitted claims with no CIViC counterpart (same gene, compatible disease): 88/146.

Calls: 104, failed 0. Finding codes over all versions: BEV004 11, BEV006 3, BEV007 3, BEV016 23, BEV017 83, BEV023 22.
