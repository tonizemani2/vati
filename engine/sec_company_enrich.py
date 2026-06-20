"""SEC company ticker/CIK enrichment for top company entities.

This is a conservative entity-backbone step, not a market-price feed. It downloads the official
SEC ``company_tickers.json`` index, preserves the raw response, and links existing top company
entities to exact ticker and CIK identifiers when an alias or legal name matches deterministically.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import urllib.request
from dataclasses import dataclass
from typing import Any

from engine import rawstore, world_catalog
from engine.graph import _upsert_source
from engine.schemas import Source, SourceKind, _now

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
UA = "predictthefuture research (research@vaticinus.com)"
REQUEST_TIMEOUT_S = 30
DEFAULT_LIMIT = 100


@dataclass(frozen=True)
class SecCompanyRecord:
    cik: int
    ticker: str
    title: str


@dataclass(frozen=True)
class SecCompanyMatch:
    entity_id: str
    canonical_name: str
    cik: int
    ticker: str
    title: str
    confidence: float
    method: str
    rationale: str


def _stable_id(*parts: object) -> str:
    payload = "\x1f".join("" if p is None else str(p) for p in parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:32]


def _load_aliases(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        out = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(x) for x in out if str(x).strip()] if isinstance(out, list) else []


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _without_legal_suffixes(text: str) -> str:
    toks = _norm(text).split()
    suffixes = {
        "a", "ab", "ag", "co", "company", "corp", "corporation", "holdings", "inc",
        "incorporated", "limited", "llc", "ltd", "n", "nv", "plc", "s", "sa", "se",
        "spa", "v",
    }
    while toks and toks[-1] in suffixes:
        toks.pop()
    return " ".join(toks)


def _cik_padded(cik: int) -> str:
    return f"{int(cik):010d}"


def _is_plain_ticker(alias: str) -> bool:
    a = alias.strip().upper()
    if alias.startswith(("LEI:", "CIK:", "registered_as:")):
        return False
    if "." in a:
        return False
    return bool(re.fullmatch(r"[A-Z][A-Z0-9-]{0,7}", a))


def _fetch_company_tickers() -> tuple[bytes | None, dict[str, Any] | None]:
    try:
        req = urllib.request.Request(SEC_TICKERS_URL, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:  # noqa: S310 official SEC file
            raw = resp.read()
        return raw, json.loads(raw.decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001 - official keyless endpoint; miss rather than fabricate
        return None, None


def _records(data: dict[str, Any]) -> list[SecCompanyRecord]:
    out: list[SecCompanyRecord] = []
    values = data.values() if isinstance(data, dict) else []
    for row in values:
        if not isinstance(row, dict):
            continue
        try:
            cik = int(row["cik_str"])
            ticker = str(row["ticker"]).strip().upper()
            title = str(row["title"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if ticker and title:
            out.append(SecCompanyRecord(cik=cik, ticker=ticker, title=title))
    return out


def _company_rows(conn: sqlite3.Connection, *, limit: int, only: list[str] | None) -> list[sqlite3.Row]:
    world_catalog.seed_top_entities(conn, log=lambda *_a, **_k: None)
    params: list[Any] = []
    sql = "SELECT id, canonical_name, aliases, note FROM entities WHERE kind='company'"
    if only:
        placeholders = ",".join("?" for _ in only)
        sql += f" AND canonical_name IN ({placeholders})"
        params.extend(only)
    sql += " ORDER BY canonical_name"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return conn.execute(sql, params).fetchall()


def _best_match(row: sqlite3.Row, records: list[SecCompanyRecord]) -> SecCompanyMatch | None:
    aliases = _load_aliases(row["aliases"])
    by_ticker = {r.ticker: r for r in records}
    for alias in aliases:
        if _is_plain_ticker(alias):
            rec = by_ticker.get(alias.upper())
            if rec:
                return SecCompanyMatch(
                    entity_id=row["id"],
                    canonical_name=row["canonical_name"],
                    cik=rec.cik,
                    ticker=rec.ticker,
                    title=rec.title,
                    confidence=1.0,
                    method="sec_ticker_alias",
                    rationale=f"Exact top-entity ticker alias {rec.ticker} matched SEC company_tickers.json.",
                )

    legal_names = [
        a for a in [row["canonical_name"], *aliases]
        if not _is_plain_ticker(a) and len(_norm(a).split()) >= 2
    ]
    legal_norms = {_norm(a) for a in legal_names}
    legal_cores = {_without_legal_suffixes(a) for a in legal_names if _without_legal_suffixes(a)}
    for rec in records:
        title_n = _norm(rec.title)
        title_core = _without_legal_suffixes(rec.title)
        if title_n in legal_norms or (title_core and title_core in legal_cores):
            return SecCompanyMatch(
                entity_id=row["id"],
                canonical_name=row["canonical_name"],
                cik=rec.cik,
                ticker=rec.ticker,
                title=rec.title,
                confidence=0.96,
                method="sec_legal_name",
                rationale=f"Exact normalized legal/title match for {rec.title} in SEC company_tickers.json.",
            )
    return None


def _upsert_sec_source(conn: sqlite3.Connection, content: bytes) -> str:
    content_hash = rawstore.put(conn, content, url=SEC_TICKERS_URL, media_type="application/json")
    src = Source(
        url=SEC_TICKERS_URL,
        title="SEC Company Tickers and CIK Index",
        pillar_id=6,
        kind=SourceKind.primary,
        trust_score=95,
        trust_rationale=(
            "Official SEC company_tickers.json index mapping reporting-company tickers to CIKs and "
            "SEC titles. Used only for deterministic ticker/CIK entity enrichment."
        ),
        content_hash=content_hash,
    )
    source_id = _upsert_source(conn, src)
    rawstore.put(conn, content, source_id=source_id, url=SEC_TICKERS_URL, media_type="application/json")
    return source_id


def _apply_match(conn: sqlite3.Connection, match: SecCompanyMatch) -> int:
    row = conn.execute("SELECT aliases, note FROM entities WHERE id=?", (match.entity_id,)).fetchone()
    aliases = set(_load_aliases(row["aliases"]))
    aliases.update({match.ticker, f"CIK:{_cik_padded(match.cik)}"})
    note = row["note"] or ""
    sec_note = f"SEC ticker:{match.ticker} CIK:{_cik_padded(match.cik)} title={match.title}."
    if "SEC ticker:" not in note:
        note = (note.rstrip() + " " + sec_note).strip()
    else:
        note = re.sub(r"SEC ticker:[^.]+\.", sec_note, note)
    conn.execute("UPDATE entities SET aliases=?, note=? WHERE id=?", (json.dumps(sorted(aliases)), note, match.entity_id))

    now_s = _now().isoformat()
    written = 0
    for ref_table, ref_id, ref_label in (
        ("ticker", match.ticker, match.title),
        ("cik", _cik_padded(match.cik), match.title),
    ):
        cur = conn.execute(
            """
            INSERT INTO entity_links (
                id, entity_id, ref_table, ref_id, ref_label, pillar_id, confidence,
                method, rationale, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(entity_id, ref_table, ref_id) DO UPDATE SET
                ref_label=excluded.ref_label,
                pillar_id=excluded.pillar_id,
                confidence=excluded.confidence,
                method=excluded.method,
                rationale=excluded.rationale
            """,
            (
                _stable_id("sec_company_tickers", match.entity_id, ref_table, ref_id),
                match.entity_id,
                ref_table,
                ref_id,
                ref_label,
                6,
                match.confidence,
                match.method,
                match.rationale,
                now_s,
            ),
        )
        written += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    return written


def enrich_top_entities(
    conn: sqlite3.Connection,
    *,
    limit: int = DEFAULT_LIMIT,
    only: list[str] | None = None,
    log=print,
) -> dict[str, Any]:
    raw, data = _fetch_company_tickers()
    if not raw or not data:
        return {"seen": 0, "matched": 0, "missed": 0, "links_written": 0, "source_id": None, "misses": []}
    source_id = _upsert_sec_source(conn, raw)
    records = _records(data)
    rows = _company_rows(conn, limit=limit, only=only)

    matches: list[SecCompanyMatch] = []
    misses: list[str] = []
    links_written = 0
    for row in rows:
        match = _best_match(row, records)
        if match:
            matches.append(match)
            links_written += _apply_match(conn, match)
            log(f"  + {row['canonical_name']}: {match.ticker} CIK {_cik_padded(match.cik)} ({match.method})")
        else:
            misses.append(row["canonical_name"])
            log(f"  - {row['canonical_name']}: no exact SEC ticker/CIK match")

    conn.commit()
    return {
        "seen": len(rows),
        "matched": len(matches),
        "missed": len(misses),
        "links_written": links_written,
        "source_id": source_id,
        "misses": misses,
    }
