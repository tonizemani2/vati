"""engine/metaculus/numeric.py — numeric (continuous CDF) + multiple-choice forecasting.

Beyond binary, Metaculus tournaments (esp. the bot-prize ones) are mostly:
  • multiple_choice — submit `probability_yes_per_category`: a vector over `question.options`, sums to 1.
  • numeric / date / discrete — submit `continuous_cdf`: cumulative probabilities at the question's
    internal grid `question.scaling.continuous_range` (201 pts for numeric, N+1 for discrete),
    monotonic non-decreasing, in [0,1], with open/closed-bound handling.

The forecaster supplies PERCENTILES (quantile→value); we convert to the CDF by interpolating in value
space over the grid (the grid already encodes any log-scaling, so no separate log handling needed), then
enforce Metaculus's validity rules (monotone, a tiny minimum slope so there are no zero-density regions,
and pinned endpoints for closed bounds).
"""
from __future__ import annotations

import numpy as np

from engine.metaculus import api

MIN_STEP = 5e-5  # Metaculus rejects flat CDF regions → guarantee a tiny minimum slope per step
MAX_STEP = 0.19  # Metaculus also rejects steps > 0.2 → cap below it (concentrated mass must spread)


# ───────────────────────────────────────────────────────── multiple choice

def options_to_vector(option_probs: dict, options: list) -> dict:
    """{option: prob} → normalized {option: prob} dict aligned to `options` (floors tiny mass, renorms).
    Metaculus wants `probability_yes_per_category` as a DICT keyed by the exact option strings."""
    # Metaculus requires every option prob in [0.001, 0.999]; floor with margin so normalization can't
    # push the smallest below 0.001.
    v = {o: min(0.99, max(2e-3, float(option_probs.get(o, 0.0)))) for o in options}
    s = sum(v.values())
    return {o: p / s for o, p in v.items()}


# ───────────────────────────────────────────────────────── continuous CDF

def percentiles_to_cdf(percentiles: dict, continuous_range: list,
                       open_lower: bool, open_upper: bool) -> list:
    """`percentiles`: {quantile in (0,1): value}. Returns a valid Metaculus CDF (len == len(grid)).

    Anchors are NOT clipped to the range — percentile values beyond an OPEN bound are kept so the
    boundary CDF correctly carries the implied outside-the-range mass (np.interp evaluates the grid
    endpoints between the out-of-range anchor and its neighbour). Closed bounds are pinned to 0/1."""
    grid = np.array(continuous_range, dtype=float)
    lo, hi = grid[0], grid[-1]
    pcs = sorted((float(v), float(q)) for q, v in percentiles.items())  # (value, cumprob)
    xs = [v for v, q in pcs]
    ys = [q for v, q in pcs]
    if not open_lower:                # closed lower → pin (lo, 0)
        xs = [lo] + xs; ys = [0.0] + ys
    if not open_upper:                # closed upper → pin (hi, 1)
        xs = xs + [hi]; ys = ys + [1.0]

    order = np.argsort(xs)
    xs = np.array(xs)[order]
    ys = np.maximum.accumulate(np.array(ys)[order])
    ux = np.unique(xs)                                    # interp needs strictly increasing x
    uy = np.array([ys[xs == x].max() for x in ux])        # duplicate value → keep the HIGHEST cumprob

    cdf = np.clip(np.interp(grid, ux, uy), 0.0, 1.0)      # np.interp clamps flat beyond the anchors
    return enforce_valid_cdf(cdf, len(grid), open_lower, open_upper)


def min_step(grid_len: int) -> float:
    """Metaculus's per-step floor: the CDF must increase by ≥ 0.01/(n_steps) at every grid point
    (5e-5 for a 201-pt numeric grid; ~9e-4 for a 12-pt discrete grid)."""
    return 0.01 / (grid_len - 1)


def enforce_valid_cdf(cdf, grid_len: int, open_lower: bool, open_upper: bool) -> list:
    """Project any near-CDF onto Metaculus's exact validity constraints in ONE correct pass:
      • monotone with EVERY step ≥ the question's min_step (plus a float round-trip safety margin),
      • closed bound → endpoint pinned to 0/1; open bound → endpoint strictly inside with min outside-mass.
    A per-point feasibility ceiling guarantees enough room remains for every LATER step to clear the
    floor, so no overshoot/endpoint-clamp can silently re-flatten a step (the old discrete-reject bug)."""
    a = np.clip(np.asarray(cdf, dtype=float), 0.0, 1.0)
    n = len(a)
    # enforce slightly ABOVE the raw floor so the server-side JSON round-trip can't land a hair under it
    step = min_step(grid_len) * (1.0 + 1e-4)
    hi_cap = 1.0 if not open_upper else 0.999          # open upper → endpoint ≤ 0.999 (carries above-range mass)
    # lower endpoint: closed → pinned 0; open → keep the interpolated below-range mass (≥0.001 cap)
    out = a.copy()
    out[0] = 0.0 if not open_lower else float(min(max(a[0], 0.001), hi_cap - (n - 1) * step))
    for i in range(1, n):
        floor_i = out[i - 1] + step                    # min upward slope from the previous point
        ceil_max = out[i - 1] + MAX_STEP               # server rejects a step > 0.2 → cap the jump
        cap = hi_cap
        if not open_upper:                             # closed upper MUST reach 1.0 → leave room for later min-steps
            cap = min(cap, hi_cap - (n - 1 - i) * step)
        out[i] = min(max(out[i], floor_i), ceil_max, cap)
    if not open_upper:
        out[-1] = 1.0                                  # closed upper → pin exactly to 1.0
    # open upper: leave out[-1] as computed (≤0.999, ≥ out[-2]+step) so it CARRIES the above-range tail mass
    return [float(x) for x in out]


def validate_cdf(cdf: list, grid_len: int | None = None) -> tuple[bool, str]:
    """Validate against the question's REAL floor (0.01/(grid_len-1)); falls back to the global
    MIN_STEP only when grid_len is unknown (which under-checks discrete grids — pass grid_len)."""
    a = np.array(cdf)
    floor = min_step(grid_len) if grid_len else MIN_STEP
    if not np.all(np.diff(a) >= 0):
        return False, "not monotonic"
    if a.min() < 0 or a.max() > 1:
        return False, "out of [0,1]"
    if np.any(np.diff(a) < floor - 1e-9):
        return False, f"step below floor {floor:.2e}"
    if np.any(np.diff(a) > 0.2 + 1e-9):
        return False, "step above 0.2 ceiling"
    return True, "ok"


# ───────────────────────────────────────────────────────── submit helpers

def submit_multiple_choice(question_id: int, prob_per_option: list) -> dict:
    return api._req("POST", "/questions/forecast/", body=[{
        "question": question_id, "source": "api",
        "probability_yes": None, "probability_yes_per_category": prob_per_option,
        "continuous_cdf": None,
    }])


def submit_cdf(question_id: int, cdf: list) -> dict:
    return api._req("POST", "/questions/forecast/", body=[{
        "question": question_id, "source": "api",
        "probability_yes": None, "probability_yes_per_category": None,
        "continuous_cdf": cdf,
    }])


def question_meta(post: dict) -> dict:
    """Normalize what the numeric/MC forecaster needs from a post."""
    q = post.get("question") or {}
    sc = q.get("scaling") or {}
    return {
        "post_id": post.get("id"), "question_id": q.get("id"), "type": q.get("type"),
        "title": post.get("title") or q.get("title") or "",
        "resolution_criteria": q.get("resolution_criteria") or "",
        "fine_print": q.get("fine_print") or "", "description": q.get("description") or "",
        "options": q.get("options"), "unit": q.get("unit") or "",
        "continuous_range": sc.get("continuous_range"),
        "open_lower_bound": bool(q.get("open_lower_bound")),
        "open_upper_bound": bool(q.get("open_upper_bound")),
        "range_min": (sc.get("continuous_range") or [None])[0],
        "range_max": (sc.get("continuous_range") or [None])[-1],
        "close_time": q.get("scheduled_close_time"),
    }
