# Edge Dataset + Finetune Plan

**Goal.** Manufacture the one thing that does not exist online and cannot be bought: a leak-free
`(structural features at T) -> (outcome at T+k)` training set dense in *divergent-and-right* rows,
where the features beat both the crowd prior and the base model's memory. Then finetune an 8B as the
packaged proof, measured on **marginal edge over the crowd** (Beyond Brier), not raw Brier.

This is the direct fix for the negative finetune result: that run failed because the teacher data had
no edge over the free prior (`crowd_prob` empty on every market row). We are building the edge into the
data on purpose, and gating hard that it is real before spending a dollar on GPUs.

**Quality is priority #1.** A few thousand clean, audited, divergent rows beat a million crowd-restating
ones. Volume is the cheap part. Leak-freeness and edge-density are the whole game.

---

## 0. The non-negotiable: leak-freeness

Every feature carries its `source_date`. The build asserts `max(source_date) < T` per row, or the row is
dropped. No live web search, ever, as a feature source. A current-cutoff LLM is never trusted to "recall
the situation as of T" because it already knows the outcome. Two lanes, both leak-free by construction:

- **Lane A (deterministic, build first):** structured features computed from dated corpus rows filtered to
  `date < T`. No LLM in the numbers => no leak possible. This is the safe, high-quality core.
- **Lane B (time-machine retrieval, add later):** an LLM reads ONLY documents timestamped `< T` (GDELT,
  arXiv-by-submission, dated archives) and extracts structured features. The time-wall is enforced in code,
  never by trusting the model.

**Validation gates (all cheap, run before any finetune):**
1. **Leak gate** — per-feature `source_date < T` assertion + a temporal holdout (train on resolutions
   before date D, test after D). Edge that survives the holdout is not leaked.
2. **Edge gate** — score features in-context with the Beyond Brier marginal-edge metric vs the crowd. If
   features add no edge in-context, they will add none finetuned. Kill here for ~$0.
3. **Base-model gate** — base LLM with no features on the same rows. Value lives only in the gap between
   (base + features) and (base alone). That gap, measured, is the moat.

---

## 1. Sources (chosen for: dated, leak-auditable, free/keyless first)

### Labels + priors (scrapable, the easy half)
| Source | Gives | Access | Cost |
|---|---|---|---|
| qbank (already in repo) | 7,094 leak-free resolved Manifold Qs + resolution dates + outcomes | local | $0 |
| Polymarket / Manifold APIs | more resolved binaries + frozen price at T | keyless | $0 |
| Metaculus history | resolved Qs + community prior trajectory | keyless | $0 |
| ForecastBench | question set + crowd anchor | keyless | $0 |

### Feature substrate — Lane A (structured, already in your 6GB layer)
| Source | Signal | Leak-safe because |
|---|---|---|
| OpenAlex (concept graph) | per-concept share-acceleration, citation velocity, diffusion | papers have publication dates; filter `< T` |
| Reliance-on-Science (paper->patent) | commercialization intensity per concept | citations dated; filter `< T` |
| Comtrade | import HHI / supply concentration per HS code | trade periods dated; filter `< T` |
| EDGAR 10-K + FINRA | filing-language deltas, short-volume trend | filings/feeds dated; filter `< T` |
| market.py anchor | the crowd/market prior to beat | frozen at T |

### Feature substrate — Lane B (time-machine, phase 2)
| Source | Signal | Leak-safe because |
|---|---|---|
| GDELT | dated global news/event density on an entity | every event timestamped; retrieve `< T` |
| arXiv (OAI-PMH) | submission velocity on a method (already 1.48M papers) | submission date; filter `< T` |
| Common Crawl historical snapshot | web state as of a past month | snapshot-dated; retrieve `< T` |

**Buy vs build:** buy nothing for v1. Labels are free APIs; the feature substrate is your existing corpus.
The only thing money can't buy is the join + edge filter, which is exactly why it's the moat.

---

## 2. Row structure

```jsonc
{
  "qid": "manifold:abc123",
  "question": "Will <X> happen by <date>?",
  "T": "2024-03-01",                 // cutoff; all features frozen strictly before this
  "crowd_prob_at_T": 0.30,           // the free prior to beat
  "entities": {"concept": "Q...", "ticker": "...", "hs_code": "..."},  // from linking step
  "features": [
    {"name": "concept_share_accel_18mo", "value": 5.1, "unit": "sigma", "source": "openalex", "source_date": "2023-09-01"},
    {"name": "paper_patent_intensity_yoy", "value": 3.0, "unit": "x", "source": "reliance", "source_date": "2023-12-01"},
    {"name": "import_hhi", "value": 0.82, "unit": "hhi", "source": "comtrade", "source_date": "2024-01-01"}
  ],
  "leak_audit": {"max_source_date": "2024-01-01", "passes": true},  // max < T
  "outcome": 1,                      // resolved; known only after T
  "divergence": 0.55,                // |target - crowd_prob_at_T|, used to up-weight edge rows
  "split": "train"                   // temporal: train if resolution < D else test
}
```

The trainer consumes a flattened text prompt (question + serialized features + crowd anchor) -> calibrated
probability target. Same JSONL shape `residual.py` / `training/eval.py` already expect (confirm in build).

---

## 3. Costs (measured against the pricing pulled 2026-06-19)

### Dataset generation — cheap; spend is NOT the bottleneck
LLM is used for two things only: entity-linking (V4 Flash) and Lane-B extraction (V4 Pro). Lane A is
deterministic ($0 LLM). Estimates assume instruction-prefix caching where it applies.

| Step | Model | Per row | 5,000 rows | 10,000 rows |
|---|---|---|---|---|
| Linking (Q -> entities) | V4 Flash | ~1.5k in + 0.3k out | ~$1.5 | ~$3 |
| Lane A features | none | $0 | $0 (+ minor Athena) | $0 |
| Lane B extraction (heavy) | V4 Pro | ~10k in + 1k out | ~$26 | ~$52 |
| Lane B extraction (deep, multi-doc) | V4 Pro | ~30k in + 2k out | ~$75 | ~$150 |

**Dataset v1 (Lane A only): under $10 all-in.** Add Lane B and you're at ~$30-150 depending on depth.
The dataset is the cheap part. Spend the money on RL *only after* the edge gate passes.

### Finetune compute
| Run | Hardware | Time | Cost |
|---|---|---|---|
| 8B SFT (LoRA) proof | 1-2x H100 @ ~$2.5/hr | 4-8 hr | ~$10-40 |
| 8B SFT + GRPO/Brier RL sweep | 4x H100 @ ~$2.5/hr | 12-48 hr | ~$120-500 |
| Eval (leak-free held-out) | API or same box | minutes | ~$0 |
| (post-raise) frontier-size DeepSeek finetune | 8x H200 node, days | per run | ~$2.5-5k/run; $10-50k effort |

**Total nothing -> proven 8B with measured edge: roughly $250-1,000, dominated by the RL run, not data.**
The frontier-size DeepSeek finetune is a post-raise, post-edge-proven lever, and likely NOT the highest-ROI
spend (data and orchestration beat model size). Do not do it before the 8B shows edge.

---

## 4. Build order

1. **Lane A pipeline (this build):** qbank -> link -> attach deterministic dated features -> leak audit ->
   write JSONL. Pure data engineering, ~$0 to run.
2. **Edge gate:** in-context, score (base + features) vs crowd with Beyond Brier marginal edge. Decision point:
   if no edge, stop and rethink features. If edge, proceed.
3. **8B SFT proof:** LoRA finetune on the audited set, eval on temporal holdout. Cheap.
4. **GRPO/Brier RL:** only if SFT + edge gate are green. The expensive step, gated.
5. **Lane B:** add time-machine retrieval features, re-run gates, expand the set.
6. **Raise artifact:** "our data adds measured marginal edge over the crowd; here's the 8B that captures it."

## 5. The raise framing (not "fund a bigger model")
The asset is *measured marginal edge over the crowd on a leak-free board*, attributable to the data layer.
The 8B is the proof object. The raise funds scaling the data + compute, with a bigger model as one downstream
lever among several. Model size is not the edge; the leak-free edge-dense join is.
