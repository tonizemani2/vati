"""Pillar 2 — Capability curves (free / keyless). The detector's real fuel.

Pillar 1 reads the *velocity of attention* (works/year). This reads the *velocity of capability*:
mechanism-backed cost/performance curves where a real driver (Wright's law, a faster-than-Moore
cost collapse, an LCOE crossing) makes a technology cross a threshold. This is the §0.5
"projectibility" commitment in data form — we trust an acceleration only when a mechanism backs it.

We store **affordability = reference / cost** (a RISING index), not the falling cost, so the
domain-agnostic detector — which fires on upward acceleration — sees a capability *taking off*
exactly as the §8 retro corpus encodes it (Mb-per-$, kWh-per-$). Each curve carries its mechanism
in the trust rationale (GIGO) and a point-in-time as_of per data-year.

Source: Our World in Data grapher CSVs (keyless, transparent methodology, stable slugs — verified
live before baking). $0; a cost-ledger row is still logged so the gate is exercised (rule 3).
"""

from __future__ import annotations

import csv
import io
import sqlite3
import urllib.request
from datetime import date

from engine import store
from engine.pillars.frontier import (
    MAILTO, UA, _content_hash, _log_cost, _upsert_series, _upsert_source,
)
from engine.schemas import Observation, Series, Source, SourceKind

CAPABILITY_PILLAR_ID = 2
OWID = "https://ourworldindata.org/grapher"
WINDOW_START = 1990
CUTOFF_YEAR = 2024

# Each curve: the OWID slug, the value column, the cost→affordability reference (value = ref / cost
# so the index RISES), the unit, the mechanism (the projectibility justification), and a domain.
# `entity` picks the global/aggregate row. Verified live: every slug returns CSV with these columns.
CURVES: list[dict] = [
    {
        "slug": "solar-pv-prices", "col": "cost", "entity": "World",
        "ref": 1.0, "metric": "solar_pv_affordability", "unit": "W per $",
        "domain": "energy",
        "mechanism": "Wright's law (Swanson): solar module $/W falls ~20% per doubling of cumulative "
                     "capacity — a learning-curve cost collapse, the canonical projectible mechanism.",
    },
    {
        "slug": "cost-of-sequencing-a-full-human-genome", "col": "cost_per_genome", "entity": "World",
        "ref": 1_000_000.0, "metric": "genome_seq_affordability", "unit": "genomes per $1M",
        "domain": "bio",
        "mechanism": "NGS cost collapse — faster-than-Moore $/genome decline (NHGRI), driven by "
                     "massively-parallel sequencing chemistry; the §8 genomics winner's curve.",
    },
    {
        "slug": "levelized-cost-of-energy", "col": "solar_photovoltaic", "entity": "World",
        "ref": 1000.0, "metric": "solar_lcoe_affordability", "unit": "MWh per $1000",
        "domain": "energy",
        "mechanism": "Utility solar LCOE ($/MWh) collapse — Wright's-law module cost + balance-of-system "
                     "learning; crosses fossil parity, a real capability threshold.",
    },
    {
        "slug": "levelized-cost-of-energy", "col": "offshore_wind", "entity": "World",
        "ref": 1000.0, "metric": "offshore_wind_lcoe_affordability", "unit": "MWh per $1000",
        "domain": "energy",
        "mechanism": "Offshore-wind LCOE decline — turbine scale-up + installation learning; a slower "
                     "but real learning curve (a useful contrast to solar's steep one).",
    },
    {
        "slug": "levelized-cost-of-energy", "col": "geothermal", "entity": "World",
        "ref": 1000.0, "metric": "geothermal_lcoe_affordability", "unit": "MWh per $1000",
        "domain": "energy",
        "mechanism": "Geothermal LCOE — largely flat (mature drilling tech, no steep learning curve); "
                     "included as a near-flat capability CONTROL among the energy curves.",
    },
    {
        "slug": "supercomputer-power-flops", "col": "computational_capacity_fastest_supercomputer",
        "entity": "World", "ref": None, "metric": "supercomputer_flops", "unit": "FLOP/s",
        "domain": "compute",
        "mechanism": "Top-500 #1 supercomputer FLOP/s — a rising PERFORMANCE curve (stored raw, not "
                     "inverted); sustained super-Moore scaling from transistor + interconnect + scale-out.",
    },
    {
        "slug": "transistors-per-microprocessor", "col": "transistors", "entity": "World",
        "ref": None, "metric": "transistors_per_chip", "unit": "transistors",
        "domain": "compute",
        "mechanism": "Moore's law — transistors per microprocessor (the canonical exponential "
                     "capability curve); rising performance stored raw. The reference projectible mechanism.",
    },
]


def _fetch_csv(slug: str) -> list[dict]:
    url = f"{OWID}/{slug}.csv?v=1&csvType=full&useColumnShortNames=true"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    text = urllib.request.urlopen(req, timeout=45).read().decode("utf-8", "replace")
    return list(csv.DictReader(io.StringIO(text)))


def collect(conn: sqlite3.Connection | None = None, *, log=print) -> dict:
    """Fetch every capability curve, store affordability series (point-in-time). Idempotent. $0."""
    from engine import db
    own = conn is None
    if own:
        conn = db.connect()
        db.init_db(conn)
    _log_cost(conn, "owid_capability_collect", "ourworldindata", float(len(CURVES)))
    # cache CSVs per slug (levelized-cost-of-energy serves several curves)
    cache: dict[str, list[dict]] = {}
    n_series = n_obs = 0
    for c in CURVES:
        try:
            rows = cache.get(c["slug"]) or cache.setdefault(c["slug"], _fetch_csv(c["slug"]))
        except OSError as e:
            log(f"  ! {c['slug']} unreachable: {e}")
            continue
        # pull (year, affordability) for the chosen entity where the column is present + numeric
        pts: dict[int, float] = {}
        for r in rows:
            if r.get("entity") != c["entity"]:
                continue
            raw = (r.get(c["col"]) or "").strip()
            yr = (r.get("year") or "").strip()
            if not raw or not yr.isdigit():
                continue
            year = int(yr)
            if not (WINDOW_START <= year <= CUTOFF_YEAR):
                continue
            try:
                cost = float(raw)
            except ValueError:
                continue
            if cost <= 0:
                continue
            # ref=None → already a rising performance metric (store raw); else affordability = ref/cost
            pts[year] = cost if c["ref"] is None else c["ref"] / cost
        if len(pts) < 8:
            log(f"  - skip {c['metric']} ({len(pts)} yrs for entity {c['entity']!r})")
            continue
        years = sorted(pts)
        last = years[-1]
        payload = {str(y): round(pts[y], 6) for y in years}
        src = Source(
            url=f"{OWID}/{c['slug']}.csv#col={c['col']}&entity={c['entity']}",
            title=f"OWID capability curve — {c['metric']} ({c['slug']})",
            pillar_id=CAPABILITY_PILLAR_ID, kind=SourceKind.primary, trust_score=82,
            trust_rationale=(
                "Our World in Data grapher CSV (keyless, transparent methodology, cited primary "
                f"datasets). Mechanism (projectibility, §0.5): {c['mechanism']} Encoded "
                + (f"as affordability = {c['ref']:g}/cost so the detector reads capability taking off; "
                   if c["ref"] is not None else "as the raw rising performance metric; ")
                + "values are directional (analyst/agency curves), ~10% 1σ."
            ),
            recency=date(last, 12, 31), content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=CAPABILITY_PILLAR_ID, source_id=source_id, provider="owid",
            external_id=f"{c['slug']}:{c['col']}", label=c["metric"].replace("_", " "),
            metric=c["metric"], unit=c["unit"], domain=c["domain"],
        )
        series_id = _upsert_series(conn, series)
        rows_obs = [
            Observation(series_id=series_id, as_of=date(y, 12, 31), value=float(pts[y]),
                        unit=c["unit"], uncertainty=0.10 * pts[y])  # ~10% on directional curves
            for y in years
        ]
        store.bulk_upsert_observations(conn, rows_obs)
        n_series += 1
        n_obs += len(rows_obs)
        log(f"  + {c['metric']:<30} {years[0]}–{last}  "
            f"{pts[years[0]]:.3g}→{pts[last]:.3g} {c['unit']}")
    conn.commit()
    if own:
        conn.close()
    return {"series": n_series, "obs": n_obs}
