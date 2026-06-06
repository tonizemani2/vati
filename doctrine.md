# doctrine.md — How We Reason (the forecasting craft)

> **Alterable, like `execution.md`.** `plan.md` says *what winning is*; `CONSTITUTION.md` says
> *how we work*; `execution.md` says *how we get there*; **this file says *how we reason*.**
> It is the durable epistemic method — the "Bucket 1" canon — loaded as **method, not as answers.**
> Read it before generating any forecast, hypothesis, or red-team.

---

## 0. Why this file exists (the contamination decision)

Expert input splits into three buckets. We treat each differently — on purpose:

1. **Epistemics — *how* to reason under uncertainty.** → **Internalize aggressively.** This file.
   Near-zero contamination; the model is sloppy here by default and improves a lot with scaffolding.
2. **Causal frameworks — mental models for *where* value migrates.** → **Use as *lenses* to generate
   hypotheses, then make the data try to kill them.** Tagged as lenses, never asserted as truth.
   (Lives in the Hypothesis engine, component #8; red-teamed by #9.)
3. **Expert *predictions* — what smart people currently think will happen.** → **Never loaded as
   reasoning context.** That *is* the consensus we exist to beat (`plan.md`: correct + already priced
   = zero). We ingest it as **timestamped data in Pillar 7** (the priced-in benchmark we measure our
   divergence against), never as a prior we reason *from*.

**The key reason this matters for us specifically:** a frontier model already absorbed the expert
canon in pretraining. Re-feeding expert takes adds little information and a lot of anchoring — it
amplifies the median prior, pulling us toward the very consensus we must beat. Our edge is the two
things the model is genuinely weak on: **fresh point-in-time data** (the 9 pillars) and **disciplined
epistemic structure** (this file). Optimize those; starve the anchor.

### 0.6 The two leakages — and why retrodiction can never validate judgment

The model's training cutoff is *past* most test dates. So when we retrodict (judge a pre-2026 case),
the answer is already in the weights. There are **two distinct leaks**, with **opposite fixes**:

1. **Data leakage** — feeding observations dated after the cutoff. Controllable, controlled:
   `as_of ≤ signal_date`, grep-verified (Phase 6: 0 look-ahead violations).
2. **Parametric leakage** — the outcome is baked into Claude's weights. Claude *knows* deep learning
   won, scRNA-seq took off, GPU→transformer rent migrated. **This cannot be removed.**

**Prompting does NOT fix #2.** "Act as if it's 2017" is theater — hindsight isn't a withheld fact, it
shapes what the model finds salient, which mechanism it reaches for, which curve it calls "the real
one," how confident it is. A model told to roleplay the past walks straight to the thing it remembers
mattered. So **a backtest of Claude's *judgment* is near-worthless as evidence.**

The fix is **architectural, not prompted**:
- **Keep the LLM out of the scoring loop for anything retrodicted.** Our retro score comes from a
  *frozen mechanical rule* (`detector.detect` + `p=logistic(σ−k)`) run on `as_of`-gated data — math on
  a point-in-time series can't leak. That number is clean. Claude's *opinion* about the case is not.
- **The judgment / generative half (oracle #8, case selection, curve choice) can ONLY be validated
  forward** — on forecasts whose **resolution date is after the cutoff**, where leakage is impossible
  by construction (forward cards resolving 2027–2028 are clean; Claude knows the present trajectory —
  legitimate — but not the outcome).

**Therefore: retrodiction validates the *detector*; only the forward track record (Phase 7) validates
the *thinking loop* — the thing this whole system is actually about.** Treat oracle retro-theses as
illustration, never proof. Log the leak as a known limit (logged-not-faked applied to our own method).

---

## 1. The core stance — be a fox, not a hedgehog

Tetlock's central finding: calibrated generalists who hold *many* loosely-held models and update
often ("foxes") beat charismatic single-Big-Idea experts ("hedgehogs") — and the **most-cited,
most-confident pundits are often the *worst* calibrated**, because boldness earns airtime, not
accuracy. So: many lenses, lightly held; distrust the compelling single narrative (especially our
own); confidence is a claim to be earned by a track record, not a tone.

---

## 1.5 — What we read in research (the leading grain)

Research is where it starts, and we should say *why* plainly: of the 9 pillars, **research moves
first**. A capability shows up in papers *before* it shows up in cost curves, capital, prices, or
policy. So the paper stream is the **earliest grain of the frontier** — the first place "where the
future is going" is legible.

But we are **not** reading research to find "what's a big/popular topic." Aggregate counts (how many
AI papers this year) are the *last* place a signal appears — by the time the count explodes, it's
priced. That is exactly the blind spot we diagnosed (the system went silent on deep learning at 2010
because it read one coarse annual-count channel). **The alpha is finer.** What we actually hunt for in
the paper stream, per technique, is:

1. **Acceleration of a technique's *share*** — a method going 0.1% → 5% of a field's literature (the
   2nd derivative bending up), caught long before the raw count saturates.
2. **Cross-field diffusion** — a technique born in field A appearing in B, then C. This is the
   deep-learning signature (CS → vision → speech → biology, years before the count exploded):
   *diffusion precedes volume.*
3. **Talent inflow** — new authors and elite labs pivoting *into* a topic (early commitment).
4. **Citation-graph reorientation** — a method becoming a hub others build on. (Hard: needs the
   citation graph, a known free-data gap — sought, not faked.)

And we read all of it against the one thesis — **rent accrues to the binding constraint.** The research
signal is *not the prediction*; it is the early warning that a capability is about to create demand,
which then must be traced to the inelastic input behind it (the supply/dependency graph). The edge is
the **conjunction**, not the paper alone:

> capability accelerating in research (a LEADING channel) **+** money / attention / policy still flat
> (the LAGGING channels) = **EARLY / not yet priced.**

That conjunction is the operative filter (it lives in `discover.py`'s pre-consensus cross-reference,
where `arxiv` is a leading provider). And the sequence is **open first, idea second**: roam the whole
corpus and compute the fine signals across *all* fields (let the data surface candidates), *then* form
a constraint-migration thesis (the hypothesis engine) and force it through the gate. Data-first, then
disciplined idea — never idea-first. *(Built: `engine/pillars/research.py` — the gapless arXiv harvest
+ the three measurable channels above; execution.md §1 / §3 recall fix.)*

---

## 1.6 — The altitude: predict the STRUCTURE, score the metric, earn the base rate

The deliverable is a **big, falsifiable, pre-consensus structural forecast** — "over N years, [sector /
sub-sector / macro regime] reorganizes such that [measurable structural claim], because [binding
constraint]; consensus believes X, I predict Y; resolved by [dated structural metric]." It is **not** a
stock pick and **not** a micro-consumable. We drifted *down* into stock-picking and got correctly killed
on "no clean instrument / already priced" — but the instrument was never the point: **physical-primary,
financial-optional** (locked). The forecast scores on the *constraint metric* (capacity, lead-time,
TWh, share, the input's own price series); a financial pair is an optional second expression, never the
proof. The inelastic-input decomposition is the **mechanism/evidence**, not the deliverable.

**The deliverable is a WEB of outcomes, not one extrapolated statement (2026-06-05).** A real forecast
of the future is a *net* — "P here for this, P there for that" — not a single point-claim that is brittle
and low-information. So a structural call is authored as a **scenario tree**: a binary ROOT (does the
binding constraint / regime shift occur at all?) branches into a **mutually-exclusive, exhaustive** set of
outcomes (*which* way it resolves — which layer binds), each carrying a **conditional** probability
(P given the parent occurred) and the set **summing to 1**; outcomes can branch again (how tight, how
fast). Every node stays an individually falsifiable, dated, Brier-scorable card — the web only adds the
linkage. The **marginal** P of any node = the product of conditionals down its path. The machine enforces
that each MECE set sums to 1 (`forecast.add_scenario_branch`) — an incoherent web is unrepresentable, the
structural analogue of the P/CI consistency check — and a conditional child **voids** (is not scored) if
its parent resolves false. This is the honest upgrade to the single-statement form below: same falsifiable
atom, now linked into the net where the future actually lives. *(Built: `forecast.create_root_card` /
`add_scenario_branch` / `scenario_tree`; `scenario_id` + `parent_card_id` on ForecastCard; CLI
`scenario-seed` / `scenario`. First worked web: HVDC grid deployment.)*

**The webs form a NET, not a forest — the belief-net (2026-06-05).** A future is a net not only *within* a
thesis but *across* theses: when two webs share an inelastic input, one's resolution must move the
other's P. So a **belief edge** links a node in web X to a node in web Y, carrying ONE judgment number —
P(target | source resolves TRUE) — and a falsifiable **direction** (`sign`). The complement P(target |
source FALSE) is **derived** so the conditional pair marginalises back to the target's own P — the
**cross-web sum-check** (the structural twin of the within-web MECE check and the P/CI check); an
incoherent lift is refused. Propagation is a **pure read** over the immutable cards — it never writes a P
back (rule 7); resolving a source shows the target's conditional view. Deliberately **NOT** a CPT /
Bayesian-propagation library: that would resurrect the exact disease we diagnosed (hand-typed
`REFERENCE_CLASSES` rates that nothing updates) — the belief-net is judgment-as-conditionals, scored like
everything else. And not every web couples: injectable-delivery is honestly an **island** (no shared
inelastic input) — forcing an edge would be fake.

**The lesson the belief-net taught (2026-06-05, external review):** the coherence guard checks the
*math* (does the conditional marginalise back?), **never the physics** (is there a real channel?). The
first 3 edges were authored coherent; an external skeptic killed 2 on first read. The **−sign "prize"
edge** (ex-China magnets → electrification root, framed as magnet scarcity *re-tightening equipment* and
reversing the off-equipment migration) was a **category error**: large-power transformers / HV switchgear
are grain-oriented electrical steel + copper, **not NdFeB** — magnets bind motors/generators, a different
vertical, so the channel does not exist. The 2nd kill (REE magnets → HVDC root, +) was **mis-signed**:
magnet-starved offshore wind builds *fewer* turbines → *less* HVDC-link demand → the constraint *eases*.
So the standing rule: **a belief edge needs a named, physically-real shared input — pressure-test the
channel as hard as the number.** The genuine cross-vertical inelastic input is **power-semiconductors
(SiC, spanning HVDC converters ↔ inverters ↔ EV traction ↔ data-centre power)** — and we then BUILT its
web (the SiC web, root 0.55) and re-pointed the net through it: **SiC → HVDC converters (+)** is a
physically-real channel (converters are made FROM power-semi modules), unlike the killed magnet edges.
The other surviving edge is trades-labour → HVDC converters (+, trimmed to 0.16 — converter commissioning
is mostly OEM teams, not the generic electrician pool). *(Built: `forecast.add_belief_edge` / `belief_net` /
`card_marginal`; one additive `belief_edges` table; CLI `belief-seed` / `belief-net --resolve`.)*

**Pre-consensus lives in the non-obvious STRUCTURE, not in the obscurity of a tiny input.** A famous
sector can still be mispriced if its *reorganization* isn't yet the consensus base case. So the
priced-in test is multi-channel at the right altitude (`consensus-eye`): narrative saturation + the
**forecaster channel** (have forecasters/specialist press already projected it?) + an optional price
run-up. **But a keyless machine can NEVER certify pre-consensus** — it is blind to paywalled sell-side
notes + specialist B2B press, so it reliably finds PRICED and otherwise returns `UNCONFIRMED` (*not* a
green light). Therefore **pre-consensus is a TAG, not a gate**: make the calibrated structural forecast
regardless, tag how-covered-it-is (held humbly, in-session), and let the **scored record settle**
whether it was truly pre-consensus — exactly the `base-rates` loop (did the pre-consensus-tagged calls
out-pay the priced ones?). Two corollaries the record taught us (2026-06-04): (a) a thesis good enough
to be mechanistically sound in a *hot* domain has usually already been written — the un-narrated edge
sits **one layer beneath the published thesis** (conversion under enrichment) or **off the hot beat**
entirely (dull sectors no sell-side analyst covers); (b) even on a *known* thesis there is edge in being
**better-calibrated on the dated metric** than the vague consensus (predict Y when the crowd says ~Z) —
you don't have to be the only one who sees the bottleneck, only the one who's numerically right.

**The horizon gap cuts both ways — and we now MEASURE it.** The market under-weights distant
constraints, but that distance is also where our own forecast error and the risk premium are largest;
under-pricing is often fair compensation, not free money. Long-dated welded to a hot near-term narrative
is **over**-priced by hype, not under (AXTI/AMSC ran 7–20× while their long-dated thesis was "hidden").
The harvestable inefficiencies are **short-fused (~1–4y), single-mechanism, checkable-in-window**:
*trough discount* and *layer blindness*. This is no longer an opinion — every call is tagged by
`thesis_kind` + `mispricing_kind`, and `base-rates` measures the hit-rate per kind, seeded from the §8
corpus (which already shows `layer_blindness`/`cost_curve_breakout` ~100% paid, `hype_overpriced`/
`horizon_gap` ~0%) and re-weighted as live cards resolve. The outside view, **earned not assumed** —
the one thing no live-data analyst has: not a pick, but a measured base rate of which *kinds* of
where-rent-migrates call actually pay. *(Built: `engine/hypothesis.py` base_rates + the closed
resolution loop; `engine/saturation.py` consensus_forecast; `engine/consensus.py` price_runup.)*

---

## 2. The operational rules (the actual checklist)

Apply these to every forecast. Each operationalizes a method in `execution.md` §3 (a few anchor to a `CONSTITUTION.md` rule instead) — this file is the
*how-to*; §3 is the *must-hold* list.

1. **Outside view first.** Before any inside-view story, name the **reference class** and its **base
   rate**. "How often does this *class* of thing happen?" Anchor the probability there, *then* adjust.
   *(Flyvbjerg, Kahneman)*
2. **Decompose (Fermi-ize).** Break the question into sub-estimates you can actually reason about;
   recombine — and put a **distribution** on each sub-estimate, not a point, so the answer comes out as a
   range (Monte-Carlo; see `execution.md` §3 *Quantitative discipline*). A wrong-but-explicit decomposition beats a confident gestalt guess. *(Tetlock)*
3. **Probabilities, not narratives.** Output a number with a resolution date, not a vibe. Granularity
   matters — 63% ≠ 70%. *(Tetlock, Hubbard)*
4. **Update in small Bayesian steps.** Move on new evidence, but beware over- and under-reaction.
   Most day-to-day movement is **noise, not signal**. *(Silver)*
5. **Kill-criteria + resolution date are mandatory.** A forecast without an explicit "what would
   prove this wrong" and a date is a story, not a bet. *(CONSTITUTION rule 7)*
6. **Adversarial self-refutation.** Spawn independent skeptics; **default to "refuted if uncertain";**
   majority-refute kills the thesis. Look for disconfirming evidence *before* asserting. *(execution §3)*
7. **Premortem.** Assume it's a year later and the call failed — write *why* before committing.
   *(Klein / Kahneman)*
8. **Guard against survivorship & selection bias.** Dead/failed cases leave fewer traces; actively
   seek them. Retrodiction is scored on **precision AND recall** — winners *and* fizzles. *(execution §3, §8)*
9. **Beware narrative seduction.** A clean causal story is *evidence of nothing*; it raises felt
   confidence without raising accuracy. Discount accordingly.
10. **"Right but early" is the dominant failure.** Separate *direction* from *timing*; the rent often
    accrues to a firm that doesn't exist yet at signal time → express theses via the most inelastic
    layer or a basket, not the obvious champion. *(execution §3)*
11. **Score everything (Brier) and stay calibrated.** Track resolved calls against a reliability
    curve and a naive base-rate baseline. Calibration is the near-term proof bar. *(Tetlock; `plan.md` scoreboard)*
12. **Quantify the uncertainty, then spend the budget.** No naked numbers — every quantity carries a
    `unit + error bar + as-of date`; propagate uncertainty through decompositions (Monte-Carlo); and let the
    term that **dominates the output variance** pick your next measurement. Keep the retrodiction corpus
    **out-of-sample** — never tune on it. *(`execution.md` §3 Quantitative discipline; Hubbard)*

---

## 3. The reading lineage (Bucket 1 — where each rule comes from)

Noted so future sessions know these exist and can go deeper or cite them. **Read for method, not
for their conclusions.**

| Source | The one idea to take | Use it for |
|---|---|---|
| **Tetlock — *Superforecasting* / *Expert Political Judgment*** | Foxes beat hedgehogs; experts are poorly calibrated; forecasting is a *trainable skill* | Core stance (§1), decomposition, scoring |
| **Kahneman — *Noise* / *Thinking, Fast and Slow*** | Bias *and* variance both wreck judgment; the outside view | Base rates, premortem, debiasing |
| **Hubbard — *How to Measure Anything*** | Anything can be quantified; calibration training; value of information | Probabilities not vibes; what to measure next |
| **Flyvbjerg — *How Big Things Get Done*** | Reference-class forecasting; the planning fallacy | Outside-view rule (§2.1), "right but early" |
| **Silver — *The Signal and the Noise*** | Bayesian updating in practice; signal vs. noise | Small-step updates; ignoring noise |
| **Good Judgment Project / Metaculus / Polymarket / Kalshi** | Calibrated communities, public track records, scoring norms | Method *and* (as Pillar-7 data) the consensus benchmark |

Buckets 2 & 3 are **not** loaded here. For the record, the framework lineage (Bucket 2, used as
lenses) is Goldratt (Theory of Constraints — our thesis), Carlota Perez (tech-capital cycles),
Hamilton Helmer (*7 Powers* — who captures rent), W. Brian Arthur (increasing returns), Ricardian
rent; and — concepts only, dogma discarded — Christensen and Taleb's *Incerto*.

---

## 4. What we explicitly do NOT do (anti-contamination guardrails)

- ❌ Don't paste expert *predictions/takes* into reasoning context. Anchors to consensus, decays fast,
  and the model already knows them. → Store as **Pillar 7 data** instead (timestamped, GIGO-gated).
- ❌ Don't let a Bucket-2 framework *assert* an outcome. Frameworks **generate hypotheses**; the data
  and the red-team decide.
- ❌ Don't raise confidence because the story is clean (rule §2.9) or because a famous name said it (§1).
- ✅ Do anchor every probability to a base rate, attach kill-criteria + a date, and red-team it.

---

## 5. How this connects to the rest of the repo

- **`execution.md` §3** — the cross-cutting methods this doctrine operationalizes (point-in-time,
  2nd-derivative, consensus delta, adversarial verification, base rates, calibration, survivorship).
- **`CONSTITUTION.md` rule 7** — immutable, falsifiable forecasts (kill-criteria + Brier) is rule §2.5 here.
- **Pillar 7 (Market pricing)** — where Bucket-3 expert opinion lives, as the priced-in benchmark.
- **Components #8 / #9** — Hypothesis engine (Bucket-2 lenses) and Skeptic/red-team (rule §2.6).
