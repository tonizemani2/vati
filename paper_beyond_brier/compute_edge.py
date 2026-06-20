#!/usr/bin/env python3
"""
Beyond Brier: Calibrated Marginal Edge over the reference prior on ForecastBench.

Recomputes a forecaster leaderboard under a new metric -- each forecaster's
CALIBRATED MARGINAL EDGE over the per-question reference prior (market price /
last-value) -- and tests whether it REORDERS relative to a raw-Brier ranking.

DATA SCOPE (honest):
  The public ForecastBench dataset repo exposes RAW per-question forecasts only
  for the 2024-07-21 round, and only for HUMAN forecasters
  (40 individual superforecasters + 500 individual public forecasters).
  Per-question LLM-model forecasts are NOT public, and the published
  'leaderboard_dataset.csv' 'Dataset' column is a multi-round, fixed-effect
  -adjusted BSS -- not a raw per-question score -- so the 200+ LLM rows cannot be
  recomputed from public data. We therefore run the reordering analysis at the
  level of the 540 individual human forecasters in the 2024-07-21 round, where
  raw forecasts, the reference prior, and resolutions are ALL public.

  The published-ranking comparison anchor used here is each forecaster's RAW MEAN
  BRIER (lower=better) -- the metric the headline leaderboard is built on -- which
  we compute ourselves from the same joined data. We additionally locate the two
  published human-aggregate rows ('Superforecaster median forecast',
  'Public median forecast') in leaderboard_dataset.csv for context.

Reproducible: reads cached data/ + forecast_sets/, writes out/.
"""
import json, os, hashlib, math, warnings
from collections import defaultdict
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.isotonic import IsotonicRegression
import statsmodels.api as sm
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = "/Users/emizemani/Desktop/predictthefuture/paper_beyond_brier"
DATA = os.path.join(ROOT, "data")
FCDIR = os.path.join(ROOT, "forecast_sets", "2024-07-21")
OUT = os.path.join(ROOT, "out")
os.makedirs(OUT, exist_ok=True)

MARKET = {"manifold", "metaculus", "polymarket", "infer"}
DATASRC = {"acled", "fred", "dbnomics", "wikipedia", "yfinance"}
EPS = 1e-3
RNG = np.random.default_rng(20240721)
B_BOOT = 10000

def brier(p, y):
    return (p - y) ** 2

def clip(p):
    return float(np.clip(p, EPS, 1 - EPS))

def logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))

# ----------------------------------------------------------------------------
# Load reference data
# ----------------------------------------------------------------------------
print("Loading question set, resolution set, leaderboard...")
qset = json.load(open(os.path.join(DATA, "q.json")))["questions"]
rset = json.load(open(os.path.join(DATA, "r.json")))["resolutions"]
lb = pd.read_csv(os.path.join(DATA, "leaderboard_dataset.csv"))

# question lookup (single-question native ids only; combos handled separately)
Q = {}
for q in qset:
    if isinstance(q["id"], str):
        Q[q["id"]] = q

# p_ref per single question id (freeze value)
P_REF = {}
for qid, q in Q.items():
    try:
        P_REF[qid] = float(q["freeze_datetime_value"])
    except (ValueError, TypeError):
        pass

# resolution lookup: single ids only, keyed by (id, resolution_date) -> resolved_to (resolved=True)
RES = {}
for r in rset:
    if isinstance(r["id"], str) and r.get("resolved") is True:
        rt = r.get("resolved_to")
        if rt is not None:
            RES[(r["id"], r["resolution_date"])] = float(rt)

print(f"  questions(single)={len(Q)}  p_ref={len(P_REF)}  resolutions(single,resolved)={len(RES)}")

# ----------------------------------------------------------------------------
# Build per-forecast joined rows for each human file
# Each individual forecaster = (file_tag, user_id)
# ----------------------------------------------------------------------------
def load_forecasts(path, tag):
    d = json.load(open(path))
    rows = []
    for f in d["forecasts"]:
        rows.append({
            "tag": tag,
            "user_id": f.get("user_id"),
            "id": f["id"],
            "source": f["source"],
            "direction": f.get("direction"),
            "resolution_date": f.get("resolution_date"),
            "forecast": f.get("forecast"),
        })
    return rows

raw = []
raw += load_forecasts(os.path.join(FCDIR, "human_super.json"), "super")
raw += load_forecasts(os.path.join(FCDIR, "human_public.json"), "public")
df = pd.DataFrame(raw)
print(f"Loaded {len(df)} raw forecast rows; "
      f"{df[df.tag=='super'].user_id.nunique()} supers + "
      f"{df[df.tag=='public'].user_id.nunique()} public forecasters.")

# combo leg ids (forecasts referencing a leg whose resolution is only under a hashed combo id)
combo_leg_ids = set()
for r in rset:
    if isinstance(r["id"], list):
        for x in r["id"]:
            combo_leg_ids.add(x)

# ----------------------------------------------------------------------------
# Join: attach p_ref and y (resolved_to). Track match accounting.
# ----------------------------------------------------------------------------
def is_market(s): return s in MARKET

# For market questions: single horizon -> match resolution by id alone (one row)
res_by_id = defaultdict(list)
for (rid, rd), y in RES.items():
    res_by_id[rid].append((rd, y))

def join_row(row):
    qid = row["id"]
    src = row["source"]
    # --- REFERENCE PRIOR ---
    # MARKET sources: freeze_datetime_value IS a probability in [0,1] (the market
    #   price / crowd value at freeze) -> use directly. This is the strong free prior.
    # DATA sources: freeze_datetime_value is the RAW SERIES LEVEL (e.g. a FRED rate of
    #   4.76, a FRED level of 105998), NOT a probability. The questions resolve on
    #   whether the series INCREASED vs that frozen level. The correct naive
    #   last-value / random-walk prior for a "will it go up?" question is therefore
    #   p_ref = 0.5 (the ForecastBench "Naive Forecaster" baseline). We do NOT and
    #   cannot use the raw level as a probability.
    if is_market(src):
        p_ref = P_REF.get(qid, np.nan)
    else:
        p_ref = 0.5
    # --- OUTCOME ---
    if is_market(src):
        cand = res_by_id.get(qid, [])
        y = cand[0][1] if len(cand) >= 1 else np.nan
    else:
        rd = row["resolution_date"]
        y = RES.get((qid, rd), np.nan)
    return pd.Series({"p_ref": p_ref, "y": y})

joined = df.join(df.apply(join_row, axis=1))

# NOTE on combinations: combination questions have LIST ids (resolutions keyed by a
# 2-tuple/hashed pair). The human forecast files contain NO combination forecasts
# (every forecast 'id' is a single native string id and 'direction' is always None).
# 455 of the 500 single questions also appear as a *leg* inside some combination
# question, but the human forecasts on them are genuine standalone single-question
# forecasts -- so combos are simply absent here and require no special handling.
# accounting
n_total = len(joined)
has_pref = joined.p_ref.notna()
has_y = joined.y.notna()
joined["track"] = np.where(joined.source.isin(MARKET), "market",
                   np.where(joined.source.isin(DATASRC), "data", "other"))
# valid forecast value: must be a probability. A small number of human entries are
# malformed (e.g. raw values like 5e8, or slightly <0); require forecast in
# [-0.01, 1.01] then clip into [0,1]. Anything wildly outside is dropped as a data error.
fc_ok = joined.forecast.notna() & (joined.forecast >= -0.01) & (joined.forecast <= 1.01)
joined.loc[fc_ok, "forecast"] = joined.loc[fc_ok, "forecast"].clip(0, 1)
has_pf = fc_ok
n_fc_dropped_bad = int((joined.forecast.notna() & ~fc_ok).sum())
# binary outcome only (resolved_to in {0,1}); also allow numeric in [0,1] for data? spec: binary/numeric resolved.
# Brier is well-defined for y in [0,1]; ForecastBench data y in {0,1} for binary, but FRED/yfinance can be 0/1 via direction questions.
y_binary = joined.y.isin([0.0, 1.0])

valid = has_pref & has_y & has_pf
joined_valid = joined[valid].copy()

# Drop combos explicitly: market track has no combos in forecasts (direction always None);
# data track combos are forecasts whose id is a combo leg AND not directly resolvable -> already NaN y (dropped).
# Record how many valid rows have ids that are combo legs (should be ~0 after y-join).
n_combo_legs_valid = joined_valid.id.isin(combo_leg_ids).sum()

print(f"JOIN ACCOUNTING:")
print(f"  total forecast rows: {n_total}")
print(f"  with p_ref: {has_pref.sum()} ({has_pref.mean()*100:.1f}%)")
print(f"  with resolution y: {has_y.sum()} ({has_y.mean()*100:.1f}%)")
print(f"  forecast values dropped as non-probability (|x|>1.01): {n_fc_dropped_bad}")
print(f"  fully joined (p_ref & y & valid p_f): {valid.sum()} ({valid.mean()*100:.1f}%)")
print(f"  of those, y is binary {{0,1}}: {(y_binary & valid).sum()}")
print(f"  (info) valid rows whose id is also used as a combo leg elsewhere: {n_combo_legs_valid} "
      f"-- these are STANDALONE single-question forecasts, not combo forecasts (no combos in human files)")

# Keep only binary outcomes for clean Brier/edge (spec: binary/numeric resolved; we use binary {0,1})
joined_valid = joined_valid[joined_valid.y.isin([0.0, 1.0])].copy()
print(f"  retained for analysis (binary y): {len(joined_valid)}")

# ----------------------------------------------------------------------------
# Per-question edge d = S(p_ref,y) - S(p_f,y)
# ----------------------------------------------------------------------------
joined_valid["s_ref"] = brier(joined_valid.p_ref, joined_valid.y)
joined_valid["s_f"]   = brier(joined_valid.forecast, joined_valid.y)
joined_valid["d"]     = joined_valid.s_ref - joined_valid.s_f
joined_valid["fid"]   = joined_valid.tag + ":" + joined_valid.user_id.astype(str)

joined_valid.to_csv(os.path.join(OUT, "joined_rows.csv"), index=False)

# ----------------------------------------------------------------------------
# Aggregate per forecaster, per track, with bootstrap CI
# ----------------------------------------------------------------------------
def bootstrap_ci(vals, B=B_BOOT):
    vals = np.asarray(vals, float)
    n = len(vals)
    if n < 2:
        return (np.nan, np.nan)
    idx = RNG.integers(0, n, size=(B, n))
    boots = vals[idx].mean(axis=1)
    return (np.percentile(boots, 2.5), np.percentile(boots, 97.5))

def build_leaderboard(track, min_n=30):
    sub = joined_valid[joined_valid.track == track]
    rows = []
    for fid, g in sub.groupby("fid"):
        n = len(g)
        if n < min_n:
            continue
        edge = g.d.mean()
        se = g.d.std(ddof=1) / math.sqrt(n) if n > 1 else np.nan
        lo, hi = bootstrap_ci(g.d.values)
        mb = g.s_f.mean()
        mb_ref = g.s_ref.mean()
        rows.append({
            "forecaster": fid,
            "tag": g.tag.iloc[0],
            "N": n,
            "mean_brier": mb,
            "mean_brier_ref": mb_ref,
            "edge": edge,
            "edge_se": se,
            "edge_ci_low": lo,
            "edge_ci_high": hi,
        })
    out = pd.DataFrame(rows)
    if len(out) == 0:
        return out
    # ranks: edge rank (1 = best/highest edge); brier rank (1 = best/lowest brier)
    out["edge_rank"] = out["edge"].rank(ascending=False, method="min").astype(int)
    out["brier_rank"] = out["mean_brier"].rank(ascending=True, method="min").astype(int)
    out["rank_change"] = out["brier_rank"] - out["edge_rank"]  # +ve = moved UP under edge
    out = out.sort_values("edge", ascending=False).reset_index(drop=True)
    return out

# Individual forecasters answer few MARKET questions (median ~6); only supers
# accumulate enough. Use min_n=20 for market (supers clear it), min_n=30 for data
# (539 forecasters, median N=45 -> well powered; this is the statistically solid track).
MIN_N_MARKET = 20
MIN_N_DATA = 30
lb_market = build_leaderboard("market", min_n=MIN_N_MARKET)
lb_data   = build_leaderboard("data", min_n=MIN_N_DATA)

print(f"\nMARKET leaderboard: {len(lb_market)} forecasters (min_n={MIN_N_MARKET})")
print(f"DATA   leaderboard: {len(lb_data)} forecasters (min_n={MIN_N_DATA})")

# Save (rename to match requested schema; published_rank == our brier_rank anchor)
def save_lb(out, path):
    cols = ["forecaster", "tag", "N", "mean_brier", "edge", "edge_ci_low",
            "edge_ci_high", "brier_rank", "edge_rank", "rank_change"]
    out2 = out[cols].rename(columns={"brier_rank": "published_rank"})
    out2.to_csv(path, index=False)

save_lb(lb_market, os.path.join(OUT, "leaderboard_edge_market.csv"))
save_lb(lb_data, os.path.join(OUT, "leaderboard_edge_data.csv"))

# ----------------------------------------------------------------------------
# Reordering statistics (market track headline)
# ----------------------------------------------------------------------------
def reorder_stats(out):
    if len(out) < 3:
        return {}
    # rank by edge vs rank by brier
    rho, rho_p = stats.spearmanr(-out["mean_brier"], out["edge"])  # both higher=better orientation
    tau, tau_p = stats.kendalltau(-out["mean_brier"], out["edge"])
    # rank-change distribution
    rc = out["rank_change"]
    movers_up = out.nlargest(5, "rank_change")[["forecaster", "brier_rank", "edge_rank", "rank_change", "edge", "mean_brier"]]
    movers_dn = out.nsmallest(5, "rank_change")[["forecaster", "brier_rank", "edge_rank", "rank_change", "edge", "mean_brier"]]
    return {
        "spearman_rho": float(rho), "spearman_p": float(rho_p),
        "kendall_tau": float(tau), "kendall_p": float(tau_p),
        "rank_change_mean_abs": float(rc.abs().mean()),
        "rank_change_max_abs": int(rc.abs().max()),
        "n_forecasters": int(len(out)),
        "biggest_gainers": movers_up.to_dict("records"),
        "biggest_losers": movers_dn.to_dict("records"),
    }

rs_market = reorder_stats(lb_market)
rs_data = reorder_stats(lb_data)

# ----------------------------------------------------------------------------
# Sanity check: does our Brier ranking reproduce the published human aggregates?
# We compute the Super-median and Public-median ensemble Brier on market+data and
# compare their RELATIVE order to leaderboard_dataset.csv (Super median ranks
# above Public median there: 63.8 vs 59.3 on the dataset half).
# ----------------------------------------------------------------------------
def median_ensemble_brier(tag, track):
    sub = joined_valid[(joined_valid.tag == tag) & (joined_valid.track == track)].copy()
    # market questions have resolution_date=None -> group by id only; data by (id, resdate)
    if track == "market":
        sub["rd_key"] = sub["id"]
    else:
        sub["rd_key"] = sub["id"].astype(str) + "|" + sub["resolution_date"].astype(str)
    med = sub.groupby("rd_key").agg(
        p=("forecast", "median"), y=("y", "first")).reset_index()
    if len(med) == 0:
        return float("nan"), 0
    return float(brier(med.p, med.y).mean()), len(med)

sanity = {}
for track in ["market", "data"]:
    sb, ns = median_ensemble_brier("super", track)
    pb, npub = median_ensemble_brier("public", track)
    sanity[track] = {
        "super_median_brier": float(sb), "super_median_nq": int(ns),
        "public_median_brier": float(pb), "public_median_nq": int(npub),
        "super_beats_public": bool(sb < pb),
    }
# Published dataset-half: Super median 63.8 > Public median 59.3 (higher=better) -> super beats public.
pub_super = lb[lb.Model == "Superforecaster median forecast"]["Dataset"].iloc[0]
pub_public = lb[lb.Model == "Public median forecast"]["Dataset"].iloc[0]
sanity["published_dataset_half"] = {
    "super_median_score": float(pub_super),
    "public_median_score": float(pub_public),
    "super_beats_public": bool(pub_super > pub_public),
}

# ----------------------------------------------------------------------------
# Forecast-encompassing logistic regression (priced vs unpriced) on MARKET track
#   y ~ Lambda(b0 + b_ref*logit(p_ref) + b_fc*logit(p_f))
# Fit for top-5 by market edge + the superforecaster-median pseudo-forecaster.
# ----------------------------------------------------------------------------
def encompass(sub):
    sub = sub.dropna(subset=["p_ref", "forecast", "y"])
    if len(sub) < 20 or sub.y.nunique() < 2:
        return None
    lref = logit(sub.p_ref.values)
    cols = {"const": 1.0, "logit_fc": logit(sub.forecast.values)}
    # include the prior term only if it has variation (data-track prior is constant 0.5)
    if np.std(lref) > 1e-9:
        cols["logit_ref"] = lref
    X = pd.DataFrame(cols)
    y = sub.y.values.astype(float)
    try:
        m = sm.Logit(y, X).fit(disp=0, maxiter=200)
    except Exception as e:
        return {"error": str(e)}
    out = {
        "n": int(len(sub)),
        "b_fc": float(m.params["logit_fc"]), "se_fc": float(m.bse["logit_fc"]), "p_fc": float(m.pvalues["logit_fc"]),
        "b0": float(m.params["const"]),
    }
    if "logit_ref" in m.params:
        out.update({"b_ref": float(m.params["logit_ref"]),
                    "se_ref": float(m.bse["logit_ref"]),
                    "p_ref": float(m.pvalues["logit_ref"])})
    else:
        out.update({"b_ref": float("nan"), "se_ref": float("nan"), "p_ref": float("nan"),
                    "note": "prior constant (data track p_ref=0.5); ref term dropped"})
    return out

enc_rows = []
# top-5 by market edge
for _, r in lb_market.head(5).iterrows():
    sub = joined_valid[(joined_valid.fid == r.forecaster) & (joined_valid.track == "market")]
    res = encompass(sub)
    if res:
        res["forecaster"] = r.forecaster
        res["edge"] = float(r.edge)
        enc_rows.append(res)
# superforecaster median pseudo-forecaster (market). Market resolution_date is None
# so group by id only.
sub = joined_valid[(joined_valid.tag == "super") & (joined_valid.track == "market")]
med = sub.groupby("id").agg(
    forecast=("forecast", "median"), p_ref=("p_ref", "first"), y=("y", "first")).reset_index()
res = encompass(med)
if res:
    res["forecaster"] = "SUPER_MEDIAN(market)"
    res["edge"] = float((brier(med.p_ref, med.y) - brier(med.forecast, med.y)).mean())
    enc_rows.append(res)

# POOLED encompassing across ALL forecasts in each track (well-powered; this is the
# real "is forecaster signal priced into the prior?" test). One row per (forecast).
for track in ["market", "data"]:
    sub = joined_valid[joined_valid.track == track]
    res = encompass(sub)
    if res:
        res["forecaster"] = f"POOLED_ALL({track})"
        res["edge"] = float(sub.d.mean())
        enc_rows.append(res)
# POOLED across supers only, each track
for track in ["market", "data"]:
    sub = joined_valid[(joined_valid.track == track) & (joined_valid.tag == "super")]
    res = encompass(sub)
    if res:
        res["forecaster"] = f"POOLED_SUPERS({track})"
        res["edge"] = float(sub.d.mean())
        enc_rows.append(res)

enc_df = pd.DataFrame(enc_rows)
if len(enc_df):
    cols = ["forecaster", "edge", "n", "b_ref", "se_ref", "p_ref", "b_fc", "se_fc", "p_fc", "b0"]
    enc_df = enc_df[[c for c in cols if c in enc_df.columns]]
    enc_df.to_csv(os.path.join(OUT, "encompassing.csv"), index=False)

# ----------------------------------------------------------------------------
# Out-of-sample isotonic recalibration (market track, 5-fold over questions)
#   recompute edge with recalibrated p_f; report alongside raw.
# ----------------------------------------------------------------------------
def oos_isotonic_edge(track, min_n=50, k=5):
    sub = joined_valid[joined_valid.track == track].copy()
    rows = []
    for fid, g in sub.groupby("fid"):
        g = g.reset_index(drop=True)
        n = len(g)
        if n < min_n or g.y.nunique() < 2:
            continue
        order = RNG.permutation(n)
        folds = np.array_split(order, k)
        p_recal = np.full(n, np.nan)
        for i in range(k):
            test = folds[i]
            train = np.concatenate([folds[j] for j in range(k) if j != i])
            ir = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
            # need variation in train y
            if g.y.iloc[train].nunique() < 2:
                p_recal[test] = g.forecast.iloc[test].values
                continue
            ir.fit(g.forecast.iloc[train].values, g.y.iloc[train].values)
            p_recal[test] = ir.predict(g.forecast.iloc[test].values)
        d_raw = (brier(g.p_ref, g.y) - brier(g.forecast, g.y)).mean()
        d_recal = (brier(g.p_ref, g.y) - brier(p_recal, g.y)).mean()
        rows.append({"forecaster": fid, "N": n, "edge_raw": d_raw, "edge_recal": d_recal})
    return pd.DataFrame(rows)

# Market coverage per individual is thin; use min_n=25 so several supers qualify.
# Isotonic recalibration with so few points is itself noisy -> reported as indicative.
recal_market = oos_isotonic_edge("market", min_n=25, k=5)
if len(recal_market):
    recal_market.to_csv(os.path.join(OUT, "recalibrated_edge_market.csv"), index=False)

# ----------------------------------------------------------------------------
# Summary JSON
# ----------------------------------------------------------------------------
summary = {
    "scope_note": ("Public ForecastBench raw forecasts exist only for 2024-07-21, "
                   "humans only. LLM per-question forecasts are not public and the "
                   "leaderboard 'Dataset' column is a multi-round fixed-effect BSS; "
                   "reordering is computed over 540 individual human forecasters."),
    "tracks": {
        "market_sources": sorted(MARKET),
        "data_sources": sorted(DATASRC),
    },
    "coverage": {
        "n_forecast_rows_total": int(n_total),
        "match_rate_p_ref": float(has_pref.mean()),
        "match_rate_resolution": float(has_y.mean()),
        "match_rate_full_join": float(valid.mean()),
        "n_valid_binary_rows": int(len(joined_valid)),
        "n_market_rows": int((joined_valid.track == "market").sum()),
        "n_data_rows": int((joined_valid.track == "data").sum()),
        "n_supers": int(df[df.tag == "super"].user_id.nunique()),
        "n_public": int(df[df.tag == "public"].user_id.nunique()),
        "n_market_forecasters_ranked": int(len(lb_market)),
        "n_data_forecasters_ranked": int(len(lb_data)),
        "combos_excluded": "yes (list-id resolutions; forecast legs drop out on y-join)",
        "dropped_unresolved_or_nan": int(n_total - valid.sum()),
        "forecast_dropped_nonprobability": n_fc_dropped_bad,
        "data_track_prior": "0.5 (random-walk / Naive Forecaster baseline; raw series level is NOT a probability)",
        "market_track_prior": "freeze_datetime_value (market price, in [0,1])",
    },
    "reordering_market": rs_market,
    "reordering_data": rs_data,
    "sanity_check": sanity,
    "recalibration_market": ({
        "n_forecasters": int(len(recal_market)),
        "mean_edge_raw": float(recal_market.edge_raw.mean()),
        "mean_edge_recal": float(recal_market.edge_recal.mean()),
        "method": "5-fold isotonic, leave-fold-out, min_n=25; indicative (thin per-forecaster N)",
    } if len(recal_market) else {"n_forecasters": 0}),
    "bootstrap_B": B_BOOT,
}

with open(os.path.join(OUT, "reordering_summary.json"), "w") as f:
    json.dump(summary, f, indent=2, default=str)

# ----------------------------------------------------------------------------
# Figure: bump/slopegraph of Brier-rank -> Edge-rank for top forecasters (market)
# ----------------------------------------------------------------------------
def make_fig(out, track, path, topn=15):
    if len(out) < 3:
        return
    # focus on the top-N by edge for legibility
    sel = out.nsmallest(topn, "brier_rank").copy()  # best Brier forecasters
    # also ensure top edge are present
    sel = pd.concat([sel, out.nsmallest(topn, "edge_rank")]).drop_duplicates("forecaster")
    sel = sel.sort_values("brier_rank")
    fig, ax = plt.subplots(figsize=(8, max(6, 0.4 * len(sel))))
    for _, r in sel.iterrows():
        color = "#2c7fb8" if r.rank_change >= 0 else "#d95f0e"
        ax.plot([0, 1], [r.brier_rank, r.edge_rank], "-o", color=color, alpha=0.8, lw=1.6, ms=5)
        lbl = r.forecaster.split(":")[0][0].upper() + "·" + r.forecaster.split(":")[-1][:6]
        ax.text(-0.03, r.brier_rank, lbl, ha="right", va="center", fontsize=7)
        ax.text(1.03, r.edge_rank, lbl, ha="left", va="center", fontsize=7)
    ax.invert_yaxis()
    ax.set_xticks([0, 1]); ax.set_xticklabels(["Rank by raw\nmean Brier", "Rank by calibrated\nmarginal edge"])
    ax.set_ylabel("Rank (1 = best)")
    ax.set_title(f"Leaderboard reordering — {track} track\n"
                 f"Spearman ρ={reorder_stats(out)['spearman_rho']:.3f}, "
                 f"Kendall τ={reorder_stats(out)['kendall_tau']:.3f}  "
                 f"(N={len(out)} forecasters)")
    ax.set_xlim(-0.35, 1.35)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()

make_fig(lb_market, "MARKET", os.path.join(OUT, "fig_reordering.png"))

# ----------------------------------------------------------------------------
# Console report
# ----------------------------------------------------------------------------
print("\n================ RESULTS ================")
print(f"MARKET track: {len(lb_market)} forecasters")
if rs_market:
    print(f"  Spearman rho (edge vs -brier) = {rs_market['spearman_rho']:.4f} (p={rs_market['spearman_p']:.2e})")
    print(f"  Kendall  tau                  = {rs_market['kendall_tau']:.4f}")
    print(f"  mean |rank change| = {rs_market['rank_change_mean_abs']:.2f}, max = {rs_market['rank_change_max_abs']}")
    print("  TOP-5 by EDGE:")
    print(lb_market.head(5)[["forecaster","N","mean_brier","edge","edge_ci_low","edge_ci_high","brier_rank","edge_rank"]].to_string(index=False))
    print("  TOP-5 by BRIER (best Brier):")
    print(lb_market.nsmallest(5,"brier_rank")[["forecaster","N","mean_brier","edge","brier_rank","edge_rank"]].to_string(index=False))
print(f"\nDATA track: {len(lb_data)} forecasters")
if rs_data:
    print(f"  Spearman rho (edge vs -brier) = {rs_data['spearman_rho']:.4f} (p={rs_data['spearman_p']:.2e})")
    print(f"  Kendall  tau                  = {rs_data['kendall_tau']:.4f}")
    print(f"  mean |rank change| = {rs_data['rank_change_mean_abs']:.2f}, max = {rs_data['rank_change_max_abs']}")

print("\nSANITY (median-ensemble Brier, lower=better):")
for t in ["market","data"]:
    s=sanity[t]
    print(f"  {t}: super={s['super_median_brier']:.4f} public={s['public_median_brier']:.4f} super_beats_public={s['super_beats_public']}")
print(f"  published dataset-half: super_beats_public={sanity['published_dataset_half']['super_beats_public']} "
      f"({sanity['published_dataset_half']['super_median_score']} vs {sanity['published_dataset_half']['public_median_score']})")
if len(enc_df):
    print("\nENCOMPASSING (market):")
    print(enc_df.to_string(index=False))
if len(recal_market):
    print(f"\nRECALIBRATION (market, 5-fold isotonic), {len(recal_market)} forecasters:")
    print(f"  mean raw edge={recal_market.edge_raw.mean():.4f}  mean recal edge={recal_market.edge_recal.mean():.4f}")
print("\nFiles written to out/:")
for fn in ["leaderboard_edge_market.csv","leaderboard_edge_data.csv","reordering_summary.json",
           "encompassing.csv","recalibrated_edge_market.csv","fig_reordering.png","joined_rows.csv"]:
    p=os.path.join(OUT,fn)
    if os.path.exists(p):
        print(f"  {p}")
print("Done.")
