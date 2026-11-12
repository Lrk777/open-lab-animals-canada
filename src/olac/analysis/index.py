"""Transparency Index: weighted rubric score per jurisdiction plus weight-sensitivity analysis.

The weight sensitivity answers the obvious reviewer question, "did you pick the weights to
get the ranking you wanted?": we redraw weights from a Dirichlet distribution 10,000 times and
report how often each jurisdiction lands in each rank.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import yaml

from olac.paths import CONFIG, PROCESSED

MAX_SCORE = 3


def load_rubric() -> dict:
    return yaml.safe_load((CONFIG / "transparency_rubric.yaml").read_text())


def scores_long(rubric: dict) -> pd.DataFrame:
    rows = []
    for j, dims in rubric["jurisdictions"].items():
        for d, cell in dims.items():
            rows.append(
                {
                    "jurisdiction": j,
                    "dimension": d,
                    "score": cell["score"],
                    "evidence": cell["evidence"],
                    "status": cell["status"],
                    "weight": rubric["dimensions"][d]["weight"],
                    "question": rubric["dimensions"][d]["question"],
                }
            )
    df = pd.DataFrame(rows)
    missing = set(rubric["dimensions"]) - set(df.dimension)
    if missing:
        raise ValueError(f"dimensions without scores: {missing}")
    return df


def index_scores(df: pd.DataFrame, weights: pd.Series | None = None) -> pd.Series:
    w = weights if weights is not None else df.groupby("dimension").weight.first()
    m = df.pivot(index="jurisdiction", columns="dimension", values="score")[w.index]
    return (m @ w) / (MAX_SCORE * w.sum()) * 100


def weight_sensitivity(df: pd.DataFrame, n: int = 10_000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dims = sorted(df.dimension.unique())
    m = df.pivot(index="jurisdiction", columns="dimension", values="score")[dims]
    w = rng.dirichlet(np.ones(len(dims)), size=n)
    s = (m.values @ w.T) / MAX_SCORE * 100  # jurisdictions x draws
    ranks = (-s).argsort(axis=0).argsort(axis=0) + 1
    out = []
    for i, j in enumerate(m.index):
        row = {"jurisdiction": j, "score_p05": np.percentile(s[i], 5), "score_p95": np.percentile(s[i], 95)}
        for r in range(1, len(m.index) + 1):
            row[f"p_rank_{r}"] = float((ranks[i] == r).mean())
        out.append(row)
    return pd.DataFrame(out)


def run() -> pd.DataFrame:
    rubric = load_rubric()
    df = scores_long(rubric)
    idx = index_scores(df).rename("index_0_100").round(1)
    sens = weight_sensitivity(df)
    unverified = df[df.status != "verified"].groupby("jurisdiction").size().rename("unverified_cells")
    summary = (
        idx.to_frame()
        .join(sens.set_index("jurisdiction"))
        .join(unverified)
        .fillna({"unverified_cells": 0})
        .sort_values("index_0_100", ascending=False)
    )
    summary["rank"] = range(1, len(summary) + 1)
    # Rounded so committed outputs are byte-identical across platforms' floating-point libraries.
    summary = summary.round(4)
    df.to_csv(PROCESSED / "transparency_scores.csv", index=False)
    summary.reset_index().to_csv(PROCESSED / "transparency_index.csv", index=False)
    print(summary.round(2).to_string())
    return summary


if __name__ == "__main__":
    run()
