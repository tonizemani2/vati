---
description: The Pope System — generate disruptive pre-consensus structural calls on demand in any area, harden them through an adversarial gate, and render a PDF.
argument-hint: "[area or topic, e.g. 'biotech' or 'any' or 'water']  [optional: top_k=8]"
---

# /pope — predict where the future is heading

Run the Pope System for the requested area: **$ARGUMENTS** (if empty, treat as `any` — wide open across all industries).

This is the gate-exempt-at-generation, strict-at-graduation pipeline. Generate wide and disruptive, then let the adversarial gate keep it honest. Execute these steps in order:

## 1. Generate + harden (multi-agent)
Call the **Workflow** tool with the saved `pope` workflow (standard/cheap tier, Sonnet):
- `name: "pope"`
- `args`: `{ "domain": "<the area from $ARGUMENTS, or 'any area, wide open across all industries'>", "model": "sonnet", "channels": 5, "per_channel": 2, "top_k": <top_k arg or 6>, "date": "<today's date YYYY-MM-DD>", "horizon": "long" }`

**Horizon (`horizon`):** `"long"` (default) mines decade-scale structural locks that resolve 2030-2040 (where the constraint *moves*). `"short"` mines specific dated near-term catalysts and clearing imbalances that resolve in 3-18 months (a forced repricing *soon*) — a different forecasting object with its own channel set and gate, and the only mode whose calls can be Brier-scored within the year. Pass `"horizon": "short"` to run the catalyst engine.

The workflow fans out the channel miners (each first reads `FUTURE_MAP.md` so it builds on our prior calls), then a grounded adversarial gate (one web search per candidate for the live price/anchor) refutes each and scores the dual probabilities (vision + strict clause), then synthesis and implications return a complete renderable spec. The implications phase must translate each survivor into a buyer-facing decision object: who is exposed, action now, decision changed, ROI/risk logic, winners/losers, what reprices, and earliest trigger. Wait for it to finish; the returned object is the spec.

**Tiers (pick by what the user asks / budget):**
- `pope` — cheap, all Sonnet, ~15-20 agents. The everyday default.
- `pope-pro` — in-between. Opus does ideation + synthesis (~7 Opus agents), Sonnet does the gate (~12). Best quality-per-Opus-quota; the recommended serious tier. ~5-6x less Opus than mega.
- `pope-mega` — ~40 Opus agents, ~2M tokens. Maximum coverage, only when budget allows.

## 2. Write the spec to disk
Take the spec object the workflow returned and **Write** it verbatim to:
`research/pope/<area-slug>-<YYYY-MM-DD>.json`
(create the `research/pope/` dir if needed; slugify the area, e.g. `water-2026-06-14`).

## 3. Render the PDF
Run the deterministic renderer:
```
python3 -m engine.pope.render research/pope/<slug>.json research/pope/<slug>
```
It writes `<slug>.html` and `<slug>.pdf` (PDF via headless Chrome). Each thesis carries an optional `chart` (or `charts[]`) — a trendline, bottleneck bars, supply/demand gap, or dependency chain built from the call's grounded numbers — rendered inline as evidence (see `engine/pope/charts.py`).

## 3b. Humanizer gate (mandatory before anything ships publicly)
Before this board feeds a PDF that goes to the site, a post, an email, or a buyer, run the **humanizer** skill over its prose fields (target AI-tell ≤ 15: no em-dashes, no "delve/underscore/landscape" filler, no antithesis-punch templating). The brand sells honesty; AI-scented prose undercuts the calls. Internal/working renders can skip it; anything public cannot. (See `VOICE.md` + `humanizer-context.md`.)

## 4. Report back
Give the user: the area, how many candidates were generated vs how many survived the refute (`promoted/total`), the top 3 calls with their `vision% / clause%`, the one-line synthesis, and the path to the PDF. For each top call, include the practical `action_now` or `decision_changed` line if present. Note that these are hardened candidates, not yet forward-tracked, and offer to append the survivors to `FUTURE_MAP.md` as a dated immutable round.

## Notes
- Cost: `/pope` is ~15-20 Sonnet agents. `/pope-mega` is ~40 Opus agents (~1.5-2.5M tokens) for maximum coverage.
- Grounding: every channel + gate agent first runs `uv run python -m engine.cli ground "<area or needle>"` (the retrieval bridge, `engine/ground.py`). That pack puts the MEASURED data layer in front of the model: spine-coverage walk (which of the 9 causal layers the data sees vs is blind to), dated signal trends + detector fires, patent HHI/concentration, the measured citation-dependency edges (to name the inelastic input), and the LIVE prediction-market priced-in gate (Manifold/Metaculus). Agents also read `FUTURE_MAP.md` (de-dupe) and do a bounded web search for anything the pack is blind to. So the generator anchors on measured trends and the gate's priced-in check is a real market anchor, not just a web search.
- Honesty rails are built into the gate: live price-channel check (obscure != unpriced), supply-elasticity test, adversarial refute, and the two-probability split so confidence never drifts into hedging or bravado.
- Commercial rail: the output must explain who it helps and which real decision it changes. If it cannot name exposure, action, ROI/risk logic, and first trigger, it is not buyer-ready even if it is intellectually interesting.
- To target a single channel hard, pass a focused `domain` and `channels: 1`.
