#!/usr/bin/env python3
"""
Beyond Brier -- MULTI-ROUND extension (29 ForecastBench rounds, 2024-07 -> 2026-05).

Turns the paper's #1 limitation (single round) into its headline. Replicates every
LLM-track empirical claim across all 29 public ForecastBench rounds and answers the
open question the single-round Discussion could not: does contribution-beyond-price
(Delta-LL) grow as models improve over two years of frontier releases?

For each round we build the resolved market panel and, per model configuration:
  Brier, mean marginal edge d = S(p_ref)-S(p_f), the encompassing beta_fc (qid-clustered
  logit), VIF(zf|zref), and the collinearity-robust Delta-LL = [LL(y|ref,fc)-LL(y|ref)]/N.

Round-level outputs:
  * identity check  rho(mean edge, -mean Brier) across configs  (must be ~1.000 every round)
  * std of each config's mean reference Brier  (the per-question constant that makes the
    edge ranking equal the Brier ranking)
  * mean / frontier Delta-LL across the systematic frontier-model battery
  * split-half rank reliability of Brier, beta_fc, Delta-LL  (pooled across rounds)

Groups:
  FRONTIER  -- ForecastBench's own systematic model battery (apples-to-apples across rounds)
  AGENTIC   -- external submitted research/tool systems (the multi-round analogue of humans)

Leak discipline: every forecast is frozen before resolution (ForecastBench design), so each
round is leak-free for that round's models. A NULL Delta-LL trend is conservative: a later
model's larger training cutoff can only inflate Delta-LL, never deflate it, so a flat/zero
trend cannot be a leakage artifact.

Keyless, local, no cost. Writes out_mr/.
"""
import os, json, glob, math, warnings, collections, re
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm

ROOT = "/Users/emizemani/Desktop/predictthefuture/paper_beyond_brier"
BASE = os.path.join(ROOT, "fb_forecast_sets", "forecastbench-processed-forecast-sets")
OUT  = os.path.join(ROOT, "out_mr")
os.makedirs(OUT, exist_ok=True)
MARKET = {"manifold", "metaculus", "polymarket", "infer"}
EPS = 1e-3
RNG = np.random.default_rng(20240721)
SPLIT_REPS = 12

# aggregates / baselines that are not single-model LLM forecasters
NON_MODEL = ("always", "random uniform", "naive forecaster", "imputed forecaster",
             "public median", "superforecaster median", "llm crowd")

def brier(p, y): return (p - y) ** 2
def logit(p):
    p = np.clip(p, EPS, 1 - EPS); return np.log(p / (1 - p))

def is_non_model(model):
    m = model.lower()
    return any(t in m for t in NON_MODEL)

# ---------------------------------------------------------------------------
# release-date parsing for the capability axis (ForecastBench battery only)
# ---------------------------------------------------------------------------
def parse_release(model):
    """Best-effort model release date (YYYY-MM-DD) parsed from the config name,
    with a small lookup for names that carry no date. Returns float year or np.nan."""
    s = model
    # explicit YYYYMMDD  (e.g. Claude-3-Opus-20240229)
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return y + (mo - 1) / 12 + (d - 1) / 365
    # explicit YYYY-MM-DD  (e.g. GPT-5.4-2026-03-05)
    m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return y + (mo - 1) / 12 + (d - 1) / 365
    # MMDD suffix on Grok (e.g. Grok-4-0709)  -> assume 2025 unless 4.20/4.3 (2026)
    m = re.search(r"-(\d{2})(\d{2})\b", s)
    if m and "grok" in s.lower():
        mo, d = int(m.group(1)), int(m.group(2))
        yr = 2026 if re.search(r"4\.2|4\.3", s) else 2025
        if 1 <= mo <= 12:
            return yr + (mo - 1) / 12 + (d - 1) / 365
    # MM-DD preview suffix (Gemini-2.5-Pro-Preview-03-25) -> 2025
    m = re.search(r"-(\d{2})-(\d{2})\)", s + ")")
    # name lookup for dateless flagships (approximate public release)
    LU = {
        "claude-2.1": 2023.9, "gpt-3.5": 2024.0, "gpt-4-0613": 2023.5,
        "gpt-4o": 2024.4, "mistral-large-latest": 2024.5,
        "gemini-1.5": 2024.3, "qwen1.5": 2024.1, "mixtral": 2024.0,
        "llama-2": 2023.6, "llama-3-": 2024.3, "llama-3.1": 2024.6,
        "llama-3.2": 2024.8, "llama-3.3": 2024.95, "llama-4": 2025.3,
        "gemini-2.0": 2025.05, "gemini-2.5-flash": 2025.3, "gemini-2.5-pro": 2025.25,
        "gemini-3-": 2025.9, "gemini-3.1": 2026.0, "gemini-3.5": 2026.3,
        "deepseek-r1": 2025.05, "deepseek-v3.1": 2025.6, "deepseek-v3": 2024.95,
        "deepseek-v4": 2026.1, "qwq-32b": 2024.95, "qwen2.5": 2024.7,
        "qwen3": 2025.4, "grok-beta": 2024.85, "grok-4": 2025.5,
        "grok-4.20": 2026.2, "grok-4.3": 2026.35, "kimi-k2": 2025.6,
        "kimi-k2.5": 2026.0, "kimi-k2.6": 2026.2, "glm-4.5": 2025.6,
        "glm-4.6": 2025.8, "glm-4.7": 2026.0, "glm-5": 2026.2, "glm-5.1": 2026.35,
        "magistral": 2025.5, "gemma-4": 2026.0, "minimax-m2.5": 2026.1,
        "minimax-m2.7": 2026.3, "gpt-4-turbo": 2024.3, "gpt-4.1": 2025.3,
        "gpt-4.5": 2025.15, "gpt-5-": 2025.6, "gpt-5.1": 2025.87,
        "gpt-5.2": 2025.95, "gpt-5.4": 2026.18, "gpt-5.5": 2026.3,
        "o3-mini": 2025.08, "o3-": 2025.3, "o4-mini": 2025.3,
    }
    sl = s.lower()
    for k, v in LU.items():
        if k in sl:
            return v
    return np.nan

def round_to_year(rd):
    y, mo, d = (int(x) for x in rd.split("-"))
    return y + (mo - 1) / 12 + (d - 1) / 365

# ---------------------------------------------------------------------------
def load_round(rd):
    """Return long DataFrame of resolved market rows for all real-model configs."""
    rows = []
    for path in sorted(glob.glob(os.path.join(BASE, rd, "*.json"))):
        try:
            d = json.load(open(path))
        except Exception:
            continue
        org, model = d.get("organization"), d.get("model")
        if not org or not model or is_non_model(model):
            continue
        cfg = f"{org} | {model}"
        is_fb = (org == "ForecastBench")
        rel = parse_release(model) if is_fb else np.nan
        for r in d.get("forecasts", []):
            if r.get("source") not in MARKET or not r.get("resolved"):
                continue
            y = r.get("resolved_to")
            if y not in (0.0, 1.0):
                continue
            pr, fc = r.get("market_value_on_due_date"), r.get("forecast")
            if pr is None or fc is None:
                continue
            try:
                pr, fc = float(pr), float(fc)
            except (TypeError, ValueError):
                continue
            if not (0 <= fc <= 1):
                continue
            rows.append({"cfg": cfg, "org": org, "is_fb": is_fb, "rel": rel,
                         "qid": str(r["id"]),
                         "p_ref": float(np.clip(pr, EPS, 1 - EPS)),
                         "p": float(np.clip(fc, EPS, 1 - EPS)), "y": float(y)})
    if not rows:
        return None
    m = pd.DataFrame(rows)
    m["s_f"] = brier(m.p, m.y); m["s_ref"] = brier(m.p_ref, m.y); m["d"] = m.s_ref - m.s_f
    m["zref"] = logit(m.p_ref); m["zf"] = logit(m.p)
    return m

def delta_ll(g):
    y = g.y.values
    X1 = np.column_stack([np.ones(len(g)), g.zref.values])
    X2 = np.column_stack([np.ones(len(g)), g.zref.values, g.zf.values])
    l0 = sm.Logit(y, X1).fit(disp=0, maxiter=200).llf
    l1 = sm.Logit(y, X2).fit(disp=0, maxiter=200).llf
    return (l1 - l0) / len(g)

def per_config(g):
    g = g.dropna(subset=["zref", "zf", "y"])
    out = {"N": len(g), "nq": g.qid.nunique(), "brier": g.s_f.mean(),
           "edge": g.d.mean(), "ref_brier": g.s_ref.mean(),
           "is_fb": bool(g.is_fb.iloc[0]), "rel": float(g.rel.iloc[0])}
    y = g.y.values
    X = np.column_stack([np.ones(len(g)), g.zref.values, g.zf.values])
    fb = sefb = vif = dll = np.nan
    if len(g) >= 20 and len(np.unique(y)) > 1:
        try:
            res = sm.Logit(y, X).fit(disp=0, maxiter=300, cov_type="cluster",
                                     cov_kwds={"groups": g.qid.values})
            fb, sefb = res.params[2], res.bse[2]
        except Exception:
            pass
        try:
            rr = sm.OLS(g.zf.values, np.column_stack([np.ones(len(g)), g.zref.values])).fit()
            vif = 1.0 / max(1e-9, 1 - rr.rsquared)
        except Exception:
            pass
        try:
            dll = delta_ll(g)
        except Exception:
            pass
    out.update({"beta_fc": fb, "se_fc": sefb, "vif": vif, "dll": dll})
    return pd.Series(out)

def quick_stat(g, col):
    g = g.dropna(subset=["zref", "zf", "y"]); y = g.y.values
    if len(g) < 20 or len(np.unique(y)) < 2:
        return np.nan
    try:
        if col == "brier":
            return -g.s_f.mean()
        X = np.column_stack([np.ones(len(g)), g.zref.values, g.zf.values])
        if col == "beta_fc":
            return sm.Logit(y, X).fit(disp=0, maxiter=150).params[2]
        if col == "dll":
            return delta_ll(g)
    except Exception:
        return np.nan

def split_half(m, col, reps=SPLIT_REPS):
    qs = m.qid.unique()
    if len(qs) < 8:
        return np.nan, 0
    out = []
    for _ in range(reps):
        perm = RNG.permutation(qs); h1 = set(perm[:len(qs) // 2])
        a = m[m.qid.isin(h1)]; b = m[~m.qid.isin(h1)]
        ca = a.groupby("cfg").apply(lambda g: quick_stat(g, col))
        cb = b.groupby("cfg").apply(lambda g: quick_stat(g, col))
        common = ca.dropna().index.intersection(cb.dropna().index)
        if len(common) > 5:
            out.append(stats.spearmanr(ca.loc[common], cb.loc[common])[0])
    return (float(np.mean(out)), len(out)) if out else (np.nan, 0)

# ===========================================================================
rounds = sorted([d for d in os.listdir(BASE) if d.startswith("20")])
round_rows, config_rows = [], []
sh_pool = {"brier": [], "beta_fc": [], "dll": []}

for rd in rounds:
    m = load_round(rd)
    if m is None:
        continue
    lb = m.groupby("cfg").apply(per_config)
    lb["round"] = rd
    lb = lb.reset_index()
    config_rows.append(lb)

    fb = lb[lb.is_fb & lb.N.ge(50)]                 # systematic frontier battery
    agentic = lb[(~lb.is_fb) & lb.N.ge(50)]         # external research/tool systems
    # identity check across the frontier battery
    idf = fb.dropna(subset=["edge", "brier"])
    if len(idf) >= 5:
        rho_id = stats.spearmanr(idf.edge, -idf.brier)[0]
        const_std = float(idf.ref_brier.std())
        # the affine constant c: edge = c - Brier  => c = edge + Brier (per config)
        c_mean = float((idf.edge + idf.brier).mean())
        c_std = float((idf.edge + idf.brier).std())
    else:
        rho_id = const_std = c_mean = c_std = np.nan

    for col in sh_pool:
        v, n = split_half(m[m.cfg.isin(fb.cfg)], col)
        if not np.isnan(v):
            sh_pool[col].append(v)

    fb_dll = fb.dropna(subset=["dll"])
    ag_dll = agentic.dropna(subset=["dll"])
    frontier_cfg = fb_dll.sort_values("brier").head(3)  # 3 best-Brier configs
    round_rows.append({
        "round": rd, "year": round_to_year(rd),
        "n_fb": int(len(fb)), "n_agentic": int(len(agentic)),
        "n_questions": int(m.qid.nunique()),
        "rows_per_cfg_med": int(m.groupby("cfg").size().median()),
        "rho_edge_negbrier": float(rho_id), "ref_brier_std": const_std,
        "c_mean": c_mean, "c_std": c_std,
        "fb_dll_mean": float(fb_dll.dll.mean()) if len(fb_dll) else np.nan,
        "fb_dll_median": float(fb_dll.dll.median()) if len(fb_dll) else np.nan,
        "fb_dll_frontier": float(frontier_cfg.dll.mean()) if len(frontier_cfg) else np.nan,
        "fb_dll_max": float(fb_dll.dll.max()) if len(fb_dll) else np.nan,
        "fb_brier_min": float(fb.brier.min()) if len(fb) else np.nan,
        "agentic_dll_mean": float(ag_dll.dll.mean()) if len(ag_dll) else np.nan,
        "agentic_dll_median": float(ag_dll.dll.median()) if len(ag_dll) else np.nan,
        "agentic_brier_min": float(agentic.brier.min()) if len(agentic) else np.nan,
    })
    print(f"{rd}  fb={len(fb):3d} ag={len(agentic):3d} Q={m.qid.nunique():4d}  "
          f"rho(edge,-Brier)={rho_id:.4f} refBrierSD={const_std:.1e}  "
          f"fb_dLL={round_rows[-1]['fb_dll_mean']:+.4f} "
          f"front={round_rows[-1]['fb_dll_frontier']:+.4f} "
          f"agentic={round_rows[-1]['agentic_dll_mean']:+.4f}")

R = pd.DataFrame(round_rows)
C = pd.concat(config_rows, ignore_index=True)
R.to_csv(os.path.join(OUT, "round_summary.csv"), index=False)
C.to_csv(os.path.join(OUT, "config_round_long.csv"), index=False)

# ---- pooled identity ----
print("\n=== ORDER-EQUIVALENCE ACROSS ROUNDS ===")
print(f"rho(edge,-Brier): min={R.rho_edge_negbrier.min():.4f} "
      f"median={R.rho_edge_negbrier.median():.4f} "
      f"frac==1.000: {(R.rho_edge_negbrier.round(4)>=1.0).mean():.2f}")
print(f"per-config affine constant c=edge+Brier within round: "
      f"max within-round SD = {R.c_std.max():.2e}  (0 => exact edge=c-Brier identity)")

# ---- pooled reliability ----
print("\n=== SPLIT-HALF RANK RELIABILITY (pooled across rounds) ===")
rel = {}
for col in sh_pool:
    a = np.array(sh_pool[col])
    rel[col] = {"mean": float(np.mean(a)), "sd": float(np.std(a)),
                "n_rounds": int(len(a)),
                "ci": [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]}
    print(f"  {col:8s}: {rel[col]['mean']:.2f} +/- {rel[col]['sd']:.2f} "
          f"(n={rel[col]['n_rounds']} rounds, 95% across-round [{rel[col]['ci'][0]:.2f},{rel[col]['ci'][1]:.2f}])")

# ---- the trend: Delta-LL beyond price over time (frontier battery) ----
print("\n=== CONTRIBUTION-BEYOND-PRICE TREND (the open question, answered) ===")
rt = R.dropna(subset=["fb_dll_mean"])
sl, ic, r_, p_, se = stats.linregress(rt.year, rt.fb_dll_mean)
print(f"  FB battery mean Delta-LL vs round-year: slope={sl:+.5f} nats/yr "
      f"(p={p_:.3f}, R^2={r_**2:.3f})  intercept-at-2025={ic+sl*2025:+.5f}")
rtf = R.dropna(subset=["fb_dll_frontier"])
slf, icf, rf_, pf_, sef = stats.linregress(rtf.year, rtf.fb_dll_frontier)
print(f"  FB frontier (3 best) Delta-LL vs year: slope={slf:+.5f} nats/yr (p={pf_:.3f})")
print(f"  FB mean Delta-LL  overall mean={rt.fb_dll_mean.mean():+.5f} nats "
      f"[{rt.fb_dll_mean.min():+.4f},{rt.fb_dll_mean.max():+.4f}]")

# per-MODEL capability axis: Delta-LL vs release date (pool configs across rounds)
cm = C[C.is_fb & C.dll.notna() & C.rel.notna() & C.N.ge(50)].copy()
# average a model config's Delta-LL across the rounds it appears in
cap = cm.groupby("cfg").agg(rel=("rel", "first"), dll=("dll", "mean"),
                            brier=("brier", "mean"), n=("dll", "size")).reset_index()
slc, icc, rc_, pc_, sec = stats.linregress(cap.rel, cap.dll)
print(f"  per-model Delta-LL vs release-year: slope={slc:+.5f} nats/yr "
      f"(p={pc_:.3f}, R^2={rc_**2:.3f}, n_models={len(cap)})")
print(f"  earliest models (<=2024.5) mean dLL={cap[cap.rel<=2024.5].dll.mean():+.5f}; "
      f"latest (>=2026.0) mean dLL={cap[cap.rel>=2026.0].dll.mean():+.5f}")

# agentic group trend
print("\n=== AGENTIC SUBMITTERS (multi-round analogue of humans) ===")
ra = R.dropna(subset=["agentic_dll_mean"])
print(f"  rounds with agentic systems: {len(ra)}  "
      f"mean Delta-LL={ra.agentic_dll_mean.mean():+.5f} nats "
      f"[{ra.agentic_dll_mean.min():+.4f},{ra.agentic_dll_mean.max():+.4f}]")
if len(ra) >= 4:
    sla, ica, raa, paa, sea = stats.linregress(ra.year, ra.agentic_dll_mean)
    print(f"  agentic mean Delta-LL vs year: slope={sla:+.5f} (p={paa:.3f})")

summary = {
    "n_rounds": int(len(R)), "date_span": [rounds[0], rounds[-1]],
    "total_config_rounds": int(len(C)),
    "order_equivalence": {
        "rho_edge_negbrier_min": float(R.rho_edge_negbrier.min()),
        "rho_edge_negbrier_median": float(R.rho_edge_negbrier.median()),
        "frac_rounds_rho_eq_1": float((R.rho_edge_negbrier.round(4) >= 1.0).mean()),
        "max_within_round_c_sd": float(R.c_std.max())},
    "split_half_reliability": rel,
    "dll_trend": {
        "fb_mean_slope_per_yr": float(sl), "fb_mean_slope_p": float(p_),
        "fb_mean_overall": float(rt.fb_dll_mean.mean()),
        "fb_frontier_slope_per_yr": float(slf), "fb_frontier_slope_p": float(pf_),
        "per_model_slope_per_yr": float(slc), "per_model_slope_p": float(pc_),
        "per_model_n": int(len(cap)),
        "early_models_mean_dll": float(cap[cap.rel <= 2024.5].dll.mean()),
        "late_models_mean_dll": float(cap[cap.rel >= 2026.0].dll.mean())},
    "agentic": {
        "n_rounds": int(len(ra)),
        "mean_dll": float(ra.agentic_dll_mean.mean()),
        "min": float(ra.agentic_dll_mean.min()),
        "max": float(ra.agentic_dll_mean.max())},
}
json.dump(summary, open(os.path.join(OUT, "summary_mr.json"), "w"), indent=2, default=float)
cap.to_csv(os.path.join(OUT, "capability_axis.csv"), index=False)
print(f"\nwrote out_mr/round_summary.csv, config_round_long.csv, capability_axis.csv, summary_mr.json")
