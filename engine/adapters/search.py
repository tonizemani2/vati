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


async def _search_async(query: str, num_results: int) -> list[SearchResult]:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
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
) -> list[SearchResult]:
    """Keyless web search (Exa → DDG). Logs a $0 'auto' ledger row before the call."""
    cost.gate(
        conn,
        action="exa_keyless_search",
        provider="exa",
        units=1,
        est_cost_cents=0,
        funded_ref=funded_ref,
    )
    return asyncio.run(_search_async(query, num_results))


def search_multi(
    conn: sqlite3.Connection,
    queries: list[str],
    num_results: int = 10,
) -> dict[str, list[SearchResult]]:
    """Bulk keyless search: one $0 'auto' ledger row covering the batch, logged first."""
    cost.gate(
        conn,
        action="exa_keyless_search_bulk",
        provider="exa",
        units=len(queries),
        est_cost_cents=0,
    )

    async def _run() -> dict[str, list[SearchResult]]:
        out: dict[str, list[SearchResult]] = {}
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            for q in queries:
                res = await _exa.search(q, num_results, client)
                if not res:
                    res = await _ddg.search(q, num_results, client)
                out[q] = res
        return out

    return asyncio.run(_run())
