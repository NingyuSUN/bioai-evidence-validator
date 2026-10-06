"""Offline canine panel reference consistency, separate from evidence admission.

This consumes complete strings in a documented genomic HGVS subset. It is not a
general HGVS validator, a normalizer, a transcript mapper or an assay validator.
References are small, content-addressed NCBI slices or producer-pinned reference
receipts. A receipt binds the producer's assertions; it does not re-hash a whole
genome or authenticate the producer. Unsupported syntax always requires review.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from . import __version__
from .grounding import SnapshotStore

HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
TEXT = {"type": "string", "minLength": 1, "pattern": r"\S"}
POS = {"type": "integer", "minimum": 1}
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["format_version", "taxon", "references", "events"],
    "properties": {
        "format_version": {"const": "canine-panel-1"}, "taxon": {"const": "NCBITaxon:9615"},
        "references": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "assembly", "sequence_id", "snapshot_sha256", "format"],
            "properties": {"id": TEXT, "assembly": TEXT, "sequence_id": TEXT, "snapshot_sha256": HASH,
                "format": {"enum": ["ncbi_efetch_json", "ncbi_fasta", "reference_receipt_json"]},
                "query_key": TEXT, "reference_sha256": HASH},
            "allOf": [{"if": {"properties": {"format": {"const": "reference_receipt_json"}}},
                       "then": {"required": ["query_key", "reference_sha256"]}}]}},
        "events": {"type": "array", "minItems": 1, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "source_hgvs", "source_assembly"],
            "properties": {"id": TEXT, "gene": TEXT, "source_hgvs": {"type": "string"},
                "reviewed_hgvs": TEXT, "source_assembly": TEXT, "source_reference": TEXT,
                "target_reference": TEXT, "target_start1": POS, "target_end1": POS,
                "target_strand": {"enum": ["+", "-"]}, "target_assembly": TEXT,
                "event_ref": {"type": "string", "pattern": "^[ACGT]*$"},
                "event_alt": {"type": "string", "pattern": "^[ACGT]*$"},
                "held_reasons": {"type": "array", "items": TEXT}},
            "allOf": [{"if": {"required": ["target_reference"]}, "then": {"required": [
                "target_start1", "target_end1", "target_strand", "target_assembly"]}}]}}
    }
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise VariantProblem("BEV024", "Reference snapshot has duplicate JSON keys.")
        result[key] = value
    return result


def reverse_complement(sequence: str) -> str:
    return sequence.translate(str.maketrans("ACGTN", "TGCAN"))[::-1]


class VariantProblem(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _number(text: str) -> int:
    if len(text) > 18:
        raise VariantProblem("BEV024", "Numeric coordinates/lengths exceed the supported 18-digit bound.")
    return int(text)


@dataclass(frozen=True)
class Edit:
    start1: int
    end1: int
    operation: str
    ref: str | None
    inserted: str | None
    inserted_length: int | None
    legacy: bool = False


def parse_genomic_hgvs(text: str) -> tuple[str, list[Edit]]:
    """Fully consume absolute RefSeq g. substitutions/del/dup/inv/ins/delins.

    Compound alleles support semicolon-separated non-overlapping edits on one
    accession. Phase and HGVS 3-prime normalization are not inferred. N[length]
    keeps its length, with unknown bases. Redundant historical deletion suffixes
    are accepted for arithmetic only and explicitly require nomenclature review.
    """
    if any(c.isspace() for c in text) or text.count("(") != text.count(")") or text.count("[") != text.count("]"):
        raise VariantProblem("BEV024", "HGVS has whitespace or unbalanced delimiters.")
    if re.match(r"N[CG]_\d+(?:\.0)?:", text):
        raise VariantProblem("BEV024", "Genomic HGVS requires an explicit positive accession version.")
    head = re.fullmatch(r"(N[CG]_\d+\.[1-9]\d*):([cgmnpr])\.(.+)", text)
    if head is None:
        # Valid HGVS may have transcript/genomic combinations or other accession
        # families. Recognize these as outside this subset, not invalid biology.
        if re.match(r"[A-Z][A-Z0-9_().]*:[cgmnpr]\.", text) and text.count("(") == text.count(")"):
            raise VariantProblem("BEV015", "Reference or notation is outside the supported RefSeq genomic subset.")
        raise VariantProblem("BEV024", "Missing versioned accession/coordinate prefix, whitespace, or malformed HGVS.")
    if head[2] != "g":
        raise VariantProblem("BEV015", "Only absolute genomic g. coordinates are checked; transcript/protein mapping is unavailable.")
    body = head[3]
    parts = body[1:-1].split(";") if body.startswith("[") and body.endswith("]") else [body]
    edits = []
    for part in parts:
        snv = re.fullmatch(r"([1-9]\d*)([ACGT])>([ACGT])", part)
        edit = re.fullmatch(r"([1-9]\d*)(?:_([1-9]\d*))?(delins|del|dup|inv|ins)([ACGT]*|N\[[1-9]\d*\]|[1-9]\d*)", part)
        if snv:
            if snv[2] == snv[3]:
                raise VariantProblem("BEV024", "A substitution must change the reference base.")
            position = _number(snv[1])
            edits.append(Edit(position, position, "substitution", snv[2], snv[3], 1))
            continue
        if edit is None:
            if re.search(r"[?()*+]|\d-\d|[ACGT]\[\d+\]|ins\[", part):
                raise VariantProblem("BEV015", "Uncertain endpoints, offsets, repeats or referenced insert sequences require another validator.")
            raise VariantProblem("BEV024", "The complete genomic edit does not match a supported form.")
        a, b = _number(edit[1]), _number(edit[2] or edit[1])
        op, tail = edit[3], edit[4]
        if b < a or edit[2] and b == a:
            raise VariantProblem("BEV024", "Reference endpoints must be ordered and an explicit range must have two distinct positions.")
        if op == "ins" and (edit[2] is None or b != a + 1):
            raise VariantProblem("BEV024", "Insertion requires two adjacent genomic flanks.")
        if op == "inv" and (a == b or tail):
            raise VariantProblem("BEV024", "An inversion requires a range without a sequence/length suffix.")
        if op in {"ins", "delins"}:
            if not tail or tail.isdigit():
                raise VariantProblem("BEV024", "Insertion requires bases or an explicit N[length], not an empty or bare length.")
            n = re.fullmatch(r"N\[([1-9]\d*)\]", tail)
            edits.append(Edit(a, b, op, None, None if n else tail, _number(n[1]) if n else len(tail)))
        else:
            if tail and (re.fullmatch(r"N\[\d+\]", tail) or tail.isdigit() and _number(tail) != b-a+1
                         or not tail.isdigit() and len(tail) != b-a+1):
                raise VariantProblem("BEV024", "Redundant deletion/duplication suffix conflicts with the inclusive interval.")
            edits.append(Edit(a, b, op, tail if tail and not tail.isdigit() else None, None, 0, bool(tail)))
    ordered = sorted(edits, key=lambda e: (e.start1, e.end1))
    if any(right.start1 <= left.end1 for left, right in zip(ordered, ordered[1:], strict=False)):
        raise VariantProblem("BEV015", "Overlapping allele components require explicit allele reconstruction and phase review.")
    return head[1], edits


@dataclass(frozen=True)
class SequenceSlice:
    sequence_id: str
    assembly: str
    start1: int
    sequence: str
    binding: str

    @property
    def end1(self) -> int:
        return self.start1 + len(self.sequence) - 1

    def interval(self, start: int, end: int) -> str:
        if not self.start1 <= start <= end <= self.end1:
            raise VariantProblem("BEV015", "The pinned slice does not cover both event endpoints.")
        result = self.sequence[start-self.start1:end-self.start1+1]
        if "N" in result:
            raise VariantProblem("BEV015", "Reference contains ambiguous N bases; matching cannot be established.")
        return result


def _fasta(data: str, assembly: str) -> SequenceSlice:
    lines = data.strip().splitlines()
    if not lines or sum(line.startswith(">") for line in lines) != 1:
        raise VariantProblem("BEV024", "Exactly one NCBI forward-strand interval FASTA record is required.")
    match = re.fullmatch(r">(N[CG]_\d+\.[1-9]\d*):(\d+)-(\d+) (.+)", lines[0])
    if match is None:
        raise VariantProblem("BEV024", "FASTA must carry an accession.version and explicit genomic interval in its header.")
    description = match[4]
    if "Canis lupus familiaris" not in description:
        raise VariantProblem("BEV017", "The FASTA header does not identify the configured canine taxon.")
    if not re.search(r"(?:^|,\s*)(?:(?:alternate )?assembly )?" + re.escape(assembly) + r"(?:,|$)", description):
        raise VariantProblem("BEV017", "The FASTA header does not identify the declared assembly exactly.")
    start, end = _number(match[2]), _number(match[3])
    sequence = "".join(lines[1:])
    if start < 1 or end < start or len(sequence) != end-start+1 or not re.fullmatch(r"[ACGTN]+", sequence):
        raise VariantProblem("BEV024", "FASTA sequence, forward interval and alphabet disagree.")
    return SequenceSlice(match[1], assembly, start, sequence, "ACCESSION_INTERVAL_HEADER_AND_SNAPSHOT")


def load_reference(spec: dict[str, Any], store: SnapshotStore) -> SequenceSlice:
    key = spec["snapshot_sha256"]
    data = store.get(key)
    if data is None:
        raise VariantProblem("BEV015", "Pinned reference snapshot is unavailable.")
    if not store.verified(key):
        raise VariantProblem("BEV014", "Reference snapshot bytes disagree with the frozen SHA-256.")
    try:
        if spec["format"] == "ncbi_fasta":
            result = _fasta(data.decode("utf-8"), spec["assembly"])
        elif spec["format"] == "ncbi_efetch_json":
            doc = json.loads(data, object_pairs_hook=_unique_json)
            if type(doc["status"]) is not int or doc["status"] != 200:
                raise VariantProblem("BEV015", "The NCBI source retrieval was not successful.")
            if not isinstance(doc["fasta"], str):
                raise VariantProblem("BEV024", "The embedded FASTA must be text.")
            raw = doc["fasta"].encode()
            if sha(raw) != doc["sha256"] or len(raw) != doc["bytes"]:
                raise VariantProblem("BEV014", "Embedded NCBI FASTA bytes disagree with their source receipt.")
            result = _fasta(doc["fasta"], spec["assembly"])
            if (type(doc["bytes"]) is not int
                    or type(doc["requested_1based_inclusive_start"]) is not int
                    or type(doc["requested_1based_inclusive_end"]) is not int
                    or doc["reference_accession"] != result.sequence_id
                    or doc["requested_1based_inclusive_start"] != result.start1
                    or doc["requested_1based_inclusive_end"] != result.end1
                    or doc["sequence_sha256"] != sha(result.sequence.encode())):
                raise VariantProblem("BEV017", "NCBI receipt metadata and actual FASTA sequence/interval disagree.")
        else:
            doc = json.loads(data, object_pairs_hook=_unique_json)
            if doc["reference_sha256"] != spec["reference_sha256"]:
                raise VariantProblem("BEV017", "The producer receipt names a different whole-reference hash.")
            row = doc["queries"][spec["query_key"]]
            seq, a, b = row["sequence"], row["start0"], row["end0"]
            if (type(a) is not int or type(b) is not int or a < 0 or b <= a or len(seq) != b-a
                    or not re.fullmatch(r"[ACGTN]+", seq) or row["sequence_sha256"] != sha(seq.encode())):
                raise VariantProblem("BEV017", "Receipt sequence, hash and zero-based interval disagree.")
            result = SequenceSlice(row["chrom"], spec["assembly"], a+1, seq, "PINNED_PRODUCER_RECEIPT_ASSERTION")
    except VariantProblem:
        raise
    except (KeyError, TypeError, UnicodeError, ValueError, RecursionError) as error:
        raise VariantProblem("BEV024", "Reference snapshot is not in the declared supported format.") from error
    if result.sequence_id != spec["sequence_id"]:
        raise VariantProblem("BEV017", "The snapshot sequence identifier differs from the declared exact identifier/version.")
    return result


def _finding(problem: VariantProblem, field: str) -> dict[str, str]:
    return {"rule_id": problem.code, "severity": "review" if problem.code == "BEV015" else "error",
            "message": str(problem), "field_path": field}


def _event(event: dict[str, Any], references: dict[str, SequenceSlice], failures: dict[str, VariantProblem]) -> dict[str, Any]:
    result: dict[str, Any] = {"id": event["id"], "source_hgvs": event["source_hgvs"],
        "candidate_hgvs": event.get("reviewed_hgvs", event["source_hgvs"]), "findings": [],
        "declared_reference_contract": {key: event[key] for key in (
            "source_assembly", "source_reference", "target_assembly", "target_reference",
            "target_start1", "target_end1", "target_strand") if key in event},
        "original_hgvs_status": "NOT_CHECKED", "candidate_hgvs_status": "NOT_CHECKED",
        "source_reference_status": "NOT_VERIFIED", "source_target_context_status": "NOT_VERIFIED",
        "hgvs_normalization": "NOT_PERFORMED", "allele_phase": "NOT_VERIFIED",
        "whole_reference_specificity": "NOT_PERFORMED", "assay_validated": False, "reportable": False, "probe_ready": False}
    for key in ("event_ref", "event_alt"):
        if key in event:
            result["declared_" + key] = event[key]
    result["declared_event_alleles_status"] = "NOT_CHECKED" if "event_ref" in event or "event_alt" in event else "NOT_SUPPLIED"
    findings = result["findings"]
    if result["candidate_hgvs"] != event["source_hgvs"]:
        findings.append(_finding(VariantProblem("BEV015", "Original and reviewed HGVS differ; correction is explicit and requires review."), "reviewed_hgvs"))
    try:
        parse_genomic_hgvs(event["source_hgvs"])
        result["original_hgvs_status"] = "SUPPORTED_SUBSET_PARSED"
    except VariantProblem as problem:
        result["original_hgvs_status"] = "UNSUPPORTED_REVIEW" if problem.code == "BEV015" else "MALFORMED_REJECTED"
        if result["candidate_hgvs"] != event["source_hgvs"]:
            findings.append({"rule_id": "BEV015", "severity": "review", "message":
                "Original HGVS is retained with its problem; a separate candidate correction requires review: " + str(problem),
                "field_path": "source_hgvs"})
        else:
            findings.append(_finding(problem, "source_hgvs"))
    try:
        accession, edits = parse_genomic_hgvs(result["candidate_hgvs"])
        result["candidate_hgvs_status"] = "SUPPORTED_SUBSET_PARSED"
        result["components"] = [{"start1": e.start1, "end1": e.end1, "operation": e.operation,
            "deleted_length": e.end1-e.start1+1 if e.operation in {"del", "delins"} else 0,
            "inserted_length": e.inserted_length if e.operation in {"ins", "delins", "substitution"}
                               else e.end1-e.start1+1 if e.operation == "dup" else 0,
            "inserted_sequence_known": e.inserted is not None or e.operation not in {"ins", "delins"}} for e in edits]
        if len(edits) > 1:
            findings.append(_finding(VariantProblem("BEV015", "All compound components parsed; allele phase is not independently verified."), "candidate_hgvs"))
            if "event_ref" in event or "event_alt" in event:
                result["declared_event_alleles_status"] = "NOT_CHECKED_COMPOUND_RECONSTRUCTION_REQUIRED"
                findings.append(_finding(VariantProblem("BEV015", "Declared compound REF/ALT retained but not checked; complete allele reconstruction is unavailable."), "event_ref/event_alt"))
        if any(e.legacy for e in edits):
            findings.append(_finding(VariantProblem("BEV015", "Redundant historical suffix checked only for arithmetic; nomenclature needs review."), "candidate_hgvs"))
        if any(e.inserted is None and e.operation in {"ins", "delins"} for e in edits):
            findings.append(_finding(VariantProblem("BEV015", "N[length] specifies length, not recovered inserted bases."), "candidate_hgvs"))
        source_id = event.get("source_reference", "")
        if source_id in failures:
            raise failures[source_id]
        if source_id not in references:
            raise VariantProblem("BEV015", "No usable source reference slice was supplied.")
        source = references[source_id]
        if accession != source.sequence_id or event["source_assembly"] != source.assembly:
            raise VariantProblem("BEV017", "Candidate accession.version or source assembly differs from the pinned source slice.")
        spans = [source.interval(e.start1, e.end1) for e in edits]
        for e, sequence in zip(edits, spans, strict=True):
            if e.ref is not None and e.ref != sequence:
                raise VariantProblem("BEV017", "The claimed reference bases differ from the actual pinned source sequence.")
        if len(edits) == 1:
            e, sequence = edits[0], spans[0]
            ref = "" if e.operation == "ins" else sequence
            alt = (e.inserted if e.operation in {"ins", "delins", "substitution"} else "" if e.operation == "del"
                   else sequence*2 if e.operation == "dup" else reverse_complement(sequence))
            result["event_ref"], result["event_alt"] = ref, alt
            if "event_ref" in event and event["event_ref"] != ref or "event_alt" in event and event["event_alt"] != alt:
                result["declared_event_alleles_status"] = "CONTRADICTS_PINNED_REFERENCE"
                raise VariantProblem("BEV017", "Declared unanchored event alleles disagree with the parsed edit and reference sequence.")
            if "event_ref" in event or "event_alt" in event:
                result["declared_event_alleles_status"] = "CHECKED_SUPPLIED_FIELDS_ONLY"
        result["source_reference_status"] = "VERIFIED_WITHIN_PINNED_SLICE"
        result["source_reference_binding"] = source.binding
        if "target_reference" not in event:
            raise VariantProblem("BEV015", "No target-reference context was supplied; portability was not checked.")
        target_id = event["target_reference"]
        if target_id in failures:
            raise failures[target_id]
        if target_id not in references:
            raise VariantProblem("BEV015", "The target-reference context is unavailable.")
        target = references[target_id]
        if event["target_assembly"] != target.assembly:
            raise VariantProblem("BEV017", "Declared target assembly differs from the pinned target contract.")
        a, b = min(e.start1 for e in edits), max(e.end1 for e in edits)
        ta, tb = event["target_start1"], event["target_end1"]
        target.interval(ta, tb)
        if tb-ta != b-a:
            raise VariantProblem("BEV017", "Source and target full-event spans have different lengths.")
        forward = event["target_strand"] == "+"
        oriented = target.sequence if forward else reverse_complement(target.sequence)
        offset = ta-target.start1 if forward else target.end1-tb
        if source.sequence != oriented or a-source.start1 != offset:
            raise VariantProblem("BEV017", "Oriented complete contexts or event offsets disagree; mapped endpoints alone are insufficient.")
        if "N" in source.sequence:
            raise VariantProblem("BEV015", "Complete context has ambiguous bases; literal N equality is not sequence identity.")
        result["source_target_context_status"] = "VERIFIED_ORIENTED_COMPLETE_SLICE"
        result["context_length_bp"] = len(source.sequence)
        result["target_reference_binding"] = target.binding
    except VariantProblem as problem:
        if not any(f["rule_id"] == problem.code and f["message"] == str(problem) for f in findings):
            findings.append(_finding(problem, "candidate_reference_checks"))
    for reason in event.get("held_reasons", []):
        findings.append(_finding(VariantProblem("BEV015", "Held source issue retained: " + reason), "held_reasons"))
    result["engineering_status"] = "rejected" if any(f["severity"] == "error" for f in findings) else "review_required" if findings else "verified"
    return result


def validate_canine_panel(document: dict[str, Any], store: SnapshotStore) -> dict[str, Any]:
    """Validate every event; report successful checks separately from admission."""
    errors = sorted(Draft202012Validator(SCHEMA).iter_errors(document), key=lambda e: str(list(e.path)))
    if errors:
        raise ValueError("Invalid canine-panel input: " + "; ".join(f"{list(e.path)}: {e.message}" for e in errors))
    for collection in ("references", "events"):
        ids = [row["id"] for row in document[collection]]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate {collection} identifier")
    references, failures = {}, {}
    for spec in document["references"]:
        try:
            references[spec["id"]] = load_reference(spec, store)
        except VariantProblem as problem:
            failures[spec["id"]] = problem
    events = [_event(event, references, failures) for event in document["events"]]
    counts = {status: sum(e["engineering_status"] == status for e in events) for status in ("verified", "review_required", "rejected")}
    status = "rejected" if counts["rejected"] else "review_required" if counts["review_required"] else "verified"
    reference_findings = [{"reference_id": key, **_finding(problem, "references")} for key, problem in failures.items()]
    if any(f["severity"] == "error" for f in reference_findings):
        status = "rejected"
    elif reference_findings and status == "verified":
        status = "review_required"
    return {"format_version": "canine-panel-report-1", "overall_status": status, "engineering_status_counts": counts,
        "input_sha256": sha(json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()),
        "validator": "canine-panel-1", "package_base_version": __version__,
        "implementation_sha256": {name: sha(Path(__file__).with_name(name).read_bytes())
                                  for name in ("canine.py", "grounding.py")},
        "scope": "Pinned source/target reference consistency only; not evidence admission",
        "events": events, "reference_findings": reference_findings,
        "reference_snapshot_hashes": sorted({r["snapshot_sha256"] for r in document["references"]}),
        "admission_assessed": False, "clinical_interpretation_assessed": False,
        "hgvs_normalization_performed": False, "whole_reference_specificity_performed": False,
        "assay_validated": False, "reportable": False, "probe_ready": False}
