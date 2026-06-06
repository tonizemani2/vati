"""Pillar 6 — Capital flows (free / keyless). Where is money already going?

A direct read on where capital/commercial attention concentrates: how many SEC filings mention a
technology each year (EDGAR full-text search, keyless, covers 2001+). Rising filing-mention velocity
= incumbents + issuers increasingly building/disclosing around a tech — a market-side signal that
complements the research velocity (pillar 1) and the pricing gate (pillar 7). The *rate of change*
is the signal (incumbent attention reveals where THEY see the constraint).

Phrase full-text match is fuzzy (a mention ≠ a bet), so trust is mid and it's tagged domain="capital".
$0; SEC fair-access UA (with contact) per their policy; a cost-ledger row is logged (rule 3).
"""

from __future__ import annotations

import json
import sqlite3
import time
import urllib.parse
import urllib.request
from datetime import date
from math import sqrt

from engine import store
from engine.pillars.frontier import UA, _content_hash, _log_cost, _upsert_series, _upsert_source
from engine.schemas import Observation, Series, Source, SourceKind

CAPITAL_PILLAR_ID = 6
EFTS = "https://efts.sec.gov/LATEST/search-index"
WINDOW_START, CUTOFF_YEAR = 2004, 2024   # EDGAR full-text search begins 2001; first reliable window 2004

PHRASES: list[str] = [
    "artificial intelligence", "machine learning", "quantum computing", "data center",
    "semiconductor", "electric vehicle", "lithium ion battery", "solid state battery",
    "autonomous vehicle", "gene therapy", "crispr", "mrna", "nuclear fusion", "hydrogen",
    "blockchain",
]


def _filing_count(phrase: str, year: int, *, retries: int = 2) -> int | None:
    q = urllib.parse.quote(f'"{phrase}"')
    url = f"{EFTS}?q={q}&startdt={year}-01-01&enddt={year}-12-31"
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            data = json.loads(urllib.request.urlopen(req, timeout=30).read())
            return int(data.get("hits", {}).get("total", {}).get("value", 0))
        except Exception:  # noqa: BLE001 — SEC 403/rate-limit/parse: back off, retry, then None
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            return None


# --- Capex acceleration — SEC XBRL companyconcept (keyless, primary) ----------
# The harder, higher-trust capital signal: actual $ incumbents POUR INTO capacity, per fiscal year.
# Per the thesis (§0.5, plan), capital flooding a layer EXPANDS supply → the constraint *dissolves*
# there — so accelerating capex tells you where the bottleneck WON'T be (the elastic tell), and a
# layer starved of capex despite a demand shock is where rent lands. We read it straight from the
# primary XBRL filings (no full-text fuzz), so trust is high. Tag varies by filer → a fallback list
# (like revenue in consensus.py). Companies are tagged by their constraint LAYER as a reading prior
# (not a hard claim — like the laggard tag): elastic compute vs inelastic grid/power vs bio.
CAPEX_TAGS = (
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireProductiveAssets",
    "PaymentsForCapitalImprovements",
    "PaymentsToAcquireOtherPropertyPlantAndEquipment",
    "PaymentsToAcquireMachineryAndEquipment",
)
# {sym: (cik, name, layer)}. CIKs SEC-verified via company_tickers.json (GIGO — know what you measure).
CAPEX_COMPANIES: dict[str, tuple[int, str, str]] = {
    "NVDA": (1045810, "NVIDIA (AI accelerators)", "elastic-compute"),
    "AMD":  (2488,    "AMD (accelerators)", "elastic-compute"),
    "AVGO": (1730168, "Broadcom (networking/ASIC)", "elastic-compute"),
    "MU":   (723125,  "Micron (HBM/memory)", "elastic-compute"),
    "ETN":  (1551182, "Eaton (electrical/power mgmt)", "inelastic-grid"),
    "HUBB": (48898,   "Hubbell (grid equipment)", "inelastic-grid"),
    "PWR":  (1050915, "Quanta (grid construction)", "inelastic-grid"),
    "VRT":  (1674101, "Vertiv (datacenter power/cooling)", "inelastic-grid"),
    "GEV":  (1996810, "GE Vernova (grid + power equip)", "inelastic-grid"),
    "TXG":  (1770787, "10x Genomics (scRNA-seq consumable)", "bio-consumable"),
    "ILMN": (1110803, "Illumina (sequencers)", "bio-sequencer"),
}


def _annual_capex(conn: sqlite3.Connection, cik: int) -> dict[int, float]:
    """Full-year capex (USD) by fiscal-year-end, merged across the tag fallback. A row counts as a
    full year if its period spans ~365d (drops 10-Q YTD partials); latest-filed wins per year."""
    from engine import consensus
    out: dict[int, tuple[float, str]] = {}
    for tag in CAPEX_TAGS:
        for r in consensus._xbrl_concept(conn, cik, "us-gaap", tag, "USD"):
            try:
                s = date.fromisoformat(r["start"]); e = date.fromisoformat(r["end"])
            except (KeyError, ValueError):
                continue
            if 350 <= (e - s).days <= 380:
                y = e.year
                if y not in out or str(r.get("filed", "")) > out[y][1]:
                    out[y] = (float(r["val"]), str(r.get("filed", "")))
    return {y: v for y, (v, _f) in out.items()}


def collect_capex(conn: sqlite3.Connection | None = None, *, log=print) -> dict:
    """Per-company capex acceleration from SEC XBRL (Pillar 6, the elasticity tell). Idempotent. $0."""
    from engine import db
    own = conn is None
    if own:
        conn = db.connect(); db.init_db(conn)
    _log_cost(conn, "edgar_capex_collect", "sec_edgar", float(len(CAPEX_COMPANIES)))
    n_series = n_obs = 0
    for sym, (cik, name, layer) in CAPEX_COMPANIES.items():
        capex = _annual_capex(conn, cik)
        capex = {y: v for y, v in capex.items() if v > 0}
        if len(capex) < 8:  # detector needs ≥8 points; never store a stub
            log(f"  - skip {sym} ({len(capex)} fiscal years of capex)")
            continue
        ys = sorted(capex); last = ys[-1]
        payload = {str(y): capex[y] for y in ys}
        src = Source(
            url=f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{CAPEX_TAGS[0]}.json",
            title=f"SEC XBRL capex — {name} [{sym}]",
            pillar_id=CAPITAL_PILLAR_ID, kind=SourceKind.filing, trust_score=85,
            trust_rationale=(
                f"SEC XBRL companyconcept (keyless, primary 10-K filings, CIK {cik}): capital "
                f"expenditure per fiscal year for {name}. High trust — primary regulatory numbers, "
                "not full-text fuzz. Merged across a capex-tag fallback list; full-year rows only "
                "(~365d span, drops 10-Q YTD partials); latest-filed wins per year. Layer tag "
                f"'{layer}' is a reading prior (capital flooding a layer = it turns elastic), not a claim."
            ),
            recency=date(last, 12, 31), content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=CAPITAL_PILLAR_ID, source_id=source_id, provider="sec_edgar",
            external_id=f"{sym} capex", label=f"{sym} capex ({layer})", metric="capex_usd",
            unit="USD/year", domain="capital",
        )
        series_id = _upsert_series(conn, series)
        store.bulk_upsert_observations(conn, [
            Observation(series_id=series_id, as_of=date(y, 12, 31), value=capex[y],
                        unit="USD/year", uncertainty=max(1.0, 0.02 * capex[y]))  # ~2% reporting/restatement
            for y in ys
        ])
        n_series += 1; n_obs += len(ys)
        log(f"  + {sym:<5} {layer:<16} {ys[0]}–{last}  ${capex[ys[0]]/1e6:.0f}M→${capex[last]/1e6:.0f}M")
    conn.commit()
    if own:
        conn.close()
    return {"series": n_series, "obs": n_obs}


# --- Thesis-resolving revenue series (component 8 → forward cards) -------------
# A SURVIVED hypothesis becomes a forward ForecastCard only when a point-in-time series can RESOLVE it
# (rule 7 + projectibility §0.5). For a constraint-migration thesis, the cleanest resolving signal is
# the REVENUE of the inelastic, rent-capturing public company the thesis names — rent actually landing
# at that layer, read straight from primary XBRL (keyless, high trust). CIKs SEC-verified (GIGO).
THESIS_PLAYERS: dict[str, tuple[int, str, str, str]] = {
    "LEU": (1065059, "Centrus Energy", "nuclear/enrichment",
            "The only US-based uranium ENRICHER (SWU + HALEU) — the inelastic layer the nuclear-restart "
            "thesis names. Revenue = enrichment rent. Honest caveat: 2008–13 is the legacy USEC SWU "
            "contract book (a structural decline post-bankruptcy); the 2018→2025 RECOVERY ($193M→$449M) "
            "is the enrichment-demand return the thesis is actually about — so read the recent trend."),
    "WST": (105770, "West Pharmaceutical Services", "glp1/injection",
            "The dominant maker of injectable drug-delivery components (elastomer closures, syringe "
            "systems) — the inelastic consumable every GLP-1 pen needs. Revenue = injection-consumable "
            "rent; clean ~3× growth 2008→2025, accelerating into the GLP-1 wave (2019–21). Caveat: WST "
            "serves all injectables, so it is a broad (not GLP-1-pure) proxy for the consumable layer."),
}


def _annual_revenue(conn: sqlite3.Connection, cik: int) -> dict[int, float]:
    """Full-year revenue (USD) by fiscal-year-end, merged across the revenue-tag fallback; ~365d rows
    only (drops 10-Q YTD partials); latest-filed wins per year. Mirrors `_annual_capex`."""
    from engine import consensus
    out: dict[int, tuple[float, str]] = {}
    for tag in consensus._REVENUE_TAGS:
        for r in consensus._xbrl_concept(conn, cik, "us-gaap", tag, "USD"):
            try:
                s = date.fromisoformat(r["start"]); e = date.fromisoformat(r["end"])
            except (KeyError, ValueError):
                continue
            if 350 <= (e - s).days <= 380:
                y = e.year
                if y not in out or str(r.get("filed", "")) > out[y][1]:
                    out[y] = (float(r["val"]), str(r.get("filed", "")))
    return {y: v for y, (v, _f) in out.items()}


def collect_thesis_revenue(conn: sqlite3.Connection | None = None, *, log=print) -> dict:
    """Annual revenue (SEC XBRL) for the inelastic-layer players that RESOLVE survived hypotheses. $0."""
    from engine import db
    own = conn is None
    if own:
        conn = db.connect(); db.init_db(conn)
    _log_cost(conn, "edgar_thesis_revenue", "sec_edgar", float(len(THESIS_PLAYERS)))
    n_series = n_obs = 0
    for sym, (cik, name, tag, why) in THESIS_PLAYERS.items():
        rev = {y: v for y, v in _annual_revenue(conn, cik).items() if v > 0}
        if len(rev) < 8:
            log(f"  - skip {sym} ({len(rev)} fiscal years of revenue)")
            continue
        ys = sorted(rev); last = ys[-1]
        payload = {str(y): rev[y] for y in ys}
        src = Source(
            url=f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/Revenues.json",
            title=f"SEC XBRL revenue — {name} [{sym}]",
            pillar_id=CAPITAL_PILLAR_ID, kind=SourceKind.filing, trust_score=88,
            trust_rationale=(
                f"SEC XBRL companyconcept (keyless, primary 10-K, CIK {cik}): annual revenue for "
                f"{name}. The inelastic, rent-capturing layer for the '{tag}' constraint-migration "
                f"thesis — revenue = rent landing there. {why} Merged across the revenue-tag fallback; "
                "full-year rows only; latest-filed wins. ~2% restatement uncertainty."
            ),
            recency=date(last, 12, 31), content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=CAPITAL_PILLAR_ID, source_id=source_id, provider="sec_edgar",
            external_id=f"{sym} revenue", label=f"{sym} revenue ({tag})", metric="revenue_usd",
            unit="USD/year", domain="capital",
        )
        series_id = _upsert_series(conn, series)
        store.bulk_upsert_observations(conn, [
            Observation(series_id=series_id, as_of=date(y, 12, 31), value=rev[y],
                        unit="USD/year", uncertainty=max(1.0, 0.02 * rev[y]))
            for y in ys
        ])
        n_series += 1; n_obs += len(ys)
        log(f"  + {sym:<5} {tag:<18} {ys[0]}–{last}  ${rev[ys[0]]/1e6:.0f}M→${rev[last]/1e6:.0f}M")
    conn.commit()
    if own:
        conn.close()
    return {"series": n_series, "obs": n_obs}


# --- Government procurement obligations (USAspending, keyless) -----------------
# The DEMAND pull that resolves a constraint-migration thesis whose inelastic layer has no public
# pure-play: actual federal contract $/fiscal-year for a product class. The re-armament→energetics
# thesis is exactly this — ammunition + propellant/explosive procurement is the measurable demand
# pulling on the (privately-held) energetics supply. USAspending.gov v2 is keyless, primary, official.
USASPENDING = "https://api.usaspending.gov/api/v2/search/spending_over_time/"
PROCUREMENT_GROUPS: dict[str, dict] = {
    "ammunition & energetics": {
        # PSC: 1305/1310/1315 ammunition · 1336 missile warheads · 1376/1377 explosives & propellants
        "psc": ["1305", "1310", "1315", "1336", "1376", "1377"],
        "metric": "energetics_procurement_usd", "domain": "capital", "thesis": "rearm/energetics",
        "why": (
            "US federal contract obligations per fiscal year for ammunition + explosives/propellants "
            "(USAspending.gov v2, keyless, official primary). The measurable DEMAND pulling on the "
            "energetics supply layer (which has no public pure-play to read directly). Textbook "
            "re-armament shape: post-Iraq drawdown to ~$1.35B (FY15) then a Ukraine-era surge "
            "($1.6B FY21 → $5.0B FY25). Caveat: obligations are demand, not energetics-maker capacity."
        ),
    },
}


def _procurement_by_fy(psc: list[str], *, start_fy: int = 2008, end_fy: int = 2025) -> dict[int, float]:
    """Annual federal contract obligations (USD) for a PSC set, by fiscal year. Keyless POST."""
    body = json.dumps({
        "group": "fiscal_year",
        "filters": {
            "time_period": [{"start_date": f"{start_fy}-10-01", "end_date": f"{end_fy}-09-30"}],
            "psc_codes": psc, "award_type_codes": ["A", "B", "C", "D"],
        },
    }).encode()
    req = urllib.request.Request(USASPENDING, data=body,
                                 headers={"User-Agent": UA, "Content-Type": "application/json"})
    data = json.loads(urllib.request.urlopen(req, timeout=45).read())  # noqa: S310 keyless public API
    out: dict[int, float] = {}
    for r in data.get("results", []):
        fy = r.get("time_period", {}).get("fiscal_year")
        amt = r.get("aggregated_amount")
        if fy and amt is not None:
            out[int(fy)] = float(amt)
    return out


def collect_procurement(conn: sqlite3.Connection | None = None, *, log=print) -> dict:
    """Federal procurement obligations per product class (USAspending, keyless). Idempotent. $0."""
    from engine import db
    own = conn is None
    if own:
        conn = db.connect(); db.init_db(conn)
    _log_cost(conn, "usaspending_procurement", "usaspending", float(len(PROCUREMENT_GROUPS)))
    n_series = n_obs = 0
    for name, spec in PROCUREMENT_GROUPS.items():
        try:
            obs = {y: v for y, v in _procurement_by_fy(spec["psc"]).items() if v > 0}
        except OSError as e:
            log(f"  ! USAspending unreachable for {name}: {e}")
            continue
        if len(obs) < 8:
            log(f"  - skip {name} ({len(obs)} fiscal years)")
            continue
        ys = sorted(obs); last = ys[-1]
        payload = {str(y): obs[y] for y in ys}
        src = Source(
            url=USASPENDING + "?psc=" + ",".join(spec["psc"]),
            title=f"USAspending — {name} federal procurement obligations (FY)",
            pillar_id=CAPITAL_PILLAR_ID, kind=SourceKind.filing, trust_score=85,
            trust_rationale=spec["why"], recency=date(last, 12, 31), content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=CAPITAL_PILLAR_ID, source_id=source_id, provider="usaspending",
            external_id=name, label=f"{name} (federal procurement)", metric=spec["metric"],
            unit="USD/fiscal-year", domain=spec["domain"],
        )
        series_id = _upsert_series(conn, series)
        store.bulk_upsert_observations(conn, [
            Observation(series_id=series_id, as_of=date(y, 12, 31), value=obs[y],
                        unit="USD/fiscal-year", uncertainty=max(1.0, 0.01 * obs[y]))  # obligations are exact
            for y in ys
        ])
        n_series += 1; n_obs += len(ys)
        log(f"  + {name:<24} FY{ys[0]}–{last}  ${obs[ys[0]]/1e6:.0f}M→${obs[last]/1e6:.0f}M")
    conn.commit()
    if own:
        conn.close()
    return {"series": n_series, "obs": n_obs}


def collect(conn: sqlite3.Connection | None = None, *, log=print) -> dict:
    """SEC filing-mention velocity per technology phrase per year. Idempotent. $0."""
    from engine import db
    own = conn is None
    if own:
        conn = db.connect()
        db.init_db(conn)
    _log_cost(conn, "edgar_fts_collect", "sec_edgar", float(len(PHRASES)))
    years = list(range(WINDOW_START, CUTOFF_YEAR + 1))
    if _filing_count(PHRASES[0], CUTOFF_YEAR) is None:
        log("  ! EDGAR full-text search unreachable — skipping capital this run. 0 series.")
        conn.commit()
        if own:
            conn.close()
        return {"series": 0, "obs": 0}
    n_series = n_obs = 0
    for phrase in PHRASES:
        counts: dict[int, int] = {}
        for y in years:
            c = _filing_count(phrase, y)
            if c is not None:
                counts[y] = c
            time.sleep(0.12)  # polite — SEC fair-access (~10 req/s ceiling)
        counts = {y: v for y, v in counts.items() if v > 0}
        if len(counts) < 8:
            log(f"  - skip {phrase!r} ({len(counts)} yrs)")
            continue
        ys = sorted(counts)
        last = ys[-1]
        payload = {str(y): counts[y] for y in ys}
        src = Source(
            url=f"{EFTS}?q=%22{urllib.parse.quote(phrase)}%22",
            title=f'SEC EDGAR filing mentions — "{phrase}"',
            pillar_id=CAPITAL_PILLAR_ID, kind=SourceKind.filing, trust_score=70,
            trust_rationale=(
                "SEC EDGAR full-text search (keyless, official primary filings): count of filings "
                "mentioning the phrase per year — a capital/commercial-attention velocity. Caveats: "
                "full-text phrase match is fuzzy (a mention is not a bet); covers EDGAR filers only; "
                "rising rate-of-change is the signal, not the level."
            ),
            recency=date(last, 12, 31), content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=CAPITAL_PILLAR_ID, source_id=source_id, provider="sec_edgar",
            external_id=phrase, label=f"{phrase} (SEC filings)", metric="sec_filing_mentions",
            unit="filings/year", domain="capital",
        )
        series_id = _upsert_series(conn, series)
        store.bulk_upsert_observations(conn, [
            Observation(series_id=series_id, as_of=date(y, 12, 31), value=float(counts[y]),
                        unit="filings/year", uncertainty=max(1.0, sqrt(counts[y])))
            for y in ys
        ])
        n_series += 1
        n_obs += len(ys)
        log(f"  + {phrase:<26} {ys[0]}–{last}  {counts[ys[0]]}→{counts[last]} filings/yr")
    conn.commit()
    if own:
        conn.close()
    return {"series": n_series, "obs": n_obs}
