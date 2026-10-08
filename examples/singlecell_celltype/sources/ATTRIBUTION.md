# Attribution

The marker tables in `snapshots/` are derived by `prepare_source.py` from the datasets below, as curated
and distributed by [CZ CELLxGENE Discover](https://cellxgene.cziscience.com/) under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The expression matrices themselves are not
redistributed; `manifest.json` records each file's SHA-256 and dataset version. The cell-type labels in
`truth.jsonl` are the datasets' own author annotations.

| Name | Dataset | Publication |
|---|---|---|
| liver | Liver, in *Single cell RNA sequencing of human liver reveals distinct intrahepatic macrophage populations* | *Nat Commun* 2018, [10.1038/s41467-018-06318-7](https://doi.org/10.1038/s41467-018-06318-7) |
| kidney | normal, in *Single-cell analyses of renal cell cancers reveal insights into tumor microenvironment, cell of origin, and therapy response* | *PNAS* 2021, [10.1073/pnas.2103240118](https://doi.org/10.1073/pnas.2103240118) |
| duodenum | Adult duodenum, in *Charting human development using a multi-endodermal organ atlas and organoid models* | *Cell* 2021, [10.1016/j.cell.2021.04.028](https://doi.org/10.1016/j.cell.2021.04.028) |
| pancreas | A Single-Cell Transcriptome Atlas of the Human Pancreas (Muraro Pancreas) | *Cell Systems* 2016, [10.1016/j.cels.2016.09.002](https://doi.org/10.1016/j.cels.2016.09.002) |
| skin | Single-cell transcriptomes of the human skin reveal age-related loss of fibroblast priming | *Commun Biol* 2020, [10.1038/s42003-020-0922-4](https://doi.org/10.1038/s42003-020-0922-4) |
| lung_t_nk_ilc | T, NK and ILC, in *A human fetal lung cell atlas uncovers proximal-distal gradients of differentiation and key regulators of epithelial fates* | *Cell* 2022, [10.1016/j.cell.2022.11.005](https://doi.org/10.1016/j.cell.2022.11.005) |

External datasets (the `external` split), from other studies:

| Name | Dataset | Publication |
|---|---|---|
| blood_bone_marrow | blood and bone marrow from a healthy young donor, in *Single-cell proteo-genomic reference maps of the hematopoietic system enable the purification and massive profiling of precisely defined cell states* (a targeted gene panel) | *Nat Immunol* 2021, [10.1038/s41590-021-01059-0](https://doi.org/10.1038/s41590-021-01059-0) |
| tonsil_t | Human tonsil T cells scRNA, in *Single-cell analysis of human B cell maturation predicts how antibody class switching shapes selection dynamics* | *Sci Immunol* 2021, [10.1126/sciimmunol.abe6291](https://doi.org/10.1126/sciimmunol.abe6291) |
| kidney_immune | Mature kidney dataset: immune, in *Spatiotemporal immune zonation of the human kidney* | *Science* 2019, [10.1126/science.aat5031](https://doi.org/10.1126/science.aat5031) |
| endometrium_immune | Immune cells from five healthy donors, in *Cellular heterogeneity and dynamics of the human uterus in healthy premenopausal women* | *PNAS* 2024, [10.1073/pnas.2404775121](https://doi.org/10.1073/pnas.2404775121) |
| bladder_immune | Adult bladder immune subset, in *Exploring the Utility of snRNA-seq in Profiling Human Bladder Tissue: A Comprehensive Comparison with scRNA-seq* | *iScience*, [10.1016/j.isci.2024.111628](https://doi.org/10.1016/j.isci.2024.111628) |
| fetal_intestine | Immune, in *Spatiotemporal analysis of human intestinal development at single-cell resolution* | *Cell* 2021, [10.1016/j.cell.2020.12.016](https://doi.org/10.1016/j.cell.2020.12.016) |

Reference releases, redistributed unchanged (gzip-compressed) in `snapshots/`:

- **Cell Ontology**, release 2026-06-08, full `cl.obo`
  ([obophenotype/cell-ontology](https://github.com/obophenotype/cell-ontology)), CC BY 4.0.
- **HGNC complete set**, retrieved 2026-09-30 from [genenames.org](https://www.genenames.org/), CC0.

The ASCT+B reference (`gene marker_of cell type`) is derived from the HuBMAP ASCT+B Tables, CCF release
v2.0 ([hubmapconsortium/ccf-releases](https://github.com/hubmapconsortium/ccf-releases)), CC BY 4.0.
Overall citation: Quardokus E, Herr BW II, Record L, Börner K. *HuBMAP ASCT+B Tables*,
[humanatlas.io/asctb-tables](https://humanatlas.io/asctb-tables).

| Organ | Table |
|---|---|
| liver | Masci AM, Kendall T, Suzuki A. HuBMAP ASCT+B Tables. Liver v1.2, [10.48539/HBM449.XCGD.289](https://doi.org/10.48539/HBM449.XCGD.289) |
| kidney | Jain S, Valerius MT, He Y, El-Achkar T, Eadon M, Spraggins J. HuBMAP ASCT+B Tables. Kidney v1.4, [10.48539/HBM636.MXKP.682](https://doi.org/10.48539/HBM636.MXKP.682) |
| pancreas | Campbell-Thompson M, Eskaros A, Saunders D. HuBMAP ASCT+B Tables. Pancreas v1.3, [10.48539/HBM336.TBNP.923](https://doi.org/10.48539/HBM336.TBNP.923) |
| skin | Ginty F, Ho J, Sunshine J, Karunamurthy A. HuBMAP ASCT+B Tables. Skin v1.3, [10.48539/HBM785.XBPB.444](https://doi.org/10.48539/HBM785.XBPB.444) |
| lung | Pryhuber G. HuBMAP ASCT+B Tables. Lung v1.4, [10.48539/HBM823.VZGJ.394](https://doi.org/10.48539/HBM823.VZGJ.394) |
