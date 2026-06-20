---
description: Refresh the live Metaculus tournament forecasts with Opus-grade research — pull the urgency-ranked worklist, forecast each with web research + crowd anchor, submit, and update the scoreboard.
argument-hint: "[optional: tournament slugs, e.g. 'cup current-events'] [optional: limit=15]"
---

# /metaculus — keep the Opus forecasts winning

This is the in-session ritual that keeps the bot competitive. The DeepSeek cron only keeps forecasts *fresh*; **Opus (you, now) is the signal that beats the human crowd and wins peer score.** Run it when you sit down, when big news breaks, or when questions near their close date. Account: `vaticinus` (user 303577); token in `.env`. Execute in order:

## 1. Pull the worklist
Run the queue builder (defaults to all tournaments, top 25; pass slugs/limit from **$ARGUMENTS** if given):
```
uv run python data/metaculus/refresh_queue.py $ARGUMENTS
```
It writes `/tmp/mtc_queue.json` — open questions ranked by urgency: **coverage gaps first** (never-forecasted = `NEW`, the biggest leak since coverage is a prize multiplier), then soonest-closing, then stalest. Read that JSON; it has each question's full text, resolution criteria, fine print, crowd anchor, days-to-close.

## 2. Forecast each, Opus-grade
For every queued question, in order of urgency:
- **Research with WebSearch/WebFetch** for the current state (these are live 2026 events — base rates alone lose). Prioritize the soonest-closing.
- **Anchor to the crowd.** When `crowd` is present, treat it as a strong prior; only diverge materially with a concrete research-backed reason, stated in the `note`. This is the guardrail against confident-wrong misses that crater peer score. **The Cup API usually withholds the community prediction (`crowd` is null)** — when so, the live CP is visible on the question `url` after its reveal time; try a WebFetch of it, but don't block. With no anchor, default to research + tight calibration (don't grandstand).
- **Calibrate, don't grandstand.** Specific short-window events default low (0.03–0.15). Reserve <0.05 / >0.95 for near-certainties. Brier/log scoring punishes overconfidence hard.
- Per type: binary → one `prob`; multiple_choice → `options` dict over the exact option strings; numeric/discrete/date → `percentiles` dict (at least 0.1/0.25/0.5/0.75/0.9).

## 3. Write the slate
Write a JSON list to `/tmp/mtc_slate.json`, one object per forecast (carry `qid`, `post_id`, `tournament`, `type`, the value, and a one-line `note` with your reasoning + crowd divergence rationale). Schema is in `data/metaculus/submit_slate.py`.

## 4. Dry-run, then submit
```
uv run python data/metaculus/submit_slate.py        # DRY — verify every line OK, CDFs valid
uv run python data/metaculus/submit_slate.py --submit   # LIVE — 8s paced, backs off on 1015
```
Inspect the dry-run output first; fix any FAIL/invalid-CDF before going live.

## 5. Update the scoreboard + report
```
uv run python data/metaculus/pull_scores.py
```
Then tell the user: how many questions you refreshed (and how many were NEW coverage gaps closed), the 3 biggest crowd-divergences you took (with why), any resolved questions + our beat-crowd rate, and what's closing soonest so they know when to run this again.

## Notes
- **Cost:** $0 in LLM API (the forecasting is *you*, in-session); only your normal session tokens. The submit/queue scripts make no LLM calls.
- **Cadence:** soonest-closing questions are where peer score is won. Re-running every few days, and always when material news hits a question, is the whole edge — Metaculus scores your *latest* forecast over the question's open life.
- **Don't re-forecast everything every time** — the queue caps to the urgent ones; that's deliberate. Coverage gaps (`NEW`) and near-close questions first.
- The cron keeps things alive between runs; this ritual is what makes them *good*.
