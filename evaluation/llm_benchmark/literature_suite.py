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
CONDITIONS = ["no_source", "with_source", "naive_paper", "naive_claim"]
# Scenario 1 of the benchmark (issue #31 follow-up): how people ask a chatbot, without the curation rules
# ("never invent", "stop if you cannot verify") and without the source.
#   naive_paper  the claim and the paper's PMID and title; quote the paper's key sentences
#   naive_claim  the claim only; the model picks the papers (PMID, title) and quotes them
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
NAIVE_PAPER_PROMPT = """I'm checking a claim for our cancer variant database. Does the paper below support it? \
Tell me, and quote the key sentences from the paper that show this.

Claim:
{claim}

Paper: {title} (PMID {pmid})

Reply as JSON: decision ("supports", "does_not_support", or "stop" if the paper doesn't address the claim), \
quotes (the paper's key sentences, each with the section or paragraph it comes from), and a short rationale. \
Do not use tools, files or the web."""
NAIVE_CLAIM_PROMPT = """I'm checking a claim for our cancer variant database. What does the published \
literature say about it? Give your conclusion and cite the key papers, quoting the sentences from each paper \
that show it.

Claim:
{claim}

Reply as JSON: decision ("supports", "does_not_support", or "stop" if the literature doesn't address the \
claim), citations (up to three papers, each with its PMID, title and an exact quote), and a short rationale. \
Do not use tools, files or the web."""
CLAIM_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["decision", "citations", "rationale"],
    "properties": {
        "decision": {"type": "string", "enum": DECISIONS},
        "citations": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                 "required": ["pmid", "title", "quote"],
                                                 "properties": {"pmid": {"type": "string"}, "title": {"type": "string"},
                                                                "quote": {"type": "string"}}}},
        "rationale": {"type": "string"},
    },
}


def load_papers() -> dict[str, list[list[str]]]:
    """pmid -> [[id, "title" or "p", text], ...]"""
    return json.loads(gzip.decompress((TASKS / "papers.json.gz").read_bytes()))


def claim_lines(claim: dict[str, str]) -> str:
    return (f"- Molecular profile: {claim['molecular_profile']}\n- Disease: {claim['disease']}\n"
            f"- Evidence type: {claim['evidence_type']}\n- Clinical significance: {claim['significance']}\n"
            f"- Therapies: {claim['therapies'] or 'none'}")


def schema_for(condition: str) -> dict[str, Any]:
    return CLAIM_SCHEMA if condition == "naive_claim" else SCHEMA


def validator_for(condition: str):
    return validate_claim if condition == "naive_claim" else validate


def prompt(task: dict[str, Any], condition: str, papers: dict[str, list[list[str]]]) -> str:
    claim = task["claim"]
    if condition == "naive_paper":
        return NAIVE_PAPER_PROMPT.format(claim=claim_lines(claim), title=task["title"], pmid=task["pmid"])
    if condition == "naive_claim":
        return NAIVE_CLAIM_PROMPT.format(claim=claim_lines(claim))
    # Paragraphs carry their ids; titles are shown as headings without one, since the pilot showed models
    # citing a heading's id for the paragraph beneath it.
    body = ("\n".join(f"[{pid}] {text}" if kind == "p" else f"## {text}" for pid, kind, text in papers[task["pmid"]])
            if condition == "with_source" else NO_TEXT)
    return PROMPT.format(molecular_profile=claim["molecular_profile"], disease=claim["disease"],
                         evidence_type=claim["evidence_type"], significance=claim["significance"],
                         therapies=claim["therapies"] or "none", pmid=task["pmid"], title=task["title"], body=body)


def validate_claim(answer: Any) -> dict[str, Any]:
    if not isinstance(answer, dict) or set(answer) != set(CLAIM_SCHEMA["required"]):
        raise ValueError("answer is not an object with exactly the required fields")
    if answer["decision"] not in DECISIONS or not isinstance(answer["rationale"], str):
        raise ValueError("invalid decision or rationale")
    if not isinstance(answer["citations"], list) or not all(
            isinstance(c, dict) and set(c) == {"pmid", "title", "quote"} and all(isinstance(v, str) for v in c.values())
            for c in answer["citations"]):
        raise ValueError("invalid citations")
    return answer


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
