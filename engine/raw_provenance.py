"""Recover missing raw-document index rows without inventing provenance.

Older collectors often stored a `sources.content_hash` for a derived payload but did not persist the
exact bytes in `raw_docs`. This module can refetch small public URLs and will only store bytes when
their sha256 exactly matches the existing source hash.
"""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from typing import Callable, Iterable
from urllib.parse import urldefrag, urlparse
from urllib.request import Request, urlopen

from engine import rawstore
from engine.schemas import _now

UA = "predictthefuture-world-state/1.0 raw-provenance-recovery"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_TIMEOUT = 20.0
DEFAULT_DETAIL_LIMIT = 25

DEFAULT_ALLOW_PREFIXES = (
    "https://www.federalregister.gov/api/",
    "https://api.federalregister.gov/api/",
    "https://api.worldbank.org/",
    "https://api.openalex.org/",
    "https://api.semanticscholar.org/",
    "https://api.gleif.org/",
    "https://www.sec.gov/",
    "https://www.sec.gov/files/",
    "https://data.sec.gov/",
    "https://efts.sec.gov/",
    "https://export.arxiv.org/",
    "https://ourworldindata.org/grapher/",
    "https://wikimedia.org/api/",
    "https://wikimedia.org/api/rest_v1/",
    "https://fred.stlouisfed.org/",
    "https://api.stlouisfed.org/",
    "https://patents.google.com/xhr/query",
    "https://comtradeapi.un.org/",
    "https://api.reporter.nih.gov/",
    "https://epoch.ai/",
    "https://api.usaspending.gov/",
    "http://exportcontrol.mofcom.gov.cn/",
)

EXACT_RAW_DOC = "exact_raw_doc"
LEGACY_HASH_NO_RAW_DOC = "legacy_hash_no_raw_doc"
LEGACY_NO_CONTENT_HASH = "legacy_no_content_hash"


@dataclass(frozen=True)
class FetchedBytes:
    url: str
    content: bytes
    media_type: str | None = None
    status_code: int | None = None


class FetchTooLarge(RuntimeError):
    pass


def _skip_reason(url: str | None, allow_prefixes: tuple[str, ...]) -> str | None:
    if not url:
        return "missing_url"
    if any(ch.isspace() or ord(ch) < 32 for ch in url):
        return "url_has_spaces_or_control_chars"
    fetch_url = urldefrag(url).url
    parsed = urlparse(fetch_url)
    if parsed.scheme not in {"http", "https"}:
        return "unsupported_scheme"
    if allow_prefixes and not any(fetch_url.startswith(prefix) for prefix in allow_prefixes):
        return "prefix_not_allowed"
    return None


def _host_bucket(url: str | None) -> str:
    if not url:
        return "missing_url"
    reason = _skip_reason(url, ())
    if reason:
        return reason
    parsed = urlparse(urldefrag(url).url)
    return parsed.netloc or "unknown_host"


def fetch_bytes(url: str, *, max_bytes: int = DEFAULT_MAX_BYTES, timeout: float = DEFAULT_TIMEOUT) -> FetchedBytes:
    """Fetch up to `max_bytes` from `url`, raising if the response is larger."""
    fetch_url = urldefrag(url).url
    req = Request(fetch_url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - explicit user-requested provenance fetch
        chunks: list[bytes] = []
        seen = 0
        while True:
            chunk = resp.read(min(64 * 1024, max_bytes + 1 - seen))
            if not chunk:
                break
            chunks.append(chunk)
            seen += len(chunk)
            if seen > max_bytes:
                raise FetchTooLarge(f"response exceeded {max_bytes} bytes")
        media_type = resp.headers.get_content_type() if resp.headers else None
        status = getattr(resp, "status", None)
    return FetchedBytes(url=fetch_url, content=b"".join(chunks), media_type=media_type, status_code=status)


def _missing_source_rows(
    conn: sqlite3.Connection,
    limit: int | None = None,
    url_prefixes: Iterable[str] | None = None,
) -> list[sqlite3.Row]:
    sql = """
        SELECT s.id, s.url, s.title, s.content_hash
        FROM sources s
        LEFT JOIN raw_docs r ON r.content_hash = s.content_hash
        WHERE s.content_hash IS NOT NULL
          AND length(s.content_hash) > 0
          AND r.content_hash IS NULL
    """
    params: list[object] = []
    prefixes = tuple(url_prefixes or ())
    if prefixes:
        sql += " AND (" + " OR ".join("s.url LIKE ?" for _ in prefixes) + ")"
        params.extend(f"{prefix}%" for prefix in prefixes)
    sql += " ORDER BY COALESCE(s.accessed_at, '') DESC, s.id"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))
    return conn.execute(sql, tuple(params)).fetchall()


def _inc(bucket: dict[str, int], key: str) -> None:
    bucket[key] = bucket.get(key, 0) + 1


def _add_detail(out: dict, detail: dict, limit: int) -> None:
    if len(out["details"]) < limit:
        out["details"].append(detail)


def recover_missing_raw_docs(
    conn: sqlite3.Connection,
    *,
    limit: int | None = 50,
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout: float = DEFAULT_TIMEOUT,
    execute: bool = False,
    allow_prefixes: Iterable[str] | None = DEFAULT_ALLOW_PREFIXES,
    url_prefixes: Iterable[str] | None = None,
    fetcher: Callable[..., FetchedBytes] = fetch_bytes,
    detail_limit: int = DEFAULT_DETAIL_LIMIT,
) -> dict:
    """Try to recover raw bytes for hashed sources missing `raw_docs` rows.

    Recovery is intentionally strict: a fetched response is stored only when
    `sha256(fetched_bytes) == sources.content_hash`.
    """
    prefixes = tuple(allow_prefixes or ())
    out = {
        "execute": bool(execute),
        "considered": 0,
        "eligible": 0,
        "fetched": 0,
        "matched": 0,
        "stored": 0,
        "mismatched": 0,
        "too_large": 0,
        "errors": 0,
        "skipped": 0,
        "skip_reasons": {},
        "details": [],
    }
    rows = _missing_source_rows(conn, limit=limit, url_prefixes=url_prefixes)
    for row in rows:
        out["considered"] += 1
        sid = row["id"]
        url = row["url"]
        expected = row["content_hash"]
        reason = _skip_reason(url, prefixes)
        if reason:
            out["skipped"] += 1
            _inc(out["skip_reasons"], reason)
            _add_detail(out, {"source_id": sid, "status": "skipped", "reason": reason, "url": url}, detail_limit)
            continue

        out["eligible"] += 1
        try:
            fetched = fetcher(url, max_bytes=max_bytes, timeout=timeout)
        except FetchTooLarge as exc:
            out["too_large"] += 1
            _add_detail(out, {"source_id": sid, "status": "too_large", "error": str(exc), "url": url}, detail_limit)
            continue
        except Exception as exc:  # noqa: BLE001 - network recovery should summarize and continue
            out["errors"] += 1
            _add_detail(
                out,
                {"source_id": sid, "status": "error", "error": f"{type(exc).__name__}: {exc}", "url": url},
                detail_limit,
            )
            continue

        out["fetched"] += 1
        actual = rawstore.content_hash(fetched.content)
        if actual != expected:
            out["mismatched"] += 1
            _add_detail(
                out,
                {
                    "source_id": sid,
                    "status": "mismatch",
                    "expected": expected,
                    "actual": actual,
                    "url": url,
                    "fetched_url": fetched.url,
                    "byte_len": len(fetched.content),
                },
                detail_limit,
            )
            continue

        out["matched"] += 1
        if execute:
            rawstore.put(conn, fetched.content, source_id=sid, url=url, media_type=fetched.media_type)
            out["stored"] += 1
        _add_detail(
            out,
            {
                "source_id": sid,
                "status": "stored" if execute else "matched",
                "content_hash": actual,
                "url": url,
                "fetched_url": fetched.url,
                "byte_len": len(fetched.content),
                "media_type": fetched.media_type,
            },
            detail_limit,
        )
    return out


def raw_gap_summary(conn: sqlite3.Connection, *, limit: int = 12) -> dict:
    """Summarize hashed sources whose exact bytes are still absent from raw_docs."""
    rows = conn.execute(
        """
        SELECT s.id, s.title, s.url, COALESCE(s.raw_provenance_status, 'unknown') AS status
        FROM sources s
        LEFT JOIN raw_docs r ON r.content_hash = s.content_hash
        WHERE s.content_hash IS NOT NULL
          AND length(s.content_hash) > 0
          AND r.content_hash IS NULL
        ORDER BY COALESCE(s.accessed_at, '') DESC, s.id
        """
    ).fetchall()
    by_host: dict[str, int] = {}
    by_status: dict[str, int] = {}
    examples_by_host: dict[str, list[dict[str, str | None]]] = {}
    malformed = 0
    for row in rows:
        host = _host_bucket(row["url"])
        by_host[host] = by_host.get(host, 0) + 1
        status = str(row["status"] or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        if host in {"url_has_spaces_or_control_chars", "missing_url", "unsupported_scheme", "unknown_host"}:
            malformed += 1
        examples = examples_by_host.setdefault(host, [])
        if len(examples) < 3:
            examples.append({
                "source_id": row["id"],
                "title": row["title"],
                "url": row["url"],
                "status": status,
            })
    top_hosts = [
        {"host": host, "sources": n, "examples": examples_by_host.get(host, [])}
        for host, n in sorted(by_host.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]
    return {
        "total": len(rows),
        "by_status": dict(sorted(by_status.items())),
        "top_hosts": top_hosts,
        "malformed_or_nonfetchable_url_count": malformed,
        "note": (
            "Exact recovery stores bytes only when sha256(refetched bytes) equals the legacy source hash; "
            "dynamic APIs and derived snapshot hashes usually mismatch and must remain legacy."
        ),
    }


def mark_legacy_provenance(conn: sqlite3.Connection, *, overwrite: bool = False) -> dict:
    """Classify source raw-byte provenance without changing source hashes or raw bytes."""
    checked_at = _now().isoformat()
    status_filter = "" if overwrite else "AND COALESCE(raw_provenance_status, 'unknown') = 'unknown'"
    exact = conn.execute(
        f"""
        UPDATE sources
        SET raw_provenance_status=?,
            raw_provenance_reason='exact bytes indexed in raw_docs',
            raw_provenance_checked_at=?
        WHERE content_hash IS NOT NULL
          AND length(content_hash) > 0
          AND EXISTS (SELECT 1 FROM raw_docs r WHERE r.content_hash=sources.content_hash)
          {status_filter}
        """,
        (EXACT_RAW_DOC, checked_at),
    ).rowcount
    legacy_hash = conn.execute(
        f"""
        UPDATE sources
        SET raw_provenance_status=?,
            raw_provenance_reason='legacy source hash without preserved raw bytes; do not treat as exact provenance',
            raw_provenance_checked_at=?
        WHERE content_hash IS NOT NULL
          AND length(content_hash) > 0
          AND NOT EXISTS (SELECT 1 FROM raw_docs r WHERE r.content_hash=sources.content_hash)
          {status_filter}
        """,
        (LEGACY_HASH_NO_RAW_DOC, checked_at),
    ).rowcount
    legacy_no_hash = conn.execute(
        f"""
        UPDATE sources
        SET raw_provenance_status=?,
            raw_provenance_reason='legacy source row predates content-hash/raw-doc contract',
            raw_provenance_checked_at=?
        WHERE (content_hash IS NULL OR length(content_hash) = 0)
          {status_filter}
        """,
        (LEGACY_NO_CONTENT_HASH, checked_at),
    ).rowcount
    conn.commit()
    counts = {
        str(r["raw_provenance_status"]): int(r["n"])
        for r in conn.execute(
            """
            SELECT raw_provenance_status, count(*) n
            FROM sources
            GROUP BY raw_provenance_status
            ORDER BY raw_provenance_status
            """
        )
    }
    return {
        "updated_exact_raw_doc": int(exact or 0),
        "updated_legacy_hash_no_raw_doc": int(legacy_hash or 0),
        "updated_legacy_no_content_hash": int(legacy_no_hash or 0),
        "status_counts": counts,
    }


def format_legacy_mark(out: dict) -> str:
    lines = [
        "source provenance marking",
        (
            f"updated exact_raw_doc={out['updated_exact_raw_doc']} "
            f"legacy_hash_no_raw_doc={out['updated_legacy_hash_no_raw_doc']} "
            f"legacy_no_content_hash={out['updated_legacy_no_content_hash']}"
        ),
    ]
    if out.get("status_counts"):
        counts = ", ".join(f"{k}={v}" for k, v in sorted(out["status_counts"].items()))
        lines.append(f"status_counts: {counts}")
    return "\n".join(lines)


def format_recovery(out: dict) -> str:
    lines = [
        "raw provenance recovery",
        f"mode: {'execute' if out['execute'] else 'dry-run'}",
        (
            f"considered={out['considered']} eligible={out['eligible']} fetched={out['fetched']} "
            f"matched={out['matched']} stored={out['stored']}"
        ),
        f"mismatched={out['mismatched']} too_large={out['too_large']} errors={out['errors']} skipped={out['skipped']}",
    ]
    if out.get("skip_reasons"):
        reasons = ", ".join(f"{k}={v}" for k, v in sorted(out["skip_reasons"].items()))
        lines.append(f"skip_reasons: {reasons}")
    if out.get("details"):
        lines.append("details:")
        for detail in out["details"]:
            status = detail.get("status")
            sid = detail.get("source_id")
            reason = detail.get("reason") or detail.get("error") or detail.get("byte_len", "")
            lines.append(f"  - {sid}: {status} {reason}")
    return "\n".join(lines)
