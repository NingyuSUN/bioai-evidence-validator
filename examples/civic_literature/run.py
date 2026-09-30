"""Negative controls for literature grounding (issue #20) on the pinned CIViC corpus, offline.

    uv run --frozen python examples/civic_literature/run.py --output artifacts/civic-literature

For every corpus paper, a base record quotes one real sentence of the paper (verified: it should be admitted)
and five controls change it the way an AI citation goes wrong. Retracted papers get base records of their
own. Detection means the record was not admitted and the expected finding was raised; a record held only
as unverifiable (BEV015/BEV020) is reported separately and is not counted as detected.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from pipeline import ROOT, Corpus, controls, keyed, quote_for, record

from bioevidence_validator.engine import RecordValidator
from bioevidence_validator.grounding import SourceBytesGrounder

EXPECTED = {"base": None, "fabricated_identifier": "BEV016", "real_identifier_wrong_paper": "BEV017",
            "altered_quote": "BEV017", "negation_flip": "BEV017", "species_swap": "BEV017", "retracted_source": "BEV019"}
UNVERIFIABLE = {"BEV015", "BEV020"}


def wilson(events: int, n: int, z: float = 1.959963984540054) -> list[float] | None:
    if not n:
        return None
    p = events / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def run(output: Path) -> dict:
    if output.exists():
        raise ValueError("Use a new output directory to preserve previous evidence")
    corpus = Corpus()
    validator = RecordValidator(profile=ROOT / "profile.yaml",
                                grounders=[SourceBytesGrounder(corpus.store), corpus.grounder()])
    papers = sorted(corpus.manifest["corpus"], key=keyed)
    fakes = corpus.manifest["nonexistent_pmids"]
    items: dict[str, list[dict]] = {}
    for item in corpus.evidence:
        items.setdefault(item["citation_id"], []).append(item)
    rows, skipped = [], {}

    def evaluate(rec: dict, pmid: str, control: str) -> None:
        report = validator.validate(corpus.pin(rec))
        codes = sorted({f["rule_id"] for f in report["findings"]})
        status = report["overall_status"]
        expected = EXPECTED[control]
        rows.append({"pmid": pmid, "control": control, "status": status, "reason_codes": codes,
                     "detected": expected is not None and status != "admitted" and expected in codes,
                     "unverifiable_only": status != "admitted" and set(codes) <= UNVERIFIABLE})

    for n, pmid in enumerate(papers):
        item = min(items[pmid], key=lambda row: int(row["evidence_id"]))
        quote = quote_for(corpus, pmid, item["molecular_profile"].split()[0])
        if quote is None:
            skipped["no_usable_sentence"] = skipped.get("no_usable_sentence", 0) + 1
            continue
        base = record(pmid, corpus.title(pmid), item, quote)
        evaluate(base, pmid, "base")
        for control, changed in controls(base, papers[(n + 1) % len(papers)], fakes[n % len(fakes)]).items():
            if changed is None:
                skipped[control] = skipped.get(control, 0) + 1
            else:
                evaluate(changed, pmid, control)
    for pmid in sorted(corpus.manifest["retracted"], key=keyed):
        quote = quote_for(corpus, pmid, None)
        if quote is None:
            skipped["retracted_no_sentence"] = skipped.get("retracted_no_sentence", 0) + 1
            continue
        placeholder = {"evidence_id": f"retracted-{pmid}", "molecular_profile_id": "0",
                       "molecular_profile": "Retracted-source control", "evidence_direction": "Supports",
                       "significance": "Control", "disease": "control", "therapies": ""}
        evaluate(record(pmid, corpus.title(pmid), placeholder, quote), pmid, "retracted_source")

    summary: dict = {"benchmark": "civic-literature-controls-v1", "papers": len(papers),
                     "retracted_papers": len(corpus.manifest["retracted"]), "skipped": dict(sorted(skipped.items())),
                     "controls": {}}
    for control, expected in EXPECTED.items():
        mine = [r for r in rows if r["control"] == control]
        if control == "base":
            blocked = sum(r["status"] != "admitted" for r in mine)
            summary["controls"][control] = {"n": len(mine), "false_blocks": blocked, "wilson_95": wilson(blocked, len(mine)),
                                            "status_counts": count(mine)}
        else:
            hits = sum(r["detected"] for r in mine)
            summary["controls"][control] = {"n": len(mine), "expected_code": expected, "detected": hits,
                                            "rate": round(hits / len(mine), 4) if mine else None,
                                            "wilson_95": wilson(hits, len(mine)),
                                            "unverifiable_only": sum(r["unverifiable_only"] for r in mine),
                                            "admitted": sum(r["status"] == "admitted" for r in mine),
                                            "status_counts": count(mine)}
    output.mkdir(parents=True)
    (output / "controls.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows),
                                           encoding="utf-8", newline="\n")
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8",
                                         newline="\n")
    (output / "summary.md").write_text(render(summary), encoding="utf-8", newline="\n")
    print(render(summary))
    return summary


def count(rows: list[dict]) -> dict[str, int]:
    return {status: sum(r["status"] == status for r in rows) for status in ("admitted", "review_required", "rejected")}


def render(summary: dict) -> str:
    lines = ["# Literature grounding: negative controls on real papers", "",
             f"{summary['papers']} open-access CIViC papers (CC BY or CC0) and {summary['retracted_papers']} retracted "
             "open-access papers, pinned as PMC JATS.", "",
             "| Control | Records | Detected | Rate (Wilson 95%) | Unverifiable only | Admitted |",
             "|---|---:|---:|---:|---:|---:|"]
    for control, m in summary["controls"].items():
        if control == "base":
            continue
        ci = m["wilson_95"]
        rate = f"{100 * m['rate']:.1f}% ({100 * ci[0]:.1f}–{100 * ci[1]:.1f})" if m["n"] else "N/A"
        lines.append(f"| {control} (`{m['expected_code']}`) | {m['n']} | {m['detected']} | {rate} | "
                     f"{m['unverifiable_only']} | {m['admitted']} |")
    base = summary["controls"]["base"]
    ci = base["wilson_95"]
    lines += ["", f"Base records (a real sentence of the cited paper): {base['false_blocks']}/{base['n']} not admitted"
              + (f" (Wilson 95% {100 * ci[0]:.1f}–{100 * ci[1]:.1f}%)." if ci else "."), "",
              "Controls that cannot be built for a sentence (no negation site, no species word) are skipped: "
              + ", ".join(f"{k} {v}" for k, v in summary["skipped"].items()) + ".", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
    sys.exit(0)
