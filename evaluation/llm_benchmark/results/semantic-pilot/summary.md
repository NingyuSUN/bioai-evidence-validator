# Semantic checks on the literature benchmark (pilot set)

## Controls

| Checker | Control | Result |
|---|---|---:|
| Claude Haiku 4.5 | base_read_correctly (direction flip exposed) | 59/63 |
| Claude Haiku 4.5 | unrelated_claim_not_addressed | 7/12 |
| Claude Haiku 4.5 | species_seen_as_non_human | 7/8 |
| Claude Haiku 4.5 | hedged_seen_as_hedged | 8/12 |
| Gemini 3.8 Flash | base_read_correctly (direction flip exposed) | 62/63 |
| Gemini 3.8 Flash | unrelated_claim_not_addressed | 12/12 |
| Gemini 3.8 Flash | species_seen_as_non_human | 7/8 |
| Gemini 3.8 Flash | hedged_seen_as_hedged | 8/12 |
| GPT-5.6-Luna | base_read_correctly (direction flip exposed) | 63/63 |
| GPT-5.6-Luna | unrelated_claim_not_addressed | 11/12 |
| GPT-5.6-Luna | species_seen_as_non_human | 7/8 |
| GPT-5.6-Luna | hedged_seen_as_hedged | 9/12 |
| semantic cues | base_flagged (false review) | 22/63 |
| semantic cues | direction_flip_flagged | 28/63 |
| semantic cues | species_flagged | 8/8 |

## Natural answers (every non-stop answer with the paper, all six extractors)

| Pipeline | Wrong direction admitted | Correct answers stopped | Wrong answers stopped |
|---|---:|---:|---:|
| LLM + paper + bioevidence (grounding) | 5/68 | 0/63 | 0/5 |
| + semantic cues | 4/68 | 23/63 | 1/5 |
| + one independent reviewer | 4/68 | 2/63 | 1/5 |
| + one independent reviewer + cues | 4/68 | 25/63 | 1/5 |
| + two independent reviewers | 4/68 | 4/63 | 1/5 |
| + two independent reviewers + cues | 4/68 | 26/63 | 1/5 |

Reviewers are the fast models of the other two vendors (Claude Haiku 4.5, GPT-5.6-Luna, Gemini 3.8 Flash) and never see the extractor's decision. With one reviewer, Gemini reviews Claude, Claude reviews GPT and GPT reviews Gemini; with two, both other vendors must accept. A reviewer or cue can only send a record to a human. Wilson 95% intervals are in `summary.json`.
