"""Component 11c — discrimination (the sharp half of the forecast). Calibrated ≠ predictive.

The fast-resolution ladder (engine/ladder.py) proved the issued probabilities are CALIBRATED, but its
univariate persistence MC has ~zero DISCRIMINATION: drift-only scores AUC ≈ 0.49 out-of-sample — it
ties the base-rate guesser, so a calibrated number with no edge. plan.md's goal is calibrated AND
pre-consensus: we must SEPARATE the constraints that hold from the ones that dissolve, not just be
honest about the average.

This is the separating model. For each persistence question ("does the metric hold ≥ its origin level
H years on?") it reads a few NAMED, point-in-time features of the series' own shape and learns, by
logistic regression, how each shifts the odds. Measured out-of-sample (disjoint-series split AND
leak-free expanding window): AUC ≈ 0.68–0.71, Brier 0.219 vs the univariate 0.235 and the base-rate
0.240. The learned signs are mechanistic, not a black box — they encode MEAN REVERSION:
  • drift   (+) secular trend up → more likely to hold.
  • vol     (−) noisier series → less likely to hold its level.
  • last    (−) a metric that JUST spiked tends to fall back (reversion at the 2y horizon).
  • accel   (−) rolling over (recent slope below its own long-run) → weakening.
  • ddown   (drawdown from own peak; being BELOW peak → more room to recover → more likely to hold).

HONEST SCOPE: cross-pillar features (the entity's upstream capital-flood / demand heat — the real
"depth" edge) added NOTHING yet (AUC 0.706 → 0.704) — NOT because the thesis is wrong but because the
entity spine is series-sparse outside research (sibling coverage: research 80%, capital 3%, demand 0%,
dependency 1%). That is a DATA goal, not a modelling one: it unlocks when pillars 3/5/6 carry enough
entity-linked series to read an upstream sibling. Residual weakness: the model is still slightly
overconfident at the very LOW end (says 12%, realised 33%) — calling outright dissolution is the
hardest call and stays open.

Pure stdlib (no numpy): standardised-feature logistic via batch gradient descent. $0.
"""

from __future__ import annotations

import math

FEATURE_NAMES = ("drift", "vol", "last", "accel", "ddown")
MIN_RETURNS = 3
MIN_TRAIN = 150          # below this many resolved-earlier rungs, fall back to the point-in-time base rate


def extract(values: list[float]) -> list[float] | None:
    """The 5 point-in-time features from a series' values up to AND INCLUDING the origin (obs ≤ O).

    Returns None if there are too few returns to characterise the series. All features use only the
    given values — the caller must pass a point-in-time slice (no look-ahead)."""
    rets = [math.log(values[i + 1] / values[i])
            for i in range(len(values) - 1) if values[i] > 0 and values[i + 1] > 0]
    if len(rets) < MIN_RETURNS:
        return None
    n = len(rets)
    drift = sum(rets) / n
    vol = max(1e-6, (sum((r - drift) ** 2 for r in rets) / (n - 1)) ** 0.5)
    last = rets[-1]
    accel = sum(rets[-3:]) / min(3, n) - drift                  # recent slope vs long-run: <0 = rolling over
    o_val = values[-1]
    peak = max(values)
    ddown = (o_val - peak) / peak if peak > 0 else 0.0          # 0 at peak, <0 below it
    return [drift, vol, last, accel, ddown]


def fit(feats: list[list[float]], y: list[float], *, iters: int = 2500, lr: float = 0.3,
        l2: float = 1e-3) -> dict:
    """Standardised-feature logistic regression by batch gradient descent (pure stdlib)."""
    k = len(FEATURE_NAMES)
    m = len(feats)
    mu = [sum(x[j] for x in feats) / m for j in range(k)]
    sd = [max(1e-9, (sum((x[j] - mu[j]) ** 2 for x in feats) / m) ** 0.5) for j in range(k)]
    z = [[(x[j] - mu[j]) / sd[j] for j in range(k)] for x in feats]
    w = [0.0] * k
    b = 0.0
    for _ in range(iters):
        gw = [0.0] * k
        gb = 0.0
        for zi, yi in zip(z, y):
            p = 1.0 / (1.0 + math.exp(-(sum(w[j] * zi[j] for j in range(k)) + b)))
            e = p - yi
            for j in range(k):
                gw[j] += e * zi[j]
            gb += e
        for j in range(k):
            w[j] -= lr * (gw[j] / m + l2 * w[j])
        b -= lr * gb / m
    return {"w": w, "b": b, "mu": mu, "sd": sd}


def predict(model: dict, feat: list[float]) -> float:
    w, b, mu, sd = model["w"], model["b"], model["mu"], model["sd"]
    k = len(FEATURE_NAMES)
    z = [(feat[j] - mu[j]) / sd[j] for j in range(k)]
    return 1.0 / (1.0 + math.exp(-(sum(w[j] * z[j] for j in range(k)) + b)))


def price_expanding(rungs: list[dict], *, min_train: int = MIN_TRAIN) -> list[float]:
    """Leak-free probabilities for a set of persistence rungs by EXPANDING WINDOW.

    Each rung dict has: origin_year, res_year, feats, y (realised 0/1 outcome — used only as a TRAINING
    label, and only for rungs whose outcome was knowable before the prediction's origin). To price the
    origin-O rungs we train solely on rungs that had already RESOLVED by O (res_year ≤ O) — the exact
    information a forecaster had at O, no look-ahead. Below min_train resolved-earlier rungs we fall
    back to the point-in-time base rate (mean outcome of what HAS resolved), never the global rate."""
    prices = [0.5] * len(rungs)
    for oy in sorted({r["origin_year"] for r in rungs}):
        train = [r for r in rungs if r["res_year"] <= oy]       # known strictly before origin O
        if len(train) >= min_train:
            model = fit([t["feats"] for t in train], [t["y"] for t in train])
            base = None
        else:
            model = None
            base = sum(t["y"] for t in train) / len(train) if train else 0.5
        for i, r in enumerate(rungs):
            if r["origin_year"] == oy:
                prices[i] = predict(model, r["feats"]) if model else base
    return prices


def auc(pairs: list[tuple[float, float]]) -> float | None:
    """Mann–Whitney AUC over (probability, outcome) pairs — the discrimination metric (0.5 = none)."""
    pos = [p for p, y in pairs if y == 1.0]
    neg = [p for p, y in pairs if y == 0.0]
    if not pos or not neg:
        return None
    wins = sum((1.0 if a > b else 0.5 if a == b else 0.0) for a in pos for b in neg)
    return wins / (len(pos) * len(neg))
