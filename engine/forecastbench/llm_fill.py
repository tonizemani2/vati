"""LLM forecaster leg for the ForecastBench bot — Vati.

Defer-to-best by design. The crowd anchor (market) and the quant models (dataset)
are used wherever they produce a signal; the LLM is invoked ONLY on the residual
gap questions — those the pipeline would otherwise impute at a blind 0.5 (missing
crowd value, unfetchable / dead series). So the LLM can only raise coverage
quality, never override a real signal — score-safe by construction.

Branded "Vati"; the backing model is whatever MINIMAX_BASE_URL / MINIMAX_API_KEY
in this repo's .env point to (read-only, via the gated engine.adapters.llm). Every
call passes the cost gate first (est 0 → sub-cent, auto-approved). Any
misconfiguration (no key, no DB) degrades silently to {} and the rows 0.5-impute
exactly as before — a forecast is never blocked by the LLM leg failing.
"""
from __future__ import annotations

import json
import re

SYSTEM = (
    "You are Vati, a careful, calibrated probabilistic forecaster. You are given one "
    "forecasting question that resolves in the future. Reply with ONLY a JSON object: "
    '{"probability": <number 0..1>, "reasoning": "<one short sentence>"} — your '
    "probability that the question resolves YES. Be calibrated: use 0.5 when you truly "
    "have no edge; avoid 0 and 1. Output the JSON object and nothing else."
)


def _prompt(q: dict, due) -> str:
    parts = [f"Question: {(q.get('question') or '').strip()}"]
    rc = q.get("resolution_criteria") or q.get("market_info_resolution_criteria")
    if rc:
        parts.append(f"Resolution criteria: {str(rc).strip()[:600]}")
    if q.get("background"):
        parts.append(f"Background: {str(q['background']).strip()[:500]}")
    fv = q.get("freeze_datetime_value")
    if fv not in (None, ""):
        parts.append(f"Current/crowd value: {fv}")
    parts.append(f"Forecast as of: {due}. Source: {q.get('source')}.")
    parts.append("Return the JSON object only.")
    return "\n".join(parts)


def _parse(text: str):
    """Extract (probability, reasoning) from the model reply; None if unusable.

    Robust to reasoning models: strips <think>…</think> blocks and ```code fences```
    (which can contain stray braces), then takes the last JSON object that parses
    and carries a numeric probability."""
    if not text:
        return None
    text = re.sub(r"<think>.*?</think>", " ", text, flags=re.S | re.I)
    text = text.replace("```json", " ").replace("```", " ")
    best = None
    for m in re.finditer(r"\{[^{}]*\}", text, re.S):   # flat JSON objects, left→right
        try:
            d = json.loads(m.group(0))
            p = float(d.get("probability"))
        except Exception:
            continue
        if 0.0 <= p <= 1.0:
            best = (min(0.97, max(0.03, p)), str(d.get("reasoning", ""))[:300])
    if best is None:                       # no JSON survived — last-resort number grab
        m = re.search(r'probabilit[a-z]*["\s:]*([01]?\.\d+)', text, re.I)
        if m:
            p = float(m.group(1))
            if 0.0 <= p <= 1.0:
                best = (min(0.97, max(0.03, p)), "")
    return best


def forecast_one(conn, q: dict, due, model: str | None = None):
    """One MiniMax-backed forecast -> (p, reasoning), or None on any failure."""
    from engine.adapters import llm
    try:
        # MiniMax-M2.7 is a reasoning model: it thinks in the body before the JSON,
        # so give it room or the answer gets truncated away.
        txt = llm.complete(conn, _prompt(q, due), provider="minimax",
                           system=SYSTEM, model=model, est_cost_cents=0,
                           max_tokens=1400)
    except Exception:
        return None
    return _parse(txt)


def fill_gaps(gap_questions, due, model: str | None = None) -> dict:
    """Forecast each residual gap question via the LLM leg.

    Returns {id: (p, reasoning)}. Opens one DB connection for the cost gate and
    closes it. Degrades to {} if the LLM leg is unavailable (no key, no DB,
    network) — callers then 0.5-impute, unchanged behaviour."""
    if not gap_questions:
        return {}
    try:
        from engine import db
        conn = db.connect()
    except Exception:
        return {}
    out = {}
    try:
        for q in gap_questions:
            r = forecast_one(conn, q, due, model=model)
            if r is not None:
                out[q["id"]] = r
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return out
