"""Opus research-forecaster leg for ForecastBench — Vati.

WHY THIS EXISTS (read before changing the weights). On every round the mechanical
pipeline already hits ~100% coverage: market questions get the crowd anchor
(`market.crowd_anchor`), dataset questions get the quant models. The crowd anchor on
liquid markets (manifold/polymarket) is a very strong, hard-to-beat baseline, and the
quant owns the dataset half (that is our #1-among-bots edge — Opus REGRESSES it, so it
is never touched here). The ONE place a frontier research agent can add decorrelated
signal is the *judgmental* market subset (metaculus + infer): slower-moving, thinner
crowds, resolves on world events an agent can research as of the due date.

So this leg does NOT gap-fill and does NOT override the quant. It blends an Opus
research forecast into the crowd anchor on the judgmental subset only, EDGE-WEIGHTED:

    each Opus forecast carries an `edge` flag it must self-assign —
      none   -> weight 0.00  (defer entirely to the crowd; the doctrine default)
      weak   -> weight 0.20
      strong -> weight 0.40  (a concrete, dated reason the crowd hasn't priced)
    p_final = sigmoid( (1-w)*logit(p_crowd) + w*logit(p_opus) )

The crowd keeps >=60% of the logit weight always, so a wild Opus call cannot tank a
well-priced market; when Opus has no edge the output is the crowd anchor unchanged.

LEAK DISCIPLINE (the one rule that never moves). Opus 4.x's training cutoff postdates
resolved 2025 rounds, so its absolute Brier on any *historical* set is leakage-flattered
and proves nothing about forward skill — DO NOT tune the blend weights on a resolved set.
The weights above are fixed by principle (defer-to-best + bounded displacement), not
fit. The only honest test of this leg is a FORWARD round (the live set the agent could
not have seen). Validation now is mechanics only: coverage, schema, sane probabilities.

PIPELINE (orchestrated by the Opus main agent on the due date — questions publish at
00:00 UTC and are not fetchable before):
    1. python -m engine.forecastbench.opus_blend worklist <qset.json> <work.jsonl>
       -> one line per judgmental question (id, prompt fields, crowd value)
    2. the main Opus agent dispatches one research sub-agent per line (web search +
       calibrated reasoning), collecting {id: {p, edge, reasoning}} into opus.json
    3. python -m engine.forecastbench.opus_blend merge <qset.json> opus.json <out.json>
       -> the FB submission with the judgmental subset edge-blended, everything else
          identical to the mechanical pipeline. Coverage is re-checked.

The AGENT CONTRACT (what each research sub-agent must return, one JSON object):
    {"id": <question id>, "probability": <0..1>, "edge": "none"|"weak"|"strong",
     "reasoning": "<= 2 sentences, cite the decisive fact + its date"}
  - probability = P(YES) as of the forecast due date, calibrated (use the crowd value
    as your prior; only move off it for a concrete, dated reason).
  - edge = how much real, decorrelated information you have beyond the crowd price.
    Default to "none" — claiming "strong" without a dated, crowd-unpriced fact is a bug.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path

from .market import calibrate_market_probability
from .score import single_questions

# Sources where a research agent can plausibly beat a thin/slow crowd. Liquid
# price markets (manifold/polymarket) are left to the crowd anchor — the price IS
# the aggregated information and the agent's marginal-over-price is ~0 (Beyond-Brier).
JUDGMENTAL_SOURCES = {"metaculus", "infer"}

# Edge -> Opus logit weight. Crowd keeps >=60% always. Fixed by principle, NOT fit
# (see LEAK DISCIPLINE). Conservative on purpose: the asymmetric cost of degrading a
# well-priced market dominates the upside of a marginal nudge.
EDGE_WEIGHT = {"none": 0.0, "weak": 0.20, "strong": 0.40}


def _logit(p):
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(z):
    return 1 / (1 + math.exp(-z))


def _crowd_value(q):
    try:
        return calibrate_market_probability(q["source"], float(q["freeze_datetime_value"]))
    except (TypeError, ValueError, KeyError):
        return None


def blend(p_crowd: float, p_opus: float, edge: str) -> float:
    """Edge-weighted logit blend, crowd-anchored. edge='none' -> p_crowd unchanged."""
    w = EDGE_WEIGHT.get(str(edge).lower().strip(), 0.0)
    if w <= 0:
        return float(p_crowd)
    z = (1 - w) * _logit(p_crowd) + w * _logit(p_opus)
    return min(max(_sigmoid(z), 0.02), 0.98)


def judgmental_questions(questions):
    return [q for q in single_questions(questions)
            if q["source"] in JUDGMENTAL_SOURCES and _crowd_value(q) is not None]


def emit_worklist(qset_path: str, out_path: str) -> int:
    """Write one JSON line per judgmental question for the agent dispatch step."""
    qd = json.loads(Path(qset_path).read_text())
    due = qd["forecast_due_date"]
    rows = []
    for q in judgmental_questions(qd["questions"]):
        rows.append({
            "id": q["id"],
            "source": q["source"],
            "due": due,
            "question": (q.get("question") or "").strip(),
            "resolution_criteria": str(q.get("resolution_criteria")
                                       or q.get("market_info_resolution_criteria") or "").strip()[:1200],
            "background": str(q.get("background") or "").strip()[:800],
            "crowd_value": _crowd_value(q),
            "resolution_dates": q.get("resolution_dates"),
        })
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"wrote {len(rows)} judgmental questions -> {out_path}")
    return len(rows)


def load_opus(opus_path: str) -> dict:
    """Read the agents' collected forecasts: {id: {probability, edge, reasoning}}.
    Accepts a JSON dict, a JSON list of objects, or JSONL. Tolerant of missing rows."""
    txt = Path(opus_path).read_text().strip()
    out = {}
    if not txt:
        return out
    rows = []
    try:
        obj = json.loads(txt)
        if isinstance(obj, dict):
            for k, v in obj.items():
                v = dict(v); v.setdefault("id", k); rows.append(v)
        elif isinstance(obj, list):
            rows = obj
    except json.JSONDecodeError:
        rows = [json.loads(l) for l in txt.splitlines() if l.strip()]
    for r in rows:
        try:
            qid = r["id"]
            p = float(r["probability"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0.0 <= p <= 1.0:
            out[_key(qid)] = {"p": p, "edge": str(r.get("edge", "none")),
                              "reasoning": str(r.get("reasoning", ""))[:300]}
    return out


def _key(qid):
    return tuple(qid) if isinstance(qid, list) else qid


def opus_overrides(questions, opus: dict) -> tuple[dict, dict]:
    """Return ({id: blended_p}, {id: reasoning}) for judgmental singles the agents
    answered. Only blends where a crowd value AND an Opus forecast both exist."""
    blended, reasoning = {}, {}
    for q in judgmental_questions(questions):
        o = opus.get(_key(q["id"]))
        if not o:
            continue
        pc = _crowd_value(q)
        pf = blend(pc, o["p"], o["edge"])
        blended[q["id"]] = pf
        if o["edge"].lower().strip() != "none" and o.get("reasoning"):
            reasoning[q["id"]] = o["reasoning"]
    return blended, reasoning


def merge(qset_path: str, opus_path: str, out_path: str | None = None, n: int = 1,
          model: str | None = None):
    """Build the mechanical submission, then edge-blend the judgmental subset with
    the Opus forecasts. Re-checks coverage. Everything else is byte-identical to the
    pure-mechanical pipeline."""
    from . import submit as S

    qd = json.loads(Path(qset_path).read_text())
    questions = qd["questions"]
    due_str = qd["forecast_due_date"]
    due = datetime.strptime(due_str, "%Y-%m-%d").date()

    opus = load_opus(opus_path)
    blended, reasoning = opus_overrides(questions, opus)

    # Mechanical singles (use_llm=False: Opus is the only judgment leg here), then
    # overlay the blended judgmental probabilities.
    singles, mech_reasoning = S.build_single_forecasts(questions, due, use_llm=False)
    n_moved = 0
    for qid, p in blended.items():
        d = singles.get(qid)
        if not d:
            continue
        moved = any(abs(p - v) > 1e-9 for v in d.values())
        singles[qid] = {rd: p for rd in d}     # one crowd value -> all (one) horizons
        n_moved += int(moved)
    mech_reasoning.update(reasoning)

    rows = _rows_from_singles(questions, singles, mech_reasoning, due)
    sub = {"organization": S.ORG, "model": model or S.MODEL, "model_organization": S.ORG,
           "question_set": qd["question_set"], "forecasts": rows}
    out_path = out_path or f"data/forecastbench/{due_str}.{S.ORG}.{n}.json"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(sub))

    cov = S._coverage(questions, rows)
    n_single = sum(1 for r in rows if r["direction"] is None)
    n_jud = len(judgmental_questions(questions))
    flag = "" if (cov["market"] >= 0.95 and cov["dataset"] >= 0.95) else "  ⚠ BELOW 95% — EXCLUDED"
    print(f"wrote {out_path}: {len(rows)} rows ({n_single} single, {len(rows)-n_single} combo)")
    print(f"  opus answered {len(opus)}/{n_jud} judgmental; blend MOVED {n_moved} off the crowd anchor")
    print(f"  coverage: market {cov['market']:.1%} ({cov['n_market']})  "
          f"dataset {cov['dataset']:.1%} ({cov['n_dataset']}){flag}")
    return out_path


def _rows_from_singles(questions, singles, reasoning, due):
    """Re-use submit.build_forecasts' row assembly, but seeded with our singles so the
    combo legs are computed from the blended values too (defer-to-best preserved)."""
    from . import submit as S
    from . import dataset as ds

    by_id = {q["id"]: q for q in single_questions(questions)}
    rows = []
    for q in single_questions(questions):
        for rd, p in singles[q["id"]].items():
            rows.append({"id": q["id"], "source": q["source"],
                         "forecast": round(float(p), 6), "resolution_date": rd,
                         "direction": None, "reasoning": reasoning.get(q["id"])})
    for q in questions:
        if not isinstance(q["id"], list):
            continue
        subq = q.get("combination_of")
        if not isinstance(subq, list) or len(subq) != 2:
            continue
        id1, id2 = subq[0]["id"], subq[1]["id"]
        sub_q = by_id.get(id1) or by_id.get(id2)
        rds = sub_q.get("resolution_dates") if sub_q else None
        rds = rds if isinstance(rds, list) else [None]
        is_dataset_combo = q["source"] in ds.DATASET_SOURCES
        for rd in rds:
            p1, p2 = S._sub_p(singles, id1, rd), S._sub_p(singles, id2, rd)
            rho = 0.0
            if is_dataset_combo and rd is not None:
                horizon = (ds._d(rd) - due).days
                rho = ds.combo_corr(subq[0], subq[1], due, horizon)
            j11 = ds.joint_up(p1, p2, rho)
            joints = {(1, 1): j11, (1, -1): p1 - j11,
                      (-1, 1): p2 - j11, (-1, -1): 1 - p1 - p2 + j11}
            for d1, d2 in S.DIRECTIONS:
                j = max(0.0, min(1.0, joints[(d1, d2)]))
                rows.append({"id": q["id"], "source": q["source"],
                             "forecast": round(float(j), 6), "resolution_date": rd,
                             "direction": [d1, d2], "reasoning": None})
    return rows


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "worklist":
        emit_worklist(sys.argv[2], sys.argv[3])
    elif cmd == "merge":
        merge(sys.argv[2], sys.argv[3],
              sys.argv[4] if len(sys.argv) > 4 else None,
              model=sys.argv[5] if len(sys.argv) > 5 else None)
    else:
        print(__doc__)
        sys.exit(1)
