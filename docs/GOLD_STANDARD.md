# Gold-standard workflow

## Applying the workflow to a project

The README shows the full workflow for a project-specific reference standard.
The protocol and templates are reusable across domains; each project supplies its own
human reviewers, reference labels, sources and review status. The bundled VBO reference
set is source-derived and has no independent human gold-standard labels. This package
currently provides validator outputs, but no dedicated gold-standard scoring command.
Its expected statuses must not be copied into these human annotation templates.

The gold standard is an offline evaluation reference. It does not become another
runtime admission rule, automatically approve a record, or overwrite evidence findings.
The existing record-level human adjudications and these independent evaluation labels
have different purposes and must be stored separately.

## Workflow states

| State | Required work | Output |
|---|---|---|
| `draft` | Define the task, intended uses, annotation guidance, source versions, sampling and concept groups | Protocol and unlabeled candidate inventory |
| `in_review` | Collect independent human judgments without validator outputs or source-derived expected statuses | Separate reviewer annotation rows |
| `adjudicated` | Resolve disagreements with recorded reasons; preserve genuine uncertainty | Adjudication rows linked to original reviews |
| `frozen` | Check completeness and leakage, record hashes, versions and reviewer roles | Immutable reference release suitable for held-out scoring |

These are dataset workflow states, separate from the engine's
`admission_status`. The templates document the process; no CLI currently enforces
state transitions or authenticates reviewers. A `frozen` label in a file alone is
not proof that the required review occurred.

## Construct the reference set

Start with a 50–100 case pilot covering straightforward mappings, ambiguous names,
regional or population-specific concepts, conflicts, and source/target mismatches.
Record the selection method and stratum counts. Keep naturally occurring cases separate
from injected faults. This pilot size is a practical starting point, not a claim of
statistical representativeness.

For the canine case, consult the original source assertions and concept scope, and
use independent registry evidence where available. A name with multiple VBO candidates
is not automatically an incorrect mapping. A single candidate is not automatically
sufficient evidence for every use. Reviewers must assess the stated task and evidence.

The 72 published VBO cases are already visible and used in development. They can
support rubric development and annotation practice; they must not be presented as an
untouched held-out test set. Select new test cases after defining the protocol. Group
all aliases of the same concept together; ambiguous names link their candidate concepts
into the same split group. Keep a group entirely in development or test, including
its derived perturbations, to prevent leakage.

## Annotate two separate questions

| Field | Labels | Meaning |
|---|---|---|
| `mapping_label` | `correct`, `incorrect`, `uncertain` | Does this particular source name/assertion refer to the proposed target concept in the stated scope? |
| `admission_label` | `admitted`, `rejected`, `review_required` | Is the supplied evidence sufficient for this specified use under the written rubric? |

A correct mapping may still lack evidence for training use. Uncertainty must not be
forced into an incorrect label. An `uncertain` mapping is not automatically equivalent
to `review_required` admission: each question must receive its own rationale.

Each case-use pair needs the same frozen record and source material for all reviewers.
Reviewers may see the proposed target and original source evidence, but not validator
predictions, reason codes, or the current benchmark's expected status. Use a written,
versioned domain rubric rather than explaining the engine's implementation to reviewers.
An AI assistant may prepare evidence packets, but AI-generated labels are not independent
human annotations.

Prefer two reviewers with relevant domain knowledge. Store reviewer IDs and relevant
qualifications, timestamps, evidence citations, and separate reasoning for each label.
Retain both original reviews. An adjudicator records a resolution and its basis when
reviewers disagree; uncertainty may remain unresolved. With only one human reviewer,
label the release a **single-reviewer reference set** and disclose that limitation.

## Templates and freeze checklist

Use the [template directory](../evaluation/gold_standard/README.md):

- `annotations.template.csv`: one row per case-use-reviewer; no prefilled answers.
- `adjudications.template.csv`: one resolved case-use row linked to original annotations.
- `manifest.template.json`: draft status, protocol/source/profile identities and future file hashes.

Before freezing, verify that every test case-use pair has the required independent
reviews and documented resolution, or a clearly retained uncertain status. Record the
identity of the label release, protocol version, data source snapshots, canonical input
hashes, profile versions/hashes, reviewer count, split groups, exclusions and file hashes.
Archive original annotations alongside adjudications. Reviewer identity and provenance
must be checked by the dataset maintainer; hashes alone do not establish authenticity.

Use the engine's canonical input convention when preparing `record_sha256`:
SHA-256 over UTF-8 JSON produced with sorted keys, compact separators, and finite numbers.
Bind each row to a `requested_use` and profile hash so labels are not silently reused for
a different task. Do not publish personal reviewer details without their authorization;
stable reviewer IDs and documented roles can identify reviews in the public release.

## Evaluation after human review

For project-specific scoring, join frozen labels and validator outputs on case ID,
canonical input hash, profile hash, and requested use. Reject missing, duplicate,
or mismatched rows. Report performance against human admission labels separately from
mapping correctness and from the existing source-derived/controlled-fault benchmark.
Do not tune profiles on the frozen test set. Freeze the validator/profile being evaluated;
subsequent development requires a separately reported evaluation version.

Report false admissions, false blocks, review-required rates and the full three-way
admission confusion matrix, with counts and denominators. Show coverage and uncertainty
rather than discarding difficult cases silently. Report reviewer agreement before
adjudication. Any statistical intervals should respect concept-level dependence; do not
treat multiple aliases or mutations of one concept as independent samples.

An improvement against this reference can support a claim about the defined curation
task. It does not establish breed-genotype membership, universal biological truth, or
clinical validity.
