"""Crowd-probability enrichment — the #1 data lever (FORECAST_LLM.md §0, "biggest single feature").

At ForecastBench test time EVERY market question arrives WITH `freeze_datetime_value` — the crowd's
probability at the freeze date. It is both the baseline to beat AND the single strongest market-half
feature: the winning move on the crowd-ceilinged market half is anchor-on-the-crowd-then-adjust. But our
harvested Manifold market rows (harvest.py) carry `crowd_prob: None` — they set as_of = market creation,
when the crowd prob is just the ~0.5 seed. So the model never learns to use the anchor it is handed at
test time. Only ~216 train rows had a real crowd prob, and bench.py's were poisoned by series levels.

This reconstructs a LEAK-SAFE crowd probability for resolved Manifold markets, exactly mirroring
ForecastBench: pick a freeze date that leaves a ForecastBench-style horizon to resolution, then read the
market's probability AT that freeze from its bet history (Manifold `/v0/bets`, keyless, `probAfter` of
the latest bet ≤ freeze). The outcome stays strictly AFTER the freeze, so it is genuine ex-ante crowd
signal, never leakage. The row's as_of/horizon are moved to the freeze; crowd_prob is set; curate.py then
surfaces it as a structured anchor → the model trains on (crowd anchor → reason → adjust), in-distribution
with the live submission pipeline.

Efficiency/coverage: bets come newest-first; we page back only until the freeze (≤ cap pages). On
hyper-active markets that blow the cap we accept the OLDEST fetched bet instead of dropping (a later but
still pre-resolution freeze → shorter horizon, logged as 'shortened'), keeping coverage high. Markets
left shorter than `--min-horizon` days are skipped (crowd_prob stays None; row kept). We enrich the
highest-liquidity markets first (the ones curate.py keeps anyway).

Run:  python -m engine.forecastbench.crowd                      # enrich market_questions.jsonl in place
      python -m engine.forecastbench.crowd --limit 12000 --workers 3 --dry-run
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DIR = Path(__file__).resolve().parents[2] / "data" / "forecastbench" / "trainset"
MARKET_FILE = DIR / "market_questions.jsonl"
UA = {"User-Agent": "Mozilla/5.0 (forecastbench-bot; research)"}
# Days-before-close to aim the freeze at — the ForecastBench horizon band. We take the LONGEST that
# still leaves the market a real trading life before the freeze (so a crowd has actually formed).
HORIZON_LADDER = [180, 90, 30]
DAY = 86400000


def _iso_to_ms(d: str) -> int:
    return int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)


def _ms_to_iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).date().isoformat()


def _bets_page(cid: str, before: str | None):
    url = f"https://api.manifold.markets/v0/bets?contractId={cid}&limit=1000" + (f"&before={before}" if before else "")
    for _ in range(3):                                  # transient 429/timeout → brief backoff
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception:
            time.sleep(1.5)
    return None


def _crowd_at_freeze(cid: str, freeze_ms: int, cap_pages: int = 8):
    """probAfter of the latest bet ≤ freeze. Returns (prob, effective_freeze_ms, status).
    If the cap is blown (very active market, all fetched bets are AFTER freeze), accept the OLDEST
    fetched bet's prob (a later, still pre-resolution freeze) so the market is kept, not dropped."""
    cursor, pages, oldest = None, 0, None
    while pages < cap_pages:
        page = _bets_page(cid, cursor)
        if page is None:
            return None, None, "fetch_error"
        if not page:
            return None, None, "no_bets"
        for bet in page:                                # newest-first within a page
            if bet["createdTime"] <= freeze_ms and bet.get("probAfter") is not None:
                return bet["probAfter"], freeze_ms, "ok"
            oldest = bet                                # track the earliest-time bet we've seen
        cursor = page[-1]["id"]
        pages += 1
        if len(page) < 1000:                            # reached the first ever bet, none ≤ freeze
            return None, None, "freeze_before_first_bet"
    if oldest is not None and oldest.get("probAfter") is not None:   # cap blown → salvage
        return oldest["probAfter"], oldest["createdTime"], "shortened"
    return None, None, "cap_blown"


_FORECASTERS = None


def _liquidity(r) -> int:
    import re
    global _FORECASTERS
    if _FORECASTERS is None:
        _FORECASTERS = re.compile(r"([\d,]+)\s+forecasters")
    m = _FORECASTERS.search(str(r.get("context") or ""))
    return int(m.group(1).replace(",", "")) if m else 0


def _enrich_row(r, min_horizon_days):
    """Reconstruct a leak-safe crowd prob + move as_of to the freeze. Returns (row, status)."""
    cid = r["id"].replace("manifold-", "")
    try:
        created = _iso_to_ms(r["as_of_date"]); resolved = _iso_to_ms(r["resolution_date"])
    except Exception:
        return r, "bad_dates"
    life = resolved - created
    if life <= min_horizon_days * DAY:
        return r, "too_short"
    freeze = None
    for h in HORIZON_LADDER:                            # longest horizon that still leaves trading life
        f = resolved - h * DAY
        if f >= created + max(DAY, int(life * 0.05)):
            freeze = f; break
    if freeze is None:                                  # short-lived market: freeze at 60% of life
        freeze = created + int(life * 0.6)
    prob, eff, status = _crowd_at_freeze(cid, freeze)
    if prob is None:
        return r, status
    horizon = (resolved - eff) // DAY
    if horizon < min_horizon_days:
        return r, "too_short_after"
    nf = _liquidity(r)
    r = dict(r)
    r["as_of_date"] = _ms_to_iso(eff)
    r["horizon_days"] = int(horizon)
    r["crowd_prob"] = round(float(prob), 4)
    r["context"] = (f"Prediction market '{r['question']}', {nf} forecasters, trading since "
                    f"{_ms_to_iso(created)}. Frozen for forecasting as of {r['as_of_date']} "
                    f"({horizon}d before resolution).").strip()
    return r, status


def main():
    args = sys.argv[1:]
    def opt(flag, default=None, cast=str):
        return cast(args[args.index(flag) + 1]) if flag in args else default
    limit = int(opt("--limit", 12000))
    workers = int(opt("--workers", 3))
    min_horizon = int(opt("--min-horizon", 7))
    inp = Path(opt("--in", str(MARKET_FILE)))
    dry = "--dry-run" in args

    rows = [json.loads(l) for l in inp.open() if l.strip()]
    manifold = [r for r in rows if r.get("source") == "manifold" and r.get("crowd_prob") is None]
    other = [r for r in rows if not (r.get("source") == "manifold" and r.get("crowd_prob") is None)]
    manifold.sort(key=_liquidity, reverse=True)         # enrich the liquid markets curate.py keeps first
    todo = manifold[:limit]
    skipped_tail = manifold[limit:]
    print(f"enriching {len(todo)} Manifold markets (of {len(manifold)} crowd-less; {len(other)} other rows "
          f"untouched), workers={workers}, min_horizon={min_horizon}d ...", flush=True)

    stats, enriched = Counter(), []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_enrich_row, r, min_horizon): r for r in todo}
        for i, fut in enumerate(as_completed(futs)):
            row, status = fut.result()
            stats[status] += 1
            enriched.append(row if status in ("ok", "shortened") else futs[fut])
            if (i + 1) % 200 == 0:
                got = stats["ok"] + stats["shortened"]
                print(f"  ...{i+1}/{len(todo)}  crowd_set={got} ({got/(i+1):.0%})  "
                      f"{(time.time()-t0)/(i+1):.2f}s/mkt  {dict(stats)}", flush=True)

    got = stats["ok"] + stats["shortened"]
    print(f"\n  crowd_prob set on {got}/{len(todo)} ({got/max(1,len(todo)):.0%})  | status {dict(stats)}")
    # quick leak-free sanity: Brier of the reconstructed crowd vs the known outcome (lower is better,
    # but the point is it's a REAL signal, not that it's great — the model anchors AND adjusts).
    cp = [(r["crowd_prob"], r["outcome"]) for r in enriched if r.get("crowd_prob") is not None]
    if cp:
        b = sum((p - y) ** 2 for p, y in cp) / len(cp)
        ymean = sum(y for _, y in cp) / len(cp)
        print(f"  reconstructed-crowd Brier {b:.4f} on {len(cp)} markets (YES rate {ymean:.0%}) "
              f"— a real ex-ante signal the model can anchor on")
    if dry:
        print("  --dry-run: nothing written"); return
    out_rows = enriched + skipped_tail + other
    raw = inp.with_name(inp.stem + "_precrowd.jsonl")
    if not raw.exists():
        raw.write_text("".join(json.dumps(r) + "\n" for r in rows))
    inp.write_text("".join(json.dumps(r) + "\n" for r in out_rows))
    print(f"  wrote {len(out_rows)} rows → {inp} (original → {raw.name})")


if __name__ == "__main__":
    main()
