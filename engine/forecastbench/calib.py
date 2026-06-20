"""Calibration layer for the numeric/dataset half — the leak-clean discrimination core.

The dataset half is the part of the corpus that trains REAL forecasting skill without leakage: a question
like "will the temp at French station 07117 on 2013-06-29 exceed its 2012-12-31 value" is unmemorizable, so
the model must reason from the provided series, not recall an outcome. It is also where bots already beat
superforecasters. The quant prior (`model_prob`, dataset.py's leak-free P(higher)) is monotonically MIS-
calibrated (measured: says 0.9 -> really 0.78, says 0.2 -> really 0.34). That miscalibration is exactly the
free win the overnight run threw away.

This fits an isotonic map (PAV, pure python — no new dep) on the quant prior with OUT-OF-FOLD prediction so
the map never sees its own row's outcome (leak-discipline: the calibrated target for a row is produced by a
map fit on the OTHER folds). The calibrated value becomes the SFT target probability for that row; the trace
reasons over the series and lands there. GRPO (Brier reward) then sharpens DISCRIMINATION beyond this
baseline, which is safe here precisely because the questions are unmemorizable.

Run:  python -m engine.forecastbench.calib            # fit, report headroom, write calibrated targets
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data" / "forecastbench"
SRC = DATA / "trainset" / "dataset_questions.jsonl"
OUT = DATA / "trainset" / "dataset_calibrated.jsonl"


def _pav(xs: list[float], ys: list[float]) -> list[float]:
    """Pool-adjacent-violators isotonic regression: returns fitted y for each (x-sorted) point."""
    # blocks of (sum_y, weight); merge while not monotone non-decreasing
    blocks = [[y, 1.0] for y in ys]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] / blocks[i][1] > blocks[i + 1][0] / blocks[i + 1][1]:
            blocks[i][0] += blocks[i + 1][0]
            blocks[i][1] += blocks[i + 1][1]
            del blocks[i + 1]
            if i > 0:
                i -= 1
        else:
            i += 1
    out, fitted = [], []
    for s, w in blocks:
        out.extend([s / w] * int(w))
    # map back to per-point (xs already sorted with ys)
    return out


def _fit_map(pairs: list[tuple[float, int]]) -> list[tuple[float, float]]:
    """Return sorted (x, calibrated_y) knots from isotonic fit; interpolate with _apply."""
    pairs = sorted(pairs)
    xs = [p for p, _ in pairs]
    ys = [float(y) for _, y in pairs]
    fit = _pav(xs, ys)
    # collapse to knots (unique x -> last fitted value)
    knots = []
    for x, fy in zip(xs, fit):
        if knots and knots[-1][0] == x:
            knots[-1] = (x, fy)
        else:
            knots.append((x, fy))
    return knots


def _apply(knots: list[tuple[float, float]], x: float) -> float:
    if x <= knots[0][0]:
        return knots[0][1]
    if x >= knots[-1][0]:
        return knots[-1][1]
    lo, hi = 0, len(knots) - 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if knots[mid][0] <= x:
            lo = mid
        else:
            hi = mid
    (x0, y0), (x1, y1) = knots[lo], knots[hi]
    t = 0.0 if x1 == x0 else (x - x0) / (x1 - x0)
    return min(0.99, max(0.01, y0 + t * (y1 - y0)))


def _brier(ps, ys):
    return statistics.mean((p - y) ** 2 for p, y in zip(ps, ys))


def _ece(ps, ys, bins=10):
    tot, acc = 0, 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, p in enumerate(ps) if (lo <= p < hi) or (b == bins - 1 and p == hi)]
        if not idx:
            continue
        conf = statistics.mean(ps[i] for i in idx)
        emp = statistics.mean(ys[i] for i in idx)
        acc += len(idx) * abs(conf - emp)
        tot += len(idx)
    return acc / tot if tot else 0.0


def _auc(ps, ys):
    pos = [p for p, y in zip(ps, ys) if y == 1]
    neg = [p for p, y in zip(ps, ys) if y == 0]
    if not pos or not neg:
        return None
    w = sum(1 for a in pos for b in neg if a > b) + 0.5 * sum(1 for a in pos for b in neg if a == b)
    return w / (len(pos) * len(neg))


def build(k: int = 5) -> dict:
    rows = [json.loads(l) for l in SRC.open()]
    rows = [r for r in rows if r.get("model_prob") is not None and r.get("outcome") in (0, 1)]
    n = len(rows)
    # k-fold out-of-fold calibration (deterministic fold by index, no RNG -> reproducible)
    folds = [[] for _ in range(k)]
    for i, r in enumerate(rows):
        folds[i % k].append(r)
    for fi in range(k):
        train = [r for fj in range(k) if fj != fi for r in folds[fj]]
        knots = _fit_map([(r["model_prob"], r["outcome"]) for r in train])
        for r in folds[fi]:
            r["calibrated_target"] = round(_apply(knots, r["model_prob"]), 4)

    raw = [r["model_prob"] for r in rows]
    cal = [r["calibrated_target"] for r in rows]
    ys = [r["outcome"] for r in rows]

    with OUT.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    report = {
        "n": n,
        "brier_raw": round(_brier(raw, ys), 4),
        "brier_calibrated": round(_brier(cal, ys), 4),
        "ece_raw": round(_ece(raw, ys), 4),
        "ece_calibrated": round(_ece(cal, ys), 4),
        "auc_raw": round(_auc(raw, ys), 4),       # AUC is rank-invariant -> calibration cannot change it
    }
    print(f"\n=== numeric calibration ({n} rows, {k}-fold OOF) -> {OUT}")
    print(f"  Brier  raw quant : {report['brier_raw']}")
    print(f"  Brier  calibrated: {report['brier_calibrated']}   "
          f"(gain {report['brier_raw'] - report['brier_calibrated']:+.4f}, free)")
    print(f"  ECE    raw quant : {report['ece_raw']}")
    print(f"  ECE    calibrated: {report['ece_calibrated']}")
    print(f"  AUC (rank, fixed): {report['auc_raw']}   <- GRPO must push THIS above the quant prior")
    print("  -> calibrated_target written per row = the leak-clean SFT probability target.\n")
    return report


if __name__ == "__main__":
    build()
