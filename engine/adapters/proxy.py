"""Proxy adapter (A2) — fetch through a residential/ISP/DC proxy when a trusted source rate-limits.

The blessed escalation ladder is: direct + polite pacing → backoff/retry → proxy (the last rung,
for *trusted* sources only — a proxy raises REACH, never trust). Wired here so the patents collector
(IP-rate-limited at $0) and bulk self-collection can get through.

Two rails hold (unchanged):
  • Cost gate (rule 3): residential-proxy bandwidth is metered = real spend, so every fetch passes
    `cost.gate(est_cost_cents=...)` BEFORE the request. ≤ the auto-approve cap runs; above it blocks.
  • Vendored isolation (rule 6): proxy credentials are read from THIS repo's `.env` only (via
    `cost.load_repo_env`, the hard-wired REPO_ROOT/.env loader) — never another repo's secrets.

No creds configured → `ProxyConfigError` (clean, no network), exactly like the LLM adapter's no-key
path. Fetched bytes are stored in the content-addressed raw store (provenance + free re-extraction).
"""

from __future__ import annotations

import os
import sqlite3
import urllib.parse

import httpx

from engine import cost, rawstore

# Supported providers (creds via .env: <PREFIX>_USER/_PASS/_HOST/_PORT). Evomi = resi/mobile default.
PROVIDERS = ("evomi", "decodo", "floxy")


class ProxyConfigError(RuntimeError):
    """No proxy credentials in this repo's .env for the requested provider (rule 6)."""


def _session_tag() -> str:
    """A short random session id (stdlib `random`, no secret). New id ⇒ new sticky IP = rotation."""
    import random
    return "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(10))


def proxy_url(provider: str = "floxy", *, session: str | None = None, ttl_min: int = 20) -> str:
    """Build the proxy URL from THIS repo's .env. Raises ProxyConfigError if unset.

    Floxy requires a SESSION-tagged username (`<user>-session-<id>-ttl-<min>`); the bare username is
    refused. A fresh `session` each call ⇒ a fresh IP (rotation, best for dodging per-IP rate limits);
    pass a fixed `session` to pin one sticky IP (up to 96h). Other providers use the bare username.
    """
    cost.load_repo_env()
    p = provider.upper()
    user, pw = os.getenv(f"{p}_USER"), os.getenv(f"{p}_PASS")
    host, port = os.getenv(f"{p}_HOST"), os.getenv(f"{p}_PORT")
    if not all([user, pw, host, port]):
        raise ProxyConfigError(
            f"no {provider} proxy creds in {cost.ENV_PATH} "
            f"(need {p}_USER/{p}_PASS/{p}_HOST/{p}_PORT)"
        )
    # Session goes in different fields per provider: Floxy → username (`-session-<id>-ttl-<min>`,
    # and the bare username is REFUSED so we always tag it); Evomi → password (`<pw>_session-<id>`,
    # bare creds = rotating, a session = sticky). Decodo → username variants (handled as bare here).
    if provider == "floxy":
        user = f"{user}-session-{session or _session_tag()}-ttl-{ttl_min}"
    elif provider == "evomi" and session:
        pw = f"{pw}_session-{session}"
    # percent-encode userinfo — a password with @ : / etc. otherwise corrupts the proxy URL → 407
    u = urllib.parse.quote(user, safe="")
    w = urllib.parse.quote(pw, safe="")
    return f"http://{u}:{w}@{host}:{port}"


def available(provider: str = "floxy") -> bool:
    """True iff this provider's creds are configured (used to decide the escalation ladder)."""
    try:
        proxy_url(provider)
        return True
    except ProxyConfigError:
        return False


def fetch(
    conn: sqlite3.Connection,
    url: str,
    *,
    est_cost_cents: int,
    provider: str = "floxy",
    headers: dict | None = None,
    timeout: int = 40,
    store: bool = True,
    source_id: str | None = None,
    funded_ref: str | None = None,
) -> tuple[bytes, str | None]:
    """Fetch `url` through the proxy. Cost-gated BEFORE the request; stored in the raw doc store.

    Returns (content_bytes, media_type). Raises ProxyConfigError if unconfigured, CostGateError if
    the estimate exceeds the auto-approve cap (blocked, on record), or httpx errors on a bad response.
    """
    purl = proxy_url(provider)  # raises before any spend/gate if unconfigured
    cost.gate(conn, action="proxy_fetch", provider=provider, units=1,
              est_cost_cents=est_cost_cents, funded_ref=funded_ref)
    with httpx.Client(proxy=purl, timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url, headers=headers or {})
        resp.raise_for_status()
        content, media = resp.content, resp.headers.get("content-type")
    if store:
        rawstore.put(conn, content, source_id=source_id, url=url, media_type=media)
    return content, media
