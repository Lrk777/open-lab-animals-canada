"""Run an extraction backend over the corpus.

  python -m olac.audit.extract --backend rules
  python -m olac.audit.extract --backend llm --model gpt-4o-mini [--only-gold]

Output: data/processed/audit_<backend>.csv  (one row per paper x field)
"""

from __future__ import annotations

import argparse
import json

import pandas as pd

from olac.audit import rules
from olac.audit.corpus import FULLTEXT
from olac.audit.schema import FIELDS, PaperAudit
from olac.paths import DATA, PROCESSED

GOLD = DATA / "gold"


def paper_text(pmcid: str) -> str:
    doc = json.loads((FULLTEXT / f"{pmcid}.json").read_text())
    return doc.get("methods") or doc.get("body", "")


def to_rows(a: PaperAudit) -> list[dict]:
    return [
        {
            "pmcid": a.pmcid,
            "backend": a.backend,
            "field": k,
            "group": FIELDS[k]["group"],
            "reported": f.reported,
            "value": f.value,
            "evidence": f.evidence,
            "confidence": f.confidence,
        }
        for k, f in a.findings.items()
    ]


def included_papers() -> pd.DataFrame:
    c = pd.read_csv(PROCESSED / "corpus.csv")
    return c[c.uses_nhp & c.has_methods]


def run(backend: str, model: str | None = None, only_gold: bool = False) -> pd.DataFrame:
    papers = included_papers()
    if only_gold:
        ids = set(pd.read_csv(GOLD / "sample.csv").pmcid)
        papers = papers[papers.pmcid.isin(ids)]
    rows = []
    if backend == "rules":
        for pmcid in papers.pmcid:
            rows += to_rows(rules.extract(pmcid, paper_text(pmcid)))
        name = "rules"
    else:
        from olac.audit import llm

        for i, pmcid in enumerate(papers.pmcid):
            try:
                rows += to_rows(llm.extract(pmcid, paper_text(pmcid), model=model))
            except Exception as exc:  # noqa: BLE001
                print(f"[warn] {pmcid}: {exc}")
            if i % 20 == 0:
                print(f"  {i}/{len(papers)}")
        name = f"llm_{(model or 'default').replace('/', '_')}"
    df = pd.DataFrame(rows)
    df.to_csv(PROCESSED / f"audit_{name}.csv", index=False)
    rates = df.groupby("field").reported.mean().sort_values()
    print(f"{df.pmcid.nunique()} papers audited with {name}. Disclosure rates:")
    print(rates.round(2).to_string())
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["rules", "llm"], default="rules")
    ap.add_argument("--model", default=None)
    ap.add_argument("--only-gold", action="store_true")
    a = ap.parse_args()
    run(a.backend, a.model, a.only_gold)
