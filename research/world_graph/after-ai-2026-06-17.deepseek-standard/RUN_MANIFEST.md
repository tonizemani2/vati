# DeepSeek V4 World Graph Run Manifest

Created: 2026-06-18T20:48:00+00:00
Run mode: `dry_run_call_plan`
Plan: `standard`
Board: `research/pope/after-ai-2026-06-17.json`
Calls: 17
Estimated cost, cache miss: $0.1184

## Models

- `deepseek-v4-flash`: 10 calls, ~191466 input tokens, ~26000 output tokens, $0.0341
- `deepseek-v4-pro`: 7 calls, ~134256 input tokens, ~29800 output tokens, $0.0843

## Cost And Approval

This manifest is safe to generate. Actual API execution requires `--execute`, `DEEPSEEK_API_KEY`, and cost-gate approval.

## Calls

- `01_graph_cartographer` graph_cartographer on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek-standard/prompts/01_graph_cartographer.md`
- `02_frontier_capability` frontier_capability on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek-standard/prompts/02_frontier_capability.md`
- `03_dependency_chain` dependency_chain on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek-standard/prompts/03_dependency_chain.md`
- `04_supply_elasticity` supply_elasticity on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek-standard/prompts/04_supply_elasticity.md`
- `05_pricing_gate` pricing_gate on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek-standard/prompts/05_pricing_gate.md`
- `06_policy_geopolitics` policy_geopolitics on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek-standard/prompts/06_policy_geopolitics.md`
- `07_capital_flows` capital_flows on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek-standard/prompts/07_capital_flows.md`
- `08_demand_shock` demand_shock on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek-standard/prompts/08_demand_shock.md`
- `09_forces_scan` forces_scan on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek-standard/prompts/09_forces_scan.md`
- `10_adversarial_refute` adversarial_refute on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek-standard/prompts/10_adversarial_refute.md`
- `11_scenario_architect` scenario_architect on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek-standard/prompts/11_scenario_architect.md`
- `12_ultra_operator` ultra_operator on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek-standard/prompts/12_ultra_operator.md`
- `13_monitoring_scorecard` monitoring_scorecard on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek-standard/prompts/13_monitoring_scorecard.md`
- `14_integrator` integrator on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek-standard/prompts/14_integrator.md`
- `15_critic` critic on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek-standard/prompts/15_critic.md`
- `16_repair` repair on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek-standard/prompts/16_repair.md`
- `17_score` score on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek-standard/prompts/17_score.md`
