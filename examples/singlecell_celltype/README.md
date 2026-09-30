# Real-source case: single-cell cell-type annotation

The third real-data case, after ontology names (`vbo_canine`) and clinical genetics (`clinvar_germline`),
moves to data: a cluster of a single-cell RNA-seq dataset, the marker genes that characterise it, and the
Cell Ontology term an annotator gives it. It asks what bioevidence adds when a model annotates clusters:
which of the model's errors can be caught without knowing the answer, and which cannot.

**Not a benchmark of cell-type annotation methods.** Author labels are the reference; they are themselves
judgments (see Limits).

## Sources

Six normal human datasets from [CZ CELLxGENE Discover](https://cellxgene.cziscience.com/) (CC BY 4.0), each
annotated by its authors with Cell Ontology terms: liver, kidney, adult duodenum, pancreas, skin, and the T,
NK and ILC compartment of a fetal lung atlas (a fine-grained immune subset). Reference releases: the Cell
Ontology (2026-06-08, full `cl.obo`, which keeps the disjointness axioms), the HGNC complete set
(2026-09-30) and the HuBMAP ASCT+B tables for liver, kidney, pancreas, skin and lung (CCF v2.0). See
[`sources/ATTRIBUTION.md`](sources/ATTRIBUTION.md).

`prepare_source.py` derives, from files downloaded once and recorded with their SHA-256 in
`sources/manifest.json`:

- **Marker tables.** Each author cell type with at least 30 cells is a "cluster". From raw counts
  (normalised to 10,000 per cell, log1p), each gene gets `logfc` (mean inside minus mean outside the
  cluster), `pct_in` and `pct_out`. The 50 genes with the highest positive `logfc` among those expressed in
  at least a quarter of the cluster form its table, named by current HGNC symbols. One table per dataset.
- **Truth.** The authors' term for each cluster (`truth.jsonl`), never shown to a model.
- **Reference.** ASCT+B biomarker genes as `gene marker_of cell type` assertions (1,027).
- **Tasks.** 70 clusters, one task each, showing the tissue, the assay and the top 20 markers with their
  statistics. Four per dataset (24) form the pilot split; the other 46 are held out.

The derived tables, the two reference releases and the ASCT+B projection are committed as gzip-compressed
snapshots named by their SHA-256; the expression matrices are not.

## Records and grounders

An annotation is a record under [`profile.yaml`](profile.yaml): `cluster has_cell_type <CL term>`, with one
`marker_gene` evidence item per cited gene, located as `cluster=c03;gene=CD8A` in the dataset's marker
table, in a supporting or contradicting evidence line. Five grounders check it, all generic:

| Grounder | What it checks here |
|---|---|
| `TableGrounder` | Each cited marker is one of this cluster's markers in the pinned table (BEV016 otherwise, naming the closest genes). A marker counts as verified only then, and the profile requires a verified marker. |
| `OntologyGrounder` | The term exists (BEV016), is current (BEV023), is a cell type under CL:0000000 (BEV024) and matches its label (BEV017, naming the term the label belongs to). |
| `GeneGrounder` | Cited genes are approved HGNC symbols (aliases and previous symbols: BEV023, naming the approved one). |
| `ReferenceGrounder` | A supporting marker that ASCT+B lists only for cell types the Cell Ontology declares disjoint from the claimed one (e.g. a B cell marker for a T cell) sends the record to an expert (BEV025). |
| `SourceBytesGrounder` | The marker table's bytes hash to the record's frozen hash. |

The AI experiment is in [`evaluation/llm_benchmark/celltype_loop.py`](../../evaluation/llm_benchmark/celltype_loop.py)
(results in the benchmark README).

## Limits

- Author labels are the reference, at the granularity each study chose ("myeloid leukocyte", "stem cell").
  Some are debatable from the markers alone (a duodenal "B cell" cluster led by JCHAIN and MZB1 looks like
  plasma cells). Scoring is ontology-aware (exact, coarser, finer, wrong), not an expert judgment.
- The marker table holds the top 50 upregulated genes of each cluster. A claim that a gene is absent
  cannot be checked against it, and is reported as not in the table.
- ASCT+B covers some organs and some cell types, and a gene it does not list is never reported. The
  disjointness axioms of the Cell Ontology cover major lineages only (e.g. epithelial cell and leukocyte,
  T cell and B cell lineage, lymphocyte and myeloid leukocyte), so a marker cited for the wrong type within
  a lineage is not caught this way.
