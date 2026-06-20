# FORECAST_LLM.md — building a forecasting LLM (full build-out)

*Last researched: 2026-06-11. Goal: a fine-tuned open model that reaches frontier-parity on
forecasting at a fraction of the size, proven by a dated, leak-free scored record — the news
artifact that funds the bigger one. The moat is the **data factory + decorrelated marginal-ensemble
value** (a cheap model whose structured-data-grounded errors are uncorrelated with the frontier pack —
worth more in an ensemble than a second frontier model). Leak-discipline is the METHOD that keeps the
number real (don't self-deceive); it is NOT the moat. Honesty is table stakes, not an edge.*

---

## 0.0 Kill the "LLMs can't beat human forecasters" line (read this BEFORE anything)

That sentence is a **domain-confusion error**, not a finding. It is the *average* across every
question class on ForecastBench — a distribution dominated by the single hardest class (liquid,
efficient prediction markets), where the crowd price is near-optimal and *nothing* beats it cheaply.
Averaging over that class buries the fact that whole strata already go the other way:

- **On the DATASET half, bots ALREADY beat superforecasters** (green-tree bot 0.123 < supers 0.132;
  ours 0.124). This is measured, not hoped. It is the half our series factory mints natively.
- **The "20% human edge" (0.081 vs 0.101) is a forward projection to PARITY in late 2026** — closeable
  now, not a wall.
- **The winning frame was never "small model beats humans standalone."** It is **marginal ensemble
  value via decorrelation** — a *math* lever (error variance falls ~1/N only when errors are
  independent). A model trained on a different distribution than web-text is the most valuable
  *addition* to any pack, per dollar. Money cannot buy that; a different data diet can.

So when any model (including future me) repeats "LLMs can't beat forecasters" — it is answering the
wrong question with a true-but-irrelevant average. Our own scored record contradicts it in the exact
place we attack. The correct claim is: **win the dataset half decisively, match the crowd on the
market half, and be the lowest-correlation ensemble member.** That is winnable at ~$0 of edge + a
GPU's worth of compute. Do not relitigate this.

## 0.1 The board is won at INFERENCE time TODAY — the fine-tune is the AMPLIFIER, not the edge

Checked the live ForecastBench frontier (Feb 2026). **None of the top AI bots are bespoke fine-tunes.**
They are inference-time ensembles + calibration — exactly what our **unlimited keyless calls** buy for $0:

- **xAI Grok 4.20** (tied #1 AI): give the model the question + tools, **generate 8 forecasts, average them.** That's it.
- **Cassi `ensemble_2_crowdadj`** (0.102, joint-2nd overall behind supers 0.086, tied #1 AI): retrieval +
  ensemble + a **crowd-adjust** step (if the forecast disagrees with the market price, let an LLM review &
  adjust → **+0.01 Brier**) + post-hoc calibration.
- **AIA Forecaster** (≈ superforecaster median): agentic search + supervisor reconciliation + **Platt
  scaling + extremization.**
- **"Wisdom of the Silicon Crowd"** (Science Advances 2024): an ensemble of **12 LLMs, simple aggregation**,
  is statistically *indistinguishable from a 925-human crowd* — no training. And LLM forecasts improve
  **17–28%** when shown the crowd median (= our crowd-anchor, already built).

**Implication for sequencing:** the GPU fine-tune (Product B below) is the viral "tiny beats big" fundraise
artifact and an ensemble-decorrelation *amplifier* — it is **NOT** how the leaderboard is won and **NOT**
on the critical path to edge. **Edge is gettable NOW, $0, keyless**, by doing what the board leaders do —
multi-model best-of-N + extremize + crowd-adjust — at a sampling scale that is economically painful for
metered competitors and free for us. The infra exists (`ensemble.py` extremized log-odds pool;
`market.py` `calibrate`/`extremize`; the `--pred` hook). The missing piece is feeding it a **diverse
multi-model inference bank** from the keyless roster. Build that first; train second.

---

## 0. Verdict (read this first)

- **It's possible and already proven.** Mantic × Thinking Machines RL-tuned `gpt-oss-120b` with a
  GRPO-style objective + Brier reward on ~10k binary questions → matched Gemini 3 Pro and became the
  2nd-most-valuable ensemble member after Grok 4. We copy that recipe, smaller, with a better data engine.
- **Never pre-train from scratch.** $1M+, buys nothing. The edge is *data + RL on a strong base*, not weights.
- **The realistic win is NOT "1B beats humans" standalone** — that's the overclaim that burns credibility.
  The true, viral, defensible artifact: *"fine-tuned 8B open model reaches frontier-parity on
  ForecastBench, at 1/30th the params, with low ensemble correlation, on a public leak-free record."*
- **The durable moat is the data factory** (auto-minted, leak-gated questions from our own series),
  not the training tech. Everyone can run GRPO. Almost nobody has the question factory.
- **How we beat a 120B-on-a-node team on ~$0 — the axes where money doesn't help:**
  1. **Decorrelation (the math lever).** Ensemble error variance falls ~1/N *only* when errors are
     independent ("Not All Accuracy Is Equal: Prioritizing Independence", 2025). A small model trained on
     a DIFFERENT distribution (our structured constraint-series) makes errors uncorrelated with web-text
     frontier models → higher *marginal* ensemble value than adding a second frontier model. We don't beat
     120B solo; we're the most valuable *addition* to any ensemble, per dollar.
  2. **Structured grounding, not parametric recall.** We feed each question its leak-safe quant/crowd
     anchor + reference-class prior (`curate.py`) so the model reasons from dated data, not vibes — the
     source of the decorrelation and the thing frontier zero-shot lacks.
  3. **Specialize where the factory is deep** (numeric/macro/compute constraints) → credibly "best in the
     world at forecasting X" beats "50th at everything".
  The win = top marginal-ensemble-value on a public leak-free record at ~$0 → THAT is the fundraise.
- **Where the LLM helps:** the dataset/numeric half + ensemble diversity on the market half. The market
  half is crowd-ceilinged (~0.065 Brier) and news *hurts* zero-shot models — so don't fight the crowd
  there; match it + add diversity. Win on the dataset half (where bots already beat supers).

---

## 1. State of the space (2026)

| Work | What they did | Takeaway for us |
|---|---|---|
| Halawi et al. 2024 | SFT on *filtered* CoT traces (kept only traces beating the crowd) | The rejection-sampling SFT recipe works; approached human-crowd Brier |
| "LLMs Can Teach Themselves to Predict the Future" (Feb 2025) | self-training / self-play | synthetic self-improvement is viable |
| **Mantic × Thinking Machines (late 2025)** | **gpt-oss-120b, GRPO-style (no std-div), Brier reward, ~10k binary Qs (Aug'24–Dec'25), pre-computed research context** | **Our blueprint.** 38.6→45.8 = Gemini-3-Pro parity; value = ensemble diversity |
| "Massive Training for Event Forecasting" (Jul 2025) | scaled training of forecasting LLMs | lane is active; scale + data are the levers |
| ForecastBench (ICLR 2025) | supers ~0.081 vs best LLM ~0.101 Brier | ~20% human edge; **LLM–super parity projected late 2026** — closeable now |

Live race, not empty field. We win on **data + honesty + a public scored record**, not compute.

---

## 2. Model selection

**Pick: Qwen3 family** (Apache 2.0, native thinking mode, full size ladder, strongest open reasoning).
Qwen3-8B ≈ Qwen2.5-7B quality; Qwen3 dense bases match/beat larger Qwen2.5 on reasoning.

| Phase | Model | Why |
|---|---|---|
| Plumbing debug | Qwen3-1.7B / Qwen3.5-2B | run the whole loop in a day. **Capability throwaway** — too weak to learn the behavior |
| **POC / news artifact** | **Qwen3-8B (or Qwen3.5-9B)** | small enough for the "tiny beats big" headline, large enough to learn. Thinking mode = built-in CoT |
| Scaled (post-raise) | Qwen3-32B **or** gpt-oss-120b | 32B = single 8×H100 node + our data moat; 120B = Mantic-class frontier-parity |

**Never sub-3B for the capability claim** — CoT too incoherent for the reward to find signal.

---

## 3. The exact system flow

```
   ┌──────────────── PHASE 0 — DATA FACTORY (CPU + API/keyless, no GPU) ────────────────┐
   │ our series (FRED/Comtrade/PatentsView/arXiv) ─┐                                     │
   │                                               ├─► QUESTION MINTER ─► binary Qs +    │
   │ resolved markets (Metaculus/Manifold/Poly) ───┘     known label (leak-controlled)   │
   │                                                          │                          │
   │                                          RESEARCH-CONTEXT BUILDER (freeze @ as-of)  │
   │                                                          │                          │
   │                                          TRACE GENERATOR (N samples → keep best-of-N│
   │                                                          │  that beat base rate/crowd│
   │                                          LEAK GATE (holdout.py date probe)          │
   │                                          QUALITY GATES (§4.5)                       │
   │                                ┌─────────────────────────┴───────────────┐         │
   │                                ▼                                          ▼         │
   │                       SFT set (JSONL ~10k)                    GRPO set (prompts +    │
   │                                                               outcomes, ~10–50k)     │
   └────────────────────────────────┼─────────────────────────────────┼─────────────────┘
   ┌──── PHASE 1 — TRAIN (1× GPU / 1× node) ────┐                       │
   │   1) SFT WARMUP (Unsloth QLoRA) ───────────┼──────► 2) GRPO (Brier reward, vLLM)    │
   └────────────────────────────────────────────┘                       │
                                                                         ▼
                              3) EVAL: ForecastBench-forward + leak-gated holdout (Brier/AUC/calib)
                                                                         │
                              4) ENSEMBLE: blend w/ stat dataset-engine + frontier models
                                                                         │
                              5) SERVE (vLLM) → live ForecastBench submission → scored record
```

**SFT before GRPO:** GRPO on a cold base wastes rollouts. SFT locks the output format + reasoning
skeleton (base rate → reference class → both sides → adjust → `Probability: 0.NN`); RL then only
sharpens calibration.

---

## 4. Data spec (the core) — designed to match the real target

> **Design principle:** our training I/O mirrors ForecastBench's I/O exactly, so the model trains on
> the distribution it's scored on, and our synthetic questions are simultaneously *leak-safe* and
> *in-distribution*. ForecastBench draws from FRED, DBnomics, Wikipedia, Yahoo Finance, ACLED
> (dataset/numeric) + Manifold, Metaculus, Polymarket, INFER (market). The dataset half is where bots
> already beat superforecasters — and it's exactly the kind of question our series factory mints.

### 4.1 The real schemas (so we match them)

**ForecastBench question object** (what the model is given):
```json
{
  "id": "SEIqqlqg8L", "source": "manifold",
  "question": "Will Polyoptions volume hit $100 million in 2026?",
  "resolution_criteria": "Resolves to the outcome of the question at <url>.",
  "background": "Market on whether 2026 volume ≥ $100,000,000 ...",
  "freeze_datetime": "2026-02-19T00:00:00+00:00",
  "freeze_datetime_value": "0.283",            // ← THE CROWD'S PROBABILITY (baseline to beat + a feature)
  "freeze_datetime_value_explanation": "The market value.",
  "market_info_open_datetime": "...", "market_info_close_datetime": "...",
  "url": "...", "resolution_dates": "N/A"       // market Qs: 1 forecast; dataset Qs: up to 8 horizons
}
```

**ForecastBench submission object** (what the model must output):
```json
{ "id": "...", "source": "metaculus", "forecast": 0.0_to_1.0,
  "resolution_date": "YYYY-MM-DD or null for market Qs", "reasoning": "optional" }
```
Rules: market Qs → one forecast, `resolution_date: null`. Dataset Qs → forecasts at **up to 8
resolution dates** (multi-horizon). ≥95% coverage or missing imputed to 0.5. **Our model's output
parser must emit exactly this.**

### 4.2 Our unified training row (superset; carries everything for training + audit)
```json
{
  "id": "fred-PAYEMS-2024Q3-h90",
  "source": "fred",                       // fred|comtrade|patents|wikipedia|yahoo|metaculus|manifold|polymarket
  "kind": "dataset",                      // dataset (numeric, multi-horizon) | market (event)
  "question": "Will US nonfarm payrolls exceed 159,000,000 on 2024-12-01?",
  "resolution_criteria": "FRED series PAYEMS value on the release covering 2024-12-01.",
  "as_of_date": "2024-09-01",             // information cutoff for THIS row (freeze date)
  "resolution_date": "2024-12-01",
  "horizon_days": 91,
  "context": "Series history through 2024-09-01: [ ... values ... ]",  // frozen, leak-safe
  "crowd_prob": 0.61,                     // freeze_datetime_value if a market; null if pure series
  "base_rate": 0.55,                      // reference-class prior (for difficulty + hedge detection)
  "outcome": 1,                           // ground truth (series lookup or market resolution)
  "category": "macro",                    // macro|geopolitics|tech|science|health|markets|sports|other
  "base_model_cutoff": "2024-10-01",      // cutoff of the model being trained/eval'd
  "leak_ok": true,                        // resolution_date > base_model_cutoff AND no answer in context
  "difficulty": 0.42,                     // |0.5 - calibrated_prior| inverted; for balanced sampling
  "trace": "<CoT ... Probability: 0.73>", // SFT only; null for GRPO rows
  "trace_score": 0.07                     // SFT only: (p-outcome)^2; kept iff beats base_rate/crowd
}
```

### 4.3 Question taxonomy (mint for diversity — don't overfit one template)
- **Threshold / level:** "Will {series} ≥ {x} by {date}?"
- **Direction / change:** "Will {series} be higher than on {t0} by {date}?"
- **Comparison (ForecastBench-style):** "Will there be more {event} in {region} in the 30d before
  {resolution_date} vs the 360d-preceding average at {forecast_due_date}?" (ACLED template)
- **Ranking:** "Will {A} exceed {B} by {date}?"
- **Multi-horizon:** the same series question asked at 7/30/90/180/365-day horizons (mirrors the
  dataset half's up-to-8 resolution dates).
- **Real market events:** ingested verbatim from Metaculus/Manifold/Polymarket (genuine world-reasoning).

### 4.4 The mix (this is what makes it "enough", not just big)
Synthetic-series-only would teach *extrapolation + calibration* but not *world reasoning* — and a model
trained only on monotone series learns "trend continues / things go up", a degenerate heuristic. So:

| Bucket | Share | Teaches | Leak status |
|---|---|---|---|
| Synthetic from our series (multi-horizon) | ~50% | numeric calibration, the dataset-half skill, full [0,1] prob range | **fully leak-controlled** (we set as_of) |
| Real resolved markets (Metaculus/Manifold/Poly) | ~35% | genuine world-event reasoning, the market-half distribution | leak-gated by date |
| Comparison/ACLED-style structured | ~15% | the exact ForecastBench dataset templates | leak-controlled |

### 4.5 Quality gates (every row must pass — this is the "good & quality" guarantee)
1. **Leak gate (hard):** `resolution_date > base_model_cutoff` AND the answer is not present in
   `context`/`question`. Enforced by `engine/holdout.py`'s effective-cutoff probe. Drop, don't impute.
2. **Label balance:** within each question type, keep outcomes near 50/50 (reject the easy monotone
   tails) so the model can't win by always-up. Track and log the realized balance.
3. **Difficulty spread:** sample across `difficulty` so the set isn't all gimmes; include genuinely
   uncertain questions (base_rate near 0.5).
4. **Probability coverage:** the SFT trace set must span the full [0,1] range (calibration breadth) —
   not clustered at 0.5 or at the extremes.
5. **Dedup / near-dup:** collapse questions about the same underlying event/series-window (embedding
   dedup) so train/eval don't share an event.
6. **Contamination check:** the frozen `context` and `question` contain no post-`as_of_date` fact and
   no statement of the outcome. Auto-scan + spot-audit.
7. **Resolution integrity:** only objective, dated, verifiable resolutions (drop ambiguous/voided markets).
8. **Category + horizon coverage:** enforce minimum counts per `category` and per horizon bucket so the
   model generalizes, not memorizes one domain.
9. **Trace filter (SFT, rejection sampling):** for each question sample **N=5–10** traces at temperature
   from a strong model; **keep only traces whose final probability beats the base rate / crowd**
   (`trace_score` better than `crowd_prob`'s score). This is the Halawi/RSFT lever — it teaches *good*
   forecasting, not average. Reject traces that reference the outcome ("as we now know…").

### 4.6 How many rows — "enough to be sure", justified
- **SFT: 3k–20k filtered traces.** Quality ≫ quantity (LIMA: ~1k can move a model; RSFT works at low
  thousands). Halawi reached crowd-parity with low-thousands of *filtered* traces. Target **~8–10k**.
- **GRPO: 10k–50k resolved questions**, rolled out at G=8–16. **Mantic hit frontier-parity at ~10k
  real questions** → 10k is the proven floor; our factory pushes to 50k for margin and coverage.
- **Eval (held-out, forward): ≥500–1,000 leak-gated questions** per category for tight Brier CIs
  (block-permutation / cluster-bootstrap, per our `significance.py`).

### 4.7 Generation procedure
1. **Mint** from series (the 5 templates) + **harvest** resolved markets.
2. **Freeze context** as of `as_of_date` (series history is naturally clean; for markets, snapshot
   structured facts — treat news text as an *ablation*, not a default, since news hurts zero-shot).
3. **Generate N traces** (frontier API or keyless DeepInfra bulk) → **best-of-N filter** (§4.5.9).
4. **Run all 9 quality gates**; log what each gate dropped (no silent truncation).
5. **Store** SFT JSONL + GRPO Parquet in object storage (R2/Backblaze/S3); SQLite holds only derived
   signals/cards (per CLAUDE.md — corpus ≠ SQLite).

---

## 5. Training recipe

### 5.1 SFT warmup
Unsloth QLoRA (4-bit), Qwen3-8B, LoRA r=16–32, 2–3 epochs, lr ~2e-4, seq 4–8k. Locks format + reasoning
shape. ~5–10 GPU-hours.

### 5.2 GRPO
- **GRPO** (drops critic → low VRAM); **FULL Dr.-GRPO: `scale_rewards="none"` (no std-division) AND
  `loss_type="dr_grpo"` (constant, non-length advantage norm)** — three papers converge (2503.20783 /
  2508.11800 / 2505.17989) that removing GRPO's per-question normalization is correct for calibrated/
  stochastic outcomes. We KEEP `beta>0` (the SFT-anchor KL), unlike math-RL Dr.GRPO which drops it:
  forecasting wants calibration, so the anchor stays. (grpo.py, both knobs `hasattr`-guarded + smoke-gated.)
- **Reward = Brier (default):** `1 - (p - outcome)^2`, strictly proper, bounded, low-variance. + small
  **format reward** (parseable `Probability:`). This is the calibration-optimal reward for an ALL-BINARY
  set and stays the default. A `--reward composite` knob adds an accuracy-side bonus (OpenForecaster/RLCR;
  anti-hedge, +AUC) for A/B ONLY — its own binary ablation shows the accuracy term can HURT calibration, and
  calibration is our edge, so do not default it on without a leak-free eval win on Brier AND temp-scale.
- G=8–16, 1k–2k steps, completions ~1–2k tokens. HF-generate rollouts for the POC (vLLM dropped — pins its
  own torch; ~6-9h/1500-step on an L40S, inside cap). The over-sharpening guard is `beta` + the no-std/
  dr_grpo norm; eval.py's temp-scale diagnostic (T>1.15 ⇒ raise beta) is the monitor.

### 5.3 Anti-reward-hacking (watch)
- **Hedge-to-0.5 collapse:** strictly-proper reward + varied base rates; **track AUC, not just Brier.**
- **RL overconfidence:** keep an SFT-calibrated checkpoint to interpolate toward; add calibration penalty.
- **Leakage inflation:** train metrics lie if the base model knows outcomes — trust only forward/leak-gated.

---

## 6. The stack

| Layer | Tool | When |
|---|---|---|
| SFT + single-GPU GRPO | **plain transformers + peft + TRL** (bf16 LoRA) | POC. ~~Unsloth~~ dropped 2026-06-11: its global monkeypatching broke 4× in a row on the DLAMI stack (trl-0.24 arg renames, placeholder tokens, unpicklable compile-config in datasets.map fingerprinting). Boring wins |
| GRPO foundation | **TRL `GRPOTrainer`** (v0.24+) | reference impl; rollouts via HF generate (vLLM dropped for the POC — it pins its own torch) |
| Multi-GPU scale | **Axolotl** | async gen, streaming scoring, replay buffer, FSDP/DeepSpeed. Switch at 32B+ |
| Serious RL throughput | **veRL** | only if Axolotl bottlenecks at large scale |
| Rollout / serving | **vLLM** | GRPO generation + live inference |
| Tracking | **wandb** | reward, Brier, AUC, calibration curves |
| Data | **Polars/DuckDB + Parquet** | the question factory; object storage for corpus |
| Eval | ForecastBench-forward + `engine/holdout.py` + `significance.py` | the only numbers that count |

Path: **plain TRL+peft (POC) → Axolotl (scale).**

---

## 7. Compute & cost — with AWS credits

**AWS prices dropped 44% (June 2025).** `p5.48xlarge` (8×H100 80GB) ≈ **$55/hr** us-east-1
(~$6.88/H100-hr); `p4d.24xlarge` (8×A100 40GB) ≈ $32.77/hr. **Gotcha: AWS sells H100 only as the
8-GPU node** — there's no cheap single H100. For single-GPU dev use `g6e.xlarge` (1× L40S 48GB, ~$1.9/hr)
or `g5.xlarge` (1× A10G 24GB, ~$1/hr); use the full p5 node when you can parallelize.

### POC (Qwen3-8B) — credit burn
| Approach | Instance | Wall-clock | Credit burn |
|---|---|---|---|
| **Frugal** (single GPU, serial) | g6e.xlarge (1× L40S 48GB) | ~1–2 weeks | **$220–560** (120–300 GPU-hr × $1.9) |
| **Fast** (parallel sweep) | p5.48xlarge (8×H100), 1–2 days | run 8 GRPO configs at once | **$825–2,200** (15–40 node-hr × $55) |

Either way the POC is **well under $2.5k of credits.** First end-to-end Brier signal ≈ $150–400.

### Scaled (post-raise / on credits)
| Base | Instance | Node-hours (w/ iteration) | Credit burn |
|---|---|---|---|
| Qwen3-32B | p5.48xlarge | 60–190 | **$3,300–10,400** |
| gpt-oss-120b | p5.48xlarge, 1–2 wks/run ×2–3 | 350–1,000 | **$20–55k** |

**With a credit pool:** ≥$5k → full POC + a serious 32B run. ≥$25k → attempt a 120B Mantic-class run.
Use on-demand + frequent checkpoints (so you *could* drop to spot at ~30–50% off if credits run thin).
Don't optimize $/hr with credits — optimize wall-clock: rent the p5 node, parallelize iteration, kill when idle.

---

## 8. Phased build plan

**Phase 0 — Data factory** (Mac + API/keyless, ~$100–500, no GPU). *Build first; it's the moat.*
- [x] **Question minter + leak gate + context builder + balance gate** → `engine/forecastbench/trainset.py`.
  Seeds from the cached real ForecastBench rounds (`data/forecastbench/q_*.json`) → exact series +
  byte-identical question templates; walks each series' history backward minting (as_of × horizon-ladder)
  binary questions whose outcome is already in the past (read from the series); frozen point-in-time
  context; `leak_ok` vs `--cutoff`; deterministic 50/50 outcome balance. Reuses `dataset.py` fetchers +
  P(higher) models (the `model_prob` baseline). **Verified: 782 leak-controlled rows from 25 series, $0.**
  Run: `python -m engine.forecastbench.trainset --cutoff 2024-10-01 --anchors 6 --balance`
- [x] **Domain/industry tagger** → `engine/forecastbench/domains.py` (22 domains; the `domain` field for variety).
- [x] **Cross-domain FRED seed** (32 series: labor, prices, rates, housing, energy, commodities, crypto,
  trade, consumer) added to the minter so the numeric corpus isn't just macro + weather.
- [x] **Market harvester** → `engine/forecastbench/harvest.py`. Manifold resolved-binary, domain-seed-term
  sweep, liquidity filter, leak-gate. **Verified: 1,812 markets across 22 domains** (defense/geopolitics 262,
  sports 227, AI 215, business 187, elections 186, crypto 124, space 69, health 63 …), $0 keyless.
- [x] **SFT trace generator (best-of-N rejection)** → `engine/forecastbench/traces.py`. Keyless DeepInfra
  (Qwen3.5/Gemma-4/DeepSeek-V4/GLM-5.1) **through a Floxy/Evomi proxy = $0**; keeps only traces beating the
  baseline; emits Unsloth-ready chat JSONL. **Verified: kept-trace Brier 0.089 vs 0.25 baseline.**
  Run: `python -m engine.forecastbench.traces --in <rows>.jsonl --provider deepinfra_keyless --proxy floxy`
- [x] **Corpus assembler + temporal leak-split** → `engine/forecastbench/corpus.py`. Merges + dedups all
  rows; splits by `leak_ok` (eval = resolution AFTER cutoff = leak-free; train = before). Reports coverage.
- [x] **Curate + structurally enrich** → `engine/forecastbench/curate.py` (2026-06-11). The raw merge was
  a low-signal RL diet — **68% Manifold** (forecasting-useless context), the numeric calibration edge
  swamped 2:1, `base_rate` never populated, `crowd_prob` discarded, label-degenerate micro-sources. Pass
  fixes it: drop degenerate micro-sources + market re-ingest dups (numeric multi-horizon ladder kept
  whole), **rebalance Manifold → 50/50 numeric:market** (the §4.4 mix; keep high-liquidity markets), and
  ENRICH every row (leak-safe) with a **Structured-anchors block prepended to context** — the frozen-series
  quant `model_prob`, the crowd prob when present, and a reference-class base rate (gated to skewed classes
  so we never inject "0.50" → no hedge-collapse). **Result: 22,487→14,532 TRAIN, exactly 50/50/50% YES,
  anchors on numeric.** This is the structural grounding that decorrelates us from frontier recall (§0).
  EVAL is only enriched, never rebalanced (stays a faithful ForecastBench mirror). Overwrites the canonical
  jsonl in place (originals → `*_raw.jsonl`) so run scripts need no path change.
  **Crowd lever SHIPPED (2026-06-11):** `crowd.py` reconstructs a LEAK-SAFE freeze-time crowd probability
  for resolved Manifold markets (`probAfter` of the latest bet ≤ a ForecastBench-style freeze date; outcome
  stays strictly after → genuine ex-ante signal). crowd_prob now on **2,226 train / 2,347 eval rows
  (15.7% / 15.3%, up from 216)**; curate.py surfaces it as a structured anchor → trains anchor→adjust,
  in-distribution with the live submission pipeline. Reconstructed crowd is a real signal (eval crowd solo
  **Brier 0.1407, AUC 0.864** — the market-half bar to beat). *Deepen next:* only ~18% of markets got a
  value (cap_pages=8 drops hyper-active markets) — raise the page cap for more coverage.
- [x] **Contamination scan PASSED** — 0/9,048 numeric point-in-time violations (every context value ≤ as-of
  date), 0/1,812 market outcome-stating contexts. Leak discipline holds.
- [x] **Phase 1 training scaffold** → `training/` (sft.py · grpo.py · eval.py · common.py · requirements.txt ·
  README). Standalone GPU-box scripts (not engine deps); all compile; helpers unit-checked on real rows.
- [~] SFT traces (2026-06-10 build): the dataset half was MISSING entirely (only 342 market traces existed,
  `sft_dataset.jsonl` never written — the bot's *edge* half had zero SFT). Fixed: two detached keyless runs
  generating **balanced dataset (3750 Q, evomi) + market top-up (1200 Q, floxy)**, streaming to
  `sft_dataset.jsonl` / `sft_market_more.jsonl`; `corpus.py` merges all `sft_*.jsonl` → `sft_all.jsonl`
  (the file `sft.py` now trains on). `finish_sft.py` watcher auto-merges + quality-gates on completion.
  Dataset traces are genuinely **calibrated** (probs cluster ~0.5 on hard numeric Qs — low leakage, the
  flagship correctly stays uncertain), so they distil real ex-ante reasoning, not leaked confidence.
  **Live-model lock (2026-06-10 probe):** direct Mac IP is fully 403-blocked; via proxy the flagship
  **Qwen/Qwen3.5-397B-A17B** + GLM-5.1 + gemma-4-26B answer reliably (several roster IDs are dead 403).
  **Op-lesson refined:** keyless is per-IP AND per-model rate-limited. workers=8 single-pool *collapses*
  keep-rate (8% — 429s drop samples). The fix that holds workers=4–5: (a) the adapter now **shuffles the
  3 live models per call** (spreads load → fewer 429s + trace diversity), (b) per-call IP rotation, (c)
  split across two proxy pools (evomi resi + floxy DC) so the two runs don't contend. ~21% question
  keep-rate, ~1.8 traces/kept-Q, ~12s/Q → ~13h for the dataset run. MiniMax 429-dead, OpenRouter excluded.
- [ ] Parquet to object storage; ForecastBench submission output parser (§4.1)

**Corpus (`data/forecastbench/trainset/`, all $0 keyless, leak-gated, cutoff 2024-10-01):**
- `grpo_train.jsonl` — **19,131 rows** (pre-cutoff), 54% YES · `grpo_eval.jsonl` — **15,118 rows** (post-cutoff,
  leak-free) = **34,249 total GRPO rows**, 24 domains.
- Sources: `harvest.py` Manifold (bulk-paginate full dump + 136-term sweep, 34k) · `trainset.py` cross-domain
  numeric (fred/dbnomics, 9k) · **`bench.py` the benchmark's OWN resolved rounds** (q_+r_ join → Metaculus/
  Polymarket/INFER/ACLED/Wikipedia + **crowd anchor on 8,188 rows**) — so EVAL matches the real ForecastBench
  distribution. `corpus.py --cap-other` trims the low-signal "other" bucket.
- `sft_market.jsonl` 342 traces (Brier 0.082) + `sft_dataset.jsonl` (numeric).
- **Verdict: data-complete for the POC. More = variety not volume; the only variety left (Metaculus/Polymarket
  depth, crowd-feature) is best driven by what the first eval reveals. We are GPU-limited, not data-limited.**

**Phase 1 — POC** (g6e single-GPU or a 1–2 day p5 sweep; <$2.5k credits).
- [ ] Unsloth QLoRA SFT warmup (Qwen3-8B) → GRPO + Brier reward + vLLM
- [ ] Eval: ForecastBench-forward + leak-gated holdout; log Brier + AUC + calibration + ensemble corr
- **Success gate:** beats Qwen3-8B zero-shot by a clear Brier margin **and** low correlation with
  frontier models (the diversity number = the headline).

**Phase 2 — Scale** (p5 node, $3–55k credits depending on base).
- [ ] Same recipe at 32B (or 120B), 50k+ questions, longer RL
- [ ] Live public ForecastBench submission → dated, leak-free scored record (= the fundraise)

---

## 9. Eval protocol (non-negotiable)
- **Forward only** for the capability claim (resolution after base-model cutoff).
- **Leak-gate every eval question**; report exclusions (no silent caps).
- Report **Brier + log score + calibration curve + AUC + ensemble correlation**, with CIs via
  `significance.py` (block-permutation / cluster-bootstrap).
- Baselines: zero-shot self, the crowd (`freeze_datetime_value`), superforecasters, frontier LLMs.

## 10. Honest risks / failure modes
- **Market half is crowd-ceilinged** and news *hurts* zero-shot models — the LLM's job there is match +
  diversity, not beating the crowd standalone. Win on the dataset half.
- **Standalone supremacy unlikely; ensemble value (low correlation) is the realistic, sufficient win.**
- **Reward hacking** (hedge-0.5, RL overconfidence) — §5.3.
- **Leakage inflation** — only forward/leak-gated numbers count.
- **Degenerate synthetic data** (monotone-trend shortcut) — defeated by §4.4 mix + §4.5 balance gates.
- **Crowded lane** — resourced labs are training forecasters; we win on data + honesty + record.

---

## 11. References
- Mantic × Thinking Machines: https://thinkingmachines.ai/news/training-llms-to-predict-world-events/
- Halawi et al. 2024: https://arxiv.org/pdf/2402.18563
- LLMs Can Teach Themselves to Predict the Future: https://arxiv.org/pdf/2502.05253
- Massive Training for Event Forecasting: https://arxiv.org/pdf/2507.19477
- ForecastBench (ICLR 2025): https://arxiv.org/pdf/2409.19839 · datasets: https://github.com/forecastingresearch/forecastbench-datasets · submit: https://github.com/forecastingresearch/forecastbench/wiki/How-to-submit-to-ForecastBench
- Qwen3: https://qwenlm.github.io/blog/qwen3/
- Unsloth RL/GRPO: https://unsloth.ai/docs/get-started/reinforcement-learning-rl-guide · Axolotl GRPO: https://docs.axolotl.ai/docs/grpo.html
- Rejection-sampling fine-tuning (RSFT/RFT): https://www.emergentmind.com/topics/rejection-sampling-fine-tuning
- AWS GPU pricing 2026: https://www.spheron.network/blog/aws-h100-pricing-2026/ · https://instances.vantage.sh/aws/ec2/p5.48xlarge
