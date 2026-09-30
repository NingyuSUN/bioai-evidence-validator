"""Generic grounders on hand-made fixtures: ontology terms, gene symbols, variants, tables, a reference resource."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from bioevidence_validator.crosscheck import ReferenceGrounder
from bioevidence_validator.engine import validate_record
from bioevidence_validator.grounding import SnapshotStore
from bioevidence_validator.identifiers import (
    Assemblies,
    GeneGrounder,
    Genes,
    Ontology,
    OntologyGrounder,
    VariantGrounder,
    pairs,
)
from bioevidence_validator.tables import TableGrounder, parse_table, same_value

ROOT = Path(__file__).resolve().parents[1]
OBO = b"""format-version: 1.2
data-version: cl/releases/2026-01-01/cl-basic.obo
ontology: cl

[Term]
id: CL:0000000
name: cell

[Term]
id: CL:0000084
name: T cell
synonym: "T-lymphocyte" EXACT []
synonym: "T lymphocyte" RELATED []
is_a: CL:0000000 ! cell

[Term]
id: CL:0000625
name: CD8-positive, alpha-beta T cell
is_a: CL:0000084 ! T cell

[Term]
id: CL:0000236
name: B cell
is_a: CL:0000000 ! cell

[Term]
id: CL:0000788
name: naive B cell
is_a: CL:0000236 ! B cell

[Term]
id: CL:0000999
name: obsolete lymphocyte of B lineage
is_obsolete: true
replaced_by: CL:0000236

[Term]
id: CL:0000998
name: obsolete lymphocyte
is_obsolete: true
consider: CL:0000084

[Term]
id: CL:0001000
name: cell part
is_a: CL:0009999 ! something that is not a cell

[Typedef]
id: part_of
name: part of
"""
HGNC = (b"hgnc_id\tsymbol\tname\tstatus\tprev_symbol\talias_symbol\n"
        b"HGNC:1706\tCD8A\tCD8 subunit alpha\tApproved\t\tCD8|Leu2\n"
        b"HGNC:1633\tCD19\tCD19 molecule\tApproved\t\t\n"
        b"HGNC:3430\tERBB2\terb-b2 receptor tyrosine kinase 2\tApproved\tNGL\tHER-2|HER2\n")
REPORT_38 = b"""# Assembly name:  GRCh38.p14
# Sequence-Name\tSequence-Role\tAssigned-Molecule\tAssigned-Molecule-Location/Type\tGenBank-Accn\tRelationship\tRefSeq-Accn\tAssembly-Unit\tSequence-Length\tUCSC-style-name
7\tassembled-molecule\t7\tChromosome\tCM000669.2\t=\tNC_000007.14\tPrimary Assembly\t159345973\tchr7
"""
REPORT_37 = b"""# Assembly name:  GRCh37.p13
7\tassembled-molecule\t7\tChromosome\tCM000669.1\t=\tNC_000007.13\tPrimary Assembly\t159138663\tchr7
"""
TABLE = b"cluster\tgene\tlogfc\tpct_in\tcall\n3\tCD8A\t2.4137\t0.91\tup\n3\tCD19\t-1.2\t0.02\tabsent\n5\tCD19\t3.1\t0.88\tup\n"


def base(**statement):
    record = json.loads((ROOT / "examples/general/curated_assertion.json").read_text(encoding="utf-8"))
    record["statement"].update(statement)
    return record


def codes(record, grounder):
    return [f.rule_id for f in grounder.check(record)]


def messages(record, grounder):
    return " | ".join(f.message for f in grounder.check(record))


CL = Ontology.from_obo(OBO)
CELLS = OntologyGrounder([CL], roots={"cell_type": ["CL:0000000"]}, locator_keys=["cell_type"])


def cell(curie, label):
    return base(object={"id": curie, "label": label, "entity_type": "cell_type"})


def test_ontology_parsing_and_hierarchy():
    assert CL.prefix == "CL" and CL.version == "cl/releases/2026-01-01/cl-basic.obo"
    assert Ontology.from_obo(OBO.replace(b"ontology: cl", b"ontology: cl/cl-basic")).prefix == "CL"
    assert CL.by_label("T lymphocyte") == CL.by_label("t-lymphocyte") == ["CL:0000084"]  # no duplicates
    assert CL.terms["CL:0000084"].synonyms == ["T-lymphocyte"]  # only exact synonyms name a term
    assert CL.ancestors("CL:0000625") == {"CL:0000625", "CL:0000084", "CL:0000000"}
    assert CL.related("CL:0000084", "CL:0000625") and not CL.related("CL:0000236", "CL:0000625")
    assert CELLS.name == "ontology:CL@cl/releases/2026-01-01/cl-basic.obo"


def test_ontology_grounder_accepts_a_current_matching_term():
    assert codes(cell("CL:0000625", "CD8-positive, alpha-beta T cell"), CELLS) == []
    assert codes(cell("CL:0000625", "cd8 positive alpha beta t cell"), CELLS) == []  # case and punctuation
    assert codes(cell("CL:0000084", "T-lymphocyte"), CELLS) == []  # exact synonym


def test_ontology_grounder_explains_what_to_fix():
    record = cell("CL:0000084", "B cell")
    assert codes(record, CELLS) == ["BEV017"]
    assert "'B cell' is the name of CL:0000236 (B cell)" in messages(record, CELLS)
    record = cell("CL:9999999", "T cell")
    assert codes(record, CELLS) == ["BEV016"] and "CL:0000084 (T cell)" in messages(record, CELLS)
    record = cell("CL:0000999", "B cell")
    assert codes(record, CELLS) == ["BEV023"] and "Use CL:0000236 (B cell)" in messages(record, CELLS)
    assert "Closest names" in messages(cell("CL:9999999", "naive B-cells"), CELLS)
    assert "Use CL:0000084 (T cell)" in messages(cell("CL:0000998", "T cell"), CELLS)


def test_ontology_grounder_checks_the_kind_of_term():
    record = cell("UBERON:0002371", "T cell")
    assert codes(record, CELLS) == ["BEV024"] and "must be a CL term" in messages(record, CELLS)
    assert codes(cell("CL:0001000", "cell part"), CELLS) == ["BEV024"]
    other = base(object={"id": "GO:0008150", "label": "biological_process", "entity_type": "biological_process"})
    assert codes(other, CELLS) == []  # no loaded ontology and no root for this kind: nothing to say


def test_ontology_grounder_checks_scope_and_locators():
    record = cell("CL:0000084", "T cell")
    record["statement"]["scope"] = ["CL:9999999"]
    record["evidence_items"][0]["locator"] = "cell_type=UBERON:1"
    assert sorted(codes(record, CELLS)) == ["BEV016", "BEV024"]


GENES = GeneGrounder(Genes.from_hgnc(HGNC, "2026-09-29"))


def with_gene(symbol, scope=("NCBITaxon:9606",)):
    record = base(scope=list(scope))
    record["evidence_items"][0].update(locator=f"cluster=3;gene={symbol}")
    return record


@pytest.mark.parametrize("symbol,code,text", [
    ("CD8A", None, ""), ("HER2", "BEV023", "alias of ERBB2"), ("NGL", "BEV023", "previous symbol or alias of ERBB2"),
    ("Cd8a", "BEV023", "the approved symbol is CD8A"), ("CD8AA", "BEV016", "Closest: CD8A"),
    ("XYZ1", "BEV016", "not an HGNC gene symbol")])
def test_gene_grounder_symbols(symbol, code, text):
    record = with_gene(symbol)
    assert codes(record, GENES) == ([code] if code else []) and text in messages(record, GENES)


def test_gene_grounder_entities_and_species():
    record = base(subject={"id": "HGNC:1706", "label": "CD8A", "entity_type": "gene"})
    assert codes(record, GENES) == []
    record["statement"]["subject"]["label"] = "CD19"
    assert codes(record, GENES) == ["BEV017"]
    record["statement"]["subject"] = {"id": "HGNC:0", "label": "X", "entity_type": "gene"}
    assert codes(record, GENES) == ["BEV016"]
    record["statement"]["subject"] = {"id": "gene:her2", "label": "HER2", "entity_type": "gene"}
    assert codes(record, GENES) == ["BEV023"]
    assert codes(with_gene("Cd8a", scope=["NCBITaxon:10090"]), GENES) == ["BEV015"]
    assert GENES.name == "genes:HGNC@2026-09-29"


VARIANTS = VariantGrounder(Assemblies.from_reports([REPORT_38, REPORT_37]))


def variant(text, scope=("GRCh38",)):
    return base(subject={"id": "var:1", "label": text, "entity_type": "variant"}, scope=list(scope))


@pytest.mark.parametrize("text,scope,code", [
    ("NC_000007.14:g.140753336A>T", ["GRCh38"], None),
    ("NC_000007.13:g.140453136A>T", ["GRCh38"], "BEV017"),
    ("NC_000007.13:g.140453136A>T", ["hg19"], None),
    ("NC_000007.15:g.1A>T", ["GRCh38"], "BEV016"),
    ("NC_000007.14:g.999999999A>T", ["GRCh38"], "BEV016"),
    ("NC_000007:g.140753336A>T", ["GRCh38"], "BEV024"),
    ("BRAF V600E", ["GRCh38"], "BEV024"),
    ("NM_004333.6:c.1799T>A", ["GRCh38"], None),
])
def test_variant_grounder(text, scope, code):
    assert codes(variant(text, scope), VARIANTS) == ([code] if code else [])


def test_variant_grounder_mixed_builds_and_locators():
    record = variant("NC_000007.14:g.140753336A>T", scope=["taxon:synthetic"])
    record["evidence_items"][0]["locator"] = "variant=NC_000007.13:g.140453136A>T"
    assert codes(record, VARIANTS) == ["BEV017"]
    assert VARIANTS.name == "variants:GRCh37+GRCh38"


def test_pairs_and_values():
    assert pairs("cluster=3; gene=CD8A") == {"cluster": "3", "gene": "CD8A"}
    assert pairs("row 3") == {} and pairs("") == {}
    assert same_value("2.4", "2.4137") and not same_value("2.5", "2.4137") and same_value("2", "2.4")
    assert same_value("Up", "up") and not same_value("up", "absent")
    assert parse_table(b"a,b\n1, 2\n") == (["a", "b"], [{"a": "1", "b": "2"}])


def table_record(locator, text, *, sha=None):
    record = base()
    record["source_artifacts"][0].update(sha256=sha or hashlib.sha256(TABLE).hexdigest())
    record["source_artifacts"][0]["observed_sha256"] = record["source_artifacts"][0]["sha256"]
    record["evidence_items"][0].update(locator=locator, extracted_text=text, evidence_type="marker_gene")
    return record


TABLES = TableGrounder(SnapshotStore({hashlib.sha256(TABLE).hexdigest(): lambda: TABLE}), ["marker_gene"])


@pytest.mark.parametrize("locator,text,code,hint", [
    ("cluster=3;gene=CD8A", "logfc=2.41; call=up", None, ""),
    ("cluster=3;gene=CD8A", "", None, ""),
    ("cluster=3;gene=CD8A", "logfc=3.2", "BEV017", "has logfc=2.4137, not logfc=3.2"),
    ("cluster=3;gene=CD8B", "call=up", "BEV016", "Closest gene values for cluster=3: CD8A"),
    ("cluster=4;gene=CD8A", "", "BEV016", "No row"),
    ("gene=CD19", "", "BEV015", "2 rows"),
    ("cluster=3;symbol=CD8A", "", "BEV024", "no column 'symbol'"),
    ("row 3", "", "BEV024", "key=value"),
])
def test_table_grounder(locator, text, code, hint):
    record = table_record(locator, text)
    assert codes(record, TABLES) == ([code] if code else []) and hint in messages(record, TABLES)
    assert TABLES.verified_items(record) == ({"bioev:item-1"} if code is None else set())


def test_table_grounder_needs_the_bytes_and_ignores_other_evidence():
    assert codes(table_record("cluster=3;gene=CD8A", "", sha="b" * 64), TABLES) == ["BEV015"]
    record = table_record("cluster=3;gene=CD8B", "")
    record["evidence_items"][0]["evidence_type"] = "curated_annotation"
    assert codes(record, TABLES) == []


MARKERS = [{"subject": "CD19", "predicate": "marker_of", "object": "CL:0000236", "object_label": "B cell"},
           {"subject": "CD8A", "predicate": "marker_of", "object": "CL:0000625"}]


def marker_record(gene, target, direction="supports"):
    record = cell(target, CL.terms[target].name)
    record["evidence_items"][0]["locator"] = f"cluster=3;gene={gene}"
    record["statement"]["evidence_lines"][0]["direction"] = direction
    return record


def test_reference_grounder_evidence_conflicts():
    grounder = ReferenceGrounder(MARKERS, label="ASCT+B", evidence_key="gene", relation="marker_of", ontology=CL)
    assert codes(marker_record("CD8A", "CL:0000625"), grounder) == []
    assert codes(marker_record("CD19", "CL:0000788"), grounder) == []  # a B cell marker for a naive B cell
    assert codes(marker_record("CD8A", "CL:0000084"), grounder) == []  # related the other way
    assert codes(marker_record("GZMB", "CL:0000084"), grounder) == []  # the reference is silent
    record = marker_record("CD19", "CL:0000084")
    assert codes(record, grounder) == ["BEV025"]
    assert "lists CD19 as a marker of CL:0000236 (B cell), not of CL:0000084" in messages(record, grounder)
    assert codes(marker_record("CD19", "CL:0000084", direction="contradicts"), grounder) == []
    plain = ReferenceGrounder(MARKERS, label="ASCT+B", evidence_key="gene", relation="marker_of")
    assert codes(marker_record("CD19", "CL:0000788"), plain) == ["BEV025"]  # without an ontology, only the same id


def test_reference_grounder_statement_conflict():
    rows = b"subject\tpredicate\tobject\nSYN:PROTEIN_A\tdoes_not_participate_in\tSYN:PROCESS_A\n"
    grounder = ReferenceGrounder.from_table(rows, label="toy", opposites={"participates_in": "does_not_participate_in"})
    assert codes(base(), grounder) == ["BEV025"] and grounder.name == "reference:toy"
    assert codes(base(predicate="does_not_participate_in"), grounder) == []


def test_grounders_route_through_the_engine():
    record = copy.deepcopy(cell("CL:0000084", "B cell"))
    report = validate_record(record, grounders=[CELLS])
    assert report["overall_status"] == "rejected" and report["grounding"] == [CELLS.name]
    report = validate_record(marker_record("CD19", "CL:0000084"), grounders=[
        ReferenceGrounder(MARKERS, label="ASCT+B", evidence_key="gene", relation="marker_of", ontology=CL)])
    assert report["overall_status"] == "review_required"


def test_cli_identifier_options(tmp_path):
    from bioevidence_validator.cli import main

    paths = {}
    for name, data in {"cl.obo": OBO, "hgnc.tsv": HGNC, "grch38.txt": REPORT_38}.items():
        paths[name] = tmp_path / name
        paths[name].write_bytes(data)
    options = ["--ontology", str(paths["cl.obo"]), "--term-root", "cell_type=CL:0000000", "--genes", str(paths["hgnc.tsv"]),
               "--assembly-report", str(paths["grch38.txt"])]

    def run(record):
        path, output = tmp_path / "record.json", tmp_path / "report.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        code = main(["validate", str(path), "--output", str(output), *options])
        return code, json.loads(output.read_text(encoding="utf-8")) if output.exists() else None

    code, report = run(cell("CL:0000625", "CD8-positive, alpha-beta T cell"))
    assert code == 0 and report["grounding"] == ["ontology:CL@cl/releases/2026-01-01/cl-basic.obo",
                                                 "genes:HGNC@hgnc.tsv", "variants:GRCh38"]
    code, report = run(cell("UBERON:0002371", "T cell"))
    assert code == 1 and {f["rule_id"] for f in report["findings"]} == {"BEV024"}
    options[3] = "cell_type"
    assert main(["validate", str(tmp_path / "record.json"), *options]) == 3
