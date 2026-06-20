#!/usr/bin/env python3
"""
Beyond Brier -- REVISION (peer-review corrections).

Extends compute_edge.py. Reuses the joined market-track table (out/joined_rows.csv,
the 3,670 market rows; the 23 superforecasters with N>=20). Addresses 8 reviewer
issues; writes NEW outputs with a _v2 suffix. Does NOT overwrite v1.

Reviewer issues addressed:
  1. Cross-forecaster comparability: (a) common-core reorder, (b) mixed-effects /
     two-way-FE difficulty-adjusted forecaster effect alpha_f, (c) difficulty-covariate
     robustness.
  2. CI-straddle disclosure (bootstrap 95% edge CIs: straddle / +ve / -ve counts).
  3. Rank-stability bootstrap (B=10000): rho(edge-rank vs Brier-rank) distribution;
     per-forecaster rank intervals.
  4. Cluster-robust encompassing (cluster on question id).
  5. FDR-controlled per-forecaster edge tests (Diebold-Mariano HLN; BH q=0.10).
  6. Log-score robustness of the reorder.
  7. Recalibration noise floor (synthetic perfectly-calibrated forecasters).
  8. Differential dropout check (market track).

Honest by construction: if a correction weakens the v1 claim, the number is reported
as-is.
"""
import os, json, math, warnings, hashlib
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.isotonic import IsotonicRegression
import statsmodels.api as sm
import statsmodels.formula.api as smf

ROOT = "/Users/emizemani/Desktop/predictthefuture/paper_beyond_brier"
OUT = os.path.join(ROOT, "out")
EPS = 1e-3
RNG = np.random.default_rng(20240721)
B_BOOT = 10000
MIN_N = 20  # market track, 23 ranked forecasters

def seed_of(s):
    """Deterministic per-string seed (Python's hash() is salted per-process)."""
    return int(hashlib.md5(str(s).encode()).hexdigest()[:8], 16)

def brier(p, y):
    return (p - y) ** 2

def logscore_loss(p, y):
    # negative log-likelihood (lower = better), clipped
    p = np.clip(p, EPS, 1 - EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))

def logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))

# ----------------------------------------------------------------------------
# Reuse the v1 joined table; restrict to the market track + the 23 ranked forecasters
# ----------------------------------------------------------------------------
j = pd.read_csv(os.path.join(OUT, "joined_rows.csv"))
m = j[j.track == "market"].copy()
m["forecast"] = m["forecast"].clip(0, 1)
# market resolution_date is None -> the (forecaster,question) key is (fid,id)
m["qid"] = m["id"]
# log-score edge per row (reference - forecaster)
m["s_ref_log"] = logscore_loss(m.p_ref.values, m.y.values)
m["s_f_log"]   = logscore_loss(m.forecast.values, m.y.values)
m["d_log"]     = m["s_ref_log"] - m["s_f_log"]

counts = m.groupby("fid").size()
ranked = sorted(counts[counts >= MIN_N].index.tolist())
assert len(ranked) == 23, f"expected 23 ranked forecasters, got {len(ranked)}"
mr = m[m.fid.isin(ranked)].copy()
print(f"market rows total={len(m)}  ranked forecasters(N>=20)={len(ranked)}  "
      f"ranked rows={len(mr)}")

# Per-forecaster base aggregates (Brier track) -- the v1 anchor
base = []
for fid, g in mr.groupby("fid"):
    base.append({
        "forecaster": fid,
        "N": len(g),
        "mean_brier": g.s_f.mean(),
        "mean_brier_ref": g.s_ref.mean(),
        "raw_edge": g.d.mean(),                 # v1 raw edge (Brier)
        "raw_edge_log": g.d_log.mean(),         # log-score edge
        "diff_proxy_absdev": (g.p_ref - 0.5).abs().mean(),  # difficulty proxy
        "diff_proxy_meanbrier": g.s_f.mean(),
    })
base = pd.DataFrame(base).set_index("forecaster").loc[ranked]
base["brier_rank"]    = base["mean_brier"].rank(ascending=True,  method="min").astype(int)
base["raw_edge_rank"] = base["raw_edge"].rank(ascending=False, method="min").astype(int)

# orientation: higher = better for spearman vs brier we compare edge vs (-brier)
def rho_vs_brier(edge_series):
    """Spearman of an edge-like score (higher=better) vs -mean_brier (higher=better)."""
    s = base.loc[edge_series.index]
    rho, p = stats.spearmanr(-s["mean_brier"].values, edge_series.values)
    tau, pt = stats.kendalltau(-s["mean_brier"].values, edge_series.values)
    return float(rho), float(p), float(tau), float(pt)

results = {}

# ============================================================================
# ISSUE 1(a): COMMON-CORE reorder
# ============================================================================
# count, per question, how many of the 23 ranked forecasters answered it
q_by_f = mr.groupby("qid")["fid"].nunique()
n_all = len(ranked)
core_all = q_by_f[q_by_f == n_all].index.tolist()
# threshold: prefer ALL-23; if that core is too small (<8 questions), fall back to >=18
THRESH = 18
core_thr = q_by_f[q_by_f >= THRESH].index.tolist()
if len(core_all) >= 8:
    core_q = core_all; core_def = n_all; core_label = "all-23"
else:
    core_q = core_thr; core_def = THRESH; core_label = f">= {THRESH}"

core = mr[mr.qid.isin(core_q)].copy()
# forecasters that actually answered EVERY core question (so the per-forecaster mean
# is over an identical question set)
fa = core.groupby("fid")["qid"].nunique()
core_fids = fa[fa == len(core_q)].index.tolist()
core = core[core.fid.isin(core_fids)].copy()

core_rows = []
for fid, g in core.groupby("fid"):
    core_rows.append({"forecaster": fid,
                      "core_edge": g.d.mean(),
                      "core_brier": g.s_f.mean()})
core_df = pd.DataFrame(core_rows).set_index("forecaster")
if len(core_df) >= 3:
    rho_c, pc = stats.spearmanr(-core_df["core_brier"].values, core_df["core_edge"].values)
    tau_c, ptc = stats.kendalltau(-core_df["core_brier"].values, core_df["core_edge"].values)
else:
    rho_c = pc = tau_c = ptc = float("nan")
# DEGENERACY DIAGNOSTIC: on a tiny shared core, every forecaster's edge =
# (shared mean s_ref) - (own mean s_f). If forecasters cluster near the same s_f on
# these few questions, edge ~ -s_f exactly -> rho(edge vs -brier-on-core)=1.0 by
# construction, NOT corroboration. Measure how collinear core_edge is with -core_brier.
if len(core_df) >= 3:
    collinear_r = float(np.corrcoef(core_df["core_edge"].values,
                                    -core_df["core_brier"].values)[0, 1])
else:
    collinear_r = float("nan")
core_degenerate = (len(core_q) < 10) or (abs(collinear_r) > 0.999)

results["common_core"] = {
    "definition": core_label,
    "core_threshold_forecasters": int(core_def),
    "n_core_questions": int(len(core_q)),
    "n_core_forecasters": int(len(core_df)),
    "n_questions_answered_by_all_23": int((q_by_f == n_all).sum()),
    "spearman_rho": float(rho_c), "spearman_p": float(pc),
    "kendall_tau": float(tau_c), "kendall_p": float(ptc),
    "core_edge_vs_neg_core_brier_corr": collinear_r,
    "DEGENERATE": bool(core_degenerate),
    "note": ("Market track is too sparse for a real common core: ZERO questions are "
             "answered by all 23 ranked forecasters; the >=18 core has only 6 questions. "
             "On so few shared questions the per-forecaster edge is nearly collinear with "
             "-Brier (corr ~ {:.3f}), so rho=1.0 is a small-N artifact, not independent "
             "corroboration. Reported but NOT load-bearing.".format(collinear_r)),
}
print(f"[1a] common-core ({core_label}): {len(core_q)} q x {len(core_df)} forecasters, "
      f"rho={rho_c:.3f} (p={pc:.3f})  [DEGENERATE={core_degenerate}, "
      f"collinear r={collinear_r:.3f}]")

# Secondary wider core (>=15 forecasters, 15 questions) to show (in)stability.
sec_thr = 15
sec_q = q_by_f[q_by_f >= sec_thr].index.tolist()
sec = mr[mr.qid.isin(sec_q)].copy()
sec_fa = sec.groupby("fid")["qid"].nunique()
sec_fids = sec_fa[sec_fa == len(sec_q)].index.tolist()
sec = sec[sec.fid.isin(sec_fids)]
sec_rows = [{"forecaster": fid, "e": g.d.mean(), "b": g.s_f.mean()}
            for fid, g in sec.groupby("fid")]
sec_df = pd.DataFrame(sec_rows)
if len(sec_df) >= 3:
    rho_s, ps = stats.spearmanr(-sec_df["b"].values, sec_df["e"].values)
else:
    rho_s = ps = float("nan")
results["common_core"]["secondary_wider_core"] = {
    "threshold_forecasters": sec_thr, "n_questions": int(len(sec_q)),
    "n_forecasters": int(len(sec_df)), "spearman_rho": float(rho_s), "p": float(ps),
}
print(f"[1a] secondary core (>= {sec_thr}f): {len(sec_q)} q x {len(sec_df)} forecasters, "
      f"rho={rho_s:.3f} (p={ps:.3f})")

# ============================================================================
# ISSUE 1(b): MIXED-EFFECTS / two-way-FE difficulty-adjusted forecaster effect alpha_f
# ============================================================================
# Model: d_if = mu + alpha_f + gamma_i + eps  (per-question edge)
# Primary: OLS with forecaster + question fixed effects (two-way), alpha_f extracted
#          relative to grand mean. Secondary: MixedLM with question as random effect.
dd = mr[["fid", "qid", "d"]].copy()
dd["fid"] = dd["fid"].astype("category")
dd["qid"] = dd["qid"].astype("category")

# --- two-way OLS FE (forecaster fixed, question fixed), sum-to-zero forecaster effects
X_f = pd.get_dummies(dd["fid"], prefix="f")
X_q = pd.get_dummies(dd["qid"], prefix="q", drop_first=True)
Xfe = pd.concat([X_f, X_q], axis=1).astype(float)
# drop intercept; forecaster dummies span the forecaster space (no global const) so
# each forecaster coef = its difficulty-adjusted mean edge given question FE.
ols = sm.OLS(dd["d"].values, Xfe).fit()
alpha_raw = {c[2:]: ols.params[c] for c in X_f.columns}  # f<fid> -> coef
# center to mean zero across forecasters for interpretability as a *relative* effect
alpha_mean = np.mean(list(alpha_raw.values()))
alpha_f = {k: v for k, v in alpha_raw.items()}  # absolute difficulty-adj edge
base["alpha_f"] = pd.Series(alpha_f).loc[base.index]
base["alpha_rank"] = base["alpha_f"].rank(ascending=False, method="min").astype(int)

# alpha_f rank vs Brier rank
rho_a, pa = stats.spearmanr(-base["mean_brier"].values, base["alpha_f"].values)
tau_a, pta = stats.kendalltau(-base["mean_brier"].values, base["alpha_f"].values)
# alpha_f rank vs v1 RAW-edge rank
rho_av1, pav1 = stats.spearmanr(base["raw_edge"].values, base["alpha_f"].values)

# --- MixedLM cross-check: question as random effect, forecaster fixed effects
mixed_ok = False
try:
    md = smf.mixedlm("d ~ C(fid)", dd, groups=dd["qid"])
    mf = md.fit(reml=False, method="lbfgs", maxiter=200)
    # forecaster fixed effects (relative to reference level); rank them
    fe = {}
    ref_level = dd["fid"].cat.categories[0]
    fe[ref_level] = 0.0
    for k, v in mf.fparams.items() if hasattr(mf, "fparams") else []:
        pass
    # extract from params by name
    params = mf.params
    for name, val in params.items():
        if name.startswith("C(fid)[T."):
            lev = name[len("C(fid)[T."):-1]
            fe[lev] = val
    mix_alpha = pd.Series(fe).reindex(base.index)
    if mix_alpha.notna().sum() >= len(base) - 1:
        rho_mix, _ = stats.spearmanr(-base["mean_brier"].values, mix_alpha.fillna(0).values)
        rho_mix_vs_ols, _ = stats.spearmanr(base["alpha_f"].values, mix_alpha.fillna(0).values)
        mixed_ok = True
except Exception as e:
    rho_mix = rho_mix_vs_ols = float("nan")
    mixed_err = str(e)

results["mixed_effects"] = {
    "method": "two-way OLS FE (forecaster + question dummies); alpha_f = forecaster coef "
              "= difficulty-adjusted mean edge",
    "alpha_f_rank_vs_brier_rank_spearman": float(rho_a), "p": float(pa),
    "alpha_f_rank_vs_brier_rank_kendall": float(tau_a), "kendall_p": float(pta),
    "alpha_f_vs_v1_raw_edge_spearman": float(rho_av1), "v1_raw_edge_p": float(pav1),
    "mixedlm_crosscheck_available": bool(mixed_ok),
    "mixedlm_alpha_vs_brier_spearman": float(rho_mix) if mixed_ok else None,
    "mixedlm_alpha_vs_ols_alpha_spearman": float(rho_mix_vs_ols) if mixed_ok else None,
    "n_obs": int(len(dd)), "n_forecasters": int(len(ranked)),
    "n_questions": int(dd["qid"].nunique()),
}
print(f"[1b] alpha_f-rank vs Brier-rank rho={rho_a:.3f} (p={pa:.3f}); "
      f"alpha_f vs v1 raw-edge rho={rho_av1:.3f}; "
      f"mixedLM cross-check rho={rho_mix if mixed_ok else float('nan'):.3f}")

# ============================================================================
# ISSUE 1(c): difficulty-covariate robustness
# ============================================================================
# regress per-forecaster RAW edge on difficulty proxies
def reg_r2(yv, xv):
    X = sm.add_constant(xv)
    r = sm.OLS(yv, X).fit()
    return float(r.rsquared), float(r.params[1]), float(r.pvalues[1]), float(np.corrcoef(xv, yv)[0, 1])

r2_absdev, b_absdev, p_absdev, c_absdev = reg_r2(base["raw_edge"].values, base["diff_proxy_absdev"].values)
r2_mb, b_mb, p_mb, c_mb = reg_r2(base["raw_edge"].values, base["diff_proxy_meanbrier"].values)
results["difficulty_covariate"] = {
    "edge_on_mean_absdev_pref": {"r2": r2_absdev, "slope": b_absdev, "p": p_absdev, "corr": c_absdev},
    "edge_on_mean_brier": {"r2": r2_mb, "slope": b_mb, "p": p_mb, "corr": c_mb},
    "note": ("High R^2 on the difficulty proxy would mean the edge ranking is largely a "
             "difficulty proxy. Low R^2 = edge carries forecaster-specific signal."),
}
print(f"[1c] edge~|p_ref-.5|: R2={r2_absdev:.3f} (corr={c_absdev:.2f}); "
      f"edge~mean_brier: R2={r2_mb:.3f} (corr={c_mb:.2f})")

# ============================================================================
# ISSUE 2: CI-straddle disclosure  (bootstrap 95% edge CIs)
# ============================================================================
def boot_ci(vals, B=B_BOOT, seed=None):
    rng = np.random.default_rng(seed)
    vals = np.asarray(vals, float)
    n = len(vals)
    idx = rng.integers(0, n, size=(B, n))
    boots = vals[idx].mean(axis=1)
    return float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))

ci_lo, ci_hi, straddle = {}, {}, {}
for fid in ranked:
    v = mr.loc[mr.fid == fid, "d"].values
    lo, hi = boot_ci(v, seed=seed_of(fid))
    ci_lo[fid] = lo; ci_hi[fid] = hi
    straddle[fid] = (lo <= 0 <= hi)
base["edge_ci_low"] = pd.Series(ci_lo).loc[base.index]
base["edge_ci_high"] = pd.Series(ci_hi).loc[base.index]
base["ci_straddles_zero"] = pd.Series(straddle).loc[base.index]

n_straddle = int(base["ci_straddles_zero"].sum())
n_pos = int(((base["edge_ci_low"] > 0)).sum())
n_neg = int(((base["edge_ci_high"] < 0)).sum())
results["ci_straddle"] = {
    "n_forecasters": len(ranked),
    "n_straddle_zero": n_straddle,
    "n_strictly_positive": n_pos,
    "n_strictly_negative": n_neg,
    "reviewer_estimate": {"straddle": 16, "strictly_positive": 7},
}
print(f"[2] CI straddle: {n_straddle} straddle, {n_pos} strictly +ve, {n_neg} strictly -ve")

# ============================================================================
# ISSUE 3: RANK-STABILITY BOOTSTRAP (resample questions w/ replacement)
# ============================================================================
# Pivot to a forecaster x question matrix of d (NaN where unanswered); resample
# QUESTIONS (columns) with replacement, recompute each forecaster's mean edge over
# its answered (resampled) questions, rerank, and record.
piv = mr.pivot_table(index="fid", columns="qid", values="d", aggfunc="mean")
piv = piv.loc[ranked]
qids = piv.columns.to_numpy()
Dmat = piv.to_numpy()  # (23, Q) with NaN
brier_rank_vec = base.loc[piv.index, "brier_rank"].to_numpy()

B3 = B_BOOT
rho_draws = np.full(B3, np.nan)
rank_draws = np.full((B3, len(ranked)), np.nan)
rng3 = np.random.default_rng(424242)
Qn = Dmat.shape[1]
for b in range(B3):
    cols = rng3.integers(0, Qn, size=Qn)
    sub = Dmat[:, cols]
    edge_b = np.nanmean(sub, axis=1)
    # if a forecaster has all-NaN in this draw (no answered questions sampled), keep NaN
    valid = ~np.isnan(edge_b)
    if valid.sum() < 3:
        continue
    # edge rank (1 = best/highest edge) among valid; rank vs brier on valid set
    er = stats.rankdata(-edge_b[valid], method="average")
    rho_draws[b], _ = stats.spearmanr(-base.loc[piv.index[valid], "mean_brier"].values,
                                       edge_b[valid])
    # full edge rank vector (1=best); rank only valid, NaN otherwise
    full_rank = np.full(len(ranked), np.nan)
    # rank across ALL valid forecasters
    full_rank[valid] = stats.rankdata(-edge_b[valid], method="min")
    rank_draws[b, :] = full_rank

rho_draws = rho_draws[~np.isnan(rho_draws)]
rho_mean = float(np.mean(rho_draws))
rho_ci = (float(np.percentile(rho_draws, 2.5)), float(np.percentile(rho_draws, 97.5)))

# per-forecaster rank distribution
rank_summary = {}
for i, fid in enumerate(piv.index):
    col = rank_draws[:, i]
    col = col[~np.isnan(col)]
    rank_summary[fid] = {
        "median_rank": float(np.median(col)),
        "rank_p05": float(np.percentile(col, 5)),
        "rank_p95": float(np.percentile(col, 95)),
        "v1_edge_rank": int(base.loc[fid, "raw_edge_rank"]),
        "brier_rank": int(base.loc[fid, "brier_rank"]),
    }
results["rank_stability"] = {
    "B": B3,
    "spearman_rho_edge_vs_brier": {"mean": rho_mean, "ci95": list(rho_ci),
                                   "v1_point": 0.3577075098814229},
    "per_forecaster_rank_interval": rank_summary,
}
print(f"[3] bootstrap rho(edge-rank vs Brier-rank): mean={rho_mean:.3f} "
      f"CI95=[{rho_ci[0]:.3f},{rho_ci[1]:.3f}]")

# ============================================================================
# ISSUE 4: CLUSTER-ROBUST ENCOMPASSING (cluster on question id)
# ============================================================================
def encompass_clustered(sub):
    sub = sub.dropna(subset=["p_ref", "forecast", "y"]).copy()
    lref = logit(sub.p_ref.values)
    X = pd.DataFrame({"const": 1.0,
                      "logit_ref": lref,
                      "logit_fc": logit(sub.forecast.values)})
    yv = sub.y.values.astype(float)
    groups = sub.qid.values
    out = {}
    # naive (iid) SEs
    m_iid = sm.GLM(yv, X, family=sm.families.Binomial()).fit()
    # cluster-robust SEs on question id
    m_cl = sm.GLM(yv, X, family=sm.families.Binomial()).fit(
        cov_type="cluster", cov_kwds={"groups": groups})
    for term in ["logit_ref", "logit_fc"]:
        out[term] = {
            "coef": float(m_cl.params[term]),
            "se_iid": float(m_iid.bse[term]),
            "p_iid": float(m_iid.pvalues[term]),
            "se_cluster": float(m_cl.bse[term]),
            "p_cluster": float(m_cl.pvalues[term]),
        }
    out["b0"] = float(m_cl.params["const"])
    out["n"] = int(len(sub))
    out["n_clusters"] = int(pd.Series(groups).nunique())
    return out

enc_supers = encompass_clustered(mr)  # pooled supers (all 23 ranked), market
enc_all = encompass_clustered(m)      # pooled ALL market forecasters (540)
results["encompassing_clustered"] = {
    "pooled_supers_market": enc_supers,
    "pooled_all_market": enc_all,
}
print(f"[4] clustered encompassing (supers): "
      f"b_fc={enc_supers['logit_fc']['coef']:.3f} "
      f"p_iid={enc_supers['logit_fc']['p_iid']:.1e} -> p_cluster={enc_supers['logit_fc']['p_cluster']:.1e}; "
      f"b_ref={enc_supers['logit_ref']['coef']:.3f} p_cluster={enc_supers['logit_ref']['p_cluster']:.1e}")

# write encompassing_v2.csv
enc_rows = []
for label, e in [("pooled_supers_market", enc_supers), ("pooled_all_market", enc_all)]:
    enc_rows.append({
        "model": label, "n": e["n"], "n_clusters": e["n_clusters"], "b0": e["b0"],
        "b_ref": e["logit_ref"]["coef"], "se_ref_iid": e["logit_ref"]["se_iid"],
        "p_ref_iid": e["logit_ref"]["p_iid"], "se_ref_cluster": e["logit_ref"]["se_cluster"],
        "p_ref_cluster": e["logit_ref"]["p_cluster"],
        "b_fc": e["logit_fc"]["coef"], "se_fc_iid": e["logit_fc"]["se_iid"],
        "p_fc_iid": e["logit_fc"]["p_iid"], "se_fc_cluster": e["logit_fc"]["se_cluster"],
        "p_fc_cluster": e["logit_fc"]["p_cluster"],
    })
pd.DataFrame(enc_rows).to_csv(os.path.join(OUT, "encompassing_v2.csv"), index=False)

# ============================================================================
# ISSUE 5: FDR-CONTROLLED per-forecaster edge tests (Diebold-Mariano HLN)
# ============================================================================
def dm_hln_pvalue(d):
    """One-sided DM test H0: mean(d)=0 vs >0, with Harvey-Leybourne-Newbold small-
    sample correction. h=1 (one-step). Returns (stat, p_onesided_positive)."""
    d = np.asarray(d, float)
    n = len(d)
    dbar = d.mean()
    s2 = d.var(ddof=1)
    if s2 <= 0 or n < 2:
        return (np.nan, np.nan)
    dm = dbar / math.sqrt(s2 / n)
    h = 1
    corr = math.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    dm_star = dm * corr
    # t with n-1 df, one-sided (positive edge)
    p_one = stats.t.sf(dm_star, df=n - 1)
    return (float(dm_star), float(p_one))

dm_stats, dm_p = {}, {}
for fid in ranked:
    v = mr.loc[mr.fid == fid, "d"].values
    stat, p = dm_hln_pvalue(v)
    dm_stats[fid] = stat; dm_p[fid] = p
pvals = pd.Series(dm_p).loc[ranked]
# Benjamini-Hochberg at q=0.10
q = 0.10
order = np.argsort(pvals.values)
sorted_p = pvals.values[order]
mtests = len(sorted_p)
thresh = (np.arange(1, mtests + 1) / mtests) * q
below = sorted_p <= thresh
if below.any():
    kmax = np.max(np.where(below)[0])
    bh_cut = sorted_p[kmax]
else:
    bh_cut = -1.0
base["dm_stat"] = pd.Series(dm_stats).loc[base.index]
base["dm_p_onesided"] = pvals.loc[base.index]
base["fdr_significant"] = base["dm_p_onesided"] <= bh_cut
n_fdr = int(base["fdr_significant"].sum())
results["fdr_edge_tests"] = {
    "test": "Diebold-Mariano (HLN small-sample corrected), one-sided H1: edge>0",
    "q": q, "bh_pvalue_cutoff": float(bh_cut),
    "n_significant_positive": n_fdr,
    "raw_p_below_0.05": int((pvals <= 0.05).sum()),
    "significant_forecasters": base.index[base["fdr_significant"]].tolist(),
}
print(f"[5] FDR (BH q=0.10): {n_fdr}/23 forecasters significant positive edge "
      f"(raw p<.05: {(pvals<=0.05).sum()}); BH cutoff p={bh_cut:.4f}")

# ============================================================================
# ISSUE 6: LOG-SCORE robustness of the reorder
# ============================================================================
base["log_edge_rank"] = base["raw_edge_log"].rank(ascending=False, method="min").astype(int)
# Brier ranking under log score: rank by mean log-loss (lower=better)
mean_logloss = mr.groupby("fid")["s_f_log"].mean().loc[base.index]
base["mean_logloss"] = mean_logloss
# reorder: log-edge vs log-loss ranking (both forecaster-self metrics, log-score world)
rho_log, p_log = stats.spearmanr(-base["mean_logloss"].values, base["raw_edge_log"].values)
tau_log, pt_log = stats.kendalltau(-base["mean_logloss"].values, base["raw_edge_log"].values)
# also: log-edge ranking vs the BRIER-based Brier ranking (does headline reorder hold?)
rho_log_vs_brier, p_lvb = stats.spearmanr(-base["mean_brier"].values, base["raw_edge_log"].values)
results["log_score_reorder"] = {
    "log_edge_vs_log_loss_spearman": float(rho_log), "p": float(p_log),
    "log_edge_vs_log_loss_kendall": float(tau_log), "kendall_p": float(pt_log),
    "log_edge_vs_brier_rank_spearman": float(rho_log_vs_brier), "p_vs_brier": float(p_lvb),
    "v1_brier_reorder_rho": 0.3577075098814229,
}
print(f"[6] log-score reorder rho(log-edge vs log-loss)={rho_log:.3f} (p={p_log:.3f}); "
      f"log-edge vs Brier-rank rho={rho_log_vs_brier:.3f}")

# ============================================================================
# ISSUE 7: RECALIBRATION NOISE FLOOR (synthetic perfectly-calibrated forecasters)
# ============================================================================
def oos_isotonic_shrink(forecasts, y, p_ref, k=5, seed=0):
    """Return (edge_raw, edge_recal) for one forecaster's arrays."""
    rng = np.random.default_rng(seed)
    n = len(forecasts)
    if n < 10 or len(np.unique(y)) < 2:
        return (np.nan, np.nan)
    order = rng.permutation(n)
    folds = np.array_split(order, k)
    p_recal = np.full(n, np.nan)
    for i in range(k):
        test = folds[i]
        train = np.concatenate([folds[jj] for jj in range(k) if jj != i])
        if len(np.unique(y[train])) < 2:
            p_recal[test] = forecasts[test]
            continue
        ir = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
        ir.fit(forecasts[train], y[train])
        p_recal[test] = ir.predict(forecasts[test])
    d_raw = (brier(p_ref, y) - brier(forecasts, y)).mean()
    d_recal = (brier(p_ref, y) - brier(p_recal, y)).mean()
    return (d_raw, d_recal)

# observed shrink: use the SAME min_n=25 set as v1 for comparability
MIN_RECAL = 25
obs_rows = []
synth_shrinks = []
N_SYNTH = 200  # synthetic replications per forecaster
rng7 = np.random.default_rng(7)
for fid in ranked:
    g = mr[mr.fid == fid]
    if len(g) < MIN_RECAL:
        continue
    fcast = g.forecast.values.astype(float)
    yv = g.y.values.astype(float)
    pref = g.p_ref.values.astype(float)
    er, ec = oos_isotonic_shrink(fcast, yv, pref, seed=seed_of(fid))
    if np.isnan(er):
        continue
    obs_rows.append({"forecaster": fid, "N": len(g), "edge_raw": er, "edge_recal": ec,
                     "shrink": er - ec})
    # synthetic PERFECTLY-CALIBRATED: keep the same forecast p-distribution and N,
    # but draw y ~ Bernoulli(p_forecast). Then the forecasts ARE perfectly calibrated,
    # so any isotonic OOS "improvement" is pure estimator noise.
    per_f_synth = []
    for s in range(N_SYNTH):
        y_syn = (rng7.random(len(fcast)) < fcast).astype(float)
        if len(np.unique(y_syn)) < 2:
            continue
        er2, ec2 = oos_isotonic_shrink(fcast, y_syn, pref, seed=rng7.integers(1, 2**31))
        if not np.isnan(er2):
            per_f_synth.append(er2 - ec2)
    if per_f_synth:
        synth_shrinks.append(np.mean(per_f_synth))

obs_df = pd.DataFrame(obs_rows)
obs_mean_shrink = float(obs_df["shrink"].mean())
obs_mean_raw = float(obs_df["edge_raw"].mean())
obs_mean_recal = float(obs_df["edge_recal"].mean())
synth_mean_shrink = float(np.mean(synth_shrinks)) if synth_shrinks else float("nan")
synth_sd_shrink = float(np.std(synth_shrinks)) if synth_shrinks else float("nan")
results["recalibration_noise_floor"] = {
    "n_forecasters": int(len(obs_df)),
    "min_n": MIN_RECAL,
    "observed_mean_edge_raw": obs_mean_raw,
    "observed_mean_edge_recal": obs_mean_recal,
    "observed_mean_shrink": obs_mean_shrink,
    "synthetic_mean_shrink": synth_mean_shrink,
    "synthetic_sd_shrink": synth_sd_shrink,
    "n_synth_per_forecaster": N_SYNTH,
    "interpretation": ("If synthetic shrink ~ observed shrink, the isotonic recalibration "
                       "drop is estimator noise at this N, not real miscalibration."),
    "shrink_ratio_obs_over_synth": (obs_mean_shrink / synth_mean_shrink
                                    if synth_mean_shrink not in (0.0,) and not math.isnan(synth_mean_shrink)
                                    else float("nan")),
}
print(f"[7] recalibration: observed shrink={obs_mean_shrink:.4f} "
      f"(raw {obs_mean_raw:.4f} -> recal {obs_mean_recal:.4f}); "
      f"synthetic noise-floor shrink={synth_mean_shrink:.4f} (sd {synth_sd_shrink:.4f})")

# ============================================================================
# ISSUE 8: DIFFERENTIAL DROPOUT CHECK (market track)
# ============================================================================
# Rebuild the market-track forecast rows BEFORE the resolution join, from the raw
# human files, to see which questions were dropped as unresolved. We reuse q.json
# for p_ref / freeze value and r.json for resolution status.
qset = json.load(open(os.path.join(ROOT, "data", "q.json")))["questions"]
rset = json.load(open(os.path.join(ROOT, "data", "r.json")))["resolutions"]
MARKET = {"manifold", "metaculus", "polymarket", "infer"}
Q = {q["id"]: q for q in qset if isinstance(q["id"], str)}
resolved_ids = set()
for r in rset:
    if isinstance(r["id"], str) and r.get("resolved") is True and r.get("resolved_to") is not None:
        resolved_ids.add(r["id"])

def load_raw(path, tag):
    d = json.load(open(path))
    out = []
    for f in d["forecasts"]:
        out.append({"tag": tag, "user_id": f.get("user_id"), "id": f["id"],
                    "source": f["source"], "forecast": f.get("forecast")})
    return out
# Full raw files live at the top-level forecast_sets/ (the data/ copies are git-LFS
# pointer stubs); this is the same FCDIR compute_edge.py reads from.
FCDIR = os.path.join(ROOT, "forecast_sets", "2024-07-21")
raw = load_raw(os.path.join(FCDIR, "human_super.json"), "super")
raw += load_raw(os.path.join(FCDIR, "human_public.json"), "public")
rawdf = pd.DataFrame(raw)
rawm = rawdf[rawdf.source.isin(MARKET)].copy()
rawm["fid"] = rawm.tag + ":" + rawm.user_id.astype(str)
rawm["resolved"] = rawm.id.isin(resolved_ids)
# difficulty proxy at QUESTION level: |freeze_value - 0.5|
def freeze_val(qid):
    q = Q.get(qid)
    if q is None: return np.nan
    try: return float(q["freeze_datetime_value"])
    except (ValueError, TypeError): return np.nan
rawm["pref"] = rawm.id.map(freeze_val)
rawm["absdev"] = (rawm.pref - 0.5).abs()

# (i) question-level: resolved vs unresolved difficulty proxy
q_level = rawm.drop_duplicates("id")[["id", "resolved", "absdev"]]
res_q = q_level[q_level.resolved]
unres_q = q_level[~q_level.resolved]
absdev_res = float(res_q.absdev.mean())
absdev_unres = float(unres_q.absdev.mean())
# Mann-Whitney on difficulty
try:
    mw_u, mw_p = stats.mannwhitneyu(res_q.absdev.dropna(), unres_q.absdev.dropna(),
                                    alternative="two-sided")
    mw_p = float(mw_p)
except Exception:
    mw_p = float("nan")
# (ii) per-forecaster resolved fraction (among the 23 ranked) -- spread
ranked_set = set(ranked)
rf = rawm[rawm.fid.isin(ranked_set)].groupby("fid")["resolved"].mean()
results["dropout_check"] = {
    "market_track": True,
    "n_market_forecast_rows_raw": int(len(rawm)),
    "n_resolved_rows": int(rawm.resolved.sum()),
    "n_unresolved_rows": int((~rawm.resolved).sum()),
    "n_market_questions": int(q_level.shape[0]),
    "n_resolved_questions": int(res_q.shape[0]),
    "n_unresolved_questions": int(unres_q.shape[0]),
    "mean_absdev_resolved_q": absdev_res,
    "mean_absdev_unresolved_q": absdev_unres,
    "mannwhitney_p_difficulty": mw_p,
    "ranked_resolved_fraction_min": float(rf.min()),
    "ranked_resolved_fraction_max": float(rf.max()),
    "ranked_resolved_fraction_mean": float(rf.mean()),
    "ranked_resolved_fraction_sd": float(rf.std()),
    "note": ("absdev = |freeze_value - 0.5| (higher = 'easier'/more confident market). "
             "If resolved questions are systematically easier/harder, dropout is "
             "differential on difficulty."),
}
print(f"[8] dropout: resolved-q absdev={absdev_res:.3f} vs unresolved-q absdev={absdev_unres:.3f} "
      f"(MW p={mw_p:.3f}); ranked resolved-frac spread "
      f"[{rf.min():.2f},{rf.max():.2f}] mean {rf.mean():.2f}")

# ============================================================================
# WRITE OUTPUTS
# ============================================================================
# leaderboard_edge_v2.csv
lb_cols = ["N", "mean_brier", "raw_edge", "alpha_f", "edge_ci_low", "edge_ci_high",
           "ci_straddles_zero", "brier_rank", "raw_edge_rank", "alpha_rank",
           "fdr_significant", "dm_p_onesided"]
lb_v2 = base.reset_index()[["forecaster"] + lb_cols]
lb_v2 = lb_v2.sort_values("raw_edge", ascending=False)
lb_v2.to_csv(os.path.join(OUT, "leaderboard_edge_v2.csv"), index=False)

# reorder_v2.json -- all corrected scalars
with open(os.path.join(OUT, "reorder_v2.json"), "w") as f:
    json.dump(results, f, indent=2, default=str)

print("\nFiles written:")
for fn in ["revise_edge.py", "reorder_v2.json", "leaderboard_edge_v2.csv", "encompassing_v2.csv"]:
    print(f"  {os.path.join(OUT, fn)}")
print("Done.")
