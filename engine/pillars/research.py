"""Pillar 1 — the FINE-GRAINED research front-end (the earliest grain of the frontier).

`frontier.py` reads research as coarse *yearly counts per concept*. That is exactly the blind spot
the project diagnosed (goal.md #2): aggregate counts are the LAST place a signal shows up, so deep
learning was invisible until it had already won. The alpha lives earlier and finer. This module reads
the raw paper stream and computes the three LEADING signals that move *before* a count saturates:

  1. topic_share   — a technique's share of the literature, per MONTH. Emergence = the share's 2nd
                     derivative bending up (a method going 0.1% → 5%), caught long before the raw count.
  2. field_breadth — how many distinct fields a technique's papers span, per month. A technique
                     crossing field A → B → C is the deep-learning signature (CS → vision → speech →
                     biology) — diffusion precedes volume.
  3. talent_inflow — distinct authors publishing on the technique per month. Labs/people pivoting in
                     is an early commitment signal.

How it stays honest / point-in-time clean: a paper's first-submission date is a FIXED fact, so
bucketing by it can never look ahead (unlike citations, which accrue in the future — a known gap).
Each signal becomes a normal Series + Observations row, so the EXISTING funnel runs over it unchanged:
QC (quality.py) → detector (detector.py) → BH-FDR (significance.py) → lead/lag pre-consensus
(discover.py — where `arxiv` is already a LEADING provider). This module only *collects + derives*;
the reasoning stays in-session (Claude).

Source: arXiv OAI-PMH (`export.arxiv.org/oai2`) — the official bulk-metadata protocol, keyless. We
harvest whole sets (every record, paginated by resumptionToken) so coverage is gapless by construction
and bucket by the real submission date. The raw records land in the `papers` table (the substrate), so
new signals can be added later without re-harvesting (data is the binding constraint — we keep it).

Cost: $0 (keyless). Every run logs a $0 'auto' cost-ledger row so the gate is exercised (rule 3).
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date
from math import sqrt
from pathlib import Path

from engine import db, store
from engine.schemas import (
    CostLedgerEntry,
    Observation,
    Series,
    Source,
    SourceKind,
    _now,
    _uid,
)

FRONTIER_PILLAR_ID = 1

MAILTO = "ruben.stout@edu.escp.eu"
UA = f"predictthefuture/0.1 (mailto:{MAILTO})"
OAI = "https://export.arxiv.org/oai2"

# OAI namespaces (the arXiv metadata format).
NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "arxiv": "http://arxiv.org/OAI/arXiv/",
}

# Point-in-time window. 2010 covers the modern era (incl. the deep-learning emergence — the marquee
# test); we drop the trailing months below because recent submissions are still being indexed/revised.
WINDOW_START_YEAR = 2010
TRAILING_MONTHS_DROPPED = 2   # the last N month-buckets under-report (indexing lag) — never store them

# The seed fields (Ruben's pick): AI/ML + biology + energy/materials, full history, gapless. OAI sets
# are coarse archives; the per-paper `primary_category` keeps the fine granularity for diffusion.
SEED_SETS: list[str] = [
    # smallest-first, so in-window signals appear early in a long harvest (cs is by far the largest).
    "q-bio",              # quantitative biology
    "eess",               # electrical eng & systems — power, signal, control
    "stat",               # stat.ML — the statistics side of ML
    "physics:cond-mat",   # condensed matter — materials, superconductivity, batteries
    "cs",                 # AI/ML lives here: cs.LG, cs.AI, cs.CL, cs.CV, … (largest — last)
]

# The techniques we track. Each is a quoted phrase matched (word-boundary) in title+abstract — we must
# know what we measure (GIGO). Domain-spanning on purpose, so the detector proves it is field-agnostic.
# The list is the *seed*; auto-discovered rising n-grams can extend it later (a logged next step).
TERMS: list[str] = [
    # --- AI / ML ---
    "deep learning", "transformer", "attention mechanism", "large language model",
    "diffusion model", "generative adversarial network", "graph neural network",
    "reinforcement learning", "self-supervised", "contrastive learning", "neural architecture search",
    "federated learning", "knowledge distillation", "mixture of experts", "retrieval augmented",
    "vision transformer", "foundation model", "in-context learning",
    # --- biology ---
    "single cell rna", "crispr", "messenger rna", "mrna vaccine", "protein folding",
    "alphafold", "organoid", "cryo-electron microscopy", "spatial transcriptomics",
    "base editing", "optogenetics",
    # --- energy / materials ---
    "perovskite", "solid state battery", "solid electrolyte", "lithium metal",
    "sodium ion battery", "metal organic framework", "electrocatalysis",
    "grain oriented", "high entropy alloy", "topological insulator", "twisted bilayer",
    "quantum error correction", "superconducting qubit",
    # --- FIZZLE negative controls (recall attempt #3, the precision half) ---
    # Over-hyped techniques that did NOT durably win — the §8/universe fizzles with arXiv (cond-mat)
    # coverage. They exist to test whether the sharp leading channel (talent-inflow) STAYS SILENT on
    # losers, not just whether it fires on winners. A channel that fires on these too is just noise
    # (the cross-field-diffusion failure mode). Tracked like any term; flagged as controls downstream.
    "graphene", "carbon nanotube", "quantum dot", "dna computing",
]

# A deliberately-flat control phrase that should NOT accelerate — a cry-wolf guard at the signal layer
# (mirrors frontier's synthetic control, but on real data: a generic word with steady usage).
# (Not a separate code path — it flows as one more term; we only note it so a fire here is a warning.)

_TERM_RE: dict[str, re.Pattern] = {
    t: re.compile(r"\b" + re.escape(t) + r"\b", re.IGNORECASE) for t in TERMS
}

_STATE_PATH = db.REPO_ROOT / "data" / "harvest_state.json"


# --- HTTP (stdlib only — no new dependency; CONSTITUTION rule 5) --------------


def _oai_get(params: dict, *, timeout: int = 60, max_retries: int = 5, log=print) -> str:
    """GET the OAI endpoint, honoring 503 Retry-After + polite backoff. Returns the XML body."""
    url = f"{OAI}?" + urllib.parse.urlencode(params)
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 keyless public endpoint
                return resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 503:  # OAI's "come back later" — respect Retry-After (arXiv asks for this)
                wait = int(e.headers.get("Retry-After", "20"))
                log(f"    · 503 (flow control) — waiting {wait}s")
                time.sleep(wait)
                continue
            if attempt < max_retries:
                time.sleep(3.0 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt < max_retries:
                time.sleep(3.0 * (attempt + 1))
                continue
            raise
    raise RuntimeError("OAI request exhausted retries")


# --- harvest (gapless full-set, resumptionToken-paginated) --------------------


def _text(el, path: str) -> str:
    node = el.find(path, NS)
    return (node.text or "").strip() if node is not None and node.text else ""


def _parse_record(rec) -> dict | None:
    """One OAI <record> → a paper dict (the arXiv metadata format). None if deleted/malformed."""
    header = rec.find("oai:header", NS)
    if header is not None and header.get("status") == "deleted":
        return None
    meta = rec.find("oai:metadata/arxiv:arXiv", NS)
    if meta is None:
        return None
    created = _text(meta, "arxiv:created")
    if not created:
        return None
    authors = []
    for a in meta.findall("arxiv:authors/arxiv:author", NS):
        key = _text(a, "arxiv:keyname")
        fore = _text(a, "arxiv:forenames")
        name = (fore + " " + key).strip() if fore else key
        if name:
            authors.append(name)
    cats = _text(meta, "arxiv:categories")  # space-separated
    return {
        "external_id": _text(meta, "arxiv:id"),
        "published": created,
        "updated": _text(meta, "arxiv:updated") or None,
        "primary_category": cats.split()[0] if cats else None,
        "categories": cats,
        "title": " ".join(_text(meta, "arxiv:title").split()),
        "abstract": " ".join(_text(meta, "arxiv:abstract").split()),
        "authors": "; ".join(authors),
        "n_authors": len(authors),
    }


def _load_state() -> dict:
    if _STATE_PATH.exists():
        try:
            return json.loads(_STATE_PATH.read_text())
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _save_state(state: dict) -> None:
    _STATE_PATH.write_text(json.dumps(state, indent=2))


def _upsert_papers(conn: sqlite3.Connection, papers: list[dict], *,
                   lock_retries: int = 12, log=print) -> int:
    """Idempotent bulk upsert by (provider, external_id). Returns rows written.

    Retries on 'database is locked' — this repo runs concurrent writers (cockpit, other collectors),
    and a long harvest must survive a transient lock rather than crash and lose the run (the token
    checkpoint makes a restart cheap, but not crashing is cheaper). Beyond the retries it re-raises.
    """
    now_iso = _now().isoformat()
    rows = []
    for p in papers:
        if not p["external_id"]:
            continue
        chash = hashlib.sha256(
            (p["external_id"] + p["published"] + p["title"]).encode()
        ).hexdigest()
        rows.append((
            _uid(), "arxiv", p["external_id"], p["published"], p["updated"],
            p["primary_category"], p["categories"], p["title"], p["abstract"],
            p["authors"], p["n_authors"], chash, now_iso,
        ))
    sql = (
        "INSERT INTO papers (id,provider,external_id,published,updated,primary_category,"
        "categories,title,abstract,authors,n_authors,content_hash,fetched_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(provider,external_id) DO UPDATE SET "
        "updated=excluded.updated, categories=excluded.categories, abstract=excluded.abstract"
    )
    for attempt in range(lock_retries + 1):
        try:
            conn.executemany(sql, rows)
            conn.commit()
            return len(rows)
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < lock_retries:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                wait = min(5 + attempt * 5, 45)
                log(f"    · DB busy (another writer) — retry in {wait}s ({attempt + 1}/{lock_retries})")
                time.sleep(wait)
                continue
            raise
    return len(rows)


def harvest_set(conn: sqlite3.Connection, set_spec: str, *, max_pages: int | None = None,
                resume: bool = True, log=print) -> int:
    """Harvest every record in an OAI set (gapless), paginating by resumptionToken. Resumable.

    A full set is large; if interrupted, re-running resumes from the checkpointed resumptionToken
    (tokens expire after a few hours — on expiry we restart the set, which is safe: the upsert is
    idempotent so nothing duplicates). Returns the number of records harvested this run.
    """
    state = _load_state()
    token = state.get(set_spec, {}).get("token") if resume else None
    harvested = 0
    page = 0
    log(f"  set={set_spec}: {'resuming' if token else 'starting'} OAI harvest")
    while True:
        params = ({"verb": "ListRecords", "resumptionToken": token} if token
                  else {"verb": "ListRecords", "metadataPrefix": "arXiv", "set": set_spec})
        try:
            body = _oai_get(params, log=log)
        except urllib.error.HTTPError as e:
            log(f"  ! set={set_spec} HTTP {e.code} — stopping (harvested {harvested} this run)")
            break
        try:
            root = ET.fromstring(body)
        except ET.ParseError as e:
            log(f"  ! set={set_spec} XML parse error: {e} — stopping")
            break
        err = root.find("oai:error", NS)
        if err is not None:
            code = err.get("code", "")
            if code == "badResumptionToken":  # expired — restart the set from scratch
                log(f"  · token expired for {set_spec}; restarting set")
                token = None
                state.get(set_spec, {}).pop("token", None)
                continue
            if code == "noRecordsMatch":
                log(f"  · set={set_spec}: no records")
            else:
                log(f"  ! set={set_spec} OAI error [{code}]: {(err.text or '').strip()}")
            break
        lr = root.find("oai:ListRecords", NS)
        if lr is None:
            break
        batch = [p for rec in lr.findall("oai:record", NS) if (p := _parse_record(rec))]
        harvested += _upsert_papers(conn, batch, log=log)
        page += 1
        rt = lr.find("oai:resumptionToken", NS)
        token = (rt.text or "").strip() if rt is not None and rt.text else None
        # checkpoint after every page so a resume costs at most one page of re-work
        state.setdefault(set_spec, {})["token"] = token
        state[set_spec]["harvested_total"] = state[set_spec].get("harvested_total", 0) + len(batch)
        _save_state(state)
        comp = rt.get("completeListSize") if rt is not None else None
        log(f"    page {page}: +{len(batch)} (run total {harvested}"
            + (f" / list {comp}" if comp else "") + ")")
        if not token:
            state[set_spec]["token"] = None
            state[set_spec]["completed_at"] = _now().isoformat()
            _save_state(state)
            log(f"  ✓ set={set_spec} complete ({harvested} records this run)")
            break
        if max_pages and page >= max_pages:
            log(f"  · set={set_spec} stopped at max_pages={max_pages} (resumable — token saved)")
            break
        time.sleep(3.0)  # arXiv OAI politeness (~1 request / 3s)
    return harvested


# --- signal computation (the three leading channels) --------------------------


def _month_floor(iso: str) -> str | None:
    """'YYYY-MM-DD' → 'YYYY-MM' (the month bucket), or None if unparseable / pre-window."""
    if len(iso) < 7:
        return None
    try:
        y = int(iso[:4])
    except ValueError:
        return None
    if y < WINDOW_START_YEAR:
        return None
    return iso[:7]


def _as_of(month: str) -> date:
    """'YYYY-MM' → the 1st of that month (point-in-time bucket label)."""
    y, m = int(month[:4]), int(month[5:7])
    return date(y, m, 1)


def _content_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _log_cost(conn: sqlite3.Connection, action: str, units: float) -> None:
    entry = CostLedgerEntry(action=action, provider="arxiv", units=units,
                            est_cost_cents=0, actual_cost_cents=0)
    conn.execute(
        "INSERT INTO cost_ledger (id,ts,action,provider,units,est_cost_cents,"
        "actual_cost_cents,approval_status) VALUES (?,?,?,?,?,?,?,?)",
        (entry.id, entry.ts.isoformat(), entry.action, entry.provider, entry.units, 0, 0, "auto"),
    )


def _store_series(conn: sqlite3.Connection, *, metric: str, unit: str, term: str,
                  points: dict[str, tuple[float, float]], trust: int, rationale: str,
                  domain: str | None, label_suffix: str) -> bool:
    """Create/refresh one Series + its Observations from {month: (value, uncertainty)}. Returns stored?"""
    months = sorted(points)
    if len(months) < 8:   # the detector needs ≥8 points for a trend
        return False
    payload = {m: round(points[m][0], 6) for m in months}
    last = months[-1]
    src = Source(
        url=f"{OAI}?verb=ListRecords&metadataPrefix=arXiv#term={urllib.parse.quote(term)}&metric={metric}",
        title=f"arXiv {label_suffix} — \"{term}\"",
        pillar_id=FRONTIER_PILLAR_ID, kind=SourceKind.primary, trust_score=trust,
        trust_rationale=rationale,
        recency=_as_of(last), content_hash=_content_hash(payload),
    )
    # inline upsert (mirrors frontier._upsert_source by url) ----------------------------------
    row = conn.execute("SELECT id FROM sources WHERE url = ?", (src.url,)).fetchone()
    if row:
        conn.execute(
            "UPDATE sources SET trust_score=?, trust_rationale=?, recency=?, accessed_at=?, "
            "content_hash=? WHERE id=?",
            (src.trust_score, src.trust_rationale, src.recency.isoformat(),
             src.accessed_at.isoformat(), src.content_hash, row["id"]))
        source_id = row["id"]
    else:
        conn.execute(
            "INSERT INTO sources (id,url,title,pillar_id,kind,trust_score,trust_rationale,"
            "recency,accessed_at,cost_cents,content_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (src.id, src.url, src.title, src.pillar_id, src.kind.value, src.trust_score,
             src.trust_rationale, src.recency.isoformat(), src.accessed_at.isoformat(),
             src.cost_cents, src.content_hash))
        source_id = src.id
    external_id = f"{term}|{metric}"
    s = Series(pillar_id=FRONTIER_PILLAR_ID, source_id=source_id, provider="arxiv",
               external_id=external_id, label=f"{term} ({label_suffix})", metric=metric,
               unit=unit, domain=domain)
    srow = conn.execute(
        "SELECT id FROM series WHERE provider=? AND external_id=? AND metric=?",
        ("arxiv", external_id, metric)).fetchone()
    if srow:
        conn.execute("UPDATE series SET source_id=?, label=?, unit=?, domain=? WHERE id=?",
                     (source_id, s.label, unit, domain, srow["id"]))
        series_id = srow["id"]
    else:
        conn.execute(
            "INSERT INTO series (id,pillar_id,source_id,provider,external_id,label,metric,unit,"
            "domain,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (s.id, s.pillar_id, source_id, "arxiv", external_id, s.label, metric, unit,
             domain, s.created_at.isoformat()))
        series_id = s.id
    obs = [Observation(series_id=series_id, as_of=_as_of(m), value=float(points[m][0]),
                       unit=unit, uncertainty=float(points[m][1])) for m in months]
    store.bulk_upsert_observations(conn, obs)
    return True


def build_category_series(conn: sqlite3.Connection, *, min_papers: int = 300, min_years: int = 8,
                          log=print) -> dict:
    """Mint one works_per_year COUNT series per arXiv primary_category from the papers substrate — the
    concept-pool POWER for the detector experiment (protocol_v2 widens the universe beyond ~74 OpenAlex
    concepts). Point-in-time clean: a paper's primary_category + first-submission year are fixed facts,
    stamped as_of = that year-end, so a universe draw at origin T sees only categories' counts ≤ T.
    Cohort = (arxiv, works_per_year, papers/year): 'share' is a category's slice of total arXiv output
    that year — zero-sum / rising-tide-immune, the SAME label machinery as the OpenAlex pool. $0, keyless.
    """
    rows = conn.execute(
        "SELECT primary_category cat, CAST(substr(published,1,4) AS INT) yr, COUNT(*) n "
        "FROM papers WHERE primary_category IS NOT NULL AND published IS NOT NULL "
        "AND length(published) >= 4 GROUP BY cat, yr"
    ).fetchall()
    by_cat: dict[str, dict[int, int]] = {}
    for r in rows:
        if r["yr"] and 1995 <= r["yr"] <= 2025:
            by_cat.setdefault(r["cat"], {})[r["yr"]] = r["n"]
    built = 0
    for cat, yearly in sorted(by_cat.items()):
        if sum(yearly.values()) < min_papers or len(yearly) < min_years:
            continue
        points = {f"{yr}-12": (float(n), sqrt(max(n, 1))) for yr, n in yearly.items()}
        if _store_series(
            conn, metric="works_per_year", unit="papers/year", term=cat, points=points, trust=85,
            rationale=("arXiv OAI-PMH full-set census; a paper's primary_category + first-submission "
                       "year are fixed point-in-time facts (immutable, no revision); the annual count "
                       "is a complete census of the set with Poisson √n uncertainty."),
            domain="arxiv_category", label_suffix="arXiv category works/yr",
        ):
            built += 1
    _log_cost(conn, "build_category_series", float(built))
    conn.commit()
    log(f"built {built} arXiv-category works/year series (≥{min_papers} papers, ≥{min_years} yrs; "
        f"{len(by_cat)} candidate categories)")
    return {"built": built, "candidates": len(by_cat)}


def compute_signals(conn: sqlite3.Connection, *, log=print) -> dict:
    """Derive the three leading signals (topic_share · field_breadth · talent_inflow) from `papers`.

    One streaming pass over the harvested corpus: per month we tally the total paper count and, per
    term, the matched-paper count, the set of distinct fields touched, and the set of distinct authors.
    Each becomes a normal Series the existing detector/FDR/discover funnel consumes. Recomputable any
    time from the substrate — the term list can grow without re-harvesting.
    """
    cur = _now().date()
    cutoff_month = f"{cur.year:04d}-{cur.month:02d}"  # drop the partial current month + the lag tail

    total: dict[str, int] = defaultdict(int)
    matched: dict[str, dict[str, int]] = {t: defaultdict(int) for t in TERMS}
    fields: dict[str, dict[str, set]] = {t: defaultdict(set) for t in TERMS}
    authors: dict[str, dict[str, set]] = {t: defaultdict(set) for t in TERMS}

    n_papers = 0
    for r in conn.execute("SELECT published, primary_category, title, abstract, authors FROM papers"):
        month = _month_floor(r["published"])
        if month is None or month >= cutoff_month:
            continue
        n_papers += 1
        total[month] += 1
        hay = f"{r['title']} {r['abstract']}"
        if not hay.strip():
            continue
        pcat = r["primary_category"] or "?"
        auths = r["authors"] or ""
        for t in TERMS:
            if _TERM_RE[t].search(hay):
                matched[t][month] += 1
                fields[t][month].add(pcat)
                if auths:
                    for a in auths.split(";"):
                        a = a.strip()
                        if a:
                            authors[t][month].add(a)

    if n_papers == 0:
        log("  no papers in window — harvest first (`collect-research`).")
        return {"papers": 0, "series": 0}

    # drop the trailing under-reported months from the *total* timeline too
    all_months = sorted(total)
    keep = set(all_months[:-TRAILING_MONTHS_DROPPED]) if len(all_months) > TRAILING_MONTHS_DROPPED else set(all_months)

    SHARE_RATIONALE = (
        "arXiv OAI-PMH full-set harvest (official keyless bulk protocol): monthly SHARE of the "
        "harvested corpus whose title+abstract contains the quoted technique — the emergence signal "
        "(a method's rising share, caught before its raw count saturates). Point-in-time clean: a "
        "paper's submission month is fixed, so the bucket can never look ahead. Caveats: lexical "
        "phrase match (directional, not exact); share is within the harvested seed fields, not all of "
        "science; the trailing months are dropped (indexing lag); preprints ≠ peer-reviewed.")
    BREADTH_RATIONALE = (
        "arXiv OAI-PMH: distinct primary-categories the technique's papers span per month — the "
        "cross-field DIFFUSION signal (a method crossing field A→B→C precedes its volume; the "
        "deep-learning signature). Point-in-time clean. Caveats: lexical match; bounded by the "
        "harvested seed fields; directional.")
    TALENT_RATIONALE = (
        "arXiv OAI-PMH: distinct authors publishing on the technique per month — the TALENT-inflow "
        "signal (labs/people pivoting in is an early commitment). Point-in-time clean. Caveats: "
        "author-name strings are not disambiguated (homonyms inflate counts — directional); lexical "
        "topic match; bounded by the harvested seed fields.")

    n_share = n_breadth = n_talent = 0
    skipped: list[str] = []
    for t in TERMS:
        # 1) topic_share — matched/total, binomial SE, only months we keep
        share_pts: dict[str, tuple[float, float]] = {}
        for m in matched[t]:
            if m not in keep or total[m] <= 0:
                continue
            p = matched[t][m] / total[m]
            se = max(sqrt(max(p * (1 - p), 1e-9) / total[m]), 1e-6)
            share_pts[m] = (p, se)
        if _store_series(conn, metric="topic_share", unit="fraction", term=t, points=share_pts,
                         trust=80, rationale=SHARE_RATIONALE, domain=None, label_suffix="topic share"):
            n_share += 1
        else:
            skipped.append(t)

        # 2) field_breadth — distinct primary-categories touched per month
        breadth_pts = {m: (float(len(s)), 1.0) for m, s in fields[t].items()
                       if m in keep and len(s) > 0}
        if _store_series(conn, metric="field_breadth", unit="fields", term=t, points=breadth_pts,
                         trust=75, rationale=BREADTH_RATIONALE, domain=None, label_suffix="field breadth"):
            n_breadth += 1

        # 3) talent_inflow — distinct authors per month (Poisson 1σ)
        talent_pts = {m: (float(len(s)), max(1.0, sqrt(len(s)))) for m, s in authors[t].items()
                      if m in keep and len(s) > 0}
        if _store_series(conn, metric="talent_inflow", unit="authors/month", term=t, points=talent_pts,
                         trust=70, rationale=TALENT_RATIONALE, domain=None, label_suffix="talent inflow"):
            n_talent += 1

    _log_cost(conn, "research_signals", float(len(TERMS)))
    conn.commit()
    n_series = n_share + n_breadth + n_talent
    log(f"  computed from {n_papers} papers over {len(keep)} months "
        f"({all_months[0]}–{sorted(keep)[-1] if keep else '?'}):")
    log(f"    topic_share: {n_share} · field_breadth: {n_breadth} · talent_inflow: {n_talent} series")
    if skipped:
        log(f"    (too sparse for a trend, skipped: {', '.join(skipped[:10])}"
            + (" …" if len(skipped) > 10 else "") + ")")
    return {"papers": n_papers, "series": n_series, "months": len(keep),
            "share": n_share, "breadth": n_breadth, "talent": n_talent}


def collect(conn: sqlite3.Connection | None = None, *, sets: list[str] | None = None,
            max_pages: int | None = None, signals_only: bool = False, log=print) -> dict:
    """Harvest the seed sets (gapless) then derive the three leading signals. Idempotent/resumable.

    `signals_only` skips the harvest and just (re)computes signals from whatever is already in `papers`
    (cheap — use it after editing the term list). `max_pages` bounds each set's harvest for a quick slice.
    """
    own = conn is None
    if own:
        conn = db.connect()
        db.init_db(conn)
    # This repo runs concurrent writers (other collectors, the cockpit). A long harvest must wait out
    # their transactions rather than crash on a 60s default, so we extend the busy-timeout to 5 min.
    conn.execute("PRAGMA busy_timeout=300000")
    try:
        conn.execute("UPDATE pillars SET status='in_progress' WHERE id=? AND status='untapped'",
                     (FRONTIER_PILLAR_ID,))
        conn.commit()
    except sqlite3.OperationalError:
        pass  # cosmetic status flip — never fatal to the harvest

    harvested = 0
    if not signals_only:
        target = sets or SEED_SETS
        log(f"arXiv OAI-PMH harvest — sets: {', '.join(target)} (gapless, resumable):")
        for s in target:
            harvested += harvest_set(conn, s, max_pages=max_pages, log=log)
        _log_cost(conn, "arxiv_oai_harvest", float(harvested))

    n_total = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    log(f"\narXiv corpus: {n_total} papers in `papers`. Computing leading signals:")
    sig = compute_signals(conn, log=log)
    if own:
        conn.close()
    return {"harvested": harvested, "papers_total": n_total, **sig}


# ── OPEN emergence discovery — "find from the vastness, beforehand" ────────────
# The curated TERMS list above can only CONFIRM known winners (hindsight/survivorship). To find a
# technique nobody named yet, we must scan the corpus itself for n-grams whose monthly share is
# breaking out FROM A SMALL BASE, RECENTLY (the faint early grain the bar demands), point-in-time.
# Two passes: (1) over a recent window ≤ as_of, find candidate phrases frequent ENOUGH to be real;
# (2) over full history ≤ as_of, build each candidate's monthly share and score the break. No look-
# ahead: every month bucketed by fixed submission date, and `as_of` hard-caps what is read. $0.

# Generic academic + English filler — dropped so n-grams are technical content, NOT "we propose that".
# Deliberately does NOT include model/network/learning/neural/etc. (those ARE the signal).
_STOP = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "with", "by", "as", "at", "from",
    "is", "are", "be", "been", "this", "that", "these", "those", "we", "our", "it", "its", "their",
    "can", "may", "such", "than", "then", "thus", "also", "however", "which", "where", "when", "while",
    "into", "via", "using", "used", "use", "based", "show", "shows", "shown", "present", "presented",
    "propose", "proposed", "proposes", "paper", "study", "studies", "result", "results", "method",
    "methods", "approach", "approaches", "framework", "algorithm", "algorithms", "performance",
    "experiment", "experiments", "experimental", "dataset", "datasets", "task", "tasks", "problem",
    "problems", "novel", "new", "two", "three", "one", "first", "second", "high", "low", "large",
    "small", "given", "work", "analysis", "between", "over", "under", "more", "most", "many", "both",
    "each", "all", "any", "some", "non", "well", "good", "better", "best", "different", "various",
    "several", "recent", "recently", "general", "specific", "important", "significant", "significantly",
    "obtain", "obtained", "achieve", "achieved", "achieves", "improve", "improved", "improves", "able",
    "find", "found", "consider", "considered", "provide", "provides", "provided", "called", "etc",
    "respectively", "namely", "due", "order", "terms", "case", "cases", "set", "sets", "number",
    "value", "values", "function", "functions", "system", "systems", "data", "time", "space", "state",
    # abstract boilerplate + LaTeX-command artifacts the tokenizer would otherwise pair up.
    # NB: "gap" is kept (real term "band gap"); only clear filler/LaTeX is dropped.
    "report", "observation", "observations", "broad", "wide", "bridge", "baseline",
    "langle", "rangle", "mathcal", "mathbb", "mathbf", "mathrm", "textit", "textbf", "left", "right",
    "begin", "end", "let", "denote", "denotes", "respect", "leq", "geq", "cdot", "ldots",
}
_WORD_RE = re.compile(r"[a-z][a-z][a-z\-]+")  # ≥3-letter alphabetic tokens (drops numbers/symbols)


def _content_tokens(text: str) -> list[str]:
    return [w for w in _WORD_RE.findall(text.lower()) if w not in _STOP]


def _paper_ngrams(text: str) -> set[str]:
    """Bigrams + trigrams of adjacent content words, deduped within a paper (so a count = #papers)."""
    toks = _content_tokens(text)
    out: set[str] = set()
    for i in range(len(toks) - 1):
        out.add(toks[i] + " " + toks[i + 1])
    for i in range(len(toks) - 2):
        out.add(toks[i] + " " + toks[i + 1] + " " + toks[i + 2])
    return out


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def discover_emerging(conn: sqlite3.Connection, *, as_of: str | None = None, recent_months: int = 18,
                      window: int = 12, min_recent: int = 40, cap_candidates: int = 6000,
                      max_recent_share: float = 0.03, top_n: int = 40, log=print) -> list[dict]:
    """Open, point-in-time emergence scan: rank n-grams breaking out from a small base, recently.

    `as_of` = 'YYYY-MM' hard cap (None = now). Returns ranked dicts {term, recent, prior, older, v,
    accel, recent_count, score, spark}. Score rewards a large RELATIVE share jump (recent/prior) with
    enough volume, gated to STILL-SMALL share (≤ max_recent_share) so already-priced big topics drop
    out — the pre-consensus filter. Read-only.
    """
    import math
    cur = _now().date()
    cutoff = as_of or f"{cur.year:04d}-{cur.month:02d}"   # exclusive upper bound (month string compare)

    def _ym_minus(ym: str, k: int) -> str:
        y, m = int(ym[:4]), int(ym[5:7])
        idx = y * 12 + (m - 1) - k
        return f"{idx // 12:04d}-{idx % 12 + 1:02d}"

    recent_lo = _ym_minus(cutoff, recent_months)

    # Pass 1 — candidate phrases frequent enough in the RECENT window (this is what makes it tractable
    # AND targets "rising now": an emerging term is frequent recently but was not before).
    log(f"  open scan as_of {cutoff}: pass 1 (recent window {recent_lo}..{cutoff}) …")
    recent_counts: dict[str, int] = {}
    seen_recent = 0
    for r in conn.execute(
        "SELECT title, abstract FROM papers WHERE substr(published,1,7) >= ? AND substr(published,1,7) < ?",
        (recent_lo, cutoff),
    ):
        seen_recent += 1
        for ng in _paper_ngrams(f"{r['title']} {r['abstract']}"):
            recent_counts[ng] = recent_counts.get(ng, 0) + 1
    candidates = {ng for ng, c in recent_counts.items() if c >= min_recent}
    if len(candidates) > cap_candidates:
        candidates = set(sorted(candidates, key=lambda g: recent_counts[g], reverse=True)[:cap_candidates])
    log(f"    {seen_recent} recent papers → {len(candidates)} candidate phrases (≥{min_recent} recent)")

    # Pass 2 — full history ≤ as_of: monthly total + matched-per-candidate (one streaming pass).
    log(f"  pass 2 (full history <{cutoff}) over the candidate set …")
    total: dict[str, int] = {}
    matched: dict[str, dict[str, int]] = {ng: {} for ng in candidates}
    seen_all = 0
    for r in conn.execute(
        "SELECT substr(published,1,7) m, title, abstract FROM papers "
        "WHERE substr(published,1,7) >= '2010-01' AND substr(published,1,7) < ?",
        (cutoff,),
    ):
        m = r["m"]
        total[m] = total.get(m, 0) + 1
        seen_all += 1
        for ng in _paper_ngrams(f"{r['title']} {r['abstract']}") & candidates:
            d = matched[ng]
            d[m] = d.get(m, 0) + 1

    # Score each candidate by its point-in-time break (relative jump × volume, gated to still-small).
    months_desc = sorted(total, reverse=True)
    w_recent = months_desc[:window]
    w_prior = months_desc[window:2 * window]
    w_older = months_desc[2 * window:3 * window]

    def share(d: dict[str, int], ms: list[str]) -> float:
        vals = [d.get(m, 0) / total[m] for m in ms if total.get(m)]
        return _mean(vals)

    eps = 1e-5
    out = []
    for ng in candidates:
        d = matched[ng]
        recent = share(d, w_recent)
        prior = share(d, w_prior)
        older = share(d, w_older)
        recent_count = sum(d.get(m, 0) for m in w_recent)
        v = recent - prior
        accel = (recent - prior) - (prior - older)
        if recent_count < min_recent or recent > max_recent_share or v <= 0 or accel < 0:
            continue
        score = math.log((recent + eps) / (prior + eps)) * math.log1p(recent_count)
        out.append({"term": ng, "recent": recent, "prior": prior, "older": older, "v": v,
                    "accel": accel, "recent_count": recent_count, "score": score})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:top_n]
