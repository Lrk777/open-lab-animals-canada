"""Gold-set sampling and labelling worksheets.

  python -m olac.audit.gold sample --n 80      stratified by publication period, seed fixed
  python -m olac.audit.gold sheet  --annotator A   blank worksheet for one annotator

Worksheet columns: pmcid, field, question, reported (TRUE/FALSE), value, evidence, notes.
Annotators label independently; never look at model output before labelling.
"""

from __future__ import annotations

import argparse

import pandas as pd

from olac.audit.extract import included_papers
from olac.audit.schema import FIELDS
from olac.paths import DATA

GOLD = DATA / "gold"


def sample(n: int = 80, seed: int = 2020) -> pd.DataFrame:
    p = included_papers().copy()
    p["period"] = pd.cut(p.year, [2009, 2015, 2019, 2022, 2026], labels=["2010-15", "2016-19", "2020-22", "2023-26"])
    per = max(1, n // p.period.nunique())
    s = pd.concat([g.sample(min(len(g), per), random_state=seed) for _, g in p.groupby("period", observed=True)])
    if len(s) < n:
        rest = p[~p.pmcid.isin(s.pmcid)].sample(n - len(s), random_state=seed)
        s = pd.concat([s, rest])
    s = s.sample(frac=1, random_state=seed)[["pmcid", "year", "period", "journal", "title", "doi"]]
    GOLD.mkdir(parents=True, exist_ok=True)
    s.to_csv(GOLD / "sample.csv", index=False)
    print(s.period.value_counts().sort_index().to_string())
    return s


def sheet(annotator: str) -> None:
    s = pd.read_csv(GOLD / "sample.csv")
    rows = [
        {"pmcid": pid, "field": k, "question": v["question"], "reported": "", "value": "", "evidence": "", "notes": ""}
        for pid in s.pmcid
        for k, v in FIELDS.items()
    ]
    out = GOLD / f"labels_{annotator}.csv"
    if out.exists():
        raise SystemExit(f"{out} exists; refusing to overwrite labels")
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"wrote {out} ({len(rows)} cells)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("sample")
    a.add_argument("--n", type=int, default=80)
    b = sub.add_parser("sheet")
    b.add_argument("--annotator", required=True)
    args = ap.parse_args()
    sample(args.n) if args.cmd == "sample" else sheet(args.annotator)
