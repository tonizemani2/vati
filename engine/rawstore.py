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
import subprocess
from pathlib import Path

from engine import data_offload, db as _db
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
    if source_id:
        checked_at = _now().isoformat()
        try:
            conn.execute(
                """
                UPDATE sources
                SET raw_provenance_status='exact_raw_doc',
                    raw_provenance_reason='exact bytes indexed in raw_docs',
                    raw_provenance_checked_at=?
                WHERE id=?
                """,
                (checked_at, source_id),
            )
        except sqlite3.OperationalError:
            # Older in-memory test DBs may not have been migrated before rawstore is exercised.
            pass
    conn.commit()
    return h


def get(h: str) -> bytes | None:
    """Return the stored bytes for a hash, or None if not present locally."""
    for p in (RAW_ROOT / h[:2]).glob(f"{h}.*"):
        if p.is_file():
            return p.read_bytes()
    return None


def _abs_repo_path(path_value: str | Path) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = _db.REPO_ROOT / path
    return path.resolve(strict=False)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _row_path(row: sqlite3.Row) -> Path | None:
    raw_path = row["path"] if "path" in row.keys() else None
    return _abs_repo_path(str(raw_path)) if raw_path else None


def _remote_uri_for_path(path: Path, manifest_path: Path | None = None) -> str | None:
    """Map a local raw path to its uploaded S3 URI using the local offload manifest."""

    manifest = manifest_path or (_db.REPO_ROOT / "data" / "_offload_manifest.jsonl")
    entries = data_offload.read_manifest(manifest)
    path = path.resolve(strict=False)
    for entry in reversed(entries):
        if not entry.uploaded:
            continue
        local = _abs_repo_path(entry.local_path)
        remote = entry.remote_uri.rstrip("/")
        if path == local:
            return remote
        if _is_relative_to(path, local):
            suffix = "/".join(path.relative_to(local).parts)
            return f"{remote}/{suffix}" if suffix else remote
    return None


def locate(conn: sqlite3.Connection, h: str, *, manifest_path: Path | None = None) -> dict[str, object]:
    """Describe where a raw document lives: local, remote/offloaded, or missing.

    This is intentionally read-only. It makes laptop offload visible without silently downloading
    bytes or re-fetching provider URLs.
    """

    row = conn.execute(
        """
        SELECT content_hash, source_id, url, media_type, byte_len, path, fetched_at
        FROM raw_docs
        WHERE content_hash=?
        """,
        (h,),
    ).fetchone()
    if not row:
        return {
            "content_hash": h,
            "indexed": False,
            "local_path": None,
            "exists_local": False,
            "remote_uri": None,
            "status": "missing_index",
        }

    local_path = _row_path(row)
    exists_local = bool(local_path and local_path.is_file())
    remote_uri = None if exists_local or local_path is None else _remote_uri_for_path(local_path, manifest_path)
    if exists_local:
        status = "local"
    elif remote_uri:
        status = "offloaded"
    else:
        status = "missing_unaccounted"
    return {
        "content_hash": h,
        "indexed": True,
        "source_id": row["source_id"],
        "url": row["url"],
        "media_type": row["media_type"],
        "byte_len": int(row["byte_len"] or 0),
        "fetched_at": row["fetched_at"],
        "path": row["path"],
        "local_path": str(local_path) if local_path else None,
        "exists_local": exists_local,
        "remote_uri": remote_uri,
        "status": status,
    }


def restore(
    conn: sqlite3.Connection,
    h: str,
    *,
    max_bytes: int = 100 * 1024 * 1024,
    manifest_path: Path | None = None,
) -> dict[str, object]:
    """Restore one offloaded raw document from S3 and verify its content hash.

    The guard is deliberately per-document: callers must opt into each hash instead of rehydrating
    a whole raw corpus onto the laptop.
    """

    info = locate(conn, h, manifest_path=manifest_path)
    if not info["indexed"]:
        raise FileNotFoundError(f"raw_doc index row not found for {h}")
    if info["exists_local"]:
        return {**info, "restored": False, "reason": "already_local"}
    remote_uri = str(info.get("remote_uri") or "")
    if not remote_uri:
        raise FileNotFoundError(f"raw_doc bytes are not local and no offload URI is recorded for {h}")
    byte_len = int(info.get("byte_len") or 0)
    if byte_len > max_bytes:
        raise ValueError(f"raw_doc {h} is {byte_len} bytes, above restore limit {max_bytes}")

    local_path_s = info.get("local_path")
    if not local_path_s:
        raise FileNotFoundError(f"raw_doc {h} has no indexed local path")
    local_path = Path(str(local_path_s))
    local_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = local_path.with_name(local_path.name + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()
    proc = subprocess.run(
        ["aws", "s3", "cp", remote_uri, str(tmp_path), "--only-show-errors"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        if tmp_path.exists():
            tmp_path.unlink()
        raise RuntimeError(f"aws s3 cp failed for {remote_uri}: {detail}")
    restored_hash = content_hash(tmp_path.read_bytes())
    if restored_hash != h:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(f"restored raw_doc hash mismatch for {h}: got {restored_hash}")
    actual_size = tmp_path.stat().st_size
    if byte_len and actual_size != byte_len:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(f"restored raw_doc size mismatch for {h}: {actual_size} != {byte_len}")
    tmp_path.replace(local_path)
    return {
        **locate(conn, h, manifest_path=manifest_path),
        "restored": True,
        "restored_from": remote_uri,
        "byte_len": actual_size,
    }


def path_of(conn: sqlite3.Connection, h: str) -> Path | None:
    row = conn.execute("SELECT path FROM raw_docs WHERE content_hash=?", (h,)).fetchone()
    if not row:
        return None
    return _abs_repo_path(row["path"])
