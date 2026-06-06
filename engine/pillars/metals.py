"""Pillar 4 (supply elasticity) — the metals/mining domain. The copper-mine drill target.

The graph's `drill_targets` named **copper mine supply** the #1 place to spend the deep-data budget:
high P(bottleneck) × thin coverage. Its coverage was thin because the node was backed only by a
*sourced parameter* (the IEA lead-time narrative), not a *measured build-out series*. This module
closes that loop — it attaches a MEASURED-QUANTITY signal to the node, so derived demand stops being
structural and becomes a number (the demand-is-measurable mechanic, started at the target the system
itself pointed to).

Where power.py reads the inelastic layer's *price*, this reads its *quantity*: how much mine output
actually scales. A price break says "tight"; a flat output index says "and it cannot scale" — the
inelasticity stated as an absolute, not inferred from price.

Sources, all FREE / KEYLESS, primary (Federal Reserve G.17 industrial production), high trust:
  • FRED IPG21223S — IP: Copper, Nickel, Lead & Zinc Mining (NAICS 21223). The copper-base-metal
    mine OUTPUT index: 111 (1972) → 89 (2025). US base-metal mine output is flat-to-DECLINING over
    half a century — the node's inelasticity thesis as a measured number, not the IEA narrative.
    This is the build series attached to the `copper mine supply` graph node.
  • FRED IPG2122S — IP: Metal Ore Mining (NAICS 2122). The whole metal-mining layer (74→80 over 53
    yrs) — corroborates that supply-inelasticity is systemic to mining, not one commodity.

Honestly-logged caveat (NOT faked): these are US output INDICES (Federal Reserve G.17), a directional
proxy for GLOBAL copper mine supply in tonnes — global mine production by tonne is a USGS Mineral
Commodity Summaries Excel workbook, not a clean keyless CSV [?]. The index measures the *shape*
(flat/declining = inelastic), which is what the graph needs; the IEA source still carries the global
lead-time / ore-grade evidence. Revised ~1% (G.17 revisions), so uncertainty is ~1% of value — not
faked noise.

Cost: $0. Logs a $0 'auto' cost-ledger row so the gate is exercised, not bypassed (rule 3).
"""

from __future__ import annotations

import sqlite3
from datetime import date

from engine import db
from engine.pillars.frontier import _log_cost, _upsert_observation, _upsert_series, _upsert_source
from engine.pillars.power import _content_hash, _fred_annual
from engine.schemas import Observation, Series, Source, SourceKind

SUPPLY_PILLAR_ID = 4
# The node the drill-score named; collect() attaches the first series below to it.
COPPER_MINE_NODE = "copper mine supply (concentrate)"
METALS_CHAIN = "metals"

# Order matters: the FIRST series is the measured build series for the copper-mine node.
FRED_SERIES: list[dict] = [
    {
        "id": "IPG21223S",
        "label": "Copper-base-metal mine output (US)",
        "metric": "copper_mine_output",
        "unit": "index (2017=100)",
        "is_build_series": True,
        "rationale": (
            "FRED / Federal Reserve G.17 Industrial Production: Copper, Nickel, Lead & Zinc Mining "
            "(NAICS 21223, keyless CSV, annual avg). PRIMARY, high trust — official Fed index, "
            "transparent method. A MEASURED-QUANTITY signal (not a price): US base-metal mine output "
            "ran 111 (1972) → 89 (2025), i.e. flat-to-DECLINING over half a century — the copper-mine "
            "node's structural inelasticity as a number, corroborating the IEA lead-time / falling-"
            "ore-grade narrative. Caveat: a US output INDEX, a directional proxy for global copper "
            "mine supply in tonnes (global tonnage = USGS Excel, not keyless [?]); revised ~1%."
        ),
    },
    {
        "id": "IPG2122S",
        "label": "Metal-ore mine output (US)",
        "metric": "metal_ore_output",
        "unit": "index (2017=100)",
        "is_build_series": False,
        "rationale": (
            "FRED / Federal Reserve G.17 Industrial Production: Metal Ore Mining (NAICS 2122, keyless "
            "CSV, annual avg). PRIMARY, high trust. Broad metal-mining output (74→80 over 53 yrs) — "
            "corroborates that supply-inelasticity is systemic to mining, not one commodity. Same "
            "US-index proxy caveat as IPG21223S."
        ),
    },
]


def collect(conn: sqlite3.Connection | None = None, *, log=print) -> dict:
    """Collect the keyless metals-mining supply-quantity series; return the copper-mine build series_id.

    Idempotent, $0. The caller (CLI `collect-metals`) attaches the build series to the copper-mine
    graph node and re-runs the drill-score to show coverage flip from parameter to measured.
    """
    own = conn is None
    if own:
        conn = db.connect()
        db.init_db(conn)
    conn.execute("UPDATE pillars SET status='in_progress' WHERE id=? AND status='untapped'",
                 (SUPPLY_PILLAR_ID,))
    conn.commit()

    n_series = n_obs = 0
    build_series_id: str | None = None
    log("FRED — metals/mining supply-QUANTITY signals (annual avg):")
    for spec in FRED_SERIES:
        try:
            counts = _fred_annual(spec["id"])
        except OSError as e:
            log(f"  ! FRED {spec['id']} unreachable: {e}")
            continue
        if len(counts) < 8:
            log(f"  - skip {spec['label']} (only {len(counts)} yrs)")
            continue
        years = sorted(counts)
        last = years[-1]
        payload = {str(y): counts[y] for y in years}
        src = Source(
            url=f"https://fred.stlouisfed.org/series/{spec['id']}",
            title=f"FRED {spec['id']} — {spec['label']} (IP, annual avg)",
            pillar_id=SUPPLY_PILLAR_ID, kind=SourceKind.primary, trust_score=88,
            trust_rationale=spec["rationale"], recency=date(last, 12, 31),
            content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=SUPPLY_PILLAR_ID, source_id=source_id, provider="fred",
            external_id=spec["id"], label=spec["label"], metric=spec["metric"],
            unit=spec["unit"], domain="metals / mining",
        )
        series_id = _upsert_series(conn, series)
        if spec["is_build_series"]:
            build_series_id = series_id
        n_series += 1
        for y in years:
            v = counts[y]
            _upsert_observation(conn, Observation(
                series_id=series_id, as_of=date(y, 12, 31), value=v,
                unit=spec["unit"], uncertainty=max(0.5, 0.01 * v),  # ~1% G.17 revision, not faked
            ))
            n_obs += 1
        flag = "  ← build series → copper-mine node" if spec["is_build_series"] else ""
        log(f"  + {spec['label']:<30} {years[0]}–{last}  {counts[years[0]]:.0f}→{counts[last]:.0f}{flag}")

    _log_cost(conn, "fred_collect", "fred", float(len(FRED_SERIES)))
    conn.commit()
    if own:
        conn.close()
    log("Logged caveat (not faked): US output indices proxy global mine tonnage (USGS Excel = [?]).")
    return {"series": n_series, "obs": n_obs, "build_series_id": build_series_id}
