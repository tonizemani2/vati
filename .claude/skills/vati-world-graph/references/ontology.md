# Vati World Graph ontology

## Node kinds

- `domain`: the sector, system, or world-slice being mapped.
- `thesis`: a Pope thesis as written in the source board.
- `constraint`: the bottleneck or rent-capturing inelastic node.
- `forecast_clause`: the dated, scored proposition.
- `metric`: the resolving measurement.
- `kill_condition`: what falsifies the thesis.
- `observable`: early signal or watch item.
- `buyer_segment`: exposed buyer, operator, investor, or policymaker.
- `action`: decision or action changed by the thesis.
- `price_channel`: instrument, contract, market, procurement price, or narrative channel to test priced-in status.
- `winner` / `loser`: beneficiaries or exposed losers, not investment advice.
- `source`: artifact, document, or dataset backing the graph.

## Edge relations

- `contains_thesis`
- `states`
- `identifies_constraint`
- `resolved_by`
- `falsified_by`
- `priced_through`
- `watched_by`
- `conditional_on_constraint`
- `scored_by`
- `exposes`
- `changes_action`
- `creates_winner`
- `creates_loser`
- `moves_rent_to`
- `creates_next_constraint`
- `migrates_to`
- `reprices`
- `changes_decision`
- `justified_by_roi`

## Coverage layers

Use the existing Vati causal order plus forces:

1. Frontier
2. Capability
3. Dependency graph
4. Supply elasticity
5. Demand
6. Capital
7. Pricing
8. Policy and geopolitics
9. Outcomes
10. Forces: social, talent, legal, climate, narrative

## Verification states

- `source_artifact`: a source artifact exists, but its internal claims still need source checks.
- `derived_from_board`: deterministic extraction from a Pope board.
- `source_verified`: source URL, date, quote/field, trust rationale, and status checked.
- `refuted`: evidence weakens or kills the claim.
- `superseded`: replaced by a newer graph claim.

Only `source_verified` facts are decision-grade.
