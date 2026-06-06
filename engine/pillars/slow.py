"""The SLOW-constraint aperture — the largest honest gap, opened (execution §7/§10).

The whole engine until now is a TECHNOLOGY-ACCELERATION detector: it fires on a 2nd-derivative bend,
the signature of a capability taking off. But scarcity rent also migrates from slow, non-exponential
forces that trip NO σ-detector and never "surprise" a noise floor — they bind by SLOWLY crossing a
mechanism-defined threshold:
  • demographics — a country's working-age population peaks, then shrinks (you cannot fast-forward
    25-year-olds → labor is the binding constraint, rent to productivity/automation),
  • aging — the old-age dependency ratio rises past a fiscal/labor stress level,
  • water — renewable freshwater per capita falls below the Falkenmark scarcity thresholds,
  • land — arable hectares per person fall toward a food-security floor.

So this pillar pairs the acceleration detector with its sibling: `detector.detect_threshold` — a robust
recent trend vs a SOURCED threshold → years-to-bind, not σ. The data is keyless and primary: the World
Bank's open WDI API (no key). Every series carries a GIGO trust rationale naming the mechanism + the
threshold's literature source. The threshold verdict is persisted to `slow_constraints` for the cockpit.

$0. Every run logs a $0 'auto' cost-ledger row so the gate is exercised, not bypassed (rule 3).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import urllib.request
from datetime import date

from engine import db, detector, store
from engine.pillars.frontier import _log_cost, _upsert_observation, _upsert_series, _upsert_source
from engine.schemas import Observation, Series, Source, SourceKind, _now, _uid

SLOW_PILLAR_ID = 4          # Supply elasticity — where scarcity rent lands (a slow constraint IS inelastic supply)
UA = "predictthefuture research (ruben.stout@edu.escp.eu)"
WB = "https://api.worldbank.org/v2/country/{country}/indicator/{ind}?format=json&date=1970:2024&per_page=200"

# Each slow constraint: a keyless WDI indicator + the MECHANISM threshold it binds at (sourced).
# direction: 'peak' (binds once it's declining), 'falling' (binds below threshold), 'rising' (above).
SLOW_CONSTRAINTS: list[dict] = [
    {"country": "CHN", "ind": "SP.POP.1564.TO", "label": "China working-age population (15–64)",
     "kind": "demographics", "metric": "working_age_pop", "unit": "persons", "scale": 1e6,
     "threshold": None, "direction": "peak",
     "why": "World Bank WDI SP.POP.1564.TO (keyless, primary). China's working-age population peaked "
            "~2015 and is now declining — labor becomes the binding constraint (a shrinking workforce "
            "cannot be fast-forwarded). Rent migrates to labor productivity / automation. Mechanism: a "
            "demographic peak is near-deterministic (the cohorts already exist), unlike a tech curve."},
    {"country": "KOR", "ind": "SP.POP.1564.TO", "label": "South Korea working-age population (15–64)",
     "kind": "demographics", "metric": "working_age_pop", "unit": "persons", "scale": 1e6,
     "threshold": None, "direction": "peak",
     "why": "WDI SP.POP.1564.TO (keyless). Korea's working-age population peaked ~2019 on the lowest "
            "fertility on Earth (~0.7) — the sharpest workforce decline in the OECD; labor + care the "
            "binding constraints."},
    {"country": "KOR", "ind": "SP.POP.DPND.OL", "label": "South Korea old-age dependency ratio",
     "kind": "aging", "metric": "old_age_dependency", "unit": "% (65+ ÷ 15–64)", "scale": 1.0,
     "threshold": 40.0, "direction": "rising",
     "why": "WDI SP.POP.DPND.OL (keyless). Crossing ~40% (≈1 retiree per 2.5 workers) is a severe "
            "fiscal/labor stress level; Korea is the fastest-aging OECD economy and headed there within "
            "the decade. Threshold per OECD/UN aging-society convention."},
    {"country": "DEU", "ind": "SP.POP.DPND.OL", "label": "Germany old-age dependency ratio",
     "kind": "aging", "metric": "old_age_dependency", "unit": "% (65+ ÷ 15–64)", "scale": 1.0,
     "threshold": 50.0, "direction": "rising",
     "why": "WDI SP.POP.DPND.OL (keyless). Germany's ratio (~40% now) heads toward 50% (2 workers per "
            "retiree) as the boomer cohort retires — the binding constraint on its industrial labor base."},
    {"country": "IND", "ind": "ER.H2O.INTR.PC", "label": "India renewable freshwater per capita",
     "kind": "water", "metric": "water_per_capita", "unit": "m³/person/yr", "scale": 1.0,
     "threshold": 1000.0, "direction": "falling",
     "why": "WDI ER.H2O.INTR.PC (keyless). FALKENMARK indicator: <1700 m³ = water stress (India crossed "
            "~2005), <1000 = SCARCITY, <500 = absolute scarcity. India is falling below 1000 — water "
            "becomes the binding agricultural/industrial constraint. Threshold = the canonical Falkenmark line."},
    {"country": "PAK", "ind": "ER.H2O.INTR.PC", "label": "Pakistan renewable freshwater per capita",
     "kind": "water", "metric": "water_per_capita", "unit": "m³/person/yr", "scale": 1.0,
     "threshold": 500.0, "direction": "falling",
     "why": "WDI ER.H2O.INTR.PC (keyless). Falkenmark: Pakistan is among the most water-stressed large "
            "economies, falling toward <500 m³ (absolute scarcity) — a hard ceiling on agriculture."},
    {"country": "WLD", "ind": "AG.LND.ARBL.HA.PC", "label": "World arable land per capita",
     "kind": "land", "metric": "arable_per_capita", "unit": "ha/person", "scale": 1.0,
     "threshold": 0.17, "direction": "falling",
     "why": "WDI AG.LND.ARBL.HA.PC (keyless). Global arable land per person has fallen from ~0.38 ha "
            "(1961) as population grows and land degrades; below ~0.17 ha/person the food system leans "
            "hard on yield (not area) — arable land the binding food constraint. Threshold is a "
            "literature-cited stress level (softer mechanism than Falkenmark — stated, not faked)."},
    {"country": "JPN", "ind": "SP.POP.1564.TO", "label": "Japan working-age population (15–64)",
     "kind": "demographics", "metric": "working_age_pop", "unit": "persons", "scale": 1e6,
     "threshold": None, "direction": "peak",
     "why": "WDI SP.POP.1564.TO (keyless). The textbook case: Japan's working-age population peaked ~1995 "
            "and has fallen ever since — three decades of a binding labor constraint that drove its "
            "automation/robotics lead. The leading indicator of the demographic transition the rest follow."},
    {"country": "CHN", "ind": "SP.POP.DPND.OL", "label": "China old-age dependency ratio",
     "kind": "aging", "metric": "old_age_dependency", "unit": "% (65+ ÷ 15–64)", "scale": 1.0,
     "threshold": 30.0, "direction": "rising",
     "why": "WDI SP.POP.DPND.OL (keyless). China ages BEFORE it gets rich ('未富先老'): old-age dependency "
            "crossing ~30% as the one-child cohorts retire strains pensions + the labor base — a binding "
            "fiscal/labor constraint on the world's #2 economy. OECD aging-society threshold."},
    {"country": "EGY", "ind": "ER.H2O.INTR.PC", "label": "Egypt renewable freshwater per capita",
     "kind": "water", "metric": "water_per_capita", "unit": "m³/person/yr", "scale": 1.0,
     "threshold": 500.0, "direction": "falling",
     "why": "WDI ER.H2O.INTR.PC (keyless). Egypt is among the most water-scarce large nations (~the Nile, "
            "fixed) with a fast-growing population → renewable water/capita falling toward <500 m³ "
            "absolute scarcity (Falkenmark) — the hard ceiling on its agriculture and a geopolitical fault line."},
    # Water SUSTAINABILITY (over-extraction) — a distinct, stronger signal than per-capita AVAILABILITY:
    # withdrawals as a % of internal renewable water. Above 100% a country is withdrawing MORE than nature
    # replenishes — mining the aquifer / drawing down stored capital it cannot replace. A hard physical
    # ceiling (the clean threshold = 100%). WDI ER.H2O.FWTL.ZS, keyless.
    {"country": "SAU", "ind": "ER.H2O.FWTL.ZS", "label": "Saudi Arabia freshwater withdrawal vs renewable",
     "kind": "water", "metric": "water_withdrawal_pct", "unit": "% of internal renewable", "scale": 1.0,
     "threshold": 100.0, "direction": "rising",
     "why": "WDI ER.H2O.FWTL.ZS (keyless). Saudi withdraws ~970% of its renewable water — mining fossil "
            "aquifers that do not recharge. Far past 100% (the sustainability ceiling): the constraint is "
            "binding NOW and terminal (the stored water runs out). The starkest slow-resource constraint."},
    {"country": "PAK", "ind": "ER.H2O.FWTL.ZS", "label": "Pakistan freshwater withdrawal vs renewable",
     "kind": "water", "metric": "water_withdrawal_pct", "unit": "% of internal renewable", "scale": 1.0,
     "threshold": 100.0, "direction": "rising",
     "why": "WDI ER.H2O.FWTL.ZS (keyless). Pakistan withdraws ~320% of renewable water (Indus over-draft) "
            "— mining groundwater faster than recharge; past 100% = binding, a structural food/stability risk."},
    {"country": "IRN", "ind": "ER.H2O.FWTL.ZS", "label": "Iran freshwater withdrawal vs renewable",
     "kind": "water", "metric": "water_withdrawal_pct", "unit": "% of internal renewable", "scale": 1.0,
     "threshold": 100.0, "direction": "rising",
     "why": "WDI ER.H2O.FWTL.ZS (keyless). Iran's withdrawals are climbing toward 100% of renewable supply "
            "— approaching the over-draft ceiling that drives its drying lakes and water-stress unrest."},
]


def _content_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _wb_annual(country: str, ind: str) -> dict[int, float]:
    """{year: value} for a World Bank WDI indicator, keyless. Empty on any failure."""
    url = WB.format(country=country, ind=ind)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 keyless public API
        data = json.loads(r.read())
    if not isinstance(data, list) or len(data) < 2 or not data[1]:
        return {}
    return {int(d["date"]): float(d["value"]) for d in data[1] if d.get("value") is not None}


def _points(conn: sqlite3.Connection, series_id: str) -> list[tuple[float, float]]:
    rows = conn.execute("SELECT as_of, value FROM observations WHERE series_id=? ORDER BY as_of",
                        (series_id,)).fetchall()
    return [(date.fromisoformat(r["as_of"]).year, float(r["value"])) for r in rows]


def _project_crossing(points: list[tuple[float, float]], threshold: float, direction: str,
                      by_year: int, *, window: int = 12, seed: int = 5, n: int = 60_000):
    """MC a drift-with-noise random walk from the latest value to `by_year` → P(crosses threshold by then).

    A slow constraint is near-deterministic (the trend is real and persistent), but NOT certain — the
    year-to-year variability is the honest uncertainty. We sample the step from N(mean Δ, sd Δ) over the
    recent window and count how often the path is past the threshold by the horizon. Returns
    (p_cross, median_final, ci_low, ci_high) or None if too short / horizon ≤ 0."""
    import random
    import statistics
    pts = sorted(points)
    recent = pts[-window:] if len(pts) > window else pts
    deltas = [recent[i + 1][1] - recent[i][1] for i in range(len(recent) - 1)]
    if not deltas:
        return None
    mean_d = statistics.fmean(deltas)
    sd_d = statistics.pstdev(deltas) if len(deltas) > 1 else abs(mean_d) * 0.5
    cur_year, cur_val = pts[-1]
    horizon = by_year - int(cur_year)
    if horizon <= 0:
        return None
    rng = random.Random(seed)
    crossed = 0
    finals: list[float] = []
    for _ in range(n):
        v = cur_val
        for _y in range(horizon):
            v += rng.gauss(mean_d, sd_d)
        finals.append(v)
        if (direction == "falling" and v <= threshold) or (direction == "rising" and v >= threshold):
            crossed += 1
    finals.sort()
    return crossed / n, finals[int(0.5 * n)], finals[int(0.1 * n)], finals[int(0.9 * n)]


def forecast_crossings(conn: sqlite3.Connection | None = None, *, log=print) -> dict:
    """Turn the approaching/crossing slow constraints into immutable forward ForecastCards.

    A slow-constraint card is a SCHEDULED binding: 'does [metric] cross [threshold] by [year]?' —
    point-in-time falsifiable, resolved from one future WDI reading. P comes from the drift-MC (not a
    story), so these enter the scored record like any other forecast (rule 7). Only the not-yet-binding,
    threshold-bearing constraints get a card (a peak with no level, or one already binding, isn't a bet)."""
    from engine import db, forecast
    own = conn is None
    if own:
        conn = db.connect(); db.init_db(conn)
    rows = conn.execute(
        "SELECT sc.series_id, sc.label, sc.constraint_kind, sc.threshold, sc.direction, sc.status, "
        "sc.years_to_cross, s.unit, s.source_id, sc.mechanism "
        "FROM slow_constraints sc JOIN series s ON s.id = sc.series_id "
        "WHERE sc.threshold IS NOT NULL AND sc.crossed = 0 AND sc.years_to_cross IS NOT NULL "
        "ORDER BY sc.years_to_cross"
    ).fetchall()
    made = 0
    for r in rows:
        pts = _points(conn, r["series_id"])
        # The informative horizon is the PROJECTED CROSSING year — there P≈0.5 (a genuine 'does it bind
        # ON SCHEDULE?' test), not a trivial 1.0/0.0. Floor at +3y so it's a real forward call.
        latest_year = int(max(p[0] for p in pts))
        by_year = latest_year + max(3, round(r["years_to_cross"]))
        proj = _project_crossing(pts, r["threshold"], r["direction"], by_year)
        if proj is None:
            continue
        p, med, lo, hi = proj
        if not (0.05 < p < 0.99):   # skip the trivially-certain / trivially-impossible — no information
            log(f"  - skip {r['label']} (P={p:.2f} by {by_year} — not an informative bet)")
            continue
        sign = "below" if r["direction"] == "falling" else "above"
        q = (f"By {by_year}-12-31, does {r['label']} cross {sign} {r['threshold']:g} {r['unit']} — the "
             f"slow {r['constraint_kind']} constraint binding on schedule?")
        if conn.execute("SELECT 1 FROM forecast_cards WHERE question=?", (q,)).fetchone():
            continue
        card = forecast.create_card(
            conn, question=q, probability=round(p, 2), resolution_date=date(by_year, 12, 31),
            ci_low=round(lo, 2), ci_high=round(hi, 2), ci_unit=f"{r['unit']} (MC median {med:.2f})",
            seed_series_id=r["series_id"],
            rationale=(f"SLOW-CONSTRAINT CARD (the aperture, execution §7). {r['mechanism']} Drift-MC over "
                       f"the recent World Bank WDI trend → P(crosses {sign} {r['threshold']:g})={p:.2f} by "
                       f"{by_year}; the year-to-year variability is the honest uncertainty. A scheduled "
                       f"binding, not a tech bet — slow forces are near-deterministic but not certain."),
            kill_criteria=[
                f"The trend reverses (the metric moves back away from {r['threshold']:g}) for 2+ readings.",
                "A WDI revision materially restates the recent level/slope.",
            ],
            pillars_used=[SLOW_PILLAR_ID], source_ids=[r["source_id"]] if r["source_id"] else [],
        )
        made += 1
        log(f"  + card: {r['label'][:38]:<38} P={p:.2f} crosses {sign} {r['threshold']:g} by {by_year}")
    conn.commit()
    if own:
        conn.close()
    log(f"  → {made} slow-constraint forecast cards (scheduled bindings, in the scored record).")
    return {"cards": made}


def collect(conn: sqlite3.Connection | None = None, *, log=print) -> dict:
    """Collect the slow-constraint series (WDI, keyless), run the threshold detector, persist. $0."""
    own = conn is None
    if own:
        conn = db.connect(); db.init_db(conn)
    conn.execute("UPDATE pillars SET status='in_progress' WHERE id=? AND status='untapped'", (SLOW_PILLAR_ID,))
    conn.commit()
    _log_cost(conn, "worldbank_slow", "world_bank", float(len(SLOW_CONSTRAINTS)))

    n_series = n_binding = 0
    log("World Bank WDI — slow-constraint aperture (threshold detector, not acceleration):")
    for spec in SLOW_CONSTRAINTS:
        try:
            vals = _wb_annual(spec["country"], spec["ind"])
        except OSError as e:
            log(f"  ! WDI {spec['country']}/{spec['ind']} unreachable: {e}")
            continue
        vals = {y: v for y, v in vals.items() if v > 0}
        if len(vals) < detector.MIN_POINTS:
            log(f"  - skip {spec['label']} ({len(vals)} yrs)")
            continue
        years = sorted(vals); last = years[-1]
        payload = {str(y): vals[y] for y in years}
        src = Source(
            url=f"https://api.worldbank.org/v2/country/{spec['country']}/indicator/{spec['ind']}",
            title=f"World Bank WDI {spec['ind']} — {spec['label']}",
            pillar_id=SLOW_PILLAR_ID, kind=SourceKind.primary, trust_score=88,
            trust_rationale=spec["why"], recency=date(last, 12, 31), content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=SLOW_PILLAR_ID, source_id=source_id, provider="world_bank",
            external_id=f"{spec['country']}:{spec['ind']}", label=spec["label"],
            metric=spec["metric"], unit=spec["unit"], domain="slow-constraint",
        )
        series_id = _upsert_series(conn, series)
        for y in years:
            _upsert_observation(conn, Observation(
                series_id=series_id, as_of=date(y, 12, 31), value=float(vals[y]),
                unit=spec["unit"], uncertainty=max(1.0, 0.01 * abs(vals[y])),  # WDI revisions ~1%
            ))
        n_series += 1

        # the SLOW signal: threshold detector (years-to-bind), not the σ detector
        sig = detector.detect_threshold(_points(conn, series_id),
                                        threshold=spec["threshold"], direction=spec["direction"])
        if sig is None:
            continue
        conn.execute("DELETE FROM slow_constraints WHERE series_id=?", (series_id,))
        conn.execute(
            "INSERT INTO slow_constraints (id,series_id,label,constraint_kind,threshold,direction,"
            "current_val,slope,crossed,years_to_cross,status,mechanism,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (_uid(), series_id, spec["label"], spec["kind"], spec["threshold"], spec["direction"],
             sig.current, sig.slope, 1 if sig.crossed else 0, sig.years_to_cross, sig.status,
             spec["why"], _now().isoformat()),
        )
        if sig.crossed:
            n_binding += 1
        scaled = lambda v: v / spec["scale"]
        ytc = f"{sig.years_to_cross:.0f}y to bind" if sig.years_to_cross is not None else (
            "BINDING now" if sig.crossed else "stable/away")
        thr = f" (threshold {spec['threshold']:g})" if spec["threshold"] is not None else " (peak)"
        log(f"  + {spec['label'][:42]:<42} {scaled(sig.current):.2f}{thr}  {sig.status.upper():<13} {ytc}")
    conn.commit()
    if own:
        conn.close()
    log(f"  → {n_series} slow-constraint series · {n_binding} BINDING now. "
        "Falkenmark water + demographic peaks = sourced mechanisms, not σ-surprises.")
    return {"series": n_series, "binding": n_binding}
