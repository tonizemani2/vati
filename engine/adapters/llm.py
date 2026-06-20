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
    # DeepSeek — keyed, OpenAI-compatible, cheap + capable. Use the V4 model ids; the legacy
    # `deepseek-chat` / `deepseek-reasoner` aliases retire on 2026-07-24.
    "deepseek": Provider(
        "deepseek", "DEEPSEEK_API_KEY",
        "https://api.deepseek.com/chat/completions",
        "deepseek-v4-flash",
    ),
}


# OpenRouter `:free` roster — the keyless-equivalent recovery after DeepInfra patched web-embed.
# Live-probed 2026-06-12: strong frees that answered; each is independently rate-limited (429), so
# the caller shuffles leaders and fails over. Tiny/safety models excluded (forecast quality).
OPENROUTER_FREE_LEADERS = (
    "openai/gpt-oss-120b:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-31b-it:free",
)
OPENROUTER_FREE_FALLBACK = (
    "openai/gpt-oss-20b:free",
    "nex-agi/nex-n2-pro:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
)

# Bedrock (our own AWS account) — top-tier reasoning for the reputation-grade council. Newer 4.x
# models reject on-demand IDs → must use the `us.` cross-region inference profile. Verified callable
# 2026-06-16: us.anthropic.claude-opus-4-8 → "OK". Default = the same Opus the in-session model runs.
BEDROCK_DEFAULT_MODEL = "us.anthropic.claude-opus-4-8"
BEDROCK_COUNCIL = (  # decorrelated analysts on Sonnet 4.6, final synthesis/calibration on Opus 4.8
    "us.anthropic.claude-sonnet-4-6",
    "us.anthropic.claude-opus-4-8",
)


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
    reasoning_effort: str | None = None,
    extra_body: dict | None = None,
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
        # per-IP/per-model 429s hit individual models; spread bulk load across the live roster.
        # Live-verified (2026-06-10 probe via proxy): the 397B flagship, GLM-5.1, gemma-4-26B all
        # answer reliably; gemma-31B/DeepSeek-V4 often 429 (kept last). For an explicit `model` we
        # honour it; otherwise we SHUFFLE the 3 reliable leaders each call so no single model gets
        # all the load (fewer 429s) and the SFT traces gain model diversity, then fall back to the
        # flakier two only if all three are rate-limited.
        if model:
            roster = [model]
        else:
            import random as _r
            # Verified keyless-OK against the live DeepInfra catalog (2026-06-11 wide probe): a diverse
            # frontier slate across model FAMILIES — spreading load keeps trace QUALITY and multiplies
            # the per-model rate ceiling (each model 429s independently). Shuffled per call so no single
            # model is the hot path; the tail are live-but-throttled fallbacks. NB: route keyless via a
            # RESIDENTIAL proxy (evomi) or direct — DeepInfra 403-blocks datacenter IPs (floxy).
            leaders = ["deepseek-ai/DeepSeek-V4-Pro", "moonshotai/Kimi-K2.6",
                       "Qwen/Qwen3.5-397B-A17B", "Qwen/Qwen3.6-35B-A3B", "Qwen/Qwen3.5-122B-A10B",
                       "zai-org/GLM-5.1", "MiniMaxAI/MiniMax-M2.5", "moonshotai/Kimi-K2-Thinking"]
            _r.shuffle(leaders)
            roster = leaders + ["XiaomiMiMo/MiMo-V2.5-Pro", "XiaomiMiMo/MiMo-V2.5",
                                "nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B",
                                "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B",
                                "deepseek-ai/DeepSeek-V3.2", "moonshotai/Kimi-K2.5", "zai-org/GLM-5"]
        last: Exception | None = None
        for m in roster:
            try:
                return dik.chat(messages, model=m, max_tokens=max_tokens, proxy=proxy)
            except dik.KeylessError as e:
                last = e
        raise RuntimeError(f"keyless DeepInfra exhausted roster (last: {last}); pass proxy= to scale")

    if provider == "openrouter_free":
        # Keyless-EQUIVALENT recovery path (2026-06-12): DeepInfra patched the `web-embed` auth
        # bypass at the app layer ({"Not authenticated"}, server=uvicorn) — that keyless route is
        # permanently dead. OpenRouter's `:free` models cost $0 with the (free-to-make) key we already
        # hold, so the cost gate still auto-passes. Each free model is independently rate-limited, so
        # we shuffle a roster of live-verified frees and fail over on 429 — same pattern as the old
        # keyless path. Live-probed 2026-06-12.
        import random as _r
        cost.load_repo_env()
        key = os.getenv("OPENROUTER_API_KEY")
        if not key:
            raise LLMConfigError("no OPENROUTER_API_KEY in .env — required for openrouter_free")
        cost.gate(conn, action="openrouter_free_completion", provider="openrouter_free",
                  units=1, est_cost_cents=0, funded_ref=funded_ref)  # $0 → 'auto'
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        if model:
            roster = [model if model.endswith(":free") else model + ":free"]
        else:
            leaders = list(OPENROUTER_FREE_LEADERS)
            _r.shuffle(leaders)
            roster = leaders + list(OPENROUTER_FREE_FALLBACK)
        last: Exception | None = None
        for m in roster:
            payload = json.dumps({"model": m, "messages": messages, "max_tokens": max_tokens}).encode()
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions", data=payload, method="POST",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                         "HTTP-Referer": "https://github.com/vaticinus", "X-Title": "vaticinus"})
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode())
                msg = data["choices"][0]["message"]
                out = msg.get("content") or msg.get("reasoning") or ""
                if out.strip():
                    return out
                last = RuntimeError(f"empty content from {m}")
            except urllib.error.HTTPError as e:
                last = RuntimeError(f"{m} HTTP {e.code}: {e.read().decode()[:120]}")
            except Exception as e:  # noqa: BLE001
                last = e
        raise RuntimeError(f"openrouter_free exhausted roster (last: {last})")

    if provider == "bedrock":
        # Top-tier reasoning on OUR OWN AWS account: Claude Opus 4.8 (and the rest of the 4.x
        # slate) via Bedrock inference profiles. Shells out to the `aws` CLI (already installed +
        # SigV4-authed) so we add NO boto3 dep. On-demand IDs are rejected → use the `us.` profile
        # prefix (e.g. us.anthropic.claude-opus-4-8). Reputation-grade council leg; cost is logged.
        import subprocess, tempfile, math
        mid = model or BEDROCK_DEFAULT_MODEL
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
        # honest spend estimate BEFORE the call: Opus ~ $15/Mtok in, $75/Mtok out (cents).
        in_tok = (len(prompt) + len(system or "")) / 4.0
        rate_in, rate_out = (0.3, 1.5) if "sonnet" in mid or "haiku" in mid else (1.5, 7.5)  # cents/Ktok
        est = max(est_cost_cents, math.ceil((in_tok / 1000 * rate_in + max_tokens / 1000 * rate_out)))
        cost.gate(conn, action="bedrock_completion", provider="bedrock",
                  units=1, est_cost_cents=est, funded_ref=funded_ref)
        req = {"modelId": mid,
               "messages": [{"role": "user", "content": [{"text": prompt}]}],
               "inferenceConfig": {"maxTokens": max_tokens}}
        if system:
            req["system"] = [{"text": system}]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(req, f); reqpath = f.name
        try:
            out = subprocess.run(
                ["aws", "bedrock-runtime", "converse", "--region", region,
                 "--cli-input-json", f"file://{reqpath}", "--output", "json"],
                capture_output=True, text=True, timeout=240)
        finally:
            try: os.unlink(reqpath)
            except OSError: pass
        if out.returncode != 0:
            raise RuntimeError(f"bedrock {mid} failed: {out.stderr.strip()[:300]}")
        data = json.loads(out.stdout)
        txt = data["output"]["message"]["content"][0]["text"]
        if not txt.strip():
            raise RuntimeError(f"bedrock {mid} returned empty content")
        return txt

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
    body = {
        "model": model or p.default_model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if reasoning_effort:
        body["reasoning_effort"] = reasoning_effort
    if extra_body:
        body.update(extra_body)
    payload = json.dumps(body).encode()

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
    msg = data["choices"][0].get("message", {})
    text = msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning") or ""
    if not str(text).strip():
        raise RuntimeError(f"{provider} {model or p.default_model} returned empty content")
    return str(text)
