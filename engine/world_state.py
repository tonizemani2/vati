"""Point-in-time world-state facts, snapshots, audit, and cost guards.

This module is intentionally local-first. It does not fetch data, call an LLM, or touch paid
services. It answers: "what was knowable about topic X as of date T?" from the derived SQLite
spine, with deterministic snapshot hashes and explicit leak gates.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from engine import data_offload, db, disk_guard, raw_provenance, rawstore
from engine.schemas import WorldStateFact, WorldStateSnapshot, _uid

QUERY_VERSION = "world_state_v1"
DEFAULT_FACT_LIMIT = 32
DEFAULT_ENTITY_LIMIT = 12
DEFAULT_SERIES_LIMIT = 12
DEFAULT_EDGE_LIMIT = 24
DEFAULT_RESEARCH_FACT_LIMIT = 16
DEFAULT_RESEARCH_PAPER_LIMIT = 24
DEFAULT_RESEARCH_PAPER_SCAN_ROWS = 250_000
RESEARCH_PROVIDERS = (
    "openalex",
    "openalex_citations",
    "openalex_cite_velocity",
    "openalex_bridge",
    "arxiv",
    "crossref",
    "semantic_scholar",
    "epoch_ai",
    "biorxiv",
    "pubmed",
    "europe_pmc",
)
GIB = 1024 ** 3
TIB = 1024 ** 4
BIGQUERY_DOLLARS_PER_TIB = 6.25
ATHENA_DOLLARS_PER_TB = 5.0

HEALTH_FAILURE_REVIEWS: dict[tuple[str, str], dict[str, str]] = {
    (
        "ilo",
        "ilo:EMP_DWAP_SEX_AGE_RT_A:CHN",
    ): {
        "status": "reviewed_upstream_source_limit",
        "reviewed_at": "2026-06-18",
        "evidence": "Live ILOSTAT API probe returned 2008-2019 only for the pinned China employment-to-population slice.",
        "next_action": "Keep failed for freshness; replace only with an authoritative newer source or a changed ILO endpoint.",
    },
    (
        "comtrade",
        "comtrade:2844:276",
    ): {
        "status": "reviewed_upstream_source_limit",
        "reviewed_at": "2026-06-18",
        "evidence": "Live UN Comtrade preview API returned Germany HS2844 all-partner import totals for 2019-2021 only.",
        "next_action": "Keep failed for freshness; use paid/full Comtrade or another official trade source if this cell matters.",
    },
    (
        "world_bank",
        "world_bank:NE.EXP.GNFS.CD:NGA",
    ): {
        "status": "reviewed_upstream_source_limit",
        "reviewed_at": "2026-06-18",
        "evidence": "Live World Bank Indicators API returned only one non-null Nigeria export value, for 1960.",
        "next_action": "Keep failed for freshness; swap to IMF/OECD/national accounts source if Nigeria export history is required.",
    },
    (
        "comtrade",
        "comtrade:8541:276",
    ): {
        "status": "reviewed_upstream_source_limit",
        "reviewed_at": "2026-06-18",
        "evidence": "Live UN Comtrade preview API returned Germany HS8541 all-partner import totals for 2019 only.",
        "next_action": "Keep failed for freshness; use paid/full Comtrade or another official trade source if this cell matters.",
    },
}

STOPWORDS = {
    "about", "after", "again", "before", "between", "from", "have", "into", "that",
    "their", "there", "these", "thing", "this", "those", "what", "when", "where",
    "which", "with", "world", "state",
}


class CostGuardError(RuntimeError):
    """Raised before a paid query can exceed a configured scan limit."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_date(v: date | datetime | str | None) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return str(v)[:10]


def _iso_dt(v: datetime | str | None) -> str:
    if v is None:
        return _now().isoformat()
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def _parse_date(v: date | str) -> date:
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def _tokens(text: str) -> set[str]:
    toks = {t.lower() for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.-]+", text)}
    return {t for t in toks if len(t) >= 2 and t not in STOPWORDS}


def _score_text(tokens: set[str], phrase: str, text: str) -> int:
    if not tokens:
        return 1
    hay = text.lower()
    score = sum(
        1
        for tok in tokens
        if re.search(rf"(?<![a-z0-9]){re.escape(tok)}(?![a-z0-9])", hay)
    )
    if phrase and phrase.lower() in hay:
        score += max(2, len(tokens))
    return score


def _topic_match_threshold(tokens: set[str]) -> int:
    if not tokens:
        return 1
    if len(tokens) == 1:
        return 1
    return min(2, len(tokens))


def _topic_match_ok(score: int, tokens: set[str]) -> bool:
    return score >= _topic_match_threshold(tokens)


def _like_pattern(value: str) -> str:
    escaped = (
        value.lower()
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    return f"%{escaped}%"


def _topic_prefilter_terms(topic: str, tokens: set[str]) -> list[str]:
    terms = sorted(tokens, key=lambda t: (-len(t), t))
    phrase = topic.strip().lower()
    if phrase and len(phrase) >= 3 and phrase not in terms:
        terms.insert(0, phrase)
    return terms


def _phrase_variants(topic: str) -> list[str]:
    phrase = " ".join(topic.strip().lower().split())
    if len(phrase) < 3:
        return []
    variants = {phrase, phrase.replace(" ", "-")}
    if phrase.endswith("y"):
        variants.add(phrase[:-1] + "ies")
        variants.add(phrase.replace(" ", "-")[:-1] + "ies")
    elif not phrase.endswith("s"):
        variants.add(phrase + "s")
        variants.add(phrase.replace(" ", "-") + "s")
    if " battery" in phrase:
        variants.add(phrase.replace(" battery", " batteries"))
        variants.add(phrase.replace(" ", "-").replace("-battery", "-batteries"))
    return sorted(variants, key=lambda v: (-len(v), v))


def _phrase_variant_score(topic: str, text: str) -> int:
    hay = text.lower()
    for variant in _phrase_variants(topic):
        if variant in hay:
            return max(4, len(_tokens(topic)) + 2)
    return 0


def _visible_where_sql() -> str:
    return """
        f.status = 'active'
        AND (f.published_at IS NULL OR substr(f.published_at, 1, 10) <= ?)
        AND (f.observed_at IS NULL OR substr(f.observed_at, 1, 10) <= ?)
        AND (f.event_time IS NULL OR substr(f.event_time, 1, 10) <= ?)
        AND f.ingested_at <= ?
    """


def _topic_prefilter_sql(terms: list[str]) -> tuple[str, list[str]]:
    if not terms:
        return "", []
    text_expr = """
        lower(
            COALESCE(se.canonical_name, '') || ' ' ||
            COALESCE(f.predicate, '') || ' ' ||
            COALESCE(oe.canonical_name, '') || ' ' ||
            COALESCE(f.rationale, '') || ' ' ||
            COALESCE(s.title, '')
        )
    """
    clause = " AND (" + " OR ".join(f"{text_expr} LIKE ? ESCAPE '\\'" for _ in terms) + ")"
    return clause, [_like_pattern(term) for term in terms]


def _table_count(conn: sqlite3.Connection, table: str) -> int:
    try:
        return int(conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
    except sqlite3.Error:
        return 0


def insert_fact(conn: sqlite3.Connection, fact: WorldStateFact) -> str:
    """Insert one immutable fact. Updates are represented by superseding facts, not overwrites."""

    conn.execute(
        """
        INSERT INTO world_state_facts (
            id, subject_entity_id, predicate, object_entity_id, value, unit, event_time,
            published_at, observed_at, ingested_at, source_id, content_hash, confidence,
            extractor, rationale, supersedes_fact_id, status, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            fact.id,
            fact.subject_entity_id,
            fact.predicate,
            fact.object_entity_id,
            fact.value,
            fact.unit,
            _iso_date(fact.event_time),
            _iso_date(fact.published_at),
            _iso_date(fact.observed_at),
            _iso_dt(fact.ingested_at),
            fact.source_id,
            fact.content_hash,
            fact.confidence,
            fact.extractor,
            fact.rationale,
            fact.supersedes_fact_id,
            fact.status,
            _iso_dt(fact.created_at),
        ),
    )
    return fact.id


def _stable_id(*parts: object) -> str:
    payload = "\x1f".join("" if p is None else str(p) for p in parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def backfill_observation_facts(
    conn: sqlite3.Connection,
    *,
    replace: bool = False,
    limit: int | None = None,
    provider: str | None = None,
) -> dict[str, int]:
    """Materialize current time-series observations as timestamped world-state facts.

    This is a deterministic bridge, not semantic extraction: it turns already-ingested measured
    series points into leak-gated facts. LLM/document facts can later coexist under a different
    extractor while this gives the world-state layer immediate numeric coverage.
    """

    extractor = "series_observation_v1"
    if replace:
        if provider:
            conn.execute(
                """
                DELETE FROM world_state_facts
                WHERE extractor=?
                  AND source_id IN (SELECT DISTINCT source_id FROM series WHERE provider=? AND source_id IS NOT NULL)
                """,
                (extractor, provider),
            )
        else:
            conn.execute("DELETE FROM world_state_facts WHERE extractor=?", (extractor,))
        conn.commit()

    sql = """
        SELECT o.id AS observation_id, o.series_id, o.as_of, o.event_time, o.published_at,
               o.observed_at, o.value, o.unit,
               o.created_at AS observation_created_at,
               s.label, s.metric, s.provider, s.external_id, s.source_id,
               src.trust_score, rd.content_hash AS raw_content_hash,
               (
                 SELECT el.entity_id
                 FROM entity_links el
                 WHERE el.ref_table='series' AND el.ref_id=s.id
                 ORDER BY el.confidence DESC, el.created_at ASC
                 LIMIT 1
               ) AS subject_entity_id
        FROM observations o
        JOIN series s ON s.id=o.series_id
        LEFT JOIN sources src ON src.id=s.source_id
        LEFT JOIN raw_docs rd ON rd.content_hash=src.content_hash
        WHERE 1=1
    """
    params: list[object] = []
    if provider:
        sql += " AND s.provider=?"
        params.append(provider)
    sql += """
        ORDER BY s.provider, s.external_id, o.as_of
    """
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(sql, tuple(params)).fetchall()

    before = conn.execute(
        "SELECT count(*) FROM world_state_facts WHERE extractor=?", (extractor,)
    ).fetchone()[0]
    now_s = _now().isoformat()
    written = 0
    for r in rows:
        fact_id = _stable_id(extractor, r["series_id"], r["as_of"])
        trust = r["trust_score"] if r["trust_score"] is not None else 75
        confidence = max(0.45, min(0.99, float(trust) / 100.0))
        rationale = (
            f"Time-series observation for '{r['label']}' from {r['provider']} "
            f"({r['external_id']}) on {r['as_of']}."
        )
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO world_state_facts (
                id, subject_entity_id, predicate, object_entity_id, value, unit, event_time,
                published_at, observed_at, ingested_at, source_id, content_hash, confidence,
                extractor, rationale, supersedes_fact_id, status, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                subject_entity_id=excluded.subject_entity_id,
                value=excluded.value,
                unit=excluded.unit,
                ingested_at=excluded.ingested_at,
                source_id=excluded.source_id,
                content_hash=excluded.content_hash,
                confidence=excluded.confidence,
                rationale=excluded.rationale,
                status=excluded.status
            """,
            (
                fact_id,
                r["subject_entity_id"],
                f"observed {r['metric']}",
                None,
                r["value"],
                r["unit"],
                r["event_time"] or r["as_of"],
                r["published_at"] or r["as_of"],
                r["observed_at"] or r["event_time"] or r["as_of"],
                r["observation_created_at"] or now_s,
                r["source_id"],
                r["raw_content_hash"],
                confidence,
                extractor,
                rationale,
                None,
                "active",
                now_s,
            ),
        )
        written += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    conn.commit()
    after = conn.execute(
        "SELECT count(*) FROM world_state_facts WHERE extractor=?", (extractor,)
    ).fetchone()[0]
    return {"seen": len(rows), "written": written, "inserted": written, "before": before, "after": after}


_METRIC_ENTITY_BRIDGES: dict[str, tuple[str, str, str]] = {
    "interconnection_queue_capacity": (
        "technology",
        "Grid interconnection",
        "LBNL interconnection-queue capacity is a direct state metric for the grid-interconnection bottleneck.",
    ),
}


def backfill_metric_entity_facts(
    conn: sqlite3.Connection,
    *,
    replace: bool = False,
    metric: str | None = None,
) -> dict[str, int]:
    """Bridge measured series facts onto their top technology/material entities.

    Observation backfill gives the measured fact its geographic/reporting subject, which is correct.
    Some top entities are cross-cutting technologies rather than reporting geographies, so this
    bridge adds a second deterministic fact with the technology as subject and the original linked
    subject as object/context. It uses only already-ingested series observations and source hashes.
    """

    extractor = "series_metric_entity_bridge_v1"
    bridges = {
        key: value for key, value in _METRIC_ENTITY_BRIDGES.items()
        if metric is None or key == metric
    }
    if not bridges:
        return {"seen": 0, "written": 0, "inserted": 0, "before": 0, "after": 0}
    if replace:
        if metric:
            conn.execute(
                "DELETE FROM world_state_facts WHERE extractor=? AND predicate=?",
                (extractor, f"observed {metric}"),
            )
        else:
            conn.execute("DELETE FROM world_state_facts WHERE extractor=?", (extractor,))
        conn.commit()

    before = conn.execute(
        "SELECT count(*) FROM world_state_facts WHERE extractor=?", (extractor,)
    ).fetchone()[0]
    now_s = _now().isoformat()
    seen = 0
    written = 0
    for metric_name, (target_kind, target_name, bridge_note) in bridges.items():
        target = conn.execute(
            "SELECT id FROM entities WHERE kind=? AND canonical_name=?",
            (target_kind, target_name),
        ).fetchone()
        if not target:
            continue
        rows = conn.execute(
            """
            SELECT o.id AS observation_id, o.series_id, o.as_of, o.event_time, o.published_at,
                   o.observed_at, o.value, o.unit,
                   o.created_at AS observation_created_at,
                   s.label, s.metric, s.provider, s.external_id, s.source_id,
                   src.trust_score, rd.content_hash AS raw_content_hash,
                   (
                     SELECT el.entity_id
                     FROM entity_links el
                     WHERE el.ref_table='series' AND el.ref_id=s.id
                     ORDER BY el.confidence DESC, el.created_at ASC
                     LIMIT 1
                   ) AS context_entity_id
            FROM observations o
            JOIN series s ON s.id=o.series_id
            LEFT JOIN sources src ON src.id=s.source_id
            LEFT JOIN raw_docs rd ON rd.content_hash=src.content_hash
            WHERE s.metric=?
            ORDER BY s.provider, s.external_id, o.as_of
            """,
            (metric_name,),
        ).fetchall()
        seen += len(rows)
        for r in rows:
            fact_id = _stable_id(extractor, target["id"], r["series_id"], r["as_of"])
            trust = r["trust_score"] if r["trust_score"] is not None else 75
            confidence = max(0.45, min(0.97, float(trust) / 100.0))
            rationale = (
                f"{target_name}: {bridge_note} Bridged from time-series observation '{r['label']}' "
                f"from {r['provider']} ({r['external_id']}) on {r['as_of']}."
            )
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO world_state_facts (
                    id, subject_entity_id, predicate, object_entity_id, value, unit, event_time,
                    published_at, observed_at, ingested_at, source_id, content_hash, confidence,
                    extractor, rationale, supersedes_fact_id, status, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    subject_entity_id=excluded.subject_entity_id,
                    object_entity_id=excluded.object_entity_id,
                    value=excluded.value,
                    unit=excluded.unit,
                    ingested_at=excluded.ingested_at,
                    source_id=excluded.source_id,
                    content_hash=excluded.content_hash,
                    confidence=excluded.confidence,
                    rationale=excluded.rationale,
                    status=excluded.status
                """,
                (
                    fact_id,
                    target["id"],
                    f"observed {metric_name}",
                    r["context_entity_id"],
                    r["value"],
                    r["unit"],
                    r["event_time"] or r["as_of"],
                    r["published_at"] or r["as_of"],
                    r["observed_at"] or r["event_time"] or r["as_of"],
                    r["observation_created_at"] or now_s,
                    r["source_id"],
                    r["raw_content_hash"],
                    confidence,
                    extractor,
                    rationale,
                    None,
                    "active",
                    now_s,
                ),
            )
            written += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    conn.commit()
    after = conn.execute(
        "SELECT count(*) FROM world_state_facts WHERE extractor=?", (extractor,)
    ).fetchone()[0]
    return {"seen": seen, "written": written, "inserted": written, "before": before, "after": after}


_IDENTIFIER_SOURCE_URLS: dict[str, str] = {
    "sec_ticker_alias": "https://www.sec.gov/files/company_tickers.json",
    "sec_legal_name": "https://www.sec.gov/files/company_tickers.json",
    "gleif_legal_name": "https://api.gleif.org/api/v1/lei-records",
    "companies_house_exact_search": "https://find-and-update.company-information.service.gov.uk/search/companies",
    "wikidata_exact_label": "https://www.wikidata.org/wiki/Special:EntityData",
}

_IDENTIFIER_REF_TABLES = ("ticker", "cik", "lei", "companies_house_number", "wikidata_qid")

_IDENTIFIER_PREDICATES: dict[str, str] = {
    "ticker": "has ticker",
    "cik": "has SEC CIK",
    "lei": "has LEI",
    "companies_house_number": "has Companies House number",
    "wikidata_qid": "has Wikidata QID",
}

_IDENTIFIER_LABELS: dict[str, str] = {
    "ticker": "Ticker",
    "cik": "SEC CIK",
    "lei": "LEI",
    "companies_house_number": "Companies House number",
    "wikidata_qid": "Wikidata QID",
}


def _identifier_source_url(method: str, ref_id: str) -> str:
    base = _IDENTIFIER_SOURCE_URLS[method]
    if method == "wikidata_exact_label":
        return f"{base}/{ref_id}.json"
    return base


def _ensure_identifier_entity(
    conn: sqlite3.Connection,
    *,
    ref_table: str,
    ref_id: str,
    ref_label: str,
) -> str:
    label = _IDENTIFIER_LABELS.get(ref_table, ref_table)
    canonical_name = f"{label}: {ref_id}"
    identifier_id = "identifier_" + _stable_id(ref_table, ref_id)[:24]
    aliases = sorted({ref_id, canonical_name, ref_label} - {""})
    now_s = _now().isoformat()
    conn.execute(
        """
        INSERT INTO entities (id, kind, canonical_name, domain, aliases, note, created_at)
        VALUES (?, 'identifier', ?, 'entity_identifier', ?, ?, ?)
        ON CONFLICT(kind, canonical_name) DO UPDATE SET
            aliases=excluded.aliases,
            note=excluded.note
        """,
        (
            identifier_id,
            canonical_name,
            json.dumps(aliases),
            f"Curated or official entity identifier of type {label}.",
            now_s,
        ),
    )
    row = conn.execute(
        "SELECT id FROM entities WHERE kind='identifier' AND canonical_name=?",
        (canonical_name,),
    ).fetchone()
    return str(row["id"] if row else identifier_id)


def backfill_entity_identifier_facts(
    conn: sqlite3.Connection,
    *,
    replace: bool = False,
    limit: int | None = None,
) -> dict[str, int]:
    """Materialize official company identifier links as timestamped world-state facts.

    This intentionally ignores internal series autolinks and fuzzy/proposed links. The purpose is
    to make high-confidence identifiers (ticker, CIK, LEI, Companies House number, Wikidata QID)
    available to frozen state packs with the same provenance gates as measured observations.
    """

    extractor = "entity_identifier_v1"
    if replace:
        conn.execute("DELETE FROM world_state_facts WHERE extractor=?", (extractor,))
        conn.commit()

    method_placeholders = ",".join("?" for _ in _IDENTIFIER_SOURCE_URLS)
    sql = f"""
        SELECT el.id AS link_id, el.entity_id, el.ref_table, el.ref_id, el.ref_label,
               el.confidence, el.method, el.rationale, el.created_at,
               e.canonical_name AS subject_name
        FROM entity_links el
        JOIN entities e ON e.id=el.entity_id
        WHERE el.method IN ({method_placeholders})
          AND el.ref_table IN ({",".join("?" for _ in _IDENTIFIER_REF_TABLES)})
        ORDER BY el.method, el.entity_id, el.ref_table, el.ref_id
    """
    params: list[object] = [*list(_IDENTIFIER_SOURCE_URLS), *_IDENTIFIER_REF_TABLES]
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(sql, tuple(params)).fetchall()

    needed_source_urls = sorted(
        {
            _identifier_source_url(str(row["method"]), str(row["ref_id"]))
            for row in rows
            if str(row["method"]) in _IDENTIFIER_SOURCE_URLS
        }
    )
    source_by_url: dict[str, sqlite3.Row] = {}
    if needed_source_urls:
        placeholders = ",".join("?" for _ in needed_source_urls)
        source_sql = f"""
            SELECT s.id, s.url, s.content_hash, s.trust_score, s.accessed_at,
                   rd.content_hash AS raw_content_hash
            FROM sources s
            LEFT JOIN raw_docs rd ON rd.content_hash=s.content_hash
            WHERE s.url IN ({placeholders})
        """
        source_by_url = {
            str(row["url"]): row
            for row in conn.execute(source_sql, tuple(needed_source_urls)).fetchall()
        }

    before = conn.execute(
        "SELECT count(*) FROM world_state_facts WHERE extractor=?", (extractor,)
    ).fetchone()[0]
    now_s = _now().isoformat()
    written = 0
    identifier_entities = 0
    for r in rows:
        source = source_by_url.get(_identifier_source_url(str(r["method"]), str(r["ref_id"])))
        source_id = source["id"] if source else None
        content_hash = source["raw_content_hash"] if source else None
        accessed_at = str(source["accessed_at"]) if source and source["accessed_at"] else str(r["created_at"])
        object_entity_id = _ensure_identifier_entity(
            conn,
            ref_table=str(r["ref_table"]),
            ref_id=str(r["ref_id"]),
            ref_label=str(r["ref_label"]),
        )
        identifier_entities += 1
        trust = source["trust_score"] if source and source["trust_score"] is not None else 90
        confidence = min(float(r["confidence"] or 0.9), max(0.45, min(0.99, float(trust) / 100.0)))
        predicate = _IDENTIFIER_PREDICATES.get(str(r["ref_table"]), f"has {r['ref_table']}")
        fact_id = _stable_id(extractor, r["entity_id"], r["ref_table"], r["ref_id"])
        rationale = (
            f"{r['subject_name']} {predicate} {r['ref_id']} according to official "
            f"{r['method']} evidence. {r['rationale']}"
        )
        cur = conn.execute(
            """
            INSERT INTO world_state_facts (
                id, subject_entity_id, predicate, object_entity_id, value, unit, event_time,
                published_at, observed_at, ingested_at, source_id, content_hash, confidence,
                extractor, rationale, supersedes_fact_id, status, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                subject_entity_id=excluded.subject_entity_id,
                object_entity_id=excluded.object_entity_id,
                published_at=excluded.published_at,
                observed_at=excluded.observed_at,
                ingested_at=excluded.ingested_at,
                source_id=excluded.source_id,
                content_hash=excluded.content_hash,
                confidence=excluded.confidence,
                rationale=excluded.rationale,
                status=excluded.status
            """,
            (
                fact_id,
                r["entity_id"],
                predicate,
                object_entity_id,
                None,
                str(r["ref_table"]),
                _iso_date(accessed_at),
                _iso_date(accessed_at),
                _iso_date(accessed_at),
                r["created_at"] or now_s,
                source_id,
                content_hash,
                confidence,
                extractor,
                rationale,
                None,
                "active",
                now_s,
            ),
        )
        written += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    conn.commit()
    after = conn.execute(
        "SELECT count(*) FROM world_state_facts WHERE extractor=?", (extractor,)
    ).fetchone()[0]
    return {
        "seen": len(rows),
        "written": written,
        "inserted": written,
        "identifier_entities": identifier_entities,
        "before": before,
        "after": after,
    }


_GEO_ALIASES: dict[str, list[str]] = {
    "Argentina": ["ARG", "AR"],
    "Australia": ["AUS", "AU"],
    "Brazil": ["BRA", "BR"],
    "Canada": ["CAN", "CA"],
    "Chile": ["CHL", "CL"],
    "China": ["CHN", "People's Republic of China", "PRC"],
    "Democratic Republic of the Congo": ["COD", "DRC"],
    "Egypt": ["EGY", "EG"],
    "Ethiopia": ["ETH", "ET"],
    "European Union": ["EU", "Europe", "European Union (27)", "EU27_2020"],
    "France": ["FRA", "FR"],
    "G7": ["G7"],
    "Germany": ["DEU", "DE"],
    "Hungary": ["HUN", "HU"],
    "India": ["IND", "IN"],
    "Indonesia": ["IDN", "ID"],
    "Iran": ["IRN", "IR"],
    "Italy": ["ITA", "IT"],
    "Japan": ["JPN", "JP"],
    "Mexico": ["MEX", "MX"],
    "Netherlands": ["NLD", "NL"],
    "Nigeria": ["NGA", "NG"],
    "Norway": ["NOR", "NO"],
    "Pakistan": ["PAK", "PK"],
    "Russia": ["RUS", "Russian Federation"],
    "Saudi Arabia": ["SAU", "SA"],
    "South Africa": ["ZAF", "ZA"],
    "South Korea": ["KOR", "Republic of Korea"],
    "Syria": ["SYR", "SY"],
    "Taiwan": ["TWN", "TW"],
    "Turkey": ["TUR", "TR"],
    "Ukraine": ["UKR", "UA"],
    "United Arab Emirates": ["ARE", "UAE"],
    "United Kingdom": ["GBR", "UK", "GB"],
    "United States": ["USA", "US", "America", "United States of America"],
    "Vietnam": ["VNM", "VN"],
    "World": ["WLD", "Global"],
}


def _load_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        out = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(x) for x in out if str(x).strip()] if isinstance(out, list) else []


def _ensure_geo_entities(conn: sqlite3.Connection) -> int:
    created = 0
    now_s = _now().isoformat()
    for name, aliases in _GEO_ALIASES.items():
        row = conn.execute(
            "SELECT id, aliases FROM entities WHERE kind='country_region' AND canonical_name=?",
            (name,),
        ).fetchone()
        if row:
            merged = sorted(set(_load_json_list(row["aliases"])) | set(aliases))
            conn.execute("UPDATE entities SET aliases=? WHERE id=?", (json.dumps(merged), row["id"]))
            continue
        conn.execute(
            "INSERT INTO entities (id, kind, canonical_name, domain, aliases, note, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                _stable_id("country_region", name)[:32],
                "country_region",
                name,
                "geography",
                json.dumps(aliases),
                "Auto-seeded country/region entity for global time-series reconciliation.",
                now_s,
            ),
        )
        created += 1
    conn.commit()
    return created


def _upsert_subject_entity(
    conn: sqlite3.Connection,
    *,
    kind: str,
    canonical_name: str,
    domain: str | None,
    aliases: list[str],
    note: str,
) -> str:
    row = conn.execute(
        "SELECT id, aliases FROM entities WHERE kind=? AND canonical_name=?",
        (kind, canonical_name),
    ).fetchone()
    if row:
        merged = sorted(set(_load_json_list(row["aliases"])) | {a for a in aliases if a})
        conn.execute("UPDATE entities SET aliases=?, domain=COALESCE(domain, ?), note=COALESCE(NULLIF(note,''), ?) WHERE id=?",
                     (json.dumps(merged), domain, note, row["id"]))
        return row["id"]
    eid = _stable_id(kind, canonical_name)[:32]
    conn.execute(
        "INSERT INTO entities (id, kind, canonical_name, domain, aliases, note, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (eid, kind, canonical_name, domain, json.dumps(sorted(set(aliases))), note, _now().isoformat()),
    )
    return eid


def _series_subject_spec(s: sqlite3.Row) -> dict[str, Any] | None:
    provider = str(s["provider"] or "")
    external_id = str(s["external_id"] or "")
    label = str(s["label"] or "")
    head = label.split(" — ", 1)[0].strip()

    if provider == "arxiv" and "|works_per_year" in external_id:
        cat = external_id.split("|", 1)[0]
        return {
            "kind": "research_field",
            "canonical_name": f"arXiv {cat}",
            "domain": "research",
            "aliases": [cat, label],
            "confidence": 0.96,
            "rationale": f"Exact arXiv category code '{cat}' from provider external_id.",
        }

    if provider in {"openalex_bridge", "openalex_cite_velocity"} and " — " in label:
        slug = external_id.rsplit(":", 1)[-1]
        return {
            "kind": "research_field",
            "canonical_name": head,
            "domain": "research",
            "aliases": [slug.replace("_", " "), label],
            "confidence": 0.94,
            "rationale": "Exact OpenAlex field label carried by the derived citation series.",
        }

    if provider == "polymarket" and " — " in label:
        question = label.split(" — ", 1)[1].strip()
        token = external_id.rsplit(":", 1)[-1]
        return {
            "kind": "market_question",
            "canonical_name": question,
            "domain": "prediction_market",
            "aliases": [token],
            "confidence": 0.9,
            "rationale": "Exact Polymarket market question shared by probability and volume series.",
        }

    if provider == "google_patents":
        topic = label.removesuffix(" (patents)").strip()
        return {
            "kind": "technology",
            "canonical_name": topic[:1].upper() + topic[1:],
            "domain": "patents",
            "aliases": [external_id, topic],
            "confidence": 0.88,
            "rationale": "Exact Google Patents topic query used as the series subject.",
        }

    if provider == "usgs_minerals" and label.startswith("USGS MCS "):
        material = label[len("USGS MCS "):].split(" — ", 1)[0].strip()
        return {
            "kind": "material",
            "canonical_name": material,
            "domain": "minerals",
            "aliases": [material.lower()],
            "confidence": 0.92,
            "rationale": "Exact USGS Mineral Commodity Summary material name in the series label.",
        }

    if provider == "imf":
        return {
            "kind": "commodity_index",
            "canonical_name": head,
            "domain": "commodity",
            "aliases": [external_id],
            "confidence": 0.88,
            "rationale": "Exact IMF commodity price index series label.",
        }

    if provider == "sec_edgar" and label.startswith("Aggregate "):
        return {
            "kind": "sector",
            "canonical_name": "US public companies",
            "domain": "capital",
            "aliases": ["SEC filers", "public companies"],
            "confidence": 0.82,
            "rationale": "Aggregate SEC EDGAR XBRL frame across public-company filers.",
        }
    if provider == "sec_edgar" and label.startswith("LEU revenue"):
        return {
            "kind": "company",
            "canonical_name": "Centrus Energy",
            "domain": "nuclear/enrichment",
            "aliases": ["LEU"],
            "confidence": 0.96,
            "rationale": "Exact SEC EDGAR capital feed ticker mapping: LEU is Centrus Energy.",
        }
    if provider == "sec_edgar" and label.startswith("WST revenue"):
        return {
            "kind": "company",
            "canonical_name": "West Pharmaceutical Services",
            "domain": "glp1/injection",
            "aliases": ["WST"],
            "confidence": 0.96,
            "rationale": "Exact SEC EDGAR capital feed ticker mapping: WST is West Pharmaceutical Services.",
        }

    if provider == "biorxiv":
        corpus = head.split(" preprints", 1)[0].strip()
        return {
            "kind": "research_corpus",
            "canonical_name": corpus,
            "domain": "research",
            "aliases": [external_id],
            "confidence": 0.86,
            "rationale": "Exact preprint corpus label from the bioRxiv/medRxiv API feed.",
        }

    if provider == "europe_pmc":
        if external_id.startswith("europe_pmc:paper:"):
            title = head.removeprefix("Europe PMC paper - ").strip() or head
            topic = external_id.split(":", 3)[2].replace("_", " ") if external_id.count(":") >= 3 else ""
            return {
                "kind": "paper",
                "canonical_name": title[:180],
                "domain": "research",
                "aliases": [external_id, topic],
                "confidence": 0.88,
                "rationale": "Exact Europe PMC paper metadata row from the official REST API feed.",
            }
        if label.startswith("Europe PMC - "):
            topic = label[len("Europe PMC - "):]
            topic = topic.removesuffix(" publications per first publication year").strip()
            return {
                "kind": "technology",
                "canonical_name": topic,
                "domain": "biomed",
                "aliases": [external_id, topic.lower(), "europe pmc"],
                "confidence": 0.88,
                "rationale": "Exact Europe PMC topic label used as the life-sciences publication series subject.",
            }

    if provider == "semantic_scholar" and label.startswith("Semantic Scholar S2AG - "):
        suffix = label[len("Semantic Scholar S2AG - "):].strip()
        if suffix.startswith("dataset "):
            dataset = suffix[len("dataset "):].split(" ", 1)[0].strip()
            canonical = f"Semantic Scholar S2AG {dataset} dataset"
            aliases = [external_id, dataset, f"S2AG {dataset}"]
        else:
            canonical = "Semantic Scholar Academic Graph"
            aliases = [external_id, "S2AG", "Semantic Scholar S2AG"]
        return {
            "kind": "research_dataset",
            "canonical_name": canonical,
            "domain": "research",
            "aliases": aliases,
            "confidence": 0.92,
            "rationale": "Exact Semantic Scholar S2AG release-manifest label used as the dataset series subject.",
        }

    if provider == "nih_reporter" and label.startswith("NIH RePORTER - "):
        topic = label[len("NIH RePORTER - "):]
        topic = topic.removesuffix(" awards per fiscal year").strip()
        return {
            "kind": "technology",
            "canonical_name": topic,
            "domain": "biomed",
            "aliases": [external_id, topic.lower(), "nih reporter"],
            "confidence": 0.9,
            "rationale": "Exact NIH RePORTER topic label used as the biomedical funding series subject.",
        }

    if provider == "nsf_awards" and label.startswith("NSF Awards - "):
        topic = label[len("NSF Awards - "):]
        topic = topic.removesuffix(" awards per calendar year").strip()
        return {
            "kind": "technology",
            "canonical_name": topic,
            "domain": "science_funding",
            "aliases": [external_id, topic.lower(), "nsf awards"],
            "confidence": 0.9,
            "rationale": "Exact NSF Awards topic label used as the science funding series subject.",
        }

    if provider == "nasa_gistemp" and label.startswith("NASA GISTEMP — "):
        suffix = label[len("NASA GISTEMP — "):].strip()
        if " monthly temperature anomaly" in suffix:
            region = suffix.split(" monthly temperature anomaly", 1)[0].strip()
        elif " annual temperature anomaly" in suffix:
            region = suffix.split(" annual temperature anomaly", 1)[0].strip()
        else:
            region = suffix
        canonical = f"{region} temperature anomaly"
        return {
            "kind": "climate_indicator",
            "canonical_name": canonical,
            "domain": "climate",
            "aliases": [external_id, canonical.lower(), f"{region.lower()} gistemp"],
            "confidence": 0.92,
            "rationale": "Exact NASA GISTEMP region label used as the temperature-anomaly series subject.",
        }

    if provider == "noaa_gml_greenhouse_gases" and label.startswith("NOAA GML — "):
        suffix = label[len("NOAA GML — "):].strip()
        for ending in (" monthly mean concentration", " trend concentration", " seasonally adjusted concentration"):
            suffix = suffix.removesuffix(ending)
        canonical = f"{suffix.strip()} atmospheric concentration"
        return {
            "kind": "climate_indicator",
            "canonical_name": canonical,
            "domain": "climate",
            "aliases": [external_id, canonical.lower(), suffix.lower()],
            "confidence": 0.92,
            "rationale": "Exact NOAA GML gas and region label used as the atmospheric-concentration series subject.",
        }

    if provider == "noaa_enso" and label.startswith("NOAA PSL ENSO — "):
        indicator = label[len("NOAA PSL ENSO — "):].strip()
        return {
            "kind": "climate_indicator",
            "canonical_name": indicator,
            "domain": "climate",
            "aliases": [external_id, indicator.lower(), "enso"],
            "confidence": 0.9,
            "rationale": "Exact NOAA PSL ENSO index label used as the climate-index series subject.",
        }

    if provider == "noaa_climate_indices" and label.startswith("NOAA PSL Climate Indices — "):
        indicator = label[len("NOAA PSL Climate Indices — "):].strip()
        return {
            "kind": "climate_indicator",
            "canonical_name": indicator,
            "domain": "climate",
            "aliases": [external_id, indicator.lower()],
            "confidence": 0.9,
            "rationale": "Exact NOAA PSL climate-regime index label used as the climate-index series subject.",
        }

    if provider == "noaa_nsidc_sea_ice" and label.startswith("NOAA/NSIDC Sea Ice Index — "):
        indicator = label[len("NOAA/NSIDC Sea Ice Index — "):].strip()
        return {
            "kind": "climate_indicator",
            "canonical_name": indicator,
            "domain": "climate",
            "aliases": [external_id, indicator.lower()],
            "confidence": 0.92,
            "rationale": "Exact NOAA/NSIDC Sea Ice Index label used as the polar climate series subject.",
        }

    if provider == "noaa_swpc_solar" and label.startswith("NOAA SWPC - "):
        indicator = label[len("NOAA SWPC - "):].strip()
        return {
            "kind": "space_weather_indicator",
            "canonical_name": indicator,
            "domain": "space_weather",
            "aliases": [external_id, indicator.lower(), "space weather", "solar activity"],
            "confidence": 0.92,
            "rationale": "Exact NOAA SWPC observed indicator label used as the space-weather series subject.",
        }

    if provider == "fred_financial" and label.startswith("FRED Financial Conditions - "):
        indicator = label[len("FRED Financial Conditions - "):].strip()
        return {
            "kind": "financial_indicator",
            "canonical_name": indicator,
            "domain": "financial_conditions",
            "aliases": [external_id, indicator.lower(), "fred financial conditions"],
            "confidence": 0.92,
            "rationale": "Exact FRED financial-condition series label used as the financial indicator subject.",
        }

    if provider == "ecb_fx" and label.startswith("ECB FX - "):
        indicator = label[len("ECB FX - "):].strip()
        currency = external_id.split(":", 2)[1] if external_id.startswith("ecb_fx:") else indicator.split(" ", 1)[0]
        return {
            "kind": "financial_indicator",
            "canonical_name": indicator,
            "domain": "financial_conditions",
            "aliases": [external_id, currency, indicator.lower(), "ecb fx", "euro reference rates"],
            "confidence": 0.92,
            "rationale": "Exact ECB FX reference-rate series label used as the financial indicator subject.",
        }

    if provider == "federal_register" and label.startswith("Federal Register — "):
        topic = label[len("Federal Register — "):]
        topic = topic.removesuffix(" rulemaking documents").removesuffix(" documents").strip()
        return {
            "kind": "policy",
            "canonical_name": topic,
            "domain": "policy",
            "aliases": [external_id, topic.lower()],
            "confidence": 0.9,
            "rationale": "Exact Federal Register topic label used as the policy activity series subject.",
        }

    if provider == "eonet" and label.startswith("NASA EONET — "):
        suffix = label[len("NASA EONET — "):].strip()
        if suffix.startswith("All categories"):
            topic = "NASA EONET global natural events"
        elif " event updates" in suffix:
            topic = suffix.split(" event updates", 1)[0].strip()
        elif " new events" in suffix:
            topic = suffix.split(" new events", 1)[0].strip()
        elif " current open events" in suffix:
            topic = suffix.split(" current open events", 1)[0].strip()
        else:
            topic = suffix
        return {
            "kind": "earth_event_type",
            "canonical_name": topic,
            "domain": "earth_events",
            "aliases": [external_id, topic.lower()],
            "confidence": 0.9,
            "rationale": "Exact NASA EONET event-category label used as the natural-event series subject.",
        }

    if provider == "usgs_earthquakes" and label.startswith("USGS Earthquake Hazards — "):
        return {
            "kind": "earth_event_type",
            "canonical_name": "Earthquakes",
            "domain": "earth_events",
            "aliases": [external_id, "earthquakes", "seismic events"],
            "confidence": 0.92,
            "rationale": "Exact USGS Earthquake Hazards label used as the earthquake series subject.",
        }

    if provider == "gdacs_alerts" and label.startswith("GDACS — "):
        suffix = label[len("GDACS — "):].strip()
        event_types = {
            "Earthquake": "Earthquakes",
            "Tropical cyclone": "Tropical cyclones",
            "Flood": "Floods",
            "Volcano": "Volcanoes",
            "Drought": "Droughts",
            "Wildfire": "Wildfires",
        }
        for label_head, canonical in event_types.items():
            if suffix.startswith(label_head):
                return {
                    "kind": "earth_event_type",
                    "canonical_name": canonical,
                    "domain": "earth_events",
                    "aliases": [external_id, label_head.lower(), canonical.lower()],
                    "confidence": 0.9,
                    "rationale": "Exact GDACS disaster type label used as the disaster-alert series subject.",
                }
        if suffix.startswith(("Red ", "Orange ", "Green ")):
            level = suffix.split(" ", 1)[0]
            return {
                "kind": "earth_alert_level",
                "canonical_name": f"GDACS {level} alert level",
                "domain": "earth_events",
                "aliases": [external_id, level.lower()],
                "confidence": 0.9,
                "rationale": "Exact GDACS alert-level label used as the disaster-alert series subject.",
            }
        if suffix.startswith("All ") or suffix.startswith("Current "):
            return {
                "kind": "earth_event_type",
                "canonical_name": "GDACS global disaster alerts",
                "domain": "earth_events",
                "aliases": [external_id, "gdacs disaster alerts"],
                "confidence": 0.9,
                "rationale": "Exact GDACS aggregate alert label used as the disaster-alert series subject.",
            }
        country = suffix.removesuffix(" current open disaster alerts").removesuffix(" disaster alerts").strip()
        if country:
            return {
                "kind": "country_region",
                "canonical_name": country,
                "domain": "geography",
                "aliases": [external_id, country],
                "confidence": 0.82,
                "rationale": "Exact GDACS affected-country label used as the disaster-alert series subject.",
            }

    if provider == "ofac_sdn" and label.startswith("OFAC SDN — "):
        suffix = label[len("OFAC SDN — "):].strip()
        if suffix.startswith("target country "):
            country = suffix[len("target country "):].strip()
            return {
                "kind": "country_region",
                "canonical_name": country,
                "domain": "geography",
                "aliases": [external_id, country],
                "confidence": 0.88,
                "rationale": "Exact OFAC SDN target-country label used as the sanctions series subject.",
            }
        if suffix.startswith("program "):
            program = suffix[len("program "):].strip()
            return {
                "kind": "policy",
                "canonical_name": f"OFAC {program} sanctions program",
                "domain": "sanctions",
                "aliases": [external_id, program],
                "confidence": 0.9,
                "rationale": "Exact OFAC SDN sanctions-program label used as the series subject.",
            }
        return {
            "kind": "policy",
            "canonical_name": "OFAC SDN list",
            "domain": "sanctions",
            "aliases": [external_id, suffix],
            "confidence": 0.9,
            "rationale": "Exact OFAC SDN list dimension used as the sanctions series subject.",
        }

    if provider == "eu_sanctions" and label.startswith("EU sanctions — "):
        suffix = label[len("EU sanctions — "):].strip()
        if suffix.startswith("target country "):
            country = suffix[len("target country "):].strip()
            return {
                "kind": "country_region",
                "canonical_name": country,
                "domain": "geography",
                "aliases": [external_id, country],
                "confidence": 0.88,
                "rationale": "Exact EU sanctions target-country label used as the sanctions series subject.",
            }
        if suffix.startswith("programme "):
            programme = suffix[len("programme "):].strip()
            return {
                "kind": "policy",
                "canonical_name": f"EU {programme} sanctions programme",
                "domain": "sanctions",
                "aliases": [external_id, programme],
                "confidence": 0.9,
                "rationale": "Exact EU sanctions programme label used as the series subject.",
            }
        if suffix.startswith("subject type "):
            subject_type = suffix[len("subject type "):].strip()
            return {
                "kind": "policy",
                "canonical_name": f"EU sanctions subject type {subject_type}",
                "domain": "sanctions",
                "aliases": [external_id, subject_type],
                "confidence": 0.9,
                "rationale": "Exact EU sanctions subject-type label used as the series subject.",
            }
        return {
            "kind": "policy",
            "canonical_name": "EU consolidated sanctions list",
            "domain": "sanctions",
            "aliases": [external_id, suffix],
            "confidence": 0.9,
            "rationale": "Exact EU consolidated sanctions list dimension used as the sanctions series subject.",
        }

    if provider == "clinicaltrials" and label.startswith("ClinicalTrials.gov — "):
        suffix = label[len("ClinicalTrials.gov — "):].strip()
        if " first posted studies" in suffix:
            topic = suffix.split(" first posted studies", 1)[0].strip()
        elif " current " in suffix:
            topic = suffix.split(" current ", 1)[0].strip()
        else:
            topic = suffix
        return {
            "kind": "technology",
            "canonical_name": topic,
            "domain": "clinical_trials",
            "aliases": [external_id, topic.lower()],
            "confidence": 0.9,
            "rationale": "Exact ClinicalTrials.gov topic label used as the therapeutic pipeline series subject.",
        }

    if provider == "openfda_drugsfda" and label.startswith("openFDA Drugs@FDA — "):
        suffix = label[len("openFDA Drugs@FDA — "):].strip()
        if " current " in suffix:
            topic = suffix.split(" current ", 1)[0].strip()
        elif " approved submissions" in suffix:
            topic = suffix.split(" approved submissions", 1)[0].strip()
        elif " original approvals" in suffix:
            topic = suffix.split(" original approvals", 1)[0].strip()
        else:
            topic = suffix
        return {
            "kind": "technology",
            "canonical_name": topic,
            "domain": "clinical_regulatory",
            "aliases": [external_id, topic.lower()],
            "confidence": 0.9,
            "rationale": "Exact openFDA Drugs@FDA topic label used as the approval-activity series subject.",
        }

    if provider == "land_permits_canada_iaac" and label.startswith("Canada IAAC project "):
        project = label[len("Canada IAAC project "):].split(" - ", 1)[0].strip()
        return {
            "kind": "infrastructure_project",
            "canonical_name": project,
            "domain": "land_use_policy",
            "aliases": [external_id, project],
            "confidence": 0.9,
            "rationale": "Exact Canada IAAC project title carried by the official registry feed.",
        }

    if provider == "us_permitting_dashboard" and label.startswith("US Permitting Dashboard - "):
        suffix = label[len("US Permitting Dashboard - "):].strip()
        if external_id.startswith("us_permitting_dashboard:action:"):
            project = suffix.rsplit(" - ", 1)[0].strip() if " - " in suffix else suffix
            action = suffix.rsplit(" - ", 1)[-1].removesuffix(" status").strip() if " - " in suffix else ""
            canonical = f"{project} - {action}" if action else project
            return {
                "kind": "permit_action",
                "canonical_name": canonical[:180],
                "domain": "land_use_policy",
                "aliases": [external_id, project, action],
                "confidence": 0.88,
                "rationale": "Exact U.S. Permitting Dashboard action title from the public data portal feed.",
            }
        project = suffix.removesuffix(" project status").strip()
        return {
            "kind": "infrastructure_project",
            "canonical_name": project[:180],
            "domain": "land_use_policy",
            "aliases": [external_id, project],
            "confidence": 0.9,
            "rationale": "Exact U.S. Permitting Dashboard project title from the public data portal feed.",
        }

    if provider == "blm_mining_claims" and label.startswith("BLM mining plan - "):
        suffix = label[len("BLM mining plan - "):].strip()
        name = suffix.split(" - ", 1)[0].strip()
        return {
            "kind": "mining_plan",
            "canonical_name": name[:180],
            "domain": "land_use",
            "aliases": [external_id, name],
            "confidence": 0.9,
            "rationale": "Exact BLM MLRS locatable plan title/case carried by the official ArcGIS feed.",
        }

    if provider == "blm_mining_claims" and label.startswith("BLM active mining claims - "):
        suffix = label[len("BLM active mining claims - "):].strip()
        canonical = suffix.removesuffix(" count").removesuffix(" acres").strip()
        return {
            "kind": "land_permit_aggregate",
            "canonical_name": f"BLM active mining claims - {canonical}"[:180],
            "domain": "land_use",
            "aliases": [external_id, canonical],
            "confidence": 0.86,
            "rationale": "Exact BLM MLRS mining-claim aggregate from the official ArcGIS feed.",
        }

    if provider == "australia_epbc_referrals" and label.startswith("Australia EPBC referral "):
        suffix = label[len("Australia EPBC referral "):].strip()
        parts = [part.strip() for part in suffix.split(" - ") if part.strip()]
        ref = parts[0] if parts else external_id
        project = parts[1] if len(parts) > 1 else suffix
        return {
            "kind": "environmental_referral",
            "canonical_name": project[:180],
            "domain": "land_use_policy",
            "aliases": [external_id, ref, project],
            "confidence": 0.9,
            "rationale": "Exact Australia EPBC referral project name from the official ArcGIS public dataset.",
        }

    if provider == "cordis" and label.startswith("CORDIS - "):
        topic = label[len("CORDIS - "):].strip()
        for ending in (" EC contribution", " signed projects", " project total cost"):
            topic = topic.removesuffix(ending).strip()
        return {
            "kind": "technology",
            "canonical_name": topic,
            "domain": "science_funding",
            "aliases": [external_id, topic.lower(), "cordis"],
            "confidence": 0.9,
            "rationale": "Exact CORDIS topic label used as the EU research-funding series subject.",
        }

    if provider == "usaspending_sam" and label.startswith("USAspending - "):
        topic = label[len("USAspending - "):].strip()
        for ending in (" prime award obligations", " prime awards"):
            topic = topic.removesuffix(ending).strip()
        return {
            "kind": "technology",
            "canonical_name": topic,
            "domain": "defense_procurement",
            "aliases": [external_id, topic.lower(), "usaspending", "sam.gov"],
            "confidence": 0.9,
            "rationale": "Exact USAspending/SAM topic label used as the defense-procurement series subject.",
        }

    if provider == "resourcecontracts" and label.startswith("ResourceContracts "):
        name = label[len("ResourceContracts "):].split(" - ", 1)[0].strip()
        return {
            "kind": "resource_contract",
            "canonical_name": name[:180],
            "domain": "land_use",
            "aliases": [external_id, name],
            "confidence": 0.86,
            "rationale": "Exact ResourceContracts contract title carried by the official API metadata feed.",
        }

    if provider == "miningterminal_permits" and label.startswith("MiningTerminal permit holder - "):
        suffix = label[len("MiningTerminal permit holder - "):].strip()
        holder = suffix.split(" - ", 1)[0].strip()
        return {
            "kind": "permit_holder",
            "canonical_name": holder[:180],
            "domain": "land_use",
            "aliases": [holder],
            "confidence": 0.86,
            "rationale": "Exact permit-holder name carried by the compact MiningTerminal permit snapshot.",
        }

    if provider == "miningterminal_permits" and label.startswith("MiningTerminal permit aggregate - "):
        suffix = label[len("MiningTerminal permit aggregate - "):].strip()
        canonical = suffix.removesuffix(" count").removesuffix(" area").strip()
        return {
            "kind": "land_permit_aggregate",
            "canonical_name": f"Mining permit aggregate - {canonical}"[:180],
            "domain": "land_use",
            "aliases": [canonical],
            "confidence": 0.84,
            "rationale": "Exact country/source/commodity/status aggregate from the compact MiningTerminal permit snapshot.",
        }

    if provider == "synthetic" and external_id == "control_flat":
        return {
            "kind": "synthetic_control",
            "canonical_name": "Synthetic flat control",
            "domain": "quality_control",
            "aliases": [external_id, label],
            "confidence": 1.0,
            "rationale": "Internal synthetic control series explicitly separated from real-world entities.",
        }

    exact_subjects = {
        "gdelt": ("event_theme", head, "news", 0.82),
        "lbnl": ("infrastructure", head, "grid", 0.86),
        "oecd": ("macro_region", head, "macro", 0.84),
        "usaspending": ("defense_supply", head, "industrial_base", 0.84),
    }
    if provider in exact_subjects:
        kind, name, domain, confidence = exact_subjects[provider]
        return {
            "kind": kind,
            "canonical_name": name,
            "domain": domain,
            "aliases": [external_id],
            "confidence": confidence,
            "rationale": f"Exact {provider} series subject label.",
        }
    return None


def _bounded_term(text: str, term: str) -> bool:
    if not term.strip():
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None


def _bounded_upper(text: str, term: str) -> bool:
    pattern = rf"(?<![A-Z0-9]){re.escape(term.upper())}(?![A-Z0-9])"
    return re.search(pattern, text.upper()) is not None


_PREFER_EXACT_SERIES_SUBJECT_PROVIDERS = {
    "arxiv",
    "australia_epbc_referrals",
    "biorxiv",
    "blm_mining_claims",
    "clinicaltrials",
    "cordis",
    "eonet",
    "ecb_fx",
    "eu_sanctions",
    "federal_register",
    "fred_financial",
    "gdacs_alerts",
    "google_patents",
    "imf",
    "land_permits_canada_iaac",
    "miningterminal_permits",
    "nasa_gistemp",
    "nih_reporter",
    "nsf_awards",
    "noaa_gml_greenhouse_gases",
    "noaa_enso",
    "noaa_climate_indices",
    "noaa_nsidc_sea_ice",
    "noaa_swpc_solar",
    "ofac_sdn",
    "openfda_drugsfda",
    "openalex_bridge",
    "openalex_cite_velocity",
    "polymarket",
    "sec_edgar",
    "semantic_scholar",
    "synthetic",
    "us_permitting_dashboard",
    "usaspending_sam",
    "usgs_earthquakes",
    "usgs_minerals",
    "resourcecontracts",
}


def autolink_series_entities(
    conn: sqlite3.Connection,
    *,
    only_unlinked: bool = True,
    limit: int | None = None,
) -> dict[str, int]:
    """Conservatively link series rows to already-known global entities.

    The matcher uses exact aliases/canonical names and explicit ISO/ticker-like surfaces. It is meant
    to improve obvious global coverage, not to solve fuzzy entity resolution.
    """

    geo_created = _ensure_geo_entities(conn)
    entities = conn.execute(
        """
        SELECT id, kind, canonical_name, aliases
        FROM entities
        WHERE kind IN ('country_region','company','technology','material','component','policy','infrastructure')
        """
    ).fetchall()

    candidates: list[dict[str, Any]] = []
    for e in entities:
        terms = [e["canonical_name"], *_load_json_list(e["aliases"])]
        candidates.append({"id": e["id"], "kind": e["kind"], "name": e["canonical_name"], "terms": terms})

    sql = "SELECT id, pillar_id, provider, external_id, label FROM series"
    if only_unlinked:
        sql += " WHERE NOT EXISTS (SELECT 1 FROM entity_links el WHERE el.ref_table='series' AND el.ref_id=series.id)"
    sql += " ORDER BY provider, label"
    params: tuple[object, ...] = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (limit,)
    rows = conn.execute(sql, params).fetchall()

    inserted = 0
    matched = 0
    now_s = _now().isoformat()
    for s in rows:
        text = f"{s['label']} {s['external_id']}"
        spec = _series_subject_spec(s)
        best: tuple[float, dict[str, Any], str] | None = None
        prefer_spec = spec is not None and str(s["provider"]) in _PREFER_EXACT_SERIES_SUBJECT_PROVIDERS
        if not prefer_spec:
            for e in candidates:
                for term in e["terms"]:
                    t = str(term).strip()
                    if not t:
                        continue
                    score = 0.0
                    if e["kind"] == "country_region" and 2 <= len(t) <= 3 and t.isupper():
                        if _bounded_upper(text, t):
                            score = 0.97
                    elif e["kind"] == "company" and len(t) >= 2 and t.upper() == t:
                        if _bounded_upper(text, t):
                            score = 0.94
                    elif len(t) >= 4 and _bounded_term(text, t):
                        score = 0.9 if e["kind"] == "country_region" else 0.88
                    if score and (best is None or score > best[0]):
                        best = (score, e, t)
        if best is None and spec is not None:
            entity_id = _upsert_subject_entity(
                conn,
                kind=spec["kind"],
                canonical_name=spec["canonical_name"],
                domain=spec["domain"],
                aliases=spec["aliases"],
                note=f"Auto-created exact subject entity for {s['provider']} series reconciliation.",
            )
            e = {"id": entity_id, "name": spec["canonical_name"]}
            confidence = spec["confidence"]
            rationale = spec["rationale"]
            conn.execute(
                """
                DELETE FROM entity_links
                WHERE ref_table='series' AND ref_id=? AND method='auto_exact' AND entity_id<>?
                """,
                (s["id"], entity_id),
            )
        elif best is None:
            continue
        else:
            confidence, e, term = best
            rationale = f"Exact surface match '{term}' in series label/external id for {e['name']}."
        matched += 1
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
                _stable_id("entity_link", e["id"], "series", s["id"])[:32],
                e["id"],
                "series",
                s["id"],
                s["label"],
                s["pillar_id"],
                confidence,
                "auto_exact",
                rationale,
                now_s,
            ),
        )
        inserted += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    conn.commit()
    remaining_unlinked = conn.execute(
        """
        SELECT count(*)
        FROM series s
        WHERE NOT EXISTS (
            SELECT 1 FROM entity_links el WHERE el.ref_table='series' AND el.ref_id=s.id
        )
        """
    ).fetchone()[0]
    return {
        "series_seen": len(rows),
        "matched": matched,
        "links_written": inserted,
        "geo_entities_created": geo_created,
        "remaining_unlinked_series": remaining_unlinked,
    }


def _visible_candidate_rows(
    conn: sqlite3.Connection,
    as_of: date,
    snapshot_created_at: datetime,
    *,
    topic: str = "",
    topic_tokens: set[str] | None = None,
    include_superseded: bool = False,
) -> tuple[list[sqlite3.Row], int]:
    as_of_s = as_of.isoformat()
    created_s = snapshot_created_at.isoformat()
    terms = _topic_prefilter_terms(topic, topic_tokens or set())
    prefilter_sql, prefilter_params = _topic_prefilter_sql(terms)
    rows = conn.execute(
        f"""
        SELECT f.*,
               se.canonical_name AS subject_name,
               oe.canonical_name AS object_name,
               s.title AS source_title,
               s.url AS source_url,
               s.kind AS source_kind,
               s.trust_score AS source_trust
        FROM world_state_facts f
        LEFT JOIN entities se ON se.id = f.subject_entity_id
        LEFT JOIN entities oe ON oe.id = f.object_entity_id
        LEFT JOIN sources s ON s.id = f.source_id
        WHERE {_visible_where_sql()}
        {prefilter_sql}
        """,
        (as_of_s, as_of_s, as_of_s, created_s, *prefilter_params),
    ).fetchall()
    if include_superseded:
        return rows, 0
    superseded = {r["supersedes_fact_id"] for r in rows if r["supersedes_fact_id"]}
    if not superseded:
        return rows, 0
    return [r for r in rows if r["id"] not in superseded], len(superseded)


def visible_facts(
    conn: sqlite3.Connection,
    topic: str,
    as_of: date | str,
    *,
    snapshot_created_at: datetime | None = None,
    limit: int = DEFAULT_FACT_LIMIT,
    include_superseded: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target = _parse_date(as_of)
    created_at = snapshot_created_at or _now()
    toks = _tokens(topic)
    rows, superseded_count = _visible_candidate_rows(
        conn,
        target,
        created_at,
        topic=topic,
        topic_tokens=toks,
        include_superseded=include_superseded,
    )
    ranked: list[tuple[int, dict[str, Any]]] = []
    for r in rows:
        d = dict(r)
        text = " ".join(
            str(d.get(k) or "")
            for k in ("subject_name", "predicate", "object_name", "rationale", "source_title")
        )
        score = _score_text(toks, topic, text)
        if not _topic_match_ok(score, toks):
            continue
        d["match_score"] = score
        ranked.append((score, d))
    ranked.sort(
        key=lambda x: (
            x[0],
            float(x[1].get("confidence") or 0),
            str(x[1].get("published_at") or ""),
            str(x[1].get("id") or ""),
        ),
        reverse=True,
    )
    exclusions = _exclusion_counts(conn, target, created_at)
    exclusions["superseded"] = superseded_count
    exclusions["low_topic_match"] = max(0, len(rows) - len(ranked))
    return [d for _, d in ranked[:limit]], exclusions


def snapshot_hash(topic: str, as_of: date | str, facts: list[dict[str, Any]]) -> str:
    """Stable hash over the manifest, excluding wall-clock row metadata."""

    target = _parse_date(as_of)
    manifest = {
        "query_version": QUERY_VERSION,
        "topic": topic.strip().lower(),
        "as_of": target.isoformat(),
        "facts": [
            {
                "id": f.get("id"),
                "subject_entity_id": f.get("subject_entity_id"),
                "predicate": f.get("predicate"),
                "object_entity_id": f.get("object_entity_id"),
                "value": f.get("value"),
                "unit": f.get("unit"),
                "event_time": _iso_date(f.get("event_time")),
                "published_at": _iso_date(f.get("published_at")),
                "observed_at": _iso_date(f.get("observed_at")),
                "ingested_at": f.get("ingested_at"),
                "source_id": f.get("source_id"),
                "content_hash": f.get("content_hash"),
                "confidence": f.get("confidence"),
                "extractor": f.get("extractor"),
                "supersedes_fact_id": f.get("supersedes_fact_id"),
                "status": f.get("status"),
            }
            for f in sorted(facts, key=lambda r: str(r.get("id") or ""))
        ],
    }
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def record_snapshot(
    conn: sqlite3.Connection,
    topic: str,
    as_of: date | str,
    facts: list[dict[str, Any]],
    *,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    target = _parse_date(as_of)
    created = created_at or _now()
    h = snapshot_hash(topic, target, facts)
    source_count = len({f.get("source_id") for f in facts if f.get("source_id")})
    snap = WorldStateSnapshot(
        topic=topic.strip(),
        as_of=target,
        created_at=created,
        query_version=QUERY_VERSION,
        fact_count=len(facts),
        source_count=source_count,
        snapshot_hash=h,
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO world_state_snapshots (
            id, topic, as_of, created_at, query_version, fact_count, source_count, snapshot_hash
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            snap.id,
            snap.topic,
            snap.as_of.isoformat(),
            snap.created_at.isoformat(),
            snap.query_version,
            snap.fact_count,
            snap.source_count,
            snap.snapshot_hash,
        ),
    )
    return snap.model_dump(mode="json")


def _match_entities(conn: sqlite3.Connection, topic: str, limit: int = DEFAULT_ENTITY_LIMIT) -> list[dict[str, Any]]:
    toks = _tokens(topic)
    try:
        rows = conn.execute(
            "SELECT id, kind, canonical_name, domain, aliases, note FROM entities ORDER BY canonical_name"
        ).fetchall()
    except sqlite3.Error:
        return []
    ranked: list[tuple[int, dict[str, Any]]] = []
    for r in rows:
        d = dict(r)
        score = _score_text(toks, topic, f"{d['canonical_name']} {d.get('aliases') or ''} {d.get('note') or ''}")
        if score > 0:
            d["match_score"] = score
            ranked.append((score, d))
    ranked.sort(key=lambda x: (x[0], x[1]["canonical_name"]), reverse=True)
    return [d for _, d in ranked[:limit]]


def _series_summaries(conn: sqlite3.Connection, topic: str, limit: int = DEFAULT_SERIES_LIMIT) -> list[dict[str, Any]]:
    toks = _tokens(topic)
    try:
        rows = conn.execute(
            """
            SELECT id, provider, external_id, label, metric, unit, domain,
                   COALESCE(n_obs, 0) AS n_obs, first_as_of, last_as_of, first_val, last_val,
                   last_fired, last_surprise_sigma, last_fdr_survive, spark
            FROM series
            ORDER BY COALESCE(last_fired, 0) DESC, COALESCE(n_obs, 0) DESC
            """
        ).fetchall()
    except sqlite3.Error:
        return []
    ranked: list[tuple[int, dict[str, Any]]] = []
    for r in rows:
        d = dict(r)
        text = " ".join(str(d.get(k) or "") for k in ("label", "provider", "external_id", "metric", "domain"))
        score = _score_text(toks, topic, text)
        if score > 0:
            d["match_score"] = score
            ranked.append((score, d))
    ranked.sort(key=lambda x: (x[0], int(x[1].get("n_obs") or 0)), reverse=True)
    return [d for _, d in ranked[:limit]]


def _entity_edges(conn: sqlite3.Connection, entity_ids: set[str], limit: int = DEFAULT_EDGE_LIMIT) -> list[dict[str, Any]]:
    if not entity_ids:
        return []
    placeholders = ",".join("?" for _ in entity_ids)
    try:
        rows = conn.execute(
            f"""
            SELECT ee.id, ee.src_entity, ee.dst_entity, ee.rel, ee.confidence, ee.rationale,
                   s.canonical_name AS src_name, d.canonical_name AS dst_name,
                   src.title AS source_title, src.url AS source_url
            FROM entity_edges ee
            LEFT JOIN entities s ON s.id = ee.src_entity
            LEFT JOIN entities d ON d.id = ee.dst_entity
            LEFT JOIN sources src ON src.id = ee.source_id
            WHERE ee.src_entity IN ({placeholders}) OR ee.dst_entity IN ({placeholders})
            ORDER BY ee.confidence DESC
            LIMIT ?
            """,
            (*entity_ids, *entity_ids, limit),
        ).fetchall()
    except sqlite3.Error:
        return []
    return [dict(r) for r in rows]


def _raw_doc_location_for_hash(
    conn: sqlite3.Connection,
    content_hash: str | None,
    cache: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    key = str(content_hash or "")
    if cache is not None and key in cache:
        return dict(cache[key])
    if not content_hash:
        out = {
            "raw_doc_status": "missing_hash",
            "raw_doc_local": False,
            "raw_doc_local_path": None,
            "raw_doc_remote_uri": None,
            "raw_doc_byte_len": None,
        }
        if cache is not None:
            cache[key] = dict(out)
        return out
    try:
        loc = rawstore.locate(conn, str(content_hash))
    except (sqlite3.Error, data_offload.DataOffloadError):
        out = {
            "raw_doc_status": "location_error",
            "raw_doc_local": False,
            "raw_doc_local_path": None,
            "raw_doc_remote_uri": None,
            "raw_doc_byte_len": None,
        }
        if cache is not None:
            cache[key] = dict(out)
        return out
    out = {
        "raw_doc_status": loc.get("status"),
        "raw_doc_local": bool(loc.get("exists_local")),
        "raw_doc_local_path": loc.get("local_path"),
        "raw_doc_remote_uri": loc.get("remote_uri"),
        "raw_doc_byte_len": loc.get("byte_len"),
    }
    if cache is not None:
        cache[key] = dict(out)
    return out


def _source_citations(
    conn: sqlite3.Connection,
    facts: list[dict[str, Any]],
    raw_location_cache: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    citations: dict[str, dict[str, Any]] = {}
    for f in facts:
        sid = f.get("source_id")
        if not sid:
            continue
        if str(sid) in citations:
            continue
        content_hash = f.get("content_hash")
        citations[str(sid)] = {
            "id": sid,
            "title": f.get("source_title"),
            "url": f.get("source_url"),
            "kind": f.get("source_kind"),
            "trust_score": f.get("source_trust"),
            "content_hash": content_hash,
            **_raw_doc_location_for_hash(
                conn,
                str(content_hash) if content_hash else None,
                raw_location_cache,
            ),
        }
    return list(citations.values())


def _fact_payload(
    conn: sqlite3.Connection,
    f: dict[str, Any],
    raw_location_cache: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    content_hash = f.get("content_hash")
    return {
        "id": f.get("id"),
        "subject_entity_id": f.get("subject_entity_id"),
        "subject": f.get("subject_name"),
        "predicate": f.get("predicate"),
        "object_entity_id": f.get("object_entity_id"),
        "object": f.get("object_name"),
        "value": f.get("value"),
        "unit": f.get("unit"),
        "event_time": _iso_date(f.get("event_time")),
        "published_at": _iso_date(f.get("published_at")),
        "observed_at": _iso_date(f.get("observed_at")),
        "ingested_at": f.get("ingested_at"),
        "confidence": f.get("confidence"),
        "extractor": f.get("extractor"),
        "rationale": f.get("rationale"),
        "source_id": f.get("source_id"),
        "content_hash": content_hash,
        **_raw_doc_location_for_hash(
            conn,
            str(content_hash) if content_hash else None,
            raw_location_cache,
        ),
        "match_score": f.get("match_score", 0),
    }


def _diverse_facts(facts: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if len(facts) <= limit:
        return facts
    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def add(fact: dict[str, Any]) -> bool:
        if len(selected) >= limit:
            return False
        fact_id = str(fact.get("id") or "")
        if fact_id and fact_id in seen_ids:
            return False
        selected.append(fact)
        if fact_id:
            seen_ids.add(fact_id)
        return True

    for key in ("predicate", "source_id"):
        seen_keys: set[str] = set()
        for fact in facts:
            value = str(fact.get(key) or "")
            if not value or value in seen_keys:
                continue
            if add(fact):
                seen_keys.add(value)
            if len(selected) >= limit:
                return selected
    for fact in facts:
        add(fact)
        if len(selected) >= limit:
            return selected
    return selected


def _snapshot_manifest(
    topic: str,
    target: date,
    facts: list[dict[str, Any]],
    *,
    created_at: datetime,
) -> dict[str, Any]:
    return {
        "topic": topic.strip(),
        "as_of": target.isoformat(),
        "created_at": created_at.isoformat(),
        "query_version": QUERY_VERSION,
        "fact_count": len(facts),
        "source_count": len({f.get("source_id") for f in facts if f.get("source_id")}),
        "snapshot_hash": snapshot_hash(topic, target, facts),
    }


def _select_visible_fact_set(
    conn: sqlite3.Connection,
    topic: str,
    target: date,
    *,
    created_at: datetime,
    limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidate_limit = max(limit, min(1000, max(limit * 10, limit + 100)))
    candidate_facts, exclusions = visible_facts(
        conn,
        topic,
        target,
        snapshot_created_at=created_at,
        limit=candidate_limit,
    )
    return _diverse_facts(candidate_facts, limit), exclusions


def _research_source_ids(conn: sqlite3.Connection) -> set[str]:
    placeholders = ",".join("?" for _ in RESEARCH_PROVIDERS)
    try:
        rows = conn.execute(
            f"""
            SELECT DISTINCT source_id
            FROM series
            WHERE provider IN ({placeholders})
              AND source_id IS NOT NULL
              AND length(source_id)>0
            """,
            list(RESEARCH_PROVIDERS),
        ).fetchall()
    except sqlite3.Error:
        return set()
    return {str(row["source_id"]) for row in rows if row["source_id"]}


def _select_visible_research_facts(
    conn: sqlite3.Connection,
    topic: str,
    target: date,
    *,
    created_at: datetime,
    limit: int,
    count_exclusions: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    source_ids = _research_source_ids(conn)
    if not source_ids:
        return [], {"research_sources_missing": 1}
    toks = _tokens(topic)
    rows, superseded_count = _visible_candidate_rows(
        conn,
        target,
        created_at,
        topic=topic,
        topic_tokens=toks,
    )
    ranked: list[tuple[int, dict[str, Any]]] = []
    skipped_non_research = 0
    for r in rows:
        d = dict(r)
        if str(d.get("source_id") or "") not in source_ids:
            skipped_non_research += 1
            continue
        text = " ".join(
            str(d.get(k) or "")
            for k in ("subject_name", "predicate", "object_name", "rationale", "source_title")
        )
        score = _score_text(toks, topic, text)
        if not _topic_match_ok(score, toks):
            continue
        d["match_score"] = score
        ranked.append((score, d))
    ranked.sort(
        key=lambda x: (
            x[0],
            float(x[1].get("confidence") or 0),
            str(x[1].get("published_at") or ""),
            str(x[1].get("id") or ""),
        ),
        reverse=True,
    )
    if count_exclusions:
        exclusions = _exclusion_counts(conn, target, created_at)
    else:
        exclusions = {
            "future_published": "not_counted",
            "future_observed": "not_counted",
            "future_event": "not_counted",
            "future_ingested": "not_counted",
        }
    exclusions["superseded"] = superseded_count
    exclusions["non_research_fact_matches"] = skipped_non_research
    exclusions["low_topic_match_research_facts"] = max(0, len(rows) - skipped_non_research - len(ranked))
    return _diverse_facts([d for _, d in ranked], limit), exclusions


def _paper_text_expr(*, search_abstracts: bool) -> str:
    abstract = "COALESCE(p.abstract, '') || ' ' ||" if search_abstracts else ""
    return f"""
        lower(
            COALESCE(p.title, '') || ' ' ||
            {abstract}
            COALESCE(p.authors, '') || ' ' ||
            COALESCE(p.external_id, '')
        )
    """


def _paper_prefilter_sql(terms: list[str], *, search_abstracts: bool = False) -> tuple[str, list[str]]:
    if not terms:
        return "", []
    text_expr = _paper_text_expr(search_abstracts=search_abstracts)
    clause = " AND (" + " OR ".join(f"{text_expr} LIKE ? ESCAPE '\\'" for _ in terms) + ")"
    return clause, [_like_pattern(term) for term in terms]


def _paper_phrase_sql(topic: str, *, search_abstracts: bool = False) -> tuple[str, list[str]]:
    variants = _phrase_variants(topic)
    if not variants:
        return "", []
    text_expr = _paper_text_expr(search_abstracts=search_abstracts)
    clause = " AND (" + " OR ".join(f"{text_expr} LIKE ? ESCAPE '\\'" for _ in variants) + ")"
    return clause, [_like_pattern(variant) for variant in variants]


def _paper_payload(row: dict[str, Any], *, abstract_chars: int = 900) -> dict[str, Any]:
    abstract = str(row.get("abstract") or "").strip()
    if abstract_chars > 0 and len(abstract) > abstract_chars:
        abstract = abstract[:abstract_chars].rstrip() + "..."
    return {
        "id": row.get("id"),
        "provider": row.get("provider"),
        "external_id": row.get("external_id"),
        "published": _iso_date(row.get("published")),
        "updated": _iso_date(row.get("updated")),
        "primary_category": row.get("primary_category"),
        "categories": row.get("categories"),
        "title": row.get("title"),
        "abstract": abstract,
        "authors": row.get("authors"),
        "n_authors": int(row.get("n_authors") or 0),
        "content_hash": row.get("content_hash"),
        "fetched_at": row.get("fetched_at"),
        "match_score": int(row.get("match_score") or 0),
        "phrase_match": bool(row.get("phrase_match")),
    }


def _hydrate_paper_abstracts(conn: sqlite3.Connection, papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = [str(p.get("id") or "") for p in papers if p.get("id")]
    if not ids:
        return papers
    placeholders = ",".join("?" for _ in ids)
    try:
        rows = conn.execute(f"SELECT id, abstract FROM papers WHERE id IN ({placeholders})", ids).fetchall()
    except sqlite3.Error:
        return papers
    abstracts = {str(row["id"]): str(row["abstract"] or "") for row in rows}
    out: list[dict[str, Any]] = []
    for paper in papers:
        row = dict(paper)
        abstract = abstracts.get(str(row.get("id") or ""))
        if abstract is not None:
            abstract = abstract.strip()
            row["abstract"] = abstract[:900].rstrip() + "..." if len(abstract) > 900 else abstract
        out.append(row)
    return out


def _paper_candidate_select_sql(*, include_abstract: bool) -> str:
    abstract_col = "p.abstract" if include_abstract else "'' AS abstract"
    return f"""
        SELECT p.id, p.provider, p.external_id, p.published, p.updated,
               p.primary_category, p.categories, p.title, {abstract_col},
               p.authors, p.n_authors, p.content_hash, p.fetched_at
        FROM papers p
    """


def _visible_research_papers(
    conn: sqlite3.Connection,
    topic: str,
    target: date,
    *,
    created_at: datetime,
    limit: int,
    search_abstracts: bool = False,
    fill_token_fallback: bool = False,
    full_scan: bool = False,
    scan_rows: int = DEFAULT_RESEARCH_PAPER_SCAN_ROWS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    toks = _tokens(topic)
    terms = _topic_prefilter_terms(topic, toks)
    prefilter_sql, prefilter_params = _paper_prefilter_sql(terms, search_abstracts=search_abstracts)
    phrase_sql, phrase_params = _paper_phrase_sql(topic, search_abstracts=search_abstracts)
    target_s = target.isoformat()
    created_s = created_at.isoformat()
    candidate_limit = max(limit, min(1000, max(limit * 25, limit + 200)))
    bounded_limit = max(limit, min(max(int(scan_rows or 0), limit), 250_000))
    try:
        phrase_rows: list[sqlite3.Row] = []
        token_rows: list[sqlite3.Row] = []
        if full_scan and phrase_sql:
            phrase_rows = conn.execute(
                f"""
                {_paper_candidate_select_sql(include_abstract=search_abstracts)}
                WHERE substr(p.published,1,10) <= ?
                  AND (p.fetched_at IS NULL OR p.fetched_at <= ?)
                  {phrase_sql}
                ORDER BY p.published DESC, COALESCE(p.updated, '') DESC, p.id
                LIMIT ?
                """,
                (target_s, created_s, *phrase_params, candidate_limit),
            ).fetchall()
        if full_scan and (not phrase_rows or (fill_token_fallback and len(phrase_rows) < limit)):
            token_rows = conn.execute(
                f"""
                {_paper_candidate_select_sql(include_abstract=search_abstracts)}
                WHERE substr(p.published,1,10) <= ?
                  AND (p.fetched_at IS NULL OR p.fetched_at <= ?)
                  {prefilter_sql}
                ORDER BY p.published DESC, COALESCE(p.updated, '') DESC, p.id
                LIMIT ?
                """,
                (target_s, created_s, *prefilter_params, candidate_limit),
            ).fetchall()
        if not full_scan:
            token_rows = conn.execute(
                f"""
                {_paper_candidate_select_sql(include_abstract=search_abstracts)}
                WHERE p.published <= ?
                  AND (p.fetched_at IS NULL OR p.fetched_at <= ?)
                ORDER BY p.published DESC, COALESCE(p.updated, '') DESC, p.id
                LIMIT ?
                """,
                (target_s, created_s, bounded_limit),
            ).fetchall()
    except sqlite3.Error:
        return [], {"paper_query_error": 1}

    rows_by_id: dict[str, sqlite3.Row] = {}
    for row in [*phrase_rows, *token_rows]:
        rows_by_id.setdefault(str(row["id"]), row)
    rows = list(rows_by_id.values())
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    low_topic = 0
    for r in rows:
        d = dict(r)
        text = " ".join(
            str(d.get(k) or "")
            for k in (("title", "abstract", "authors", "external_id") if search_abstracts else ("title", "authors", "external_id"))
        )
        phrase_score = _phrase_variant_score(topic, text)
        score = max(_score_text(toks, topic, text), phrase_score)
        if not _topic_match_ok(score, toks):
            low_topic += 1
            continue
        d["match_score"] = score
        d["phrase_match"] = bool(phrase_score)
        ranked.append((score, str(d.get("published") or ""), d))
    ranked.sort(key=lambda x: (x[0], x[1], str(x[2].get("id") or "")), reverse=True)
    papers = _hydrate_paper_abstracts(conn, [_paper_payload(d) for _, _, d in ranked[:limit]])
    return papers, {
        "low_topic_match_papers": low_topic,
        "paper_candidates_scanned": len(rows),
        "paper_phrase_candidates": len(phrase_rows),
        "paper_token_fallback_scanned": len(token_rows),
        "paper_candidates_ranked": len(ranked),
        "paper_abstract_search": bool(search_abstracts),
        "paper_fill_token_fallback": bool(fill_token_fallback),
        "paper_full_scan": bool(full_scan),
        "paper_scan_rows": bounded_limit if not full_scan else None,
    }


def _paper_exclusion_counts(
    conn: sqlite3.Connection,
    topic: str,
    target: date,
    *,
    created_at: datetime,
    search_abstracts: bool = False,
) -> dict[str, int]:
    toks = _tokens(topic)
    terms = _topic_prefilter_terms(topic, toks)
    prefilter_sql, prefilter_params = _paper_prefilter_sql(terms, search_abstracts=search_abstracts)
    target_s = target.isoformat()
    created_s = created_at.isoformat()
    try:
        future_published = conn.execute(
            f"""
            SELECT count(*)
            FROM papers p
            WHERE substr(p.published,1,10) > ?
              {prefilter_sql}
            """,
            (target_s, *prefilter_params),
        ).fetchone()[0]
        future_fetched = conn.execute(
            f"""
            SELECT count(*)
            FROM papers p
            WHERE p.fetched_at IS NOT NULL
              AND p.fetched_at > ?
              {prefilter_sql}
            """,
            (created_s, *prefilter_params),
        ).fetchone()[0]
    except sqlite3.Error:
        return {"paper_exclusion_query_error": 1}
    return {
        "future_published_papers": int(future_published or 0),
        "future_fetched_papers": int(future_fetched or 0),
    }


def _research_summaries(papers: list[dict[str, Any]], facts: list[dict[str, Any]]) -> dict[str, Any]:
    by_provider = Counter(str(p.get("provider") or "unknown") for p in papers)
    by_category = Counter(
        str(p.get("primary_category") or "unknown")
        for p in papers
    )
    by_year = Counter(
        str(p.get("published") or "")[:4]
        for p in papers
        if p.get("published")
    )
    fact_predicates = Counter(str(f.get("predicate") or "unknown") for f in facts)
    return {
        "papers_by_provider": dict(sorted(by_provider.items())),
        "papers_by_primary_category": dict(by_category.most_common(12)),
        "papers_by_year": dict(sorted(by_year.items())),
        "fact_predicates": dict(fact_predicates.most_common(12)),
    }


def _research_snapshot_hash(
    topic: str,
    target: date,
    facts: list[dict[str, Any]],
    papers: list[dict[str, Any]],
) -> str:
    manifest = {
        "query_version": f"{QUERY_VERSION}_research",
        "topic": topic.strip().lower(),
        "as_of": target.isoformat(),
        "facts": [
            {
                "id": f.get("id"),
                "source_id": f.get("source_id"),
                "published_at": _iso_date(f.get("published_at")),
                "observed_at": _iso_date(f.get("observed_at")),
                "event_time": _iso_date(f.get("event_time")),
                "ingested_at": f.get("ingested_at"),
                "content_hash": f.get("content_hash"),
            }
            for f in sorted(facts, key=lambda r: str(r.get("id") or ""))
        ],
        "papers": [
            {
                "id": p.get("id"),
                "provider": p.get("provider"),
                "external_id": p.get("external_id"),
                "published": _iso_date(p.get("published")),
                "content_hash": p.get("content_hash"),
            }
            for p in sorted(papers, key=lambda r: str(r.get("id") or ""))
        ],
    }
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def research_pack(
    topic: str,
    as_of: date | str,
    *,
    conn: sqlite3.Connection | None = None,
    paper_limit: int = DEFAULT_RESEARCH_PAPER_LIMIT,
    fact_limit: int = DEFAULT_RESEARCH_FACT_LIMIT,
    count_fact_exclusions: bool = False,
    count_paper_exclusions: bool = False,
    search_abstracts: bool = False,
    fill_token_fallback: bool = False,
    full_paper_scan: bool = False,
    paper_scan_rows: int = DEFAULT_RESEARCH_PAPER_SCAN_ROWS,
) -> dict[str, Any]:
    """Return a read-only, point-in-time research context pack from local data."""

    owns_conn = conn is None
    if conn is None:
        conn = db.connect()
        db.init_db(conn)
    target = _parse_date(as_of)
    created_at = _now()
    facts, fact_exclusions = _select_visible_research_facts(
        conn,
        topic,
        target,
        created_at=created_at,
        limit=fact_limit,
        count_exclusions=count_fact_exclusions,
    )
    papers, paper_exclusions = _visible_research_papers(
        conn,
        topic,
        target,
        created_at=created_at,
        limit=paper_limit,
        search_abstracts=search_abstracts,
        fill_token_fallback=fill_token_fallback,
        full_scan=full_paper_scan,
        scan_rows=paper_scan_rows,
    )
    if count_paper_exclusions:
        paper_exclusions.update(
            _paper_exclusion_counts(
                conn,
                topic,
                target,
                created_at=created_at,
                search_abstracts=search_abstracts,
            )
        )
    else:
        paper_exclusions["future_published_papers"] = "not_counted"
        paper_exclusions["future_fetched_papers"] = "not_counted"
    raw_location_cache: dict[str, dict[str, Any]] = {}
    fact_payloads = [_fact_payload(conn, f, raw_location_cache) for f in facts]
    snapshot = {
        "topic": topic.strip(),
        "as_of": target.isoformat(),
        "created_at": created_at.isoformat(),
        "query_version": f"{QUERY_VERSION}_research",
        "fact_count": len(fact_payloads),
        "paper_count": len(papers),
        "source_count": len({f.get("source_id") for f in facts if f.get("source_id")}),
        "paper_search_abstracts": bool(search_abstracts),
        "paper_fill_token_fallback": bool(fill_token_fallback),
        "paper_full_scan": bool(full_paper_scan),
        "paper_scan_rows": int(paper_scan_rows),
        "snapshot_hash": _research_snapshot_hash(topic, target, fact_payloads, papers),
    }
    out = {
        "ok": True,
        "engine": f"{QUERY_VERSION}_research",
        "topic": topic.strip(),
        "as_of": target.isoformat(),
        "snapshot": snapshot,
        "facts": fact_payloads,
        "papers": papers,
        "sources": _source_citations(conn, facts, raw_location_cache),
        "summaries": _research_summaries(papers, fact_payloads),
        "gate_rule": {
            "facts": "active facts with published_at/observed_at/event_time <= as_of and ingested_at <= snapshot.created_at",
            "papers": "papers with published <= as_of and fetched_at <= snapshot.created_at",
            "paper_search": "title/metadata by default; abstracts only when search_abstracts is true",
            "paper_fallback": "token fallback is used only when no exact phrase papers match, unless fill_token_fallback is true",
            "paper_scan": "bounded newest-paper scan by default; full corpus text scan only when full_paper_scan is true",
        },
        "exclusions": {**fact_exclusions, **paper_exclusions},
    }
    if owns_conn:
        conn.close()
    return out


def state_pack(
    topic: str,
    as_of: date | str,
    *,
    conn: sqlite3.Connection | None = None,
    limit: int = DEFAULT_FACT_LIMIT,
    record: bool = True,
) -> dict[str, Any]:
    """Return frozen context usable by prompt assembly or a CLI caller."""

    owns_conn = conn is None
    if conn is None:
        conn = db.connect()
        db.init_db(conn)
    target = _parse_date(as_of)
    created_at = _now()
    facts, exclusions = _select_visible_fact_set(
        conn,
        topic,
        target,
        created_at=created_at,
        limit=limit,
    )
    snap = record_snapshot(conn, topic, target, facts, created_at=created_at) if record else _snapshot_manifest(
        topic,
        target,
        facts,
        created_at=created_at,
    )
    entity_ids = {
        str(v)
        for f in facts
        for v in (f.get("subject_entity_id"), f.get("object_entity_id"))
        if v
    }
    matched_entities = _match_entities(conn, topic)
    entity_ids.update(str(e["id"]) for e in matched_entities)
    raw_location_cache: dict[str, dict[str, Any]] = {}
    pack = {
        "ok": True,
        "engine": QUERY_VERSION,
        "topic": topic.strip(),
        "as_of": target.isoformat(),
        "snapshot": snap,
        "matched_entities": matched_entities,
        "facts": [_fact_payload(conn, f, raw_location_cache) for f in facts],
        "series": _series_summaries(conn, topic),
        "edges": _entity_edges(conn, entity_ids),
        "sources": _source_citations(conn, facts, raw_location_cache),
        "exclusions": exclusions,
    }
    if record:
        conn.commit()
    if owns_conn:
        conn.close()
    return pack


def _date_gate(value: str | None, cutoff: str) -> dict[str, Any]:
    observed = _iso_date(value)
    return {
        "value": observed,
        "cutoff": cutoff,
        "passes": observed is None or observed <= cutoff,
    }


def _datetime_gate(value: str | None, cutoff: str) -> dict[str, Any]:
    observed = str(value) if value else None
    return {
        "value": observed,
        "cutoff": cutoff,
        "passes": observed is None or observed <= cutoff,
    }


def _proof_fact(fact: dict[str, Any], sources_by_id: dict[str, dict[str, Any]], *, as_of: str, snapshot_created_at: str) -> dict[str, Any]:
    source = sources_by_id.get(str(fact.get("source_id") or ""), {})
    gates = {
        "published_at": _date_gate(fact.get("published_at"), as_of),
        "observed_at": _date_gate(fact.get("observed_at"), as_of),
        "event_time": _date_gate(fact.get("event_time"), as_of),
        "ingested_at": _datetime_gate(fact.get("ingested_at"), snapshot_created_at),
    }
    return {
        "id": fact.get("id"),
        "subject": fact.get("subject"),
        "subject_entity_id": fact.get("subject_entity_id"),
        "predicate": fact.get("predicate"),
        "object": fact.get("object"),
        "object_entity_id": fact.get("object_entity_id"),
        "value": fact.get("value"),
        "unit": fact.get("unit"),
        "event_time": fact.get("event_time"),
        "published_at": fact.get("published_at"),
        "observed_at": fact.get("observed_at"),
        "ingested_at": fact.get("ingested_at"),
        "confidence": fact.get("confidence"),
        "extractor": fact.get("extractor"),
        "rationale": fact.get("rationale"),
        "source_id": fact.get("source_id"),
        "source_title": source.get("title"),
        "source_url": source.get("url"),
        "content_hash": fact.get("content_hash"),
        "raw_doc_status": fact.get("raw_doc_status"),
        "raw_doc_local": fact.get("raw_doc_local"),
        "raw_doc_local_path": fact.get("raw_doc_local_path"),
        "raw_doc_remote_uri": fact.get("raw_doc_remote_uri"),
        "raw_doc_byte_len": fact.get("raw_doc_byte_len"),
        "gates": gates,
        "visible_as_of_proven": all(g["passes"] for g in gates.values()),
    }


def state_proof(
    topic: str,
    as_of: date | str,
    *,
    conn: sqlite3.Connection | None = None,
    limit: int = DEFAULT_FACT_LIMIT,
) -> dict[str, Any]:
    """Read-only proof that the returned facts were visible under point-in-time gates."""

    owns_conn = conn is None
    if conn is None:
        conn = db.connect()
        db.init_db(conn)
    target = _parse_date(as_of)
    created_at = _now()
    selected_facts, exclusions = _select_visible_fact_set(
        conn,
        topic,
        target,
        created_at=created_at,
        limit=limit,
    )
    snapshot = _snapshot_manifest(topic, target, selected_facts, created_at=created_at)
    raw_location_cache: dict[str, dict[str, Any]] = {}
    fact_payloads = [
        _fact_payload(conn, fact, raw_location_cache)
        for fact in selected_facts
    ]
    sources = _source_citations(conn, selected_facts, raw_location_cache)
    sources_by_id = {
        str(source["id"]): source
        for source in sources
        if source.get("id")
    }
    facts = [
        _proof_fact(
            fact,
            sources_by_id,
            as_of=target.isoformat(),
            snapshot_created_at=str(snapshot["created_at"]),
        )
        for fact in fact_payloads
    ]
    out = {
        "ok": True,
        "engine": f"{QUERY_VERSION}_proof",
        "topic": topic.strip(),
        "as_of": target.isoformat(),
        "snapshot": snapshot,
        "gate_rule": {
            "published_at": "published_at is null or published_at <= as_of",
            "observed_at": "observed_at is null or observed_at <= as_of",
            "event_time": "event_time is null or event_time <= as_of",
            "ingested_at": "ingested_at is null or ingested_at <= snapshot.created_at",
            "status": "visible_facts includes active facts and hides superseded facts by default",
        },
        "facts": facts,
        "sources": sources,
        "exclusions": exclusions,
        "all_visible_as_of_proven": all(f.get("visible_as_of_proven") for f in facts),
    }
    if owns_conn:
        conn.close()
    return out


def _exclusion_counts(conn: sqlite3.Connection, as_of: date, snapshot_created_at: datetime) -> dict[str, int]:
    as_of_s = as_of.isoformat()
    created_s = snapshot_created_at.isoformat()
    try:
        row = conn.execute(
            """
            SELECT
                COALESCE(sum(CASE WHEN published_at IS NOT NULL AND substr(published_at,1,10) > ? THEN 1 ELSE 0 END), 0)
                    AS future_published,
                COALESCE(sum(CASE WHEN observed_at IS NOT NULL AND substr(observed_at,1,10) > ? THEN 1 ELSE 0 END), 0)
                    AS future_observed,
                COALESCE(sum(CASE WHEN event_time IS NOT NULL AND substr(event_time,1,10) > ? THEN 1 ELSE 0 END), 0)
                    AS future_event,
                COALESCE(sum(CASE WHEN ingested_at > ? THEN 1 ELSE 0 END), 0)
                    AS future_ingested
            FROM world_state_facts
            WHERE status='active'
            """,
            (as_of_s, as_of_s, as_of_s, created_s),
        ).fetchone()
    except sqlite3.Error:
        return {
            "future_published": 0,
            "future_observed": 0,
            "future_event": 0,
            "future_ingested": 0,
        }
    return {
        "future_published": int(row["future_published"] or 0),
        "future_observed": int(row["future_observed"] or 0),
        "future_event": int(row["future_event"] or 0),
        "future_ingested": int(row["future_ingested"] or 0),
    }


def estimate_bigquery_cost_cents(bytes_scanned: int, *, free_tib_remaining: float = 0.0) -> int:
    billable_tib = max(0.0, (bytes_scanned / TIB) - free_tib_remaining)
    return int(round(billable_tib * BIGQUERY_DOLLARS_PER_TIB * 100))


def estimate_athena_cost_cents(bytes_scanned: int) -> int:
    return int(round((bytes_scanned / 1_000_000_000_000) * ATHENA_DOLLARS_PER_TB * 100))


def guard_scan_bytes(
    provider: str,
    bytes_scanned: int,
    *,
    max_gb: float = 100.0,
    allow_large: bool = False,
    free_tib_remaining: float = 0.0,
) -> dict[str, Any]:
    """Dry-run guard for paid scan engines. Call before execution, then log through cost_ledger."""

    limit_bytes = int(max_gb * GIB)
    if bytes_scanned > limit_bytes and not allow_large:
        raise CostGuardError(
            f"{provider} dry run would scan {bytes_scanned / GIB:.2f} GiB, above limit {max_gb:.2f} GiB"
        )
    provider_l = provider.lower()
    if provider_l == "bigquery":
        est = estimate_bigquery_cost_cents(bytes_scanned, free_tib_remaining=free_tib_remaining)
    elif provider_l == "athena":
        est = estimate_athena_cost_cents(bytes_scanned)
    else:
        est = 0
    return {
        "provider": provider_l,
        "bytes_scanned": bytes_scanned,
        "gb_scanned": bytes_scanned / GIB,
        "max_gb": max_gb,
        "estimated_cost_cents": est,
        "allowed": True,
    }


def _scan_log_estimates() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1] / "data" / "_collect_logs"
    logs = {
        "athena": root / "athena_cost.log",
        "google_patents_bigquery": root / "google_patents_cost.log",
    }
    estimates: dict[str, Any] = {}
    for key, path in logs.items():
        if not path.exists():
            estimates[key] = {"gb_scanned": 0.0, "estimated_cost_cents": 0, "log": str(path), "exists": False}
            continue
        text = path.read_text(errors="ignore")
        nums = [float(x) for x in re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*GB", text)]
        gb = sum(nums)
        if key == "athena":
            cents = estimate_athena_cost_cents(int(gb * 1_000_000_000))
        else:
            cents = estimate_bigquery_cost_cents(int(gb * GIB))
        estimates[key] = {
            "gb_scanned": round(gb, 3),
            "estimated_cost_cents": cents,
            "log": str(path),
            "exists": True,
        }
    return estimates


def audit(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Non-mutating health snapshot of the data layer."""

    owns_conn = conn is None
    if conn is None:
        conn = db.connect()
        db.init_db(conn)
    counts = {
        table: _table_count(conn, table)
        for table in (
            "sources", "series", "observations", "observation_revisions", "raw_docs",
            "papers", "entities", "entity_links", "entity_edges", "graph_nodes", "graph_edges",
            "world_state_facts", "world_state_snapshots", "forecast_cards", "series_health",
            "cost_ledger",
        )
    }
    health_rows = conn.execute(
        "SELECT status, count(*) n FROM series_health GROUP BY status"
    ).fetchall() if counts["series_health"] else []
    health = {str(r["status"]): int(r["n"]) for r in health_rows}
    health_failures = conn.execute(
        """
        SELECT
            sh.series_id,
            s.provider,
            s.external_id,
            s.label,
            s.metric,
            sh.fresh_status,
            sh.complete_status,
            sh.valid_status,
            sh.recon_status,
            sh.prov_status,
            sh.days_stale,
            sh.n_gaps,
            sh.health_score,
            sh.detail
        FROM series_health sh
        LEFT JOIN series s ON s.id=sh.series_id
        WHERE sh.status='fail'
        ORDER BY sh.health_score ASC, sh.days_stale DESC, sh.series_id
        LIMIT 20
        """
    ).fetchall() if counts["series_health"] else []
    health_failure_items = []
    for row in health_failures:
        item = dict(row)
        item["health_failure_review"] = HEALTH_FAILURE_REVIEWS.get(
            (str(item.get("provider") or ""), str(item.get("external_id") or ""))
        )
        health_failure_items.append(item)
    reviewed_health_failures = sum(1 for row in health_failure_items if row.get("health_failure_review"))
    source_hash = conn.execute(
        """
        SELECT count(*) AS total,
               sum(CASE WHEN content_hash IS NOT NULL AND length(content_hash)>0 THEN 1 ELSE 0 END) AS hashed
        FROM sources
        """
    ).fetchone()
    raw_status_rows = conn.execute(
        """
        SELECT COALESCE(raw_provenance_status, 'unknown') AS status, count(*) AS n
        FROM sources
        GROUP BY COALESCE(raw_provenance_status, 'unknown')
        """
    ).fetchall() if counts["sources"] else []
    raw_status_counts = {str(r["status"]): int(r["n"]) for r in raw_status_rows}
    raw_linked = conn.execute(
        "SELECT count(*) FROM raw_docs WHERE source_id IS NOT NULL"
    ).fetchone()[0] if counts["raw_docs"] else 0
    sources_with_raw_doc = conn.execute(
        """
        SELECT count(DISTINCT s.id)
        FROM sources s
        JOIN raw_docs r ON r.content_hash = s.content_hash
        """
    ).fetchone()[0] if counts["sources"] else 0
    cost_row = conn.execute(
        """
        SELECT COALESCE(sum(est_cost_cents),0) AS est,
               COALESCE(sum(actual_cost_cents),0) AS actual,
               COALESCE(sum(CASE WHEN approval_status='approved' THEN est_cost_cents ELSE 0 END),0) AS approved,
               COALESCE(sum(CASE WHEN approval_status='auto' THEN est_cost_cents ELSE 0 END),0) AS auto
        FROM cost_ledger
        """
    ).fetchone()
    by_provider = conn.execute(
        """
        SELECT provider, COALESCE(sum(est_cost_cents),0) AS est,
               COALESCE(sum(actual_cost_cents),0) AS actual, count(*) AS n
        FROM cost_ledger GROUP BY provider ORDER BY est DESC LIMIT 12
        """
    ).fetchall() if counts["cost_ledger"] else []
    predicates = conn.execute(
        "SELECT predicate, count(*) n FROM world_state_facts GROUP BY predicate ORDER BY n DESC LIMIT 12"
    ).fetchall() if counts["world_state_facts"] else []
    facts_by_source = conn.execute(
        """
        SELECT COALESCE(s.title, f.source_id, 'unknown') AS source, count(*) n
        FROM world_state_facts f
        LEFT JOIN sources s ON s.id = f.source_id
        GROUP BY COALESCE(s.title, f.source_id, 'unknown')
        ORDER BY n DESC LIMIT 12
        """
    ).fetchall() if counts["world_state_facts"] else []
    facts_missing_raw_by_source = conn.execute(
        """
        SELECT COALESCE(s.title, f.source_id, 'unknown') AS source, count(*) n
        FROM world_state_facts f
        LEFT JOIN sources s ON s.id = f.source_id
        WHERE f.content_hash IS NULL
           OR NOT EXISTS (SELECT 1 FROM raw_docs r WHERE r.content_hash=f.content_hash)
        GROUP BY COALESCE(s.title, f.source_id, 'unknown')
        ORDER BY n DESC LIMIT 12
        """
    ).fetchall() if counts["world_state_facts"] else []
    source_hashes_without_raw_sample = conn.execute(
        """
        SELECT title, url
        FROM sources s
        WHERE s.content_hash IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM raw_docs r WHERE r.content_hash=s.content_hash)
        ORDER BY title LIMIT 12
        """
    ).fetchall() if counts["sources"] else []
    linked_series = conn.execute(
        """
        SELECT count(*)
        FROM series s
        WHERE EXISTS (
            SELECT 1 FROM entity_links el WHERE el.ref_table='series' AND el.ref_id=s.id
        )
        """
    ).fetchone()[0] if counts["series"] else 0
    facts_with_subject = conn.execute(
        "SELECT count(*) FROM world_state_facts WHERE subject_entity_id IS NOT NULL"
    ).fetchone()[0] if counts["world_state_facts"] else 0
    facts_with_raw_doc = conn.execute(
        """
        SELECT count(*)
        FROM world_state_facts f
        WHERE f.content_hash IS NOT NULL
          AND EXISTS (SELECT 1 FROM raw_docs r WHERE r.content_hash=f.content_hash)
        """
    ).fetchone()[0] if counts["world_state_facts"] else 0
    latest_snapshot = conn.execute(
        """
        SELECT topic, as_of, created_at, snapshot_hash, fact_count, source_count
        FROM world_state_snapshots ORDER BY created_at DESC LIMIT 1
        """
    ).fetchone() if counts["world_state_snapshots"] else None
    disk = disk_guard.usage(db.REPO_ROOT)
    offload_manifest = db.REPO_ROOT / "data" / "_offload_manifest.jsonl"
    offload_entries = data_offload.read_manifest(offload_manifest)
    uploaded_entries = [e for e in offload_entries if e.uploaded]
    local_deleted_entries = [e for e in offload_entries if e.deleted_local]
    raw_doc_files = _raw_doc_file_status(conn, offload_entries) if counts["raw_docs"] else {
        "raw_docs_indexed": 0,
        "raw_docs_present_local": 0,
        "raw_docs_missing_local": 0,
        "raw_docs_offloaded": 0,
        "raw_docs_missing_unaccounted": 0,
        "raw_doc_local_bytes": 0,
        "raw_doc_offloaded_bytes_estimated": 0,
        "raw_doc_missing_local_sample": [],
    }
    total_sources = int(source_hash["total"] or 0)
    hashed_sources = int(source_hash["hashed"] or 0)
    out = {
        "counts": counts,
        "series_health": {
            "ok": int(health.get("ok", 0)),
            "warn": int(health.get("warn", 0)),
            "fail": int(health.get("fail", 0)),
            "audited": sum(int(v) for v in health.values()),
            "reviewed_failures": reviewed_health_failures,
            "unreviewed_failures": max(int(health.get("fail", 0)) - reviewed_health_failures, 0),
            "failures": health_failure_items,
        },
        "raw_doc_coverage": {
            "sources_total": total_sources,
            "sources_with_content_hash": hashed_sources,
            "sources_with_raw_doc": int(sources_with_raw_doc),
            "sources_missing_content_hash": total_sources - hashed_sources,
            "source_hashes_without_raw_doc": max(0, hashed_sources - int(sources_with_raw_doc)),
            "legacy_no_raw_doc": int(raw_status_counts.get("legacy_hash_no_raw_doc", 0))
            + int(raw_status_counts.get("legacy_no_content_hash", 0)),
            "legacy_hash_no_raw_doc": int(raw_status_counts.get("legacy_hash_no_raw_doc", 0)),
            "legacy_no_content_hash": int(raw_status_counts.get("legacy_no_content_hash", 0)),
            "unclassified_raw_provenance": int(raw_status_counts.get("unknown", 0)),
            "raw_provenance_status_counts": raw_status_counts,
            "raw_docs": counts["raw_docs"],
            "raw_docs_linked_to_source": int(raw_linked),
            **raw_doc_files,
            "source_hash_coverage_pct": round((hashed_sources / total_sources) * 100, 2)
            if total_sources else 0.0,
            "source_raw_doc_coverage_pct": round((int(sources_with_raw_doc) / total_sources) * 100, 2)
            if total_sources else 0.0,
            "source_hashes_without_raw_doc_sample": [dict(r) for r in source_hashes_without_raw_sample],
            "raw_gap_summary": raw_provenance.raw_gap_summary(conn),
        },
        "costs": {
            "estimated_cost_cents": int(cost_row["est"] or 0),
            "actual_cost_cents": int(cost_row["actual"] or 0),
            "approved_est_cost_cents": int(cost_row["approved"] or 0),
            "auto_est_cost_cents": int(cost_row["auto"] or 0),
            "by_provider": [dict(r) for r in by_provider],
            "scan_logs": _scan_log_estimates(),
        },
        "local_storage": {
            "disk": disk,
            "guard": {
                "min_free_gb": disk_guard.DEFAULT_MIN_FREE_GB,
                "max_used_pct": disk_guard.DEFAULT_MAX_USED_PCT,
                "safe": disk["free_gb"] >= disk_guard.DEFAULT_MIN_FREE_GB
                and disk["used_pct"] <= disk_guard.DEFAULT_MAX_USED_PCT,
            },
            "offload_manifest": {
                "path": str(offload_manifest),
                "entries": len(offload_entries),
                "uploaded_entries": len(uploaded_entries),
                "local_deleted_entries": len(local_deleted_entries),
                "recorded_gib": round(sum(e.size_bytes for e in offload_entries) / GIB, 3),
                "estimated_storage_usd_month": round(
                    sum(e.estimated_storage_usd_month for e in offload_entries), 4
                ),
            },
        },
        "world_state": {
            "facts_by_predicate": [dict(r) for r in predicates],
            "facts_by_source": [dict(r) for r in facts_by_source],
            "facts_missing_raw_by_source": [dict(r) for r in facts_missing_raw_by_source],
            "facts_with_subject_entity": int(facts_with_subject),
            "facts_without_subject_entity": counts["world_state_facts"] - int(facts_with_subject),
            "fact_subject_coverage_pct": round((int(facts_with_subject) / counts["world_state_facts"]) * 100, 2)
            if counts["world_state_facts"] else 0.0,
            "facts_with_raw_doc": int(facts_with_raw_doc),
            "fact_raw_doc_coverage_pct": round((int(facts_with_raw_doc) / counts["world_state_facts"]) * 100, 2)
            if counts["world_state_facts"] else 0.0,
            "series_with_entity_link": int(linked_series),
            "series_without_entity_link": counts["series"] - int(linked_series),
            "series_entity_link_coverage_pct": round((int(linked_series) / counts["series"]) * 100, 2)
            if counts["series"] else 0.0,
            "latest_snapshot": dict(latest_snapshot) if latest_snapshot else None,
        },
    }
    if owns_conn:
        conn.close()
    return out


def format_pack(pack: dict[str, Any]) -> str:
    snap = pack["snapshot"]
    lines = [
        f"World-state pack: {pack['topic']} as of {pack['as_of']}",
        f"snapshot {snap['snapshot_hash']} ({snap['fact_count']} facts, {snap['source_count']} sources)",
    ]
    if pack["matched_entities"]:
        ents = ", ".join(e["canonical_name"] for e in pack["matched_entities"][:6])
        lines.append(f"matched entities: {ents}")
    if pack["facts"]:
        lines.append("facts:")
        for f in pack["facts"][:10]:
            subj = f.get("subject") or f.get("subject_entity_id") or "subject"
            obj = f.get("object") or f.get("value") or ""
            unit = f" {f['unit']}" if f.get("unit") else ""
            when = f.get("published_at") or f.get("observed_at") or f.get("event_time") or "undated"
            lines.append(
                f"- {subj} {f['predicate']} {obj}{unit} "
                f"(published/observed {when}, conf {float(f.get('confidence') or 0):.2f})"
            )
    else:
        lines.append("facts: none matched the point-in-time gates yet")
    if pack["series"]:
        lines.append("series context:")
        for s in pack["series"][:6]:
            lines.append(
                f"- {s['provider']}:{s['label']} n={s['n_obs']} "
                f"last={s.get('last_as_of') or 'n/a'}"
            )
    ex = pack.get("exclusions", {})
    if ex:
        lines.append(
            "exclusions: "
            + ", ".join(f"{k}={v}" for k, v in ex.items() if v)
        )
    return "\n".join(lines)


def format_research_pack(pack: dict[str, Any]) -> str:
    snap = pack["snapshot"]
    lines = [
        f"Research pack: {pack['topic']} as of {pack['as_of']}",
        f"snapshot {snap['snapshot_hash']} ({snap['fact_count']} facts, {snap['paper_count']} papers)",
    ]
    summaries = pack.get("summaries") or {}
    providers = summaries.get("papers_by_provider") or {}
    if providers:
        lines.append("paper providers: " + ", ".join(f"{k}={v}" for k, v in providers.items()))
    categories = summaries.get("papers_by_primary_category") or {}
    if categories:
        lines.append("paper categories: " + ", ".join(f"{k}={v}" for k, v in list(categories.items())[:8]))
    if pack.get("facts"):
        lines.append("research facts:")
        for f in pack["facts"][:8]:
            subj = f.get("subject") or f.get("subject_entity_id") or "research"
            obj = f.get("object") or f.get("value") or ""
            unit = f" {f['unit']}" if f.get("unit") else ""
            when = f.get("published_at") or f.get("observed_at") or f.get("event_time") or "undated"
            lines.append(
                f"- {subj} {f['predicate']} {obj}{unit} "
                f"(published/observed {when}, conf {float(f.get('confidence') or 0):.2f})"
            )
    else:
        lines.append("research facts: none matched the point-in-time gates")
    if pack.get("papers"):
        lines.append("papers:")
        for p in pack["papers"][:10]:
            title = str(p.get("title") or "").strip() or p.get("external_id") or p.get("id")
            lines.append(
                f"- {p.get('published') or 'undated'} {p.get('provider')}:{p.get('external_id')} "
                f"[{p.get('primary_category') or 'n/a'}] {title}"
            )
    else:
        lines.append("papers: none matched the point-in-time gates")
    ex = pack.get("exclusions") or {}
    if ex:
        visible_ex = ", ".join(f"{k}={v}" for k, v in ex.items() if v)
        lines.append(f"exclusions: {visible_ex or 'none'}")
    return "\n".join(lines)


def format_proof(proof: dict[str, Any]) -> str:
    snap = proof["snapshot"]
    lines = [
        f"World-state proof: {proof['topic']} as of {proof['as_of']}",
        f"snapshot {snap['snapshot_hash']} ({snap['fact_count']} facts, query={snap['query_version']})",
        "gate rule: published/observed/event <= as_of and ingested <= snapshot.created_at",
    ]
    facts = proof.get("facts") or []
    if not facts:
        lines.append("facts: none matched the point-in-time gates")
    for fact in facts[:10]:
        subj = fact.get("subject") or fact.get("subject_entity_id") or "subject"
        obj = fact.get("object") or fact.get("value") or ""
        unit = f" {fact['unit']}" if fact.get("unit") else ""
        gates = fact.get("gates") or {}
        gate_bits = []
        for key in ("published_at", "observed_at", "event_time", "ingested_at"):
            gate = gates.get(key) or {}
            gate_bits.append(f"{key}={'PASS' if gate.get('passes') else 'FAIL'}")
        raw = fact.get("raw_doc_status") or "unknown"
        h = str(fact.get("content_hash") or "")
        h_short = h[:12] + "..." if len(h) > 12 else h
        lines.append(
            f"- {subj} {fact.get('predicate')} {obj}{unit} | "
            + ", ".join(gate_bits)
            + f" | raw={raw}"
            + (f" hash={h_short}" if h_short else "")
        )
        if fact.get("source_url"):
            lines.append(f"  source: {fact['source_url']}")
        if fact.get("raw_doc_remote_uri"):
            lines.append(f"  raw: {fact['raw_doc_remote_uri']}")
    ex = proof.get("exclusions") or {}
    if ex:
        visible_ex = ", ".join(f"{k}={v}" for k, v in ex.items() if v)
        lines.append(f"exclusions: {visible_ex or 'none'}")
    lines.append(f"all_visible_as_of_proven={proof.get('all_visible_as_of_proven')}")
    return "\n".join(lines)


def _health_failure_detail(row: dict[str, Any]) -> str:
    detail_raw = str(row.get("detail") or "")
    try:
        detail = json.loads(detail_raw)
    except json.JSONDecodeError:
        detail = {}
    if not isinstance(detail, dict):
        detail = {}

    parts: list[str] = []
    checks = (
        ("fresh", "fresh_status"),
        ("complete", "complete_status"),
        ("valid", "valid_status"),
        ("recon", "recon_status"),
        ("prov", "prov_status"),
    )
    for detail_key, status_key in checks:
        status = str(row.get(status_key) or "")
        if status in {"fail", "warn"}:
            reason = str(detail.get(detail_key) or "").strip()
            parts.append(f"{detail_key}={status}" + (f": {reason}" if reason else ""))
    if parts:
        return ", ".join(parts)
    return detail_raw.replace("\n", " ")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _raw_doc_file_status(
    conn: sqlite3.Connection,
    offload_entries: list[data_offload.ManifestEntry],
) -> dict[str, Any]:
    """Compare raw_docs index rows with bytes actually present on local disk.

    raw_docs is the durable provenance index. The byte store can be intentionally offloaded from a
    laptop, so audit reports local availability separately from proven remote/offloaded status.
    """

    rows = conn.execute(
        """
        SELECT content_hash, path, byte_len
        FROM raw_docs
        ORDER BY content_hash
        """
    ).fetchall()
    deleted_roots: list[tuple[Path, str]] = []
    for entry in offload_entries:
        if not (entry.uploaded and entry.deleted_local):
            continue
        local_path = Path(entry.local_path).expanduser()
        if not local_path.is_absolute():
            local_path = db.REPO_ROOT / local_path
        deleted_roots.append((local_path.resolve(strict=False), entry.remote_uri.rstrip("/")))

    present = 0
    missing = 0
    offloaded = 0
    local_bytes = 0
    offloaded_bytes = 0
    sample: list[dict[str, object]] = []
    for row in rows:
        rel_path = str(row["path"] or "")
        if not rel_path:
            missing += 1
            if len(sample) < 8:
                sample.append({"content_hash": row["content_hash"], "path": None, "remote_uri": None})
            continue
        raw_path = Path(rel_path).expanduser()
        if not raw_path.is_absolute():
            raw_path = db.REPO_ROOT / raw_path
        raw_path = raw_path.resolve(strict=False)
        byte_len = int(row["byte_len"] or 0)
        if raw_path.is_file():
            present += 1
            local_bytes += byte_len
            continue

        missing += 1
        remote_uri: str | None = None
        for root, remote_root in deleted_roots:
            if raw_path == root:
                remote_uri = remote_root
                break
            if _is_relative_to(raw_path, root):
                suffix = "/".join(raw_path.relative_to(root).parts)
                remote_uri = f"{remote_root}/{suffix}" if suffix else remote_root
                break
        if remote_uri:
            offloaded += 1
            offloaded_bytes += byte_len
        if len(sample) < 8:
            sample.append(
                {
                    "content_hash": row["content_hash"],
                    "path": rel_path,
                    "remote_uri": remote_uri,
                }
            )

    return {
        "raw_docs_indexed": len(rows),
        "raw_docs_present_local": present,
        "raw_docs_missing_local": missing,
        "raw_docs_offloaded": offloaded,
        "raw_docs_missing_unaccounted": max(missing - offloaded, 0),
        "raw_doc_local_bytes": local_bytes,
        "raw_doc_offloaded_bytes_estimated": offloaded_bytes,
        "raw_doc_missing_local_sample": sample,
    }


def format_audit(a: dict[str, Any]) -> str:
    c = a["counts"]
    raw = a["raw_doc_coverage"]
    h = a["series_health"]
    cost = a["costs"]
    storage = a.get("local_storage") or {}
    disk = storage.get("disk") or {}
    guard = storage.get("guard") or {}
    offload = storage.get("offload_manifest") or {}
    latest = a["world_state"]["latest_snapshot"]
    ws = a["world_state"]
    lines = [
        "World-state data audit",
        f"sources={c['sources']} series={c['series']} observations={c['observations']} "
        f"papers={c['papers']} entities={c['entities']} edges={c['graph_edges']}",
        f"world_state_facts={c['world_state_facts']} snapshots={c['world_state_snapshots']} "
        f"raw_docs={c['raw_docs']}",
        f"world-state coverage: facts_with_subject={ws['facts_with_subject_entity']}/{c['world_state_facts']} "
        f"({ws['fact_subject_coverage_pct']:.2f}%), "
        f"facts_with_raw={ws['facts_with_raw_doc']}/{c['world_state_facts']} "
        f"({ws['fact_raw_doc_coverage_pct']:.2f}%), "
        f"series_linked={ws['series_with_entity_link']}/{c['series']} "
        f"({ws['series_entity_link_coverage_pct']:.2f}%)",
        f"raw coverage: {raw['sources_with_content_hash']}/{raw['sources_total']} sources hashed "
        f"({raw['source_hash_coverage_pct']:.2f}%), "
        f"{raw['sources_with_raw_doc']}/{raw['sources_total']} byte-linked "
        f"({raw['source_raw_doc_coverage_pct']:.2f}%), "
        f"hashes_without_bytes={raw['source_hashes_without_raw_doc']} "
        f"legacy_no_raw_doc={raw['legacy_no_raw_doc']} "
        f"unclassified={raw.get('unclassified_raw_provenance', 0)}",
        f"raw byte files: indexed={raw.get('raw_docs_indexed', 0)} "
        f"local={raw.get('raw_docs_present_local', 0)} "
        f"offloaded={raw.get('raw_docs_offloaded', 0)} "
        f"missing_unaccounted={raw.get('raw_docs_missing_unaccounted', 0)} "
        f"local_bytes={float(raw.get('raw_doc_local_bytes') or 0) / GIB:.2f}GiB "
        f"offloaded_est={float(raw.get('raw_doc_offloaded_bytes_estimated') or 0) / GIB:.2f}GiB",
        f"series health: ok={h['ok']} warn={h['warn']} fail={h['fail']} audited={h['audited']}",
        f"health failure review: reviewed={h.get('reviewed_failures', 0)} "
        f"unreviewed={h.get('unreviewed_failures', h.get('fail', 0))}",
        f"local disk: free={float(disk.get('free_gb') or 0):.1f}GiB "
        f"used={float(disk.get('used_pct') or 0):.1f}% "
        f"guard_min={float(guard.get('min_free_gb') or 0):.1f}GiB "
        f"guard={'ok' if guard.get('safe') else 'BLOCKED'}",
        f"offload manifest: entries={offload.get('entries', 0)} uploaded={offload.get('uploaded_entries', 0)} "
        f"local_deleted={offload.get('local_deleted_entries', 0)} "
        f"recorded={float(offload.get('recorded_gib') or 0):.2f}GiB "
        f"est=${float(offload.get('estimated_storage_usd_month') or 0):.2f}/mo",
        f"cost ledger: est=${cost['estimated_cost_cents']/100:.2f} "
        f"actual=${cost['actual_cost_cents']/100:.2f} approved=${cost['approved_est_cost_cents']/100:.2f}",
    ]
    failures = h.get("failures") or []
    if failures:
        lines.append("health failures:")
        for row in failures[:6]:
            label = row.get("label") or row.get("series_id")
            provider = row.get("provider") or "unknown"
            review = row.get("health_failure_review") or {}
            review_label = f" reviewed={review.get('status')}" if review else ""
            lines.append(
                f"- {provider}:{label} [{row.get('series_id')}]{review_label} {_health_failure_detail(row)}"
            )
        more = len(failures) - min(len(failures), 6)
        if more > 0:
            lines.append(f"- +{more} more")
        reviewed_notes = [
            row
            for row in failures[:6]
            if (row.get("health_failure_review") or {}).get("next_action")
        ]
        if reviewed_notes:
            lines.append("health failure review notes:")
            for row in reviewed_notes:
                review = row.get("health_failure_review") or {}
                provider = row.get("provider") or "unknown"
                external_id = row.get("external_id") or row.get("series_id")
                label = str(external_id)
                if not label.startswith(f"{provider}:"):
                    label = f"{provider}:{label}"
                lines.append(f"- {label} -> {review['next_action']}")
    status_counts = raw.get("raw_provenance_status_counts") or {}
    if status_counts:
        lines.append(
            "raw provenance status: "
            + ", ".join(f"{k}={v}" for k, v in sorted(status_counts.items()))
        )
    gap_summary = raw.get("raw_gap_summary") or {}
    top_gap_hosts = gap_summary.get("top_hosts") or []
    if top_gap_hosts:
        lines.append(
            "raw gap hosts: "
            + ", ".join(f"{r['host']}={r['sources']}" for r in top_gap_hosts[:8])
        )
        if gap_summary.get("malformed_or_nonfetchable_url_count"):
            lines.append(
                f"raw gap nonfetchable urls: {gap_summary['malformed_or_nonfetchable_url_count']}"
            )
    raw_gaps = ws.get("facts_missing_raw_by_source") or []
    if raw_gaps:
        top = ", ".join(f"{r['source']}={r['n']}" for r in raw_gaps[:5])
        lines.append(f"top fact raw gaps: {top}")
    scans = cost["scan_logs"]
    for name, row in scans.items():
        if row["exists"]:
            lines.append(
                f"{name}: scanned={row['gb_scanned']:.2f} GB est=${row['estimated_cost_cents']/100:.2f}"
            )
    if latest:
        lines.append(
            f"latest snapshot: {latest['topic']} as_of={latest['as_of']} "
            f"hash={latest['snapshot_hash']} facts={latest['fact_count']}"
        )
    else:
        lines.append("latest snapshot: none")
    return "\n".join(lines)
