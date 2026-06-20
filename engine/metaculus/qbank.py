"""engine/metaculus/qbank.py — a leak-free historical question bank for backtesting & training.

The breakthrough that makes a REAL backtest possible (Ruben, 2026-06-12): use an OLD-cutoff model.
A model whose training cutoff precedes a question's resolution makes a genuine ex-ante forecast (the
outcome is NOT in its weights) while WE already know the truth — so we can score it leakage-free
([[parametric-leakage]], engine/holdout.py). gpt-4-0613 has a 2021-09 cutoff yet forecasts well, so
EVERY question resolving 2022+ is a clean test for it.

This module harvests that test set. Source = resolved BINARY Manifold markets (keyless, public, with a
real crowd + outcome + dated resolution). We harvest by TOPIC TERM (reaches back through history, unlike
the global recency sort which is swamped by the newest year) across the forecasting domains that look
like the Metaculus Cup (politics, macro, geopolitics, tech/AI, science, business, crypto, climate).

Filters (on the QUESTION, never the outcome → no selection bias on what we measure):
  • liquid (≥ MIN_BETTORS, ≥ MIN_VOL)         — a thin market is noise, not a crowd
  • a real forecasting horizon (≥ MIN_HORIZON_DAYS) — drops intraday finance & same-day sports lines
  • not pure sports                            — research-blind & unlike Cup judgmental questions

Output: data/metaculus/qbank.jsonl, one question per line with full dated metadata. Reusable as a
backtest set (calibrate.py), a model eval, and supervised/RL signal for the fine-tuned "top model".
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone

_UA = {"User-Agent": "Mozilla/5.0"}
_MANIFOLD = "https://api.manifold.markets/v0"
BANK_PATH = "data/metaculus/qbank.jsonl"

MIN_BETTORS = 8
MIN_VOL = 200.0
MIN_HORIZON_DAYS = 14

# Diverse forecasting domains that resemble the Metaculus Cup. Each term is paginated; the union (after
# dedup) is the bank. More terms → more coverage; these reach 2022 comfortably.
TERMS = [
    "election", "president", "senate", "congress", "supreme court", "referendum",
    "interest rate", "recession", "inflation", "GDP", "unemployment", "stock market",
    "war", "ceasefire", "Ukraine", "China Taiwan", "Israel", "nuclear", "sanctions", "coup",
    "OpenAI", "GPT", "AI model", "artificial intelligence", "self-driving", "chip",
    "SpaceX", "rocket launch", "NASA", "fusion", "vaccine", "FDA approval", "pandemic",
    "bitcoin", "ethereum", "crypto", "IPO", "acquisition", "bankruptcy", "CEO",
    "climate", "temperature record", "hurricane", "oil price", "OPEC",
]

_SPORTS = (" defeat ", " beat ", " vs ", " vs. ", "premier league", "nba ", " nfl ", " ufc ",
           "world cup", "champions league", "super bowl", "grand prix", " odds ", "leading scorer",
           "win the match", " fc ", "playoff", "wembanyama", "super rugby", " open final")


def _get(url: str):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _ok(m: dict) -> bool:
    if m.get("outcomeType") != "BINARY" or m.get("resolution") not in ("YES", "NO"):
        return False
    if (m.get("uniqueBettorCount") or 0) < MIN_BETTORS or (m.get("volume") or 0) < MIN_VOL:
        return False
    title = (m.get("question") or "")
    if any(s in (" " + title.lower() + " ") for s in _SPORTS):
        return False
    cms, rms = m.get("createdTime"), m.get("resolutionTime")
    if not cms or not rms or (rms - cms) < MIN_HORIZON_DAYS * 86400_000:
        return False
    return True


def _row(m: dict) -> dict:
    cms, rms = m["createdTime"], m["resolutionTime"]
    cd = datetime.fromtimestamp(cms / 1000, timezone.utc).date()
    rd = datetime.fromtimestamp(rms / 1000, timezone.utc).date()
    return {
        "id": m["id"], "title": m.get("question", ""),
        "outcome": m["resolution"] == "YES",
        "created_ms": cms, "resolve_ms": rms,
        "created_date": cd.isoformat(), "resolved_date": rd.isoformat(),
        "created_year": cd.year, "resolved_year": rd.year,
        "horizon_days": round((rms - cms) / 86400_000),
        "crowd_final": m.get("probability"),
        "vol": m.get("volume") or 0, "bettors": m.get("uniqueBettorCount") or 0,
        "url": m.get("url", ""),
    }


def harvest(*, terms=TERMS, max_per_term: int = 600, page: int = 200, log=print) -> list[dict]:
    """Paginate each topic term (filter=resolved, resolve-date order), keep Cup-like liquid binary
    questions, dedup by id. Returns the bank (also written by `build`)."""
    by_id: dict[str, dict] = {}
    for ti, term in enumerate(terms, 1):
        kept_before = len(by_id)
        for off in range(0, max_per_term, page):
            url = (f"{_MANIFOLD}/search-markets?term={urllib.parse.quote(term)}&filter=resolved"
                   f"&sort=resolve-date&contractType=BINARY&limit={page}&offset={off}")
            try:
                ms = _get(url)
            except Exception:
                break
            if not ms:
                break
            for m in ms:
                if _ok(m) and m["id"] not in by_id:
                    by_id[m["id"]] = _row(m)
            if len(ms) < page:
                break
        log(f"   [{ti}/{len(terms)}] {term:<18} +{len(by_id) - kept_before:<4} (total {len(by_id)})")
    return list(by_id.values())


def build(*, path: str = BANK_PATH, log=print, **kw) -> dict:
    """Harvest → write the bank jsonl → report the year distribution."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    log(f"📚 Harvesting leak-free question bank → {path}")
    rows = harvest(log=log, **kw)
    rows.sort(key=lambda r: r["resolved_date"])
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    yr = Counter(r["resolved_year"] for r in rows)
    base = sum(r["outcome"] for r in rows) / len(rows) if rows else 0
    log(f"\n   {len(rows)} questions · resolve-year {dict(sorted(yr.items()))} · base-rate YES {base:.2f}")
    log(f"   saved → {path}")
    return {"n": len(rows), "by_year": dict(sorted(yr.items())), "base_rate": base, "path": path}


def load(path: str = BANK_PATH, *, resolved_after_year: int | None = None,
         max_resolved_year: int | None = None) -> list[dict]:
    """Load the bank, optionally restricting to a resolution-year window (for per-model leak gating)."""
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if resolved_after_year is not None and r["resolved_year"] <= resolved_after_year:
                continue
            if max_resolved_year is not None and r["resolved_year"] > max_resolved_year:
                continue
            out.append(r)
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Harvest the leak-free historical question bank.")
    ap.add_argument("--max-per-term", type=int, default=600)
    ap.add_argument("--path", default=BANK_PATH)
    a = ap.parse_args()
    build(path=a.path, max_per_term=a.max_per_term)
