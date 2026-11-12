"""Open Lab Animals Canada - public dashboard.

Run: streamlit run app/streamlit_app.py
Reads only files in data/processed/, so it can be deployed with the published dataset alone.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
P = ROOT / "data" / "processed"

st.set_page_config(page_title="Open Lab Animals Canada", layout="wide")

EU_ISO = ["AUT", "BEL", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA", "DEU", "GRC", "HUN", "IRL",
          "ITA", "LVA", "LTU", "LUX", "MLT", "NLD", "POL", "PRT", "ROU", "SVK", "SVN", "ESP", "SWE", "NOR"]
JUR_LABEL = {"canada": "Canada", "uk": "Great Britain", "eu": "EU27 + Norway", "us": "United States",
             "canada_lab_ci_c_e": "Canada (lab genera, CI C-E)"}


@st.cache_data
def load(name: str) -> pd.DataFrame | None:
    path = P / f"{name}.csv"
    return pd.read_csv(path) if path.exists() else None


def missing(name: str) -> None:
    st.info(f"`{name}.csv` not built yet. Run the pipeline (`make all`).")


st.title("Open Lab Animals Canada")
st.caption(
    "Open data on animal-based science in Canada: national statistics, international transparency "
    "comparison, university openness, and the reporting quality of primate research papers. "
    "Every number links back to a public source; see the Methods tab."
)

tabs = st.tabs(["Overview", "Transparency Index", "Primate trends", "University scorecard",
                "Reporting audit", "Funding", "Data quality", "Methods & downloads"])

nhp = load("ccac_type_year")
comp = load("nhp_comparison_with_sensitivity")
idx = load("transparency_index")

# ---------------------------------------------------------------- Overview
with tabs[0]:
    c1, c2, c3, c4 = st.columns(4)
    if nhp is not None:
        n = nhp[nhp.animal_type == "Nonhuman primates"].set_index("year").n_animals
        c1.metric("Nonhuman primates used in Canada, 2025", f"{int(n[2025]):,}", f"{n[2025] / n[2024] - 1:+.0%} vs 2024")
        c2.metric("Change since 2012", f"{n[2025] / n[2012] - 1:+.0%}")
    if comp is not None:
        latest = comp[comp.year == 2025].set_index("jurisdiction").per_million
        if "canada" in latest and "uk" in latest:
            c3.metric("Primates per million people, Canada vs Great Britain (2025)",
                      f"{latest['canada']:.0f} vs {latest['uk']:.0f}")
    if idx is not None:
        ca = idx.set_index("jurisdiction").loc["canada"]
        c4.metric("Transparency Index rank (of 4)", f"{int(ca['rank'])}", f"{ca.index_0_100:.0f}/100", delta_color="off")
    st.markdown(
        """
**What this project found**

- Canada's national animal statistics are internally consistent, but labelling problems (species renamed
  between years, primates recorded without a species, a 2025 worksheet labelled 2024) make them hard to use.
  See the *Data quality* tab for the full log.
- Canada ranks last of four jurisdictions on reporting transparency. It publishes national totals only, with
  prospective (not actual) severity and no information on primate origin.
- Most primates in Canadian science are cynomolgus macaques used in regulatory testing. Rhesus macaques, the
  species in the York University investigation, number a few hundred per year nationally.
- Published Canadian primate neuroscience papers rarely report housing, fluid-control detail, or the number
  of surgeries per animal. See the *Reporting audit* tab.
"""
    )

# ---------------------------------------------------------------- Transparency Index
with tabs[1]:
    scores = load("transparency_scores")
    if idx is None or scores is None:
        missing("transparency_index")
    else:
        left, right = st.columns([2, 3])
        with left:
            fig = px.bar(idx.sort_values("index_0_100"), x="index_0_100", y="jurisdiction", orientation="h",
                         error_x=idx.score_p95 - idx.index_0_100, error_x_minus=idx.index_0_100 - idx.score_p05,
                         labels={"index_0_100": "Transparency Index (0-100)", "jurisdiction": ""},
                         title="Index with 5th-95th percentile over 10,000 random weightings")
            st.plotly_chart(fig, use_container_width=True)
            ranks = idx.set_index("jurisdiction")[[c for c in idx.columns if c.startswith("p_rank_")]]
            st.caption("Probability of each rank under random weights")
            st.dataframe(ranks.style.format("{:.0%}"), use_container_width=True)
        with right:
            m = []
            for j, row in idx.set_index("jurisdiction").iterrows():
                isos = EU_ISO if j == "eu" else [{"canada": "CAN", "uk": "GBR", "us": "USA"}[j]]
                m += [{"iso": i, "jurisdiction": JUR_LABEL[j], "index": row.index_0_100} for i in isos]
            fig = px.choropleth(pd.DataFrame(m), locations="iso", color="index", hover_name="jurisdiction",
                                color_continuous_scale="Viridis", range_color=(0, 100), projection="natural earth")
            fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=380)
            st.plotly_chart(fig, use_container_width=True)
        st.subheader("Rubric and evidence")
        heat = scores.pivot(index="dimension", columns="jurisdiction", values="score")
        st.plotly_chart(px.imshow(heat, text_auto=True, color_continuous_scale="Blues", zmin=0, zmax=3,
                                  aspect="auto"), use_container_width=True)
        j = st.selectbox("Show evidence for", scores.jurisdiction.unique(), format_func=JUR_LABEL.get)
        st.dataframe(scores[scores.jurisdiction == j][["dimension", "score", "status", "evidence"]],
                     use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- Primate trends
with tabs[2]:
    fc = load("nhp_forecast")
    if fc is not None:
        fig = go.Figure()
        hist = fc[fc.observed.notna()]
        fut = fc[fc.forecast.notna()]
        fig.add_trace(go.Scatter(x=list(fut.year) + list(fut.year[::-1]), y=list(fut.hi95) + list(fut.lo95[::-1]),
                                 fill="toself", line=dict(width=0), name="95% interval", opacity=0.2))
        fig.add_trace(go.Scatter(x=list(fut.year) + list(fut.year[::-1]), y=list(fut.hi80) + list(fut.lo80[::-1]),
                                 fill="toself", line=dict(width=0), name="80% interval", opacity=0.35))
        fig.add_trace(go.Scatter(x=hist.year, y=hist.observed, mode="lines+markers", name="Reported (CCAC)"))
        fig.add_trace(go.Scatter(x=fut.year, y=fut.forecast, mode="lines", line=dict(dash="dash"), name="Forecast"))
        fig.update_layout(title="Nonhuman primates in Canadian science, 2012-2025, with 2026-2030 forecast",
                          yaxis_title="animals", height=420)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Local linear trend structural time series on log counts. Short series: treat the forecast as a "
                   "scenario, not a prediction.")
    c1, c2 = st.columns(2)
    pau = load("nhp_pau_year")
    if pau is not None:
        c1.plotly_chart(px.bar(pau, x="year", y="n_animals", color="pau_label", title="Primate uses by purpose",
                               labels={"n_animals": "uses (File 2)", "pau_label": ""}), use_container_width=True)
    ci = load("nhp_ci_year")
    if ci is not None:
        c2.plotly_chart(px.bar(ci, x="year", y="n_animals", color="ci", title="Primate uses by category of invasiveness",
                               labels={"n_animals": "uses (File 2)", "ci": "CI"}), use_container_width=True)
    genus = load("nhp_genus_year")
    if genus is not None:
        top = genus.groupby("genus").n_animals.sum().nlargest(8).index
        g = genus.assign(genus=genus.genus.where(genus.genus.isin(top), "Other"))
        st.plotly_chart(px.area(g.groupby(["year", "genus"], as_index=False).n_animals.sum(), x="year", y="n_animals",
                                color="genus", title="Primates by genus"), use_container_width=True)
    if comp is not None:
        cc = comp.assign(jurisdiction=comp.jurisdiction.map(JUR_LABEL))
        st.plotly_chart(px.line(cc, x="year", y="per_million", color="jurisdiction", markers=True,
                                title="Primates per million population (counting units differ; see notes)"),
                        use_container_width=True)
        st.caption("Canada counts animals in protocols each year; Great Britain and the EU count first uses; the US "
                   "counts animals used under the Animal Welfare Act (columns C-E). The 'Canada (lab genera, CI C-E)' "
                   "series keeps only laboratory genera in CI C-E as a conservative like-for-like check.")

# ---------------------------------------------------------------- Scorecard
with tabs[3]:
    sc, ev = load("scorecard"), load("scorecard_evidence")
    if sc is None:
        missing("scorecard")
    else:
        st.markdown("Scores are automated first passes with evidence for every point. Cells become *verified* only "
                    "after human review (`data/scorecard/review.csv`).")
        st.plotly_chart(px.bar(sc.sort_values("score_0_100"), x="score_0_100", y="university", color="grade",
                               orientation="h", height=700, labels={"score_0_100": "Openness score (0-100)"},
                               category_orders={"grade": ["A", "B", "C", "D", "E"]}), use_container_width=True)
        u = st.selectbox("Evidence for", sc.university)
        st.dataframe(ev[ev.university == u][["label", "points", "final_hit", "verified", "evidence_url", "evidence_snippet"]],
                     use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- Reporting audit
with tabs[4]:
    au, its, ev_sum = load("audit_rules"), load("its_results"), load("eval_summary")
    if au is None:
        missing("audit_rules")
    else:
        rates = au.groupby(["group", "field"], as_index=False).reported.mean()
        st.plotly_chart(px.bar(rates.sort_values("reported"), x="reported", y="field", color="group", orientation="h",
                               height=650, labels={"reported": "share of papers reporting the item"},
                               title=f"Reporting rates in {au.pmcid.nunique()} Canadian primate neuroscience papers "
                                     "(rules baseline)"), use_container_width=True)
        if ev_sum is not None:
            st.dataframe(ev_sum, use_container_width=True, hide_index=True)
        else:
            st.warning("Extractor accuracy has not been validated against the human gold set yet; treat rates as "
                       "provisional.")
        by_year = load("disclosure_by_year")
        if by_year is not None:
            f = st.multiselect("Fields over time", sorted(by_year.field.unique()),
                               default=["housing_type", "fluid_control_detail", "surgery_count", "randomisation"])
            d = by_year[by_year.field.isin(f)]
            fig = px.line(d, x="year", y="mean", color="field", markers=True, labels={"mean": "share reporting"})
            fig.add_vline(x=2020.5, line_dash="dot", annotation_text="ARRIVE 2.0")
            st.plotly_chart(fig, use_container_width=True)
        if its is not None:
            st.dataframe(its, use_container_width=True, hide_index=True)
    st.subheader("Try the checker")
    txt = st.text_area("Paste a methods section", height=200)
    if txt.strip():
        from olac.audit.cli import render_markdown
        from olac.audit.rules import extract

        st.markdown(render_markdown(extract("pasted text", txt)))

# ---------------------------------------------------------------- Funding
with tabs[5]:
    fy = load("funding_by_category_year")
    if fy is None:
        missing("funding_by_category_year")
    else:
        d = fy[fy.category != "other"].copy()
        d["amount_m"] = d.amount_cad / 1e6
        funder = st.radio("Funder", ["CIHR", "NSERC", "Both"], horizontal=True)
        if funder != "Both":
            d = d[d.funder == funder]
        d = d.groupby(["fiscal_year", "category"], as_index=False).amount_m.sum()
        st.plotly_chart(px.line(d, x="fiscal_year", y="amount_m", color="category", markers=True,
                                labels={"amount_m": "CAD millions paid in fiscal year"}), use_container_width=True)
        st.caption("Keyword classification of award titles, keywords and abstracts (config/funding_lexicon.yaml). "
                   "NSERC data cover 2020-2024 only; CIHR covers 2015-2025. Personnel awards excluded.")

# ---------------------------------------------------------------- Data quality
with tabs[6]:
    dq = load("dq_issues")
    if dq is None:
        missing("dq_issues")
    else:
        c1, c2, c3 = st.columns(3)
        for col, sev in zip((c1, c2, c3), ("error", "warning", "review"), strict=True):
            col.metric(sev.title() + "s", int((dq.severity == sev).sum()))
        chk = st.multiselect("Checks", sorted(dq.check_id.unique()))
        view = dq[dq.check_id.isin(chk)] if chk else dq
        st.dataframe(view, use_container_width=True, hide_index=True)
        st.download_button("Download issue log (CSV)", dq.to_csv(index=False), "ccac_dq_issues.csv")

# ---------------------------------------------------------------- Methods
with tabs[7]:
    st.markdown((ROOT / "docs" / "methods.md").read_text() if (ROOT / "docs" / "methods.md").exists() else "")
    for f in sorted(P.glob("*.csv")):
        st.download_button(f.name, f.read_bytes(), f.name, key=f.name)
