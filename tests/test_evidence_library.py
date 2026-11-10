"""Optional integration tests with synthetic originals and synthetic human reviews only."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from bioevidence_validator import cli
from bioevidence_validator.engine import validate_record
from bioevidence_validator.evidence_library import EvidenceLibraryGrounder

library = pytest.importorskip("evidence_database.store")
pymupdf = pytest.importorskip("pymupdf")
acquisition = pytest.importorskip("evidence_database.acquisition")
packets = pytest.importorskip("evidence_database.packets")

ROOT = Path(__file__).resolve().parents[1]
TITLE = "Synthetic evidence library validation of simulated dose response measurements"
DOI = "10.9999/synthetic.library"
QUOTE = "All synthetic controls showed dose 1.25 mg under explicitly simulated conditions."
OTHER = "This second synthetic quotation has separate and explicitly limited review coverage."


def record_for(source, citation):
    record = json.loads((ROOT / "examples/literature_claim/curated_association.json").read_text(encoding="utf-8"))
    record["source_artifacts"][0].update(uri="doi:" + DOI, title=TITLE, sha256=source["sha256"],
                                         observed_sha256=source["sha256"])
    record["evidence_items"][0].update(locator=citation, extracted_text=QUOTE)
    return record


def conversion(store, source, *, version="1", status="completed", issues=None):
    return store.add_conversion(source["source_id"], parser="synthetic_fixture", parser_version=version,
        blocks=[{"id": "b1", "kind": "paragraph", "text": QUOTE + "\n" + OTHER,
                 "locator": {"page": 1}, "issues": issues or []}], status=status, issues=issues)


@pytest.fixture
def fixture(tmp_path):
    pdf = tmp_path / "synthetic.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_textbox((30, 30, 550, 800), TITLE + "\nhttps://doi.org/" + DOI + "\n" + QUOTE + "\n" + OTHER)
        doc.save(pdf)
    store = library.Store(tmp_path / "library")
    queue = acquisition.AcquisitionQueue(tmp_path / "queue", store)
    metadata = {"doi": DOI, "pmid": "99999999", "title": TITLE, "provider": "synthetic",
                "record_id": "test-only", "provenance": {"matched_records": [{"provider": "europe_pmc",
                "record": {"source": "MED", "id": "99999999", "doi": DOI, "title": TITLE,
                           "pubTypeList": {"pubType": ["research-article"]}}}]}}
    paper = queue.register([metadata], provenance={"purpose": "synthetic integration fixture"})["papers"][0]
    attached = queue.attach(paper["paper_id"], pdf)
    assert attached["identity_status"] == "verified"
    source = store.source(attached["source_id"])
    converted = conversion(store, source)
    citation = converted["citations"][0]
    return {"store": store, "source": source, "citation": citation, "pdf": pdf, "tmp": tmp_path,
            "record": record_for(source, citation), "conversion": converted,
            "metadata": copy.deepcopy(store.ingestion_receipts(source["source_id"])[0]["metadata"])}


def approve(fixture, *, citation=None, quote=QUOTE):
    store = fixture["store"]
    citation = citation or fixture["citation"]
    packet = packets.create_packet(store, citation, fixture["tmp"] / ("packet-" + str(len(store.reviews(citation)))))
    return store.review(citation, quote, decision="approve", reviewer="SYNTHETIC TEST FIXTURE",
                        reviewer_kind="human", note="Synthetic integration test, no real scientific review",
                        viewed_original=True, packet_id=packet["packet_id"])


def codes(fixture, *, record=None):
    grounder = EvidenceLibraryGrounder(fixture["store"].root)
    return {item.rule_id for item in grounder.check(record or fixture["record"])}


def add_receipt(fixture, metadata):
    source = fixture["source"]
    fixture["store"].ingest(fixture["pdf"], source["document_id"], role=source["role"], metadata=metadata)


def test_unreviewed_quote_is_not_verified_even_if_text_matches(fixture):
    grounder = EvidenceLibraryGrounder(fixture["store"].root)
    assert grounder.verified_items(fixture["record"]) == set()
    report = validate_record(fixture["record"], profile="literature-claim", grounders=[grounder])
    assert report["overall_status"] == "review_required"
    assert {item["rule_id"] for item in report["findings"]} == {"BEV015"}
    assert grounder.last_checks[0]["quote_matches"] and not grounder.last_checks[0]["admitted"]


def test_synthetic_original_page_review_admits_extraction_only(fixture):
    review = approve(fixture)
    grounder = EvidenceLibraryGrounder(fixture["store"].root)
    report = validate_record(fixture["record"], profile="literature-claim", grounders=[grounder])
    assert report["overall_status"] == "admitted"
    assert grounder.verified_items(fixture["record"]) == {fixture["record"]["evidence_items"][0]["id"]}
    receipt = grounder.last_checks[0]
    assert receipt["review_id"] == review["review_id"]
    assert receipt["source_sha256"] == fixture["source"]["sha256"]
    assert receipt["scientifically_verified"] is False and receipt["locator"] == {"page": 1}


def test_review_revocation_applies_without_cached_acceptance(fixture):
    approve(fixture)
    grounder = EvidenceLibraryGrounder(fixture["store"].root)
    assert grounder.verified_items(fixture["record"])
    fixture["store"].review(fixture["citation"], QUOTE, decision="revoke", reviewer="SYNTHETIC TEST FIXTURE",
                            reviewer_kind="human", note="Synthetic revocation")
    assert grounder.verified_items(fixture["record"]) == set()
    assert {item.rule_id for item in grounder.check(fixture["record"])} == {"BEV015"}


def test_review_is_quote_specific(fixture):
    approve(fixture, quote=OTHER)
    assert codes(fixture) == {"BEV015"}


def test_new_conversion_does_not_inherit_review(fixture):
    approve(fixture)
    converted = conversion(fixture["store"], fixture["source"], version="2")
    record = record_for(fixture["source"], converted["citations"][0])
    assert codes(fixture, record=record) == {"BEV015"}


def test_inspection_and_ai_review_cannot_supply_human_approval(fixture):
    assert not fixture["store"].check(fixture["citation"], QUOTE, require_review=False)["admitted"]
    fixture["store"].review(fixture["citation"], QUOTE, decision="reject", reviewer="SYNTHETIC AI",
                            reviewer_kind="ai", note="Synthetic diagnostic only")
    assert codes(fixture) == {"BEV015"}


@pytest.mark.parametrize("quote", ["An invented finding absent from the original paper.", "dose 1", ""])
def test_quote_mismatch_numeric_truncation_and_empty_quote(fixture, quote):
    record = copy.deepcopy(fixture["record"])
    record["evidence_items"][0]["extracted_text"] = quote
    assert codes(fixture, record=record) == {"BEV017" if quote else "BEV015"}


@pytest.mark.parametrize("citation", ["page 1", "doi:" + DOI, "evidence:" + "a" * 64 + "#b1",
                                      "evidence:../../private#b1"])
def test_non_library_locators_cannot_fall_back_to_matching_text(fixture, citation):
    record = copy.deepcopy(fixture["record"])
    record["evidence_items"][0]["locator"] = citation
    assert codes(fixture, record=record) == {"BEV015"}


def test_unknown_block_does_not_fall_back_to_text_elsewhere(fixture):
    record = copy.deepcopy(fixture["record"])
    record["evidence_items"][0]["locator"] = fixture["citation"].replace("#b1", "#not-there")
    assert codes(fixture, record=record) == {"BEV017"}


@pytest.mark.parametrize("block_id", ["section:paragraph.1-part_2", "b" + "_" * 199])
def test_library_block_id_contract_includes_colons_and_maximum_length(fixture, block_id):
    converted = fixture["store"].add_conversion(fixture["source"]["source_id"], parser="synthetic_fixture",
        parser_version="block-id-contract", blocks=[{"id": block_id, "kind": "paragraph", "text": QUOTE,
                                                     "locator": {"page": 1}}])
    citation = converted["citations"][0]
    approve(fixture, citation=citation)
    assert codes(fixture, record=record_for(fixture["source"], citation)) == set()


@pytest.mark.parametrize("block_id", [":leading-colon", ".leading-period", "b" * 201])
def test_invalid_library_block_id_contract_is_rejected_before_lookup(fixture, block_id):
    citation = fixture["citation"].split("#", 1)[0] + "#" + block_id
    assert codes(fixture, record=record_for(fixture["source"], citation)) == {"BEV015"}


@pytest.mark.parametrize(("key", "value"), [("sha256", "b" * 64), ("uri", "pmid:12345"),
                                          ("title", "A different paper with an incompatible scientific title")])
def test_wrong_hash_identifier_or_title_is_rejected(fixture, key, value):
    record = copy.deepcopy(fixture["record"])
    record["source_artifacts"][0][key] = value
    assert codes(fixture, record=record) == {"BEV017"}


def test_missing_publication_identifier_is_pending(fixture):
    record = copy.deepcopy(fixture["record"])
    record["source_artifacts"][0]["uri"] = "https://example.org/synthetic.pdf"
    assert codes(fixture, record=record) == {"BEV015"}


def test_source_type_spoof_does_not_skip_publication_identity(fixture):
    record = copy.deepcopy(fixture["record"])
    record["source_artifacts"][0].update(source_type="dataset_snapshot", uri="doi:10.9999/wrong")
    assert codes(fixture, record=record) == {"BEV017"}


@pytest.mark.parametrize("retracted", [False, True])
def test_declared_type_uri_and_evidence_type_cannot_hide_stored_publication(fixture, retracted):
    approve(fixture)
    if retracted:
        metadata = fixture["metadata"]
        metadata["literature"]["provenance"]["matched_records"][0]["record"]["pubTypeList"] = {
            "pubType": ["Retracted Publication"]}
        add_receipt(fixture, metadata)
    record = copy.deepcopy(fixture["record"])
    record["source_artifacts"][0].update(source_type="dataset_snapshot", uri="https://example.org/dataset.pdf")
    record["evidence_items"][0]["evidence_type"] = "dataset_result"
    record.update(profile_id="general", requested_uses=["research_summary"])
    report = validate_record(record, profile="general", grounders=[EvidenceLibraryGrounder(fixture["store"].root)])
    assert report["schema_valid"]
    assert report["overall_status"] == ("rejected" if retracted else "review_required")
    assert {f["rule_id"] for f in report["findings"]} == {"BEV019" if retracted else "BEV015"}


def test_retraction_in_later_receipt_overrides_earlier_nonretracted_receipt(fixture):
    approve(fixture)
    metadata = fixture["metadata"]
    metadata["literature"]["provenance"]["matched_records"][0]["record"]["pubTypeList"] = {
        "pubType": ["Retracted Publication"]}
    add_receipt(fixture, metadata)
    assert codes(fixture) == {"BEV019"}


def test_crossref_retraction_is_recomputed_offline(fixture):
    metadata = fixture["metadata"]
    metadata["literature"]["provenance"]["matched_records"].append({"provider": "crossref", "record": {
        "DOI": DOI, "title": [TITLE], "updated-by": [{"type": "retraction"}]}})
    add_receipt(fixture, metadata)
    assert codes(fixture) == {"BEV019"}


def test_pmc_retraction_without_pdf_url_is_still_blocking(fixture):
    approve(fixture)
    metadata = fixture["metadata"]
    metadata["literature"]["pmcid"] = "PMC99999999"
    metadata["literature"]["provenance"]["providers"] = [{"provider": "pmc_cloud", "requests": [
        {"raw_response": "<?xml version='1.0'?><ListBucketResult />"},
        {"raw_response": json.dumps({"pmcid": "PMC99999999", "doi": DOI, "is_retracted": True})}]}]
    add_receipt(fixture, metadata)
    assert codes(fixture) == {"BEV019"}


def test_unrelated_pmc_retraction_is_not_bound_by_filename_or_provider_alone(fixture):
    approve(fixture)
    metadata = fixture["metadata"]
    metadata["literature"]["provenance"]["providers"] = [{"provider": "pmc_cloud", "requests": [
        {"raw_response": json.dumps({"pmcid": "PMC12345", "doi": "10.9999/unrelated", "is_retracted": True})}]}]
    add_receipt(fixture, metadata)
    assert not codes(fixture)


def test_pmc_raw_response_hash_is_verified_when_present(fixture):
    metadata = fixture["metadata"]
    metadata["literature"]["provenance"]["providers"] = [{"provider": "pmc_cloud", "requests": [
        {"raw_response": json.dumps({"pmcid": "PMC99999999", "doi": DOI, "is_retracted": False}),
         "sha256": "0" * 64}]}]
    add_receipt(fixture, metadata)
    assert codes(fixture) == {"BEV014"}


def test_secondary_provider_identifier_conflict_cannot_hide_behind_matching_doi(fixture):
    metadata = fixture["metadata"]
    metadata["literature"]["provenance"]["matched_records"][0]["record"]["id"] = "12345"
    add_receipt(fixture, metadata)
    assert codes(fixture) == {"BEV017"}


def test_old_import_without_original_identity_receipt_requires_review(fixture):
    store = library.Store(fixture["tmp"] / "old-import")
    source = store.ingest(fixture["pdf"], "old-original")
    cv = conversion(store, source)
    grounder = EvidenceLibraryGrounder(store.root)
    assert {f.rule_id for f in grounder.check(record_for(source, cv["citations"][0]))} == {"BEV015"}


def test_supplement_cannot_inherit_primary_identity(fixture):
    store = fixture["store"]
    source = store.ingest(fixture["pdf"], "synthetic-supplement", role="supplement", metadata=fixture["metadata"])
    cv = conversion(store, source)
    assert codes(fixture, record=record_for(source, cv["citations"][0])) == {"BEV015"}


def test_tampered_original_rejects_previously_reviewed_quote(fixture):
    approve(fixture)
    Path(fixture["source"]["path"]).write_bytes(b"tampered original")
    assert codes(fixture) == {"BEV014"}


def test_partial_warnings_survive_specific_quote_approval(fixture):
    cv = conversion(fixture["store"], fixture["source"], version="partial", status="partial", issues=["synthetic-warning"])
    citation = cv["citations"][0]
    approve(fixture, citation=citation)
    grounder = EvidenceLibraryGrounder(fixture["store"].root)
    assert not grounder.check(record_for(fixture["source"], citation))
    receipt = grounder.last_checks[0]
    assert receipt["conversion_status"] == "partial"
    assert receipt["conversion_issues"] == ["synthetic-warning"] and receipt["block_issues"] == ["synthetic-warning"]


def test_other_grounder_union_cannot_override_missing_review(fixture):
    class Permissive:
        name = "synthetic-permissive-grounder"

        def verified_items(self, record):
            return {item["id"] for item in record["evidence_items"]}

        def check(self, record):
            return []

    grounder = EvidenceLibraryGrounder(fixture["store"].root)
    report = validate_record(fixture["record"], profile="literature-claim", grounders=[Permissive(), grounder])
    assert report["overall_status"] == "review_required" and report["findings"][0]["rule_id"] == "BEV015"


def test_validation_does_not_change_library_bytes(fixture):
    def snapshot():
        return {str(p.relative_to(fixture["store"].root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in fixture["store"].root.rglob("*") if p.is_file()}
    before = snapshot()
    assert codes(fixture) == {"BEV015"}
    assert snapshot() == before


def test_missing_library_is_not_created(tmp_path):
    with pytest.raises(ValueError, match="does not exist|Missing|missing"):
        EvidenceLibraryGrounder(tmp_path / "absent")
    assert not (tmp_path / "absent").exists()


def test_missing_optional_package_is_an_explicit_error(monkeypatch, tmp_path):
    from bioevidence_validator import evidence_library
    def missing(name):
        raise ImportError("Synthetic missing optional package")
    monkeypatch.setattr(evidence_library.importlib, "import_module", missing)
    with pytest.raises(ValueError, match="independent local-evidence-database package"):
        EvidenceLibraryGrounder(tmp_path)


def test_cli_includes_version_bound_check_receipts(fixture, capsys):
    path = fixture["tmp"] / "record.json"
    path.write_text(json.dumps(fixture["record"]), encoding="utf-8")
    assert cli.main(["validate", str(path), "--profile", "literature-claim", "--evidence-library",
                     str(fixture["store"].root)]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["grounding"] == ["evidence-library"]
    assert report["evidence_library"]["checks"][0]["citation"] == fixture["citation"]
    assert report["evidence_library"]["scientifically_verified"] is False


def test_cli_refuses_output_inside_read_only_store(fixture, capsys):
    path = fixture["tmp"] / "record.json"
    path.write_text(json.dumps(fixture["record"]), encoding="utf-8")
    assert cli.main(["validate", str(path), "--evidence-library", str(fixture["store"].root),
                     "--output", str(fixture["store"].root / "index.sqlite3")]) == 3
    assert "outside the read-only" in capsys.readouterr().err
    assert fixture["store"].audit()["ok"]


def test_cli_rejects_legacy_database_flag_with_library():
    with pytest.raises(SystemExit):
        cli.parser().parse_args(["validate", "record.json", "--evidence-db", "old", "--evidence-library", "new"])


def test_no_flag_preserves_old_report_shape(capsys):
    assert cli.main(["validate", str(ROOT / "examples/literature_claim/curated_association.json"),
                     "--profile", "literature-claim"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert "grounding" not in report and "evidence_library" not in report
