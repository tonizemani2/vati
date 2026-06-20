# DeepSeek V4 World Graph Run Manifest

Created: 2026-06-18T20:48:00+00:00
Run mode: `dry_run_call_plan`
Plan: `full`
Board: `research/pope/after-ai-2026-06-17.json`
Calls: 40
Estimated cost, cache miss: $0.2847

## Models

- `deepseek-v4-flash`: 22 calls, ~423151 input tokens, ~54800 output tokens, $0.0746
- `deepseek-v4-pro`: 18 calls, ~346974 input tokens, ~68000 output tokens, $0.2101

## Cost And Approval

This manifest is safe to generate. Actual API execution requires `--execute`, `DEEPSEEK_API_KEY`, and cost-gate approval.

## Calls

- `01_graph_cartographer` graph_cartographer on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/01_graph_cartographer.md`
- `02_frontier_capability` frontier_capability on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/02_frontier_capability.md`
- `03_dependency_chain` dependency_chain on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/03_dependency_chain.md`
- `04_supply_elasticity` supply_elasticity on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/04_supply_elasticity.md`
- `05_pricing_gate` pricing_gate on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/05_pricing_gate.md`
- `06_policy_geopolitics` policy_geopolitics on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/06_policy_geopolitics.md`
- `07_capital_flows` capital_flows on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/07_capital_flows.md`
- `08_demand_shock` demand_shock on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/08_demand_shock.md`
- `09_forces_scan` forces_scan on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/09_forces_scan.md`
- `10_adversarial_refute` adversarial_refute on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/10_adversarial_refute.md`
- `11_scenario_architect` scenario_architect on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/11_scenario_architect.md`
- `12_ultra_operator` ultra_operator on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/12_ultra_operator.md`
- `13_monitoring_scorecard` monitoring_scorecard on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/13_monitoring_scorecard.md`
- `14_p1_source_pack` source_pack on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/14_p1_source_pack.md`
- `15_p1_substitute_refute` substitute_refute on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/15_p1_substitute_refute.md`
- `16_p1_scenario_branch` scenario_branch on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/16_p1_scenario_branch.md`
- `17_p1_ultra_verification` ultra_verification on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/17_p1_ultra_verification.md`
- `18_p2_source_pack` source_pack on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/18_p2_source_pack.md`
- `19_p2_substitute_refute` substitute_refute on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/19_p2_substitute_refute.md`
- `20_p2_scenario_branch` scenario_branch on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/20_p2_scenario_branch.md`
- `21_p2_ultra_verification` ultra_verification on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/21_p2_ultra_verification.md`
- `22_p3_source_pack` source_pack on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/22_p3_source_pack.md`
- `23_p3_substitute_refute` substitute_refute on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/23_p3_substitute_refute.md`
- `24_p3_scenario_branch` scenario_branch on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/24_p3_scenario_branch.md`
- `25_p3_ultra_verification` ultra_verification on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/25_p3_ultra_verification.md`
- `26_p4_source_pack` source_pack on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/26_p4_source_pack.md`
- `27_p4_substitute_refute` substitute_refute on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/27_p4_substitute_refute.md`
- `28_p4_scenario_branch` scenario_branch on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/28_p4_scenario_branch.md`
- `29_p4_ultra_verification` ultra_verification on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/29_p4_ultra_verification.md`
- `30_p5_source_pack` source_pack on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/30_p5_source_pack.md`
- `31_p5_substitute_refute` substitute_refute on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/31_p5_substitute_refute.md`
- `32_p5_scenario_branch` scenario_branch on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/32_p5_scenario_branch.md`
- `33_p5_ultra_verification` ultra_verification on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/33_p5_ultra_verification.md`
- `34_p6_source_pack` source_pack on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/34_p6_source_pack.md`
- `35_p6_substitute_refute` substitute_refute on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/35_p6_substitute_refute.md`
- `36_p6_scenario_branch` scenario_branch on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/36_p6_scenario_branch.md`
- `37_p6_ultra_verification` ultra_verification on `deepseek-v4-flash` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/37_p6_ultra_verification.md`
- `38_integrator` integrator on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/38_integrator.md`
- `39_critic` critic on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/39_critic.md`
- `40_repair` repair on `deepseek-v4-pro` -> `research/world_graph/after-ai-2026-06-17.deepseek/prompts/40_repair.md`
