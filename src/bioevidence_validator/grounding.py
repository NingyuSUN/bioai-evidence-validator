"""Source grounding: recompute from pinned source snapshots what a record only asserts.

The engine trusts supplied metadata. A grounder moves that trust boundary toward the source: given
the exact source bytes, it recomputes what the record claims (hashes, identifiers, derived evidence)
and reports disagreements as findings. Grounding is optional, offline and deterministic; without
grounders, validation and its reports are unchanged.

Rule codes (all apply to every requested use):
  BEV014 error   source bytes in the snapshot store do not match the record's frozen hash
  BEV015 review  the source cannot confirm it: bytes unavailable, or an item the grounder cannot recompute
  BEV016 error   a cited identifier does not exist in the source
  BEV017 error   the record disagrees with what the source says
  BEV018 review  the source holds evidence the record leaves out

Domain grounders (which fields to recompute for a given source format) live with their importers,
outside the engine; `SourceBytesGrounder` is generic.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from .engine import Finding

SEVERITY = {"BEV014": "error", "BEV015": "review", "BEV016": "error", "BEV017": "error", "BEV018": "review"}


class Grounder(Protocol):
    name: str

    def check(self, record: dict[str, Any]) -> list[Finding]: ...


def finding(record: dict[str, Any], rule_id: str, message: str, field_path: str) -> Finding:
    return Finding(rule_id, SEVERITY[rule_id], message, field_path, list(record["requested_uses"]))


class SnapshotStore:
    """Local source bytes, looked up by frozen SHA-256 and re-hashed when loaded (never trusted by name)."""

    def __init__(self, loaders: dict[str, Callable[[], bytes]] | None = None):
        self._loaders = dict(loaders or {})
        self._cache: dict[str, tuple[bytes | None, bool]] = {}

    @classmethod
    def from_directory(cls, directory: Path) -> SnapshotStore:
        """Files named by their SHA-256, optionally with an extension (e.g. `ab12….json`)."""
        loaders = {}
        for path in sorted(Path(directory).iterdir()):
            key = path.name.split(".", 1)[0].lower()
            if path.is_file() and len(key) == 64:
                loaders[key] = path.read_bytes
        return cls(loaders)

    def _load(self, sha256: str) -> tuple[bytes | None, bool]:
        if sha256 not in self._cache:
            loader = self._loaders.get(sha256)
            data = loader() if loader else None
            self._cache[sha256] = (data, data is not None and hashlib.sha256(data).hexdigest() == sha256)
        return self._cache[sha256]

    def get(self, sha256: str) -> bytes | None:
        return self._load(sha256)[0]

    def verified(self, sha256: str) -> bool:
        return self._load(sha256)[1]


class SourceBytesGrounder:
    """Recompute every source artifact's hash from the snapshot store instead of trusting `observed_sha256`."""

    name = "source-bytes"

    def __init__(self, store: SnapshotStore):
        self.store = store

    def check(self, record: dict[str, Any]) -> list[Finding]:
        findings = []
        for index, source in enumerate(record["source_artifacts"]):
            path = f"$.source_artifacts[{index}]"
            if self.store.get(source["sha256"]) is None:
                findings.append(finding(record, "BEV015", "Source bytes for this frozen hash are not in the snapshot store.", path))
            elif not self.store.verified(source["sha256"]):
                findings.append(finding(record, "BEV014", "Snapshot bytes do not hash to the record's frozen hash.", path))
        return findings
