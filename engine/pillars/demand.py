"""Pillar 5 — Demand / adoption (free / keyless). Is it really diffusing?

The frontier (pillar 1) reads research velocity; this reads *attention/adoption* velocity — a
~2–4yr-lead signal that a capability is crossing from labs into the world. v1 source: **Wikipedia
pageviews** (Wikimedia REST, keyless, monthly from 2015, summed to yearly) per technology — a clean,
high-volume public-attention curve. The detector reads its acceleration like any other series.

This is an ATTENTION signal (doctrine §0.5: never sufficient alone — the consensus gate + capability
curves are what separate a real diffusion from a hype spike). Stored tagged `domain="demand"` so it
is never mistaken for a capability curve. $0; a cost-ledger row is logged (rule 3).
"""

from __future__ import annotations

import json
import sqlite3
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date
from math import sqrt

from engine import store
from engine.pillars.frontier import UA, _content_hash, _log_cost, _upsert_series, _upsert_source
from engine.schemas import Observation, Series, Source, SourceKind

DEMAND_PILLAR_ID = 5
WIKI = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/all-agents"
WINDOW_START, CUTOFF_YEAR = 2016, 2024   # pageviews API starts 2015-07; first full year is 2016

# term -> exact English-Wikipedia article title (verified shape; 404s degrade quietly + logged).
ARTICLES: dict[str, str] = {
    "deep learning": "Deep_learning",
    "large language model": "Large_language_model",
    "quantum computing": "Quantum_computing",
    "crispr": "CRISPR",
    "mrna vaccine": "MRNA_vaccine",
    "gene therapy": "Gene_therapy",
    "solid-state battery": "Solid-state_battery",
    "perovskite solar cell": "Perovskite_solar_cell",
    "lithium-ion battery": "Lithium-ion_battery",
    "self-driving car": "Self-driving_car",
    "nuclear fusion": "Nuclear_fusion",
    "hydrogen economy": "Hydrogen_economy",
    "blockchain": "Blockchain",
    "single-cell sequencing": "Single-cell_sequencing",
    "generative artificial intelligence": "Generative_artificial_intelligence",
}


def _pageviews_by_year(title: str) -> dict[int, int]:
    url = (f"{WIKI}/{urllib.parse.quote(title, safe='')}/monthly/"
           f"{WINDOW_START}010100/{CUTOFF_YEAR}123100")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    items = json.loads(urllib.request.urlopen(req, timeout=30).read()).get("items", [])
    by_year: dict[int, int] = defaultdict(int)
    for it in items:
        by_year[int(it["timestamp"][:4])] += int(it.get("views", 0))
    return dict(by_year)


def collect(conn: sqlite3.Connection | None = None, *, log=print) -> dict:
    """Wikipedia-pageview demand velocity per technology (yearly). Idempotent. $0."""
    from engine import db
    own = conn is None
    if own:
        conn = db.connect()
        db.init_db(conn)
    _log_cost(conn, "wikipedia_pageviews_collect", "wikimedia", float(len(ARTICLES)))
    n_series = n_obs = 0
    for term, title in ARTICLES.items():
        try:
            counts = _pageviews_by_year(title)
        except Exception as e:  # noqa: BLE001 — 404 (bad title) / network: degrade quietly, logged
            log(f"  ! wikipedia {title!r}: {type(e).__name__}")
            continue
        counts = {y: v for y, v in counts.items() if WINDOW_START <= y <= CUTOFF_YEAR and v > 0}
        if len(counts) < 8:
            log(f"  - skip {term} ({len(counts)} yrs)")
            continue
        years = sorted(counts)
        last = years[-1]
        payload = {str(y): counts[y] for y in years}
        src = Source(
            url=f"{WIKI}/{urllib.parse.quote(title, safe='')}/monthly",
            title=f"Wikipedia pageviews — {title}",
            pillar_id=DEMAND_PILLAR_ID, kind=SourceKind.primary, trust_score=70,
            trust_rationale=(
                "Wikimedia REST pageviews API (keyless, official): English-Wikipedia article views/"
                "year, an ATTENTION/adoption proxy (§0.5: never sufficient alone — capability + the "
                "consensus gate separate diffusion from hype). Bot/spike noise possible; directional."
            ),
            recency=date(last, 12, 31), content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=DEMAND_PILLAR_ID, source_id=source_id, provider="wikipedia",
            external_id=title, label=f"{term} (pageviews)", metric="wikipedia_pageviews",
            unit="views/year", domain="demand",
        )
        series_id = _upsert_series(conn, series)
        store.bulk_upsert_observations(conn, [
            Observation(series_id=series_id, as_of=date(y, 12, 31), value=float(counts[y]),
                        unit="views/year", uncertainty=max(1.0, sqrt(counts[y])))
            for y in years
        ])
        n_series += 1
        n_obs += len(years)
        log(f"  + {term:<34} {years[0]}–{last}  {counts[years[0]]:,}→{counts[last]:,} views/yr")
    conn.commit()
    if own:
        conn.close()
    return {"series": n_series, "obs": n_obs}
