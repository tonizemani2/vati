"""Prophet Arena forecast agent — the `--local` / HTTP `predict(event)` entry point.

Contract (from ai-prophet CLI, packages/core/.../forecast):
  input  event dict: {event_ticker, market_ticker, title, subtitle, description,
                      category, rules, close_time, outcomes:[...], market_stats?}
  output:            {"probabilities": [{"market": <label>, "probability": float}, ...]}

Scoring is multiclass Brier  sum_i (p_i - 1[winner])^2  (winner = resolved_outcome.value[0]),
so for an N-way event we return a calibrated categorical summing to 1. Binary "A vs B" / "Will X?"
events (all sports + most of the board) take outcomes[0] as the YES side and run the full
research→ensemble→crowd-anchor pipeline once; the Kalshi price (when present in market_stats) is
fed as the `crowd` anchor — the lever that lets us beat, rather than echo, the market.
"""
from __future__ import annotations

import os

from engine.forecastbench.ensemble import _logit, _sigmoid
from engine.metaculus import forecast

# Research (Exa) still rotates through a residential proxy; the LLM ensemble now runs on OpenRouter's
# $0 `:free` route (the old DeepInfra web-embed keyless was patched dead 2026-06-12), which is keyed +
# direct so it ignores the proxy. Override the research proxy with PROPHET_PROXY.
PROXY = os.environ.get("PROPHET_PROXY", "evomi")

# Lean, FAST free roster for the live agent (1h/event budget, but we want seconds not minutes). Diverse
# families = decorrelated errors = the real ensemble gain; the slow giant frees (nemotron-550b) are
# excluded so one queued model can't stall a forecast. nex-n2-pro answers in ~4s.
ENSEMBLE = [
    "nex-agi/nex-n2-pro:free",
    "google/gemma-4-31b-it:free",
    "openai/gpt-oss-20b:free",
]

# Category-aware market anchor (market weight w in the log-odds blend with our researched forecast).
# Calibrated 2026-06-12 leak-free (engine/prophet/anchor.py + kalshi.py): the Kalshi midpoint price is
# WELL-CALIBRATED, and our prior adds ~nothing on coin-flip sports → defer hard there; spend deviation
# budget only on the research-rich tail where the market is genuinely uncertain. CONSERVATIVE priors —
# refit FORWARD on live scored events, never on the (leaky) retro set. Our live test cratered 0.63→0.21
# under the old flat w=0.40; this is the fix.
ANCHOR_W = {
    "Sports": 0.88,             # near-coin-flips, calibrated market, hallucination risk → trust it
    "Climate and Weather": 0.80,
    "Financials": 0.75,
    "Economics": 0.45,          # market genuinely uncertain pre-release → let research move us
    "Politics": 0.45,
    "Entertainment": 0.55,
}
ANCHOR_W_DEFAULT = 0.65


def _blend(p_agent: float, p_mkt: float | None, category: str | None) -> float:
    """Log-odds blend of our researched forecast toward the market price, weighted by category."""
    if p_mkt is None:
        return p_agent
    w = ANCHOR_W.get(category or "", ANCHOR_W_DEFAULT)
    return _sigmoid((1 - w) * _logit(p_agent) + w * _logit(p_mkt))


def _to_q(event: dict) -> dict:
    """Prophet event → forecast_question's question dict."""
    return {
        "title": event.get("title") or "",
        "resolution_criteria": event.get("rules") or event.get("context") or "",
        "description": event.get("description") or event.get("subtitle") or "",
        "fine_print": "",
    }


def _market_prob(event: dict, outcome: str) -> float | None:
    """Best-effort Kalshi price for `outcome` from the agent-board market_stats payload.

    Tolerant of two observed shapes: keyed by outcome label, or {"Yes":{...},"No":{...}}.
    Returns a probability in (0,1) or None when no live price is supplied (e.g. offline backtest).
    """
    ms = event.get("market_stats") or {}
    if not isinstance(ms, dict):
        return None
    for key in (outcome, "Yes", "yes"):
        cell = ms.get(key)
        if isinstance(cell, dict):
            for f in ("last_price", "yes_ask", "mid"):
                v = cell.get(f)
                if isinstance(v, (int, float)) and 0.0 < float(v) < 1.0:
                    return float(v)
    return None


def _uniform(outcomes: list[str]) -> dict:
    p = 1.0 / max(1, len(outcomes))
    return {"probabilities": [{"market": o, "probability": p} for o in outcomes]}


def predict(event: dict) -> dict:
    """Forecast one Prophet Arena event. Keyless ($0) by default."""
    outcomes = event.get("outcomes") or []
    if len(outcomes) < 2:
        # Single-market / degenerate: fall back to a YES/NO binary on the lone label.
        outcomes = outcomes or [event.get("market_ticker") or "Yes"]
        if len(outcomes) == 1:
            outcomes = [outcomes[0], f"NOT {outcomes[0]}"]

    q = _to_q(event)
    today = (event.get("close_time") or "")[:10] or None

    category = event.get("category")
    if len(outcomes) == 2:
        yes, no = outcomes[0], outcomes[1]
        # Researched forecast with NO internal anchor (crowd=None), then category-aware market blend.
        out = forecast.forecast_question(q, today=today, crowd=None, proxy=PROXY, ensemble_models=ENSEMBLE)
        p = _blend(float(out["prob"]), _market_prob(event, yes), category)
        return {"probabilities": [
            {"market": yes, "probability": round(p, 4)},
            {"market": no, "probability": round(1.0 - p, 4)},
        ]}

    # N-way: forecast each outcome as an independent binary on shared machinery, then normalise.
    # (Threshold ranges are genuinely independent binaries; mutually-exclusive sets approximate well.)
    raw: list[tuple[str, float]] = []
    for o in outcomes:
        qi = dict(q, title=f"{q['title']}  → outcome: {o}",
                  resolution_criteria=f"Resolves YES iff the event resolves to '{o}'. {q['resolution_criteria']}")
        out = forecast.forecast_question(qi, today=today, crowd=None, proxy=PROXY, ensemble_models=ENSEMBLE)
        raw.append((o, _blend(float(out["prob"]), _market_prob(event, o), category)))
    s = sum(p for _, p in raw) or 1.0
    return {"probabilities": [{"market": o, "probability": round(p / s, 4)} for o, p in raw]}
