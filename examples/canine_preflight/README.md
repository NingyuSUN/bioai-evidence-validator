# Complete-event preflight example

This example wraps the existing six real source cases. It uses the unchanged
snapshots and attribution in `../canine_panel/sources/`.

```bash
bioevidence canine-preflight examples/canine_preflight/panel.json \
  --snapshot-dir examples/canine_panel/sources --output /tmp/preflight.json
```

Expected: all six source mutant contexts reconstructed; target equivalence is
`not_assessed` for all six because target VCF alleles have not been supplied in
this example. All six therefore remain review-required. Existing ABCB1 and DLL3
source issues remain visible. This is a development replay, not new scientific
validation of those events or coverage of the full 629-event canine draft.

See [the input/output and reuse contract](../../docs/CANINE_PREFLIGHT.md).
