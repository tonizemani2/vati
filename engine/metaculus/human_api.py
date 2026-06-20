"""Human-account Metaculus client — submit forecasts under YOUR logged-in account via browser cookies,
not the bot's API token. You paste your cookies (Application → Cookies on metaculus.com) into
`data/metaculus/.human_session.json` (gitignored); this reads the JWT access token and posts forecasts
as you. The Django API accepts the access token as a Bearer header — no Cloudflare clearance needed
from this machine (verified 2026-06-14, account 303699 / 'vati').

The access token is short-lived (~15 min) and the public API exposes no refresh route, so the model is:
drop fresh cookies, submit immediately. `me()` verifies the session is still live before any write.
Reads (get_post etc.) still go through the bot client in api.py (public data, longer-lived token).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

BASE = "https://www.metaculus.com/api"
SESSION = os.path.join(os.path.dirname(__file__), "..", "..", "data", "metaculus", ".human_session.json")


class SessionError(RuntimeError):
    pass


def _session() -> dict:
    if not os.path.exists(SESSION):
        raise SessionError(f"no session at {SESSION} — paste your metaculus cookies first")
    return json.load(open(SESSION))


def _headers() -> dict:
    s = _session()
    tok = s.get("access_token")
    if not tok:
        raise SessionError("session has no access_token")
    return {
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
        "User-Agent": s.get("user_agent", "Mozilla/5.0"),
    }


def _req(method: str, path: str, body=None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        if e.code in (401, 403):
            raise SessionError(
                f"auth failed (HTTP {e.code}) — your access token likely expired; re-grab the "
                f"metaculus_access_token cookie. detail: {detail}"
            ) from e
        raise SessionError(f"{method} {path} → HTTP {e.code}: {detail}") from e


def me() -> dict:
    """Verify the session is live; returns the logged-in user (id, username). Raises if expired."""
    return _req("GET", "/users/me/")


# ---- writes (same /questions/forecast/ body shape as the bot client, but as YOU) ----

def submit_binary(question_id: int, probability_yes: float) -> dict:
    p = max(0.01, min(0.99, float(probability_yes)))
    return _req("POST", "/questions/forecast/", [{
        "question": question_id, "source": "api", "probability_yes": p,
        "probability_yes_per_category": None, "continuous_cdf": None,
    }])


def submit_multiple_choice(question_id: int, prob_per_option) -> dict:
    return _req("POST", "/questions/forecast/", [{
        "question": question_id, "source": "api", "probability_yes": None,
        "probability_yes_per_category": prob_per_option, "continuous_cdf": None,
    }])


def submit_cdf(question_id: int, cdf: list) -> dict:
    return _req("POST", "/questions/forecast/", [{
        "question": question_id, "source": "api", "probability_yes": None,
        "probability_yes_per_category": None, "continuous_cdf": cdf,
    }])
