# Engineering contract — 0.8.0

## Validation stages

1. Parse one JSON record. The CLI rejects duplicate keys, nonfinite numbers, malformed
   UTF-8/JSON, and nesting deeper than 100 levels as operational errors.
2. Validate against the packaged LinkML core compiled to JSON Schema, plus any
   explicitly selected extension. Structural failures stop semantic evaluation.
3. Check profile binding, supported/distinct uses, IDs and references, and review targets.
   Integrity failures stop profile evaluation and reject all requested uses.
4. Apply fixed evidence checks and the selected profile's declarative use contracts.
   If grounders are given, compare the record with its pinned sources ([source grounding](#source-grounding)).
5. Return findings and a decision for each use. Any rejection makes the overall status
   rejected; otherwise any review requirement makes it review_required.

Unsupported uses, absent/empty required lists, broken references (including unused
evidence items), and duplicate source/item/line/adjudication IDs cannot be admitted.

## Rules

| Code | Condition | Result |
|---|---|---|
| SCHEMA | Structural/type/date/required-field violation | Reject all uses |
| RECORD_INTEGRITY | Profile/use/ID/reference/review-target mismatch | Reject all uses |
| BEV001 | Rejected or superseded statement | Reject |
| BEV002 | Supplied observed and frozen source hashes differ | Reject |
| BEV003 | Entity type or predicate outside profile allowlist | Reject |
| BEV004 | Contradicting evidence line | Review |
| BEV005 | Supporting evidence and statement scopes differ | Reject |
| BEV006 | No resolved scope-matched support | Review |
| BEV007 | Required supporting evidence type absent | Reject affected use |
| BEV008 | LLM-only support within a required evidence type without profile permission | Review affected use |
| BEV009 | String-match-only support within a required evidence type without profile permission | Review affected use |
| BEV010 | Required human acceptance absent for this use | Reject affected use |
| BEV011 | Human rejection present for this use | Reject affected use |
| BEV012 | Human deferral present for this use | Review affected use |
| BEV013 | Only LLM and string-match support mixed within a required type, without both permissions | Review affected use |
| BEV014 | Grounding: snapshot bytes do not hash to the record's frozen hash | Reject |
| BEV015 | Grounding: the source cannot confirm it (bytes unavailable, or an item type the grounder cannot recompute) | Review |
| BEV016 | Grounding: a cited identifier does not exist in the source | Reject |
| BEV017 | Grounding: the record disagrees with what the source says | Reject |
| BEV018 | Grounding: the source holds evidence the record leaves out | Review |
| BEV019 | Grounding: the cited source is retracted | Reject |
| BEV020 | A required type the profile lists under `verified_evidence_types` has no item a grounder verified | Review affected use |
| BEV021 | The use requires independent review, and no independent non-human reviewer accepted it (or one deferred or rejected) | Review affected use |
| BEV022 | Semantic cue: a quote supporting a positive claim is negated, hedged (optional), or only about animals or cells for a human-scoped item | Review |
| BEV023 | Grounding: a cited identifier is obsolete, withdrawn, or not its current name (a previous gene symbol or alias) | Reject |
| BEV024 | Grounding: a cited identifier is malformed, or of the wrong kind for its place (e.g. not a cell type) | Reject |
| BEV025 | Cross-check: a pinned reference resource contradicts the claim or its supporting evidence | Review |
| BEV026 | Definition check: measurements contradict a marker the ontology defines the claimed term to have or lack | Review |

A human acceptance does not erase contradictions, missing evidence, source mismatches,
or other human rejection/deferral. Low-strength extraction permissions are explicit
profile choices; they cannot disable structural or integrity checks.

## Audit and trust

Reports contain canonical input SHA-256; exact profile-byte SHA-256 and version;
compiled schema SHA-256 and versions/roles for baseline and extensions; validator
version; UTC validation time; findings; and per-use reason codes. The timestamp changes
between runs. Hashes identify inputs/configuration; they do not sign records or prove
that a source, source hash, label, or reviewer identity is authentic.

Source artifacts require a declared version, retrieval time, and frozen hash. The optional
observed hash is compared to that hash. Validation never retrieves source bytes; without
grounders it does not calculate their hashes either. Only `build` hashes local files explicitly named in a draft; it
does not fetch URIs. A profile can require a declared `independent_cohort_review`
evidence item, but the engine cannot establish independence or evaluation validity.

Report writes use a temporary file and atomic replacement. Input, selected profile,
selected schema, and baseline schema paths cannot be the report destination. Operational
failures leave no completed new report and preserve an existing report if replacement fails.
CLI configuration is trusted, including schema import paths.

## Source grounding

The rules above judge what a record says about its evidence; they cannot tell whether it is
true. Grounding moves that trust boundary toward the source. A grounder takes the exact
source bytes a record names, recomputes what the record claims, and reports disagreements
as BEV014–BEV019 findings. It is optional, offline and deterministic. Grounders run only on
records that passed the schema and integrity checks, and add findings to the same per-use
decisions. Reports gain a `grounding` key listing the grounders used; without grounders,
reports keep their exact previous shape.

- `SnapshotStore` holds local source bytes keyed by frozen SHA-256 and re-hashes them when
  loaded, so a file is never trusted by its name. `SnapshotStore.from_directory` reads files
  named `<sha256>` or `<sha256>.<ext>`.
- `SourceBytesGrounder` is generic: it recomputes every source artifact's hash from the store
  instead of trusting `observed_sha256` (BEV014, or BEV015 when the bytes are missing).
- Domain grounders know one source format and live with their importers, outside the
  engine: `VboGrounder` (term existence, name match, candidate resolution) and
  `ClinVarGrounder` (submissions, review tiers, derived aggregates, directions, completeness).
  A grounder returns no findings for records that do not cite its source.
- `LiteratureGrounder` is generic for publications (`source_type: publication` with a
  `pmid:`, `pmcid:` or `doi:` URI). It reads what the network step `bioevidence ground` pinned:
  the resolver's response and, for open-access papers, the PMC JATS full text. From those bytes
  it recomputes whether the identifier exists (BEV016), whether the paper is retracted
  (BEV019), whether the record's title and hash belong to that paper (BEV017), and whether each
  quote (`extracted_text`) appears in the full text, at its paragraph when the locator ends in
  `#<paragraph id>` (BEV017). Matching is by substring after normalising Unicode, quote marks,
  dashes and spacing; a quote may leave out a trailing parenthetical reference, nothing else. A paper without open full text, or a quote under five words,
  cannot be verified (BEV015): it is sent to review, never admitted silently.

A profile use can list `verified_evidence_types` (a subset of its required types). Such a type
counts only through items a grounder verified (`verified_items`); otherwise the use gets BEV020
and goes to review, including when validation runs without grounders. Built-in profiles list
none, so their decisions do not change.

```bash
bioevidence ground record.json --snapshot-dir snapshots/ --output pinned.json   # network: resolve and pin
bioevidence validate pinned.json --snapshot-dir snapshots/                      # offline
```

`ground` uses Europe PMC (with Crossref for DOIs it does not know) or, with `--resolver ncbi`,
NCBI E-utilities. It writes content-addressed snapshots and `snapshots/literature.json`, and
pins the record's source hash to them. Snapshots may be stored gzip-compressed
(`<sha256>.xml.gz`); the name is the hash of the uncompressed bytes.

```python
from bioevidence_validator.engine import RecordValidator
from bioevidence_validator.grounding import SnapshotStore, SourceBytesGrounder

store = SnapshotStore.from_directory(Path("snapshots"))
validator = RecordValidator(profile="general", grounders=[SourceBytesGrounder(store)])
```

With `--snapshot-dir`, the CLI runs the byte check, and the literature grounder when the
directory holds a `literature.json`. Grounding checks a record against the source it cites;
it cannot tell whether that source is itself right, whether a verbatim quote really supports
the claim (a correctly quoted sentence read with the wrong polarity passes), or anything about
sources without a pinned snapshot and a grounder.

### Identifiers, tables and reference resources

These grounders are generic: they check what a record cites against a pinned release of a reference,
whatever the domain. Their messages say what to fix, so a model can act on them (see the feedback loop
below). Each grounder's name carries the release it used, and so does the report's `grounding` key.

Identifiers are read from the statement's subject and object (`id`, `label`, `entity_type`), its scope
tokens, and evidence locators written as `key=value` pairs separated by `;` (`cluster=3;gene=CD8A`).

- `OntologyGrounder` (`identifiers`) checks terms against pinned OBO releases (Cell Ontology, HPO,
  MONDO, UBERON …):
  - the term exists (BEV016);
  - it is not obsolete (BEV023, naming its replacement);
  - its label is the term's name or an exact synonym, ignoring case, punctuation and a plain plural (BEV017, naming the
    term that label belongs to);
  - it is of the right kind: `roots` maps an entity type or locator key to the terms it must descend
    from, so a `cell_type` must be under CL:0000000 (BEV024).
- `GeneGrounder` checks human gene symbols and HGNC identifiers against a pinned HGNC complete set:
  - an unknown symbol is BEV016;
  - a previous symbol, an alias or a wrong case is BEV023, naming the approved symbol;
  - a record scoped to another species is not checked (BEV015).
- `VariantGrounder` checks HGVS descriptions on RefSeq sequences against pinned NCBI assembly reports:
  - the description must be well formed and versioned (BEV024);
  - a chromosome accession must be a real sequence (BEV016), on the genome build of the record's scope
    (`GRCh38`, `GRCh37`, `hg19`, `hg38`; BEV017), with the position inside the chromosome (BEV016);
  - variants on more than one build in one record are BEV017.
- `TableGrounder` (`tables`) is the data counterpart of the quote check.
  - An evidence item of a configured type names one row of a pinned table (TSV or CSV) by its key
    columns in the locator, and may claim values from it in `extracted_text` (`logfc=2.4; pct_in=0.91`).
  - A missing row is BEV016, naming the closest key values. Several matching rows are BEV015.
  - A claimed value that differs from the table is BEV017; a number matches at the precision it is
    written with.
  - An item whose row exists and whose values match counts as verified.
- `ReferenceGrounder` (`crosscheck`) compares a record with a pinned reference resource it does not cite,
  a table of curated `subject`, `predicate`, `object` assertions. A disagreement sends the record to review
  (BEV025) and never rejects it: references are partial and can be out of date, and their silence is not
  support. It raises BEV025 in two cases:
  - the reference asserts the opposite predicate for the statement's subject and object;
  - supporting evidence names an entity (e.g. `gene=CD19`) that the reference relates (e.g. `marker_of`)
    only to objects that conflict with the statement's object. By default a different term conflicts unless
    the ontology makes it an ancestor or descendant. With `conflict="disjoint"`, only terms the ontology
    declares disjoint conflict (`disjoint_from` on them or their ancestors, e.g. T cell and B cell), so a
    marker the reference lists for a sibling type is not reported. That needs an ontology release that keeps
    its disjointness axioms: the Cell Ontology's full `cl.obo` does, `cl-basic.obo` does not.

```bash
bioevidence validate record.json --ontology cl-basic.obo --term-root cell_type=CL:0000000     --genes hgnc_complete_set.txt --assembly-report GRCh38_assembly_report.txt
```

`TableGrounder` and `ReferenceGrounder` need their configuration (evidence types, keys, relation) and are
used from Python.

### Ontology definitions as checks

Many Cell Ontology terms are defined by marker proteins. A CD8-positive, alpha-beta T cell `has plasma membrane
part` the CD8 co-receptor and `lacks plasma membrane part` CD4; a natural killer cell lacks CD3 epsilon. These
axioms belong to a pinned release, not to a judgment about one dataset, so they can be checked against
measurements without knowing the right answer.

- `MarkerDefinitions` (`definitions`) collects each term's presence and absence axioms, its own and inherited
  through `is_a`. It maps each protein to HGNC genes:
  - by its PRO short label or gene-based synonym;
  - as a family (`Fcgr3` is FCGR3A and FCGR3B);
  - through the components of a complex (the CD8 co-receptor is CD8A and CD8B);
  - or through the protein a modified form belongs to.
- It leaves some axioms out:
  - isoform-specific markers (CD45RA), which gene-level counts cannot see;
  - axioms about relative amounts, which compare with another cell type rather than with the rest of a
    dataset.

  It needs the full `cl.obo`, which keeps the logical definitions.
- `DefinitionGrounder` compares the claimed term with `measure(record)`, which gives each gene's detection rate
  and log fold change for the record's subject. It raises BEV026 in two cases:
  - **presence:** every gene of a defining protein is detected in fewer than 10% of the cells;
  - **absence:** a gene of an excluded protein is detected in at least half of them and more than elsewhere.

  The thresholds were set on the single-cell case's first six datasets, before it was run on six others.

BEV026 sends a record to review and does not reject it, because a transcript is not a protein and some
definitions are written for one species. In the feedback loop it goes back to the proposer together with the
measurement. The proposer cannot make the finding go away by leaving evidence out, because the check reads the
data, not the evidence the proposer cites. The check is **experimental**.

**It did not transfer to new data.** On the single-cell case's external split, the thresholds set on the
first six datasets flagged wrong annotations no better than chance (47% against 42%). The cause was definitions
that do not hold for transcripts:
- mast cells defined by CCR3, and neutrophils by CEACAM8, whose transcripts are not detected;
- NK cells defined as lacking CD3 epsilon, although their CD3E transcripts are.

Fed back to models, these findings turned correct answers into wrong ones (see the benchmark README). Use it
on transcript data only with markers validated at the mRNA level, since the loop passes its findings to the
proposer as they are.

### The feedback loop

`feedback.revise(propose, validator)` runs the loop around any proposer: a model call, an agent or a person.

1. The proposer returns a record, and bioevidence validates it.
2. Every finding the proposer can fix goes back as a reason that points at the part of the record
   concerned ("evidence 2 (cluster=3;gene=CD8B): No row of the pinned table has cluster=3, gene=CD8B.
   Closest gene values for cluster=3: CD8A.").
3. The proposer may then revise, up to a set number of rounds.

Two kinds of finding are not fed back. The record goes to a person as it is:

- **Judgment:** its own evidence disagrees (BEV004), a reference contradicts it (BEV025), a semantic cue
  flags it (BEV022), or it lacks an independent review (BEV021).
- **Policy:** the use needs a human decision whatever the proposer does (BEV008–BEV013).

Evidence verified in one attempt is carried into the next while the claim stays the same, so a revision can fix or replace what failed
but cannot withdraw verified evidence against its answer. The literature benchmark's agent loop
(`evaluation/llm_benchmark/agent_loop.py`) showed why: before that rule, an agent whose record held a
misquote and a verified quote against its decision dropped the latter and was admitted.

## Semantic checks

Grounding proves that a quote is real; it cannot tell whether the quote supports the claim.
Two optional layers look at that, and both can only send a record to a human:

- `CueChecker` (`bioevidence_validator.semantic`) is deterministic and cheap. It raises BEV022 when a
  quote supporting a positive claim contains a negation, when a quote is hedged (if asked), or when
  an item scoped to humans quotes only animal or in-vitro evidence. It does not understand text:
  it misses misreadings without such words and flags some correct quotes.
- An independent reviewer (another model, an agent, a second pipeline) reads the quotes without the
  extractor's conclusion and records its reading as a non-human adjudication. Under
  `require_independent_review` the use needs that reviewer's acceptance, and the reviewer must not
  have created any of the evidence (BEV021).

Their measured effect is in the [LLM benchmark](../evaluation/llm_benchmark/README.md).

`validate`: 0 admitted, 1 rejected, 2 review_required, 3 input/configuration/execution error.
Argparse usage errors also exit 2, with usage text rather than a validation report.
`profiles` prints all built-in contracts; `generate-schema --output schema.json`
exports the compiled core schema. Custom schema export exports that selected schema;
validation still applies the baseline independently.

`build draft.yaml [--output record.json]` expands a [draft](DRAFTS.md) into a full record:
it derives identifiers, groups evidence lines by direction and hashes named local files,
but never supplies scope, extraction method, retrieval time, versions or review decisions.
Unknown, missing, blank, repeated or out-of-choice draft fields exit 3. The output cannot
overwrite the draft. `draft-schema --profile NAME` prints a JSON Schema for drafts in which
the profile's allowlists are enums; it guides authoring and never replaces validation.

The repository's composite GitHub Action (`action.yml`) installs the package from the
action's own revision and runs `build`/`validate` through the CLI for each matched file.
It fails on rejected or unreadable files, and on review-required files unless
`fail-on: rejected` is set.

`review` implements the [gold-standard protocol](GOLD_STANDARD.md) on its CSV formats and is
separate from validation: reference labels evaluate decisions and never become admission
rules. `check` rejects blank fields, unknown columns or labels, malformed hashes, times and
JSON, duplicate annotation IDs, a reviewer labelling a case-use twice, and reviewers of one
case-use bound to different records, profiles, groups or splits. `agreement` reports
Krippendorff's nominal α (bootstrap 95% interval, fixed seed) and, for two reviewers, Cohen's κ.
`adjudication-sheet` lists disagreements and refuses to overwrite an existing file. `score`
requires every disagreement to be adjudicated, joins predictions on case, use and record and
profile hashes, rejects mismatches or missing predictions, and scores one split (default
`test`). `freeze` refuses unresolved labels and records counts, reference type and file hashes;
hashes identify files but do not prove that review took place. All exit 3 on invalid input.

## Reproduction

```bash
uv sync --frozen --extra dev
uv run --frozen pytest
uv build
uv run --isolated --no-project --with ./dist/*.whl python tools/check_distribution.py
uv run --frozen --with matplotlib==3.11.2 python tools/reproduce.py   # every benchmark result and figure
```

`tools/reproduce.py` regenerates every committed benchmark table, summary and figure offline from what is
committed, and compares each with the repository: text with line endings normalised, everything else byte for
byte. What it replays from:
- for the real-data cases, the hash-checked source snapshots;
- for the LLM benchmark, the recorded model answers, agent episodes and paper verifications;
- for the figures, the summaries, with matplotlib pinned.

CI runs it on every change, and a test fails if a results directory or figure is not covered by one of its steps.

CI runs on Linux/Python 3.11–3.14 and Windows/Python 3.13, and runs the GitHub Action on
Linux and Windows. Tests cover multi-domain acceptance, negative evidence cases,
use-specific human review, strict configuration/JSON/draft parsing, baseline enforcement,
context snapshots, audit digests, and CLI report behavior. The wheel smoke test imports
outside editable source, checks packaged profiles/schema, and exercises accepted, rejected,
review-required, custom-domain and draft-built records. It does not assess
biological correctness, model calibration, or predictive performance.

The [VBO case](../examples/vbo_canine/README.md) adds offline source verification and a
separate real-source/controlled-fault evaluation. The
[ClinVar case](../examples/clinvar_germline/README.md) adds policy reproduction against
an independent implementation (NCBI's review status) and a three-year outcome comparison.
Each also reports a trust-boundary cohort that the rules alone admit and grounding catches
(80/80 admitted without grounding, 0/80 with it), and checks that grounding changes no
real-source decision.
Both replay byte-identically from frozen, hash-checked sources, and CI compares each run
with the committed results. [Standards alignment](STANDARDS.md) maps the record model to
ECO, Biolink and GA4GH VA-Spec.
