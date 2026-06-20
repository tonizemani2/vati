"""Category-aware market-anchor calibration — leak-free, defensive.

The dominant Prophet lever (76% sports = mostly coin-flips): how hard to defer to the Kalshi price
per category. Our live test deviated to 0.21 from a 0.63 price — a Brier bomb. This fits a per-category
blend weight w_c so the agent ties the market on coin-flips and only moves off the price where a
leak-safe signal justifies it.

Two leak-free measurements (NO web search → no outcome leak; June-2026 events are post-cutoff):
  1. market reliability per category — is the midpoint price calibrated? (pure price→outcome)
  2. research-OFF agent prior blended with the price over a w-grid → w_c that minimises Brier.

w_c calibrated this way is a SAFE LOWER bound on market-trust (research, added forward, only lowers it).
Final blend (matches forecast.py): p = sigmoid((1-w)·logit(p_agent) + w·logit(p_mkt)).

Usage:
  uv run python -m engine.prophet.anchor --bench data/prophet/kalshi_bench.jsonl   # compute raw + calibrate
  uv run python -m engine.prophet.anchor --reliability-only                        # instant, no LLM
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from engine.forecastbench.ensemble import _logit, _sigmoid
from engine.prophet.agent import PROXY

RAW_CACHE = "data/prophet/anchor_raw.jsonl"


def _brier(pairs: list[tuple[float, int]]) -> float:
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs) if pairs else float("nan")


def reliability(pairs: list[tuple[float, int]], bins: int = 5) -> list[dict]:
    """Calibration table: per probability bin, predicted mean vs observed frequency."""
    buckets: dict[int, list] = defaultdict(list)
    for p, y in pairs:
        buckets[min(bins - 1, int(p * bins))].append((p, y))
    table = []
    for b in range(bins):
        rows = buckets.get(b, [])
        if rows:
            table.append({"bin": f"{b/bins:.1f}-{(b+1)/bins:.1f}", "n": len(rows),
                          "pred": round(sum(p for p, _ in rows) / len(rows), 3),
                          "obs": round(sum(y for _, y in rows) / len(rows), 3)})
    return table


def market_reliability(recs: list[dict]) -> dict:
    by_cat: dict[str, list] = defaultdict(list)
    allp = []
    for r in recs:
        pair = (r["yes_price"], r["outcome"])
        by_cat[r["category"]].append(pair); allp.append(pair)
    return {"overall": {"brier": round(_brier(allp), 4), "reliability": reliability(allp)},
            "by_category": {c: {"n": len(v), "brier": round(_brier(v), 4)} for c, v in sorted(by_cat.items())}}


def _yes_question(r: dict) -> dict:
    """Frame the market's YES side as an explicit binary question for the ensemble."""
    return {"title": f"{r['title']}  Will the outcome be '{r['yes_label']}'?",
            "resolution_criteria": r.get("rules") or f"Resolves YES iff '{r['yes_label']}'.",
            "description": "", "fine_print": ""}


def compute_raw(recs: list[dict], log=print) -> dict[str, float]:
    """Leak-safe p_agent per market: research-OFF ensemble prior, NO market anchor. Resumable cache."""
    from engine.metaculus import forecast
    cache_path = Path(RAW_CACHE); cache_path.parent.mkdir(parents=True, exist_ok=True)
    done: dict[str, float] = {}
    if cache_path.exists():
        for line in cache_path.read_text().splitlines():
            if line.strip():
                d = json.loads(line); done[d["ticker"]] = d["p_raw"]
    with cache_path.open("a") as fh:
        for i, r in enumerate(recs, 1):
            if r["ticker"] in done:
                continue
            today = (r["close_time"] or "")[:10] or None
            out = forecast.forecast_question(_yes_question(r), today=today, crowd=None,
                                             do_research=False, proxy=PROXY, n=1,
                                             min_models=5, fill_passes=2)
            p = float(out["prob"]); done[r["ticker"]] = p
            fh.write(json.dumps({"ticker": r["ticker"], "p_raw": p}) + "\n"); fh.flush()
            log(f"  [{i}/{len(recs)}] {r['category']:<10} raw={p:.3f} mkt={r['yes_price']:.3f} y={r['outcome']} {r['yes_label'][:24]}")
    return done


def calibrate_w(recs: list[dict], raw: dict[str, float], log=print) -> dict:
    """Per-category w* minimising blended Brier; compare to market-alone and agent-alone."""
    by_cat: dict[str, list] = defaultdict(list)
    for r in recs:
        if r["ticker"] in raw:
            by_cat[r["category"]].append((raw[r["ticker"]], r["yes_price"], r["outcome"]))
    grid = [i / 20 for i in range(21)]  # 0.0 .. 1.0
    result = {}
    allrows = [row for rows in by_cat.values() for row in rows]
    for scope, rows in list(by_cat.items()) + [("ALL", allrows)]:
        if not rows:
            continue
        mkt = _brier([(p_m, y) for _, p_m, y in rows])
        agt = _brier([(p_a, y) for p_a, _, y in rows])
        best_w, best_b = 1.0, mkt
        for w in grid:
            b = _brier([(_sigmoid((1 - w) * _logit(p_a) + w * _logit(p_m)), y) for p_a, p_m, y in rows])
            if b < best_b:
                best_w, best_b = w, b
        result[scope] = {"n": len(rows), "w_star": best_w, "brier_at_w": round(best_b, 4),
                         "market_brier": round(mkt, 4), "agent_brier": round(agt, 4),
                         "lift_vs_market": round(mkt - best_b, 4)}
    return result


def main() -> None:
    args = sys.argv[1:]
    bench = args[args.index("--bench") + 1] if "--bench" in args else "data/prophet/kalshi_bench.jsonl"
    recs = [json.loads(l) for l in Path(bench).read_text().splitlines() if l.strip()]

    print("== MARKET RELIABILITY (leak-free) ==")
    print(json.dumps(market_reliability(recs), indent=2))
    if "--reliability-only" in args:
        return

    print(f"\n== research-OFF agent prior over {len(recs)} markets (proxy={PROXY}) ==")
    raw = compute_raw(recs)
    print("\n== CATEGORY-AWARE ANCHOR w* (leak-safe; w=1 ⇒ trust market fully) ==")
    print(json.dumps(calibrate_w(recs, raw), indent=2))


if __name__ == "__main__":
    main()
