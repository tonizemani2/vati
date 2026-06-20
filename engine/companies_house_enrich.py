"""Targeted Companies House enrichment for UK-linked top company entities.

This is a compact entity-backbone step, not a full Companies House lake. It uses the
official public company search page to discover exact company numbers, then fetches the
official JSON URI for each matched company number and preserves raw bytes through rawstore.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from engine import rawstore, world_catalog
from engine.graph import _upsert_source as _graph_upsert_source
from engine.schemas import Source, SourceKind, _now

SEARCH_URL = "https://find-and-update.company-information.service.gov.uk/search/companies"
URI_URL = "https://data.companieshouse.gov.uk/doc/company/{company_number}.json"
UA = "predictthefuture research (research@vaticinus.com)"
REQUEST_TIMEOUT_S = 20
REQUEST_SPACING_S = 0.2
DEFAULT_LIMIT = 100
ACTIVE_STATUSES = {"active", "registered", "open"}


@dataclass(frozen=True)
class SearchResult:
    company_number: str
    company_name: str
    href: str


@dataclass(frozen=True)
class CompaniesHouseMatch:
    entity_id: str
    canonical_name: str
    query: str
    company_number: str
    company_name: str
    status: str
    category: str
    country_of_origin: str
    incorporation_date: str | None
    uri: str
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
    text = text.replace("&amp;", "&")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _without_legal_suffixes(text: str) -> str:
    toks = _norm(text).split()
    suffixes = {
        "ag", "bv", "co", "company", "corp", "corporation", "holdings", "inc",
        "incorporated", "limited", "llc", "ltd", "n", "nv", "p", "plc", "s", "sa",
        "se", "spa", "v",
    }
    while toks and toks[-1] in suffixes:
        toks.pop()
    return " ".join(toks)


def _looks_like_legal_name(text: str) -> bool:
    toks = _norm(text).split()
    if len(toks) < 2:
        return False
    suffixes = {"plc", "limited", "ltd", "holdings", "group", "p", "l", "c"}
    return any(t in suffixes for t in toks[1:])


def _looks_like_uk_public_parent(text: str) -> bool:
    toks = _norm(text).split()
    if len(toks) < 2:
        return False
    if "plc" in toks:
        return True
    for idx in range(len(toks) - 2):
        if toks[idx:idx + 3] == ["p", "l", "c"]:
            return True
    return False


def _active_status(status: str) -> bool:
    s = status.strip().lower()
    if s in ACTIVE_STATUSES:
        return True
    return s.startswith("transform status open")


def _usable_queries(name: str, aliases: list[str]) -> list[str]:
    out: list[str] = []
    for candidate in aliases:
        c = candidate.strip()
        if not c or c.startswith(("LEI:", "CIK:", "CH:", "CompaniesHouse:", "registered_as:")):
            continue
        if re.fullmatch(r"[A-Z]{1,5}(?:\\.[A-Z]+)?", c):
            continue
        if len(_norm(c)) < 3:
            continue
        if _looks_like_uk_public_parent(c):
            out.append(c)
    deduped: list[str] = []
    seen: set[str] = set()
    for q in out:
        key = _norm(q)
        if key not in seen:
            seen.add(key)
            deduped.append(q)
    deduped.sort(key=lambda q: (_looks_like_legal_name(q), len(q)), reverse=True)
    return deduped[:5]


def _search_url(query: str) -> str:
    return f"{SEARCH_URL}?{urllib.parse.urlencode({'q': query})}"


def _parse_search_results(raw: bytes | str) -> list[SearchResult]:
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    results: list[SearchResult] = []
    seen: set[str] = set()
    pattern = re.compile(r'<a[^>]+href="(/company/([A-Z0-9]+))"[^>]*>(.*?)</a>', re.I | re.S)
    for match in pattern.finditer(text):
        href = html.unescape(match.group(1))
        company_number = html.unescape(match.group(2)).strip().upper()
        company_name = re.sub(r"<.*?>", "", match.group(3), flags=re.S)
        company_name = " ".join(html.unescape(company_name).split())
        if not company_number or not company_name or company_number in seen:
            continue
        seen.add(company_number)
        results.append(SearchResult(company_number=company_number, company_name=company_name, href=href))
    return results


def _search_company(query: str) -> tuple[bytes | None, list[SearchResult]]:
    try:
        req = urllib.request.Request(_search_url(query), headers={"User-Agent": UA, "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:  # noqa: S310 official public search
            raw = resp.read()
        return raw, _parse_search_results(raw)
    except Exception:  # noqa: BLE001 - public endpoint; miss rather than fabricate
        return None, []


def _fetch_company_json(company_number: str) -> tuple[bytes | None, dict[str, Any] | None]:
    url = URI_URL.format(company_number=company_number)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:  # noqa: S310 official public URI
            raw = resp.read()
        return raw, json.loads(raw.decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001 - public endpoint; miss rather than fabricate
        return None, None


def _candidate_names(row: sqlite3.Row) -> set[str]:
    return {_norm(row["canonical_name"]), *{_norm(a) for a in _load_aliases(row["aliases"])}}


def _best_result(row: sqlite3.Row, query: str, results: list[SearchResult]) -> SearchResult | None:
    acceptable = _candidate_names(row)
    query_n = _norm(query)
    for result in results[:10]:
        name_n = _norm(result.company_name)
        if name_n == query_n and name_n in acceptable:
            return result
    return None


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


def _extract_match(row: sqlite3.Row, query: str, result: SearchResult, data: dict[str, Any]) -> CompaniesHouseMatch | None:
    primary = data.get("primaryTopic") if isinstance(data.get("primaryTopic"), dict) else {}
    company_name = str(primary.get("CompanyName") or result.company_name).strip()
    company_number = str(primary.get("CompanyNumber") or result.company_number).strip().upper()
    if company_number != result.company_number:
        return None
    status = str(primary.get("CompanyStatus") or "")
    if not _active_status(status):
        return None
    names = _candidate_names(row)
    if _norm(company_name) != _norm(query) or _norm(company_name) not in names:
        return None
    return CompaniesHouseMatch(
        entity_id=row["id"],
        canonical_name=row["canonical_name"],
        query=query,
        company_number=company_number,
        company_name=company_name,
        status=status,
        category=str(primary.get("CompanyCategory") or ""),
        country_of_origin=str(primary.get("CountryOfOrigin") or ""),
        incorporation_date=primary.get("IncorporationDate"),
        uri=URI_URL.format(company_number=company_number),
        confidence=0.98,
        method="companies_house_exact_search",
        rationale=f"Exact official Companies House search/URI match for query '{query}'.",
    )


def _upsert_companies_house_source(conn: sqlite3.Connection, content: bytes) -> str:
    content_hash = rawstore.put(conn, content, url=SEARCH_URL, media_type="application/json")
    src = Source(
        url=SEARCH_URL,
        title="Companies House Company Search and URI Records",
        pillar_id=6,
        kind=SourceKind.primary,
        trust_score=92,
        trust_rationale=(
            "Official Companies House public search and company URI JSON records. Used only for "
            "deterministic UK company-number enrichment of top company entities."
        ),
        content_hash=content_hash,
    )
    source_id = _graph_upsert_source(conn, src)
    rawstore.put(conn, content, source_id=source_id, url=SEARCH_URL, media_type="application/json")
    return source_id


def _clean_existing_companies_house(conn: sqlite3.Connection, rows: list[sqlite3.Row]) -> int:
    cleaned = 0
    for row in rows:
        existing_links = conn.execute(
            """
            SELECT ref_id, ref_label
            FROM entity_links
            WHERE entity_id=? AND ref_table='companies_house_number' AND method='companies_house_exact_search'
            """,
            (row["id"],),
        ).fetchall()
        if not existing_links:
            continue
        remove_aliases = {l["ref_id"] for l in existing_links}
        remove_aliases |= {f"CH:{l['ref_id']}" for l in existing_links}
        remove_aliases |= {f"CompaniesHouse:{l['ref_id']}" for l in existing_links}
        remove_aliases |= {l["ref_label"] for l in existing_links}
        aliases = [a for a in _load_aliases(row["aliases"]) if a not in remove_aliases]
        note = re.sub(r"\s*Companies House:[^.]+\.", "", row["note"] or "").strip()
        conn.execute(
            "UPDATE entities SET aliases=?, note=? WHERE id=?",
            (json.dumps(sorted(set(aliases))), note, row["id"]),
        )
        cur = conn.execute(
            """
            DELETE FROM entity_links
            WHERE entity_id=? AND ref_table='companies_house_number' AND method='companies_house_exact_search'
            """,
            (row["id"],),
        )
        cleaned += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    return cleaned


def _apply_match(conn: sqlite3.Connection, match: CompaniesHouseMatch) -> int:
    row = conn.execute("SELECT aliases, note FROM entities WHERE id=?", (match.entity_id,)).fetchone()
    aliases = set(_load_aliases(row["aliases"]))
    aliases.update({match.company_name, f"CH:{match.company_number}", f"CompaniesHouse:{match.company_number}"})
    note = row["note"] or ""
    ch_note = (
        f"Companies House:{match.company_number} name={match.company_name} "
        f"status={match.status or 'n/a'} incorporated={match.incorporation_date or 'n/a'}."
    )
    if "Companies House:" not in note:
        note = (note.rstrip() + " " + ch_note).strip()
    else:
        note = re.sub(r"Companies House:[^.]+\\.", ch_note, note)
    conn.execute("UPDATE entities SET aliases=?, note=? WHERE id=?", (json.dumps(sorted(aliases)), note, match.entity_id))
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
            _stable_id("companies_house", match.entity_id, match.company_number),
            match.entity_id,
            "companies_house_number",
            match.company_number,
            match.company_name,
            6,
            match.confidence,
            match.method,
            match.rationale,
            _now().isoformat(),
        ),
    )
    return cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0


def enrich_top_entities(
    conn: sqlite3.Connection,
    *,
    limit: int = DEFAULT_LIMIT,
    only: list[str] | None = None,
    log=print,
) -> dict[str, Any]:
    rows = _company_rows(conn, limit=limit, only=only)
    cleaned = _clean_existing_companies_house(conn, rows)
    if cleaned:
        rows = _company_rows(conn, limit=limit, only=only)
    matches: list[CompaniesHouseMatch] = []
    misses: list[str] = []
    raw_events: list[dict[str, Any]] = []
    profile_payloads: list[dict[str, Any]] = []

    for row in rows:
        match: CompaniesHouseMatch | None = None
        queries = _usable_queries(row["canonical_name"], _load_aliases(row["aliases"]))
        for query in queries:
            search_raw, results = _search_company(query)
            if search_raw:
                rawstore.put(conn, search_raw, url=_search_url(query), media_type="text/html")
            result = _best_result(row, query, results)
            raw_events.append(
                {
                    "entity": row["canonical_name"],
                    "query": query,
                    "result_count": len(results),
                    "chosen_company_number": result.company_number if result else None,
                    "chosen_company_name": result.company_name if result else None,
                }
            )
            if not result:
                time.sleep(REQUEST_SPACING_S)
                continue
            profile_raw, profile = _fetch_company_json(result.company_number)
            if profile_raw:
                rawstore.put(conn, profile_raw, url=URI_URL.format(company_number=result.company_number), media_type="application/json")
            if profile:
                match = _extract_match(row, query, result, profile)
                profile_payloads.append({"query": query, "profile": profile})
            time.sleep(REQUEST_SPACING_S)
            if match:
                break
        if match:
            matches.append(match)
            log(f"  + {row['canonical_name']}: {match.company_number} {match.company_name} ({match.status})")
        else:
            misses.append(row["canonical_name"])
            log(f"  - {row['canonical_name']}: no exact Companies House match")

    source_bytes = json.dumps(
        {
            "source": "Companies House Company Search and URI Records",
            "fetched_at": _now().isoformat(),
            "matches": [m.__dict__ for m in matches],
            "misses": misses,
            "search_events": raw_events,
            "profiles": profile_payloads,
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    source_id = _upsert_companies_house_source(conn, source_bytes)
    links_written = 0
    for match in matches:
        links_written += _apply_match(conn, match)
    # Attach exact profile bytes to the registered source after it exists.
    for payload in profile_payloads:
        profile = payload.get("profile") if isinstance(payload, dict) else None
        primary = profile.get("primaryTopic") if isinstance(profile, dict) and isinstance(profile.get("primaryTopic"), dict) else {}
        number = str(primary.get("CompanyNumber") or "").strip().upper()
        if number:
            rawstore.put(
                conn,
                json.dumps(profile, ensure_ascii=False, sort_keys=True).encode("utf-8"),
                source_id=source_id,
                url=URI_URL.format(company_number=number),
                media_type="application/json",
            )
    conn.commit()
    return {
        "seen": len(rows),
        "matched": len(matches),
        "missed": len(misses),
        "links_written": links_written,
        "source_id": source_id,
        "misses": misses,
        "cleaned": cleaned,
    }
