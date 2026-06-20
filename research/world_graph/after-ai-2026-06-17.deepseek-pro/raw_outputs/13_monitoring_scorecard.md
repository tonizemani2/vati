# Monitoring Scorecard: After AI – Constraint Migration Forecasts

## Findings

- The atlas contains 6 forecast clauses (P1–P6), each with a defined metric, kill condition, resolution date, and a watchlist signal.
- Coverage gaps remain: 24 verification tasks open across source packs, substitute paths, scenario branches, and entity resolution. No decision-grade node has yet reached external source-verified status; all current node confidence derives from the board artifact (`derived_from_board`).
- The board itself is a source artifact (`n-source-research-pope-after-ai-2026-06-17-json-afabfe46`, confidence 1.0) and serves as the origin of all thesis structure.
- The monitoring scorecard must operationalise these clauses by linking observables to a scoring cadence, kill triggers, and a log of scoring updates.

## Proposed Nodes

### 1. Master Monitoring Scorecard

- **ID**: `n-monitoring-scorecard-master`
- **Kind**: `monitoring_scorecard`
- **Label**: `Master Monitoring Scorecard – After AI Constraint Forecasts (2026-06-17 board)`
- **Confidence**: `hypothesis` (proposed by this role)
- **Fields**:
  - `generated_at`: `2026-06-18T21:26:03+00:00` (from atlas meta)
  - `horizon`: `2028 to 2031`
  - `board_source`: `n-source-research-pope-after-ai-2026-06-17-json-afabfe46`
  - `coverage_score`: `85` (current)
  - `status`: `active`
- **Rationale**: Aggregates all active forecast clauses, their observables, and scoring records into a single management dashboard.

### 2. Scoring Records (one per thesis)

For each thesis Px (x=1..6) create a scoring record node that holds the current score, update log, and the scoring logic. All are **hypothesis** until populated.

| ID | Kind | Label | Fields |
|----|------|-------|--------|
| `n-score-p1` | `scoring_record` | `Scoring Record: P1 Firm Power Siting` | `forecast_id`: `f-forecast-p1-...`, `metric_node`: `n-metric-...`, `kill_node`: `n-kill-condition-...`, `resolution_date`: `2028-12-31`, `current_score`: `null`, `score_history`: `[]`, `scoring_rule`: `binary_resolve` |
| `n-score-p2` | `scoring_record` | `Scoring Record: P2 Certified Deployment` | ... same pattern ... |
| `n-score-p3` | `scoring_record` | `Scoring Record: P3 Autonomous Science` | ... |
| `n-score-p4` | `scoring_record` | `Scoring Record: P4 Edge Consumer AI` | ... |
| `n-score-p5` | `scoring_record` | `Scoring Record: P5 Biomanufacturing Scale-Up` | ... |
| `n-score-p6` | `scoring_record` | `Scoring Record: P6 Agentic Authority Layer` | ... |

**Common scoring rule**: At resolution date, if kill condition is met → score = 0; else evaluate metric against threshold defined in kill condition; final score ∈ {0,1}. Interim scoring based on metric trend may be logged but not alter final binary.

### 3. Watchlist Signal Checkpoint Nodes (optional future nodes)

The existing watchlist items already capture the primary observable signal. A future node could be a `signal_checkpoint` linking to the watchlist item, timestamp of last check, and signal strength. Not proposed now to avoid redundant nodes; instead, the scoring record will reference the watchlist ID.

## Proposed Edges

All edges will be derived from the master scorecard node to the relevant scoring records and then to existing nodes. They are **hypothesis** pending creation.

- `(n-monitoring-scorecard-master)-[contains_scorecard]->(n-score-px)` for each scoring record.
- `(n-score-px)-[scores_forecast]->(n-forecast-clause-...-px)` (existing forecast clause node).
- `(n-score-px)-[evaluated_by]->(n-metric-...-px)` (existing metric node).
- `(n-score-px)-[terminated_by]->(n-kill-condition-...-px)` (existing kill condition node).
- `(n-score-px)-[watched_via]->(w-watch-px-...)` (existing watchlist item).
- `(n-score-px)-[updates_status]->(n-forecast-clause-...-px)` to reflect score changes.

## Evidence Needed

All 24 unknown‑queue items must be resolved before any external source‑verified scoring can begin. The critical paths are:

- **Source Packs** (6 tasks, owner A01, priority critical): Attach primary/official URLs and publication dates to every load‑bearing node. Until complete, metrics and kill thresholds lack a verifiable basis.
- **Entity Resolution** (6 tasks, owner A01, priority high): Resolve named entities (e.g., “Fervo‑style EGS”, “NVIDIA Isaac/Cosmos”) to canonical companies/projects.
- **Substitute Paths** (6 tasks, owner A10, priority high): Map substitutes that would weaken or kill the bottleneck. These act as systematic refutations.
- **Scenario Branches** (6 tasks, owner A11, priority medium): Create base/upside/downside scenarios. Needed to calibrate score sensitivity.

No sourcing has been verified for the watchlist signals yet. All six signals are marked `unverified_source_needed`.

## Refutations

Each thesis comes with a built‑in kill condition, which is the refutation clause. Summarised:

| Thesis | Kill Condition |
|--------|---------------|
| P1 | By end 2028, fewer than two hyperscaler‑scale campuses publicly secure behind‑the‑meter firm clean generation as core siting advantage, or transformer/interconnection delays normalize below ~24 months in main US AI DC markets. |
| P2 | By end 2028, humanoid/mobile manipulation scale mainly via turnkey hardware with little separate pricing for task validation, commissioning software, or safety tooling. |
| P3 | By 2029, model‑only AI discovery companies repeatedly produce commercially validated materials/therapies without materially expanding wet‑lab/physical‑test throughput. |
| P4 | By end 2028, dominant consumer AI usage remains cloud‑chat in phones/browsers; wearables/glasses fail to show persistent local context as major usage mode. |
| P5 | By 2030, multiple AI‑designed industrial bio‑products reach commodity scale and price parity without scarce pilot capacity, downstream processing, or process‑development labor becoming a public bottleneck. |
| P6 | By mid‑2028, large enterprises widely deploy multi‑step agents with real system authority using mostly prompt‑level guardrails and generic logging, without a separate action‑governance budget. |

## Next Actions

1. **Prioritise source packs**: Instruct agent A01 to complete the 6 critical source‑pack tasks. Establish a deadline (e.g., within 7 days) to attach verified URLs and publication dates.
2. **Schedule first watchlist check**: For all 6 watchlist items, set a recurring monthly cadence (as stated) and create a log entry for the initial check date. Assign agent A13 to perform the first scan.
3. **Integrate scoring records**: Once source packs are verified, populate the proposed `n-score-px` nodes with baseline confidence and mark them as `source_verified` for the metric definition.
4. **Resolve unknowns in order**: After source packs, complete entity resolution (A01), then substitute paths (A10), then scenario branches (A11). Each completed task should raise the coverage score and transition affected nodes to `source_verified` or `lead`.
5. **Publish an interim scorecard report**: After the first watchlist cycle, publish a summary with current signal status and updated coverage score. This report becomes a new node in the graph (e.g., `n-report-monitoring-interim-2026-07`).

All dates and agent assignments are taken directly from the atlas `meta` and `unknown_queue` entries; no new dates or agents are invented.
