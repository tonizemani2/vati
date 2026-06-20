"""Bulk-corpus ingest — load a downloaded Parquet snapshot into the `papers` substrate.

The arXiv OAI-PMH harvest in `pillars/research.py` is gapless but slow (1 req/3s). A community
Parquet mirror (e.g. HF `nick007x/arxiv-papers`, 2.5M rows through 2025) backfills the whole corpus
in one pass — the detector then runs on a far larger, more recent substrate with no new pipeline.

This is the only NEW code the arXiv expansion needs: map the mirror's columns onto the `papers`
schema, clean the (HTML-laced) date, and reuse `research._upsert_papers` (idempotent by arxiv_id,
so it merges with whatever the OAI harvest already landed — no duplicates). Corpus stays out of git
(see .gitignore data/corpus/); only the derived series live in the DB. $0, keyless.

Patents and OpenAlex are separate stores (PatentsView → Parquet on R2; OpenAlex → API adapter) —
they do NOT land in `papers`, which is the arXiv research corpus.
"""
from __future__ import annotations

import re
import sqlite3
import sys

from . import db
from .pillars.research import _upsert_papers

_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
_DATE_RE = re.compile(r"(\d{1,2})\s+([A-Z][a-z]{2})\s+(\d{4})")
_CODE_RE = re.compile(r"\(([^)]+)\)")  # arXiv category code sits inside parens in the subject label


def _iso(d: str, m: str, y: str) -> str | None:
    mm = _MONTHS.get(m)
    return f"{int(y):04d}-{mm:02d}-{int(d):02d}" if mm else None


def _parse_dates(s: str | None) -> tuple[str, str]:
    """'18 Feb 2009 (<a..>v1</a>), last revised 18 Jun 2009 ...' → (published, updated)."""
    if not s:
        return "", ""
    hits = _DATE_RE.findall(s)
    if not hits:
        return "", ""
    published = _iso(*hits[0]) or ""
    updated = ""
    if "last revised" in s.lower() and len(hits) > 1:
        updated = _iso(*hits[-1]) or ""
    return published, updated


def _codes(label: str | None) -> list[str]:
    """Extract arXiv category codes ('astro-ph.EP') from a subject label string."""
    return _CODE_RE.findall(label) if label else []


def _row_to_paper(r: dict) -> dict | None:
    published, updated = _parse_dates(r.get("submission_date"))
    if not published:
        return None  # undated → useless to the time-series detector
    prim = _codes(r.get("primary_subject"))
    cats = _codes(r.get("subjects")) or prim
    authors = r.get("authors") or []
    if not isinstance(authors, list):
        authors = [a.strip() for a in str(authors).split(";") if a.strip()]
    return {
        "external_id": (r.get("arxiv_id") or "").strip(),
        "published": published,
        "updated": updated,
        "primary_category": prim[0] if prim else None,
        "categories": " ".join(cats),
        "title": (r.get("title") or "").strip(),
        "abstract": (r.get("abstract") or "").strip(),
        "authors": "; ".join(a.strip() for a in authors if a and a.strip()),
        "n_authors": len(authors),
    }


def ingest_parquet(conn: sqlite3.Connection, path: str, *, batch: int = 50_000, log=print) -> dict:
    """Stream a Parquet arXiv mirror into `papers` in bounded-memory slices. Idempotent."""
    import polars as pl

    cols = ["arxiv_id", "title", "authors", "submission_date", "primary_subject", "subjects", "abstract"]
    lazy = pl.scan_parquet(path).select(cols)
    total = lazy.select(pl.len()).collect().item()
    log(f"corpus ingest: {total:,} rows from {path}")
    written = skipped = offset = 0
    while offset < total:
        df = lazy.slice(offset, batch).collect()
        papers = []
        for r in df.iter_rows(named=True):
            p = _row_to_paper(r)
            if p and p["external_id"]:
                papers.append(p)
            else:
                skipped += 1
        written += _upsert_papers(conn, papers, log=log)
        offset += batch
        log(f"  {min(offset, total):,}/{total:,} (skipped {skipped} undated/empty)")
    n = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    log(f"✓ ingest done — papers table now holds {n:,} rows")
    return {"rows_seen": total, "written": written, "skipped": skipped, "papers_total": n}


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/corpus/arxiv.parquet"
    conn = db.connect()
    db.init_db(conn)
    conn.execute("PRAGMA busy_timeout=300000")
    ingest_parquet(conn, path)
    conn.close()
