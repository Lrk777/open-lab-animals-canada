2026-11-10

Canadian Council on Animal Care
190 O'Connor St., Suite 800, Ottawa, ON K2P 2R3

**Re: Data-quality observations on the CCAC Animal Data Reports, 2011-2025**

Dear CCAC Animal Use Data team,

I am a data science student at York University. As part of an open-data project on animal-based science in Canada, I converted the CCAC Animal Data Reports (2011-2025) and sortable Excel files (2019-2025) into a machine-readable time series and ran automated consistency checks. The headline totals reconcile: in every year the animal-type rows sum to the published total, the invasiveness and purpose tables agree, and the Excel files match the PDF reports. Thank you for maintaining that consistency.

The checks did surface labelling issues that make the data harder to analyse across years. I am sharing them in case they are useful for the revised animal use data collection planned for 2030. The complete, reproducible log is attached (`ccac_dq_issues.csv`, 234 entries) with the code that produced it.

**Issues that may warrant correction**

1. The worksheet in the 2025 Excel File 2 is labelled '2024 Excel 2'. The data match the 2025 report, so this appears to be a label only.
2. Nonhuman primates without a species: 2019: 62, 2020: 44, 2021: 137, 2022: 168, 2023: 506, 2024: 97, 2025: 500. Most are recorded as 'Monkeys, Marmoset' alongside 'Monkeys, Marmosets, Common (Callithrix jacchus)', and in 2025 as 'Monkeys, Baboon' (500 animals). Species-level attribution matters for primates because housing standards differ by species.
3. 34 species appear in File 2 but not in File 1 in the same year, and 2 differ only by capitalisation between the two files.

**Issues affecting comparisons across years**

4. 68 cases where the same scientific name is listed under a different common name than in the previous year (e.g. Saimiri oerstedii: 'Squirrels Central American' in 2024, 'Squirrel Central American' in 2025).
5. 42 scientific names listed under more than one common name within a year. Some may be breeds or subspecies (Sus scrofa: wild boar and Yucatan), which could be coded separately.
6. Species names with stray line breaks or repeated spaces: 2019: 123, 2020: 93, 2021: 80, 2022: 89, 2023: 89, 2024: 70, 2025: 73.
7. File 2 Nonhuman primates total is exactly 10,857 in both 2024 and 2025 although the species breakdown differs; worth confirming.

**Suggestions**

- Publish a stable species code (for example ITIS TSN or NCBI Taxonomy ID) alongside the common name.
- Publish a single long-format CSV covering all years, alongside the current files.
- Re-host the 2011-2018 reports on ccac.ca. I obtained them from a third-party mirror.
- State in the data files whether animals on multi-year protocols are counted once or every year.

I am happy to share the cleaned dataset and species crosswalk with the CCAC, and I would welcome corrections if I have misread any part of the data.

Sincerely,

[Name], [Program], York University
[email]

Attachments: ccac_dq_issues.csv; docs/data_quality_report.md; ccac_species_crosswalk.csv