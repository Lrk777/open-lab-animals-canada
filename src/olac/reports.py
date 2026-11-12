"""Generate outreach documents from the processed data so every number stays in sync.

  python -m olac.reports

Writes:
  policy/ccac_data_quality_letter.md      formal submission of the data-quality log to CCAC
  policy/policy_brief.md                  2-page brief for journalists, MPs, NGOs
  policy/consultation_submission.md       template for a federal consultation / committee brief
  policy/university_right_of_reply.md     email inviting each university to correct its scorecard
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from olac.paths import PROCESSED, ROOT

POLICY = ROOT / "policy"


def _csv(name: str) -> pd.DataFrame | None:
    p = PROCESSED / f"{name}.csv"
    return pd.read_csv(p) if p.exists() else None


def facts() -> dict:
    f: dict = {"today": date.today().isoformat()}
    t = _csv("ccac_type_year")
    nhp = t[t.animal_type == "Nonhuman primates"].set_index("year").n_animals
    f.update(nhp_2025=int(nhp[2025]), nhp_2024=int(nhp[2024]), nhp_2012=int(nhp[2012]),
             nhp_2023=int(nhp[2023]), nhp_growth=nhp[2025] / nhp[2012] - 1)
    sp = _csv("ccac_species_year")
    p = sp[sp.animal_type == "Nonhuman primates"]
    f["rhesus_2025"] = int(p[(p.year == 2025) & (p.scientific_name == "Macaca mulatta")].n_animals.sum())
    f["cyno_2025"] = int(p[(p.year == 2025) & (p.scientific_name == "Macaca fascicularis")].n_animals.sum())
    pau = _csv("nhp_pau_year")
    y = pau[pau.year == 2025]
    f["regulatory_share_2025"] = float(y[y.pau == 3].n_animals.sum() / y.n_animals.sum())
    f["fundamental_share_2025"] = float(y[y.pau == 1].n_animals.sum() / y.n_animals.sum())
    comp = _csv("nhp_comparison_with_sensitivity")
    c = comp[comp.year == 2025].set_index("jurisdiction").per_million
    f.update(pc_ca=c.get("canada"), pc_ca_lab=c.get("canada_lab_ci_c_e"), pc_uk=c.get("uk"), pc_us=c.get("us"))
    eu = comp[(comp.jurisdiction == "eu")].sort_values("year").iloc[-1]
    f.update(pc_eu=eu.per_million, eu_year=int(eu.year))
    idx = _csv("transparency_index").set_index("jurisdiction")
    f["idx"] = idx.index_0_100.to_dict()
    f["idx_last_prob"] = float(idx.loc["canada", "p_rank_4"])
    dq = _csv("dq_issues")
    f["dq_counts"] = dq.severity.value_counts().to_dict()
    f["dq"] = dq
    au = _csv("audit_rules")
    if au is not None:
        r = au.groupby("field").reported.mean()
        f["audit_n"] = au.pmcid.nunique()
        f["audit_rates"] = r.to_dict()
    sc = _csv("scorecard")
    if sc is not None:
        f["scorecard"] = sc
    fund = _csv("funding_by_category_year")
    if fund is not None:
        d = fund[(fund.fiscal_year >= 2020) & (fund.fiscal_year <= 2024)]
        tot = d.groupby("category").amount_cad.sum() / 5 / 1e6
        f["fund_nhp_m"] = tot.get("nhp_research", 0)
        f["fund_nam_m"] = tot.get("non_animal_methods", 0)
    return f


def ccac_letter(f: dict) -> str:
    dq = f["dq"]
    pick = lambda cid: dq[dq.check_id == cid]  # noqa: E731
    sheet = pick("sheet_label_year")
    nhp_unspec = pick("nhp_unspecified_species")
    dup = pick("duplicate_scientific_name")
    drift = pick("cross_year_label_drift")
    f2only = pick("file2_without_file1")
    case = pick("label_case_mismatch")
    ws = pick("name_whitespace")
    same = pick("identical_consecutive_total")
    lines = [
        f"{f['today']}",
        "",
        "Canadian Council on Animal Care",
        "190 O'Connor St., Suite 800, Ottawa, ON K2P 2R3",
        "",
        "**Re: Data-quality observations on the CCAC Animal Data Reports, 2011-2025**",
        "",
        "Dear CCAC Animal Use Data team,",
        "",
        "I am a data science student at York University. As part of an open-data project on animal-based "
        "science in Canada, I converted the CCAC Animal Data Reports (2011-2025) and sortable Excel files "
        "(2019-2025) into a machine-readable time series and ran automated consistency checks. The "
        "headline totals reconcile: in every year the animal-type rows sum to the published total, the "
        "invasiveness and purpose tables agree, and the Excel files match the PDF reports. Thank you for "
        "maintaining that consistency.",
        "",
        "The checks did surface labelling issues that make the data harder to analyse across years. I am "
        "sharing them in case they are useful for the revised animal use data collection planned for 2030. "
        "The complete, reproducible log is attached (`ccac_dq_issues.csv`, "
        f"{len(dq)} entries) with the code that produced it.",
        "",
        "**Issues that may warrant correction**",
        "",
    ]
    if len(sheet):
        lines.append(f"1. The worksheet in the 2025 Excel File 2 is labelled '{sheet.iloc[0].observed}'. "
                     "The data match the 2025 report, so this appears to be a label only.")
    lines += [
        f"2. Nonhuman primates without a species: {', '.join(f'{int(r.year)}: {int(r.observed)}' for _, r in nhp_unspec.iterrows())}. "
        "Most are recorded as 'Monkeys, Marmoset' alongside 'Monkeys, Marmosets, Common (Callithrix jacchus)', "
        "and in 2025 as 'Monkeys, Baboon' (500 animals). Species-level attribution matters for primates because "
        "housing standards differ by species.",
        f"3. {len(f2only)} species appear in File 2 but not in File 1 in the same year, and {len(case)} differ "
        "only by capitalisation between the two files.",
        "",
        "**Issues affecting comparisons across years**",
        "",
        f"4. {len(drift)} cases where the same scientific name is listed under a different common name than in the "
        "previous year (e.g. Saimiri oerstedii: 'Squirrels Central American' in 2024, 'Squirrel Central American' "
        "in 2025).",
        f"5. {len(dup)} scientific names listed under more than one common name within a year. Some may be breeds "
        "or subspecies (Sus scrofa: wild boar and Yucatan), which could be coded separately.",
        f"6. Species names with stray line breaks or repeated spaces: {', '.join(f'{int(r.year)}: {int(r.observed)}' for _, r in ws.iterrows())}.",
    ]
    if len(same):
        lines.append(f"7. {same.iloc[0].detail}.")
    lines += [
        "",
        "**Suggestions**",
        "",
        "- Publish a stable species code (for example ITIS TSN or NCBI Taxonomy ID) alongside the common name.",
        "- Publish a single long-format CSV covering all years, alongside the current files.",
        "- Re-host the 2011-2018 reports on ccac.ca. I obtained them from a third-party mirror.",
        "- State in the data files whether animals on multi-year protocols are counted once or every year.",
        "",
        "I am happy to share the cleaned dataset and species crosswalk with the CCAC, and I would welcome "
        "corrections if I have misread any part of the data.",
        "",
        "Sincerely,",
        "",
        "[Name], [Program], York University",
        "[email]",
        "",
        "Attachments: ccac_dq_issues.csv; docs/data_quality_report.md; ccac_species_crosswalk.csv",
    ]
    return "\n".join(lines)


def policy_brief(f: dict) -> str:
    i = f["idx"]
    audit = ""
    if "audit_rates" in f:
        r = f["audit_rates"]
        audit = (
            f"- **Published papers omit key welfare details.** In {f['audit_n']} open-access Canadian primate "
            f"research papers (2010-2026, mostly neuroscience), housing conditions were reported in "
            f"{r.get('housing_type', 0):.0%}, whether fluid was controlled or unrestricted in "
            f"{r.get('fluid_or_food_control', 0):.0%}, fluid amounts or monitoring in "
            f"{r.get('fluid_control_detail', 0):.0%}, and the number of surgeries per animal in "
            f"{r.get('surgery_count', 0):.0%}. Reporting did not change detectably after ARRIVE 2.0 (2020). "
            "(Automated baseline; human validation in progress.)"
        )
    fund = ""
    if "fund_nhp_m" in f:
        fund = (f"- **Funding.** CIHR and NSERC awards that name primates as study animals averaged about "
                f"${f['fund_nhp_m']:.0f}M a year in 2020-2024, against about ${f['fund_nam_m']:.0f}M for "
                "projects using organoids, organs-on-chips, stem-cell and other non-animal methods "
                "(keyword classification; see methods).")
    return f"""# Canada's animal research data gap

*Open Lab Animals Canada, policy brief, {f['today']}*

## Summary

Canada reports less about animal-based science than the UK, the EU or the US, and what it reports is hard to
use. Primate use is rising. Most of it is regulatory testing, not university neuroscience. Fixing
transparency is cheap, has precedent abroad, and is something the research sector itself has called for.

## Key findings

- **Primate use is rising.** {f['nhp_2025']:,} nonhuman primates were reported in 2025, {f['nhp_growth']:+.0%} since 2012,
  with a peak of {f['nhp_2023']:,} in 2023. Cynomolgus macaques ({f['cyno_2025']:,}) dominate; rhesus macaques, the species in
  the York University investigation, numbered {f['rhesus_2025']:,}.
- **Most primate use is regulatory testing.** {f['regulatory_share_2025']:.0%} of primate uses in 2025 were for regulatory
  testing and {f['fundamental_share_2025']:.0%} for fundamental research.
- **Per person, Canada uses primates at US levels and several times the European rate.** About
  {f['pc_ca']:.0f} per million people in 2025 ({f['pc_ca_lab']:.0f} counting only laboratory species in higher
  invasiveness categories), against {f['pc_us']:.0f} in the US, {f['pc_uk']:.0f} in Great Britain and {f['pc_eu']:.0f} in the
  EU ({f['eu_year']}). Counting rules differ, but the gap with Europe survives the conservative comparison.
- **Canada ranks last on transparency.** On a 12-dimension index Canada scores {i['canada']:.0f}/100, against
  {i['uk']:.0f} (GB), {i['eu']:.0f} (EU) and {i['us']:.0f} (US). Canada ranks last in {f['idx_last_prob']:.0%} of 10,000 random
  re-weightings and never ranks in the top two.
- **The official data have labelling problems.** An audit found {f['dq_counts'].get('warning', 0)} labelling and structure
  issues (species renamed between years, primates recorded without a species, a mislabelled 2025 file).
{audit}
{fund}

## Recommendations

1. **Publish institution-level statistics.** The US already publishes per-facility reports. The CCAC
   could publish counts by certified institution, starting with primates, dogs and cats.
2. **Report actual severity, not only prospective categories**, as in the UK and the EU.
3. **Report primate origin**: supplier country, generation, and whether animals are reused.
4. **Create a Canadian Openness Agreement**, as the CCAC itself proposes, modelled on the UK Concordat.
5. **Make ARRIVE 2.0 reporting a condition of CIHR/NSERC-funded animal research**, including housing and
   fluid-control details for primates.
6. **Track replacement funding**: report annually how much CIHR/NSERC money goes to non-animal methods.

## About

Data, code and methods: [repository link]. All figures are reproducible from public sources. Contact: [email].
"""


def consultation(f: dict) -> str:
    return f"""# Submission to [consultation / committee name]

**Submitted by:** [Name], data science student, York University (individual submission)
**Date:** {f['today']}
**Topic:** Transparency of animal-based research data in Canada

## 1. Who I am and what I did

I built Open Lab Animals Canada, an open, reproducible dataset and analysis of Canadian animal-use
statistics (CCAC, 2011-2025), compared with Great Britain, the EU and the US. All code and data are public at
[repository link].

## 2. Evidence

1. Canada scores {f['idx']['canada']:.0f}/100 on a 12-dimension transparency index, last of four jurisdictions
   (GB {f['idx']['uk']:.0f}, EU {f['idx']['eu']:.0f}, US {f['idx']['us']:.0f}). The ranking holds under 10,000 random weightings.
2. Canada reported {f['nhp_2025']:,} nonhuman primates in 2025 ({f['nhp_growth']:+.0%} since 2012), about {f['pc_ca']:.0f} per million people
   against {f['pc_uk']:.0f} in Great Britain.
3. National data are published only as totals, by a voluntary body, for certified institutions only.

## 3. Recommendations

[Pick two or three recommendations from the policy brief that fit the consultation's mandate; for a Health
Canada or ECCC consultation on alternatives, prioritise replacement-funding tracking and regulatory-testing
data, because {f['regulatory_share_2025']:.0%} of primate uses are regulatory.]

## 4. Offer

I am happy to provide the dataset, answer questions, or present the analysis.
"""


def right_of_reply(f: dict) -> str:
    return """Subject: Draft openness score for [University] - invitation to review before publication

Dear [Animal Care Committee chair / Director, Animal Care Services],

I am a York University data science student building an open scorecard of how Canadian universities
communicate about research involving animals. The rubric follows the CCAC's Institutional Transparency
guidance and the UK Concordat on Openness, and every point is linked to a page on your own website.

Your institution's draft score is [score]/100 (grade [grade]). The attached sheet lists each indicator, the
page we found, and the quoted text. Automated crawling can miss pages, so before anything is published I
would be grateful if you could tell me:

1. any indicator we marked as missing that your website does cover (with the URL), and
2. any page we cited that you consider out of date.

I will publish corrections with the scorecard and note that your institution reviewed its entry. If I do
not hear back within [21 days], the score will be published as "not reviewed by the institution".

Thank you for your time.

[Name]
[Program], York University
[email]
"""


def run() -> None:
    POLICY.mkdir(exist_ok=True)
    f = facts()
    (POLICY / "ccac_data_quality_letter.md").write_text(ccac_letter(f))
    (POLICY / "policy_brief.md").write_text(policy_brief(f))
    (POLICY / "consultation_submission.md").write_text(consultation(f))
    (POLICY / "university_right_of_reply.md").write_text(right_of_reply(f))
    print("wrote", ", ".join(p.name for p in sorted(POLICY.glob("*.md"))))


if __name__ == "__main__":
    run()
