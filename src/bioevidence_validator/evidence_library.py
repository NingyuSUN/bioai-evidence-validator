"""Optional, read-only consumer of the independent local evidence library.

Reviewed extraction is not scientific entailment. Legacy database grounding and
reports without this grounder retain their existing contracts.
"""
from __future__ import annotations

import hashlib
import html
import importlib
import json
import re
import sqlite3
import unicodedata
from pathlib import Path

from .grounding import finding
from .literature import identifier, parse_metadata


def _title(value: str) -> str:
    plain = html.unescape(re.sub(r"<[^>]*>", "", value))
    return "".join(c for c in unicodedata.normalize("NFKC", plain).casefold() if c.isalnum())


def _identifiers(metadata: dict) -> set[str]:
    return {key for kind in ("doi", "pmid", "pmcid") if metadata.get(kind)
            if (key := identifier(f"{kind}:{metadata[kind]}")) is not None}


def _pinned_metadata(literature: dict) -> list[dict]:
    """Recompute known providers' metadata, including retractions, offline."""
    provenance = literature.get("provenance") or {}
    records = provenance.get("matched_records", [])
    if provenance.get("provider") and isinstance(provenance.get("record"), dict):
        records = [*records, provenance]
    parsed = []
    for entry in records:
        provider, record = entry.get("provider"), entry.get("record")
        if not isinstance(record, dict):
            raise ValueError("Pinned provider record must be an object")
        if provider == "europe_pmc":
            record = dict(record)
            if not record.get("pmid") and record.get("source") == "MED":
                record["pmid"] = record.get("id")
            parsed.append(parse_metadata("europepmc", json.dumps({"resultList": {"result": [record]}}).encode()))
        elif provider == "crossref":
            parsed.append(parse_metadata("crossref", json.dumps({"message": record}).encode()))
    for provider in provenance.get("providers", []):
        if provider.get("provider") != "pmc_cloud":
            continue
        for request in provider.get("requests", []):
            raw = request.get("raw_response")
            if not isinstance(raw, str):
                continue
            if request.get("sha256") and hashlib.sha256(raw.encode("utf-8")).hexdigest() != request["sha256"]:
                raise ValueError("Pinned PMC metadata response hash differs")
            if raw.lstrip().startswith("<"):  # XML object listings are discovery receipts, not article metadata.
                continue
            metadata = json.loads(raw)
            if not isinstance(metadata, dict):
                raise ValueError("Pinned PMC version metadata must be an object")
            retracted = metadata.get("is_retracted")
            if retracted is not None and type(retracted) is not bool:
                raise ValueError("Pinned PMC retraction status must be a boolean")
            parsed.append({"found": True, "doi": metadata.get("doi"),
                           "pmcid": metadata.get("pmcid") or provider.get("pmcid"),
                           "retracted": retracted is True, "retraction_only": True})
    return parsed


class EvidenceLibraryGrounder:
    """Exact source/version/quote grounding, with a mandatory original-page review gate."""

    name = "evidence-library"

    def __init__(self, directory: Path):
        try:
            store_type = importlib.import_module("evidence_database.store").Store
        except ImportError as exc:
            raise ValueError("--evidence-library requires the independent local-evidence-database package; "
                             "install its reviewed local checkout or wheel (see docs/EVIDENCE_LIBRARY.md)") from exc
        try:
            self.store = store_type(directory, read_only=True)
        except TypeError as exc:
            raise ValueError("The installed evidence library must support Store(..., read_only=True); "
                             "update the independent package") from exc
        self.last_checks: list[dict] = []

    def _publication(self, item: dict, supplied: dict, receipts: list[dict]) -> tuple[str, str] | None:
        publications = []
        for receipt in receipts:
            metadata = receipt.get("metadata") or {}
            literature = metadata.get("literature")
            if not isinstance(literature, dict):
                continue
            keys, pinned_records = _identifiers(literature), _pinned_metadata(literature)
            publications.append((metadata, literature, keys, pinned_records))
            # The caller cannot suppress a stored publication's retraction by changing its declared URI/type.
            if any(pinned.get("retracted") is True and keys.intersection(_identifiers(pinned))
                   for pinned in pinned_records):
                return "BEV019", "Pinned provider metadata identifies a retracted publication."
            if literature.get("retracted") is True or any(
                location.get("evidence", {}).get("is_retracted") is True
                for location in literature.get("oa_locations", [])
            ):
                return "BEV019", "Pinned acquisition metadata identifies a retracted publication."
        key = identifier(supplied.get("uri") or "")
        if key is None:
            return "BEV015", "Publication needs an explicit DOI/PMID/PMCID URI; filenames do not establish identity."
        source = item["source"]
        if source["role"] not in {"paper", "primary"}:
            return "BEV015", "Supplement identity must be reviewed separately; a parent DOI is not its identity."
        confirmed = False
        for metadata, literature, keys, pinned_records in publications:
            if key not in keys:
                return "BEV017", "Publication URI conflicts with metadata bound to this original."
            expected_title = literature.get("title") or ""
            if not _title(expected_title) or _title(supplied.get("title") or "") != _title(expected_title):
                return "BEV017", "Publication title differs from metadata bound to this original."
            matched = False
            for pinned in pinned_records:
                if not pinned.get("found"):
                    continue
                pinned_keys = _identifiers(pinned)
                if not keys.intersection(pinned_keys):
                    if pinned.get("retraction_only"):
                        continue
                    return "BEV017", "Pinned provider identifiers do not describe the archived publication."
                if pinned.get("retracted") is True:
                    return "BEV019", "Pinned provider metadata identifies a retracted publication."
                for kind in ("doi", "pmid", "pmcid"):
                    if literature.get(kind) and pinned.get(kind) and (
                        identifier(f"{kind}:{literature[kind]}") != identifier(f"{kind}:{pinned[kind]}")
                    ):
                        return "BEV017", "Publication identifiers conflict across pinned metadata."
                if pinned.get("retraction_only"):
                    continue
                if _title(pinned.get("title") or "") != _title(expected_title):
                    return "BEV017", "Publication title conflicts with pinned provider metadata."
                matched = True
            identity = metadata.get("identity_check") or {}
            original_doi = identifier("doi:" + str(identity.get("expected_doi") or ""))
            metadata_doi = identifier("doi:" + str(literature.get("doi") or ""))
            if (matched and identity.get("identity_rule_version") == 2
                    and identity.get("status") == "verified" and identity.get("title_match") is True
                    and not identity.get("supplementary_frontmatter") and original_doi == metadata_doi):
                confirmed = True
        if not confirmed:
            return "BEV015", "Publication identity lacks a verified original-file check and matching pinned provider metadata."
        return None

    def _check_item(self, item: dict, source: dict) -> dict:
        citation, quote = item.get("locator") or "", item.get("extracted_text") or ""
        result = {"evidence_item_id": item["id"], "citation": citation, "quote": quote,
                  "verified": False, "scientifically_verified": False}
        if not re.fullmatch(r"evidence:cv_[0-9a-f]{64}#[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}", citation):
            return {**result, "rule": "BEV015", "reason": "Use an exact evidence:cv_<64 hex>#<block> library citation."}
        if not quote.strip():
            return {**result, "rule": "BEV015", "reason": "An exact extracted_text quotation is required."}
        try:
            original = self.store.get(citation)
            result.update(source_id=original["source"]["source_id"], source_sha256=original["source"]["sha256"],
                          conversion_id=original["conversion_id"], locator=original["block"]["locator"],
                          block_issues=original["block"].get("issues", []))
            if source["sha256"] != original["source"]["sha256"]:
                return {**result, "rule": "BEV017", "reason": "Record source hash differs from the exact archived original."}
            receipts = self.store.ingestion_receipts(original["source"]["source_id"])
            publication = (original["source"]["role"] in {"paper", "supplement"}
                           or any(isinstance((receipt.get("metadata") or {}).get("literature"), dict)
                                  for receipt in receipts)
                           or source["source_type"] == "publication" or item["evidence_type"] == "publication_result"
                           or identifier(source.get("uri") or "") is not None)
            if publication and (problem := self._publication(original, source, receipts)):
                return {**result, "rule": problem[0], "reason": problem[1]}
            checked = self.store.check(citation, quote, require_review=True)
            result.update(checked)
            if not checked["quote_matches"]:
                return {**result, "rule": "BEV017", "reason": "Exact quotation is not present in the specified block."}
            if not checked["admitted"]:
                return {**result, "rule": "BEV015", "reason": "Original-page review for this exact quote is required: "
                        + checked["reason"]}
            return {**result, "verified": True, "rule": None,
                    "reason": "Exact source-bound quotation passed original-page review; scientific support is not checked."}
        except (OSError, ValueError, KeyError, TypeError, AttributeError, sqlite3.Error) as exc:
            code = "BEV017" if "Citation block does not exist" in str(exc) else "BEV014"
            return {**result, "rule": code, "reason": "Evidence library check failed: " + str(exc)}

    def _evaluate(self, record: dict) -> tuple[list, set[str]]:
        sources = {source["id"]: source for source in record["source_artifacts"]}
        findings, verified, checks = [], set(), []
        for index, item in enumerate(record["evidence_items"]):
            source = sources.get(item["source_artifact_id"])
            if source is None:  # The engine rejects broken structural references before invoking grounders.
                continue
            result = self._check_item(item, source)
            checks.append(result)
            if result["verified"]:
                verified.add(item["id"])
            else:
                findings.append(finding(record, result["rule"], result["reason"], f"$.evidence_items[{index}]"))
        self.last_checks = checks
        return findings, verified

    def check(self, record: dict) -> list:
        return self._evaluate(record)[0]

    def verified_items(self, record: dict) -> set[str]:
        return self._evaluate(record)[1]
