# Model reviewers on the blinded ClinVar packet

| Model | Calls | Answered | With tool use | Later information seen | Median seconds |
|---|---:|---:|---:|---:|---:|
| claude-opus-5-5 | 190 | 190 | 0 | 0 | 9.9 |
| gpt-6-astra | 190 | 190 | 0 | 0 | 35.2 |
| gemini-3.1-pro-high | 190 | 190 | 0 | 0 | 21.5 |
| claude-haiku-4-5-20251001 | 190 | 190 | 0 | 0 | 25.0 |
| gpt-5.6-luna | 190 | 190 | 0 | 0 | 32.6 |
| gemini-3.8-flash-medium | 190 | 190 | 0 | 0 | 26.3 |

Agreement among the 6 models on the test split, before any reference (Krippendorff's alpha, bootstrap 95% interval):

| Label | Units | All agree | Alpha (95% CI) |
|---|---:|---:|---|
| research_summary | 170 | 0.9176 | 0.1237 (0.0281–0.2131) |
| clinical_reference | 170 | 0.5529 | 0.5333 (0.4326–0.6209) |
| expert_reference | 170 | 0.3824 | 0.4908 (0.4302–0.5453) |
| statement | 170 | 0.8647 | 0.4656 (0.2435–0.6246) |

Reference: none. Scores, error correlation and the decision statement follow once the expert labels are resolved.
