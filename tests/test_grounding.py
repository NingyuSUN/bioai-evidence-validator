"""Source grounding: the snapshot store, generic byte checks, the CLI, and the two domain grounders."""
import copy
import functools
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from bioevidence_validator.cli import main
from bioevidence_validator.engine import RecordValidator, validate_record
from bioevidence_validator.grounding import SnapshotStore, SourceBytesGrounder

ROOT = Path(__file__).resolve().parents[1]
BYTES = b"pinned source bytes\n"
SHA = hashlib.sha256(BYTES).hexdigest()


def load(folder, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "examples" / folder / "pipeline.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


vbo = load("vbo_canine", "grounding_vbo_pipeline")
clinvar = load("clinvar_germline", "grounding_clinvar_pipeline")


def general(sha=SHA):
    record = json.loads((ROOT / "examples/general/curated_assertion.json").read_text(encoding="utf-8"))
    record["source_artifacts"][0].update(sha256=sha, observed_sha256=sha)
    return record


def codes(findings):
    return sorted({f.rule_id for f in findings})


def test_store_verifies_bytes_by_hash_not_by_file_name(tmp_path):
    forged = "b" * 64
    (tmp_path / f"{SHA}.txt").write_bytes(BYTES)
    (tmp_path / forged).write_bytes(BYTES)
    (tmp_path / "notes.txt").write_bytes(b"ignored")
    (tmp_path / ("c" * 64)).mkdir()
    store = SnapshotStore.from_directory(tmp_path)
    assert store.get(SHA) == BYTES and store.verified(SHA)
    assert store.get(forged) == BYTES and not store.verified(forged)
    assert store.get("c" * 64) is None and not store.verified("c" * 64)


def test_store_loads_and_hashes_each_snapshot_once():
    calls = []
    store = SnapshotStore({SHA: lambda: calls.append(SHA) or BYTES})
    assert all(store.verified(SHA) for _ in range(3)) and calls == [SHA]


@pytest.mark.parametrize("loaders,expected", [
    ({SHA: lambda: BYTES}, ([], "admitted")),
    ({}, (["BEV015"], "review_required")),
    ({SHA: lambda: BYTES + b"edited"}, (["BEV014"], "rejected")),
], ids=["verified", "missing", "changed"])
def test_source_hashes_are_recomputed_from_the_snapshot(loaders, expected):
    report = validate_record(general(), grounders=[SourceBytesGrounder(SnapshotStore(loaders))])
    assert (sorted({f["rule_id"] for f in report["findings"]}), report["overall_status"]) == expected
    assert report["grounding"] == ["source-bytes"]


def test_reports_without_grounders_keep_their_shape():
    assert "grounding" not in validate_record(general())


def test_grounders_only_see_structurally_sound_records():
    class Exploding:
        name = "exploding"

        def check(self, record):
            raise AssertionError("a grounder received an invalid record")

    record = general()
    del record["statement"]
    report = RecordValidator(grounders=[Exploding()]).validate(record)
    assert report["overall_status"] == "rejected" and report["grounding"] == ["exploding"]


def test_cli_snapshot_dir(tmp_path, capsys):
    path, snapshots = tmp_path / "record.json", tmp_path / "snapshots"
    path.write_text(json.dumps(general()), encoding="utf-8")
    snapshots.mkdir()
    assert main(["validate", str(path), "--snapshot-dir", str(snapshots)]) == 2
    assert "BEV015" in capsys.readouterr().out
    (snapshots / f"{SHA}.bin").write_bytes(BYTES)
    assert main(["validate", str(path), "--snapshot-dir", str(snapshots)]) == 0
    assert json.loads(capsys.readouterr().out)["grounding"] == ["source-bytes"]


@functools.cache
def dog_names():
    return vbo.DogNames()


def vbo_check(record):
    return codes(vbo.VboGrounder(dog_names()).check(record))


def dog(query="Labrador Retriever (Dog)"):
    return dog_names().record(query, "case")


def edited(record, change):
    record = copy.deepcopy(record)
    change(record)
    return record


def set_term_text(value):
    return lambda r: r["evidence_items"][0].update(extracted_text=value)


def test_vbo_grounder_accepts_importer_records():
    assert vbo_check(dog()) == []
    assert vbo_check(dog("Border Collie")) == []  # ambiguity is visible, and the engine's to judge


@pytest.mark.parametrize("change,expected", [
    (lambda r: r.update(vbo.perturb(r, "falsified_target")), ["BEV016", "BEV017"]),
    (lambda r: r.update(vbo.perturb(r, "wrong_existing_target", dog_names())), ["BEV017"]),
    (lambda r: r["statement"]["object"].update(label="Labrador"), ["BEV017"]),
    (set_term_text(json.dumps({"query": "Labrador Retriever (Dog)", "id": "VBO:NOPE", "name": "x"})), ["BEV016"]),
    (set_term_text("not json"), ["BEV016"]),
    (set_term_text("[1]"), ["BEV016"]),
    (lambda r: r["evidence_items"][0].update(locator="term:VBO:0200800;upstream-line:1"), ["BEV017"]),
    (lambda r: r["evidence_items"][1].update(extracted_text=json.dumps({"candidate_ids": []})), ["BEV017"]),
    (lambda r: r["evidence_items"][1].update(evidence_type="ambiguous_label_resolution"), ["BEV017"]),
    (vbo.add_note, ["BEV015"]),
    (lambda r: r["evidence_items"][0].update(source_artifact_id="bioev:elsewhere"), []),
    (lambda r: r.update(vbo.perturb(r, "unpinned_source")), []),  # not this grounder's source: SourceBytesGrounder flags it
], ids=["nonexistent-target", "wrong-real-target", "label", "asserted-term", "unparsable", "not-an-object", "locator",
        "candidates", "resolution-type", "unknown-type", "other-source", "unpinned"])
def test_vbo_grounder_recomputes_what_the_record_asserts(change, expected):
    assert vbo_check(edited(dog(), change)) == expected


@functools.cache
def clinvar_grounder():
    return clinvar.ClinVarGrounder(clinvar.ClinVarSample())


def clinvar_check(record):
    return codes(clinvar_grounder().check(record))


@functools.cache
def variant(stratum, dissent=False):
    source = clinvar_grounder().source
    for case in source.cases:
        record = source.record(case)
        lines = record["statement"]["evidence_lines"]
        if case["stratum"] == stratum and any(line["direction"] == "contradicts" for line in lines) == dissent:
            return record
    raise LookupError(stratum)


def test_clinvar_grounder_accepts_importer_records():
    for stratum in ["no_criteria", "single_submitter", "multiple_submitters", "expert_panel", "conflicting"]:
        assert clinvar_check(variant(stratum)) == [], stratum
    assert clinvar_check(variant("expert_panel", dissent=True)) == []


def first_submission(record):
    return next(i for i in record["evidence_items"] if i["id"].startswith("bioev:SCV"))


def flip_direction(record):
    item = first_submission(record)
    for line in record["statement"]["evidence_lines"]:
        line["evidence_item_ids"] = [i for i in line["evidence_item_ids"] if i != item["id"]]
    record["statement"]["evidence_lines"].append({"id": "bioev:flipped", "direction": "contradicts",
                                                  "evidence_item_ids": [item["id"]]})


def reclassify(record):
    item = first_submission(record)
    text = json.loads(item["extracted_text"])
    item["extracted_text"] = json.dumps({**text, "classification": "Benign"})


@pytest.mark.parametrize("stratum,change,expected", [
    ("expert_panel", lambda r: r.update(clinvar.perturb(r, "omitted_dissent")), ["BEV018"]),
    ("no_criteria", lambda r: r.update(clinvar.perturb(r, "fabricated_expert_review")), ["BEV017"]),
    ("multiple_submitters", lambda r: r.update(clinvar.perturb(r, "injected_dissent")), ["BEV016"]),
    ("multiple_submitters", lambda r: r.update(clinvar.perturb(r, "somatic_scope")), ["BEV017"]),
    ("multiple_submitters", lambda r: r.update(clinvar.perturb(r, "llm_derived_review")), []),
    ("multiple_submitters", flip_direction, ["BEV017"]),
    ("multiple_submitters", reclassify, ["BEV017"]),
    ("multiple_submitters", lambda r: first_submission(r).update(extracted_text="not json"), ["BEV017"]),
    ("multiple_submitters", lambda r: r["evidence_items"][-1].update(extracted_text="0 distinct submitters"), ["BEV017"]),
    ("multiple_submitters", clinvar.add_note, ["BEV015"]),
    ("multiple_submitters", lambda r: first_submission(r).update(source_artifact_id="bioev:elsewhere"), ["BEV018"]),
    ("multiple_submitters", lambda r: r["statement"]["subject"].update(id="clinvar:0"), ["BEV016"]),
    ("multiple_submitters", lambda r: r["statement"]["subject"].update(id="bioev:unknown"), ["BEV016"]),
    ("multiple_submitters", lambda r: r["source_artifacts"][0].update(sha256="d" * 64), []),
], ids=["omitted-dissent", "fabricated-review", "invented-submission", "scope", "method-not-compared", "direction",
        "classification", "unparsable", "derived-text", "unknown-type", "omitted-submission", "unknown-variant",
        "not-a-clinvar-id", "other-source"])
def test_clinvar_grounder_rebuilds_the_evidence(stratum, change, expected):
    assert clinvar_check(edited(variant(stratum, dissent=stratum == "expert_panel"), change)) == expected
