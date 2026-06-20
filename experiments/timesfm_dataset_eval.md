# TimesFM vs incumbent — dataset-half Brier (leak-free backtest)

_rounds: 29 | sources: fred, dbnomics, yfinance | generated 2026-06-20_

## Head-to-head on the TimesFM-covered subset (same rows)

| source | n | incumbent | timesfm | blend | best | Δ(blend−inc) |
|---|---:|---:|---:|---:|---|---:|
| fred | 5550 | 0.2167 | 0.2805 | 0.2303 | **incumbent** | +0.0135 |
| dbnomics | 4566 | 0.0995 | 0.2134 | 0.1258 | **incumbent** | +0.0263 |
| yfinance | 5351 | 0.2438 | 0.3073 | 0.2570 | **incumbent** | +0.0132 |

## Whole source: incumbent-everywhere vs blend-where-available (adoption number)

| source | n | coverage | incumbent | blend | Δ |
|---|---:|---:|---:|---:|---:|
| fred | 5912 | 94% | 0.2181 | 0.2308 | +0.0127 |
| dbnomics | 4990 | 92% | 0.1061 | 0.1302 | +0.0241 |
| yfinance | 6009 | 89% | 0.2432 | 0.2550 | +0.0118 |
| **pooled** | 16911 | | 0.1940 | 0.2097 | +0.0157 |

_Lower Brier = better. 'blend' = 0.5·incumbent + 0.5·timesfm where TimesFM covered the horizon, else incumbent. Negative Δ = TimesFM helps._

## Verdict — NULL. Not adopted. (2026-06-20)

**Google TimesFM (2.5/200M) does not improve the ForecastBench dataset half. It is worse on every numeric source, alone and in a 50/50 blend, at full power (n=16,911 resolved rows over 29 leak-free rounds).** The submission path was left untouched.

A 4-round smoke run had shown a tiny FRED blend win (−0.0039, n=53); at n=5,550 that flips to **+0.0135 worse**. The blip was small-sample noise — a good reminder of why we score on the full set, not a slice.

**Why it loses (mechanism, not vibes):**
- The incumbent dataset models are not naive baselines — they are purpose-built, leak-free, and per-source calibrated: FRED = recency-weighted empirical directional base rate; dbnomics = day-of-year climatology (already near its floor at Brier 0.099); yfinance = the structural equity-up prior (markets are ~efficient, so a flat prior is hard to beat). TimesFM is a *generic* foundation model and is beaten by each specialist by ~0.06 Brier head-to-head.
- The questions are **directional** ("higher than freeze?"). TimesFM forecasts a level + quantile band; converting that to P(direction) discards the directional calibration the incumbents already have, and TimesFM's quantile spread is not calibrated to ForecastBench's realized volatility at these horizons.
- The blend can't rescue it: a decorrelated member only helps if it is decorrelated **and** competitive. TimesFM is decorrelated but too noisy, so averaging drags the strong incumbent toward a worse number. Optimal blend weight on TimesFM ≈ 0 → reduces to the incumbent.

**Decision:** keep `timesfm_model.py` + `timesfm_eval.py` as the reusable harness and the documented kill; do **not** wire TimesFM into `forecast_dataset_question`. The June 21 submission is unaffected (zero added risk). This is the leak-free, no-cherry-pick outcome — a call killed by evidence.

**Reproduce:** `uv run python -m engine.forecastbench.timesfm_eval` (needs `uv pip install 'timesfm[torch]'`).
