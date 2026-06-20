# Beyond Brier: A Marginal-Edge Skill Score for Forecasting, and What It Does to a Leaderboard
### With a leak-free human demonstration and a pre-registered protocol for language models

**Toni Zemani**

---

## Abstract

Probabilistic forecasters, increasingly large language models (LLMs), are ranked almost entirely on the Brier score and on accuracy against a crowd. We argue this practice ranks the wrong quantity: it rewards a forecaster for being right about questions whose answers are *already public*. A model can post a near-superforecaster Brier score by reproducing a prediction-market price or crowd median while contributing no information beyond it. We formalize the omitted quantity. The **marginal edge** of a forecaster is the information it adds over the strongest freely-available prior, scored per question with a strictly proper rule and decomposed, via a forecast-encompassing regression, into a *priced* component (recoverable from the prior) and an *unpriced* component (the forecaster's own contribution). We rank by a difference of proper scores rather than the biased skill-score ratio. We then show, both as a simple identity and on data, that ranking by marginal edge reorders a leaderboard *only* when the reference prior is informative and question-varying; under a constant prior it collapses to a monotone transform of Brier. We demonstrate the metric on the one public, leak-free slice of ForecastBench for which per-question forecasts, priors, and outcomes coincide: 540 human forecasters, 2024-07-21 round. On market-sourced questions, a difficulty-adjusted forecaster effect reorders the 23 rankable superforecasters against their Brier ranking (Spearman ρ = 0.66, p < 0.001; robust to the log score, ρ = 0.61), and a question-clustered encompassing regression shows superforecasters carry information beyond the market price (β_fc > 0, p ≈ 0.005) though the price itself adds little incremental signal for them. On data-sourced questions, where no informative prior exists, the ranking is unchanged by construction. We are deliberate about scope: only 7 of 23 forecasters have an edge distinguishable from zero after multiplicity control, individual rank positions are not stable at this sample size, and per-question LLM forecasts are not public, so we cannot recompute the LLM leaderboard. We therefore **pre-register** the LLM-leaderboard reordering as a forward hypothesis with a fixed instrument, to be evaluated on future ForecastBench rounds and on live submissions to Metaculus and Prophet Arena. The claim is narrow and falsifiable: the field ranks on a quantity it does not want, and a better one is well-defined and computable.

---

## 1. Introduction

Language models now produce probabilistic forecasts at scale, and the community evaluates them with a small set of headline metrics: the Brier score (Brier, 1950), sometimes the logarithmic score, and accuracy or calibration against a human crowd (Halawi et al., 2024; Karger et al., 2024; Lu, 2025). These metrics are proper, interpretable, and comparable. They are also, we argue, the wrong thing to *rank* on.

The problem is the absence of a reference. A proper score measures how close a forecast is to the truth. But on many questions the truth is, in probability terms, *already public*: a liquid prediction market or a large crowd has already moved the implied probability close to where it will resolve. On such a question, a forecaster who reads the market and reports it scores almost as well as one who reasoned to the same number independently, and better than one who reasoned independently to a slightly different, slightly worse number that nonetheless carried new information. Brier rewards the copyist over the contributor. This failure mode is not hypothetical for LLMs: when models are given the market's freeze value as context, they learn to track it closely, inflating Brier without adding independent skill.[^copy]

[^copy]: The "copy-the-market" phenomenon is discussed in ForecastBench-related commentary (Karger et al., 2024) and associated Forecasting Research Institute writing. We use it only as motivation; the specific correlation figures sometimes quoted should be verified against the primary source before any load-bearing citation.

The quantity that distinguishes forecasters is therefore not their score but their score *relative to the best thing one could have known for free*. We call this the **marginal edge**: the calibrated information a forecaster adds beyond a reference prior, where the reference is the strongest freely-available prior per question, a market price where one exists and a crowd median otherwise.

This is not a new scoring rule. Measuring improvement over a reference is the half-century-old *skill score* (Murphy, 1973; Jolliffe & Stephenson, 2012), and meteorology has long known the *choice* of reference is consequential (Mason, 2004). Our contribution is to (i) take the reference to be the strongest freely-available prior rather than the usual climatology; (ii) score it per question and decompose it into priced and unpriced components; and (iii) show, as an identity and in data, that this reordering is real where an informative prior exists.

We are explicit about a limitation that shapes the paper. The natural target, recomputing the *LLM* leaderboard under marginal edge, is not possible from public data: ForecastBench releases per-question forecasts only for human forecasters on a single round. We therefore demonstrate the metric where the data exist (humans) and pre-register the LLM result as a forward, falsifiable prediction (Section 5). Not claiming what we cannot yet show is part of the contribution.

**Contributions.**
1. A definition of *marginal edge* over the strongest freely-available prior, ranked by a difference of strictly proper scores, with a priced/unpriced decomposition (Section 3).
2. An elementary reordering result: the metric reranks a leaderboard iff the prior is informative and question-varying (Section 3.3). It is an existence claim, with magnitude an empirical question.
3. A leak-free demonstration on public ForecastBench human data: a difficulty-adjusted reorder on market questions that survives the log score, with full disclosure of its statistical fragility (Section 4).
4. A pre-registered instrument and protocol for the LLM-leaderboard reordering, to be evaluated forward (Section 5).

---

## 2. Related Work

**Skill scores and the choice of reference.** The Brier Skill Score, BSS = 1 − BS/BS_ref, is the canonical "improvement over a baseline" (Jolliffe & Stephenson, 2012). Murphy (1973) decomposed the Brier score into reliability, resolution, and uncertainty, isolating skill (resolution) above the climatological base rate; Murphy & Winkler (1987) gave the general calibration–refinement framework. The reference in this tradition is almost always *statistical*: climatology, the base rate, or a random walk (Lehmann, 2023). Mason (2004) showed the choice is not innocent, since the expected skill score against climatology is biased. Wheatcroft (2019) showed the ratio form is itself biased and small-sample-fragile, and recommended reporting the underlying scores or their differences, which we do.

**Proper scoring and calibration.** That a marginal-information metric be built on a strictly proper rule, to remain incentive-compatible, follows from Gneiting & Raftery (2007); the unpriced edge is, in the language of Gneiting, Balabdaoui & Raftery (2007), the calibrated sharpness a forecaster adds beyond the prior. DeGroot & Fienberg (1983) supply the calibration-vs-refinement decomposition behind our recalibration check.

**Edge over the crowd in human forecasting.** Tetlock's Good Judgment Project defined forecaster value as improvement over the crowd (Mellers et al., 2014, 2015); the information-diversity view of aggregation (Satopää et al., 2014) explains why a *less accurate* forecaster can still hold information not in the crowd, which is exactly the unpriced edge. Atanasov et al. (2017) compared market prices against poll aggregates as alternative crowds, motivating our preference for a market price as the prior where available.

**LLM forecasting evaluation.** This literature reports near-exclusively absolute Brier or accuracy against a crowd. Halawi et al. (2024) evaluate a retrieval-augmented system against the crowd aggregate; Karger et al. (2024) introduce ForecastBench, ranking on a difficulty-adjusted Brier; Schoenegger & Park (2023) find GPT-4 below the crowd; Lu (2025) reports o3 beating the crowd on Brier but far short of superforecasters. In each, the crowd is a *comparison target*, not a per-question reference against which skill is scored.

**Market-as-reference: the nearest prior art.** We are not the first to use a market baseline, and the idea of "edge over the priced consensus" is not ours. Prophet Arena (Yang et al., 2025) instantiates an explicit market baseline, reports model advantage over it, down-weights low-discrimination (already-priced) questions via an IRT model, and adds a market-return axis. The AIA Forecaster (Alur et al., 2025) uses market prices as the baseline and frames LLM value as information that diversifies a market ensemble, essentially the unpriced component. **We concede the concept of edge-over-market to this work.** Our delta is narrower and we state it as such: we collapse these separate axes into a *single ranked, strictly proper, per-question* edge scalar; we add the forecast-encompassing decomposition that separates priced from unpriced skill at the forecaster level; and we study what that scalar does to the *order* of a leaderboard, including the difficulty-adjustment that a raw edge requires. The reader should weigh this contribution against Prophet Arena specifically. It is a methodological consolidation plus a human-data existence proof, not a new idea of market-relative scoring.

---

## 3. The Marginal-Edge Metric

### 3.1 Setup

Questions are indexed $i \in \{1,\dots,N\}$. Question $i$ has a binary outcome $y_i \in \{0,1\}$ (categorical/ordinal cases extend via the ranked-probability and log scores), a **reference prior** $p^{\mathrm{ref}}_i \in (0,1)$ that is a market price or crowd median at a *pre-fixed* snapshot $t^{*}$, and a forecaster prediction $p_i \in (0,1)$. We use the Brier score $S(p,y)=(p-y)^2$ as the primary rule and the log score $S(p,y)=-[y\ln p+(1-y)\ln(1-p)]$ (clipped at $\epsilon=10^{-3}$) as a reported robustness check.

### 3.2 Per-question edge and the leaderboard metric

The per-question marginal contribution of forecaster $f$ is the score difference
$$ d_i^f \;=\; S\!\left(p^{\mathrm{ref}}_i, y_i\right) - S\!\left(p^f_i, y_i\right), $$
positive when $f$ beats the prior on question $i$. We rank by an aggregate of these differences rather than the skill-score *ratio* $1-\sum_i S(p^f_i,y_i)/\sum_i S(p^{\mathrm{ref}}_i,y_i)$, which is biased and small-sample-fragile (Wheatcroft, 2019); the difference of two proper scores at the same outcome retains proper incentives in $p^f$ (the reference term is exogenous to the forecaster).

**Cross-forecaster comparability requires difficulty adjustment.** A naive ranking by each forecaster's mean $\overline d^{\,f}=\frac1{N_f}\sum_{i\in\mathcal Q_f} d_i^f$ is confounded: forecasters answer *different* question subsets $\mathcal Q_f$, so a high mean can reflect an easier or more-contested question mix rather than more skill. We therefore rank by the **difficulty-adjusted forecaster effect** $\hat\alpha_f$ from a crossed two-way model over the per-question edges,
$$ d_i^f \;=\; \mu + \alpha_f + \gamma_i + \varepsilon_{i}^{f}, $$
with forecaster effects $\alpha_f$ and question effects $\gamma_i$ (estimated by two-way fixed effects, cross-checked against a mixed model with a question random effect). $\hat\alpha_f$ is the edge net of question difficulty and is the headline statistic; the naive $\overline d^{\,f}$ is reported only to expose the confound it carries. We attach percentile bootstrap intervals over questions ($B=10^4$) and test $H_0:\alpha_f=0$ per forecaster (Diebold–Mariano with the Harvey–Leybourne–Newbold small-sample correction; Diebold & Mariano, 1995; Harvey et al., 1997), controlling the false discovery rate across forecasters with Benjamini–Hochberg (1995).

### 3.3 An observation on reordering

The metric earns its keep only if it changes the order, and it does so under a precise condition.

**Observation.** *If the reference prior is constant across questions, $p^{\mathrm{ref}}_i\equiv c$, then ranking by mean edge is identical to ranking by mean Brier. If the prior varies and is informative, there exist configurations under which the two orderings disagree.*

The first half is an identity: with $p^{\mathrm{ref}}_i\equiv c$, $\overline d^{\,f}=\big[\frac1{N_f}\sum_i (c-y_i)^2\big]-\overline{\mathrm{Brier}}_f$, and the bracket is forecaster-independent on a fixed question set, so $\overline d^{\,f}$ is a monotone transform of mean Brier and the ranking is preserved. The second half is an existence claim (a two-question example with $p^{\mathrm{ref}}$ near-certain on one question and near-even on the other suffices), and it says nothing about magnitude. *How much* a real leaderboard reorders is an empirical question (Section 4). The practical reading: a leaderboard can reorder under marginal edge only to the extent the reference prior is informative and question-varying, which is why the climatology-anchored skill-score tradition never surfaced the effect.

### 3.4 Priced vs. unpriced decomposition

To separate skill a forecaster *adds* from skill it *echoes*, we use a forecast-encompassing regression (Fair & Shiller, 1990; Clements, 2010): in logit space, over questions,
$$ y_i \;=\; \Lambda\!\left(\beta_0 + \beta_{\mathrm{ref}}\, z^{\mathrm{ref}}_i + \beta_{\mathrm{fc}}\, z^{f}_i\right),\qquad z=\mathrm{logit}(p). $$
$\beta_{\mathrm{fc}}=0$ means the prior encompasses the forecaster (no unpriced edge); $\beta_{\mathrm{fc}}>0$ means information not in the price; $\beta_{\mathrm{ref}}\to0$ with large $\beta_{\mathrm{fc}}$ means the forecaster dominates the prior. Because the same outcome $y_i$ is shared across all forecasters on a question, residuals are clustered by question, and we report **question-clustered standard errors** rather than the badly understated i.i.d. ones.

### 3.5 What we report

For every headline claim we report: the difficulty-adjusted $\hat\alpha_f$ ranking and its Spearman/Kendall correlation with the Brier ranking; the same under the log score; bootstrap intervals and the count of forecasters whose edge is distinguishable from zero; a rank-stability bootstrap; FDR-controlled significance; question-clustered SEs for the decomposition; and an out-of-sample recalibration with an explicit estimator-noise floor.

---

## 4. Empirical Demonstration on Public ForecastBench Data

### 4.1 Data and the leak-free scope

ForecastBench (Karger et al., 2024) is the natural substrate: each question carries a `freeze_datetime_value` (the prior), each resolution a `resolved_to` outcome, and the benchmark ranks ~214 forecasters. Two facts bound what is honestly computable. First, **per-question raw forecasts are public only for human forecasters on the 2024-07-21 round**: 40 superforecasters and 500 public forecasters; the LLM leaderboard's scores are multi-round adjusted aggregates that cannot be recomputed from public files. Second, `freeze_datetime_value` is a genuine probability prior only for **market** sources (manifold, metaculus, polymarket, infer); for **data** sources (acled, fred, dbnomics, wikipedia, yfinance) it is a raw series level. We therefore split into a **market track** (informative prior) and a **data track** (no informative prior; constant prior $p^{\mathrm{ref}}\equiv0.5$, the most defensible choice absent a series-to-probability model, a limitation we return to in Section 7), and use only as-submitted forecasts, leak-free by ForecastBench's forward design.

Joining questions, forecasts, and resolutions on native ids gives a 100% prior-match rate, a 60.4% resolution-match rate (the remainder unresolved long-horizon questions), 292 malformed non-probability values dropped, and **33,271 binary rows**: 3,670 on the market track and 29,601 on the data track. **The market track is sparse**: of 540 human forecasters, only 23 superforecasters answer $\ge 20$ market questions and are rankable; no public forecaster qualifies. We name this selection plainly: the market result is about 23 superforecasters, not the full field. As a join sanity check, our median-ensemble Brier reproduces the published order (superforecaster median beats public median: market 0.084 vs 0.122; data 0.122 vs 0.158; published dataset-half 63.8 vs 59.3).

### 4.2 The leaderboard reorders on market questions, but only after difficulty adjustment

A *naive* ranking by mean edge reorders against Brier at Spearman ρ = 0.358 (p = 0.094), but this is confounded: mean edge correlates with mean Brier at R² = 0.38 (edge and Brier are mechanically linked) while showing no association with a difficulty proxy alone (edge vs mean $|p^{\mathrm{ref}}-0.5|$, R² = 0.008). The honest statistic is the **difficulty-adjusted forecaster effect** $\hat\alpha_f$. Ranking by $\hat\alpha_f$:

- reorders against Brier at **Spearman ρ = 0.66 (p = 0.0006)**, a moderate but significant reorder (≈ 56% of rank variance reshuffled). Two-way fixed effects and a question-random-effect mixed model agree at ρ = 0.99, so the estimate is not an artifact of the estimator.
- **survives the log score**: log-edge vs log-loss ρ = 0.61 (p = 0.002); the conclusion is not a Brier artifact.

Difficulty adjustment *reduces* the apparent reorder relative to the naive ρ = 0.358, because part of the naive reorder was question selection (exactly the confound the metric warns of), while putting the surviving reorder on firm statistical footing. We do **not** report individual rank-swap anecdotes: a rank-stability bootstrap (resampling questions, $B=10^4$) gives a Spearman distribution with mean 0.35 and 95% interval [0.07, 0.64], and individual forecasters' 90% rank intervals span 10–18 of 23 positions. The reorder is a property of the ranking, not of any one forecaster's position.

We are explicit about power: only **7 of 23** forecasters have a bootstrap 95% edge interval strictly above zero (16 straddle zero, none strictly negative), and all 7 survive Benjamini–Hochberg FDR control at q = 0.10. The reorder is therefore best read as *a reshuffling among the forecasters who have a resolvable edge*, on a single round of 56 market questions: an existence proof, not a powered population claim. The powered claim is pre-registered (Section 5). The figure `out/fig_reordering.png` shows the rank movement.

### 4.3 The data track is an identity check, not a result

On the data track, ranking by edge equals ranking by Brier exactly (ρ = 1.000), because a constant prior forces $\mathrm{edge}=0.25-\overline{\mathrm{Brier}}$ (verified to machine precision). This is the first half of the Observation evaluated on data, a numerical consistency check that the implementation respects the identity rather than an empirical finding. We report it as such.

### 4.4 Who has unpriced edge: the decomposition

The forecast-encompassing regression with question-clustered SEs separates contributors from echoers. Pooled over superforecasters (market), the forecaster term is positive and significant ($\beta_{\mathrm{fc}}=0.62$, clustered p=0.005) while the **price term is not** ($\beta_{\mathrm{ref}}=0.18$, clustered p=0.58): on this set, superforecasters carry information beyond the market and the market adds little incremental signal to them. Pooled over *all* forecasters the picture inverts: $\beta_{\mathrm{ref}}=0.73$ (p=0.0009) dominates while $\beta_{\mathrm{fc}}=0.18$ (p=0.001) is small, so the average forecaster mostly tracks the price. We stress that question clustering inflates these p-values by 10–12 orders of magnitude relative to the i.i.d. SEs a naive fit would report; the directional conclusion ("superforecasters carry unpriced edge") survives, the spurious precision does not.

We attempted to net out miscalibration via out-of-sample isotonic recalibration, but report it as inconclusive: the observed shrink in mean edge (0.034 → 0.006) is only 1.6× the spurious shrink that the same procedure produces on synthetic *perfectly-calibrated* forecasters at matched sample size (0.017 ± 0.005), so roughly 60% of it is small-$N$ estimator noise. We therefore do **not** claim the raw edge is "mostly miscalibration"; at this $N$ the recalibrated edge is uninterpretable.

---

## 5. Pre-Registered Forward Protocol

Because the LLM leaderboard cannot be recomputed from public data today, we register the LLM result as a forward, falsifiable prediction. We fix the following before outcomes are known, in the spirit of the Good Judgment Project's pre-specified design and Registered-Report practice (Center for Open Science), and we deposit this section as a timestamped, immutable pre-registration (OSF DOI to be inserted on deposit) whose analysis instrument is the released `compute_edge.py` / `revise_edge.py`, run unmodified.

**Hypothesis H1.** On future resolved ForecastBench rounds (and any benchmark publishing per-question LLM forecasts, priors, and outcomes), ranking LLM forecasters by the difficulty-adjusted marginal edge over the market prior reorders the leaderboard relative to the Brier ranking, with Spearman ρ < 0.9 on the market-question subset.

**Hypothesis H2.** Forecasters whose Brier advantage concentrates on high-certainty (already-priced) questions fall under the edge ranking; forecasters with significant $\beta_{\mathrm{fc}}$ rise.

**Fixed in advance:** (i) inclusion rule (market sources, binary, resolved); (ii) prior snapshot $t^{*}$ (the round freeze datetime); (iii) scoring rule (Brier primary, log secondary); (iv) primary statistic (the difficulty-adjusted $\hat\alpha_f$ with bootstrap CI and rank-stability bootstrap); (v) the clustered encompassing decomposition; (vi) FDR level 0.10.

**Live commitment.** The author maintains live forward submissions to Metaculus and Prophet Arena. Because these forecasts are made before outcomes are known, they constitute a leak-free prospective test of H1–H2 once a sufficient number resolve (target and horizon fixed in the OSF deposit). We make no claim about the author's own standing in advance of resolution; the design, not the result, is the present contribution.

---

## 6. Discussion

The field's practice answers *"which forecaster is closest to the truth?"* The question that determines whether a forecaster is worth consulting is *"which forecaster knows something the free prior does not?"* These coincide only when no informative free prior exists. As markets and large crowds cover more of the question space, and as LLMs are increasingly handed those priors as context, the gap widens, and a Brier leaderboard increasingly ranks fluency at copying over capacity to contribute. The moderate human reorder we measure is the visible symptom; the copy-the-market behavior reported for LLMs is the same effect in a more acute form.

A marginal-edge metric also changes incentives, not just rankings. Under Brier, the optimal move on a well-priced question is to echo the price; under marginal edge that move scores zero, and the only way to rank is to find questions where one genuinely knows more. That is the property a benchmark should reward if its purpose is to identify forecasters that add decision value rather than re-derive consensus.

We are deliberately narrow. We do not claim our metric is uniquely correct, nor that Brier should be discarded, since it is the proper rule from which the edge is built. We claim that *ranking* on absolute Brier reports a quantity the field does not want; that a better quantity is well-defined, strictly proper, and computable; and that where an informative prior exists, the reorder it induces is real, if on the one round we can see modest and statistically fragile.

---

## 7. Limitations

1. **Single round, humans only.** The entire demonstration is the 2024-07-21 ForecastBench human round; LLMs are excluded because their per-question forecasts are not public. The reorder is *shown* for human superforecasters and *predicted* for LLMs (Section 5).
2. **Power and stability.** The market track has 23 rankable forecasters and 56 questions; only 7 forecasters have an edge distinguishable from zero (FDR q = 0.10), the rank-stability bootstrap interval on ρ nearly reaches zero ([0.07, 0.64]), and individual rank positions are not identifiable. This is an existence proof, not a population estimate.
3. **No common-question core.** No market question was answered by all 23 forecasters (the $\ge 18$-forecaster core has 6 questions), so a common-core robustness check is degenerate; the difficulty-adjusted forecaster effect is the substitute, but it cannot fully escape the sparsity.
4. **Differential dropout.** Resolved market questions are significantly *easier* than unresolved ones (mean $|p^{\mathrm{ref}}-0.5|$ 0.33 vs 0.25; Mann–Whitney p = 0.018), so the analyzed sample is a non-random, easier subset, which likely inflates measured edge.
5. **Single-snapshot, data-track-constant priors.** The prior is one freeze-time value with no path or uncertainty; the data-track constant prior is a modeling choice (no series-to-probability model), which is what forces the identity in the data track.
6. **Recalibration inconclusive** at this sample size (≈ 60% of the shrink is estimator noise).
7. **Nearest prior art overlaps.** Prophet Arena and the AIA Forecaster already use a market baseline; our contribution is the consolidation into a single per-question proper edge scalar with a clustered priced/unpriced decomposition and the difficulty-adjusted reordering analysis, not the idea of market-relative scoring.

**Reproducibility.** All numbers in Section 4 are produced by `compute_edge.py` and `revise_edge.py` from public ForecastBench data (CC BY-SA 4.0); outputs in `out/`. These scripts are the pre-registered instrument for Section 5.

---

## References

Alur, R., et al. (2025). *AIA Forecaster: Technical Report.* arXiv:2511.07678.

Atanasov, P., Mellers, B., Tetlock, P., et al. (2017). Distilling the Wisdom of Crowds: Prediction Markets vs. Prediction Polls. *Management Science.*

Benjamini, Y., & Hochberg, Y. (1995). Controlling the False Discovery Rate. *Journal of the Royal Statistical Society B*, 57(1), 289–300.

Brier, G. W. (1950). Verification of Forecasts Expressed in Terms of Probability. *Monthly Weather Review*, 78(1), 1–3.

Clements, M. P. (2010). Forecast Encompassing Tests and Probability Forecasts. *Journal of Applied Econometrics*, 25(6).

DeGroot, M. H., & Fienberg, S. E. (1983). The Comparison and Evaluation of Forecasters. *The Statistician*, 32(1–2), 12–22.

Diebold, F. X., & Mariano, R. S. (1995). Comparing Predictive Accuracy. *Journal of Business & Economic Statistics*, 13(3), 253–263.

Fair, R. C., & Shiller, R. J. (1990). The Informational Content of Ex Ante Forecasts. *Review of Economics and Statistics*, 72(2), 325–331. [verify pages before camera-ready]

Gneiting, T., Balabdaoui, F., & Raftery, A. E. (2007). Probabilistic Forecasts, Calibration and Sharpness. *Journal of the Royal Statistical Society B*, 69(2), 243–268.

Gneiting, T., & Raftery, A. E. (2007). Strictly Proper Scoring Rules, Prediction, and Estimation. *Journal of the American Statistical Association*, 102(477), 359–378.

Halawi, D., Zhang, F., Yueh-Han, C., & Steinhardt, J. (2024). Approaching Human-Level Forecasting with Language Models. *NeurIPS 2024*; arXiv:2402.18563.

Harvey, D., Leybourne, S., & Newbold, P. (1997). Testing the Equality of Prediction Mean Squared Errors. *International Journal of Forecasting*, 13(2), 281–291.

Jolliffe, I. T., & Stephenson, D. B. (eds.) (2012). *Forecast Verification: A Practitioner's Guide in Atmospheric Science*, 2nd ed. Wiley.

Karger, E., Bastani, H., Yueh-Han, C., Jacobs, Z., Halawi, D., Zhang, F., & Tetlock, P. E. (2024). ForecastBench: A Dynamic Benchmark of AI Forecasting Capabilities. *ICLR 2025*; arXiv:2409.19839.

Lehmann, N. V. (2023). Forecasting Skill of a Crowd-Prediction Platform. arXiv:2312.09081.

Lu, J. (2025). Evaluating LLMs on Real-World Forecasting Against Expert Forecasters. arXiv:2507.04562.

Mason, S. J. (2004). On Using "Climatology" as a Reference Strategy in the Brier and Ranked Probability Skill Scores. *Monthly Weather Review*, 132(7), 1891–1895.

Mellers, B., et al. (2014). Psychological Strategies for Winning a Geopolitical Forecasting Tournament. *Psychological Science*, 25(5).

Mellers, B., et al. (2015). Identifying and Cultivating Superforecasters. *Perspectives on Psychological Science*, 10(3).

Murphy, A. H. (1973). A New Vector Partition of the Probability Score. *Journal of Applied Meteorology*, 12(4), 595–600.

Murphy, A. H., & Winkler, R. L. (1987). A General Framework for Forecast Verification. *Monthly Weather Review*, 115(7), 1330–1338.

Satopää, V. A., Baron, J., Foster, D. P., Mellers, B. A., Tetlock, P. E., & Ungar, L. H. (2014). Combining Multiple Probability Predictions Using a Simple Logit Model. *International Journal of Forecasting*, 30(2).

Schoenegger, P., & Park, P. S. (2023). Large Language Model Prediction Capabilities: Evidence from a Real-World Forecasting Tournament. arXiv:2310.13014.

Wheatcroft, E. (2019). Interpreting the Skill Score Form of Forecast Performance Metrics. *International Journal of Forecasting*, 35(2), 573–579.

Yang, Q., Wu, J., et al. (2025). LLM-as-a-Prophet: Understanding Predictive Intelligence with Prophet Arena. arXiv:2510.17638. [verify full author list before camera-ready]
