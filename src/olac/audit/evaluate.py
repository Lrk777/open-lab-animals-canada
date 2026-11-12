"""Evaluate extraction backends against the human gold set.

Gold = data/gold/labels_A.csv (primary annotator). If labels_B.csv exists, inter-annotator
agreement (Cohen's kappa) is reported per field and disagreements are written out for
adjudication; adjudicated labels in labels_adjudicated.csv take precedence over A.

Outputs:
  data/processed/eval_by_field.csv       backend x field: precision, recall, F1, support, kappa vs gold
  data/processed/eval_summary.csv        backend: macro F1, micro F1, n papers
  data/processed/eval_calibration.csv    LLM confidence bins vs observed accuracy
  data/processed/annotator_agreement.csv field: kappa(A,B), percent agreement
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score, precision_recall_fscore_support

from olac.paths import DATA, PROCESSED

GOLD = DATA / "gold"
TRUE = {"true", "1", "yes", "y", "t"}


def _labels(path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str).fillna("")
    df = df[df.reported.str.strip() != ""]
    df["reported"] = df.reported.str.strip().str.lower().isin(TRUE)
    return df[["pmcid", "field", "reported"]]


def gold() -> pd.DataFrame:
    a = _labels(GOLD / "labels_A.csv")
    adj = GOLD / "labels_adjudicated.csv"
    if adj.exists():
        a = pd.concat([_labels(adj), a]).drop_duplicates(["pmcid", "field"], keep="first")
    return a


def agreement() -> pd.DataFrame | None:
    if not (GOLD / "labels_B.csv").exists():
        return None
    a, b = _labels(GOLD / "labels_A.csv"), _labels(GOLD / "labels_B.csv")
    m = a.merge(b, on=["pmcid", "field"], suffixes=("_a", "_b"))
    rows = []
    for f, g in m.groupby("field"):
        k = cohen_kappa_score(g.reported_a, g.reported_b) if g.reported_a.nunique() + g.reported_b.nunique() > 2 else np.nan
        rows.append({"field": f, "n": len(g), "kappa": k, "pct_agree": (g.reported_a == g.reported_b).mean()})
    m[m.reported_a != m.reported_b].to_csv(GOLD / "disagreements.csv", index=False)
    out = pd.DataFrame(rows)
    out.to_csv(PROCESSED / "annotator_agreement.csv", index=False)
    return out


def evaluate() -> pd.DataFrame:
    g = gold()
    preds = sorted(PROCESSED.glob("audit_*.csv"))
    by_field, summary, calib = [], [], []
    for path in preds:
        p = pd.read_csv(path)
        backend = p.backend.iloc[0]
        m = g.merge(p[["pmcid", "field", "reported", "confidence"]], on=["pmcid", "field"], suffixes=("_gold", "_pred"))
        if m.empty:
            continue
        for f, d in m.groupby("field"):
            pr, rc, f1, _ = precision_recall_fscore_support(
                d.reported_gold, d.reported_pred, average="binary", zero_division=0
            )
            kappa = cohen_kappa_score(d.reported_gold, d.reported_pred) if d.reported_gold.nunique() > 1 else np.nan
            by_field.append({"backend": backend, "field": f, "precision": pr, "recall": rc, "f1": f1,
                             "support_pos": int(d.reported_gold.sum()), "n": len(d), "kappa_vs_gold": kappa})
        pr, rc, f1, _ = precision_recall_fscore_support(m.reported_gold, m.reported_pred, average="binary", zero_division=0)
        bf = pd.DataFrame([r for r in by_field if r["backend"] == backend])
        summary.append({"backend": backend, "n_papers": m.pmcid.nunique(), "micro_precision": pr,
                        "micro_recall": rc, "micro_f1": f1, "macro_f1": bf.f1.mean()})
        if m.confidence.notna().any():
            m["correct"] = m.reported_gold == m.reported_pred
            m["conf_bin"] = pd.cut(m.confidence, [0, .5, .7, .8, .9, .95, 1.0], include_lowest=True)
            c = m.groupby("conf_bin", observed=True).agg(n=("correct", "size"), accuracy=("correct", "mean"),
                                                         mean_conf=("confidence", "mean")).reset_index()
            c["backend"] = backend
            c["conf_bin"] = c.conf_bin.astype(str)
            calib.append(c)
    pd.DataFrame(by_field).to_csv(PROCESSED / "eval_by_field.csv", index=False)
    s = pd.DataFrame(summary)
    s.to_csv(PROCESSED / "eval_summary.csv", index=False)
    if calib:
        pd.concat(calib).to_csv(PROCESSED / "eval_calibration.csv", index=False)
    return s


def run() -> None:
    if not (GOLD / "labels_A.csv").exists():
        raise SystemExit(
            "No gold labels yet. Run `python -m olac.audit.gold sample` then "
            "`python -m olac.audit.gold sheet --annotator A`, label it, and re-run."
        )
    ag = agreement()
    if ag is not None:
        print("Inter-annotator agreement:\n", ag.round(2).to_string(index=False))
    print(evaluate().round(3).to_string(index=False))


if __name__ == "__main__":
    run()
