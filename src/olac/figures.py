"""Static figures for the preprint, README and policy brief (PNG, 200 dpi) in docs/figures/."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from olac.paths import PROCESSED, ROOT  # noqa: E402

OUT = ROOT / "docs" / "figures"
LABEL = {"canada": "Canada", "uk": "Great Britain", "eu": "EU27 + Norway", "us": "United States",
         "canada_lab_ci_c_e": "Canada, lab genera CI C-E"}


def _save(fig, name):
    from matplotlib.ticker import MaxNLocator

    for ax in fig.axes:
        if ax.get_xlabel() == "" and name != "audit_rates.png" and name != "transparency_index.png":
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    OUT.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=200)
    plt.close(fig)


def nhp_trend():
    fc = pd.read_csv(PROCESSED / "nhp_forecast.csv")
    h, f = fc[fc.observed.notna()], fc[fc.forecast.notna()]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.fill_between(f.year, f.lo95, f.hi95, alpha=0.15, label="95% interval")
    ax.fill_between(f.year, f.lo80, f.hi80, alpha=0.3, label="80% interval")
    ax.plot(h.year, h.observed, "o-", label="Reported (CCAC)")
    ax.plot(f.year, f.forecast, "--", label="Forecast")
    ax.set_title("Nonhuman primates in Canadian science")
    ax.set_ylabel("animals per year")
    ax.legend(frameon=False)
    _save(fig, "nhp_trend.png")


def per_capita():
    c = pd.read_csv(PROCESSED / "nhp_comparison_with_sensitivity.csv")
    fig, ax = plt.subplots(figsize=(8, 4))
    for j, g in c.groupby("jurisdiction"):
        ax.plot(g.year, g.per_million, "o-" if j != "canada_lab_ci_c_e" else "o--", label=LABEL[j])
    ax.set_title("Nonhuman primates per million population")
    ax.set_ylabel("per million")
    ax.legend(frameon=False, fontsize=8)
    _save(fig, "per_capita.png")


def transparency():
    i = pd.read_csv(PROCESSED / "transparency_index.csv").sort_values("index_0_100")
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.barh([LABEL[j] for j in i.jurisdiction], i.index_0_100,
            xerr=[i.index_0_100 - i.score_p05, i.score_p95 - i.index_0_100], capsize=4)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Transparency Index (0-100), whiskers: 5th-95th pct over random weights")
    _save(fig, "transparency_index.png")


def purpose():
    p = pd.read_csv(PROCESSED / "nhp_pau_year.csv").pivot(index="year", columns="pau_label", values="n_animals").fillna(0)
    fig, ax = plt.subplots(figsize=(8, 4))
    p.plot.bar(stacked=True, ax=ax, width=0.8)
    ax.set_title("Primate uses by purpose (CCAC Excel File 2)")
    ax.set_ylabel("uses")
    ax.legend(frameon=False, fontsize=7)
    _save(fig, "nhp_purpose.png")


def audit_rates():
    path = PROCESSED / "audit_rules.csv"
    if not path.exists():
        return
    a = pd.read_csv(path)
    r = a.groupby(["group", "field"]).reported.mean().reset_index().sort_values("reported")
    fig, ax = plt.subplots(figsize=(7, 6))
    colors = {"arrive_essential": "C0", "primate_welfare": "C3", "oversight": "C2"}
    ax.barh(r.field, r.reported, color=[colors[g] for g in r.group])
    ax.set_xlim(0, 1)
    ax.set_xlabel(f"share of {a.pmcid.nunique()} papers reporting the item (rules baseline)")
    _save(fig, "audit_rates.png")


def run():
    for fn in (nhp_trend, per_capita, transparency, purpose, audit_rates):
        fn()
    print("figures in", OUT)


if __name__ == "__main__":
    run()
