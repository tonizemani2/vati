---
description: Find needle-in-haystack pre-consensus theses — specific binding constraints, not themes — each with a transparent, gated WHY. You reason + surface; the machine verifies; Ruben decides.
---

# /needle — surface the structural forecast, show the why, let Ruben decide

**The deliverable is a big, falsifiable, pre-consensus STRUCTURAL forecast** — "over N years, [sector / sub-sector / macro regime] reorganizes such that [measurable structural claim], because [binding constraint]; consensus believes X, I predict Y; resolved by [dated structural metric]." NOT a stock pick, NOT a micro-consumable. The inelastic-input decomposition is the **mechanism/evidence**, never the product (we drifted into stock-picking and got killed on "no instrument / already priced" — the instrument was never the point; **physical-primary, financial-optional** is the locked rule). Pre-consensus lives in the **non-obvious STRUCTURE**, not the obscurity of a tiny input. **You reason and surface (gated); the cold machine verifies; Ruben decides.** Read `doctrine.md` first. $0/keyless; log before any spend.

**Horizon gap cuts BOTH ways (the measured lesson).** Short-fused (~1–4y), single-mechanism, checkable-in-window structural calls are the *harvestable* kind. Long-dated welded to a hot near-term narrative is **hype-over-priced**, not under-priced. Run `base-rates` — our own §8 record already measures it: `layer_blindness`/`cost_curve_breakout` ~100% paid; `hype_overpriced`/`horizon_gap` ~0%. Tag every call with `--thesis-kind` + `--mispricing-kind` + `--horizon-years` so it feeds that loop.

## The trap this exists to kill
The scan ranks EARLY by raw σ and treats "no lagging channel linked" as "crowd hasn't noticed" → it floats the **broadest** curve (e.g. `supercomputer flops` — one OWID series, 0 lag) as the headline. That is the obvious end-product B, not the needle. **A theme is never an acceptable answer.**

## Procedure (each step is an existing gate)
1. **Scan.** `uv run python -m engine.cli discover` → the EARLY list.
2. **Drop vacuous-early.** Discard any candidate with **0 lagging series linked** — its "early" is absence of data, not measured flatness. Keep leads whose lag channel was checked and is flat.
3. **Measure saturation.** `… saturation-topic "<name>"` on each survivor. **Hard-demote** any `priced/known` — in the trade press ⇒ not pre-consensus. Keep only measured-low.
4. **Decompose theme → constraint (in-session — the generative act).** For each survivor, walk *down* the dependency graph through a Bucket-2 lens (toc / ricardian / helmer / inversion / analogy). Name the **specific** inelastic input: a named consumable / material / isotope / sub-component, with **named suppliers** and a multi-year expansion lead time. ("AI" → not "compute" but e.g. "ABF substrate, Ajinomoto >95%"). 2–4 candidates per theme.
5. **Run the consensus eye at structural altitude.** `consensus-eye "<the structural claim>"` — multi-channel: narrative saturation + the **consensus-forecast channel** (have IEA/IMF/banks already projected it? → priced) + an optional price run-up if a clean ticker exists. Edge lives ONLY where all channels are quiet. A claim with no instrument is still valid — say so; never kill it for that.
6. **Write survivors as gated Hypotheses.** `… hypothesis-add` with every disciplinary field **plus `--thesis-kind` / `--mispricing-kind` / `--horizon-years`** (so it feeds `base-rates`). The status is mechanical; the judgment lives in the fields. Frame `claim` at sector/macro altitude with a dated structural metric — the inelastic layer goes in `--inelastic` as the mechanism.

## Output contract — what you hand back
A ranked shortlist (best first). For EACH structural forecast, ≤8 lines:
- **Structural call:** the sector/macro reorganization — "consensus believes X; I predict Y" + the dated structural metric it resolves on.
- **Mechanism (the needle):** the binding inelastic input + named suppliers — *why* the structure must reorganize (1–2 lines).
- **Outside view:** reference class + the **measured** base rate for its kind (`base-rates`).
- **Disconfirmer (sought first):** the strongest case against.
- **Falsifier + horizon:** the dated, numeric kill-criterion; flag if `horizon_years` makes it harvestable vs hype-over-priced.
- **Consensus eye:** narrative · forecaster-channel · price (if any) → PRE-CONSENSUS / PARTLY / PRICED.
- **Kind tags:** `thesis_kind` · `mispricing_kind` · gated status (survived/parked).

## Hard rules
- **Never** return a theme as the answer, and **never** cite σ as the reason — σ is magnitude; the *why* is the disciplinary trace.
- **Stop at the shortlist. Do NOT promote** to a ForecastCard — promotion is Ruben's call (rule 7, ask-don't-assume).
- If nothing survives, say so plainly. An empty needle list is the honest default, not a failure.
