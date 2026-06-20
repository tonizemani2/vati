# DeepSeek V4 Pro Partial Run Status

Date: 2026-06-18

Status: paused manually because the Mac was unstable/restarting.

Completed raw outputs:

1. `01_graph_cartographer.md`
2. `02_frontier_capability.md`
3. `03_dependency_chain.md`
4. `04_supply_elasticity.md`
5. `05_pricing_gate.md`
6. `06_policy_geopolitics.md`
7. `07_capital_flows.md`
8. `08_demand_shock.md`
9. `09_forces_scan.md`

Next call to resume:

10. `10_adversarial_refute.md`

Resume command:

```bash
COST_AUTO_APPROVE_CENTS=200 uv run python -m engine.cli world-graph-deepseek research/pope/after-ai-2026-06-17.json --out-dir research/world_graph/after-ai-2026-06-17.deepseek-pro --plan full --model-flash deepseek-v4-pro --model-pro deepseek-v4-pro --execute
```

The runner skips non-empty existing `raw_outputs/*.md` files, so it should continue from call 10 rather than rerunning calls 1-9.
