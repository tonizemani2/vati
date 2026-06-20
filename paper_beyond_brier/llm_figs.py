#!/usr/bin/env python3
"""Figures for the honest revision. Reads out_llm/*v2*. Writes out_llm/*.png."""
import os, json
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = "/Users/emizemani/Desktop/predictthefuture/paper_beyond_brier/out_llm"
lb = pd.read_csv(os.path.join(OUT, "llm_leaderboard_v2.csv"), index_col=0)
S = json.load(open(os.path.join(OUT, "summary_llm_v2.json")))
old = pd.read_csv(os.path.join(OUT, "llm_leaderboard.csv"))  # has mean_brier, edge
plt.rcParams.update({"font.size": 9, "figure.dpi": 150})

# human Delta-LL beyond price (computed in-text): pooled supers, super-median ensemble
H_POOLED, H_MED = 0.080, 0.126
LLM_MEAN = float(S["C2_delta_ll"]["mean_per_row_nats"])

# ---- Figure 1: the two negatives ----
fig, ax = plt.subplots(1, 2, figsize=(8.4, 3.5))
# (a) identity edge = const - Brier
ax[0].scatter(old.mean_brier, old.edge, s=14, alpha=.7, color="#444")
ax[0].set_xlabel("mean Brier (per configuration)"); ax[0].set_ylabel("mean marginal edge")
ax[0].set_title("(a) Edge is Brier in disguise\n"r"edge $=$ const $-$ Brier, $\rho=1.000$")
# (b) split-half rank reliability: only Brier ranks
labels = ["Brier", r"$\beta_{\rm fc}$", r"$\Delta$LL"]
vals = [S["stability_split_half_rho"]["brier"][0],
        S["stability_split_half_rho"]["beta_fc"][0],
        S["stability_split_half_rho"]["delta_ll"][0]]
errs = [S["stability_split_half_rho"]["brier"][1],
        S["stability_split_half_rho"]["beta_fc"][1],
        S["stability_split_half_rho"]["delta_ll"][1]]
bars = ax[1].bar(labels, vals, yerr=errs, color=["#444", "#b03a2e", "#b03a2e"],
                 capsize=4, width=.6)
ax[1].axhline(0.8, ls="--", lw=.8, color="grey")
ax[1].text(2.3, 0.82, "usable\nranking", fontsize=7, color="grey", ha="right")
ax[1].set_ylim(0, 1.05); ax[1].set_ylabel("split-half rank reliability")
ax[1].set_title("(b) Only Brier ranks reliably\nthe encompassing statistics do not")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_negatives.png"), bbox_inches="tight")
plt.close(fig)

# ---- Figure 2: the positive + the exposed confound ----
fig, ax = plt.subplots(1, 2, figsize=(8.6, 3.6))
# (a) Delta-LL beyond price: LLMs ~0 vs superforecasters
xj = np.random.default_rng(0).normal(0, 0.05, len(lb))
ax[0].scatter(xj, lb.dll, s=12, alpha=.6, color="#777", label="130 LLM configs")
ax[0].scatter([0], [LLM_MEAN], s=60, marker="D", color="#222", zorder=5, label="LLM mean")
ax[0].scatter([1], [H_POOLED], s=60, marker="s", color="#1f6f4f", zorder=5, label="superforecasters (pooled)")
ax[0].scatter([1], [H_MED], s=60, marker="^", color="#1f6f4f", zorder=5, label="super-median ensemble")
ax[0].axhline(0, lw=.6, color="grey")
ax[0].set_xticks([0, 1]); ax[0].set_xticklabels(["LLMs", "humans"])
ax[0].set_ylabel(r"$\Delta$LL beyond the price (nats/forecast)")
ax[0].set_title("(a) Who adds information beyond the price?\nLLMs $\\approx 0$; superforecasters do")
ax[0].legend(fontsize=6.5, loc="upper left")
# (b) copy-the-market: raw beta_fc drops (confound) but Delta-LL flat
fst = S["copy_the_market"]["family_sign_tests"]
groups = ["|p$-$p_ref|\n(copying)", "Brier", r"raw $\beta_{\rm fc}$", r"$\Delta$LL"]
meds = [fst["dAbsdev"][1], fst["dBrier"][1], fst["dBeta"][1], fst["dDLL"][1]]
cols = ["#777", "#777", "#b03a2e", "#1f6f4f"]
ax[1].bar(groups, meds, color=cols, width=.6)
ax[1].axhline(0, lw=.6, color="grey")
ax[1].set_ylabel("family-median change when handed the price")
ax[1].set_title("(b) Copy-the-market: the price drop is real,\n"
                r"the raw $\beta_{\rm fc}$ drop is collinearity ($\Delta$LL flat)")
ax[1].tick_params(axis="x", labelsize=7.5)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_positive.png"), bbox_inches="tight")
plt.close(fig)
print("wrote fig_negatives.png, fig_positive.png")
