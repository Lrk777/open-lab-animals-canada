"""Parse CCAC Animal Data Reports into tidy tables.

Two source families:
  * Summary PDFs (2011-present): national totals by animal type, category of invasiveness (CI)
    and purpose of animal use (PAU).
  * Sortable Excel files (2019-present): File 1 = animals by species; File 2 = species x CI x PAU.

Outputs (data/processed/):
  ccac_type_year.csv       year, animal_type, n_animals, source
  ccac_ci_year.csv         year, ci, n_animals
  ccac_pau_year.csv        year, pau, n_animals
  ccac_species_year.csv    year, animal_type, species, scientific_name, n_animals
  ccac_species_ci_pau.csv  year, animal_type, species, scientific_name, ci, pau, n_animals
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

from olac.paths import INTERIM, PROCESSED, RAW

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

CCAC = RAW / "ccac"

ANIMAL_TYPES = {
    "amphibians": "Amphibians",
    "birds": "Birds",
    "cats": "Cats",
    "cattle": "Cattle",
    "dogs": "Dogs",
    "fish": "Fish",
    "guinea pigs": "Guinea pigs",
    "mice": "Mice",
    "nonhuman primates": "Nonhuman primates",
    "non-human primates": "Nonhuman primates",
    "other animals": "Other animals",
    "animals, other": "Other animals",
    "other rodents": "Other rodents",
    "rodents, other": "Other rodents",
    "pigs": "Pigs",
    "rabbits": "Rabbits",
    "rats": "Rats",
    "reptiles": "Reptiles",
    "reptiles/amphibians": "Reptiles/Amphibians",
}

_ROW = re.compile(r"^\s*([A-Za-z][A-Za-z ,/\-]+?)\s+([\d,]+)(?:\s+[\d.]+)?\s*$")
_TOTAL = re.compile(r"^\s*T\s?O\s?T\s?A\s?L\s+([\d,]+)", re.I)
_CI = re.compile(r"^\s*(?:CI\s*)?([A-E])\s+([\d,]{3,})(?:\s+[\d.]+)?\s*$")
_PAU = re.compile(r"^\s*(?:PAU\s*)?([0-5])\s+([\d,]{3,})(?:\s+[\d.]+)?\s*$")


def _num(s: str) -> int:
    return int(s.replace(",", ""))


def pdf_text(year: int) -> str:
    cache = INTERIM / f"ccac_pdf_{year}.txt"
    if cache.exists():
        return cache.read_text()
    text = "\n".join(p.extract_text() or "" for p in PdfReader(CCAC / f"pdf_{year}.pdf").pages)
    cache.write_text(text)
    return text


def parse_pdf(year: int) -> dict[str, pd.DataFrame]:
    """Extract Table 1 (types), the CI table and the PAU table from a summary report."""
    lines = pdf_text(year).splitlines()

    types: dict[str, int] = {}
    type_total = None
    for line in lines:
        if type_total is None and (m := _TOTAL.match(line)) and types:
            type_total = _num(m.group(1))
            continue
        if type_total is not None:
            break
        if (m := _ROW.match(line)) and (key := m.group(1).strip().lower()) in ANIMAL_TYPES:
            value = _num(m.group(2))
            name = ANIMAL_TYPES[key]
            # Figure captions sometimes repeat names with 0 or percentages; keep the table value.
            if value > types.get(name, -1):
                types[name] = value

    ci = {m.group(1): _num(m.group(2)) for line in lines if (m := _CI.match(line))}
    pau = {int(m.group(1)): _num(m.group(2)) for line in lines if (m := _PAU.match(line))}

    t = pd.DataFrame({"animal_type": list(types), "n_animals": list(types.values())})
    t.insert(0, "year", year)
    t["source"] = "pdf_table1"
    return {
        "types": t,
        "type_total": pd.DataFrame([{"year": year, "reported_total": type_total}]),
        "ci": pd.DataFrame({"year": year, "ci": list(ci), "n_animals": list(ci.values())}),
        "pau": pd.DataFrame({"year": year, "pau": list(pau), "n_animals": list(pau.values())}),
    }


def _split_name(name: str) -> tuple[str, str | None]:
    name = re.sub(r"\s+", " ", str(name)).strip()
    m = re.search(r"\(([^)]+)\)\s*$", name)
    return name, (m.group(1).strip() if m else None)


def _find_header(path: Path) -> int:
    raw = pd.read_excel(path, sheet_name=0, header=None, nrows=15)
    for i, row in raw.iterrows():
        if row.astype(str).str.strip().eq("Animal Type").any():
            return int(i)
    raise ValueError(f"no header row in {path}")


def parse_excel(year: int) -> dict[str, pd.DataFrame]:
    f1 = CCAC / f"{year}-sortable-excel-file1.xlsx"
    f2 = CCAC / f"{year}-sortable-excel-file2.xlsx"

    a = pd.read_excel(f1, sheet_name=0, header=_find_header(f1))
    a = a.iloc[:, [0, 2, 4]]
    a.columns = ["animal_type", "species", "n_animals"]
    grand_total_1 = a.loc[a["animal_type"].isna() & a["species"].isna(), "n_animals"].sum()
    a = a.dropna(subset=["animal_type", "species"])

    b = pd.read_excel(f2, sheet_name=0, header=_find_header(f2))
    b = b.iloc[:, [0, 2, 4, 5, 6]]
    b.columns = ["animal_type", "species", "ci", "pau", "n_animals"]
    grand_total_2 = b.loc[b["animal_type"].isna() & b["species"].isna(), "n_animals"].sum()
    b = b.dropna(subset=["animal_type", "species"])

    for df in (a, b):
        df["animal_type"] = df["animal_type"].astype(str).str.strip()
        df["raw_species"] = df["species"].astype(str)
        split = df["species"].map(_split_name)
        df["species"] = split.str[0]
        df["scientific_name"] = split.str[1]
        df["n_animals"] = pd.to_numeric(df["n_animals"], errors="coerce")
        df.insert(0, "year", year)
    b["ci"] = b["ci"].astype(str).str.strip().str.upper()
    b["pau"] = pd.to_numeric(b["pau"], errors="coerce").astype("Int64")

    sheet1 = pd.ExcelFile(f1).sheet_names[0]
    sheet2 = pd.ExcelFile(f2).sheet_names[0]
    meta = pd.DataFrame(
        [
            {
                "year": year,
                "file1_sheet": sheet1,
                "file2_sheet": sheet2,
                "file1_grand_total_row": grand_total_1 or None,
                "file2_grand_total_row": grand_total_2 or None,
            }
        ]
    )
    return {"species": a, "species_ci_pau": b, "meta": meta}


def species_crosswalk(species: pd.DataFrame) -> pd.DataFrame:
    """One canonical label per taxon so species can be tracked across years.

    Key = lower-cased scientific name when present, else lower-cased common name. The canonical
    label is the most recent spelling used by CCAC.
    """
    df = species.copy()
    df["species_key"] = (
        df.scientific_name.fillna(df.species).str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    )
    latest = df.sort_values("year").groupby(["animal_type", "species_key"]).species.last()
    xw = (
        df.groupby(["animal_type", "species_key", "species"], as_index=False)
        .agg(first_year=("year", "min"), last_year=("year", "max"))
        .merge(latest.rename("canonical_label").reset_index(), on=["animal_type", "species_key"])
    )
    return xw


PDF_YEARS = range(2011, 2026)
EXCEL_YEARS = range(2019, 2026)


def run() -> None:
    pdf = [parse_pdf(y) for y in PDF_YEARS]
    xl = [parse_excel(y) for y in EXCEL_YEARS]

    types = pd.concat([p["types"] for p in pdf], ignore_index=True)
    type_totals = pd.concat([p["type_total"] for p in pdf], ignore_index=True)
    ci = pd.concat([p["ci"] for p in pdf], ignore_index=True)
    pau = pd.concat([p["pau"] for p in pdf], ignore_index=True)
    species = pd.concat([x["species"] for x in xl], ignore_index=True)
    scp = pd.concat([x["species_ci_pau"] for x in xl], ignore_index=True)
    meta = pd.concat([x["meta"] for x in xl], ignore_index=True)

    types.to_csv(PROCESSED / "ccac_type_year.csv", index=False)
    type_totals.to_csv(PROCESSED / "ccac_reported_totals.csv", index=False)
    ci.to_csv(PROCESSED / "ccac_ci_year.csv", index=False)
    pau.to_csv(PROCESSED / "ccac_pau_year.csv", index=False)
    species.drop(columns="raw_species").to_csv(PROCESSED / "ccac_species_year.csv", index=False)
    scp.drop(columns="raw_species").to_csv(PROCESSED / "ccac_species_ci_pau.csv", index=False)
    species[["year", "animal_type", "raw_species"]].to_csv(INTERIM / "ccac_raw_species.csv", index=False)
    xw = species_crosswalk(pd.concat([species, scp], ignore_index=True))
    xw.to_csv(PROCESSED / "ccac_species_crosswalk.csv", index=False)
    print(f"crosswalk: {xw.species.nunique()} labels -> {xw.species_key.nunique()} taxa")
    meta.to_csv(INTERIM / "ccac_excel_meta.csv", index=False)

    nhp = types[types.animal_type == "Nonhuman primates"].set_index("year")["n_animals"]
    print("NHP by year:", nhp.to_dict())
    print(f"{len(species)} species-year rows, {len(scp)} species x CI x PAU rows")


if __name__ == "__main__":
    run()
