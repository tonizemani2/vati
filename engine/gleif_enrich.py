"""Targeted GLEIF LEI enrichment for top company entities.

This is not the full GLEIF lake. It is a conservative V1 entity-backbone step: query the official
GLEIF API for existing top company entities, attach high-confidence LEI identifiers as aliases, and
write an `entity_links` row keyed by the LEI. Raw API responses are preserved through rawstore.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from engine import rawstore, world_catalog
from engine.graph import _upsert_source
from engine.schemas import Source, SourceKind, _now

GLEIF_URL = "https://api.gleif.org/api/v1/lei-records"
UA = "predictthefuture research (research@vaticinus.com)"
REQUEST_TIMEOUT_S = 20
REQUEST_SPACING_S = 0.2
DEFAULT_LIMIT = 50
EXPECTED_GLEIF_JURISDICTION = {
    "Siemens Energy": "DE",
}


@dataclass
class LeiMatch:
    entity_id: str
    canonical_name: str
    query: str
    lei: str
    legal_name: str
    status: str
    registration_status: str
    jurisdiction: str | None
    country: str | None
    headquarters_country: str | None
    registered_as: str | None
    golden_copy_publish_date: str | None
    score: float


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


def _tokens(text: str) -> set[str]:
    return {t for t in _norm(text).split() if len(t) > 1 and t not in {"the", "inc", "corp", "co", "ltd"}}


def _without_legal_suffixes(text: str) -> str:
    toks = _norm(text).split()
    suffixes = {
        "a",
        "ab", "ag", "co", "company", "corp", "corporation", "gmbh", "group", "holdings",
        "inc", "incorporated", "limited", "llc", "ltd", "n", "nv", "plc", "s", "sa", "se",
        "spa", "v",
    }
    while toks and toks[-1] in suffixes:
        toks.pop()
    return " ".join(toks)


def _one_token_legal_match_ok(name_n: str, legal_n: str) -> bool:
    toks = legal_n.split()
    # Bare one-token legal names such as "TESLA" or "PFIZER" often resolve to regional
    # branches instead of the global parent. Require a legal suffix for one-token company seeds.
    if len(toks) < 2 or toks[0] != name_n:
        return False
    strong_suffixes = {
        "a", "ag", "corp", "corporation", "holding", "holdings", "inc", "incorporated",
        "limited", "ltd", "n", "nv", "plc", "s", "sa", "se", "v",
    }
    return all(t in strong_suffixes for t in toks[1:])


def _looks_like_legal_name(text: str) -> bool:
    toks = _norm(text).split()
    legal_suffixes = {
        "a", "ag", "as", "co", "company", "corp", "corporation", "inc", "incorporated",
        "limited", "llc", "ltd", "n", "nv", "plc", "s", "sa", "se", "spa", "v",
    }
    return bool(toks) and toks[-1] in legal_suffixes


def _usable_queries(name: str, aliases: list[str]) -> list[str]:
    out = [name]
    legal_aliases: list[str] = []
    name_token_count = len(_tokens(name))
    for alias in aliases:
        a = alias.strip()
        if not a:
            continue
        if a.startswith(("LEI:", "registered_as:")):
            continue
        # Do not search GLEIF legal names by ticker/short code; that returns ETFs/share classes
        # and similarly named vehicles far too often.
        if len(a) <= 5 and a.upper() == a:
            continue
        if " " not in a and re.fullmatch(r"[A-Z0-9.\-]+", a.upper()):
            continue
        if len(_tokens(a)) < name_token_count:
            continue
        if _looks_like_legal_name(a):
            legal_aliases.append(a)
        out.append(a)
    if legal_aliases:
        out = legal_aliases
    deduped: list[str] = []
    seen: set[str] = set()
    for q in out:
        key = q.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(q)
    deduped.sort(key=lambda q: (len(_tokens(q)), len(q)), reverse=True)
    return deduped


def _fetch(
    query: str,
    *,
    page_size: int = 5,
    jurisdiction: str | None = None,
) -> tuple[bytes | None, dict[str, Any] | None]:
    params = {
        "filter[entity.legalName]": query,
        "filter[entity.status]": "ACTIVE",
        "filter[registration.status]": "ISSUED",
        "page[size]": str(page_size),
    }
    if jurisdiction:
        params["filter[entity.jurisdiction]"] = jurisdiction
    url = f"{GLEIF_URL}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:  # noqa: S310 official API
            raw = resp.read()
        return raw, json.loads(raw.decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001 — keyless public endpoint; miss rather than fabricate
        return None, None


def _candidate_score(entity_name: str, aliases: list[str], record: dict[str, Any]) -> float:
    attrs = record.get("attributes") if isinstance(record.get("attributes"), dict) else {}
    ent = attrs.get("entity") if isinstance(attrs.get("entity"), dict) else {}
    registration = attrs.get("registration") if isinstance(attrs.get("registration"), dict) else {}
    if ent.get("status") != "ACTIVE" or registration.get("status") != "ISSUED":
        return 0.0
    legal = ((ent.get("legalName") or {}).get("name") or "").strip()
    if not legal:
        return 0.0
    legal_n = _norm(legal)
    legal_core = _without_legal_suffixes(legal)
    names = _usable_queries(entity_name, aliases)
    best = 0.0
    for name in names:
        name_n = _norm(name)
        name_core = _without_legal_suffixes(name)
        if not name_n:
            continue
        name_tokens = _tokens(name)
        legal_tokens = _tokens(legal)
        if legal_n == name_n and len(name_n.split()) > 1:
            best = max(best, 1.0)
        elif len(name_tokens) == 1:
            if legal_core == name_core and _one_token_legal_match_ok(name_n, legal_n):
                best = max(best, 1.0)
        elif legal_n == name_n or legal_core == name_core:
            best = max(best, 1.0)
    best += 0.05
    return min(best, 1.0)


def _extract_match(row: sqlite3.Row, query: str, record: dict[str, Any], score: float,
                   golden_copy: str | None) -> LeiMatch:
    attrs = record.get("attributes") if isinstance(record.get("attributes"), dict) else {}
    ent = attrs.get("entity") if isinstance(attrs.get("entity"), dict) else {}
    registration = attrs.get("registration") if isinstance(attrs.get("registration"), dict) else {}
    legal_address = ent.get("legalAddress") if isinstance(ent.get("legalAddress"), dict) else {}
    hq_address = ent.get("headquartersAddress") if isinstance(ent.get("headquartersAddress"), dict) else {}
    return LeiMatch(
        entity_id=row["id"],
        canonical_name=row["canonical_name"],
        query=query,
        lei=str(attrs.get("lei") or record.get("id") or ""),
        legal_name=str(((ent.get("legalName") or {}).get("name") or "")),
        status=str(ent.get("status") or ""),
        registration_status=str(registration.get("status") or ""),
        jurisdiction=ent.get("jurisdiction"),
        country=legal_address.get("country"),
        headquarters_country=hq_address.get("country"),
        registered_as=ent.get("registeredAs"),
        golden_copy_publish_date=golden_copy,
        score=round(score, 3),
    )


def best_match(row: sqlite3.Row, data: dict[str, Any], *, query: str) -> LeiMatch | None:
    records = data.get("data") if isinstance(data.get("data"), list) else []
    aliases = _load_aliases(row["aliases"])
    golden = (((data.get("meta") or {}).get("goldenCopy") or {}).get("publishDate"))
    best: tuple[float, dict[str, Any]] | None = None
    for rec in records:
        if not isinstance(rec, dict):
            continue
        score = _candidate_score(row["canonical_name"], aliases, rec)
        if best is None or score > best[0]:
            best = (score, rec)
    if best is None or best[0] < 0.92:
        return None
    return _extract_match(row, query, best[1], best[0], golden)


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


def _clean_existing_gleif(conn: sqlite3.Connection, rows: list[sqlite3.Row]) -> int:
    cleaned = 0
    lei_re = re.compile(r"^[A-Z0-9]{18,20}$")
    legacy_fragment_re = re.compile(r"\s*[^.]*\bjurisdiction=[^.]*\bgolden_copy=[^.]*\.")
    for row in rows:
        existing_links = conn.execute(
            """
            SELECT ref_id, ref_label
            FROM entity_links
            WHERE entity_id=? AND ref_table='lei' AND method='gleif_legal_name'
            """,
            (row["id"],),
        ).fetchall()
        remove_aliases = {l["ref_id"] for l in existing_links}
        remove_aliases |= {f"LEI:{l['ref_id']}" for l in existing_links}
        remove_aliases |= {l["ref_label"] for l in existing_links}
        aliases = [
            a for a in _load_aliases(row["aliases"])
            if a not in remove_aliases
            and not a.startswith("registered_as:")
            and not a.startswith("LEI:")
            and not lei_re.match(a)
        ]
        note = re.sub(r"\s*GLEIF LEI:[^.]+\.", "", row["note"] or "")
        note = legacy_fragment_re.sub("", note).strip()
        conn.execute(
            "UPDATE entities SET aliases=?, note=? WHERE id=?",
            (json.dumps(sorted(set(aliases))), note, row["id"]),
        )
        cur = conn.execute(
            "DELETE FROM entity_links WHERE entity_id=? AND ref_table='lei' AND method='gleif_legal_name'",
            (row["id"],),
        )
        cleaned += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    return cleaned


def _upsert_gleif_source(conn: sqlite3.Connection, content: bytes) -> str:
    content_hash = rawstore.put(conn, content, url=GLEIF_URL, media_type="application/json")
    src = Source(
        url=GLEIF_URL,
        title="GLEIF LEI Records API",
        pillar_id=6,
        kind=SourceKind.primary,
        trust_score=95,
        trust_rationale=(
            "Official Global Legal Entity Identifier Foundation API; current golden-copy legal "
            "entity identifiers, names, jurisdictions, and registration statuses."
        ),
        content_hash=content_hash,
    )
    source_id = _upsert_source(conn, src)
    rawstore.put(conn, content, source_id=source_id, url=GLEIF_URL, media_type="application/json")
    return source_id


def _apply_match(conn: sqlite3.Connection, match: LeiMatch, *, source_id: str) -> None:
    row = conn.execute("SELECT aliases, note FROM entities WHERE id=?", (match.entity_id,)).fetchone()
    aliases = set(_load_aliases(row["aliases"]))
    aliases.update({match.lei, f"LEI:{match.lei}", match.legal_name})
    if match.registered_as:
        aliases.add(f"registered_as:{match.registered_as}")
    note = row["note"] or ""
    gleif_note = (
        f"GLEIF LEI:{match.lei} legal_name={match.legal_name} "
        f"jurisdiction={match.jurisdiction or 'n/a'} hq_country={match.headquarters_country or 'n/a'} "
        f"golden_copy={match.golden_copy_publish_date or 'n/a'}."
    )
    if "GLEIF LEI:" not in note:
        note = (note.rstrip() + " " + gleif_note).strip()
    else:
        note = re.sub(r"GLEIF LEI:[^.]+\\.", gleif_note, note)
    conn.execute(
        "UPDATE entities SET aliases=?, note=? WHERE id=?",
        (json.dumps(sorted(aliases)), note, match.entity_id),
    )
    conn.execute(
        """
        INSERT INTO entity_links (
            id, entity_id, ref_table, ref_id, ref_label, pillar_id, confidence,
            method, rationale, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(entity_id, ref_table, ref_id) DO UPDATE SET
            ref_label=excluded.ref_label,
            confidence=excluded.confidence,
            method=excluded.method,
            rationale=excluded.rationale
        """,
        (
            f"gleif_{match.lei}",
            match.entity_id,
            "lei",
            match.lei,
            match.legal_name,
            6,
            match.score,
            "gleif_legal_name",
            f"GLEIF active legal-name match for query '{match.query}' from official LEI record.",
            _now().isoformat(),
        ),
    )


def enrich_top_entities(
    conn: sqlite3.Connection,
    *,
    limit: int = DEFAULT_LIMIT,
    only: list[str] | None = None,
    log=print,
) -> dict[str, Any]:
    rows = _company_rows(conn, limit=limit, only=only)
    cleaned = _clean_existing_gleif(conn, rows)
    if cleaned:
        rows = _company_rows(conn, limit=limit, only=only)
    matches: list[LeiMatch] = []
    misses: list[str] = []
    raw_payloads: list[dict[str, Any]] = []
    raw_seen = 0
    for row in rows:
        queries = _usable_queries(row["canonical_name"], _load_aliases(row["aliases"]))
        match: LeiMatch | None = None
        jurisdiction = EXPECTED_GLEIF_JURISDICTION.get(row["canonical_name"])
        for query in queries[:4]:
            raw, data = _fetch(query, jurisdiction=jurisdiction)
            if raw:
                raw_seen += 1
                rawstore.put(conn, raw, url=f"{GLEIF_URL}?entity.legalName={query}", media_type="application/json")
            if data:
                raw_payloads.append({"query": query, "response": data})
                match = best_match(row, data, query=query)
                if match:
                    break
            time.sleep(REQUEST_SPACING_S)
        if match:
            matches.append(match)
            log(f"  + {row['canonical_name']}: {match.lei} {match.legal_name} ({match.score:.2f})")
        else:
            misses.append(row["canonical_name"])
            log(f"  - {row['canonical_name']}: no high-confidence active LEI match")

    source_bytes = json.dumps(
        {
            "source": "GLEIF LEI Records API",
            "fetched_at": _now().isoformat(),
            "matches": [m.__dict__ for m in matches],
            "misses": misses,
            "raw_query_count": len(raw_payloads),
            "raw_payloads": raw_payloads,
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    source_id = _upsert_gleif_source(conn, source_bytes)
    for match in matches:
        _apply_match(conn, match, source_id=source_id)
    conn.commit()
    return {
        "seen": len(rows),
        "matched": len(matches),
        "missed": len(misses),
        "raw_responses": raw_seen,
        "source_id": source_id,
        "misses": misses,
        "cleaned": cleaned,
    }
