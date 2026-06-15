"""Live prediction-market anchor — the 'already priced?' check at the structural altitude.

The gate's existing price channel (consensus.py) only reads a clean inelastic-vs-elastic EQUITY pair,
which exists for almost none of our structural calls. The sharpest priced-in signal for a judgmental /
structural claim is a LIVE PREDICTION MARKET: if a liquid market already trades the thing at P, the
crowd has arrived and the edge is only the GAP between our P and theirs. This module resolves a claim
to the nearest live market(s) and returns the implied probability + liquidity, keyless and $0.

Legs (keyless public read APIs, graceful degrade — a dead/empty leg is skipped, never faked):
  • Manifold  — api.manifold.markets/v0/search-markets (full-text, returns probability+volume). Primary.
  • Metaculus — metaculus.com/api2/questions (search; community prediction). Defensive parse.

HONEST ASYMMETRY (same lock as consensus-eye): a matching liquid market reliably certifies PRICED at
its probability. NO match is NOT a pre-consensus green light — it can mean the question simply is not
traded anywhere, which is the *common* case for a genuinely early structural call. So 'no market found'
returns UNPRICED-UNSEEN, never CONFIRMED pre-consensus. The judgment stays with the human.

LEAK DISCIPLINE: this reads TODAY's live crowd price for the 'is it priced now' gate — it is never an
input to a retro/holdout score (those are frozen by cutoff). It only informs the forward edge call.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import urllib.parse
import urllib.request

from engine import cost, db

UA = "vaticinus-research/1.0 (forecasting; contact via repo)"
VOLUME_FLOOR = 50.0  # below this a Manifold market is too thin to count as 'the crowd has arrived'


def _gated_json(conn: sqlite3.Connection, url: str, *, action: str, provider: str):
    """Log a $0 'auto' ledger row BEFORE the fetch (rule 3), then GET keyless JSON. None on failure."""
    cost.gate(conn, action=action, provider=provider, units=1, est_cost_cents=0)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 keyless public endpoint
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


# ── Manifold (primary) ────────────────────────────────────────────────────────


def _manifold(conn: sqlite3.Connection, query: str, *, limit: int) -> list[dict]:
    q = urllib.parse.quote(query)
    url = (f"https://api.manifold.markets/v0/search-markets?term={q}"
           f"&filter=open&sort=score&contractType=BINARY&limit={limit}")
    data = _gated_json(conn, url, action="manifold_search", provider="manifold")
    if not isinstance(data, list):
        return []
    out = []
    for m in data:
        if m.get("isResolved") or m.get("outcomeType") != "BINARY":
            continue
        prob, vol = m.get("probability"), float(m.get("volume") or 0)
        if prob is None or vol < VOLUME_FLOOR:
            continue
        out.append({"source": "manifold", "question": m.get("question", ""),
                    "prob": round(float(prob), 3), "volume": round(vol),
                    "url": m.get("url", ""), "close": m.get("closeTime")})
    return out


# ── Metaculus (secondary, defensive) ───────────────────────────────────────────


def _dig(d: dict, *path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _metaculus(conn: sqlite3.Connection, query: str, *, limit: int) -> list[dict]:
    q = urllib.parse.quote(query)
    url = (f"https://www.metaculus.com/api2/questions/?search={q}"
           f"&status=open&forecast_type=binary&limit={limit}&order_by=-activity")
    data = _gated_json(conn, url, action="metaculus_search", provider="metaculus")
    results = (data or {}).get("results") if isinstance(data, dict) else None
    if not results:
        return []
    out = []
    for m in results:
        # community median lives under different keys across API versions — try the known shapes
        prob = (_dig(m, "community_prediction", "full", "q2")
                or _dig(m, "question", "aggregations", "recency_weighted", "latest", "centers")
                or _dig(m, "community_prediction", "history"))
        if isinstance(prob, list):
            prob = prob[0] if prob else None
        if prob is None:
            continue
        try:
            prob = round(float(prob), 3)
        except (TypeError, ValueError):
            continue
        if not 0 <= prob <= 1:
            continue
        out.append({"source": "metaculus", "question": m.get("title", ""),
                    "prob": prob, "volume": m.get("number_of_forecasters"),
                    "url": f"https://www.metaculus.com{m.get('page_url', '')}", "close": m.get("close_time")})
    return out


# ── the anchor ──────────────────────────────────────────────────────────────


def market_anchor(query: str, *, limit: int = 6) -> dict:
    """Resolve a claim/topic to the nearest live prediction market(s). Keyless, $0.

    Returns {query, markets:[...], verdict}. verdict is PRICED (a liquid market trades it) /
    UNPRICED-UNSEEN (none found — NOT a pre-consensus green light, just not traded where we can see).
    """
    conn = db.connect()
    try:
        markets = _manifold(conn, query, limit=limit) + _metaculus(conn, query, limit=limit)
        conn.commit()
    finally:
        conn.close()
    markets.sort(key=lambda m: -(m.get("volume") or 0))
    verdict = "PRICED" if markets else "UNPRICED-UNSEEN"
    return {"query": query, "markets": markets[:limit], "verdict": verdict}


def format_anchor(a: dict) -> str:
    if not a["markets"]:
        return (f"MARKET ANCHOR for '{a['query']}': no live prediction market found (Manifold/Metaculus). "
                f"UNPRICED-UNSEEN — this is NOT a pre-consensus green light; a genuinely early structural "
                f"call is usually not traded anywhere. Judge the edge on physical + narrative channels.")
    lines = [f"MARKET ANCHOR for '{a['query']}': {a['verdict']} — the crowd already trades this:"]
    for m in a["markets"]:
        vol = f"vol {m['volume']}" if m.get("volume") is not None else "vol n/a"
        lines.append(f"  - [{m['source']}] {m['prob']:.0%} — \"{m['question'][:90]}\" ({vol})  {m['url']}")
    lines.append("If a liquid market sits near your P, the thesis is PRICED — the edge is only the GAP "
                 "between your probability and the market's. Quote the gap, not the level.")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    query = " ".join(argv[1:]).strip()
    if not query:
        print("usage: python -m engine.market <claim or topic>")
        return 1
    a = market_anchor(query)
    print(format_anchor(a))
    print("\ncost: $0.00")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
