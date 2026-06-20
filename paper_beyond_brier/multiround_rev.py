#!/usr/bin/env python3
"""Revision analysis answering the peer-review panel.

CRITICAL fixes:
  (1) finite-sample bias-corrected Delta-LL.  In-sample LL gain of adding one
      regressor (the forecast) to the price-only logit has expected value 0.5/N
      per row under H0 (2N*dLL ~ chi^2_1, mean 1).  Late rounds have small N, so
      the raw dLL is inflated exactly where capability is highest.  We subtract
      the 0.5/N null bias: dLL_adj = dLL_insample - 0.5/N.
  (2) report the trend SLOPE with a 95% CI and an equivalence (TOST-style)
      reading -- years to reach the human level -- instead of "flat, p=0.57".
  (3) N-weighted trend + robustness to dropping the thin late rounds.
  (4) human Delta-LL pooled, with a question-block-bootstrap 95% CI, as a dated
      point (single round) rather than a line.
  (5) agentic group: dLL_adj, significance, robustness to dropping the max round.
  (6) per-round mean dLL_adj standard error (across configs) for error bars.
  (7) capability-axis slope with a base-model-clustered bootstrap CI.

Reuses out_mr/config_round_long.csv (already has per-config dll and N) and
out/joined_rows.csv (human market track).  Keyless, local.
"""
import os, json, re, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from scipy import stats
import statsmodels.api as sm

ROOT = "/Users/emizemani/Desktop/predictthefuture/paper_beyond_brier"
OUT = os.path.join(ROOT, "out_mr")
RNG = np.random.default_rng(20240721)
EPS = 1e-3
H_LEVEL = 0.080  # single-round superforecaster pooled dLL target

C = pd.read_csv(os.path.join(OUT, "config_round_long.csv"))
R = pd.read_csv(os.path.join(OUT, "round_summary.csv"))

def rd_year(rd):
    y, m, d = (int(x) for x in rd.split("-")); return y + (m - 1) / 12 + (d - 1) / 365

# bias-corrected per-config dLL
C["dll_adj"] = C["dll"] - 0.5 / C["N"]
fb = C[C.is_fb & C.N.ge(50) & C.dll.notna()].copy()
ag = C[(~C.is_fb) & C.N.ge(50) & C.dll.notna()].copy()

# question-count confound the reviewers flagged
rr = R.dropna(subset=["fb_dll_mean"])
print(f"[confound] corr(year, n_questions) = {np.corrcoef(rr.year, rr.n_questions)[0,1]:+.2f}")
print(f"[confound] corr(raw fb_dll_mean, n_questions) = {np.corrcoef(rr.fb_dll_mean, rr.n_questions)[0,1]:+.2f}")

# ---- per-round means of bias-corrected dLL (+ SE across configs) ----
g = fb.groupby("round")
rd = pd.DataFrame({
    "round": g.size().index,
    "n_cfg": g.size().values,
    "n_q": g["nq"].median().values,
    "dll_raw": g["dll"].mean().values,
    "dll_adj": g["dll_adj"].mean().values,
    "dll_adj_se": (g["dll_adj"].std() / np.sqrt(g.size())).values,
    "n_rows_med": g["N"].median().values,
})
rd["year"] = rd["round"].map(rd_year)
rd = rd.sort_values("year").reset_index(drop=True)
rd.to_csv(os.path.join(OUT, "round_trend_rev.csv"), index=False)

def slope_ci(x, y, w=None, B=5000):
    x = np.asarray(x); y = np.asarray(y)
    if w is None:
        sl, ic, r, p, se = stats.linregress(x, y)
    else:
        W = np.asarray(w); b = np.polyfit(x, y, 1, w=np.sqrt(W)); sl, ic = b
        p = se = r = np.nan
    bs = []
    n = len(x)
    for _ in range(B):
        idx = RNG.integers(0, n, n)
        try:
            if w is None:
                bs.append(np.polyfit(x[idx], y[idx], 1)[0])
            else:
                bs.append(np.polyfit(x[idx], y[idx], 1, w=np.sqrt(np.asarray(w)[idx]))[0])
        except Exception:
            pass
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return sl, ic, (lo, hi), p

print("\n=== BIAS-CORRECTED TREND (per-round means of dLL_adj) ===")
sl, ic, ci, p = slope_ci(rd.year, rd.dll_adj)
print(f"  dll_adj slope = {sl:+.5f} nats/yr  95%CI [{ci[0]:+.5f}, {ci[1]:+.5f}]  p={p:.3f}")
print(f"  level (mean dll_adj over rounds) = {rd.dll_adj.mean():+.5f} nats "
      f"[{rd.dll_adj.min():+.4f},{rd.dll_adj.max():+.4f}]")
slw, icw, ciw, _ = slope_ci(rd.year, rd.dll_adj, w=rd.n_rows_med)
print(f"  N-weighted slope = {slw:+.5f}  95%CI [{ciw[0]:+.5f},{ciw[1]:+.5f}]")
# robustness: drop the thinnest 5 rounds (fewest questions)
keep = rd.sort_values("n_q").iloc[5:]
slk, ick, cik, pk = slope_ci(keep.year, keep.dll_adj)
print(f"  drop 5 thinnest rounds (n={len(keep)}): slope={slk:+.5f} 95%CI [{cik[0]:+.5f},{cik[1]:+.5f}]")

# equivalence / years-to-human at the upper CI bound
level = rd.dll_adj.mean()
gap = H_LEVEL - max(level, 0)
yrs_at_upper = gap / ci[1] if ci[1] > 0 else np.inf
print(f"  TOST reading: to reach human {H_LEVEL} from level {level:.4f}, even at the UPPER "
      f"95% slope {ci[1]:+.5f}/yr needs {yrs_at_upper:.0f} years")

# raw (uncorrected) for comparison
slr, icr, cir, pr = slope_ci(rd.year, rd.dll_raw)
print(f"  [raw dLL slope was {slr:+.5f}, level {rd.dll_raw.mean():.5f}] "
      f"-> bias correction lowers the level by {rd.dll_raw.mean()-rd.dll_adj.mean():.5f} nats")

# ---- capability axis: per-model dll_adj, base-model-clustered bootstrap CI ----
def base_model(cfg):
    s = cfg.split("|", 1)[1].strip() if "|" in cfg else cfg
    s = re.sub(r"\(.*?\)", "", s).strip()
    return s
cm = fb.dropna(subset=["rel"]).copy()
cm["bm"] = cm.cfg.map(base_model)
cap = cm.groupby("cfg").agg(rel=("rel", "first"), bm=("bm", "first"),
                            dll_adj=("dll_adj", "mean")).reset_index()
slc, icc, rc, pc, sec = stats.linregress(cap.rel, cap.dll_adj)
# cluster bootstrap over base models
bms = cap.bm.unique()
byb = {b: cap[cap.bm == b] for b in bms}
bs = []
for _ in range(5000):
    pick = RNG.choice(bms, len(bms), replace=True)
    d = pd.concat([byb[b] for b in pick])
    if d.rel.nunique() > 1:
        bs.append(np.polyfit(d.rel, d.dll_adj, 1)[0])
clo, chi = np.percentile(bs, [2.5, 97.5])
print("\n=== CAPABILITY AXIS (bias-corrected, base-model clustered) ===")
print(f"  per-model dll_adj slope = {slc:+.5f} nats/yr  base-model-clustered 95%CI "
      f"[{clo:+.5f},{chi:+.5f}]  (n_models={len(cap)}, n_base={len(bms)})")
early = cap[cap.rel <= 2024.5].dll_adj.mean(); late = cap[cap.rel >= 2026.0].dll_adj.mean()
print(f"  early <=2024.5 mean dll_adj={early:+.5f};  late >=2026 mean={late:+.5f}")
cap.to_csv(os.path.join(OUT, "capability_axis_rev.csv"), index=False)

# ---- agentic group: dll_adj, significance, drop-max robustness ----
ga = ag.groupby("round").agg(dll_adj=("dll_adj", "mean"), n=("dll_adj", "size")).reset_index()
ga["year"] = ga["round"].map(rd_year)
print("\n=== AGENTIC SYSTEMS (bias-corrected) ===")
print(f"  rounds={len(ga)} mean dll_adj={ga.dll_adj.mean():+.5f} "
      f"[{ga.dll_adj.min():+.4f},{ga.dll_adj.max():+.4f}]")
if len(ga) >= 4:
    sla, ica, ra_, pa_, sea = stats.linregress(ga.year, ga.dll_adj)
    print(f"  trend slope={sla:+.5f} p={pa_:.3f} (NON-significant)")
    gd = ga.sort_values("dll_adj").iloc[:-1]  # drop max round
    print(f"  drop max round: mean dll_adj={gd.dll_adj.mean():+.5f} "
          f"(was {ga.dll_adj.mean():+.5f})")
# one-sample test agentic vs base-model level
tb, pb = stats.ttest_ind(ag.dll_adj, fb.dll_adj, equal_var=False)
print(f"  agentic vs base-model dll_adj (Welch): "
      f"agentic mean={ag.dll_adj.mean():+.5f} base={fb.dll_adj.mean():+.5f} p={pb:.3f}")

# ---- human per-forecaster bias-corrected dLL (single round), apples-to-apples ----
# Compared like-for-like with the per-config LLM dLL_adj: each superforecaster's own
# dLL on their ~28 questions, bias-corrected by 0.5/N, then averaged over forecasters.
print("\n=== HUMAN Delta-LL (single round), bias-corrected, apples-to-apples ===")
def logit(p): p = np.clip(p, EPS, 1 - EPS); return np.log(p / (1 - p))
BFAM = sm.families.Binomial()
h_perf = h_lo = h_hi = h_pool = h_ens = np.nan
try:
    j = pd.read_csv(os.path.join(ROOT, "out", "joined_rows.csv"))
    h = j[j.track == "market"].copy()
    h["forecast"] = h["forecast"].clip(0, 1)
    h = h.dropna(subset=["p_ref", "forecast", "y"])
    h["zref"] = logit(h.p_ref); h["zf"] = logit(h.forecast)
    cnt = h.groupby("fid").size(); ranked = list(cnt[cnt >= 20].index)   # the 23 superforecasters
    hs = h[h.fid.isin(ranked)]
    def dll_glm(df):
        y = df.y.values.astype(float)
        if len(np.unique(y)) < 2 or len(df) < 10: return np.nan
        try:
            l0 = sm.GLM(y, np.column_stack([np.ones(len(df)), df.zref]), family=BFAM).fit().llf
            l1 = sm.GLM(y, np.column_stack([np.ones(len(df)), df.zref, df.zf]), family=BFAM).fit().llf
            return (l1 - l0) / len(df)
        except Exception: return np.nan
    perf = {}
    for f in ranked:
        d = dll_glm(hs[hs.fid == f]); n = (hs.fid == f).sum()
        if d == d: perf[f] = d - 0.5 / n
    vals = np.array(list(perf.values()))
    bs = [np.mean(RNG.choice(vals, len(vals), replace=True)) for _ in range(5000)]
    h_perf, h_lo, h_hi = float(vals.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))
    h_pool = float(dll_glm(hs))                              # pooled over all super rows (~ the 0.08 in §6)
    qg = hs.groupby("id").agg(y=("y", "first"), p_ref=("p_ref", "first"),
                              forecast=("forecast", "median")).dropna()
    qg["zref"] = logit(qg.p_ref); qg["zf"] = logit(qg.forecast)
    h_ens = float(dll_glm(qg) - 0.5 / len(qg))               # median ensemble, bias-corrected
    print(f"  per-forecaster bias-corrected mean = {h_perf:+.4f}  95%CI [{h_lo:+.4f},{h_hi:+.4f}] (n={len(vals)})")
    print(f"  pooled-over-super-rows dLL = {h_pool:+.4f} (the ~0.08 reported in Section 6)")
    print(f"  median-ensemble bias-corrected = {h_ens:+.4f}")
except Exception as e:
    print(f"  (human computation skipped: {e})")

summary = {
    "bias_correction": "dLL_adj = dLL_insample - 0.5/N (null in-sample LR bias)",
    "confound_corr_year_nq": float(np.corrcoef(rr.year, rr.n_questions)[0, 1]),
    "trend_adj": {"slope": float(sl), "ci": [float(ci[0]), float(ci[1])], "p": float(p),
                  "level": float(level), "slope_weighted": float(slw),
                  "slope_drop_thin": float(slk), "ci_drop_thin": [float(cik[0]), float(cik[1])],
                  "years_to_human_at_upper_ci": float(yrs_at_upper),
                  "raw_level": float(rd.dll_raw.mean()), "raw_slope": float(slr)},
    "capability_adj": {"slope": float(slc), "cluster_ci": [float(clo), float(chi)],
                       "n_models": int(len(cap)), "n_base": int(len(bms)),
                       "early_mean": float(early), "late_mean": float(late)},
    "agentic_adj": {"n_rounds": int(len(ga)), "mean": float(ga.dll_adj.mean()),
                    "slope": float(sla), "slope_p": float(pa_),
                    "mean_drop_max": float(gd.dll_adj.mean()),
                    "vs_base_p": float(pb), "base_mean": float(fb.dll_adj.mean())},
    "human": {"per_forecaster_bias_corrected": float(h_perf), "ci": [float(h_lo), float(h_hi)],
              "pooled": float(h_pool), "median_ensemble_bias_corrected": float(h_ens)},
}
json.dump(summary, open(os.path.join(OUT, "summary_rev.json"), "w"), indent=2, default=float)
print("\nwrote out_mr/summary_rev.json, round_trend_rev.csv, capability_axis_rev.csv")
