# ForecastBench submission runbook

Org/model on the leaderboard: **Vaticinus / vati-2.0** (FINAL once posted — set in `submit.py`).

Forecaster = crowd-anchor (market) + quant (dataset) + an **LLM gap-fill leg** (`llm_fill.py`,
keyed via `.env`) that forecasts ONLY the residual questions quant/crowd can't (no crowd value /
dead series). Defer-to-best: the LLM never overrides a real signal, so it can't regress the score.
Backtests run `use_llm=False` (LLM leg is live-only). The model name is Vaticinus; the backing LLM is
not surfaced anywhere in the submission.

## One-time onboarding (only Ruben can do this)
Email **forecastbench@forecastingresearch.org** from/naming the **Google account(s)**
that will upload. Draft:

> Subject: ForecastBench participation — Vaticinus
>
> Hi — we'd like to submit to ForecastBench. Please grant upload access for the
> following Google account: tonizemani921@gmail.com. Our organization name is "Vaticinus".
> Could you confirm our GCS bucket and the next forecast due date? Thanks.

**Status (2026-06-16): ✅ GRANTED + WRITE-VERIFIED.** Onboarding complete (Toni emailed Jun 8,
Houtan replied). Upload account = **tonizemani921@gmail.com**. Assigned folder:
**`gs://forecastbench-submissions/2026-06-21/team26/`**.
Write access confirmed 2026-06-16 by uploading a test file (`gsutil cp` exit 0). NOTE: the
account has WRITE-ONLY access — `gsutil ls` on the bucket returns 403 by design (teams can't
browse each other's folders). A failed `ls` does NOT mean you're blocked; only a failed `cp` does.
Deadline this round: **Sunday 2026-06-21, 23:59:59 UTC** (set publishes 00:00 UTC same day).

They reply with a **GCS bucket folder** + the next due date. Then log into GCP and
upload a test file to confirm write access (their wiki step).

## Every round (biweekly, due dates from 2025-03-02)
At **00:00 UTC on the due date** the question set publishes. You have 24h; upload by
**23:59:59 UTC on the due date** or the set is not scored.

```bash
# 1. build the submission (downloads the round's question set, runs the quant+crowd pipeline)
uv run python -m engine.forecastbench.submit <YYYY-MM-DD>        # the due date
#    -> writes data/forecastbench/<due>.Vaticinus.1.json  and prints coverage
#    REQUIRE: coverage market ≥95% AND dataset ≥95% (it flags ⚠ if not). Below that = excluded.

# 2. upload the file to your bucket, keeping the exact name <due>.Vaticinus.1.json
gsutil cp data/forecastbench/<due>.Vaticinus.1.json gs://forecastbench-submissions/2026-06-21/team26/
```

## Opus research leg (Bedrock, tiered — added 2026-06-16)
The mechanical pipeline already hits ~100% coverage and #1-among-bots. The Opus leg adds
decorrelated research signal on the JUDGMENTAL subset only (metaculus+infer, ~103/round) —
dataset + liquid markets (manifold/polymarket) are left to the quant/crowd (Opus regresses
them). Runs on our AWS Bedrock account (headless, retry-safe; ~$5-16/round, near-zero on
credits). Tiered: Sonnet 4.6 forecasts all judgmental q's research-augmented; Opus 4.8
council re-forecasts only the movers (edge>=weak). Blend keeps the crowd >=60% logit weight,
so a bad Opus call cannot tank a well-priced market. Code: `opus_forecaster.py` (runner) +
`opus_blend.py` (math/merge). LEAK RULE: never tune the blend weights on a resolved set
(Opus cutoff postdates 2025) — they are fixed by principle; forward rounds only.

```bash
# On the DUE DATE only (set publishes 00:00 UTC; not fetchable before):
uv run python -m engine.forecastbench.submit <YYYY-MM-DD>            # fetch the set (writes q_<date>.json)
uv run python -m engine.forecastbench.opus_forecaster data/forecastbench/q_<date>.json \
    /tmp/opus_<date>.json --council 3 --proxy evomi --workers 6      # Bedrock research leg
uv run python -m engine.forecastbench.opus_blend merge \
    data/forecastbench/q_<date>.json /tmp/opus_<date>.json           # -> data/forecastbench/<date>.Vaticinus.1.json
#   REQUIRE coverage market >=95% AND dataset >=95% (printed). Then gsutil cp to the bucket.
```

## Hard rules (do not break)
- File name **must** be `<forecast_due_date>.<organization>.<N>.json` (N = 1..3).
- Root JSON has **exactly** 5 keys: organization, model, model_organization, question_set, forecasts. (No extras — handled.)
- ≤ **3** submissions per round (extras: first 3 alphabetically used).
- Model name is **permanent** once on the board.
- Missing forecasts are imputed 0.5 — the coverage gate guards this.

## Official spec — frozen from the wiki (2026-06-16)
Source: <https://github.com/forecastingresearch/forecastbench/wiki/How-to-submit-to-ForecastBench>.
Verified our pipeline matches every point below.

**Top-level keys** (these 5, exactly):
`organization`, `model` (differentiates prompt/variant), `model_organization`
(creator org; = organization if anonymous), `question_set` (copy the value from the
question-set file verbatim), `forecasts` (array).

**Each forecast object:**
- `id` — unique identifier from the question
- `source` — the market/dataset source
- `forecast` — float in **[0,1]**
- `resolution_date` — `YYYY-MM-DD` for **dataset** questions; **`null`** for **market** questions
- `reasoning` — optional string or `null`

**Coverage shape per round:** ~250 market + ~250 dataset questions.
- **Market** (250): exactly **1** forecast/question, `resolution_date: null`.
- **Dataset** (250): one forecast at **each** horizon — `7, 30, 90, 180, 365, 1095, 1825, 3650`
  days from the due date (≤8; fewer only if the series updates less than weekly).
- Gate: **≥95% of market AND ≥95% of dataset** must be covered or the submission is excluded;
  anything missing is imputed 0.5.

**Timing:** set releases 00:00 UTC on the due date (may slip ≤5 min); deadline 23:59:59 UTC
same day. Dry-run the code against a previously-released set before the round.

**Anonymity:** can request an "Anonymous N" org name; **cannot** be de-anonymized later.

## Where we stand (honest)
- #1-among-bots, #2-overall behind humans. Dataset half is where bots beat supers.
- fred forecaster now recency-weighted (held-out 0.1995→0.1952, broad 3–8y optimum, no tuned knob).
- Beating humans (needs D<0.115) is **not mechanically reachable**: the fred super-gap is
  macro world-knowledge, not a better estimator (AR(1) tested, worse; hard-coded tilt = overfit, refused).
