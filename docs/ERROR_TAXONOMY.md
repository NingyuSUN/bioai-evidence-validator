# Error taxonomy

How AI-assisted biological curation goes wrong, which layer is expected to catch each failure, and what the
benchmarks show today. Generated from `evaluation/error_taxonomy.yaml` and the committed benchmark results by
`tools/render_taxonomy.py`; a test fails if this page, the benchmark faults and the rule codes drift apart.
Part of the [AI validation roadmap](AI_VALIDATION_ROADMAP.md).

**20 failure modes:** ✅ caught 8 · 🟡 partial 7 · ❌ exposed 0 · ⬜ uncovered 5

## Coverage matrix

Negative controls show how many injected cases the validator with grounding admitted (0 is the goal); where
the rules alone admit a different number, it follows in parentheses.

| ID | Failure mode | Origin | Expected to catch it | Status | Negative controls: admitted / cases | Next |
|---|---|---|---|---|---|---|
| SRC-1 | Fabricated source identifier | source | Grounding | ✅ caught | `vbo:falsified_target` 0/16 (rules alone: 16)<br>`civic:fabricated_identifier` 0/120 | — |
| SRC-2 | Misattributed source | source | Grounding | ✅ caught | `civic:real_identifier_wrong_paper` 0/120 | — |
| SRC-3 | Retracted or superseded source | source | Grounding | 🟡 partial | `civic:retracted_source` 0/20 | [#25](https://github.com/NingyuSUN/bioai-evidence-validator/issues/25) |
| SRC-4 | Source bytes changed | source | Rules, Grounding | ✅ caught | `vbo:source_hash_mismatch` 0/16<br>`clinvar:source_hash_mismatch` 0/16<br>`vbo:unpinned_source` 0/16 (rules alone: 16) | — |
| EXT-1 | Fabricated or altered quote | extraction | Grounding | ✅ caught | `civic:altered_quote` 0/120 | — |
| EXT-2 | Polarity error | extraction | Grounding, Models, Experts | 🟡 partial | `civic:negation_flip` 0/82 | [#31](https://github.com/NingyuSUN/bioai-evidence-validator/issues/31), [#22](https://github.com/NingyuSUN/bioai-evidence-validator/issues/22) |
| EXT-3 | Certainty inflation | extraction | Models, Experts | ⬜ uncovered | — | [#31](https://github.com/NingyuSUN/bioai-evidence-validator/issues/31), [#21](https://github.com/NingyuSUN/bioai-evidence-validator/issues/21) |
| EXT-4 | Scope error | extraction | Rules, Grounding | 🟡 partial | `vbo:scope_mismatch` 0/16<br>`clinvar:somatic_scope` 0/16<br>`civic:species_swap` 0/27 | [#20](https://github.com/NingyuSUN/bioai-evidence-validator/issues/20) |
| EXT-5 | Entity resolution error | extraction | Rules, Grounding | 🟡 partial | `vbo:missing_uniqueness` 0/16<br>`vbo:wrong_existing_target` 0/16 (rules alone: 16) | [#20](https://github.com/NingyuSUN/bioai-evidence-validator/issues/20), [#21](https://github.com/NingyuSUN/bioai-evidence-validator/issues/21) |
| EXT-6 | Relation error | extraction | Rules, Models, Experts | ⬜ uncovered | — | [#21](https://github.com/NingyuSUN/bioai-evidence-validator/issues/21) |
| PRV-1 | Extraction method misreported | provenance | Attestation | ⬜ uncovered | — | future: signed pipeline attestations |
| PRV-2 | Weak support masked | provenance | Rules | ✅ caught | `vbo:required_llm_plus_note` 0/16<br>`vbo:required_string_plus_note` 0/16<br>`vbo:required_mixed_weak_plus_note` 0/16<br>`vbo:weak_unique_resolution` 0/16<br>`clinvar:llm_classification_plus_note` 0/16<br>`clinvar:string_match_classification_plus_note` 0/16<br>`clinvar:mixed_weak_classification_plus_note` 0/16<br>`clinvar:llm_derived_review` 0/16 | — |
| PRV-3 | Fabricated review | provenance | Grounding, Attestation | 🟡 partial | `clinvar:fabricated_expert_review` 0/16 (rules alone: 16) | future: signed pipeline attestations |
| PRV-4 | Broken record integrity | provenance | Rules | ✅ caught | `vbo:dangling_reference` 0/16<br>`clinvar:dangling_reference` 0/16<br>`clinvar:missing_derived_review` 0/16 | — |
| AGG-1 | Unresolved conflict | aggregation | Rules | ✅ caught | `vbo:explicit_contradiction` 0/16<br>`clinvar:injected_dissent` 0/16 | — |
| AGG-2 | Dissent omitted | aggregation | Grounding | 🟡 partial | `clinvar:omitted_dissent` 0/16 (rules alone: 16) | [#20](https://github.com/NingyuSUN/bioai-evidence-validator/issues/20) |
| AGG-3 | Withdrawn statement reused | aggregation | Rules | ✅ caught | `vbo:withdrawn_statement` 0/16<br>`clinvar:withdrawn_statement` 0/16 | — |
| AGG-4 | Correlated model consensus | aggregation | Design, Models | ⬜ uncovered | — | [#22](https://github.com/NingyuSUN/bioai-evidence-validator/issues/22) |
| REV-1 | Reviewer exposure | review | Design | 🟡 partial | — | [#23](https://github.com/NingyuSUN/bioai-evidence-validator/issues/23) |
| REV-2 | Unreliable reference labels | review | Experts, Design | ⬜ uncovered | — | [#23](https://github.com/NingyuSUN/bioai-evidence-validator/issues/23) |

## Legend

| Status | Meaning |
|---|---|
| ✅ caught | Every controlled case of this failure is refused or sent to review by the validator with grounding. |
| 🟡 partial | Controlled or tested forms are caught; a described form is not yet covered. |
| ❌ exposed | Controlled cases show it is NOT caught today, even with grounding; a measured trust-boundary gap. |
| ⬜ uncovered | No negative control yet; the planned work will add one. |

| Layer | Meaning |
|---|---|
| Rules (`deterministic`) | Fixed engine rules over the supplied record (offline, reproducible). |
| Grounding (`grounding`) | Checks recomputed from the source itself (identifiers, bytes, quotes, completeness). |
| Models (`model_review`) | Independent model or agent review; weak evidence on its own. |
| Experts (`human_review`) | Expert review, blinded, with measured agreement. |
| Attestation (`attestation`) | Signed statements from a trusted pipeline about how evidence was produced. |
| Design (`process`) | Study design (blinding, pre-registration) rather than a runtime check. |

| Origin | Meaning |
|---|---|
| source | The cited source itself is wrong, missing, changed or withdrawn. |
| extraction | The AI misreads or misrepresents what the source says. |
| provenance | The record misdescribes where evidence came from or how it was produced. |
| aggregation | Evidence is combined or selected in a way that hides what it really supports. |
| review | The human reference used to judge everything else is itself unreliable. |

## Failure modes

### SRC-1 · Fabricated source identifier

**✅ caught** · origin: source · expected layer: Grounding

The record cites an identifier (ontology term, accession, PMID, DOI) that does not exist in the source.

*Example:* A dog-name mapping whose target VBO term does not exist in the pinned release.

Rule codes: `BEV016`

*Note:* Grounding checks identifiers against pinned snapshots (VBO terms; ClinVar variants and submissions; PMIDs, PMCIDs and DOIs resolved by `bioevidence ground`).

| Negative control | Cases | Schema-only admitted | Aggregate gate admitted | Rules admitted | Rules + grounding admitted |
|---|---:|---:|---:|---:|---:|
| [vbo](../examples/vbo_canine/README.md) `falsified_target` | 16 | 16 | 16 | 16 | 0 |
| [civic](../examples/civic_literature/README.md) `fabricated_identifier` | 120 | — | — | — | 0 |

### SRC-2 · Misattributed source

**✅ caught** · origin: source · expected layer: Grounding

A real identifier is cited, but the claim or quote comes from a different source.

*Example:* A correct PMID for an unrelated paper attached to a gene–disease claim.

Rule codes: `BEV017`

*Note:* The literature grounder compares the record's title and quotes with the pinned paper the identifier resolves to. A paper without open full text cannot be checked and goes to review (BEV015).

| Negative control | Cases | Schema-only admitted | Aggregate gate admitted | Rules admitted | Rules + grounding admitted |
|---|---:|---:|---:|---:|---:|
| [civic](../examples/civic_literature/README.md) `real_identifier_wrong_paper` | 120 | — | — | — | 0 |

### SRC-3 · Retracted or superseded source

**🟡 partial** · origin: source · expected layer: Grounding

The cited source has been retracted, corrected or replaced by a newer version.

*Example:* A claim resting on a paper retracted after the extraction was made.

Rule codes: `BEV019`

*Not yet covered:* A retraction published after grounding is seen only when the source is grounded again (`bioevidence ground --refresh`).

*Note:* Retraction as recorded by PubMed, Europe PMC or Crossref when the paper was grounded.

| Negative control | Cases | Schema-only admitted | Aggregate gate admitted | Rules admitted | Rules + grounding admitted |
|---|---:|---:|---:|---:|---:|
| [civic](../examples/civic_literature/README.md) `retracted_source` | 20 | — | — | — | 0 |

Planned: [#25](https://github.com/NingyuSUN/bioai-evidence-validator/issues/25)

### SRC-4 · Source bytes changed

**✅ caught** · origin: source · expected layer: Rules, Grounding

The bytes used differ from the frozen snapshot the record names.

*Example:* An observed source hash that differs from the record's frozen hash.

Rule codes: `BEV002`, `BEV014`, `BEV015`

*Note:* The engine compares the hashes a record supplies (BEV002). Grounding recomputes them from the snapshot store, so consistent but false hashes are caught too; bytes that are missing go to review (BEV015) and bytes that differ are rejected (BEV014).

| Negative control | Cases | Schema-only admitted | Aggregate gate admitted | Rules admitted | Rules + grounding admitted |
|---|---:|---:|---:|---:|---:|
| [vbo](../examples/vbo_canine/README.md) `source_hash_mismatch` | 16 | 16 | 0 | 0 | 0 |
| [clinvar](../examples/clinvar_germline/README.md) `source_hash_mismatch` | 16 | 16 | 0 | 0 | 0 |
| [vbo](../examples/vbo_canine/README.md) `unpinned_source` | 16 | 16 | 16 | 16 | 0 |

### EXT-1 · Fabricated or altered quote

**✅ caught** · origin: extraction · expected layer: Grounding

The extracted text does not appear in the source, or was reworded so its meaning changed.

*Example:* A quote that reads "strongly associated" where the source says "may be associated".

Rule codes: `BEV017`

*Note:* Quotes must appear verbatim (after Unicode, quote-mark, dash and whitespace normalisation) in the pinned full text, at the named paragraph.

| Negative control | Cases | Schema-only admitted | Aggregate gate admitted | Rules admitted | Rules + grounding admitted |
|---|---:|---:|---:|---:|---:|
| [civic](../examples/civic_literature/README.md) `altered_quote` | 120 | — | — | — | 0 |

### EXT-2 · Polarity error

**🟡 partial** · origin: extraction · expected layer: Grounding, Models, Experts

A negative or contradicting finding is extracted as supporting.

*Example:* "No association was observed between X and Y" extracted as X associated_with Y.

Rule codes: `BEV017`

*Not yet covered:* A verbatim quote read with the wrong polarity passes grounding; only semantic review can catch it.

| Negative control | Cases | Schema-only admitted | Aggregate gate admitted | Rules admitted | Rules + grounding admitted |
|---|---:|---:|---:|---:|---:|
| [civic](../examples/civic_literature/README.md) `negation_flip` | 82 | — | — | — | 0 |

Planned: [#31](https://github.com/NingyuSUN/bioai-evidence-validator/issues/31), [#22](https://github.com/NingyuSUN/bioai-evidence-validator/issues/22)

### EXT-3 · Certainty inflation

**⬜ uncovered** · origin: extraction · expected layer: Models, Experts

A hedged, speculative or preliminary statement is extracted as an asserted finding.

*Example:* "These data suggest a possible role" extracted as an established association.

Planned: [#31](https://github.com/NingyuSUN/bioai-evidence-validator/issues/31), [#21](https://github.com/NingyuSUN/bioai-evidence-validator/issues/21)

### EXT-4 · Scope error

**🟡 partial** · origin: extraction · expected layer: Rules, Grounding

Evidence about one species, population, tissue or origin is used for another.

*Example:* A somatic finding supporting a germline classification; a mouse result supporting a human claim.

Rule codes: `BEV005`

*Not yet covered:* When the record's scope tokens are wrong but consistent with each other, only a check against the source text (e.g. the species it mentions) can catch it.

| Negative control | Cases | Schema-only admitted | Aggregate gate admitted | Rules admitted | Rules + grounding admitted |
|---|---:|---:|---:|---:|---:|
| [vbo](../examples/vbo_canine/README.md) `scope_mismatch` | 16 | 16 | 0 | 0 | 0 |
| [clinvar](../examples/clinvar_germline/README.md) `somatic_scope` | 16 | 16 | 0 | 0 | 0 |
| [civic](../examples/civic_literature/README.md) `species_swap` | 27 | — | — | — | 0 |

Planned: [#20](https://github.com/NingyuSUN/bioai-evidence-validator/issues/20)

### EXT-5 · Entity resolution error

**🟡 partial** · origin: extraction · expected layer: Rules, Grounding

A named entity is mapped to the wrong identifier, or to one of several candidates without evidence that the choice is unique.

*Example:* An ambiguous dog name mapped to one of two VBO terms without uniqueness evidence.

Rule codes: `BEV007`, `BEV017`

*Not yet covered:* An entity resolved from free text needs the source passage to check the mention against.

*Note:* For exact-name mappings, grounding recomputes the candidates from the pinned ontology, so a real but wrong target is rejected.

| Negative control | Cases | Schema-only admitted | Aggregate gate admitted | Rules admitted | Rules + grounding admitted |
|---|---:|---:|---:|---:|---:|
| [vbo](../examples/vbo_canine/README.md) `missing_uniqueness` | 16 | 16 | 0 | 0 | 0 |
| [vbo](../examples/vbo_canine/README.md) `wrong_existing_target` | 16 | 16 | 16 | 16 | 0 |

Planned: [#20](https://github.com/NingyuSUN/bioai-evidence-validator/issues/20), [#21](https://github.com/NingyuSUN/bioai-evidence-validator/issues/21)

### EXT-6 · Relation error

**⬜ uncovered** · origin: extraction · expected layer: Rules, Models, Experts

The wrong relation is extracted, e.g. association stated as causation, or a predicate the evidence does not support.

*Example:* "Carriers had higher risk" extracted as "variant causes disease".

Rule codes: `BEV003`

*Note:* Predicates outside a profile's allowlist are rejected (BEV003, unit-tested), but an allowed yet wrong predicate has no negative control.

Planned: [#21](https://github.com/NingyuSUN/bioai-evidence-validator/issues/21)

### PRV-1 · Extraction method misreported

**⬜ uncovered** · origin: provenance · expected layer: Attestation

The record claims manual curation or deterministic parsing for evidence produced by a model.

*Example:* LLM output submitted with extraction_method manual_curation.

*Note:* The engine trusts the declared method; profiles and draft docs require the pipeline, not the model, to set it.

Planned: future: signed pipeline attestations

### PRV-2 · Weak support masked

**✅ caught** · origin: provenance · expected layer: Rules

A required evidence type rests only on LLM or string-match output, padded with unrelated stronger evidence so the record looks well supported.

*Example:* An LLM-only classification plus a manually curated note of another type.

Rule codes: `BEV008`, `BEV009`, `BEV013`

| Negative control | Cases | Schema-only admitted | Aggregate gate admitted | Rules admitted | Rules + grounding admitted |
|---|---:|---:|---:|---:|---:|
| [vbo](../examples/vbo_canine/README.md) `required_llm_plus_note` | 16 | 16 | 16 | 0 | 0 |
| [vbo](../examples/vbo_canine/README.md) `required_string_plus_note` | 16 | 16 | 16 | 0 | 0 |
| [vbo](../examples/vbo_canine/README.md) `required_mixed_weak_plus_note` | 16 | 16 | 16 | 0 | 0 |
| [vbo](../examples/vbo_canine/README.md) `weak_unique_resolution` | 16 | 16 | 16 | 0 | 0 |
| [clinvar](../examples/clinvar_germline/README.md) `llm_classification_plus_note` | 16 | 16 | 16 | 0 | 0 |
| [clinvar](../examples/clinvar_germline/README.md) `string_match_classification_plus_note` | 16 | 16 | 16 | 0 | 0 |
| [clinvar](../examples/clinvar_germline/README.md) `mixed_weak_classification_plus_note` | 16 | 16 | 16 | 0 | 0 |
| [clinvar](../examples/clinvar_germline/README.md) `llm_derived_review` | 16 | 16 | 16 | 0 | 0 |

### PRV-3 · Fabricated review

**🟡 partial** · origin: provenance · expected layer: Grounding, Attestation

The record claims an expert or human review that did not happen, or relabels weak evidence as reviewed.

*Example:* No-criteria ClinVar submissions relabelled as criteria-based, with an invented expert-panel review.

Rule codes: `BEV017`

*Not yet covered:* A review claimed outside any pinned source (e.g. a curator's own sign-off) can only be checked by a signed attestation.

*Note:* Grounding rebuilds review tiers from the pinned ClinVar sample, so relabelled submissions and invented expert reviews are rejected.

| Negative control | Cases | Schema-only admitted | Aggregate gate admitted | Rules admitted | Rules + grounding admitted |
|---|---:|---:|---:|---:|---:|
| [clinvar](../examples/clinvar_germline/README.md) `fabricated_expert_review` | 16 | 16 | 16 | 16 | 0 |

Planned: future: signed pipeline attestations

### PRV-4 · Broken record integrity

**✅ caught** · origin: provenance · expected layer: Rules

References dangle, required evidence is missing, or the record is structurally invalid.

*Example:* An evidence item pointing to a source that is not in the record.

Rule codes: `SCHEMA`, `RECORD_INTEGRITY`, `BEV007`

| Negative control | Cases | Schema-only admitted | Aggregate gate admitted | Rules admitted | Rules + grounding admitted |
|---|---:|---:|---:|---:|---:|
| [vbo](../examples/vbo_canine/README.md) `dangling_reference` | 16 | 16 | 0 | 0 | 0 |
| [clinvar](../examples/clinvar_germline/README.md) `dangling_reference` | 16 | 16 | 0 | 0 | 0 |
| [clinvar](../examples/clinvar_germline/README.md) `missing_derived_review` | 16 | 16 | 0 | 0 | 0 |

### AGG-1 · Unresolved conflict

**✅ caught** · origin: aggregation · expected layer: Rules

Contradicting evidence is present but the claim is admitted as if it were settled.

*Example:* A pathogenic classification admitted despite a criteria-based uncertain-significance submission.

Rule codes: `BEV004`

*Note:* In the ClinVar population, 1★ P/LP variants with a dissenting submission were reclassified or put in conflict within three years 13.77% of the time, against 2.63% without.

| Negative control | Cases | Schema-only admitted | Aggregate gate admitted | Rules admitted | Rules + grounding admitted |
|---|---:|---:|---:|---:|---:|
| [vbo](../examples/vbo_canine/README.md) `explicit_contradiction` | 16 | 16 | 0 | 0 | 0 |
| [clinvar](../examples/clinvar_germline/README.md) `injected_dissent` | 16 | 16 | 0 | 0 | 0 |

### AGG-2 · Dissent omitted

**🟡 partial** · origin: aggregation · expected layer: Grounding

Contradicting evidence that exists in the source is left out of the record entirely.

*Example:* An importer or agent that drops the one submission disagreeing with the rest.

Rule codes: `BEV018`

*Not yet covered:* Completeness is checked only where a grounder can enumerate the source (structured registries); dissent omitted from free text is not.

*Note:* The engine can only act on dissent it is shown. Grounding lists every submission for the variant in the pinned sample and sends a record that leaves one out to review.

| Negative control | Cases | Schema-only admitted | Aggregate gate admitted | Rules admitted | Rules + grounding admitted |
|---|---:|---:|---:|---:|---:|
| [clinvar](../examples/clinvar_germline/README.md) `omitted_dissent` | 16 | 16 | 16 | 16 | 0 |

Planned: [#20](https://github.com/NingyuSUN/bioai-evidence-validator/issues/20)

### AGG-3 · Withdrawn statement reused

**✅ caught** · origin: aggregation · expected layer: Rules

A statement already rejected or superseded is admitted again.

*Example:* A superseded mapping resubmitted for catalog use.

Rule codes: `BEV001`

| Negative control | Cases | Schema-only admitted | Aggregate gate admitted | Rules admitted | Rules + grounding admitted |
|---|---:|---:|---:|---:|---:|
| [vbo](../examples/vbo_canine/README.md) `withdrawn_statement` | 16 | 16 | 0 | 0 | 0 |
| [clinvar](../examples/clinvar_germline/README.md) `withdrawn_statement` | 16 | 16 | 0 | 0 | 0 |

### AGG-4 · Correlated model consensus

**⬜ uncovered** · origin: aggregation · expected layer: Design, Models

Agreement among several models is treated as independent confirmation although their errors are correlated.

*Example:* Three models all accepting a claim none of them checked against the source.

*Note:* By design, model-produced evidence is typed as LLM output and cannot be a required type's only support (BEV008); error correlation is not yet measured.

Planned: [#22](https://github.com/NingyuSUN/bioai-evidence-validator/issues/22)

### REV-1 · Reviewer exposure

**🟡 partial** · origin: review · expected layer: Design

A human reviewer sees validator or model outputs, the aggregate status, or later outcomes before labelling.

*Example:* A reviewer looking up the variant's current ClinVar page.

*Not yet covered:* Exposure outside the packet is only self-reported.

*Note:* The review packet is tested to contain no identifiers, aggregate status or outputs; reviewers self-report later information. Look-ups outside the packet cannot be prevented.

Planned: [#23](https://github.com/NingyuSUN/bioai-evidence-validator/issues/23)

### REV-2 · Unreliable reference labels

**⬜ uncovered** · origin: review · expected layer: Experts, Design

Expert labels disagree too much, or reflect one reviewer's view, to serve as a reference.

*Example:* Two reviewers agreeing barely above chance on clinical-reference admission.

*Note:* Agreement is measured with bioevidence review agreement; no expert labels exist yet.

Planned: [#23](https://github.com/NingyuSUN/bioai-evidence-validator/issues/23)
