#!/usr/bin/env python3
"""
Beyond Brier -- REVISION v3 (second-round peer-review corrections).

Adds the four analyses the methodology/EIC panel asked for, reusing the SAME joined
market-track table (out/joined_rows.csv; 3,670 market rows; 23 superforecasters N>=20).
Additive: writes *_v3 outputs, overwrites nothing.

Round-2 issues addressed:
  T3.1  Two-way-FE IDENTIFICATION: (a) connectivity of the forecaster x question
        incidence graph (is alpha_f comparable across a single connected component?);
        (b) leave-one-question-out re-estimate of the alpha_f ranking (does any single
        question drive the reorder?).
  T3.2  Small-cluster inference on the encompassing regression (56 clusters is in the
        danger zone): (a) wild cluster bootstrap-t (Cameron-Gelbach-Miller, Rademacher,
        null imposed) on a linear-probability encompassing model; (b) pairs cluster
        bootstrap of the logit coefficients. Both as a check on the CR p=0.005.
  T3.3  Differential-dropout SENSITIVITY: reweight resolved questions toward the
        (harder) unresolved difficulty distribution and re-estimate the reorder, to
        bound how far the headline rho could move under the disclosed selection.
  T3.4  Per-forecaster RESULTS TABLE (alpha_f, ranks, bootstrap CI, FDR flag) as a
        LaTeX-ready CSV + tabular snippet.

Honest by construction: if a check weakens the claim, the number is reported as-is.
"""
import os, json, math, warnings, hashlib
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm

ROOT = "/Users/emizemani/Desktop/predictthefuture/paper_beyond_brier"
OUT = os.path.join(ROOT, "out")
EPS = 1e-3
MIN_N = 20
B_WILD = 9999      # wild cluster bootstrap reps
B_PAIRS = 4999     # pairs cluster bootstrap reps

def seed_of(s):
    return int(hashlib.md5(str(s).encode()).hexdigest()[:8], 16)

def logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))

# ---- reuse the v1 joined table; market track + 23 ranked forecasters ----
j = pd.read_csv(os.path.join(OUT, "joined_rows.csv"))
m = j[j.track == "market"].copy()
m["forecast"] = m["forecast"].clip(0, 1)
m["qid"] = m["id"]
counts = m.groupby("fid").size()
ranked = sorted(counts[counts >= MIN_N].index.tolist())
assert len(ranked) == 23, f"expected 23 ranked, got {len(ranked)}"
mr = m[m.fid.isin(ranked)].copy()
print(f"market ranked rows={len(mr)}  forecasters={len(ranked)}  questions={mr.qid.nunique()}")

# per-forecaster Brier anchor (same as v1/v2)
base = mr.groupby("fid").agg(N=("d", "size"), mean_brier=("s_f", "mean"),
                             raw_edge=("d", "mean")).loc[ranked]
base["brier_rank"] = base["mean_brier"].rank(ascending=True, method="min").astype(int)
results = {}

# ============================================================================
# T3.1  Two-way-FE identification: connectivity + leave-one-question-out
# ============================================================================
def two_way_fe_alpha(df):
    """Return Series alpha_f (difficulty-adjusted mean edge) from d ~ forecaster FE +
    question FE, indexed by fid. Forecaster dummies span the space (no intercept)."""
    dd = df[["fid", "qid", "d"]].copy()
    Xf = pd.get_dummies(dd["fid"], prefix="f")
    Xq = pd.get_dummies(dd["qid"], prefix="q", drop_first=True)
    X = pd.concat([Xf, Xq], axis=1).astype(float)
    res = sm.OLS(dd["d"].values, X).fit()
    return pd.Series({c[2:]: res.params[c] for c in Xf.columns})

# --- (a) connectivity of the forecaster x question incidence graph ---
# union-find over forecasters; link two forecasters if they share >=1 question.
adj = {f: set() for f in ranked}
by_q = mr.groupby("qid")["fid"].apply(lambda s: sorted(set(s)))
pair_shared = {}  # (f1,f2) -> # shared questions
for qid, fs in by_q.items():
    for a in range(len(fs)):
        for b in range(a + 1, len(fs)):
            f1, f2 = fs[a], fs[b]
            adj[f1].add(f2); adj[f2].add(f1)
            key = (f1, f2)
            pair_shared[key] = pair_shared.get(key, 0) + 1
# connected components via BFS
seen, comps = set(), []
for f in ranked:
    if f in seen:
        continue
    stack, comp = [f], []
    while stack:
        u = stack.pop()
        if u in seen:
            continue
        seen.add(u); comp.append(u)
        stack.extend(adj[u] - seen)
    comps.append(comp)
comp_sizes = sorted((len(c) for c in comps), reverse=True)
shared_counts = np.array(list(pair_shared.values()))
# fraction of the 23*22/2 forecaster pairs that share at least one question
n_pairs_possible = len(ranked) * (len(ranked) - 1) // 2
results["fe_connectivity"] = {
    "n_components": len(comps),
    "component_sizes": comp_sizes,
    "single_connected_component": bool(len(comps) == 1),
    "n_forecaster_pairs_possible": int(n_pairs_possible),
    "n_forecaster_pairs_sharing_a_question": int(len(pair_shared)),
    "frac_pairs_linked": float(len(pair_shared) / n_pairs_possible),
    "shared_questions_per_linked_pair": {
        "min": int(shared_counts.min()), "median": float(np.median(shared_counts)),
        "mean": float(shared_counts.mean()), "max": int(shared_counts.max()),
    },
    "note": ("Two-way FE forecaster effects are mutually comparable only within a "
             "connected forecaster-question incidence graph (AKM connectedness). A single "
             "component => all 23 alpha_f live on one comparable scale; the median shared-"
             "question count indicates how thin each pairwise contrast is."),
}
print(f"[T3.1a] connectivity: {len(comps)} component(s), sizes {comp_sizes[:5]}; "
      f"{len(pair_shared)}/{n_pairs_possible} pairs linked "
      f"({100*len(pair_shared)/n_pairs_possible:.0f}%); shared-q/pair median="
      f"{np.median(shared_counts):.0f} [min {shared_counts.min()}, max {shared_counts.max()}]")

# --- (b) leave-one-question-out alpha_f ranking stability ---
alpha_full = two_way_fe_alpha(mr).loc[ranked]
rank_full = alpha_full.rank(ascending=False, method="min")
neg_brier = -base["mean_brier"]
rho_full, _ = stats.spearmanr(neg_brier.values, alpha_full.values)

qids_all = sorted(mr.qid.unique())
loo_rho_vs_brier, loo_rho_vs_full = [], []
for qdrop in qids_all:
    sub = mr[mr.qid != qdrop]
    # keep only forecasters still having >=2 obs (FE needs within-forecaster variation)
    keep = sub.groupby("fid").size()
    keep = keep[keep >= 2].index
    sub = sub[sub.fid.isin(keep)]
    a = two_way_fe_alpha(sub)
    common = [f for f in ranked if f in a.index]
    if len(common) < 5:
        continue
    rb, _ = stats.spearmanr(neg_brier.loc[common].values, a.loc[common].values)
    rf, _ = stats.spearmanr(alpha_full.loc[common].values, a.loc[common].values)
    loo_rho_vs_brier.append(rb); loo_rho_vs_full.append(rf)
loo_rho_vs_brier = np.array(loo_rho_vs_brier)
loo_rho_vs_full = np.array(loo_rho_vs_full)
results["fe_leave_one_question_out"] = {
    "full_sample_alpha_vs_brier_rho": float(rho_full),
    "n_questions_dropped_one_at_a_time": int(len(loo_rho_vs_brier)),
    "loo_alpha_vs_brier_rho": {
        "min": float(loo_rho_vs_brier.min()), "max": float(loo_rho_vs_brier.max()),
        "mean": float(loo_rho_vs_brier.mean()), "sd": float(loo_rho_vs_brier.std()),
    },
    "loo_alpha_ordering_vs_full_ordering_rho": {
        "min": float(loo_rho_vs_full.min()), "mean": float(loo_rho_vs_full.mean()),
    },
    "note": ("If dropping any single question moves the alpha_f-vs-Brier reorder far from "
             "the full-sample value, the reorder is driven by one high-leverage question. "
             "loo_vs_full min near 1.0 => no single question drives the alpha_f ordering."),
}
print(f"[T3.1b] LOO reorder rho vs Brier: full={rho_full:.3f}, "
      f"LOO range [{loo_rho_vs_brier.min():.3f},{loo_rho_vs_brier.max():.3f}] "
      f"mean {loo_rho_vs_brier.mean():.3f}; ordering-vs-full min "
      f"rho={loo_rho_vs_full.min():.3f}")

# ============================================================================
# T3.2  Small-cluster inference on the encompassing regression
# ============================================================================
def design(df):
    sub = df.dropna(subset=["p_ref", "forecast", "y"]).copy()
    X = pd.DataFrame({"const": 1.0,
                      "logit_ref": logit(sub.p_ref.values),
                      "logit_fc": logit(sub.forecast.values)})
    return X.reset_index(drop=True), sub.y.values.astype(float), sub.qid.values

def cluster_t_lpm(X, y, groups, term):
    """OLS (linear prob) cluster-robust t-stat for `term`."""
    res = sm.OLS(y, X.values).fit(cov_type="cluster", cov_kwds={"groups": groups})
    cols = list(X.columns)
    k = cols.index(term)
    return res.params[k] / res.bse[k], res.params[k]

def wild_cluster_bootstrap_t(X, y, groups, term, B, seed):
    """CGM wild cluster bootstrap-t with the null imposed (Rademacher weights).
    Tests H0: coef[term]=0 in a linear-probability encompassing model."""
    rng = np.random.default_rng(seed)
    cols = list(X.columns)
    Xv = X.values
    t_obs, _ = cluster_t_lpm(X, y, groups, term)
    # restricted fit with term forced to 0
    restr_cols = [c for c in cols if c != term]
    Xr = X[restr_cols].values
    res_r = sm.OLS(y, Xr).fit()
    yhat_r = res_r.predict(Xr)
    u_r = y - yhat_r
    uniq = np.unique(groups)
    gidx = {g: np.where(groups == g)[0] for g in uniq}
    count = 0
    for b in range(B):
        w = rng.choice([-1.0, 1.0], size=len(uniq))
        wvec = np.empty(len(y))
        for gi, g in enumerate(uniq):
            wvec[gidx[g]] = w[gi]
        y_star = yhat_r + u_r * wvec
        t_star, _ = cluster_t_lpm(X, y_star, groups, term)
        if abs(t_star) >= abs(t_obs):
            count += 1
    p = (count + 1) / (B + 1)
    return float(t_obs), float(p)

def pairs_cluster_bootstrap_logit(df, term, B, seed):
    """Resample question-clusters with replacement; refit the logit; bootstrap-t & CI
    for the logit coefficient on `term`."""
    rng = np.random.default_rng(seed)
    sub = df.dropna(subset=["p_ref", "forecast", "y"]).copy()
    qids = sub.qid.unique()
    by = {q: sub[sub.qid == q] for q in qids}
    # observed
    Xo, yo, go = design(sub)
    base_fit = sm.GLM(yo, Xo.values, family=sm.families.Binomial()).fit(
        cov_type="cluster", cov_kwds={"groups": go})
    k = list(Xo.columns).index(term)
    coef_obs = base_fit.params[k]
    coefs = []
    for b in range(B):
        pick = rng.choice(qids, size=len(qids), replace=True)
        parts = [by[q] for q in pick]
        bs = pd.concat(parts, ignore_index=True)
        Xb, yb, _ = design(bs)
        if len(np.unique(yb)) < 2:
            continue
        try:
            fit = sm.GLM(yb, Xb.values, family=sm.families.Binomial()).fit()
            coefs.append(fit.params[list(Xb.columns).index(term)])
        except Exception:
            continue
    coefs = np.array(coefs)
    lo, hi = np.percentile(coefs, [2.5, 97.5])
    # bootstrap-t style two-sided p: fraction of recentred draws beyond observed
    p_boot = 2 * min((coefs <= 0).mean(), (coefs >= 0).mean())
    return {"coef_obs": float(coef_obs), "boot_mean": float(coefs.mean()),
            "ci95_low": float(lo), "ci95_high": float(hi),
            "p_two_sided": float(min(1.0, p_boot)), "n_draws": int(len(coefs))}

Xs, ys, gs = design(mr)
# collinearity diagnostic (domain reviewer W2): VIF between logit_ref and logit_fc
corr_reffc = float(np.corrcoef(Xs["logit_ref"].values, Xs["logit_fc"].values)[0, 1])
vif = 1.0 / (1.0 - corr_reffc**2)
enc_small = {}
for term in ["logit_fc", "logit_ref"]:
    t_obs, p_wild = wild_cluster_bootstrap_t(Xs, ys, gs, term, B_WILD, seed_of("wild_" + term))
    pairs = pairs_cluster_bootstrap_logit(mr, term, B_PAIRS, seed_of("pairs_" + term))
    enc_small[term] = {"lpm_cluster_t": t_obs, "wild_cluster_boot_p": p_wild,
                       "pairs_cluster_boot_logit": pairs}
    print(f"[T3.2] {term}: wild-cluster-t p={p_wild:.4f} (t={t_obs:.2f}); "
          f"pairs-boot logit coef={pairs['coef_obs']:.3f} "
          f"CI95=[{pairs['ci95_low']:.3f},{pairs['ci95_high']:.3f}] p={pairs['p_two_sided']:.4f}")
results["encompassing_small_cluster"] = {
    "n_clusters": int(pd.Series(gs).nunique()),
    "corr_logit_ref_fc": corr_reffc, "vif_ref_fc": vif,
    "terms": enc_small,
    "note": ("56 clusters is in the small-cluster regime where CR p-values are "
             "anti-conservative; the wild cluster bootstrap-t (null imposed, Rademacher) "
             "and a pairs cluster bootstrap are reported as the primary small-cluster "
             "checks on the CR p=0.005 for logit_fc."),
}

# ============================================================================
# T3.3  Differential-dropout sensitivity (reweight to the harder unresolved mix)
# ============================================================================
# Build resolved (analyzed) and unresolved question difficulty (|p_ref-0.5|) from the
# raw market files; reweight resolved questions so their difficulty histogram matches
# the unresolved one, then re-estimate the reorder via weighted two-way FE (WLS).
qset = json.load(open(os.path.join(ROOT, "data", "q.json")))["questions"]
rset = json.load(open(os.path.join(ROOT, "data", "r.json")))["resolutions"]
MARKET = {"manifold", "metaculus", "polymarket", "infer"}
Q = {q["id"]: q for q in qset if isinstance(q["id"], str)}
resolved_ids = {r["id"] for r in rset
                if isinstance(r["id"], str) and r.get("resolved") is True
                and r.get("resolved_to") is not None}
def freeze_val(qid):
    q = Q.get(qid)
    try:
        return float(q["freeze_datetime_value"])
    except (ValueError, TypeError, KeyError):
        return np.nan

# difficulty of analyzed (resolved) questions actually in mr
res_q = pd.DataFrame({"qid": sorted(mr.qid.unique())})
res_q["absdev"] = res_q.qid.map(lambda q: abs(freeze_val(q) - 0.5))
# unresolved market questions (answered by humans, market source, not resolved)
all_mkt_qids = {q["id"] for q in qset
                if isinstance(q["id"], str) and q.get("source") in MARKET}
unres_qids = [q for q in all_mkt_qids if q not in resolved_ids]
unres_absdev = np.array([abs(freeze_val(q) - 0.5) for q in unres_qids])
unres_absdev = unres_absdev[~np.isnan(unres_absdev)]

# weight resolved questions to match the unresolved difficulty distribution via bins
bins = np.linspace(0, 0.5, 6)  # 5 difficulty bins
res_bin = np.clip(np.digitize(res_q.absdev.values, bins) - 1, 0, len(bins) - 2)
unres_hist, _ = np.histogram(unres_absdev, bins=bins, density=False)
res_hist, _ = np.histogram(res_q.absdev.values, bins=bins, density=False)
unres_frac = unres_hist / max(unres_hist.sum(), 1)
res_frac = res_hist / max(res_hist.sum(), 1)
bin_w = np.where(res_frac > 0, unres_frac / np.where(res_frac == 0, 1, res_frac), 0.0)
qweight = {q: bin_w[res_bin[i]] for i, q in enumerate(res_q.qid.values)}
# normalise mean weight to 1
wvals = np.array([qweight[q] for q in res_q.qid.values])
scale = len(wvals) / max(wvals.sum(), 1e-9)
qweight = {q: w * scale for q, w in qweight.items()}

# weighted two-way FE (WLS): d ~ forecaster FE + question FE, weights = question weight
dd = mr[["fid", "qid", "d"]].copy()
dd["w"] = dd.qid.map(qweight).fillna(0.0)
Xf = pd.get_dummies(dd["fid"], prefix="f")
Xq = pd.get_dummies(dd["qid"], prefix="q", drop_first=True)
Xwls = pd.concat([Xf, Xq], axis=1).astype(float)
wls = sm.WLS(dd["d"].values, Xwls, weights=dd["w"].values).fit()
alpha_w = pd.Series({c[2:]: wls.params[c] for c in Xf.columns}).loc[ranked]
rho_w, p_w = stats.spearmanr(neg_brier.values, alpha_w.values)
# also reweighted RAW edge ranking
we = mr.copy(); we["w"] = we.qid.map(qweight).fillna(0.0)
wedge = we.groupby("fid").apply(
    lambda g: np.average(g.d, weights=g.w) if g.w.sum() > 0 else np.nan).loc[ranked]
rho_we, p_we = stats.spearmanr(neg_brier.values, wedge.values)
results["dropout_sensitivity"] = {
    "n_resolved_questions": int(len(res_q)),
    "n_unresolved_questions": int(len(unres_qids)),
    "mean_absdev_resolved": float(res_q.absdev.mean()),
    "mean_absdev_unresolved": float(np.nanmean(unres_absdev)),
    "reweighted_alpha_vs_brier_rho": float(rho_w), "p": float(p_w),
    "unweighted_alpha_vs_brier_rho": float(rho_full),
    "reweighted_rawedge_vs_brier_rho": float(rho_we), "p_raw": float(p_we),
    "note": ("Resolved (analyzed) questions are easier; reweighting them to the harder "
             "unresolved difficulty mix bounds how much the reorder is an artifact of "
             "the easier analyzed subset. A reweighted rho close to the unweighted "
             "rho => the reorder is not driven by the dropout selection."),
}
print(f"[T3.3] dropout sensitivity: unweighted alpha-reorder rho={rho_full:.3f} -> "
      f"difficulty-reweighted rho={rho_w:.3f} (p={p_w:.3f}); "
      f"reweighted raw-edge rho={rho_we:.3f}")

# ============================================================================
# T3.4  Per-forecaster results table (LaTeX-ready)
# ============================================================================
v2 = pd.read_csv(os.path.join(OUT, "leaderboard_edge_v2.csv"))
v2 = v2.set_index("forecaster").loc[ranked].reset_index()
# anonymise forecaster ids -> F01..F23 by Brier rank
v2 = v2.sort_values("brier_rank")
v2["label"] = ["F%02d" % i for i in range(1, len(v2) + 1)]
tab = v2[["label", "N", "mean_brier", "brier_rank", "raw_edge", "raw_edge_rank",
          "alpha_f", "alpha_rank", "edge_ci_low", "edge_ci_high", "fdr_significant"]].copy()
tab.to_csv(os.path.join(OUT, "results_table_v3.csv"), index=False)

# LaTeX tabular
lines = [r"\begin{tabular}{lrrrrrrc}", r"\toprule",
         r"F & $N$ & Brier & rk & edge & rk & $\hat\alpha_f$ & rk\,/\,FDR\\",
         r"\midrule"]
for _, r in tab.iterrows():
    star = r"$^\ast$" if r["fdr_significant"] else ""
    lines.append("%s & %d & %.3f & %d & %+.3f & %d & %+.3f & %d%s\\\\" % (
        r["label"], int(r["N"]), r["mean_brier"], int(r["brier_rank"]),
        r["raw_edge"], int(r["raw_edge_rank"]), r["alpha_f"], int(r["alpha_rank"]), star))
lines += [r"\bottomrule", r"\end{tabular}"]
with open(os.path.join(OUT, "results_table_v3.tex"), "w") as f:
    f.write("\n".join(lines))
print(f"[T3.4] results table -> out/results_table_v3.csv + .tex "
      f"({tab.fdr_significant.sum()} FDR-significant marked)")

# ---- write all v3 scalars ----
with open(os.path.join(OUT, "reorder_v3.json"), "w") as f:
    json.dump(results, f, indent=2, default=str)
print("\nFiles written: out/reorder_v3.json, results_table_v3.csv, results_table_v3.tex")
print("Done.")
