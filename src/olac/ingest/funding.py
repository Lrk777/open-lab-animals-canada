"""Federal research funding (CIHR, NSERC) classified by research approach.

Privacy rule: researcher names are never written anywhere. Rows are reduced to
(funder, fiscal_year, institution, category, amount) immediately after reading.

Outputs (data/processed/):
  funding_by_category_year.csv          funder, fiscal_year, category, n_awards, amount_cad
  funding_by_institution_category.csv   funder, institution, category, n_awards, amount_cad (2019+)
data/interim/funding_precision_sample.csv  random matched titles for manual precision checks
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator

import openpyxl
import pandas as pd
import yaml

from olac.paths import CONFIG, INTERIM, PROCESSED, RAW

FUND = RAW / "funding"

CIHR_COLS = {
    "fy": "FiscalYear_AnneeFinanciere",
    "ref": "FundingReferenceNumber_NumeroReferenceFinancement",
    "inst": "InstitutionPaidNameEN_NomEtablissementPayeAN",
    "program_type": "ProgramTypeEN_TypeProgrammeAN",
    "amount": "AmountPaidFY_MontantPayeAF",
    "title": "ApplicationTitle_TitreDemande",
    "abstract": "ApplicationAbstract_ResumeDemande",
    "keywords": "ApplicationKeywords_MotsClesDemande",
}


def _lexicon() -> dict[str, dict[str, list[re.Pattern]]]:
    cfg = yaml.safe_load((CONFIG / "funding_lexicon.yaml").read_text())["categories"]
    return {
        k: {
            "include": [re.compile(p, re.I) for p in v["include"]],
            "exclude": [re.compile(p, re.I) for p in v.get("exclude", [])],
        }
        for k, v in cfg.items()
    }


def classify(text: str, lex) -> list[str]:
    cats = []
    for cat, pats in lex.items():
        if any(p.search(text) for p in pats["include"]) and not any(p.search(text) for p in pats["exclude"]):
            cats.append(cat)
    return cats


def _cihr_rows(path) -> Iterator[dict]:
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb["G&A_S&B"]
    it = ws.iter_rows(values_only=True)
    header = next(it)
    idx = {k: header.index(v) for k, v in CIHR_COLS.items()}
    for row in it:
        yield {k: row[i] for k, i in idx.items()}
    wb.close()


def load_cihr_raw() -> pd.DataFrame:
    """Project rows without any personal fields; cached because the XLSX files are slow to read."""
    cache = INTERIM / "cihr_projects.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    rows = []
    for path in sorted(FUND.glob("cihr_*.xlsx")):
        for r in _cihr_rows(path):
            if r["program_type"] and "Award" in str(r["program_type"]):
                continue  # personnel awards (scholarships) are not research projects
            rows.append(r)
        print(f"  {path.name}: {len(rows):,} project rows so far")
    df = pd.DataFrame(rows).drop(columns=["program_type"])
    df["fy"] = pd.to_numeric(df["fy"].astype(str).str[:4], errors="coerce").astype("Int64")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    for c in ("ref", "inst", "title", "abstract", "keywords"):
        df[c] = df[c].astype("string")
    df.to_parquet(cache, index=False)
    return df


def load_cihr(lex) -> pd.DataFrame:
    df = load_cihr_raw()
    text = df["title"].fillna("") + " " + df["keywords"].fillna("") + " " + df["abstract"].fillna("")
    df = df.assign(category=text.map(lambda t: classify(t, lex) or ["other"])).explode("category")
    return pd.DataFrame(
        {
            "funder": "CIHR",
            "fiscal_year": df["fy"],
            "award_ref": df["ref"],
            "institution": df["inst"],
            "category": df["category"],
            "amount_cad": df["amount"],
            "title": df["title"].where(df["category"] != "other"),
        }
    )


def _read_nserc(path) -> pd.DataFrame:
    """NSERC files mix UTF-8-with-BOM and Latin-1, and rename the keyword column between years."""
    raw = path.read_bytes()
    encoding = "utf-8-sig" if raw[:3] == b"\xef\xbb\xbf" else "latin1"
    df = pd.read_csv(path, encoding=encoding, low_memory=False, dtype=str)
    rename = {}
    for c in df.columns:
        key = c.strip().lower()
        if key == "applicationid":
            rename[c] = "app_id"
        elif key.startswith("institution-"):
            rename[c] = "institution"
        elif key.startswith("fiscalyear"):
            rename[c] = "fy"
        elif key == "awardamount":
            rename[c] = "amount"
        elif key == "groupen":
            rename[c] = "group"
        elif key == "applicationtitle":
            rename[c] = "title"
        elif key in ("keyword", "keywords"):
            rename[c] = "keywords"
        elif key == "applicationsummary":
            rename[c] = "summary"
    df = df.rename(columns=rename)
    if "keywords" not in df.columns:
        df["keywords"] = ""
    return df[["app_id", "institution", "fy", "amount", "group", "title", "keywords", "summary"]]


def load_nserc(lex) -> pd.DataFrame:
    out = []
    for path in sorted(FUND.glob("nserc_*.csv")):
        df = _read_nserc(path)
        df = df[~df["group"].fillna("").str.contains("SCHOLARSHIP|FELLOWSHIP", case=False)]
        text = df["title"].fillna("") + " " + df["keywords"].fillna("") + " " + df["summary"].fillna("")
        cats = text.map(lambda t: classify(t, lex) or ["other"])
        df = df.assign(category=cats).explode("category")
        out.append(
            pd.DataFrame(
                {
                    "funder": "NSERC",
                    "fiscal_year": pd.to_numeric(df["fy"], errors="coerce").astype("Int64"),
                    "award_ref": df["app_id"],
                    "institution": df["institution"],
                    "category": df["category"],
                    "amount_cad": pd.to_numeric(df["amount"], errors="coerce").fillna(0),
                    "title": df["title"].where(df["category"] != "other"),
                }
            )
        )
        print(f"  {path.name}: {len(df):,} research rows")
    return pd.concat(out, ignore_index=True)


def run(sample: bool = False) -> None:
    lex = _lexicon()
    print("CIHR...")
    cihr = load_cihr(lex)
    print("NSERC...")
    nserc = load_nserc(lex)
    df = pd.concat([cihr, nserc], ignore_index=True)

    by_year = df.groupby(["funder", "fiscal_year", "category"], as_index=False).agg(
        n_awards=("award_ref", "nunique"), amount_cad=("amount_cad", "sum")
    )
    by_year.to_csv(PROCESSED / "funding_by_category_year.csv", index=False)

    recent = df[df.fiscal_year >= 2019]
    by_inst = recent[recent.category != "other"].groupby(
        ["funder", "institution", "category"], as_index=False
    ).agg(n_awards=("award_ref", "nunique"), amount_cad=("amount_cad", "sum"))
    by_inst.to_csv(PROCESSED / "funding_by_institution_category.csv", index=False)

    matched = df[df.category != "other"][["funder", "fiscal_year", "category", "title"]].drop_duplicates()
    s = pd.concat(
        [g.sample(min(len(g), 40), random_state=7) for _, g in matched.groupby("category")],
        ignore_index=True,
    )
    s.assign(is_correct="").to_csv(INTERIM / "funding_precision_sample.csv", index=False)

    piv = by_year.pivot_table(index="fiscal_year", columns=["category"], values="amount_cad", aggfunc="sum") / 1e6
    print(piv.round(1).to_string())
    if sample:
        print(s.head(30).to_string())


if __name__ == "__main__":
    run(sample="--sample" in sys.argv)
