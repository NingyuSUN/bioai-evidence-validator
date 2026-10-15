# Project evidence: BioAI Evidence Validator

**A reproducible evaluation and delivery project for AI-assisted biological curation.**
The central question is which errors can be checked against a source, which can be repaired through
feedback, and which still require a biologist's judgment.

**Contributions.** Ningyu Sun designed and built the project: research framing, software
implementation, benchmark design and execution, analysis, figures and documentation.
[PandaHUN777](https://github.com/PandaHUN777) contributed Python 3.14 CI support and documentation
updates. The concrete artifacts below make the methods and results inspectable; they do not constitute
an external endorsement.

## Method and scope

The system checks records produced by six general-purpose models from three vendors. Each record carries
a biological claim, evidence and source provenance. Deterministic rules and source checks verify identifiers,
names, quotations and intended-use requirements against pinned source snapshots. A feedback loop returns
fixable findings to the proposer; conflicts and policy decisions are flagged for human review.

Experiments compare **model alone**, **validation gate**, and **validation plus feedback**. Protocols were
fixed before the held-out or external runs. The project evaluates and controls model output; it does not
train a new foundation model. Its intended use is research curation, outside clinical decision-making.

## Results a reviewer can verify

These are recorded experiments at
[`b9c9c74`](https://github.com/NingyuSUN/bioai-evidence-validator/tree/b9c9c74d70734646a64109bfdb72052e81feeec0),
not new runs performed for this page. Each denominator identifies the evaluated objects.

| Experiment and split | Comparison | Meaning and remaining limit |
|---|---|---|
| Full-paper extraction: 6 models, 40 held-out papers, 240 episodes | Of **714** first-version claims, **198** had an identifier, name or quote error. The gate admitted **489/714**; feedback admitted **663/714**, with **0/663** such errors. The admitted claims covered **77/87** CIViC items. | Source integrity improved while recovering claims a gate alone would lose. Semantic correctness remains unmeasured; **205/663** admitted claims have no CIViC counterpart, which does not establish whether they are correct. [Result JSON](https://github.com/NingyuSUN/bioai-evidence-validator/blob/b9c9c74d70734646a64109bfdb72052e81feeec0/evaluation/llm_benchmark/results/extraction-test/summary.json) |
| Single-cell annotation: 6 models, 46 held-out clusters from the development studies, 276 episodes | Answers compatible with the authors' term rose from **176/276** to **205/276**. Feedback admitted **255/276**, of which **50/255 (19.6%)** disagreed with the authors; **21/276** were flagged for human review; human review has not been performed. | Compatibility includes exact, broader or narrower ontology terms. These are study-author labels, not independent expert adjudications. [Result JSON](https://github.com/NingyuSUN/bioai-evidence-validator/blob/b9c9c74d70734646a64109bfdb72052e81feeec0/evaluation/llm_benchmark/results/celltype-test/summary.json) |
| External single-cell test: 6 other studies, 81 clusters, 486 episodes; 479 first answers | With an added ontology-definition check, compatible answers fell from **278/486** to **242/486** after feedback. The check changed **15** initially correct answers to wrong terms. | A negative result: protein-level marker definitions did not reliably transfer to transcript measurements. This experimental check differs from the held-out protocol. [Results and explanation](https://github.com/NingyuSUN/bioai-evidence-validator/blob/b9c9c74d70734646a64109bfdb72052e81feeec0/evaluation/llm_benchmark/README.md#external-split-protocol-3-the-definition-check-did-not-transfer) |

The design choices and frozen protocols are recorded in the
[validation dossier](https://github.com/NingyuSUN/bioai-evidence-validator/blob/b9c9c74d70734646a64109bfdb72052e81feeec0/docs/VALIDATION_DOSSIER.md).
Raw counts and per-model results matter: repeated answers to the same cluster or paper are correlated,
and pooled episode counts are not counts of independent biological samples.

## What has and has not been independently evaluated

Source checking establishes whether an identifier or quotation matches the pinned source. It does not
establish that a real quotation supports the interpretation or that a cell annotation is biologically correct.
The external study split tests transfer, but its reference labels still come from the dataset authors.

Six models have reviewed a blinded ClinVar packet of **190 cases each**: 20 calibration and 170 test cases.
The published [model-review summary](https://github.com/NingyuSUN/bioai-evidence-validator/blob/b9c9c74d70734646a64109bfdb72052e81feeec0/evaluation/clinvar_review/results/models/summary.md)
reports agreement among models and explicitly has **no expert reference labels**. Cross-model agreement
is not an independent human evaluation.

Independent expert annotations, an expert audit of admitted records, and a study measuring actual user
time and final-result quality remain open. The [review kit](https://github.com/NingyuSUN/bioai-evidence-validator/blob/b9c9c74d70734646a64109bfdb72052e81feeec0/evaluation/clinvar_review/README.md)
and audit tooling prepare those evaluations; they are not completed human-use studies. No measured human
time saving or clinical performance is claimed.

## Reproduce and inspect the delivery

From a checkout of the evidence snapshot above, with `uv` installed, replay the two principal result sets:

```bash
uv sync --frozen
uv run --frozen python tools/reproduce.py --only celltype-test extraction-test
```

The expected outcome is `all reproduced`. The command recomputes scores from committed model outputs and
pinned sources in temporary directories, then checks them against the committed files. It makes **no new
model calls**. Dependency setup may need network access; the replay uses local evidence. This demonstrates
cached-result reproducibility, not an independent rerun of the models or acquisition of the source data.

The full 22-step replay, installed-wheel checks and dependency requirements are documented in
[the engineering contract](ENGINEERING.md#reproduction). The wheel checks use runtime dependencies
exported from `uv.lock`, excluding the editable project, so the schema compiler matches the frozen evidence.
They retain package isolation and byte-for-byte comparisons. Versioned source, a CLI, a wheel and automated
checks provide delivery evidence; check the actual commit's [Actions run](https://github.com/NingyuSUN/bioai-evidence-validator/actions)
for its current status. Passing engineering checks does not establish biological validity.

The [v0.8.0 release](https://github.com/NingyuSUN/bioai-evidence-validator/releases/tag/v0.8.0) predates the
full-paper extraction and complete ClinVar model-review additions summarized here. Use the fixed source
snapshot to inspect these experiment artifacts instead of assuming every result is included in that release.
