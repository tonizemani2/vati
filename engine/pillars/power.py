"""Pillar 4 (supply elasticity) collector — the AI-power buildout's inelastic layer.

The second domain. Where Frontier (pillar 1) reads the *velocity of science*, this reads the
*price of the binding physical constraint*: when a supply layer cannot scale to meet demand, its
producer price index breaks upward. That break IS the elasticity signal — point-in-time, primary,
and exactly the falsifiable series the hypothesis gate demanded for the survived thesis ("AI rent
migrates from the GPU to the electrical interconnect / large-power transformers").

Sources, all FREE / KEYLESS, primary (BLS via FRED), high trust:
  • FRED PCU335311335311 — PPI: Power, Distribution & Specialty Transformer Mfg. The transformer
    layer's price. Flat ~230–255 (2011–2020) then a textbook break: 300 (2021) → 396 (2022) →
    443 (2025). The constraint binding in real time.
  • FRED PCU335313335313 — PPI: Switchgear & Switchboard Apparatus Mfg. The adjacent grid-gear
    layer, same break (219 in 2020 → 353 in 2025).

We pull the ANNUAL average (fq=Annual) so the cadence matches the detector's per-year curves.
The PPI is an essentially-exact reported index (small subsequent revision), so uncertainty is set
to a conservative 0.5% of value — not faked Poisson noise (these are not counts).

Honestly-logged gaps (need paid/Excel/auth sources — NOT faked):
  • Large-power-transformer LEAD TIMES (the hypothesis's own kill-criterion) — trade-survey / Wood
    Mackenzie, no clean keyless series. The PPI is the keyless proxy (price spikes when lead times
    blow out).
  • Grid-interconnection QUEUE durations — LBNL "Queued Up" publishes this, but as an Excel
    workbook, not a clean CSV endpoint. Logged for a later parse (it is free).
  • Data-center electricity LOAD — no clean keyless point-in-time series (EIA needs a key for v2).

Cost: $0. Every run logs a $0 'auto' cost-ledger row so the gate is exercised, not bypassed
(CONSTITUTION rule 3). Reasoning stays in-session; this module only collects and stores.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
import urllib.request
from datetime import date

from engine import db
from engine.pillars.frontier import _log_cost, _upsert_observation, _upsert_series, _upsert_source
from engine.schemas import Observation, Series, Source, SourceKind

SUPPLY_PILLAR_ID = 4          # Supply elasticity — where the scarcity rent lands
UA = "predictthefuture research (ruben.stout@edu.escp.eu)"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"
WINDOW_START = 2005
CUTOFF_YEAR = 2025            # 2026 is incomplete in the annual file

# Each FRED series: (id, label, what it measures + why it's the inelastic-layer signal).
FRED_SERIES: list[dict] = [
    {
        "id": "PCU335311335311",
        "label": "Large-power transformer PPI",
        "metric": "transformer_ppi",
        "unit": "index (1982=100)",
        "rationale": (
            "FRED / U.S. BLS Producer Price Index for Power, Distribution & Specialty Transformer "
            "Manufacturing (keyless CSV, annual avg). PRIMARY, high trust: official BLS index, "
            "transparent methodology. It is the directly-priced signal of the transformer layer's "
            "supply elasticity — a sustained upward break = the layer cannot scale to demand "
            "(the binding-constraint signature). Caveat: a price proxy for lead-time scarcity, not "
            "lead times themselves (those are not keyless); minor subsequent revision (~0.5%)."
        ),
    },
    {
        "id": "PCU335313335313",
        "label": "HV switchgear PPI",
        "metric": "switchgear_ppi",
        "unit": "index (1982=100)",
        "rationale": (
            "FRED / U.S. BLS Producer Price Index for Switchgear & Switchboard Apparatus "
            "Manufacturing (keyless CSV, annual avg). PRIMARY, high trust. The adjacent grid-gear "
            "layer; corroborates the transformer break (the whole electrical-delivery layer is "
            "tightening, not one SKU). Same price-proxy caveat as the transformer PPI."
        ),
    },
    {
        "id": "PCU331420331420",
        "label": "Copper mill products PPI",
        "metric": "copper_ppi",
        "unit": "index",
        "rationale": (
            "FRED / U.S. BLS PPI for Copper Rolling, Drawing & Extruding (keyless CSV, annual avg). "
            "PRIMARY, high trust. Copper is a core conductor input to transformers, switchgear and "
            "grid build; its break (82→146, 2015→2025) corroborates that the electrical-MATERIALS "
            "layer is tightening alongside the equipment — evidence the constraint is systemic, "
            "not one SKU."
        ),
    },
    {
        "id": "WPU101",
        "label": "Iron & steel PPI (GOES proxy)",
        "metric": "steel_ppi",
        "unit": "index (1982=100)",
        "rationale": (
            "FRED / U.S. BLS PPI for Iron & Steel (keyless CSV, annual avg). PRIMARY, high-trust "
            "SOURCE — but a directional PROXY for the deepest bottleneck the graph names, grain-"
            "oriented electrical steel (GOES): GOES-specific price is not public keyless [?]. Break "
            "196→314 (2015→2025) is consistent with (does not prove) the inelasticity of the steel "
            "input behind the transformer. Proxy caveat stated, not faked."
        ),
    },
    {
        "id": "PCU335999335999",
        "label": "Other electrical equipment PPI",
        "metric": "electrical_equip_ppi",
        "unit": "index",
        "rationale": (
            "FRED / U.S. BLS PPI for All Other Electrical Equipment & Components (keyless CSV, "
            "annual avg). PRIMARY, high trust. A broad electrical-equipment price (115→165, "
            "2015→2025) — corroborates the systemic electrical-supply squeeze beyond the named "
            "transformer/switchgear SKUs."
        ),
    },
]


# LBNL "Queued Up" — total active capacity (GW) seeking U.S. grid interconnection, year-end. The
# DEMAND-SIDE constraint metric behind the transformer/switchgear PRICE break: a growing queue =
# the interconnection bottleneck binding harder. The authoritative US dataset (Berkeley Lab compiles
# all 7 ISO/RTO + 26-utility queues). NOT a clean keyless endpoint — the data lives in annual PDFs;
# each value below was GROUNDED from the cited edition (poppler-extracted headline total or the LBNL
# news release), never from memory. Pre-2021 backfill + queue-DURATION (the sharper metric: request→
# agreement reached 35 months in 2022, up sharply since 2015) remain logged gaps — the figure-only
# data resists keyless parse; future annual releases extend this forward (a maintainable cadence).
LBNL_QUEUE: list[dict] = [
    {"year": 2021, "gw": 1430.0, "src": "https://eta-publications.lbl.gov/sites/default/files/queued_up_2021_04-13-2022.pdf",
     "note": "Queued Up (end-2021 edition): ~1,000 GW generation + ~427 GW storage active in queues."},
    {"year": 2022, "gw": 2040.0, "src": "https://emp.lbl.gov/sites/default/files/queued_up_2022_04-06-2023.pdf",
     "note": "Queued Up (end-2022 edition): 'Active capacity in queues (~2,040 GW) exceeds the entire US power-plant fleet (~1,250 GW).'"},
    {"year": 2023, "gw": 2600.0, "src": "https://emp.lbl.gov/news/grid-connection-backlog-grows-30-2023-dominated-requests-solar-wind-and-energy-storage",
     "note": "LBNL release (end-2023): 'nearly 2,600 GW of generation and storage now actively seeking grid interconnection' (+30% in 2023)."},
]
LBNL_QUEUE_RATIONALE = (
    "Lawrence Berkeley National Laboratory (US DOE national lab) 'Queued Up' — the authoritative, "
    "annually-published dataset of capacity seeking US grid interconnection, compiled from all 7 "
    "ISO/RTO queues + 26 utilities. Primary, non-commercial, methodologically documented. Trust < the "
    "FRED PPI (88) because these are rounded HEADLINE totals grounded from the annual PDFs/release "
    "(poppler-extracted), not the raw project workbook — so a conservative ~2% uncertainty is carried, "
    "not faked. Each year's value cites its specific edition (see LBNL_QUEUE[].src)."
)


def _get_text(url: str, *, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 keyless public endpoint
        return resp.read().decode("utf-8", "replace")


def _content_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _fred_annual(series_id: str) -> dict[int, float]:
    """{year: annual-average value} for a FRED series, clamped to the point-in-time window."""
    url = f"{FRED_CSV}?id={series_id}&fq=Annual&fam=avg"
    rows = list(csv.DictReader(io.StringIO(_get_text(url))))
    out: dict[int, float] = {}
    for r in rows:
        raw = (r.get(series_id) or "").strip()
        d = (r.get("observation_date") or "").strip()
        if not raw or raw == "." or len(d) < 4:
            continue
        try:
            year = int(d[:4])
            val = float(raw)
        except ValueError:
            continue
        if WINDOW_START <= year <= CUTOFF_YEAR:
            out[year] = val
    return out


def collect(conn: sqlite3.Connection | None = None, *, log=print) -> dict:
    """Collect the FRED supply-elasticity price series for the AI-power thesis. Idempotent, $0."""
    own = conn is None
    if own:
        conn = db.connect()
        db.init_db(conn)
    # Opening pillar 4 from the supply-price side (strict-layering visibility, rule 2).
    conn.execute("UPDATE pillars SET status='in_progress' WHERE id=? AND status='untapped'",
                 (SUPPLY_PILLAR_ID,))
    conn.commit()

    n_series = n_obs = 0
    log("FRED — AI-power inelastic-layer price signals (annual avg):")
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
            title=f"FRED {spec['id']} — {spec['label']} (PPI, annual avg)",
            pillar_id=SUPPLY_PILLAR_ID, kind=SourceKind.primary, trust_score=88,
            trust_rationale=spec["rationale"], recency=date(last, 12, 31),
            content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=SUPPLY_PILLAR_ID, source_id=source_id, provider="fred",
            external_id=spec["id"], label=spec["label"], metric=spec["metric"],
            unit=spec["unit"], domain="energy/grid",
        )
        series_id = _upsert_series(conn, series)
        n_series += 1
        for y in years:
            v = counts[y]
            _upsert_observation(conn, Observation(
                series_id=series_id, as_of=date(y, 12, 31), value=v,
                unit=spec["unit"], uncertainty=max(0.5, 0.005 * v),  # ~0.5% revision, not faked noise
            ))
            n_obs += 1
        log(f"  + {spec['label']:<28} {years[0]}–{last}  {counts[years[0]]:.0f}→{counts[last]:.0f}")

    # LBNL interconnection-queue total — the demand-side constraint metric (closes the named gap).
    log("LBNL Queued Up — total active capacity in US interconnection queues (year-end, grounded):")
    last = LBNL_QUEUE[-1]
    qsrc = Source(
        url="https://emp.lbl.gov/queues",
        title="LBNL Queued Up — active capacity in US interconnection queues (GW, year-end)",
        pillar_id=SUPPLY_PILLAR_ID, kind=SourceKind.primary, trust_score=85,
        trust_rationale=LBNL_QUEUE_RATIONALE, recency=date(last["year"], 12, 31),
        content_hash=_content_hash({str(r["year"]): r["gw"] for r in LBNL_QUEUE}),
    )
    qsrc_id = _upsert_source(conn, qsrc)
    qseries = Series(
        pillar_id=SUPPLY_PILLAR_ID, source_id=qsrc_id, provider="lbnl",
        external_id="queued_up_active_capacity", label="US interconnection-queue active capacity",
        metric="interconnection_queue_capacity", unit="GW (active)", domain="energy/grid",
    )
    qseries_id = _upsert_series(conn, qseries)
    n_series += 1
    for r in LBNL_QUEUE:
        _upsert_observation(conn, Observation(
            series_id=qseries_id, as_of=date(r["year"], 12, 31), value=r["gw"],
            unit="GW (active)", uncertainty=max(20.0, 0.02 * r["gw"]),  # ~2% on a rounded headline total
        ))
        n_obs += 1
    log(f"  + interconnection-queue capacity  {LBNL_QUEUE[0]['year']}–{last['year']}  "
        f"{LBNL_QUEUE[0]['gw']:.0f}→{last['gw']:.0f} GW  ({len(LBNL_QUEUE)} pts grounded; pre-2021 = logged gap)")

    _log_cost(conn, "fred_collect", "fred", float(len(FRED_SERIES)))
    _log_cost(conn, "lbnl_queue_collect", "lbnl", float(len(LBNL_QUEUE)))
    conn.commit()
    if own:
        conn.close()
    log("Logged gaps (not faked): transformer lead-times (trade-survey); LBNL queue DURATION "
        "(request→agreement 35mo@2022, figure-only); pre-2021 queue backfill; data-center load (EIA key).")
    return {"series": n_series, "obs": n_obs}
