"""Table grounding: evidence that cites rows of a pinned table must be in that table, with the values it claims.

The data counterpart of a quote check. An evidence item points at a table snapshot (TSV or CSV with a
header, pinned by SHA-256 in the snapshot store) and names one row by its key columns in the locator,
`key=value` pairs separated by `;` (e.g. `cluster=3;gene=CD8A`). Its `extracted_text` may claim values
from that row the same way (`logfc=2.4; pct_in=0.91`). A claimed number matches when the table's value
rounds to it at the precision the claim is written with; text matches ignoring case.

Only items of the evidence types the grounder is given are checked, so tables used in other ways are left
alone. Rule codes (see `grounding`): BEV015 (bytes unavailable, or the locator names several rows),
BEV016 (no such row), BEV017 (a claimed value differs from the table), BEV024 (a locator or claim that is
not `key=value` pairs, or names a column the table does not have).
"""
from __future__ import annotations

import csv
import difflib
import io
from collections.abc import Iterable
from typing import Any

from .engine import Finding
from .grounding import SnapshotStore, finding
from .identifiers import pairs


def parse_table(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = data.decode("utf-8")
    delimiter = "\t" if "\t" in text.partition("\n")[0] else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]
    return list(reader.fieldnames or []), rows


def same_value(claimed: str, actual: str) -> bool:
    try:
        number, value = float(claimed), float(actual)
    except ValueError:
        return claimed.strip().casefold() == actual.strip().casefold()
    decimals = len(claimed.strip().partition(".")[2].rstrip()) if "." in claimed else 0
    return abs(number - value) <= 0.5 * 10 ** -decimals + 1e-12


class TableGrounder:
    """Check evidence items of the given types against the rows of their pinned table."""

    name = "tables"

    def __init__(self, store: SnapshotStore, evidence_types: Iterable[str]):
        self.store = store
        self.types = set(evidence_types)
        self._tables: dict[str, tuple[list[str], list[dict[str, str]]]] = {}

    def _table(self, sha256: str) -> tuple[list[str], list[dict[str, str]]] | None:
        if not self.store.verified(sha256):
            return None
        if sha256 not in self._tables:
            self._tables[sha256] = parse_table(self.store.get(sha256) or b"")
        return self._tables[sha256]

    def _evaluate(self, record: dict[str, Any]) -> tuple[list[Finding], set[str]]:
        sources = {s["id"]: s for s in record["source_artifacts"]}
        findings, verified = [], set()
        for index, item in enumerate(record["evidence_items"]):
            source = sources.get(item["source_artifact_id"])
            if item["evidence_type"] not in self.types or source is None:
                continue
            path = f"$.evidence_items[{index}]"

            def add(code: str, message: str, where: str = path) -> None:
                findings.append(finding(record, code, message, where))

            table = self._table(source["sha256"])
            if table is None:
                add("BEV015", "The table's bytes for this frozen hash are not in the snapshot store.")
                continue
            columns, rows = table
            key, claims = pairs(item["locator"]), pairs(item.get("extracted_text"))
            if not key or (item.get("extracted_text") and not claims):
                add("BEV024", "A table citation needs a locator, and any claimed values, written as key=value pairs.")
                continue
            unknown = sorted(set(key) - set(columns)) + sorted(set(claims) - set(columns))
            if unknown:
                add("BEV024", f"The table has no column {', '.join(map(repr, unknown))}; columns: {', '.join(columns)}.")
                continue
            matches = [r for r in rows if all(same_value(v, r[k]) for k, v in key.items())]
            if not matches:
                add("BEV016", f"No row of the pinned table has {_render(key)}.{_closest(rows, key)}", path + ".locator")
                continue
            if len(matches) > 1:
                add("BEV015", f"{len(matches)} rows have {_render(key)}; the locator must name one row.", path + ".locator")
                continue
            wrong = {k: matches[0][k] for k, v in claims.items() if not same_value(v, matches[0][k])}
            if wrong:
                add("BEV017", f"The row {_render(key)} has {_render(wrong)}, not {_render({k: claims[k] for k in wrong})}.",
                    path + ".extracted_text")
            else:
                verified.add(item["id"])
        return findings, verified

    def check(self, record: dict[str, Any]) -> list[Finding]:
        return self._evaluate(record)[0]

    def verified_items(self, record: dict[str, Any]) -> set[str]:
        return self._evaluate(record)[1]


def _render(values: dict[str, str]) -> str:
    return ", ".join(f"{k}={v}" for k, v in values.items())


def _closest(rows: list[dict[str, str]], key: dict[str, str]) -> str:
    """Values of the last key column among rows that match the other keys, closest first."""
    *fixed, last = list(key)
    candidates = sorted({r[last] for r in rows if all(same_value(key[k], r[k]) for k in fixed)})
    close = difflib.get_close_matches(key[last], candidates, n=3, cutoff=0.6)
    return f" Closest {last} values for {_render({k: key[k] for k in fixed})}: {', '.join(close)}." if close and fixed \
        else (f" Closest {last} values: {', '.join(close)}." if close else "")
