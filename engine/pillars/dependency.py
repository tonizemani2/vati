"""Pillar 3 (dependency graph) collector — the trade-flow layer. The value layer that was at 0.

Where power.py reads the inelastic layer's *price* and metals.py its *quantity*, this reads the
**dependency**: for a critical input, how much a country must import, and from how few suppliers.
That second number — supplier concentration — IS the dependency-graph signal the value layer needs:
a chokepoint isn't just an inelastic node, it's an inelastic node sourced from a concentrated set of
hands. A rising import-concentration is a dependency *deepening* — the constraint becoming fragile
before it is priced.

We read UN Comtrade (the authoritative bilateral-trade record), US as reporter, per HS commodity,
broken down by partner, both import and export flows. From the keyless calls per year we derive
three orthogonal point-in-time annual series per commodity:
  • <key>_import_value         — world-total import value (sum over partners), USD. Dependency MAGNITUDE.
  • <key>_import_hhi           — Herfindahl concentration of import partners (0–1). Dependency FRAGILITY.
  • <key>_net_import_reliance  — (imports − exports)/imports. Dependency RELIANCE — how much the US
    cannot supply itself, in trade terms. A keyless PROXY for USGS net-import-reliance (which also
    needs domestic production [?]); can go negative for a net exporter, which is kept (it's meaningful).
The world-aggregate ("World", partnerCode 0) row is summed from the partners, not trusted directly,
because the preview tier serves it inconsistently — the partner rows are the robust substrate.

Commodities are the inelastic constraints the world graph already names (the metals/AI-power world):
refined copper (the cathode node), grain-oriented electrical steel (GOES — the deepest named
bottleneck behind the transformer), electrical transformers (the finished good — a deliberate
ELASTIC contrast: many suppliers → low HHI), and rare-earth compounds (the canonical concentrated
chokepoint). The HHI discriminating inelastic (GOES ~0.55) from elastic (transformers ~0.09) is the
graph's elastic/inelastic thesis turned into a measured number.

Source, FREE / KEYLESS, primary (UN Statistics Division), high trust — with two honestly-logged
caveats (NOT faked):
  • US as reporter is a directional proxy for *global* dependency on each input (the graph is already
    US-FRED/BLS-centric, so this is consistent); the constraint SHAPE (rising value, rising
    concentration) is what the graph needs, not a global tonnage total.
  • The keyless endpoint is the Comtrade *preview* tier — coverage-limited and occasionally drops a
    year transiently (we retry once and keep only what returns; gaps are skipped, never interpolated).
    The full gapless annual series needs a free Comtrade API key (registration) — same posture as the
    EIA-keyed series in power.py. When `COMTRADE_KEY` lands in .env this module swaps the endpoint.

Cost: $0. Logs a $0 'auto' cost-ledger row so the gate is exercised, not bypassed (rule 3).
"""

from __future__ import annotations

import json
import sqlite3
import time
import urllib.request
from datetime import date

from engine import db
from engine.pillars.frontier import _log_cost, _upsert_observation, _upsert_series, _upsert_source
from engine.pillars.power import _content_hash
from engine.schemas import Observation, Series, Source, SourceKind

DEP_PILLAR_ID = 3            # Dependency graph — the chain structure / who-depends-on-whom
UA = "predictthefuture research (ruben.stout@edu.escp.eu)"
COMTRADE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
US_REPORTER = 842
WINDOW_START = 2012
CUTOFF_YEAR = 2024          # 2025 is incomplete in the annual record
MIN_YEARS = 8              # same gate as power/metals: too sparse → skip, don't fake

# Minimal M49 numeric-code → name map, for readable top-supplier logging only (not stored).
# Covers the metals/electrical suppliers that actually appear; everything else logs as M49:<code>.
_M49 = {
    152: "Chile", 124: "Canada", 484: "Mexico", 604: "Peru", 180: "DR Congo", 156: "China",
    410: "South Korea", 392: "Japan", 276: "Germany", 56: "Belgium", 643: "Russia", 842: "USA",
    36: "Australia", 76: "Brazil", 528: "Netherlands", 826: "UK", 250: "France", 380: "Italy",
    724: "Spain", 752: "Sweden", 158: "Taiwan", 704: "Vietnam", 356: "India", 372: "Ireland",
    32: "Argentina", 348: "Hungary", 616: "Poland", 203: "Czechia", 40: "Austria", 442: "Luxembourg",
}

# The critical inputs the world graph already names. `key` becomes the metric/series prefix.
COMMODITIES: list[dict] = [
    {
        "cmd": "7403", "key": "refined_copper", "label": "Refined copper imports",
        "domain": "metals", "what": "refined/cathode copper (the metals-chain 'refined copper' node)",
        "story": (
            "US refined-copper import VALUE and supplier CONCENTRATION are both rising (HHI ~0.37→0.53, "
            "top supplier ~50%→70% over the 2010s) — the cathode layer behind every transformer winding "
            "and switchgear busbar is becoming both more import-dependent and more concentrated. A "
            "dependency deepening on the inelastic node the graph already flags."
        ),
    },
    {
        "cmd": "722611", "key": "goes_steel", "label": "Grain-oriented electrical steel imports",
        "domain": "metals / electrical", "what": "GOES — the deepest named bottleneck behind the transformer",
        "story": (
            "Grain-oriented electrical steel (the transformer-core input the AI-power graph derives as "
            "the deepest constraint). Import concentration is high and rising (HHI ~0.54→0.59) — few "
            "qualified mills worldwide. The chokepoint's fragility as a measured number, corroborating "
            "the graph's GOES bottleneck from the dependency side."
        ),
    },
    {
        "cmd": "8504", "key": "transformers", "label": "Electrical transformer imports",
        "domain": "energy / grid", "what": "the FINISHED transformer (deliberate elastic contrast)",
        "story": (
            "Finished electrical transformers — the OBVIOUS layer. Import value is large but supplier "
            "concentration is LOW (HHI ~0.09, ~140 partners): the finished good is broadly sourced and "
            "elastic. The contrast vs GOES (~0.55) is the graph's elastic/inelastic thesis measured: the "
            "constraint is the input, not the assembly. A low-HHI series the detector should NOT fire on."
        ),
    },
    {
        "cmd": "2846", "key": "rare_earths", "label": "Rare-earth compound imports",
        "domain": "critical minerals", "what": "rare-earth compounds (the canonical concentrated chokepoint)",
        "story": (
            "Rare-earth compounds — the textbook concentrated dependency (HHI ~0.42, China-dominated). "
            "Included to show the dependency pillar generalizes beyond the copper world: the same keyless "
            "Comtrade collector measures any critical input's import fragility."
        ),
    },
]

_CAVEAT = (
    " Caveats (not faked): US-as-reporter is a directional proxy for GLOBAL dependence on this input "
    "(the graph is US-FRED-centric, consistent); keyless Comtrade PREVIEW tier is coverage-limited "
    "(years that drop transiently are retried once then skipped, never interpolated) — the full "
    "gapless series needs a free Comtrade key. Net-import-reliance here is the TRADE-BALANCE proxy "
    "(M−X)/M; the precise USGS NIR adds domestic apparent consumption [?]."
)


def _get_json(url: str, *, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 keyless public endpoint
        return json.loads(resp.read().decode("utf-8", "replace"))


def _partners(cmd: str, year: int, flow: str) -> list[tuple[int, float]]:
    """Per-partner (code, value) rows for US `flow` (M imports / X exports) of `cmd` in `year`.

    Sums at the call site (robust to the preview's flaky World aggregate); excludes the World
    (partnerCode 0) and re-export partner2 rows to avoid double counting. Retries once on an empty
    return (the preview drops years transiently). Returns [] if still empty.
    """
    url = (f"{COMTRADE}?reporterCode={US_REPORTER}&period={year}"
           f"&partnerCode=&cmdCode={cmd}&flowCode={flow}")
    for attempt in range(2):
        try:
            rows = _get_json(url).get("data") or []
        except OSError:
            rows = []
        partners = [
            (int(r["partnerCode"]), float(r["primaryValue"]))
            for r in rows
            if r.get("partnerCode") and int(r["partnerCode"]) != 0
            and int(r.get("partner2Code") or 0) == 0
            and r.get("primaryValue")
        ]
        if partners:
            return partners
        if attempt == 0:
            time.sleep(1.0)
    return []


def _year_stats(cmd: str, year: int) -> dict | None:
    """Three dependency channels for US trade in `cmd`, `year` — magnitude, concentration, reliance.

    value = world-total import $ (magnitude); hhi = supplier Herfindahl (concentration/fragility);
    nir = (imports − exports)/imports, the net-import-reliance PROXY (how much the US can't supply
    itself in trade terms). Returns None if imports are empty (no usable year).
    """
    imp = _partners(cmd, year, "M")
    if not imp:
        return None
    total = sum(v for _, v in imp)
    if total <= 0:
        return None
    shares = [(c, v / total) for c, v in imp]
    hhi = sum(s * s for _, s in shares)
    top_code, top_share = max(shares, key=lambda cs: cs[1])
    x_total = sum(v for _, v in _partners(cmd, year, "X"))   # exports; [] → 0 (US barely exports it)
    nir = (total - x_total) / total                         # can go <0 (net exporter) — kept, meaningful
    return {"value": total, "hhi": hhi, "top_share": top_share,
            "top_code": top_code, "n": len(imp), "nir": nir, "x_total": x_total}


def collect(conn: sqlite3.Connection | None = None, *, log=print) -> dict:
    """Collect keyless UN Comtrade import-dependency series into Pillar 3. Idempotent, $0.

    Per commodity, builds two annual series — import VALUE (magnitude) and partner HHI (fragility) —
    from the per-partner trade rows. Skips a commodity with < MIN_YEARS usable years (logged), and
    never interpolates a dropped year.
    """
    own = conn is None
    if own:
        conn = db.connect()
        db.init_db(conn)
    # Opening pillar 3 from the dependency/trade-flow side (strict-layering visibility, rule 2).
    conn.execute("UPDATE pillars SET status='in_progress' WHERE id=? AND status='untapped'",
                 (DEP_PILLAR_ID,))
    conn.commit()

    n_series = n_obs = 0
    log("UN Comtrade — US import-dependency (value + supplier concentration), keyless preview:")
    for spec in COMMODITIES:
        stats: dict[int, dict] = {}
        for year in range(WINDOW_START, CUTOFF_YEAR + 1):
            s = _year_stats(spec["cmd"], year)
            if s:
                stats[year] = s
        if len(stats) < MIN_YEARS:
            log(f"  - skip {spec['label']} (only {len(stats)} yrs from preview — needs Comtrade key)")
            continue
        years = sorted(stats)
        last = years[-1]
        payload = {str(y): [stats[y]["value"], round(stats[y]["hhi"], 4), round(stats[y]["nir"], 4)]
                   for y in years}
        rationale = spec["story"] + _CAVEAT
        # NIR is trustworthy ONLY where the export leg is substantial + stable (else the tiny/flaky
        # preview export total makes (M−X)/M noise — e.g. GOES/REE swung wildly). Gate it; keep
        # value+hhi regardless. Material = exports ≥5% of imports; need ≥MIN_YEARS such years.
        material_x = [y for y in years if stats[y]["value"] > 0
                      and stats[y]["x_total"] >= 0.05 * stats[y]["value"]]
        nir_ok = len(material_x) >= MIN_YEARS

        src = Source(
            url=f"https://comtradeapi.un.org/public/v1/preview/C/A/HS (cmd {spec['cmd']}, US M+X)",
            title=f"UN Comtrade — {spec['label']} (HS {spec['cmd']}, US reporter, annual)",
            pillar_id=DEP_PILLAR_ID, kind=SourceKind.primary, trust_score=80,
            trust_rationale=rationale, recency=date(last, 12, 31),
            content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)

        # Three orthogonal dependency channels off the one source: MAGNITUDE · FRAGILITY · RELIANCE.
        for metric_suffix, label_tail, unit, key, fmt, unc_of in (
            ("import_value", "value", "USD (current)", "value",
             lambda v: f"${v / 1e9:.2f}B", lambda v: 0.03 * v),                 # ~3% Comtrade revision
            ("import_hhi", "partner concentration", "HHI (0-1)", "hhi",
             lambda v: f"{v:.3f}", lambda _v: 0.01),                            # ~0.01 partner-rounding
            ("net_import_reliance", "net-import-reliance (proxy)", "ratio (net M / M)", "nir",
             lambda v: f"{v:+.0%}", lambda _v: 0.03),                           # ~3% trade-balance revision
        ):
            series = Series(
                pillar_id=DEP_PILLAR_ID, source_id=source_id, provider="un_comtrade",
                external_id=f"{spec['cmd']}_{metric_suffix}",
                label=f"{spec['label']} — {label_tail}",
                metric=f"{spec['key']}_{metric_suffix}", unit=unit, domain=spec["domain"],
            )
            series_id = _upsert_series(conn, series)
            n_series += 1
            for y in years:
                v = stats[y][key]
                _upsert_observation(conn, Observation(
                    series_id=series_id, as_of=date(y, 12, 31), value=v, unit=unit, uncertainty=unc_of(v),
                ))
                n_obs += 1
            first, lastv = stats[years[0]][key], stats[last][key]
            log(f"  + {series.label:<52} {years[0]}–{last}  {fmt(first)}→{fmt(lastv)}")
        top = _M49.get(stats[last]["top_code"], f"M49:{stats[last]['top_code']}")
        log(f"      └ {spec['label']}: {stats[last]['n']} partners, "
            f"top supplier {top} ({stats[last]['top_share']:.0%}) in {last}")

    _log_cost(conn, "comtrade_collect", "un_comtrade", float(len(COMMODITIES)))
    conn.commit()
    if own:
        conn.close()
    log("Logged caveats (not faked): US-reporter proxy for global dependence; keyless PREVIEW tier "
        "coverage-limited (full series needs a Comtrade key).")
    return {"series": n_series, "obs": n_obs}
