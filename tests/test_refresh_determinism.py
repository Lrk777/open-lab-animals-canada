"""Regression tests for the Nov 2026 refresh bugs (non-deterministic labels, failed fetches as 0)."""

import pandas as pd

from olac.audit import corpus
from olac.ingest.ccac import species_crosswalk


def test_crosswalk_label_does_not_depend_on_row_order():
    rows = [
        {"animal_type": "Other", "scientific_name": "Lynx rufus", "species": "Bobcat", "year": 2025},
        {"animal_type": "Other", "scientific_name": "Lynx rufus", "species": "Lynx, Red", "year": 2025},
        {"animal_type": "Other", "scientific_name": "Lynx rufus", "species": "Bobcat", "year": 2019},
    ]
    a = species_crosswalk(pd.DataFrame(rows))
    b = species_crosswalk(pd.DataFrame(rows[::-1]))
    assert set(a.canonical_label) == set(b.canonical_label) == {"Lynx, Red"}


def test_failed_fetch_keeps_previous_result(tmp_path, monkeypatch):
    monkeypatch.setattr(corpus, "PROCESSED", tmp_path)
    pd.DataFrame(
        {"pmcid": ["PMC1", "PMC2"], "n_methods_chars": [18765, 900],
         "uses_nhp": [True, False], "is_neuro": [False, False], "has_methods": [True, True]}
    ).to_csv(tmp_path / "corpus.csv", index=False)
    new = pd.DataFrame(
        {"pmcid": ["PMC1", "PMC2", "PMC3"], "fetch_ok": [False, True, False],
         "n_methods_chars": [0, 950, 0], "uses_nhp": [False, False, False],
         "is_neuro": [False, False, False], "has_methods": [False, True, False]}
    )
    out = corpus._keep_previous_on_failure(new).set_index("pmcid")
    assert out.at["PMC1", "n_methods_chars"] == 18765 and bool(out.at["PMC1", "has_methods"])
    assert out.at["PMC2", "n_methods_chars"] == 950  # successful fetch wins
    assert out.at["PMC3", "n_methods_chars"] == 0 and not out.at["PMC3", "fetch_ok"]
