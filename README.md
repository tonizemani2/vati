# Vati — an honest, leak-free forecasting instrument

**The problem nobody admits.** You can't trust an AI that says it predicts the future. Test it on the
**past** and it isn't forecasting — it's *remembering* (the outcomes are already in its weights). Test it
on the **genuine future** and you wait years to learn whether it was any good. So the field hand-waves,
and most "AI predicts X" claims are quietly contaminated.

**What Vati is.** An instrument built *around* that problem instead of past it:

1. **Leak-free testing** — forecast the past with a model whose training cutoff *precedes* the outcome,
   so it physically cannot have memorized the answer. An honest test you can run in minutes, not years.
2. **A sealed record** — every live forward forecast is hash-committed and timestamped, so when a call
   comes true nobody can claim it was written after the fact. The plaintext is revealed at resolution.
3. **A scored method** — calibrated, falsifiable, Brier-scored forecasts of *where a binding constraint
   migrates next*, not vibes.

It is **early, and honest about it.** The moat is the record + time, not the code.

## An early leak-free signal (2026-06-06) — indicative, not proof
A clean ~2021-cutoff model (GPT-3.5-turbo-0613), asked to forecast 2024 outcomes it could not have
seen, scored **Brier 0.110 vs a 0.245 base rate (6/7)** on 7 leakage-gated questions. **N = 7 — this
demonstrates the test *apparatus* works, not a validated edge.** Scaling N and using externally-authored
questions is the next step. It's shown here *with* its limitation on purpose: the honesty is the point.

## The sealed record
`experiments/forward_calls_seal.sha256` is a SHA-256 commitment to every live, unresolved structural
forecast. When a manifest is revealed, anyone can verify it:
```
shasum -a 256 forward_calls_seal.jsonl   # must equal the committed hash
```
The git commit timestamp makes the record un-backdateable.

## How it's built
`engine/` — Python + SQLite, free/keyless-first. `plan.md` (the goal), `doctrine.md` (the forecasting
method), `CONSTITUTION.md` (the operating principles), `proof.md` (the evidence, stated with its
maturity).

---
*Status: early-stage, solo, in progress.*
