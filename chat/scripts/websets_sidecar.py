#!/usr/bin/env python3
"""Small HTTP sidecar for the Exa Websets people tool.

The chat app deploys as a Cloudflare Worker, which cannot use Python/curl_cffi and
currently gets blocked by Exa's createWebset endpoint from Node-style fetch. This
sidecar keeps the proven curl_cffi client in one small private service and exposes
a simple JSON contract to the Worker. It uses only the Python standard library so
it can run inside the existing orca97-v2 .venv-fe environment.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ORCA_ROOT = Path(os.environ.get("ORCA_ROOT", "/Users/emizemani/orca97-v2"))
SCRIPTS_DIR = ORCA_ROOT / "people_intel" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import exa_websets as exa  # noqa: E402

TOKEN = os.environ.get("WEBSETS_TOOL_TOKEN", "")


class Handler(BaseHTTPRequestHandler):
    server_version = "VaticinusWebsetsTool/1.0"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            self._authorize()
            if path == "/health":
                self._json(200, {"ok": True})
            elif path == "/credits":
                self._json(200, {"ok": True, **credits_payload()})
            else:
                self._json(404, {"ok": False, "error": "not found"})
        except HttpError as e:
            self._json(e.status, {"ok": False, "detail": e.message})
        except Exception as e:
            self._json(500, {"ok": False, "detail": str(e)})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            self._authorize()
            body = self._body()
            if path == "/search":
                self._json(200, {"ok": True, **search_payload(body)})
            elif path == "/status":
                self._json(200, {"ok": True, **status_payload(body)})
            else:
                self._json(404, {"ok": False, "error": "not found"})
        except HttpError as e:
            self._json(e.status, {"ok": False, "detail": e.message})
        except Exception as e:
            self._json(500, {"ok": False, "detail": str(e)})

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.log_date_time_string(), fmt % args))

    def _authorize(self) -> None:
        if TOKEN and self.headers.get("authorization") != f"Bearer {TOKEN}":
            raise HttpError(401, "unauthorized")

    def _body(self) -> dict[str, Any]:
        size = int(self.headers.get("content-length") or 0)
        if size <= 0:
            return {}
        data = self.rfile.read(size)
        try:
            parsed = json.loads(data.decode("utf-8"))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            raise HttpError(400, "bad json")

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class HttpError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(message)


def client(proxy: str):
    pool = exa.Pool(proxy)
    c = pool.client()
    if not c:
        raise HttpError(503, "no usable Websets account")
    return c


def credits_payload() -> dict[str, Any]:
    c = client("none")
    return {
        "account_email": c.account.get("email", ""),
        "credits": c.credits(),
    }


def search_payload(req: dict[str, Any]) -> dict[str, Any]:
    query = str(req.get("query") or "").strip()
    if not query:
        raise HttpError(400, "empty query")

    entity = "company" if req.get("entity") == "company" else "person"
    count = max(1, min(25, int(req.get("count") or 5)))
    wait_seconds = max(0, min(420, int(int(req.get("wait_ms") or 0) / 1000)))
    proxy = str(req.get("proxy") or "none")

    c = client(proxy)
    enrichments = exa.ENRICHMENTS_PERSON_FULL[:3] if entity == "person" else exa.ENRICHMENTS_COMPANY[:3]
    webset_id = c.create_webset(query, count=count, entity=entity, enrichments=enrichments)
    if not webset_id:
        raise HttpError(502, "createWebset failed")

    completed = c.wait_for(webset_id, timeout=wait_seconds) if wait_seconds else False
    items = c.get_items(webset_id)
    contacts = [_contact(row) for row in exa._parse_items(items, query, webset_id)]
    return {
        "webset_id": webset_id,
        "status": "idle" if completed else "running",
        "completed": completed,
        "contacts": contacts,
        "account_email": c.account.get("email", ""),
        "credits": c.credits(),
        "item_count": len(contacts),
    }


def status_payload(req: dict[str, Any]) -> dict[str, Any]:
    webset_id = str(req.get("webset_id") or "")
    if not webset_id:
        raise HttpError(400, "missing webset_id")

    c = client(str(req.get("proxy") or "none"))
    state = c.get_webset(webset_id) or {}
    completed = state.get("status") == "idle"
    items = c.get_items(webset_id)
    contacts = [_contact(row) for row in exa._parse_items(items, "", webset_id)]
    return {
        "webset_id": webset_id,
        "status": state.get("status", "unknown"),
        "completed": completed,
        "contacts": contacts,
        "item_count": len(contacts),
    }


def _contact(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "full_name": row.get("full_name", ""),
        "first_name": row.get("first_name", ""),
        "last_name": row.get("last_name", ""),
        "title": row.get("title", ""),
        "company": row.get("company", ""),
        "location": row.get("location", ""),
        "linkedin": row.get("linkedin", ""),
        "email": row.get("email", ""),
        "phone": row.get("phone", ""),
    }


def main() -> None:
    host = os.environ.get("WEBSETS_TOOL_HOST", "127.0.0.1")
    port = int(os.environ.get("WEBSETS_TOOL_PORT", "8765"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"websets sidecar listening on http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
