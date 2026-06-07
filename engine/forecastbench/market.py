"""Market-question forecaster.

Market questions (~203/round, manifold/metaculus/polymarket/infer) ship with the
crowd's own probability (freeze_datetime_value). The crowd is a very strong,
hard-to-beat anchor (resolved-row Brier ~0.04-0.11). Top ForecastBench entries
all feed it in. So our market forecast = crowd prior, optionally nudged by an
LLM+news adjustment, then lightly calibrated.

Keyless-first: the LLM nudge runs on keyless models / in-session reasoning; any
paid news API is costed and approved first. Until then, crowd-anchor + calibration
is the baseline (already competitive on the market half).
"""
from __future__ import annotations

import math

from .score import MARKET_SOURCES, single_questions


def _logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(z):
    return 1 / (1 + math.exp(-z))


def calibrate(p, extremize=1.0, floor=0.02):
    """Map a probability through a logit-scale extremization (>1 sharpens toward
    0/1, <1 softens toward 0.5) and a clamp. extremize=1.0 is identity."""
    z = _logit(p) * extremize
    q = _sigmoid(z)
    return min(max(q, floor), 1 - floor)


def crowd_anchor(questions, extremize=1.0) -> dict:
    """Market forecast = (calibrated) crowd value."""
    f = {}
    for q in single_questions(questions):
        if q["source"] in MARKET_SOURCES:
            try:
                p = float(q["freeze_datetime_value"])
            except (TypeError, ValueError, KeyError):
                continue          # no crowd value -> not anchored (LLM leg fills the gap)
            f[q["id"]] = calibrate(p, extremize=extremize)
    return f
