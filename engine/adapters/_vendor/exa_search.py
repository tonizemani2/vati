"""Exa.ai keyless search + DuckDuckGo HTML fallback.

VENDORED — orca-derived (CONSTITUTION rule 6). Do not edit beyond the strip below.
  Source : orca97-v2 @ e642a1dd  —  invest_intel/search.py
  Strip  : removed `from invest_intel.config import ...` (the only cross-repo coupling /
           path machinery) and inlined the three URL constants + the user-agent list it
           used. No `.env` access, no parent-directory walk, no path hacks — faithful to
           the original keyless token dance otherwise.

The asset here is the keyless protocol: POST exa.ai/api/token/issue → bearer token (5-min
TTL) → POST exa.ai/api/search. Free, no API key, from a home IP. Our sync typed wrapper +
cost-gate logging live in `engine/adapters/search.py`.
"""

import random
import re
import time
from dataclasses import dataclass
from urllib.parse import unquote, parse_qs, urlparse

import httpx

# --- inlined from orca invest_intel/config.py (the strip) ---------------------
EXA_TOKEN_URL = "https://exa.ai/api/token/issue"
EXA_SEARCH_URL = "https://exa.ai/api/search"
DDG_SEARCH_URL = "https://html.duckduckgo.com/html/"

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
]


def random_ua() -> str:
    return random.choice(USER_AGENTS)


# --- original orca logic (unchanged) -----------------------------------------
@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    source: str = ""  # "exa" or "ddg"


class ExaClient:
    """Exa.ai keyless search — free tokens with 5-min TTL."""

    def __init__(self):
        self._token: str | None = None
        self._token_expires: float = 0

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        if self._token and time.time() < self._token_expires:
            return self._token
        r = await client.post(EXA_TOKEN_URL, json={}, headers={
            "User-Agent": random_ua(),
            "Origin": "https://exa.ai",
            "Referer": "https://exa.ai/",
        })
        data = r.json()
        self._token = data["token"]
        self._token_expires = time.time() + data.get("expiresIn", 240)
        return self._token

    async def search(self, query: str, num_results: int = 10,
                     client: httpx.AsyncClient | None = None) -> list[SearchResult]:
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=15, follow_redirects=True)
        try:
            token = await self._get_token(client)
            r = await client.post(EXA_SEARCH_URL, json={
                "query": query,
                "num_results": num_results,
            }, headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": random_ua(),
                "Origin": "https://exa.ai",
                "Referer": "https://exa.ai/",
            })
            if r.status_code != 200:
                return []
            data = r.json()
            results = []
            for item in data.get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("text", "")[:300] if item.get("text") else "",
                    source="exa",
                ))
            return results
        except Exception:
            return []
        finally:
            if own_client:
                await client.aclose()


class DDGClient:
    """DuckDuckGo HTML search — no auth needed."""

    @staticmethod
    def _unwrap_ddg_url(raw: str) -> str:
        """Extract real URL from DDG redirect wrapper."""
        parsed = urlparse(raw)
        qs = parse_qs(parsed.query)
        if "uddg" in qs:
            return unquote(qs["uddg"][0])
        return raw

    async def search(self, query: str, num_results: int = 10,
                     client: httpx.AsyncClient | None = None) -> list[SearchResult]:
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=15, follow_redirects=True)
        try:
            r = await client.get(DDG_SEARCH_URL, params={"q": query}, headers={
                "User-Agent": random_ua(),
            })
            if r.status_code != 200:
                return []
            return self._parse_html(r.text, num_results)
        except Exception:
            return []
        finally:
            if own_client:
                await client.aclose()

    def _parse_html(self, html: str, limit: int) -> list[SearchResult]:
        results = []
        # Match result blocks
        blocks = re.findall(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)',
            html, re.DOTALL,
        )
        for href, title_html, snippet_html in blocks[:limit]:
            url = self._unwrap_ddg_url(href)
            title = re.sub(r"<[^>]+>", "", title_html).strip()
            snippet = re.sub(r"<[^>]+>", "", snippet_html).strip()
            if url and title:
                results.append(SearchResult(
                    title=title, url=url, snippet=snippet, source="ddg",
                ))
        return results
