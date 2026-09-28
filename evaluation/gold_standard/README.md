# Gold-standard preparation templates

Status: **draft**. Human-reviewed cases: **0**. No independent gold-standard metrics
are available. These are blank preparation templates, not a completed dataset.
Follow the [protocol](../../docs/GOLD_STANDARD.md).

Copy the templates to a working directory before annotating. Leave source-derived
expected statuses and validator predictions out of reviewer packets. Store each
reviewer's work separately until independent annotation is complete.

`annotations.template.csv` has one row per case-use-reviewer. `annotation_id` is unique;
`record_sha256` binds the frozen record; `profile_sha256` and `requested_use` bind the
task; `group_id` controls concept-level splitting. `mapping_label` and
`admission_label` use the labels in the protocol. Provide a reason for each label and
source URLs/locators in `evidence_refs_json` (a JSON array inside the CSV cell).
`reviewer_id` is a stable identifier; `reviewer_qualification` describes relevant
experience. `annotated_at` is an ISO 8601 timestamp.

`adjudications.template.csv` links the original `annotation_ids_json` (a JSON array)
to the final labels, adjudicator, time and reasons. It never replaces original reviews.
Record unresolved uncertainty explicitly. Both files currently contain headers only.

`manifest.template.json` contains unfilled source/profile/group/file metadata and
zero reviewed cases. An editor changing its status does not complete human review.

`bioevidence review` works on these formats. It never produces labels; people do:

| Command | Does |
|---|---|
| `bioevidence review check annotations.csv [--adjudications adjudications.csv]` | Strict format check: labels, hashes, timestamps, duplicates, and that all reviewers of a case saw the same record |
| `bioevidence review agreement annotations.csv` | Krippendorff's α with a bootstrap 95% interval, Cohen's κ (two reviewers) and raw agreement, per use |
| `bioevidence review adjudication-sheet annotations.csv --output adjudications.csv` | Blank rows for every disagreement; never overwrites an existing file |
| `bioevidence review score --annotations … --adjudications … --predictions …` | Resolves final labels and scores predictions on the test split; rejects missing or hash-mismatched rows |
| `bioevidence review freeze --manifest … --annotations … --adjudications …` | Refuses unresolved cases; records counts, reference type and file hashes |

A worked, domain-specific kit is in [`../clinvar_review/`](../clinvar_review/README.md).
The VBO replay command still evaluates only its source-derived reference set and controlled faults.
