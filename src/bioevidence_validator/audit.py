"""Audit sampling: measure the error of what an automated route lets through.

Routing sends each record one way: admitted automatically, to an expert, or rejected. Experts decide every
routed record, so the error nobody sees is the error of what was admitted. An audit measures it: experts label a
seeded random sample of admitted records with the usual annotation protocol (docs/GOLD_STANDARD.md). A few
records from the other routes can be mixed in, in shuffled order, so that auditors cannot tell which route a record
took. Each route's error rate is then reported with an exact one-sided upper bound: 0 errors in 299 audited
admitted records bounds the admitted error rate below 1% at 95% confidence.

`audit_sample` returns the auditors' sheet (blank annotation rows) and a manifest. The manifest holds the seed,
each route's population and the route each sampled record took. **Keep the manifest from the auditors:** it
unblinds them. `audit_score` reads the manifest and the resolved labels.

An admitted record is an error when the reference says it should not have been admitted for the use
(`admission_label` review_required or rejected) or that its claim is wrong (`mapping_label` incorrect). A record
from another route is an error when the reference says it could have been admitted as it was (admitted and
correct): expert time spent for nothing, or a good record blocked.
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from typing import Any

from . import __version__
from .review import ANNOTATION_COLUMNS, Unit, wilson

ROUTES = {"admitted": "auto-admitted", "review_required": "expert review", "rejected": "rejected",
          "not_admitted": "not admitted"}
EXPERT_ROUTES = {"review_required"}  # every record on these routes is decided by an expert


def _log_binomial_cdf(errors: int, n: int, p: float) -> float:
    """log P(X <= errors) for X ~ Binomial(n, p), 0 < p < 1."""
    terms = [math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * math.log(p)
             + (n - k) * math.log1p(-p) for k in range(errors + 1)]
    top = max(terms)
    return top + math.log(sum(math.exp(t - top) for t in terms))


def upper_bound(errors: int, n: int, confidence: float = 0.95) -> float | None:
    """Exact (Clopper-Pearson) one-sided upper bound on the error rate after `errors` errors in `n` audited records.

    Sampling without replacement from a finite route makes the true bound a little lower; this one is conservative.
    """
    if n <= 0:
        return None
    if not 0 <= errors <= n or not 0 < confidence < 1:
        raise ValueError("need 0 <= errors <= n and 0 < confidence < 1")
    if errors == n:
        return 1.0
    low, high, alpha = errors / n, 1.0, math.log(1 - confidence)
    for _ in range(60):  # bisection: P(X <= errors) falls as the rate rises
        middle = (low + high) / 2
        if _log_binomial_cdf(errors, n, middle) > alpha:
            low = middle
        else:
            high = middle
    return math.ceil(high * 1e6) / 1e6  # rounded up, never below the exact bound


def sample_size(target: float, confidence: float = 0.95, errors: int = 0) -> int:
    """The smallest audit that bounds the error rate below `target` if it finds at most `errors` errors."""
    if not 0 < target < 1:
        raise ValueError("target must be between 0 and 1")

    def enough(n: int) -> bool:
        return n > errors and (upper_bound(errors, n, confidence) or 1.0) < target

    high = errors + 1
    while not enough(high):
        high *= 2
        if high > 100_000_000:
            raise ValueError("target too small to audit")
    low = high // 2
    while high - low > 1:
        middle = (low + high) // 2
        if enough(middle):
            high = middle
        else:
            low = middle
    return high


def audit_sample(predictions: list[dict[str, str]], *, method: str, use: str, size: int, seed: int,
                 profile_id: str, controls: int = 0, split: str = "test", confidence: float = 0.95,
                 predictions_sha256: str = "") -> tuple[list[dict[str, str]], dict[str, Any]]:
    """(auditors' sheet, manifest): a seeded random sample of one method's admitted records for one use, with
    `controls` records from its other routes mixed in."""
    rows = sorted((p for p in predictions if p["method"] == method and p["requested_use"] == use),
                  key=lambda p: p["case_id"])
    if not rows:
        raise ValueError(f"No predictions for method {method!r} and use {use!r}")
    admitted = [p for p in rows if p["predicted_status"] == "admitted"]
    others = [p for p in rows if p["predicted_status"] != "admitted"]
    if size <= 0 or not admitted:
        raise ValueError("Nothing to audit: the sample size must be positive and some records admitted")
    rng = random.Random(seed)
    chosen = rng.sample(admitted, min(size, len(admitted))) + rng.sample(others, min(max(controls, 0), len(others)))
    rng.shuffle(chosen)
    sheet = [{**dict.fromkeys(ANNOTATION_COLUMNS, ""), "case_id": p["case_id"], "record_sha256": p["record_sha256"],
              "profile_id": profile_id, "profile_sha256": p["profile_sha256"], "requested_use": use,
              "group_id": p["case_id"], "split": split, "evidence_refs_json": "[]"} for p in chosen]
    audited = min(size, len(admitted))
    manifest = {
        "audit": "bioevidence audit sample: keep from the auditors", "validator_version": __version__,
        "method": method, "requested_use": use, "profile_id": profile_id, "seed": seed,
        "predictions_sha256": predictions_sha256,
        "population": dict(sorted(Counter(p["predicted_status"] for p in rows).items())),
        "sample": {"admitted": audited, "controls": len(chosen) - audited},
        "confidence": confidence, "if_no_errors_admitted_error_below": upper_bound(0, audited, confidence),
        "sampled": {p["case_id"]: {"route": p["predicted_status"], "record_sha256": p["record_sha256"],
                                   "profile_sha256": p["profile_sha256"]} for p in sorted(chosen, key=lambda p: p["case_id"])},
    }
    return sheet, manifest


def _is_error(route: str, label: dict[str, str]) -> bool:
    if route == "admitted":
        return label["admission_label"] != "admitted" or label["mapping_label"] == "incorrect"
    return label["admission_label"] == "admitted" and label["mapping_label"] == "correct"


def audit_score(manifest: dict[str, Any], final: dict[Unit, dict[str, str]],
                annotations: list[dict[str, str]] | None = None, *, confidence: float = 0.95) -> dict[str, Any]:
    """Per route: share of records, audited records, errors, error rate with Wilson and exact one-sided bounds, and
    expert time when the annotations record `minutes_spent`.

    Expert time per route is estimated as: on expert routes, the mean audited minutes per record times the route's
    records (an expert decides each one); on other routes, the audit's own minutes (experts see only the sample).
    """
    use, sampled, population = manifest["requested_use"], manifest["sampled"], manifest["population"]
    stray = sorted({u for u in final if u[1] == use and u[0] not in sampled})
    if stray:
        raise ValueError(f"{len(stray)} labelled record(s) were not in the audit sample, e.g. {stray[0]}")
    total = sum(population.values())
    minutes: defaultdict[str, float] = defaultdict(float)
    timed: Counter[str] = Counter()
    for row in annotations or []:
        case = sampled.get(row["case_id"])
        recorded = (row.get("minutes_spent") or "").strip()
        if case and row["requested_use"] == use and recorded:
            try:
                minutes[case["route"]] += float(recorded)
            except ValueError:
                raise ValueError(f"{row['case_id']}: minutes_spent must be a number, not {recorded!r}") from None
            timed[case["route"]] += 1
    routes: dict[str, dict[str, Any]] = {}
    pending = []
    for case_id, case in sorted(sampled.items()):
        label = final.get((case_id, use))
        if label is None:
            pending.append(case_id)
            continue
        if (label["record_sha256"], label["profile_sha256"]) != (case["record_sha256"], case["profile_sha256"]):
            raise ValueError(f"{case_id}: the audited record or profile differs from the sampled one")
        stats = routes.setdefault(case["route"], {"audited": 0, "errors": 0, "uncertain": 0})
        stats["audited"] += 1
        stats["errors"] += _is_error(case["route"], label)
        stats["uncertain"] += label["mapping_label"] == "uncertain"
    workload: dict[str, float | None] = {}
    for route, stats in routes.items():
        n, errors, size = stats["audited"], stats["errors"], population.get(route, 0)
        bound = upper_bound(errors, n, confidence)
        stats.update(route_name=ROUTES.get(route, route), population=size,
                     share_of_records=round(size / total, 4) if total else None,
                     error_rate=round(errors / n, 4), error_rate_wilson_95=wilson(errors, n),
                     error_rate_upper_bound=bound,
                     errors_in_route_at_most=math.ceil(round(bound * size, 6)) if bound is not None else None,
                     audit_minutes=round(minutes[route], 1) if timed[route] else None)
        if route in EXPERT_ROUTES:
            workload[route] = minutes[route] / timed[route] * size if timed[route] else None
        else:
            workload[route] = minutes[route] if minutes else None
    known = [w for w in workload.values() if w is not None]
    spent = sum(known) if known and len(known) == len(workload) else None
    for route, stats in routes.items():
        estimate = workload[route]
        stats["expert_minutes_estimated"] = round(estimate, 1) if estimate is not None else None
        stats["share_of_expert_time"] = round(estimate / spent, 4) if spent and estimate is not None else None
    admitted = routes.get("admitted", {})
    return {"method": manifest["method"], "requested_use": use, "confidence": confidence, "seed": manifest["seed"],
            "population": population, "routes": dict(sorted(routes.items())), "not_yet_audited": pending,
            "admitted_error_upper_bound": admitted.get("error_rate_upper_bound"),
            "expert_minutes_estimated": round(spent, 1) if spent is not None else None}


def render_audit(report: dict[str, Any]) -> str:
    def pct(value: float | None) -> str:  # two decimals under 10%, where a bound such as 0.997% matters
        return "–" if value is None else f"{100 * value:.{2 if value < 0.1 else 1}f}%"

    level = f"{100 * report['confidence']:g}%"
    lines = [f"# Audit of `{report['method']}` for {report['requested_use']}", "",
             f"| Route | Records | Share of records | Audited | Errors | Error rate | Wilson 95% | Upper bound "
             f"({level}, one-sided) | Share of expert time |",
             "|---|---:|---:|---:|---:|---:|---|---:|---:|"]
    for s in report["routes"].values():
        low_high = s["error_rate_wilson_95"]
        interval = "–" if low_high is None else f"{pct(low_high[0])}–{pct(low_high[1])}"
        lines.append(f"| {s['route_name']} | {s['population']} | {pct(s['share_of_records'])} | {s['audited']} | "
                     f"{s['errors']} | {pct(s['error_rate'])} | {interval} | {pct(s['error_rate_upper_bound'])} | "
                     f"{pct(s['share_of_expert_time'])} |")
    lines += ["", "An error on the auto-admitted route is a record the reference says should not have been admitted, "
              "or whose claim is wrong. On another route, it is a record that could have been admitted as it was."]
    if report["admitted_error_upper_bound"] is not None:
        s = report["routes"]["admitted"]
        lines += ["", f"**{s['errors']} error(s) in {s['audited']} audited auto-admitted records: the auto-admitted "
                  f"error rate is below {pct(report['admitted_error_upper_bound'])} at {level} confidence**, at most "
                  f"{s['errors_in_route_at_most']} of {s['population']} records."]
    if report["not_yet_audited"]:
        lines += ["", f"{len(report['not_yet_audited'])} sampled record(s) are not yet audited and are left out."]
    if report["expert_minutes_estimated"] is not None:
        lines += ["", f"Expert time, estimated from the recorded minutes: {report['expert_minutes_estimated']} minutes. "
                  "Expert routes count every record at the audited mean; other routes count only the audit."]
    return "\n".join(lines) + "\n"
