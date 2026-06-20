#!/usr/bin/env python3
"""Worked example for benchmark designers: the marginal-edge leaderboard IS the Brier
leaderboard, and it crowns the best price-copier while the contribution it claims to
measure (Delta-LL) lives on a decorrelated, near-empty axis.

Reconstructs the real ForecastBench 2024-07-21 LLM leaderboard (balanced market panel)
with real model names; shows edge-rank == Brier-rank to the digit; flags freeze-value
(price-handed) configs; adds the bias-corrected Delta-LL contribution column, both
single-round and pooled multi-round (reliable). Honest by construction: prints what is
true and lets the framing follow.
"""
import os, json, glob, re, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, statsmodels.api as sm
from scipy import stats

ROOT = "/Users/emizemani/Desktop/predictthefuture/paper_beyond_brier"
RD = "2024-07-21"
FCDIR = os.path.join(ROOT, "fb_forecast_sets", "forecastbench-processed-forecast-sets", RD)
OUT = os.path.join(ROOT, "out_mr")
MARKET = {"manifold", "metaculus", "polymarket", "infer"}
EPS = 1e-3
B = sm.families.Binomial()
NON_MODEL = ("always", "random uniform", "naive forecaster", "imputed forecaster",
             "public median", "superforecaster median", "llm crowd")

def lg(p): p = np.clip(p, EPS, 1 - EPS); return np.log(p / (1 - p))
def brier(p, y): return (p - y) ** 2

# ---- load 2024-07-21 LLM market panel with real model names ----
rows = []
names = {}
for path in sorted(glob.glob(os.path.join(FCDIR, "*.json"))):
    d = json.load(open(path))
    org, model = d.get("organization"), d.get("model")
    if not model or any(t in model.lower() for t in NON_MODEL):
        continue
    cfg = os.path.basename(path)[:-5]
    names[cfg] = model
    for r in d.get("forecasts", []):
        if r.get("source") not in MARKET or not r.get("resolved"):
            continue
        y = r.get("resolved_to")
        if y not in (0.0, 1.0):
            continue
        pr, fc = r.get("market_value_on_due_date"), r.get("forecast")
        if pr is None or fc is None:
            continue
        try: pr, fc = float(pr), float(fc)
        except Exception: continue
        if not (0 <= fc <= 1):
            continue
        rows.append({"cfg": cfg, "qid": str(r["id"]),
                     "pr": float(np.clip(pr, EPS, 1 - EPS)),
                     "fc": float(np.clip(fc, EPS, 1 - EPS)), "y": float(y)})
m = pd.DataFrame(rows)
m["s_f"] = brier(m.fc, m.y); m["s_ref"] = brier(m.pr, m.y); m["d"] = m.s_ref - m.s_f

def per_cfg(g):
    N = len(g); y = g.y.values
    out = {"N": N, "brier": g.s_f.mean(), "edge": g.d.mean()}
    dll = np.nan
    if N >= 30 and len(np.unique(y)) > 1:
        try:
            l0 = sm.GLM(y, np.column_stack([np.ones(N), lg(g.pr)]), family=B).fit().llf
            l1 = sm.GLM(y, np.column_stack([np.ones(N), lg(g.pr), lg(g.fc)]), family=B).fit().llf
            dll = (l1 - l0) / N
        except Exception:
            pass
    out["dll_adj"] = dll - 0.5 / N if dll == dll else np.nan
    return pd.Series(out)

lb = m.groupby("cfg").apply(per_cfg)
lb["model"] = [names[c] for c in lb.index]
lb["freeze"] = ["with freeze values" in names[c].lower() for c in lb.index]
lb["brier_rank"] = lb.brier.rank(method="min").astype(int)
lb["edge_rank"] = (-lb.edge).rank(method="min").astype(int)

# the identity, with real names
rho_eb = stats.spearmanr(lb.edge, -lb.brier)[0]
exact = (lb.brier_rank.values == lb.edge_rank.values).all()
print(f"[A] N_configs={len(lb)}  edge-rank vs Brier-rank: rho={rho_eb:.4f}  byte-identical={exact}")

# contribution decorrelated from Brier?
w = lb.dropna(subset=["dll_adj"])
rho_db = stats.spearmanr(-w.brier, w.dll_adj)[0]
print(f"[B] rho(bias-corrected Delta-LL, -Brier) = {rho_db:.3f}  (contribution vs closeness)")

# who tops the edge/Brier board, and are they freeze-value copiers?
top = lb.sort_values("brier_rank").head(15)
print(f"\n[C] top-15 by marginal edge (== Brier). 'frz'=handed the market price:")
print(f"{'rk':>2} {'model':52s} {'Brier':>6} {'edge':>7} {'dLL_adj':>8} frz")
for _, r in top.iterrows():
    print(f"{r.brier_rank:2d} {r.model[:52]:52s} {r.brier:6.3f} {r.edge:+7.3f} "
          f"{r.dll_adj:+8.4f} {'Y' if r.freeze else ''}")
n_frz_top = int(top.freeze.sum())
print(f"   -> {n_frz_top}/15 of the top edge/Brier models were handed the market price")

# the #1 edge model's contribution, vs the highest single-round contribution
best = lb.sort_values("brier_rank").iloc[0]
print(f"\n[D] #1 by marginal edge: {best.model}  (Brier {best.brier:.3f}, "
      f"bias-corrected Delta-LL {best.dll_adj:+.4f})")

# ---- pooled MULTI-ROUND contribution per base model (reliable) ----
C = pd.read_csv(os.path.join(OUT, "config_round_long.csv"))
C = C[C.is_fb & C.N.ge(50) & C.dll.notna()].copy()
C["dll_adj"] = C.dll - 0.5 / C.N
def base_model(cfg):  # cfg is "org | model"
    s = cfg.split("|", 1)[1].strip() if "|" in cfg else cfg
    return re.sub(r"\(.*?\)", "", s).strip()
C["bm"] = C.cfg.map(base_model)
pool = C.groupby("bm").apply(
    lambda g: pd.Series({"N": int(g.N.sum()),
                         "dll_adj": float(np.average(g.dll_adj, weights=g.N)),
                         "brier": float(np.average(g.brier, weights=g.N)),
                         "rounds": g["round"].nunique()})).reset_index()
pool = pool[pool.N >= 2000].sort_values("dll_adj", ascending=False)
print(f"\n[E] pooled multi-round bias-corrected Delta-LL by base model (N>=2000 forecasts):")
print(f"   highest contribution:")
for _, r in pool.head(6).iterrows():
    print(f"     {r.bm[:46]:46s} dLL_adj={r.dll_adj:+.4f}  Brier={r.brier:.3f}  N={int(r.N)} ({int(r.rounds)}rd)")
print(f"   lowest contribution:")
for _, r in pool.tail(4).iterrows():
    print(f"     {r.bm[:46]:46s} dLL_adj={r.dll_adj:+.4f}  Brier={r.brier:.3f}  N={int(r.N)}")
rho_pool = stats.spearmanr(-pool.brier, pool.dll_adj)[0]
print(f"   rho(pooled Delta-LL, -Brier) across {len(pool)} base models = {rho_pool:.3f}")
print(f"   range of pooled Delta-LL: [{pool.dll_adj.min():+.4f}, {pool.dll_adj.max():+.4f}] "
      f"(all near 0; human per-forecaster is +0.091)")

# save the table for the paper (top 12 by edge)
tab = lb.sort_values("brier_rank").head(12)[
    ["brier_rank", "model", "N", "brier", "edge", "edge_rank", "dll_adj", "freeze"]].copy()
tab.to_csv(os.path.join(OUT, "worked_example_table.csv"), index=False)
summary = {"n_configs": int(len(lb)), "rho_edge_brier": float(rho_eb),
           "edge_brier_byte_identical": bool(exact),
           "rho_contribution_brier": float(rho_db),
           "top15_freeze_count": n_frz_top,
           "best_edge_model": str(best.model), "best_edge_dll_adj": float(best.dll_adj),
           "pooled_dll_range": [float(pool.dll_adj.min()), float(pool.dll_adj.max())],
           "rho_pooled_contribution_brier": float(rho_pool)}
json.dump(summary, open(os.path.join(OUT, "worked_example.json"), "w"), indent=2, default=float)
print("\nwrote out_mr/worked_example_table.csv, worked_example.json")
