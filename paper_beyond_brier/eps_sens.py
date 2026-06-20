#!/usr/bin/env python3
"""epsilon-clipping sensitivity of the bias-corrected Delta-LL trend (reviewer ask).
Recomputes per-config Delta-LL at eps in {1e-2,1e-3,1e-4}, FB battery N>=50, and reports
the bias-corrected battery level + round-level slope at each eps."""
import os, json, glob, re, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, statsmodels.api as sm
from scipy import stats

BASE = "/Users/emizemani/Desktop/predictthefuture/paper_beyond_brier/fb_forecast_sets/forecastbench-processed-forecast-sets"
MARKET = {"manifold", "metaculus", "polymarket", "infer"}
NON_MODEL = ("always", "random uniform", "naive forecaster", "imputed forecaster",
             "public median", "superforecaster median", "llm crowd")
B = sm.families.Binomial()

def rd_year(rd):
    y, m, d = (int(x) for x in rd.split("-")); return y + (m - 1) / 12 + (d - 1) / 365

def load(rd):
    rows = []
    for p in sorted(glob.glob(os.path.join(BASE, rd, "*.json"))):
        try: d = json.load(open(p))
        except Exception: continue
        org, mod = d.get("organization"), d.get("model")
        if org != "ForecastBench" or not mod or any(t in mod.lower() for t in NON_MODEL): continue
        for r in d.get("forecasts", []):
            if r.get("source") not in MARKET or not r.get("resolved"): continue
            y = r.get("resolved_to")
            if y not in (0.0, 1.0): continue
            pr, fc = r.get("market_value_on_due_date"), r.get("forecast")
            if pr is None or fc is None: continue
            try: pr, fc = float(pr), float(fc)
            except Exception: continue
            if not (0 <= fc <= 1): continue
            rows.append({"cfg": f"{org}|{mod}", "qid": str(r["id"]), "pr": pr, "fc": fc, "y": float(y)})
    return pd.DataFrame(rows)

def dll_at(g, eps):
    def lg(p): p = np.clip(p, eps, 1 - eps); return np.log(p / (1 - p))
    y = g.y.values
    if len(g) < 50 or len(np.unique(y)) < 2: return np.nan, len(g)
    try:
        l0 = sm.GLM(y, np.column_stack([np.ones(len(g)), lg(g.pr)]), family=B).fit().llf
        l1 = sm.GLM(y, np.column_stack([np.ones(len(g)), lg(g.pr), lg(g.fc)]), family=B).fit().llf
        return (l1 - l0) / len(g), len(g)
    except Exception:
        return np.nan, len(g)

rounds = sorted(d for d in os.listdir(BASE) if d.startswith("20"))
res = {e: [] for e in (1e-2, 1e-3, 1e-4)}
for rd in rounds:
    m = load(rd)
    if m.empty: continue
    for eps in res:
        adj = []
        for _, g in m.groupby("cfg"):
            d, n = dll_at(g, eps)
            if d == d: adj.append(d - 0.5 / n)
        if len(adj) >= 5:
            res[eps].append((rd_year(rd), float(np.mean(adj))))
print("eps        level(nats)   slope(nats/yr)   p")
for eps in (1e-2, 1e-3, 1e-4):
    a = np.array(res[eps]); lvl = a[:, 1].mean()
    sl, ic, r, p, se = stats.linregress(a[:, 0], a[:, 1])
    print(f"{eps:.0e}   {lvl:+.5f}      {sl:+.5f}        {p:.3f}   (n_rounds={len(a)})")
