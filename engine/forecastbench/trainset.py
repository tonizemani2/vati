"""Training-data factory — leak-safe forecasting questions minted from real series.

The moat for a fine-tuned forecasting LLM (see ../../FORECAST_LLM.md) is data nobody else has:
binary questions with a KNOWN outcome, frozen point-in-time context, and strict leak control. This
mints exactly that from the dataset half of ForecastBench — *for free*.

How it stays honest + in-distribution:
  • SEED from the real cached question sets (data/forecastbench/q_*.json) → the exact series the
    benchmark uses (fred / yfinance / dbnomics) AND their exact question template text.
  • For each series, walk BACKWARD over its own history: pick `as_of` anchors and, for each, the
    ForecastBench horizon ladder. A row is kept only when the resolution date is already in the PAST
    (so WE know the outcome) — the outcome is read straight from the series. Zero outcome leakage into
    the label; the model's `context` is the series truncated to `as_of` (point-in-time, no peeking).
  • The question text is the benchmark's own template with {forecast_due_date}/{resolution_date}
    filled → byte-identical phrasing to what the model is scored on.

Output: JSONL rows in the unified schema (FORECAST_LLM.md §4.2) → the GRPO prompt+outcome set. SFT
trace generation (best-of-N, needs an LLM through the cost gate) is a separate step.

Keyless / $0: reuses dataset.py's cached, proxy-escalating fetchers and its leak-free P(higher)
models (the `model_prob` baseline, so we can score difficulty + later detect hedge-collapse).

Run:  python -m engine.forecastbench.trainset [--cutoff YYYY-MM-DD] [--anchors N] [--series-limit N]
                                              [--balance] [--out PATH]
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from . import dataset as ds
from .domains import tag_domain

DATA = Path(__file__).resolve().parents[2] / "data" / "forecastbench"
OUT_DEFAULT = DATA / "trainset" / "dataset_questions.jsonl"
# ForecastBench's own horizon ladder (days from the forecast_due_date), per the question sets.
HORIZONS = [7, 23, 90, 180, 365, 730, 1460]
NUMERIC_SOURCES = {"fred", "yfinance", "dbnomics"}

# Cross-domain FRED seed (keyless) — broadens the numeric corpus beyond the benchmark's own series so
# the model sees labor, prices, rates, housing, energy, credit, trade, consumer, output, crypto. Each
# is (series_id, short_name, domain). Hand-picked for domain spread, not tuned to any outcome.
FRED_SEED: list[tuple[str, str, str]] = [
    ("PAYEMS", "US nonfarm payroll employment", "macro_economy"),
    ("UNRATE", "the US unemployment rate", "macro_economy"),
    ("ICSA", "US initial jobless claims", "macro_economy"),
    ("JTSJOL", "US job openings", "macro_economy"),
    ("CPIAUCSL", "US consumer price index", "macro_economy"),
    ("CPILFESL", "US core CPI", "macro_economy"),
    ("PCEPI", "the US PCE price index", "macro_economy"),
    ("PPIACO", "US producer prices (all commodities)", "macro_economy"),
    ("FEDFUNDS", "the US federal funds rate", "credit_finance"),
    ("DGS10", "the US 10-year Treasury yield", "credit_finance"),
    ("DGS2", "the US 2-year Treasury yield", "credit_finance"),
    ("T10Y2Y", "the US 10y-2y Treasury spread", "credit_finance"),
    ("BAMLH0A0HYM2", "the US high-yield credit spread", "credit_finance"),
    ("MORTGAGE30US", "the US 30-year mortgage rate", "housing_realestate"),
    ("HOUST", "US housing starts", "housing_realestate"),
    ("PERMIT", "US building permits", "housing_realestate"),
    ("CSUSHPINSA", "the US Case-Shiller home price index", "housing_realestate"),
    ("INDPRO", "US industrial production", "macro_economy"),
    ("TCU", "US capacity utilization", "macro_economy"),
    ("DCOILWTICO", "WTI crude oil price", "energy"),
    ("DHHNGSP", "US natural gas (Henry Hub) price", "energy"),
    ("GASREGW", "US regular gasoline price", "energy"),
    ("GOLDAMGBD228NLBM", "the gold price (London fix)", "commodities"),
    ("CBBTCUSD", "the Bitcoin price", "crypto"),
    ("DTWEXBGS", "the trade-weighted US dollar index", "trade_supplychain"),
    ("BOPGSTB", "the US trade balance", "trade_supplychain"),
    ("UMCSENT", "US consumer sentiment", "consumer_retail"),
    ("RSAFS", "US retail sales", "consumer_retail"),
    ("PCE", "US personal consumption expenditures", "consumer_retail"),
    ("M2SL", "the US M2 money supply", "macro_economy"),
    ("TOTALSA", "US total vehicle sales", "consumer_retail"),
    ("DEXCHUS", "the China/US exchange rate", "trade_supplychain"),
]

# Cross-domain yfinance seed (keyless via dataset.fetch_yahoo + p_higher_equity). EVAL is yfinance-heavy
# (the real FB rounds carry ~122 equity tickers → all post-cutoff → eval), but TRAIN had almost none, so
# the model trained on a different dataset-half distribution than it's scored on. These liquid, long-
# history tickers mint PRE-cutoff equity questions into TRAIN, closing that gap on the dataset half where
# we win. Each is (ticker, short_name, domain); indices/sectors/commodities/crypto/FX for spread, no
# outcome tuning. ForecastBench's equity question template is "higher on {res} than {due}?" — same as ours.
YF_SEED: list[tuple[str, str, str]] = [
    ("^GSPC", "the S&P 500 index", "equities_markets"),
    ("^IXIC", "the Nasdaq Composite index", "equities_markets"),
    ("^DJI", "the Dow Jones Industrial Average", "equities_markets"),
    ("^RUT", "the Russell 2000 small-cap index", "equities_markets"),
    ("^VIX", "the VIX volatility index", "equities_markets"),
    ("^FTSE", "the FTSE 100 index", "equities_markets"),
    ("^N225", "the Nikkei 225 index", "equities_markets"),
    ("AAPL", "Apple stock", "equities_markets"),
    ("MSFT", "Microsoft stock", "equities_markets"),
    ("GOOGL", "Alphabet stock", "equities_markets"),
    ("AMZN", "Amazon stock", "equities_markets"),
    ("NVDA", "Nvidia stock", "equities_markets"),
    ("META", "Meta Platforms stock", "equities_markets"),
    ("TSLA", "Tesla stock", "equities_markets"),
    ("JPM", "JPMorgan stock", "equities_markets"),
    ("XOM", "ExxonMobil stock", "energy"),
    ("XLE", "the energy-sector ETF (XLE)", "energy"),
    ("XLF", "the financial-sector ETF (XLF)", "credit_finance"),
    ("XLK", "the technology-sector ETF (XLK)", "equities_markets"),
    ("XLV", "the health-care-sector ETF (XLV)", "health_medicine"),
    ("SMH", "the semiconductor ETF (SMH)", "ai_compute"),
    ("GLD", "the gold ETF (GLD)", "commodities"),
    ("SLV", "the silver ETF (SLV)", "commodities"),
    ("USO", "the US oil fund (USO)", "energy"),
    ("TLT", "the 20+ year Treasury ETF (TLT)", "credit_finance"),
    ("HYG", "the high-yield corporate bond ETF (HYG)", "credit_finance"),
    ("BTC-USD", "Bitcoin", "crypto"),
    ("ETH-USD", "Ethereum", "crypto"),
    ("EURUSD=X", "the EUR/USD exchange rate", "trade_supplychain"),
    ("JPY=X", "the USD/JPY exchange rate", "trade_supplychain"),
    ("GC=F", "gold futures", "commodities"),
    ("CL=F", "WTI crude oil futures", "energy"),
    ("HG=F", "copper futures", "commodities"),
    ("EEM", "the emerging-markets ETF (EEM)", "equities_markets"),
    ("ARKK", "the ARK Innovation ETF (ARKK)", "equities_markets"),
]


def _today() -> date:
    return datetime.now().date()


# ── seed: pull (source, id, url, question_template) from the cached benchmark rounds ──────────────
def _series_domain(src: str, template: str) -> str:
    if src == "yfinance":
        return "equities_markets"
    if src == "dbnomics":
        return "climate_weather"
    return tag_domain(template) if template else "macro_economy"   # fred → from its description


def seed_series() -> list[dict]:
    """Every numeric dataset series — the benchmark's own (from cached rounds) + the cross-domain FRED
    seed — deduped, each with template text and a `domain` (for variety coverage)."""
    seen: dict[tuple, dict] = {}
    for f in sorted(DATA.glob("q_*.json")):
        try:
            doc = json.loads(f.read_text())
        except Exception:
            continue
        qs = doc["questions"] if isinstance(doc, dict) else doc
        for q in qs:
            src = q.get("source")
            qid = q.get("id")
            if src not in NUMERIC_SOURCES or isinstance(qid, list):
                continue
            key = (src, qid)
            if key not in seen:
                tmpl = q.get("question") or ""
                seen[key] = {"source": src, "id": qid, "url": q.get("url"),
                             "template": tmpl, "domain": _series_domain(src, tmpl)}
    for sid, name, domain in FRED_SEED:                       # cross-domain breadth
        key = ("fred", sid)
        if key not in seen:
            seen[key] = {"source": "fred", "id": sid,
                         "url": f"https://fred.stlouisfed.org/series/{sid}",
                         "template": f"Will {name} be higher on {{resolution_date}} than on "
                                     f"{{forecast_due_date}}?", "domain": domain}
    for tkr, name, domain in YF_SEED:                         # equity breadth → match eval's yfinance half
        key = ("yfinance", tkr)
        if key not in seen:
            seen[key] = {"source": "yfinance", "id": tkr,
                         "url": f"https://finance.yahoo.com/quote/{tkr}",
                         "template": f"Will {name} be higher on {{resolution_date}} than on "
                                     f"{{forecast_due_date}}?", "domain": domain}
    return list(seen.values())


def _fetch(s: dict):
    if s["source"] == "fred":
        return ds.fetch_fred(s["id"])
    if s["source"] == "yfinance":
        return ds.fetch_yahoo(s["id"])
    if s["source"] == "dbnomics":
        return ds.fetch_dbnomics(s["url"])
    return None


def _value_near(history, target: date, tol_days: int):
    """Observation value closest to `target` within tol_days, else None (not resolved / gap)."""
    best = None
    for dt, v in history:
        d = abs((dt - target).days)
        if d <= tol_days and (best is None or d < best[0]):
            best = (d, v)
    return best[1] if best else None


def _period_days(history) -> int:
    sp = [(history[i][0] - history[i - 1][0]).days for i in range(1, len(history))
          if (history[i][0] - history[i - 1][0]).days > 0]
    return max(1, int(statistics.median(sp))) if sp else 1


def _model_prob(s: dict, history, due: date, res: date, h: int):
    """The leak-free quant baseline for this question (reused from dataset.py)."""
    if s["source"] == "yfinance":
        return ds.p_higher_equity(history, due, h)
    if s["source"] == "fred":
        return ds.p_higher_baserate(history, due, h)
    p = ds.p_higher_seasonal(history, due, res)
    return p if p is not None else ds.p_higher_drift(history, due, h, use_log=False)


def _context(history, due: date, period: int) -> str:
    """Frozen point-in-time context: the tail of the series up to `due` (no peeking)."""
    h = ds._truncate(history, due)
    tail = h[-24:]
    pts = "; ".join(f"{dt.isoformat()}={v:.4g}" for dt, v in tail)
    lo = min(v for _, v in h); hi = max(v for _, v in h)
    return (f"Series history through {due.isoformat()} (most-recent {len(tail)} of {len(h)} obs, "
            f"~{period}d spacing; full-history min {lo:.4g}, max {hi:.4g}): {pts}")


def mint(cutoff: date | None, anchors: int, series_limit: int | None, sources: set | None = None):
    """Yield unified training rows from all seeded series."""
    series = seed_series()
    if sources:
        series = [s for s in series if s["source"] in sources]
    if series_limit:
        series = series[:series_limit]
    today = _today()
    drops: Counter = Counter()
    rows = []
    for i, s in enumerate(series):
        try:
            hist = _fetch(s)
        except Exception:
            drops["fetch_failed"] += 1
            continue
        if not hist or len(hist) < 60:
            drops["thin_history"] += 1
            continue
        period = _period_days(hist)
        tol = max(7, period * 2)
        first, last = hist[0][0], hist[-1][0]
        # anchors evenly spaced from (first + 1y warmup) to (last - shortest horizon)
        lo = first + timedelta(days=365)
        hi = min(last, today) - timedelta(days=HORIZONS[0])
        if hi <= lo:
            drops["span_too_short"] += 1
            continue
        span = (hi - lo).days
        for a in range(anchors):
            due = lo + timedelta(days=int(span * a / max(1, anchors - 1))) if anchors > 1 else lo
            due_val = _value_near(hist, due, tol)
            if due_val is None:
                drops["no_due_value"] += 1
                continue
            for h in HORIZONS:
                res = due + timedelta(days=h)
                if res >= today:           # not yet resolved → we don't know the outcome
                    drops["unresolved"] += 1
                    continue
                res_val = _value_near(hist, res, tol)
                if res_val is None:
                    drops["no_res_value"] += 1
                    continue
                outcome = 1 if res_val > due_val else 0
                mp = _model_prob(s, hist, due, res, h)
                leak_ok = (cutoff is None) or (res > cutoff)
                tmpl = s["template"].replace("{resolution_date}", res.isoformat()) \
                                    .replace("{forecast_due_date}", due.isoformat())
                rows.append({
                    "id": f"{s['source']}-{s['id']}-{due.isoformat()}-h{h}",
                    "source": s["source"], "kind": "dataset",
                    "question": tmpl or f"Will {s['id']} be higher on {res.isoformat()} "
                                        f"than on {due.isoformat()}?",
                    "resolution_criteria": f"Resolves YES iff the {s['source']} series {s['id']} value "
                                           f"on {res.isoformat()} exceeds its value on {due.isoformat()}.",
                    "as_of_date": due.isoformat(), "resolution_date": res.isoformat(),
                    "horizon_days": h,
                    "context": _context(hist, due, period),
                    "crowd_prob": None,
                    "model_prob": round(mp, 4) if mp is not None else None,
                    "outcome": outcome,
                    "domain": s.get("domain") or _series_domain(s["source"], s.get("template", "")),
                    "base_model_cutoff": cutoff.isoformat() if cutoff else None,
                    "leak_ok": leak_ok,
                    "difficulty": round(1 - 2 * abs((mp if mp is not None else 0.5) - 0.5), 4),
                    "trace": None,
                })
        if (i + 1) % 20 == 0:
            print(f"  ...{i+1}/{len(series)} series, {len(rows)} rows", flush=True)
    return rows, drops


def balance(rows: list[dict]) -> list[dict]:
    """Downsample the majority outcome per source to ~50/50 (deterministic stride) so the model
    can't win by always predicting the dominant direction (§4.5 label balance)."""
    out = []
    by_src: dict[str, list] = {}
    for r in rows:
        by_src.setdefault(r["source"], []).append(r)
    for src, rs in by_src.items():
        pos = [r for r in rs if r["outcome"] == 1]
        neg = [r for r in rs if r["outcome"] == 0]
        k = min(len(pos), len(neg))
        if k == 0:
            out.extend(rs)
            continue
        def stride(xs, k):
            step = len(xs) / k
            return [xs[int(j * step)] for j in range(k)]
        out.extend(stride(pos, k) + stride(neg, k))
    return out


def main():
    args = sys.argv[1:]
    def opt(flag, default=None, cast=str):
        if flag in args:
            return cast(args[args.index(flag) + 1])
        return default
    cutoff = opt("--cutoff")
    cutoff = datetime.strptime(cutoff, "%Y-%m-%d").date() if cutoff else None
    anchors = int(opt("--anchors", 8))
    series_limit = opt("--series-limit", None, int)
    sources = opt("--sources")
    sources = set(sources.split(",")) if sources else None
    out = Path(opt("--out", str(OUT_DEFAULT)))
    do_balance = "--balance" in args

    print(f"minting (cutoff={cutoff}, anchors={anchors}, sources={sources or 'all'}) ...", flush=True)
    rows, drops = mint(cutoff, anchors, series_limit, sources)
    raw_n = len(rows)
    bal = Counter(r["outcome"] for r in rows)
    if do_balance:
        rows = balance(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    leak_ok = sum(1 for r in rows if r["leak_ok"])
    print(f"\n  minted {raw_n} rows; wrote {len(rows)} → {out}")
    print(f"  raw label balance: YES={bal[1]} NO={bal[0]} ({bal[1]/max(1,raw_n):.0%} YES)")
    print(f"  by source: {dict(Counter(r['source'] for r in rows))}")
    print(f"  by domain: {dict(Counter(r['domain'] for r in rows).most_common())}")
    print(f"  leak_ok (res > cutoff): {leak_ok}/{len(rows)}" + (" [no cutoff set]" if cutoff is None else ""))
    print(f"  dropped: {dict(drops)}")


if __name__ == "__main__":
    main()
