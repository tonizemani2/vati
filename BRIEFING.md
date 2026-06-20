# BRIEFING.md — The whole initiative, in one place

> One transmittable document for four jobs: (1) hand it to another AI as full context,
> (2) explain the project to other people, simply, (3) re-orient yourself, (4) read my honest
> opinion. It is layered — read only as deep as you need. Layer 0–1 is the human pitch;
> Layer 7 is my unhedged take; the Appendix is the paste-into-an-AI block.
>
> It cites the repo's own honest record (`plan.md`, `execution.md`, `proof.md`, `doctrine.md`,
> the sealed experiment ledger). Where the truth is uncomfortable, it says so — that is the
> entire point of the thing being described.

---

## Layer 0 — In one paragraph

I'm building a machine that predicts **where scarcity and value will move next**, and proves it
with a **scored, sealed, un-editable track record** instead of a story. The bet: when fast-improving
technology collides with something slow to build — a mine, a fab, a transformer, a skilled trade, a
permit — the profit migrates to that **bottleneck**. The craft is to find the bottleneck *one layer
deeper* than the obvious headline, write a **dated, falsifiable** prediction with a number and a
kill-condition, and let time grade it. The product is not a tip — it's the **track record**. And the
thing that makes it trustworthy is that it is engineered to **catch itself being wrong**, which it
already has, repeatedly and on the record.

---

## Layer 1 — The one-page story (explain it to anyone)

**The thesis, in one line.** Rent accrues to the binding constraint. Find where the constraint moves
next, before the market prices it.

**Why it can work.** A correct forecast that everyone already believes is worth nothing. The edge
lives in the *gap* between where the bottleneck will actually be and where capital currently thinks
it will be. A reasoning engine can own three honest advantages: (1) **calibration** — say 70% and be
right 70% of the time; (2) **depth** — go one layer beneath the published thesis (the steel beneath
the transformer, the input beneath the input); (3) **a compounding scored record** — the real moat,
because it can't be faked after the fact.

**What a forecast looks like here.** Never "X will boom," never a stock pick. It is:

> *"Given only what was knowable on date D: over the next N years, [sector] reorganizes so that
> [measurable claim] — because the binding constraint is **A**, not the obvious end-product **B**.
> Consensus says X; I predict **Y [interval]**, resolved by [dated metric] on date Z. Here's what
> proves it wrong."*

**What makes it honest (and unusual).** Every claim is falsifiable, dated, and scored with a Brier
score at resolution. The system distrusts its own outputs and hunts disconfirmation first. It logs
its gaps instead of hiding them. When an honest test showed the engine had *no* edge, that was
committed to the record — not deleted.

**The sealed record is proof of edge, not a moat.** Models are swappable; the un-fakeable record of
dated calls is genuine evidence — but it only *certifies* edge, it doesn't protect it. A real moat is a
better method, exclusive data, or owning the benchmark. You cannot manufacture a track record overnight,
which is what makes a real one credible — but credibility ≠ defensibility.

---

## Layer 2 — What has actually been built (honest inventory)

A thin software **instrument** wrapped around human + AI judgment. Two folders, one SQLite database.
The code is scaffolding; the intelligence is the reasoning loop and the record.

**Live data substrate** (all keyless / free, self-collected): **557 sources · 550 series · 22,651
observations** across the causal chain — research output, capability cost-curves, dependency graphs,
supply-elasticity price signals, demand/adoption, capital flows, market pricing, policy/decrees,
outcomes.

**The 9 pillars** (causal order): Frontier → Capability curves → Dependency graph → Supply elasticity
→ Demand → Capital → Market pricing (the *gate*) → Policy/geo → Outcomes. Value concentrates in the
dependency-graph and supply-elasticity layers; market pricing is the gate (correct + priced = zero
edge).

**The FORCES axis** (added because the spine was blind to them): politics/geo (export-control decrees
— both US OFAC/BIS *and* China MOFCOM channels wired), social/demographic (labour & acceptance caps),
talent inflow, narrative. Each held to the same falsifiable-scored bar, never punditry.

**The working machinery** (17 components; the ones that matter):
- A **frozen mechanical detector** (robust-slope + noise-floor surprise) with an empirical-null /
  FDR layer so a "σ" is a ranking and a p-value is the reliability.
- A **dependency/supply graph** with constraint-propagation — flow a demand shock, find the
  first-saturating, least-substitutable node.
- A **consensus / priced-in gate** ("consensus-eye") — multi-channel read of whether the thesis is
  already believed (narrative saturation, forecaster outlets, price run-up).
- A **hypothesis engine** ("the oracle") — the generative half: propose a constraint-migration
  thesis through a lens, then force it through the same falsifiable gate; it kills its own seductive
  narratives on demand.
- A **forecast registry** — immutable, supersede-never-edit, Brier at resolution.
- A **sealed experiment apparatus** — pre-registered protocols committed to git as the seal *before*
  any test score; block-permutation nulls, multiple-testing deflation, leakage tripwires. **56
  configurations tried** are logged as the deflation denominator (it counts its own p-hacking risk).
- A **cockpit** (Next.js) + a hand-maintained **status.html** visual map, and a **Vaticinus** landing
  site.

**The forecast record today:** **~53 live forward structural calls**, sealed, resolving **2027–2028**.
(The DB shows ~7,900 "forecast cards," but the overwhelming majority are *persistence-ladder rungs* —
a calibration backtest — not forward calls. Be precise about this when you explain it.) Hypotheses:
10 promoted · 9 survived · 5 parked · 4 killed.

---

## Layer 3 — What has actually been found (results, including the negatives)

This is where the honesty discipline earns its keep. Read all of it together — the wins and the nulls.

**Confirmed positives:**
- **The instrument runs and gates correctly.** Data flows through GIGO/quality/FDR gates; the
  detector fires on real accelerations and stays silent on synthetic flat controls. The hard QC gate
  refuses stale/incomplete data into a forecast.
- **Recall on a known case is real:** the talent-inflow channel flags deep learning at ~2013, ~4
  years early — the kind of structural shift the old coarse-count approach missed.
- **A leak-gated older-model holdout came out positive (indicative).** Run on GPT-3.5 (2021 cutoff)
  with a leakage probe gating out any question whose outcome predates the model's effective cutoff:
  **Brier 0.110 vs 0.245 base, 6/7 correct on 7 leak-free questions.** Flagged INDICATIVE, N=7 — not
  validated, but the right sign.

**Honest negatives — the system caught its own false positives:**
- **The retrodiction "detector edge" did not survive honest testing.** v1 gave a deflated p=0.013, but
  the concept-disjoint v2 split collapsed it; a power analysis then showed v2 was *under-powered*
  (fired on 2 of 60 concepts) — so the count detector's edge is **neither proven nor refuted**, and
  the chapter was closed as *tautological* (predicting attention from attention). No p-hacking re-run.
- **A fair external test showed the raw model has NO edge** (committed, `867ce29`) — published, not
  buried.
- **Stage-2 "locator" (the thesis test with an independent price label) is a null at N=5** — 20% hit
  rate, below random. The constraint migration was judged *real* (rent landed on deep electrical
  steel) but **not mechanically predictable from price at that altitude and sample size.**
- **Cross-industry talent is not scientifically measurable** with open data (GitHub repo-counts tried
  and removed: repos ≠ people). Marked NOT MEASURABLE rather than faked.

**The meta-finding that matters most:** what is *demonstrated* today is the **apparatus that honestly
tests for edge** — the sealing, the nulls, the power analysis, the leakage gating. The *edge on the
actual deliverable* (forward structural calls) is **not yet demonstrated and cannot be until 2027–28**.
That is a structural fact about time, not a failure of effort. (See `doctrine.md §0.6`: the detector
is retro-testable now; the human+AI *judgment* — the soul of the thing — can only be validated
forward, because the model's weights already contain past outcomes.)

---

## Layer 4 — The ideas over time (how the thinking evolved)

The intellectual journey is itself part of the asset — it shows the method working on itself.

1. **"An AI that predicts the future"** → narrowed to the honest, doable core: **capability-vs-supply
   collisions**, scored, falsifiable. (The grand "any industry" headline became a scoped instrument.)
2. **From themes to needles.** Early runs surfaced vague themes ("supercomputing"). Fixed by ranking
   on *un-priced-ness* (saturation), not move-magnitude (σ): a theme is never a needle; the edge is
   the inelastic input beneath it.
3. **From stock-picks to structure.** The deliverable kept drifting down into micro stock-picks and
   got correctly killed on "no clean instrument / already priced." Locked the rule:
   **physical-primary, financial-optional** — score the constraint metric (capacity, lead-time, TWh,
   price), a tradeable instrument is an optional second expression, never the proof.
4. **Closing the loop.** Added outcome + Brier back-propagation and base-rates-by-kind, so the system
   measures *which kinds of corner pay* — not just whether one pick was right.
5. **The FORCES axis.** Recognized a structural blind spot — politics, social, talent, narrative could
   relocate scarcity and never surface autonomously (same failure class as missing deep learning).
   Opened them as first-class channels, same discipline.
6. **The Vati pivot.** Re-pointed from "forecasting engine" to **honest, leak-free forecasting
   *instrument*** proven by its own scored STRUCTURAL record (prediction-market benchmarks removed — wrong
   question class). The sealed record is **proof of edge, not a moat**; a real moat is method/data/referee;
   the durable layer is the method, models are swappable.
7. **The retro-verify reckoning.** Tried hard to validate the past without LLM bias, built a rigorous
   sealed apparatus — and used it to *refute its own headline claims*. This is the maturity moment:
   the project's defining behavior became "catch yourself being wrong."

The through-line: **realist about the world, fallibilist about our access to it.** Constraints and
rent are real; every one of our findings is a candidate for refutation.

---

## Layer 5 — The honest scorecard (what's proven, what's not)

| Rung | Claim | Status |
|---|---|---|
| 1 | Method is disciplined, not vibes | **Lit** — kill-criteria, intervals, doctrine all inspectable now |
| 2 | The edge has a stated, reproducible mechanism | Stated; shown when the graph runs |
| 3 | Backtest holds without look-ahead | **Strengthened but not lit** — detector edge neither proven nor refuted under honest splits |
| 4 | Our probabilities are honest (calibration) | Pending forward resolution |
| 5 | We called it, on the record, and it resolved right | **Pending** — zero resolved forward forecasts yet |
| 6 | Edge was real *and still capturable* when found | Pending |
| 7 | Acting on it beats a benchmark (P&L) | Conditional bonus, pending |

**The blunt summary:** Rung 1 is real and rare. Rungs 4–7 — the ones that prove foresight — are
**empty until 2027–28**. There is **no live calibration and no track record yet**, and the document
that says so (`proof.md §4`) saying so plainly *is* the first proof.

**The moat,** restated: rung 5, the compounding sealed record, is the only thing that can't be faked or
copied. Everything upstream is method and scaffolding. The asset is the clock, once it starts ticking
on enough good forward calls.

---

## Layer 6 — As a business / initiative (what this could become)

**What it is not, today:** not a fund, not a SaaS, not a product with revenue. It is a research
instrument plus one person's disciplined judgment, plus the beginning of a track record.

**The honest business truth:** until the forward cards resolve, there is no fully proven edge to sell as
a finished product. But there is a near-term design-partner offer: decision memos that translate each
forecast into exposure, action now, decision changed, ROI/risk logic, first trigger, and kill condition.
So the correct near-term move is two-track: **maximize the number and quality of dated forward calls now**
so the clock starts, while using Pope-style memos to test whether buyers will pay for practical constraint
intelligence before the scored record matures.

**Three plausible shapes it could grow into** (not mutually exclusive):
1. **A verifiable forecaster reputation** → once the scored record is credible, sell pre-consensus
   constraint-migration reads to capital allocators and operators deciding *where to build*. The
   buyers are anyone exposed to where scarcity moves.
2. **The instrument as the product** → the honesty-first forecasting harness (sealing, leakage
   gating, calibration scoring) is itself rare and licensable — most "AI predicts X" tools have none
   of it.
3. **A decision-value layer** → capital-allocation calls derived from the forecasts, scored against a
   benchmark (the "north of north" metric).

**Fundraising reality:** public forecasting benchmarks are not the product, but they are useful proof for
a solo founder. Use Metaculus/FutureEval/ForecastBench results and a credible fine-tune/data plan as the
investor credential while keeping the commercial story anchored in ROI: fewer wrong capex, procurement,
portfolio, hedge, partnership, and policy decisions.

**Why it's differentiated:** the market is flooded with confident, unfalsifiable AI-forecasting hype.
This initiative's entire identity is the opposite — falsifiable, scored, self-refuting. In a field
where the default failure is overclaiming, *credible honesty is the wedge*. The risk is the mirror
image: it is so honest that it currently has little to show, and the payoff is years out.

**Who recognizes it:** capital allocators (a pre-consensus scored read is a mispricing signal),
operators/strategists (where-to-build is a bet on the next constraint), and the operator himself (the
first and most skeptical customer).

---

## Layer 7 — My honest opinion (no hedging)

**What's genuinely impressive, and rare.** The honesty machinery is the real achievement. I have seen
many "AI predicts the future" projects; their defining trait is that they cannot fail in their own
eyes. This one's defining trait is that it is *built to fail loudly* — and it does. The v2 power
correction, the locator null, the "raw model has no edge" commit: those are not embarrassments, they
are the product working. The sealed-record / time-moat insight is correct and most people miss it. The
"one layer deeper, physical-primary" forecasting craft is intellectually sound. **If you keep nothing
else, keep the discipline — it is the moat, more than any model.**

**The hard truth you should not flinch from.** Right now there is **no demonstrated forecasting edge on
the actual deliverable.** The retrodiction edge keeps dissolving under honest testing; the judgment —
the soul — *cannot* be retro-validated (parametric leakage), only forward-validated; and you have zero
resolved forward cards. So today the project is a **beautifully honest apparatus that has not yet
proven it can predict anything.** That is not a criticism of the work — it is a structural fact about
where you are on the clock. But you must say it exactly that plainly to others, or you become the thing
you built this to reject.

**The single biggest risk** is not being wrong — it's **complexity outrunning legibility.** 17
components, 9 pillars, a forces axis, three validation stages, sealed experiments. The "thin
scaffolding" ideal is under strain. For a one-person initiative whose value is judgment, every hour on
infrastructure that doesn't produce a *dated forward call* is an hour the clock isn't ticking. Be
ruthless here.

**What I would do next, in order:**
1. **Start the clock harder.** The 53 live calls are the asset. Get to a focused, defensible set of
   high-conviction forward calls with clean kill-criteria, and *stop building instrument*. Your own
   rules already say this; follow them.
2. **Make the simple story unmissable.** The Layer-1 pitch above should be the front door — a smart
   outsider should re-explain it after one read. Right now the depth is gorgeous and the door is hard
   to find.
3. **Run the rigorous older-model holdout** (GPT-3.5-0613 via OpenRouter, pennies, cost-gated). It's
   the one near-term test that can move judgment-validation from "indicative, N=7" toward real signal
   without waiting for 2028. The blocker is model access, not method.
4. **Resist the urge to add another channel.** The next channel is almost never the bottleneck. The
   bottleneck is *resolved forward calls*, and only time supplies those.

**My overall read:** this is a serious, unusually honest piece of intellectual work whose value is
**latent and time-locked.** It is not yet a proven forecaster and shouldn't pretend to be — but it has
done the one thing that lets it *become* one: it built the discipline to know the difference. I'd back
the method. I'd start the clock and protect it from your own appetite for more machinery.

---

## Appendix — Paste-ready context block for another AI

> Copy everything below this line into another AI to give it complete context.

```
You are being briefed on a project called Vati / Vaticinus ("predict the future").

GOAL: Produce calibrated, falsifiable, structural forecasts of where scarcity/value will migrate —
where accelerating capability collides with slow-moving supply — and prove it with a tracked, scored,
sealed record. Thesis: rent accrues to the binding constraint; the edge is finding where the
constraint moves next, before it's priced in. A correct-but-priced-in forecast is worth zero.

FORECAST FORMAT (never a stock pick, never "X will boom"):
"Given only what was knowable on date D: over N years, [sector] reorganizes so that [measurable claim],
because the binding constraint is A not obvious end-product B. Consensus says X; I predict Y [interval];
resolved by [dated constraint metric] on date Z. Here's the kill-criterion." Scored by Brier at
resolution. Physical-primary (score the constraint metric: capacity/lead-time/TWh/share/input price),
financial-optional (a tradeable pair is an optional second expression, never the proof).

WHAT'S BUILT: A thin software instrument (Python engine + Next.js cockpit, two folders, one SQLite DB)
around human+AI judgment. 557 sources / 550 series / 22,651 observations, all keyless/free. 9 causal
pillars (Frontier→Capability→Dependency graph→Supply elasticity→Demand→Capital→Market pricing[the
gate]→Policy→Outcomes) + a FORCES axis (politics/social/talent/narrative). Key parts: a frozen
mechanical detector with empirical-null/FDR; a dependency graph with constraint-propagation; a
priced-in "consensus-eye" gate; a hypothesis engine ("oracle") that gates its own ideas; an immutable
forecast registry; a sealed pre-registered experiment apparatus (block-permutation nulls, multiple-
testing deflation over 56 logged configs, leakage tripwires).

RECORD: ~53 live forward structural calls, sealed, resolving 2027-2028. ZERO resolved yet. (DB has
~7,900 "cards" but those are mostly persistence-ladder calibration rungs, not forward calls.)

WHAT'S PROVEN vs NOT (be precise): Method discipline is real and inspectable now. Recall is real on a
known case (flagged deep learning ~2013, ~4y early). A leak-gated older-model holdout (GPT-3.5,
2021 cutoff) came out positive but INDICATIVE only (Brier 0.110 vs 0.245 base, 6/7, N=7). HONEST
NEGATIVES the system caught itself: the retrodiction detector "edge" did not survive honest concept-
disjoint splits (under-powered; neither proven nor refuted; closed as tautological); a fair external
test showed the raw model has NO edge (committed, not buried); the Stage-2 price-label "locator" is a
null at N=5; cross-industry talent is NOT scientifically measurable with open data (marked, not faked).
CRITICAL: there is NO demonstrated forecasting edge on the actual deliverable yet, and there cannot be
until forward cards resolve in 2027-28. The human+AI JUDGMENT can only be validated forward (parametric
leakage: the model's weights already contain past outcomes, so retrodiction validates only the frozen
mechanical detector, never the judgment).

STANCE: Realist about the world, fallibilist about our access. Distrust your own findings; hunt
disconfirmation first; log gaps instead of hiding them; supersede never edit; kill-criterion + interval
on everything or it's not a forecast. The sealed record is PROOF of edge, not a moat (a real moat is
method/data/referee); models are swappable.

When reasoning for this project: be a fox not a hedgehog; do NOT feed me expert predictions as priors
(that's the consensus we exist to beat); my edge is fresh point-in-time data + disciplined epistemics.
Commit to a position, mark the boundary of the claim as precision, never retreat to "on one hand / on
the other."
```
