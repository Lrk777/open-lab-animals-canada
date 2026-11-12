# Datasheet: Open Lab Animals Canada dataset

Following *Datasheets for Datasets* (Gebru et al., 2021).

## Motivation

- **Purpose.** To make Canadian statistics on animals used in science machine-readable, comparable
  across years and with other countries, and auditable. Canada has no government database of
  animal use; the only national source is the Canadian Council on Animal Care (CCAC), which
  publishes annual PDF reports and Excel files.
- **Creator.** [Name], York University, as an independent student project. No funding. No
  affiliation with the CCAC, any advocacy organisation, or any research institution named here.

## Composition

| File | Rows | Description |
|---|---|---|
| `ccac_type_year.csv` | ~210 | animals by animal type and year, 2011-2025 (PDF Table 1) |
| `ccac_ci_year.csv`, `ccac_pau_year.csv` | ~130 | national totals by Category of Invasiveness and Purpose of Animal Use |
| `ccac_species_year.csv` | ~7,000 | animals by species and year, 2019-2025 (Excel File 1) |
| `ccac_species_ci_pau.csv` | ~15,000 | species x CI x PAU uses, 2019-2025 (Excel File 2) |
| `ccac_species_crosswalk.csv` | ~2,400 | every published species label mapped to a canonical taxon |
| `dq_issues.csv` | ~230 | data-quality issues found in the CCAC releases |
| `nhp_comparison_with_sensitivity.csv` | ~60 | primates per million population: Canada, GB, EU, US |
| `transparency_scores.csv`, `transparency_index.csv` | 48 / 4 | rubric scores with evidence; index and rank probabilities |
| `funding_by_category_year.csv` | ~40 | CIHR/NSERC funding by research-approach category |
| `scorecard.csv`, `scorecard_evidence.csv` | ~26 / ~310 | university openness scores with quoted evidence (added after institutional review) |
| `corpus.csv` | ~600 | open-access Canadian primate neuroscience papers (bibliographic metadata only) |
| `audit_*.csv` | ~10,000 | paper x reporting item, with verbatim evidence quotes |

- **What an instance is.** Varies by file; each has a documented grain in `docs/methods.md`.
- **Personal data.** None. Researcher names are excluded from the funding and corpus files by
  design. Paper DOIs and titles are public bibliographic records.
- **Known gaps.** CCAC covers certified institutions only. Pre-2012 CCAC data are not comparable
  with later years. NSERC data cover 2020-2024 only. EU data are available for three years.

## Collection

- All inputs are public web documents, downloaded by `src/olac/ingest/download.py` with a
  SHA-256 manifest (`data/raw/manifest.json`). The university scorecard crawler respects
  robots.txt and rate-limits itself.
- Collection dates are recorded per file in the manifest.

## Preprocessing

Parsing, crosswalking and checks are fully scripted; see `docs/methods.md`. No values were edited
by hand. Raw files are retained so every step can be re-run.

## Uses

- **Intended:** research, journalism, policy analysis, teaching, and improving official statistics.
- **Not intended:** identifying or targeting individual researchers, staff, or facility locations.
  The project does not contain and will not accept such information.
- **Caution:** counting units differ between countries (see `config/jurisdictions.yaml`).
  Automated scorecard and audit values are provisional until marked verified.

## Distribution and maintenance

- Licence: data CC BY 4.0; code MIT.
- Hosted on Zenodo (versioned DOI) and Kaggle; refreshed weekly by GitHub Actions, with
  upstream changes logged in `CHANGELOG.md`.
- Errata and corrections: open an issue or email the maintainer. Institutions may request
  review of their scorecard entry at any time.
