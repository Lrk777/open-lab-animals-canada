# Methods

This page documents how every number in the dashboard, dataset and preprint is produced.
Everything is reproducible with `make all`; raw inputs are pinned in `data/raw/manifest.json`
by SHA-256.

## 1. Canadian animal-use statistics (CCAC)

**Sources.** CCAC Animal Data Report PDFs for 2011-2025 (2019+ from ccac.ca; 2011-2018 from the
Speaking of Research mirror because ccac.ca no longer hosts them) and the sortable Excel files
for 2019-2025 (File 1: animals by species; File 2: species x Category of Invasiveness (CI) x
Purpose of Animal Use (PAU)).

**Parsing.** `src/olac/ingest/ccac.py` extracts PDF Table 1 (animal type), the CI table and the
PAU table with anchored regular expressions, and reads the Excel files by locating the header
row. Grand-total rows are separated from data rows. A species crosswalk keyed on scientific name
(`ccac_species_crosswalk.csv`) assigns one canonical label per taxon so species can be tracked
across years despite CCAC renaming them.

**Caveats carried into every chart.**
- CCAC only covers CCAC-certified institutions.
- CCAC states that data before 2012 are not comparable; 2011 is shown but excluded from trend models.
- File 2 counts *uses*: an animal used in more than one protocol is counted more than once.
- CI is assigned prospectively when a protocol is approved; it is not the actual severity experienced.

## 2. Data-quality audit

`src/olac/dq.py` runs 15 checks: arithmetic consistency (PDF totals, Excel totals, CI vs PAU),
cross-file consistency (File 1 vs File 2 by species), labelling (sheet names, whitespace,
capitalisation, the same scientific name under several common names, cross-year renaming),
attribution (primates without a species), and robust year-over-year outliers. Severity:
*error* = published numbers contradict each other; *warning* = labelling/structure problem;
*review* = unusual but possibly genuine. Output: `dq_issues.csv`, `docs/data_quality_report.md`.

## 3. International comparison

| Jurisdiction | Source | Unit |
|---|---|---|
| Great Britain | Home Office annual statistics, ODS tables 1.3 and 3.1 (2014-2025) | animals used for the first time; procedures by actual severity |
| EU27 + Norway | European Commission 2023 statistical report, Table 2 (2018, 2022, 2023) | animals used for the first time |
| United States | USDA APHIS Research Facility Annual Report Summaries FY2021-FY2025 | animals used (columns C-E) |

Counting units differ, so per-capita comparisons are shown with a conservative Canadian
sensitivity series: only laboratory genera (*Macaca, Chlorocebus, Callithrix, Papio, Saimiri,
Aotus, Saguinus*) in CI C-E, rescaled from File 2 uses to File 1 animal totals.

## 4. Transparency Index

Twelve dimensions scored 0-3 per jurisdiction in `config/transparency_rubric.yaml`, each with a
written evidence statement and a verification status. Index = weighted mean / 3 x 100.
Robustness: 10,000 Dirichlet(1,...,1) weight draws; we report the 5th-95th percentile of each
score and the probability of each rank. The SQL (dbt) and Python implementations are tested to
agree to 0.1 points.

## 5. Trends and forecast

- Structural breaks: PELT (l2 cost, penalty 0.5, minimum segment 3) on log counts 2012-2025.
- Trend: OLS on log counts, reported as an annual growth factor with p-value.
- Forecast: local linear trend structural time-series model (Kalman filter, `statsmodels`
  UnobservedComponents) on log counts, 2026-2030, with 80% and 95% intervals. With 14 annual
  observations this is a scenario, not a prediction.

## 6. University Openness Scorecard

Indicators in `config/scorecard_rubric.yaml` follow the UK Concordat on Openness commitments and
the CCAC Institutional Transparency guidance. `src/olac/scorecard/crawl.py` visits only each
university's own domain, honours robots.txt, waits 1 s between requests, uses sitemaps first and
then a keyword-guided crawl (max 40 relevant pages, 160 requests). `score.py` matches indicator
patterns only on pages that are about animal research and stores the URL and a quoted snippet
for every point. Automated scores are labelled *unverified* until a reviewer confirms each cell
in `data/scorecard/review.csv`; institutions are invited to submit corrections before publication.

## 7. Federal funding

CIHR Grants and Awards (FY2015-16 to 2025-26) and NSERC Awards (FY2020-2024) open data.
Personnel awards (scholarships, fellowships) are excluded. Titles, keywords and abstracts are
classified with the conservative regular expressions in `config/funding_lexicon.yaml`;
precision is estimated by hand-labelling `data/interim/funding_precision_sample.csv`. Results
are aggregated by institution and fiscal year only; researcher names are never written to disk.

## 8. Reporting-quality audit (ARRIVE 2.0)

**Corpus.** Europe PMC, open-access non-review articles 2010-2026 with a Canadian affiliation and
macaques/monkeys plus neural/brain/visual terms in the METHODS section. Full text (JATS XML) is
reduced to methods sections; papers are included if the methods state that monkeys were used.

**Schema.** 21 items (`src/olac/audit/schema.py`): nine ARRIVE 2.0 Essential items, ten
primate-welfare items drawn from the Recommended Set (housing, enrichment, fluid/food control and
its monitoring, implants, number of surgeries, anaesthesia/analgesia, welfare monitoring, reuse,
fate), and two oversight items.

**Extractors.** (a) A deterministic regular-expression baseline; (b) an LLM with JSON-schema
structured output. Every reported item must carry a verbatim quote; quotes that cannot be found
in the source are automatically downgraded to "not reported".

**Validation.** A stratified random sample of 80 papers (`python -m olac.audit.gold sample`) is
labelled independently by two annotators following `docs/annotation_guidelines.md`. We report
Cohen's kappa between annotators, per-item precision/recall/F1 for each extractor against the
adjudicated gold labels, and calibration of LLM confidence.

**Interrupted time series.** Paper-level logistic regression per item with terms for time, a
post-ARRIVE-2.0 level change (2021+; 2020 excluded as a washout year), and a slope change;
journal-clustered standard errors; Holm correction across items.

## 9. Ethics

Only public, aggregate information is used. No facility locations, no personal data about
researchers or staff, no leaked documents. The audit scores papers, not people, and results are
reported at the institution level at most. No human participants are involved; if surveys or
interviews are added, York University Human Participants Review Committee approval will be
sought first.
