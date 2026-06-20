# Overnight Briefing — Data Lake + the Loop-Closing Measurement
_2026-06-12. Everything below is keyless/$0 except ~$0.80 of (terminated) EC2. S3 bucket: `mining-terminal-research-405844305300-us-east-1/predict/`._

## TL;DR (the bigger picture)
We built a ~5 GB, point-in-time, mostly-global data lake **and then actually scored whether it forecasts**. The honest result:
- **Raw frontier-LLM forecasts ≈ base rate (Brier 0.248 vs 0.243). No raw edge** — confirms the standing retro-bench finding, now on a fresh 1,500-question set.
- **But two cheap, MEASURED, leak-free-methodology levers recover real signal:**
  - **Calibration** (Platt/shrink, fit on half → scored on other half): **0.248 → 0.230** (now beats base rate).
  - **Domain gating** (structural domains only): **→ 0.212**. Chaotic domains (commodities/elections/sports) are noise (0.29–0.36) and should be excluded.
- **Ensembling the 5 frontier models does nothing (lift −0.0015)** because they're **correlated 0.58–0.69**. The thesis edge (marginal ensemble value) requires a **decorrelated, structured-data-grounded member** — which the lake is for, but is **not yet wired into forecasts**. That is the real product and the #1 next bet.

## What we have (verified in S3)
| Layer | Scope |
|---|---|
| Prediction markets | 66,374 resolved (Manifold+Polymarket) |
| Equities (US + 16 global markets) | ~10.3M daily rows, 1,653 symbols, hist to 1970 |
| Crypto | ~200 symbols daily+hourly, 2017→ |
| Patents (US) | ~4.1M 2015–26; **(global counts panel building: CN/JP/EP/KR/WO × tech × year)** |
| Research | OpenAlex (resuming to ~5–6M works) + **CrossRef (building, 2022→)** |
| GDELT events | ~10M daily rows, 2015→2026-06, 235 countries × CAMEO |
| GitHub | daily events+repos+language 2015→2026 (ClickHouse, no 7TB download) |
| Wikipedia attention | en (~30M rows) + 10 languages |
| Weather | 231 cities, gap-free daily 2015→ |
| Macro | FRED 308 series + World Bank 262 countries + ECB/Eurostat/IMF |
| Trade | UN Comtrade 60 reporters |
| Filings | SEC (resuming to ~10k cos) + foreign 20-F (36 cos, 17 countries) |
| China export controls | MOFCOM 65 decrees (rare-earth/graphite/semis) |
| **LLM reasoning (derived)** | **14,264 dated structured extractions**: filings/economy/geopolitics/social/research/forecast_bank |

## The measurement (forecast_bank: 1,500 questions × 3–5 frontier models, real outcomes)
Per-model Brier: Kimi-K2 0.244, DeepSeek-V3.2 0.246, GLM-5 0.259, gemma 0.265, **Qwen-397B 0.275 (flagship = worst)**. Base rate 0.242.
- **Decorrelation matrix: pairwise prob corr 0.58–0.69** → models are NOT independent → ensemble lift ≈ 0.
- **Calibration: ECE 0.12**, too timid at low end (says 0.15 → happens 0.37), overconfident at high end (says 0.74 → happens 0.44). Miscalibrated, not leaked (if leaked, Brier would be ~0.05, not 0.25 — leakage looks LOW on this set).
- **By domain (ensemble Brier):** health 0.185 · science 0.186 · finance 0.198 · semis 0.210 · macro 0.216 || commodities 0.364 · elections 0.305 · sports 0.292 · ai_ml 0.281. **Structural >> chaotic — empirically on-thesis.**

## Prioritized next moves (high ROI first)
1. **Ship the calibration layer** (proven: −0.018 Brier, leak-free method). Small, mechanical, repo-ready. _Lowest effort, immediate._
2. **Domain gate** the instrument to structural classes; refuse/abstain on commodities/elections/sports. _Cheap, on-thesis._
3. **THE BIG ONE — wire the lake into a decorrelated quant member.** For each structural question, build point-in-time features from the lake (SEC fundamentals + patent velocity + GitHub/Wikipedia momentum + GDELT + prices + macro), fit a small calibrated model, and **measure its error-correlation vs the LLMs** (target < 0.3) and the **marginal Brier reduction when added to the blend**. This is the only path to real edge; the data is now in place for it. _Higher effort; needs a steer on question/entity scope._
4. (Optional) Reconstruct crowd_prob (crowd.py) for the market half — it's the strongest single market-half feature and the anchor at submission time.

## Honest caveats
- forecast_bank questions are RESOLVED markets; recent models could leak. Signs say leakage is LOW here (at base rate, miscalibrated), but **forward scoring is the only real proof** (standing position).
- Gaps documented, not hidden: FRED daily (FRED server flaky + mostly redundant w/ price layer), EIA (bulk moved; oil/gas via FRED mirrors), GitHub language 2016–2021 (ClickHouse throttle), global patents detail (counts panel built; full per-patent is key-gated).

## Still running (background, no Claude needed; Mac caffeinated + on AC)
OpenAlex resume (8 fields, ~2.5h) · SEC resume (~1.5h) · global patents counts panel · CrossRef research · all with completion watchers.
