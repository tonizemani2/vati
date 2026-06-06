"""LLM scale adapter — DeepInfra / MiniMax / OpenRouter, behind the cost gate.

SCALE ONLY. Default reasoning is Claude in-session (CLAUDE.md). These providers exist for
bulk work the in-session model shouldn't do by hand: mass extraction, OCR text cleanup,
high-volume classification. Every call is OpenAI-compatible chat-completions.

Two guardrails are structural, not optional:
  1. Keys are read from THIS repo's `.env` only (via engine.cost.load_repo_env → rule 6).
     No key for a provider ⇒ a clear LLMConfigError, never a silent foreign-secret read.
  2. Every call passes engine.cost.gate FIRST with an explicit `est_cost_cents`. A bulk run
     over COST_AUTO_APPROVE_CENTS is logged 'pending' and BLOCKED until a human approves —
     you cannot spend by accident.
"""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.request
from dataclasses import dataclass

from engine import cost


class LLMConfigError(RuntimeError):
    """No API key configured (in this repo's .env) for the requested provider."""


@dataclass(frozen=True)
class Provider:
    name: str
    env_key: str
    url: str
    default_model: str
    base_url_env: str | None = None  # for providers whose host is configurable (MiniMax)


PROVIDERS: dict[str, Provider] = {
    "deepinfra": Provider(
        "deepinfra", "DEEPINFRA_API_KEY",
        "https://api.deepinfra.com/v1/openai/chat/completions",
        "Qwen/Qwen2.5-72B-Instruct",
    ),
    "openrouter": Provider(
        "openrouter", "OPENROUTER_API_KEY",
        "https://openrouter.ai/api/v1/chat/completions",
        "qwen/qwen-2.5-72b-instruct",
    ),
    "minimax": Provider(
        "minimax", "MINIMAX_API_KEY",
        "",  # resolved from MINIMAX_BASE_URL at call time
        "MiniMax-M2.7",
        base_url_env="MINIMAX_BASE_URL",
    ),
}


def _resolve(provider: str) -> tuple[Provider, str, str]:
    """Return (provider, api_key, url) or raise LLMConfigError. Reads this repo's .env only."""
    cost.load_repo_env()
    p = PROVIDERS.get(provider)
    if p is None:
        raise LLMConfigError(f"unknown provider {provider!r}; have {list(PROVIDERS)}")
    key = os.getenv(p.env_key)
    if not key:
        raise LLMConfigError(
            f"no {p.env_key} in {cost.ENV_PATH.name} — set it to use {provider} "
            f"(default reasoning is Claude in-session; these providers are scale-only)"
        )
    url = p.url
    if p.base_url_env:
        base = (os.getenv(p.base_url_env) or "").rstrip("/")
        if not base:
            raise LLMConfigError(f"{provider} needs {p.base_url_env} set in {cost.ENV_PATH.name}")
        # base may or may not already include /v1 (orca's MiniMax base is .../v1) — don't double it
        url = base + ("/chat/completions" if base.endswith("/v1") else "/v1/chat/completions")
    return p, key, url


def complete(
    conn: sqlite3.Connection,
    prompt: str,
    *,
    provider: str = "deepinfra_keyless",
    est_cost_cents: int = 0,
    model: str | None = None,
    system: str | None = None,
    max_tokens: int = 1024,
    proxy: str | None = None,
    funded_ref: str | None = None,
) -> str:
    """One scale-LLM completion. Gate fires (with est_cost_cents) BEFORE any network call.

    Default provider is **deepinfra_keyless** — the $0 web-embed route (no key; per-IP rate-limited,
    pass a `proxy` to scale). Keyed providers (deepinfra/minimax/openrouter) require est_cost_cents
    and a key; a bulk run over the threshold raises CostGateError before any network call. Returns
    the assistant text.
    """
    if provider == "deepinfra_keyless":
        from engine.adapters._vendor import deepinfra_keyless as dik
        cost.gate(conn, action="deepinfra_keyless_completion", provider="deepinfra_keyless",
                  units=1, est_cost_cents=est_cost_cents, funded_ref=funded_ref)  # $0 → 'auto'
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        # per-IP 429s hit individual models; rotate the orca roster (flagship first) before failing.
        roster = [model] if model else [
            "Qwen/Qwen3.5-397B-A17B", "google/gemma-4-31B-it",
            "deepseek-ai/DeepSeek-V4-Flash", "zai-org/GLM-5.1", "google/gemma-4-26B-A4B-it",
        ]
        last: Exception | None = None
        for m in roster:
            try:
                return dik.chat(messages, model=m, max_tokens=max_tokens, proxy=proxy)
            except dik.KeylessError as e:
                last = e
        raise RuntimeError(f"keyless DeepInfra exhausted roster (last: {last}); pass proxy= to scale")

    p, key, url = _resolve(provider)  # raises before the gate if misconfigured
    ledger_id = cost.gate(
        conn,
        action=f"{provider}_completion",
        provider=provider,
        units=1,
        est_cost_cents=est_cost_cents,
        funded_ref=funded_ref,
    )

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = json.dumps({
        "model": model or p.default_model,
        "messages": messages,
        "max_tokens": max_tokens,
    }).encode()

    req = urllib.request.Request(
        url, data=payload, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{provider} HTTP {e.code}: {e.read().decode()[:300]}") from e

    cost.record_actual(conn, ledger_id, est_cost_cents)  # no per-call meter yet; est is the record
    return data["choices"][0]["message"]["content"]
