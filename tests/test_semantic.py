"""Semantic cues (BEV022) and independent review (BEV021): both can only send a record to a human."""
import copy
import json
from pathlib import Path

import pytest
import yaml

from bioevidence_validator.engine import RecordValidator, load_profile
from bioevidence_validator.semantic import CueChecker

ROOT = Path(__file__).resolve().parents[1]


def record(quote="Tumours carrying the variant responded to the drug in 12 of 15 patients.",
           predicate="associated_with", scope=("taxon:synthetic",)):
    data = json.loads((ROOT / "examples/literature_claim/curated_association.json").read_text(encoding="utf-8"))
    data["statement"]["predicate"] = predicate
    data["evidence_items"][0].update(extracted_text=quote, scope=list(scope))
    data["statement"]["scope"] = list(scope)
    return data


def cues(rec, **options):
    checker = CueChecker(negative_predicates={"not_associated_with"}, human_scope={"NCBITaxon:9606"}, **options)
    return [f.message for f in checker.check(rec)]


@pytest.mark.parametrize("quote,predicate,flagged", [
    ("The variant was not associated with response in 40 patients.", "associated_with", True),
    ("Patients with the variant failed to respond to treatment.", "associated_with", True),
    ("No significant difference in survival was observed between groups.", "associated_with", True),
    ("The variant was not associated with response in 40 patients.", "not_associated_with", False),
    ("Tumours carrying the variant responded to the drug in 12 of 15 patients.", "associated_with", False),
    ("Tumours carrying the variant are nonresponsive.", "associated_with", False),  # a known blind spot
])
def test_negation_cue(quote, predicate, flagged):
    assert bool(cues(record(quote, predicate))) is flagged


def test_hedge_cue_is_optional():
    rec = record("These data suggest that the variant may confer sensitivity to the drug.")
    assert cues(rec) == [] and "hedged" in cues(rec, hedges=True)[0]


@pytest.mark.parametrize("quote,flagged", [
    ("Xenografts carrying the variant regressed in treated mice.", True),
    ("Cell lines harbouring the variant were sensitive in vitro.", True),
    ("Patient-derived xenografts from 12 patients regressed.", False),
    ("Tumours carrying the variant responded to the drug in 12 of 15 patients.", False),
])
def test_species_cue_for_human_scope(quote, flagged):
    assert bool(cues(record(quote, scope=("NCBITaxon:9606",)))) is flagged
    assert cues(record(quote, scope=("taxon:synthetic",))) == [] or "negation" in cues(record(quote))[0]


def test_cues_ignore_items_that_do_not_support():
    rec = record("The variant was not associated with response.")
    rec["statement"]["evidence_lines"][0]["direction"] = "contradicts"
    assert cues(rec) == []


def test_cue_findings_route_to_review(tmp_path):
    rec = record("The variant was not associated with response in 40 patients.")
    report = RecordValidator(profile="literature-claim", grounders=[CueChecker()]).validate(rec)
    assert report["overall_status"] == "review_required" and {f["rule_id"] for f in report["findings"]} == {"BEV022"}


def profile_path(tmp_path, flag=True):
    profile = load_profile((ROOT / "src/bioevidence_validator/profiles/literature-claim.yaml").read_bytes())
    profile["uses"]["research_summary"]["require_independent_review"] = flag
    path = tmp_path / "reviewed.yaml"
    path.write_text(yaml.safe_dump(profile), encoding="utf-8")
    return path


def review(decision, reviewer="model:reviewer", agent="software", uses=("research_summary",)):
    return {"id": f"bioev:review-{reviewer}-{decision}", "statement_id": "bioev:synthetic-statement",
            "applies_to_uses": list(uses), "decision": decision, "reviewer": {"id": reviewer, "agent_type": agent},
            "rationale": "Checked the quote against the claim.", "decided_at": "2026-09-29T00:00:00Z"}


@pytest.mark.parametrize("adjudications,status,codes", [
    ([review("accept")], "admitted", set()),
    ([], "review_required", {"BEV021"}),
    ([review("defer")], "review_required", {"BEV021"}),
    ([review("reject")], "review_required", {"BEV021"}),  # a model can send a record to a human, not reject it
    ([review("accept"), review("defer", reviewer="model:second")], "review_required", {"BEV021"}),
    ([review("accept", reviewer="model:extractor")], "review_required", {"BEV021"}),  # not independent
    ([review("accept", agent="human")], "review_required", {"BEV021"}),  # a human is not the model review
    ([review("accept", uses=("knowledge_base",))], "review_required", {"BEV021"}),
])
def test_independent_review(tmp_path, adjudications, status, codes):
    rec = record()
    rec["requested_uses"] = ["research_summary"]
    rec["evidence_items"][0]["created_by"] = {"id": "model:extractor", "agent_type": "software"}
    rec["adjudications"] = copy.deepcopy(adjudications)
    report = RecordValidator(profile=profile_path(tmp_path)).validate(rec)
    assert report["overall_status"] == status and {f["rule_id"] for f in report["findings"]} == codes


def test_independent_review_is_off_unless_asked(tmp_path):
    rec = record()
    rec["adjudications"] = [review("defer")]
    assert RecordValidator(profile=profile_path(tmp_path, flag=False)).validate(rec)["overall_status"] == "admitted"
    with pytest.raises(ValueError, match="require_independent_review"):
        profile = load_profile((ROOT / "src/bioevidence_validator/profiles/literature-claim.yaml").read_bytes())
        profile["uses"]["research_summary"]["require_independent_review"] = "yes"
        load_profile(yaml.safe_dump(profile).encode())
