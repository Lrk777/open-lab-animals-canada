"""Build dashboard/index.html from the committed tables in data/processed (no network, no extra packages).

Usage: python dashboard/build.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from _lib import page

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
LABEL_FIX = {"Ccac": "CCAC", "Nhp": "Primate", "Yoy outlier": "Year-over-year outlier", "File2 without file1": "Species in File 2 but not File 1",
             "Type missing from table1": "Animal type missing from Table 1", "Anaesthesia analgesia": "Anaesthesia / analgesia",
             "Inclusion exclusion": "Inclusion / exclusion criteria", "Animal age or weight": "Animal age or weight"}


def nice(raw: str) -> str:
    out = raw.replace("_", " ").capitalize()
    for k, v in LABEL_FIX.items():
        out = out.replace(k, v)
    return out


NAMES = {"canada": "Canada", "us": "United States", "uk": "Great Britain", "eu": "EU"}
COLORS = {"canada": "--c1", "us": "--c2", "uk": "--c3", "eu": "--c4"}


def build_data() -> dict:
    comp = pd.read_csv(P / "nhp_comparison.csv")
    years = list(range(int(comp.year.min()), int(comp.year.max()) + 1))
    series = []
    for j in ["canada", "us", "uk", "eu"]:
        s = comp[comp.jurisdiction == j].set_index("year")
        series.append({"key": j, "name": NAMES[j], "color": COLORS[j], "measure": s.measure.iloc[0],
                       "vals": [None if y not in s.index else round(float(s.per_million[y]), 1) for y in years],
                       "counts": [None if y not in s.index else int(s.nhp[y]) for y in years]})
    can = comp[comp.jurisdiction == "canada"].set_index("year")
    latest = int(can.index.max())

    pau = pd.read_csv(P / "nhp_pau_year.csv")
    purposes = {int(y): [{"label": r.pau_label, "n": int(r.n_animals)} for r in g.sort_values("n_animals", ascending=False).itertuples()]
                for y, g in pau.groupby("year")}

    ti = pd.read_csv(P / "transparency_index.csv").sort_values("index_0_100", ascending=False)
    transp = [{"key": r.jurisdiction, "name": NAMES[r.jurisdiction], "v": float(r.index_0_100), "lo": round(float(r.score_p05), 1),
               "hi": round(float(r.score_p95), 1), "p_last": float(r.p_rank_4), "rank": int(r.rank)} for r in ti.itertuples()]

    its = pd.read_csv(P / "its_results.csv").sort_values("rate_post", ascending=False)
    audit = [{"field": nice(r.field), "pre": float(r.rate_pre), "post": float(r.rate_post),
              "p": float(r.p_level_holm)} for r in its.itertuples()]
    improved = int((its.p_level_holm < 0.05).sum())

    dq = pd.read_csv(P / "dq_issues.csv")
    dq_counts = (dq.groupby(["check_id", "severity"]).size().reset_index(name="n").sort_values("n", ascending=False))
    dq_rows = [{"check": nice(r.check_id), "severity": r.severity, "n": int(r.n)} for r in dq_counts.itertuples()]

    us = comp[(comp.jurisdiction == "us") & (comp.year == latest)]
    uk = comp[(comp.jurisdiction == "uk") & (comp.year == latest)]
    return {
        "years": years, "series": series, "purposes": purposes, "transparency": transp, "audit": audit,
        "audit_papers": int(its.n_papers.iloc[0]), "improved": improved, "n_items": len(its), "dq": dq_rows,
        "dq_warnings": int((dq.severity == "warning").sum()), "dq_review": int((dq.severity == "review").sum()),
        "kpi": {"year": latest, "nhp": int(can.nhp[latest]), "per_million": float(can.per_million[latest]),
                "us": float(us.per_million.iloc[0]), "uk": float(uk.per_million.iloc[0]),
                "nhp_2012": int(can.nhp[2012]), "canada_index": next(t["v"] for t in transp if t["key"] == "canada")},
    }


BODY = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,800&family=Inter:wght@400;500;600&display=swap">
<style>
:root{--surface:#f5f1ea;--card:#f5f1ea;--ink:#1d1a16;--ink2:#4f4a42;--muted:#6e675c;--grid:#e4ddd1;--line:#cfc6b6;
--c1:#b3261e;--c2:#3b5b8c;--c3:#2f7d6d;--c4:#a87700;--gray:#a39a8b;--lo:#e8c9c4}
@media (prefers-color-scheme:dark){:root{--surface:#191714;--card:#191714;--ink:#efe9df;--ink2:#c9c0b2;--muted:#9d9486;--grid:#2e2a25;--line:#433d35;
--c1:#e0574b;--c2:#7f9fd1;--c3:#4fb39d;--c4:#d9a52a;--gray:#6f685d;--lo:#5a2a26}}
body{font-family:Inter,system-ui,sans-serif}
main{max-width:860px;padding-top:56px}
.kicker{font-weight:600;font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--c1);margin:0 0 14px}
h1{font-family:Fraunces,Georgia,serif;font-size:48px;line-height:1.04;font-weight:800;letter-spacing:-.015em;margin:0 0 16px}
.sub{font-size:19px;line-height:1.55;color:var(--ink2);max-width:none}
.byline{font-size:13px;color:var(--muted);border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:10px 0;margin:24px 0 36px}
.kpis{gap:0;border-top:3px solid var(--ink);margin-bottom:48px}
.kpi{background:none;border:none;border-right:1px solid var(--line);border-radius:0;padding:16px 18px 4px 0;margin-right:18px}.kpi:last-child{border-right:none;margin-right:0}
.kpi .v{font-family:Fraunces,Georgia,serif;font-size:42px;font-weight:800;color:var(--c1)}.kpi .l{font-size:13px}
.grid{grid-template-columns:1fr;gap:0}
.card{background:none;border:none;border-top:1px solid var(--line);border-radius:0;padding:30px 0 40px}
.card h2{font-family:Fraunces,Georgia,serif;font-size:30px;line-height:1.15;font-weight:600;margin:4px 0 10px}
.num{font-weight:600;font-size:12px;letter-spacing:.16em;color:var(--c1);text-transform:uppercase;margin:0}
.card p.note{font-size:15.5px;line-height:1.6;margin:0 0 16px}
svg text{font-size:12px}
@media (max-width:760px){h1{font-size:34px}.kpi{border-right:none}}
</style>
<p class="kicker">Open data investigation</p>
<h1>Primates in Canadian science</h1>
<p class="sub">Canada has no government database of animals used in research. This one is rebuilt from 15 years of Canadian Council on Animal Care reports, compared with official US, Great Britain and EU figures, and checked against 300+ published studies.</p>
<p class="byline">By Lavanya Kumar · Data 2011–2025 · Refreshed automatically every week</p>
<div class="kpis">
 <div class="kpi"><div class="v" id="k1"></div><div class="l" id="k1l"></div></div>
 <div class="kpi"><div class="v" id="k2"></div><div class="l" id="k2l"></div></div>
 <div class="kpi"><div class="v" id="k3"></div><div class="l">transparency score out of 100, lowest of 4 places compared</div></div>
 <div class="kpi"><div class="v" id="k4"></div><div class="l" id="k4l"></div></div>
</div>
<div class="grid">
 <div class="card"><p class="num">01 · Scale</p><h2>Canada now uses more primates per person than the United States</h2><p class="note">Primates per million people. Each place counts differently (Canada and the US count animals used each year; Great Britain and the EU count first use only), so the repo also runs a stricter like-for-like comparison. Canada's 2023 spike is in the official data.</p>
  <div class="legend" id="lg1"></div><div id="c1"></div><details><summary>Table</summary><div id="t1"></div></details></div>
 <div class="card"><p class="num">02 · Purpose</p><h2>About half of primate use is regulatory testing, not university research</h2><div class="controls"><label for="yr">Year</label><select id="yr"></select></div><p class="note">Reported uses by purpose. The CCAC's purpose file counts uses, so these totals are higher than the number of animals.</p><div id="c2"></div><details><summary>Table</summary><div id="t2"></div></details></div>
 <div class="card"><p class="num">03 · Transparency</p><h2>Canada publishes the least about animal use of the four places compared</h2><p class="note">Score out of 100 on 12 questions about what each place publishes. The line shows the range across 10,000 random reweightings of the questions: Canada stays last or near last in every one.</p><div id="c3"></div><details><summary>Table</summary><div id="t3"></div></details></div>
 <div class="card"><p class="num">04 · Published studies</p><h2>New reporting guidelines didn't change what studies report</h2><p class="note" id="n4"></p>
  <div class="legend"><span><i style="background:var(--gray)"></i>before ARRIVE 2.0 (2010–2019; 2020 left out as a transition year)</span><span><i style="background:var(--c1)"></i>after ARRIVE 2.0 (2021 on)</span></div>
  <div id="c4"></div><details><summary>Table</summary><div id="t4"></div></details></div>
 <div class="card"><p class="num">05 · Data quality</p><h2>The official tables are hard to compare year to year</h2><p class="note" id="n5"></p><div id="c5"></div><details><summary>Table</summary><div id="t5"></div></details></div>
</div>
<footer>Sources: Canadian Council on Animal Care annual animal data reports (2011–2025); USDA APHIS annual reports; UK Home Office statistics; EU ALURES reports. Code, method and limitations: <a href="https://github.com/Lrk777/open-lab-animals-canada">github.com/Lrk777/open-lab-animals-canada</a>.</footer>
"""

SCRIPT = r"""
const pc = v => Math.round(v * 100) + "%";
D.purposes_years = Object.keys(D.purposes).map(Number).sort((a, b) => b - a);
D.purposes_years.forEach(y => { const o = document.createElement("option"); o.value = o.textContent = y; $("#yr").appendChild(o); });
$("#yr").addEventListener("change", render);
function render() {
  const K = D.kpi;
  $("#k1").textContent = fmtN(K.nhp); $("#k1l").textContent = "primates reported in " + K.year + ", about " + (K.nhp / K.nhp_2012).toFixed(1) + "× the 2012 figure";
  $("#k2").textContent = fmtN(K.per_million); $("#k2l").textContent = "per million people in " + K.year + " (US " + fmtN(K.us) + ", Great Britain " + fmtN(K.uk) + ")";
  $("#k3").textContent = fmtN(K.canada_index);
  $("#k4").textContent = D.improved + " of " + D.n_items; $("#k4l").textContent = "reporting items that improved after ARRIVE 2.0 guidelines";
  const ser = D.series.map(s => ({name: s.name, color: css(s.color), vals: s.vals, strong: s.key === "canada", width: s.key === "canada" ? 3 : 2}));
  $("#lg1").replaceChildren(...ser.map(s => { const sp = document.createElement("span"); const i = document.createElement("i"); i.style.background = s.color; sp.append(i, s.name); return sp; }));
  lineChart("#c1", D.years, ser, {label: "Primates per million people by year", fmt: v => fmtN(v, 0), right: 150});
  table("#t1", ["Year"].concat(D.series.map(s => s.name)), D.years.map((y, i) => [y].concat(D.series.map(s => s.vals[i] == null ? "—" : fmtN(s.vals[i], 1)))));
  const yr = $("#yr").value || D.purposes_years[0], rows = D.purposes[yr], tot = rows.reduce((t, r) => t + r.n, 0);
  hbars("#c2", rows.map(r => ({label: r.label.replace(" (human/animal disease)", ""), v: r.n, color: css("--c1"), extra: [[css("--gray"), "share", pc(r.n / tot)]]})), {left: 230, metric: "uses", label: "Primate uses by purpose"});
  table("#t2", ["Purpose", "Uses", "Share"], rows.map(r => [r.label, fmtN(r.n), pc(r.n / tot)]));
  intervals("#c3", D.transparency.map(t => ({label: t.name, v: t.v, lo: t.lo, hi: t.hi, color: t.key === "canada" ? css("--c1") : css("--c2"), strong: t.key === "canada",
    extra: [[css("--gray"), "chance of ranking last", pc(t.p_last)]]})), {left: 110, metric: "score", rangeName: "5th–95th percentile", fmt: v => fmtN(v, 1)});
  table("#t3", ["Place", "Score", "Range (5–95%)", "Rank"], D.transparency.map(t => [t.name, fmtN(t.v, 1), fmtN(t.lo, 1) + "–" + fmtN(t.hi, 1), t.rank]));
  $("#n4").textContent = "Share of " + D.audit_papers + " open-access papers that report each item. A change after ARRIVE 2.0 (2020) was tested for every item; " + D.improved + " of " + D.n_items + " changed after correcting for multiple tests.";
  dumbbell("#c4", D.audit.map(a => ({label: a.field, a: a.pre, b: a.post, extra: [[css("--gray"), "adjusted p-value", a.p.toFixed(2)]]})), {left: 210, fmt: pc, aName: "before", bName: "after", label: "Reporting rates before and after ARRIVE 2.0"});
  table("#t4", ["Item", "Before", "After", "Adjusted p"], D.audit.map(a => [a.field, pc(a.pre), pc(a.post), a.p.toFixed(2)]));
  $("#n5").textContent = "The totals add up, but " + D.dq_warnings + " labelling and structure problems (red) make years hard to compare, plus " + D.dq_review + " items flagged for review (gray).";
  hbars("#c5", D.dq.map(d => ({label: d.check, v: d.n, color: d.severity === "warning" ? css("--c1") : css("--gray"), extra: [[css("--gray"), "severity", d.severity]]})), {left: 210, metric: "issues", label: "Data-quality issues by type"});
  table("#t5", ["Check", "Severity", "Issues"], D.dq.map(d => [d.check, d.severity, d.n]));
}
render();
"""


def main() -> None:
    out = ROOT / "dashboard" / "index.html"
    out.write_text(page("Primates in Canadian science, 2011–2025", BODY, SCRIPT, build_data()), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
