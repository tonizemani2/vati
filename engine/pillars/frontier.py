"""Pillar 1 — Frontier collector (free / keyless).

What's becoming newly possible, read as the *velocity* of science. We turn each frontier
concept into a point-in-time series: works published per year. The detector (engine/detector.py)
then asks the only question that matters here — is it *accelerating* beyond its own noise floor?

Sources, in trust order:
  • OpenAlex (REST, keyless polite pool) — the spine. An open scholarly graph (250M+ works)
    with normalized concepts and per-year work counts. High trust: open methodology, transparent
    coverage, no login/ToS wall. Each concept's works-by-year query is one point-in-time Source.
  • NIH RePORTER (REST, keyless POST) — biomedical grant *count* per topic per fiscal year.
    Authoritative US gov source; biomedical-only (NSF, the physical-science complement, is a
    logged gap: it exposes no cheap total-count endpoint so per-year counts need full pagination).
  • Epoch AI (public CSV, keyless) — per-domain frontier (max) training-compute FLOP by year:
    the canonical capability-acceleration curve. Compute figures are estimates (~0.3 dex).
  • arXiv (REST, keyless) — wired end-to-end (current totals per category). The legacy API's
    submittedDate faceting is unreliable, so per-year arXiv *history* is a logged Mendeleev gap
    (execution.md §2 Pillar 1) awaiting a better aggregate (e.g. the arXiv monthly stats dump).
  • Google Patents (public XHR JSON, keyless) — patent filing velocity per phrase per priority
    year. LOW trust by design: PatentsView's free API went key-gated/unreachable and USPTO's open
    APIs were down at build (2026-06-02), so this undocumented/ToS-grey endpoint is the only
    keyless patent feed reachable; fuzzy full-text matching + an ~18mo publication lag (see Source).

Cost: $0. Every run still logs a cost-ledger entry (approval_status=auto) so the gate is
exercised, not bypassed (CONSTITUTION rule 3).

Reasoning stays in-session (Claude); this module only *collects and stores* — no LLM calls.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from math import sqrt

from engine import db
from engine.schemas import (
    CostLedgerEntry,
    Observation,
    Series,
    Source,
    SourceKind,
    _now,
)

FRONTIER_PILLAR_ID = 1

# Polite-pool identification (keyless). The mailto puts us in OpenAlex's faster, free pool.
MAILTO = "ruben.stout@edu.escp.eu"
UA = f"predictthefuture/0.1 (mailto:{MAILTO})"
OPENALEX = "https://api.openalex.org"
ARXIV = "https://export.arxiv.org/api/query"

# Point-in-time window. Recent years are under-indexed and OpenAlex reports erratic
# near-future counts (preprints dated ahead), so we cap at the last reliably-complete year.
WINDOW_START = 2000
CUTOFF_YEAR = 2024

# The frontier we sweep. Domain-spanning so the detector proves it is domain-agnostic.
# We resolve each term to an OpenAlex concept at runtime; PINS override the cases where
# free-text search picks a wrong/niche concept (GIGO: we must know what we're measuring).
TERMS: list[str] = [
    "deep learning", "reinforcement learning", "natural language processing",
    "computer vision", "generative adversarial network", "graph neural network",
    "large language model", "diffusion model", "self-supervised learning", "transfer learning",
    "lithium ion battery", "solid state battery", "photovoltaic", "perovskite solar cell",
    "wind power", "hydrogen fuel", "nuclear fusion", "solid oxide fuel cell",
    "quantum computing", "quantum error correction", "superconductivity",
    "semiconductor device", "gallium nitride", "photonics", "neuromorphic computing",
    "crispr gene editing", "gene therapy", "messenger rna", "protein folding",
    "synthetic biology", "single cell rna sequencing", "cancer immunotherapy",
    "antibody engineering", "organoid", "microbiome",
    "graphene", "carbon nanotube", "metamaterial",
    "autonomous driving", "robotics", "additive manufacturing", "drone",
    "satellite constellation", "brain computer interface", "augmented reality",
    "internet of things", "edge computing", "federated learning", "blockchain",
    "direct air capture", "carbon sequestration", "desalination", "heat pump",
    "wearable sensor", "solid electrolyte",
    # second sweep — broaden past 50 distinct concepts
    "supercapacitor", "thermoelectric material", "metal organic framework", "quantum dot",
    "electrocatalysis", "geothermal energy", "biofuel", "stem cell", "nanoparticle",
    "knowledge graph", "speech recognition", "object detection", "anomaly detection",
    "machine translation", "tokamak", "5g", "microfluidics", "exoskeleton",
]

# The laggard pool — technologies a 2010 observer would call hyped/established-but-uncertain that
# then plateaued or faded. They are the backtest's *true negatives*: without genuine non-winners,
# a 72%-base-rate universe makes "predicting a winner" nearly free. These enter the same blind
# universe (tagged domain="laggard"); the tag is only our prior — if one actually accelerated, the
# backtest counts it as a winner, no relabeling. We never trim the set to look flat.
DUD_TERMS: list[str] = [
    "rfid", "wimax", "near field communication", "semantic web", "grid computing",
    "expert system", "fuzzy logic", "peer to peer computing", "memristor", "spintronics",
    "dna computing", "plasma display", "stereoscopic 3d display", "personal digital assistant",
    "cold fusion", "agent based model",
]

# term -> OpenAlex concept id, where free-text search resolves to the wrong concept.
# (Each id verified against /concepts/{id} before baking — GIGO: know what you measure.)
PINS: dict[str, str] = {
    "messenger rna": "C105580179",          # Messenger RNA (not "Gene" / "Subgenomic mRNA")
    "robotics": "C34413123",                # Robotics (not "George (robot)")
    "quantum computing": "C5320026",        # Quantum information science (broad, not a sub-niche)
    "heat pump": "C2776461528",             # Heat pump (not "Refrigerant")
    "synthetic biology": "C191908910",      # Synthetic biology
}

# Concepts we never want even if search returns them (mis-resolutions seen in vetting).
BLOCK: set[str] = {"C67101536", "C512567305", "C199499590"}  # George(robot), Life extension, Refrigerant


# --- HTTP (stdlib only — no new dependency; CONSTITUTION rule 5) --------------


def _get_json(url: str, *, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _get_text(url: str, *, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def _post_json(url: str, payload: dict, *, timeout: int = 30) -> dict:
    """POST a JSON body (NIH RePORTER's search API takes one). Keyless."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"User-Agent": UA, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


# --- OpenAlex -----------------------------------------------------------------


def resolve_concept(term: str) -> dict | None:
    """Resolve a free-text term to one OpenAlex concept (pinned id wins; else best of top-5)."""
    if term in PINS:
        cid = PINS[term]
        data = _get_json(f"{OPENALEX}/concepts/{cid}?select=id,display_name,level,works_count&mailto={MAILTO}")
        return {"id": cid, "display_name": data["display_name"], "level": data["level"]}
    q = urllib.parse.quote(term)
    url = f"{OPENALEX}/concepts?search={q}&per_page=5&select=id,display_name,level,works_count&mailto={MAILTO}"
    results = _get_json(url).get("results", [])
    results = [c for c in results if c["id"].split("/")[-1] not in BLOCK]
    if not results:
        return None
    cand = [c for c in results if 1 <= c["level"] <= 3] or results
    best = max(cand, key=lambda c: c["works_count"])
    return {"id": best["id"].split("/")[-1], "display_name": best["display_name"], "level": best["level"]}


def works_by_year(concept_id: str) -> dict[int, int]:
    """Return {year: work_count} for a concept, clamped to the point-in-time window."""
    url = f"{OPENALEX}/works?filter=concepts.id:{concept_id}&group_by=publication_year&mailto={MAILTO}"
    groups = _get_json(url).get("group_by", [])
    out: dict[int, int] = {}
    for g in groups:
        try:
            year = int(g["key"])
        except (TypeError, ValueError):
            continue
        if WINDOW_START <= year <= CUTOFF_YEAR:
            out[year] = int(g["count"])
    return out


# --- storage (validated through the Pydantic models — GIGO gate) --------------


def _content_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _upsert_source(conn: sqlite3.Connection, src: Source) -> str:
    """Insert a Source if its (url) isn't already present; return the id used."""
    row = conn.execute("SELECT id FROM sources WHERE url = ?", (src.url,)).fetchone()
    if row:
        conn.execute(
            "UPDATE sources SET trust_score=?, trust_rationale=?, recency=?, accessed_at=?, "
            "content_hash=? WHERE id=?",
            (src.trust_score, src.trust_rationale,
             src.recency.isoformat() if src.recency else None,
             src.accessed_at.isoformat(), src.content_hash, row["id"]),
        )
        return row["id"]
    conn.execute(
        "INSERT INTO sources (id,url,title,pillar_id,kind,trust_score,trust_rationale,"
        "recency,accessed_at,cost_cents,content_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (src.id, src.url, src.title, src.pillar_id, src.kind.value, src.trust_score,
         src.trust_rationale, src.recency.isoformat() if src.recency else None,
         src.accessed_at.isoformat(), src.cost_cents, src.content_hash),
    )
    return src.id


def _upsert_series(conn: sqlite3.Connection, s: Series) -> str:
    row = conn.execute(
        "SELECT id FROM series WHERE provider=? AND external_id=? AND metric=?",
        (s.provider, s.external_id, s.metric),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE series SET source_id=?, label=?, unit=?, domain=? WHERE id=?",
            (s.source_id, s.label, s.unit, s.domain, row["id"]),
        )
        return row["id"]
    conn.execute(
        "INSERT INTO series (id,pillar_id,source_id,provider,external_id,label,metric,unit,"
        "domain,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (s.id, s.pillar_id, s.source_id, s.provider, s.external_id, s.label, s.metric,
         s.unit, s.domain, s.created_at.isoformat()),
    )
    return s.id


def _upsert_observation(conn: sqlite3.Connection, o: Observation) -> None:
    """Upsert one observation through the revision-logging path (point-in-time integrity, A6).

    Kept as the module's public helper (retro.py / entity.py import it); delegates to engine.store
    so a re-collection that CHANGES a historical value appends the old value to the revision log
    instead of silently destroying it.
    """
    from engine import store
    store.upsert_observation(conn, o)


def _log_cost(conn: sqlite3.Connection, action: str, provider: str, units: float) -> None:
    """Free/keyless work still hits the ledger at $0 with approval_status=auto (rule 3)."""
    entry = CostLedgerEntry(action=action, provider=provider, units=units,
                            est_cost_cents=0, actual_cost_cents=0)
    conn.execute(
        "INSERT INTO cost_ledger (id,ts,action,provider,units,est_cost_cents,"
        "actual_cost_cents,approval_status) VALUES (?,?,?,?,?,?,?,?)",
        (entry.id, entry.ts.isoformat(), entry.action, entry.provider, entry.units,
         0, 0, "auto"),
    )


# --- collectors ---------------------------------------------------------------


def collect_openalex(conn: sqlite3.Connection, *, terms: list[str] = TERMS,
                     domain: str | None = None, log=print) -> tuple[int, int]:
    """Resolve `terms` → concepts, store works-by-year series. Returns (n_series, n_obs).

    `domain` tags the resulting series (e.g. "laggard" for the dud control pool); the path is
    otherwise identical, so duds enter the same universe blind — only labelled, never grouped.
    """
    calls = 0
    n_series = n_obs = 0
    seen: set[str] = set()
    for term in terms:
        try:
            concept = resolve_concept(term)
            calls += 1
        except urllib.error.URLError as e:
            log(f"  ! resolve failed for {term!r}: {e}")
            continue
        if not concept or concept["id"] in seen:
            continue
        cid = concept["id"]
        seen.add(cid)
        try:
            counts = works_by_year(cid)
            calls += 1
        except urllib.error.URLError as e:
            log(f"  ! works failed for {term!r}: {e}")
            continue
        if len(counts) < 5:  # need enough points for a trend; skip sparse concepts
            log(f"  - skip {concept['display_name']} (only {len(counts)} yrs)")
            continue

        years = sorted(counts)
        payload = {str(y): counts[y] for y in years}
        last_year = years[-1]
        query_url = f"{OPENALEX}/works?filter=concepts.id:{cid}&group_by=publication_year"
        src = Source(
            url=query_url,
            title=f"OpenAlex works/year — {concept['display_name']}",
            pillar_id=FRONTIER_PILLAR_ID,
            kind=SourceKind.primary,
            trust_score=85,
            trust_rationale=(
                "OpenAlex: open scholarly graph, transparent methodology and coverage, "
                "no login/ToS wall; normalized concept counts. Caveat: recent years under-indexed "
                f"(capped at {CUTOFF_YEAR}); concept assignment is automated, so counts are "
                "directional, not exact."
            ),
            recency=date(last_year, 12, 31),
            content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=FRONTIER_PILLAR_ID, source_id=source_id, provider="openalex",
            external_id=cid, label=concept["display_name"], metric="works_per_year",
            unit="works/year", domain=domain,
        )
        series_id = _upsert_series(conn, series)
        n_series += 1
        for y in years:
            count = counts[y]
            obs = Observation(
                series_id=series_id, as_of=date(y, 12, 31), value=float(count),
                unit="works/year", uncertainty=max(1.0, sqrt(count)),  # Poisson 1σ on counts
            )
            _upsert_observation(conn, obs)
            n_obs += 1
        log(f"  + {concept['display_name']:<34} {years[0]}–{last_year}  "
            f"{counts[years[0]]}→{counts[last_year]}")

    _log_cost(conn, "openalex_collect", "openalex", float(calls))
    conn.commit()
    return n_series, n_obs


# --- cross-field diffusion (the ORTHOGONAL early channel) ---------------------
# The diagnosed blind spot (goal.md #2): the system predicted off ONE coarse channel — annual
# works-counts. The alpha lives earlier and finer. A general-purpose technique spreads ACROSS
# fields before its aggregate count saturates (deep learning crossed from CS into vision, speech,
# then medicine/biology years before its raw count exploded). So we add a second, orthogonal series
# per concept: the inverse-Simpson EFFECTIVE NUMBER OF FIELDS its works span each year — breadth,
# not volume. 1 = sits in one field; higher = spreading. Top-weighted (squared shares), so it
# tracks genuine diffusion rather than the rare-field tail that merely grows with work-count.
# Point-in-time clean (a work's publication year + field are fixed facts — unlike citations, which
# accrue future and would poison the no-look-ahead guarantee). Keyless OpenAlex group_by, $0.


def _field_simpson(cid: str, year: int) -> tuple[float, int] | None:
    """Inverse-Simpson effective number of OpenAlex fields for `cid`'s works in `year`: 1/Σ(shareᵢ²)
    over the 26-field primary-topic distribution. Returns (effective_fields, total_works), or None
    on error/empty. One keyless group_by call."""
    url = (f"{OPENALEX}/works?filter=concepts.id:{cid},publication_year:{year}"
           f"&group_by=primary_topic.field.id&mailto={MAILTO}")
    try:
        groups = _get_json(url).get("group_by", [])
    except urllib.error.URLError:
        return None
    counts = [int(g["count"]) for g in groups
              if g.get("key") not in (None, "unknown", "")]
    total = sum(counts)
    if total <= 0:
        return None
    sq = sum((c / total) ** 2 for c in counts)
    return (1.0 / sq if sq > 0 else 1.0, total)


def collect_diffusion(conn: sqlite3.Connection, *, log=print) -> int:
    """Build a point-in-time cross-field-diffusion series for every existing OpenAlex concept.

    Iterates the works series already in the DB (so the diffusion series shares the concept id and
    the laggard tag — duds enter identically, only labelled), queries the field distribution per
    year, stores the inverse-Simpson effective-field-count. The universe bench then runs the SAME
    frozen detector on this channel and OR-combines it with the count channel. Keyless, $0.
    """
    rows = conn.execute(
        "SELECT id, external_id, label, domain FROM series "
        "WHERE provider='openalex' AND metric='works_per_year' ORDER BY label"
    ).fetchall()
    calls = 0
    n_series = 0
    for r in rows:
        cid, label, domain = r["external_id"], r["label"], r["domain"]
        years = [int(x["y"]) for x in conn.execute(
            "SELECT CAST(strftime('%Y', as_of) AS INT) y FROM observations "
            "WHERE series_id=? ORDER BY y", (r["id"],))]
        vals: dict[int, tuple[float, int]] = {}
        for y in years:
            res = _field_simpson(cid, y)
            calls += 1
            if res is not None:
                vals[y] = res
            time.sleep(0.1)                      # polite pacing on the keyless pool
        if len(vals) < 5:                        # need enough points for a trend
            log(f"  - skip {label} (only {len(vals)} diffusion yrs)")
            continue
        ys = sorted(vals)
        payload = {str(y): round(vals[y][0], 3) for y in ys}
        src = Source(
            url=f"{OPENALEX}/works?filter=concepts.id:{cid}&group_by=primary_topic.field.id",
            title=f"OpenAlex cross-field diffusion — {label}",
            pillar_id=FRONTIER_PILLAR_ID, kind=SourceKind.primary, trust_score=75,
            trust_rationale=(
                "OpenAlex primary-topic field distribution (26 fields) → inverse-Simpson effective-"
                "field-count per year: an ORTHOGONAL early signal (breadth of adoption, not volume). "
                "Trust 75: field assignment is automated and diversity is volume-biased at low work "
                "counts (named confound) — directional. Point-in-time: only works published ≤ the "
                "year are ever counted, so no look-ahead."
            ),
            recency=date(ys[-1], 12, 31), content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=FRONTIER_PILLAR_ID, source_id=source_id, provider="openalex",
            external_id=cid, label=label, metric="field_diffusion",
            unit="effective_fields", domain=domain,
        )
        series_id = _upsert_series(conn, series)
        n_series += 1
        for y in ys:
            d, total = vals[y]
            _upsert_observation(conn, Observation(
                series_id=series_id, as_of=date(y, 12, 31), value=float(d),
                unit="effective_fields", uncertainty=max(0.05, d / sqrt(total)),
            ))
        log(f"  + {label:<32} {ys[0]}–{ys[-1]}  "
            f"{payload[str(ys[0])]}→{payload[str(ys[-1])]} eff-fields")
    _log_cost(conn, "diffusion_collect", "openalex", float(calls))
    conn.commit()
    return n_series


# arXiv categories we touch (current totals only — see module docstring on the history gap).
ARXIV_CATS: dict[str, str] = {
    "cs.LG": "Machine Learning", "cs.AI": "Artificial Intelligence",
    "cs.CL": "Computation & Language", "cs.CV": "Computer Vision",
    "quant-ph": "Quantum Physics", "cond-mat.supr-con": "Superconductivity",
    "q-bio.BM": "Biomolecules", "eess.SY": "Systems & Control",
}


def _arxiv_total(cat: str) -> int | None:
    import re
    url = f"{ARXIV}?" + urllib.parse.urlencode({"search_query": f"cat:{cat}", "max_results": 1})
    try:
        text = _get_text(url, timeout=20)
    except OSError:  # URLError, TimeoutError, connection resets — arXiv is flaky, degrade quietly
        return None
    m = re.search(r"<opensearch:totalResults[^>]*>(\d+)<", text)
    return int(m.group(1)) if m else None


def collect_arxiv(conn: sqlite3.Connection, *, log=print) -> int:
    """Wire arXiv end-to-end: one current-total observation per category. Returns n_series."""
    n_series = 0
    today = _now().date()
    for cat, name in ARXIV_CATS.items():
        total = _arxiv_total(cat)
        if total is None:
            log(f"  ! arxiv {cat} unreachable")
            continue
        src = Source(
            url=f"{ARXIV}?search_query=cat:{cat}",
            title=f"arXiv {cat} ({name}) — cumulative submissions",
            pillar_id=FRONTIER_PILLAR_ID,
            kind=SourceKind.primary,
            trust_score=80,
            trust_rationale=(
                "arXiv: primary preprint repository, author-submitted, no paywall. High trust for "
                "existence/volume; per-year history not used (legacy API submittedDate faceting is "
                "unreliable — logged as a Mendeleev gap)."
            ),
            recency=today,
            content_hash=_content_hash({"cat": cat, "total": total}),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=FRONTIER_PILLAR_ID, source_id=source_id, provider="arxiv",
            external_id=cat, label=f"arXiv {cat} ({name})", metric="cumulative_submissions",
            unit="submissions", domain=None,
        )
        series_id = _upsert_series(conn, series)
        _upsert_observation(conn, Observation(
            series_id=series_id, as_of=today, value=float(total), unit="submissions",
            uncertainty=0.0,  # an exact reported total, not a sampled estimate
        ))
        n_series += 1
        log(f"  + arXiv {cat:<18} {name:<26} total={total}")
    _log_cost(conn, "arxiv_collect", "arxiv", float(len(ARXIV_CATS)))
    conn.commit()
    return n_series


# --- Patents — Google Patents (public XHR JSON, keyless) ----------------------
# PatentsView's free API went key-gated/DNS-unreachable and USPTO's open APIs were down
# at build time (2026-06-02). Google Patents' public query endpoint is the only keyless
# patent feed we could reach — it is undocumented/ToS-grey, hence the low trust score and
# the caveats baked into the Source rationale.

GPATENTS = "https://patents.google.com/xhr/query"
GPATENTS_UA = f"Mozilla/5.0 (predictthefuture research; mailto:{MAILTO})"
PATENT_WINDOW_START = 2006
PATENT_CUTOFF_YEAR = 2023  # ~18-mo publication lag → cap at the last reliably-complete priority
                          # year (extended 2021→2023 in 2026 now the lag on those years has cleared)

# Quoted phrases — we measure the literal phrase in patent full-text (know what we measure).
PATENT_TOPICS: list[str] = [
    "solid state battery", "perovskite solar cell", "lithium ion battery",
    "crispr", "mrna vaccine", "gene therapy",
    "quantum computing", "neural network", "autonomous driving", "solid electrolyte",
    # widened (proxy patents, Ruben-authorized): patent filing-velocity as a LEADING capital/capability
    # signal for the live forward-card theses. Phrases chosen unambiguous + old enough to clear the
    # ≥8-year gate (2024+ omitted — the ~18mo publication lag would under-report, PATENT_CUTOFF_YEAR).
    "uranium enrichment",        # nuclear-restart thesis (enrichment/SWU bottleneck)
    "rare earth magnet",         # ai_power / EV motor thesis (rare-earth concentration)
    "high bandwidth memory",     # AI-memory / mixture-of-experts thesis (HBM, Micron)
    "semiconductor packaging",   # advanced packaging / CoWoS (the elastic compute layer)
    "power transformer",         # ai_power grid-interconnect bottleneck
    "solid rocket motor",        # re-armament / energetics thesis (defense)
    "sodium ion battery",        # the lithium substitute (elasticity check)
    "electrolyzer",              # hydrogen-economy thesis
    "fuel cell",                 # hydrogen (high-volume corroborator)
    "heat pump",                 # electrification / demand
]


def _gpatents_count(phrase: str, year: int, *, retries: int = 2,
                    proxy_provider: str | None = None) -> int | None:
    """Worldwide patents/applications matching the quoted phrase, by priority year.

    Google rate-limits/blocks bare datacenter+repeat IPs, so when a proxy is configured we route
    through it (httpx; a fresh rotating IP per call dodges the per-IP limit — execution.md §6, now
    wired). Without a proxy we fall back to a direct urllib call with backoff, degrading quietly.
    """
    quoted = urllib.parse.quote(f'"{phrase}"')
    inner = f"q={quoted}&before=priority:{year + 1}0101&after=priority:{year}0101"
    url = f"{GPATENTS}?url={urllib.parse.quote(inner)}&exp="
    for attempt in range(retries + 1):
        try:
            if proxy_provider:
                import httpx
                from engine.adapters import proxy as _proxy
                with httpx.Client(proxy=_proxy.proxy_url(proxy_provider), timeout=30,
                                  headers={"User-Agent": GPATENTS_UA}) as cl:
                    data = cl.get(url).json()
            else:
                req = urllib.request.Request(url, headers={"User-Agent": GPATENTS_UA})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.load(resp)
            total = data.get("results", {}).get("total_num_results")
            return int(total) if isinstance(total, int) else None
        except Exception:  # noqa: BLE001 — 503 / proxy / parse: degrade quietly, retry then None
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            return None


def collect_patents(conn: sqlite3.Connection, *, log=print) -> int:
    """Patent filing velocity per topic per priority year (Google Patents). Returns n_series.

    The endpoint hard-rate-limits an IP after sustained bulk use (503 on every call until it
    cools off). A canary call short-circuits the whole collector in that state — fast + honest
    (never grind 160 doomed calls). The blessed fix for reliable bulk is an orca proxy through
    the cost gate (Ruben, 2026-06-02; execution.md §6), wired when patents earns that spend.
    """
    from engine.adapters import proxy as _proxy
    # Google blocks DC+repeat IPs; prefer the residential proxy (Evomi), else DC (Floxy), else direct.
    prov = "evomi" if _proxy.available("evomi") else ("floxy" if _proxy.available("floxy") else None)
    _log_cost(conn, "gpatents_collect", f"google_patents{'+'+prov if prov else ''}",
              float(len(PATENT_TOPICS)))
    if _gpatents_count(PATENT_TOPICS[0], PATENT_CUTOFF_YEAR, proxy_provider=prov) is None:
        log(f"  ! Google Patents unreachable ({'via '+prov if prov else 'direct, no proxy'}) — "
            f"skipping patents this run. 0 series.")
        conn.commit()
        return 0
    log(f"  · patents via {prov or 'direct'} (rotating IP per call)")
    years = list(range(PATENT_WINDOW_START, PATENT_CUTOFF_YEAR + 1))
    n_series = 0
    for phrase in PATENT_TOPICS:
        counts: dict[int, int] = {}
        for y in years:
            c = _gpatents_count(phrase, y, proxy_provider=prov)
            if c is not None:
                counts[y] = c
            time.sleep(0.3 if prov else 0.6)  # proxy rotation eases the per-IP limit
        if len(counts) < 8:  # detector needs ≥8 points; don't store a stub (never silent-cap)
            log(f"  - skip patents {phrase!r} ({len(counts)} yrs returned)")
            continue
        ys = sorted(counts)
        last = ys[-1]
        payload = {str(y): counts[y] for y in ys}
        src = Source(
            url=f"{GPATENTS}?url=q%3D{urllib.parse.quote(chr(34) + phrase + chr(34))}",
            title=f'Google Patents — "{phrase}" filings/priority-year',
            pillar_id=FRONTIER_PILLAR_ID, kind=SourceKind.primary,
            trust_score=55,
            trust_rationale=(
                "Google Patents public XHR JSON endpoint (keyless): worldwide patents/"
                "applications counted by priority year for the quoted phrase. Caveats: "
                "undocumented/ToS-grey endpoint (may break without notice); full-text phrase "
                "matching is fuzzy (directional, not exact); recent priority years under-report "
                f"due to the ~18-month publication lag (capped at {PATENT_CUTOFF_YEAR})."
            ),
            recency=date(last, 12, 31),
            content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=FRONTIER_PILLAR_ID, source_id=source_id, provider="google_patents",
            external_id=phrase, label=f"{phrase} (patents)",
            metric="patents_per_priority_year", unit="patents/year", domain=None,
        )
        series_id = _upsert_series(conn, series)
        for y in ys:
            _upsert_observation(conn, Observation(
                series_id=series_id, as_of=date(y, 12, 31), value=float(counts[y]),
                unit="patents/year", uncertainty=max(1.0, sqrt(counts[y])),  # Poisson 1σ
            ))
        n_series += 1
        log(f"  + {phrase:<24} patents {ys[0]}–{last}  {counts[ys[0]]}→{counts[last]}")
    conn.commit()
    return n_series


# --- Citation velocity — Semantic Scholar graph (keyless, via Floxy DC) -------
# The ORTHOGONAL leading channel (the recall fix, execution.md §3). The annual publication-count
# curve is structurally blind to an EARLY move: it called deep learning silent at 2010 and missed
# AI-compute at 2017. The leading signal is not "how many papers" (attention/decoy) but "how fast
# the field starts BUILDING ON its foundational corpus" — citations RECEIVED per year by the
# seminal papers. That accelerates years before the paper-count explosion (a 2009 deep-learning
# paper's uptake ran 2011:16 → 2013:103 → 2015:334, point-in-time honest: a citation received in
# year y is a fact knowable at end of y). OpenAlex couldn't give this (concept counts_by_year went
# empty; per-work history only spans ~10yr), so we read it from Semantic Scholar's open citation
# graph — bulk self-collected, routed through the DC proxy (rotating IP dodges the shared limit).
S2 = "https://api.semanticscholar.org/graph/v1"
S2_UA = f"predictthefuture research (mailto:{MAILTO})"
# One uniform rule, NO per-term tuning (anti-overfitting): foundational = published in the formative
# window (≥10yr old by the cutoff) and cited in a *paginatable* range. The ceiling excludes the
# mega-landmark papers (S2 caps citation paging at offset 10k) — a logged selection caveat: we
# measure the uptake velocity of the paginatable foundational corpus, not every citation.
S2_FORMATIVE_START = 2006
S2_MIN_CITES = 300       # below this = not foundational (noise)
S2_MAX_CITES = 8000      # above this = un-paginatable (offset cap) → excluded, documented
S2_N_SEMINAL = 15        # seminal papers aggregated per term

# Terms to read citation-velocity for. Deliberately overlaps the §8 retro corpus + existing
# publication-count series so the channel can be discrimination-tested (winner vs fizzle, and
# does it fire EARLIER than the count channel?). Science-citation-rich concepts only.
S2_TERMS: list[str] = [
    "deep learning",                 # THE recall case — the winner the count channel missed
    "single cell rna sequencing",    # known winner (the system's flagship constraint)
    "perovskite solar cell",         # winner (energy)
    "graphene",                      # §8 fizzle — must NOT show clean leading acceleration
]


def _s2_get(path: str, params: dict, *, prov: str, retries: int = 3) -> dict | None:
    """One Semantic Scholar GET through the proxy. Fresh IP per attempt (rotation) to dodge the
    shared keyless rate-limit; degrades to None on persistent 429/5xx rather than faking a number."""
    import httpx
    from engine.adapters import proxy as _proxy
    for attempt in range(retries + 1):
        try:
            with httpx.Client(proxy=_proxy.proxy_url(prov), timeout=45, follow_redirects=True,
                              headers={"User-Agent": S2_UA}) as cl:
                resp = cl.get(f"{S2}{path}", params=params)
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                return None
        except Exception:  # noqa: BLE001 — proxy/parse/timeout: rotate-retry then degrade quietly
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            return None
    return None


def _s2_seminal(term: str, formative_end: int, *, prov: str) -> list[str]:
    """Top ≤N foundational paper ids for `term`: most-cited in the formative window, citation count
    in the paginatable range. Selection is by citation magnitude (a mild hindsight bias on *which*
    papers — logged in the Source rationale); the velocity SHAPE it yields stays point-in-time."""
    js = _s2_get("/paper/search/bulk", {
        "query": term, "sort": "citationCount:desc", "fields": "year,citationCount",
        "year": f"{S2_FORMATIVE_START}-{formative_end}",
    }, prov=prov)
    if not js:
        return []
    out = []
    for p in js.get("data") or []:
        cc = p.get("citationCount") or 0
        if S2_MIN_CITES < cc < S2_MAX_CITES and p.get("paperId"):
            out.append(p["paperId"])
        if len(out) >= S2_N_SEMINAL:
            break
    return out


def _s2_citations_by_year(paper_id: str, *, prov: str) -> dict[int, int]:
    """Full year-histogram of citations RECEIVED by one paper (paginated; bounded by the 10k offset
    cap, which is why the seminal set is citation-ceilinged)."""
    hist: dict[int, int] = {}
    offset = 0
    while offset < 10000:
        js = _s2_get(f"/paper/{paper_id}/citations",
                     {"fields": "year", "limit": 1000, "offset": offset}, prov=prov)
        if not js:
            break
        data = js.get("data") or []
        for d in data:
            y = (d.get("citingPaper") or {}).get("year")
            if isinstance(y, int):
                hist[y] = hist.get(y, 0) + 1
        if len(data) < 1000:
            break
        offset += 1000
    return hist


def collect_citation_velocity(conn: sqlite3.Connection, *, terms: list[str] = S2_TERMS,
                              end: int = CUTOFF_YEAR, log=print) -> int:
    """Pillar 1, orthogonal leading channel: citations-received-per-year by each term's seminal
    papers (Semantic Scholar, via DC proxy). Returns n_series. $0/keyless; DC bandwidth is sub-cent
    so it logs an `auto` ledger row (rule 3). Requires a proxy — degrades to 0 series without one."""
    from engine.adapters import proxy as _proxy
    prov = "floxy" if _proxy.available("floxy") else ("evomi" if _proxy.available("evomi") else None)
    _log_cost(conn, "s2_citation_velocity", f"semantic_scholar{'+'+prov if prov else ''}",
              float(len(terms)))
    if prov is None:
        log("  ! no proxy configured — Semantic Scholar bulk needs one. 0 series.")
        return 0
    formative_end = end - 10  # one uniform rule: foundational = ≥10yr old at the cutoff
    n_series = 0
    for term in terms:
        seminal = _s2_seminal(term, formative_end, prov=prov)
        if len(seminal) < 5:
            log(f"  - skip {term!r} (only {len(seminal)} seminal papers found)")
            continue
        vel: dict[int, int] = {}
        for pid in seminal:
            for y, n in _s2_citations_by_year(pid, prov=prov).items():
                if S2_FORMATIVE_START <= y <= end:
                    vel[y] = vel.get(y, 0) + n
        ys = [y for y in sorted(vel) if vel[y] > 0]
        if len(ys) < 8:  # detector needs ≥8 points; never store a stub (no silent cap)
            log(f"  - skip {term!r} ({len(ys)} yrs of citation data)")
            continue
        last = ys[-1]
        payload = {str(y): vel[y] for y in ys}
        src = Source(
            url=f"{S2}/paper/search/bulk?query={urllib.parse.quote(term)}&metric=citation_velocity",
            title=f'Semantic Scholar — "{term}" citations-received/year (seminal corpus)',
            pillar_id=FRONTIER_PILLAR_ID, kind=SourceKind.primary,
            trust_score=70,
            trust_rationale=(
                "Semantic Scholar open citation graph (keyless, self-collected via DC proxy): "
                f"citations RECEIVED per year, summed over the top {len(seminal)} most-cited papers "
                f"matching the phrase in the formative window {S2_FORMATIVE_START}-{formative_end}, "
                f"each with {S2_MIN_CITES}-{S2_MAX_CITES} total citations (paginatable). Raw counts "
                "are high-trust primary graph data. Caveats: the seminal SET is chosen by citation "
                "magnitude (a mild hindsight bias on which papers — the velocity SHAPE stays "
                "point-in-time); the citation ceiling excludes mega-landmark papers (S2 10k offset "
                "cap); recent years under-report (indexing lag) so they read low, not high — a "
                "conservative bias for an acceleration detector."
            ),
            recency=date(last, 12, 31),
            content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=FRONTIER_PILLAR_ID, source_id=source_id, provider="semantic_scholar",
            external_id=term, label=f"{term} (citation velocity)",
            metric="citations_received_per_year", unit="citations/year", domain=None,
        )
        series_id = _upsert_series(conn, series)
        for y in ys:
            _upsert_observation(conn, Observation(
                series_id=series_id, as_of=date(y, 12, 31), value=float(vel[y]),
                unit="citations/year", uncertainty=max(1.0, sqrt(vel[y])),  # Poisson 1σ
            ))
        n_series += 1
        log(f"  + {term:<28} cites/yr {ys[0]}–{last}  {vel[ys[0]]}→{vel[last]}  "
            f"({len(seminal)} seminal)")
    conn.commit()
    return n_series


# --- Grants — NIH RePORTER (REST POST, keyless) -------------------------------
# Biomedical only. NSF (the physical-science/CS complement) is a logged gap: its Award
# Search returns no total-count field, so per-year counts would need full pagination.

NIH_REPORTER = "https://api.reporter.nih.gov/v2/projects/search"
GRANT_WINDOW_START = 2008
GRANT_CUTOFF_YEAR = 2023  # FY record-load lag → cap one below the OpenAlex cutoff
NIH_TOPICS: list[str] = [
    "crispr", "mrna vaccine", "car t cell", "gene therapy",
    "single cell rna sequencing", "cancer immunotherapy", "organoid",
    "microbiome", "antibody engineering", "synthetic biology",
]


def _nih_count(text: str, fiscal_year: int) -> int | None:
    """Number of NIH-funded projects matching `text` in a fiscal year (meta.total)."""
    payload = {
        "criteria": {
            "advanced_text_search": {
                "operator": "and",
                "search_field": "projecttitle,terms,abstracttext",
                "search_text": text,
            },
            "fiscal_years": [fiscal_year],
        },
        "include_fields": ["FiscalYear"], "limit": 1, "offset": 0,
    }
    try:
        data = _post_json(NIH_REPORTER, payload)
    except OSError:  # degrade quietly on a flaky API call
        return None
    except json.JSONDecodeError:
        return None
    total = data.get("meta", {}).get("total")
    return int(total) if isinstance(total, int) else None


def collect_grants(conn: sqlite3.Connection, *, log=print) -> int:
    """NIH grant award count per biomedical topic per fiscal year. Returns n_series."""
    _log_cost(conn, "nih_reporter_collect", "nih_reporter", float(len(NIH_TOPICS)))
    years = list(range(GRANT_WINDOW_START, GRANT_CUTOFF_YEAR + 1))
    n_series = 0
    for topic in NIH_TOPICS:
        counts = {y: c for y in years if (c := _nih_count(topic, y)) is not None}
        if len(counts) < 8:
            log(f"  - skip grants {topic!r} ({len(counts)} yrs returned)")
            continue
        ys = sorted(counts)
        last = ys[-1]
        payload = {str(y): counts[y] for y in ys}
        src = Source(
            url=f"{NIH_REPORTER}#text={urllib.parse.quote(topic)}",
            title=f"NIH RePORTER — \"{topic}\" awards/fiscal-year",
            pillar_id=FRONTIER_PILLAR_ID, kind=SourceKind.filing,
            trust_score=85,
            trust_rationale=(
                "NIH RePORTER v2 API (official US NIH grants database, keyless POST): count of "
                "federally-funded projects matching the topic per fiscal year. Caveats: lexical "
                "keyword match over title/terms/abstract (may over/under-include); covers NIH "
                "BIOMEDICAL funding only (NSF/physical-science absent — logged gap); award-$ not "
                f"summed (count only); recent FYs may under-report on load lag (capped at {GRANT_CUTOFF_YEAR})."
            ),
            recency=date(last, 12, 31),
            content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=FRONTIER_PILLAR_ID, source_id=source_id, provider="nih_reporter",
            external_id=topic, label=f"{topic} (NIH grants)",
            metric="nih_awards_per_year", unit="awards/year", domain="biomed",
        )
        series_id = _upsert_series(conn, series)
        for y in ys:
            _upsert_observation(conn, Observation(
                series_id=series_id, as_of=date(y, 12, 31), value=float(counts[y]),
                unit="awards/year", uncertainty=max(1.0, sqrt(counts[y])),  # Poisson 1σ
            ))
        n_series += 1
        log(f"  + {topic:<26} grants {ys[0]}–{last}  {counts[ys[0]]}→{counts[last]}")
    conn.commit()
    return n_series


# --- Benchmarks — Epoch AI notable-models compute curve (public CSV, keyless) -

EPOCH_CSV = "https://epoch.ai/data/notable_ai_models.csv"
EPOCH_WINDOW_START = 2010
EPOCH_DOMAIN_CANDIDATES = ["Language", "Vision", "Image generation", "Speech", "Games"]


def _epoch_year(s: str | None) -> int | None:
    s = (s or "").strip()
    return int(s[:4]) if len(s) >= 4 and s[:4].isdigit() else None


def _epoch_flop(s: str | None) -> float | None:
    s = (s or "").strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def collect_benchmarks(conn: sqlite3.Connection, *, log=print) -> int:
    """Per-domain frontier (max) training-compute FLOP by year (Epoch AI). Returns n_series."""
    _log_cost(conn, "epoch_collect", "epoch_ai", 1.0)
    try:
        rows = list(csv.DictReader(io.StringIO(_get_text(EPOCH_CSV, timeout=45))))
    except OSError:  # epoch.ai unreachable — degrade quietly
        log("  ! epoch.ai unreachable")
        conn.commit()
        return 0
    n_series = 0
    for domain in EPOCH_DOMAIN_CANDIDATES:
        by_year: dict[int, float] = {}
        for r in rows:
            doms = [d.strip() for d in (r.get("Domain") or "").split(",")]
            if domain not in doms:
                continue
            y = _epoch_year(r.get("Publication date"))
            flop = _epoch_flop(r.get("Training compute (FLOP)"))
            if y is None or flop is None or not (EPOCH_WINDOW_START <= y <= CUTOFF_YEAR):
                continue
            if flop > by_year.get(y, 0.0):  # frontier = the max-compute model that year
                by_year[y] = flop
        if len(by_year) < 8:
            log(f"  - skip epoch {domain!r} ({len(by_year)} yrs with compute)")
            continue
        ys = sorted(by_year)
        last = ys[-1]
        payload = {str(y): by_year[y] for y in ys}
        src = Source(
            url=f"{EPOCH_CSV}#domain={urllib.parse.quote(domain)}",
            title=f"Epoch AI — frontier training compute ({domain})",
            pillar_id=FRONTIER_PILLAR_ID, kind=SourceKind.primary,
            trust_score=80,
            trust_rationale=(
                "Epoch AI 'Notable AI Models' public CSV (keyless, transparent curated "
                "methodology): per-domain frontier (max) training-compute FLOP by publication "
                "year — the canonical capability-acceleration curve. Caveats: compute figures "
                "are ESTIMATES (~0.3 dex / ~2x; stored as sigma=0.5*value); the model set is "
                f"curated (may omit systems and lags for the latest year, capped at {CUTOFF_YEAR})."
            ),
            recency=date(last, 12, 31),
            content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=FRONTIER_PILLAR_ID, source_id=source_id, provider="epoch_ai",
            external_id=domain, label=f"Frontier training compute ({domain})",
            metric="frontier_training_compute", unit="FLOP", domain="AI",
        )
        series_id = _upsert_series(conn, series)
        for y in ys:
            v = by_year[y]
            _upsert_observation(conn, Observation(
                series_id=series_id, as_of=date(y, 12, 31), value=v,
                unit="FLOP", uncertainty=0.5 * v,  # ~0.3 dex compute-estimate uncertainty
            ))
        n_series += 1
        log(f"  + Epoch {domain:<16} compute {ys[0]}–{last}  {by_year[ys[0]]:.1e}→{by_year[last]:.1e}")
    conn.commit()
    return n_series


def add_control_series(conn: sqlite3.Connection, *, log=print) -> None:
    """A deterministic, intentionally-flat series — the detector MUST stay silent on it.

    Not evidence (no Source): it is a cry-wolf guard for the detector, not a frontier signal.
    A small fixed zigzag around 100 gives σ>0 so 'silent' means 'below k·σ', not 'no noise'.
    """
    pattern = [100, 103, 98, 101, 99, 102, 100, 97, 101, 100, 103, 98, 100, 99, 102,
               100, 101, 98, 100, 103, 99, 100, 102, 98, 101]
    series = Series(
        pillar_id=FRONTIER_PILLAR_ID, source_id=None, provider="synthetic",
        external_id="control_flat", label="CONTROL (synthetic flat)",
        metric="works_per_year", unit="works/year", domain="control",
    )
    series_id = _upsert_series(conn, series)
    for i, v in enumerate(pattern):
        year = WINDOW_START + i
        _upsert_observation(conn, Observation(
            series_id=series_id, as_of=date(year, 12, 31), value=float(v),
            unit="works/year", uncertainty=max(1.0, sqrt(v)),
        ))
    conn.commit()
    log(f"  + CONTROL (synthetic flat)         {WINDOW_START}–{WINDOW_START + len(pattern) - 1}  flat≈100")


def collect(conn: sqlite3.Connection | None = None, *, log=print) -> dict:
    """Run the full Frontier collection. Idempotent (upserts by natural key)."""
    own = conn is None
    if own:
        conn = db.connect()
        db.init_db(conn)
    log("OpenAlex — frontier concept velocity:")
    n_series, n_obs = collect_openalex(conn, log=log)
    log("OpenAlex — laggard control pool (backtest true-negatives):")
    n_lag_series, n_lag_obs = collect_openalex(conn, terms=DUD_TERMS, domain="laggard", log=log)
    n_series += n_lag_series
    n_obs += n_lag_obs
    log("Patents — Google Patents filing velocity (priority year):")
    n_patents = collect_patents(conn, log=log)
    log("Grants — NIH RePORTER awards/fiscal-year:")
    n_grants = collect_grants(conn, log=log)
    log("Benchmarks — Epoch AI frontier training compute:")
    n_bench = collect_benchmarks(conn, log=log)
    log("arXiv — category presence (current totals):")
    n_arxiv = collect_arxiv(conn, log=log)
    log("Control:")
    add_control_series(conn, log=log)
    if own:
        conn.close()
    return {"openalex_series": n_series, "openalex_obs": n_obs, "arxiv_series": n_arxiv,
            "patent_series": n_patents, "grant_series": n_grants, "benchmark_series": n_bench}
