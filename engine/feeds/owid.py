"""Our World in Data (OWID) — keyless collector for structural energy/tech-adoption series.

OWID republishes its grapher charts as fully public CSVs (NO API key, no auth):
    https://ourworldindata.org/grapher/<slug>.csv?v=1&csvType=full&useColumnShortNames=true
The CSV is tidy long-format: columns `entity,code,year,<value_column>`, one row per
(entity, year). We fetch the FULL csv and keep the values exactly as published — every
observation carries its REAL reporting year as its date (point-in-time, leak-safe). We never
synthesize, backfill, or interpolate a missing year; a gap in OWID's CSV stays a gap here.

This module is self-contained on purpose (the broader engine collectors write to SQLite via
db.py; this one only writes a flat JSONL sample to data/feeds/owid.jsonl). It mirrors the style
of engine/pillars/power.py: an explicit per-series spec with a stated trust rationale, urllib
fetch with a UA, and a LEADING vs LAG/CONFIRMATION tag for each signal.

Three adoption datasets plus the compact capability-curve basket, all confirmed keyless:
  • share-electricity-renewables — renewable share of electricity generation (%), per country/region.
        LEADING: the generation-mix share moves AHEAD of the priced fossil-asset / utility-revenue
        outcome — a rising renewable share telegraphs stranded-fossil and grid-rebuild pressure years
        before it shows up in incumbent earnings.
  • solar-pv-prices — solar PV module price (USD per watt), the global cost curve.
        LEADING: the module cost curve leads deployment and the capex/levelised-cost outcomes that
        markets eventually price; the price drop precedes the demand build it unlocks.
  • electric-car-sales-share — EV share of new car sales (%), per country/region.
        LEADING: new-sales share leads the FLEET stock and the oil-demand / ICE-supplier revenue
        outcome by the vehicle-replacement lag (sales today => fleet & demand shift over years).

OWID is a CONFIRMATION-grade *aggregator* of primary sources (Ember, IRENA, IEA), but the SIGNALS
themselves are leading relative to the economic outcomes they predict — so leak_class = leading.

Cost: $0, keyless. Reasoning stays in-session; this module only collects + samples.
"""

from __future__ import annotations

import csv
import io
import json
import urllib.request
from datetime import date
from pathlib import Path

from engine.pillars.capability import CURVES as CAPABILITY_CURVES
from engine.pillars.capability import CUTOFF_YEAR, WINDOW_START

UA = "predictthefuture research (research@vaticinus.com)"
GRAPHER = "https://ourworldindata.org/grapher/{slug}.csv"
OUT_PATH = Path(__file__).resolve().parents[2] / "data" / "feeds" / "owid.jsonl"

# Each series: the grapher slug, the short value-column OWID emits, plus our normalized
# series_id/unit/title and a one-line trust + leak rationale (matches power.py's discipline).
SERIES: list[dict] = [
    {
        "series_id": "owid_renewable_share_electricity",
        "slug": "share-electricity-renewables",
        "value_col": "renewable_share_of_electricity__pct",
        "unit": "% of electricity",
        "title": "Renewable share of electricity generation",
        "leak": "leading",
        "rationale": (
            "OWID republication of Ember/Energy Institute electricity data (keyless full CSV). "
            "Renewable generation share leads the priced fossil-asset / utility-revenue outcome — "
            "it telegraphs stranded-fossil and grid-rebuild pressure ahead of incumbent earnings."
        ),
    },
    {
        "series_id": "owid_solar_pv_module_price",
        "slug": "solar-pv-prices",
        "value_col": "cost",
        "unit": "USD/watt (real)",
        "title": "Solar PV module price (global cost curve)",
        "leak": "leading",
        "rationale": (
            "OWID republication of the solar PV module cost curve (keyless full CSV). The module "
            "price LEADS deployment and the capex / levelised-cost outcomes markets later price — "
            "the cost drop precedes the demand build it unlocks (classic learning-curve leading signal)."
        ),
    },
    {
        "series_id": "owid_ev_sales_share",
        "slug": "electric-car-sales-share",
        "value_col": "ev_sales_share",
        "unit": "% of new car sales",
        "title": "Electric car share of new car sales",
        "leak": "leading",
        "rationale": (
            "OWID republication of IEA EV data (keyless full CSV). EV share of NEW sales leads the "
            "fleet stock and the oil-demand / ICE-supplier-revenue outcome by the vehicle-replacement "
            "lag — sales today imply fleet and demand shifts over the following years."
        ),
    },
]

# Keep the sample focused + leak-safe: a handful of major, well-reported entities.
KEEP_ENTITIES = {"World", "United States", "China", "European Union (27)", "Germany", "Norway", "India"}


def _get_text(url: str, *, timeout: int = 40) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 keyless public endpoint
        return resp.read().decode("utf-8", "replace")


def _fetch_series(spec: dict, *, log=print) -> list[dict]:
    """Fetch one OWID grapher CSV and normalize to observations. NO synthesis: a value is kept
    only if it parses as a real number for a real year; OWID gaps stay gaps."""
    url = GRAPHER.format(slug=spec["slug"]) + "?v=1&csvType=full&useColumnShortNames=true"
    rows = list(csv.DictReader(io.StringIO(_get_text(url))))
    vcol = spec["value_col"]
    obs: list[dict] = []
    for r in rows:
        entity = (r.get("entity") or "").strip()
        if entity not in KEEP_ENTITIES:
            continue
        raw = (r.get(vcol) or "").strip()
        yr = (r.get("year") or "").strip()
        if not raw or not yr:
            continue
        try:
            year = int(yr)
            value = float(raw)
        except ValueError:
            continue
        # The REAL date this value reports for — annual cadence, stamped year-end (point-in-time).
        obs.append({
            "series_id": f"{spec['series_id']}::{entity}",
            "date": date(year, 12, 31).isoformat(),
            "value": value,
            "unit": spec["unit"],
            "title": f"{spec['title']} — {entity}",
        })
    log(f"  + {spec['slug']:<28} {len(obs)} obs across {len(KEEP_ENTITIES & {o['title'].split(' — ')[-1] for o in obs})} entities")
    return obs


def _fetch_capability_curve(spec: dict, *, log=print) -> list[dict]:
    """Mirror the DB-direct capability curves as feed rows so refreshed series point to raw bytes."""
    url = GRAPHER.format(slug=spec["slug"]) + "?v=1&csvType=full&useColumnShortNames=true"
    rows = list(csv.DictReader(io.StringIO(_get_text(url))))
    pts: dict[int, float] = {}
    for r in rows:
        if r.get("entity") != spec["entity"]:
            continue
        raw = (r.get(spec["col"]) or "").strip()
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
        pts[year] = cost if spec["ref"] is None else spec["ref"] / cost
    metric = spec["metric"]
    out = [
        {
            "series_id": f"{spec['slug']}:{spec['col']}",
            "date": date(year, 12, 31).isoformat(),
            "value": round(pts[year], 6),
            "unit": spec["unit"],
            "title": metric.replace("_", " "),
            "metric": metric,
            "domain": spec["domain"],
        }
        for year in sorted(pts)
    ]
    log(f"  + {spec['slug']:<28} {metric:<32} {len(out)} obs")
    return out


def collect(*, log=print) -> list[dict]:
    """Fetch all configured OWID series, normalized to observation dicts. Keyless, $0."""
    log("OWID — structural energy / tech-adoption series (keyless full CSV):")
    all_obs: list[dict] = []
    for spec in SERIES:
        try:
            all_obs.extend(_fetch_series(spec, log=log))
        except OSError as e:
            log(f"  ! {spec['slug']} unreachable: {e}")
    log("OWID — compact capability curves (keyless full CSV):")
    for spec in CAPABILITY_CURVES:
        try:
            all_obs.extend(_fetch_capability_curve(spec, log=log))
        except OSError as e:
            log(f"  ! {spec['slug']} unreachable: {e}")
    return all_obs


def main() -> None:
    obs = collect()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for o in obs:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(obs)} real observations -> {OUT_PATH}")
    print("First 5:")
    for o in obs[:5]:
        print(" ", json.dumps(o, ensure_ascii=False))


if __name__ == "__main__":
    main()
