"""Targeted Wikidata QID enrichment for top global entities.

This is a small identity-backbone collector, not a Wikidata mirror. It searches only existing
top entities, accepts only exact label/alias matches that look kind-appropriate, preserves raw JSON
responses, and writes a `wikidata_qid` entity link for state-pack provenance.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from engine import rawstore, world_catalog
from engine.graph import _upsert_source
from engine.schemas import Source, SourceKind, _now

SEARCH_URL = "https://www.wikidata.org/w/api.php"
ENTITYDATA_URL = "https://www.wikidata.org/wiki/Special:EntityData"
UA = "predictthefuture research (research@vaticinus.com)"
REQUEST_TIMEOUT_S = 20
REQUEST_SPACING_S = 0.1
DEFAULT_LIMIT = 100

ORG_QIDS = {
    "Q43229",    # organization
    "Q4830453",  # business
    "Q6881511",  # enterprise
    "Q783794",   # company
    "Q891723",   # public company
    "Q167037",   # corporation
}
ORG_WORD_RE = re.compile(
    r"\b(company|corporation|business|enterprise|manufacturer|startup|laborator|"
    r"organisation|organization|conglomerate|utility|agency|department|ministry|"
    r"commission|bureau|office|bank|banking|fund|project|archive|institute|institution|"
    r"authority|system|body|branch|catalog|service|database|laboratory|"
    r"ship(?:ping)?|semiconductor|battery|aerospace|technology|electronics|energy|"
    r"mining|pharmaceutical)\b",
    re.I,
)
MATERIAL_WORD_RE = re.compile(
    r"\b(chemical|element|elements|compound|mineral|metal|metals|metallic|material|substance|isotope|"
    r"semiconductor|steel|alloy|gas|radioactive|rare earth|silicon|graphite|uranium|"
    r"lithium|nickel|cobalt|copper|silver|gallium|germanium|polysilicon|lanthanide|lanthanides)\b",
    re.I,
)
TECH_WORD_RE = re.compile(
    r"\b(technology|technique|method|field|computing|battery|storage|photovoltaic|"
    r"solar|hydrogen|capture|fusion|fission|nuclear|reaction|robot|drone|aircraft|vehicle|"
    r"navigation|therapy|therapeutic|drug|agonist|receptor|battery|memory|ram|dram|interface|"
    r"semiconductor|packaging|lithography|transformer|electrical|device|voltage|transmission|"
    r"computer|photons|light|interconnection|learning|language model|gene editing|crispr|"
    r"modification|cells|computation|launch)\b",
    re.I,
)
TECH_REJECT_RE = re.compile(
    r"\b(company|scientific article|publication|patent|website|web site|site|stack exchange|journal)\b",
    re.I,
)
REGION_WORD_RE = re.compile(
    r"\b(country|sovereign|state|continent|region|union|world|planet|global|territory)\b",
    re.I,
)


@dataclass(frozen=True)
class WikidataMatch:
    entity_id: str
    canonical_name: str
    query: str
    qid: str
    label: str
    description: str
    entity_url: str
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
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


def _without_legal_suffixes(text: str) -> str:
    toks = _norm(text).split()
    suffixes = {
        "a", "ab", "ag", "as", "co", "company", "corp", "corporation", "gmbh", "group",
        "inc", "incorporated", "limited", "llc", "ltd", "n", "nv", "plc", "p", "s", "sa",
        "se", "spa", "v",
    }
    while toks and toks[-1] in suffixes:
        toks.pop()
    return " ".join(toks)


def _without_parenthetical_suffix(text: str) -> str:
    return re.sub(r"\s*\([^)]{2,80}\)\s*$", "", text).strip()


def _is_symbol(alias: str) -> bool:
    a = alias.strip()
    if not a:
        return True
    if a.startswith(("LEI:", "CIK:", "CH:", "CompaniesHouse:", "registered_as:", "Wikidata:")):
        return True
    return bool(len(a) <= 6 and re.fullmatch(r"[A-Z0-9.\-]+", a))


def _usable_queries(name: str, aliases: list[str], *, kind: str = "company") -> list[str]:
    if kind == "company":
        candidates = [name, *aliases]
    else:
        candidates = [name, *_top_aliases(kind, name)]
    out: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        c = candidate.strip()
        if not c or _is_symbol(c) or len(_norm(c)) < 3:
            continue
        key = _norm(c)
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out[:6]


def _top_aliases(kind: str, name: str) -> list[str]:
    for spec in world_catalog.TOP_ENTITIES:
        if spec.kind == kind and spec.name == name:
            return list(spec.aliases)
    return []


def _acceptable_names(row: sqlite3.Row, *, kind: str) -> set[str]:
    if kind == "company":
        aliases = [a for a in _load_aliases(row["aliases"]) if not _is_symbol(a)]
    else:
        aliases = [a for a in _top_aliases(kind, row["canonical_name"]) if not _is_symbol(a)]
    names = [row["canonical_name"], *aliases]
    out: set[str] = set()
    for name in names:
        n = _norm(name)
        core = _without_legal_suffixes(name)
        no_parens = _norm(_without_parenthetical_suffix(name))
        if n:
            out.add(n)
        if no_parens:
            out.add(no_parens)
        if core:
            out.add(core)
    return out


def _search_url(query: str) -> str:
    params = {
        "action": "wbsearchentities",
        "format": "json",
        "language": "en",
        "type": "item",
        "limit": "5",
        "search": query,
    }
    return f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"


def _fetch_search(query: str) -> tuple[bytes | None, dict[str, Any] | None, str]:
    url = _search_url(query)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:  # noqa: S310 official public API
            raw = resp.read()
        return raw, json.loads(raw.decode("utf-8", "replace")), url
    except Exception:  # noqa: BLE001 - public endpoint; miss rather than fabricate
        return None, None, url


def _entity_url(qid: str) -> str:
    return f"{ENTITYDATA_URL}/{qid}.json"


def _fetch_entity(qid: str) -> tuple[bytes | None, dict[str, Any] | None, str]:
    url = _entity_url(qid)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:  # noqa: S310 official public API
            raw = resp.read()
        return raw, json.loads(raw.decode("utf-8", "replace")), url
    except Exception:  # noqa: BLE001 - public endpoint; miss rather than fabricate
        return None, None, url


def _entity_record(data: dict[str, Any], qid: str) -> dict[str, Any] | None:
    entities = data.get("entities") if isinstance(data.get("entities"), dict) else {}
    rec = entities.get(qid)
    return rec if isinstance(rec, dict) else None


def _label_aliases(rec: dict[str, Any]) -> list[str]:
    labels = rec.get("labels") if isinstance(rec.get("labels"), dict) else {}
    aliases = rec.get("aliases") if isinstance(rec.get("aliases"), dict) else {}
    out: list[str] = []
    for key in ("en", "mul"):
        label = labels.get(key) if isinstance(labels.get(key), dict) else {}
        if label.get("value"):
            out.append(str(label["value"]))
    if not out:
        for label in labels.values():
            if isinstance(label, dict) and label.get("value"):
                value = str(label["value"])
                if value.isascii():
                    out.append(value)
                    break
    for alias in aliases.get("en", []) if isinstance(aliases.get("en"), list) else []:
        if isinstance(alias, dict) and alias.get("value"):
            out.append(str(alias["value"]))
    return out


def _primary_label(rec: dict[str, Any]) -> str:
    labels = rec.get("labels") if isinstance(rec.get("labels"), dict) else {}
    for key in ("en", "mul"):
        label = labels.get(key) if isinstance(labels.get(key), dict) else {}
        if label.get("value"):
            return str(label["value"])
    for label in labels.values():
        if isinstance(label, dict) and label.get("value"):
            value = str(label["value"])
            if value.isascii():
                return value
    return ""


def _description(rec: dict[str, Any]) -> str:
    descriptions = rec.get("descriptions") if isinstance(rec.get("descriptions"), dict) else {}
    en = descriptions.get("en") if isinstance(descriptions.get("en"), dict) else {}
    return str(en.get("value") or "")


def _claim_qids(rec: dict[str, Any], prop: str) -> set[str]:
    claims = rec.get("claims") if isinstance(rec.get("claims"), dict) else {}
    out: set[str] = set()
    for claim in claims.get(prop, []) if isinstance(claims.get(prop), list) else []:
        mainsnak = claim.get("mainsnak") if isinstance(claim, dict) else {}
        datavalue = mainsnak.get("datavalue") if isinstance(mainsnak, dict) else {}
        value = datavalue.get("value") if isinstance(datavalue, dict) else {}
        entity_id = value.get("id") if isinstance(value, dict) else None
        if entity_id:
            out.add(str(entity_id))
    return out


def _matches_entity(row: sqlite3.Row, rec: dict[str, Any], *, kind: str = "company") -> bool:
    acceptable = _acceptable_names(row, kind=kind)
    labels = [_primary_label(rec)] if kind in {"country_region", "material", "technology"} else _label_aliases(rec)
    for label in labels:
        if not label:
            continue
        label_no_parens = _without_parenthetical_suffix(label)
        if (
            _norm(label) in acceptable
            or _norm(label_no_parens) in acceptable
            or _without_legal_suffixes(label_no_parens) in acceptable
        ):
            return True
    return False


def _looks_org_like(rec: dict[str, Any]) -> bool:
    desc = _description(rec)
    if ORG_WORD_RE.search(desc):
        return True
    return bool((_claim_qids(rec, "P31") | _claim_qids(rec, "P279")) & ORG_QIDS)


def _looks_kind_like(rec: dict[str, Any], kind: str) -> bool:
    desc = _description(rec)
    if kind in {"company", "institution"}:
        return _looks_org_like(rec)
    if kind == "material":
        return bool(MATERIAL_WORD_RE.search(desc))
    if kind == "technology":
        if TECH_REJECT_RE.search(desc):
            return False
        return bool(TECH_WORD_RE.search(desc))
    if kind == "country_region":
        return bool(REGION_WORD_RE.search(desc))
    return True


def _extract_match(
    row: sqlite3.Row,
    query: str,
    qid: str,
    data: dict[str, Any],
    url: str,
    *,
    kind: str,
) -> WikidataMatch | None:
    rec = _entity_record(data, qid)
    if not rec or not _matches_entity(row, rec, kind=kind) or not _looks_kind_like(rec, kind):
        return None
    label = (_label_aliases(rec) or [qid])[0]
    desc = _description(rec)
    return WikidataMatch(
        entity_id=row["id"],
        canonical_name=row["canonical_name"],
        query=query,
        qid=qid,
        label=label,
        description=desc,
        entity_url=url,
        confidence=0.84,
        method="wikidata_exact_label",
        rationale=(
            f"Exact Wikidata English label/alias match for query '{query}' with kind-appropriate "
            f"description/claims for kind '{kind}'. Used as identity anchor only: "
            f"{desc or 'no English description'}."
        ),
    )


def _entity_rows(
    conn: sqlite3.Connection,
    *,
    kind: str,
    limit: int,
    only: list[str] | None,
    missing_only: bool,
) -> list[sqlite3.Row]:
    world_catalog.seed_top_entities(conn, log=lambda *_a, **_k: None)
    top_names = sorted(e.name for e in world_catalog.TOP_ENTITIES if e.kind == kind)
    if not top_names:
        return []
    top_placeholders = ",".join("?" for _ in top_names)
    params: list[Any] = [kind, *top_names]
    sql = f"SELECT id, canonical_name, aliases, note FROM entities WHERE kind=? AND canonical_name IN ({top_placeholders})"
    if only:
        placeholders = ",".join("?" for _ in only)
        sql += f" AND canonical_name IN ({placeholders})"
        params.extend(only)
    if missing_only:
        ref_placeholders = ",".join("?" for _ in world_catalog.IDENTIFIER_REF_TABLES)
        sql += (
            " AND NOT EXISTS ("
            "SELECT 1 FROM entity_links el "
            "WHERE el.entity_id=entities.id "
            f"AND el.ref_table IN ({ref_placeholders})"
            ")"
        )
        params.extend(world_catalog.IDENTIFIER_REF_TABLES)
    sql += " ORDER BY canonical_name"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return conn.execute(sql, params).fetchall()


def _upsert_wikidata_source(conn: sqlite3.Connection, match: WikidataMatch, content: bytes) -> str:
    content_hash = rawstore.put(conn, content, url=match.entity_url, media_type="application/json")
    src = Source(
        url=match.entity_url,
        title=f"Wikidata entity data for {match.qid}",
        pillar_id=6,
        kind=SourceKind.analyst,
        trust_score=78,
        trust_rationale=(
            "Wikidata entity JSON is a community-curated knowledge graph record. This source is used "
            "only for exact QID identity anchoring after label/alias validation, not for primary facts."
        ),
        content_hash=content_hash,
    )
    source_id = _upsert_source(conn, src)
    rawstore.put(conn, content, source_id=source_id, url=match.entity_url, media_type="application/json")
    return source_id


def _apply_match(conn: sqlite3.Connection, match: WikidataMatch) -> int:
    row = conn.execute("SELECT aliases, note FROM entities WHERE id=?", (match.entity_id,)).fetchone()
    aliases = set(_load_aliases(row["aliases"]))
    aliases.update({match.qid, f"Wikidata:{match.qid}", match.label})
    note = row["note"] or ""
    wd_note = f"Wikidata QID:{match.qid} label={match.label}."
    if "Wikidata QID:" not in note:
        note = (note.rstrip() + " " + wd_note).strip()
    else:
        note = re.sub(r"Wikidata QID:[^.]+\.", wd_note, note)
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
            _stable_id("wikidata", match.entity_id, match.qid),
            match.entity_id,
            "wikidata_qid",
            match.qid,
            match.label,
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
    kind: str = "company",
    limit: int = DEFAULT_LIMIT,
    only: list[str] | None = None,
    missing_only: bool = True,
    log=print,
) -> dict[str, Any]:
    rows = _entity_rows(conn, kind=kind, limit=limit, only=only, missing_only=missing_only)
    matches: list[WikidataMatch] = []
    misses: list[str] = []
    links_written = 0
    raw_responses = 0
    source_ids: list[str] = []
    for row in rows:
        match: WikidataMatch | None = None
        match_raw: bytes | None = None
        for query in _usable_queries(row["canonical_name"], _load_aliases(row["aliases"]), kind=kind):
            search_raw, search_data, search_url = _fetch_search(query)
            if search_raw:
                rawstore.put(conn, search_raw, url=search_url, media_type="application/json")
                raw_responses += 1
            if not search_data:
                continue
            qids = [
                str(item.get("id"))
                for item in search_data.get("search", [])
                if isinstance(item, dict) and str(item.get("id") or "").startswith("Q")
            ]
            for qid in qids[:5]:
                entity_raw, entity_data, entity_url = _fetch_entity(qid)
                if entity_raw:
                    rawstore.put(conn, entity_raw, url=entity_url, media_type="application/json")
                    raw_responses += 1
                if not entity_raw or not entity_data:
                    continue
                candidate = _extract_match(row, query, qid, entity_data, entity_url, kind=kind)
                if candidate:
                    match = candidate
                    match_raw = entity_raw
                    break
            if match:
                break
            time.sleep(REQUEST_SPACING_S)
        if match and match_raw:
            source_ids.append(_upsert_wikidata_source(conn, match, match_raw))
            matches.append(match)
            links_written += _apply_match(conn, match)
            log(f"  + {row['canonical_name']}: {match.qid} ({match.label})")
        else:
            misses.append(row["canonical_name"])
            log(f"  - {row['canonical_name']}: no exact Wikidata QID match")
    conn.commit()
    return {
        "seen": len(rows),
        "matched": len(matches),
        "missed": len(misses),
        "links_written": links_written,
        "raw_responses": raw_responses,
        "source_ids": sorted(set(source_ids)),
        "misses": misses,
    }
