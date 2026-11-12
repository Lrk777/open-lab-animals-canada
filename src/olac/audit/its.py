"""Interrupted time series: did reporting change after ARRIVE 2.0 (published July 2020)?

Model per field (paper-level logistic regression, cluster-robust by journal):
    reported ~ time + post + time_since_2020
where time = year - 2010, post = 1 for papers published 2021 onward (2020 is a washout year
because ARRIVE 2.0 appeared mid-year), and time_since_2020 = max(0, year - 2020).
`post` is the immediate level change; `time_since_2020` is the change in slope.

Output: data/processed/its_results.csv, data/processed/disclosure_by_year.csv
"""

from __future__ import annotations

import sys
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from olac.paths import PROCESSED

warnings.filterwarnings("ignore")


def run(backend_file: str = "audit_rules.csv") -> pd.DataFrame:
    a = pd.read_csv(PROCESSED / backend_file)
    c = pd.read_csv(PROCESSED / "corpus.csv")[["pmcid", "year", "journal"]]
    d = a.merge(c, on="pmcid")
    d = d[d.year != 2020].copy()
    d["y"] = d.reported.astype(int)
    d["time"] = d.year - 2010
    d["post"] = (d.year >= 2021).astype(int)
    d["time_since"] = np.maximum(0, d.year - 2020)
    d["journal"] = d.journal.fillna("unknown")

    by_year = d.groupby(["field", "year"]).y.agg(["mean", "size"]).reset_index()
    by_year.to_csv(PROCESSED / "disclosure_by_year.csv", index=False)

    rows = []
    for f, g in d.groupby("field"):
        pre, post = g[g.post == 0].y.mean(), g[g.post == 1].y.mean()
        row = {"field": f, "n_papers": len(g), "rate_pre": pre, "rate_post": post}
        if 0 < g.y.mean() < 1 and g.post.nunique() == 2:
            try:
                groups = pd.factorize(g.journal)[0]
                res = smf.logit("y ~ time + post + time_since", data=g).fit(
                    disp=False, cov_type="cluster", cov_kwds={"groups": groups}
                )
                row.update(
                    {
                        "or_level_change": float(np.exp(res.params["post"])),
                        "p_level_change": float(res.pvalues["post"]),
                        "or_slope_change": float(np.exp(res.params["time_since"])),
                        "p_slope_change": float(res.pvalues["time_since"]),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                row["note"] = f"model failed: {type(exc).__name__}"
        rows.append(row)
    out = pd.DataFrame(rows).sort_values("rate_post")
    # Holm correction across fields for the level-change test.
    if "p_level_change" in out:
        p = out.p_level_change.fillna(1).values
        order = np.argsort(p)
        adj = np.empty_like(p)
        running = 0.0
        for rank, i in enumerate(order):
            running = max(running, min(1.0, (len(p) - rank) * p[i]))
            adj[i] = running
        out["p_level_holm"] = adj
    out.to_csv(PROCESSED / "its_results.csv", index=False)
    print(out.round(3).to_string(index=False))
    return out


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "audit_rules.csv")
