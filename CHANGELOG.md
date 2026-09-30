# Changelog

## Unreleased

- Add the single-cell cell-type annotation case (`examples/singlecell_celltype`): marker tables derived
  from six CELLxGENE datasets annotated by their authors, with the Cell Ontology, HGNC and ASCT+B pinned.
  Benchmark scenario 3 runs six models on it, alone and in the feedback loop. In the pilot, 35 of 138 first
  answers gave a Cell Ontology ID that belongs to another term; none was admitted. Wrong or invalid
  annotations fell from 43% of answers to 18% of those admitted behind the gate, at the cost of half
  the annotations going to a person. The ASCT+B cross-check proved to be noise as a conflict source.
- Add generic grounders that check what a record cites against pinned reference releases, with
  messages that say what to fix: `OntologyGrounder` (ontology terms: existence, obsoletion, label,
  kind), `GeneGrounder` (HGNC symbols, previous symbols and aliases), `VariantGrounder` (HGVS form,
  RefSeq accession, genome build, position), `TableGrounder` (rows and values of a pinned table) and
  `ReferenceGrounder` (a curated reference resource that contradicts the claim or its evidence).
  New codes BEV023 (obsolete or superseded identifier), BEV024 (malformed or wrong kind) and BEV025
  (reference conflict, review only). `bioevidence validate` gains `--ontology`, `--term-root`,
  `--genes` and `--assembly-report`.
- Add `feedback`, the validate–feedback–revise loop around any proposer: fixable findings go back as
  reasons, conflicts and policy decisions go to a person unchanged, and verified evidence is carried
  through revisions.
- Benchmark scenario 2 (`agent_loop.py`): an agent searches PubMed, reads papers and submits a
  decision with citations; bioevidence checks each submission and returns its reasons, and the agent
  may revise. Five of six models cited only what they had read; Claude Haiku 4.5 misquoted in 8 of
  16 first submissions, the gate stopped all eight, and after feedback 4 were admitted. No answer
  with an invalid citation was admitted (0/73); 4 of 108 episodes went to a human.
- Benchmark scenario 2b: each citation carries its stance toward the claim and the agent may decide
  "conflicting". Stances become evidence lines, so disagreeing evidence sends a record to an expert
  (BEV004) whatever the agent decided; verified citations stay in the record through revisions.
  Wrong decisions admitted without review fell from 15 to 10 of 108, and 10 records went to an
  expert as conflicting, 8 of them on the five contested claims. The rest need the counter-evidence
  to be found: on FGFR3 G697C all six agents missed it.

- Benchmark scenario 1: the literature tasks asked as a user would ask a chatbot, without rules, source
  or tools. With only PMID and title, 32 of 49 model answers held an invented quote; with the claim
  only, 38 of 50 cited at least one invalid paper or quote (28 of 66 citations were real PMIDs of
  unrelated papers). Bioevidence admitted only the three answers whose citations all verified.
- Literature grounding verifies a quote against the pinned PubMed abstract when a paper has no open
  full text; `bioevidence ground` pins the abstract, and a record's source hash names it. The literature hallucination metric now counts
  invented quotes only; answers without a quote are reported separately.

- Add semantic checks (#31). A use may require independent review: an accepting non-human
  reviewer that created none of the evidence, whose absence, deferral or rejection sends the use
  to review (BEV021). `semantic.CueChecker` flags negated, hedged or non-human quotes (BEV022).
  In the benchmark pilot, a reviewer from another vendor exposed direction flips on clear text
  (59–63 of 63) but caught 1 of 5 natural misreadings, which sat on mixed evidence; cues flagged
  22 of 63 correct answers.
- Add an LLM benchmark (`evaluation/llm_benchmark`): six models (frontier and fast tiers of Claude, GPT
  and Gemini) answer ClinVar and literature tasks with and without the source, and each answer is
  scored alone and after bioevidence validation and grounding. Pilot sets only: with the source,
  models quoted faithfully (165/165 literature quotes); without it they almost always abstained, and
  grounding stopped the one reworded quote. The remaining errors were semantic (5/72 literature
  answers the wrong way round on 2 tasks, with verbatim quotes), which text grounding cannot catch.
- Add literature grounding (#20). `bioevidence ground` (network) resolves cited PMIDs, PMCIDs and
  DOIs with Europe PMC, Crossref or NCBI E-utilities and pins the resolver response and any
  open-access JATS full text; `LiteratureGrounder` (offline) checks identity, retraction, title
  and every quote against those bytes. New codes BEV019 (retracted source) and BEV020 (evidence a
  profile requires to be verified is not); profiles may list `verified_evidence_types`.
  Snapshot stores read gzip-compressed snapshots.
- Add the CIViC literature case (`examples/civic_literature`): open-access CIViC papers (CC BY or
  CC0) and retracted papers pinned from PMC, with the issue's AI-specific negative controls
  measured on real text.
- Add the AI validation roadmap (`docs/AI_VALIDATION_ROADMAP.md`, tracked in #26).
- Add an error taxonomy of 20 failure modes (`evaluation/error_taxonomy.yaml`, rendered to
  `docs/ERROR_TAXONOMY.md`): each with its expected catching layer and a status checked
  against the committed benchmark results.
- The ClinVar case commits `results/faults.jsonl`, its per-case controlled-fault and
  trust-boundary outcomes.
- Add source grounding (#19): optional grounders recompute from pinned source snapshots what a
  record only asserts, with new rule codes BEV014–BEV018. `SnapshotStore` and the generic
  `SourceBytesGrounder` live in `bioevidence_validator.grounding`; `bioevidence validate
  --snapshot-dir` recomputes source hashes from local files. Reports without grounders are
  unchanged.
- The VBO and ClinVar cases add domain grounders and a fourth method, full validator plus
  grounding. New trust-boundary controls: a real but wrong VBO target, an unpinned VBO source,
  and ClinVar records that omit dissent. Trust-boundary false admissions fall from 48/48 to
  0/48 (VBO) and 32/32 to 0/32 (ClinVar), with no change to any real-source decision.
- Error taxonomy statuses are now judged with grounding: no failure mode is left exposed.
- Add Python 3.14 to the supported package classifiers and Linux CI test matrix.
- Add admitted and rejected `dataset-label` draft examples, covered by draft and
  installed-wheel checks.

## 0.7.0 — Expert review, quality checks, community and documentation site

- Add `bioevidence review` (`check`, `agreement`, `adjudication-sheet`, `score`, `freeze`)
  implementing the gold-standard protocol: strict annotation checks, Krippendorff's α with
  bootstrap interval and Cohen's κ (both cross-checked against reference implementations),
  adjudication of disagreements, scoring on the test split with hash-bound joins, and frozen
  manifests. It never produces labels.
- Add a blinded ClinVar expert-review kit (`evaluation/clinvar_review/`): all 95 variants where
  the validator and NCBI disagree plus 95 stratum-matched controls, an Excel workbook with
  dropdowns, a reviewer rubric, a private key, and an importer into the protocol format.
- CI runs ruff and mypy, and enforces a 95% test-coverage minimum (currently 98%).
- Add CONTRIBUTING, CODE_OF_CONDUCT (Contributor Covenant 2.1), SECURITY, issue forms and a
  pull request template.
- Add `community/profiles/`: contributed domain profiles whose example cases are built,
  validated and checked against expected outcomes in CI; `_template/` to copy.
- Add a documentation site (MkDocs, strict link checking) published to GitHub Pages.
- The canine 0.3 implementation is also preserved at the `canine-0.3` tag.
- No change to validation decisions or report format; both benchmarks reproduce 0.6.0 exactly
  apart from `validator_version`.

## 0.6.0 — ClinVar case and standards alignment

- Add a second real-data case: ClinVar germline classifications. 5,026 sampled variants
  from the 2023-09 release are built from per-submission evidence and validated with a
  ClinVar-style profile; decisions are compared with NCBI's own 2023-09 review status and
  with each classification's 2026-09 outcome, plus controlled faults and a trust-boundary
  cohort. Frozen, hash-pinned sample; rebuild script verifies the three upstream files.
- Add `docs/STANDARDS.md`, mapping the record model to ECO, Biolink 4.4.4, GA4GH VA-Spec
  1.0.1 and PROV-O, with mapping strength and caveats.
- Annotate `ExtractionMethod` values with ECO meanings in the LinkML schema. The compiled
  JSON Schema, and therefore every report's `schema_sha256`, is unchanged.
- The VBO benchmark summary changes only `validator_version`.

## 0.5.0 — Drafts, LLM draft schema and GitHub Action

- Add compact YAML/JSON drafts: `bioevidence build` and `build_record()` derive identifiers,
  group evidence lines and hash named local files, without supplying scope, method, times
  or review decisions. Strict parsing rejects unknown, missing and out-of-choice fields.
- Add `bioevidence draft-schema` and `draft_json_schema()`: a per-profile JSON Schema for
  drafts, e.g. for LLM structured output.
- Add a composite GitHub Action that validates records or drafts in pull requests, with a
  job summary, file annotations and count outputs.
- Add a Colab quickstart notebook and draft examples.
- Export `build_record`, `load_draft`, `draft_json_schema` and `validate_record` from the package root.

## 0.4.1 — Required-evidence quality and real-source evaluation

- Apply extraction-method quality gates to each required evidence type independently.
- Prevent unrelated manual/parser evidence from admitting an LLM-only required result.
- Add an attributed, frozen VBO canine name-mapping case and source rebuild script.
- Evaluate 72 real-source names, 160 controlled faults, and 16 explicit trust-boundary cases separately.
- Preserve generic main and the legacy canine-breed branch.
- Publish to PyPI from version tags; add package metadata and citation file.
- Reject CLI input nested deeper than 100 levels (exit 3) on every platform and Python version.

## 0.4.0 — Domain-neutral main

- Preserve canine 0.3 functionality on the `canine-breed` branch.
- Replace canine defaults with a generic entity/relation/evidence schema and strict YAML profiles.
- Add general, literature-claim, dataset-label, and custom assay examples.
- Bind human adjudications to statements and uses; enforce evidence scope and reference integrity.
- Replace `--policy` with `--profile`; add profile discovery and generic audit fields.
- Remove the canine SQLite command from main. See `docs/MIGRATION-0.4.md` for breaking changes.

## 0.3.0 — Evidence and snapshot contract hardening

- Require resolved supporting evidence, selected-candidate consistency and
  compatible claim predicates; block relationship claims from sample/frequency label use.
- Enforce scope exclusions from concept scope, use only supporting scope evidence,
  reject blank provenance and unresolved references in unused evidence.
- Reject incomplete/duplicate/unknown policy configuration; custom schemas cannot
  relax the packaged structural baseline. Snapshot validation context per batch.
- Reject duplicate database IDs, WAL/SHM/journal sidecars, malformed manifests
  and unrecognized boolean evidence. Include resolution-row provenance,
  limits/accounting and batch hashes; publish the completion summary last.
- Preserve earlier policy files, synthetic examples and operational CLI exit codes.

## 0.2.0 — Evidence admission contracts and reproducible CLI

- Version schema/policy 0.2; preserve policy 0.1 and record generated-schema hashes.
- Prevent withdrawn statements or conflicting human judgments from silently being admitted.
- Reject missing, empty, malformed, duplicated or unknown requested uses.
- Make structural and identity errors block the entire record, including unknown uses.
- Require evidence collections and reject duplicate IDs before dictionary lookup.
- Return structured operational CLI errors; parse UTF-8 strictly and write reports atomically.
- Add regression tests, a Linux/Windows CI workflow and an installed-wheel smoke check.
- Include the Apache-2.0 license already declared in project metadata.
