"""World Bank CAPITAL-FLOW indicators — keyless collector for the Capital layer (pillar 6).

The substrate's capital layer was US-skewed (SEC, usaspending) and grant-heavy (cordis). The World
Bank Indicators API is keyless, dated, and GLOBAL — it carries the cross-country private + portfolio +
debt capital-flow series that the layer was missing. This collector is deliberately SEPARATE from
`world_bank.py` (which routes to Outcome, pillar 9): every series here is routed to CAPITAL (pillar 6)
via its own `wbcap:` namespace, so the flows land on the right spine layer.

What it lands (per country, annual, real reference-year dates only — nulls dropped, never filled):
  • FDI net inflows / outflows (BoP)         — cross-border direct investment, the headline capital flow
  • Portfolio equity & investment, net       — hot/portfolio capital
  • External debt stocks, PNG private debt   — the stock of foreign claims (leverage build-up)
  • Gross capital formation (current US$)     — domestic investment spending
  • Market cap of listed firms, value traded — equity-market capital depth
  • Domestic credit to private sector (% GDP)— bank-credit intensity

Leak class: World Bank capital-account series are published with a LAG and revised across vintages →
this is a LAG / CONFIRMATION channel (confirms a capital-flow regime after it is priced), grounding the
capital layer as an authoritative global baseline, not an early-warning. $0, keyless.

Run directly:  uv run python -m engine.feeds.worldbank_capital
"""

from __future__ import annotations

import json
import time
from pathlib import Path

# Reuse the proven keyless pagination from the sibling World Bank collector (generic over code/iso).
from engine.feeds.world_bank import fetch_indicator

OUT_PATH = Path(__file__).resolve().parents[2] / "data" / "feeds" / "worldbank_capital.jsonl"
MIN_REFRESH_FRACTION = 0.8

# Capital-flow indicator basket. Each is its OWN series per country (`wbcap:<code>:<iso>`).
INDICATORS: list[dict] = [
    {"code": "BX.KLT.DINV.CD.WD", "metric": "fdi_inflow", "unit": "current US$",
     "title": "FDI, net inflows (BoP)"},
    {"code": "BM.KLT.DINV.CD.WD", "metric": "fdi_outflow", "unit": "current US$",
     "title": "FDI, net outflows (BoP)"},
    {"code": "BX.KLT.DINV.WD.GD.ZS", "metric": "fdi_inflow_pct_gdp", "unit": "% of GDP",
     "title": "FDI, net inflows (% of GDP)"},
    {"code": "BX.PEF.TOTL.CD.WD", "metric": "portfolio_equity_inflow", "unit": "current US$",
     "title": "Portfolio equity, net inflows (BoP)"},
    {"code": "BN.KLT.PTXL.CD", "metric": "portfolio_investment_net", "unit": "current US$",
     "title": "Portfolio investment, net (BoP)"},
    {"code": "DT.DOD.DECT.CD", "metric": "external_debt_stock", "unit": "current US$",
     "title": "External debt stocks, total"},
    {"code": "DT.DOD.DPNG.CD", "metric": "private_nonguaranteed_debt", "unit": "current US$",
     "title": "External debt, private nonguaranteed (PNG)"},
    {"code": "NE.GDI.TOTL.CD", "metric": "gross_capital_formation", "unit": "current US$",
     "title": "Gross capital formation (current US$)"},
    {"code": "CM.MKT.LCAP.CD", "metric": "equity_market_cap", "unit": "current US$",
     "title": "Market cap of listed domestic companies"},
    {"code": "CM.MKT.TRAD.CD", "metric": "equity_value_traded", "unit": "current US$",
     "title": "Stocks traded, total value"},
    {"code": "FS.AST.PRVT.GD.ZS", "metric": "private_credit_pct_gdp", "unit": "% of GDP",
     "title": "Domestic credit to private sector (% of GDP)"},
    {"code": "GC.DOD.TOTL.GD.ZS", "metric": "govt_debt_pct_gdp", "unit": "% of GDP",
     "title": "Central government debt, total (% of GDP)"},
]

# Global basket: World aggregate + G20 + key emerging markets (ISO-3, as the API expects).
REPORTERS: list[tuple[str, str]] = [
    ("WLD", "World"),
    ("USA", "United States"), ("CHN", "China"), ("JPN", "Japan"), ("DEU", "Germany"),
    ("IND", "India"), ("GBR", "United Kingdom"), ("FRA", "France"), ("BRA", "Brazil"),
    ("ITA", "Italy"), ("CAN", "Canada"), ("KOR", "South Korea"), ("RUS", "Russia"),
    ("AUS", "Australia"), ("MEX", "Mexico"), ("IDN", "Indonesia"), ("SAU", "Saudi Arabia"),
    ("TUR", "Turkey"), ("ZAF", "South Africa"), ("NGA", "Nigeria"), ("VNM", "Vietnam"),
    ("ARE", "United Arab Emirates"), ("NLD", "Netherlands"), ("SGP", "Singapore"),
]


def _existing_count() -> int:
    if not OUT_PATH.exists():
        return 0
    with OUT_PATH.open(encoding="utf-8") as f:
        return sum(1 for ln in f if ln.strip())


def normalize(code: str, iso3: str, spec: dict, raw_rows: list[dict]) -> list[dict]:
    series_id = f"wbcap:{code}:{iso3}"
    out: list[dict] = []
    for r in raw_rows:
        year = (r.get("date") or "").strip()
        if len(year) != 4 or not year.isdigit():
            continue
        try:
            value = float(r["value"])
        except (KeyError, TypeError, ValueError):
            continue
        out.append({
            "series_id": series_id, "date": f"{year}-12-31", "as_of": f"{year}-12-31",
            "value": value, "metric": spec["metric"], "domain": "capital",
            "unit": spec["unit"], "title": f"{spec['title']} — {iso3}",
        })
    out.sort(key=lambda o: o["date"])
    return out


def collect(*, log=print) -> list[dict]:
    all_obs: list[dict] = []
    for spec in INDICATORS:
        code = spec["code"]
        landed = 0
        for iso3, _name in REPORTERS:
            raw = fetch_indicator(code, iso3)
            obs = normalize(code, iso3, spec, raw)
            if obs:
                all_obs.extend(obs)
                landed += 1
            time.sleep(0.25)
        log(f"  + {spec['metric']:<26} {code:<20} {landed}/{len(REPORTERS)} reporters")

    existing = _existing_count()
    if not all_obs:
        log(f"\nno observations fetched; preserved existing {existing} rows at {OUT_PATH}")
        return []
    if existing and len(all_obs) < MIN_REFRESH_FRACTION * existing:
        log(f"\npartial refresh {len(all_obs)} < {MIN_REFRESH_FRACTION:.0%} of {existing}; preserved {OUT_PATH}")
        return []
    all_obs.sort(key=lambda o: (o["series_id"], o["date"]))
    tmp = OUT_PATH.with_suffix(".jsonl.tmp")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w", encoding="utf-8") as f:
        for o in all_obs:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    tmp.replace(OUT_PATH)
    log(f"\nwrote {len(all_obs)} observations across "
        f"{len({o['series_id'] for o in all_obs})} series → {OUT_PATH}")
    return all_obs


if __name__ == "__main__":
    print("World Bank capital-flow indicators (keyless, Capital layer / pillar 6):")
    observations = collect()
    if not observations:
        print("\nNO observations collected — World Bank API unreachable this run.")
    else:
        print(f"\n{len(observations)} obs across {len({o['series_id'] for o in observations})} series.")
        for o in observations[:3]:
            print("  " + json.dumps({k: o[k] for k in ('series_id', 'date', 'value', 'unit')}, ensure_ascii=False))
