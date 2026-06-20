"""Per-source dataset-half diagnostic — where is the real Brier gap?

Scores the CURRENT quant model (dataset.forecast_dataset_question) on every resolved DATASET row of
every past round, broken out by source, against two references: the 0.5 floor and the round's own
empirical YES-rate (the "always base rate" strawman). This is pure measurement — no new model, no
overfit — so it honestly answers: which dataset source is dragging the half, and is it already near
its floor (irreducible noise) or genuinely improvable?

Run: uv run python -m engine.forecastbench.dataset_diag
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from . import dataset as ds
from .score import DATA, DATASET_SOURCES, load_round, resolved_rows, single_questions


def main():
    rounds = sorted(p.name[2:12] for p in Path(DATA).glob("q_*.json")
                    if len(p.name) == len("q_YYYY-MM-DD.json"))
    # per-source accumulators: [sum_brier_model, sum_brier_half, n, sum_y]
    agg = defaultdict(lambda: [0.0, 0.0, 0, 0.0])
    for dt in rounds:
        try:
            questions, resolutions = load_round(dt)
        except FileNotFoundError:
            continue
        due = datetime.strptime(dt, "%Y-%m-%d").date()
        rows = resolved_rows(resolutions, sources=DATASET_SOURCES)
        if not rows:
            continue
        ds.prefetch_round(questions)                       # warm series cache (floxy, cached)
        fc = {}
        for q in single_questions(questions):
            if q["source"] in DATASET_SOURCES:
                for rd, p in ds.forecast_dataset_question(q, due).items():
                    fc[(q["id"], rd)] = p
        for x in rows:
            src, rd, y = x["source"], x["resolution_date"], x["resolved_to"]
            p = fc.get((x["id"], rd))
            if p is None:
                p = 0.5
            a = agg[src]
            a[0] += (p - y) ** 2          # current model
            a[1] += (0.5 - y) ** 2        # 0.5 floor
            a[2] += 1
            a[3] += y
        print(f"  scored round {dt}", flush=True)

    print(f"\n{'source':10s}{'n':>6s}{'model':>9s}{'p=.5':>9s}{'baserate':>10s}{'YES%':>7s}  verdict")
    tot = [0.0, 0.0, 0]
    for src in sorted(agg):
        bm, bh, n, sy = agg[src]
        yr = sy / n
        base = yr * (1 - yr) + (yr - yr) ** 2   # Brier of forecasting the constant base rate = yr(1-yr)... use yr
        # Brier of always-predict-yr on a Bernoulli(yr) sample ≈ yr(1-yr); compute exact on these rows:
        base_brier = (sy * (1 - yr) ** 2 + (n - sy) * (yr) ** 2) / n
        mB, hB = bm / n, bh / n
        tot[0] += bm; tot[1] += bh; tot[2] += n
        gap = hB - mB
        verdict = ("near floor" if abs(mB - hB) < 0.01 else
                   "BEATS .5 well" if gap > 0.03 else "beats .5")
        print(f"{src:10s}{n:6d}{mB:9.4f}{hB:9.4f}{base_brier:10.4f}{yr*100:6.0f}%  {verdict} (Δvs.5 {gap:+.3f})")
    print(f"\n{'POOLED':10s}{tot[2]:6d}{tot[0]/tot[2]:9.4f}{tot[1]/tot[2]:9.4f}")
    print("\nRead: model << p=.5 means real edge; model ≈ baserate-Brier means it's just calling the\n"
          "base rate (improvable only if a level/structure signal exists); model ≈ .5 = irreducible noise.")


if __name__ == "__main__":
    main()
