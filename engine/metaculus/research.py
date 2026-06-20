"""Research phase — the dominant winning lever for judgmental questions (memory:
forecastbench-news-layer-blocked). A frontier model's weights are stale; without current evidence it
is blind on world-events. Every top bot (Mantic, AIA, Cassi) retrieves. Ours retrieves for $0:
keyless DeepInfra writes the queries, keyless Exa fetches the sources.

Flow:  question → LLM drafts K focused, dated search queries → keyless Exa (proxy-rotated, DDG
       fallback) → dedup + rank snippets → a compact dated EVIDENCE DIGEST the forecaster reasons over.

The digest is plain dated snippets, not a pre-chewed conclusion: the forecaster (forecast.py) does the
reasoning, so the ensemble's decorrelation survives. We never inject a probability here.
"""
from __future__ import annotations

import re

from engine import db
from engine.adapters import llm, search

_QGEN_SYSTEM = (
    "You turn a forecasting question into search queries that surface the LATEST decision-relevant "
    "facts. Output 4 short web-search queries, one per line, no numbering. Cover: (a) the most recent "
    "news/status, (b) the specific actors/numbers in the resolution criteria, (c) base-rate / "
    "historical-precedent context. Prefer concrete entities and recent dates over vague phrasing."
)


def _gen_queries(conn, q: dict, today: str, proxy: str | None,
                 provider: str = "openrouter_free") -> list[str]:
    """Ask the LLM roster for focused queries; fall back to the bare title on any failure.
    Default provider is openrouter_free — the old deepinfra_keyless web-embed route is dead (2026-06-12).
    openrouter is keyed+direct so the proxy is not applied to it (the proxy still rotates the Exa fetch)."""
    prompt = (f"Today is {today}.\nQuestion: {q['title']}\n"
              f"Resolution criteria: {(q.get('resolution_criteria') or '')[:600]}\n"
              "Write the 4 search queries.")
    try:
        txt = llm.complete(conn, prompt, provider=provider, system=_QGEN_SYSTEM,
                           max_tokens=250,
                           proxy=(_px(proxy) if provider != "openrouter_free" else None),
                           est_cost_cents=0)
    except Exception:
        txt = ""
    qs = [re.sub(r'^[\s\-\d\.\)"]+', "", ln).strip().strip('"')
          for ln in (txt or "").splitlines()]
    qs = [x for x in qs if len(x) > 8][:4]
    return qs or [q["title"]]


def _px(proxy):
    from engine.forecastbench.traces import _resolve_proxy
    return _resolve_proxy(proxy) if proxy else None


def gather(q: dict, today: str, *, proxy: str | None = None, per_query: int = 5,
           max_snippets: int = 12, with_markets: bool = False,
           provider: str = "openrouter_free") -> tuple[str, list[dict]]:
    """Return (digest_text, sources). `q` is api.question_text(post). today = 'YYYY-MM-DD'.

    proxy: bare provider ('evomi') rotates the source IP per query so a full tournament sweep doesn't
    rate-limit one home IP. Exa keyless works direct from a home IP, so proxy is optional.
    with_markets: also look for a liquid prediction-market price on the SAME event (markets.py) and
    add it as one evidence line — opt-in because it matches nothing on niche questions and costs 2
    extra calls; valuable when the question mix is politics/crypto/macro or Metaculus hides its CP."""
    conn = db.connect()
    try:
        queries = _gen_queries(conn, q, today, proxy, provider=provider)
        results = search.search_multi(conn, queries, num_results=per_query, proxy=proxy)
    finally:
        conn.close()

    seen, picked = set(), []
    for query, hits in results.items():
        for h in hits:
            key = (h.url or h.title).strip()
            if not key or key in seen or not (h.snippet or h.title):
                continue
            seen.add(key)
            picked.append({"title": h.title, "url": h.url, "snippet": h.snippet,
                           "source": h.source, "query": query})
    # interleave-by-query order already roughly diversifies; cap total
    picked = picked[:max_snippets]

    market_line = None
    if with_markets:
        from engine.metaculus import markets
        market_line, m = markets.evidence_line(q["title"])
        if m:
            picked.append({"title": m["question"], "url": m["url"], "snippet": market_line,
                           "source": m["source"], "query": "prediction-market"})

    if not picked:
        return "(no current sources retrieved)", []

    lines = [f"Evidence retrieved as of {today} (treat as current, may be noisy/conflicting):"]
    for i, s in enumerate(picked, 1):
        snip = (s["snippet"] or "").replace("\n", " ").strip()
        lines.append(f"[{i}] {s['title'].strip()} — {snip}".strip(" —")[:400])
    if market_line:
        lines.append(market_line)
    return "\n".join(lines), picked
