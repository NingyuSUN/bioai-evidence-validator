# AI validation roadmap

Tracking issue: [#26](https://github.com/NingyuSUN/bioai-evidence-validator/issues/26) · target release: **0.8.0**

## Why AI validation is the core of this project

Most Bio-AI demonstrations show that a model *can* produce a plausible answer. Organisations
that act on biological evidence, pharma above all, need something else: a reason to trust a
specific output for a specific purpose, and a measured account of when that trust fails.
This project is built around that question. The same claim can be admitted for a research
summary and refused for a clinical reference, depending on what evidence the intended use
requires.

That framing matches how regulators describe AI credibility. FDA's draft guidance
*Considerations for the Use of Artificial Intelligence To Support Regulatory Decision-Making
for Drug and Biological Products* (January 2025) proposes a risk-based credibility assessment
framework:

1. define the question of interest;
2. define the **context of use** of the model;
3. assess **model risk**, which combines model influence (how much the decision rests on the
   model) with decision consequence (the harm of a wrong decision);
4. then plan and gather credibility evidence.

In this project, a requested use plays the role of the context of use, and a profile states the
evidence that use requires. The mapping is conceptual. The project makes no claim of regulatory
compliance.

What the benchmarks already show:

- **Schema checks are not validation.** On both real-data cases, schema-only checking admitted
  160/160 injected faults; the full validator admitted 0/160.
- **The trust boundary is real, measured, and now reduced.** The rules trust supplied metadata:
  they admitted 16/16 records pointing to a non-existent ontology term, and 16/16 records with
  a fabricated expert review. Source grounding (#19) recomputes such claims from the pinned
  snapshots and admits none of the 80 trust-boundary forgeries in the two benchmarks, without
  changing any real-source decision.

## The chain

```text
source → structured extraction → provenance → deterministic validation
       → model/agent evaluation → trust boundary → human review
```

| Stage | Question it answers | In the repository today | Gap | Issue |
|---|---|---|---|---|
| Source | Which exact bytes is the evidence taken from? | Frozen, hash-pinned snapshots with rebuild scripts (VBO, ClinVar, 140 open-access papers for CIViC) | Papers without open full text can only be sent to review | — |
| Structured extraction | Did the AI turn the source into the right claim? | Draft format and per-profile JSON Schema for LLM output | **Never run with real models on real text**; extraction methods in the benchmarks are simulated | [#21](https://github.com/NingyuSUN/bioai-evidence-validator/issues/21) |
| Provenance | Can each item be traced to its source and method? | Source artifacts, locators, methods; PROV/ECO/VA-Spec mapping; locators and review tiers recomputed from pinned snapshots | Methods are self-declared | Signed attestations (future) |
| Deterministic validation | Is the evidence sufficient for this use, by fixed rules? | Engine, profiles, per-type quality gates, audit reports | — | — |
| Model/agent evaluation | What can model review replace, and where does it fail? | Blinded model-review runner (#17), pilot on 20 cases | No reference labels yet; error correlation unmeasured | [#22](https://github.com/NingyuSUN/bioai-evidence-validator/issues/22) |
| Trust boundary | What does the system still take on faith? | Source grounding recomputes identifiers, review tiers, completeness, retractions and quotes from pinned snapshots (0/80 structured-source forgeries and 0/489 literature controls admitted) | Whether a verbatim quote supports the claim | [#31](https://github.com/NingyuSUN/bioai-evidence-validator/issues/31) |
| Human review | What do experts conclude, and how reliably? | Protocol, `bioevidence review` tooling, blinded ClinVar kit | **No expert labels yet** | [#23](https://github.com/NingyuSUN/bioai-evidence-validator/issues/23) |

## How the work will be evaluated

- **Negative controls for every failure mode.** Each entry of the
  [error taxonomy](ERROR_TAXONOMY.md) either has a controlled fault that is expected to be
  caught, or is listed as uncovered with the issue that will add one.
- **Held-out evaluation.** The ClinVar case already judges 2023 evidence against 2026 outcomes.
  Expert review separates a calibration set, used to clarify the rubric, from a test set that
  is only scored.
- **Pre-registration.** Profiles, mappings, prompts and thresholds are fixed before test
  results are seen. Changes after that require a separately reported evaluation.
- **Calibrated triage.** Records are routed to auto-admit, risk-ranked expert review or reject.
  A seeded random audit bounds the error rate of what was auto-admitted
  ([#24](https://github.com/NingyuSUN/bioai-evidence-validator/issues/24)).
- **Reproducibility.** Every number regenerates from pinned snapshots with one command
  ([#25](https://github.com/NingyuSUN/bioai-evidence-validator/issues/25)).
- **Limits next to results.** Every result states what its labels are and what it does not
  measure.

## Workstreams and order

| Order | Issue | Workstream | Depends on |
|---|---|---|---|
| Now | [#18](https://github.com/NingyuSUN/bioai-evidence-validator/issues/18) | Error taxonomy and coverage matrix | — |
| Done | [#19](https://github.com/NingyuSUN/bioai-evidence-validator/issues/19) | Source grounding, phase 1: recompute what the pinned snapshot can prove | — |
| Now | [#23](https://github.com/NingyuSUN/bioai-evidence-validator/issues/23) | Expert review of the ClinVar packet (runs in parallel; experts' time) | — |
| Done | [#20](https://github.com/NingyuSUN/bioai-evidence-validator/issues/20) | Source grounding, phase 2: verify cited literature and quotes | #19 |
| Now | [#31](https://github.com/NingyuSUN/bioai-evidence-validator/issues/31) | Semantic support check: does a verbatim quote support the claim's direction? | #20 |
| Next | [#21](https://github.com/NingyuSUN/bioai-evidence-validator/issues/21) | Real AI extraction experiment on openly licensed sources | #18, #20 |
| Next | [#22](https://github.com/NingyuSUN/bioai-evidence-validator/issues/22) | Model and agent evaluation against expert labels | #17, #23 |
| Done | [#24](https://github.com/NingyuSUN/bioai-evidence-validator/issues/24) | Calibrated triage and audit of auto-admitted records (tooling, routing evidence and a dry run; the expert audit needs #23) | #23 |
| Done | [#25](https://github.com/NingyuSUN/bioai-evidence-validator/issues/25) | Reproducible benchmark, funnel figure and validation dossier | all |

## Definition of done for 0.8.0

- Every failure mode in the taxonomy is caught by a measured layer, or explicitly listed as a
  remaining limitation.
- The two existing trust-boundary cohorts fall from 16/16 admitted to 0/16, with no new false
  blocks on the real-source cohorts.
- Real AI extraction on openly licensed sources has passed through the whole chain, with
  per-stage counts.
- Expert labels, their reliability, and model and validator scores against them are published.
- The auto-admitted error rate has an audited upper bound.
- One command reproduces all of it. A validation dossier presents the question of interest,
  context of use, model risk, credibility evidence and limitations.

## Non-goals

- No claim of regulatory or clinical validity. Admission means a record meets a profile, not
  that a claim is true.
- Not a variant classifier and not a replacement for expert curation of high-consequence decisions.
- No training of new models. Models are used and evaluated as they are, pinned by version and
  date.

## Risks

| Risk | Mitigation |
|---|---|
| Expert time is scarce | Calibration first; smaller control sets; a single-reviewer set is labelled as such |
| Models change silently | Record model IDs, CLI versions and dates; re-measure after upgrades |
| Licensing of source text | Store and redistribute only openly licensed text; otherwise hashes and locators only |
| Overfitting rules to the test set | Pre-registration; calibration and test splits; report later changes separately |
| Model-review cost and quotas | Pilot sizes first; record tokens and time per call |
