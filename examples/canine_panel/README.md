# Canine panel: six real reference checks

Run `python examples/canine_panel/run.py` with this branch installed. The case
uses exact source bytes and a frozen target producer receipt from panel commit
`f6ffbe9909ec2a350fc320579f2a7019ddf7b3d6`. It needs no network.

All six source/target complete contexts match (five 201 bp, one 214 bp;
1,219 bp total). Four records have verified engineering checks. ABCB1 remains
under review because the catalogue's event type conflicts with its genomic edit;
DLL3 remains under review because the original description lacks `g.` and the
correction is explicit. All six keep assay/report/probe readiness false.

Nine deliberately authored faults check wrong REF, accession version, assembly,
target shift, second endpoint, whole-reference hash, missing snapshot, missing
source reference and a retained hold. These are software controls based on real
source sequences, not independent clinical labels or accuracy estimates. An
unavailable snapshot is review, not proof that its sequence is incorrect.

`results/` is deterministic and replayed byte for byte in tests and installed
wheel checks. `provenance.json` preserves the older extraction notes separately:
notes that once said target matching was pending do not override the later actual
target receipt. Other biological, nomenclature and assay issues remain outside
the sequence-check contract. See [the contract](../../docs/CANINE_PANEL_VALIDATION.md)
and [source terms](sources/README.md).
