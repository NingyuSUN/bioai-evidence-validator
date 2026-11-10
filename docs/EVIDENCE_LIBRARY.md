# Independent evidence library integration

The optional `--evidence-library` grounder reads an existing independent
`local-evidence-database` store. It does not download, ingest, convert, or approve
papers. Existing `ground`, profiles, schemas, and frozen benchmark replays
retain their previous behavior. This public integration adds only the
independent `--evidence-library` option.

## Install and validate

Install both reviewed checkouts into the same environment, or install their built
wheels. The independent library is not assumed to exist on PyPI:

```sh
python -m pip install -e /path/to/evidence-database
python -m pip install -e /path/to/bioai-evidence-validator
bioevidence validate record.json --profile literature-claim \
  --evidence-library /path/to/project/store --output validation.json
```

Use the independent library's PDF extra when working with PDF review packets.
The library must support `Store(root, read_only=True)`. A missing package, old
package, absent store, or unusable store produces an operational error; the
validator never silently disables this requested check. Validation output must
be outside the library directory.

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
  version 2 original-file identity check and matching frozen provider metadata.
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
