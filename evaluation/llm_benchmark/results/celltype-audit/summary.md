# Audit dry run: single-cell held-out annotations

**Not an expert audit.** The auditor is a stand-in: the dataset authors' cluster labels (not an expert). It shows what the audit procedure reports, and checks its statistics against a census.

| Route | Records | Share of records | Audited | Errors | Error rate | Wilson 95% | Upper bound (95%, one-sided) | Share of expert time |
|---|---:|---:|---:|---:|---:|---|---:|---:|
| auto-admitted | 255 | 92.4% | 59 | 14 | 23.7% | 14.7%–36.0% | 34.6% | – |
| rejected | 3 | 1.09% | 2 | 0 | 0.00% | 0.00%–65.8% | 77.6% | – |
| expert review | 18 | 6.52% | 8 | 1 | 12.5% | 2.24%–47.1% | 47.1% | – |

An error on the auto-admitted route is a record the reference says should not have been admitted, or whose claim is wrong. On another route, it is a record that could have been admitted as it was.

**14 error(s) in 59 audited auto-admitted records: the auto-admitted error rate is below 34.6% at 95% confidence**, at most 89 of 255 records.

## Against the census

The authors' labels cover every record, so here the error rate of the whole route is known:

| Route | Census error rate | Audit estimate | Wilson 95% | Upper bound (95%) | Census inside |
|---|---:|---:|---|---:|---|
| auto-admitted | 50/255 (19.6%) | 23.7% | 14.7%–36.0% | 34.6% | yes |
| rejected | 0/3 (0.0%) | 0.0% | 0.0%–65.8% | 77.6% | yes |
| expert review | 5/18 (27.8%) | 12.5% | 2.2%–47.1% | 47.1% | yes |

The audit was sized to show an auto-admitted error rate below 5% if none of 59 sampled records was wrong. It found 14, so this route does not meet a 5% target: the census rate is 19.6%. An audit is how a deployment would learn that these annotations need review, or a better model, before research summaries rely on them.

Seed 20261006; `sample/audit_manifest.json` holds the routes and stays with the maintainer. Expert time is not measured: the stand-in records none.
