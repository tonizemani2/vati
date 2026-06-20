# Spec: the two edge levers

*Written 2026-06-14. Implements the two "how you win" levers from [[LEADERSHIP_AND_SUPERFORECASTING.md]] against the real `engine/forecastbench/` pipeline. Calibration and aggregation already keep us from losing; these two are what generate edge.*

Both levers ship as new `--pred name=path.jsonl` signals into the existing `ensemble.py` blend, so they slot in without touching the data pipeline. Both are keyless-first and cost-gated. Both are scored leak-free on `grpo_eval.jsonl` (the `leak_ok=True` post-cutoff half).

---

## Lever 1: sequential Bayesian update loop

**File to create:** `engine/forecastbench/sequential.py`
**Output:** `eval_seq.jsonl` (`{id: prob}`), consumed as `ensemble.py --pred seq=eval_seq.jsonl`

### The idea, and why it beats one-shot

`traces.py:_one_question()` and `inference.py:_one_question()` are one-shot: sample N chains, each produces a fresh absolute probability, mean them. Each chain re-anchors from scratch, which is exactly the amateur failure mode (leap to the vivid inside view, over/under-react in unmeasured ways).

The superforecaster habit, and the 2026 agentic method, is **incremental updating in small steps**. We mechanize it by updating in **logit space with a likelihood-ratio per evidence item**, not by re-asking for an absolute probability each round:

```
logit_post = logit(prior) + Σ clamp(delta_i, -CAP, +CAP)
```

where each `delta_i` is the LLM's estimate of the evidence's log-likelihood ratio (how much more probable this evidence is under YES than under NO). This is the single design decision that matters:

- Asking "give me a new probability" each round collapses to one-shot re-anchoring. Asking "how much does this *one* piece of evidence move the odds" forces a genuine Bayesian update and keeps it incremental.
- The `CAP` (start at `logit(0.85) - logit(0.5)` ≈ 1.73, i.e. no single item swings odds more than ~5.7x) mechanizes "small updates, occasional large, never overreact."
- Outside-view-first is baked in: the prior is the base rate, not a guess.

### Flow

1. **Anchor (outside view).** `prior = r.get("base_rate") or r.get("model_prob") or 0.5`. Never start from `crowd_prob` here (we want a signal that can diverge from the market; see Lever 2 rationale). `logit_acc = logit(prior)`.
2. **Fermi-decompose.** One LLM call: break the question into 3-6 sub-estimands / evidence questions. Returns a list of search queries.
3. **Gather.** `engine.adapters.search.search_multi(conn, queries, num_results=6, proxy=proxy)`. Summarize hits per sub-question (one cheap LLM call, or reuse the retrieval-summarize prompt style from `dataset.py`'s context build).
4. **Update loop.** For each summarized evidence block, one LLM call returning a single signed number = `delta_logit` (the likelihood-ratio estimate) plus a one-line rationale. `logit_acc += clamp(delta, -CAP, +CAP)`. Carry the running `sigmoid(logit_acc)` into the next prompt as "current belief" for transparency (display only; the math is in logit space).
5. **Quantify.** `p = sigmoid(logit_acc)`, clamp to `[0.02, 0.98]`.
6. **Calibrate.** Pass through the existing isotonic map (`calib.py:_fit_map` / `_apply`) fit OOF on the train half. Write `{id: p}`.

### Signatures

```python
# engine/forecastbench/sequential.py
def _decompose(conn, r, *, provider, proxy) -> list[str]: ...
def _delta_logit(conn, r, evidence, current_p, *, provider, proxy) -> tuple[float, str]: ...
def forecast_one(conn, r, *, provider="deepinfra_keyless", proxy=None,
                 cap=1.73, max_rounds=6) -> dict: ...
    # returns {"id": r["id"], "prob": p, "trace": [(delta, why), ...], "prior": prior}
def main(): ...  # --in grpo_eval.jsonl --out eval_seq.jsonl --proxy evomi --n-workers K
```

Reuse `llm.py:complete(conn, prompt, provider=..., est_cost_cents=..., system=..., proxy=...)` for every call and `_parse_p`-style extraction from `traces.py` for the delta number. Thread-safe per the `traces.py` pattern (own DB conn per worker).

### Acceptance gate (leak-free)

Run on `grpo_eval.jsonl`. The lever earns its place only if, on the **market + long-horizon subset** (the hard half), it beats:
- the one-shot LLM mean (`eval_llm.jsonl` from `inference.py`), and
- its own anchor prior.

Report Brier and AUC via `ensemble.py:brier/auc`. If it only wins on the easy numeric half, it is not the win we need (see the leadership doc: easy-half Brier is question selection).

---

## Lever 2: decorrelated structural member

**File to create:** `engine/forecastbench/structural.py`
**Output:** `eval_structural.jsonl`, consumed as `ensemble.py --pred structural=eval_structural.jsonl`

### The idea, and the one rule that makes or breaks it

The ensemble is dead when members correlate (~0.6 across frontier models). A second correlated model adds zero. The only thing worth adding is a member that contributes **information beyond the market price**. That gives one hard constraint:

> **The structural member must be blind to `crowd_prob` at inference time.** If you feed it the market price, it correlates with the market and contributes nothing beyond it. This is non-negotiable and is the whole point.

Instead it reasons from **binding-constraint / supply-elasticity facts** the market under-weights: scheduled events, capacity and lead times, physical and demographic locks, regulatory calendars, inventory and concentration (HHI) signals. We already collect much of this.

### Flow

1. **Feature pull (no market price).** From `engine/feeds/` + `data/feeds/` and the structured anchors `curate.py` already attaches (`base_rate`, `model_prob`, domain), assemble a structural feature block for the question. Explicitly exclude `crowd_prob`.
2. **Structural reasoning.** One LLM call with a system prompt aimed at the thesis spine (`Frontier → Capability → Dependency graph → Supply elasticity → Demand → Capital → Pricing`): "Reason from the binding constraint and supply elasticity. What does the structure imply, independent of any market price?" Returns a probability.
3. **Calibrate** through the same isotonic map. Write `{id: p}`.

### Signatures

```python
# engine/forecastbench/structural.py
def _features(conn, r) -> dict: ...        # structural signals, crowd_prob EXCLUDED
def forecast_one(conn, r, *, provider="deepinfra_keyless", proxy=None) -> dict: ...
def main(): ...  # --in grpo_eval.jsonl --out eval_structural.jsonl
```

### Acceptance gate: contribution-beyond-price (the leadership metric)

This is the metric from the leadership doc, and `ensemble.py` is most of the way there already. Add an explicit beyond-price report:

1. Fit the blend on `[crowd_prob]` alone (market-only baseline). Record its held-out log-score.
2. Fit `[crowd_prob, structural]`. Record held-out log-score.
3. Report `delta = LL(crowd+structural) - LL(crowd)` in **nats**. Positive and stable = the member adds information beyond the market. That is the only success criterion that matches "leadership."

Also dump the decorrelation `corr(structural, crowd_prob)`: we want it low. High correlation means we failed rule 1.

---

## Shared follow-ups in `ensemble.py`

Two small additions, both cheap and both from the superforecaster toolbox:

1. **Extremizing test.** After fitting the linear blend, test pushing the pooled logit away from 0 by a factor `a` in `{1.0, 1.1, 1.3, 1.5}`, scored on the held-out half. GJP got double-digit gains from extremizing because pooled members share signal. Add `--extremize` and report the best `a` and its lift. Function: extend `best_linear_blend` or add `extremize(ps, a)`.
2. **Beyond-price as a first-class number.** Make the `LL(crowd+X) - LL(crowd)` delta a standard column in the marginal-value table for every `--pred` signal, not just structural. This becomes our internal leaderboard, the one the field does not report.

---

## Build order

1. `sequential.py` end to end, keyless, on a 50-question slice. Confirm it beats one-shot on the hard half before scaling. This is the higher-value lever.
2. Wire `--extremize` and the beyond-price column into `ensemble.py` (small, unlocks honest measurement of everything else).
3. `structural.py`, gated strictly on positive beyond-price nats. If it cannot clear that bar, it does not ship; a correlated member is worse than nothing because it dilutes the blend.

Cost: all keyless (`deepinfra_keyless` / `openrouter_free`) via the `cost.gate()` path; proxy `evomi` for DeepInfra datacenter blocks per `inference.py`. No paid calls without a nod.

## Honest risks

- **Sequential loop can drift.** Many small updates compound; a biased `delta` estimator walks away from a good prior. The `CAP` and the OOF calibration are the guards; watch the eval Brier vs the prior, not just vs one-shot.
- **Structural member may just fail the beyond-price gate.** That is an acceptable, informative outcome. The doctrine says kill it cleanly and report the null rather than ship a correlated member that flatters the ensemble.
- **Leakage.** Both levers retrieve live web content. On `grpo_eval` the questions are post-cutoff but the *search* can surface post-resolution articles. For the leak-free score, constrain `search` to as-of-date where the adapter allows, or treat retrieval-on results as forward-only (the real use case is live questions anyway, where this is moot).
