# Vati — an honest, leak-free forecasting instrument

**The problem nobody admits.** You can't trust an AI that says it predicts the future. Test it on the
**past** and it isn't forecasting — it's *remembering* (the outcomes are already in its weights). Test it
on the **genuine future** and you wait years to learn whether it was any good. So the field hand-waves,
and most "AI predicts X" claims are quietly contaminated.

**What Vati is.** An instrument built *around* that problem instead of past it:

1. **Leak-free testing** — forecast the past with a model whose training cutoff *precedes* the outcome,
   so it physically cannot have memorized the answer. And never trust a model's *claimed* cutoff —
   *measure* it with a non-leading recall probe (we caught a model labelled "2021" that actually knew
   2023 events).
2. **A sealed record** — every live forward forecast is hash-committed and timestamped, so when a call
   comes true nobody can claim it was written after the fact. The plaintext is revealed at resolution.
3. **A scored method** — calibrated, falsifiable, Brier-scored forecasts of *where a binding constraint
   migrates next*. The edge claim rests on the *method + data*, not on a raw model.

It is **early, and ruthlessly honest about what is and isn't proven.** The moat is the record + time.

## What's proven vs not (stated plainly)
- **A fair, leak-free test of a *raw* frozen model shows NO edge.** On 49 externally-authored,
  already-resolved ForecastBench questions (leak-gated), a clean ~2023-cutoff model scored **Brier 0.244
  vs a 0.204 base rate — it does not beat base rate.** That's the point, not an embarrassment: a raw LLM
  is a *consensus machine*, not an oracle. Any forecasting edge must come from the **method + data**, not
  the model alone.
- **The method's edge is not yet proven** — by construction it can only be validated **forward**, via
  the sealed record, or via point-in-time backtests. That honesty is the product.
- We deliberately built the fair test *that refuted our own flattering early number* (a 7-question,
  self-authored holdout that looked great and didn't generalize). Catching your own false positives is
  the whole discipline.

## The sealed record
`experiments/forward_calls_seal.sha256` is a SHA-256 commitment to every live, unresolved structural
forecast. When a manifest is revealed, anyone can verify it:
```
shasum -a 256 forward_calls_seal.jsonl   # must equal the committed hash
```
The git commit timestamp makes the record un-backdateable.

## How it's built
`engine/` — Python + SQLite, free/keyless-first. `experiments/holdout_questions.jsonl` — the external
ForecastBench test set (reproducible). `plan.md`, `doctrine.md`, `CONSTITUTION.md`, `proof.md` — the
goal, the method, the principles, and the evidence stated with its maturity.

---
*Status: early-stage, solo, in progress. The honesty is not a disclaimer — it's the moat.*
