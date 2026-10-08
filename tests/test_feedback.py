"""The feedback loop: what goes back to the proposer, what goes to an expert, and what is carried."""
import copy
import hashlib

from test_reference_grounders import CELLS, CL, MARKERS, TABLE, base

from bioevidence_validator.crosscheck import ReferenceGrounder
from bioevidence_validator.engine import RecordValidator
from bioevidence_validator.feedback import EXPERT, carry, reasons, revise, to_expert, where
from bioevidence_validator.grounding import SnapshotStore
from bioevidence_validator.tables import TableGrounder

SHA = hashlib.sha256(TABLE).hexdigest()


def annotation(target, genes, *, against=()):
    """A cluster annotated as `target`, citing marker genes of cluster 3 (and some against it)."""
    record = base(object={"id": target, "label": CL.terms[target].name if target in CL.terms else "T cell",
                          "entity_type": "cell_type"})
    record["source_artifacts"][0].update(sha256=SHA, observed_sha256=SHA)
    items = [{"id": f"bioev:item-{n}", "source_artifact_id": "bioev:source-1", "locator": f"cluster=3;gene={gene}",
              "extracted_text": text, "evidence_type": "marker_gene", "extraction_method": "deterministic_parser",
              "scope": ["taxon:synthetic"]} for n, (gene, text) in enumerate([*genes, *against], start=1)]
    record["evidence_items"] = items
    lines = [{"id": "bioev:line-1", "direction": "supports", "evidence_item_ids": [i["id"] for i in items[:len(genes)]]}]
    if against:
        lines.append({"id": "bioev:line-2", "direction": "contradicts",
                      "evidence_item_ids": [i["id"] for i in items[len(genes):]]})
    record["statement"]["evidence_lines"] = lines
    return record


def validator(*extra):
    tables = TableGrounder(SnapshotStore({SHA: lambda: TABLE}), ["marker_gene"])
    return RecordValidator(grounders=[tables, CELLS, *extra])


def test_reasons_point_at_what_to_fix():
    record = annotation("CL:0000084", [("CD8A", "logfc=3.0"), ("CD8B", "")])
    record["statement"]["object"]["label"] = "B cell"
    report = validator().validate(record)
    lines = reasons(record, report)
    assert any(line.startswith("evidence 1 (cluster=3;gene=CD8A): The row") for line in lines)
    assert any(line.startswith("evidence 2 (cluster=3;gene=CD8B): No row") for line in lines)
    assert any(line.startswith("object label: The label 'B cell'") for line in lines)
    assert where(record, "$.source_artifacts[0]") == "source 1" and where(record, "$.statement.scope") == "statement.scope"


def test_conflicts_go_to_an_expert_and_are_not_fed_back():
    record = annotation("CL:0000084", [("CD8A", "call=up")], against=[("CD19", "call=absent")])
    report = validator().validate(record)
    assert {f["rule_id"] for f in report["findings"]} == {"BEV004"} and to_expert(report)
    assert reasons(record, report) == []
    marker = ReferenceGrounder(MARKERS, label="ASCT+B", evidence_key="gene", relation="marker_of", ontology=CL)
    record = annotation("CL:0000084", [("CD19", "")])
    report = validator(marker).validate(record)
    assert to_expert(report) and reasons(record, report) == []
    assert "BEV025" in EXPERT and not to_expert({"overall_status": "admitted", "findings": [{"rule_id": "BEV004"}]})


def test_policy_findings_go_to_a_person_not_back_to_the_agent():
    record = annotation("CL:0000625", [("CD8A", "logfc=2.41")])
    for item in record["evidence_items"]:
        item["extraction_method"] = "llm_extraction"
    report = validator().validate(record)
    assert {f["rule_id"] for f in report["findings"]} == {"BEV008"} and to_expert(report)
    assert reasons(record, report) == []
    record["evidence_items"][0]["locator"] = "cluster=3;gene=CD8B"  # a fixable finding as well: fed back
    report = validator().validate(record)
    assert not to_expert(report) and [r.split(":")[0] for r in reasons(record, report)] == ["evidence 1 (cluster=3;gene=CD8B)"]


def test_carry_keeps_verified_evidence_in_its_line():
    previous = annotation("CL:0000084", [("CD8A", "call=up")], against=[("CD19", "call=absent")])
    new = annotation("CL:0000084", [("CD8A", "call=up")])
    merged = carry(previous, {"bioev:item-1", "bioev:item-2"}, new)
    assert [i["locator"] for i in merged["evidence_items"]] == ["cluster=3;gene=CD8A", "cluster=3;gene=CD19"]
    lines = {line["direction"]: line["evidence_item_ids"] for line in merged["statement"]["evidence_lines"]}
    assert lines == {"supports": ["bioev:item-1"], "contradicts": ["bioev:item-2"]}
    assert new["evidence_items"][0]["id"] == "bioev:item-1" and len(new["evidence_items"]) == 1  # not modified
    other = copy.deepcopy(new)
    other["source_artifacts"][0].update(id="bioev:other", sha256="c" * 64, observed_sha256="c" * 64)
    other["evidence_items"][0]["source_artifact_id"] = "bioev:other"
    merged = carry(previous, {"bioev:item-1"}, other)
    assert [s["id"] for s in merged["source_artifacts"]] == ["bioev:other", "bioev:source-1"]
    assert merged["evidence_items"][1]["id"] == "bioev:item-1-2"  # a fresh id, no collision
    changed = annotation("CL:0000625", [("CD8A", "call=up")])  # another claim: nothing is carried
    assert carry(previous, {"bioev:item-1", "bioev:item-2"}, changed) == changed


def test_revise_fixes_then_admits():
    attempts, seen = [], []
    wrong = annotation("CL:0000084", [("CD8A", "logfc=3.0")])
    right = annotation("CL:0000625", [("CD8A", "logfc=2.41")])

    def propose(feedback):
        seen.append(feedback)
        return [wrong, right][len(seen) - 1]

    attempts = revise(propose, validator())
    assert [a.report["overall_status"] for a in attempts] == ["rejected", "admitted"]
    assert seen[0] == [] and seen[1] and seen[1] == attempts[0].feedback


def test_revise_cannot_withdraw_verified_evidence_against_it():
    first = annotation("CL:0000084", [("CD8A", "logfc=3.0")], against=[("CD19", "call=absent")])
    second = annotation("CL:0000084", [("CD8A", "logfc=2.41")])  # fixed the value, dropped the evidence against
    proposals = iter([first, second])
    attempts = revise(lambda feedback: next(proposals), validator())
    assert [a.report["overall_status"] for a in attempts] == ["rejected", "review_required"]
    assert to_expert(attempts[-1].report) and len(attempts[-1].record["evidence_items"]) == 2


def test_revise_stops_when_the_proposer_stops_or_rounds_run_out():
    assert revise(lambda feedback: None, validator()) == []
    wrong = annotation("CL:9999999", [("CD8A", "")])
    attempts = revise(lambda feedback: copy.deepcopy(wrong), validator(), rounds=2)
    assert len(attempts) == 2 and all(a.report["overall_status"] == "rejected" for a in attempts)
    broken = {"record_id": "x"}
    attempts = revise(lambda feedback: broken, validator(), rounds=1)
    assert attempts[0].report["schema_valid"] is False
