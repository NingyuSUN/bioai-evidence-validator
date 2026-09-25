"""Independent human review: check annotations, measure agreement, adjudicate, score and freeze.

Implements the workflow in docs/GOLD_STANDARD.md for the CSV formats in evaluation/gold_standard/.
Reference labels live here, never in the engine: they evaluate decisions, they do not make them.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ANNOTATION_COLUMNS = [
    "annotation_id", "case_id", "record_sha256", "profile_id", "profile_sha256", "requested_use", "group_id",
    "split", "reviewer_id", "reviewer_qualification", "annotated_at", "mapping_label", "mapping_rationale",
    "admission_label", "admission_rationale", "evidence_refs_json",
]
OPTIONAL_ANNOTATION_COLUMNS = ["later_information_seen", "minutes_spent"]
ADJUDICATION_COLUMNS = [
    "adjudication_id", "case_id", "record_sha256", "profile_sha256", "requested_use", "annotation_ids_json",
    "mapping_label", "admission_label", "adjudicator_id", "adjudicated_at", "mapping_rationale",
    "admission_rationale", "evidence_refs_json",
]
PREDICTION_COLUMNS = ["case_id", "requested_use", "record_sha256", "profile_sha256", "method", "predicted_status"]
MAPPING_LABELS = ["correct", "incorrect", "uncertain"]
ADMISSION_LABELS = ["admitted", "review_required", "rejected"]
PREDICTED = ADMISSION_LABELS + ["not_admitted"]  # binary baselines predict admitted / not_admitted
SPLITS = {"development", "test"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")

Unit = tuple[str, str]  # (case_id, requested_use)


def _read_csv(path: Path, required: list[str], optional: Sequence[str] = ()) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:  # tolerate Excel's BOM
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        missing = [c for c in required if c not in header]
        unknown = [c for c in header if c not in required and c not in optional]
        if missing or unknown:
            raise ValueError(f"{path}: missing columns {missing}, unknown columns {unknown}")
        return [dict(row) for row in reader]


def _iso(value: str, where: str) -> None:
    try:
        dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{where}: not an ISO 8601 time: {value!r}") from None


def _json_list(value: str, where: str) -> list:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        raise ValueError(f"{where}: not valid JSON: {value!r}") from None
    if not isinstance(parsed, list) or not all(isinstance(x, str) and x.strip() for x in parsed):
        raise ValueError(f"{where}: must be a JSON array of nonblank strings")
    return parsed


def load_annotations(path: Path) -> list[dict[str, str]]:
    """Read and strictly check an annotations CSV; raise ValueError listing the first problems."""
    rows = _read_csv(path, ANNOTATION_COLUMNS, OPTIONAL_ANNOTATION_COLUMNS)
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_reviews: set[tuple[str, str, str]] = set()
    bindings: dict[Unit, tuple[str, ...]] = {}
    for number, row in enumerate(rows, start=2):  # line 1 is the header
        where = f"{path}:{number}"
        blank = [c for c in ANNOTATION_COLUMNS
                 if c not in ("mapping_rationale", "admission_rationale") and not (row[c] or "").strip()]
        if blank:
            errors.append(f"{where}: blank {blank}")
            continue
        if row["annotation_id"] in seen_ids:
            errors.append(f"{where}: duplicate annotation_id {row['annotation_id']!r}")
        seen_ids.add(row["annotation_id"])
        review = (row["case_id"], row["requested_use"], row["reviewer_id"])
        if review in seen_reviews:
            errors.append(f"{where}: reviewer {row['reviewer_id']!r} labelled {review[:2]} twice")
        seen_reviews.add(review)
        if row["mapping_label"] not in MAPPING_LABELS:
            errors.append(f"{where}: mapping_label must be one of {MAPPING_LABELS}")
        if row["admission_label"] not in ADMISSION_LABELS:
            errors.append(f"{where}: admission_label must be one of {ADMISSION_LABELS}")
        if row["split"] not in SPLITS:
            errors.append(f"{where}: split must be one of {sorted(SPLITS)}")
        for column in ("record_sha256", "profile_sha256"):
            if not HEX64.match(row[column]):
                errors.append(f"{where}: {column} must be 64 lowercase hex characters")
        try:
            _iso(row["annotated_at"], where)
            _json_list(row["evidence_refs_json"], where)
        except ValueError as exc:
            errors.append(str(exc))
        binding = (row["record_sha256"], row["profile_sha256"], row["profile_id"], row["group_id"], row["split"])
        if bindings.setdefault(review[:2], binding) != binding:
            errors.append(f"{where}: reviewers of {review[:2]} saw a different record, profile, group or split")
    if errors:
        raise ValueError("Invalid annotations:\n" + "\n".join(errors[:20]))
    return rows


def load_adjudications(path: Path, annotations: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = _read_csv(path, ADJUDICATION_COLUMNS)
    by_id = {a["annotation_id"]: a for a in annotations}
    errors, units = [], set()
    for number, row in enumerate(rows, start=2):
        where = f"{path}:{number}"
        blank = [c for c in ADJUDICATION_COLUMNS if not (row[c] or "").strip()]
        if blank:
            errors.append(f"{where}: blank {blank}")
            continue
        unit = (row["case_id"], row["requested_use"])
        if unit in units:
            errors.append(f"{where}: {unit} adjudicated twice")
        units.add(unit)
        if row["mapping_label"] not in MAPPING_LABELS or row["admission_label"] not in ADMISSION_LABELS:
            errors.append(f"{where}: labels must be from {MAPPING_LABELS} and {ADMISSION_LABELS}")
        try:
            _iso(row["adjudicated_at"], where)
            _json_list(row["evidence_refs_json"], where)
            linked = _json_list(row["annotation_ids_json"], where)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        for annotation_id in linked:
            original = by_id.get(annotation_id)
            if original is None or (original["case_id"], original["requested_use"]) != unit:
                errors.append(f"{where}: {annotation_id!r} is not an annotation of {unit}")
            elif (original["record_sha256"], original["profile_sha256"]) != (row["record_sha256"], row["profile_sha256"]):
                errors.append(f"{where}: record or profile hash differs from annotation {annotation_id!r}")
    if errors:
        raise ValueError("Invalid adjudications:\n" + "\n".join(errors[:20]))
    return rows


def _units(annotations: list[dict[str, str]], field: str, use: str | None = None) -> dict[Unit, dict[str, str]]:
    units: dict[Unit, dict[str, str]] = defaultdict(dict)
    for row in annotations:
        if use is None or row["requested_use"] == use:
            units[(row["case_id"], row["requested_use"])][row["reviewer_id"]] = row[field]
    return units


def krippendorff_alpha_nominal(units: list[list[str]]) -> float | None:
    """Krippendorff's alpha for nominal data; units with fewer than two values are not pairable.

    Returns None when there is no variation to measure agreement against (expected disagreement is 0).
    """
    coincidence: dict[tuple[str, str], float] = defaultdict(float)
    for values in units:
        if len(values) < 2:
            continue
        for i, c in enumerate(values):
            for j, k in enumerate(values):
                if i != j:
                    coincidence[(c, k)] += 1 / (len(values) - 1)
    totals: dict[str, float] = defaultdict(float)
    for (c, _), weight in coincidence.items():
        totals[c] += weight
    n = sum(totals.values())
    observed = sum(w for (c, k), w in coincidence.items() if c != k)
    expected = (n * n - sum(t * t for t in totals.values())) / (n - 1) if n > 1 else 0.0
    return None if expected == 0 else 1 - observed / expected


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    first, second = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(first[c] * second[c] for c in set(first) | set(second)) / (n * n)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def wilson(events: int, n: int, z: float = 1.959963984540054) -> list[float] | None:
    if not n:
        return None
    p = events / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 6), round(min(1.0, centre + half), 6)]


def _bootstrap_alpha(units: list[list[str]], resamples: int, seed: int) -> list[float] | None:
    rng = random.Random(seed)
    values = []
    for _ in range(resamples):
        alpha = krippendorff_alpha_nominal([units[rng.randrange(len(units))] for _ in units])
        if alpha is not None:
            values.append(alpha)
    if len(values) < resamples * 0.9:
        return None  # too many resamples without variation for a meaningful interval
    values.sort()
    last = len(values) - 1
    return [round(values[int(0.025 * last)], 4), round(values[math.ceil(0.975 * last)], 4)]


def agreement(annotations: list[dict[str, str]], *, resamples: int = 2000, seed: int = 20260925) -> dict[str, Any]:
    """Inter-reviewer agreement per requested use, before adjudication."""
    reviewers = sorted({row["reviewer_id"] for row in annotations})
    result: dict[str, Any] = {"reviewers": reviewers, "uses": {}}
    for use in sorted({row["requested_use"] for row in annotations}):
        per_field = {}
        for field in ("admission_label", "mapping_label"):
            units = _units(annotations, field, use)
            multi = [list(v.values()) for v in units.values() if len(v) >= 2]
            alpha = krippendorff_alpha_nominal(multi)
            entry: dict[str, Any] = {
                "units": len(units), "units_with_2plus_reviews": len(multi),
                "percent_agreement": round(sum(len(set(v)) == 1 for v in multi) / len(multi), 4) if multi else None,
                "krippendorff_alpha": None if alpha is None else round(alpha, 4),
                "alpha_95_bootstrap": _bootstrap_alpha(multi, resamples, seed) if multi else None,
            }
            if len(reviewers) == 2:
                a, b = reviewers
                pairs = [(v[a], v[b]) for v in units.values() if a in v and b in v]
                kappa = cohen_kappa(pairs)
                entry["cohen_kappa"] = None if kappa is None else round(kappa, 4)
                entry["confusion"] = {f"{x}|{y}": n for (x, y), n in sorted(Counter(pairs).items())}
            per_field[field] = entry
        result["uses"][use] = per_field
    return result


def adjudication_sheet(annotations: list[dict[str, str]], *, min_reviewers: int = 2) -> tuple[list[dict], list[Unit]]:
    """Blank adjudication rows for every disagreement, plus units that still lack enough reviews."""
    grouped: dict[Unit, list[dict[str, str]]] = defaultdict(list)
    for row in annotations:
        grouped[(row["case_id"], row["requested_use"])].append(row)
    rows, incomplete = [], []
    for unit, reviews in sorted(grouped.items()):
        if len(reviews) < min_reviewers:
            incomplete.append(unit)
            continue
        if len({r["admission_label"] for r in reviews}) > 1 or len({r["mapping_label"] for r in reviews}) > 1:
            first = reviews[0]
            rows.append({"adjudication_id": f"adj:{unit[0]}:{unit[1]}", "case_id": unit[0],
                         "record_sha256": first["record_sha256"], "profile_sha256": first["profile_sha256"],
                         "requested_use": unit[1],
                         "annotation_ids_json": json.dumps(sorted(r["annotation_id"] for r in reviews)),
                         **{c: "" for c in ADJUDICATION_COLUMNS[6:]}})
    return rows, incomplete


def resolve(annotations: list[dict[str, str]], adjudications: list[dict[str, str]], *,
            min_reviewers: int = 2) -> dict[Unit, dict[str, str]]:
    """Final reference labels: unanimous reviews, or the adjudicated label where reviewers disagreed."""
    grouped: dict[Unit, list[dict[str, str]]] = defaultdict(list)
    for row in annotations:
        grouped[(row["case_id"], row["requested_use"])].append(row)
    decided = {(a["case_id"], a["requested_use"]): a for a in adjudications}
    final, problems = {}, []
    for unit, reviews in sorted(grouped.items()):
        first = reviews[0]
        base = {"record_sha256": first["record_sha256"], "profile_sha256": first["profile_sha256"],
                "split": first["split"], "group_id": first["group_id"], "reviews": str(len(reviews))}
        if unit in decided:
            final[unit] = {**base, "admission_label": decided[unit]["admission_label"],
                           "mapping_label": decided[unit]["mapping_label"], "resolution": "adjudicated"}
        elif len(reviews) < min_reviewers:
            problems.append(f"{unit}: {len(reviews)} review(s), {min_reviewers} required")
        elif len({r["admission_label"] for r in reviews}) == 1 and len({r["mapping_label"] for r in reviews}) == 1:
            final[unit] = {**base, "admission_label": first["admission_label"],
                           "mapping_label": first["mapping_label"], "resolution": "unanimous"}
        else:
            problems.append(f"{unit}: reviewers disagree and there is no adjudication")
    unknown = sorted(set(decided) - set(grouped))
    problems += [f"{unit}: adjudicated but never reviewed" for unit in unknown]
    if problems:
        raise ValueError("Unresolved reference labels:\n" + "\n".join(problems[:20]))
    return final


def load_predictions(path: Path) -> list[dict[str, str]]:
    rows = _read_csv(path, PREDICTION_COLUMNS, ["subset"])
    seen = set()
    for number, row in enumerate(rows, start=2):
        key = (row["case_id"], row["requested_use"], row["method"])
        if key in seen:
            raise ValueError(f"{path}:{number}: duplicate prediction for {key}")
        seen.add(key)
        if row["predicted_status"] not in PREDICTED:
            raise ValueError(f"{path}:{number}: predicted_status must be one of {PREDICTED}")
    return rows


def score(final: dict[Unit, dict[str, str]], predictions: list[dict[str, str]], *, split: str = "test") -> dict[str, Any]:
    """Compare predictions with reference labels on one split; hashes must match the reviewed records."""
    selected = {u: v for u, v in final.items() if v["split"] == split}
    if not selected:
        raise ValueError(f"No reference labels in split {split!r}")
    rows: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)  # (method, subset) -> (gold, predicted)
    for p in predictions:
        unit = (p["case_id"], p["requested_use"])
        if unit not in final:
            continue
        gold = final[unit]
        if (p["record_sha256"], p["profile_sha256"]) != (gold["record_sha256"], gold["profile_sha256"]):
            raise ValueError(f"{unit}: prediction was made on a different record or profile than was reviewed")
        if unit in selected:
            for subset in {"all", p.get("subset") or "all"}:
                rows[(p["method"], subset)].append((gold["admission_label"], p["predicted_status"]))
    predicted = {(p["method"], p["case_id"], p["requested_use"]) for p in predictions}
    missing = [(m, u) for m in sorted({p["method"] for p in predictions}) for u in sorted(selected)
               if (m, *u) not in predicted]
    if missing:
        raise ValueError(f"Missing predictions for {len(missing)} reviewed unit(s), e.g. {missing[0]}")
    report: dict[str, Any] = {"split": split, "reference_units": len(selected), "methods": {}}
    for (method, subset), pairs in sorted(rows.items()):
        positives = [p for g, p in pairs if g == "admitted"]
        negatives = [p for g, p in pairs if g != "admitted"]
        false_admissions = sum(p == "admitted" for p in negatives)
        false_blocks = sum(p != "admitted" for p in positives)
        report["methods"].setdefault(method, {})[subset] = {
            "n": len(pairs), "reference_admitted": len(positives), "reference_not_admitted": len(negatives),
            "false_admissions": false_admissions, "false_admission_rate_wilson_95": wilson(false_admissions, len(negatives)),
            "false_blocks": false_blocks, "false_block_rate_wilson_95": wilson(false_blocks, len(positives)),
            "admission_agreement": sum((g == "admitted") == (p == "admitted") for g, p in pairs),
            "exact_matches": sum(g == p for g, p in pairs),
            "confusion": {f"{g}|{p}": n for (g, p), n in sorted(Counter(pairs).items())},
        }
    return report


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze(manifest: dict[str, Any], final: dict[Unit, dict[str, str]], annotations: list[dict[str, str]],
           files: list[Path], *, dataset_id: str, version: str, frozen_at: str) -> dict[str, Any]:
    """Fill a manifest for a completed reference set. Hashes identify files; they do not prove review happened."""
    _iso(frozen_at, "frozen_at")
    reviewers = {row["reviewer_id"] for row in annotations}
    single = all(v["reviews"] == "1" for v in final.values())
    return {**manifest, "dataset_id": dataset_id, "version": version, "status": "frozen",
            "reference_type": "single-reviewer reference set" if single else "independently reviewed reference set",
            "reviewed_case_use_count": len(final), "independent_human_reviewer_count": len(reviewers),
            "resolution_counts": dict(sorted(Counter(v["resolution"] for v in final.values()).items())),
            "split_groups": sorted({v["group_id"] for v in final.values()}),
            "files": {Path(f).name: sha256_file(f) for f in files}, "frozen_at": frozen_at,
            "gold_standard_metrics_available": True}


def _fmt(value: Any) -> str:
    return "–" if value is None else str(value)


def render_agreement(report: dict[str, Any]) -> str:
    lines = [f"Reviewers: {', '.join(report['reviewers'])}", "",
             "| Use | Label | Units (2+ reviews) | % agreement | Krippendorff α (95% bootstrap) | Cohen κ |",
             "|---|---|---:|---:|---|---:|"]
    for use, fields in report["uses"].items():
        for field, e in fields.items():
            ci = e["alpha_95_bootstrap"]
            alpha = _fmt(e["krippendorff_alpha"]) + (f" ({ci[0]}–{ci[1]})" if ci else "")
            lines.append(f"| {use} | {field} | {e['units_with_2plus_reviews']} | {_fmt(e['percent_agreement'])} | "
                         f"{alpha} | {_fmt(e.get('cohen_kappa'))} |")
    return "\n".join(lines) + "\n"


def render_score(report: dict[str, Any]) -> str:
    lines = [f"Split: {report['split']} · reference units: {report['reference_units']}", "",
             "| Method | Subset | n | False admissions | False blocks | Admission agreement | Exact |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for method, subsets in report["methods"].items():
        for subset, m in subsets.items():
            lines.append(f"| {method} | {subset} | {m['n']} | {m['false_admissions']}/{m['reference_not_admitted']} | "
                         f"{m['false_blocks']}/{m['reference_admitted']} | {m['admission_agreement']}/{m['n']} | "
                         f"{m['exact_matches']}/{m['n']} |")
    return "\n".join(lines) + "\n"


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
