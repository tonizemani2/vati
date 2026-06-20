"""Kalshi harvester + leak-free market-baseline — the honest bar before we go live.

Pulls REAL resolved Kalshi binary markets across curated, in-season series (sports-weighted to
match Prophet's ~76%-sports mix), and reconstructs the PRE-CLOSE price from candlesticks (the
settled price is post-resolution = leaky; the candle at close−lead mirrors the live agent input).

Two honest, LLM-free outputs:
  • market baseline Brier (price→outcome) — the number our agent must beat.
  • a representative event set (with market_stats) to drive agent backtests + the live loop.

Leak note: anchor price + outcome are clean. Running the research agent on these RESOLVED events is
NOT leak-free (web search sees the result) — that number is an upper bound, never a forward proof.

Usage:
  uv run python -m engine.prophet.kalshi --n 60 --lead-hours 1 --out data/prophet/kalshi_bench.jsonl
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

B = "https://api.elections.kalshi.com/trade-api/v2"

# Curated real series by category. Sports-weighted to mirror the production slate (~76% sports).
# Off-season / empty series are skipped gracefully.
SERIES: dict[str, list[str]] = {
    "Sports": [
        "KXNBAGAME", "KXMLBGAME", "KXNHLGAME", "KXWNBAGAME",
        "KXATPMATCH", "KXWTAMATCH", "KXEPLGAME", "KXUCLGAME", "KXNCAAFGAME",
    ],
    "Climate and Weather": ["KXHIGHNY", "KXHIGHLAX", "KXHIGHCHI", "KXHIGHMIA", "KXHIGHAUS"],
    "Economics": ["KXHOUSINGSTART", "KXCPIYOY", "KXU3", "KXPAYROLLS"],
    "Financials": ["KXNASDAQ100", "KXSP500", "KXBTCD", "KXETH"],
    "Politics": ["KXSECRETARY", "KXPRES"],
}


def _get(path: str, **params) -> dict:
    url = B + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"User-Agent": "vaticinus/1.0"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 4:
                time.sleep(1.5 * (2 ** attempt))  # back off on Kalshi rate-limit
                continue
            raise


def _ts(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _anchor_price(series: str, ticker: str, open_ts: int, close_ts: int,
                  lead_frac: float | None, lead_hours: float) -> float | None:
    """Yes-price at the forecast anchor from candlesticks; the leak-free input.

    lead_frac (preferred): price at open + frac·(close−open) — the project's `early_crowd` method,
    genuinely uncertain and uniform across event types. Falls back to close−lead_hours if no open.
    """
    if lead_frac is not None and open_ts and close_ts > open_ts:
        cutoff = int(open_ts + lead_frac * (close_ts - open_ts))
    else:
        cutoff = close_ts - int(lead_hours * 3600)
    start = cutoff - 3 * 86400
    for interval in (60, 1440):
        try:
            c = _get(f"/series/{series}/markets/{ticker}/candlesticks",
                     start_ts=start, end_ts=cutoff, period_interval=interval)
        except Exception:
            continue
        best = None
        for cs in c.get("candlesticks", []):
            if cs.get("end_period_ts", 0) > cutoff:
                continue
            pr = cs.get("price") or {}
            p = _f(pr.get("close_dollars")) or _f(pr.get("mean_dollars"))
            if p is None:
                ya, yb = _f((cs.get("yes_ask") or {}).get("close_dollars")), _f((cs.get("yes_bid") or {}).get("close_dollars"))
                if ya is not None and yb is not None:
                    p = (ya + yb) / 2
            if p is not None and 0.0 < p < 1.0:
                best = p
        if best is not None:
            return best
    return None


def harvest(n: int = 60, lead_hours: float = 1.0, lead_frac: float | None = 0.5,
            per_series: int = 6, min_vol: float = 5000.0, log=print) -> list[dict]:
    """One real resolved binary market per event, sports-weighted, with a leak-free anchor price."""
    # 76% sports target
    want = {"Sports": int(round(n * 0.76))}
    rest = [c for c in SERIES if c != "Sports"]
    for i, c in enumerate(rest):
        want[c] = (n - want["Sports"]) // len(rest)

    out: list[dict] = []
    for category, target in want.items():
        got = 0
        for series in SERIES[category]:
            if got >= target:
                break
            try:
                d = _get("/markets", series_ticker=series, status="settled", limit=50)
            except Exception as e:
                log(f"  {series}: fetch err {repr(e)[:60]}"); continue
            seen_events = set()
            series_got = 0
            for m in d.get("markets", []):
                if got >= target or series_got >= per_series:
                    break
                res = m.get("result")
                if res not in ("yes", "no"):
                    continue
                ev = m.get("event_ticker")
                if ev in seen_events:  # one market per game/event → diverse, no anti-correlated dupes
                    continue
                if (_f(m.get("volume_fp")) or 0) < min_vol:
                    continue
                ct = m.get("close_time")
                if not ct:
                    continue
                ot = m.get("open_time")
                price = _anchor_price(series, m["ticker"], _ts(ot) if ot else 0, _ts(ct),
                                      lead_frac, lead_hours)
                if price is None:
                    continue
                seen_events.add(ev)
                got += 1; series_got += 1
                out.append({
                    "ticker": m["ticker"], "event_ticker": ev, "series": series, "category": category,
                    "title": m.get("title") or "", "yes_label": m.get("yes_sub_title") or "Yes",
                    "no_label": m.get("no_sub_title") or "No", "rules": m.get("rules_primary") or "",
                    "close_time": ct, "yes_price": round(price, 4),
                    "outcome": 1 if res == "yes" else 0,
                })
            log(f"  {series}: +{got}/{target} ({category})")
    log(f"harvested {len(out)} markets")
    return out


def market_baseline(recs: list[dict]) -> dict:
    """Brier of the pre-close market price vs outcome — the bar to beat. Pure data, leak-free."""
    from collections import defaultdict
    by_cat: dict[str, list] = defaultdict(list)
    for r in recs:
        by_cat[r["category"]].append((r["yes_price"], r["outcome"]))
    def brier(rows): return sum((p - y) ** 2 for p, y in rows) / len(rows)
    overall = [(r["yes_price"], r["outcome"]) for r in recs]
    return {
        "n": len(recs),
        "market_brier": round(brier(overall), 4) if overall else None,
        "market_1mb": round(1 - brier(overall), 4) if overall else None,
        "by_category": {c: {"n": len(v), "brier": round(brier(v), 4)} for c, v in sorted(by_cat.items())},
    }


def to_event(r: dict) -> dict:
    """Kalshi record → Prophet event dict with leak-free market_stats anchor (for agent backtests)."""
    return {
        "event_ticker": r["event_ticker"], "market_ticker": r["ticker"],
        "title": r["title"], "category": r["category"], "rules": r["rules"],
        "close_time": r["close_time"], "outcomes": [r["yes_label"], r["no_label"]],
        "market_stats": {r["yes_label"]: {"last_price": r["yes_price"]}},
        "_outcome": r["yes_label"] if r["outcome"] == 1 else r["no_label"],
    }


def main() -> None:
    args = sys.argv[1:]
    def opt(f, d): return args[args.index(f) + 1] if f in args else d
    n = int(opt("--n", "60")); lead = float(opt("--lead-hours", "1"))
    lf = opt("--lead-frac", "0.5"); lead_frac = None if lf in ("none", "None", "") else float(lf)
    out = opt("--out", "data/prophet/kalshi_bench.jsonl")

    recs = harvest(n=n, lead_hours=lead, lead_frac=lead_frac, per_series=8)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    base = market_baseline(recs)
    anchor = f"midpoint (lead_frac {lead_frac})" if lead_frac is not None else f"close−{lead}h"
    print(f"\n== MARKET BASELINE (anchor: {anchor}, leak-free) ==")
    print(json.dumps(base, indent=2))
    print(f"\nwrote {len(recs)} → {out}")
    print("Prophet agent-board bar to beat: Agent GPT-5.5 1-Brier 0.9441; Kalshi market overall ~0.851.")


if __name__ == "__main__":
    main()
