#!/usr/bin/env python3
"""Multi-round figures. Reads out_mr/*. Writes out_mr/fig_trend.png, fig_robust.png."""
import os, json
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from scipy import stats

OUT = "/Users/emizemani/Desktop/predictthefuture/paper_beyond_brier/out_mr"
R = pd.read_csv(os.path.join(OUT, "round_summary.csv"))
C = pd.read_csv(os.path.join(OUT, "config_round_long.csv"))
cap = pd.read_csv(os.path.join(OUT, "capability_axis.csv"))
S = json.load(open(os.path.join(OUT, "summary_mr.json")))
plt.rcParams.update({"font.size": 9, "figure.dpi": 150})

GREY, RED, GREEN, INK = "#888", "#b03a2e", "#1f6f4f", "#222"
H_POOLED, H_MED = 0.080, 0.126          # single-round superforecaster references

# bias-corrected revision inputs
RT = pd.read_csv(os.path.join(OUT, "round_trend_rev.csv"))
CAPr = pd.read_csv(os.path.join(OUT, "capability_axis_rev.csv"))
SR = json.load(open(os.path.join(OUT, "summary_rev.json")))
H_PERF, H_LO, H_HI = 0.091, 0.060, 0.124      # per-forecaster bias-corrected + 95% CI
H_DATE = 2024.55
Ra = R.dropna(subset=["agentic_dll_mean"]).copy()
Ra = Ra.merge(RT[["round"]], on="round", how="inner") if "round" in Ra else Ra

# ============================================================================
# Figure: contribution beyond price over 2 years, finite-sample-bias corrected
# ============================================================================
fig, ax = plt.subplots(1, 2, figsize=(9.2, 3.8))

# (a) per-round bias-corrected Delta-LL over time, vs the single-round human point
ax[0].axhline(0, lw=0.6, color="grey")
# raw (faded) to show the bias that the correction removes
ax[0].scatter(RT.year, RT.dll_raw, s=18, color="#ccc", edgecolor="none", zorder=2,
              label="raw (in-sample) battery mean")
ax[0].errorbar(RT.year, RT.dll_adj, yerr=RT.dll_adj_se, fmt="o", ms=4.5, color=INK,
               ecolor=GREY, elinewidth=0.8, capsize=2, lw=0, zorder=3,
               label="bias-corrected battery mean")
xs = np.linspace(RT.year.min(), RT.year.max(), 50)
b1, b0 = np.polyfit(RT.year, RT.dll_adj, 1)
sl = SR["trend_adj"]["slope"]; clo, chi = SR["trend_adj"]["ci"]
ax[0].plot(xs, b0 + b1 * xs, color=INK, lw=1.3,
           label=f"corrected trend {sl:+.4f}/yr\n95%CI [{clo:+.4f},{chi:+.4f}]")
# single-round human point with CI (not a line)
ax[0].errorbar([H_DATE], [H_PERF], yerr=[[H_PERF - H_LO], [H_HI - H_PERF]], fmt="D",
               ms=7, color=GREEN, ecolor=GREEN, elinewidth=1.1, capsize=3, zorder=5)
ax[0].text(H_DATE + 0.04, H_PERF, "human superforecasters\n(single round, bias-corrected)",
           fontsize=6.5, color=GREEN, va="center")
ax[0].set_ylim(-0.012, 0.135)
ax[0].set_xlabel("round date"); ax[0].set_ylabel(r"$\Delta$LL beyond the price (nats/forecast)")
ax[0].set_title("(a) Bias-corrected contribution is $\\approx$0\nand does not rise over two years")
ax[0].xaxis.set_major_locator(MaxNLocator(5))
ax[0].legend(fontsize=6.0, loc="upper right", framealpha=0.9)

# (b) capability axis: per-model bias-corrected Delta-LL vs release date
ax[1].scatter(CAPr.rel, CAPr.dll_adj, c=CAPr.rel, cmap="viridis", s=15, alpha=0.7,
              edgecolor="none")
b1c, b0c = np.polyfit(CAPr.rel, CAPr.dll_adj, 1)
xs2 = np.linspace(CAPr.rel.min(), CAPr.rel.max(), 50)
slc = SR["capability_adj"]["slope"]; cl, ch = SR["capability_adj"]["cluster_ci"]
ax[1].plot(xs2, b0c + b1c * xs2, color=INK, lw=1.3,
           label=(f"slope {slc:+.4f}/yr\nbase-clustered 95%CI\n[{cl:+.4f},{ch:+.4f}]"))
e = SR["capability_adj"]["early_mean"]; l = SR["capability_adj"]["late_mean"]
ax[1].axhspan(H_LO, H_HI, color=GREEN, alpha=0.12, zorder=0)
ax[1].axhline(H_PERF, ls="--", lw=0.9, color=GREEN)
ax[1].text(CAPr.rel.min(), H_PERF + 0.004, "human superforecasters", fontsize=6.6, color=GREEN)
ax[1].annotate(f"≤2024.5: {e:+.4f}", (2023.5, 0.045), fontsize=6.4, color=INK)
ax[1].annotate(f"≥2026: {l:+.4f}", (2025.4, 0.045), fontsize=6.4, color=INK)
ax[1].axhline(0, lw=0.6, color="grey")
ax[1].set_ylim(-0.03, 0.135)
ax[1].set_xlabel("model release date (year)"); ax[1].set_ylabel(r"$\Delta$LL beyond the price (nats)")
ax[1].set_title("(b) Capability axis: scale does not\nbuy information beyond the price")
ax[1].legend(fontsize=6.0, loc="upper right", framealpha=0.9)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_trend.png"), bbox_inches="tight")
plt.close(fig)

# ============================================================================
# Figure: multi-round robustness -- identity to machine precision + reliability
# ============================================================================
fig, ax = plt.subplots(1, 2, figsize=(8.6, 3.5))

# (a) the affine constant c = edge + Brier has ~0 within-round spread, every round
Ri = R.dropna(subset=["c_std"]).copy()
cstd = np.maximum(Ri.c_std.values, 1e-18)
ax[0].scatter(Ri.year, cstd, s=26, color=GREY, edgecolor=INK, lw=0.4, zorder=3)
ax[0].set_yscale("log")
ax[0].axhline(1e-3, ls="--", lw=0.9, color=RED)
ax[0].text(Ri.year.min(), 1.4e-3, "Brier-rank resolution ($10^{-3}$)", fontsize=6.8, color=RED)
ax[0].set_ylim(1e-18, 1e-2)
ax[0].set_xlabel("round date")
ax[0].xaxis.set_major_locator(MaxNLocator(5))
ax[0].set_ylabel(r"within-round SD of $c=$ edge $+$ Brier")
ax[0].set_title(f"(a) edge $=c-$Brier to machine precision,\nall {int((R.rho_edge_negbrier.round(4)>=1).sum())} rounds "
                r"($\rho=1.000$)")

# (b) pooled split-half rank reliability with across-round CI
rel = S["split_half_reliability"]
labels = ["Brier", r"$\beta_{\rm fc}$", r"$\Delta$LL"]
keys = ["brier", "beta_fc", "dll"]
means = [rel[k]["mean"] for k in keys]
los = [rel[k]["mean"] - rel[k]["ci"][0] for k in keys]
his = [rel[k]["ci"][1] - rel[k]["mean"] for k in keys]
ax[1].bar(labels, means, yerr=[los, his], color=[INK, RED, RED], capsize=4, width=0.6)
ax[1].axhline(0.8, ls="--", lw=0.8, color="grey")
ax[1].text(2.35, 0.82, "usable\nranking", fontsize=7, color="grey", ha="right")
ax[1].set_ylim(0, 1.05)
ax[1].set_ylabel("split-half rank reliability")
ax[1].set_title(f"(b) Only Brier ranks reliably across\n{rel['brier']['n_rounds']} rounds (95% across-round CI)")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_robust.png"), bbox_inches="tight")
plt.close(fig)
print("wrote out_mr/fig_trend.png, out_mr/fig_robust.png")
