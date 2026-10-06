"""Canine NGS requirements consistency and reference-boundary replay, offline.

This validates the draft's contract, not biological causality, phase, probe
chemistry or assay performance. A trusted producer is still needed for reference
receipts. No output grants experimental validation, ordering or reporting.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from . import __version__
from .canine import HASH, TEXT, VariantProblem, _unique_json, load_reference, reverse_complement, sha
from .grounding import SnapshotStore

SNAPSHOTS = ("requirements", "method_constraints", "context_mapping", "context_checks",
             "target_reference_receipt", "templates")
SCHEMA = {"type": "object", "additionalProperties": False,
    "required": ["format_version", "taxon", "requirements_snapshot_sha256", "method_constraints_snapshot_sha256"],
    "properties": {"format_version": {"const": "canine-capture-1"}, "taxon": {"const": "NCBITaxon:9615"},
        **{f"{name}_snapshot_sha256": HASH for name in SNAPSHOTS}},
    "dependentRequired": {
        "context_checks_snapshot_sha256": ["context_mapping_snapshot_sha256", "target_reference_receipt_snapshot_sha256"],
        "templates_snapshot_sha256": ["context_mapping_snapshot_sha256", "context_checks_snapshot_sha256",
                                      "target_reference_receipt_snapshot_sha256"]}}
BINDING = {"type": "object", "required": ["sha256"], "properties": {"sha256": HASH}}
ROW_SCHEMA = {"type": "object", "required": ["event_id", "gene", "plan_kind", "scope", "primary_product_method",
    "source_record_binding", "method_constraints_binding", "required_ngs_evidence", "capture_design",
    "coverage_and_performance", "inconclusive_rule_zh", "event_specific_limits_zh", "assay_validated",
    "probe_ready", "orderable", "reportable", "germline_panel_admission_approved"],
    "properties": {**{k: TEXT for k in ["event_id", "gene", "plan_kind", "scope", "primary_product_method",
                                      "inconclusive_rule_zh", "event_specific_limits_zh"]},
        "source_record_binding": BINDING, "method_constraints_binding": BINDING,
        "required_ngs_evidence": {"type": "array", "minItems": 1, "uniqueItems": True, "items": TEXT},
        "capture_design": {"type": "object", "required": ["requirements_zh", "final_baits", "final_capture_intervals"],
            "properties": {"requirements_zh": TEXT}},
        "coverage_and_performance": {"type": "object", "required": ["actual_experimental_samples", "minimum_effective_depth"],
            "properties": {"actual_experimental_samples": {"type": "integer", "minimum": 0},
                           "minimum_effective_depth": {"type": ["number", "null"], "exclusiveMinimum": 0}}},
        **{k: {"type": "boolean"} for k in ["assay_validated", "probe_ready", "orderable", "reportable",
            "germline_panel_admission_approved", "normal_copy_number_excludes_event", "total_copy_number_establishes_phase",
            "PE300_guarantees_complete_repeat_length", "sex_ploidy_calibration_required", "source_payload_sequence_held"]}}}
KINDS = {"SMALL", "SMALL_ALLELE", "LOCAL_DEL", "AUTOSOMAL_DEL", "X_DEL", "UNKNOWN_DEL", "MOSAIC_DEL",
    "INSERTION", "X_INSERTION", "POLY", "PMEL", "TANDEM", "X_TANDEM", "CN_TOTAL", "CN_PHASE", "VNTR",
    "HAPLOTYPE", "EXPANSION", "COMPLEX", "X_COMPLEX", "X_INVERSION", "RNA", "SOMATIC", "DELETION",
    "DUPLICATION", "REPLACEMENT", "COMPOUND", "INVERSION"}
ROUTE_KINDS = {"LOCAL_SMALL_ALLELE_ASSAY": "SMALL_ALLELE", "LOCAL_SMALL_ALLELE_ASSEMBLY": "REPLACEMENT",
    "INSERTION_JUNCTIONS_AND_INSERT_SEQUENCE": "INSERTION", "TWO_RECIPROCAL_INVERSION_JUNCTIONS": "INVERSION",
    "MULTI_REGION_DOSAGE_PLUS_DELETION_JUNCTION": "DELETION",
    "MULTI_REGION_DOSAGE_PLUS_DUPLICATION_ORIENTATION": "DUPLICATION",
    "MULTI_REGION_DOSAGE_PLUS_REPLACEMENT_JUNCTION": "REPLACEMENT", "ALL_COMPONENTS_PLUS_PHASE": "COMPOUND"}
FLAGS = ("assay_validated", "probe_ready", "orderable", "reportable", "germline_panel_admission_approved",
         "PE300_guarantees_complete_repeat_length", "total_copy_number_establishes_phase", "normal_copy_number_excludes_event",
         "copy_count_from_shared_FGF4_coding_reads_is_locus_specific", "dosage_regions_independent_verified")
GENOMIC = "GENOMIC_CANDIDATE_TARGET_IN_DRAFT_NOT_ADMITTED"
RNA = "RNA_ONLY_SOURCE_GDNA_CAUSAL_ANCHOR_HELD"
SOMATIC = "LESION_SOMATIC_RESEARCH_NOT_GERMLINE_SCREENING"


def _note(findings: list[dict[str, str]], code: str, message: str, path: str) -> None:
    findings.append({"rule_id": code, "severity": "review" if code == "BEV015" else "error",
                     "message": message, "field_path": path})


def _status(findings: list[dict[str, str]]) -> str:
    return "rejected" if any(x["severity"] == "error" for x in findings) else "review_required" if findings else "verified"


def _bytes(key: str, store: SnapshotStore, findings: list[dict[str, str]], path: str) -> bytes | None:
    data = store.get(key)
    if data is None:
        _note(findings, "BEV015", "Frozen source bytes are unavailable.", path)
        return None
    if not store.verified(key):
        _note(findings, "BEV014", "Actual snapshot bytes disagree with the frozen SHA-256.", path)
        return None
    return data


def _nonfinite(_: str) -> None:
    raise ValueError("Non-finite JSON number is not supported")


def _json(key: str, store: SnapshotStore, findings: list[dict[str, str]], path: str) -> Any:
    raw = _bytes(key, store, findings, path)
    if raw is None:
        return None
    try:
        value = json.loads(raw, object_pairs_hook=_unique_json, parse_constant=_nonfinite)
        if value is None:
            raise ValueError("Snapshot cannot be JSON null")
        return value
    except (ValueError, UnicodeError, RecursionError):
        _note(findings, "BEV024", "Snapshot is not unique-key, finite, supported JSON.", path)
        return None


def _source(row: dict[str, Any], store: SnapshotStore, findings: list[dict[str, str]]) -> dict[str, Any] | None:
    binding = row["source_record_binding"]
    data = _bytes(binding["sha256"], store, findings, "source_record_binding")
    if data is None:
        return None
    if "bytes" in binding and (type(binding["bytes"]) is not int or binding["bytes"] != len(data)):
        _note(findings, "BEV017", "Source byte count disagrees with the frozen binding.", "source_record_binding.bytes")
    if "source_event_requirements_lossless" in row:
        original = _json(binding["sha256"], store, findings, "source_record_binding")
        if not isinstance(original, dict):
            if original is not None:
                _note(findings, "BEV024", "Original source plan must be a JSON object.", "source_record_binding")
            return None
        if original != row["source_event_requirements_lossless"]:
            _note(findings, "BEV017", "Claimed original requirements differ from actual source JSON.", "source_event_requirements_lossless")
        if (original.get("event_id") != row["event_id"] or original.get("gene_original") != row["gene"]
                or original.get("plan_kind") != row["plan_kind"]):
            _note(findings, "BEV017", "Event identity, gene or kind differs from the frozen source plan.", "event_id/gene/plan_kind")
        return original
    try:
        values = list(csv.DictReader(io.StringIO(data.decode("utf-8")), delimiter="\t"))
        matches = [x for x in values if x.get("event_id") == row["event_id"]]
    except UnicodeError:
        matches = []
    if len(matches) != 1:
        _note(findings, "BEV016", "Source registry does not contain exactly one matching event ID.", "event_id")
        return None
    original = matches[0]
    if original != row.get("source_registry_row_lossless") or original.get("gene") != row["gene"]:
        _note(findings, "BEV017", "Original registry row or gene was changed.", "source_registry_row_lossless")
    if ROUTE_KINDS.get(original.get("proposed_detection", "")) != row["plan_kind"]:
        _note(findings, "BEV017", "Source route and declared kind disagree.", "plan_kind")
    part_binding = row.get("source_parts_binding", {})
    if not isinstance(part_binding, dict) or not isinstance(part_binding.get("sha256"), str):
        _note(findings, "BEV024", "Registry routes require a bound source component table.", "source_parts_binding")
        return original
    raw_parts = _bytes(part_binding["sha256"], store, findings, "source_parts_binding")
    if raw_parts is not None:
        try:
            actual = [x for x in csv.DictReader(io.StringIO(raw_parts.decode("utf-8")), delimiter="\t") if x.get("event_id") == row["event_id"]]
        except UnicodeError:
            actual = []
        if not actual or actual != row.get("source_parts_lossless"):
            _note(findings, "BEV017", "Required components differ from the frozen source table.", "source_parts_lossless")
        payload_held = any(p.get("operation") in {"ins", "delins"} and not p.get("inserted_sequence") for p in actual)
        if row.get("source_payload_sequence_held") is not payload_held:
            _note(findings, "BEV017", "Unknown insertion payload hold disagrees with the actual source components.", "source_payload_sequence_held")
    return original


def _requirements(row: dict[str, Any], store: SnapshotStore, constraints_hash: str) -> dict[str, Any]:
    result: dict[str, Any] = {"event_id": row.get("event_id"), "findings": [], "unresolved_evidence": [
        "NO_INDEPENDENT_PANEL_EXPERIMENTAL_PERFORMANCE", "EFFECTIVE_READ_AND_FRAGMENT_DISTRIBUTIONS_NOT_ESTABLISHED"],
        "design_status": "review_required", "assay_validated": False, "orderable": False, "reportable": False}
    f = result["findings"]
    errors = list(Draft202012Validator(ROW_SCHEMA).iter_errors(row))
    if errors:
        for error in errors:
            _note(f, "BEV024", error.message, str(list(error.path)))
        result["requirements_status"] = "rejected"
        return result
    original = _source(row, store, f)
    kind = row["plan_kind"]
    if kind not in KINDS or row["primary_product_method"] != "NGS_HYBRID_CAPTURE_PREFERRED_PE300":
        _note(f, "BEV024", "Unsupported event kind or product method.", "plan_kind/primary_product_method")
    if row["method_constraints_binding"]["sha256"] != constraints_hash:
        _note(f, "BEV017", "Row binds a different method parameter snapshot.", "method_constraints_binding")
    for flag in FLAGS:
        if flag in row and row[flag] is not False:
            _note(f, "BEV017", "Requirements metadata cannot establish admission, phase, repeat length or assay readiness.", flag)
    scope = RNA if kind == "RNA" else SOMATIC if kind == "SOMATIC" else GENOMIC
    if row["scope"] != scope:
        _note(f, "BEV017", "Source measurement scope cannot be silently promoted to germline DNA.", "scope")
    result["scope"] = row["scope"]
    if scope != GENOMIC:
        result["unresolved_evidence"].append("GDNA_GERMLINE_TARGET_NOT_ESTABLISHED")
    is_x = kind.startswith("X_") or bool(original and str(original.get("source_chrom", "")).removeprefix("chr") == "X")
    if is_x and row.get("sex_ploidy_calibration_required") is not True:
        _note(f, "BEV017", "X source requires explicit sex/ploidy calibration.", "sex_ploidy_calibration_required")
    evidence = set(row["required_ngs_evidence"])
    if kind in {"X_INVERSION", "INVERSION"}:
        required = {"orientation_junction_evidence", "both_breakend_contexts_if_established"} if kind == "X_INVERSION" else {"both_orientation_junctions"}
        if not required <= evidence:
            _note(f, "BEV017", "Dosage or one generic junction cannot define a reciprocal inversion.", "required_ngs_evidence")
    if kind == "DELETION" and "local_allele_or_breakpoint_sequence_evidence" not in evidence:
        _note(f, "BEV017", "A length label or overlapping windows cannot establish a deletion by dosage alone.", "required_ngs_evidence")
    if kind == "COMPOUND" and "all_components_and_same_allele_phase" not in evidence:
        _note(f, "BEV017", "Compound alleles require every component and same-allele phase.", "required_ngs_evidence")
    if row["capture_design"]["final_capture_intervals"] is None or row["capture_design"]["final_baits"] is None:
        result["unresolved_evidence"].append("FINAL_CAPTURE_NOT_DEFINED")
    else:
        result["unresolved_evidence"].append("BAIT_CHEMISTRY_AND_PERFORMANCE_NOT_ASSESSED")
    if row["coverage_and_performance"]["actual_experimental_samples"]:
        _note(f, "BEV015", "This input supplies a sample count, not independent assay performance evidence.", "coverage_and_performance")
    if row.get("source_payload_sequence_held"):
        result["unresolved_evidence"].append("INSERTION_PAYLOAD_OR_TSD_NOT_RECOVERED")
    review = row.get("interpretation_review", {})
    if not isinstance(review, dict):
        _note(f, "BEV024", "Interpretation review must be an object.", "interpretation_review")
    if isinstance(review, dict):
        if any(review[k] is not False for k in ["causal_disease_claim_accepted", "population_generalization_accepted"] if k in review):
            _note(f, "BEV017", "This contract cannot establish a causal or population-wide disease interpretation.", "interpretation_review")
        if review.get("counterevidence_pmids"):
            result["unresolved_evidence"].append("DISEASE_ASSOCIATION_CONFLICT_REQUIRES_REVIEW")
    result["requirements_status"] = _status(f)
    return result


def _point(mapping: dict[str, Any], name: str) -> tuple[str, int, str] | None:
    points = mapping.get("point_candidate_mappings", {})
    if not isinstance(points, dict):
        return None
    values = points.get(name, [])
    if (not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], list)
            or len(values[0]) != 3):
        return None
    chrom, pos, strand = values[0]
    return (chrom, pos, strand) if isinstance(chrom, str) and type(pos) is int and pos > 0 and isinstance(strand, str) and strand in {"+", "-"} else None


def _geometry(mapping: dict[str, Any]) -> bool | None:
    left, right = _point(mapping, "insertion_left"), _point(mapping, "insertion_right")
    if left is None or right is None:
        return None
    sign = 1 if left[2] == "+" else -1
    if left[0] != right[0] or left[2] != right[2] or right[1] - left[1] != sign:
        return False
    if (mapping.get("target_strand", left[2]) != left[2] or mapping.get("target_chrom", left[0]) != left[0]
            or type(mapping.get("target_after_base1", min(left[1], right[1]))) is not int
            or mapping.get("target_after_base1", min(left[1], right[1])) != min(left[1], right[1])):
        return False
    original = mapping.get("original_request_lossless", {})
    if not isinstance(original, dict):
        return None
    size = original.get("TSD_bp")
    if size is None or (type(size) is int and size == 0):
        return True  # boundary consistency only; no TSD sequence/biology claim
    start, end = _point(mapping, "tsd_start"), _point(mapping, "tsd_end")
    if type(size) is not int or size < 1 or start is None or end is None:
        return None
    return (start[0] == end[0] == left[0] and start[2] == end[2] == left[2]
            and (end[1] - start[1]) * sign + 1 == size and end[1] == left[1])


def _contexts(document: dict[str, Any], parsed: dict[str, Any], store: SnapshotStore,
              findings: list[dict[str, str]]) -> list[dict[str, Any]]:
    mapping = parsed.get("context_mapping")
    checks = parsed.get("context_checks")
    if not isinstance(mapping, dict) or not isinstance(checks, dict):
        return []
    rows = mapping.get("rows", [])
    checked_rows = checks.get("rows", [])
    if (not isinstance(rows, list) or not isinstance(checked_rows, list)
            or any(not isinstance(r, dict) or not isinstance(r.get("source_event_id"), str) or not r["source_event_id"] for r in rows + checked_rows)):
        _note(findings, "BEV024", "Context snapshots need source-ID row lists.", "context_snapshots")
        return []
    checked = {r.get("source_event_id"): r for r in checked_rows}
    if len(checked) != len(checked_rows) or len({r.get("source_event_id") for r in rows}) != len(rows):
        _note(findings, "BEV024", "Context snapshots contain duplicate source IDs.", "context_snapshots")
        return []
    if checks.get("mapping_file_sha256") != document["context_mapping_snapshot_sha256"]:
        _note(findings, "BEV017", "Context checks bind a different mapping snapshot.", "mapping_file_sha256")
    if checks.get("target_receipt_sha256") != document["target_reference_receipt_snapshot_sha256"]:
        _note(findings, "BEV017", "Context checks bind a different target receipt.", "target_receipt_sha256")
    result = []
    for row in rows:
        event = row.get("source_event_id")
        context = checked.get(event, {})
        f: list[dict[str, str]] = []
        geometry = _geometry(row)
        output: dict[str, Any] = {"source_event_id": event, "computed_endpoint_geometry_consistent": geometry,
            "complete_context_equal": None, "local_100bp_each_flank_equal": None, "findings": f,
            "source_TSD_length_is_only_a_producer_assertion": True}
        if context.get("mapping_lossless") != row:
            _note(f, "BEV017", "Check row does not preserve its actual mapping source.", "mapping_lossless")
        if context.get("TSD_endpoint_geometry_verified") is True and geometry is not True:
            _note(f, "BEV017", "Cached endpoint acceptance contradicts actual point geometry.", "TSD_endpoint_geometry_verified")
        if geometry is False:
            _note(f, "BEV015", "Endpoint span, direction or insertion adjacency remains held.", "point_candidate_mappings")
        if geometry is None:
            _note(f, "BEV015", "Endpoint mapping is absent or ambiguous.", "point_candidate_mappings")
        source_hash = context.get("source_file_sha256")
        if isinstance(source_hash, str) and "target_query_key" in row:
            try:
                coordinates = [row[k] for k in ["source_start1", "source_end1", "target_start1", "target_end1",
                                               "source_after_base1", "target_after_base1"]]
                if not all(type(v) is int and v > 0 for v in coordinates) or row["target_strand"] not in {"+", "-"}:
                    raise VariantProblem("BEV024", "Window coordinates/strand have unsupported types or values.")
                accession = row.get("source_accession_version")
                if accession is None:
                    followup = context.get("source_window_lossless", {}).get("reviewed_fields", {})
                    accession = followup.get("accession_version")
                    _note(f, "BEV015", "Original accession remains null; follow-up accession is a producer assertion, not independently replayed assembly mapping.", "source_accession_version")
                source = load_reference({"snapshot_sha256": source_hash, "format": "ncbi_fasta",
                    "assembly": row["source_assembly"], "sequence_id": accession}, store)
                target = load_reference({"snapshot_sha256": document["target_reference_receipt_snapshot_sha256"],
                    "format": "reference_receipt_json", "assembly": "ROSY_custom", "sequence_id": row["target_chrom"],
                    "query_key": row["target_query_key"], "reference_sha256": row["target_reference_sha256"]}, store)
                if (source.start1, source.end1, target.start1, target.end1) != (
                        row["source_start1"], row["source_end1"], row["target_start1"], row["target_end1"]):
                    raise VariantProblem("BEV017", "Actual source/target intervals disagree with the mapping window.")
                oriented = target.sequence if row["target_strand"] == "+" else reverse_complement(target.sequence)
                source_offset = row["source_after_base1"] - source.start1 + 1
                target_offset = row["target_after_base1"] - target.start1 + 1 if row["target_strand"] == "+" else target.end1 - row["target_after_base1"]
                if source_offset != target_offset:
                    _note(f, "BEV015", "Relative insertion offsets disagree; no normalization is inferred.", "source_target_offsets")
                exact = source.sequence == oriented and "N" not in source.sequence + oriented
                output["complete_context_equal"] = exact
                if context.get("complete_source_target_window_equal") is True and not exact:
                    _note(f, "BEV017", "Cached complete-window acceptance contradicts actual sequence bytes.", "complete_source_target_window_equal")
                if 100 <= source_offset <= len(source.sequence) - 100 and 100 <= target_offset <= len(oriented) - 100:
                    left, right = oriented[target_offset-100:target_offset], oriented[target_offset:target_offset+100]
                    local = (source.sequence[source_offset-100:source_offset+100] == left+right and "N" not in left+right)
                    output.update(local_100bp_each_flank_equal=local, target_left100=left, target_right100=right)
                if not exact:
                    _note(f, "BEV015", "Complete window difference/ambiguity retained even if local flanks match.", "complete_context")
            except VariantProblem as problem:
                _note(f, problem.code, str(problem), "context_references")
            except (KeyError, TypeError, ValueError, AttributeError):
                _note(f, "BEV024", "Incomplete or malformed context coordinate metadata.", "context_references")
        else:
            _note(f, "BEV015", "Genomic anchor or source/target bytes remain unavailable.", "context_references")
        output["engineering_status"] = _status(f)
        result.append(output)
    return result


def _templates(document: dict[str, Any], parsed: dict[str, Any], contexts: list[dict[str, Any]],
               findings: list[dict[str, str]]) -> list[dict[str, Any]]:
    value = parsed.get("templates")
    if not isinstance(value, dict):
        return []
    if value.get("context_checks_sha256") != document["context_checks_snapshot_sha256"]:
        _note(findings, "BEV017", "Templates bind a different context check snapshot.", "context_checks_sha256")
    lookup = {x["source_event_id"]: x for x in contexts}
    result = []
    rows = value.get("records")
    if not isinstance(rows, list):
        _note(findings, "BEV024", "Templates need a record list.", "templates.records")
        return []
    seen: set[str] = set()
    for row in rows:
        f: list[dict[str, str]] = []
        if not isinstance(row, dict):
            _note(findings, "BEV024", "Template record is not an object.", "templates.records")
            continue
        sequence = row.get("sequence")
        identifier = row.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            _note(f, "BEV024", "Template ID must be a unique nonempty string.", "id")
        else:
            seen.add(identifier)
        if (not isinstance(sequence, str) or set(sequence) - set("ACGT") or not sequence
                or sha(sequence.encode()) != row.get("sequence_sha256") or len(sequence) != row.get("sequence_length_bp")):
            _note(f, "BEV017", "Template sequence, alphabet, length and SHA disagree.", "sequence")
        for flag in ["assay_validated", "probe_ready", "orderable", "reportable", "observed_target_mutant_sequence"]:
            if row.get(flag) is not False:
                _note(f, "BEV017", "A proposed context template does not establish observed mutant or assay readiness.", flag)
        ids = row.get("event_ids")
        if not isinstance(ids, list) or not ids or any(not isinstance(x, str) for x in ids):
            _note(f, "BEV024", "Template must link a nonempty source ID list.", "event_ids")
            ids = []
        linked = [lookup[x] for x in ids if x in lookup]
        if len(linked) != len(ids):
            _note(f, "BEV017", "Every template source ID needs a replayed context.", "event_ids")
        if not linked or any(x["computed_endpoint_geometry_consistent"] is not True or x["engineering_status"] == "rejected" for x in linked):
            _note(f, "BEV017", "Template requires consistent actual endpoints and source contexts.", "event_ids")
        if any(x["local_100bp_each_flank_equal"] is not True for x in linked):
            _note(f, "BEV015", "Actual WT flanks have not been confirmed for the candidate template.", "event_ids")
        if row.get("complete_source_window_exact") is True and any(x["complete_context_equal"] is not True for x in linked):
            _note(f, "BEV017", "Template complete-window claim is not supported by actual reference bytes.", "complete_source_window_exact")
        if row.get("reference_derived") is True and isinstance(sequence, str) and linked:
            if any("target_left100" in x and "target_right100" in x
                   and sequence != x["target_left100"] + x["target_right100"] for x in linked):
                _note(f, "BEV017", "WT boundary template differs from the actual target-reference flanks.", "sequence")
        if row.get("reference_derived") is not True:
            _note(f, "BEV015", "Proposed mutant payload reconstruction is not independently replayed by this contract.", "sequence")
        result.append({"id": row.get("id"), "engineering_status": _status(f), "findings": f,
            "mutant_sequence_reconstruction_performed": False, "capture_specificity_verified": False,
            "assay_validated": False, "orderable": False, "reportable": False})
    return result


def validate_canine_capture(document: dict[str, Any], store: SnapshotStore) -> dict[str, Any]:
    """Replay every source route and optional references. Always preserve holds."""
    errors = list(Draft202012Validator(SCHEMA).iter_errors(document))
    if errors:
        raise ValueError("Invalid canine-capture input: " + "; ".join(e.message for e in errors))
    findings: list[dict[str, str]] = []
    parsed = {name: _json(document[f"{name}_snapshot_sha256"], store, findings, name)
              for name in SNAPSHOTS if f"{name}_snapshot_sha256" in document}
    for name in ["context_mapping", "context_checks", "target_reference_receipt", "templates"]:
        if parsed.get(name) is not None and not isinstance(parsed[name], dict):
            _note(findings, "BEV024", "Optional reference/context snapshot must be a JSON object.", name)
    payload = parsed.get("requirements")
    records: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        candidate = payload.get("records")
        if (payload.get("schema") != "canine-all-ngs-route-requirements-1" or not isinstance(candidate, list)
                or not candidate or any(not isinstance(x, dict) for x in candidate)
                or type(payload.get("source_id_count")) is not int or payload["source_id_count"] != len(candidate)):
            raise ValueError("Requirements snapshot needs a supported nonempty source-ID record list and exact count")
        ids = [x.get("event_id") for x in candidate]
        if any(not isinstance(x, str) or not x for x in ids) or len(set(ids)) != len(ids):
            raise ValueError("Requirements snapshot has missing/duplicate source event IDs")
        records = candidate
        for flag in ["assay_validated", "probe_ready", "orderable", "reportable", "full_CNV_SV_completeness_verified"]:
            if payload.get(flag) is not False:
                _note(findings, "BEV017", "Requirements cannot establish global scientific readiness or completeness.", flag)
    elif payload is not None:
        raise ValueError("Requirements snapshot must be a JSON object")
    constraints = parsed.get("method_constraints")
    if isinstance(constraints, dict):
        seq = constraints.get("sequencing", {})
        primary = constraints.get("primary_method", {})
        enrichment = constraints.get("preferred_enrichment", {})
        if not all(isinstance(v, dict) for v in [seq, primary, enrichment]):
            _note(findings, "BEV024", "Method parameter groups must be objects.", "method_constraints")
        elif (constraints.get("schema") != "canine-ngs-capture-constraints-1"
                or primary.get("value") != "NGS"
                or enrichment.get("value") != "HYBRIDIZATION_CAPTURE"
                or seq.get("mode") != "PE300" or seq.get("paired_end") is not True
                or type(seq.get("read1_nominal_max_bp")) is not int or seq["read1_nominal_max_bp"] != 300
                or type(seq.get("read2_nominal_max_bp")) is not int or seq["read2_nominal_max_bp"] != 300
                or seq.get("PE300_is_guaranteed_contiguous_600bp") is not False):
            _note(findings, "BEV017", "Method parameters disagree with the confirmed NGS/capture/PE300 contract.", "method_constraints")
    elif constraints is not None:
        _note(findings, "BEV024", "Method constraints must be a JSON object.", "method_constraints")
    events = [_requirements(row, store, document["method_constraints_snapshot_sha256"]) for row in records]
    for event in events:
        method_issues = [x for x in findings if x["field_path"] == "method_constraints"]
        event["findings"].extend(method_issues)
        event["requirements_status"] = _status(event["findings"])
    contexts = _contexts(document, parsed, store, findings)
    templates = _templates(document, parsed, contexts, findings)
    errors_present = any(_status(x["findings"]) == "rejected" for x in events + contexts + templates)
    overall = "rejected" if _status(findings) == "rejected" or errors_present else "review_required"
    declared_hashes = {document[f"{n}_snapshot_sha256"] for n in SNAPSHOTS if f"{n}_snapshot_sha256" in document}
    for row in records:
        for name in ["source_record_binding", "source_parts_binding", "method_constraints_binding"]:
            binding = row.get(name)
            if isinstance(binding, dict) and isinstance(binding.get("sha256"), str):
                declared_hashes.add(binding["sha256"])
    checks = parsed.get("context_checks")
    if isinstance(checks, dict) and isinstance(checks.get("rows"), list):
        declared_hashes.update(x["source_file_sha256"] for x in checks["rows"]
                              if isinstance(x, dict) and isinstance(x.get("source_file_sha256"), str))
    return {"format_version": "canine-capture-report-1", "overall_status": overall,
        "requirements_consistency_counts": {s: sum(x["requirements_status"] == s for x in events) for s in ["verified", "review_required", "rejected"]},
        "validator": "canine-capture-1", "package_base_version": __version__,
        "source_route_count": len(events), "source_route_count_is_not_sample_or_unique_locus_count": True,
        "events": events, "context_checks": contexts, "template_checks": templates, "findings": findings,
        "input_sha256": sha(json.dumps(document, sort_keys=True, separators=(",", ":")).encode()),
        "implementation_sha256": {name: sha(Path(__file__).with_name(name).read_bytes())
                                  for name in ["canine_capture.py", "canine.py", "grounding.py"]},
        "source_snapshot_hashes": sorted(declared_hashes),
        "source_snapshot_hashes_are_declared_dependencies_not_all_verified": True,
        "scope": "Source-bound canine NGS draft consistency, independent endpoint arithmetic and pinned context replay only",
        "limitations": ["Does not authenticate receipt producers or rehash whole genomes/chains", "Mutant payloads, phase, capture chemistry, uniqueness and sample performance are not independently established", "Does not adjudicate disease causality or population-wide risk"],
        "clinical_interpretation_assessed": False, "whole_reference_specificity_performed": False,
        "experimental_samples_evaluated": 0, "assay_validated": False, "probe_ready": False,
        "orderable": False, "reportable": False}
