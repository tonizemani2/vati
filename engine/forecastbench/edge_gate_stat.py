"""engine/forecastbench/edge_gate_stat.py — the LEAK-FREE edge gate ($0, no LLM).

Why not an LLM gate? A current frontier model already knows the resolution of any question that
resolved before its training cutoff — it reasons backward from the answer (observed live: DeepSeek
V4-Pro "…a second test flight happened on November 18, 2023… thus the answer resolved NO"). So an
in-context LLM gate on historical questions measures the model's MEMORY, not our features. The only
honest test of "do the features carry edge over the crowd" is statistical:

    fit  (features → outcome)  on a TRAIN split of questions that resolved EARLY,
    score on a held-out TEST split that resolved LATER (the model never sees test outcomes),
    and ask: does adding the features to the crowd prior LOWER test Brier vs the crowd alone?

That is the Beyond Brier marginal-edge question, computed leak-free. Features are leak-free by
construction (edge_dataset.py audits source_date < T); the temporal split makes the evaluation
ex-ante. No network, no spend.

CLI:
    uv run python -m engine.forecastbench.edge_gate_stat --path data/forecastbench/trainset/edge_scitech.jsonl
"""
from __future__ import annotations

import argparse
import json
import math

import numpy as np


def _feat_vector(r: dict) -> list[float] | None:
    """Pull the numeric leak-free features from a row into a fixed vector."""
    fv = next((f for f in r.get("features", []) if f["name"] == "arxiv_share_velocity"), None)
    if fv is None:
        return None
    return [
        fv["accel"],
        math.log1p(max(0.0, fv["share_ppm_y2"])),
        fv["yoy_share_growth"],
        fv.get("surprise_sigma", 0.0),
        fv.get("diffusion_growth", 1.0),
        math.log1p(max(0.0, fv.get("diffusion_breadth", 0))),
    ]


def _logit(p: float) -> float:
    p = min(0.999, max(0.001, p))
    return math.log(p / (1 - p))


def _fit_logistic(X: np.ndarray, y: np.ndarray, *, l2: float = 1.0, iters: int = 500, lr: float = 0.1) -> np.ndarray:
    """Tiny ridge-logistic via gradient descent (numpy only — no sklearn dep). X has a bias column."""
    w = np.zeros(X.shape[1])
    n = len(y)
    for _ in range(iters):
        z = X @ w
        p = 1.0 / (1.0 + np.exp(-z))
        grad = X.T @ (p - y) / n + l2 * np.r_[0.0, w[1:]] / n  # don't regularize bias
        w -= lr * grad
    return w


def _predict(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-(X @ w)))


def _brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def run(*, path: str, test_frac: float = 0.30, log=print) -> dict:
    with open(path) as f:
        rows = [json.loads(line) for line in f]
    rows = [r for r in rows if _feat_vector(r) is not None and r.get("crowd_prob_at_T") is not None]
    rows.sort(key=lambda r: r["resolved_date"])  # temporal order: train early, test late
    n = len(rows)
    if n < 20:
        log(f"only {n} usable rows — too few for a split. Build a bigger dataset first.")
        return {"n": n}
    n_test = max(8, int(n * test_frac))
    train, test = rows[: n - n_test], rows[n - n_test :]
    split_date = test[0]["resolved_date"]

    def design(rs):
        feats = np.array([_feat_vector(r) for r in rs], dtype=float)
        crowd_logit = np.array([[_logit(r["crowd_prob_at_T"])] for r in rs])
        y = np.array([float(r["outcome"]) for r in rs])
        return feats, crowd_logit, y

    f_tr, c_tr, y_tr = design(train)
    f_te, c_te, y_te = design(test)

    # standardize features on TRAIN stats only (no test leakage into preprocessing)
    mu, sd = f_tr.mean(0), f_tr.std(0) + 1e-9
    f_tr_z, f_te_z = (f_tr - mu) / sd, (f_te - mu) / sd

    bias_tr, bias_te = np.ones((len(y_tr), 1)), np.ones((len(y_te), 1))

    # 1) crowd-only (the free prior, no fit) — the bar to beat
    p_crowd = np.array([r["crowd_prob_at_T"] for r in test])
    b_crowd = _brier(p_crowd, y_te)

    # 2) features-only logistic
    w_feat = _fit_logistic(np.hstack([bias_tr, f_tr_z]), y_tr)
    p_feat = _predict(np.hstack([bias_te, f_te_z]), w_feat)
    b_feat = _brier(p_feat, y_te)

    # 3) crowd + features: does fitting features ON TOP of the crowd help out-of-sample?
    w_cf = _fit_logistic(np.hstack([bias_tr, c_tr, f_tr_z]), y_tr)
    p_cf = _predict(np.hstack([bias_te, c_te, f_te_z]), w_cf)
    b_cf = _brier(p_cf, y_te)

    # 4) crowd-only logistic (recalibrated crowd, NO features) — the fair control for #3
    w_c = _fit_logistic(np.hstack([bias_tr, c_tr]), y_tr)
    p_c = _predict(np.hstack([bias_te, c_te]), w_c)
    b_c = _brier(p_c, y_te)

    log(f"\n── leak-free edge gate (temporal split) ─────────────")
    log(f"   rows usable        : {n}  (train {len(train)} resolve ≤ {train[-1]['resolved_date']}, "
        f"test {len(test)} resolve ≥ {split_date})")
    log(f"   base rate (test)   : {y_te.mean():.2f} YES")
    log(f"   crowd-only   Brier : {b_crowd:.4f}   (the free prior — the bar to beat)")
    log(f"   crowd(recal) Brier : {b_c:.4f}   (recalibrated crowd, NO features — fair control)")
    log(f"   features-only Brier: {b_feat:.4f}")
    log(f"   crowd+features Brier: {b_cf:.4f}")
    log(f"   marginal edge      : {b_c - b_cf:+.4f}   (recal-crowd − crowd+features; positive ⇒ features add edge)")
    log(f"   features vs crowd  : {b_crowd - b_feat:+.4f}   (features ALONE − raw crowd)")
    verdict = ("ALIVE — features add out-of-sample edge over the crowd. Worth a real (bigger) build + finetune."
               if (b_c - b_cf) > 0.003
               else "WEAK/NULL — features don't beat the crowd out-of-sample here. Need better features/sources "
                    "before any GPU. (n is small; a bigger build could still change this.)")
    log(f"   verdict            : {verdict}")
    log(f"\n   NOTE: leak-free (features audited < T; evaluated on questions resolving AFTER the train split).")
    log(f"   NOTE: n={n} is small — this is indicative. Scale the build (FTS over papers) for a robust number.")
    return {"n": n, "b_crowd": b_crowd, "b_crowd_recal": b_c, "b_feat": b_feat,
            "b_crowd_feat": b_cf, "marginal_edge": b_c - b_cf}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Leak-free statistical edge gate ($0, no LLM).")
    ap.add_argument("--path", default="data/forecastbench/trainset/edge_scitech.jsonl")
    ap.add_argument("--test-frac", type=float, default=0.30)
    a = ap.parse_args()
    run(path=a.path, test_frac=a.test_frac)
