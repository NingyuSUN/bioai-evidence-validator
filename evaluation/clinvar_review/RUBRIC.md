# ClinVar evidence review: reviewer rubric

Rubric version: **clinvar-review-rubric-1**

Thank you for reviewing. Each case is one human genetic variant that, in ClinVar's
**September 2023** release, had at least one submission classifying it as pathogenic or
likely pathogenic for a germline condition. You will see every submission ClinVar held for
that variant at that time. Your judgment will be compared with automated decisions, so
please follow your own professional judgment rather than guessing what a tool would do.

## What you see

For each case (identified only by a code such as `C3F9A21`):

- the gene symbol;
- every submission: submitter, whether the submitter provided **assertion criteria** (or the
  submission is an **expert panel** review or a **practice guideline**), the classification,
  the collection method, and the date the submitter last evaluated the variant.

Variant identifiers, submission accessions and ClinVar's own summary rating are hidden on
purpose.

## Rules

1. **Work independently.** Do not discuss cases with other reviewers until everyone has
   submitted. The group discusses only the *calibration* set, after labelling it.
2. **Judge the evidence as of September 2023.** Do not look up the variant's current ClinVar
   page or later literature. If you learn later information anyway, answer `yes` in
   `later_information_seen` for that case and label it as you would have without it.
3. **Use what is in the packet.** You may consult general references (e.g. ACMG/AMP
   guidance, gene–disease background). List anything you consulted in `sources_consulted`.
4. **Uncertainty is a valid answer.** Do not force a confident label.

## Label 1: the statement (`statement_label`)

*Taken together, do these submissions support describing this variant as pathogenic or
likely pathogenic (germline)?*

| Label | Meaning |
|---|---|
| `correct` | Yes, P/LP is the right summary of this evidence. |
| `incorrect` | No; the evidence as a whole points elsewhere (e.g. uncertain significance or benign). |
| `uncertain` | The evidence does not let you decide. |

## Labels 2–4: is the evidence sufficient for each use?

For each intended use, decide whether the P/LP classification may be used **as it stands**,
based on the submissions shown.

| Use (column) | The question |
|---|---|
| `research_summary` | May it be cited as a reported P/LP classification in a research summary or exploratory analysis, with ordinary caveats? |
| `clinical_reference` | May a clinical-grade knowledge base adopt it as a reference classification without its own re-curation? |
| `expert_reference` | Is it settled enough to serve as an expert-level reference, for example a benchmark or a training label, without further review? |

| Label | Meaning |
|---|---|
| `admitted` | Yes, usable for this purpose as it stands. |
| `review_required` | Plausibly usable, but a curator should look at it before this use. |
| `rejected` | Not usable for this purpose on this evidence. |

The three uses are increasingly demanding, but label each on its own merits.

## Rationales

Give a short reason for each label (a phrase is enough), especially for `review_required`,
`rejected`, `incorrect` and `uncertain`. Record roughly how many minutes the case took in
`minutes_spent` if you can; it helps plan future reviews.

## Returning your work

Send back the completed `review_workbook.xlsx` (or `labels.csv`) with your reviewer ID and
the date you finished. Your name is not published; a stable reviewer ID and a one-line
description of your relevant experience are.
