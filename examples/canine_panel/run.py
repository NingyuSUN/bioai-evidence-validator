"""Replay frozen real source checks and explicitly authored faults, fully offline."""
import argparse
import copy
import json
from pathlib import Path

from bioevidence_validator.canine import validate_canine_panel
from bioevidence_validator.grounding import SnapshotStore

ROOT = Path(__file__).resolve().parent


def evaluate():
    document = json.loads((ROOT / "panel.json").read_text(encoding="utf-8"))
    store = SnapshotStore.from_directory(ROOT / "sources")
    report = validate_canine_panel(document, store)
    assert report["engineering_status_counts"] == {"verified": 4, "review_required": 2, "rejected": 0}
    assert all(e["source_target_context_status"] == "VERIFIED_ORIENTED_COMPLETE_SLICE" for e in report["events"])
    assert sum(e["context_length_bp"] for e in report["events"]) == 1219
    assert report["events"][-1]["original_hgvs_status"] == "MALFORMED_REJECTED"
    assert report["events"][1]["engineering_status"] == "review_required"  # source type conflict
    cases = []
    for name, expected in [("wrong_ref", "rejected"), ("wrong_accession_version", "rejected"),
                           ("wrong_assembly", "rejected"), ("target_shift", "rejected"),
                           ("second_endpoint", "rejected"), ("receipt_whole_hash", "rejected"),
                           ("snapshot_hash", "review_required"), ("missing_source", "review_required"),
                           ("retained_hold", "review_required")]:
        fault = copy.deepcopy(document)
        # Isolate one actual event and its references; controls are authored,
        # not naturally occurring false records or independent disease labels.
        event = fault["events"][2 if name == "second_endpoint" else 0]
        fault["events"] = [event]
        fault["references"] = [r for r in fault["references"] if r["id"] in
                               {event["source_reference"], event["target_reference"]}]
        if name == "wrong_ref": event["event_ref"] = "A"
        elif name == "wrong_accession_version": event["source_hgvs"] = event["source_hgvs"].replace(".4:", ".999:")
        elif name == "wrong_assembly": event["source_assembly"] = "CanFam3.1"
        elif name == "target_shift": event["target_start1"] += 1; event["target_end1"] += 1
        elif name == "second_endpoint": event["target_end1"] += 1
        elif name == "receipt_whole_hash": fault["references"][1]["reference_sha256"] = "0" * 64
        elif name == "snapshot_hash": fault["references"][0]["snapshot_sha256"] = "0" * 64
        elif name == "missing_source": del event["source_reference"]
        else: event["held_reasons"] = ["Authored unresolved breakpoint ambiguity"]
        observed = validate_canine_panel(fault, store)
        assert observed["overall_status"] == expected, name
        assert not observed["assay_validated"] and not observed["reportable"] and not observed["admission_assessed"]
        cases.append({"name": name, "label_origin": "AUTHORED_FAULT_ON_REAL_SOURCE_CASE",
                      "expected": expected, "observed": observed["overall_status"]})
    return {"report.json": report, "controls.json": {
        "source_cases": 6, "complete_oriented_context_matches": 6, "context_bases": 1219,
        "authored_controls": cases, "clinical_accuracy_assessed": False,
        "independent_labels_available": False, "assay_validated": False}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    results = evaluate()
    args.output.mkdir(parents=True, exist_ok=True)
    for name, result in results.items():
        (args.output / name).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"source_cases": 6, "complete_context_matches": 6, "authored_controls": 9,
                      "clinical_accuracy_assessed": False, "assay_validated": False}))


if __name__ == "__main__":
    main()
