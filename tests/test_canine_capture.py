"""Authored counterexamples: requirements checks are not sample validation."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from bioevidence_validator.grounding import SnapshotStore


def fixture(kind="X_INVERSION"):
    source = {"event_id": "authored:1", "gene_original": "F8", "plan_kind": kind}
    constraints = {"schema": "canine-ngs-capture-constraints-1", "primary_method": {"value": "NGS"},
        "preferred_enrichment": {"value": "HYBRIDIZATION_CAPTURE"}, "sequencing": {"mode": "PE300",
        "paired_end": True, "read1_nominal_max_bp": 300, "read2_nominal_max_bp": 300,
        "PE300_is_guaranteed_contiguous_600bp": False, "dna_insert_length_distribution_bp": None,
        "actual_effective_read_length_distribution_bp": None}}
    raw = {}

    def pin(value):
        data = json.dumps(value).encode(); key = hashlib.sha256(data).hexdigest(); raw[key] = data
        return key

    source_hash = pin(source); constraint_hash = pin(constraints)
    scope = "RNA_ONLY_SOURCE_GDNA_CAUSAL_ANCHOR_HELD" if kind == "RNA" else (
        "LESION_SOMATIC_RESEARCH_NOT_GERMLINE_SCREENING" if kind == "SOMATIC" else "GENOMIC_CANDIDATE_TARGET_IN_DRAFT_NOT_ADMITTED")
    row = {"event_id": "authored:1", "gene": "F8", "plan_kind": kind,
        "primary_product_method": "NGS_HYBRID_CAPTURE_PREFERRED_PE300", "scope": scope,
        "source_record_binding": {"sha256": source_hash}, "source_event_requirements_lossless": source,
        "method_constraints_binding": {"sha256": constraint_hash},
        "required_ngs_evidence": ["orientation_junction_evidence", "both_breakend_contexts_if_established"],
        "capture_design": {"requirements_zh": "Authored requirement", "final_baits": None, "final_capture_intervals": None},
        "inconclusive_rule_zh": "Authored inconclusive rule", "event_specific_limits_zh": "No sample truth",
        "coverage_and_performance": {"actual_experimental_samples": 0, "minimum_effective_depth": None},
        "sex_ploidy_calibration_required": kind.startswith("X_"),
        "PE300_guarantees_complete_repeat_length": False, "total_copy_number_establishes_phase": False,
        "normal_copy_number_excludes_event": False, "germline_panel_admission_approved": False,
        "assay_validated": False, "probe_ready": False, "orderable": False, "reportable": False}
    payload = {"schema": "canine-all-ngs-route-requirements-1", "source_id_count": 1, "records": [row],
        "experimental_samples_tested": 0, "final_baits": 0, "full_CNV_SV_completeness_verified": False,
        "assay_validated": False, "probe_ready": False, "orderable": False, "reportable": False}
    doc = {"format_version": "canine-capture-1", "taxon": "NCBITaxon:9615",
        "requirements_snapshot_sha256": pin(payload), "method_constraints_snapshot_sha256": constraint_hash}
    return doc, raw, payload, constraints


def rebind(document, raw, payload, key="requirements_snapshot_sha256"):
    data = json.dumps(payload).encode(); value = hashlib.sha256(data).hexdigest(); raw[value] = data; document[key] = value


def run(document, raw):
    from bioevidence_validator.canine_capture import validate_canine_capture
    return validate_canine_capture(document, SnapshotStore({k: (lambda v=v: v) for k, v in raw.items()}))


def test_consistent_requirements_do_not_release_an_assay():
    doc, raw, _, _ = fixture()
    report = run(doc, raw)
    assert report["requirements_consistency_counts"]["verified"] == 1
    assert report["overall_status"] == "review_required"
    assert not any(report[k] for k in ["assay_validated", "probe_ready", "orderable", "reportable", "clinical_interpretation_assessed"])
    assert "FINAL_CAPTURE_NOT_DEFINED" in report["events"][0]["unresolved_evidence"]


@pytest.mark.parametrize("field", ["PE300_guarantees_complete_repeat_length", "total_copy_number_establishes_phase",
    "normal_copy_number_excludes_event", "germline_panel_admission_approved", "assay_validated", "probe_ready", "orderable", "reportable"])
def test_unsupported_admission_and_inference_flags_are_rejected(field):
    doc, raw, payload, _ = fixture(); payload["records"][0][field] = True; rebind(doc, raw, payload)
    assert run(doc, raw)["overall_status"] == "rejected"


def test_normal_dosage_and_one_junction_cannot_define_inversion():
    doc, raw, payload, _ = fixture(); payload["records"][0]["required_ngs_evidence"] = ["normalized_depth_vs_comparable_controls"]
    rebind(doc, raw, payload)
    assert run(doc, raw)["overall_status"] == "rejected"


@pytest.mark.parametrize("kind", ["RNA", "SOMATIC"])
def test_RNA_or_lesion_source_is_not_silently_a_germline_target(kind):
    doc, raw, payload, _ = fixture(kind); payload["records"][0]["scope"] = "GENOMIC_CANDIDATE_TARGET_IN_DRAFT_NOT_ADMITTED"
    rebind(doc, raw, payload)
    assert run(doc, raw)["overall_status"] == "rejected"


def test_source_kind_cannot_be_changed_to_bypass_rules():
    doc, raw, payload, _ = fixture(); payload["records"][0]["plan_kind"] = "SMALL"
    rebind(doc, raw, payload)
    assert run(doc, raw)["overall_status"] == "rejected"


def test_shared_retrogene_coding_reads_do_not_establish_insertion_locus():
    doc, raw, payload, _ = fixture(); payload["records"][0]["copy_count_from_shared_FGF4_coding_reads_is_locus_specific"] = True
    rebind(doc, raw, payload)
    assert run(doc, raw)["overall_status"] == "rejected"


def test_counterevidence_is_not_clinical_acceptance():
    doc, raw, payload, _ = fixture()
    payload["records"][0]["interpretation_review"] = {"counterevidence_pmids": ["25661582"], "causal_disease_claim_accepted": True}
    rebind(doc, raw, payload)
    assert run(doc, raw)["overall_status"] == "rejected"


def test_two_300bp_reads_do_not_establish_a_contiguous_600bp_fragment():
    doc, raw, payload, constraints = fixture(); constraints["sequencing"]["PE300_is_guaranteed_contiguous_600bp"] = True
    rebind(doc, raw, constraints, "method_constraints_snapshot_sha256")
    payload["records"][0]["method_constraints_binding"]["sha256"] = doc["method_constraints_snapshot_sha256"]
    rebind(doc, raw, payload)
    assert run(doc, raw)["overall_status"] == "rejected"


def test_missing_source_bytes_require_review_and_tampered_bytes_are_rejected():
    doc, raw, payload, _ = fixture(); key = payload["records"][0]["source_record_binding"]["sha256"]
    missing = copy.copy(raw); missing.pop(key)
    assert run(doc, missing)["requirements_consistency_counts"]["review_required"] == 1
    raw[key] = b"{}"
    assert run(doc, raw)["overall_status"] == "rejected"


def context_fixture(strand="+"):
    from bioevidence_validator.canine import reverse_complement
    doc, raw, payload, constraints = fixture()
    sequence = "A" * 101 + "C" * 99 + "G" * 103 + "T" * 97
    target = sequence if strand == "+" else reverse_complement(sequence)
    source = f">NC_000001.1:1-400 Canis lupus familiaris, CanFam3.1, whole genome shotgun sequence\n{sequence}\n".encode()
    source_hash = hashlib.sha256(source).hexdigest(); raw[source_hash] = source
    receipt = {"reference_sha256": "a" * 64, "queries": {"authored": {"chrom": "chr1", "start0": 0,
        "end0": 400, "sequence": target, "sequence_sha256": hashlib.sha256(target.encode()).hexdigest()}}}
    rebind(doc, raw, receipt, "target_reference_receipt_snapshot_sha256")
    left, right, start = (200, 201, 198) if strand == "+" else (201, 200, 203)
    mapping = {"source_event_id": "authored:1", "source_accession_version": "NC_000001.1", "source_assembly": "CanFam3.1",
        "source_start1": 1, "source_end1": 400, "source_after_base1": 200, "target_start1": 1, "target_end1": 400,
        "target_after_base1": 200, "target_strand": strand, "target_chrom": "chr1", "target_query_key": "authored",
        "target_reference_sha256": "a" * 64, "original_request_lossless": {"TSD_bp": 3},
        "point_candidate_mappings": {"insertion_left": [["chr1", left, strand]], "insertion_right": [["chr1", right, strand]],
            "tsd_start": [["chr1", start, strand]], "tsd_end": [["chr1", left, strand]]}}
    rebind(doc, raw, {"rows": [mapping]}, "context_mapping_snapshot_sha256")
    checks = {"mapping_file_sha256": doc["context_mapping_snapshot_sha256"],
        "target_receipt_sha256": doc["target_reference_receipt_snapshot_sha256"], "rows": [{"source_event_id": "authored:1",
        "mapping_lossless": copy.deepcopy(mapping), "source_file_sha256": source_hash,
        "complete_source_target_window_equal": True, "TSD_endpoint_geometry_verified": True}]}
    rebind(doc, raw, checks, "context_checks_snapshot_sha256")
    templates = {"context_checks_sha256": doc["context_checks_snapshot_sha256"], "records": [{"id": "authored:WT",
        "event_ids": ["authored:1"], "sequence": sequence[100:300], "sequence_length_bp": 200,
        "sequence_sha256": hashlib.sha256(sequence[100:300].encode()).hexdigest(), "reference_derived": True,
        "complete_source_window_exact": True, "observed_target_mutant_sequence": False,
        "assay_validated": False, "probe_ready": False, "orderable": False, "reportable": False}]}
    rebind(doc, raw, templates, "templates_snapshot_sha256")
    return doc, raw, mapping, checks, templates, receipt


def context_rebind(doc, raw, mapping, checks, templates):
    rebind(doc, raw, {"rows": [mapping]}, "context_mapping_snapshot_sha256")
    checks["mapping_file_sha256"] = doc["context_mapping_snapshot_sha256"]
    checks["mapping_lossless"] = mapping
    checks["rows"][0]["mapping_lossless"] = copy.deepcopy(mapping)
    rebind(doc, raw, checks, "context_checks_snapshot_sha256")
    templates["context_checks_sha256"] = doc["context_checks_snapshot_sha256"]
    rebind(doc, raw, templates, "templates_snapshot_sha256")


@pytest.mark.parametrize("strand", ["+", "-"])
def test_independent_endpoint_math_and_oriented_WT_bytes(strand):
    doc, raw, *_ = context_fixture(strand)
    report = run(doc, raw)
    assert report["context_checks"][0]["engineering_status"] == "verified"
    assert report["context_checks"][0]["computed_endpoint_geometry_consistent"] is True
    assert report["template_checks"][0]["engineering_status"] == "verified"
    assert report["overall_status"] == "review_required"


@pytest.mark.parametrize("point", ["insertion_left", "insertion_right", "tsd_start", "tsd_end"])
def test_cached_TSD_acceptance_cannot_hide_an_endpoint_error(point):
    doc, raw, mapping, checks, templates, _ = context_fixture()
    mapping["point_candidate_mappings"][point][0][1] += 1
    context_rebind(doc, raw, mapping, checks, templates)
    assert run(doc, raw)["overall_status"] == "rejected"


def test_complete_window_difference_is_held_despite_matching_local_flanks():
    doc, raw, mapping, checks, templates, receipt = context_fixture()
    query = receipt["queries"]["authored"]; query["sequence"] = "T" + query["sequence"][1:]
    query["sequence_sha256"] = hashlib.sha256(query["sequence"].encode()).hexdigest()
    rebind(doc, raw, receipt, "target_reference_receipt_snapshot_sha256")
    checks["target_receipt_sha256"] = doc["target_reference_receipt_snapshot_sha256"]
    checks["rows"][0]["complete_source_target_window_equal"] = False
    templates["records"][0]["complete_source_window_exact"] = False
    context_rebind(doc, raw, mapping, checks, templates)
    report = run(doc, raw); context = report["context_checks"][0]
    assert context["complete_context_equal"] is False and context["local_100bp_each_flank_equal"] is True
    assert context["engineering_status"] == "review_required"
    assert report["overall_status"] == "review_required"
    checks["rows"][0]["complete_source_target_window_equal"] = True
    context_rebind(doc, raw, mapping, checks, templates)
    assert run(doc, raw)["overall_status"] == "rejected"


@pytest.mark.parametrize("case", ["absent_points", "multi_mapping", "malformed_points", "strand_object", "bad_direction",
    "null_request", "null_TSD", "negative_TSD", "wrong_anchor", "boolean_anchor", "no_cached_acceptance"])
def test_ambiguous_geometry_never_releases_templates(case):
    doc, raw, mapping, checks, templates, _ = context_fixture()
    if case == "absent_points": mapping.pop("point_candidate_mappings")
    if case == "multi_mapping": mapping["point_candidate_mappings"]["insertion_left"] *= 2
    if case == "malformed_points": mapping["point_candidate_mappings"] = []
    if case == "strand_object": mapping["point_candidate_mappings"]["insertion_left"][0][2] = {}
    if case == "bad_direction": mapping["point_candidate_mappings"]["insertion_right"][0][2] = "-"
    if case == "null_request": mapping["original_request_lossless"] = None
    if case == "null_TSD": mapping["original_request_lossless"]["TSD_bp"] = None
    if case == "negative_TSD": mapping["original_request_lossless"]["TSD_bp"] = -1
    if case == "wrong_anchor": mapping["target_after_base1"] += 1
    if case == "boolean_anchor": mapping["target_after_base1"] = True
    if case == "no_cached_acceptance":
        mapping["point_candidate_mappings"]["insertion_right"][0][1] += 1
        checks["rows"][0]["TSD_endpoint_geometry_verified"] = False
    context_rebind(doc, raw, mapping, checks, templates)
    report = run(doc, raw)
    if case == "null_TSD":
        assert report["context_checks"][0]["computed_endpoint_geometry_consistent"] is True
        assert report["context_checks"][0]["source_TSD_length_is_only_a_producer_assertion"] is True
    else:
        assert report["overall_status"] == "rejected"


@pytest.mark.parametrize("field,value", [("sequence", "N" * 200), ("sequence", "A" * 200),
    ("sequence_length_bp", 201), ("assay_validated", True), ("event_ids", ["missing"]),
    ("event_ids", [{}]), ("event_ids", "authored:1"), ("id", None)])
def test_template_integrity_and_linkage_errors_are_rejected(field, value):
    doc, raw, _, _, templates, _ = context_fixture(); templates["records"][0][field] = value
    rebind(doc, raw, templates, "templates_snapshot_sha256")
    assert run(doc, raw)["overall_status"] == "rejected"


def test_mutant_is_a_proposal_and_missing_WT_flanks_remain_held():
    doc, raw, mapping, checks, templates, _ = context_fixture()
    templates["records"][0]["reference_derived"] = False
    context_rebind(doc, raw, mapping, checks, templates)
    assert run(doc, raw)["template_checks"][0]["engineering_status"] == "review_required"
    checks["rows"][0].pop("source_file_sha256"); templates["records"][0]["complete_source_window_exact"] = False
    context_rebind(doc, raw, mapping, checks, templates)
    assert run(doc, raw)["template_checks"][0]["engineering_status"] == "review_required"


@pytest.mark.parametrize("case", ["mapping_shape", "check_shape", "duplicate_mapping", "duplicate_checks", "invalid_ID", "mapping_binding", "receipt_binding", "template_binding", "template_list", "template_row", "duplicate_template", "coordinate_missing", "coordinate_boolean", "source_missing", "source_accession_null"])
def test_context_input_errors_and_unknowns_are_explicit(case):
    doc, raw, mapping, checks, templates, _ = context_fixture()
    contexts = {"rows": [mapping]}
    if case == "mapping_shape": contexts["rows"] = "bad"
    if case == "check_shape": checks["rows"] = [None]
    if case == "duplicate_mapping": contexts["rows"] *= 2
    if case == "duplicate_checks": checks["rows"] *= 2
    if case == "invalid_ID": mapping["source_event_id"] = []
    if case == "mapping_binding": checks["mapping_file_sha256"] = "a" * 64
    if case == "receipt_binding": checks["target_receipt_sha256"] = "a" * 64
    if case == "template_binding": templates["context_checks_sha256"] = "a" * 64
    if case == "template_list": templates["records"] = "bad"
    if case == "template_row": templates["records"] = [None]
    if case == "duplicate_template": templates["records"] *= 2
    if case == "coordinate_missing": mapping.pop("source_start1")
    if case == "coordinate_boolean": mapping["source_start1"] = True
    if case == "source_missing": raw.pop(checks["rows"][0]["source_file_sha256"])
    if case == "source_accession_null":
        mapping["source_accession_version"] = None
        checks["rows"][0]["source_window_lossless"] = {"reviewed_fields": {"accession_version": "NC_000001.1"}}
    if case in {"coordinate_missing", "coordinate_boolean", "source_accession_null"}:
        checks["rows"][0]["mapping_lossless"] = copy.deepcopy(mapping)
    rebind(doc, raw, contexts, "context_mapping_snapshot_sha256")
    if case != "mapping_binding": checks["mapping_file_sha256"] = doc["context_mapping_snapshot_sha256"]
    rebind(doc, raw, checks, "context_checks_snapshot_sha256")
    if case != "template_binding": templates["context_checks_sha256"] = doc["context_checks_snapshot_sha256"]
    if case == "source_missing": templates["records"][0]["complete_source_window_exact"] = False
    rebind(doc, raw, templates, "templates_snapshot_sha256")
    report = run(doc, raw)
    assert report["overall_status"] == ("review_required" if case in {"source_missing", "source_accession_null"} else "rejected")


@pytest.mark.parametrize("kind,token", [("DELETION", "local_allele_or_breakpoint_sequence_evidence"),
    ("COMPOUND", "all_components_and_same_allele_phase"), ("INVERSION", "both_orientation_junctions")])
def test_structural_routes_require_sequence_orientation_and_phase(kind, token):
    doc, raw, payload, _ = fixture(kind)
    assert run(doc, raw)["overall_status"] == "rejected"
    payload["records"][0]["required_ngs_evidence"] = [token]; rebind(doc, raw, payload)
    assert run(doc, raw)["requirements_consistency_counts"]["verified"] == 1


@pytest.mark.parametrize("case", ["schema", "unknown_kind", "method", "X_calibration", "source_lossless", "source_bytes",
    "source_identity", "method_binding", "interpretation_type", "counterevidence_held", "samples", "payload_held", "final_baits"])
def test_source_requirements_errors_and_remaining_evidence(case):
    doc, raw, payload, _ = fixture(); row = payload["records"][0]
    if case == "schema": row.pop("scope")
    if case == "unknown_kind": row["plan_kind"] = "bad"
    if case == "method": row["primary_product_method"] = "PCR"
    if case == "X_calibration": row["sex_ploidy_calibration_required"] = False
    if case == "source_lossless": row["source_event_requirements_lossless"]["extra"] = "unsupported change"
    if case == "source_bytes": row["source_record_binding"]["bytes"] = 1
    if case == "source_identity": row["gene"] = "other"
    if case == "method_binding": row["method_constraints_binding"]["sha256"] = "a" * 64
    if case == "interpretation_type": row["interpretation_review"] = []
    if case == "counterevidence_held": row["interpretation_review"] = {"counterevidence_pmids": ["authored"], "causal_disease_claim_accepted": False}
    if case == "samples": row["coverage_and_performance"]["actual_experimental_samples"] = 1
    if case == "payload_held": row["source_payload_sequence_held"] = True
    if case == "final_baits": row["capture_design"].update(final_baits=["authored"], final_capture_intervals=["authored"])
    rebind(doc, raw, payload)
    report = run(doc, raw)
    assert report["overall_status"] == ("review_required" if case in {"counterevidence_held", "samples", "payload_held", "final_baits"} else "rejected")


@pytest.mark.parametrize("case", ["wrong_taxon", "duplicate_ID", "empty_ID", "empty_records", "count", "list_payload", "constraints_list", "constraint_groups", "source_json_list", "source_duplicate_json", "nonfinite", "global_claim"])
def test_strict_snapshots_fail_closed(case):
    doc, raw, payload, constraints = fixture()
    if case == "wrong_taxon": doc["taxon"] = "NCBITaxon:9606"
    if case == "duplicate_ID": payload["records"] *= 2; payload["source_id_count"] = 2
    if case == "empty_ID": payload["records"][0]["event_id"] = ""
    if case == "empty_records": payload["records"] = []
    if case == "count": payload["source_id_count"] = True
    if case == "list_payload": payload = []
    if case == "global_claim": payload["orderable"] = True
    if case == "constraints_list": constraints = []
    if case == "constraint_groups": constraints["sequencing"] = []
    if case in {"constraints_list", "constraint_groups"}: rebind(doc, raw, constraints, "method_constraints_snapshot_sha256")
    if case in {"source_json_list", "source_duplicate_json", "nonfinite"}:
        content = b"[]" if case == "source_json_list" else b'{"a":1,"a":2}' if case == "source_duplicate_json" else b'{"a":NaN}'
        key = hashlib.sha256(content).hexdigest(); raw[key] = content; payload["records"][0]["source_record_binding"]["sha256"] = key
    rebind(doc, raw, payload)
    if case in {"wrong_taxon", "duplicate_ID", "empty_ID", "empty_records", "count", "list_payload"}:
        with pytest.raises(ValueError): run(doc, raw)
    else:
        report = run(doc, raw)
        assert report["overall_status"] == "rejected"


def test_actual154_development_fixture_preserves_scope_and_holds():
    from bioevidence_validator.canine_capture import validate_canine_capture
    root = Path(__file__).resolve().parents[1] / "examples/canine_capture"
    report = validate_canine_capture(json.loads((root / "panel.json").read_text()), SnapshotStore.from_directory(root / "sources"))
    assert report["source_route_count"] == 154
    assert report["requirements_consistency_counts"] == {"verified": 154, "review_required": 0, "rejected": 0}
    assert sum(x["complete_context_equal"] is True for x in report["context_checks"]) == 8
    assert sum(x["complete_context_equal"] is False for x in report["context_checks"]) == 11
    assert sum(x["complete_context_equal"] is None for x in report["context_checks"]) == 6
    assert report["overall_status"] == "review_required"
    assert report["experimental_samples_evaluated"] == 0


def test_capture_CLI_review_error_and_input_protection(tmp_path, capsys):
    from bioevidence_validator.cli import main
    doc, raw, *_ = fixture(); source = tmp_path / "sources"; source.mkdir()
    for key, value in raw.items(): (source / key).write_bytes(value)
    path = tmp_path / "input.json"; path.write_text(json.dumps(doc)); output = tmp_path / "report.json"
    args = ["canine-capture", str(path), "--snapshot-dir", str(source)]
    assert main(args + ["--output", str(output)]) == 2
    assert json.loads(output.read_text())["overall_status"] == "review_required"
    assert main(args) == 2
    assert main(args + ["--output", str(path)]) == 3
    assert main(args + ["--output", str(source / "unsafe.json")]) == 3
    path.write_text('{"a":1,"a":2}')
    assert main(args) == 3
    assert "input_or_execution_error" in capsys.readouterr().err


def registry_fixture():
    doc, raw, payload, _ = fixture("DELETION"); row = payload["records"][0]
    original = {"event_id": "authored:1", "gene": "F8", "source_chrom": "1",
        "proposed_detection": "MULTI_REGION_DOSAGE_PLUS_DELETION_JUNCTION"}
    parts = [{"event_id": "authored:1", "part": "1", "required_parts": "1"}]

    def bind(rows):
        fields = list(rows[0]); data = ("\t".join(fields) + "\n" + "\n".join("\t".join(r[k] for k in fields) for r in rows) + "\n").encode()
        key = hashlib.sha256(data).hexdigest(); raw[key] = data
        return {"sha256": key, "bytes": len(data)}

    row.pop("source_event_requirements_lossless")
    row["source_registry_row_lossless"] = original; row["source_record_binding"] = bind([original])
    row["source_parts_lossless"] = parts; row["source_parts_binding"] = bind(parts)
    row["source_payload_sequence_held"] = False
    row["required_ngs_evidence"] = ["local_allele_or_breakpoint_sequence_evidence"]
    rebind(doc, raw, payload)
    return doc, raw, payload, bind


@pytest.mark.parametrize("case", ["consistent", "duplicate_source", "wrong_gene", "wrong_route", "lost_parts",
    "bad_part_binding", "wrong_parts", "missing_part_bytes", "source_utf8", "part_utf8", "null_source_plan"])
def test_registry_and_components_are_bound_to_actual_bytes(case):
    doc, raw, payload, bind = registry_fixture(); row = payload["records"][0]
    if case == "duplicate_source": row["source_record_binding"] = bind([row["source_registry_row_lossless"]]*2)
    if case == "wrong_gene": row["source_registry_row_lossless"]["gene"] = "other"
    if case == "wrong_route": row["plan_kind"] = "SMALL_ALLELE"
    if case == "lost_parts": row.pop("source_parts_binding")
    if case == "bad_part_binding": row["source_parts_binding"] = []
    if case == "wrong_parts": row["source_parts_lossless"][0]["part"] = "2"
    if case == "missing_part_bytes": raw.pop(row["source_parts_binding"]["sha256"])
    if case in {"source_utf8", "part_utf8", "null_source_plan"}:
        content = b"null" if case == "null_source_plan" else b"\xff"
        key = hashlib.sha256(content).hexdigest(); raw[key] = content
        row["source_record_binding" if case != "part_utf8" else "source_parts_binding"] = {"sha256": key}
        if case == "null_source_plan": row["source_event_requirements_lossless"] = {}
    rebind(doc, raw, payload); report = run(doc, raw)
    assert report["overall_status"] == ("review_required" if case in {"consistent", "missing_part_bytes"} else "rejected")


@pytest.mark.parametrize("name", ["context_mapping", "context_checks", "target_reference_receipt", "templates"])
def test_optional_snapshot_root_type_is_checked(name):
    doc, raw, *_ = context_fixture(); rebind(doc, raw, [], f"{name}_snapshot_sha256")
    assert run(doc, raw)["overall_status"] == "rejected"


def test_missing_top_snapshots_are_unknown_and_JSON_null_is_an_error():
    doc, raw, *_ = fixture(); raw.pop(doc["requirements_snapshot_sha256"])
    report = run(doc, raw)
    assert report["overall_status"] == "review_required" and report["source_route_count"] == 0
    data = b"null"; key = hashlib.sha256(data).hexdigest(); raw[key] = data
    doc["requirements_snapshot_sha256"] = key
    assert run(doc, raw)["overall_status"] == "rejected"


def test_unknown_insert_payload_hold_is_derived_from_bound_components():
    doc, raw, payload, bind = registry_fixture(); row = payload["records"][0]
    parts = [{"event_id": "authored:1", "part": "1", "operation": "ins", "inserted_sequence": ""}]
    row["source_parts_binding"] = bind(parts); row["source_parts_lossless"] = parts
    rebind(doc, raw, payload)
    assert run(doc, raw)["overall_status"] == "rejected"
    row["source_payload_sequence_held"] = True; rebind(doc, raw, payload)
    assert run(doc, raw)["requirements_consistency_counts"]["verified"] == 1
    assert "INSERTION_PAYLOAD_OR_TSD_NOT_RECOVERED" in run(doc, raw)["events"][0]["unresolved_evidence"]
