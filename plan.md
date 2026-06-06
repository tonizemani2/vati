# plan.md — The North Star

> **This file is write-once-then-stable.** It states the one goal and how we'll know we hit it.
> Changing it is itself a pivotal Decision (logged, approved) — not a casual edit.
> `CONSTITUTION.md` says *how we work*. This file says *what winning is*.

---

## The Goal

**An AI that predicts the future.**

Concretely: a system that produces **calibrated, falsifiable, structural forecasts of where major value and scarcity will migrate — where accelerating capability meets slow-moving supply — and proves it with a tracked, scored record.** The edge is **not secret content.** It is three things a keyless reasoning engine can actually own: (1) **better calibration** than the vague consensus on a partially-visible thesis — predict Y when the crowd says ~Z and be numerically right on the dated metric; (2) **going one layer deeper** than the published thesis (the conversion step beneath enrichment, the steel beneath the transformer, the input beneath the input); (3) a **compounding scored record** — the real moat. "Pre-consensus" is a humble tag we attach in-session and let the record adjudicate; it is never the claim, never a gate.

*(Scope note: this narrows the prior "across any industry" headline to what the instrument actually does well — capability-vs-supply collisions. Widening to slow non-acceleration constraints, e.g. demographics/depletion, remains an open Decision per `execution.md §10`; accepting this amendment ratifies the narrowing until that Decision is taken. Amended by Decision logged 2026-06-04 per `REVIEW.md §0`.)*

*(Scope amendment 2 — the FORCES axis, Decision `40f7743d` logged 2026-06-05: scarcity is also relocated by forces that act ACROSS the capability→supply spine — **politics/geo** (a state cornering an input by decree), **social/demographic** (a labour or acceptance cap), **talent** (elite flux — already the recall jewel in `research.py`), **narrative/news**. The discovery funnel was structurally blind to them (a politics- or society-driven constraint migration could never surface autonomously — the same failure class as missing deep learning). This amendment widens scope to include these as **first-class binding-constraint channels**, held to the SAME falsifiable-scored discipline (a leading signal + a dated constraint metric + Brier) — never punditry. It does NOT loosen the bar; it adds force-driven collisions alongside capability-vs-supply ones. See `engine/pillars/forces.py` + `execution.md §3 (Forces axis)`.)*

We are not building a trend-spotter or a narrative generator. We are building a machine that finds, earlier and better-calibrated than consensus, the collisions where **accelerating capability meets slow-moving supply** — because that is where scarcity rent migrates, and rent accrues to the binding constraint.

The output is never "X will boom" and never a stock pick. It is a dated, falsifiable structural claim:

> *"Given only what was knowable as of date D: over the next N years, [sector/sub-sector] reorganizes such that [measurable structural claim] — because the binding constraint is **A**, not the obvious end-product **B**. Consensus's base case is X; I predict **Y `[credible interval]`**, resolved by [dated structural metric] on **date Z `[earliest–latest]`**. Here is what would prove this wrong (falsification → scored Brier), and here is what would make it moot (premise-void → not scored)."*

The forecast scores on the **constraint metric** (capacity, lead-time, TWh, share, the input's own price) — **physical-primary, financial-optional**. A tradeable instrument is an optional second expression, never the proof. Every magnitude and date carries a method-produced interval; a bare point estimate is a story. (See `execution.md` §3 "Quantitative discipline.")

---

## The Scoreboard (how we measure "huge")

All five are surfaced in the cockpit. A capability that doesn't move one of these numbers has to justify its existence.

1. **Calibration** — rolling Brier score + a calibration curve across all resolved forecasts. Must beat a naive base-rate baseline. *(Are our probabilities honest?)*

2. **Retrodiction benchmark** — the acceptance test. Using **only point-in-time, pre-inflection data**, the system must both:
   - **rediscover** major shifts (AI chips, GLP-1, cloud, solar/batteries, shale), **and**
   - **reject** the famous fizzles (hydrogen economy, cleantech 1.0, consumer 3D printing, etc.).
   - Scored on **precision AND recall** — never recall alone. A system that only retrodicts winners has learned nothing about its false-positive rate.
   - *Honest scope (`doctrine.md §0.6`): the retrodiction pass validates the **frozen mechanical detector only** — the LLM's weights already contain these outcomes, so it says nothing about the oracle's judgment, and its cases are eventually-obvious by construction. It is a detector sanity check, **not** the gate that says the edge is real. The bias-proof universe benchmark (drawn-by-rule, de-clustered, Fisher p≈0.13 "suggestive") is the more honest — and weaker — number; lead with it.*

3. **Lead time** — median months a constraint is flagged *before* consensus / market pricing reflects it. *(Is the insight still mispriced when we find it?)*

4. **Live track record** — count and accuracy of forward forecasts, each with a resolution date and kill-criteria, scored as they resolve. This compounding record is the real moat — not the code, not the data.

5. **Decision value** *(north of north)* — capital-allocation calls derived from forecasts, scored against a benchmark.

---

## Ambition vs. near-term proof

- **Ambition:** a trillion-dollar-relevant foresight engine — the layer that sees constraint migration one step before the market.
- **Near-term proof that we're real (honest):** there is **no calibration evidence on the actual deliverable (structural calls) until forward cards resolve in 2027–28.** Until then the only interim proxies are (a) each structural call **surviving an adversarial priced-in challenge at authoring time** (the consensus-eye gate + the independent multi-skeptic panel + a separate-model search for the published thesis), and (b) the **persistence ladder staying calibrated** — explicitly a persistence backtest, not proof of foresight. The retrodiction pass is **not** counted as proof-of-edge.

---

## What this is NOT

- Not an oracle. We forecast *conditional constraint migration*, not exogenous shocks (wars, pandemics).
- Not consensus-following. A correct forecast that is already priced in is worth zero. The edge lives in the **gap** between where the constraint will be and where capital currently thinks it will be.
- Not a data-ops platform. The intelligence lives in the reasoning and the human's decisions; the code is thin scaffolding. (See `CONSTITUTION.md`.)
