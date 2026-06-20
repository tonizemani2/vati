"""Thin Metaculus REST client — list open tournament questions, read the community prediction,
submit a binary forecast. No SDK, no ORM (CLAUDE.md minimalism): just the four calls the bot needs.

Auth: a bot account's API token, read from THIS repo's .env (rule 6 — never another repo's secret):
    METACULUS_TOKEN=...
Get one at metaculus.com → Settings → "Create Token" after the account joins the tournament.

API shape (verified against the official metac-bot-template, 2026-06):
  base   = https://www.metaculus.com/api
  auth   = Authorization: Token <token>
  list   = GET  /posts/?tournaments=<slug|id>&statuses=open&forecast_type=binary&...
  detail = GET  /posts/<id>/
  submit = POST /questions/forecast/   body=[{question, source:"api", probability_yes, ...}]
  comment= POST /comments/             body={on_post, text, is_private}   (optional rationale)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from engine import cost

BASE = "https://www.metaculus.com/api"


class MetaculusError(RuntimeError):
    pass


def _token() -> str:
    cost.load_repo_env()
    tok = os.getenv("METACULUS_TOKEN")
    if not tok:
        raise MetaculusError(
            f"no METACULUS_TOKEN in {cost.ENV_PATH} — create a bot account, join the tournament, "
            "then Settings → Create Token and add METACULUS_TOKEN=... to .env"
        )
    return tok


def _req(method: str, path: str, *, params: dict | None = None, body=None) -> dict:
    url = BASE + path
    if params:
        # repeat list-valued params (tournaments) rather than comma-join — the API expects repeats
        flat = []
        for k, v in params.items():
            if isinstance(v, (list, tuple)):
                flat.extend((k, str(x)) for x in v)
            else:
                flat.append((k, str(v)))
        url += "?" + urllib.parse.urlencode(flat)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Token {_token()}",
        "Content-Type": "application/json",
        "User-Agent": "vati-forecaster/0.1",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        raise MetaculusError(f"{method} {path} → HTTP {e.code}: {detail}") from e


# ---------------------------------------------------------------------------- list / read

def list_open_questions(tournament: str, *, limit: int = 100,
                        forecast_type: str = "binary") -> list[dict]:
    """All currently-open posts in a tournament (paginated). `tournament` is the slug or numeric id.
    Defaults to binary (the v1 scope + the press-scalp core); pass e.g.
    'binary,multiple_choice,numeric' to widen once those output paths exist."""
    out: list[dict] = []
    offset = 0
    while True:
        page = _req("GET", "/posts/", params={
            "limit": limit, "offset": offset, "order_by": "-hotness",
            "forecast_type": forecast_type, "tournaments": [tournament],
            "statuses": "open", "include_description": "true",
        })
        results = page.get("results", [])
        out.extend(results)
        if len(results) < limit or not page.get("next"):
            break
        offset += limit
    return out


def get_post(post_id: int) -> dict:
    """Full post detail (resolution criteria, fine print, current aggregation/community prediction)."""
    return _req("GET", f"/posts/{post_id}/")


# ---------------------------------------------------------------------------- field extraction

def binary_question(post: dict) -> dict | None:
    """Pull the single binary question dict out of a post, or None if the post isn't binary.
    A post may carry one `question` (simple) — group/conditional posts are skipped in v1."""
    q = post.get("question")
    if q and q.get("type") == "binary":
        return q
    return None


def community_prob(post_or_q: dict) -> float | None:
    """The current community prediction for a binary question (the crowd anchor, 0..1), if visible.

    AIB bot tournaments often HIDE the community prediction until resolution → returns None and the
    pipeline runs anchor-free. The Metaculus Cup exposes it (human crowd) → the +17–28% lever.
    Reads the recency-weighted aggregation center, tolerating both post- and question-level shapes."""
    q = post_or_q.get("question", post_or_q)
    aggs = (q or {}).get("aggregations") or {}
    for key in ("recency_weighted", "metaculus_prediction", "unweighted"):
        latest = ((aggs.get(key) or {}).get("latest")) or {}
        centers = latest.get("centers") or latest.get("forecast_values")
        if centers:
            try:
                return float(centers[-1])
            except (TypeError, ValueError):
                pass
    return None


def question_text(post: dict) -> dict:
    """Normalize the fields the forecaster needs into one dict."""
    q = post.get("question") or {}
    return {
        "post_id": post.get("id"),
        "question_id": q.get("id"),
        "title": post.get("title") or q.get("title") or "",
        "description": q.get("description") or post.get("description") or "",
        "resolution_criteria": q.get("resolution_criteria") or "",
        "fine_print": q.get("fine_print") or "",
        "close_time": q.get("scheduled_close_time") or post.get("scheduled_close_time"),
        "url": f"https://www.metaculus.com/questions/{post.get('id')}/",
    }


# ---------------------------------------------------------------------------- write

def submit_binary(question_id: int, probability_yes: float) -> dict:
    """POST one binary forecast. Clamps to [0.01, 0.99] (Metaculus rejects 0/1 and we never want them)."""
    p = max(0.01, min(0.99, float(probability_yes)))
    return _req("POST", "/questions/forecast/", body=[{
        "question": question_id,
        "source": "api",
        "probability_yes": p,
        "probability_yes_per_category": None,
        "continuous_cdf": None,
    }])


def post_comment(post_id: int, text: str, *, private: bool = True) -> dict:
    """Attach the reasoning as a comment (Metaculus encourages bots to show their work).
    Default private so we don't leak rationale to human competitors mid-season."""
    return _req("POST", "/comments/", body={
        "on_post": post_id, "text": text[:20000], "is_private": private,
        "included_forecast": True,
    })
