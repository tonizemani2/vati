#!/usr/bin/env python3
"""
Two robustness checks demanded by the review panel (single round 2024-07-21).

(1) OUT-OF-SAMPLE Delta-LL. The in-sample Delta-LL is corrected by the first-order
    null mean 1/2N; a skeptic worries the small late rounds break that asymptotic.
    The cross-fitted (2-fold) Delta-LL carries NO in-sample optimism and needs no
    analytic correction. If it agrees with the bias-corrected in-sample number, the
    correction is vindicated.

(2) DEBIASED-PRICE Delta-LL. The whole apparatus assumes p_ref is a calibrated
    probability. If the price is biased (favorite-longshot), part of the human edge
    could be freely-recoverable price de-biasing rather than private information.
    We recalibrate p_ref with OUT-OF-FOLD isotonic regression and recompute Delta-LL
    beyond the debiased price for both groups. If the human number largely survives,
    the 'private information' reading is earned.
"""
import os, json, glob, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import statsmodels.api as sm
from sklearn.isotonic import IsotonicRegression

ROOT = os.path.dirname(os.path.abspath(__file__))
FCDIR = os.path.join(ROOT, "fb_forecast_sets",
                     "forecastbench-processed-forecast-sets", "2024-07-21")
MARKET = {"manifold", "metaculus", "polymarket", "infer"}
BASELINE = ("always-0", "always-1", "always-0.5", "random-uniform",
            "naive-forecaster", "imputed-forecaster", "human_public",
            "human_super", "llm_crowd")
EPS = 1e-3
RNG = np.random.default_rng(20240721)

def logit(p): p = np.clip(p, EPS, 1-EPS); return np.log(p/(1-p))
def fid_of(p):
    b = os.path.basename(p)[:-5]
    for pre in ("2024-07-21.", "24-07-21."): b = b[len(pre):] if b.startswith(pre) else b
    return b
def is_base(f): return any(t in f for t in BASELINE)
def fit_ll(y, X):
    return sm.Logit(y, X).fit(disp=0).llf
def ll_eval(y, X, beta):
    eta = X @ beta; p = np.clip(1/(1+np.exp(-eta)), EPS, 1-EPS)
    return np.sum(y*np.log(p) + (1-y)*np.log(1-p))

def insample_dll(df, refcol="zref"):
    y = df["y"].values.astype(float); N = len(df)
    if N < 8 or y.std() == 0: return np.nan
    try:
        ll1 = fit_ll(y, sm.add_constant(df[[refcol]].values))
        ll2 = fit_ll(y, sm.add_constant(df[[refcol, "zf"]].values))
    except Exception: return np.nan
    return (ll2 - ll1)/N - 0.5/N

def oos_dll(df, refcol="zref"):
    """cross-fitted 2-fold held-out Delta-LL; no analytic correction."""
    y = df["y"].values.astype(float); N = len(df)
    if N < 12 or y.std() == 0: return np.nan
    idx = RNG.permutation(N); half = N//2
    folds = [(idx[:half], idx[half:]), (idx[half:], idx[:half])]
    num = den = 0.0
    for tr, te in folds:
        ytr, yte = y[tr], y[te]
        if ytr.std() == 0 or yte.std() == 0: return np.nan
        Xtr1 = sm.add_constant(df[[refcol]].values[tr]); Xte1 = sm.add_constant(df[[refcol]].values[te])
        Xtr2 = sm.add_constant(df[[refcol, "zf"]].values[tr]); Xte2 = sm.add_constant(df[[refcol, "zf"]].values[te])
        try:
            b1 = sm.Logit(ytr, Xtr1).fit(disp=0).params
            b2 = sm.Logit(ytr, Xtr2).fit(disp=0).params
        except Exception: return np.nan
        num += ll_eval(yte, Xte2, b2) - ll_eval(yte, Xte1, b1); den += len(te)
    return num/den

# ---- load ----
rows = []
for path in sorted(glob.glob(os.path.join(FCDIR, "*.json"))):
    fid = fid_of(path)
    if is_base(fid): continue
    for r in json.load(open(path))["forecasts"]:
        if r.get("source") not in MARKET or not r.get("resolved"): continue
        y = r.get("resolved_to")
        if y not in (0.0, 1.0): continue
        pr, fc = r.get("market_value_on_due_date"), r.get("forecast")
        if pr is None or fc is None: continue
        try: pr, fc = float(pr), float(fc)
        except (TypeError, ValueError): continue
        if not (0 <= fc <= 1): continue
        rows.append({"fid": fid, "qid": str(r["id"]), "p_ref": pr, "p": fc, "y": float(y)})
L = pd.DataFrame(rows); L["zref"] = logit(L.p_ref); L["zf"] = logit(L.p)

J = pd.read_csv(os.path.join(ROOT, "out/joined_rows.csv"))
H = J[(J.track == "market") & (J.tag == "super")].copy()
H["qid"] = H["id"].astype(str); H["p_ref"] = H.p_ref.astype(float)
H["zref"] = logit(H.p_ref); H["zf"] = logit(H.forecast.astype(float)); H["y"] = H.y.astype(float)

# ---- out-of-fold isotonic debiasing of the price (per question) ----
def add_debiased_ref(df):
    q = df.groupby("qid").agg(p_ref=("p_ref", "first"), y=("y", "first")).reset_index()
    qids = q.qid.values; perm = RNG.permutation(len(q)); half = len(q)//2
    fa, fb = qids[perm[:half]], qids[perm[half:]]
    pr_deb = {}
    for tr_ids, te_ids in [(fa, fb), (fb, fa)]:
        tr = q[q.qid.isin(tr_ids)]; te = q[q.qid.isin(te_ids)]
        iso = IsotonicRegression(out_of_bounds="clip", y_min=EPS, y_max=1-EPS)
        iso.fit(tr.p_ref.values, tr.y.values)
        for _, row in te.iterrows(): pr_deb[row.qid] = float(iso.predict([row.p_ref])[0])
    df = df.copy(); df["p_ref_deb"] = df.qid.map(pr_deb); df["zref_deb"] = logit(df.p_ref_deb)
    return df

Ld = add_debiased_ref(L); Hd = add_debiased_ref(H)

def battery(df, fn, refcol="zref"):
    v = [fn(g, refcol) for _, g in df.groupby("fid")]
    v = [x for x in v if not np.isnan(x)]
    return float(np.mean(v)), len(v)
def humans(df, fn, refcol="zref", min_n=20):
    v = [fn(g, refcol) for _, g in df.groupby("user_id") if len(g) >= min_n]
    v = [x for x in v if not np.isnan(x)]
    return float(np.mean(v)), len(v)

out = {}
out["llm_insample_adj"] = battery(L, insample_dll)[0]
out["llm_oos"] = battery(L, oos_dll)[0]
out["llm_insample_adj_debiased"] = battery(Ld, insample_dll, "zref_deb")[0]
out["human_insample_adj"], out["n_human"] = humans(H, insample_dll)
out["human_oos"] = humans(H, oos_dll)[0]
out["human_insample_adj_debiased"] = humans(Hd, insample_dll, "zref_deb")[0]
# price calibration check
q = L.groupby("qid").agg(p=("p_ref", "first"), y=("y", "first"))
out["price_brier"] = float(((q.p - q.y)**2).mean())
out["price_debiased_brier"] = float(((Ld.groupby("qid").p_ref_deb.first() - q.y)**2).mean())

json.dump(out, open(os.path.join(ROOT, "out_mr/oos_debias.json"), "w"), indent=2)
for k, v in out.items(): print(f"{k}: {v}")
print("\nSUMMARY")
print(f"  OOS:      human {out['human_oos']:+.4f}  vs LLM {out['llm_oos']:+.4f}")
print(f"  in-samp:  human {out['human_insample_adj']:+.4f}  vs LLM {out['llm_insample_adj']:+.4f}")
print(f"  debiased: human {out['human_insample_adj_debiased']:+.4f}  vs LLM {out['llm_insample_adj_debiased']:+.4f}")
