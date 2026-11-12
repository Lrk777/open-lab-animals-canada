"""Regression tests pinned to published CCAC figures. They run against data/processed, so CI
rebuilds the processed files from the pinned raw inputs before running pytest."""

import pandas as pd
import pytest

from olac.analysis.index import index_scores, load_rubric, scores_long, weight_sensitivity
from olac.paths import PROCESSED

needs_data = pytest.mark.skipif(not (PROCESSED / "ccac_type_year.csv").exists(), reason="pipeline not run")


@needs_data
def test_nhp_counts_match_published_reports():
    t = pd.read_csv(PROCESSED / "ccac_type_year.csv")
    nhp = t[t.animal_type == "Nonhuman primates"].set_index("year").n_animals
    # Figures printed in CCAC Animal Data Reports, Table 1.
    assert nhp[2015] == 4942
    assert nhp[2017] == 6412
    assert nhp[2018] == 8522
    assert nhp[2024] == 7826
    assert nhp[2025] == 8889


@needs_data
def test_table1_rows_sum_to_reported_total():
    t = pd.read_csv(PROCESSED / "ccac_type_year.csv").groupby("year").n_animals.sum()
    r = pd.read_csv(PROCESSED / "ccac_reported_totals.csv").set_index("year").reported_total
    assert (t == r).all()


@needs_data
def test_excel_species_reconcile_to_pdf_types():
    sp = pd.read_csv(PROCESSED / "ccac_species_year.csv")
    t = pd.read_csv(PROCESSED / "ccac_type_year.csv")
    a = sp[sp.animal_type == "Nonhuman primates"].groupby("year").n_animals.sum()
    b = t[t.animal_type == "Nonhuman primates"].set_index("year").n_animals
    assert (a == b.loc[a.index]).all()


@needs_data
def test_crosswalk_gives_one_label_per_taxon():
    xw = pd.read_csv(PROCESSED / "ccac_species_crosswalk.csv")
    assert xw.groupby(["animal_type", "species_key"]).canonical_label.nunique().max() == 1


def test_index_is_bounded_and_ordered():
    df = scores_long(load_rubric())
    s = index_scores(df)
    assert ((s >= 0) & (s <= 100)).all()
    assert s.idxmin() == "canada"


def test_weight_sensitivity_probabilities_sum_to_one():
    sens = weight_sensitivity(scores_long(load_rubric()), n=500)
    cols = [c for c in sens.columns if c.startswith("p_rank_")]
    assert sens[cols].sum(axis=1).round(6).eq(1).all()
    assert sens[cols].sum(axis=0).round(6).eq(1).all()
