"""Point-in-time backtest: forecast a past round as-of its due date, score on
resolved rows. The dataset half is leakage-free (only series data <= due date).
The market/crowd half is the freeze-time crowd value (also point-in-time).

Usage: uv run python -m engine.forecastbench.validate 2025-08-03 [sources...]
"""
from __future__ import annotations

import sys
from datetime import datetime

from . import dataset as ds
from .score import (DATASET_SOURCES, MARKET_SOURCES, brier, crowd_forecast,
                    load_round, resolved_rows)


def run(date: str, sources=None):
    questions, resolutions = load_round(date)
    due = datetime.strptime(date, "%Y-%m-%d").date()
    rows = resolved_rows(resolutions)

    f = dict(crowd_forecast(questions))                       # market: crowd anchor
    ds.prefetch_round(questions, sources=sources)             # warm cache concurrently
    quant = ds.forecast_round(questions, due, sources=sources)  # dataset: quant
    f.update(quant)

    s = brier(f, rows)
    print(f"\n=== round {date}  Brier={s['brier']:.4f}  n={s['n']}  missing={s['missing']} ===")
    print(f"{'source':12s} {'Brier':>7s} {'n':>6s}")
    for src in sorted(s["by_source"]):
        print(f"{src:12s} {s['by_source'][src]:7.4f} {s['n_by_source'][src]:6d}")
    # market vs dataset split
    for label, srcs in [("MARKET", MARKET_SOURCES), ("DATASET", DATASET_SOURCES)]:
        b = sum(s["by_source"][k] * s["n_by_source"][k] for k in srcs if k in s["by_source"])
        n = sum(s["n_by_source"][k] for k in srcs if k in s["n_by_source"])
        if n:
            print(f"  {label:8s} Brier={b/n:.4f}  n={n}")
    return s


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else "2025-08-03"
    srcs = set(sys.argv[2:]) or None
    run(date, srcs)
