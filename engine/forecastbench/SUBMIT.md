# ForecastBench submission runbook

Org/model on the leaderboard: **Vati / vati-2.0** (FINAL once posted — set in `submit.py`).

Forecaster = crowd-anchor (market) + quant (dataset) + an **LLM gap-fill leg** (`llm_fill.py`,
keyed via `.env`) that forecasts ONLY the residual questions quant/crowd can't (no crowd value /
dead series). Defer-to-best: the LLM never overrides a real signal, so it can't regress the score.
Backtests run `use_llm=False` (LLM leg is live-only). The model name is Vati; the backing LLM is
not surfaced anywhere in the submission.

## One-time onboarding (only Ruben can do this)
Email **forecastbench@forecastingresearch.org** from/naming the **Google account(s)**
that will upload. Draft:

> Subject: ForecastBench participation — Vati
>
> Hi — we'd like to submit to ForecastBench. Please grant upload access for the
> following Google account(s): <your-google-email>. Our organization name is "Vati".
> Could you confirm our GCS bucket and the next forecast due date? Thanks.

They reply with a **GCS bucket folder** + the next due date. Then log into GCP and
upload a test file to confirm write access (their wiki step).

## Every round (biweekly, due dates from 2025-03-02)
At **00:00 UTC on the due date** the question set publishes. You have 24h; upload by
**23:59:59 UTC on the due date** or the set is not scored.

```bash
# 1. build the submission (downloads the round's question set, runs the quant+crowd pipeline)
uv run python -m engine.forecastbench.submit <YYYY-MM-DD>        # the due date
#    -> writes data/forecastbench/<due>.Vati.1.json  and prints coverage
#    REQUIRE: coverage market ≥95% AND dataset ≥95% (it flags ⚠ if not). Below that = excluded.

# 2. upload the file to your bucket, keeping the exact name <due>.Vati.1.json
gsutil cp data/forecastbench/<due>.Vati.1.json gs://<your-bucket>/
```

## Hard rules (do not break)
- File name **must** be `<forecast_due_date>.<organization>.<N>.json` (N = 1..3).
- Root JSON has **exactly** 5 keys: organization, model, model_organization, question_set, forecasts. (No extras — handled.)
- ≤ **3** submissions per round (extras: first 3 alphabetically used).
- Model name is **permanent** once on the board.
- Missing forecasts are imputed 0.5 — the coverage gate guards this.

## Where we stand (honest)
- #1-among-bots, #2-overall behind humans. Dataset half is where bots beat supers.
- fred forecaster now recency-weighted (held-out 0.1995→0.1952, broad 3–8y optimum, no tuned knob).
- Beating humans (needs D<0.115) is **not mechanically reachable**: the fred super-gap is
  macro world-knowledge, not a better estimator (AR(1) tested, worse; hard-coded tilt = overfit, refused).
