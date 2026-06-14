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
- `args`: `{ "domain": "<the area from $ARGUMENTS, or 'any area, wide open across all industries'>", "model": "sonnet", "channels": 5, "per_channel": 2, "top_k": <top_k arg or 6>, "date": "<today's date YYYY-MM-DD>" }`

The workflow fans out the channel miners (each first reads `FUTURE_MAP.md` so it builds on our prior calls), then a grounded adversarial gate (one web search per candidate for the live price/anchor) refutes each and scores the dual probabilities (vision + strict clause), then synthesis returns a complete renderable spec. Wait for it to finish; the returned object is the spec.

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
It writes `<slug>.html` and `<slug>.pdf` (PDF via headless Chrome).

## 4. Report back
Give the user: the area, how many candidates were generated vs how many survived the refute (`promoted/total`), the top 3 calls with their `vision% / clause%`, the one-line synthesis, and the path to the PDF. Note that these are hardened candidates, not yet forward-tracked, and offer to append the survivors to `FUTURE_MAP.md` as a dated immutable round.

## Notes
- Cost: `/pope` is ~15-20 Sonnet agents. `/pope-mega` is ~40 Opus agents (~1.5-2.5M tokens) for maximum coverage.
- Grounding: agents read `FUTURE_MAP.md` and do a bounded web search for the price-channel check. They do NOT yet query the arXiv corpus or a patent graph (patents are our known data gap); that is a future upgrade.
- Honesty rails are built into the gate: live price-channel check (obscure != unpriced), supply-elasticity test, adversarial refute, and the two-probability split so confidence never drifts into hedging or bravado.
- To target a single channel hard, pass a focused `domain` and `channels: 1`.
