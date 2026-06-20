# Vaticinus Mega Plan — Proof-Stacking Through People

> Durable repo copy. Identity in this repo is **Toni Zemani, always** (any "Ruben Stout / ESCP" reference is a bug to fix).

## Context

Vaticinus is a finance-facing forecasting-intelligence company (the Oracle) with the ambition to become a bottleneck-builder (the Builder). The product is being right about where the binding constraint moves before it is priced; the scored record is how that is proven. The binding constraint on *capturing* value from being right is **access/trust**, not forecasting or execution. Outreach is the tool that attacks access.

The pieces are built but were unaligned. Real state (audited 2026-06-19):

- **Proof assets:** ForecastBench leg ready to upload **June 21** (onboarding done, no blocker). Public sealed call board live at `chat.vaticinus.com` (53 calls) but **not auto-scored**. Metaculus Cup + FutureEval bot **submitting in-session but not cronned**. The **3-arm ablation does not exist** yet (PEOPLE_MAP calls it "the highest-leverage single artifact"). `/forecasts` PDFs + Beyond-Brier preprint shipped.
- **People assets (mature, not "ramming"):** `PEOPLE_MAP.md` (four rings, evidence engine, ~50 named Ring-1 advisors incl. Tier S), `closing_roadmap.md`, `contacts.md`, `outreach_messages.md`, a scored universe of **3,498 people** (`research/targets/`), and `pope-capture` (named-target money plans, already produced a real board).
- **Gaps closed by this plan:** (1) two unreconciled frameworks; (2) Rings 2-4 have no named depth; (3) the Builder/value-capture outreach motion existed only in a prompt; (4) proof-gating not per-person; (5) stale calendar; (6) identity inconsistency.

**Hard constraint:** board control is sacred — revenue > SAFE > priced VC; no co-founder board seat; lieutenant vests.

---

## Part 1 — The unified spine (one model, not two)

Every target maps to a **Capture-Ladder rung**, a **Ring**, a **proof-key**, a **control impact**, and a **when**.

| Ring / target | Ladder rung | What you want | Proof-key (minimal) | Control | When |
|---|---|---|---|---|---|
| **R5 Bottleneck operator / data-holder** | 1-2 be useful / broker / **barter** | proprietary data for the moat + position | a specific correct insight about *their* world | neutral/+ | **now** (proof-agnostic) |
| **R1 Advisor / credential-lender** | 3 advise (signal) | 3-5 named advisors + intros | FB rank + the ablation number | + (advisory equity, no seat) | after FB + ablation |
| **R4 Amplifier** | 1 be seen | broadcast the scored record | the live auto-scored board + FB | neutral | right after FB |
| **R2 Client (lighthouse)** | 3 sell intel | 1-3 paying pilots | a forecast that would have made/saved *them* money | ++ (revenue = control) | after FB, warm via R1 |
| **R3 Angel** | 4 take a position | small SAFE (only if barter insufficient) | record + ablation + ≥1 pilot | safe (SAFE, no seat) | last |
| **Lieutenant** | — | thinking partner + multiplier | the vision + the working system | guard: vesting, no seat | after proof |

**The loop:** proof → unlocks a person → that person is the proof that unlocks a bigger person. People are credentials, not just labor.

---

## Part 2 — How proof-stacking works (the primer)

1. **Every door has a lock, and the lock is a specific proof** — the minimal, domain-specific proof *this exact person* needs to say yes.
2. **Stack external, ungameable proofs at the base** (ForecastBench rank, a public Brier number, a Metaculus standing) — strong because someone who is not you verified them.
3. **Give before you ask.** The first contact carries value *to them*, never a request. Giving is itself a proof and starts the relationship in credit.
4. **Match the key to the rung.** Do not over-build proof for doors you are not opening.
5. **Warm beats cold 10-30x.** Convert the warmest, highest-leverage person first, then use them as the bridge.
6. **People compound.** Each conversion is a credential and a set of warm paths; sequence rings so each unlocks the next.
7. **Access is the binding constraint; communication manufactures it.** Being right is worthless without access. (Musk's "find the limiting factor," pointed at yourself.)

---

## Part 3 — Track A: the proof stack (build)

1. **Build the 3-arm ablation (FIRST).** Arms: raw Opus single-shot / Opus + decorrelated council / full system. Brier on one held-out 2026-resolved set. Reuse `data/metaculus/config_bakeoff.py` panel loader + Brier. Kills "are you just a prompt layer?" Unlocks R1 + R2.
2. **June 21 — fire ForecastBench** via `engine/forecastbench/SUBMIT.md`.
3. **Wire the board auto-scoring loop** — resolver fills `outcome` on `resolution_date`, rolling Brier surfaced publicly. Seed short-fuse calls.
4. **Cron Metaculus Cup + FutureEval** so coverage is continuous; capture the public peer-score/rank.

---

## Part 4 — Track B: the people plan (the emphasis)

### 4a. Named depth
- **R1: deep already** (Tier S: Lifland, Karger, Halawi, Sempere, Wildeford, Liptay, Hickman, wasabipesto). Warm-path-only.
- **R2/R3/R4: thin — run a named sourcing pass** (pope-capture + `research/targets/` scripts + verified web). Lieutenant pool from Manifold/Metaculus/ACX/Numerai + adjacent-tier Kaggle/Codeforces/olympiad (not the taken apex).

### 4b. Per-group messaging (give-before-ask; humanizer rules, no em dashes, Toni Zemani)
- **R5 operator (pure give):** "I track [constraint]. I'm seeing [specific correct insight]. Happy to share what the data shows." → info, barter, position.
- **R1 advisor (peer):** "I built an instrument that ranks #1-among-bots on ForecastBench; here's the live scored board + a 3-arm ablation beating raw Opus. I admire [their work]. Would value your read, and if it resonates, your advice."
- **R4 amplifier:** "A leak-free, auto-scored forecasting board + the ablation behind it. Thought it'd interest you given [their thing]." Artifact does the work.
- **R2 client (the person who loses sleep):** "You're exposed to [X constraint]. Here's what our instrument said 6 months ago and how it resolved, plus our current read on your book. Worth 20 minutes?"
- **R3 angel:** "Record + ablation + first pilot attached. Building the data moat for constraint-forecasting, keeping the raise tight. Thought you'd want to see it given [their portfolio]."
- **Lieutenant:** "I'm building an instrument that predicts where value migrates before it's priced. Here's the proof. I think you'd love this problem. Want to think about it together?"

### 4c. Sequencing
- **Phase 1 (now, before sending):** build ablation; identity sweep to Toni Zemani; per-person proof-key column; one CRM-of-record + reply loop; R2-R4 named sourcing; begin R5 give-only outreach.
- **Phase 2 (FB + ablation live):** hand-send P0 R1 from the Toni Zemani identity; post proof publicly → R4. Goal: 1 anchor advisor.
- **Phase 3 (first advisor / proof in hand):** warm R2 lighthouse clients; barter-for-data with R5; small SAFE only if barter cannot fund the moat.
- **Phase 4:** recruit the first lieutenant (vesting, no seat); Builder motion on 1-2 highest-conviction calls.

### 4d. Decision rule
Hand-craft where you need few, spray where you need many. **R1 = warm-path-only, ~50 names, target 3-5 closes.** Volume machine only for **R2 clients** + **R4**.

---

## Part 5 — The Builder motion (rungs 2-5)
- **Ring 5 operators** are the entry: be useful, then **broker** or **barter**.
- **Venture-scout structure:** find the ASML-shaped bottleneck-openers, a fund funds them, you take carry. Builder with someone else's capital, control preserved.
- **`pope-capture` is the engine:** run on the 1-2 highest-conviction calls → named targets, ask, value-mechanism, first move.

---

## Part 6 — Hygiene & source of truth
- **Identity:** Toni Zemani everywhere; remove "Ruben Stout / ESCP."
- **Proof-key column:** extend `build_outreach_assets.py` so each target carries the artifact that converts them.
- **CRM-of-record:** the scored universe CSV is the single source of truth; replies update tier; a closed advisor triggers R2/R3 round-2 sourcing.

---

## Verification
- Ablation: committed results, three Brier numbers, full system < council < raw Opus by a clear margin (or it's a finding).
- ForecastBench: `gsutil cp` exit 0 to `team26/` with ≥95%/≥95% coverage.
- Board: `outcome` populated on a resolved call + a public Brier number on `chat.vaticinus.com`.
- People: ≥1 signed anchor advisor; ≥1 R5 reply yielding data/intro; identity sweep returns zero old-name/`escp` hits across `research/` and the engine UA strings (done 2026-06-19 for outreach docs, generator, CSV, and 68 feed UA emails → `research@vaticinus.com`).

## Critical files
- Proof: `data/metaculus/config_bakeoff.py`, `engine/forecastbench/SUBMIT.md` + `{submit,opus_forecaster,opus_blend}.py`, `chat/src/app/api/record/route.ts` + `chat/db/schema.sql` + `experiments/forward_calls_seal.jsonl`, `data/metaculus/{cup_update,futureeval_update}.py`.
- People: `research/PEOPLE_MAP.md`, `closing_roadmap.md`, `contacts.md`, `outreach_messages.md`, `research/targets/` + `build_outreach_assets.py`, `.claude/workflows/pope-capture.js`, `engine/ground.py` + `engine.cli data-query`.
