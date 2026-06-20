"""Bedrock research-forecaster runner for the judgmental ForecastBench subset.

This is the unattended, AWS-billed engine behind the Opus leg (`opus_blend.py` does the
math; this does the forecasting). It is deliberately TIERED so frontier-model spend lands
only where it changes the answer — never rammed across questions the crowd/quant own:

  Stage 1  Sonnet 4.6 forecasts ALL judgmental questions (metaculus+infer), each
           research-augmented with a few keyless Exa snippets. Cheap (~$0.04/q). Most
           return edge="none" (defer to the crowd) — that is the doctrine default.
  Stage 2  Opus 4.8 COUNCIL (N independent analysts, median-logit aggregate) re-forecasts
           ONLY the movers Stage 1 flagged edge>=weak — the ~15-30 questions where research
           departs from the crowd. Opus quality + decorrelation concentrated on exactly the
           forecasts we are betting against the crowd on.

Output: {id: {probability, edge, reasoning}} JSON, consumed by `opus_blend.merge`, which
applies the conservative edge-weighted blend (crowd keeps >=60% logit weight).

WHY BEDROCK, not interactive sub-agents: this must run headless on the due date (the set
publishes 00:00 UTC and we upload within 24h). Bedrock on our own account retries cleanly
and is immune to interactive-session API-overload (529s). Cost is gated+logged per call.

LEAK DISCIPLINE: never run this to "tune" anything on a resolved set — Opus's cutoff
postdates 2025 rounds, so historical Brier is leakage-flattered. Forward rounds only.

Run (on the due date, after the set publishes):
  python -m engine.forecastbench.opus_forecaster <qset.json> <opus_out.json> \
      [--council 3] [--proxy evomi] [--workers 6] [--limit N]
"""
from __future__ import annotations

import json
import math
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .opus_blend import EDGE_WEIGHT, _crowd_value, judgmental_questions  # noqa: F401  (shared contract)

STAGE1_MODEL = "us.anthropic.claude-sonnet-4-6"
STAGE2_MODEL = "us.anthropic.claude-opus-4-8"
EDGE_RANK = {"none": 0, "weak": 1, "strong": 2}
_RANK_EDGE = {v: k for k, v in EDGE_RANK.items()}

SYSTEM = (
    "You are Vati, a careful, calibrated probabilistic forecaster. You forecast ONE question "
    "that resolves in the future, as of a stated due date. You are given the crowd's own "
    "probability at the freeze (freeze value) — treat it as a strong PRIOR; only move off it "
    "for a concrete, dated reason the crowd plausibly has not priced. Be calibrated; never use "
    "0 or 1. Reply with ONLY one JSON object: "
    '{"probability": <0..1>, "edge": "none"|"weak"|"strong", "reasoning": "<=2 sentences, '
    'cite the decisive fact + its date"}. edge = how much real, decorrelated information you '
    'have BEYOND the crowd price: "none" (default — no dated, crowd-unpriced fact; defer to the '
    'crowd), "weak" (soft directional reason), "strong" (concrete dated fact the crowd has not '
    "priced). Claiming strong without a dated unpriced fact is an error. Output the JSON only."
)


def _logit(p):
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(z):
    return 1 / (1 + math.exp(-z))


def _research(conn, q: dict, proxy: str | None) -> str:
    """A few keyless Exa snippets as of the due date. Best-effort: failure -> empty
    context (the model still forecasts from the question + crowd prior)."""
    from engine.adapters import search
    snippets = []
    queries = [q["question"][:180]]
    rc = q.get("resolution_criteria") or ""
    if "metaculus.com" not in rc and len(q["question"]) > 20:
        queries.append(q["question"][:120] + " latest news 2026")
    for query in queries[:2]:
        try:
            for r in search.search(conn, query, num_results=4, proxy=proxy)[:4]:
                title = getattr(r, "title", "") or ""
                text = (getattr(r, "text", "") or getattr(r, "snippet", "") or "")[:400]
                if text:
                    snippets.append(f"- {title}: {text}")
        except Exception:
            continue
    return "\n".join(snippets[:8])


def _prompt(q: dict, context: str) -> str:
    parts = [f"Question: {q['question']}"]
    rc = q.get("resolution_criteria")
    if rc:
        parts.append(f"Resolution criteria: {str(rc)[:800]}")
    if q.get("background"):
        parts.append(f"Background: {str(q['background'])[:600]}")
    if q.get("raw_crowd_value") is not None:
        parts.append(f"Raw crowd freeze value: {q['raw_crowd_value']}")
    parts.append(f"Calibrated crowd prior: {q['crowd_value']}")
    parts.append(f"Forecast as of: {q['due']}. Source: {q['source']}. "
                 "Use NOTHING published after the due date.")
    if context:
        parts.append(f"Research snippets (verify dates; ignore anything after the due date):\n{context}")
    parts.append("Return the JSON object only.")
    return "\n".join(parts)


def _parse(text: str):
    """Extract (p, edge, reasoning) from a model reply. Robust to reasoning models:
    strip <think> blocks + code fences, take the last JSON object with a numeric prob."""
    if not text:
        return None
    text = re.sub(r"<think>.*?</think>", " ", text, flags=re.S | re.I)
    text = text.replace("```json", " ").replace("```", " ")
    best = None
    for m in re.finditer(r"\{[^{}]*\}", text, re.S):
        try:
            d = json.loads(m.group(0))
            p = float(d.get("probability"))
        except Exception:
            continue
        if 0.0 <= p <= 1.0:
            edge = str(d.get("edge", "none")).lower().strip()
            edge = edge if edge in EDGE_RANK else "none"
            best = (min(0.98, max(0.02, p)), edge, str(d.get("reasoning", ""))[:300])
    return best


def _forecast_once(conn, q: dict, model: str, context: str):
    """One Bedrock forecast -> (p, edge, reasoning) or None."""
    from engine.adapters import llm
    try:
        txt = llm.complete(conn, _prompt(q, context), provider="bedrock", model=model,
                           system=SYSTEM, max_tokens=1200)
    except Exception:
        return None
    return _parse(txt)


def _stage1(q: dict, proxy: str | None):
    """Sonnet, research-augmented. Own DB conn (thread-safe). Returns the worklist row
    enriched with the Sonnet forecast, or None on failure."""
    from engine import db
    conn = db.connect()
    db.init_db(conn)
    try:
        ctx = _research(conn, q, proxy)
        r = _forecast_once(conn, q, STAGE1_MODEL, ctx)
    finally:
        conn.close()
    if r is None:
        return None
    p, edge, why = r
    return {**q, "_ctx": ctx, "p": p, "edge": edge, "reasoning": why}


def _stage2(q: dict, council: int):
    """Opus council on a flagged mover. Reuses Stage-1 research context. Median-logit
    aggregate of `council` independent samples; edge = median claimed edge."""
    from engine import db
    conn = db.connect()
    db.init_db(conn)
    samples = []
    try:
        for _ in range(council):
            r = _forecast_once(conn, q, STAGE2_MODEL, q.get("_ctx", ""))
            if r is not None:
                samples.append(r)
    finally:
        conn.close()
    if not samples:
        return q["p"], q["edge"], q.get("reasoning", "")   # fall back to Stage-1
    logits = sorted(_logit(p) for p, _, _ in samples)
    mid = logits[len(logits) // 2]
    ranks = sorted(EDGE_RANK[e] for _, e, _ in samples)
    edge = _RANK_EDGE[ranks[len(ranks) // 2]]
    why = max(samples, key=lambda s: EDGE_RANK[s[1]])[2]   # the most-confident sample's reason
    return _sigmoid(mid), edge, why


def run(qset_path: str, out_path: str, council: int = 3, proxy: str | None = None,
        workers: int = 6, limit: int | None = None) -> dict:
    qd = json.loads(Path(qset_path).read_text())
    qs = judgmental_questions(qd["questions"])
    due = qd["forecast_due_date"]
    rows = []
    for q in qs:
        rows.append({"id": q["id"], "source": q["source"], "due": due,
                     "question": (q.get("question") or "").strip(),
                     "resolution_criteria": str(q.get("resolution_criteria")
                                                or q.get("market_info_resolution_criteria") or "").strip(),
                     "background": str(q.get("background") or "").strip(),
                     "crowd_value": _crowd_value(q),
                     "raw_crowd_value": float(q["freeze_datetime_value"])})
    if limit:
        rows = rows[:limit]
    print(f"Stage 1 (Sonnet, research-augmented): {len(rows)} judgmental questions, workers={workers}")

    s1 = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_stage1, q, proxy): q for q in rows}
        for i, fut in enumerate(as_completed(futs)):
            r = fut.result()
            if r:
                s1.append(r)
            if (i + 1) % 20 == 0:
                print(f"  ...{i+1}/{len(rows)}")

    movers = [r for r in s1 if EDGE_RANK[r["edge"]] >= 1]
    print(f"Stage 1 done: {len(s1)}/{len(rows)} forecast; {len(movers)} movers (edge>=weak) "
          f"-> Stage 2 Opus {council}-council")

    final = {}
    for r in s1:                                    # default: keep Stage-1 (mostly edge=none)
        final[_key(r["id"])] = {"id": r["id"], "probability": round(r["p"], 6),
                                "edge": r["edge"], "reasoning": r["reasoning"]}
    with ThreadPoolExecutor(max_workers=max(1, workers // 2)) as ex:
        futs = {ex.submit(_stage2, q, council): q for q in movers}
        for fut in as_completed(futs):
            q = futs[fut]
            p, edge, why = fut.result()
            final[_key(q["id"])] = {"id": q["id"], "probability": round(p, 6),
                                    "edge": edge, "reasoning": why}

    serial = {(k if not isinstance(k, tuple) else json.dumps(list(k))): v for k, v in final.items()}
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(serial, indent=1))
    n_move = sum(1 for v in final.values() if EDGE_RANK[v["edge"]] >= 1)
    print(f"wrote {len(final)} forecasts -> {out_path}  ({n_move} will move the crowd anchor)")
    return final


def _key(qid):
    return tuple(qid) if isinstance(qid, list) else qid


if __name__ == "__main__":
    a = sys.argv[1:]
    def opt(flag, default=None, cast=str):
        return cast(a[a.index(flag) + 1]) if flag in a else default
    qset, out = a[0], a[1]
    run(qset, out, council=int(opt("--council", 3)), proxy=opt("--proxy"),
        workers=int(opt("--workers", 6)),
        limit=int(opt("--limit")) if "--limit" in a else None)
