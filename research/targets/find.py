#!/usr/bin/env python3
"""Keyless people-finder search CLI for the target-harvest agents.

Usage:
  uv run python research/targets/find.py "query string" [num_results]

Prints JSON: [{"title","url","snippet","source"}]. Tries keyless Exa first
(unlimited, free), falls back to DuckDuckGo HTML. No API key, home IP.
"""
import asyncio
import json
import sys

import httpx

from engine.adapters._vendor.exa_search import ExaClient, DDGClient


async def run(query: str, num: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as c:
        ex = ExaClient()
        res = await ex.search(query, num_results=num, client=c, text_chars=400)
        if not res:
            res = await DDGClient().search(query, num_results=num, client=c)
        return [{"title": r.title, "url": r.url, "snippet": r.snippet, "source": r.source}
                for r in res]


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else ""
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    if not q:
        print("[]")
        sys.exit(0)
    print(json.dumps(asyncio.run(run(q, n)), ensure_ascii=False, indent=0))
