"""Authored engineering fixtures; these do not label disease or assay truth."""
import copy
import hashlib
import json

import pytest

from bioevidence_validator.canine import VariantProblem, parse_genomic_hgvs, validate_canine_panel
from bioevidence_validator.cli import main
from bioevidence_validator.grounding import SnapshotStore
from bioevidence_validator.identifiers import Assemblies, VariantGrounder

ASSEMBLY = "UU_Cfam_GSD_1.0"
ACCESSION = "NC_049235.1"
SEQUENCE = "AACCGGTTAACCGGTT"
WHOLE_HASH = "a" * 64


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fixture(hgvs=None, fmt="ncbi_efetch_json", strand="+"):
    text = f">{ACCESSION}:100-115 Canis lupus familiaris chromosome 14, alternate assembly {ASSEMBLY}, whole genome shotgun sequence\n{SEQUENCE}\n\n"
    source = {"fasta": text, "bytes": len(text.encode()), "sha256": digest(text.encode()), "status": 200,
        "reference_accession": ACCESSION, "requested_1based_inclusive_start": 100,
        "requested_1based_inclusive_end": 115, "sequence_sha256": digest(SEQUENCE.encode())}
    source_bytes = json.dumps(source).encode() if fmt == "ncbi_efetch_json" else text.encode()
    target_sequence = SEQUENCE if strand == "+" else "AACCGGTTAACCGGTT"  # independently written reverse complement
    receipt = {"reference_sha256": WHOLE_HASH, "queries": {"case": {"chrom": "chr14", "start0": 199, "end0": 215,
        "sequence": target_sequence, "sequence_sha256": digest(target_sequence.encode())}}}
    target_bytes = json.dumps(receipt).encode()
    raw = {digest(source_bytes): source_bytes, digest(target_bytes): target_bytes}
    document = {"format_version": "canine-panel-1", "taxon": "NCBITaxon:9615", "references": [
        {"id": "source", "assembly": ASSEMBLY, "sequence_id": ACCESSION, "snapshot_sha256": digest(source_bytes), "format": fmt},
        {"id": "target", "assembly": "ROSY_custom", "sequence_id": "chr14", "snapshot_sha256": digest(target_bytes),
         "format": "reference_receipt_json", "query_key": "case", "reference_sha256": WHOLE_HASH}],
        "events": [{"id": "authored:1", "source_hgvs": hgvs or f"{ACCESSION}:g.102C>T", "source_assembly": ASSEMBLY,
            "source_reference": "source", "target_reference": "target", "target_start1": 202 if strand == "+" else 213,
            "target_end1": 202 if strand == "+" else 213, "target_strand": strand, "target_assembly": "ROSY_custom"}]}
    return document, raw


def run(document, raw):
    return validate_canine_panel(document, SnapshotStore({k: (lambda data=v: data) for k, v in raw.items()}))


def rebind(document, raw, index, value):
    """Author a new snapshot, with an independently recomputed hash."""
    key = document["references"][index]["snapshot_sha256"]
    data = json.dumps(value).encode() if isinstance(value, dict) else value
    raw[digest(data)] = data
    document["references"][index]["snapshot_sha256"] = digest(data)
    return key


@pytest.mark.parametrize("edit,ref,alt,end", [
    ("102C>T", "C", "T", 102), ("102_103del", "CC", "", 103),
    ("102_103dup", "CC", "CCCC", 103), ("102_104inv", "CCG", "CGG", 104),
    ("102_103delinsAT", "CC", "AT", 103), ("102_103insAT", "", "AT", 103)])
def test_actual_alleles_and_both_endpoints(edit, ref, alt, end):
    doc, raw = fixture(f"{ACCESSION}:g.{edit}")
    doc["events"][0].update(target_end1=end+100, event_ref=ref, event_alt=alt)
    report = run(doc, raw)
    row = report["events"][0]
    assert report["overall_status"] == "verified"
    assert (row["event_ref"], row["event_alt"]) == (ref, alt)
    assert row["context_length_bp"] == 16 and row["source_target_context_status"].startswith("VERIFIED")
    assert not any(report[key] for key in ["admission_assessed", "clinical_interpretation_assessed", "assay_validated", "reportable", "probe_ready"])


@pytest.mark.parametrize("text,code", [
    ("NC_049235:g.102C>T", "BEV024"), ("NC_049235.0:g.102C>T", "BEV024"),
    ("NC_049235.1:102C>T", "BEV024"), ("NC_049235.1:g.102C>T)", "BEV024"),
    ("NC_049235.1:g.102 C>T", "BEV024"), ("NC_049235.1:g.0C>T", "BEV024"),
    ("NC_049235.1:g.102C>C", "BEV024"), ("NC_049235.1:g.105_102del", "BEV024"),
    ("NC_049235.1:g.102_102del", "BEV024"), ("NC_049235.1:g.102insAT", "BEV024"),
    ("NC_049235.1:g.102_104insAT", "BEV024"), ("NC_049235.1:g.102inv", "BEV024"),
    ("NC_049235.1:g.102_103inv2", "BEV024"), ("NC_049235.1:g.102_103ins", "BEV024"),
    ("NC_049235.1:g.102_103ins2", "BEV024"), ("NC_049235.1:g.102_103del3", "BEV024"),
    ("NC_049235.1:g.102_103delN[2]", "BEV024"), ("NC_049235.1:g.102_103delA", "BEV024"),
    ("NM_001003343.1:c.7528-4048_7645+4450dup", "BEV015"),
    ("NC_049235.1:c.102C>T", "BEV015"), ("NC_049235.1:g.(102_105)del", "BEV015"),
    ("NC_049235.1:g.102_103ins[NC_000001.11:g.1_5]", "BEV015"),
    ("NC_049235.1:g.102A[5]", "BEV015"),
    ("NC_049235.1:g.[102_103del;103C>T]", "BEV015")])
def test_malformed_and_supported_limits_are_distinct(text, code):
    with pytest.raises(VariantProblem) as exc:
        parse_genomic_hgvs(text)
    assert exc.value.code == code


@pytest.mark.parametrize("edit,expected", [("102_103insN[223]", 223), ("102_103delinsN[143]", 143)])
def test_insert_length_is_not_insert_sequence(edit, expected):
    doc, raw = fixture(f"{ACCESSION}:g.{edit}")
    doc["events"][0]["target_end1"] = 203
    report = run(doc, raw)
    row = report["events"][0]
    assert row["engineering_status"] == "review_required" and row["event_alt"] is None
    assert row["components"][0]["inserted_length"] == expected
    assert row["components"][0]["deleted_length"] == (2 if "delins" in edit else 0)


@pytest.mark.parametrize("tail", ["CC", "2"])
def test_redundant_historical_deletion_keeps_nomenclature_review(tail):
    doc, raw = fixture(f"{ACCESSION}:g.102_103del{tail}")
    doc["events"][0]["target_end1"] = 203
    assert run(doc, raw)["events"][0]["engineering_status"] == "review_required"


def test_compound_components_are_not_silently_dropped():
    doc, raw = fixture(f"{ACCESSION}:g.[102C>T;104_105del]")
    doc["events"][0]["target_end1"] = 205
    row = run(doc, raw)["events"][0]
    assert len(row["components"]) == 2 and row["engineering_status"] == "review_required"
    assert row["allele_phase"] == "NOT_VERIFIED" and "event_ref" not in row


def test_compound_declared_alleles_retained_and_explicitly_unchecked():
    doc, raw = fixture(f"{ACCESSION}:g.[102C>T;104_105del]")
    doc["events"][0].update(target_end1=205, event_ref="AAAA", event_alt="AAAA")
    row = run(doc, raw)["events"][0]
    assert row["declared_event_ref"] == row["declared_event_alt"] == "AAAA"
    assert row["declared_event_alleles_status"] == "NOT_CHECKED_COMPOUND_RECONSTRUCTION_REQUIRED"
    assert row["engineering_status"] == "review_required"
    assert any(f["field_path"] == "event_ref/event_alt" and "not checked" in f["message"] for f in row["findings"])


@pytest.mark.parametrize("body", ["9"*5000+"C>T", "102_103insN["+"9"*5000+"]", "102_103del"+"9"*5000])
def test_unbounded_numeric_hgvs_returns_per_event_findings(body):
    with pytest.raises(VariantProblem, match="18-digit"):
        parse_genomic_hgvs(ACCESSION+":g."+body)
    doc, raw = fixture(ACCESSION+":g."+body)
    assert run(doc, raw)["overall_status"] == "rejected"


@pytest.mark.parametrize("kind", ["unbounded_fasta", "deep_json", "unbounded_json_number"])
def test_reference_parser_resource_limits_return_findings(kind):
    doc, raw = fixture()
    value = json.loads(raw[doc["references"][0]["snapshot_sha256"]])
    if kind == "unbounded_fasta":
        value["fasta"] = value["fasta"].replace(":100-115", ":"+"9"*5000+"-115")
        value.update(sha256=digest(value["fasta"].encode()), bytes=len(value["fasta"].encode()))
    elif kind == "deep_json": value = b'['*2000+b'0'+b']'*2000
    else: value = b'{"status":'+b'9'*5000+b'}'
    rebind(doc, raw, 0, value)
    assert run(doc, raw)["overall_status"] == "rejected"


def test_reverse_complement_context_and_offsets():
    doc, raw = fixture(strand="-")
    assert run(doc, raw)["overall_status"] == "verified"
    doc["events"][0]["target_start1"] = doc["events"][0]["target_end1"] = 202
    assert run(doc, raw)["overall_status"] == "rejected"


def test_reverse_complement_nonpalindromic_real_orientation():
    doc, raw = fixture(strand="-")
    sequence = "AACCGGTTAACCGGTA"
    source = json.loads(raw[doc["references"][0]["snapshot_sha256"]])
    source["fasta"] = source["fasta"].replace(SEQUENCE, sequence)
    source.update(sha256=digest(source["fasta"].encode()), sequence_sha256=digest(sequence.encode()))
    rebind(doc, raw, 0, source)
    target = json.loads(raw[doc["references"][1]["snapshot_sha256"]])
    target["queries"]["case"].update(sequence="TACCGGTTAACCGGTT", sequence_sha256=digest(b"TACCGGTTAACCGGTT"))
    rebind(doc, raw, 1, target)
    assert run(doc, raw)["overall_status"] == "verified"
    target["queries"]["case"].update(sequence=sequence, sequence_sha256=digest(sequence.encode()))
    rebind(doc, raw, 1, target)
    assert run(doc, raw)["overall_status"] == "rejected"


@pytest.mark.parametrize("field,value", [("source_assembly", "CanFam3.1"), ("source_reference", "missing"),
    ("target_reference", "missing"), ("target_assembly", "UU_Cfam_GSD_1.0"),
    ("target_end1", 203), ("event_ref", "A"), ("event_alt", "G")])
def test_wrong_contract_or_event_allele(field, value):
    doc, raw = fixture(); doc["events"][0][field] = value
    expected = "review_required" if field.endswith("reference") else "rejected"
    assert run(doc, raw)["overall_status"] == expected


def test_missing_target_and_endpoint_or_wrong_ref_cannot_pass():
    doc, raw = fixture(); del doc["events"][0]["target_reference"]
    assert run(doc, raw)["overall_status"] == "review_required"
    for text, expected in [(f"{ACCESSION}:g.102A>T", "rejected"), (f"{ACCESSION}:g.102_999del", "review_required"),
                           ("NC_049235.999:g.102C>T", "rejected")]:
        doc, raw = fixture(text); assert run(doc, raw)["overall_status"] == expected


def test_original_correction_and_held_issues_cannot_be_promoted():
    doc, raw = fixture()
    doc["events"][0].update(source_hgvs="NC_049235.1:102C>T", reviewed_hgvs=f"{ACCESSION}:g.102C>T", held_reasons=["1bp source conflict"])
    row = run(doc, raw)["events"][0]
    assert row["original_hgvs_status"] == "MALFORMED_REJECTED" and row["source_reference_status"].startswith("VERIFIED")
    assert row["engineering_status"] == "review_required" and len(row["findings"]) >= 2
    doc["events"][0].update(source_hgvs=f"{ACCESSION}:g.103C>T")
    assert run(doc, raw)["overall_status"] == "review_required"


@pytest.mark.parametrize("collection", ["events", "references"])
def test_duplicate_identifiers_are_invalid(collection):
    doc, raw = fixture(); doc[collection].append(copy.deepcopy(doc[collection][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        run(doc, raw)


@pytest.mark.parametrize("mutation", ["taxon", "unknown", "target", "bool", "hash"])
def test_input_contract_fails_closed(mutation):
    doc, raw = fixture()
    if mutation == "taxon": doc["taxon"] = "NCBITaxon:9606"
    elif mutation == "unknown": doc["events"][0]["reportable"] = True
    elif mutation == "target": del doc["events"][0]["target_end1"]
    elif mutation == "bool": doc["events"][0]["target_start1"] = True
    else: doc["references"][0]["snapshot_sha256"] = "unversioned"
    with pytest.raises(ValueError, match="Invalid canine-panel"):
        run(doc, raw)


@pytest.mark.parametrize("kind,expected", [("missing", "review_required"), ("tampered", "rejected"),
    ("json", "rejected"), ("raw_hash", "rejected"), ("receipt_meta", "rejected"),
    ("status", "review_required"), ("sequence_id", "rejected"), ("assembly", "rejected"),
    ("taxon", "rejected"), ("range", "rejected"), ("multi_fasta", "rejected"), ("bad_header", "rejected"),
    ("whole_hash", "rejected"), ("target_hash", "rejected"), ("target_bool", "rejected"),
    ("target_bases", "rejected"), ("ambiguity", "review_required"), ("context_mismatch", "rejected")])
def test_reference_bytes_and_metadata(kind, expected):
    doc, raw = fixture(); index = 1 if kind.startswith("target") or kind in {"whole_hash", "context_mismatch"} else 0
    key = doc["references"][index]["snapshot_sha256"]
    if kind == "missing": del raw[key]
    elif kind == "tampered": raw[key] += b"changed"
    elif kind == "json": rebind(doc, raw, index, b"not JSON")
    else:
        value = json.loads(raw[key])
        if kind == "raw_hash": value["sha256"] = "0"*64
        elif kind == "receipt_meta": value["requested_1based_inclusive_end"] += 1
        elif kind == "status": value["status"] = 403
        elif kind == "sequence_id": doc["references"][0]["sequence_id"] = "NC_049235.999"
        elif kind == "assembly": doc["references"][0]["assembly"] = "CanFam3.1"
        elif kind in {"taxon", "range", "multi_fasta", "bad_header", "ambiguity"}:
            replacements = {"taxon": ("Canis lupus familiaris", "Homo sapiens"), "range": ("100-115", "100-116"),
                "multi_fasta": ("\n\n", "\n>NC_049235.1:1-1 bad\nA\n"), "bad_header": (":100-115", ""),
                "ambiguity": (SEQUENCE, SEQUENCE[:2]+"N"+SEQUENCE[3:])}
            value["fasta"] = value["fasta"].replace(*replacements[kind])
            value["sha256"] = digest(value["fasta"].encode()); value["bytes"] = len(value["fasta"].encode())
            if kind == "ambiguity": value["sequence_sha256"] = digest((SEQUENCE[:2]+"N"+SEQUENCE[3:]).encode())
        elif kind == "whole_hash": value["reference_sha256"] = "b"*64
        else:
            row = value["queries"]["case"]
            if kind == "target_hash": row["sequence_sha256"] = "0"*64
            elif kind == "target_bool": row["start0"] = True
            else:
                row["sequence"] = "X"+SEQUENCE[1:] if kind == "target_bases" else "T"+SEQUENCE[1:]
                row["sequence_sha256"] = digest(row["sequence"].encode())
        rebind(doc, raw, index, value)
    assert run(doc, raw)["overall_status"] == expected


def test_unreferenced_bad_snapshot_is_still_reported():
    doc, raw = fixture(); bad = copy.deepcopy(doc["references"][0]); bad.update(id="unused", snapshot_sha256="f"*64)
    doc["references"].append(bad)
    report = run(doc, raw)
    assert report["events"][0]["engineering_status"] == "verified" and report["overall_status"] == "review_required"
    assert len(report["reference_findings"]) == 1


@pytest.mark.parametrize("kind", ["duplicate_json", "fasta_not_text", "float_coordinate", "float_bytes", "list", "invalid_utf8"])
def test_malformed_snapshots_return_findings_without_crashing(kind):
    doc, raw = fixture()
    value = json.loads(raw[doc["references"][0]["snapshot_sha256"]])
    if kind == "duplicate_json": value = b'{"status":200,"status":403}'
    elif kind == "fasta_not_text": value["fasta"] = 123
    elif kind == "float_coordinate": value["requested_1based_inclusive_start"] = 100.0
    elif kind == "float_bytes": value["bytes"] = float(value["bytes"])
    elif kind == "list": value = b'[]'
    else: value = b'\xff'
    rebind(doc, raw, 0, value)
    assert run(doc, raw)["overall_status"] == "rejected"


def test_raw_fasta_input_and_no_mutation():
    doc, raw = fixture(fmt="ncbi_fasta"); original = copy.deepcopy(doc)
    assert run(doc, raw)["overall_status"] == "verified" and doc == original


def test_ncbi_legacy_header_exact_assembly_comma_field():
    doc, raw = fixture()
    value = json.loads(raw[doc["references"][0]["snapshot_sha256"]])
    value["fasta"] = value["fasta"].replace("alternate assembly " + ASSEMBLY, "CanFam3.1")
    value.update(sha256=digest(value["fasta"].encode()), bytes=len(value["fasta"].encode()))
    doc["references"][0]["assembly"] = doc["events"][0]["source_assembly"] = "CanFam3.1"
    rebind(doc, raw, 0, value)
    assert run(doc, raw)["overall_status"] == "verified"
    doc["references"][0]["assembly"] = doc["events"][0]["source_assembly"] = "CanFam3"
    assert run(doc, raw)["overall_status"] == "rejected"


def test_real_panel_example_replays_committed_results(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root/"examples/canine_panel/run.py"), "--output", str(tmp_path)],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    for expected in (root/"examples/canine_panel/results").iterdir():
        assert expected.read_bytes() == (tmp_path/expected.name).read_bytes()


def test_assembly_decimal_and_patch_identity():
    reports = [b"# Assembly name: CanFam3.1\n14\tx\tx\tx\tx\t=\tNC_006602.3\tx\t1000\n",
               b"# Assembly name: UU_Cfam_GSD_1.0\n14\tx\tx\tx\tx\t=\tNC_049235.1\tx\t1000\n",
               b"# Assembly name: GRCh38.p14\n7\tx\tx\tx\tx\t=\tNC_000007.14\tx\t1000\n"]
    assemblies = Assemblies.from_reports(reports)
    assert assemblies.sequences["NC_006602.3"][0] == "CanFam3.1"
    assert assemblies.sequences[ACCESSION][0] == ASSEMBLY
    assert assemblies.sequences["NC_000007.14"][0] == "GRCh38"
    record = {"statement": {"subject": {"id": f"{ACCESSION}:g.1A>T", "label": "test", "entity_type": "variant"},
        "object": {"id": "p:1", "label": "phenotype", "entity_type": "phenotype"}, "scope": ["CanFam3.1"]}, "evidence_items": [], "requested_uses": ["research_summary"]}
    assert [f.rule_id for f in VariantGrounder(assemblies).check(record)] == ["BEV017"]
    record["statement"]["scope"] = [ASSEMBLY]
    assert VariantGrounder(assemblies).check(record) == []


@pytest.mark.parametrize("state,expected", [("verified", 0), ("review", 2), ("rejected", 1)])
def test_cli_statuses_and_protected_inputs(tmp_path, capsys, state, expected):
    doc, raw = fixture()
    if state == "review": doc["events"][0]["held_reasons"] = ["source pending"]
    if state == "rejected": doc["events"][0]["event_ref"] = "A"
    snapshots = tmp_path/"snapshots"; snapshots.mkdir()
    for key, data in raw.items(): (snapshots/(key+".json")).write_bytes(data)
    inp = tmp_path/"input.json"; inp.write_text(json.dumps(doc)); out = tmp_path/"report.json"
    args = ["canine-panel", str(inp), "--snapshot-dir", str(snapshots)]
    assert main(args+["--output", str(out)]) == expected
    assert json.loads(out.read_text())["assay_validated"] is False
    assert main(args) == expected and "engineering_status_counts" in capsys.readouterr().out
    for path in (inp, snapshots/"report.json"):
        assert main(args+["--output", str(path)]) == 3
