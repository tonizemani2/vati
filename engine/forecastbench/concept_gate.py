"""engine/forecastbench/concept_gate.py — the DEFINITIVE leak-free test of the core signal ($0, no LLM).

The category-level gate was coarse and came back flat. This runs the test at the granularity the
detector is actually built for — per OpenAlex concept (46k) — reusing the repo's REAL detector
(engine.detector.detect) on each concept's share series TRUNCATED to an origin year T. So the
surprise-σ is computed point-in-time, leak-free, exactly as it would have been knowable at T.

The question, sharply: does the detector's departure-from-trend signal (surprise_sigma / sustained_sigma)
predict which concepts GAIN literature share over the next 3 years — and does it add anything BEYOND the
trend (Theil-Sen slope + recent momentum) that is already visible at T — out-of-sample?

    panel  = (concept × origin-year T), features use data <= T only, label uses T+1..T+3 (the outcome)
    split  = temporal on T: fit on early origins, score on later ones
    arms   = base-rate  /  momentum+slope (the 'price')  /  + detector σ (the leading signal)

Data: data/_athena_tmp/concept_year_works.csv (real OpenAlex per-concept-per-year, already cached by
engine.feeds.concept_emergence). No Athena, no FTS, no network.

CLI:
    uv run python -m engine.forecastbench.concept_gate --origin-split 2017
"""
from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

from engine.detector import detect
from engine.forecastbench.edge_gate_stat import _brier, _fit_logistic, _predict

CACHE = Path(__file__).resolve().parents[2] / "data" / "_athena_tmp" / "concept_year_works.csv"

START_YEAR = 2000
MIN_TOTAL_TO_T = 1500   # leak-free volume gate: lifetime works THROUGH T (never future size)
MIN_LAST = 50           # materially active in year T
HORIZON = 3


def _load():
    byc: dict[str, dict[int, int]] = defaultdict(dict)
    total_by_year: dict[int, int] = defaultdict(int)
    with CACHE.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row["cid"].split("/")[-1]
            yr, n = int(row["yr"]), int(row["n"])
            byc[cid][yr] = n
            total_by_year[yr] += n
    return byc, total_by_year


def _build_panel(origins):
    byc, tby = _load()
    last_complete = max(tby) - 1  # drop the provisional trailing snapshot year
    rows = []
    for cid, d in byc.items():
        def share(y):
            return 1e6 * d[y] / tby[y] if (y in d and tby.get(y)) else 0.0
        for T in origins:
            if T + HORIZON > last_complete or T not in d:
                continue
            hist = [y for y in range(START_YEAR, T + 1) if y in d and tby.get(y)]
            if len(hist) < 6:
                continue
            if sum(d[y] for y in hist) < MIN_TOTAL_TO_T or d.get(T, 0) < MIN_LAST:
                continue
            fut = [share(y) for y in range(T + 1, T + 1 + HORIZON)]
            if any(v == 0 for v in fut):
                continue
            series = [(float(y), share(y)) for y in hist]
            det = detect(series, log=True)
            if det is None:
                continue
            sT = share(T)
            mom1 = math.log((sT + 1e-9) / (share(T - 1) + 1e-9))
            mom2 = math.log((share(T - 1) + 1e-9) / (share(T - 2) + 1e-9))
            label = 1.0 if (sum(fut) / len(fut)) > sT else 0.0
            rows.append({
                "cid": cid, "T": T, "label": label,
                "log_share": math.log(sT + 1e-9), "mom1": mom1, "mom2": mom2,
                "slope": det.slope, "surprise": det.surprise_sigma, "sustained": det.sustained_sigma,
            })
    return rows, last_complete


def run(*, origin_split: int = 2017, log=print) -> dict:
    if not CACHE.exists():
        log(f"missing {CACHE} — run `python -m engine.feeds.concept_emergence --build` first.")
        return {}
    origins = list(range(2010, 2021))
    rows, last_complete = _build_panel(origins)
    train = [r for r in rows if r["T"] < origin_split]
    test = [r for r in rows if r["T"] >= origin_split]
    if len(train) < 50 or len(test) < 30:
        log(f"too few rows (train {len(train)}, test {len(test)}).")
        return {}

    cols = ["log_share", "mom1", "mom2", "slope", "surprise", "sustained"]
    mu = {c: np.mean([r[c] for r in train]) for c in cols}
    sd = {c: (np.std([r[c] for r in train]) or 1e-9) for c in cols}
    for r in train + test:
        for c in cols:
            r[c] = (r[c] - mu[c]) / sd[c]

    def design(rs, use):
        X = np.array([[1.0] + [r[c] for c in use] for r in rs])
        y = np.array([r["label"] for r in rs])
        return X, y

    yte = np.array([r["label"] for r in test])
    base_rate = float(yte.mean())
    b_base = _brier(np.full(len(test), base_rate), yte)

    price = ["log_share", "mom1", "mom2", "slope"]                 # the trend already visible at T
    detec = price + ["surprise", "sustained"]                       # + the detector's leading signal

    Xtr, ytr = design(train, price); Xte, _ = design(test, price)
    w = _fit_logistic(Xtr, ytr, l2=1.0, iters=2000)
    b_price = _brier(_predict(Xte, w), yte)

    Xtr2, _ = design(train, detec); Xte2, _ = design(test, detec)
    w2 = _fit_logistic(Xtr2, ytr, l2=1.0, iters=2000)
    b_det = _brier(_predict(Xte2, w2), yte)

    n_concepts = len({r["cid"] for r in rows})
    log("\n── concept gate (OpenAlex 46k, real detector, leak-free) ──")
    log(f"   panel: {len(rows)} (concept×origin) rows · {n_concepts} concepts · "
        f"train {len(train)} (T<{origin_split}) · test {len(test)} (T>={origin_split})")
    log(f"   base rate (test)      : {base_rate:.3f} 'share rose over {HORIZON}y'")
    log(f"   base-rate      Brier  : {b_base:.4f}")
    log(f"   price (trend)  Brier  : {b_price:.4f}   (log-share + momentum + Theil-Sen slope at T)")
    log(f"   price+detector Brier  : {b_det:.4f}   (+ surprise-σ + sustained-σ, the leading signal)")
    log(f"   detector edge         : {b_price - b_det:+.4f}   (positive ⇒ the σ signal adds OOS skill BEYOND trend)")
    log(f"   detector vs base-rate : {b_base - b_det:+.4f}")
    verdict = ("ALIVE — the detector's acceleration signal adds out-of-sample skill beyond the trend at "
               "concept granularity. THIS is where the data-layer edge lives; build the dataset/features here."
               if (b_price - b_det) > 0.002
               else "FLAT/NULL — even at concept granularity, surprise-σ adds nothing beyond the trend OOS. "
               "The core acceleration signal does not carry forecastable edge in this test.")
    log(f"   verdict               : {verdict}")
    return {"n_test": len(test), "n_concepts": n_concepts, "base": b_base,
            "price": b_price, "detector": b_det, "detector_edge": b_price - b_det}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Definitive leak-free concept-granularity gate ($0).")
    ap.add_argument("--origin-split", type=int, default=2017)
    a = ap.parse_args()
    run(origin_split=a.origin_split)
