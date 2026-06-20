"""engine/forecastbench/structural_gate.py — the HOME-TURF leak-free test ($0, no LLM).

The Manifold gate said field-level features don't predict event-timing outcomes (the wrong question
class). This asks the question the data layer is actually built for, on the cleanest leak-free substrate
in the repo (papers.primary_category — structured, no keyword-matching noise):

    Do the repo's LEADING structural features (detrended surprise-σ, on the share-of-literature
    trajectory) predict which arXiv subfields GAIN share over the next 3 years — and crucially, do
    they add anything OVER naive momentum (the 'price') out-of-sample?

That last clause is the whole forecasting thesis in miniature: is there a leading signal beyond the
trend already in the price. Panel = (category × origin-year). Features use only data <= T; the label
(did share rise over T+1..T+3) uses data > T but is the OUTCOME, not a feature — so it's leak-free.
Temporal split on origin year: fit on early origins, score on later ones.

CLI:
    uv run python -m engine.forecastbench.structural_gate --origin-split 2019
"""
from __future__ import annotations

import argparse
import math

import numpy as np

from engine.db import connect
from engine.forecastbench.edge_gate_stat import _brier, _fit_logistic, _predict


def _panel(conn, *, min_year: int = 2012, max_year: int = 2023):
    """Per-(category, year) share of total arXiv literature, from one indexed scan."""
    rows = conn.execute(
        "SELECT primary_category AS cat, CAST(substr(published,1,4) AS INT) AS yr, COUNT(*) AS n "
        "FROM papers WHERE primary_category != '' AND substr(published,1,4) GLOB '[0-9][0-9][0-9][0-9]' "
        "GROUP BY cat, yr"
    ).fetchall()
    by_cat: dict[str, dict[int, int]] = {}
    totals: dict[int, int] = {}
    for r in rows:
        y = r["yr"]
        if y < min_year or y > max_year:
            continue
        by_cat.setdefault(r["cat"], {})[y] = r["n"]
        totals[y] = totals.get(y, 0) + r["n"]
    share = {c: {y: (n / totals[y]) for y, n in ys.items() if totals.get(y)} for c, ys in by_cat.items()}
    return share, totals


def _surprise_sigma(years, logs) -> float:
    if len(years) < 4:
        return 0.0
    x = np.array(years[:-1], float); y = np.array(logs[:-1], float)
    slope, intercept = np.polyfit(x, y, 1)
    resid = y - (slope * x + intercept)
    s = float(resid.std()) or 1e-6
    return float((logs[-1] - (slope * years[-1] + intercept)) / s)


def _rows(share, *, origins, horizon=3, min_share=2e-4):
    """Build (features, label, origin) examples. Label = mean share over T+1..T+horizon > share[T]."""
    out = []
    eps = 1e-9
    for cat, ys in share.items():
        for T in origins:
            if T not in ys or ys[T] < min_share:
                continue
            hist_years = [y for y in range(T - 5, T + 1) if y in ys]
            if len(hist_years) < 4:
                continue
            fut = [ys[y] for y in range(T + 1, T + 1 + horizon) if y in ys]
            if len(fut) < horizon:
                continue
            logs = [math.log(ys[y] + eps) for y in hist_years]
            mom1 = math.log((ys[T] + eps) / (ys.get(T - 1, ys[T]) + eps))
            mom2 = math.log((ys.get(T - 1, ys[T]) + eps) / (ys.get(T - 2, ys[T]) + eps))
            sigma = _surprise_sigma(hist_years, logs)
            label = 1.0 if (sum(fut) / len(fut)) > ys[T] else 0.0
            out.append({
                "cat": cat, "T": T, "label": label,
                "log_share": math.log(ys[T] + eps), "mom1": mom1, "mom2": mom2, "sigma": sigma,
            })
    return out


def run(*, origin_split: int = 2019, log=print) -> dict:
    conn = connect()
    share, _ = _panel(conn)
    origins = list(range(2014, 2021))  # T values; label horizon stays within the corpus (<=2023)
    rows = _rows(share, origins=origins)
    train = [r for r in rows if r["T"] < origin_split]
    test = [r for r in rows if r["T"] >= origin_split]
    if len(train) < 30 or len(test) < 15:
        log(f"too few rows (train {len(train)}, test {len(test)}).")
        return {}

    def design(rs, cols):
        X = np.array([[1.0] + [r[c] for c in cols] for r in rs])
        y = np.array([r["label"] for r in rs])
        return X, y

    base_rate = float(np.mean([r["label"] for r in test]))
    # standardize predictors on train
    cols_all = ["log_share", "mom1", "mom2", "sigma"]
    mu = {c: np.mean([r[c] for r in train]) for c in cols_all}
    sd = {c: (np.std([r[c] for r in train]) or 1e-9) for c in cols_all}
    for r in train + test:
        for c in cols_all:
            r[c] = (r[c] - mu[c]) / sd[c]

    # 1) base rate (no features)
    b_baserate = _brier(np.full(len(test), base_rate), np.array([r["label"] for r in test]))
    # 2) momentum-only (the "price" — trend already visible)
    mom_cols = ["log_share", "mom1", "mom2"]
    Xtr, ytr = design(train, mom_cols); Xte, yte = design(test, mom_cols)
    w = _fit_logistic(Xtr, ytr, l2=1.0, iters=1500); p_mom = _predict(Xte, w)
    b_mom = _brier(p_mom, yte)
    # 3) momentum + surprise-σ (the leading signal beyond price)
    Xtr2, _ = design(train, mom_cols + ["sigma"]); Xte2, _ = design(test, mom_cols + ["sigma"])
    w2 = _fit_logistic(Xtr2, ytr, l2=1.0, iters=1500); p_full = _predict(Xte2, w2)
    b_full = _brier(p_full, yte)

    log("\n── structural gate (arXiv subfield share-growth, leak-free) ──")
    log(f"   panel: {len(rows)} (category×origin) rows · train {len(train)} (T<{origin_split}) · test {len(test)} (T>={origin_split})")
    log(f"   base rate (test)     : {base_rate:.2f} 'share rose'")
    log(f"   base-rate     Brier  : {b_baserate:.4f}")
    log(f"   momentum-only Brier  : {b_mom:.4f}   (the 'price' — trend already visible at T)")
    log(f"   momentum+σ    Brier  : {b_full:.4f}")
    log(f"   leading edge (σ)     : {b_mom - b_full:+.4f}   (positive ⇒ surprise-σ adds signal BEYOND momentum)")
    log(f"   features vs baserate : {b_baserate - b_full:+.4f}")
    verdict = ("ALIVE — the leading feature adds out-of-sample signal beyond the trend. The features have real "
               "predictive content on structural questions; the Manifold null was question-class, not feature death."
               if (b_mom - b_full) > 0.002
               else "FLAT — surprise-σ adds nothing beyond momentum here. The leading channel is not beating price "
               "OOS even on home turf.")
    log(f"   verdict              : {verdict}")
    return {"n_test": len(test), "base_rate": b_baserate, "mom": b_mom, "full": b_full,
            "leading_edge": b_mom - b_full}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Leak-free structural gate: do leading features beat momentum? ($0)")
    ap.add_argument("--origin-split", type=int, default=2019)
    a = ap.parse_args()
    run(origin_split=a.origin_split)
