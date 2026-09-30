"""Semantic cues: cheap, deterministic hints that a verbatim quote is being read the wrong way.

Grounding proves that a quote is real; it cannot tell whether the quote supports the claim. These
checks cannot either: they look for words that often signal a misreading, and send the record to a
human (BEV022, review). They never admit and never reject, and their false-review rate on genuine
quotes is measured rather than assumed (see evaluation/llm_benchmark/semantic.py).

- negation: a quote supporting a positive claim contains a negation ("no", "did not", "failed to" …)
- hedge (optional): a quote supporting the claim is hedged ("may", "suggest", "potential" …)
- species: an item scoped to humans quotes only animal or in-vitro evidence ("mice", "cell lines" …)

An independent model or agent review is the other semantic layer: it is recorded as a non-human
adjudication, which the engine counts under a use's `require_independent_review` (BEV021).
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from .engine import Finding
from .grounding import finding

NEGATION = re.compile(r"\b(no|not|none|neither|nor|without|lack(?:ed|s)? of|absence of|fail(?:ed|s)? to|cannot"
                      r"|non-?significant|insignificant|unaffected|insensitive|unchanged|did not|does not|do not"
                      r"|was not|were not|is not|are not)\b", re.IGNORECASE)
HEDGE = re.compile(r"\b(may|might|could|suggests?|suggested|suggesting|possibl[ey]|potential(?:ly)?|likely"
                   r"|appears? to|hypothes\w+|speculat\w+|preliminary)\b", re.IGNORECASE)
NON_HUMAN = re.compile(r"\b(mice|mouse|murine|rats?|xenografts?|zebrafish|drosophila|yeast|cell lines?|in vitro"
                       r"|organoids?)\b", re.IGNORECASE)
HUMAN = re.compile(r"\b(patients?|humans?|individuals|subjects|participants|women|men|children|cohorts?|probands?"
                   r"|families|carriers|cases)\b", re.IGNORECASE)


class CueChecker:
    """Deterministic cue checks over the quotes (`extracted_text`) of supporting evidence items."""

    name = "semantic-cues"

    def __init__(self, negative_predicates: Iterable[str] = (), human_scope: Iterable[str] = ("NCBITaxon:9606",),
                 hedges: bool = False):
        self.negative_predicates = set(negative_predicates)
        self.human_scope = set(human_scope)
        self.hedges = hedges

    def check(self, record: dict[str, Any]) -> list[Finding]:
        statement = record["statement"]
        positive = statement["predicate"] not in self.negative_predicates
        supporting = {i for line in statement["evidence_lines"] if line["direction"] == "supports"
                      for i in line["evidence_item_ids"]}
        out = []
        for index, item in enumerate(record["evidence_items"]):
            text = item.get("extracted_text") or ""
            if item["id"] not in supporting or not text:
                continue
            path = f"$.evidence_items[{index}]"
            if positive and (match := NEGATION.search(text)):
                out.append(finding(record, "BEV022", f"The quote contains a negation ({match.group(0)!r}) but "
                                                      "supports a positive claim.", path))
            if self.hedges and (match := HEDGE.search(text)):
                out.append(finding(record, "BEV022", f"The quote is hedged ({match.group(0)!r}) but is used as "
                                                      "a finding.", path))
            if set(item["scope"]) & self.human_scope and (match := NON_HUMAN.search(text)) and not HUMAN.search(text):
                out.append(finding(record, "BEV022", f"The quote describes non-human or in-vitro evidence "
                                                      f"({match.group(0)!r}) but the item's scope is human.", path))
        return out
