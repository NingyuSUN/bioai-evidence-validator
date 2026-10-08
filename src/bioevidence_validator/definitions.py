"""Ontology definitions as checks: what a claimed term is defined to have or lack, against what was measured.

The Cell Ontology defines many cell types by marker proteins: a CD8-positive, alpha-beta T cell is a mature
alpha-beta T cell that `has plasma membrane part` the CD8 co-receptor and `lacks plasma membrane part` CD4;
a natural killer cell lacks CD3 epsilon. These axioms are part of a pinned release, not of anyone's
judgment about a dataset, so they can be checked against measurements without knowing the right answer:
when a record says a cluster is a CD8 T cell and CD4 is detected in most of its cells, the data contradict
the definition of the term it claims (BEV026). That is not proof the record is wrong (protein and transcript
differ, and some definitions are written for one species), so the finding sends the record to review; in a
feedback loop it goes back to the proposer with the measurement, which no omission can hide.

**Experimental.** On transcript data the check did not transfer to new datasets: several protein definitions do
not hold for mRNA (mast cell CCR3, neutrophil CEACAM8, NK cells lacking CD3 epsilon), and it flagged correct
annotations as often as wrong ones. Fed back to models, its findings turned correct answers into wrong ones
(evaluation/llm_benchmark/README.md, external split). Use it on transcripts only with markers validated at the
mRNA level.

`MarkerDefinitions` collects, for each term, its presence (`RO:0002104` has plasma membrane part) and absence
(`CL:4030046` lacks plasma membrane part) axioms, its own and inherited through `is_a`, and maps each protein
to genes: by its PRO short label or gene-based synonym (`CD4`, `HLA-DRA`; `Fcgr3` names the FCGR3A/FCGR3B
family), through the components of a
complex (`RO:0002180`, the CD8 co-receptor is CD8A and CD8B), or through its parent protein. Isoform-specific
markers (CD45RA) are left out: gene-level counts cannot see them. Relative axioms (high or low amounts) are
not checked; they compare with another cell type, not with the rest of a dataset.

`DefinitionGrounder` reads the claimed term (the statement's object) and asks `measure(record)` for the
subject's measurements: gene -> (fraction of cells in which it is detected, log fold change against the other
cells). A presence axiom is contradicted when every measured gene of the protein is detected in fewer than
`present` of the cells; an absence axiom when some gene is detected in at least `absent` of them and is higher
than elsewhere (`absent_logfc`). Genes that were not measured are not judged.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from functools import cache
from typing import Any

from .engine import Finding
from .grounding import finding
from .identifiers import Genes, Ontology

HAS, LACKS, COMPONENT = "RO:0002104", "CL:4030046", "RO:0002180"
KINDS = {HAS: "has", LACKS: "lacks"}


class MarkerDefinitions:
    def __init__(self, ontology: Ontology, genes: Genes):
        self.ontology, self.genes = ontology, genes
        self.folded = {s.casefold(): s for s in genes.approved}

    def _symbols(self, label: str) -> tuple[str, ...]:
        if label.casefold() in self.folded:
            return (self.folded[label.casefold()],)
        family = sorted(s for s in self.genes.approved if re.fullmatch(re.escape(label.upper()) + r"[A-Z]", s))
        return tuple(family) if 1 < len(family) <= 4 else ()

    def protein_genes(self, protein: str) -> tuple[str, ...]:
        return self._genes(protein, 0)

    @cache  # noqa: B019 - one instance per pinned release, kept for the process
    def _genes(self, protein: str, depth: int) -> tuple[str, ...]:
        term = self.ontology.terms.get(protein)
        if term is None or depth > 4 or (depth == 0 and "isoform" in term.name):
            return ()
        for label in term.short_labels:
            if found := self._symbols(label):
                return found
        parts = [target for relation, target in term.relations if relation == COMPONENT]
        if parts:
            return tuple(sorted({g for part in parts for g in self._genes(part, depth + 1)}))
        if depth:  # a modified or cleaved form: the gene of the protein it is a form of
            return tuple(sorted({g for p in term.parents if p.startswith("PR:") for g in self._genes(p, depth + 1)}))
        return ()

    @cache  # noqa: B019
    def of(self, curie: str) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
        """(kind, protein name, genes) for each testable presence or absence axiom, own and inherited."""
        found = []
        for ancestor in sorted(self.ontology.ancestors(curie)):
            term = self.ontology.terms.get(ancestor)
            for relation, target in term.relations if term else []:
                if relation in KINDS and target.startswith("PR:") and (genes := self.protein_genes(target)):
                    protein = self.ontology.terms[target].name
                    found.append((KINDS[relation], protein, genes))
        return tuple(sorted(set(found)))


class DefinitionGrounder:
    def __init__(self, definitions: MarkerDefinitions,
                 measure: Callable[[dict[str, Any]], Mapping[str, tuple[float, float]] | None], *,
                 present: float = 0.10, absent: float = 0.50, absent_logfc: float = 0.25):
        self.definitions, self.measure = definitions, measure
        self.present, self.absent, self.absent_logfc = present, absent, absent_logfc
        ontology = definitions.ontology
        self.name = f"definitions:{ontology.prefix}@{ontology.version}"

    def check(self, record: dict[str, Any]) -> list[Finding]:
        claimed = record["statement"]["object"]["id"]
        axioms = self.definitions.of(claimed)
        stats = self.measure(record) if axioms else None
        if not stats:
            return []
        out = []
        described = self.definitions.ontology.describe(claimed)
        for kind, protein, genes in axioms:
            measured = [g for g in genes if g in stats]
            if not measured:
                continue
            names = "/".join(measured)
            if kind == "has" and all(stats[g][0] < self.present for g in measured):
                seen = max(stats[g][0] for g in measured)
                out.append(finding(record, "BEV026", f"{described} is defined as having {protein} ({names}) on the "
                                                     f"membrane, but {names} is detected in only {seen:.0%} of the "
                                                     "cluster's cells.", "$.statement.object.id"))
            if kind == "lacks":
                high = [g for g in measured if stats[g][0] >= self.absent and stats[g][1] > self.absent_logfc]
                if high:
                    g = max(high, key=lambda x: stats[x][0])
                    out.append(finding(record, "BEV026", f"{described} is defined as lacking {protein} ({g}), but {g} "
                                                         f"is detected in {stats[g][0]:.0%} of the cluster's cells, more "
                                                         f"than in the others (logfc {stats[g][1]:.2f}).",
                                       "$.statement.object.id"))
        return out
