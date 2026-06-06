"""Component A4 — the content-addressed raw-document store.

Every byte we fetch (a 10-K, an HTML page, a PDF, a JSON payload) is written to disk keyed by its
own sha256: `data/raw/<sha[:2]>/<sha>.<ext>`. The hash IS the key, so storage is automatically
deduped and tamper-evident, and a Source's `content_hash` (already on the schema) points at the
exact bytes it was derived from. Two payoffs:
  • Provenance — every number traces to the precise document it came from (extreme QC).
  • Free re-extraction — re-parsing a stored doc with a better extractor reads local bytes ($0, no
    re-fetch, point-in-time exact); improving data quality over time doesn't re-incur fetch cost.

The bytes are git-ignored (a cache of external content); the durable record is the hash row in
`raw_docs`. Pure filesystem + one index table — no network, no new dependency.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from engine import db as _db
from engine.schemas import _now

RAW_ROOT = _db.REPO_ROOT / "data" / "raw"

_EXT = {
    "text/html": "html", "application/pdf": "pdf", "application/json": "json",
    "text/plain": "txt", "text/csv": "csv", "application/xml": "xml", "text/xml": "xml",
}


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _path_for(h: str, media_type: str | None) -> Path:
    ext = _EXT.get((media_type or "").split(";")[0].strip(), "bin")
    return RAW_ROOT / h[:2] / f"{h}.{ext}"


def exists(h: str) -> bool:
    for p in (RAW_ROOT / h[:2]).glob(f"{h}.*"):
        return p.is_file()
    return False


def put(conn: sqlite3.Connection, content: bytes, *, source_id: str | None = None,
        url: str | None = None, media_type: str | None = None) -> str:
    """Store bytes (write-if-absent), index them in raw_docs, return the content hash.

    Idempotent: the same bytes never rewrite the file; the index row is upserted (so a later fetch
    can attach the source_id/url to an already-cached doc)."""
    h = content_hash(content)
    path = _path_for(h, media_type)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    rel = str(path.relative_to(_db.REPO_ROOT))
    conn.execute(
        "INSERT INTO raw_docs (content_hash, source_id, url, media_type, byte_len, path, fetched_at) "
        "VALUES (?,?,?,?,?,?,?) "
        "ON CONFLICT(content_hash) DO UPDATE SET "
        "source_id=COALESCE(excluded.source_id, raw_docs.source_id), "
        "url=COALESCE(excluded.url, raw_docs.url), "
        "media_type=COALESCE(excluded.media_type, raw_docs.media_type)",
        (h, source_id, url, media_type, len(content), rel, _now().isoformat()),
    )
    conn.commit()
    return h


def get(h: str) -> bytes | None:
    """Return the stored bytes for a hash, or None if not present locally."""
    for p in (RAW_ROOT / h[:2]).glob(f"{h}.*"):
        if p.is_file():
            return p.read_bytes()
    return None


def path_of(conn: sqlite3.Connection, h: str) -> Path | None:
    row = conn.execute("SELECT path FROM raw_docs WHERE content_hash=?", (h,)).fetchone()
    if not row:
        return None
    return _db.REPO_ROOT / row["path"]
