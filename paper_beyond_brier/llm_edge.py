#!/usr/bin/env python3
"""
Beyond Brier -- LLM track on PUBLIC ForecastBench per-question model forecasts.

Source: forecastbench.org processed forecast sets, round 2024-07-21
        (fb_forecast_sets/forecastbench-processed-forecast-sets/2024-07-21/*.json).
Each model file already carries, per question row:
    source, market_value_on_due_date (= prior p_ref for market sources),
    forecast (= model p), resolved, resolved_to (= outcome y), imputed.
These were elicited at the 2024-07-21 freeze, before resolution -> LEAK-FREE by
ForecastBench's contamination-free design (same guarantee as the human track).

Three questions, matching the paper's instrument (brier/edge/encompassing):

D1  BALANCED-PANEL IDENTITY. All models answer the SAME market question set, so
    edge_f = [const over f] - Brier_f  ==>  rank-by-edge == rank-by-Brier (rho~1).
    We verify this is what the data show: the naive 'edge over market' does NOT
    reorder a balanced benchmark, and on the copy-the-market pairs it actually
    REWARDS copying (freeze lowers Brier -> raises edge).

D1b DECOMPOSITION REORDER. The priced/unpriced encompassing coefficient beta_fc
    (info the model adds beyond the price) is NOT a monotone transform of Brier.
    Rank models by beta_fc vs by Brier -> this is the ranking that genuinely
    reorders a balanced leaderboard and separates contributors from echoers.

D2  COPY-THE-MARKET (matched within-model manipulation). For each base config X
    vs X_with_freeze_values: does handing the model the prior lower |p - p_ref|
    (copying) and Brier, while NOT adding unpriced edge (beta_fc flat/down,
    beta_ref up)? This turns the paper's hedged footnote into a measured result.

Writes out_llm/*.csv + summary_llm.json. Overwrites nothing in out/.
"""
import os, json, glob, math, warnings, collections
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm

ROOT = "/Users/emizemani/Desktop/predictthefuture/paper_beyond_brier"
FCDIR = os.path.join(ROOT, "fb_forecast_sets",
                     "forecastbench-processed-forecast-sets", "2024-07-21")
OUT = os.path.join(ROOT, "out_llm")
os.makedirs(OUT, exist_ok=True)

MARKET = {"manifold", "metaculus", "polymarket", "infer"}
EPS = 1e-3
RNG = np.random.default_rng(20240721)

# ForecastBench non-LLM baselines / humans / ensembles -- excluded from the
# 'LLM leaderboard' we reorder (kept in the table flagged, for reference).
BASELINE_TOKENS = ("always-0", "always-1", "always-0.5", "random-uniform",
                   "naive-forecaster", "imputed-forecaster", "human_public",
                   "human_super", "llm_crowd")

def brier(p, y):
    return (p - y) ** 2

def logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))

def fid_of(path):
    b = os.path.basename(path)[:-5]            # drop .json
    for pre in ("2024-07-21.", "24-07-21."):   # normalise round-date prefix
        if b.startswith(pre):
            b = b[len(pre):]
    return b

def is_baseline(fid):
    return any(t in fid for t in BASELINE_TOKENS)

# ----------------------------------------------------------------------------
# Load every model file into one long market-track table
# ----------------------------------------------------------------------------
files = sorted(glob.glob(os.path.join(FCDIR, "*.json")))
rows = []
for f in files:
    fid = fid_of(f)
    d = json.load(open(f))
    org = d.get("organization", fid.split(".")[0])
    for r in d["forecasts"]:
        src = r.get("source")
        if src not in MARKET:
            continue
        if not r.get("resolved"):
            continue
        y = r.get("resolved_to")
        if y not in (0.0, 1.0):
            continue
        pr = r.get("market_value_on_due_date")
        fc = r.get("forecast")
        if pr is None or fc is None:
            continue
        try:
            pr = float(pr); fc = float(fc)
        except (TypeError, ValueError):
            continue
        if not (0.0 <= fc <= 1.0):       # forecasts must be probabilities
            continue
        rows.append({
            "fid": fid, "org": org, "qid": str(r["id"]), "source": src,
            "p_ref": float(np.clip(pr, EPS, 1 - EPS)),
            "forecast": float(np.clip(fc, EPS, 1 - EPS)),
            "y": float(y), "imputed": bool(r.get("imputed", False)),
        })
m = pd.DataFrame(rows)
m["s_ref"] = brier(m.p_ref, m.y)
m["s_f"] = brier(m.forecast, m.y)
m["d"] = m.s_ref - m.s_f
m["is_baseline"] = m.fid.map(is_baseline)
print(f"market rows (all files): {len(m)}  | configs: {m.fid.nunique()}  "
      f"| resolved binary market questions: {m.qid.nunique()}")

# the model leaderboard set: real LLM configs only (exclude baselines/humans/crowd)
ml = m[~m.is_baseline].copy()
print(f"LLM configs: {ml.fid.nunique()}  | rows: {len(ml)}")

# ----------------------------------------------------------------------------
# Panel-balance check  (is the reference term really constant across configs?)
# ----------------------------------------------------------------------------
cov = ml.groupby("fid").qid.nunique()
qset_per = ml.groupby("fid").qid.apply(lambda s: frozenset(s))
common_q = set.intersection(*[set(x) for x in qset_per]) if len(qset_per) else set()
balance = {
    "n_configs": int(ml.fid.nunique()),
    "n_distinct_market_questions": int(ml.qid.nunique()),
    "coverage_per_config": {"min": int(cov.min()), "median": float(cov.median()),
                            "max": int(cov.max())},
    "n_questions_answered_by_all_configs": int(len(common_q)),
    "frac_of_questions_common_to_all": float(len(common_q) / ml.qid.nunique()),
}
print(f"[balance] questions/config min={cov.min()} med={cov.median():.0f} "
      f"max={cov.max()}; common-to-all={len(common_q)}/{ml.qid.nunique()}")

# ----------------------------------------------------------------------------
# Per-config aggregates: Brier, edge (incl + excl imputed)
# ----------------------------------------------------------------------------
def agg(g):
    real = g[~g.imputed]
    return pd.Series({
        "org": g.org.iloc[0], "N": len(g),
        "mean_brier": g.s_f.mean(), "mean_brier_ref": g.s_ref.mean(),
        "edge": g.d.mean(),
        "mean_abs_dev_from_ref": (g.forecast - g.p_ref).abs().mean(),
        "N_real": len(real),
        "mean_brier_real": real.s_f.mean() if len(real) else np.nan,
        "edge_real": real.d.mean() if len(real) else np.nan,
    })

lb = ml.groupby("fid").apply(agg)
lb["brier_rank"] = lb["mean_brier"].rank(ascending=True, method="min").astype(int)
lb["edge_rank"] = lb["edge"].rank(ascending=False, method="min").astype(int)

# D1: does edge reorder vs Brier?  (predict rho ~ 1 on a balanced panel)
rho_eb, p_eb = stats.spearmanr(-lb["mean_brier"], lb["edge"])
# how constant is the reference term across configs?
ref_term = ml.groupby("fid").s_ref.mean()
print(f"\n[D1] rank-by-edge vs rank-by-Brier (LLM configs): "
      f"Spearman rho={rho_eb:.4f} (p={p_eb:.1e})")
print(f"[D1] per-config mean reference Brier  spread: "
      f"min={ref_term.min():.4f} max={ref_term.max():.4f} "
      f"sd={ref_term.std():.5f}  (sd~0 => edge = const - Brier => rho=1)")

# ----------------------------------------------------------------------------
# D1b: priced/unpriced decomposition per config -> beta_fc ranking
#   y ~ Lambda(b0 + b_ref*logit(p_ref) + b_fc*logit(p_fc))   (per config, market)
# ----------------------------------------------------------------------------
def encompass(g):
    g = g.dropna(subset=["p_ref", "forecast", "y"])
    if len(g) < 30 or g.y.nunique() < 2:
        return (np.nan, np.nan, np.nan)
    X = np.column_stack([np.ones(len(g)),
                         logit(g.p_ref.values), logit(g.forecast.values)])
    yv = g.y.values
    try:
        res = sm.Logit(yv, X).fit(disp=0, maxiter=200)
        return (res.params[1], res.params[2], res.bse[2])   # b_ref, b_fc, se_fc
    except Exception:
        # LPM fallback (separation / non-convergence)
        try:
            res = sm.OLS(yv, X).fit()
            return (res.params[1], res.params[2], res.bse[2])
        except Exception:
            return (np.nan, np.nan, np.nan)

dec = ml.groupby("fid").apply(lambda g: pd.Series(
    dict(zip(["beta_ref", "beta_fc", "se_fc"], encompass(g)))))
lb = lb.join(dec)
lb["fc_rank"] = lb["beta_fc"].rank(ascending=False, method="min")

valid = lb.dropna(subset=["beta_fc"])
rho_fc_brier, p_fc_brier = stats.spearmanr(-valid["mean_brier"], valid["beta_fc"])
rho_fc_edge, _ = stats.spearmanr(valid["edge"], valid["beta_fc"])
print(f"\n[D1b] decomposition reorder: rank-by-beta_fc vs rank-by-Brier "
      f"Spearman rho={rho_fc_brier:.3f} (p={p_fc_brier:.1e})  "
      f"[<1 => the decomposition genuinely reorders the balanced leaderboard]")
print(f"[D1b] beta_fc vs raw edge rho={rho_fc_edge:.3f}")

lb_sorted = lb.sort_values("beta_fc", ascending=False)
print("\n  top contributors (high unpriced edge beta_fc):")
for fid, r in lb_sorted.head(8).iterrows():
    print(f"    {fid:55s} beta_fc={r.beta_fc:+.2f} beta_ref={r.beta_ref:+.2f} "
          f"brier={r.mean_brier:.3f} brierRank={int(r.brier_rank)}")
print("  bottom (echoers / low unpriced edge):")
for fid, r in lb_sorted.tail(6).iterrows():
    print(f"    {fid:55s} beta_fc={r.beta_fc:+.2f} beta_ref={r.beta_ref:+.2f} "
          f"brier={r.mean_brier:.3f} brierRank={int(r.brier_rank)}")

lb.reset_index().rename(columns={"index": "fid"}).to_csv(
    os.path.join(OUT, "llm_leaderboard.csv"), index=False)

# ----------------------------------------------------------------------------
# D2: copy-the-market matched pairs  X  vs  X_with_freeze_values
# ----------------------------------------------------------------------------
all_fids = set(m.fid.unique())
pairs = []
for fid in sorted(all_fids):
    if fid.endswith("_with_freeze_values"):
        continue
    twin = fid + "_with_freeze_values"
    if twin in all_fids:
        pairs.append((fid, twin))

def stats_on_common(base_fid, frz_fid):
    a = m[m.fid == base_fid].set_index("qid")
    b = m[m.fid == frz_fid].set_index("qid")
    common = a.index.intersection(b.index)
    if len(common) < 30:
        return None
    a, b = a.loc[common], b.loc[common]
    br_b, bf = encompass(a.reset_index()), encompass(b.reset_index())
    return {
        "base": base_fid, "freeze": frz_fid, "n_common": int(len(common)),
        "absdev_base": float((a.forecast - a.p_ref).abs().mean()),
        "absdev_freeze": float((b.forecast - b.p_ref).abs().mean()),
        "brier_base": float(a.s_f.mean()), "brier_freeze": float(b.s_f.mean()),
        "edge_base": float(a.d.mean()), "edge_freeze": float(b.d.mean()),
        "beta_fc_base": float(br_b[1]), "beta_fc_freeze": float(bf[1]),
        "beta_ref_base": float(br_b[0]), "beta_ref_freeze": float(bf[0]),
    }

pr = [s for s in (stats_on_common(a, b) for a, b in pairs) if s]
pr = pd.DataFrame(pr)
pr["d_absdev"] = pr.absdev_freeze - pr.absdev_base      # <0: freeze copies price
pr["d_brier"] = pr.brier_freeze - pr.brier_base         # <0: freeze better Brier
pr["d_edge"] = pr.edge_freeze - pr.edge_base            # >0: freeze "wins" on edge
pr["d_beta_fc"] = pr.beta_fc_freeze - pr.beta_fc_base   # <=0: no unpriced gain
pr["d_beta_ref"] = pr.beta_ref_freeze - pr.beta_ref_base
pr.to_csv(os.path.join(OUT, "copy_the_market_pairs.csv"), index=False)

def wilcox(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    try:
        return float(stats.wilcoxon(x).pvalue)
    except Exception:
        return float("nan")

d2 = {
    "n_pairs": int(len(pr)),
    "absdev": {"base": float(pr.absdev_base.mean()),
               "freeze": float(pr.absdev_freeze.mean()),
               "median_delta": float(pr.d_absdev.median()),
               "frac_freeze_copies_more": float((pr.d_absdev < 0).mean()),
               "wilcoxon_p": wilcox(pr.d_absdev)},
    "brier": {"base": float(pr.brier_base.mean()),
              "freeze": float(pr.brier_freeze.mean()),
              "median_delta": float(pr.d_brier.median()),
              "frac_freeze_better_brier": float((pr.d_brier < 0).mean()),
              "wilcoxon_p": wilcox(pr.d_brier)},
    "edge": {"base": float(pr.edge_base.mean()),
             "freeze": float(pr.edge_freeze.mean()),
             "median_delta": float(pr.d_edge.median()),
             "frac_freeze_higher_edge": float((pr.d_edge > 0).mean()),
             "note": "edge=const-Brier on a question, so freeze 'winning' on edge "
                     "is the SAME fact as freeze winning on Brier -> raw edge "
                     "rewards copying."},
    "beta_fc_unpriced": {"base": float(pr.beta_fc_base.mean()),
                         "freeze": float(pr.beta_fc_freeze.mean()),
                         "median_delta": float(pr.d_beta_fc.median()),
                         "frac_freeze_lower_unpriced": float((pr.d_beta_fc < 0).mean()),
                         "wilcoxon_p": wilcox(pr.d_beta_fc)},
    "beta_ref_priced": {"base": float(pr.beta_ref_base.mean()),
                        "freeze": float(pr.beta_ref_freeze.mean()),
                        "median_delta": float(pr.d_beta_ref.median()),
                        "frac_freeze_higher_priced": float((pr.d_beta_ref > 0).mean())},
}
print(f"\n[D2] copy-the-market matched pairs: n={len(pr)}")
print(f"     |p-p_ref| (copying): base={d2['absdev']['base']:.3f} -> "
      f"freeze={d2['absdev']['freeze']:.3f}  "
      f"(freeze copies more in {100*d2['absdev']['frac_freeze_copies_more']:.0f}% of pairs, "
      f"p={d2['absdev']['wilcoxon_p']:.1e})")
print(f"     Brier:               base={d2['brier']['base']:.3f} -> "
      f"freeze={d2['brier']['freeze']:.3f}  "
      f"(freeze better in {100*d2['brier']['frac_freeze_better_brier']:.0f}%, "
      f"p={d2['brier']['wilcoxon_p']:.1e})")
print(f"     raw edge:            base={d2['edge']['base']:.3f} -> "
      f"freeze={d2['edge']['freeze']:.3f}  "
      f"(freeze HIGHER edge in {100*d2['edge']['frac_freeze_higher_edge']:.0f}% "
      f"-> raw edge rewards copying)")
print(f"     unpriced beta_fc:    base={d2['beta_fc_unpriced']['base']:+.2f} -> "
      f"freeze={d2['beta_fc_unpriced']['freeze']:+.2f}  "
      f"(freeze LOWER unpriced in {100*d2['beta_fc_unpriced']['frac_freeze_lower_unpriced']:.0f}%, "
      f"p={d2['beta_fc_unpriced']['wilcoxon_p']:.1e})")
print(f"     priced  beta_ref:    base={d2['beta_ref_priced']['base']:+.2f} -> "
      f"freeze={d2['beta_ref_priced']['freeze']:+.2f}  "
      f"(freeze higher priced in {100*d2['beta_ref_priced']['frac_freeze_higher_priced']:.0f}%)")

# ----------------------------------------------------------------------------
summary = {
    "round": "2024-07-21",
    "data_source": "forecastbench.org processed forecast sets (public, CC BY-SA 4.0)",
    "leak_free": "forecasts elicited at 2024-07-21 freeze, before resolution",
    "panel_balance": balance,
    "D1_edge_vs_brier": {
        "spearman_rho": float(rho_eb), "p": float(p_eb),
        "reference_term_sd_across_configs": float(ref_term.std()),
        "interpretation": ("On a (near-)balanced panel the reference score is "
                           "constant across configs, so edge=const-Brier and the "
                           "edge ranking is a monotone transform of Brier: the naive "
                           "'edge over market' does NOT reorder a balanced benchmark."),
    },
    "D1b_decomposition_reorder": {
        "beta_fc_vs_brier_rho": float(rho_fc_brier), "p": float(p_fc_brier),
        "beta_fc_vs_edge_rho": float(rho_fc_edge),
        "interpretation": ("beta_fc (unpriced edge) is NOT a monotone transform of "
                           "Brier; ranking by it reorders the balanced leaderboard "
                           "and is the honest instrument on balanced data."),
    },
    "D2_copy_the_market": d2,
}
json.dump(summary, open(os.path.join(OUT, "summary_llm.json"), "w"), indent=2)
print(f"\nwrote {OUT}/llm_leaderboard.csv, copy_the_market_pairs.csv, summary_llm.json")
