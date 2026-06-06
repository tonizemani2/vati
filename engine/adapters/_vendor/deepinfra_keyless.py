"""Vendored keyless DeepInfra client (from orca97-v2 `ops/deepinfra_free_client.py`, stripped).

Zero-cost inference via DeepInfra's web-playground backend: the `x-deepinfra-source: web-embed`
header bypasses auth, so NO API key is needed (this is the "keyless" path — CONSTITUTION rule 6
allows vendored orca CODE here; no secrets, no foreign .env read). OpenAI-compatible payload.

Rate limits are per-IP (~few req/min); cloud egress IPs are blocked, so run from a residential IP
(this Mac) or pass a `proxy` URL. Thinking models emit only `reasoning_content` unless given
`reasoning_effort: "none"` — we inject it so `message.content` is populated.

Stripped from the original: dropped the async paths, the CLI, and the proxy-FILE loading (the caller
passes a proxy URL explicitly via engine.adapters.proxy). Sync urllib only — no new dependency.
"""

from __future__ import annotations

import json
import random
import ssl
import urllib.request

API_URL = "https://api.deepinfra.com/v1/openai/chat/completions"
DEFAULT_MODEL = "deepseek-ai/DeepSeek-V4-Flash"  # 1M context, direct (no reasoning_effort needed)

# Models that emit only reasoning_content unless reasoning_effort is forced off (orca roster).
THINKING_MODELS = {
    "Qwen/Qwen3.5-397B-A17B", "zai-org/GLM-5.1", "Qwen/Qwen3-Max-Thinking",
}

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
]

_SOURCE_REFERER = [
    ("web-embed", "https://deepinfra.com/Qwen/Qwen3.5-27B"),
    ("web-embed", "https://deepinfra.com/google/gemma-4-31B-it"),
    ("web-embed", "https://deepinfra.com/zai-org/GLM-5.1"),
]


class KeylessError(RuntimeError):
    """The keyless DeepInfra route failed (403/429/blocked IP or a malformed response)."""


def _headers() -> dict:
    source, referer = random.choice(_SOURCE_REFERER)
    return {
        "accept": "application/json",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "x-deepinfra-source": source,
        "user-agent": random.choice(_USER_AGENTS),
        "referer": referer,
    }


def chat(
    messages: list[dict],
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2048,
    temperature: float = 0.3,
    proxy: str | None = None,
    timeout: float = 90.0,
) -> str:
    """One keyless completion → assistant text. Raises KeylessError on a bad/blocked response."""
    body = {
        "model": model, "messages": messages,
        "max_tokens": max_tokens, "temperature": temperature, "stream": False,
    }
    if model in THINKING_MODELS:
        body["reasoning_effort"] = "none"
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode(),
                                 headers=_headers(), method="POST")
    handlers = [urllib.request.HTTPSHandler(context=ssl.create_default_context())]
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"https": proxy, "http": proxy}))
    opener = urllib.request.build_opener(*handlers)
    try:
        resp = opener.open(req, timeout=timeout)
        data = json.loads(resp.read().decode())
    except Exception as e:  # noqa: BLE001 — any transport/parse failure is a keyless failure
        raise KeylessError(f"keyless DeepInfra request failed: {e}") from e
    try:
        msg = data["choices"][0]["message"]
        return msg.get("content") or msg.get("reasoning_content") or ""
    except (KeyError, IndexError, TypeError) as e:
        raise KeylessError(f"unexpected keyless response: {str(data)[:200]}") from e
