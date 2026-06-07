"""Scoring harness + baselines — the measurement backbone.

Everything we do is optimized against Brier on *resolved* rows of past rounds.
Raw Brier (lower=better) is our internal metric; ForecastBench's published
"Brier Index" is a difficulty-adjusted monotone transform of it, so lowering
raw Brier is the right target. We never tune on the live set (no overfitting):
validate on held-out past rounds.

Data layout (gitignored, downloaded from forecastingresearch/forecastbench-datasets):
  data/forecastbench/q_<date>.json   question set   {forecast_due_date, questions:[...]}
  data/forecastbench/r_<date>.json   resolution set {resolutions:[{id,source,resolution_date,resolved_to,resolved}]}

A forecast is a dict keyed by (id, resolution_date) -> p in [0,1].
  - market questions: one entry, resolution_date = the row's date (forecaster sends null,
    but a round has exactly one market row per id, so we bind by id).
  - dataset questions: one entry per resolution_date horizon.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data" / "forecastbench"
MARKET_SOURCES = {"manifold", "metaculus", "polymarket", "infer"}
DATASET_SOURCES = {"acled", "dbnomics", "fred", "wikipedia", "yfinance"}


def _key(qid):
    return tuple(qid) if isinstance(qid, list) else qid


def load_round(date: str, data_dir: Path = DATA):
    """Return (questions, resolutions) for a round date 'YYYY-MM-DD'."""
    q = json.loads((data_dir / f"q_{date}.json").read_text())
    r = json.loads((data_dir / f"r_{date}.json").read_text())
    return q["questions"], r["resolutions"]


def single_questions(questions):
    """Drop combo questions (id is a list) — we forecast singles first."""
    return [q for q in questions if not isinstance(q["id"], list)]


def resolved_rows(resolutions, sources=None, singles_only=True):
    """Resolved resolution rows, optionally filtered to a source set."""
    out = []
    for x in resolutions:
        if not x.get("resolved"):
            continue
        if singles_only and isinstance(x["id"], list):
            continue
        if sources is not None and x["source"] not in sources:
            continue
        out.append(x)
    return out


def brier(forecast: dict, rows) -> dict:
    """Score a forecast {(id,resdate)->p or id->p for market} on resolved rows.

    Market rows are looked up by id alone (one row per id); dataset rows by
    (id, resolution_date). Missing forecasts are imputed 0.5 (FB rule) and
    counted, so coverage gaps are penalized honestly.
    """
    se, n, missing = 0.0, 0, 0
    by_src = {}
    for x in rows:
        qid, src, rd, y = _key(x["id"]), x["source"], x["resolution_date"], x["resolved_to"]
        if src in MARKET_SOURCES:
            p = forecast.get(qid, forecast.get((qid, None), forecast.get((qid, rd))))
        else:
            p = forecast.get((qid, rd), forecast.get(qid))
        if p is None:
            p = 0.5
            missing += 1
        d = (p - y) ** 2
        se += d
        n += 1
        b = by_src.setdefault(src, [0.0, 0])
        b[0] += d
        b[1] += 1
    out = {"brier": se / n if n else float("nan"), "n": n, "missing": missing,
           "by_source": {s: v[0] / v[1] for s, v in sorted(by_src.items())},
           "n_by_source": {s: v[1] for s, v in sorted(by_src.items())}}
    return out


def score_submission(submission: dict, resolutions) -> dict:
    """Combo-aware Brier of a full submission (the real FB metric). Market rows
    match by (id, direction) ignoring date (FB fills it); dataset rows by
    (id, resolution_date, direction). Missing -> 0.5."""
    def kdir(d):
        return tuple(d) if isinstance(d, list) else d
    fm, fd = {}, {}
    for r in submission["forecasts"]:
        if r["source"] in MARKET_SOURCES:
            fm[(_key(r["id"]), kdir(r["direction"]))] = r["forecast"]
        else:
            fd[(_key(r["id"]), r["resolution_date"], kdir(r["direction"]))] = r["forecast"]
    agg = {"MARKET": [0.0, 0], "DATASET": [0.0, 0]}
    miss = 0
    for x in resolutions:
        if not x.get("resolved"):
            continue
        if x["source"] in MARKET_SOURCES:
            grp = "MARKET"
            p = fm.get((_key(x["id"]), kdir(x.get("direction"))))
        else:
            grp = "DATASET"
            p = fd.get((_key(x["id"]), x["resolution_date"], kdir(x.get("direction"))))
        if p is None:
            p, miss = 0.5, miss + 1
        a = agg[grp]
        a[0] += (p - x["resolved_to"]) ** 2
        a[1] += 1
    se = sum(a[0] for a in agg.values())
    n = sum(a[1] for a in agg.values())
    return {"overall": se / n if n else float("nan"), "n": n, "missing": miss,
            "market": agg["MARKET"][0] / agg["MARKET"][1] if agg["MARKET"][1] else None,
            "dataset": agg["DATASET"][0] / agg["DATASET"][1] if agg["DATASET"][1] else None,
            "n_market": agg["MARKET"][1], "n_dataset": agg["DATASET"][1]}


# ---- baselines -------------------------------------------------------------

def crowd_forecast(questions) -> dict:
    """Market: the crowd value (freeze_datetime_value). Dataset: 0.5 (no info)."""
    f = {}
    for q in single_questions(questions):
        if q["source"] in MARKET_SOURCES:
            try:
                f[q["id"]] = float(q.get("freeze_datetime_value"))
            except (TypeError, ValueError):
                pass
    return f


def uniform_forecast(questions, p=0.5) -> dict:
    return {q["id"]: p for q in single_questions(questions)}


if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else "2025-08-03"
    questions, resolutions = load_round(date)
    rows = resolved_rows(resolutions)
    print(f"round {date}: {len(rows)} resolved single rows")
    for name, f in [("uniform-0.5", uniform_forecast(questions)),
                    ("crowd", crowd_forecast(questions))]:
        s = brier(f, rows)
        print(f"\n[{name}] Brier={s['brier']:.4f}  n={s['n']}  missing={s['missing']}")
        for src in sorted(s["by_source"]):
            print(f"    {src:10s} {s['by_source'][src]:.4f}  (n={s['n_by_source'][src]})")
