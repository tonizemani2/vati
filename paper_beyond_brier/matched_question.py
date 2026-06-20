#!/usr/bin/env python3
"""
Matched-question human-vs-LLM contribution control (peer-review C1/C2).

The 75x human-LLM gap was challenged as a question-selection artifact: humans
answered 56 market questions, the LLM battery 256, and resolved human questions
are (mildly) easier. This script removes the confound by scoring BOTH groups on
the SAME 56 questions and recomputing bias-corrected Delta-LL.

Result: on the identical question set the superforecasters add ~+0.094 nats while
the 130-config LLM battery adds ~ -0.003 (NEGATIVE). The human-answered questions
are not easier (mean |p_ref-0.5| 0.357 vs 0.393 full) so the gap is not selection.
Single round 2024-07-21 (the only released human track).
"""
import os, json, glob, re, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import statsmodels.api as sm

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

def dll_adj(df):
    """bias-corrected per-forecast incremental log-likelihood of zf beyond zref."""
    y = df["y"].values.astype(float); N = len(df)
    if N < 8 or y.std() == 0: return np.nan
    try:
        ll1 = sm.Logit(y, sm.add_constant(df[["zref"]].values)).fit(disp=0).llf
        ll2 = sm.Logit(y, sm.add_constant(df[["zref", "zf"]].values)).fit(disp=0).llf
    except Exception:
        return np.nan
    return (ll2 - ll1) / N - 0.5 / N

# ---- LLM battery rows (single round, market track) ----
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

# ---- human superforecasters (market track) from the committed join ----
J = pd.read_csv(os.path.join(ROOT, "out/joined_rows.csv"))
H = J[(J.track == "market") & (J.tag == "super")].copy()
H["qid"] = H["id"].astype(str); H["zref"] = logit(H.p_ref)
H["zf"] = logit(H.forecast.astype(float))

human_qids = set(H.qid.unique())
common = sorted(human_qids & set(L.qid.unique()))

def battery_mean(df):
    v = [dll_adj(g) for _, g in df.groupby("fid")]
    v = [x for x in v if not np.isnan(x)]
    return float(np.mean(v)), len(v)

def human_mean(df, min_n=20):
    v = [dll_adj(g) for _, g in df.groupby("user_id") if len(g) >= min_n]
    v = [x for x in v if not np.isnan(x)]
    return float(np.mean(v)), len(v)

# difficulty
q = L.groupby("qid").p_ref.first()
diff_common = (q[q.index.isin(common)] - 0.5).abs().mean()
diff_full = (q - 0.5).abs().mean()

llm_full, n_full = battery_mean(L)
llm_match, n_match = battery_mean(L[L.qid.isin(common)])
hum_match, n_h = human_mean(H[H.qid.isin(common)])

# bootstrap the matched gap over the common questions
boot = []
cq = np.array(common)
for _ in range(2000):
    samp = set(RNG.choice(cq, size=len(cq), replace=True))
    lm, _ = battery_mean(L[L.qid.isin(samp)])
    hm, _ = human_mean(H[H.qid.isin(samp)])
    if not (np.isnan(lm) or np.isnan(hm)): boot.append(hm - lm)
boot = np.array(boot)

out = {
    "n_common_questions": len(common),
    "difficulty_mean_abs_pref_minus_half": {"common": diff_common, "full": diff_full},
    "llm_battery_dll_adj_full": llm_full, "n_configs_full": n_full,
    "llm_battery_dll_adj_matched": llm_match, "n_configs_matched": n_match,
    "human_super_dll_adj_matched": hum_match, "n_human": n_h,
    "matched_gap_human_minus_llm": hum_match - llm_match,
    "matched_gap_bootstrap_95ci": [float(np.percentile(boot, 2.5)),
                                   float(np.percentile(boot, 97.5))],
}
os.makedirs(os.path.join(ROOT, "out_mr"), exist_ok=True)
json.dump(out, open(os.path.join(ROOT, "out_mr/matched_question.json"), "w"), indent=2)
for k, v in out.items(): print(f"{k}: {v}")
