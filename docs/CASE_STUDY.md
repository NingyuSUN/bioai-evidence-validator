# Case study: evidence admission across BioAI workflows

## Problem

AI-assisted pipelines can emit structurally valid records that lack sufficient evidence
for the destination. A literature statement may be suitable for a research summary but
require human review before knowledge-base admission. A sample label may be usable as an
annotation while lacking approval for training or evidence of cohort independence.

## Implementation

The core schema separates assertion, source, evidence, adjudication, and intended use.
The engine checks references and provenance consistency before evaluating a selected
YAML profile. Each use receives its own decision and reason codes. Human adjudications
are attached to a statement and explicit uses; acceptance cannot erase contrary evidence.
The report hashes the input and configuration to make decisions traceable.

The public examples demonstrate:

| Input | Expected result | Reason |
|---|---|---|
| General curated assertion | Admitted | Scoped supporting evidence satisfies the general contract |
| Literature LLM-only association | Review required | Extraction alone needs review under this profile |
| Dataset label with sample link and scoped acceptance | Admitted for training | Both evidence types and human acceptance are supplied |
| Dataset label missing sample link | Rejected | The required link evidence is absent |
| Custom assay record | Admitted for assay curation | A new YAML profile supplies the domain contract |

All records, identifiers, reviewers, and source hashes in these fixtures are synthetic.
The independent test suite additionally demonstrates a novel organoid/imaging profile,
negative evidence/reference cases, and isolation between training and external-validation
approval. These are software contract tests, not measurements of biological truth.

## Scope of the project

This is a reusable evidence-validation component for curation pipelines, not a predictive
model. It consumes already structured records; it does not extract literature, run
training, authenticate reviewers, or evaluate a model. Domain-specific pipelines can
supply those results as located evidence, while retaining responsibility for scientific
quality and source verification. The canine project remains a separate working example
on the [`canine-breed` branch](https://github.com/NingyuSUN/bioai-evidence-validator/tree/canine-breed).
