# Drafts: write a claim in a few lines

A full evidence record spells out identifiers, evidence lines and hashes. A **draft** is a
compact YAML or JSON form of the same claim. `bioevidence build` (or `build_record` in
Python) expands it into a full record, which is then validated as usual.

```bash
bioevidence build examples/drafts/llm_claim.yaml --output record.json
bioevidence validate record.json --profile literature-claim
```

## What building does, and what it does not

Building only removes repetition. It:

- derives identifiers from the record `id` (or, when omitted, from a hash of the draft content);
- groups evidence items into one evidence line per `direction`;
- computes SHA-256 hashes of local source files named in `file`.

It never supplies facts you did not state. Scope, extraction method, retrieval time, source
version and reviewer decisions must be written explicitly, because each one can change an
admission decision. Unknown fields, missing fields, blank values, repeated list entries and
values outside the allowed choices are errors, not warnings.

## Format

```yaml
id: lab:claim-7                 # optional record id
profile: literature-claim       # must match the profile used for validation
uses: [research_summary, knowledge_base]
status: proposed                # optional: proposed (default), accepted, rejected, superseded

statement:
  subject: {id: "HGNC:1100", label: BRCA1, type: gene}
  predicate: associated_with
  object: {id: "MONDO:0007254", label: breast cancer, type: disease}
  scope: ["taxon:9606"]

sources:
  - id: paper                   # local name, referenced by evidence[].source
    title: Example paper
    type: publication           # ontology_snapshot, registry_snapshot, dataset_snapshot,
                                # publication, web_page, local_file
    uri: https://doi.org/10.0000/example   # optional
    version: "2024-05"
    retrieved_at: "2026-09-21T00:00:00Z"
    file: sources/paper.pdf     # hashed at build time, relative to the draft
    # sha256: <64 hex>          # frozen hash; see below

evidence:
  - source: paper
    locator: Table 2
    text: BRCA1 variants were associated with ...   # optional
    type: publication_result
    method: llm_extraction      # deterministic_parser, manual_curation,
                                # normalized_string_match, llm_extraction
    scope: ["taxon:9606"]
    direction: supports         # optional: supports (default), contradicts, neutral

reviews:                        # optional
  - reviewer: {id: "orcid:0000-0000-0000-0000", name: A. Curator, type: human}
    decision: accept            # accept, reject, defer
    uses: [knowledge_base]
    rationale: Checked Table 2 against the source.
    decided_at: "2026-09-22T00:00:00Z"
```

Quote identifiers containing `:`, versions and timestamps so YAML keeps them as strings.
Unquoted timestamps are converted to ISO 8601 strings.

## Source hashes

| You provide | Record gets | Meaning |
|---|---|---|
| `file` | `sha256` = hash of the file | The file you have is the reference snapshot. |
| `sha256` | `sha256` as stated | A frozen reference hash, e.g. from a registry or manifest. |
| both | `sha256` as stated, `observed_sha256` = hash of the file | Validation rejects the record (`BEV002`) if the file changed. |

Hashes identify bytes; they do not prove that a source is authentic or that the file is the
one a URI points to.

## Drafts from an LLM

`bioevidence draft-schema --profile literature-claim` prints a JSON Schema for drafts under
that profile: its allowed predicates, entity types and uses become enums. Use it for
structured output, then let your pipeline, not the model, set `method` and any `reviews`:
a model should not declare how its own output was produced or that a human accepted it.

```python
from bioevidence_validator import build_record, draft_json_schema, validate_record

schema = draft_json_schema("literature-claim")      # give this to your model
draft = ...                                         # the model's structured output
for item in draft["evidence"]:
    item["method"] = "llm_extraction"               # set by your pipeline
report = validate_record(build_record(draft, base_dir="."), profile="literature-claim")
```

The schema guides authoring only. `build_record` and validation remain authoritative.
