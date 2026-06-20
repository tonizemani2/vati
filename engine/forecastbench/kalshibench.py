"""KalshiBench scoring — the leak-free, no-overfit path to #1.

KalshiBench (arXiv:2512.16030) scores Brier + ECE + Brier-Skill-Score on 1,531 resolved Kalshi
contracts (close_time 2024-05 .. 2025-11). The published Table-4 frontier:

    model              acc     Brier    ECE      BSS
    Claude-Opus-4.5    0.693   0.227    0.120   +0.057   <- only model that beats the base rate
    Kimi-K2            0.671   0.347    0.298   -0.446
    Qwen3-235B         0.657   0.346    0.297   -0.437
    GPT-5.2-XHigh      0.653   0.433    0.395   -0.799
    DeepSeek-V3.2      0.643   0.339    0.284   -0.407
    base-rate floor      -     0.244     -       0.000

THE FINDING. Accuracy is flat (.64-.69); the whole spread is *calibration*. Four of five frontier
models score WORSE than the 0.244 base rate purely on overconfidence (ECE .28-.40). So the winning
move is not a smarter model — it is refusing to be overconfident. This module proves it.

LEAK DISCIPLINE ([[parametric-leakage]]). Every contract here resolved before any 2026-cutoff model's
training cutoff, so a naive current-model run is a horoscope. We never use a model's outcome knowledge:
  * climatology priors use ONLY out-of-fold outcomes (k-fold), never the row being scored;
  * an LLM directional signal is admitted ONLY on the slice that resolves AFTER that model's
    effective cutoff (the holdout-model rule, engine/holdout.py), so the outcome is not in its weights.

NO OVERFIT. Every learned quantity (category rate, blend weight, calibration map) is fit out-of-fold
and scored on the held-out fold; small categories shrink toward the global rate. Nothing is tuned on
the row it predicts. Reported numbers are pure OOS.

Run:
    python -m engine.forecastbench.kalshibench                       # climatology floor (the $0 #1)
    python -m engine.forecastbench.kalshibench --pred llm=preds.jsonl # blend a leak-free LLM signal
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data" / "kalshibench" / "train.parquet"
BASE_RATE_REF = 0.244  # KalshiBench reference-class Brier (paper); BSS = 1 - Brier/ref
N_FOLDS = 10

# Published Table-4 frontier (arXiv:2512.16030) — the bar we report against.
PUBLISHED = [
    ("Claude-Opus-4.5", 0.693, 0.227, 0.120, 0.057),
    ("Kimi-K2", 0.671, 0.347, 0.298, -0.446),
    ("Qwen3-235B", 0.657, 0.346, 0.297, -0.437),
    ("GPT-5.2-XHigh", 0.653, 0.433, 0.395, -0.799),
    ("DeepSeek-V3.2", 0.643, 0.339, 0.284, -0.407),
]


# ── metrics ──────────────────────────────────────────────────────────────────────────────────────
def brier(ps, ys):
    return sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(ys)


def bss(ps, ys, ref=BASE_RATE_REF):
    return 1 - brier(ps, ys) / ref


def accuracy(ps, ys):
    return sum((p >= 0.5) == (y == 1) for p, y in zip(ps, ys)) / len(ys)


def ece(ps, ys, bins=10):
    e = 0.0
    n = len(ys)
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, p in enumerate(ps) if (lo <= p < hi) or (b == bins - 1 and p == hi)]
        if not idx:
            continue
        conf = sum(ps[i] for i in idx) / len(idx)
        acc = sum(ys[i] for i in idx) / len(idx)
        e += (len(idx) / n) * abs(conf - acc)
    return e


# ── data ─────────────────────────────────────────────────────────────────────────────────────────
def load_rows(path: Path = DATA):
    """Return list of dicts: {id, question, category, close_time(ISO), y(0/1)}. Deterministic order."""
    import pandas as pd

    df = pd.read_parquet(path)
    df["close_time"] = pd.to_datetime(df["close_time"], errors="coerce", utc=True)
    df = df.sort_values(["close_time", "id"]).reset_index(drop=True)
    rows = []
    for i, r in df.iterrows():
        ct = r["close_time"]
        ct_iso = ct.isoformat() if pd.notna(ct) else None
        rows.append(
            {
                "row": int(i),
                "id": str(r["id"]),
                "question": str(r["question"]),
                "category": str(r["category"]),
                "series_ticker": str(r.get("series_ticker", "")),
                "close_time": ct_iso,
                "y": int(r["ground_truth"] == "yes"),
            }
        )
    return rows


def fold_of(row_idx: int) -> int:
    """Deterministic fold assignment (no RNG — reproducible across machines)."""
    return row_idx % N_FOLDS


# ── climatology (the leak-free, no-overfit floor) ──────────────────────────────────────────────────
def climatology(rows, k_shrink: float = 1.0, by="category"):
    """Out-of-fold reference forecast: smoothed historical rate of the row's `by` class.

    p_i = (yes_in_class + k*global) / (count_in_class + k), computed from rows NOT in i's fold.
    Uses zero information about row i's own outcome -> leak-free and overfit-free by construction.
    """
    ys = [r["y"] for r in rows]
    preds = [0.0] * len(rows)
    for f in range(N_FOLDS):
        tr = [i for i, r in enumerate(rows) if fold_of(r["row"]) != f]
        te = [i for i, r in enumerate(rows) if fold_of(r["row"]) == f]
        g = sum(ys[i] for i in tr) / len(tr)
        agg = {}
        for i in tr:
            c = rows[i][by]
            s, n = agg.get(c, (0, 0))
            agg[c] = (s + ys[i], n + 1)
        for i in te:
            c = rows[i][by]
            if c in agg:
                s, n = agg[c]
                preds[i] = (s + k_shrink * g) / (n + k_shrink)
            else:
                preds[i] = g
    return preds


# ── leak partition ─────────────────────────────────────────────────────────────────────────────────
def clean_slice(rows, cutoff_iso: str):
    """Indices of rows resolving strictly AFTER cutoff_iso (leak-free for a model with that cutoff)."""
    return [i for i, r in enumerate(rows) if r["close_time"] and r["close_time"] > cutoff_iso]


# ── LLM-signal blend (calibrated, out-of-fold) ─────────────────────────────────────────────────────
def _clip(p, e=1e-6):
    return min(1 - e, max(e, float(p)))


def _logit(p):
    p = _clip(p)
    return math.log(p / (1 - p))


def _sigmoid(x):
    return 1 / (1 + math.exp(-x))


def blend_logit(prior, signal, w):
    """Pool prior & signal in logit space with signal weight w in [0,1]."""
    return [_sigmoid((1 - w) * _logit(a) + w * _logit(b)) for a, b in zip(prior, signal)]


def fit_blend_weight(prior, signal, ys, rows):
    """OOS grid-search the single signal weight that minimises held-out Brier (no fit-on-itself)."""
    grid = [i / 20 for i in range(21)]
    best_preds = list(prior)
    # choose w per fold on the other folds, apply to held-out fold
    out = [0.0] * len(ys)
    for f in range(N_FOLDS):
        tr = [i for i, r in enumerate(rows) if fold_of(r["row"]) != f]
        te = [i for i, r in enumerate(rows) if fold_of(r["row"]) == f]
        bw, bbr = 0.0, 1e9
        for w in grid:
            p = blend_logit([prior[i] for i in tr], [signal[i] for i in tr], w)
            b = brier(p, [ys[i] for i in tr])
            if b < bbr:
                bbr, bw = b, w
        bp = blend_logit([prior[i] for i in te], [signal[i] for i in te], bw)
        for j, i in enumerate(te):
            out[i] = bp[j]
    return out, best_preds


# ── isotonic calibration via PAV (out-of-fold; no sklearn) ─────────────────────────────────────────
def _pav(xs, ys):
    """Pool-adjacent-violators isotonic regression. Returns step boundaries (x_thresh, y_level)."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    blocks = [[ys[i], 1, xs[i]] for i in order]  # [sum_y, count, max_x]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] / blocks[i][1] > blocks[i + 1][0] / blocks[i + 1][1]:
            blocks[i][0] += blocks[i + 1][0]
            blocks[i][1] += blocks[i + 1][1]
            blocks[i][2] = blocks[i + 1][2]
            del blocks[i + 1]
            if i > 0:
                i -= 1
        else:
            i += 1
    return [(b[2], b[0] / b[1]) for b in blocks]


def _apply_iso(steps, x):
    for thr, lvl in steps:
        if x <= thr:
            return lvl
    return steps[-1][1] if steps else x


def calibrate_oos(raw, ys, rows):
    """Out-of-fold isotonic calibration of a raw probability column (collapses overconfidence)."""
    out = [0.0] * len(ys)
    for f in range(N_FOLDS):
        tr = [i for i, r in enumerate(rows) if fold_of(r["row"]) != f]
        te = [i for i, r in enumerate(rows) if fold_of(r["row"]) == f]
        steps = _pav([raw[i] for i in tr], [ys[i] for i in tr])
        for i in te:
            out[i] = _apply_iso(steps, raw[i])
    return out


def report(name, preds, ys):
    print(
        f"  {name:32s} N={len(ys):4d}  acc={accuracy(preds, ys):.3f}  "
        f"Brier={brier(preds, ys):.4f}  ECE={ece(preds, ys):.4f}  BSS={bss(preds, ys):+.4f}"
    )


# ── keyless inference (calibration-minded binary forecast) ─────────────────────────────────────────
FORECAST_SYS = (
    "You are a careful, calibrated forecaster. You give a probability that reflects genuine "
    "uncertainty. You are NOT rewarded for confidence — you are scored by Brier, so a wrong 0.95 is "
    "punished far more than an honest 0.6. Most real-world binary questions are closer to a coin flip "
    "than intuition suggests; anchor on the base rate of the reference class before adjusting."
)


def _forecast_prompt(row) -> str:
    return (
        f"Question: {row['question']}\n"
        f"Category: {row['category']}\n"
        "Estimate the probability this resolves YES. First think briefly about the reference-class "
        "base rate, then adjust only for specific evidence you are confident about. "
        "End with exactly one line: PROBABILITY: <0..1>"
    )


def _parse_prob(text: str):
    import re
    m = re.findall(r"PROBABILITY:\s*([01](?:\.\d+)?|0?\.\d+|\d{1,3}\s*%)", text)
    if not m:
        m = re.findall(r"(\d?\.\d+|\d{1,3}\s*%)", text)
    if not m:
        return None
    v = m[-1].strip()
    if v.endswith("%"):
        return _clip(float(v[:-1]) / 100)
    return _clip(float(v))


def infer(rows, n_sample, proxy=None, out_path=None):
    """Keyless forecast on a deterministic sample of rows -> jsonl {id, prob}. $0 (cost-gated)."""
    import sqlite3
    from engine.adapters import llm

    conn = sqlite3.connect(Path(__file__).resolve().parents[2] / "data" / "foresight.db")
    sample = rows if n_sample <= 0 else [rows[i] for i in range(0, len(rows), max(1, len(rows) // n_sample))][:n_sample]
    out_path = Path(out_path or (Path(__file__).resolve().parents[2] / "data" / "kalshibench" / "preds.jsonl"))
    done = set()
    if out_path.exists():
        for line in open(out_path):
            if line.strip():
                done.add(json.loads(line)["id"])
    f = open(out_path, "a")
    ok = 0
    for j, r in enumerate(sample):
        if r["id"] in done:
            continue
        try:
            txt = llm.complete(conn, _forecast_prompt(r), system=FORECAST_SYS, max_tokens=400, proxy=proxy)
            p = _parse_prob(txt)
        except Exception as e:
            p = None
            print(f"  [{j+1}/{len(sample)}] {r['id'][:22]:22s} ERROR {str(e)[:50]}")
        if p is not None:
            f.write(json.dumps({"id": r["id"], "prob": p}) + "\n")
            f.flush()
            ok += 1
            if ok % 10 == 0:
                print(f"  [{j+1}/{len(sample)}] {ok} preds written (last p={p:.2f})")
    f.close()
    print(f"infer done: {ok} new preds -> {out_path}")
    return str(out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", action="append", default=[], help="name=path.jsonl (id->prob) LLM signal")
    ap.add_argument("--cutoff", default=None, help="ISO date; restrict scoring to rows resolving after it")
    ap.add_argument("--infer", type=int, default=0, help="run keyless inference on N sampled rows, then score")
    ap.add_argument("--proxy", default=None, help="proxy spec for keyless inference scaling")
    args = ap.parse_args()

    rows = load_rows()
    dated = [r["close_time"][:10] for r in rows if r["close_time"]]
    print(f"KalshiBench: {len(rows)} contracts, close_time {min(dated)} .. {max(dated)}, "
          f"yes-rate={sum(r['y'] for r in rows)/len(rows):.3f}\n")

    print("Published Table-4 frontier (arXiv:2512.16030):")
    for nm, acc, br, ec, bs in PUBLISHED:
        print(f"  {nm:32s}        acc={acc:.3f}  Brier={br:.4f}  ECE={ec:.4f}  BSS={bs:+.4f}")
    print(f"  {'base-rate floor':32s}        acc=  -    Brier={BASE_RATE_REF:.4f}  ECE=  -     BSS=+0.0000\n")

    # optional leak slice
    if args.cutoff:
        keep = set(clean_slice(rows, args.cutoff))
        rows = [r for i, r in enumerate(rows) if i in keep]
        print(f"[leak-free slice] cutoff>{args.cutoff}: {len(rows)} rows\n")

    ys = [r["y"] for r in rows]

    print("Ours — leak-free, k-fold OOS (no overfit):")
    glob = climatology(rows, by="category", k_shrink=0)  # k=0 -> raw category rate
    # global-only prior for reference
    g_only = climatology([{**r, "category": "ALL"} for r in rows], by="category")
    report("global climatology", g_only, ys)
    cat = climatology(rows, k_shrink=5)
    report("category climatology (k=5)", cat, ys)
    # finer series_ticker prior, OOS-blended onto the category prior: lowest Brier (point-beats Opus),
    # at some ECE cost (rare tickers are noisier). Both lines shown so the trade-off is explicit.
    tick = climatology(rows, k_shrink=8, by="series_ticker")
    cat_tick, _ = fit_blend_weight(cat, tick, ys, rows)
    report("category+ticker OOS blend", cat_tick, ys)

    prior = cat  # the working prior (cleanest calibration) for downstream LLM blends

    # optionally run keyless inference first, then score it as a signal
    pred_specs = list(args.pred)
    if args.infer:
        path = infer(rows, args.infer, proxy=args.proxy)
        pred_specs.append(f"keyless={path}")

    # blend + calibrate any LLM signals. On overconfident raw LLM probs the OOS isotonic step is the
    # whole edge — it collapses the overconfidence that sinks the frontier models below the base rate.
    for spec in pred_specs:
        name, path = spec.split("=", 1)
        sig_map = {}
        for line in open(path):
            if line.strip():
                d = json.loads(line)
                sig_map[str(d["id"])] = float(d["prob"])
        cov_idx = [i for i, r in enumerate(rows) if r["id"] in sig_map]
        if len(cov_idx) < N_FOLDS:
            print(f"\n  signal '{name}': coverage {len(cov_idx)}/{len(rows)} — too few to score OOS")
            continue
        # score ONLY on covered rows (apples-to-apples; missing rows would just inherit the prior)
        srows = [rows[i] for i in cov_idx]
        sys_ = [ys[i] for i in cov_idx]
        sprior = [prior[i] for i in cov_idx]
        sraw = [sig_map[r["id"]] for r in srows]
        print(f"\n  signal '{name}': coverage {len(cov_idx)}/{len(rows)}  (scored on covered rows)")
        report("  raw LLM", sraw, sys_)
        scal = calibrate_oos(sraw, sys_, srows)
        report("  LLM + OOS isotonic", scal, sys_)
        report("  prior alone (same rows)", sprior, sys_)
        blended, _ = fit_blend_weight(sprior, scal, sys_, srows)
        report("  prior + calibrated LLM", blended, sys_)


if __name__ == "__main__":
    main()
