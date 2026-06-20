"""Market harvester — resolved prediction-market questions → the world-reasoning slice.

Synthetic series questions teach numeric calibration; they don't teach reasoning about elections, wars,
launches, drug approvals, company events. Resolved prediction markets do — and they span industries
natively. This pulls RESOLVED binary markets from Manifold (keyless, huge, free), domain-tags them, and
emits the SAME unified row schema as trainset.py so the two corpora concatenate.

Leak-safe by construction: a market is only harvested once it has RESOLVED (outcome known to us). We set
`as_of_date = createdTime` (the question was askable then) and `resolution_date = resolutionTime`; the
label is the real resolution. `leak_ok` vs --cutoff lets the trainer hold out post-cutoff rows for eval.

Variety by design: we query Manifold's search across a spread of domain seed-terms (ai, election, war,
science, crypto, sports, business, energy, health …) and dedup, so coverage isn't dominated by one topic.

Metaculus is skipped — its API 403s headless; Manifold alone yields large, domain-diverse volume.

Run:  python -m engine.forecastbench.harvest [--cutoff YYYY-MM-DD] [--per-term N] [--min-bettors N]
                                             [--balance] [--out PATH]
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .domains import tag_domain

DATA = Path(__file__).resolve().parents[2] / "data" / "forecastbench"
OUT_DEFAULT = DATA / "trainset" / "market_questions.jsonl"
UA = {"User-Agent": "Mozilla/5.0 (forecastbench-bot; research)"}

# Domain seed-terms → broad, deliberately diverse coverage (not one topic). "" pulls the most-popular
# resolved set generally; the rest pull topic-specific resolved markets. Deduped across terms, so a big
# list with high per-term simply broadens + deepens coverage (markets are where the LLM's edge lives).
SEED_TERMS = [
    "", "ai", "agi", "openai", "anthropic", "google", "deepmind", "gpt", "llm", "chatgpt", "gemini",
    "semiconductor", "nvidia", "tsmc", "chip",
    "election", "president", "senate", "house", "governor", "primary", "nominee", "referendum",
    "parliament", "poll", "vote", "trump", "biden", "harris",
    "war", "ukraine", "russia", "israel", "gaza", "iran", "china", "taiwan", "north korea", "ceasefire",
    "sanction", "nato", "coup", "missile",
    "supreme court", "lawsuit", "indictment", "ban", "regulation", "antitrust", "tariff", "bill",
    "bitcoin", "ethereum", "solana", "crypto", "etf", "stablecoin",
    "stock", "s&p", "nasdaq", "earnings", "ipo", "merger", "acquisition", "bankruptcy", "layoff",
    "fed", "recession", "inflation", "interest rate", "rate cut", "unemployment", "gdp", "jobs report",
    "oil", "gas", "gold", "opec", "energy",
    "spacex", "nasa", "rocket", "starship", "mars", "satellite", "launch",
    "covid", "vaccine", "fda", "drug", "pandemic", "outbreak", "cancer",
    "climate", "hurricane", "temperature", "wildfire", "carbon",
    "nba", "nfl", "mlb", "soccer", "premier league", "world cup", "olympics", "champion", "super bowl",
    "movie", "box office", "oscar", "grammy", "album", "netflix",
    "ceo", "tesla", "apple", "amazon", "meta", "microsoft", "twitter", "spacex",
    "nuclear", "fusion", "superconductor", "quantum", "nobel",
    "reach", "above", "exceed", "record", "billion", "by 2025", "by 2026", "win", "approve", "resign",
]


def _search(term: str, limit: int) -> list[dict]:
    url = ("https://api.manifold.markets/v0/search-markets?"
           f"term={urllib.parse.quote(term)}&filter=resolved&contractType=BINARY"
           f"&limit={limit}&sort=most-popular")
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return []


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).date().isoformat()


def _market_row(m, cutoff, today, min_bettors, drops):
    """Validate + build one unified row from a Manifold market dict; None (+ a drop reason) if unusable."""
    if m.get("resolution") not in ("YES", "NO"):
        drops["not_yes_no"] += 1; return None
    if (m.get("uniqueBettorCount") or 0) < min_bettors:        # liquidity = cleaner signal
        drops["thin_market"] += 1; return None
    created, resolved = m.get("createdTime"), m.get("resolutionTime")
    if not created or not resolved or resolved <= created:
        drops["bad_dates"] += 1; return None
    as_of, res_d = _iso(created), _iso(resolved)
    if datetime.strptime(res_d, "%Y-%m-%d").date() >= today:    # not yet resolved → outcome unknown
        drops["unresolved"] += 1; return None
    q = (m.get("question") or "").strip()
    horizon = (datetime.strptime(res_d, "%Y-%m-%d").date()
               - datetime.strptime(as_of, "%Y-%m-%d").date()).days
    return {
        "id": f"manifold-{m['id']}", "source": "manifold", "kind": "market", "question": q,
        "resolution_criteria": (m.get("textDescription") or "")[:800]
                               or "Resolves YES/NO per the Manifold market.",
        "as_of_date": as_of, "resolution_date": res_d, "horizon_days": horizon,
        "context": f"Prediction market created {as_of}, {m.get('uniqueBettorCount')} forecasters. "
                   f"{(m.get('textDescription') or '')[:400]}".strip(),
        "crowd_prob": None, "model_prob": None,
        "outcome": 1 if m["resolution"] == "YES" else 0,
        "domain": tag_domain(q, m.get("groupSlugs")),
        "base_model_cutoff": cutoff if cutoff else None,
        "leak_ok": (cutoff is None) or (res_d > cutoff), "trace": None,
    }


def harvest(cutoff, per_term: int, min_bettors: int):
    """Topical coverage — search each seed term for resolved binary markets."""
    rows, drops, today = {}, Counter(), datetime.now().date()
    for ti, term in enumerate(SEED_TERMS):
        for m in _search(term, per_term):
            mid = m.get("id")
            if not mid or mid in rows:
                continue
            row = _market_row(m, cutoff, today, min_bettors, drops)
            if row:
                rows[mid] = row
        if (ti + 1) % 8 == 0:
            print(f"  ...{ti+1}/{len(SEED_TERMS)} terms, {len(rows)} markets", flush=True)
    return list(rows.values()), drops


def bulk_harvest(cutoff, target: int, min_bettors: int, max_pages: int = 1200):
    """VOLUME — paginate the full /v0/markets dump (newest→oldest via `before=`), keeping resolved
    binary markets, until `target` rows or the history is exhausted. The real ramp: hundreds of
    thousands of markets, ~10% resolved-binary, all keyless."""
    rows, drops, today = {}, Counter(), datetime.now().date()
    cursor, pages = None, 0
    while len(rows) < target and pages < max_pages:
        url = "https://api.manifold.markets/v0/markets?limit=1000" + (f"&before={cursor}" if cursor else "")
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                page = json.loads(r.read().decode("utf-8", "replace"))
        except Exception:
            break
        if not page:
            break
        for m in page:
            mid = m.get("id")
            if not mid or mid in rows or m.get("outcomeType") != "BINARY":
                continue
            row = _market_row(m, cutoff, today, min_bettors, drops)
            if row:
                rows[mid] = row
        cursor = page[-1]["id"]
        pages += 1
        if pages % 20 == 0:
            print(f"  ...bulk page {pages}, {len(rows)} markets kept", flush=True)
        if len(page) < 1000:
            break          # reached the end of history
    return list(rows.values()), drops


def _poly_row(m, cutoff, today, min_volume, drops):
    """One unified row from a Polymarket Gamma-API market (real-money → cleaner signal, decorrelated
    from Manifold play-money). Binary Yes/No only; outcome from the final resolved outcomePrices."""
    try:
        outs = json.loads(m.get("outcomes") or "[]")
        prices = json.loads(m.get("outcomePrices") or "[]")
    except (json.JSONDecodeError, TypeError):
        drops["bad_json"] += 1; return None
    if [o.lower() for o in outs] != ["yes", "no"]:
        drops["not_yes_no"] += 1; return None
    if not m.get("closed") or m.get("umaResolutionStatus") != "resolved" or len(prices) != 2:
        drops["unresolved"] += 1; return None
    if (m.get("volumeNum") or 0) < min_volume:
        drops["thin_market"] += 1; return None
    start, end = m.get("startDate"), (m.get("closedTime") or m.get("endDate"))
    if not start or not end:
        drops["bad_dates"] += 1; return None
    as_of, res_d = start[:10], end[:10]
    if res_d <= as_of or datetime.strptime(res_d, "%Y-%m-%d").date() >= today:
        drops["bad_dates"] += 1; return None
    outcome = 1 if str(prices[0]).startswith("1") else 0          # Yes-price == "1" → resolved YES
    q = (m.get("question") or "").strip()
    return {
        "id": f"polymarket-{m.get('id')}", "source": "polymarket", "kind": "market", "question": q,
        "resolution_criteria": (m.get("description") or "")[:800] or "Resolves YES/NO per Polymarket (UMA).",
        "as_of_date": as_of, "resolution_date": res_d,
        "horizon_days": (datetime.strptime(res_d, "%Y-%m-%d") - datetime.strptime(as_of, "%Y-%m-%d")).days,
        "context": f"Real-money prediction market opened {as_of}, ${int(m.get('volumeNum') or 0):,} volume. "
                   f"{(m.get('description') or '')[:400]}".strip(),
        "crowd_prob": None, "model_prob": None, "outcome": outcome,
        "domain": tag_domain(q), "base_model_cutoff": cutoff if cutoff else None,
        "leak_ok": (cutoff is None) or (res_d > cutoff), "trace": None,
    }


def poly_harvest(cutoff, target: int, min_volume: int, page: int = 500):
    """Paginate the Polymarket Gamma API (closed markets, by volume) for resolved binary Yes/No."""
    rows, drops, today, offset = {}, Counter(), datetime.now().date(), 0
    while len(rows) < target and offset < 60000:
        url = (f"https://gamma-api.polymarket.com/markets?closed=true&limit={page}&offset={offset}"
               f"&order=volumeNum&ascending=false")
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                got = json.loads(r.read().decode("utf-8", "replace"))
        except Exception:
            break
        if not got:
            break
        for m in got:
            row = _poly_row(m, cutoff, today, min_volume, drops)
            if row:
                rows[row["id"]] = row
        offset += page
        if offset % 2500 == 0:
            print(f"  ...polymarket offset {offset}, {len(rows)} kept", flush=True)
        if len(got) < page:
            break
    return list(rows.values()), drops


def _balance(rows):
    pos = [r for r in rows if r["outcome"] == 1]
    neg = [r for r in rows if r["outcome"] == 0]
    k = min(len(pos), len(neg))
    if k == 0:
        return rows
    def stride(xs):
        step = len(xs) / k
        return [xs[int(j * step)] for j in range(k)]
    return stride(pos) + stride(neg)


def main():
    args = sys.argv[1:]
    def opt(flag, default=None, cast=str):
        return cast(args[args.index(flag) + 1]) if flag in args else default
    cutoff = opt("--cutoff")
    per_term = int(opt("--per-term", 120))
    min_bettors = int(opt("--min-bettors", 25))
    bulk = int(opt("--bulk", 0))           # >0 → paginate the full dump for this many resolved-binary rows
    poly = int(opt("--poly", 0))           # >0 → paginate Polymarket (real-money) for this many rows
    min_volume = int(opt("--min-volume", 2000))
    out = Path(opt("--out", str(OUT_DEFAULT)))
    do_balance = "--balance" in args
    merge = "--merge" in args              # accumulate with whatever is already in --out (dedup by id)

    by_id: dict[str, dict] = {}
    if merge and out.exists():             # keep prior harvest, add to it
        for line in out.open():
            if line.strip():
                r = json.loads(line); by_id[r["id"]] = r
        print(f"  merging onto {len(by_id)} existing rows", flush=True)

    drops = Counter()
    if bulk > 0:
        print(f"bulk-paginating Manifold for {bulk} resolved-binary markets (min_bettors={min_bettors}) ...",
              flush=True)
        brows, bdrops = bulk_harvest(cutoff, bulk, min_bettors)
        for r in brows:
            by_id[r["id"]] = r
        drops += bdrops
    if poly > 0:
        print(f"paginating Polymarket (real-money) for {poly} resolved Yes/No markets "
              f"(min_volume=${min_volume}) ...", flush=True)
        prows, pdrops = poly_harvest(cutoff, poly, min_volume)
        for r in prows:
            by_id[r["id"]] = r
        drops += pdrops
    if "--no-terms" not in args:
        print(f"term-searching Manifold (per_term={per_term}, min_bettors={min_bettors}) ...", flush=True)
        trows, tdrops = harvest(cutoff, per_term, min_bettors)
        for r in trows:
            by_id[r["id"]] = r
        drops += tdrops

    rows = list(by_id.values())
    raw_n = len(rows)
    bal = Counter(r["outcome"] for r in rows)
    if do_balance:
        rows = _balance(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    leak_ok = sum(1 for r in rows if r["leak_ok"])
    print(f"\n  total {raw_n} resolved markets; wrote {len(rows)} → {out}")
    print(f"  raw label balance: YES={bal[1]} NO={bal[0]} ({bal[1]/max(1,raw_n):.0%} YES)")
    print(f"  by domain: {dict(Counter(r['domain'] for r in rows).most_common())}")
    print(f"  leak_ok (res > cutoff): {leak_ok}/{len(rows)}" + (" [no cutoff]" if not cutoff else ""))
    print(f"  dropped: {dict(drops)}")


if __name__ == "__main__":
    main()
