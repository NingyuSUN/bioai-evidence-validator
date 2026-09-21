from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from linkml.generators.jsonschemagen import JsonSchemaGenerator

from . import __version__
from .config import load_mapping, nonblank


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
    return _resource_path("schema", "bioevidence_core.yaml")


def generate_json_schema(schema_path: Path | None = None) -> dict[str, Any]:
    schema_path = schema_path or default_schema_path()
    try:
        rendered = JsonSchemaGenerator(str(schema_path), mergeimports=True).serialize()
        schema = json.loads(rendered)
        Draft202012Validator.check_schema(schema)
        return schema
    except Exception as exc:
        raise ValueError(f"Unable to compile LinkML schema: {exc}") from exc


def profile_path(profile: str | Path = "general") -> Path:
    """Resolve a built-in name or an explicit YAML path; never silently fall back."""
    if isinstance(profile, str) and profile in {"general", "literature-claim", "dataset-label"}:
        return _resource_path("profiles", profile + ".yaml")
    path = Path(profile)
    if not path.is_file():
        raise ValueError(f"Unknown profile or missing profile file: {profile}")
    return path


def _string_list(value: Any) -> bool:
    return (isinstance(value, list) and all(nonblank(x) for x in value)
            and len(set(value)) == len(value))


def load_profile(data: bytes) -> dict[str, Any]:
    profile = load_mapping(data, "Profile")
    if set(profile) != {"id", "version", "description", "predicates", "subject_types", "object_types", "uses"}:
        raise ValueError("Profile has missing or unknown fields")
    if any(not nonblank(profile[k]) for k in ("id", "version", "description")):
        raise ValueError("Profile id, version and description must be nonblank strings")
    for key in ("predicates", "subject_types", "object_types"):
        if not _string_list(profile[key]):
            raise ValueError(f"Profile {key} must be a list of distinct nonblank strings")
    if not isinstance(profile["uses"], dict) or not profile["uses"]:
        raise ValueError("Profile uses must be a nonempty mapping")
    flags = {"require_human_acceptance", "allow_llm_only", "allow_string_match_only"}
    for name, use in profile["uses"].items():
        if not nonblank(name) or not isinstance(use, dict) or set(use) != flags | {"required_evidence_types"}:
            raise ValueError(f"Invalid or incomplete use configuration: {name!r}")
        if any(type(use[key]) is not bool for key in flags) or not _string_list(use["required_evidence_types"]):
            raise ValueError(f"Use {name!r} requires boolean flags and distinct evidence types")
    return profile


def list_profiles() -> list[dict[str, Any]]:
    return [load_profile(profile_path(name).read_bytes())
            for name in ("general", "literature-claim", "dataset-label")]


def _schema_findings(record: Any, rendered: dict, uses: list[str]) -> list[Finding]:
    validator = Draft202012Validator(rendered, format_checker=FormatChecker())
    findings = []
    for error in sorted(validator.iter_errors(record), key=lambda e: tuple(str(p) for p in e.absolute_path)):
        path = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path)
        findings.append(Finding("SCHEMA", "error", error.message, path, uses))
    return findings


def _integrity_findings(record: dict, profile: dict) -> list[Finding]:
    findings = []
    uses = record["requested_uses"]
    statement = record["statement"]

    def error(message, path):
        findings.append(Finding("RECORD_INTEGRITY", "error", message, path, uses))

    if record["profile_id"] != profile["id"]:
        error("Record profile_id does not match the explicitly selected profile.", "$.profile_id")
    if not _string_list(uses) or not uses or set(uses) - profile["uses"].keys():
        error("requested_uses must contain distinct uses supported by the selected profile.", "$.requested_uses")
    collections = [("$.source_artifacts", record["source_artifacts"]),
                   ("$.evidence_items", record["evidence_items"]),
                   ("$.statement.evidence_lines", statement["evidence_lines"]),
                   ("$.adjudications", record.get("adjudications") or [])]
    for path, rows in collections:
        identities = [row["id"] for row in rows]
        if len(identities) != len(set(identities)):
            error("Duplicate identifiers make references ambiguous.", path)
    artifacts = {row["id"] for row in record["source_artifacts"]}
    items = {row["id"] for row in record["evidence_items"]}
    for index, item in enumerate(record["evidence_items"]):
        if item["source_artifact_id"] not in artifacts:
            error("Evidence references an absent source artifact.", f"$.evidence_items[{index}].source_artifact_id")
        if not _string_list(item["scope"]):
            error("Scope must contain distinct tokens.", f"$.evidence_items[{index}].scope")
    if not _string_list(statement["scope"]):
        error("Scope must contain distinct tokens.", "$.statement.scope")
    for index, line in enumerate(statement["evidence_lines"]):
        refs = line["evidence_item_ids"]
        if not _string_list(refs) or set(refs) - items:
            error("Evidence line has duplicate or unresolved item references.", f"$.statement.evidence_lines[{index}].evidence_item_ids")
    for index, decision in enumerate(record.get("adjudications") or []):
        if decision["statement_id"] != statement["id"]:
            error("Adjudication targets a different statement.", f"$.adjudications[{index}].statement_id")
        targets = decision["applies_to_uses"]
        if not _string_list(targets) or set(targets) - profile["uses"].keys():
            error("Adjudication uses must be distinct and supported by this profile.", f"$.adjudications[{index}].applies_to_uses")
    return findings


def evaluate_profile(record: dict, profile: dict) -> list[Finding]:
    """Fixed evidence checks plus declarative use contracts; no domain dispatch."""
    findings = []
    requested = record["requested_uses"]
    statement = record["statement"]
    items = {x["id"]: x for x in record["evidence_items"]}

    def add(code, severity, message, path, uses=None):
        findings.append(Finding(code, severity, message, path, requested if uses is None else uses))

    if statement["statement_status"] in {"rejected", "superseded"}:
        add("BEV001", "error", "A rejected or superseded statement is ineligible.", "$.statement.statement_status")
    for index, source in enumerate(record["source_artifacts"]):
        if source.get("observed_sha256") and source["observed_sha256"] != source["sha256"]:
            add("BEV002", "error", "Observed source hash differs from the frozen hash.", f"$.source_artifacts[{index}].observed_sha256")
    for key, value, path in [("predicates", statement["predicate"], "$.statement.predicate"),
                             ("subject_types", statement["subject"]["entity_type"], "$.statement.subject.entity_type"),
                             ("object_types", statement["object"]["entity_type"], "$.statement.object.entity_type")]:
        if profile[key] and value not in profile[key]:
            add("BEV003", "error", f"Value is outside the profile's allowed {key}.", path)
    supporting = {}
    for index, line in enumerate(statement["evidence_lines"]):
        if line["direction"] == "contradicts":
            add("BEV004", "review", "Contradicting evidence remains unresolved.", f"$.statement.evidence_lines[{index}]")
        if line["direction"] == "supports":
            for item_id in line["evidence_item_ids"]:
                item = items[item_id]
                if set(item["scope"]) != set(statement["scope"]):
                    add("BEV005", "error", "Supporting evidence scope must match the statement's explicit scope tokens.", f"$.statement.evidence_lines[{index}]")
                else:
                    supporting[item_id] = item
    if not supporting:
        add("BEV006", "review", "No resolved, scope-matched supporting evidence.", "$.statement.evidence_lines")
    types = {item["evidence_type"] for item in supporting.values()}
    methods = {item["extraction_method"] for item in supporting.values()}
    decisions = record.get("adjudications") or []
    for use in requested:
        contract = profile["uses"][use]
        missing = set(contract["required_evidence_types"]) - types
        if missing:
            add("BEV007", "error", "Missing supporting evidence types: " + ", ".join(sorted(missing)), "$.evidence_items", [use])
        if methods == {"llm_extraction"} and not contract["allow_llm_only"]:
            add("BEV008", "review", "Support comes only from LLM extraction.", "$.evidence_items", [use])
        if methods == {"normalized_string_match"} and not contract["allow_string_match_only"]:
            add("BEV009", "review", "Support comes only from normalized string matching.", "$.evidence_items", [use])
        # Mixing two weak extraction methods does not create independent support.
        if len(methods) > 1 and methods <= {"llm_extraction", "normalized_string_match"}:
            if not (contract["allow_llm_only"] and contract["allow_string_match_only"]):
                add("BEV013", "review", "Support mixes only LLM extraction and string matching.", "$.evidence_items", [use])
        human = {d["decision"] for d in decisions if d["reviewer"]["agent_type"] == "human" and use in d["applies_to_uses"]}
        if contract["require_human_acceptance"] and "accept" not in human:
            add("BEV010", "error", "This use requires explicit human acceptance.", "$.adjudications", [use])
        if "reject" in human:
            add("BEV011", "error", "Human rejection remains present for this use.", "$.adjudications", [use])
        if "defer" in human:
            add("BEV012", "review", "A human decision is deferred for this use.", "$.adjudications", [use])
    return findings


def decide_uses(requested_uses: list[str], findings: list[Finding]) -> list[dict[str, Any]]:
    decisions = []
    for use in requested_uses:
        relevant = [f for f in findings if f.rule_id in {"SCHEMA", "RECORD_INTEGRITY"} or use in f.blocking_uses]
        status = ("rejected" if any(f.severity == "error" for f in relevant) else
                  "review_required" if any(f.severity == "review" for f in relevant) else "admitted")
        decisions.append({"use": use, "admission_status": status, "reason_codes": sorted({f.rule_id for f in relevant})})
    return decisions


class RecordValidator:
    """Snapshot a profile and compile schemas once for a consistent batch.

    A trusted custom LinkML schema may add constraints; baseline checks always run.
    Source bytes and reviewer identities are supplied assertions, not authenticated here.
    """
    def __init__(self, *, profile: str | Path = "general", schema_path: Path | None = None):
        profile_bytes = profile_path(profile).read_bytes()
        self._profile = load_profile(profile_bytes)
        self.profile_sha256 = sha256_bytes(profile_bytes)
        baseline = default_schema_path().resolve()
        selected = Path(schema_path or baseline).resolve()
        paths = [baseline] if selected == baseline else [baseline, selected]
        self._schemas = [generate_json_schema(path) for path in paths]
        versions = [str(load_mapping(path.read_bytes(), "Schema").get("version", "unknown")) for path in paths]
        self.schema_version = versions[-1]
        self.schema_sources = [{"role": "baseline" if i == 0 else "extension", "version": versions[i],
                                "sha256": sha256_bytes(json.dumps(schema, sort_keys=True, separators=(",", ":")).encode())}
                               for i, schema in enumerate(self._schemas)]
        self.schema_sha256 = (self.schema_sources[0]["sha256"] if len(paths) == 1 else
                              sha256_bytes(json.dumps(self._schemas, sort_keys=True, separators=(",", ":")).encode()))

    def validate(self, record: Any) -> dict[str, Any]:
        canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        requested = record.get("requested_uses") if isinstance(record, dict) else None
        uses = list(dict.fromkeys(use for use in requested if isinstance(use, str))) if isinstance(requested, list) else []
        findings = []
        for rendered in self._schemas:
            findings.extend(_schema_findings(record, rendered, uses))
        if not findings:
            findings.extend(_integrity_findings(record, self._profile))
        if not findings:
            findings.extend(evaluate_profile(record, self._profile))
        decisions = decide_uses(uses, findings)
        overall = ("rejected" if not decisions or any(f.severity == "error" for f in findings) else
                   "review_required" if any(x["admission_status"] == "review_required" for x in decisions) else "admitted")
        return {
            "validator": "bioai-evidence-validator", "validator_version": __version__,
            "profile_id": self._profile["id"], "profile_version": self._profile["version"],
            "profile_sha256": self.profile_sha256,
            "schema_version": self.schema_version, "schema_sha256": self.schema_sha256,
            "schema_sources": [dict(source) for source in self.schema_sources],
            "input_sha256": sha256_bytes(canonical), "validated_at": datetime.now(timezone.utc).isoformat(),
            "schema_valid": not any(f.rule_id == "SCHEMA" for f in findings),
            "overall_status": overall, "findings": [asdict(f) for f in findings], "use_decisions": decisions,
        }


def validate_record(record: Any, *, profile: str | Path = "general", schema_path: Path | None = None) -> dict[str, Any]:
    return RecordValidator(profile=profile, schema_path=schema_path).validate(record)
