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

It is **early, and ruthlessly honest about what is and isn't proven.** The sealed record is *proof of
edge, not a moat* — a real moat is a better method, exclusive data, or owning the benchmark.

## What's proven vs not (stated plainly)
- **There is NO leak-free retro edge to show — and we proved that on ourselves.** Prediction-market
  questions (sports/crypto/elections — the chaotic class): three capable 2023-cutoff models land on the
  base rate, no edge (expected; that regime is unpredictable for everyone). A *self-authored* N=7
  structural set looked great (Brier 0.069–0.149) — but it **did not replicate** on a **mechanically-
  built, pre-registered N=45 set** drawn from public dated series (FRED PPIs, trade, demographics):
  **Brier 0.254 / 0.230 vs ~0.23 base — no edge.** The N=7 win was selection bias; the apparatus caught
  it. A weak old brain running the method *prompt* (no data pipeline) floats at base rate.
- **The real product can't be retro-tested at all.** Its edge is a frontier brain (Claude) + the data
  pipeline — and a frontier model already holds post-cutoff outcomes in its weights (parametric
  leakage), so its forecasting skill is provable **forward only**. The retro path is capped by physics,
  not effort. That honesty *is* the product: we are the team that refuses to show a number it can't stand behind.
- We deliberately **deleted the prediction-market benchmark** once we showed it's the wrong question
  class. Catching your own false positives — and cutting what doesn't measure your edge — is the discipline.

## The sealed record
`experiments/forward_calls_seal.sha256` is a SHA-256 commitment to every live, unresolved structural
forecast. When a manifest is revealed, anyone can verify it:
```
shasum -a 256 forward_calls_seal.jsonl   # must equal the committed hash
```
The git commit timestamp makes the record un-backdateable.

## How it's built
`engine/` — Python + SQLite, free/keyless-first. The retro bench (`engine/holdout.py`) runs the
framework on Class-1 structural questions, leak-gated by a non-leading recall probe. `plan.md`,
`doctrine.md`, `CONSTITUTION.md`, `proof.md` — the goal, the method, the principles, and the evidence
stated with its maturity.

---
*Status: in active development. Vati is built to top the field, and the scored record is how we prove it.*
