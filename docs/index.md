# BioAI Evidence Validator

**Stop AI-extracted biological claims from entering your knowledge base or training set
before their evidence is good enough for that use.**

An LLM can turn a paper into a tidy `gene → associated_with → phenotype` record that passes
every schema check. This toolkit asks the next question: *is the evidence behind it sufficient
for the specific use you have in mind?* It checks evidence structure, provenance consistency,
scope and human-review requirements, then returns an auditable **admitted / review_required /
rejected** decision for each requested use.

```bash
pip install bioai-evidence-validator
```

Try it without installing anything:
[quickstart notebook on Colab](https://colab.research.google.com/github/NingyuSUN/bioai-evidence-validator/blob/main/examples/quickstart.ipynb).

## In one minute

Write the claim as a [draft](DRAFTS.md), build it into a full evidence record, and validate
it against a [profile](PROFILES.md):

```bash
bioevidence build examples/drafts/llm_claim.yaml --output record.json
bioevidence validate record.json --profile literature-claim    # exit 2: review required
```

The evidence came only from LLM extraction, and the `literature-claim` profile does not let
a publication result rest on that alone (`BEV008`). The manually curated version of the same
claim is admitted. Exit codes: **0** admitted, **1** rejected, **2** review required,
**3** input or configuration error.

## What the evidence says

- **[ClinVar, three years later](benchmarks/clinvar.md).** A ClinVar-style profile matches
  NCBI's own 2023 review status on 98–99% of decisions. Where the validator is stricter,
  holding back pathogenic classifications that carry a dissenting submission, those
  classifications were about 4–5× more likely to be reclassified or in conflict by 2026.
- **[Controlled faults](benchmarks/vbo-canine.md).** On both real-data cases, schema-only
  checks admit 160/160 injected faults; the full validator admits 0/160.
- **Stated limits.** Both cases report what the engine cannot catch (fabricated source
  metadata), and neither has independent expert annotation yet.

## Where to go next

| I want to… | Read |
|---|---|
| Write records quickly or from LLM output | [Drafts](DRAFTS.md) |
| Encode my domain's admission policy | [Profiles](PROFILES.md), [community profiles](community-profiles.md) |
| Check records in pull requests | [GitHub Action](https://github.com/NingyuSUN/bioai-evidence-validator#check-records-in-ci) |
| Know exactly what is checked | [Engineering contract](ENGINEERING.md) |
| Map records to ECO, Biolink or VA-Spec | [Standards alignment](STANDARDS.md) |
| Evaluate on my own project | [Building a gold standard](GOLD_STANDARD.md) |
| Contribute | [Contributing](contributing.md) |

Not for clinical use. Admission means a record meets the selected profile, not that a
biological claim is true.
