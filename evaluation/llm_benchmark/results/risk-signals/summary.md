# Risk signals: which routing signals predict a wrong answer

First answers only, before any feedback. *Shown*: the risk ratio's 95% interval lies above 1 on a held-out or external split, and no such split points the other way. *Indicative*: that holds only on a pilot. The criterion was set after the runs.

| Signal | Role | Default routing | Split | Wrong when flagged | Wrong otherwise | Risk ratio (95% CI) | Verdict |
|---|---|---|---|---:|---:|---:|---|
| **BEV004** Contradicting evidence line (the answer's own evidence disagrees with it) | risk | on: engine rule | celltype-pilot (pilot) | 39/62 (63%) | 20/76 (26%) | 2.39 (1.57–3.65) | shown |
|  |  |  | celltype-test (held-out) | 14/17 (82%) | 86/259 (33%) | 2.48 (1.87–3.28) |  |
|  |  |  | celltype-external (external) | 38/54 (70%) | 163/425 (38%) | 1.83 (1.49–2.27) |  |
|  |  |  | agent-stance-pilot (pilot) | 10/11 (91%) | 11/69 (16%) | 5.7 (3.21–10.12) |  |
| **BEV022** Semantic cue: negated, hedged or non-human quote | risk | opt-in: `semantic` cues | semantic-pilot (pilot) | 1/24 (4%) | 4/44 (9%) | 0.46 (0.05–3.87) | not shown |
| **BEV025** A pinned reference resource contradicts the claim (ASCT+B) | risk | opt-in: `ReferenceGrounder`; dropped from the cell-type validator after the pilot | celltype-pilot (pilot) | 13/23 (57%) | 46/115 (40%) | 1.41 (0.93–2.16) | not shown |
| **BEV026** Measurements contradict the ontology's definition | risk | opt-in, experimental: `DefinitionGrounder`; fed back to the model | celltype-external (external) | 41/88 (47%) | 160/391 (41%) | 1.14 (0.88–1.47) | not shown |
| **BEV016** A cited identifier or marker does not exist in the source | fixable | fed back to the model | celltype-pilot (pilot) | 3/4 (75%) | 56/134 (42%) | 1.79 (0.98–3.27) | not shown |
|  |  |  | celltype-test (held-out) | 2/3 (67%) | 98/273 (36%) | 1.86 (0.82–4.2) |  |
| **BEV017** The record disagrees with the source (e.g. a label that is not the term's name) | fixable | fed back to the model | celltype-pilot (pilot) | 26/35 (74%) | 33/103 (32%) | 2.32 (1.65–3.26) | shown |
|  |  |  | celltype-test (held-out) | 48/59 (81%) | 52/217 (24%) | 3.4 (2.6–4.43) |  |
|  |  |  | celltype-external (external) | 49/69 (71%) | 152/410 (37%) | 1.92 (1.57–2.33) |  |
|  |  |  | agent-stance-pilot (pilot) | 4/10 (40%) | 17/70 (24%) | 1.65 (0.69–3.91) |  |
| **BEV023** An obsolete identifier or a previous gene symbol | fixable | fed back to the model | celltype-pilot (pilot) | 2/2 (100%) | 57/136 (42%) | 1.99 (1.15–3.42) | indicative |
|  |  |  | celltype-test (held-out) | 1/1 (100%) | 99/275 (36%) | 2.08 (0.92–4.7) |  |
|  |  |  | celltype-external (external) | 1/1 (100%) | 200/478 (42%) | 1.79 (0.8–4.02) |  |

Risk signals that route by default: BEV004 (shown). Opt-in: BEV022 (not shown), BEV025 (not shown), BEV026 (not shown); a signal that is not shown stays off by default. BEV026 is fed back to the model first; a record it still flags after feedback goes to a person, which is why it is experimental. Fixable findings predict wrong answers too, partly by construction (an unknown identifier is an invalid answer); they go back to the model.

Rules that route a record because it cannot be verified (BEV006, BEV015, BEV018, BEV020) or because the use requires a person (BEV008–BEV013, BEV021) are admission policy, not predictions, and are not listed.
