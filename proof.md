# proof.md — The Case (how we prove the system is strong)

> **What this is.** The outward-facing evidence that this system has genuine forecasting edge — the
> document you put in front of an investor, a collaborator, or your own future doubt. It is built for
> the **goal** (`plan.md`), not tailored to any audience; positioning falls *out of* the proof, never
> the other way around.
>
> **Two rules keep it honest.** (1) It **cites artifacts, never asserts** — every claim points to a
> number the cockpit or the DB can show live. (2) It states **maturity plainly** — what is proven
> today vs. what is not yet. A proof doc that overclaims would violate the very fallibilism we sell.
> Refresh it whenever a phase gate (`execution.md` §5) lights a new rung.

---

## 1. The thesis, transmittable in one page

*(If a reader can re-explain this after one pass, it's transmittable. That is the bar.)*

Value migrates to the **binding constraint**. When accelerating capability (cheaper compute, better
models, falling $/unit) collides with slow-moving supply (a fab, a mineral, a permit, a scarce skill),
scarcity **rent** lands on whatever saturates first and can't be substituted. The edge is to find
**where that constraint moves next — before the market prices it.**

- **Edge = our constraint forecast − what's already priced in.** Correct *and* already priced = zero return. The whole game lives in that gap.
- We never say "X will boom." We say: *given only what was knowable at date D, there is a P% chance demand for X exceeds supply by Y `[interval]` before Z `[range]`; the highest-rent bottleneck is A, not the obvious end-product B; here is what would prove it wrong.*
- We prove it the only honest way: a **tracked, scored record** — calibrated, falsifiable, with a false-positive denominator. *Scored = Brier on observable constraint-metrics (the primary, instrument-free proof that reaches even unbettable constraints); paper P&L is a conditional bonus when a liquid pure-play exists (§8.2, two-track).*
- **What we are not:** a trend-spotter, a narrative generator, or an oracle of exogenous shocks (wars, pandemics). We forecast *conditional constraint migration*.

The deeper stance (`execution.md` §0.5): **realist about the world, fallibilist about our access** —
constraints and scarcity are real; every one of our findings is a candidate for refutation.

---

## 2. The standard of proof (what we refuse to count)

We hold predictive claims to a **falsifiable, scored** bar — never to narrative.

| ❌ Not proof | ✅ Proof |
|---|---|
| A cherry-picked hit | A pre-registered claim, scored at resolution |
| A story that fits in hindsight | A backtest on **point-in-time** data, no look-ahead |
| "Directionally right" (unfalsifiable) | An explicit kill-criterion + resolution date |
| Calling every boom (recall only) | **Precision AND recall** — a false-positive denominator |
| Beating nothing | Beating a **naive base-rate baseline** |

If a skeptic cannot *try* to falsify a claim, it is not evidence. (Method: `doctrine.md`; discipline: `execution.md` §3.)

---

## 3. The ladder of proof

Each rung is a distinct, showable claim. We climb in order; lower rungs never expire.

| # | Claim it establishes | Showable artifact | A skeptic kills it by | Lights up at |
|---|---|---|---|---|
| 1 | **Method is disciplined, not vibes** | `doctrine.md` §2 checklist · §0.5 commitments · §3 quantitative discipline; every card has kill-criteria + interval | finding a forecast with no kill-criterion, no interval, or narrative-only reasoning | **now** (Phase 0) |
| 2 | **The edge has a stated, reproducible mechanism** | the constraint-migration thesis → supply graph + propagation logic | showing the mechanism makes no specific, checkable prediction | Phase 4 (stated now) |
| 3 | **Backtest holds without look-ahead** | §8 retrodiction run: precision · recall · lead-time, **method frozen** | finding look-ahead, or recall achieved without precision | Phase 6 — *sweep-hardened: 1.93× lift held 5/5 origins, Fisher p<.001, honest LOCO Brier beats baseline; recall 39% + lead-time still partial → strengthened, not lit* |
| 4 | **Our probabilities are honest** | Brier + reliability curve vs. base-rate baseline (cockpit) | showing Brier ≤ baseline, or a miscalibrated curve | Phase 3 → matures |
| 5 | **We called it, on the record, and it resolved right** | immutable forecast registry, scored at resolution | finding an edited card, post-hoc dating, or survivorship in the record | Phase 3+ (compounds) |
| 6 | **The edge was real and still capturable when found** | median lead-time vs. a timestamped consensus proxy (market price *or* non-market mention/coverage/survey count, pillar 7) | showing flags *lag* the consensus rather than lead it | Phase 5–6 |
| 7 | **Acting on it beats a benchmark** *(bonus track — conditional)* | paper P&L vs. a benchmark, **only when a liquid pure-play + consensus gap both exist** | underperformance vs. the benchmark *where a bet was placeable* | Phase 7+ |

Rungs 3–5 are the spine; rung 5 (the live track record) is the **moat** — it compounds and cannot be
faked after the fact. **Two-track proof (§8.2):** rungs 4–6 (Brier-scored constraint forecasts) are the
*primary* proof and reach the deepest, unbettable constraints; rung 7 (P&L) is a *conditional bonus* — most
deep calls have no instrument, and that is expected, not a failure.

---

## 4. Where we stand today (honest)

- **Rung 1 — lit.** The method, the foundations, and the quantitative discipline exist and are inspectable right now.
- **Rung 2 — stated, not yet demonstrated.** The mechanism is fully articulated; it gets *shown* when the graph runs (Phase 4).
- **Rung 3 — strengthened, not yet lit.** The time-machine backtest (`engine/backtest.py`) runs point-in-time with **no look-ahead (assert-enforced)**. After correcting the base rate 72%→35% (14 laggard controls) and grading in log-space against the thesis target *"did it gain share of its field?"*, a **rolling-origin sweep** (origins 2008→2016) shows a **1.93× lift that holds at 5/5 origins** (1.44–2.28×; 69% precision vs 36% base), **Fisher-exact p<0.001**, and an **honest leave-one-cutoff-out Brier 0.205 < 0.229** — firing beats the base rate *out of sample*, so the probabilities are now demonstrably informative, not overconfident. Two honest limits keep the rung un-lit: **recall is 39%** (a precision instrument, not coverage — the biggest share-gainers were flat at the cutoff), and the tiny p is **clustering-optimistic** (the same concepts recur across origins), so the 5/5 consistency — not the p — is the load-bearing evidence. The companion **§8 case corpus** (`engine/retro.py`) carries the named winners/fizzles + lead-time. We report the edge and its limits together — and on the record, an honest single-cutoff run first showed *no* edge before the sweep corrected that overstatement.
- **Rungs 4–7 — pending their phases.** We have **zero resolved forward forecasts**, so we claim **no live calibration and no track record yet.**

Saying this plainly *is* the first proof: a system that operates as advertised reports its own immaturity
instead of dressing method up as results — and when an honest backtest first showed *no* edge (acceleration
mean-reverts), we published that before finding the target on which an edge actually holds. The credible
near-term milestone is **Phase 6** (retrodiction passes precision *and* recall, calibrated) — the first
moment "we're real" is a number, not a claim.

---

## 5. Verify us yourself (don't trust — check)

This doubles as the diligence pack. Every check is reproducible:

1. **Re-run the retrodiction harness** point-in-time and confirm precision *and* recall, not recall alone (§8, Phase 6).
2. **Inspect the forecast registry** — cards are immutable; corrections are `supersede` chains; resolution dates and kill-criteria predate resolution.
3. **Read the calibration curve** against the naive base-rate baseline in the cockpit — not our adjectives.
4. **`grep` for look-ahead** — that no backtest fact post-dates its as-of stamp.
5. **Check provenance** — every `Source` carries a non-empty `trust_rationale` (rank ≠ trust; CONSTITUTION rule 1).

Reproducibility is the proof. If any check fails, the corresponding rung is not earned — and this document should say so.

---

## 6. Who recognizes this (positioning, derived — not targeted)

Built for the goal; we do **not** bend the system to an audience. But the proof, once it exists, is
legible to anyone exposed to where scarcity moves:

- **Capital allocators** — a pre-consensus, scored read on constraint migration is, by construction, a mispricing signal.
- **Operators / strategists** — deciding *where to build* is a bet on the next binding constraint.
- **The operator (us)** — the first and most skeptical customer; the cockpit is the steering surface.

Positioning is a *consequence* of clearing the ladder, not an input to what we build.

---

## 7. How we'd know we're wrong (system-level kill-criteria)

The whole system is itself falsifiable. We would declare **no demonstrated edge** — and this document
would say so — if, after a meaningful N of resolved forecasts:

- rolling **Brier ≤ base-rate baseline** (probabilities add nothing), **or**
- retrodiction passes on **recall but fails precision** (we just cheer winners), **or**
- median **lead-time ≤ 0** (we lag the price — correct but not capturable), **or**
- **decision value < benchmark** (right on paper, useless in allocation).

We would rather know. A foresight engine that can't be proven wrong is the thing it exists to reject.

---

## 8. Open gaps in the proof itself (named, not faked)

Two gaps weaken the case today. Naming them *is* the discipline.

1. **Look-elsewhere correction on the detector σ — BUILT (2026-06-03, `engine/significance.py`).**
   We reported per-series σ (transformer 10.6σ, Epoch Vision "43345σ") with no null and no
   denominator — the Gaussian tail is a fantasy on ~10 points (the 43345σ is the tell: a collapsed
   noise estimate, not reliability). Now an additive layer (the frozen detector is untouched) runs
   detect() on M=2000 synthetic nulls per series — "the early trend continues + Gaussian noise at the
   detector's own MAD-σ" — and reports an **empirical p** = (1+#{null σ ≥ observed})/(M+1), then
   **Benjamini-Hochberg FDR** at q=10% across the whole scan. First run: **scanned 230 · fired 123 raw
   · 102 survive BH-FDR · expected false discoveries ≤ 10.2.** The synthetic flat control is silent
   and non-significant (2.0σ, p=0.37); the real accelerations survive (transformer PPI p=0.002; deep
   learning / DNA-seq / lithium-ion / solar p<0.0005); **21 marginal 3–7σ fires are FDR-rejected** as
   look-elsewhere false positives (blockchain-SEC, IoT, crispr-patents, AR…) — the false-positive
   denominator *at the detector* (the §2 denominator is at the gate; goal.md: recall at the detector,
   precision at the gate). The σ is now a **ranking; the p + survival flag is the reliability.** A
   discrete-bootstrap null was tried first and **cut as pathological** (small-window resamples collapse
   the MAD-σ → spurious 1e6 surprises that falsely rejected real signals) — logged in the module, not
   hidden. Honest limit kept: the i.i.d.-Gaussian null ignores autocorrelation → p is mildly
   anti-conservative. Renders in the cockpit (#frontier: per-fire p + survival + the run summary).

2. **The unbettable-edge tension — RESOLVED (two-track, 2026-06-03).** The deepest constraints we
   derive (GOES, the interconnection queue) have **no public pure-play**, so a P&L record cannot reach
   where the real alpha lives — and both domains run so far returned *priced / inconclusive* on the
   bettable layer. **Decision (Ruben):** "proven" is **two-track** —
   - **Primary track (always): Brier-scored forecasts on observable constraint-metrics**, instrument-free
     (e.g. "GOES supply gap > X by date Y"; "transformer PPI ≥ 1.5× baseline through 2028"). This is the
     proof that reaches the deep edge, and it is falsifiable without any market.
   - **Pre-consensus** for unbettable layers is measured as **divergence from a timestamped non-market
     consensus proxy** (mention / coverage / expert-survey count in Pillar 7), not only market mispricing.
   - **Bonus track (conditional): paper P&L** only when a liquid pure-play **and** a consensus gap both
     exist. Most deep calls won't qualify — that's expected, not a failure.
   See `doctrine.md` §0.6 for the related leakage rule (judgment is validated forward, never retro).

---

## Supporting proof artifacts (reserved — Mendeleev; created when there's evidence to fill them)
- `[ ]` **One-page extract** — §1 alone, for a cold reader.
- `[ ]` **Per-case retrodiction write-ups** — one `(signal_date → what was knowable → our call → outcome → who captured rent → lag)` story per §8 case.
- `[ ]` **Live scoreboard snapshot** — exported from the cockpit (calibration, lead-time, track record).

*Earn-your-place: these are slots, not files. Build each when the evidence to fill it exists.*
