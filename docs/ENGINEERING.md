# Engineering contract — 0.7.0

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

A human acceptance does not erase contradictions, missing evidence, source mismatches,
or other human rejection/deferral. Low-strength extraction permissions are explicit
profile choices; they cannot disable structural or integrity checks.

## Audit and trust

Reports contain canonical input SHA-256; exact profile-byte SHA-256 and version;
compiled schema SHA-256 and versions/roles for baseline and extensions; validator
version; UTC validation time; findings; and per-use reason codes. The timestamp changes
between runs. Hashes identify inputs/configuration; they do not sign records or prove
that a source, source hash, label, or reviewer identity is authentic.

ECO annotations are opt-in. `validate_record(..., annotate_eco=True)` and
`bioevidence validate --annotate-eco` add `evidence_eco_annotations` to the report,
derived from the packaged LinkML `ExtractionMethod` meanings. Without the option, the
report shape is unchanged.

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
```

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
