# Local EvidPort MCP validation

This optional bridge reads evidence through EvidPort's local MCP server, then
independently checks the same citations against the original evidence library.
The existing `bioevidence validate --evidence-library` command remains available.
EvidPort stays independent: it does not import Validator.

## What is checked

For each exact `evidence:cv_<hash>#<block>` citation in a proposed record, the bridge
calls `evidport_evidence_get` and `evidport_evidence_check_quote`. It compares their
structured responses with the read-only library: source SHA-256, extraction
version, citation, page/region locator, text, warnings and quote-specific review.
Repeated identical citations and quotations share calls within a session.

The normal `EvidenceLibraryGrounder` still checks publication identity, pinned
retraction metadata, source bytes and original-page review. A server cannot grant
admission merely by returning `admitted: true`. Timeouts, malformed responses,
wrong source hashes and disagreements block admission. Text-only responses are
not accepted as a substitute for the structured contract.

The bridge validates a proposed record. It does not invent its scientific claim,
acquire missing papers or create a human approval.

## Install

From this Validator checkout, install its optional MCP dependency (official
Python SDK **2.3.0**) and the reviewed EvidPort revision:

```sh
python -m pip install -e '.[mcp]'
python -m pip install 'local-evidence-database[mcp,pdf] @ git+https://github.com/NingyuSUN/evidport.git@65c8626185eaa3c3e9e7b60db4c17b43a545d394'
```

The optional extra is also locked in `uv.lock`. The server can use a separate
environment, but both processes must read the **same evidence library**. The
example below uses one activated environment containing both packages.

## Configure one project

Keep your actual papers, project configuration and generated reports outside
version control. Place an ignored `local-mcp.json` beside your EvidPort
`project.json`:

```json
{
  "command": "python",
  "args": [
    "-m", "evidence_database.mcp_server",
    "--project-config", "project.json"
  ],
  "cwd": "."
}
```

This is a single-server configuration, not an application's `mcpServers` wrapper.
`python` is resolved from the activated environment's `PATH`. The explicit `cwd`
is resolved relative to the configuration file, so `project.json` is interpreted
beside that file regardless of the caller's working directory. No workstation
directory is embedded in this example. The executable and arguments are trusted
operator settings; the process starts directly without a shell.

EvidPort starts offline by default. Add `--allow-network` to its startup arguments
to enable the existing discovery and free-PDF providers. The bridge itself only
needs local retrieval. Remote URL configurations are rejected. Its optional
`env` accepts only `PYTHONIOENCODING: "utf-8"` and `PYTHONUTF8: "1"`, also the
defaults; do not put credentials in this file.

From the project folder, assuming the configured store is named `evidence`:

```console
python -m bioevidence_validator.evidence_mcp --server-config local-mcp.json --evidence-library evidence --record proposed-record.json --profile literature-claim --output validation-report.json
```

Use the store selected by your project configuration if it has another name.
The output must be outside the library and must not overwrite the record,
configuration, schema or profile. Sessions default to a 60-second timeout,
configurable up to 300 seconds with `--timeout`. Records are limited to 8 MiB and
100 evidence items; each structured response is limited to 1 MiB.

| Exit code | Meaning |
|---|---|
| `0` | Record admitted under the selected policy |
| `1` | Record rejected; inspect the JSON findings |
| `2`, with a JSON report | Original-page review or other required review is pending |
| `2`, with a command-line error | Configuration/input failed; no successful validation report was produced |

## From a missing paper to a checked quotation

1. Use EvidPort to discover candidates and try free acquisition. A paper without
   available full text remains a DOI task, with no invented quotation or page.
2. Save a paper obtained through your own access in the configured inbox. Finish
   the identity-checking import and conversion jobs before searching its text.
3. Search an exact extraction version, inspect warnings and the original page,
   then place its citation and complete quotation in the proposed record.
4. Run this bridge against the same library. An exact quotation with no recorded
   original-page review remains `review_required`.

A pending item may instead mean uncertain file identity or partial extraction;
inspect its reason before treating it as a missing or paywalled paper.
[EvidPort's MCP guide](https://github.com/NingyuSUN/evidport/blob/main/docs/MCP_USAGE.md)
describes its 13 tools, 4 resource templates and local job workflow. Human review
remains a separate recorded action, and new versions do not inherit approvals.

## Python use

```python
from pathlib import Path
from bioevidence_validator.evidence_mcp import load_server_config, validate_via_mcp

config = load_server_config(Path("local-mcp.json"))
report = await validate_via_mcp(
    record,
    library_path=Path("evidence").resolve(),
    profile="literature-claim",
    **config,
)
```

The ordinary report gains `evidence_mcp` and `evidence_library` details. A completed
MCP check means the responses matched the library. The record's `overall_status`
and per-use decisions still determine admission.

## Validation and limitations

Synthetic tests cover false quotations, wrong hashes, fabricated approvals,
conflicting pages/versions/text, timeouts, malformed responses and revoked
reviews. A real stdio subprocess test sends matching and fabricated quotations
through the server and this consumer. CI requires both the SDK and pinned server
to import before running the suite, so that protocol test cannot silently skip
because a dependency was omitted.

The [EvidPort acceptance summary](https://github.com/NingyuSUN/evidport/blob/main/evaluation/mcp-local-20261111.json)
separately records known-positive retrieval from nine distinct papers, including
three manual re-imports, and real Validator checks. These were engineering
checks with historical metadata, not blind scientific question answering or a
new test of live acquisition. Original PDFs, databases and private reports are
not distributed here.

Matching extracted text does not establish accurate OCR, scientific support or
clinical validity. Original-page review still matters. SDK tests do not establish
desktop application approval, configuration reload or every client's behavior.
The library stays on the local computer, but a consuming AI client may send its
returned text or page images to its model provider.
