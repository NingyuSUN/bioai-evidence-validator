"""The literature task: does a paper support a CIViC-style claim, and which sentences show it?

Standard library only, like run_models.py. Paper text comes from `literature_tasks/papers.json.gz`, which
tasks_literature.py writes from the pinned JATS with the same paragraph ids the literature grounder uses.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
TASKS = ROOT / "literature_tasks"
CONDITIONS = ["no_source", "with_source"]
DECISIONS = ["supports", "does_not_support", "stop"]
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["decision", "quotes", "rationale"],
    "properties": {
        "decision": {"type": "string", "enum": DECISIONS},
        "quotes": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                              "required": ["paragraph", "text"],
                                              "properties": {"paragraph": {"type": "string"}, "text": {"type": "string"}}}},
        "rationale": {"type": "string"},
    },
}
PROMPT = """You are assisting a cancer variant curation team. Decide whether the paper below reports evidence \
that supports the claim, or evidence against it, and quote the sentences of the paper that show this.

Claim:
- Molecular profile: {molecular_profile}
- Disease: {disease}
- Evidence type: {evidence_type}
- Clinical significance: {significance}
- Therapies: {therapies}

Rules:
- Do not use tools, files or the web.
- decision: "supports" if the paper reports evidence for the claim; "does_not_support" if it reports \
evidence against it (for example no response, or no association); "stop" if the paper does not address \
this claim or you cannot verify what it says.
- Quote one to three sentences exactly as they appear in the paper, each with the id of its paragraph \
(the text in square brackets). Do not paraphrase, shorten or combine sentences.
- Reply with one JSON object matching the required schema and nothing else.

<paper pmid="{pmid}">
Title: {title}
{body}
</paper>"""
NO_TEXT = "The full text is not provided."


def load_papers() -> dict[str, list[list[str]]]:
    """pmid -> [[id, "title" or "p", text], ...]"""
    return json.loads(gzip.decompress((TASKS / "papers.json.gz").read_bytes()))


def prompt(task: dict[str, Any], condition: str, papers: dict[str, list[list[str]]]) -> str:
    claim = task["claim"]
    # Paragraphs carry their ids; titles are shown as headings without one, since the pilot showed models
    # citing a heading's id for the paragraph beneath it.
    body = ("\n".join(f"[{pid}] {text}" if kind == "p" else f"## {text}" for pid, kind, text in papers[task["pmid"]])
            if condition == "with_source" else NO_TEXT)
    return PROMPT.format(molecular_profile=claim["molecular_profile"], disease=claim["disease"],
                         evidence_type=claim["evidence_type"], significance=claim["significance"],
                         therapies=claim["therapies"] or "none", pmid=task["pmid"], title=task["title"], body=body)


def validate(answer: Any) -> dict[str, Any]:
    if not isinstance(answer, dict) or set(answer) != set(SCHEMA["required"]):
        raise ValueError("answer is not an object with exactly the required fields")
    if answer["decision"] not in DECISIONS or not isinstance(answer["rationale"], str):
        raise ValueError("invalid decision or rationale")
    if not isinstance(answer["quotes"], list) or not all(
            isinstance(q, dict) and set(q) == {"paragraph", "text"} and all(isinstance(v, str) for v in q.values())
            for q in answer["quotes"]):
        raise ValueError("invalid quotes")
    return answer
