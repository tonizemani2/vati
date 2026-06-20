"""inbox — OWNER-ONLY, READ-ONLY reply reader over Stalwart JMAP.

Hard boundaries (do not relax):
  - These are TONI'S private mailboxes. This module is NEVER registered as a chat/agent tool
    (it is not in vati-data-agent TOOL_SPECS / server.py). Only the owner runs it, via the CLI.
  - READ-ONLY. There is no send path here. No EmailSubmission, ever. The system drafts the next
    move; the human sends it manually from their own client.

Config (env, in this repo's .env): VATI_JMAP_SESSION (the JMAP session URL),
VATI_JMAP_TOKEN (bearer) or VATI_JMAP_USER + VATI_JMAP_PASS (basic auth).

Flow: resolve session -> Mailbox/query (inbox) -> Email/query (recent) -> Email/get. Then
process_replies() matches each reply to a drafted play and runs classify_reply to queue the next
move (draft only) into data/capture/<slug>/replies.json.
"""
from __future__ import annotations

import base64
import json
import os
import sqlite3
import urllib.request
from pathlib import Path

from engine import cost

REPO_ROOT = Path(__file__).resolve().parents[2]


class InboxConfigError(RuntimeError):
    """JMAP is not configured in .env."""


def _auth_header() -> str:
    cost.load_repo_env()
    tok = os.getenv("VATI_JMAP_TOKEN")
    if tok:
        return f"Bearer {tok}"
    user, pw = os.getenv("VATI_JMAP_USER"), os.getenv("VATI_JMAP_PASS")
    if user and pw:
        return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()
    raise InboxConfigError(
        "set VATI_JMAP_TOKEN, or VATI_JMAP_USER + VATI_JMAP_PASS, in .env to read the inbox")


def _post(url: str, body: dict | None, auth: str) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method="POST" if data else "GET",
        headers={"Authorization": auth, "Content-Type": "application/json",
                 "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _session() -> tuple[str, str, str]:
    """Return (api_url, account_id, auth_header) from the JMAP session resource."""
    cost.load_repo_env()
    sess_url = os.getenv("VATI_JMAP_SESSION")
    if not sess_url:
        raise InboxConfigError("set VATI_JMAP_SESSION (the JMAP session URL) in .env")
    auth = _auth_header()
    sess = _post(sess_url, None, auth)
    account_id = sess["primaryAccounts"]["urn:ietf:params:jmap:mail"]
    return sess["apiUrl"], account_id, auth


_MAIL = "urn:ietf:params:jmap:mail"
_CORE = "urn:ietf:params:jmap:core"


def fetch_recent(limit: int = 30) -> list[dict]:
    """Read the most recent Inbox messages (READ-ONLY). Returns compact dicts."""
    api_url, acct, auth = _session()
    calls = [
        ["Mailbox/query", {"accountId": acct, "filter": {"role": "inbox"}}, "m"],
        ["Email/query", {
            "accountId": acct,
            "filter": {"inMailbox": {"resultOf": "m", "name": "Mailbox/query", "path": "/ids/0"}},
            "sort": [{"property": "receivedAt", "isAscending": False}],
            "limit": limit}, "q"],
        ["Email/get", {
            "accountId": acct,
            "#ids": {"resultOf": "q", "name": "Email/query", "path": "/ids"},
            "properties": ["id", "threadId", "subject", "from", "receivedAt", "preview"]}, "g"],
    ]
    resp = _post(api_url, {"using": [_CORE, _MAIL], "methodCalls": calls}, auth)
    out = []
    for name, res, _cid in resp.get("methodResponses", []):
        if name == "Email/get":
            for e in res.get("list", []):
                frm = (e.get("from") or [{}])[0]
                out.append({
                    "id": e.get("id"), "thread": e.get("threadId"),
                    "from_name": frm.get("name", ""), "from_email": frm.get("email", ""),
                    "subject": e.get("subject", ""), "received": e.get("receivedAt", ""),
                    "preview": e.get("preview", ""),
                })
    return out


def process_replies(slug: str, conn: sqlite3.Connection | None = None, limit: int = 30) -> dict:
    """Match recent inbox replies to drafted plays and queue the next move (DRAFT ONLY).

    Writes data/capture/<slug>/replies.json. Sends nothing; the owner reviews + sends by hand.
    """
    from engine.capture import engine as ce
    from engine.capture.schema import Play, play_dir, read_json, write_json

    d = play_dir(slug, REPO_ROOT)
    plays = [Play.from_dict(p) for p in read_json(d / "plays.json")]
    by_email = {p.target.reachability.lower(): p for p in plays if "@" in (p.target.reachability or "")}
    by_name = {p.target.name.lower(): p for p in plays}

    msgs = fetch_recent(limit)
    own = conn is None
    if own:
        from engine import db
        conn = db.connect()
    suggestions = []
    try:
        for m in msgs:
            play = by_email.get(m["from_email"].lower()) or by_name.get(m["from_name"].lower())
            if not play:
                continue  # not a reply to one of our plays
            verdict = ce.classify_reply(conn, play, m["preview"] or m["subject"])
            suggestions.append({
                "from": f'{m["from_name"]} <{m["from_email"]}>', "subject": m["subject"],
                "received": m["received"], "target": play.target.name,
                "matched_branch": verdict.get("branch_idx"),
                "confidence": verdict.get("confidence"),
                "suggested_move_DRAFT": verdict.get("recommended_move"),
            })
    finally:
        if own:
            conn.close()
    write_json(d / "replies.json", suggestions)
    return {"scanned": len(msgs), "matched": len(suggestions), "file": str(d / "replies.json")}
