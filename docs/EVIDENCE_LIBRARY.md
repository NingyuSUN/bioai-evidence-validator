# EvidPort evidence library integration

[EvidPort](https://github.com/NingyuSUN/evidport) is the independent evidence layer.
Its existing distribution name `local-evidence-database`, Python module
`evidence_database`, and `evidence-db` command remain compatible.

The optional `--evidence-library` grounder reads an existing independent
`local-evidence-database` store. It does not download, ingest, convert, or approve
papers. Existing `ground`, profiles, schemas, and frozen benchmark replays
retain their previous behavior. This public integration adds only the
independent `--evidence-library` option.

## Install and validate

From this Validator checkout, install both reviewed packages into the activated
environment, or install their built wheels. The independent library is not assumed
to exist on PyPI. Use the configured store folder when validating; `evidence` below
is a project-relative example:

```sh
python -m pip install -e .
python -m pip install 'local-evidence-database[pdf] @ git+https://github.com/NingyuSUN/evidport.git@e89d5d71741bb183323b7c0e32ddd7434e2c44c5'
bioevidence validate record.json --profile literature-claim \
  --evidence-library evidence --output validation.json
```

Use the independent library's PDF extra when working with PDF review packets.
The library must support `Store(root, read_only=True)`. A missing package, old
package, absent store, or unusable store produces an operational error; the
validator never silently disables this requested check. Validation output must
be outside the library directory.

## Accepting machine-verified quotations

By default a quotation passes only after a recorded human original-page review. Add
`--accept-independent-reading` to also accept a quotation that the library reports as
confirmed by an independent OCR reading of the same page region:

```sh
bioevidence validate record.json --profile literature-claim \
  --evidence-library /path/to/project/store --accept-independent-reading
```

The validator recomputes this from the read-only library; it does not take a server's word.
Each check in the report carries `admission_route` (`human_review` or
`independent_reading`), and `evidence_library.independent_reading_accepted` records that the
option was on. A recorded rejection or revocation still blocks the quotation. A library that
predates the route is an operational error, not a silent fallback. Through the MCP bridge
(`--accept-independent-reading` on `bioevidence_validator.evidence_mcp`) the server's project
must enable the same route; a disagreement between server and local library blocks admission.
Without the option, a quotation that the server admits by independent reading is not a
disagreement: it stays `review_required` (BEV015), and its check carries
`server_route_not_accepted: independent_reading`. Any other admission the local library cannot
confirm is still rejected.
Machine verification settles transcription only and is never reported as human review.

## Record contract

- `source_artifacts[].sha256` is the exact original PDF hash, not a parsed text
  hash. Set `uri` to the publication's DOI, PMID, or PMCID URI, and `title` to its
  pinned title. Metadata-only acquisition candidates have no full-text citation.
- `evidence_items[].locator` is the complete library citation, for example
  `evidence:cv_<64 hexadecimal characters>#b000001`. Copy it from library output;
  do not substitute a page number, filename, DOI, or legacy database citation.
- `extracted_text` contains the actual quotation from that block. The library
  checks numeric boundaries and does not treat related text elsewhere as a match.
- Publication identity must have a source-bound acquisition receipt with the
  original-file identity check, under rule version 2 or 3, and matching frozen
  provider metadata. A check made under any other rule version is not accepted.
  Older imports without these receipts remain `review_required`; filenames and
  document IDs alone are insufficient. Parent-paper DOIs do not identify
  supplementary files. Contradictory identifiers/titles and pinned retractions
  block admission, including when another grounder accepts the evidence item.
- The exact conversion, block, and quotation require a human original-page
  review in the independent library. AI diagnostics, text matches, inspection
  mode, or approval of another quotation/version cannot supply this review.
  Revocations are honored on the next validation. Human identity remains locally
  self-declared; this is not an authenticated review service.

The adapter calls `Store.check(..., require_review=True)` unconditionally.
Failures emit findings rather than merely omitting an item from the verified set:
BEV014 for integrity/read failures, BEV015 for unavailable identity or review,
BEV017 for source/identifier/title/quotation disagreement, and BEV019 for pinned
retraction evidence. Existing CLI exit codes remain 0 admitted, 1 rejected,
2 review required, and 3 operational error.

## Warnings, provenance, and replay

When this flag is used, the report adds an `evidence_library.checks` receipt for
each checked evidence item: exact citation and quotation, source hash, conversion,
original-page locator, parser/version, conversion and block warnings, and the
specific review ID/status where available. A reviewed quotation from a partial
conversion can pass its specific extraction gate; partial-conversion warnings
remain visible. Admission does not establish the correctness of the whole
conversion, scientific support, or clinical validity.

Python callers can instantiate `EvidenceLibraryGrounder(path)` and pass it in
`validate_record(..., grounders=[grounder])`. Its `last_checks` contains the most
recent evaluation receipts. Library imports are lazy; ordinary validation does
not require the optional package.

The check is offline and uses frozen provider metadata. It does not claim to
detect retractions published after acquisition. It does not rerun parsers: the
stored original, conversion, native artifacts, indexes, and quote-specific
review packet are checked by the library. Preserve the exact library snapshot,
record, report, and installed package versions to replay a decision. New review
events intentionally change a validation of the live store. Historical benchmark
snapshots and `tools/reproduce.py` are not migrated or rewritten by this adapter.

No real-paper reviews are created by the integration or its tests. Positive
approval/revocation tests use explicitly synthetic PDFs and reviewers only.
