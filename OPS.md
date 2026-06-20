# OPS.md — the one-and-done forecasting setup (read this when confused)

**Everything runs by itself via cron on this Mac. You run NOTHING daily.** FutureEval uses the approved
Bedrock/Opus path; Metaculus Cup refresh defaults to OpenRouter `:free` unless a paid provider is
explicitly enabled after approval.

## What runs automatically (cron, already installed)
| Job | When | What it does |
|---|---|---|
| **FutureEval** (Metaculus bot tournament) | 06:30 / 14:30 / 22:30 daily | Opus deep research → auto-submits every new question. No-ops between batches. |
| **ForecastBench** | Sundays 09:00 / 15:00 | On a due-date Sunday: builds the round (quant+crowd+Opus) → uploads to GCS. No-ops on non-due Sundays. |
| Metaculus Cup bot/proof refresh + score pull | daily 08:30 / 09:30 | keeps the Cup proof-track forecasts fresh + pulls scores from the non-Desktop runtime |

Schedules are biweekly-aware: ForecastBench question sets only exist on due dates (every 2nd Sunday
from 2025-03-02 → next is **2026-06-21**, then Jul 5, Jul 19, …), so non-due Sundays just exit clean.

## The ONLY things you ever touch (one-time, ~5 min, then never again)
1. **ForecastBench onboarding (only you can):** email `forecastbench@forecastingresearch.org` from the
   Google account that will upload → they reply with a **GCS bucket name**.
2. On this Mac: `gcloud auth login` with that Google account, then add `FORECASTBENCH_BUCKET=<name>`
   to `.env`. After this, ForecastBench uploads itself every round. (Until then it BUILDS the file
   but won't upload — you'd `gsutil cp data/forecastbench/<due>.Vati.1.json gs://<bucket>/` by hand.)

## Reliability caveat
Cron runs on THIS Mac, so it must be **awake + plugged in** at the scheduled times (keep it from
sleeping, or `caffeinate -s`). If the Mac is asleep, that run is missed. For true 24/7 we'd move the
crons to an always-on box / cloud scheduler — say the word if you want that.

## Cost (plain)
- **Out of pocket: ~$0** — all Opus runs on your AWS Bedrock credits; ForecastBench upload is free.
- Credit burn, if you want the number: FutureEval ~$5–8/day, ForecastBench a few $/round. Over the
  whole summer to Sept 6 that's roughly **$500–750 of credits total** — that, and only that, is where
  the "$450–700" figure came from. It is credit consumption, NOT a bill.

## Check status anytime (optional, not required)
- Metaculus Cup status: `uv run python data/metaculus/cup_status.py`
- FutureEval/Metaculus scoreboard: `uv run python data/metaculus/pull_scores.py`
- Cron logs: `/tmp/futureeval_cron.log`, `/tmp/forecastbench_cron.log`, `/tmp/cup_cron.log`, `/tmp/mtc_scores.log`
- To force a manual FutureEval run now: `data/metaculus/run_futureeval_update.sh`
