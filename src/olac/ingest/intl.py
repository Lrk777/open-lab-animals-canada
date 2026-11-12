"""Comparison data: UK Home Office, USDA APHIS, EU (ALURES / Commission reports).

Outputs (data/processed/):
  uk_first_use.csv     year, animal_group, species, purpose, n_animals   (Table 1.3)
  uk_severity.csv      year, species, severity, n_procedures             (Table 3.1, primates)
  us_aphis_nhp.csv     fiscal_year, col_b_held, col_c_no_pain, col_d_pain_relieved, col_e_pain_not_relieved, total
  eu_nhp.csv           year, species, n_first_use, source
  nhp_comparison.csv   jurisdiction, year, nhp, measure, per_million
"""

from __future__ import annotations

import re
import zipfile

import pandas as pd
import yaml
from lxml import etree
from pypdf import PdfReader

from olac.paths import CONFIG, PROCESSED, RAW

INTL = RAW / "intl"
_T = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
_O = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"


def ods_tables(path, wanted: set[str]) -> dict[str, list[list[str]]]:
    """Minimal streaming ODS reader; odfpy is far too slow for the 1.9 MB Home Office file."""
    root = etree.fromstring(zipfile.ZipFile(path).read("content.xml"))
    out: dict[str, list[list[str]]] = {}
    for tb in root.iter(_T + "table"):
        name = tb.get(_T + "name")
        if name not in wanted:
            continue
        rows = []
        for r in tb.iter(_T + "table-row"):
            cells: list[str] = []
            for c in r:
                if c.tag not in (_T + "table-cell", _T + "covered-table-cell"):
                    continue
                n = min(int(c.get(_T + "number-columns-repeated", "1")), 64)
                v = c.get(_O + "value") or "".join(c.itertext()).strip()
                cells.extend([v] * n)
            while cells and cells[-1] == "":
                cells.pop()
            if cells:
                rows.append(cells)
        out[name] = rows
    return out


def _frame(rows: list[list[str]], first_col: str) -> pd.DataFrame:
    h = next(i for i, r in enumerate(rows) if r and r[0] == first_col)
    width = len(rows[h])
    body = [r + [""] * (width - len(r)) for r in rows[h + 1 :]]
    return pd.DataFrame([r[:width] for r in body], columns=rows[h])


def parse_uk() -> tuple[pd.DataFrame, pd.DataFrame]:
    t = ods_tables(INTL / "uk_2025_tables.ods", {"Table_1_3", "Table_3_1"})

    df = _frame(t["Table_1_3"], "Year")
    purpose_cols = [c for c in df.columns if c.startswith("Experimental purpose")] + [
        "Creation & breeding of GA animals not used in experimental procedures",
        "Total animals used for the first time in procedures",
    ]
    long = df.melt(
        id_vars=["Year", "Animal Group", "Species of animal"],
        value_vars=purpose_cols,
        var_name="purpose",
        value_name="n_animals",
    )
    long["purpose"] = long.purpose.str.replace(
        "Experimental purpose of procedure (excluding creation & breeding): ", "", regex=False
    )
    long = long.rename(columns={"Year": "year", "Animal Group": "animal_group", "Species of animal": "species"})
    long["year"] = pd.to_numeric(long.year, errors="coerce")
    long["n_animals"] = pd.to_numeric(long.n_animals, errors="coerce")
    long = long.dropna(subset=["year"]).astype({"year": int})

    sev = _frame(t["Table_3_1"], "Year")
    sev = sev[sev["Animal Group"].eq("Primate") & ~sev["Actual Severity"].str.startswith("Total")]
    sev = sev.rename(
        columns={
            "Year": "year",
            "Species of animal": "species",
            "Actual Severity": "severity",
            "Total procedures": "n_procedures",
            "Basic Research": "basic_research",
            "Regulatory": "regulatory",
        }
    )
    sev["severity"] = sev.severity.str.lower().str.replace(r"[\s-]+", "-", regex=True)
    sev = sev[["year", "species", "severity", "basic_research", "regulatory", "n_procedures"]]
    for c in ("year", "basic_research", "regulatory", "n_procedures"):
        sev[c] = pd.to_numeric(sev[c], errors="coerce")
    return long, sev.dropna(subset=["year"]).astype({"year": int})


_US_ROW = re.compile(r"Non-?\s?Human Primates\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", re.I)


def parse_us() -> pd.DataFrame:
    rows = []
    for path in sorted(INTL.glob("usda_fy*.pdf")):
        fy = int(re.search(r"fy(\d{4})", path.name).group(1))
        text = "\n".join((p.extract_text() or "") for p in PdfReader(path).pages[:2])
        m = _US_ROW.search(text)
        if not m:
            print(f"[warn] no NHP row in {path.name}")
            continue
        b, c, d, e, total = map(int, m.groups())
        if b + c + d + e != total:
            print(f"[warn] FY{fy} NHP columns do not sum to total")
        rows.append(
            {
                "fiscal_year": fy,
                "col_b_held": b,
                "col_c_no_pain": c,
                "col_d_pain_relieved": d,
                "col_e_pain_not_relieved": e,
                "total": total,
                "used": c + d + e,
            }
        )
    return pd.DataFrame(rows)


def build_comparison(uk: pd.DataFrame, us: pd.DataFrame, eu: pd.DataFrame) -> pd.DataFrame:
    juris = yaml.safe_load((CONFIG / "jurisdictions.yaml").read_text())
    ca = pd.read_csv(PROCESSED / "ccac_type_year.csv")
    ca = ca[ca.animal_type == "Nonhuman primates"][["year", "n_animals"]]

    uk_nhp = (
        uk[(uk.animal_group == "Primate") & (uk.purpose == "Total animals used for the first time in procedures")]
        .groupby("year", as_index=False)
        .n_animals.sum()
    )
    frames = [
        ca.assign(jurisdiction="canada", measure="animals used (CCAC)").rename(columns={"n_animals": "nhp"}),
        uk_nhp.assign(jurisdiction="uk", measure="animals used for the first time").rename(
            columns={"n_animals": "nhp"}
        ),
        us.rename(columns={"fiscal_year": "year", "used": "nhp"})[["year", "nhp"]].assign(
            jurisdiction="us", measure="animals used, columns C-E (excludes held-not-used)"
        ),
        eu.groupby("year", as_index=False)
        .n_first_use.sum()
        .rename(columns={"n_first_use": "nhp"})
        .assign(jurisdiction="eu", measure="animals used for the first time"),
    ]
    out = pd.concat(frames, ignore_index=True)
    out["population_m"] = out.jurisdiction.map({k: v["population_m"] for k, v in juris.items()})
    out["per_million"] = (out.nhp / out.population_m).round(1)
    return out[["jurisdiction", "year", "nhp", "measure", "population_m", "per_million"]]


def run() -> None:
    uk, uk_sev = parse_uk()
    us = parse_us()
    eu = pd.read_csv(CONFIG / "eu_nhp.csv")
    uk.to_csv(PROCESSED / "uk_first_use.csv", index=False)
    uk_sev.to_csv(PROCESSED / "uk_primate_severity.csv", index=False)
    us.to_csv(PROCESSED / "us_aphis_nhp.csv", index=False)
    eu.to_csv(PROCESSED / "eu_nhp.csv", index=False)
    comp = build_comparison(uk, us, eu)
    comp.to_csv(PROCESSED / "nhp_comparison.csv", index=False)
    print(comp.pivot(index="year", columns="jurisdiction", values="per_million").to_string())


if __name__ == "__main__":
    run()
