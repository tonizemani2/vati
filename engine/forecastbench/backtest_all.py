"""Definitive multi-round backtest of the FULL pipeline (singles + combos),
combo-aware Brier per round + pooled. The honest no-overfit headline: the bot
is built once and scored on every past round it never saw.

Usage: uv run python -m engine.forecastbench.backtest_all
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

from .score import DATA, load_round, score_submission
from .submit import make_submission


def main():
    # only canonical rounds: q_YYYY-MM-DD.json (skip the -human variant etc.)
    rounds = sorted(p.name[2:12] for p in Path(DATA).glob("q_*.json")
                    if len(p.name) == len("q_YYYY-MM-DD.json"))
    pool = {"MARKET": [0.0, 0], "DATASET": [0.0, 0]}
    print(f"{'round':12s}{'overall':>9s}{'market':>9s}{'dataset':>9s}{'n':>7s}{'miss':>6s}")
    for dt in rounds:
        out = make_submission(str(DATA / f"q_{dt}.json"),
                              str(DATA / f"submission_{dt}.json"),
                              use_llm=False)   # offline quant eval — no LLM gap-fill
        sub = json.loads(Path(out).read_text())
        _, res = load_round(dt)
        s = score_submission(sub, res)
        print(f"{dt:12s}{s['overall']:9.4f}"
              f"{(s['market'] or 0):9.4f}{(s['dataset'] or 0):9.4f}"
              f"{s['n']:7d}{s['missing']:6d}", flush=True)
        pool["MARKET"][0] += (s["market"] or 0) * s["n_market"]
        pool["MARKET"][1] += s["n_market"]
        pool["DATASET"][0] += (s["dataset"] or 0) * s["n_dataset"]
        pool["DATASET"][1] += s["n_dataset"]
    m = pool["MARKET"][0] / pool["MARKET"][1]
    d = pool["DATASET"][0] / pool["DATASET"][1]
    n = pool["MARKET"][1] + pool["DATASET"][1]
    print(f"\nPOOLED  market={m:.4f} (n={pool['MARKET'][1]})  "
          f"dataset={d:.4f} (n={pool['DATASET'][1]})  overall={(m+d)/2:.4f} (equal-wt)")


if __name__ == "__main__":
    main()
