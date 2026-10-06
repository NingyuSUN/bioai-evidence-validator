"""Ontology marker definitions checked against measurements."""
from test_reference_grounders import base

from bioevidence_validator.definitions import DefinitionGrounder, MarkerDefinitions
from bioevidence_validator.engine import validate_record
from bioevidence_validator.identifiers import Genes, Ontology

OBO = b"""format-version: 1.2
data-version: cl/releases/2026-01-01/cl.obo
ontology: cl

[Term]
id: CL:0000000
name: cell

[Term]
id: CL:0000084
name: T cell
is_a: CL:0000000 ! cell

[Term]
id: CL:0000623
name: natural killer cell
is_a: CL:0000000 ! cell
intersection_of: CL:0000000 ! cell
intersection_of: CL:4030046 PR:000001020 ! lacks_plasma_membrane_part CD3 epsilon

[Term]
id: CL:0000625
name: CD8-positive, alpha-beta T cell
is_a: CL:0000084 ! T cell
intersection_of: CL:0000084 ! T cell
intersection_of: CL:4030046 PR:000001004 ! lacks_plasma_membrane_part CD4 molecule
intersection_of: RO:0002104 PR:000025402 ! has plasma membrane part T cell receptor co-receptor CD8
relationship: RO:0002104 PR:000025402 ! has plasma membrane part T cell receptor co-receptor CD8

[Term]
id: CL:0000939
name: CD16-positive, CD56-dim natural killer cell, human
is_a: CL:0000623 ! natural killer cell
intersection_of: RO:0002104 PR:000001483 ! has plasma membrane part Fc receptor III
intersection_of: CL:4030046 PR:000002015 ! lacks MHC class II DRA
intersection_of: RO:0002104 PR:000001015 ! has plasma membrane part CD45RA
intersection_of: RO:0015016 PR:000001024 ! has low plasma membrane amount NCAM1

[Term]
id: PR:000001004
name: CD4 molecule
synonym: "CD4" EXACT PRO-short-label [PRO:DNx]

[Term]
id: PR:000001020
name: CD3 epsilon
synonym: "CD3E" EXACT PRO-short-label [PRO:DNx]

[Term]
id: PR:000001084
name: T-cell surface glycoprotein CD8 alpha chain
synonym: "CD8A" EXACT PRO-short-label [PRO:DNx]

[Term]
id: PR:000025408
name: T-cell surface glycoprotein CD8 alpha chain isoform 1, glycosylated form
is_a: PR:000001084 ! CD8 alpha chain

[Term]
id: PR:000001085
name: T-cell surface glycoprotein CD8 beta chain
synonym: "CD8B" EXACT PRO-short-label [PRO:DNx]

[Term]
id: PR:000025402
name: T cell receptor co-receptor CD8
relationship: RO:0002180 PR:000025408 ! has component CD8 alpha chain form
relationship: RO:0002180 PR:000001085 ! has component CD8 beta chain

[Term]
id: PR:000001483
name: low affinity immunoglobulin gamma Fc region receptor III
synonym: "Fcgr3" EXACT PRO-short-label [PRO:DNx]

[Term]
id: PR:000002015
name: MHC class II histocompatibility antigen alpha chain DRA
synonym: "HLA-DRA" RELATED Gene-based []
synonym: "MHCcIIalpha_DRA" EXACT PRO-short-label [PRO:DAN]

[Term]
id: PR:000001015
name: receptor-type tyrosine-protein phosphatase C isoform CD45RA
synonym: "PTPRC" EXACT PRO-short-label [PRO:DNx]

[Term]
id: PR:000001024
name: neural cell adhesion molecule 1
synonym: "NCAM1" EXACT PRO-short-label [PRO:DNx]
"""
SYMBOLS = ["CD4", "CD3E", "CD8A", "CD8B", "FCGR3A", "FCGR3B", "HLA-DRA", "PTPRC", "NCAM1"]
GENES = Genes([{"hgnc_id": f"HGNC:{n}", "symbol": s} for n, s in enumerate(SYMBOLS, start=1)], "test")
DEFINITIONS = MarkerDefinitions(Ontology.from_obo(OBO), GENES)


def test_protein_genes_follow_labels_families_components_and_forms():
    assert DEFINITIONS.protein_genes("PR:000001004") == ("CD4",)
    assert DEFINITIONS.protein_genes("PR:000001483") == ("FCGR3A", "FCGR3B")  # a family
    assert DEFINITIONS.protein_genes("PR:000025402") == ("CD8A", "CD8B")  # a complex, one part a modified form
    assert DEFINITIONS.protein_genes("PR:000002015") == ("HLA-DRA",)  # a gene-based synonym
    assert DEFINITIONS.protein_genes("PR:000001015") == ()  # an isoform marker cannot be measured by gene counts
    assert DEFINITIONS.protein_genes("PR:999") == ()


def test_definitions_are_inherited_and_only_presence_or_absence():
    assert DEFINITIONS.of("CL:0000625") == (("has", "T cell receptor co-receptor CD8", ("CD8A", "CD8B")),
                                            ("lacks", "CD4 molecule", ("CD4",)))
    kinds = DEFINITIONS.of("CL:0000939")
    assert ("lacks", "CD3 epsilon", ("CD3E",)) in kinds  # from natural killer cell
    assert all(genes != ("NCAM1",) for _, _, genes in kinds)  # a relative amount is not checked
    assert DEFINITIONS.of("CL:0000084") == ()


def record(term, label):
    return base(object={"id": term, "label": label, "entity_type": "cell_type"})


def grounder(stats):
    return DefinitionGrounder(DEFINITIONS, lambda record: stats)


def test_presence_and_absence_against_measurements():
    cd8 = record("CL:0000625", "CD8-positive, alpha-beta T cell")
    fine = {"CD8A": (0.8, 2.0), "CD8B": (0.6, 1.5), "CD4": (0.05, -0.2)}
    assert grounder(fine).check(cd8) == []
    no_cd8 = grounder({**fine, "CD8A": (0.02, -0.5), "CD8B": (0.04, -0.3)}).check(cd8)
    assert [f.rule_id for f in no_cd8] == ["BEV026"] and "detected in only 4%" in no_cd8[0].message
    assert grounder({**fine, "CD8A": (0.02, -0.5)}).check(cd8) == []  # one part of the complex is enough
    cd4 = grounder({**fine, "CD4": (0.7, 1.1)}).check(cd8)
    assert [f.rule_id for f in cd4] == ["BEV026"] and "lacking CD4 molecule (CD4), but CD4 is detected in 70%" in cd4[0].message
    assert grounder({**fine, "CD4": (0.7, 0.1)}).check(cd8) == []  # not higher than elsewhere
    assert grounder({"CD4": (0.9, 2.0)}).check(record("CL:0000084", "T cell")) == []  # nothing defined
    assert grounder({}).check(cd8) == [] and grounder(None).check(cd8) == []  # nothing measured
    assert grounder({"CD8A": (0.01, 0.0)}).name == "definitions:CL@cl/releases/2026-01-01/cl.obo"


def test_definition_findings_send_a_record_to_review():
    cd8 = record("CL:0000625", "CD8-positive, alpha-beta T cell")
    report = validate_record(cd8, grounders=[grounder({"CD8A": (0.8, 2.0), "CD4": (0.9, 1.5)})])
    assert report["overall_status"] == "review_required" and {f["rule_id"] for f in report["findings"]} == {"BEV026"}
