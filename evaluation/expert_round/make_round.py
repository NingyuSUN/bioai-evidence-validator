"""Build one expert-review workbook for three pending reviews, and the private key that maps it back (#23).

    uv run --frozen python evaluation/expert_round/make_round.py \
        --clinvar-packet artifacts/clinvar-review/reviewer_packet \
        --clinvar-key artifacts/clinvar-review/maintainer/key.json \
        --seed <a number you keep private> --output artifacts/expert-round-1

The workbook (`expert_review_round1.xlsx`) is what experts get. It has one sheet per part, so each expert does the
parts in their field, and every answer is a dropdown:
- Part A: ClinVar germline classifications as of September 2023: half where the validator and NCBI's review
  status disagree, half where they agree, in random order (the ClinVar review kit, #23);
- Part B: claims models extracted from cancer papers (the 60-claim expert sample of the extraction test, #21);
- Part C: single-cell cluster annotations: a fresh random sample of auto-admitted records with a few others
  mixed in (the audit of #24).

Nothing in the workbook shows which model made a claim, how bioevidence decided, or what the reference says. Items
of parts B and C get new codes, so the public results cannot be looked up by code. `maintainer/` holds the key,
the audit manifest and the seed: **keep it from the experts.** `import_round.py` reads returned workbooks back
into each review's own format.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BENCH = REPO / "evaluation" / "llm_benchmark"
sys.path.insert(0, str(BENCH))

ROUND = "expert-review-round-1"
CLINVAR_CASES = 40  # half divergent, half control, from the test split
WORKBOOK = "expert_review_round1.xlsx"

# What experts pick, and what each choice means in the review formats. Plain words, so the dropdowns read easily.
STATEMENT = {"yes": "correct", "no": "incorrect", "unsure": "uncertain"}
USE = {"usable as is": "admitted", "needs a curator's check": "review_required", "not usable": "rejected"}
CLAIM = {"yes": "yes", "no": "no", "unsure": "unsure"}
PROBLEMS = {  # the extraction-relevant failure modes of evaluation/error_taxonomy.yaml
    "Wrong gene, variant or disease": "EXT-5", "Wrong relation or effect": "EXT-6", "Opposite direction": "EXT-2",
    "Overstated certainty": "EXT-3", "Wrong population (e.g. only cell lines or mice)": "EXT-4",
    "The quotes do not show it": "EXT-1", "Not this paper's own result": "SRC-2", "Other (see comment)": "OTHER",
}

PARTS = {
    "A": {"sheet": "A · Variants", "title": "Part A · Germline variant classifications (ClinVar, September 2023)",
          "who": "Clinical or molecular geneticist, variant curator", "minutes": "about 2 hours"},
    "B": {"sheet": "B · Paper claims", "title": "Part B · Claims extracted from cancer papers",
          "who": "Cancer genomics, clinical variant curation", "minutes": "about 1.5 hours"},
    "C": {"sheet": "C · Single-cell", "title": "Part C · Single-cell cluster annotations",
          "who": "Single-cell biology, cell types", "minutes": "about 1 hour"},
}
RULES = [
    ("Do only the parts in your field; leave the other sheets blank.", "只做您专业相关的部分，其他工作表留空即可。"),
    ("Work alone. Do not discuss items with other reviewers until everyone has sent their file.",
     "请独立完成；所有人提交之前，不要和其他审稿人讨论。"),
    ("Judge only what is shown. Do not look up the variant's current ClinVar page or this project's results.",
     "只根据表中给出的信息判断；不要查询变异当前的 ClinVar 页面，也不要查看本项目的结果。"),
    ("Pick each answer from the dropdown in the yellow cells. 'unsure' is a valid answer.",
     "在黄色单元格的下拉菜单里选择答案；“unsure（不确定）”也是有效答案。"),
    ("A comment is optional, but one phrase helps when you answer 'no' or 'not usable'.",
     "备注可选；选择 no 或 not usable 时，写一句理由会很有帮助。"),
    ("Fill in your name or ID and one line on your experience above, then save and send the file back.",
     "在上方填写姓名或代号和一句话的专业背景，保存后把文件发回即可。"),
]
GUIDES = {
    "A": ["Evidence: every submission ClinVar held for the variant in September 2023 (submitter, criteria, "
          "classification, method, date). Variant IDs and ClinVar's own rating are hidden on purpose.",
          "Q1: taken together, do these submissions support calling the variant pathogenic or likely pathogenic "
          "(germline)? Q2–Q4: may the P/LP classification be used, as it stands, for:",
          "Q2 a research summary (cited as reported, with ordinary caveats) · Q3 a clinical knowledge base, without "
          "its own re-curation · Q4 an expert-level reference, such as a benchmark or training label."],
    "B": ["A model read the paper and extracted the claim. The quotes are the sentences it cited, with the paragraph "
          "each comes from; the PMID links to the paper if you need more.",
          "Q1: does the paper report this claim as stated: gene, variant, kind of effect, disease and therapies? "
          "Q2: if not, what is the main problem?"],
    "C": ["Each row is one cluster of a single-cell RNA-seq dataset: its top marker genes (log fold change; share "
          "of cells expressing it inside vs outside the cluster) and the cell type a model assigned.",
          "Q1: is that cell type right for this cluster? A correct but broader type counts as 'yes'. "
          "Q2: may this annotation be used, as it stands, in a research summary?"],
}
COLUMNS = {
    "A": [("Item", 10, None), ("Gene", 10, None), ("Submissions", 12, None), ("ClinVar submissions, September 2023", 80, None),
          ("Q1 · P/LP is the right summary?", 18, STATEMENT), ("Q2 · Research summary", 22, USE),
          ("Q3 · Clinical reference", 22, USE), ("Q4 · Expert reference", 22, USE), ("Comment (optional)", 36, "text")],
    "B": [("Item", 10, None), ("Paper", 14, None), ("Claim", 60, None), ("Quotes cited, with their paragraphs", 90, None),
          ("Q1 · The paper reports this claim?", 18, CLAIM), ("Q2 · If no: main problem", 34, PROBLEMS),
          ("Comment (optional)", 36, "text")],
    "C": [("Item", 10, None), ("Dataset", 26, None), ("Top marker genes", 70, None), ("Assigned cell type", 30, None),
          ("Markers the model cited", 40, None), ("Q1 · Right cell type?", 16, CLAIM),
          ("Q2 · Usable in a research summary?", 24, USE), ("Comment (optional)", 36, "text")],
}
HEADER_ROW = len(max(GUIDES.values(), key=len)) + 2  # guide lines, a blank line, then the header


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clinvar_items(packet: Path, key: dict, rng: random.Random) -> list[dict[str, Any]]:
    with (packet / "labels.csv").open(encoding="utf-8", newline="") as handle:
        rows = {r["case_code"]: r for r in csv.DictReader(handle)}
    picked = []
    for role in ("divergent", "control"):
        codes = sorted(c for c, case in key["cases"].items() if case["split"] == "test" and case["role"] == role)
        picked += rng.sample(codes, CLINVAR_CASES // 2)
    rng.shuffle(picked)
    return [{"item": code, "source": {"case_code": code},
             "cells": [code, rows[code]["gene"], rows[code]["submissions"], rows[code]["summary"]]} for code in picked]


def claim_items(rng: random.Random) -> list[dict[str, Any]]:
    import extraction_loop as x
    case = x.Case()
    results = BENCH / "results" / "extraction-test"
    rows = {(r["model"], r["task_id"]): r for r in x.load_jsonl(results / "episodes.jsonl")}
    sample = x.load_jsonl(results / "expert_sample" / "key.jsonl")
    words = {"predicts_sensitivity_in": "predicts sensitivity or response, in", "predicts_resistance_in":
             "predicts resistance, in", "poor_outcome_in": "is associated with poor outcome in", "better_outcome_in":
             "is associated with better outcome in", "diagnostic_of": "is diagnostic of", "predisposes_to": "predisposes to"}
    rng.shuffle(sample)
    items = []
    for number, entry in enumerate(sample, start=1):
        task = case.tasks[entry["task_id"]]
        attempts = rows[(entry["model"], entry["task_id"])]["claims"][entry["claim"]]["attempts"]
        claim = (attempts[0] if entry["group"] == "stopped by the chain" else attempts[-1])["claim"]
        s = claim["statement"]
        text = (f"{s['subject']['label']}{' ' + claim['variant'] if claim['variant'] else ''} "
                f"{words.get(s['predicate'], s['predicate'])} {s['object']['label']}"
                + (f" (therapies: {', '.join(claim['therapies'])})" if claim["therapies"] else ""))
        quotes = []
        for n, e in enumerate(claim["evidence"] or [], start=1):
            context = case.paragraph(task["pmid"], e["locator"], e["text"])
            against = " [cited as evidence AGAINST the claim]" if e["direction"] == "contradicts" else ""
            quotes.append(f"{n}. \"{e['text']}\"{against}" + (f"\n   Paragraph: {context}" if context and context != e["text"] else ""))
        items.append({"item": f"B{number:03d}", "source": {"sample_id": entry["sample_id"], "pmid": task["pmid"]},
                      "cells": [f"B{number:03d}", f"PMID {task['pmid']}", text, "\n\n".join(quotes) or "(no quote given)"],
                      "link": f"https://pubmed.ncbi.nlm.nih.gov/{task['pmid']}/"})
    return items


def singlecell_items(seed: int, maintainer: Path) -> list[dict[str, Any]]:
    import audit_celltype as ac
    import celltype_loop as cl

    from bioevidence_validator import audit, review
    case = cl.Case()
    cases = ac.export(case)
    predictions = review.load_predictions(BENCH / "results" / "celltype-audit" / "predictions.csv")
    sheet, manifest = audit.audit_sample(predictions, method=ac.METHOD, use=ac.USE, size=audit.sample_size(ac.TARGET),
                                         seed=seed, profile_id=ac.PROFILE, controls=ac.CONTROLS,
                                         predictions_sha256=review.sha256_file(BENCH / "results" / "celltype-audit" /
                                                                               "predictions.csv"))
    (maintainer / "singlecell_audit_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    items = []
    for number, row in enumerate(sheet, start=1):
        c = cases[row["case_id"]]
        task, answer = c["task"], c["answer"]
        markers = ", ".join(f"{m['gene']} ({float(m['logfc']):.1f}; {float(m['pct_in']):.0%} vs {float(m['pct_out']):.0%})"
                            for m in task["markers"])
        cited = ", ".join(f"{m['gene']}{'' if m['stance'] == 'supports' else ' (against)'}" for m in answer["markers"])
        items.append({"item": f"S{number:03d}", "source": {k: row[k] for k in ("case_id", "record_sha256", "profile_id",
                                                                                "profile_sha256", "requested_use", "split")},
                      "cells": [f"S{number:03d}", f"{task['species']} {task['tissue']}, {task['assay']} (cluster {task['cluster']})",
                                markers, f"{answer['cell_type_label']} ({answer['cell_type_id']})", cited or "none"]})
    return items


def write_workbook(path: Path, parts: dict[str, list[dict[str, Any]]]) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation

    yellow, grey = PatternFill("solid", fgColor="FFF4CC"), PatternFill("solid", fgColor="F2F2F2")
    wrap = Alignment(wrap_text=True, vertical="top")
    thin = Border(bottom=Side(style="thin", color="BFBFBF"))
    book = Workbook()
    start = book.active
    start.title = "Start here"
    start.column_dimensions["A"].width = 30
    start.column_dimensions["B"].width = 70
    start.column_dimensions["C"].width = 55
    start["A1"] = "Expert review · round 1   专家审阅 · 第一轮"
    start["A1"].font = Font(bold=True, size=15)
    start["A2"] = ("We test whether AI-produced curation can be trusted. Your judgment is the reference the AI is "
                   "measured against. 我们在检验 AI 生成的生物学标注是否可信，您的判断就是衡量 AI 的标准。")
    start["A2"].alignment = wrap
    start.merge_cells("A2:C2")
    start.row_dimensions[2].height = 32
    for row, label in enumerate(("Your name or ID  姓名或代号", "Your field, one line  专业背景（一句话）",
                                 "Date finished  完成日期"), start=4):
        start.cell(row=row, column=1, value=label).font = Font(bold=True)
        start.cell(row=row, column=2).fill = yellow
    start.cell(row=8, column=1, value="Part  部分").font = Font(bold=True)
    start.cell(row=8, column=2, value="For  适合").font = Font(bold=True)
    start.cell(row=8, column=3, value="Items · time  条目 · 时间").font = Font(bold=True)
    for row, (name, part) in enumerate(PARTS.items(), start=9):
        start.cell(row=row, column=1, value=f"{part['sheet']}")
        start.cell(row=row, column=2, value=part["who"])
        start.cell(row=row, column=3, value=f"{len(parts[name])} items · {part['minutes']}")
    start.cell(row=13, column=1, value="How  怎么做").font = Font(bold=True)
    for row, (english, chinese) in enumerate(RULES, start=14):
        start.cell(row=row, column=1, value=f"{row - 13}.")
        start.cell(row=row, column=2, value=english).alignment = wrap
        start.cell(row=row, column=3, value=chinese).alignment = wrap
        start.row_dimensions[row].height = 30
    start.cell(row=21, column=1, value="Thank you!  谢谢！").font = Font(bold=True)

    # Dropdown options live on a hidden sheet: an inline list would split options at their commas.
    options = book.create_sheet("Lists")
    lists: dict[int, str] = {}
    for column, choices in enumerate((STATEMENT, USE, CLAIM, PROBLEMS), start=1):
        for row, label in enumerate(choices, start=1):
            options.cell(row=row, column=column, value=label)
        letter = options.cell(row=1, column=column).column_letter
        lists[id(choices)] = f"=Lists!${letter}$1:${letter}${len(choices)}"
    options.sheet_state = "hidden"

    for name, items in parts.items():
        sheet = book.create_sheet(PARTS[name]["sheet"])
        columns = COLUMNS[name]
        sheet.cell(row=1, column=1, value=PARTS[name]["title"]).font = Font(bold=True, size=13)
        for n, line in enumerate(GUIDES[name], start=2):
            cell = sheet.cell(row=n, column=1, value=line)
            cell.alignment = wrap
            sheet.merge_cells(start_row=n, start_column=1, end_row=n, end_column=len(columns))
            sheet.row_dimensions[n].height = 30
        for index, (title, width, choices) in enumerate(columns, start=1):
            cell = sheet.cell(row=HEADER_ROW, column=index, value=title)
            cell.font, cell.alignment, cell.fill = Font(bold=True), wrap, yellow if choices else grey
            sheet.column_dimensions[cell.column_letter].width = width
        sheet.row_dimensions[HEADER_ROW].height = 34
        first, last = HEADER_ROW + 1, HEADER_ROW + len(items)
        for offset, item in enumerate(items):
            row = first + offset
            for index, value in enumerate(item["cells"], start=1):
                cell = sheet.cell(row=row, column=index, value=value)
                cell.alignment, cell.border = wrap, thin
            if item.get("link"):
                sheet.cell(row=row, column=2).hyperlink = item["link"]
                sheet.cell(row=row, column=2).font = Font(color="0563C1", underline="single")
            for index, (_, _, choices) in enumerate(columns, start=1):
                if choices:
                    cell = sheet.cell(row=row, column=index)
                    cell.fill, cell.alignment, cell.border = yellow, wrap, thin
        for index, (_, _, choices) in enumerate(columns, start=1):
            if isinstance(choices, dict):
                letter = sheet.cell(row=HEADER_ROW, column=index).column_letter
                rule = DataValidation(type="list", formula1=lists[id(choices)], allow_blank=True,
                                      showErrorMessage=True, errorTitle="Please pick from the list",
                                      error="Choose one of the options in the dropdown.")
                rule.add(f"{letter}{first}:{letter}{last}")
                sheet.add_data_validation(rule)
        sheet.freeze_panes = sheet.cell(row=first, column=2)
    book.save(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clinvar-packet", type=Path, required=True)
    parser.add_argument("--clinvar-key", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True, help="Keep it private: it fixes which items are drawn")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"{args.output} is not empty; refusing to overwrite a round")
    maintainer = args.output / "maintainer"
    maintainer.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    clinvar_key = json.loads(args.clinvar_key.read_text(encoding="utf-8"))
    parts = {"A": clinvar_items(args.clinvar_packet, clinvar_key, rng), "B": claim_items(rng),
             "C": singlecell_items(args.seed, maintainer)}
    write_workbook(args.output / WORKBOOK, parts)
    key = {"round": ROUND, "warning": "Keep from the experts: it maps items to their sources.", "seed": args.seed,
           "clinvar_key_sha256": sha256_text(args.clinvar_key.read_text(encoding="utf-8")),
           "choices": {"statement": STATEMENT, "use": USE, "claim": CLAIM, "problems": PROBLEMS},
           "items": {name: {i["item"]: i["source"] for i in items} for name, items in parts.items()}}
    (maintainer / "round_key.json").write_text(json.dumps(key, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output / WORKBOOK}: " + ", ".join(f"part {n} {len(i)} items" for n, i in parts.items())
          + f". Keep {maintainer} private.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
