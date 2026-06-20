"""TimesFM numeric forecaster for the dataset half — a decorrelated mechanical member.

The dataset-half questions are "will <series> be higher on <resolution_date> than at
freeze?" — a directional move on a real numeric series. TimesFM (Google's decoder-only
time-series foundation model, 2.5/200M) gives a calibrated quantile forecast at any
horizon; we read P(value at horizon > freeze) straight off that predictive distribution.

Why this is leak-free even on backtests: TimesFM sees ONLY the raw truncated numbers —
no dates, no series id, no text — so it physically cannot recall a series' realized
future the way an LLM can. As long as we feed it observations dated <= due (point-in-time
truncation, same `_truncate` guard the rest of dataset.py uses), a historical round is a
clean test. The model is pretrained and never tuned on our rounds, so this is also no-overfit.

Decorrelated by construction: our incumbent dataset models are hand-built statistics
(drift-RW, empirical base rate, day-of-year climatology). TimesFM is a neural foundation
model — a different failure surface entirely, which is exactly the kind of member that can
add ensemble value (the LLM members are all ~0.6 correlated; this one is not an LLM).

Graceful: if `timesfm`/`torch` are not installed, the series is too short, or the horizon
exceeds the compiled window, every entry returns None so the caller falls back to the
incumbent model — never 0.5.
"""
from __future__ import annotations

import math
import statistics
import threading
from datetime import date

# Compiled forecast window. 512 context covers every cached series; 256 horizon covers
# all monthly/quarterly horizons (10y == 120 months) and daily horizons out to ~1y
# (~252 trading days). Longer daily horizons return None -> incumbent fallback.
MAX_CONTEXT = 512
MAX_HORIZON = 256
MIN_CONTEXT = 32                     # TimesFM's minimum useful context
_QLEVELS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)

_model = None
_load_failed = False
_lock = threading.Lock()


def available() -> bool:
    """True if the TimesFM model can be loaded (deps present, weights reachable)."""
    return _load_model() is not None


def _load_model():
    """Lazy singleton: load + compile TimesFM 2.5 once. Returns the model or None
    (deps missing / weights unreachable) — callers degrade to the incumbent model."""
    global _model, _load_failed
    if _model is not None:
        return _model
    if _load_failed:
        return None
    with _lock:
        if _model is not None:
            return _model
        if _load_failed:
            return None
        try:
            import torch
            import timesfm
            torch.set_float32_matmul_precision("high")
            try:
                torch.set_num_threads(max(1, (torch.get_num_threads() or 4)))
            except Exception:
                pass
            m = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
                "google/timesfm-2.5-200m-pytorch")
            m.compile(timesfm.ForecastConfig(
                max_context=MAX_CONTEXT, max_horizon=MAX_HORIZON,
                normalize_inputs=True, use_continuous_quantile_head=True,
                force_flip_invariance=True, infer_is_positive=False,
                fix_quantile_crossing=True,
            ))
            _model = m
            return _model
        except Exception as e:                       # noqa: BLE001 - any failure -> fallback
            _load_failed = True
            print(f"[timesfm] model unavailable, falling back to incumbent: {e}", flush=True)
            return None


# ---- quantile -> P(value > threshold) --------------------------------------

def _cdf_at(values, levels, x: float) -> float:
    """Piecewise-linear CDF implied by the quantile anchors (values, levels), with
    linear tail extrapolation beyond q10/q90. Clamped to (0.001, 0.999)."""
    n = len(values)
    if x <= values[0]:
        slope = (levels[1] - levels[0]) / (values[1] - values[0]) if values[1] > values[0] else 0.0
        return max(0.001, levels[0] + slope * (x - values[0]))
    if x >= values[-1]:
        slope = (levels[-1] - levels[-2]) / (values[-1] - values[-2]) if values[-1] > values[-2] else 0.0
        return min(0.999, levels[-1] + slope * (x - values[-1]))
    for i in range(1, n):
        if x <= values[i]:
            if values[i] > values[i - 1]:
                frac = (x - values[i - 1]) / (values[i] - values[i - 1])
            else:
                frac = 0.0
            return levels[i - 1] + frac * (levels[i] - levels[i - 1])
    return 0.5


def p_above(qrow, threshold: float) -> float:
    """P(forecast value at this horizon step > threshold), from the 9 quantile slices.

    qrow is the length-10 quantile vector for one horizon step (index 0 = mean,
    1..9 = q10..q90). Returns a probability in [0.02, 0.98]."""
    qs = [float(v) for v in list(qrow)[1:10]]
    for i in range(1, len(qs)):                      # guard monotonicity (belt-and-braces)
        if qs[i] < qs[i - 1]:
            qs[i] = qs[i - 1]
    p_below = _cdf_at(qs, _QLEVELS, float(threshold))
    return min(0.98, max(0.02, 1.0 - p_below))


# ---- horizon math ----------------------------------------------------------

def _period_days(dts) -> int | None:
    sp = [(dts[i] - dts[i - 1]).days for i in range(1, len(dts)) if (dts[i] - dts[i - 1]).days > 0]
    if not sp:
        return None
    return max(1, int(statistics.median(sp)))


def _steps(period_days: int, horizon_days: int) -> int:
    return max(1, round(horizon_days / period_days))


# ---- single-series forecast ------------------------------------------------

def p_higher_timesfm(history, due: date, res_dates, freeze: float | None = None):
    """Forecast P(value at each resolution_date > freeze) for one series.

    `history` is the full series [(date, value)]; it is truncated to <= due here.
    `res_dates` is a list of 'YYYY-MM-DD' strings. `freeze` is the threshold (the
    question's freeze_datetime_value); if None we use the last point-in-time obs.

    Returns {res_date_str: p} for the horizons that fit the compiled window; horizons
    beyond MAX_HORIZON (or with too little history) are simply omitted -> caller falls
    back to the incumbent model for those."""
    from .dataset import _d, _truncate

    h = _truncate(history, due)
    if len(h) < MIN_CONTEXT:
        return {}
    dts = [d for d, _ in h]
    vals = [float(v) for _, v in h]
    pd = _period_days(dts)
    if pd is None:
        return {}
    thr = float(freeze) if freeze is not None else vals[-1]

    # one forecast per series, to the max step any of its horizons needs (<= MAX_HORIZON)
    wanted = {}
    for rd in res_dates:
        s = _steps(pd, (_d(rd) - due).days)
        if 1 <= s <= MAX_HORIZON:
            wanted[rd] = s
    if not wanted:
        return {}
    model = _load_model()
    if model is None:
        return {}
    horizon = max(wanted.values())
    import numpy as np
    ctx = np.asarray(vals[-MAX_CONTEXT:], dtype=np.float32)
    try:
        _, q = model.forecast(horizon=horizon, inputs=[ctx])
        q = np.asarray(q)
    except Exception as e:                            # noqa: BLE001
        print(f"[timesfm] forecast failed: {e}", flush=True)
        return {}
    out = {}
    for rd, s in wanted.items():
        row = q[0, s - 1]
        if np.isnan(row).any():
            continue
        out[rd] = p_above(row, thr)
    return out
