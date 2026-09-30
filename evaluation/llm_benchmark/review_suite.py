"""The independent review task: what do quoted passages show about a claim? (Issue #31.)

Standard library only, like run_models.py. A reviewer sees the claim, the paper's title, each quote and the
paragraph it comes from, but never the extractor's decision; it answers with its own reading. Units are
written by semantic.py to `semantic/<split>-units.jsonl`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
UNITS = ROOT / "semantic"
VERDICTS = ["supports", "does_not_support", "not_addressed"]
SOURCES = ["patients", "non_human", "unclear"]
CERTAINTY = ["finding", "hedged"]
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["verdict", "evidence_from", "certainty", "rationale"],
    "properties": {"verdict": {"type": "string", "enum": VERDICTS},
                   "evidence_from": {"type": "string", "enum": SOURCES},
                   "certainty": {"type": "string", "enum": CERTAINTY},
                   "rationale": {"type": "string"}},
}
PROMPT = """You are an independent reviewer for a cancer variant curation team. Another curator extracted the \
quotes below from a paper as evidence about the claim; you do not see their conclusion. Judge only what the \
quoted passages, read in their paragraphs, show.

Claim:
- Molecular profile: {molecular_profile}
- Disease: {disease}
- Evidence type: {evidence_type}
- Clinical significance: {significance}
- Therapies: {therapies}

Paper: {title}

Quoted evidence:
{quotes}

Answer:
- verdict: "supports" if the quoted evidence supports the claim; "does_not_support" if it reports evidence \
against the claim (for example no response, or no association); "not_addressed" if it does not bear on this claim.
- evidence_from: "patients" if the quoted evidence comes from human patients or human samples; "non_human" if \
only from animals, cell lines or other in-vitro work; "unclear" otherwise.
- certainty: "finding" if the quoted evidence states an observed result; "hedged" if it states a possibility, \
suggestion or hypothesis.
- rationale: one or two sentences.

Do not use tools, files or the web. Reply with one JSON object matching the required schema and nothing else."""


def prompt(unit: dict[str, Any]) -> str:
    claim = unit["claim"]
    quotes = "\n".join(f'{n}. "{q["text"]}"' + (f'\n   In its paragraph: "{q["context"]}"' if q.get("context") else "")
                       for n, q in enumerate(unit["quotes"], start=1))
    return PROMPT.format(molecular_profile=claim["molecular_profile"], disease=claim["disease"],
                         evidence_type=claim["evidence_type"], significance=claim["significance"],
                         therapies=claim["therapies"] or "none", title=unit["title"], quotes=quotes)


def validate(answer: Any) -> dict[str, Any]:
    if not isinstance(answer, dict) or set(answer) != set(SCHEMA["required"]):
        raise ValueError("answer is not an object with exactly the required fields")
    if (answer["verdict"] not in VERDICTS or answer["evidence_from"] not in SOURCES
            or answer["certainty"] not in CERTAINTY or not isinstance(answer["rationale"], str)):
        raise ValueError("invalid review answer")
    return answer
