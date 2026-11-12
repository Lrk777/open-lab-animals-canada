"""Nonhuman-primate trends in CCAC data.

1. Series: NHP per year 2011-2025 (PDF Table 1); 2011 is flagged because CCAC says pre-2012
   data are not comparable.
2. Structural breaks: PELT (ruptures) on log counts, plus a Chow-style test at each candidate year.
3. Forecast: local linear trend structural time series (Kalman filter, statsmodels
   UnobservedComponents) on log counts, 2026-2030 with 80/95% intervals.
4. Composition: genus mix, invasiveness (CI) mix and purpose (PAU) mix for 2019-2025 (Excel).
5. Like-for-like sensitivity: Canadian NHP counts restricted to laboratory genera and to
   CI C-E, rescaled from File 2 (which double counts) to File 1 totals.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import ruptures as rpt
import statsmodels.api as sm
import yaml

from olac.paths import CONFIG, PROCESSED

warnings.filterwarnings("ignore")

# Genera kept in captive laboratory colonies in North America. Everything else in the CCAC
# primate list (lemurs, howlers, colobus, langurs, great apes...) is field or sanctuary study.
LAB_GENERA = {"Macaca", "Chlorocebus", "Callithrix", "Papio", "Saimiri", "Aotus", "Saguinus"}

PAU_LABELS = {
    0: "Breeding colonies",
    1: "Fundamental research",
    2: "Medical research (human/animal disease)",
    3: "Regulatory testing",
    4: "Development of products/appliances",
    5: "Education and training",
}


def nhp_series() -> pd.Series:
    t = pd.read_csv(PROCESSED / "ccac_type_year.csv")
    return t[t.animal_type == "Nonhuman primates"].set_index("year").n_animals.astype(float).sort_index()


def breaks(y: pd.Series) -> pd.DataFrame:
    s = np.log(y.loc[2012:].values).reshape(-1, 1)
    algo = rpt.Pelt(model="l2", min_size=3).fit(s)
    bkps = algo.predict(pen=0.5)
    years = y.loc[2012:].index.tolist()
    rows = []
    for b in bkps[:-1]:
        before, after = s[:b, 0], s[b:, 0]
        rows.append(
            {
                "break_year": years[b],
                "mean_before": float(np.exp(before.mean())),
                "mean_after": float(np.exp(after.mean())),
                "ratio": float(np.exp(after.mean() - before.mean())),
                "method": "PELT l2 on log counts, pen=0.5, min_size=3",
            }
        )
    x = np.arange(len(s))
    ols = sm.OLS(s[:, 0], sm.add_constant(x)).fit()
    rows.append(
        {
            "break_year": None,
            "mean_before": None,
            "mean_after": None,
            "ratio": float(np.exp(ols.params[1])),
            "method": f"log-linear trend 2012-{years[-1]}: annual growth factor (p={ols.pvalues[1]:.3f})",
        }
    )
    return pd.DataFrame(rows)


def forecast(y: pd.Series, horizon: int = 5) -> pd.DataFrame:
    s = np.log(y.loc[2012:])
    mod = sm.tsa.UnobservedComponents(s.values, level="local linear trend")
    res = mod.fit(disp=False)
    fc = res.get_forecast(horizon)
    years = np.arange(s.index[-1] + 1, s.index[-1] + 1 + horizon)
    mean = fc.predicted_mean
    ci80 = fc.conf_int(alpha=0.2)
    ci95 = fc.conf_int(alpha=0.05)
    hist = pd.DataFrame({"year": s.index, "observed": np.exp(s.values), "fitted": np.exp(res.fittedvalues)})
    hist.loc[hist.index[0], "fitted"] = np.nan
    fut = pd.DataFrame(
        {
            "year": years,
            "forecast": np.exp(mean),
            "lo80": np.exp(ci80[:, 0]),
            "hi80": np.exp(ci80[:, 1]),
            "lo95": np.exp(ci95[:, 0]),
            "hi95": np.exp(ci95[:, 1]),
        }
    )
    return pd.concat([hist, fut], ignore_index=True)


def composition() -> dict[str, pd.DataFrame]:
    sp = pd.read_csv(PROCESSED / "ccac_species_year.csv")
    sp = sp[sp.animal_type == "Nonhuman primates"].copy()
    sp["genus"] = sp.scientific_name.fillna("Unspecified").str.split().str[0]
    sp["setting"] = np.where(sp.genus.isin(LAB_GENERA | {"Unspecified"}), "laboratory genera", "field/other genera")
    genus = sp.groupby(["year", "genus"], as_index=False).n_animals.sum()
    species = sp.groupby(["year", "species"], as_index=False).n_animals.sum()

    x = pd.read_csv(PROCESSED / "ccac_species_ci_pau.csv")
    x = x[x.animal_type == "Nonhuman primates"].copy()
    x["genus"] = x.scientific_name.fillna("Unspecified").str.split().str[0]
    ci = x.groupby(["year", "ci"], as_index=False).n_animals.sum()
    pau = x.groupby(["year", "pau"], as_index=False).n_animals.sum()
    pau["pau_label"] = pau.pau.map(PAU_LABELS)
    species_pau = x.assign(pau_label=x.pau.map(PAU_LABELS)).groupby(
        ["year", "species", "pau_label"], as_index=False).n_animals.sum()

    # Like-for-like: share of File 2 uses in lab genera with CI C-E, applied to File 1 totals.
    f1 = sp.groupby("year").n_animals.sum()
    f2 = x.groupby("year").n_animals.sum()
    lab = x[x.genus.isin(LAB_GENERA | {"Unspecified"})]
    lab_ce = lab[lab.ci.isin(["C", "D", "E"])].groupby("year").n_animals.sum()
    sens = pd.DataFrame(
        {
            "all_nhp_file1": f1,
            "file2_uses": f2,
            "lab_genera_share": lab.groupby("year").n_animals.sum() / f2,
            "lab_ci_c_to_e_share": lab_ce / f2,
        }
    )
    sens["lab_genera_est"] = (sens.all_nhp_file1 * sens.lab_genera_share).round()
    sens["lab_ci_c_to_e_est"] = (sens.all_nhp_file1 * sens.lab_ci_c_to_e_share).round()
    return {
        "nhp_genus_year": genus,
        "nhp_species_year": species,
        "nhp_ci_year": ci,
        "nhp_pau_year": pau,
        "nhp_species_pau_year": species_pau,
        "nhp_like_for_like": sens.reset_index().rename(columns={"index": "year"}),
    }


def all_animals_ci_share() -> pd.DataFrame:
    ci = pd.read_csv(PROCESSED / "ccac_ci_year.csv")
    ci["share"] = ci.n_animals / ci.groupby("year").n_animals.transform("sum")
    return ci


def per_capita_like_for_like(sens: pd.DataFrame) -> pd.DataFrame:
    comp = pd.read_csv(PROCESSED / "nhp_comparison.csv")
    pop = yaml.safe_load((CONFIG / "jurisdictions.yaml").read_text())["canada"]["population_m"]
    extra = sens[["year", "lab_ci_c_to_e_est"]].rename(columns={"lab_ci_c_to_e_est": "nhp"})
    extra = extra.assign(
        jurisdiction="canada_lab_ci_c_e",
        measure="CCAC lab genera, CI C-E only (sensitivity)",
        population_m=pop,
    )
    extra["per_million"] = (extra.nhp / pop).round(1)
    return pd.concat([comp, extra], ignore_index=True)


def run() -> None:
    y = nhp_series()
    b = breaks(y)
    f = forecast(y)
    comp = composition()
    b.to_csv(PROCESSED / "nhp_breaks.csv", index=False)
    f.to_csv(PROCESSED / "nhp_forecast.csv", index=False)
    for name, df in comp.items():
        df.to_csv(PROCESSED / f"{name}.csv", index=False)
    all_animals_ci_share().to_csv(PROCESSED / "ccac_ci_share.csv", index=False)
    pc = per_capita_like_for_like(comp["nhp_like_for_like"])
    pc.to_csv(PROCESSED / "nhp_comparison_with_sensitivity.csv", index=False)

    print("Breaks:\n", b.to_string())
    print("Forecast:\n", f.tail(5).round(0).to_string())
    print("Like-for-like:\n", comp["nhp_like_for_like"].round(3).to_string())
    print(pc[pc.year.isin([2022, 2023, 2024, 2025])].pivot(index="year", columns="jurisdiction",
                                                           values="per_million").to_string())


if __name__ == "__main__":
    run()
