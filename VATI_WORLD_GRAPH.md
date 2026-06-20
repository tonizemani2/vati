# VATI_WORLD_GRAPH - the persistent future atlas

## What this is

Pope Mega should no longer be only a topic-to-report machine. The durable layer is a
persistent World Graph: a dated, sourced map of constraints, dependencies, actors,
signals, forecasts, scenarios, unknowns, and actions.

Pope Mega becomes a view generator over the graph. Pope Ultra becomes the operating
and verification layer for the nodes that matter.

## The spine

The system follows the existing Vaticinus causal order:

`Frontier -> Capability -> Dependency graph -> Supply elasticity -> Demand -> Capital -> Pricing -> Policy -> Outcomes`

The graph adds the missing connective tissue:

- entities: companies, agencies, labs, assets, materials, technologies, people, places;
- state variables: capacity, price, cost, lead time, demand, adoption, permits, funding;
- mechanisms: depends_on, substitutes_for, bottlenecks, amplifies, regulates, finances, delays, unlocks;
- constraints: nodes whose supply elasticity is too slow for the demand shock;
- forecast clauses: dated, probabilistic, falsifiable claims tied to nodes;
- watch signals: measurable triggers that update the graph;
- unknowns: explicit tasks, never hidden by prose;
- actions: buyer, operator, investor, or policymaker decisions that change if the call is right.

## Artifact contract

The deterministic compiler emits:

- `world_graph.json` - source of truth for nodes, edges, forecasts, coverage, unknowns, and agents.
- `world_graph.md` - human-readable atlas memo.
- `nodes.csv` and `edges.csv` - graph imports.
- `coverage_audit.csv` - what is covered and what remains blind.
- `unknown_queue.csv` - tasks for agents or human verification.
- `watchlist.csv` - monitorable signals and kill checks.
- `agent_roster.csv` - the multi-agent topology for a future approved run.

Run it:

```bash
python3 -m engine.cli world-graph-compile research/pope/after-ai-2026-06-17.json \
  --out-dir research/world_graph/after-ai-2026-06-17
```

## Agent topology

The full agent run is not the deterministic compiler. The compiler creates the map and
the work queue. A full run fans out across:

1. graph cartography,
2. frontier and capability,
3. dependency chains,
4. supply elasticity,
5. pricing gate,
6. policy and geopolitics,
7. capital flows,
8. demand shocks,
9. social, talent, legal, climate, and narrative forces,
10. adversarial refutation,
11. scenario architecture,
12. Ultra operations,
13. monitoring and scoring.

Any paid or Opus version of this requires a user nod first with the agent count,
rough token/cost estimate, and run mode.

## Quality bar

- A graph node without source status is not decision-grade.
- A forecast without metric, resolve date, probability, watch signal, and kill condition does not graduate.
- A named permit, project, company, person, contact, or dollar amount stays unverified until source-backed.
- Unknowns become tasks, not narrative filler.
- Forecasts and graph claims are superseded, never silently edited.
- The graph must preserve refutations, substitutes, and already-priced evidence.

## Product shape

The public product is not "ask an AI about the future." It is a visible research cockpit:
dated calls, graph context, constraint maps, watch signals, source trail, calibration, and
open unknowns. The premium product is the deeper graph plus agentic verification and
decision-specific operating packets.
