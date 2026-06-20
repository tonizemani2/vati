"""OpenAI-compatible `/chat/completions` forecasting core — Prophet Arena's MODEL onboarding path.

Prophet's harness POSTs an OpenAI chat request whose prompt describes one event + its outcome labels
and asks for `{"probabilities": {<label>: <p>}, "rationale": "..."}` as the reply *content*
(github.com/ai-prophet/example-api). We answer with a FAST, PARALLEL best-of-N ensemble across free
OpenRouter models — the decorrelated-ensemble edge — merged into one calibrated probability vector.

Latency-bounded (a hard deadline) so the onboarding compatibility test can never time out; the model
path expects LLM-speed seconds, not the 1h agent budget.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FTimeout, as_completed

from engine import db
from engine.adapters import llm
from engine.prophet.agent import ENSEMBLE

FORMAT_SYS = (
    "You are a calibrated superforecaster. Read the user's forecasting question and the list of "
    "possible outcomes it provides. Reply with ONLY a single JSON object and nothing else, in exactly "
    'this shape: {"probabilities": {"<outcome label>": <number between 0 and 1>, ...}, '
    '"rationale": "<2-4 sentence justification>"}. Use the EXACT outcome labels from the question as '
    "the keys. The probabilities must be calibrated and sum to 1. Do not wrap the JSON in markdown."
)

_JSON = re.compile(r"\{.*\}", re.S)


def _extract(txt: str) -> dict | None:
    """Pull the {"probabilities": {...}, ...} object out of a model reply (tolerant of stray prose)."""
    if not txt:
        return None
    m = _JSON.search(txt)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except Exception:
        return None
    return d if isinstance(d, dict) and isinstance(d.get("probabilities"), dict) else None


def _one(prompt: str, model: str) -> dict | None:
    conn = db.connect()
    try:
        txt = llm.complete(conn, prompt, provider="openrouter_free", model=model,
                           system=FORMAT_SYS, max_tokens=900, est_cost_cents=0)
        return _extract(txt)
    except Exception:
        return None
    finally:
        conn.close()


def _merge(dicts: list[dict]) -> dict:
    """Average each outcome's probability across the models that scored it, then normalise to sum 1."""
    labels: list[str] = []
    for d in dicts:
        for k in d["probabilities"]:
            if k not in labels:
                labels.append(k)
    avg: dict[str, float] = {}
    for k in labels:
        vals = [float(d["probabilities"][k]) for d in dicts
                if isinstance(d["probabilities"].get(k), (int, float))]
        if vals:
            avg[k] = sum(vals) / len(vals)
    s = sum(avg.values()) or 1.0
    return {k: round(v / s, 4) for k, v in avg.items()}


def forecast_chat(prompt: str, deadline_s: float = 25.0) -> str:
    """Return the assistant message *content*: the {"probabilities", "rationale"} JSON string."""
    outs: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, len(ENSEMBLE))) as ex:
        futs = [ex.submit(_one, prompt, m) for m in ENSEMBLE]
        try:
            for f in as_completed(futs, timeout=deadline_s):
                d = f.result()
                if d:
                    outs.append(d)
        except FTimeout:
            pass  # take whatever finished before the deadline
    if outs:
        rationale = max((str(d.get("rationale", "")) for d in outs), key=len)
        return json.dumps({"probabilities": _merge(outs),
                           "rationale": rationale or f"Ensemble of {len(outs)} free models."}, indent=2)
    # fallback: one direct completion so the envelope is ALWAYS a valid, parseable JSON string
    conn = db.connect()
    try:
        txt = llm.complete(conn, prompt, provider="openrouter_free", system=FORMAT_SYS,
                           max_tokens=900, est_cost_cents=0)
    except Exception:
        txt = ""
    finally:
        conn.close()
    d = _extract(txt)
    return json.dumps(d) if d else (txt or json.dumps({"probabilities": {}, "rationale": "no signal"}))
