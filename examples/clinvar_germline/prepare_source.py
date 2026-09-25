"""Rebuild the frozen ClinVar sample and population outcome table from three pinned NCBI archive files.

Needs the exact upstream bytes (about 850 MB in total); runtime examples need only the outputs.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import hashlib
import json
import re
from pathlib import Path

ARCHIVE = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/archive/"
UPSTREAM = {
    "submission_summary_2023-09": ("2023/submission_summary_2023-09.txt.gz", 201026694,
                                   "71c799c2d1bf5dbd4ffffdfc8e3d743093e5ee0c24ba9544ec0cb654ac8141ca"),
    "variant_summary_2023-09": ("2023/variant_summary_2023-09.txt.gz", 210839206,
                                "3c224263fbe8ade318c4bdbfda0e4cef4d449470ad6467bdc504171dc9a1a4e3"),
    "variant_summary_2026-09": ("variant_summary_2026-09.txt.gz", 442495433,
                                "186ad2838a138f0bc7a79b1b7b6dde5533b105175d293e1131652889529804c9"),
}
SAMPLE_SALT = "bioai-clinvar-v1:"
PER_STRATUM = 1000
PLP_AGGREGATE = {"Pathogenic", "Likely pathogenic", "Pathogenic/Likely pathogenic"}
STRATA = {  # 2023 aggregate review status -> stratum; conflicting variants need a criteria-based P/LP submission.
    "no assertion criteria provided": "no_criteria",
    "criteria provided, single submitter": "single_submitter",
    "criteria provided, multiple submitters, no conflicts": "multiple_submitters",
    "reviewed by expert panel": "expert_panel",
    "practice guideline": "practice_guideline",
    "criteria provided, conflicting interpretations": "conflicting",
}
PLP_TERMS = {"Pathogenic", "Likely pathogenic", "Pathogenic, low penetrance", "Likely pathogenic, low penetrance"}
RISK_TERMS = {"Likely risk allele", "Established risk allele"}
DOWNGRADE_TERMS = {"Uncertain significance", "Likely benign", "Benign"}
SUBMISSION_FIELDS = ["SCV", "Submitter", "ReviewStatus", "ClinicalSignificance", "CollectionMethod", "DateLastEvaluated"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def rows(path: Path):
    """Yield dicts from a ClinVar tab file whose header line starts with '#VariationID' or '#AlleleID'."""
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        header = None
        for line in handle:
            if header is None:
                if line.startswith(("#VariationID\t", "#AlleleID\t")):
                    header = line[1:].rstrip("\n").split("\t")
                continue
            yield dict(zip(header, line.rstrip("\n").split("\t")))


def variant_table(path: Path) -> dict[str, dict]:
    """One row per VariationID; the GRCh38 row wins where both assemblies are listed."""
    table = {}
    for row in rows(path):
        if row["VariationID"] not in table or row["Assembly"] == "GRCh38":
            table[row["VariationID"]] = row
    return table


def outcome(classification: str | None) -> str:
    """Categorize a later aggregate germline classification."""
    if classification is None:
        return "missing"
    if classification.startswith("Conflicting"):
        return "conflicting"
    terms = {term.strip() for term in re.split(r"[/;]", classification) if term.strip()}
    if terms & PLP_TERMS and terms <= PLP_TERMS | RISK_TERMS:
        return "stable_plp"
    if terms & DOWNGRADE_TERMS:
        return "downgraded"
    return "other"


def stratum(row: dict) -> str | None:
    if row["OriginSimple"] != "germline":
        return None
    name = STRATA.get(row["ReviewStatus"])
    if name == "conflicting" or (name and row["ClinicalSignificance"] in PLP_AGGREGATE):
        return name
    return None


def order_key(variation_id: str) -> str:
    return hashlib.sha256((SAMPLE_SALT + variation_id).encode()).hexdigest()


def build(inputs: dict[str, Path], output: Path, retrieved_at: str) -> dict:
    if output.exists():
        raise ValueError("Use a new output directory")
    for name, (relative, size, expected) in UPSTREAM.items():
        path = inputs[name]
        if path.stat().st_size != size or sha256_file(path) != expected:
            raise ValueError(f"{path} is not the pinned upstream file {relative}")

    v23 = variant_table(inputs["variant_summary_2023-09"])
    v26 = variant_table(inputs["variant_summary_2026-09"])
    candidates = collections.defaultdict(list)
    for variation_id, row in v23.items():
        if name := stratum(row):
            candidates[name].append(variation_id)

    submissions = collections.defaultdict(list)
    wanted = {i for ids in candidates.values() for i in ids}
    for row in rows(inputs["submission_summary_2023-09"]):
        if row["VariationID"] in wanted:
            submissions[row["VariationID"]].append({key: row[key] for key in SUBMISSION_FIELDS})

    def outcomes(ids):
        counts = collections.Counter(outcome(v26[i]["ClinicalSignificance"] if i in v26 else None) for i in ids)
        return {"n": len(ids), "outcomes_2026_09": dict(sorted(counts.items()))}

    # Whole-population context, including the split the validator treats more strictly than NCBI:
    # a 2023-09 P/LP variant with any dissenting (VUS/LB/B) submission, with or without assertion criteria.
    population = {}
    for name, ids in sorted(candidates.items()):
        if name == "conflicting":
            continue
        dissent = {i for i in ids if any(s["ClinicalSignificance"] in DOWNGRADE_TERMS for s in submissions.get(i, []))}
        population[name] = {**outcomes(ids),
                            "with_dissenting_submission": outcomes(sorted(dissent)),
                            "without_dissenting_submission": outcomes(sorted(set(ids) - dissent))}

    def eligible(variation_id: str, name: str) -> bool:
        subs = submissions.get(variation_id)
        if not subs:
            return False
        if name == "conflicting":  # the proposed P/LP statement needs criteria-based P/LP support
            return any(s["ClinicalSignificance"] in PLP_TERMS and s["ReviewStatus"] != "no assertion criteria provided"
                       and s["ReviewStatus"] != "no assertion provided" for s in subs)
        return True

    sample = []
    for name, ids in sorted(candidates.items()):
        chosen = [i for i in sorted(ids, key=order_key) if eligible(i, name)][:PER_STRATUM]
        for variation_id in chosen:
            old, new = v23[variation_id], v26.get(variation_id)
            sample.append({
                "variation_id": variation_id, "stratum": name, "gene": old["GeneSymbol"],
                "clinvar_2023_09": {"classification": old["ClinicalSignificance"], "review_status": old["ReviewStatus"],
                                    "number_submitters": int(old["NumberSubmitters"])},
                "clinvar_2026_09": None if new is None else {"classification": new["ClinicalSignificance"],
                                                             "review_status": new["ReviewStatus"]},
                "submissions": sorted(submissions[variation_id], key=lambda s: s["SCV"]),
            })
    sample.sort(key=lambda case: (case["stratum"], order_key(case["variation_id"])))

    output.mkdir(parents=True)
    projection = "".join(json.dumps(case, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n" for case in sample)
    # Compressed bytes can differ between zlib builds, so the manifest pins the decompressed content.
    (output / "clinvar-sample.jsonl.gz").write_bytes(gzip.compress(projection.encode(), mtime=0))
    population_text = json.dumps({"population_2023_09_germline_plp": population}, indent=2, sort_keys=True) + "\n"
    (output / "population_outcomes.json").write_text(population_text, encoding="utf-8", newline="\n")
    manifest = {
        "dataset": "ClinVar germline classification sample (2023-09) with 2026-09 aggregate outcome",
        "upstream": {name: {"url": ARCHIVE + relative, "bytes": size, "sha256": expected}
                     for name, (relative, size, expected) in UPSTREAM.items()},
        "retrieved_at": retrieved_at,
        "attribution": "ClinVar, National Center for Biotechnology Information (NCBI), U.S. National Library of Medicine",
        "terms": "ClinVar data are freely available (https://www.ncbi.nlm.nih.gov/clinvar/intro/); "
                 "not for direct diagnostic use (https://www.ncbi.nlm.nih.gov/clinvar/docs/maintenance_use/).",
        "projection_file": "sources/clinvar-sample.jsonl.gz",
        "projection_sha256": hashlib.sha256(projection.encode()).hexdigest(),
        "projection_bytes": len(projection.encode()),
        "projection_hash_scope": "SHA-256 and byte count of the decompressed JSON Lines content",
        "population_file": "sources/population_outcomes.json",
        "population_sha256": hashlib.sha256(population_text.encode()).hexdigest(),
        "variant_count": len(sample),
        "strata": dict(sorted(collections.Counter(case["stratum"] for case in sample).items())),
        "selection": (f"2023-09 germline (OriginSimple) variants whose aggregate classification is Pathogenic, "
                      f"Likely pathogenic or Pathogenic/Likely pathogenic, stratified by aggregate review status, "
                      f"plus 'conflicting interpretations' variants with at least one criteria-based P/LP submission. "
                      f"Within each stratum, variants are ordered by SHA-256('{SAMPLE_SALT}' + VariationID) and the "
                      f"first {PER_STRATUM} with 2023-09 submissions are kept (all, if fewer). Retained per submission: "
                      f"{', '.join(SUBMISSION_FIELDS)}. Free-text descriptions are not retained."),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in UPSTREAM:
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True, dest=name)
    parser.add_argument("--retrieved-at", required=True, help="UTC time the upstream files were downloaded")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dt.datetime.fromisoformat(args.retrieved_at.replace("Z", "+00:00"))
    result = build({name: getattr(args, name) for name in UPSTREAM}, args.output, args.retrieved_at)
    print(json.dumps({k: result[k] for k in ("variant_count", "strata", "projection_sha256", "projection_bytes")}, indent=2))
