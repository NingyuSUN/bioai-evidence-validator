# Standards alignment

How this project's record model relates to the evidence standards biocurators already use.
Every term below was checked against its source on 2026-09-25:

| Standard | Version checked | Source |
|---|---|---|
| Evidence & Conclusion Ontology (ECO) | release 2026-07-10 | [OLS](https://www.ebi.ac.uk/ols4/ontologies/eco) |
| Biolink Model | 4.4.4 | [biolink_model.yaml](https://github.com/biolink/biolink-model) |
| GA4GH Variant Annotation Specification (VA-Spec) | 1.0.1 | [va-core-source.yaml](https://github.com/ga4gh/va-spec/blob/1.0.1/schema/va-spec/base/va-core-source.yaml) |
| W3C PROV-O | Recommendation | [PROV-O](https://www.w3.org/TR/prov-o/) |

Mapping strength follows SKOS: **exact** (interchangeable), **close** (same intent, some
difference in scope), **related** (overlapping idea, not a substitute), **none**.

## Records, statements and evidence

| This project | GA4GH VA-Spec 1.0.1 | Biolink 4.4.4 | PROV-O | Strength and notes |
|---|---|---|---|---|
| `Statement` (`subject`, `predicate`, `object`) | `Statement` with a `Proposition` (`subject`, `predicate`, `object`) | `Association` (`subject`, `predicate`, `object`) | – | **close**. VA separates the proposition from the statement about it; here they are one object. |
| `Statement.scope` (explicit tokens) | proposition qualifiers, e.g. `alleleOriginQualifier`, `geneContextQualifier` | association qualifiers | – | **related**. Scope is a flat token list compared for equality, not typed qualifiers. |
| `statement_status` | – | – | – | **none**. |
| `EvidenceLine` | `EvidenceLine` (`hasEvidenceItems`, `directionOfEvidenceProvided`) | – | – | **close**. Biolink does not model evidence lines. |
| `direction`: `supports` / `contradicts` / `neutral` | `supports` / `disputes` / `neutral` | – | – | **exact** values; `contradicts` = `disputes`. |
| `EvidenceItem` | an item of `EvidenceLine.hasEvidenceItems` | `has evidence` (range: information content entity) | `Entity` | **close** to VA; **related** to Biolink. |
| `EvidenceItem.extracted_text` | – | `supporting text` | – | **close**. |
| `EvidenceItem.extraction_method` | – | `agent type` | – | See [extraction methods](#extraction-methods). |
| `SourceArtifact` | `Document` (via `reportedIn`) | `primary knowledge source` / `retrieval source` | `Entity` (schema `class_uri`) | **exact** to PROV; **close** to VA; **related** to Biolink, which names an information resource rather than a hashed file snapshot. |
| `SourceArtifact` `version`, `retrieved_at`, `sha256`, `observed_sha256` | – | – | – | **none**. Project extension for frozen-source audit. |
| `Agent` (`human` / `software` / `organization`) | `Agent.agentType` (`person` / `software` / `organization` recommended) | – | `Agent` (schema `class_uri`) | **exact** to PROV; **close** to VA (`human` = `person`). |
| `Adjudication` (decision, rationale, uses, reviewer, time) | `Contribution` (`contributor`, `activityType`, `date`) | `agent type: manual_validation_of_automated_agent`, when a person accepts automated output | – | **related**. No standard field binds a human decision to a specific intended use. |
| Profiles, use contracts, per-use decisions | – | – | – | **none**. This is what the project adds: the same statement can be admitted for one use and not another. |

## Extraction methods

Machine-readable in the packaged LinkML schema as `meaning:` on each `ExtractionMethod`
value (the compiled validation schema and `schema_sha256` are unchanged by these annotations).

| `extraction_method` | ECO term (release 2026-07-10) | Biolink `agent type` | Strength and notes |
|---|---|---|---|
| `manual_curation` | `ECO:0000352` evidence used in manual assertion | `manual_agent` | **close**. |
| `deterministic_parser` | `ECO:0000313` imported information used in automatic assertion | the *upstream* source's agent type | **close** to ECO. When the imported record was itself manually asserted (e.g. a ClinVar lab submission), `ECO:0000322` imported manually asserted information used in automatic assertion is more specific. Biolink's agent type describes who produced the knowledge, not the importer. |
| `normalized_string_match` | `ECO:0008021` string-matching method evidence used in automatic assertion | `automated_agent` | **close**. |
| `llm_extraction` | `ECO:0008004` machine learning method evidence used in automatic assertion | `text_mining_agent` | **close**. ECO had no LLM-specific term at the release checked. Biolink notes that text-mining agents are prone to misinterpretation and that the source text should be consulted, which is why built-in profiles default to `allow_llm_only: false`. |
| (after a human `accept` adjudication of automated evidence) | `ECO:0000218` manual assertion, which "could involve human review of computationally generated information" | `manual_validation_of_automated_agent` | **close**, at the level of the assertion rather than the evidence item. |

To read the ECO meanings in code:

```python
from linkml_runtime.utils.schemaview import SchemaView
from bioevidence_validator.engine import default_schema_path

view = SchemaView(str(default_schema_path()))
eco = {name: value.meaning for name, value in view.get_enum("ExtractionMethod").permissible_values.items()}
# {'deterministic_parser': 'ECO:0000313', 'manual_curation': 'ECO:0000352', ...}
```

Validation reports expose this mapping only on request so the default report contract
stays unchanged. `bioevidence validate ... --annotate-eco` (or
`validate_record(record, annotate_eco=True)`) adds `evidence_eco_annotations`, with
one entry per evidence item containing `evidence_item_id`, `extraction_method`, and
`eco_curie`.

## The ClinVar case in VA-Spec terms

In the [ClinVar case](../examples/clinvar_germline/README.md), each ClinVar submission (SCV)
corresponds to a VA-Spec `Statement` by its submitter, and the case's statement is
**related** to a `VariantPathogenicityProposition` (predicate `isCausalFor`, with an
`objectCondition`). The case is variant-level and does not model the condition, so it is
not a VA-Spec pathogenicity statement. Submissions are imported by `deterministic_parser`;
`ECO:0000322` describes them more precisely.

## Not mapped

- **SEPIO.** The schema declares the `sepio:` prefix from earlier design work, but no SEPIO
  terms are used. VA-Spec's [introduction](https://github.com/ga4gh/va-spec/blob/1.0.1/docs/source/introduction.rst)
  states that it adopts and builds on the SEPIO model, so alignment is stated against VA-Spec.
- **The word "profile".** A SEPIO / VA-Spec profile specializes the *data model* for a
  knowledge type. A profile here specializes the *admission policy*: which evidence each
  intended use requires. The two are complementary; a VA-Spec pathogenicity statement could
  be checked against a profile of this project.
- **Biolink `knowledge level`.** Not modeled. A profile can require evidence types that
  imply a knowledge level, but the engine does not read or set it.
- **Strength and scores.** VA `strength`/`score` and Biolink confidence values are not
  used; admission is decided by per-use evidence requirements, not a numeric threshold.
