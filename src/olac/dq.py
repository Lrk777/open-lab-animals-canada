"""Data-quality audit of CCAC Animal Data Reports.

Every check is a function returning issue dicts. Severity levels:
  error   - the published numbers contradict each other
  warning - labelling/structure problems that can mislead users of the data
  review  - statistically unusual values worth a human look (not necessarily wrong)

Outputs data/processed/dq_issues.csv and docs/data_quality_report.md.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from olac.paths import INTERIM, PROCESSED, ROOT

Issue = dict

_CHECKS: list[Callable[[], list[Issue]]] = []


def check(fn: Callable[[], list[Issue]]) -> Callable[[], list[Issue]]:
    _CHECKS.append(fn)
    return fn


def _issue(check_id: str, severity: str, year, detail: str, expected=None, observed=None) -> Issue:
    return {
        "check_id": check_id,
        "severity": severity,
        "year": year,
        "detail": detail,
        "expected": expected,
        "observed": observed,
    }


def _load():
    p = PROCESSED
    return (
        pd.read_csv(p / "ccac_type_year.csv"),
        pd.read_csv(p / "ccac_reported_totals.csv"),
        pd.read_csv(p / "ccac_ci_year.csv"),
        pd.read_csv(p / "ccac_pau_year.csv"),
        pd.read_csv(p / "ccac_species_year.csv"),
        pd.read_csv(p / "ccac_species_ci_pau.csv"),
        pd.read_csv(INTERIM / "ccac_excel_meta.csv"),
        pd.read_csv(INTERIM / "ccac_raw_species.csv"),
    )


TYPES, TOTALS, CI, PAU, SPECIES, SCP, META, RAW_SPECIES = (None,) * 8


@check
def pdf_type_sum_matches_total() -> list[Issue]:
    out = []
    sums = TYPES.groupby("year")["n_animals"].sum()
    for _, r in TOTALS.iterrows():
        s = int(sums.get(r.year, 0))
        if pd.notna(r.reported_total) and s != int(r.reported_total):
            out.append(
                _issue(
                    "pdf_type_sum",
                    "error" if abs(s - r.reported_total) > 1 else "warning",
                    int(r.year),
                    "Table 1 animal-type rows do not sum to the reported Table 1 total",
                    int(r.reported_total),
                    s,
                )
            )
    return out


@check
def pdf_ci_equals_pau() -> list[Issue]:
    out = []
    ci = CI.groupby("year")["n_animals"].sum()
    pau = PAU.groupby("year")["n_animals"].sum()
    for y in sorted(set(ci.index) & set(pau.index)):
        if ci[y] != pau[y]:
            out.append(
                _issue(
                    "pdf_ci_vs_pau",
                    "error",
                    int(y),
                    "Invasiveness table and purpose table count different totals for the same animals",
                    int(ci[y]),
                    int(pau[y]),
                )
            )
    return out


@check
def excel_matches_pdf() -> list[Issue]:
    out = []
    sp_sum = SPECIES.groupby("year")["n_animals"].sum()
    scp_sum = SCP.groupby("year")["n_animals"].sum()
    ci_sum = CI.groupby("year")["n_animals"].sum()
    for _, m in META.iterrows():
        y = int(m.year)
        pdf_total = TOTALS.set_index("year").reported_total.get(y)
        if round(sp_sum[y]) != round(m.file1_grand_total_row):
            out.append(
                _issue(
                    "excel1_rows_vs_total_row",
                    "error",
                    y,
                    "Excel File 1 species rows do not sum to its own grand-total row",
                    m.file1_grand_total_row,
                    sp_sum[y],
                )
            )
        if pdf_total is not None and round(m.file1_grand_total_row) != round(pdf_total):
            out.append(
                _issue(
                    "excel1_vs_pdf_total",
                    "error",
                    y,
                    "Excel File 1 grand total differs from the PDF Table 1 total",
                    pdf_total,
                    m.file1_grand_total_row,
                )
            )
        if y in ci_sum and round(scp_sum[y]) != round(ci_sum[y]):
            out.append(
                _issue(
                    "excel2_vs_pdf_ci",
                    "error",
                    y,
                    "Excel File 2 rows differ from the PDF invasiveness-table total",
                    int(ci_sum[y]),
                    scp_sum[y],
                )
            )
    return out


@check
def excel_type_matches_pdf_type() -> list[Issue]:
    out = []
    xl = SPECIES.groupby(["year", "animal_type"])["n_animals"].sum()
    pdf = TYPES.assign(animal_type=TYPES.animal_type.str.lower()).set_index(["year", "animal_type"])[
        "n_animals"
    ]
    for (y, t), v in xl.items():
        p = pdf.get((y, t.lower()))
        if p is not None and round(v) != round(p):
            out.append(
                _issue(
                    "excel_type_vs_pdf_type",
                    "error",
                    int(y),
                    f"{t}: Excel File 1 species sum differs from the PDF Table 1 value",
                    int(p),
                    v,
                )
            )
    return out


@check
def sheet_year_labels() -> list[Issue]:
    out = []
    for _, m in META.iterrows():
        for col in ("file1_sheet", "file2_sheet"):
            if str(int(m.year)) not in str(m[col]):
                out.append(
                    _issue(
                        "sheet_label_year",
                        "warning",
                        int(m.year),
                        f"{m.year} {col.replace('_sheet', '').replace('file', 'Excel File ')} "
                        f"worksheet is labelled '{m[col]}'",
                        str(int(m.year)),
                        m[col],
                    )
                )
    return out


@check
def non_integer_counts() -> list[Issue]:
    out = []
    for name, df in (("File 1", SPECIES), ("File 2", SCP)):
        bad = df[df.n_animals.notna() & (df.n_animals % 1 != 0)]
        for _, r in bad.iterrows():
            out.append(
                _issue(
                    "non_integer_count",
                    "error",
                    int(r.year),
                    f"{name}: fractional animal count for {r.species}",
                    "integer",
                    r.n_animals,
                )
            )
        missing = df[df.n_animals.isna()]
        for _, r in missing.iterrows():
            out.append(
                _issue(
                    "missing_count",
                    "warning",
                    int(r.year),
                    f"{name}: blank animal count for {r.species}",
                    "number",
                    None,
                )
            )
    return out


@check
def zero_rows() -> list[Issue]:
    z = SPECIES[SPECIES.n_animals == 0].groupby("year").size()
    return [
        _issue(
            "zero_count_rows",
            "warning",
            int(y),
            f"{n} species listed with 0 animals in Excel File 1 (ambiguous: unused or redacted?)",
            0,
            int(n),
        )
        for y, n in z.items()
    ]


@check
def name_hygiene() -> list[Issue]:
    raw = RAW_SPECIES.raw_species.astype(str)
    bad = RAW_SPECIES[raw.str.contains(r"\n|\s{2,}|^\s|\s$", regex=True)]
    g = bad.groupby("year").size()
    return [
        _issue(
            "name_whitespace",
            "warning",
            int(y),
            f"{n} species names contain stray line breaks or repeated spaces, which breaks joins "
            "across years",
            0,
            int(n),
        )
        for y, n in g.items()
    ]


@check
def unspecified_taxa_share() -> list[Issue]:
    """Animals reported without a scientific name, per year and animal type.

    Flags groups where more than 5% of animals cannot be attributed to a species, plus every
    unattributed nonhuman primate entry because species matters for welfare standards.
    """
    out = []
    df = SPECIES[SPECIES.n_animals > 0]
    for (y, t), g in df.groupby(["year", "animal_type"]):
        unspec = g[g.scientific_name.isna()]
        share = unspec.n_animals.sum() / g.n_animals.sum()
        if t == "Nonhuman primates" and len(unspec):
            names = ", ".join(f"'{s}' ({int(n)})" for s, n in zip(unspec.species, unspec.n_animals, strict=False))
            out.append(
                _issue(
                    "nhp_unspecified_species",
                    "warning",
                    int(y),
                    f"{int(unspec.n_animals.sum())} nonhuman primates ({share:.1%}) reported without "
                    f"a species: {names}",
                    0,
                    int(unspec.n_animals.sum()),
                )
            )
        elif share > 0.05 and g.n_animals.sum() > 1000:
            out.append(
                _issue(
                    "unspecified_species_share",
                    "review",
                    int(y),
                    f"{t}: {share:.1%} of animals ({int(unspec.n_animals.sum()):,}) have no "
                    "scientific name",
                    "<5%",
                    round(share, 3),
                )
            )
    return out


@check
def same_scientific_name_multiple_labels() -> list[Issue]:
    """One issue per scientific name, listing every year it was split across labels."""
    df = SPECIES.dropna(subset=["scientific_name"])
    g = df.groupby(["scientific_name", "year"]).species.nunique()
    g = g[g > 1].reset_index()
    out = []
    for sci, rows in g.groupby("scientific_name"):
        labels = sorted(df[df.scientific_name == sci].species.unique())
        years = rows.year.tolist()
        out.append(
            _issue(
                "duplicate_scientific_name",
                "warning",
                f"{min(years)}-{max(years)}" if len(years) > 1 else int(years[0]),
                f"{sci} is split across {len(labels)} common names in {len(years)} year(s): "
                f"{'; '.join(labels)}. May reflect breeds or subspecies, but should be coded "
                "separately if so.",
                1,
                len(labels),
            )
        )
    return out


@check
def file2_not_below_file1() -> list[Issue]:
    """File 2 may double-count reused animals, so it should never be lower than File 1."""
    out = []
    keys = ["year", "animal_type", "key"]
    s1 = SPECIES.assign(key=SPECIES.species.str.lower())
    s2 = SCP.assign(key=SCP.species.str.lower())

    labels1 = s1.groupby(keys).species.first()
    labels2 = s2.groupby(keys).species.first()
    both = pd.concat([labels1.rename("l1"), labels2.rename("l2")], axis=1).dropna()
    for (y, t, _), r in both[both.l1 != both.l2].iterrows():
        out.append(
            _issue(
                "label_case_mismatch",
                "warning",
                int(y),
                f"{t}: File 1 says '{r.l1}' but File 2 says '{r.l2}' (same species, different "
                "capitalisation; exact-match joins drop it)",
                r.l1,
                r.l2,
            )
        )

    f1 = s1.groupby(keys).n_animals.sum()
    f2 = s2.groupby(keys).n_animals.sum()
    joined = pd.concat([f1.rename("f1"), f2.rename("f2")], axis=1).fillna(0)
    label = labels1.combine_first(labels2)
    bad = joined[(joined.f2 < joined.f1)]
    for idx, r in bad.iterrows():
        y, t, s = idx[0], idx[1], label[idx]
        sev = "error" if r.f1 - r.f2 >= 10 else "warning"
        where = "missing from File 2" if r.f2 == 0 else "lower in File 2"
        out.append(
            _issue(
                "file2_below_file1",
                sev,
                int(y),
                f"{t} / {s}: {int(r.f1):,} animals in File 1 but {int(r.f2):,} in File 2 ({where})",
                int(r.f1),
                int(r.f2),
            )
        )
    only2 = joined[(joined.f1 == 0) & (joined.f2 > 0)]
    for idx, r in only2.iterrows():
        y, t, s = idx[0], idx[1], label[idx]
        out.append(
            _issue(
                "file2_without_file1",
                "warning",
                int(y),
                f"{t} / {s}: {int(r.f2):,} animals in File 2 but species absent from File 1",
                0,
                int(r.f2),
            )
        )
    return out


@check
def cross_year_label_drift() -> list[Issue]:
    """Same scientific name under a different common name than the previous year."""
    df = SPECIES.dropna(subset=["scientific_name"])
    labels = df.groupby(["scientific_name", "year"]).species.agg(lambda s: tuple(sorted(set(s))))
    out = []
    for sci, by_year in labels.groupby(level=0):
        seq = by_year.droplevel(0).sort_index()
        for (y0, l0), (y1, l1) in zip(seq.items(), list(seq.items())[1:], strict=False):
            if y1 == y0 + 1 and len(l0) == 1 and len(l1) == 1 and l0 != l1:
                out.append(
                    _issue(
                        "cross_year_label_drift",
                        "warning",
                        int(y1),
                        f"{sci}: '{l0[0]}' in {y0} became '{l1[0]}' in {y1}; year-over-year "
                        "joins on the common name break",
                        l0[0],
                        l1[0],
                    )
                )
    return out


@check
def identical_consecutive_totals() -> list[Issue]:
    """Exact repeats of an animal-type total in consecutive years are worth confirming."""
    out = []
    for name, df in (("File 1", SPECIES), ("File 2", SCP)):
        t = df.groupby(["animal_type", "year"]).n_animals.sum()
        for typ, s in t.groupby(level=0):
            s = s.droplevel(0).sort_index()
            for y in s.index[1:]:
                if y - 1 in s.index and s[y] == s[y - 1] and s[y] > 100:
                    out.append(
                        _issue(
                            "identical_consecutive_total",
                            "review",
                            int(y),
                            f"{name} {typ} total is exactly {int(s[y]):,} in both {y - 1} and {y} "
                            "although the species breakdown differs; worth confirming",
                            None,
                            int(s[y]),
                        )
                    )
    return out


@check
def yoy_anomalies() -> list[Issue]:
    """Robust z-score of log year-over-year change per animal type (2012+)."""
    out = []
    t = TYPES[(TYPES.year >= 2012) & (TYPES.n_animals > 0)].pivot(
        index="year", columns="animal_type", values="n_animals"
    )
    d = np.log(t).diff()
    for col in d.columns:
        s = d[col].dropna()
        if len(s) < 6:
            continue
        mad = np.median(np.abs(s - s.median())) or 1e-9
        z = 0.6745 * (s - s.median()) / mad
        for y, zval in z[np.abs(z) > 3.5].items():
            prev, cur = t[col].get(y - 1), t[col][y]
            out.append(
                _issue(
                    "yoy_outlier",
                    "review",
                    int(y),
                    f"{col}: {int(prev):,} -> {int(cur):,} ({(cur / prev - 1):+.0%}), robust z={zval:.1f}",
                    int(prev),
                    int(cur),
                )
            )
    return out


@check
def missing_types() -> list[Issue]:
    out = []
    expected = set(TYPES[TYPES.year >= 2012].animal_type)
    for y, df in TYPES.groupby("year"):
        miss = expected - set(df.animal_type) - ({"Reptiles", "Amphibians"} if y == 2011 else set())
        for m in sorted(miss):
            out.append(
                _issue(
                    "type_missing_from_table1",
                    "warning",
                    int(y),
                    f"'{m}' absent from Table 1 (category not reported or merged elsewhere)",
                    "present",
                    "absent",
                )
            )
    return out


def run() -> pd.DataFrame:
    global TYPES, TOTALS, CI, PAU, SPECIES, SCP, META, RAW_SPECIES
    TYPES, TOTALS, CI, PAU, SPECIES, SCP, META, RAW_SPECIES = _load()

    issues = [i for fn in _CHECKS for i in fn()]
    df = pd.DataFrame(issues, columns=["check_id", "severity", "year", "detail", "expected", "observed"])
    df = df.sort_values(["severity", "year", "check_id"], key=lambda s: s.map(
        {"error": 0, "warning": 1, "review": 2}) if s.name == "severity" else s)
    df.insert(0, "issue_id", [f"DQ-{i:03d}" for i in range(1, len(df) + 1)])
    df.to_csv(PROCESSED / "dq_issues.csv", index=False)
    _write_report(df)
    print(df.severity.value_counts().to_string())
    return df


def _write_report(df: pd.DataFrame) -> None:
    counts = df.severity.value_counts()
    lines = [
        "# CCAC Animal Data Reports: data-quality audit",
        "",
        "Generated by `python -m olac.dq` from the CCAC summary PDFs (2011-2025) and sortable "
        "Excel files (2019-2025). Every issue is reproducible from `data/processed/dq_issues.csv`.",
        "",
        f"- **Errors** (published numbers contradict each other): {counts.get('error', 0)}",
        f"- **Warnings** (labelling or structure problems): {counts.get('warning', 0)}",
        f"- **Review** (statistically unusual, may be genuine): {counts.get('review', 0)}",
        "",
        "Severity definitions and check logic live in `src/olac/dq.py`.",
        "",
    ]
    for sev in ("error", "warning", "review"):
        sub = df[df.severity == sev]
        if sub.empty:
            continue
        lines += [f"## {sev.title()}s", "", "| ID | Year | Check | Detail |", "|---|---|---|---|"]
        for _, r in sub.iterrows():
            detail = str(r.detail).replace("|", "/")
            lines.append(f"| {r.issue_id} | {r.year} | `{r.check_id}` | {detail} |")
        lines.append("")
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "data_quality_report.md").write_text("\n".join(lines))


if __name__ == "__main__":
    run()
