"""Literature grounding with synthetic papers and recorded resolver responses; never touches the network."""
import copy
import json
import urllib.error
from pathlib import Path

import pytest
import yaml

from bioevidence_validator import cli, literature
from bioevidence_validator.engine import RecordValidator, load_profile
from bioevidence_validator.literature import LiteratureGrounder, ground_record, identifier, normalize

ROOT = Path(__file__).resolve().parents[1]
EPMC = literature.EUROPE_PMC
PAPER_A = b"""<?xml version="1.0" encoding="UTF-8"?>
<article><front><article-meta><title-group>
<article-title>Loss-of-function variants in SYNG1 cause a recessive retinal dystrophy</article-title>
</title-group><abstract><p id="abs1">We describe biallelic loss-of-function variants in SYNG1 in five families.</p>
</abstract></article-meta></front><body><sec><title>Results</title>
<p id="p1">All affected individuals carried biallelic SYNG1 variants and showed early retinal degeneration.</p>
<p id="p2">No association was observed between SYNG1 variants and hearing loss in the mouse model.</p>
</sec></body></article>"""
PAPER_B = b"""<?xml version="1.0" encoding="UTF-8"?>
<article><front><article-meta><title-group><article-title>A survey of synthetic kinase expression in yeast</article-title>
</title-group></article-meta></front><body><p id="p1">Expression of the synthetic kinase was stable across all tested strains.</p>
</body></article>"""
QUOTE = "All affected individuals carried biallelic SYNG1 variants and showed early retinal degeneration."


def epmc(hit=None):
    return json.dumps({"resultList": {"result": [hit] if hit else []}}).encode()


def hit(pmid, pmcid, title, oa=True, pub_types=("research-article",), corrections=()):
    return {"pmid": pmid, "pmcid": pmcid, "doi": f"10.9999/syn.{pmid}", "title": title, "isOpenAccess": "Y" if oa else "N",
            "license": "cc by", "pubTypeList": {"pubType": list(pub_types)},
            "commentCorrectionList": {"commentCorrection": [{"type": c} for c in corrections]}}


TITLE_A = "Loss-of-function variants in SYNG1 cause a recessive retinal dystrophy"
RESPONSES = {
    literature._search_url("pmid:1001"): epmc(hit("1001", "PMC1001", TITLE_A)),
    f"{EPMC}/PMC1001/fullTextXML": PAPER_A,
    literature._search_url("pmid:1002"): epmc(hit("1002", "PMC1002", "A survey of synthetic kinase expression in yeast")),
    f"{EPMC}/PMC1002/fullTextXML": PAPER_B,
    literature._search_url("pmid:1003"): epmc(hit("1003", "PMC1003", TITLE_A, pub_types=("Retracted Publication",))),
    f"{EPMC}/PMC1003/fullTextXML": PAPER_A,
    literature._search_url("pmid:1004"): epmc(hit("1004", None, TITLE_A, oa=False)),
    literature._search_url("pmid:1005"): epmc(hit("1005", "PMC1005", TITLE_A, corrections=("Retraction in",))),
    f"{EPMC}/PMC1005/fullTextXML": PAPER_A,
    literature._search_url("pmid:9999999"): epmc(),
    literature._search_url("doi:10.9999/crossref.only"): epmc(),
    literature.CROSSREF + "10.9999/crossref.only": json.dumps({"message": {
        "DOI": "10.9999/crossref.only", "title": [TITLE_A], "updated-by": [{"type": "retraction"}]}}).encode(),
    literature._search_url("doi:10.9999/nowhere"): epmc(),
}


class Fetcher:
    def __init__(self, responses=RESPONSES):
        self.responses, self.calls = responses, []

    def __call__(self, url):
        self.calls.append(url)
        if url not in self.responses:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        return self.responses[url]


def claim(uri="pmid:1001", quote=QUOTE, locator="pmc#p1", title=TITLE_A):
    record = json.loads((ROOT / "examples/literature_claim/curated_association.json").read_text(encoding="utf-8"))
    record["source_artifacts"][0].update(uri=uri, title=title)
    record["evidence_items"][0].update(extracted_text=quote, locator=locator)
    return record


def grounded(record, tmp_path, fetch=None):
    record, _ = ground_record(record, tmp_path / "snapshots", fetch or Fetcher(), now="2026-09-29T00:00:00+00:00")
    return record


def check(record, tmp_path):
    grounder = LiteratureGrounder.from_directory(tmp_path / "snapshots")
    return sorted({f.rule_id for f in grounder.check(record)}), grounder.verified_items(record)


@pytest.mark.parametrize("uri,key", [
    ("pmid:0001001", "pmid:1001"), ("PMID: 1001", "pmid:1001"), ("pmcid:pmc77", "pmcid:PMC77"),
    ("doi:10.1000/ABC", "doi:10.1000/abc"), ("https://doi.org/10.1000/ABC", "doi:10.1000/abc"),
    ("https://example.org/x", None), ("pmid:abc", None), ("doi:11.1/x", None),
])
def test_identifier(uri, key):
    assert identifier(uri) == key


def test_normalize_plain_punctuation_and_spaces():
    assert normalize("“No  association” – in\nmice") == '"No association" - in mice'


def test_ground_pins_metadata_full_text_and_the_record_hash(tmp_path):
    fetch = Fetcher()
    record = grounded(claim(), tmp_path, fetch)
    catalog = json.loads((tmp_path / "snapshots/literature.json").read_text(encoding="utf-8"))
    entry = catalog["works"]["pmid:1001"]
    assert entry["resolver"] == "europepmc" and entry["fulltext_sha256"] == record["source_artifacts"][0]["sha256"]
    assert (tmp_path / "snapshots" / f"{entry['fulltext_sha256']}.xml").read_bytes() == PAPER_A
    assert record["source_artifacts"][0]["retrieved_at"] == "2026-09-29T00:00:00+00:00"
    calls = len(fetch.calls)
    grounded(claim(), tmp_path, fetch)
    assert len(fetch.calls) == calls  # already in the catalog
    ground_record(claim(), tmp_path / "snapshots", fetch, refresh=True)
    assert len(fetch.calls) == calls * 2


def test_verified_quote(tmp_path):
    record = grounded(claim(), tmp_path)
    assert check(record, tmp_path) == ([], {"bioev:item-1"})
    elsewhere = grounded(claim(locator="no anchor"), tmp_path)
    assert check(elsewhere, tmp_path) == ([], {"bioev:item-1"})


def swap(text, old, new):
    assert old in text
    return text.replace(old, new)


NEGATION = "No association was observed between SYNG1 variants and hearing loss in the mouse model."
CONTROLS = {
    # AI-specific negative controls from issue #20.
    "fabricated_identifier": (dict(uri="pmid:9999999"), ["BEV016"]),
    "real_identifier_wrong_paper": (dict(uri="pmid:1002"), ["BEV017"]),
    "real_identifier_wrong_paper_same_title": (dict(uri="pmid:1002", title="A survey of synthetic kinase expression"),
                                               ["BEV017"]),
    "altered_quote": (dict(quote=swap(QUOTE, "early", "severe")), ["BEV017"]),
    "negation_flip": (dict(quote=swap(NEGATION, "No association was", "An association was"), locator="#p2"), ["BEV017"]),
    "species_swap": (dict(quote=swap(NEGATION, "the mouse model", "human patients"), locator="#p2"), ["BEV017"]),
    "retracted_source": (dict(uri="pmid:1003"), ["BEV019"]),
    "retraction_notice": (dict(uri="pmid:1005"), ["BEV019"]),
    "retracted_doi_via_crossref": (dict(uri="doi:10.9999/crossref.only"), ["BEV015"]),  # no full text either
    "unknown_doi": (dict(uri="https://doi.org/10.9999/nowhere"), ["BEV016"]),
    "not_open_access": (dict(uri="pmid:1004"), ["BEV015"]),
    "wrong_paragraph": (dict(locator="#p2"), ["BEV017"]),
    "short_quote": (dict(quote="retinal degeneration"), ["BEV015"]),
}


@pytest.mark.parametrize("name", CONTROLS)
def test_negative_controls(name, tmp_path):
    changes, expected = CONTROLS[name]
    codes, verified = check(grounded(claim(**changes), tmp_path), tmp_path)
    assert codes == expected or set(expected) <= set(codes), codes
    assert not verified


def test_crossref_retraction_is_reported(tmp_path):
    record = grounded(claim(uri="doi:10.9999/crossref.only"), tmp_path)
    grounder = LiteratureGrounder.from_directory(tmp_path / "snapshots")
    assert [f.rule_id for f in grounder.check(record) if f.field_path.startswith("$.source_artifacts")] == ["BEV019"]


def test_ungrounded_unidentified_and_tampered(tmp_path):
    record = grounded(claim(), tmp_path)
    assert check(claim(uri="pmid:1002"), tmp_path) == (["BEV015"], set())  # not in the catalog
    assert check(claim(uri="https://example.org/x"), tmp_path) == (["BEV015"], set())
    changed = copy.deepcopy(record)
    changed["source_artifacts"][0]["sha256"] = "b" * 64
    assert check(changed, tmp_path)[0] == ["BEV017"]
    entry = json.loads((tmp_path / "snapshots/literature.json").read_text(encoding="utf-8"))["works"]["pmid:1001"]
    (tmp_path / "snapshots" / f"{entry['metadata_sha256']}.json").write_bytes(epmc())  # edited after pinning
    assert check(record, tmp_path) == (["BEV015"], set())


def test_non_publications_are_ignored(tmp_path):
    record = grounded(claim(), tmp_path)
    record["source_artifacts"][0]["source_type"] = "dataset"
    assert check(record, tmp_path) == ([], set())


def profile_file(tmp_path, verified=("publication_result",)):
    text = (ROOT / "src/bioevidence_validator/profiles/literature-claim.yaml").read_text(encoding="utf-8")
    text = text.replace("    require_human_acceptance: false\n",
                        "    require_human_acceptance: false\n    verified_evidence_types: ["
                        + ", ".join(verified) + "]\n", 1)
    path = tmp_path / "verified.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_only_verified_evidence_satisfies_a_verified_requirement(tmp_path):
    record = grounded(claim(), tmp_path)
    profile = profile_file(tmp_path)
    unchecked = RecordValidator(profile=profile).validate(record)
    assert unchecked["overall_status"] == "review_required" and {f["rule_id"] for f in unchecked["findings"]} == {"BEV020"}
    grounder = LiteratureGrounder.from_directory(tmp_path / "snapshots")
    checked = RecordValidator(profile=profile, grounders=[grounder]).validate(record)
    assert checked["overall_status"] == "admitted" and checked["grounding"] == ["literature"]
    altered = grounded(claim(quote=swap(QUOTE, "early", "severe")), tmp_path)
    report = RecordValidator(profile=profile, grounders=[grounder]).validate(altered)
    assert report["overall_status"] == "rejected" and {f["rule_id"] for f in report["findings"]} == {"BEV017", "BEV020"}
    # The built-in profile asks for no verification, so its decisions are unchanged.
    assert RecordValidator(profile="literature-claim").validate(record)["overall_status"] == "admitted"


@pytest.mark.parametrize("verified", [["not_required"], ["publication_result", "publication_result"], "x"])
def test_verified_types_must_be_distinct_required_types(verified):
    text = (ROOT / "src/bioevidence_validator/profiles/literature-claim.yaml").read_bytes()
    profile = load_profile(text)
    profile["uses"]["research_summary"]["verified_evidence_types"] = verified
    with pytest.raises(ValueError, match="verified_evidence_types"):
        load_profile(yaml.safe_dump(profile).encode())


def test_cli_ground_then_validate_offline(tmp_path, monkeypatch, capsys):
    source, pinned, snapshots = tmp_path / "claim.json", tmp_path / "pinned.json", tmp_path / "snapshots"
    source.write_text(json.dumps(claim()), encoding="utf-8")
    monkeypatch.setattr(cli, "http_fetch", lambda email=None: Fetcher())
    assert cli.main(["ground", str(source), "--snapshot-dir", str(snapshots), "--output", str(pinned)]) == 0
    assert "1 publication(s)" in capsys.readouterr().out
    assert cli.main(["validate", str(pinned), "--profile", str(profile_file(tmp_path)),
                     "--snapshot-dir", str(snapshots)]) == 0
    assert json.loads(capsys.readouterr().out)["grounding"] == ["source-bytes", "literature"]
    assert cli.main(["ground", str(source), "--snapshot-dir", str(snapshots), "--output", str(source)]) == 3


def test_http_fetch_identifies_itself(monkeypatch):
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"{}"

    def urlopen(request, timeout):
        seen.update(agent=request.get_header("User-agent"), timeout=timeout)
        return Response()

    monkeypatch.setattr(literature.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(literature.time, "sleep", lambda s: None)
    assert literature.http_fetch("me@example.org")("https://www.ebi.ac.uk/x") == b"{}"
    assert seen == {"agent": f"bioai-evidence-validator/{literature.__version__} (mailto:me@example.org)", "timeout": 60}


def esummary(uid, title, pmcid=None, pub_types=("Journal Article",), db="pubmed"):
    ids = [{"idtype": "pubmed" if db == "pubmed" else "pmid", "value": uid}]
    ids += [{"idtype": "pmc" if db == "pubmed" else "pmcid", "value": pmcid}] if pmcid else []
    return json.dumps({"result": {"uids": [uid], uid: {"uid": uid, "title": title, "pubtype": list(pub_types),
                                                       "articleids": ids}}}).encode()


LICENSED = PAPER_A.replace(b"<front><article-meta>", b'<front><article-meta><permissions><license xlink:href='
                           b'"https://creativecommons.org/licenses/by/4.0/" xmlns:xlink="http://www.w3.org/1999/xlink">'
                           b"<license-p>Open access.</license-p></license></permissions>")
RESTRICTED = b"<pmc-articleset><article><front><restricted-by>pmc</restricted-by></front></article></pmc-articleset>"
NCBI = {
    literature._eutils("esummary", db="pubmed", id="2001", retmode="json"): esummary("2001", TITLE_A, "PMC2001"),
    literature._eutils("efetch", db="pmc", id="2001", retmode="xml"): LICENSED,
    literature._eutils("esummary", db="pubmed", id="2002", retmode="json"): esummary("2002", TITLE_A, "PMC2002"),
    literature._eutils("efetch", db="pmc", id="2002", retmode="xml"): RESTRICTED,
    literature._eutils("esummary", db="pubmed", id="2003", retmode="json"): esummary(
        "2003", TITLE_A, "PMC2003", pub_types=("Journal Article", "Retracted Publication")),
    literature._eutils("efetch", db="pmc", id="2003", retmode="xml"): LICENSED,
    literature._eutils("esummary", db="pubmed", id="9900001", retmode="json"): json.dumps(
        {"result": {"uids": ["9900001"], "9900001": {"uid": "9900001", "error": "cannot get document summary"}}}).encode(),
    literature._eutils("esummary", db="pmc", id="2001", retmode="json"): esummary("2001", TITLE_A, "PMC2001", db="pmc"),
    literature._eutils("esearch", db="pubmed", term="10.9999/syn.2001[doi]", retmode="json"): json.dumps(
        {"esearchresult": {"idlist": ["2001"]}}).encode(),
    literature._eutils("esearch", db="pubmed", term="10.9999/none[doi]", retmode="json"): json.dumps(
        {"esearchresult": {"idlist": []}}).encode(),
}


@pytest.mark.parametrize("uri,codes,verified", [
    ("pmid:2001", [], {"bioev:item-1"}),
    ("pmcid:PMC2001", [], {"bioev:item-1"}),
    ("doi:10.9999/syn.2001", [], {"bioev:item-1"}),
    ("pmid:2002", ["BEV015"], set()),  # PMC holds only the front matter: not open access
    ("pmid:2003", ["BEV019"], set()),
    ("pmid:9900001", ["BEV016"], set()),
    ("doi:10.9999/none", ["BEV016"], set()),
])
def test_ncbi_resolver(uri, codes, verified, tmp_path):
    record, catalog = ground_record(claim(uri=uri), tmp_path / "snapshots", Fetcher(NCBI), now="2026-09-29T00:00:00+00:00",
                                    resolver="ncbi", compress=True)
    assert all(entry["resolver"] == "ncbi" for entry in catalog["works"].values())
    assert check(record, tmp_path) == (codes, verified)
    if uri == "pmid:2001":
        entry = catalog["works"]["pmid:2001"]
        assert entry["license"] == "cc by" and (tmp_path / "snapshots" / f"{entry['fulltext_sha256']}.xml.gz").exists()


@pytest.mark.parametrize("license_xml,expected", [
    (b'<license xlink:href="https://creativecommons.org/licenses/by/4.0/"/>', "cc by"),
    (b'<license><ali:license_ref xmlns:ali="http://www.niso.org/schemas/ali/1.0/">'
     b"https://creativecommons.org/publicdomain/zero/1.0/</ali:license_ref></license>", "cc0"),
    (b"<license><license-p>This article is distributed under the Creative Commons Attribution License."
     b"</license-p></license>", "cc by"),
    (b'<license xlink:href="https://creativecommons.org/licenses/by-nc/4.0/"/>', "other"),
    (b"<license><license-p>Creative Commons Attribution-NonCommercial License.</license-p></license>", "other"),
    (b"<license><license-p>All rights reserved.</license-p></license>", "other"),
])
def test_jats_license(license_xml, expected):
    document = (b'<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><permissions>' + license_xml
                + b"</permissions></front><body><p>x</p></body></article>")
    assert literature.jats_license(document) == expected
    assert literature.jats_open(document) and not literature.jats_open(RESTRICTED)


def test_store_reads_gzip_snapshots_by_uncompressed_hash(tmp_path):
    import gzip
    import hashlib

    sha = hashlib.sha256(PAPER_A).hexdigest()
    (tmp_path / f"{sha}.xml.gz").write_bytes(gzip.compress(PAPER_A))
    store = literature.SnapshotStore.from_directory(tmp_path)
    assert store.get(sha) == PAPER_A and store.verified(sha)


def test_jats_blocks_tell_titles_from_paragraphs():
    blocks = literature.jats_blocks(PAPER_A)
    kinds = {text: kind for _, kind, text in blocks}
    assert kinds["Results"] == "title" and kinds[TITLE_A] == "title" and kinds[QUOTE] == "p"
    assert literature.jats_paragraphs(PAPER_A) == [(pid, text) for pid, _, text in blocks]


@pytest.mark.parametrize("quote,found", [
    ("stable across all tested strains (Figure 2).", True),        # spacing inside brackets
    ("Expression was stable across all tested strains.", True),    # trailing reference left out
    ("Expression was stable across all tested", True),             # substring semantics: a shortened quote matches
    ("Expression was stable across all strains (Figure 2).", False),
    ("Expression was stable (Figure 2).", False),                   # a middle part left out
])
def test_quote_matching_tolerates_only_formatting(quote, found):
    text = normalize("Expression was stable across all tested strains ( Figure 2 ). Other text followed.")
    assert literature.quote_in(normalize(quote), text) is found


def test_quote_may_end_with_a_period_the_text_lacks():
    title = normalize("MYOD1 (L122R) mutations are associated with aggressive clinical outcomes")
    assert literature.quote_in(normalize("MYOD1 (L122R) mutations are associated with aggressive clinical outcomes."), title)
    assert not literature.quote_in(normalize("MYOD1 (L122R) mutations are associated with aggressive clinical."), title)


PUBMED_2002 = (b"<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>2002</PMID><Article><ArticleTitle>"
               + TITLE_A.encode() + b"</ArticleTitle><Abstract><AbstractText Label=\"RESULTS\">Tumours carrying the "
               b"SYNG1 variant regressed in eight of ten treated patients.</AbstractText></Abstract></Article>"
               b"</MedlineCitation></PubmedArticle></PubmedArticleSet>")


def test_quotes_are_verified_against_the_abstract_without_open_full_text(tmp_path):
    responses = {**NCBI, literature._eutils("efetch", db="pubmed", id="2002", retmode="xml"): PUBMED_2002}
    quote = "Tumours carrying the SYNG1 variant regressed in eight of ten treated patients."
    record, catalog = ground_record(claim(uri="pmid:2002", quote=quote, locator=""), tmp_path / "snapshots",
                                    Fetcher(responses), resolver="ncbi")
    entry = catalog["works"]["pmid:2002"]
    assert entry["fulltext_sha256"] is None and record["source_artifacts"][0]["sha256"] == entry["abstract_sha256"]
    assert check(record, tmp_path) == ([], {"bioev:item-1"})
    altered = grounded(claim(uri="pmid:2002", quote=quote.replace("eight", "nine"), locator=""), tmp_path,
                       Fetcher(responses))
    assert check(altered, tmp_path) == (["BEV017"], set())
