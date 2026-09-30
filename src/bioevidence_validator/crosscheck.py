"""Cross-check against a pinned reference resource: what a curated reference contradicts goes to an expert.

Grounding checks a record against the sources it cites. A reference resource is a second, independent
source the record does not cite: a knowledge base of curated assertions. Where it disagrees, the record is
not wrong on that ground alone (the reference can be out of date, and its coverage is partial), so the
finding sends the record to review (BEV025) and never rejects it. Silence of the reference is not support.

Assertions are rows with `subject`, `predicate` and `object` (optionally `subject_label`, `object_label`),
e.g. a CIViC-style `BRAF V600E | does_not_support_sensitivity | vemurafenib in X`, or a marker table
`CD19 | marker_of | CL:0000236`. Two checks:

- statement: the reference asserts the opposite predicate for the same subject and object (`opposites`
  maps each predicate to its opposite);
- evidence: supporting evidence names an entity in its locator (`evidence_key`, e.g. `gene=CD19`) that the
  reference relates (`relation`, e.g. `marker_of`) only to objects unrelated to the statement's object. With
  an ontology, an ancestor or descendant of the object counts as related (a B cell marker supports "naive
  B cell"); without one, only the same identifier does.
"""
from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from typing import Any

from .engine import Finding
from .grounding import finding
from .identifiers import Ontology, pairs


class ReferenceGrounder:
    def __init__(self, assertions: Iterable[dict[str, str]], *, label: str, opposites: dict[str, str] | None = None,
                 evidence_key: str | None = None, relation: str | None = None, ontology: Ontology | None = None):
        self.assertions = list(assertions)
        self.label, self.ontology = label, ontology
        self.opposites = dict(opposites or {})
        self.opposites.update({v: k for k, v in self.opposites.items()})
        self.key, self.relation = evidence_key, relation
        self.name = f"reference:{label}"
        self._pairs: dict[tuple[str, str], list[dict[str, str]]] = {}
        self._objects: dict[str, list[dict[str, str]]] = {}
        for row in self.assertions:
            self._pairs.setdefault((row["subject"], row["object"]), []).append(row)
            if row["predicate"] == relation:
                self._objects.setdefault(row["subject"], []).append(row)

    @classmethod
    def from_table(cls, data: bytes, **options: Any) -> ReferenceGrounder:
        text = data.decode("utf-8")
        delimiter = "\t" if "\t" in text.partition("\n")[0] else ","
        return cls(csv.DictReader(io.StringIO(text), delimiter=delimiter), **options)

    def _related(self, a: str, b: str) -> bool:
        return a == b or bool(self.ontology and self.ontology.related(a, b))

    def _name(self, row: dict[str, str]) -> str:
        return f"{row['object']} ({row['object_label']})" if row.get("object_label") else row["object"]

    def check(self, record: dict[str, Any]) -> list[Finding]:
        statement = record["statement"]
        subject, predicate, target = statement["subject"]["id"], statement["predicate"], statement["object"]["id"]
        out = []
        for row in self._pairs.get((subject, target), []):
            if self.opposites.get(row["predicate"]) == predicate:
                out.append(finding(record, "BEV025", f"The {self.label} reference records {subject} {row['predicate']} "
                                                     f"{target}, the opposite of this claim.", "$.statement.predicate"))
        if not self.key:
            return out
        supporting = {i for line in statement["evidence_lines"] if line["direction"] == "supports"
                      for i in line["evidence_item_ids"]}
        for index, item in enumerate(record["evidence_items"]):
            entity = pairs(item["locator"]).get(self.key)
            rows = self._objects.get(entity or "", [])
            if item["id"] not in supporting or not rows or any(self._related(r["object"], target) for r in rows):
                continue
            names = sorted({self._name(r) for r in rows})
            more = f" and {len(names) - 3} more" if len(names) > 3 else ""
            out.append(finding(record, "BEV025", f"The {self.label} reference lists {entity} as a {(self.relation or '').replace('_', ' ')} "
                                                 f"{'; '.join(names[:3])}{more}, not of {target} or a related term.",
                               f"$.evidence_items[{index}].locator"))
        return out
