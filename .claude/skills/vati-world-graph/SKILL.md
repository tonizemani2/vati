---
name: vati-world-graph
description: Build or update Vaticinus/Vati's persistent World Graph from Pope boards, world-state packs, data feeds, and Ultra dossiers. Use when the user asks for a context graph, future web, world model, constraint atlas, generalized Pope system, scenario web, many-agent forecasting run, graph coverage audit, or a way to connect Pope Mega/Pope Ultra/data into one persistent future-prediction system.
---

# Vati World Graph

## Overview

Use this skill to turn Pope boards and data-layer evidence into a persistent, sourced
constraint atlas. The atlas is not a report. It is the substrate Pope Mega reads from
and Pope Ultra verifies against.

## Non-negotiables

- Do not run paid or Opus multi-agent workflows without first stating the agent count,
  rough token/cost estimate, run mode, and waiting for approval.
- Read `CLAUDE.md`, `VOICE.md`, `VATI_WORLD_GRAPH.md`, `FUTURE_MAP.md`, `VATI.md`,
  and `BRIEFING.md` before writing strategic artifacts or changing doctrine.
- Keep deterministic compiles separate from agent runs. The compiler builds the atlas
  and queue; it is not a full Pope Mega run.
- Promote only source-verified facts. Unverified names become tasks.
- Preserve forecast clauses exactly unless the task is explicitly to supersede them.

## Quick Start

Compile a board into a graph pack:

```bash
python3 -m engine.cli world-graph-compile research/pope/after-ai-2026-06-17.json \
  --out-dir research/world_graph/after-ai-2026-06-17
```

Prepare a DeepSeek V4 E2E improvement run without spending money:

```bash
python3 -m engine.cli world-graph-deepseek research/pope/after-ai-2026-06-17.json \
  --out-dir research/world_graph/after-ai-2026-06-17.deepseek \
  --plan standard
```

Execute only after explicit approval:

```bash
python3 -m engine.cli world-graph-deepseek research/pope/after-ai-2026-06-17.json \
  --out-dir research/world_graph/after-ai-2026-06-17.deepseek \
  --plan full --execute
```

Read outputs in this order:

1. `world_graph.md` for the human atlas.
2. `coverage_audit.csv` for blind spots.
3. `unknown_queue.csv` for agent tasks.
4. `watchlist.csv` for monitorable signals.
5. `world_graph.json` for the machine source of truth.
6. For DeepSeek runs: `RUN_MANIFEST.md`, `call_plan.json`, `prompts/`, and, after execute, `raw_outputs/`.

## Workflow

1. Load context.
   - Read the docs above and skim relevant `research/pope/*.json`.
   - If an existing atlas exists under `research/world_graph/`, compare before rewriting.

2. Compile the deterministic atlas.
   - Use `engine.world_graph` through the CLI.
   - Do not fill missing sources by memory.
   - Treat the coverage audit as the work queue.

3. Decide whether agents are needed.
   - Use agents when the user asks for a full graph expansion, cross-domain scenario web,
     or source-verified Ultra layer.
   - Before any paid/Opus run, ask for approval with cost and topology.
   - If running Codex-native local agents, label the run mode honestly and preserve a manifest.
   - For DeepSeek V4, use `world-graph-deepseek` dry-run first; show call count and estimate.

4. Fan out by role.
   - Cartographer: entity/node/edge map.
   - Frontier/capability: what changed technically.
   - Dependency chain: upstream input graph.
   - Supply elasticity: capacity, lead time, substitutes.
   - Pricing gate: already-priced and consensus checks.
   - Policy/geopolitics: permits, rules, controls.
   - Capital/demand/forces: why now, who funds it, what social/legal/climate forces matter.
   - Refute: kill arguments and demotions.
   - Scenario: compatible world states.
   - Ultra: named verification and action tasks.
   - Monitor: watchlist, scorecard, kill cadence.

5. Merge with discipline.
   - Merge new facts only with source URL, source date, trust rationale, and verification status.
   - Keep contradictions visible.
   - Do not hide weak coverage in prose.
   - Add or supersede graph claims; never silently mutate a scored forecast.

## Output Contract

Every serious run should produce or update:

- `world_graph.json`
- `world_graph.md`
- `nodes.csv`
- `edges.csv`
- `coverage_audit.csv`
- `unknown_queue.csv`
- `watchlist.csv`
- `agent_roster.csv`
- `RUN_MANIFEST.md` when agents are used

See `references/ontology.md` for the node, edge, and coverage vocabulary.
See `references/deepseek.md` for V4 model IDs, plan sizes, and cost rules.
