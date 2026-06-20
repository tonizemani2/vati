"""Search adapter — typed, sync wrapper over the vendored keyless Exa client.

Exa keyless is free ($0), so the cost gate logs it at cost 0 (`approval_status='auto'`)
and lets it run — but it still goes through the gate, so every external call is on the
ledger (rule 3). Exa first; DuckDuckGo HTML on empty. The vendored client is async; we run
it via `asyncio.run` so the rest of the engine (CLI, sqlite) stays plain sync.
"""

from __future__ import annotations

import asyncio
import sqlite3

import httpx

from engine import cost
from engine.adapters._vendor.exa_search import DDGClient, ExaClient, SearchResult

_exa = ExaClient()
_ddg = DDGClient()


def _resolve_proxy(spec):
    """Bare provider name ('evomi'/'floxy') → a fresh rotating proxy URL (dodges per-IP rate
    limits when sweeping many questions); a full URL passes through; None = direct (home IP,
    which is what the vendored keyless dance assumes by default)."""
    if not spec:
        return None
    if "://" in spec:
        return spec
    from engine.adapters import proxy as px
    return px.proxy_url(spec)


def _client(proxy: str | None):
    """A fresh async client, optionally tunnelled through a rotating proxy (httpx 0.28 `proxy=`)."""
    return httpx.AsyncClient(timeout=15, follow_redirects=True,
                             proxy=_resolve_proxy(proxy) if proxy else None)


async def _search_async(query: str, num_results: int, proxy: str | None) -> list[SearchResult]:
    async with _client(proxy) as client:
        results = await _exa.search(query, num_results, client)
        if results:
            return results
        return await _ddg.search(query, num_results, client)


def search(
    conn: sqlite3.Connection,
    query: str,
    num_results: int = 10,
    *,
    funded_ref: str | None = None,
    proxy: str | None = None,
) -> list[SearchResult]:
    """Keyless web search (Exa → DDG). Logs a $0 'auto' ledger row before the call.

    `proxy` (bare provider name or full URL) rotates the source IP — useful when sweeping a whole
    tournament's questions in one run, where Exa/DDG would otherwise rate-limit a single home IP."""
    cost.gate(
        conn,
        action="exa_keyless_search",
        provider="exa",
        units=1,
        est_cost_cents=0,
        funded_ref=funded_ref,
    )
    return asyncio.run(_search_async(query, num_results, proxy))


def search_multi(
    conn: sqlite3.Connection,
    queries: list[str],
    num_results: int = 10,
    *,
    proxy: str | None = None,
    text_chars: int = 300,
) -> dict[str, list[SearchResult]]:
    """Bulk keyless search: one $0 'auto' ledger row covering the batch, logged first.

    A fresh proxy IP is drawn PER QUERY (a new client each query) so a multi-query research
    pass spreads across IPs rather than hammering one. `text_chars` keeps more of Exa's indexed
    page text per hit (deep research reads it; the shallow snippet pass keeps the 300 default)."""
    cost.gate(
        conn,
        action="exa_keyless_search_bulk",
        provider="exa",
        units=len(queries),
        est_cost_cents=0,
    )

    async def _run() -> dict[str, list[SearchResult]]:
        out: dict[str, list[SearchResult]] = {}
        for q in queries:
            async with _client(proxy) as client:
                res = await _exa.search(q, num_results, client, text_chars=text_chars)
                if not res:
                    res = await _ddg.search(q, num_results, client)
                out[q] = res
        return out

    return asyncio.run(_run())
