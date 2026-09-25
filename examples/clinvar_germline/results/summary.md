# ClinVar germline evidence benchmark

Evidence: ClinVar 2023-09 submissions. Outcome: ClinVar 2026-09 aggregate classification. No independent expert annotation.

## A. Policy reproduction against NCBI's 2023-09 review status

| Use | n | Agreement | NCBI admitted | Validator admitted | Validator stricter | Validator looser |
|---|---:|---:|---:|---:|---:|---:|
| research_summary | 5026 | 4932/5026 | 3026 | 2934 | 93 | 1 |
| clinical_reference | 5026 | 4941/5026 | 2026 | 1941 | 85 | 0 |
| expert_reference | 5026 | 4960/5026 | 1026 | 960 | 66 | 0 |

## B. Three-year stability of 2023-09 P/LP classifications (destabilized = conflicting or downgraded by 2026-09; Wilson 95% CI)

| Use | Admitted in 2023 | Not admitted in 2023 |
|---|---|---|
| research_summary | 43/2933 = 1.47% (1.09–1.97) | 53/1083 = 4.89% (3.76–6.35) |
| clinical_reference | 16/1941 = 0.82% (0.51–1.33) | 80/2075 = 3.86% (3.11–4.77) |
| expert_reference | 0/960 = 0.00% (0.00–0.40) | 96/3056 = 3.14% (2.58–3.82) |

| 2023-09 review status stratum | Destabilized by 2026-09 |
|---|---|
| no_criteria | 52/990 = 5.25% (4.03–6.82) |
| single_submitter | 27/1000 = 2.70% (1.86–3.90) |
| multiple_submitters | 17/1000 = 1.70% (1.06–2.71) |
| expert_panel | 0/1000 = 0.00% (0.00–0.38) |
| practice_guideline | 0/26 = 0.00% (0.00–12.87) |

## Whole-population context: all 2023-09 germline P/LP variants

Validator routes a variant with any dissenting (VUS/LB/B) submission to review (BEV004); NCBI's aggregate may still admit it.

| 2023-09 review status | All | With a dissenting submission | Without |
|---|---|---|---|
| expert_panel | 13/8950 = 0.15% (0.08–0.25) | 7/539 = 1.30% (0.63–2.66) | 6/8411 = 0.07% (0.03–0.16) |
| multiple_submitters | 981/42804 = 2.29% (2.15–2.44) | 59/709 = 8.32% (6.51–10.59) | 922/42095 = 2.19% (2.05–2.33) |
| no_criteria | 1248/29532 = 4.23% (4.00–4.46) | N/A | 1248/29532 = 4.23% (4.00–4.46) |
| practice_guideline | 0/26 = 0.00% (0.00–12.87) | 0/1 = 0.00% (0.00–79.35) | 0/25 = 0.00% (0.00–13.32) |
| single_submitter | 3687/137197 = 2.69% (2.60–2.77) | 100/726 = 13.77% (11.46–16.47) | 3587/136471 = 2.63% (2.54–2.71) |

## C/D. Controlled faults and trust boundary (false admissions)

| Cohort | Schema-only | Aggregate-quality ablation | Full |
|---|---:|---:|---:|
| controlled_fault | 160/160 | 64/160 | 0/160 |
| trust_boundary | 16/16 | 16/16 | 16/16 |

Stability is not correctness, and ClinVar's own review tiers influence later submissions. Strata are equal-sized, so pooled sample rates are not population rates. Observational; not for clinical use.
