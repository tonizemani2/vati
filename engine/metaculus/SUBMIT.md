# Metaculus live-arena bot — operating guide

The judgmental half of the instrument. ForecastBench (`engine/forecastbench/`) wins numeric/series
zero-shot; this wins world-event questions via **research → keyless ensemble → extremize → crowd-anchor**.
The default Cup automation uses OpenRouter `:free` models for **$0**; paid providers require explicit
approval before they are enabled.

## Pipeline (what runs per question)
1. `research.gather` — keyless LLM drafts 4 focused queries → keyless Exa (DDG fallback) → dated digest.
2. `forecast.forecast_question` — best-of-N across the 13-model `ROSTER` → log-odds pool → extremize
   (`d=1.15`) → crowd-anchor (`w=0.30`, only when the community prediction is visible).
3. `run.py` — pull open tournament questions → forecast → **dry-run (default)** or `--submit`.

Fixed priors (`EXTREMIZE_D`, `CROWD_WEIGHT`, `BLIND_SHRINK`) are **never tuned on the scored season** —
re-fit out-of-sample on MiniBench. That is the no-overfit guarantee.

## One-time setup (human, ~10 min — I can't do this headlessly)
1. Create a Metaculus **bot account** (Settings shows a "Bot" account type).
2. **Join the tournaments** while logged into that account:
   - Metaculus Cup Summer 2026 (bot-vs-human proof track) — slug `metaculus-cup-summer-2026`.
   - FutureEval / AI Benchmarking (bot prize tournament) — use the **current season's slug**
     (changes each season; find it on the tournament page URL).
3. Settings → **Create Token** → add to this repo's `.env`:
   ```
   METACULUS_TOKEN=...
   ```
   (Optional, to scale the keyless sweep past a single home IP: `EVOMI_USER/_PASS/_HOST/_PORT`.)

## Run
```bash
# $0 local proof — no token needed, exercises research + ensemble + anchor end-to-end:
python -m engine.metaculus.run --selftest --proxy evomi

# READ-ONLY Cup status / live open-question check:
python data/metaculus/cup_update.py --healthcheck --limit 5

# Generate a private human-review slate from existing submitted forecasts:
python data/metaculus/human_slate.py

# SUBMIT bot/proof-track refresh for real ($0 default; logs every write):
python data/metaculus/cup_update.py --submit
```

Bot/proof-track forecasts are logged to `data/metaculus/forecasts_<tournament>.jsonl`; private human
slates are written under `data/metaculus/private_slates/` and stay gitignored.

## Cadence (newbenchmarksplan.md)
- Re-run on the tournament daily from the non-Desktop runtime; questions resolve over the season.
- Keep a weekly out-of-sample calibration check on MiniBench; adjust `EXTREMIZE_D`/`CROWD_WEIGHT`
  **only** from that held-out signal, never from the live Cup scores.
- Lock the bot ~3 weeks before season close; no late tinkering.

## v1 scope / next
- Binary, numeric/discrete/date, and multiple-choice submission paths exist. Keep human prize-eligible
  work separate from the bot/proof track.
- The proxy is optional for correctness; use it when sweeping a whole tournament so Exa/DeepInfra
  don't rate-limit one IP.
