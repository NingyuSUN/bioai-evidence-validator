"""The feedback loop: validate what an AI proposes, tell it what to fix, and keep what was verified.

An agent proposes a record; bioevidence validates it with its grounders. Every finding the agent can fix
(an identifier that does not exist, a label that belongs to another term, a quote or table value that is
not in the source) goes back to it as a reason that points at the part of the record concerned, and it
may revise and propose again. Two kinds of finding are not fed back, and send the record to a person as it
is. Judgment: its own evidence disagrees (BEV004), a reference resource contradicts it (BEV025), a semantic
cue flags it (BEV022) or it lacks an independent review (BEV021); the agent is never asked to make the
evidence against its answer go away. Policy: the use needs a human decision whatever the agent does
(LLM-only or string-match-only evidence where the profile forbids it, BEV008/009/013; human acceptance
required, deferred or refused, BEV010/012/011). For the same reason, evidence verified in one attempt is carried
into the next while the claim stays the same: a revision may fix or replace what failed, but not withdraw what
was verified.

`revise` runs the loop around any proposer (a model call, an agent, a person); nothing here calls a model.
"""
from __future__ import annotations

import copy
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .engine import RecordValidator

JUDGMENT = frozenset({"BEV004", "BEV021", "BEV022", "BEV025"})
POLICY = frozenset({"BEV008", "BEV009", "BEV010", "BEV011", "BEV012", "BEV013"})
EXPERT = JUDGMENT | POLICY


def to_expert(report: dict[str, Any]) -> bool:
    """The record goes to a person as it is: it is not admitted, and only for findings the agent cannot fix."""
    codes = {f["rule_id"] for f in report["findings"]}
    return report["overall_status"] != "admitted" and bool(codes) and codes <= EXPERT


def where(record: dict[str, Any], path: str) -> str:
    """A short, human-readable name for the part of the record a finding's path points at."""
    if match := re.match(r"\$\.evidence_items\[(\d+)\]", path):
        n = int(match.group(1))
        items = record.get("evidence_items") or []
        locator = items[n].get("locator") if n < len(items) else None
        return f"evidence {n + 1}" + (f" ({locator})" if locator else "")
    if match := re.match(r"\$\.source_artifacts\[(\d+)\]", path):
        return f"source {int(match.group(1)) + 1}"
    if match := re.match(r"\$\.statement\.(subject|object)(?:\.(id|label))?", path):
        return match.group(1) + (f" {match.group(2)}" if match.group(2) else "")
    return path.removeprefix("$.").replace("_", " ") or "record"


def reasons(record: dict[str, Any], report: dict[str, Any]) -> list[str]:
    """What to fix, one line per finding, without the findings that go to an expert."""
    lines = [f"{where(record, f['field_path'])}: {f['message']}" for f in report["findings"] if f["rule_id"] not in EXPERT]
    return list(dict.fromkeys(lines))


def verified_items(validator: RecordValidator, record: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for grounder in validator.grounders:
        if hasattr(grounder, "verified_items"):
            found |= set(grounder.verified_items(record))
    return found


def _key(record: dict[str, Any], item: dict[str, Any]) -> tuple[str, str, str]:
    sha = next((s["sha256"] for s in record["source_artifacts"] if s["id"] == item["source_artifact_id"]), "")
    return sha, item["locator"], item.get("extracted_text") or ""


def claim(record: dict[str, Any]) -> tuple[str, str, str]:
    statement = record["statement"]
    return statement["subject"]["id"], statement["predicate"], statement["object"]["id"]


def carry(previous: dict[str, Any], verified: set[str], record: dict[str, Any]) -> dict[str, Any]:
    """`record` plus the verified evidence of `previous` that it left out, in the evidence line it was in.

    Only for the same claim: evidence lines are relative to their statement, so a record that states something
    else (another cell type, the opposite predicate) is validated on its own evidence."""
    merged = copy.deepcopy(record)
    if claim(previous) != claim(record):
        return merged
    present = {_key(merged, item) for item in merged["evidence_items"]}
    directions = {i: line["direction"] for line in previous["statement"]["evidence_lines"] for i in line["evidence_item_ids"]}
    ids = {x["id"] for x in merged["evidence_items"]} | {s["id"] for s in merged["source_artifacts"]}
    for item in previous["evidence_items"]:
        if item["id"] not in verified or _key(previous, item) in present:
            continue
        source = next(s for s in previous["source_artifacts"] if s["id"] == item["source_artifact_id"])
        same = next((s for s in merged["source_artifacts"] if s["sha256"] == source["sha256"]), None)
        if same is None:
            same = dict(source, id=_fresh(source["id"], ids))
            merged["source_artifacts"].append(same)
        kept = dict(item, id=_fresh(item["id"], ids), source_artifact_id=same["id"])
        merged["evidence_items"].append(kept)
        direction = directions.get(item["id"], "supports")
        line = next((x for x in merged["statement"]["evidence_lines"] if x["direction"] == direction), None)
        if line is None:
            line = {"id": _fresh(f"carried-{direction}", ids), "direction": direction, "evidence_item_ids": []}
            merged["statement"]["evidence_lines"].append(line)
        line["evidence_item_ids"].append(kept["id"])
        present.add(_key(previous, item))
    return merged


def _fresh(base: str, taken: set[str]) -> str:
    name, n = base, 1
    while name in taken:
        n += 1
        name = f"{base}-{n}"
    taken.add(name)
    return name


@dataclass
class Attempt:
    record: dict[str, Any]
    report: dict[str, Any]
    feedback: list[str] = field(default_factory=list)


def revise(propose: Callable[[list[str]], dict[str, Any] | None], validator: RecordValidator,
           rounds: int = 3) -> list[Attempt]:
    """Up to `rounds` attempts. `propose(feedback)` returns a record, or None to stop; the first call gets no
    feedback. The loop ends when a record is admitted, goes to an expert, or the rounds run out."""
    attempts: list[Attempt] = []
    feedback: list[str] = []
    previous, verified = None, set()
    for _ in range(rounds):
        record = propose(feedback)
        if record is None:
            break
        if previous is not None:
            record = carry(previous, verified, record)
        report = validator.validate(record)
        attempts.append(Attempt(record, report))
        if report["overall_status"] == "admitted" or to_expert(report):
            break
        feedback = reasons(record, report)
        attempts[-1].feedback = feedback
        sound = not {f["rule_id"] for f in report["findings"]} & {"SCHEMA", "RECORD_INTEGRITY"}
        previous, verified = record, verified_items(validator, record) if sound else set()
    return attempts
