# Experiment registry — the pre-registration ledger

One line per protocol version. The **git commit SHA** of the protocol file is the binding seal:
it proves the protocol was fixed *before* the sealed TEST origins were scored. Verify with
`git log --diff-filter=A -- experiments/protocol_vN.yaml` (when the file was added) vs the
`experiment_ledger` row carrying `is_test_reveal=1` (when TEST was scored). The add must precede
the reveal.

| Protocol | Registered | Scope | Sealed TEST origins | Commit SHA | TEST revealed? |
|---|---|---|---|---|---|
| [v1](protocol_v1.yaml) | 2026-06-05 | Frozen detector → gain-of-cohort-share, OpenAlex universe | 2018, 2020 | `8067df5` | **yes — 2026-06-05** |
| [v2](protocol_v2.yaml) | 2026-06-05 | Concept-DISJOINT split, powered pool (OpenAlex + 119 arXiv-category), annual origins | held-out concepts (hash bucket 2) | `4fdec9a` | **yes — 2026-06-05** |

### v1 result (sealed-TEST reveal, recorded immutably in `experiment_ledger`, `is_test_reveal=1`)

Promoted config (argmax selection de-clustered lift): **k=3.5, gain_margin=2.0, channels=count**.
Scored once on the held-out 2018+2020 origins. De-clustered 2×2 `[[fired&win 7, fired&loss 6],[silent&win 1, silent&loss 59]]`, n=73:

- **Discrimination: real and multiple-testing-robust.** Caught **7 of 8** share-gain winners (recall 88%), silent on **59 of 60** losers. Lift **4.9×**, block-permutation p at the 1/2001 floor, Fisher 7.8e-6 → **deflated p = 0.013** (survives the 27-config Bonferroni). → the frozen, point-in-time, LLM-free detector **ranks** winners far better than chance on a rule-drawn universe.
- **Calibration: NOT established.** Brier model 0.074 > base 0.066, and the lift CI runs to 0 (small n=73, only 8 winners). The detector is a good *discriminator*, not a calibrated *forecaster* — its probabilities are overconfident.
- **Honest caveat on the split.** The temporal split shares concepts across selection (2008–2016) and test (2018–2020), and winners persist, so some selection optimism remains. The clean hardening is a **concept-disjoint** split — deferred to protocol_v2 (also adds power: annual origins + the papers-substrate concepts).

Headline, committed and bounded: **the mechanical detector has a genuine, contamination-free ranking edge on the past; it is not yet a calibrated forecaster, and the magnitude is under-powered. v2 hardens the split and adds N.**

### v2 result (concept-disjoint reveal) — THE EDGE DOES NOT SURVIVE. The most important finding here.

Promoted config (argmax SELECT lift): **k=3.5, gain_margin=2.0, count** (SELECT de-clustered lift **3.69×**). Revealed once on the **68 held-out concepts** that share *zero* concepts with the selection set:

- **De-clustered TEST lift = 0.00×, block-p = 1.0, deflated = 1.0 → NOT significant.** Brier 0.0997 ≈ base 0.106 (no calibration gain). The promoted config's edge **collapsed from 3.69× (select) to 0.00× (held-out concepts).**
- **Post-hoc (exploratory, not the sealed metric):** across *all 27* configs on the held-out set, de-clustered lift is 0.00–1.27 — **no config shows a real edge.** The detector fires on only ~2–3 of ~60 de-clustered held-out concepts (11–22 winners are *silent*/missed). The non-independent **pooled** view does retain lift ~2–3×, and de-clustering-to-earliest leaves the detector data-starved — so this is "**cannot confirm at this N**", not a clean refutation. Either way it does **not** clear the honest bar.

**Verdict, committed (no hedging):** v1's p=0.013 was **optimistic** — inflated by persistent-winner concepts shared across its temporal select/test. Under a concept-disjoint split (the honest test), **the detector's edge is NOT established.** The project should not claim a "proven detector edge." What *is* proven is the **method**: a pre-registered, contamination-free apparatus that caught its own false positive. Honesty is the moat.

**Methodological lessons for any v3 (logged, NOT run — chasing significance now would be the exact p-hacking this apparatus prevents):** (a) argmax-lift promotion systematically selects the most-selective, highest-variance config → it overfits; promote by a robustness criterion instead. (b) De-clustering to the *earliest* origin starves the detector of data → the independent test is underpowered; a fixed-horizon de-cluster would be fairer. (c) The real unlock is **finer-grained** concepts at scale (coarse arXiv categories have no edge; the "needle not theme" lesson), not just more coarse ones.

### POWER ANALYSIS of the v2 reveal (2026-06-05, read-only audit — `engine.cli experiment-power`)

The v2 verdict above said "cannot confirm at this N." This **quantifies** it and **corrects the word "refuted."** The audit re-scores the same held-out concepts with the same promoted config (read-only on the spent seal), takes the de-clustered events the reveal's p was built on, and asks: for an assumed *true* lift L, how often would this exact test have flagged it significant? (Bernoulli firing at per-class rates that preserve the observed fire-rate and imply lift L; same `block_permutation_lift`; deflated by the cumulative config count.)

- **The de-clustered test fired on only 2 of 60 concepts (3.3%).** With 11 winners (base 18.3%) and 2 fires, there is almost no signal to test.
- **Power is near-zero at every plausible lift.** Even a *true* **5× lift** is caught only **31%** of the time (raw), **1%** after the ×54 cumulative-deflation tax. **MDE_80 is off-grid** (the test cannot reach 80% power at any lift its 3.3% fire-rate can even express, ≤30×).
- **Therefore v2 did NOT refute the count detector** — it had no power to detect even a strong edge. "0.00× / p=1.0" is a **non-result, not a refutation.** The honest statement: under a clean concept-disjoint split the count detector's edge is **neither established nor refuted** — the clean test was under-powered, and the cause is structural (lessons a+b: argmax-lift promoted the most-selective k=3.5, and de-cluster-to-earliest starved it of fires).

**Why we still do NOT run a powered v3 count re-run.** Power is fixable; the *label* is not. The gain-of-share label is computed from the **same works/year feed** the detector fires on (the NAMED CEILING in `universe.py`) — so even a powered, significant count edge would only prove "attention predicts attention," not the thesis (rent migrating to a binding constraint). The count chapter is therefore **closed as under-powered-and-tautological**, and effort moves to the **locator** (`protocol_locator.yaml`), whose label comes from an **independent** feed (input price / supplier HHI / lead-time) and so escapes the ceiling. This is the honest full-stop, not a pivot-to-chase-significance.

### Locator (Stage 2) — the THESIS test with an INDEPENDENT label (`engine.cli locator-run`)

The count chapter is closed (under-powered + tautological label). The locator tests the actual thesis — *rent migrates to the binding constraint one layer deeper* — with a label drawn from an **independent** feed (producer PRICE per layer, BLS/FRED PPI), not any research count, so it escapes the NAMED CEILING. Pre-registration: [`protocol_locator.yaml`](protocol_locator.yaml) (frozen score formula, window, origins, layer set — no tuning knobs; the git commit is the seal). World = connected `ai_power → metals`; 4 comparable price layers (large-power transformer, HV switchgear, GOES electrical steel, refined copper). At each origin T, three mechanisms name the binding layer from ≤T data; graded vs the layer whose price actually rose most over (T, T+4].

- **Result (N=5 origin-cases, one connected world):** `located` (frozen detector acceleration on log-price ≤T) **1/5 = 20%, BELOW the 25% random baseline** → **no mechanical edge**. `obvious` (naive momentum) 0/5. `graph` (hand-tuned propagate control) N/A — its modal bottleneck (copper mine, a *quantity* layer) isn't in the priced comparison set.
- **Why (honest, and it matches the pre-registered caveat):** the detector kept picking **refined copper** (its price accelerated in the pre-2016 window), but the layer that actually became binding was **GOES electrical steel** in 4 of 5 origins. The transformer/steel/copper **price surge is a 2021+ regime change largely invisible in the pre-surge trend** — so a mechanical, point-in-time score cannot locate it. The constraint migration is **REAL** (rent did land on the deep electrical-steel/transformer layer, share-multiples 1.2–1.66×) but is **NOT mechanically predictable from price alone at this altitude/N.**
- **Verdict (no hedging):** at N=5 this is **suggestive only, cannot refute** — but the direction is a clean negative: the thesis is sound as a *description*, not yet as a *mechanical predictor*. The unlock is **more comparable priced layers** (widen N), not loosening any rule. The judgment loop (human+LLM constraint reasoning) remains the part that actually located electrical steel ex-ante — and that part can only be validated **forward** (Stage 3 holdout), never by retro replay (parametric leakage).

### Holdout (Stage 3) — the leakage-bounded test of LLM JUDGMENT (`engine.cli holdout-run`)

The mechanics (count, locator) test only the frozen parts. The LLM's *judgment* can't be retro-replayed (parametric leakage). The one escape: a model whose training cutoff **precedes** a question's resolution makes a genuine ex-ante forecast we can grade against the now-known outcome. `engine/holdout.py` builds this with a **leakage probe as the validity gate** — it measures the model's *effective* cutoff from dated events and refuses to score any question whose outcome was determined at/before that cutoff (GIGO, no self-certified cutoffs).

- **Hard constraint surfaced:** a valid run needs a genuinely OLD model (GPT-3.5-turbo-0613 ~2021-09 / Llama-2 ~2022-09 via OpenRouter). The reachable models on current credentials — the keyless DeepInfra roster and keyed MiniMax — are all ~2025-cutoff, and the **keyless roster rotates** (probe model ≠ scoring model). So no *rigorous* run is possible yet.
- **Indicative smoke-test (keyless, $0):** the probed model knew ≤2023, was blind to 2024+ (correctly didn't know the 2024 US election or DeepSeek-R1) → effective cutoff 2023. The per-question gate **excluded `graphite_control`** (determined Dec-2023 ≤ cutoff) and scored the 7 leak-free questions: **Brier 0.090 vs 0.245 base, hit-rate 6/7 = 86%** — flagged **INDICATIVE ONLY** (unpinned/rotating model, not validated). It demonstrates the apparatus + gate work; it is **not** a result to claim.
- **To make it rigorous:** set `OPENROUTER_API_KEY`, then `holdout-run --provider openrouter --model openai/gpt-3.5-turbo-0613 --est-cost-cents <budget>` (cost-gated; GPT-3.5/Llama-2 are pennies). With a 2021-cutoff model, the entire 2023–2024 question set is cleanly post-cutoff.
- **Verdict:** Stage 3 is BUILT and gated; the honest blocker is model access, not method. This is the only retro number the leakage wall permits — forward forecasting (the ladder) stays the primary, fully-clean clock.

## Rules
- A protocol is **immutable once committed**. To change a knob, the universe, the label, or the
  splits, write `protocol_v2.yaml` with **new, later** test origins — never re-open an old seal.
- The headline number is always `lift_declustered` on the sealed TEST, with its block-permutation
  `p_block` **deflated** by that protocol's `n_configs_declared`.
- A null result is logged here as faithfully as a positive one. The point of the seal is that we
  cannot quietly discard the runs we didn't like.
