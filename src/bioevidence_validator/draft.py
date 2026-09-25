"""Compact drafts: a short, strict authoring format that expands to a full evidence record.

A draft names each fact once. Building it derives identifiers, groups evidence items into
evidence lines by direction, and hashes local source files. It never fills in facts the
caller did not state: scopes, extraction methods, retrieval times and reviewer decisions
must be written explicitly, and the resulting record still goes through full validation.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

from .config import load_mapping, nonblank
from .engine import load_profile, profile_path

DRAFT_KEYS = {"required": {"profile", "uses", "statement", "sources", "evidence"},
              "optional": {"id", "status", "reviews"}}
STATEMENT_KEYS = {"required": {"subject", "predicate", "object", "scope"}, "optional": set()}
ENTITY_KEYS = {"required": {"id", "label", "type"}, "optional": set()}
SOURCE_KEYS = {"required": {"id", "title", "type", "version", "retrieved_at"},
               "optional": {"uri", "sha256", "file"}}
EVIDENCE_KEYS = {"required": {"source", "locator", "type", "method", "scope"},
                 "optional": {"text", "direction"}}
REVIEW_KEYS = {"required": {"reviewer", "decision", "uses", "rationale", "decided_at"}, "optional": set()}
REVIEWER_KEYS = {"required": {"id", "type"}, "optional": {"name"}}

STATUSES = ["proposed", "accepted", "rejected", "superseded"]
SOURCE_TYPES = ["ontology_snapshot", "registry_snapshot", "dataset_snapshot", "publication", "web_page", "local_file"]
METHODS = ["deterministic_parser", "manual_curation", "normalized_string_match", "llm_extraction"]
DIRECTIONS = ["supports", "contradicts", "neutral"]
DECISIONS = ["accept", "reject", "defer"]
AGENT_TYPES = ["human", "software", "organization"]


def _fields(value: Any, keys: dict, path: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be a mapping")
    missing = keys["required"] - value.keys()
    unknown = value.keys() - keys["required"] - keys["optional"]
    if missing:
        raise ValueError(f"{path} is missing: {', '.join(sorted(missing))}")
    if unknown:
        raise ValueError(f"{path} has unknown fields: {', '.join(sorted(map(str, unknown)))}")
    return value


def _text(value: Any, path: str, choices: list[str] | None = None) -> str:
    if isinstance(value, (dt.date, dt.datetime)):
        value = value.isoformat()  # YAML loads unquoted timestamps as datetime objects.
    if not nonblank(value):
        raise ValueError(f"{path} must be a nonblank string (quote numbers and versions in YAML)")
    if choices is not None and value not in choices:
        raise ValueError(f"{path} must be one of: {', '.join(choices)}")
    return value


def _texts(value: Any, path: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{path} must be a nonempty list")
    items = [_text(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if len(set(items)) != len(items):
        raise ValueError(f"{path} must not repeat values")
    return items


def _rows(value: Any, path: str, required: bool = True) -> list:
    if not isinstance(value, list) or (required and not value):
        raise ValueError(f"{path} must be a {'nonempty ' if required else ''}list")
    return value


def _entity(value: Any, path: str) -> dict:
    entity = _fields(value, ENTITY_KEYS, path)
    return {"id": _text(entity["id"], path + ".id"), "label": _text(entity["label"], path + ".label"),
            "entity_type": _text(entity["type"], path + ".type")}


def _source(value: Any, path: str, base_dir: Path) -> tuple[str, dict]:
    source = _fields(value, SOURCE_KEYS, path)
    if "sha256" not in source and "file" not in source:
        raise ValueError(f"{path} needs sha256, file, or both")
    artifact = {"title": _text(source["title"], path + ".title"),
                "source_type": _text(source["type"], path + ".type", SOURCE_TYPES)}
    if "uri" in source:
        artifact["uri"] = _text(source["uri"], path + ".uri")
    artifact.update({"version": _text(source["version"], path + ".version"),
                     "retrieved_at": _text(source["retrieved_at"], path + ".retrieved_at")})
    observed = None
    if "file" in source:
        file = base_dir / _text(source["file"], path + ".file")
        if not file.is_file():
            raise ValueError(f"{path}.file does not exist: {file}")
        observed = hashlib.sha256(file.read_bytes()).hexdigest()
    # A stated hash is the frozen reference; a file hash is what was observed now.
    # With both, validation reports a mismatch (BEV002) instead of trusting either.
    artifact["sha256"] = _text(source["sha256"], path + ".sha256").lower() if "sha256" in source else observed
    if "sha256" in source and observed is not None:
        artifact["observed_sha256"] = observed
    return _text(source["id"], path + ".id"), artifact


def load_draft(path: Path) -> dict:
    """Read a YAML or JSON draft with duplicate-key rejection."""
    return load_mapping(Path(path).read_bytes(), "Draft")


def build_record(draft: dict, *, base_dir: Path | str = ".") -> dict[str, Any]:
    """Expand a compact draft into a full record. Raises ValueError on any malformed field."""
    draft = _fields(draft, DRAFT_KEYS, "draft")
    base_dir = Path(base_dir)
    profile = _text(draft["profile"], "draft.profile")
    uses = _texts(draft["uses"], "draft.uses")
    statement = _fields(draft["statement"], STATEMENT_KEYS, "draft.statement")
    scope = _texts(statement["scope"], "draft.statement.scope")

    record_id = _text(draft["id"], "draft.id") if "id" in draft else None
    if record_id is None:
        canonical = json.dumps(draft, sort_keys=True, separators=(",", ":"), default=str).encode()
        record_id = "bioev:draft-" + hashlib.sha256(canonical).hexdigest()[:16]

    sources, local_ids = [], {}
    for index, row in enumerate(_rows(draft["sources"], "draft.sources")):
        name, artifact = _source(row, f"draft.sources[{index}]", base_dir)
        if name in local_ids:
            raise ValueError(f"draft.sources[{index}].id repeats {name!r}")
        local_ids[name] = f"{record_id}/source/{name}"
        sources.append({"id": local_ids[name], **artifact})

    items, lines = [], {}
    for index, row in enumerate(_rows(draft["evidence"], "draft.evidence")):
        path = f"draft.evidence[{index}]"
        evidence = _fields(row, EVIDENCE_KEYS, path)
        source = _text(evidence["source"], path + ".source")
        if source not in local_ids:
            raise ValueError(f"{path}.source {source!r} is not a declared source id")
        item = {"id": f"{record_id}/evidence/{index + 1}", "source_artifact_id": local_ids[source],
                "locator": _text(evidence["locator"], path + ".locator")}
        if "text" in evidence:
            item["extracted_text"] = _text(evidence["text"], path + ".text")
        item.update({"evidence_type": _text(evidence["type"], path + ".type"),
                     "extraction_method": _text(evidence["method"], path + ".method", METHODS),
                     "scope": _texts(evidence["scope"], path + ".scope")})
        items.append(item)
        direction = _text(evidence.get("direction", "supports"), path + ".direction", DIRECTIONS)
        lines.setdefault(direction, []).append(item["id"])

    statement_id = f"{record_id}/statement"
    adjudications = []
    for index, row in enumerate(_rows(draft.get("reviews", []), "draft.reviews", required=False)):
        path = f"draft.reviews[{index}]"
        review = _fields(row, REVIEW_KEYS, path)
        reviewer = _fields(review["reviewer"], REVIEWER_KEYS, path + ".reviewer")
        agent = {"id": _text(reviewer["id"], path + ".reviewer.id")}
        if "name" in reviewer:
            agent["name"] = _text(reviewer["name"], path + ".reviewer.name")
        agent["agent_type"] = _text(reviewer["type"], path + ".reviewer.type", AGENT_TYPES)
        adjudications.append({"id": f"{record_id}/review/{index + 1}", "statement_id": statement_id,
                              "applies_to_uses": _texts(review["uses"], path + ".uses"),
                              "decision": _text(review["decision"], path + ".decision", DECISIONS),
                              "reviewer": agent, "rationale": _text(review["rationale"], path + ".rationale"),
                              "decided_at": _text(review["decided_at"], path + ".decided_at")})

    return {
        "record_id": record_id,
        "profile_id": profile,
        "statement": {
            "id": statement_id,
            "subject": _entity(statement["subject"], "draft.statement.subject"),
            "predicate": _text(statement["predicate"], "draft.statement.predicate"),
            "object": _entity(statement["object"], "draft.statement.object"),
            "scope": scope,
            "evidence_lines": [{"id": f"{record_id}/line/{direction}", "direction": direction,
                                "evidence_item_ids": ids} for direction, ids in lines.items()],
            "statement_status": _text(draft.get("status", "proposed"), "draft.status", STATUSES),
        },
        "source_artifacts": sources,
        "evidence_items": items,
        "adjudications": adjudications,
        "requested_uses": uses,
    }


def _object(keys: dict, properties: dict, description: str | None = None) -> dict:
    if properties.keys() != keys["required"] | keys["optional"]:
        raise RuntimeError("Draft schema and parser fields diverged")
    schema = {"type": "object", "additionalProperties": False,
              "required": sorted(keys["required"]), "properties": properties}
    return {"description": description, **schema} if description else schema


def _choice(values: list[str], description: str | None = None) -> dict:
    if not values:
        return {"type": "string", "minLength": 1, **({"description": description} if description else {})}
    return {"type": "string", "enum": list(values), **({"description": description} if description else {})}


def draft_json_schema(profile: str | Path = "general") -> dict[str, Any]:
    """JSON Schema for drafts under one profile, e.g. for LLM structured output.

    Profile allowlists become enums. The schema guides authoring only; build_record and
    validation remain authoritative.
    """
    contract = load_profile(profile_path(profile).read_bytes())
    evidence_types = sorted({kind for use in contract["uses"].values() for kind in use["required_evidence_types"]})
    text = {"type": "string", "minLength": 1}
    tokens = {"type": "array", "minItems": 1, "uniqueItems": True, "items": text}

    def entity(types):
        return _object(ENTITY_KEYS, {"id": {**text, "description": "Stable identifier, e.g. a CURIE."},
                                     "label": text, "type": _choice(types)})

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"BioAI evidence draft ({contract['id']} profile {contract['version']})",
        **_object(DRAFT_KEYS, {
            "id": {**text, "description": "Optional record id; derived from the draft content when omitted."},
            "profile": {"const": contract["id"]},
            "uses": {"type": "array", "minItems": 1, "uniqueItems": True,
                     "items": _choice(sorted(contract["uses"]))},
            "status": _choice(STATUSES, "Defaults to proposed."),
            "statement": _object(STATEMENT_KEYS, {
                "subject": entity(contract["subject_types"]),
                "predicate": _choice(contract["predicates"]),
                "object": entity(contract["object_types"]),
                "scope": {**tokens, "description": "Explicit scope tokens, e.g. taxon:9606."}}),
            "sources": {"type": "array", "minItems": 1, "items": _object(SOURCE_KEYS, {
                "id": {**text, "description": "Local name referenced by evidence[].source."},
                "title": text, "type": _choice(SOURCE_TYPES), "uri": text, "version": text,
                "retrieved_at": {"type": "string", "format": "date-time"},
                "sha256": {"type": "string", "pattern": "^[0-9a-fA-F]{64}$",
                           "description": "Frozen source hash."},
                "file": {**text, "description": "Local file hashed at build time, relative to the draft."}},
                "Provide sha256, file, or both.")},
            "evidence": {"type": "array", "minItems": 1, "items": _object(EVIDENCE_KEYS, {
                "source": text, "locator": {**text, "description": "Where in the source, e.g. 'Table 2'."},
                "text": text, "type": _choice(evidence_types),
                "method": _choice(METHODS, "Set by the pipeline that produced this item, not by a model."),
                "scope": {**tokens, "description": "Scope the source actually supports."},
                "direction": _choice(DIRECTIONS, "Defaults to supports.")})},
            "reviews": {"type": "array", "items": _object(REVIEW_KEYS, {
                "reviewer": _object(REVIEWER_KEYS, {"id": text, "name": text, "type": _choice(AGENT_TYPES)}),
                "decision": _choice(DECISIONS),
                "uses": {"type": "array", "minItems": 1, "uniqueItems": True,
                         "items": _choice(sorted(contract["uses"]))},
                "rationale": text, "decided_at": {"type": "string", "format": "date-time"}})},
        }),
    }
