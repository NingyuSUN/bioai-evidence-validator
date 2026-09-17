from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from linkml.generators.jsonschemagen import JsonSchemaGenerator

from . import __version__


ALL_USES = [
    "reference_catalog",
    "display_name",
    "source_sample_mapping",
    "frequency_label_mapping",
    "training_label",
    "external_validation_label",
]
SAMPLE_USES = {"source_sample_mapping", "training_label", "external_validation_label"}
HUMAN_ACCEPTANCE_USES = {"training_label", "external_validation_label"}
CURIE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*:[^\s:][^\s]*$")


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    message: str
    field_path: str
    blocking_uses: list[str]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resource_path(kind: str, filename: str) -> Path:
    return Path(__file__).resolve().parent / kind / filename


def default_schema_path() -> Path:
    return _resource_path("schema", "canine_breed.yaml")


def default_policy_path() -> Path:
    return _resource_path("policies", "canine_breed_catalog_v0.1.yaml")


def generate_json_schema(schema_path: Path | None = None) -> dict[str, Any]:
    schema_path = schema_path or default_schema_path()
    rendered = JsonSchemaGenerator(str(schema_path), mergeimports=True).serialize()
    return json.loads(rendered)


def _schema_findings(record: dict[str, Any], schema_path: Path | None) -> list[Finding]:
    validator = Draft202012Validator(generate_json_schema(schema_path), format_checker=FormatChecker())
    findings: list[Finding] = []
    for error in sorted(validator.iter_errors(record), key=lambda e: list(e.absolute_path)):
        path = "$" + "".join(f"[{item}]" if isinstance(item, int) else f".{item}" for item in error.absolute_path)
        findings.append(Finding("SCHEMA", "error", error.message, path, list(ALL_USES)))
    return findings


def _finding(rule_id: str, policy: dict[str, Any], message: str, field_path: str,
             uses: set[str] | list[str]) -> Finding | None:
    rule = policy["rules"].get(rule_id, {})
    if not rule.get("enabled", False):
        return None
    return Finding(rule_id, rule["severity"], message, field_path, sorted(set(uses)))


def _accepted_adjudication(record: dict[str, Any]) -> bool:
    for item in record.get("adjudications", []):
        reviewer = item.get("reviewer") or {}
        if (item.get("decision") == "accept" and item.get("rationale")
                and item.get("decided_at") and reviewer.get("id") and reviewer.get("agent_type") == "human"):
            return True
    return False


def evaluate_policy(record: dict[str, Any], policy: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    requested = set(record["requested_uses"])
    statement = record["statement"]
    subject = statement["subject_label"]
    breed = statement["object_breed"]
    artifacts = {x["id"]: x for x in record["source_artifacts"]}
    items = {x["id"]: x for x in record["evidence_items"]}

    def add(rule_id: str, message: str, path: str, uses: set[str] | list[str] | None = None) -> None:
        found = _finding(rule_id, policy, message, path, uses or requested)
        if found:
            findings.append(found)

    if not CURIE.match(breed["concept_id"]):
        add("CBR001", "The canonical breed identifier is not a CURIE-like identifier.",
            "$.statement.object_breed.concept_id")

    for index, artifact in enumerate(record["source_artifacts"]):
        if not artifact.get("version") or not artifact.get("sha256"):
            add("CBR002", "The source is not both versioned and content-addressed.",
                f"$.source_artifacts[{index}]")
        if artifact.get("observed_sha256") and artifact["observed_sha256"] != artifact["sha256"]:
            add("CBR009", "The observed source hash differs from the frozen source hash.",
                f"$.source_artifacts[{index}].observed_sha256")

    if breed["concept_status"] == "obsolete":
        add("CBR003", "The selected breed concept is obsolete.",
            "$.statement.object_breed.concept_status")

    ambiguous = len(set(subject["candidate_concept_ids"])) > 1
    if ambiguous:
        add("CBR004", "The source label resolves to more than one candidate breed concept.",
            "$.statement.subject_label.candidate_concept_ids")

    used_items: list[dict[str, Any]] = []
    unresolved = False
    directions = set()
    for line_index, line in enumerate(statement["evidence_lines"]):
        directions.add(line["direction"])
        for item_id in line["evidence_item_ids"]:
            item = items.get(item_id)
            if item is None:
                unresolved = True
                add("CBR013", f"Evidence item {item_id!r} does not exist.",
                    f"$.statement.evidence_lines[{line_index}].evidence_item_ids")
                continue
            used_items.append(item)
            if item["source_artifact_id"] not in artifacts:
                unresolved = True
                add("CBR013", f"Source artifact {item['source_artifact_id']!r} does not exist.",
                    f"$.evidence_items[{item_id}].source_artifact_id")

    if not unresolved and used_items and all(x["extraction_method"] == "normalized_string_match" for x in used_items):
        add("CBR005", "All supporting evidence is derived only from normalized string matching.",
            "$.evidence_items")

    regional_to_generic = (
        subject.get("scope_hint") == "regional_population"
        and breed["breed_scope"] == "breed"
        and statement["predicate"] in {"maps_to_breed", "denotes_breed"}
    )
    has_scope_evidence = any(x.get("evidence_type") == "official_scope_statement" for x in used_items)
    if regional_to_generic and not has_scope_evidence:
        add("CBR006", "A regional population is mapped to a generic breed without official scope evidence.",
            "$.statement")

    prohibited = set(policy["rules"].get("CBR007", {}).get("prohibited_scope_flags", []))
    conflict_flags = prohibited.intersection(breed.get("scope_flags", []))
    if conflict_flags:
        add("CBR007", "The concept has incompatible scope flags: " + ", ".join(sorted(conflict_flags)) + ".",
            "$.statement.object_breed.scope_flags")

    if requested.intersection(SAMPLE_USES) and subject.get("genotype_membership_verified") is not True:
        add("CBR008", "Sample-dependent admission was requested without verified genotype membership.",
            "$.statement.subject_label.genotype_membership_verified", requested.intersection(SAMPLE_USES))

    accepted = _accepted_adjudication(record)
    if (ambiguous or regional_to_generic or "contradicts" in directions) and not accepted:
        add("CBR010", "This high-risk mapping has no complete human acceptance record.",
            "$.adjudications")

    declared_sources = set(subject["source_scope"])
    if subject["source_name"] not in declared_sources:
        add("CBR011", "The source label's origin is absent from the mapping's declared source scope.",
            "$.statement.subject_label.source_scope", SAMPLE_USES.intersection(requested) or requested)

    if "contradicts" in directions:
        add("CBR012", "The statement has explicit contradicting evidence.",
            "$.statement.evidence_lines")

    if requested.intersection(HUMAN_ACCEPTANCE_USES) and not accepted:
        add("CBR014", "Training or external-validation use requires explicit human acceptance.",
            "$.adjudications", requested.intersection(HUMAN_ACCEPTANCE_USES))

    return findings


def decide_uses(requested_uses: list[str], findings: list[Finding]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for use in requested_uses:
        relevant = [f for f in findings if use in f.blocking_uses]
        if any(f.severity == "error" for f in relevant):
            status = "rejected"
        elif any(f.severity == "review" for f in relevant):
            status = "review_required"
        else:
            status = "admitted"
        decisions.append({
            "use": use,
            "admission_status": status,
            "reason_codes": sorted({f.rule_id for f in relevant}),
        })
    return decisions


def validate_record(record: dict[str, Any], *, schema_path: Path | None = None,
                    policy_path: Path | None = None) -> dict[str, Any]:
    policy_path = policy_path or default_policy_path()
    policy_bytes = policy_path.read_bytes()
    policy = yaml.safe_load(policy_bytes)
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    findings = _schema_findings(record, schema_path)
    if not findings:
        findings.extend(evaluate_policy(record, policy))
    decisions = decide_uses(record.get("requested_uses", ALL_USES), findings)
    schema_valid = not any(f.rule_id == "SCHEMA" for f in findings)
    overall = (
        "rejected" if any(x["admission_status"] == "rejected" for x in decisions)
        else "review_required" if any(x["admission_status"] == "review_required" for x in decisions)
        else "admitted"
    )
    return {
        "validator": "bioai-evidence-validator",
        "validator_version": __version__,
        "profile": "canine_breed",
        "schema_version": "0.1.0",
        "policy_id": policy["id"],
        "policy_version": policy["version"],
        "policy_sha256": sha256_bytes(policy_bytes),
        "input_sha256": sha256_bytes(canonical),
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "schema_valid": schema_valid,
        "overall_status": overall,
        "findings": [asdict(f) for f in findings],
        "use_decisions": decisions,
    }
