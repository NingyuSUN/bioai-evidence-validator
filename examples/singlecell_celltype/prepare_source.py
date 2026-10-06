"""Build the pinned single-cell cell-type annotation case (run once, offline, from downloaded files).

    uv run --frozen --with anndata==0.11.4 python examples/singlecell_celltype/prepare_source.py --data DIR

DIR holds what was downloaded beforehand (see README): `selected.json` (the CELLxGENE Discover metadata of the
six datasets), `h5ad/<name>.h5ad`, `ref/cl.obo` (the full release: it keeps the disjointness axioms), `ref/hgnc_complete_set.txt`, `asctb/asct-b-vh-<organ>.csv`.
None of it is committed except as the derived, content-addressed snapshots below.

1. Markers. For each dataset, each cell type its authors annotated (a Cell Ontology term, not "unknown", with
   at least MIN_CELLS cells) is one "cluster". Raw counts are normalised to 10,000 per cell and log1p-transformed; for
   each cluster and gene, `logfc` is the mean in the cluster minus the mean in all other cells, `pct_in` and
   `pct_out` the fractions of cells with a non-zero count. Genes expressed in at least a quarter of the
   cluster are ranked by `logfc`; the top TOP_GENES with a positive `logfc` form the cluster's marker table.
   Genes are named by their current HGNC approved symbol, mapped from their Ensembl ID; genes without an
   HGNC entry are left out.
2. Truth. The authors' term for each cluster, updated to its replacement when the pinned Cell Ontology release
   has obsoleted it. It is kept apart from the tasks, which never show it.
3. Reference. HuBMAP ASCT+B biomarker genes, as `gene marker_of cell type` assertions: each row's most specific
   cell type with a CL identifier, and its gene biomarkers under their current HGNC symbols.
4. Tasks. One per cluster: the tissue, the assay and the top PROMPT_GENES markers with their statistics. Per
   dataset, clusters in keyed-hash order go to the pilot split (PILOT_PER_DATASET) and the rest to the test split.
5. Definition panels. For every cluster, `pct_in` and `logfc` of every gene that a Cell Ontology presence or
   absence axiom mentions (`bioevidence_validator.definitions`), whether or not it is a marker of the cluster.
6. External datasets. When DIR also holds `selected-v2.json` and `h5ad-v2/`, six more datasets from other
   studies are added the same way, all of their clusters in the `external` split: a held-out set for checks
   designed on the first six.

Outputs in sources/: `snapshots/<sha256>.<ext>.gz` (marker tables, the Cell Ontology release, the HGNC set, the
ASCT+B reference), `tasks.jsonl`, `truth.jsonl`, `manifest.json` and `ATTRIBUTION.md`.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

import anndata
import numpy as np
import scipy.sparse as sp

from bioevidence_validator.definitions import MarkerDefinitions
from bioevidence_validator.identifiers import Genes, Ontology

ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / "sources"
KEY = "bioai-singlecell-celltype-v1"
MIN_CELLS, TOP_GENES, PROMPT_GENES, MIN_PCT, PILOT_PER_DATASET = 30, 50, 20, 0.25, 4
ORGANS = {"liver": "liver", "kidney": "kidney", "pancreas": "pancreas", "skin": "skin", "lung_t_nk_ilc": "lung"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pin(data: bytes, suffix: str) -> str:
    """Write a gzip-compressed snapshot named by the SHA-256 of its uncompressed bytes."""
    digest = sha256(data)
    (SOURCES / "snapshots").mkdir(parents=True, exist_ok=True)
    (SOURCES / "snapshots" / f"{digest}.{suffix}.gz").write_bytes(gzip.compress(data, mtime=0))
    return digest


def tsv(columns: list[str], rows: list[dict]) -> bytes:
    out = io.StringIO()
    writer = csv.DictWriter(out, columns, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def markers(path: Path, genes: Genes, ontology: Ontology, panel: set[str]) -> tuple[list[dict], list[dict], list[dict]]:
    """(marker rows, clusters, definition panel rows) for one dataset."""
    data = anndata.read_h5ad(path)
    counts = data.raw.X if data.raw is not None else data.X
    var = data.raw.var if data.raw is not None else data.var
    matrix = sp.csr_matrix(counts, dtype=np.float64)
    ensembl = {row.get("ensembl_gene_id"): symbol for symbol, row in
               ((r["symbol"], r) for r in genes.by_id.values()) if row.get("ensembl_gene_id")}
    keep, symbols = [], []
    for column, gene_id in enumerate(var.index):
        symbol = ensembl.get(str(gene_id).split(".")[0])
        if symbol and symbol not in symbols:
            keep.append(column)
            symbols.append(symbol)
    matrix = matrix[:, keep]
    size = np.asarray(matrix.sum(axis=1)).ravel()
    normalised = sp.diags(1e4 / np.where(size > 0, size, 1)) @ matrix
    normalised.data = np.log1p(normalised.data)
    expressed = (matrix > 0).astype(np.float64)
    terms = data.obs["cell_type_ontology_term_id"].astype(str).to_numpy()
    labels = dict(zip(terms, data.obs["cell_type"].astype(str), strict=True))
    total, total_expressed, cells = (np.asarray(normalised.sum(axis=0)).ravel(),
                                     np.asarray(expressed.sum(axis=0)).ravel(), len(terms))
    rows, clusters, panel_rows = [], [], []
    measured = [i for i, g in enumerate(symbols) if g in panel]
    usable = sorted(t for t in set(terms) if t.startswith("CL:") and (terms == t).sum() >= MIN_CELLS)
    for n, term in enumerate(usable, start=1):
        mask = terms == term
        inside = mask.sum()
        mean_in = np.asarray(normalised[mask].sum(axis=0)).ravel() / inside
        mean_out = (total - mean_in * inside) / (cells - inside)
        pct_in = np.asarray(expressed[mask].sum(axis=0)).ravel() / inside
        pct_out = (total_expressed - pct_in * inside) / (cells - inside)
        logfc = mean_in - mean_out
        ranked = sorted((i for i in range(len(symbols)) if pct_in[i] >= MIN_PCT and logfc[i] > 0),
                        key=lambda i: (-round(logfc[i], 6), symbols[i]))[:TOP_GENES]
        cluster = f"c{n:02d}"
        panel_rows += [{"cluster": cluster, "gene": symbols[i], "pct_in": f"{pct_in[i]:.3f}", "logfc": f"{logfc[i]:.3f}"}
                       for i in sorted(measured, key=lambda i: symbols[i])]
        rows += [{"cluster": cluster, "gene": symbols[i], "rank": rank, "logfc": f"{logfc[i]:.3f}",
                  "pct_in": f"{pct_in[i]:.3f}", "pct_out": f"{pct_out[i]:.3f}"} for rank, i in enumerate(ranked, start=1)]
        truth, note = term, ""
        if term in ontology.terms and ontology.terms[term].obsolete:
            replacement = ontology.terms[term].replaced_by
            truth, note = (replacement[0], f"obsolete {term} replaced") if replacement else (term, "obsolete, no replacement")
        clusters.append({"cluster": cluster, "author_term": term, "author_label": labels[term], "term": truth,
                         "label": ontology.terms[truth].name if truth in ontology.terms else labels[term],
                         "cells": int(inside), "note": note})
    return rows, clusters, panel_rows


def asctb(directory: Path, genes: Genes) -> list[dict]:
    """gene marker_of cell type, from the ASCT+B biomarker gene columns."""
    found = {}
    for organ in sorted(set(ORGANS.values())):
        lines = (directory / f"asct-b-vh-{organ}.csv").read_text(encoding="utf-8-sig").splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith("AS/1,"))
        for row in csv.DictReader(lines[start:]):
            cell_types = [(row[k], row.get(k.replace("/ID", "/LABEL")) or row.get(k.replace("/ID", "")) or "")
                          for k in row if k and k.startswith("CT/") and k.endswith("/ID") and (row[k] or "").startswith("CL:")]
            if not cell_types:
                continue
            cell_type, label = cell_types[-1]
            for key in (k for k in row if k and k.startswith("BGene/") and k.endswith("/ID")):
                gene = genes.by_id.get((row[key] or "").strip())
                if gene:
                    found[(gene["symbol"], cell_type)] = {"subject": gene["symbol"], "predicate": "marker_of",
                                                          "object": cell_type, "object_label": label.strip(),
                                                          "organ": organ}
    return [found[k] for k in sorted(found)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, required=True)
    args = parser.parse_args(argv)
    data = args.data
    cl_bytes, hgnc_bytes = (data / "ref/cl.obo").read_bytes(), (data / "ref/hgnc_complete_set.txt").read_bytes()
    ontology, genes = Ontology.from_obo(cl_bytes), Genes.from_hgnc(hgnc_bytes)
    definitions = MarkerDefinitions(ontology, genes)
    panel = {g for t in ontology.terms if t.startswith("CL:") for _, _, gs in definitions.of(t) for g in gs}
    manifest = {"key": KEY, "parameters": {"min_cells": MIN_CELLS, "top_genes": TOP_GENES, "prompt_genes": PROMPT_GENES,
                                           "min_pct": MIN_PCT, "pilot_per_dataset": PILOT_PER_DATASET},
                "cell_ontology": {"version": ontology.version, "sha256": pin(cl_bytes, "obo")},
                "hgnc": {"file": "hgnc_complete_set.txt", "retrieved": "2026-09-30", "sha256": pin(hgnc_bytes, "tsv")},
                "datasets": []}
    reference = asctb(data / "asctb", genes)
    manifest["asctb"] = {"organs": sorted(set(ORGANS.values())), "release": "ccf-releases v2.0", "assertions": len(reference),
                         "sha256": pin(tsv(["subject", "predicate", "object", "object_label", "organ"], reference), "tsv")}
    tasks, truth = [], []
    groups = [("development", data / "selected.json", data / "h5ad"), ("external", data / "selected-v2.json", data / "h5ad-v2")]
    selected = [(group, meta, folder) for group, listing, folder in groups if listing.exists()
                for meta in json.loads(listing.read_text(encoding="utf-8"))]
    manifest["parameters"]["definition_panel_genes"] = len(panel)
    for group, meta, folder in selected:
        h5ad = folder / f"{meta['name']}.h5ad"
        rows, clusters, panel_rows = markers(h5ad, genes, ontology, panel)
        table = pin(tsv(["cluster", "gene", "rank", "logfc", "pct_in", "pct_out"], rows), "tsv")
        panel_table = pin(tsv(["cluster", "gene", "pct_in", "logfc"], panel_rows), "tsv")
        manifest["datasets"].append({**{k: meta[k] for k in ("name", "dataset_id", "dataset_version_id", "title",
                                                               "collection_name", "collection_doi", "cell_count", "url")},
                                     "tissue": meta["tissue"][0], "assay": [a["label"] for a in meta["assay"]],
                                     "h5ad_sha256": sha256(h5ad.read_bytes()), "markers_sha256": table,
                                     "panel_sha256": panel_table, "clusters": len(clusters), "group": group})
        order = sorted(clusters, key=lambda c: sha256(f"{KEY}:{meta['dataset_id']}:{c['cluster']}".encode()))
        pilot = {c["cluster"] for c in order[:PILOT_PER_DATASET]}
        for c in clusters:
            task_id = "ct-" + sha256(f"{meta['dataset_id']}:{c['cluster']}".encode())[:10]
            top = [r for r in rows if r["cluster"] == c["cluster"]][:PROMPT_GENES]
            split = "external" if group == "external" else "pilot" if c["cluster"] in pilot else "test"
            tasks.append({"task_id": task_id, "split": split,
                          "dataset": meta["name"], "cluster": c["cluster"], "tissue": meta["tissue"][0]["label"],
                          "assay": ", ".join(a["label"] for a in meta["assay"]), "species": "Homo sapiens",
                          "markers_sha256": table,
                          "markers": [{k: r[k] for k in ("gene", "logfc", "pct_in", "pct_out")} for r in top]})
            truth.append({"task_id": task_id, "dataset": meta["name"], **c})
    for name, rows in (("tasks.jsonl", tasks), ("truth.jsonl", truth)):
        (SOURCES / name).write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8",
                                    newline="\n")
    (SOURCES / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8",
                                           newline="\n")
    splits = {s: sum(t["split"] == s for t in tasks) for s in ("pilot", "test", "external")}
    print(f"{len(tasks)} tasks {splits}, {len(reference)} ASCT+B assertions, {len(panel)} definition panel genes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
