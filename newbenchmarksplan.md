# newbenchmarksplan.md — win the live forecasting arena (fundraise artifact)

**Goal.** Produce a dated, public, verifiable result — *top-tier bot AND beating human pros* — in the
live Metaculus arena, the way Mantic did (4th/539 humans, Metaculus Cup → Bloomberg/Guardian/Time →
~$4M pre-seed). That scalp is the credential that lands a credentialed cofounder + the raise.
Benchmark ≠ goal; the **press-worthy human scalp** is the goal. WIN. No overfit.

**Today: 2026-06-12. The Summer season is LIVE NOW — enter today, don't wait for Fall.**

## Targets (one synchronized question feed)
1. **Summer 2026 FutureEval AIB** (bot tournament): started May 18, runs to ~mid-Aug (Qs stop a few
   weeks before Sep 1). $50k, 300–500 Qs. Join anytime, start mid-leaderboard at 0. → **bot credential + prize.**
2. **Metaculus Cup Summer 2026** (same timeframe): bot-vs-human, NO prizes. → **the press scalp. The real prize.**
3. **MiniBench** (bi-weekly $1k): fast resolve → **our test harness / iteration loop.**
4. (Secondary) **ForecastBench**: bucket opens Jun 15, upload by Jun 21. Ship the proven stack, don't overbuild.

## How we win (architecture — gate retrieval BY question class)
- **Judgmental Qs (Metaculus):** research phase (AskNews/Exa) → reconcile → **best-of-N across the free
  keyless roster** (our cost edge: others pay per token) → extremize log-odds → **anchor to community median.**
- **Numeric Qs:** NO news (naive RAG hurts) — series-grounded model_prob + base rate, zero-shot.
- **Calibration:** Platt/shrink fit OUT-OF-SAMPLE, then extremize. **Domain-gate:** abstain/0.5 on chaotic
  classes (commodities/elections/sports). Reuse engine/forecastbench/{inference,ensemble,crowd}.py.

## No-overfit guardrails (non-negotiable)
- Calibration coefficients fit only on a holdout, never the scored set. Leak-gate every question.
- **MiniBench = held-out feedback, NEVER trained on.** Don't tune to one season's noise; report CIs.
- Abstain, don't guess. Crowd-anchor caps overconfidence. Code is inspectable (Metaculus rule) → keep it clean,
  plan a legit inference path (keyless free-tier is gray-area + visible to inspectors).

## Timeline (tight)
- **Jun 12–14:** stand up Metaculus template bot; wire keyless ensemble + research phase + crowd-anchor.
  Register + ENTER Summer AIB + Cup. Smoke-test on resolved Qs.
- **Jun 15–21:** ForecastBench submission window — ship proven stack (ensemble+calibration+domain-gate). Parallel, capped.
- **Jun 15–30:** first MiniBench cycles — tune research depth + ensemble weights out-of-sample. Begin AIB climb.
- **Jul:** full AIB climb; compete in Cup vs pros; weekly calibration re-fit on holdout; track peer score + AUC.
- **~Aug 10–18:** Qs stop opening. Lock the bot; no late tinkering.
- **Sep 1:** season resolves → crystallized public record. Target: **top-3 bot + beat the pro baseline.**
- **Sep+:** use the scalp → recruit credentialed technical cofounder (EF London) → pitch EU pre-seed
  (Episode 1-type) + trading desks (DRW-type). Fine-tune (120B/22B-active) = use-of-funds slide, post-raise.

## Definition of WIN
A dated, inspectable, leak-free public result where our bot (a) ranks top-tier in FutureEval AIB and
(b) beats the human pro baseline in the Metaculus Cup — reproducible, no overfit. That is the artifact.
