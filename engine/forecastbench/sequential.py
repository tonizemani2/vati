"""Sequential Bayesian update loop — lever 1 from SPEC_EDGE_LEVERS.md.

The one-shot path (traces.py / inference.py) samples a fresh ABSOLUTE probability per chain and means
them; every chain re-anchors from scratch, which is the amateur failure mode (leap to the vivid inside
view, over/under-react in unmeasured ways). The superforecaster habit, and the 2026 agentic method, is
INCREMENTAL updating. We mechanize it by updating in LOGIT space with one likelihood-ratio per driver:

    logit_post = logit(prior) + Σ clamp(delta_i, -CAP, +CAP)

Asking "give me a new probability" each round collapses back to one-shot re-anchoring. Asking "how much
does THIS one driver move the log-odds" forces a genuine Bayesian update and keeps it incremental. CAP
mechanizes "small updates, occasional large, never overreact". The prior is the reference-class base rate
(outside view first), NOT the crowd — we want a signal that can diverge from the market.

LEAK NOTE: --search retrieves live web content, which can surface post-resolution articles on historical
eval rows. The honest first test runs WITHOUT --search (frozen as-of context only, crowd line stripped),
so BOTH sequential and one-shot see identical inputs and the Brier DELTA isolates the reasoning structure.
Absolute Brier is leak-inflated for both equally; the delta is the signal. The real use is live questions.

Run:  python -m engine.forecastbench.sequential --compare --scope market --limit 40 --provider openrouter_free
      python -m engine.forecastbench.sequential --out eval_seq.jsonl --provider openrouter_free   # full
"""
from __future__ import annotations

import json
import math
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from engine import db
from engine.adapters import llm, search

DIR = Path(__file__).resolve().parents[2] / "data" / "forecastbench" / "trainset"
CAP = 1.73          # max |log-odds| move per driver (~5.7x odds); the "never overreact" guard
MAX_ROUNDS = 6      # cap on drivers processed per question


def _clip(p, lo=0.02, hi=0.98):
    return min(hi, max(lo, float(p)))


def _logit(p):
    p = min(1 - 1e-6, max(1e-6, float(p)))
    return math.log(p / (1 - p))


def _sigmoid(x):
    return 1 / (1 + math.exp(-x))


def _anchor(r) -> float:
    """Outside-view prior: reference-class base rate first, then the quant model_prob, else 0.5.
    Deliberately NOT crowd_prob — the loop must be able to diverge from the market."""
    for k in ("base_rate", "model_prob"):
        v = r.get(k)
        if v is not None and 0.0 <= float(v) <= 1.0:
            return float(v)
    return 0.5


def _context(r) -> str:
    """Frozen as-of context with the crowd/market-probability anchor line stripped (so the loop does
    not just copy the market). Truncated; keeps the leak-free series / background."""
    ctx = r.get("context") or ""
    lines = [ln for ln in ctx.splitlines() if "market/crowd probability" not in ln.lower()]
    return "\n".join(lines)[:1400]


def _qblock(r) -> str:
    parts = [f"Question: {r['question']}"]
    if r.get("resolution_criteria"):
        parts.append(f"Resolution criteria: {r['resolution_criteria'][:400]}")
    ctx = _context(r)
    if ctx.strip():
        parts.append(f"Information known as of {r.get('as_of_date')} (use nothing after this date):\n{ctx}")
    return "\n".join(parts)


_DECOMP_SYS = (
    "You are a careful forecaster decomposing a question into its key drivers (Fermi-ization). "
    "List the 3 to 5 distinct considerations that most move the probability of YES, most important "
    "first. One per line, terse. No probabilities, no preamble."
)

_DELTA_SYS = (
    "You are doing one Bayesian update. You are given a forecasting question, the information known "
    "as of a date, your CURRENT probability of YES, and ONE driver to weigh. Decide how this single "
    "driver should move your log-odds of YES, relative to your current belief. Negative pushes toward "
    "NO, positive toward YES, zero if it is already priced into your current belief or is uninformative. "
    "Keep it modest unless the driver is decisive. End with exactly one line: 'Delta: <signed number>' "
    "in log-odds (roughly: 0.4 ~ a mild nudge, 1.0 ~ strong, 1.7 ~ near-decisive)."
)

_ONESHOT_SYS = (
    "You are a careful, calibrated probabilistic forecaster. Use nothing known after the stated date. "
    "Reason briefly: (1) anchor on the reference-class base rate; (2) forces toward YES; (3) forces "
    "toward NO; (4) reconcile into ONE calibrated probability, avoiding 0 and 1. End with exactly one "
    "line: 'Probability: 0.NN'."
)

_PROB = re.compile(r"probability\s*[:=]\s*([01](?:\.\d+)?|\.\d+)", re.I)
_DELTA = re.compile(r"delta\s*[:=]\s*([+-]?\d*\.?\d+)", re.I)


def _parse_prob(text):
    if not text:
        return None
    m = list(_PROB.finditer(text))
    if m:
        try:
            return _clip(float(m[-1].group(1)), 0.01, 0.99)
        except ValueError:
            return None
    for tok in reversed(re.findall(r"\d?\.\d+", text)):
        v = float(tok)
        if 0 <= v <= 1:
            return _clip(v, 0.01, 0.99)
    return None


def _parse_delta(text):
    if not text:
        return None
    m = list(_DELTA.finditer(text))
    if m:
        try:
            return float(m[-1].group(1))
        except ValueError:
            return None
    # fallback: last signed float anywhere
    toks = re.findall(r"[+-]?\d*\.?\d+", text)
    return float(toks[-1]) if toks else None


def _call(conn, prompt, system, provider, proxy):
    """One gated keyless call with roster-failover handled inside llm.complete; None on hard failure."""
    for _ in range(3):
        try:
            return llm.complete(conn, prompt, provider=provider, system=system,
                                max_tokens=400, proxy=proxy, est_cost_cents=0)
        except Exception:
            continue
    return None


def _decompose(conn, r, provider, proxy) -> list[str]:
    txt = _call(conn, _qblock(r), _DECOMP_SYS, provider, proxy)
    if not txt:
        return []
    drivers = []
    for ln in txt.splitlines():
        ln = re.sub(r"^\s*(?:[-*\d.)]+)\s*", "", ln).strip()
        if len(ln) > 8 and "delta" not in ln.lower():
            drivers.append(ln)
    return drivers[:MAX_ROUNDS]


def _delta_logit(conn, r, driver, current_p, provider, proxy):
    prompt = (f"{_qblock(r)}\n\nYour CURRENT probability of YES: {current_p:.3f}\n"
              f"Driver to weigh now: {driver}\nHow should this one driver move your log-odds of YES?")
    txt = _call(conn, prompt, _DELTA_SYS, provider, proxy)
    d = _parse_delta(txt)
    if d is None:
        return 0.0, "(no parse → 0)"
    return max(-CAP, min(CAP, d)), driver


def forecast_one(conn, r, *, provider="openrouter_free", proxy=None, do_search=False) -> dict:
    """Sequential Bayesian forecast for one row. Anchor on base rate, decompose, update in logit space."""
    prior = _anchor(r)
    logit_acc = _logit(prior)
    drivers = _decompose(conn, r, provider, proxy)
    if do_search:
        # optional retrieval: enrich each driver with a fresh keyless search summary (LEAKY on historical)
        try:
            hits = search.search_multi(conn, [f"{r['question']} {d}" for d in drivers][:MAX_ROUNDS],
                                       num_results=4, proxy=proxy)
            drivers = [f"{d}\nRecent: " + "; ".join(h.title for h in hits.get(f"{r['question']} {d}", [])[:3])
                       for d in drivers]
        except Exception:
            pass
    trace = []
    for d in drivers:
        cur = _sigmoid(logit_acc)
        delta, why = _delta_logit(conn, r, d, cur, provider, proxy)
        logit_acc += delta
        trace.append({"driver": why[:120], "delta": round(delta, 3), "p_after": round(_sigmoid(logit_acc), 4)})
    return {"id": r["id"], "prob": _clip(_sigmoid(logit_acc)), "prior": round(prior, 4),
            "n_drivers": len(drivers), "trace": trace}


def oneshot_one(conn, r, *, provider="openrouter_free", proxy=None) -> dict:
    """One-shot baseline on the SAME stripped context, for an apples-to-apples comparison."""
    prompt = (f"{_qblock(r)}\n\nForecast the probability this resolves YES, as of {r.get('as_of_date')}.")
    txt = _call(conn, prompt, _ONESHOT_SYS, provider, proxy)
    p = _parse_prob(txt)
    return {"id": r["id"], "prob": _clip(p if p is not None else _anchor(r))}


def _job(r, provider, proxy, compare, do_search):
    conn = db.connect()
    try:
        seq = forecast_one(conn, r, provider=provider, proxy=proxy, do_search=do_search)
        out = {"row": r, "seq": seq}
        if compare:
            out["one"] = oneshot_one(conn, r, provider=provider, proxy=proxy)
        return out
    finally:
        conn.close()


def _brier(ps, ys):
    return sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(ys)


def main():
    args = sys.argv[1:]
    def opt(flag, default=None, cast=str):
        return cast(args[args.index(flag) + 1]) if flag in args else default
    data = Path(opt("--data", str(DIR / "grpo_eval.jsonl")))
    out = opt("--out")
    provider = opt("--provider", "openrouter_free")
    proxy = opt("--proxy")
    scope = opt("--scope", "market")          # market = the hard half (crowd_prob present); else all
    limit = opt("--limit", None, int)
    workers = int(opt("--workers", 6))
    compare = "--compare" in args
    do_search = "--search" in args

    rows = [json.loads(l) for l in data.open() if l.strip()]
    rows = [r for r in rows if r.get("outcome") in (0, 1)]
    if scope == "market":
        rows = [r for r in rows if r.get("crowd_prob") is not None]
    rows.sort(key=lambda r: str(r["id"]))      # deterministic slice (no RNG)
    if limit:
        rows = rows[:limit]
    print(f"sequential: {len(rows)} rows (scope={scope}, provider={provider}, proxy={proxy}, "
          f"search={do_search}, compare={compare}, workers={workers})", flush=True)

    results = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_job, r, provider, proxy, compare, do_search) for r in rows]
        for i, fut in enumerate(as_completed(futs), 1):
            results.append(fut.result())
            if i % 5 == 0:
                print(f"  ...{i}/{len(rows)}", flush=True)

    if out:
        with open(out, "w") as fh:
            for res in results:
                fh.write(json.dumps({"id": res["seq"]["id"], "prob": res["seq"]["prob"]}) + "\n")
        print(f"wrote {len(results)} predictions → {out}")

    # scoring summary on the same slice (the proof)
    ys = [int(res["row"]["outcome"]) for res in results]
    seq_p = [res["seq"]["prob"] for res in results]
    anch_p = [_clip(_anchor(res["row"])) for res in results]
    print(f"\n=== Brier on {len(ys)} rows (scope={scope}) ===")
    print(f"  anchor (base_rate) : {_brier(anch_p, ys):.4f}")
    if compare:
        one_p = [res["one"]["prob"] for res in results]
        print(f"  one-shot LLM       : {_brier(one_p, ys):.4f}")
    print(f"  sequential Bayesian: {_brier(seq_p, ys):.4f}")
    crowd = [(res["row"].get("crowd_prob"), res["row"]["outcome"]) for res in results
             if res["row"].get("crowd_prob") is not None]
    if crowd:
        print(f"  crowd (reference)  : {_brier([c for c, _ in crowd], [y for _, y in crowd]):.4f}  "
              f"(n={len(crowd)})")
    avg_drivers = sum(res["seq"]["n_drivers"] for res in results) / max(1, len(results))
    print(f"  avg drivers/question: {avg_drivers:.1f}")


if __name__ == "__main__":
    main()
