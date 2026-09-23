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
There is no automated annotation, freeze or gold-scoring command in this release.
The existing VBO replay command still evaluates only the published source-derived
reference set and controlled faults.
