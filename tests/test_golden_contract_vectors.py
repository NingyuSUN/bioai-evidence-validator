"""Cross-repository contract tests using synthetic originals and review events."""
import hashlib
import json
import re
from operator import itemgetter
from pathlib import Path
from unittest.mock import Mock

import pytest

from bioevidence_validator import evidence_mcp
from bioevidence_validator.engine import validate_record
from bioevidence_validator.evidence_library import IDENTITY_RULE_VERSIONS, EvidenceLibraryGrounder

FIXTURE = Path(__file__).parent / "fixtures" / "golden_contract_vectors_v1.json"
FIXTURE_SHA256 = "c177b91e7037f7e6562671a7a400da91f6bcd61a262cc23d90831252e0721d2a"
VECTORS = json.loads(FIXTURE.read_bytes())
DOCUMENT = VECTORS["fixture_document"]
BLOCKS = {block["id"]: block for block in DOCUMENT["blocks"]}
MEMORY = VECTORS["memory_ledger_and_pitfall_vectors"]
RECORD_TEMPLATE = Path(__file__).resolve().parents[1] / "examples/literature_claim/curated_association.json"


def test_fixture_sha256():
    assert FIXTURE.is_file()
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256


@pytest.fixture
def store(tmp_path):
    return pytest.importorskip("evidence_database.store").Store(tmp_path / "library")


def literature_record(citation, quote, sha256):
    record = json.loads(RECORD_TEMPLATE.read_bytes())
    record["source_artifacts"][0].update(
        uri="doi:" + DOCUMENT["doi"], title=DOCUMENT["title"], sha256=sha256, observed_sha256=sha256
    )
    record["evidence_items"][0].update(locator=citation, extracted_text=quote)
    return record


@pytest.mark.parametrize("vec", VECTORS["citation_vectors"], ids=itemgetter("id"))
def test_citation_contract(vec, store):
    citation = vec["citation"]
    strict = re.fullmatch(r"^evidence:cv_[0-9a-f]{64}#b\d+$", citation) is not None
    assert strict is vec["valid"]
    assert strict is vec["ro_citation_re_valid"]
    assert bool(evidence_mcp.CITATION.fullmatch(citation)) is vec["library_citation_valid"]
    if not vec["library_citation_valid"]:
        grounder = EvidenceLibraryGrounder(store.root)
        observed_store = Mock(wraps=grounder.store)
        grounder.store = observed_store
        record = literature_record(citation, BLOCKS["b1"]["sentence_1"], "a" * 64)
        assert [finding.rule_id for finding in grounder.check(record)] == [vec["expected_validator_malformed_rule"]]
        assert observed_store.mock_calls == []


def attach_document(tmp_path, store, *, degree_vector=None):
    from evidence_database.acquisition import AcquisitionQueue

    pymupdf = pytest.importorskip("pymupdf")
    pdf = tmp_path / "synthetic.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        header = DOCUMENT["title"] + "\nhttps://doi.org/" + DOCUMENT["doi"]
        assert page.insert_textbox((30, 15, 550, 78), header, fontsize=11) >= 0
        for block in DOCUMENT["blocks"]:
            assert page.insert_textbox(block["locator"]["bbox"], block["text"], fontsize=11) >= 0
        if degree_vector is not None:
            page.insert_text((30, 260), degree_vector["cjk_degree_line"],
                             fontname=degree_vector["pymupdf_cjk_fontname"], fontsize=12)
        doc.save(pdf)

    metadata = {key: DOCUMENT[key] for key in ("document_id", "title", "doi", "pmid", "role")}
    metadata["provenance"] = {"matched_records": [{"provider": "europe_pmc", "record": DOCUMENT["europe_pmc_record"]}]}
    queue = AcquisitionQueue(tmp_path / "queue", store)
    paper, = queue.register([metadata], provenance={"purpose": "synthetic contract fixture"})["papers"]
    return pdf, queue.attach(paper["paper_id"], pdf)


@pytest.fixture
def acquired_source(tmp_path, store):
    _, state = attach_document(tmp_path, store)
    assert state["identity_status"] == "verified"
    return store.source(state["source_id"])


def convert_document(store, source, *, matching_ocr=False):
    blocks = []
    for original in DOCUMENT["blocks"]:
        block = {key: original[key] for key in ("id", "kind", "text", "locator")}
        block.update(superscripts=[], symbol_font_spans=[])
        if matching_ocr:
            block["independent_reading"] = {"text": block["text"], "engine": "synthetic", "engine_version": "1"}
        blocks.append(block)
    conversion = store.add_conversion(source["source_id"], parser="synthetic", parser_version="1", blocks=blocks)
    return {citation.split("#")[1]: citation for citation in conversion["citations"]}


def record_review(tmp_path, store, citation, quote, *, with_packet, **event):
    from evidence_database.packets import create_packet

    packet_id = None
    if with_packet:
        directory = tmp_path / f"packet-{len(store.reviews(citation))}"
        packet_id = create_packet(store, citation, directory)["packet_id"]
    store.review(citation, quote, packet_id=packet_id, **event)


def validator_result(store, source, citation, quote, *, accept_independent_reading=False):
    grounder = EvidenceLibraryGrounder(store.root, accept_independent_reading=accept_independent_reading)
    record = literature_record(citation, quote, source["sha256"])
    report = validate_record(record, profile="literature-claim", grounders=[grounder])
    check, = grounder.last_checks
    return {
        "verified": check["verified"],
        "overall_status": report["overall_status"],
        "rule_ids": [finding["rule_id"] for finding in report["findings"]],
    }


def test_identity_rule_versions():
    assert IDENTITY_RULE_VERSIONS == frozenset({2, 3})


@pytest.mark.parametrize("vec", VECTORS["identity_rule_vectors"], ids=itemgetter("id"))
def test_identity_rule_contract(vec, tmp_path, store):
    from evidence_database.store import Store

    if vec["mode"] == "ingested_receipt":
        pdf, state = attach_document(tmp_path, store)
        assert state["identity_status"] == "verified"
        receipt, = store.ingestion_receipts(state["source_id"])
        metadata = receipt["metadata"]
        metadata["identity_check"].update(
            identity_rule_version=vec["identity_rule_version"], status=vec["identity_status"],
            title_match=vec["title_match"], supplementary_frontmatter=vec["supplementary_frontmatter"],
        )
        expected = vec["expected_validator"]
    else:
        assert vec["mode"] == "acquisition_attach_pdf"
        pdf, state = attach_document(tmp_path, store, degree_vector=vec)
        attachment, = state["attachments"]
        identity = attachment["identity"]
        assert state["metadata"]["role"] == vec["role"]
        assert identity["title_match"] is True and identity["doi_match"] is True
        assert identity["status"] == state["identity_status"]
        assert {
            "identity_rule_version": identity["identity_rule_version"],
            "degree_record_wording": identity["degree_record_wording"],
            "identity_status": state["identity_status"],
            "availability": state["availability"],
            "reason": state["last_failure"],
            "source_ingested": state["source_id"] is not None,
        } == vec["expected_acquisition"]
        assert store.sources() == []
        metadata = {"literature": state["metadata"], "identity_check": identity}
        expected = vec["expected_validator_if_ingested"]

    # Replay only this receipt so a separately verified identity cannot mask the case under test.
    replay = Store(tmp_path / "replay")
    source = replay.ingest(pdf, DOCUMENT["document_id"], role=DOCUMENT["role"], metadata=metadata)
    citation = convert_document(replay, source)["b1"]
    quote = BLOCKS["b1"]["sentence_1"]
    record_review(tmp_path, replay, citation, quote, with_packet=True, decision="approve",
                  reviewer="SYNTHETIC_CURATOR", reviewer_kind="human", viewed_original=True, note="Synthetic review")
    assert replay.check(citation, quote)["admission_route"] == "human_review"
    assert validator_result(replay, source, citation, quote) == {
        "verified": expected["identity_confirmed"],
        "overall_status": expected["overall_status_when_quote_approved"],
        "rule_ids": expected["rule_ids_when_quote_approved"],
    }


@pytest.mark.parametrize("vec", VECTORS["quote_admission_vectors"], ids=itemgetter("id"))
def test_quote_admission_contract(vec, tmp_path, store, acquired_source):
    citations = convert_document(store, acquired_source, matching_ocr=vec["has_matching_ocr"])
    citation, quote = citations[vec["block_id"]], vec["quote"]
    for event in vec["review_events"]:
        record_review(tmp_path, store, citation, quote, **event)

    accept = vec["accept_independent_reading"]
    checked = store.check(citation, quote, accept_independent_reading=accept)
    expected = vec["expected_evidport"]
    for key in ("quote_matches", "admitted", "admission_route", "reason", "review_status", "scientifically_verified"):
        assert checked[key] == expected[key], key
    suggestions = [entry["quote"] for entry in checked["suggested_quotes"]]
    assert bool(suggestions) is expected["suggested_quotes_nonempty"]
    if "expected_suggested_quotes" in expected:
        assert suggestions == expected["expected_suggested_quotes"]
    result = validator_result(store, acquired_source, citation, quote, accept_independent_reading=accept)
    assert result == vec["expected_validator"]


def test_memory_code_contract():
    pytest.importorskip("evidence_database")
    from evidence_database.memory import MEMORY_CODES
    from evidence_database.triage import RULE_TO_MEMORY_CODE

    rule_codes = {rule: code for rule, code in RULE_TO_MEMORY_CODE.items() if rule.startswith("BEV")}
    assert rule_codes == MEMORY["rule_to_memory_code_mapping"]
    assert MEMORY_CODES == tuple(MEMORY["memory_codes"])


@pytest.mark.parametrize("vec", MEMORY["import_vectors"], ids=itemgetter("id"))
def test_memory_import_contract(vec, tmp_path, store, acquired_source):
    from evidence_database.mcp_evidence import EvidenceTools
    from evidence_database.memory import MemoryLedger
    from evidence_database.triage import import_validator_report

    citations = convert_document(store, acquired_source)
    anchors = [{"source": DOCUMENT["document_id"], "block_id": vec["anchor_block"], "quote": vec["anchor_quote"]}]
    for sibling in vec["sibling_blocks"]:
        anchors.append({"source": DOCUMENT["document_id"], "block_id": sibling, "quote": BLOCKS[sibling]["text"]})
    facet = {key: vec[key] for key in ("verdict", "reason", "claim_fact", "source_fact")}
    report = {
        "findings": [{"rule_id": vec["validator_rule"]}],
        "semantic_review": {
            "checks": {vec["facet_name"]: {**facet, "evidence": anchors}},
            "reviewed_quotes": [{**anchor, "citation": citations[anchor["block_id"]]} for anchor in anchors],
        },
    }

    citation, quote = citations[vec["anchor_block"]], vec["anchor_quote"]
    before = store.check(citation, quote)
    assert before["quote_matches"] is True
    ledger = MemoryLedger(tmp_path / "memory", other_roots=(store.root,))
    imported = import_validator_report([report], store=store, ledger=ledger)
    assert imported["added_count"] == 1
    invariants = MEMORY["public_note_invariants"]
    assert invariants["alters_store_check_admission"] is False
    assert store.check(citation, quote) == before

    tools = EvidenceTools(store.root, tmp_path / "review", memory_root=ledger.root)
    note, = tools.check_quote(citation, quote)["memory"]["notes"]
    assert [note["memory_id"]] == imported["added_memory_ids"]
    assert note["code"] == vec["expected_memory_code"]
    assert note["citation"] == citation
    assert note["related_citations"] == [citations[sibling] for sibling in vec["sibling_blocks"]]
    assert note["citable"] is vec["expected_citable"] is invariants["citable"]
    assert note["authority"] == invariants["authority"]
    assert note["scientifically_verified"] is invariants["scientifically_verified"]
    assert ("actor" not in note) is invariants["omits_local_actor"]
