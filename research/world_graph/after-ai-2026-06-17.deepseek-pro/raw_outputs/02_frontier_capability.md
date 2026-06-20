# Findings

## Capability Frontier Shift
The atlas reveals a consistent pattern across six domains: **the AI capability frontier is moving from digital model performance to physical-world and operational constraints**.  
When foundational model access becomes commoditized, the binding scarcity becomes *where and how intelligence is deployed, validated, and governed*.

**Exact technical changes creating new demand:**
1. **Power‑siting integration** – AI load outruns grid capacity; demand shifts to developers who can bundle land, fiber, firm behind‑the‑meter generation, and permitting into a single campus timeline (P1).
2. **Deployment certification stack** – Robot bodies are abundant; the scarce layer becomes task libraries, sim‑to‑real validation, safety sign‑off, and repeatable commissioning workflows (P2).
3. **Autonomous lab throughput** – AI‑generated molecular hypotheses surpass physical testing; the bottleneck moves to robotic experiments with standardized metadata and assay capacity (P3).
4. **On‑device AI orchestration** – Cloud‑chat dominates today; the next wave requires low‑power NPUs, persistent local context, thermal management, and privacy‑preserving agents on wearables/glasses (P4).
5. **Biomanufacturing scale‑up** – AI‑engineered organisms are designed faster than they can be fermented; the gap is pilot capacity, downstream processing, and COGS parity (P5).
6. **Agent authority & auditability** – Multi‑step agents need more than prompt guardrails; demand emerges for identity‑permissioned action logs, rollback, and insurance‑grade governance (P6).

This frontier pattern is not about discovering new AI models but about **delivering AI outcomes** under real‑world physics, institutional consent, and economic viability.

---

# Proposed Nodes*

*Marked as hypothesis unless sourced from the Pope board (source_verified). Existing nodes are referenced by ID; new nodes receive proposed IDs.*

| Proposed Node | Label | Kind | Status |
|---------------|-------|------|--------|
| `n-capability-frontier-what-comes-next` | “Post‑AI capability frontier is physical/operational, not model‑centric” | `frontier` | hypothesis |
| `n-demand-shift-site-development-as-ai-infra` | “Site development with power‑secured land becomes the primary AI infrastructure asset” | `demand_shift` | hypothesis |
| `n-demand-shift-deployment-assurance-software` | “Deployment assurance (sim‑validation, task libs, safety case) separates from robot hardware sales” | `demand_shift` | hypothesis |
| `n-demand-shift-lab-robotics-capacity` | “High‑throughput autonomous labs become the counterpart to AI‑driven discovery” | `demand_shift` | hypothesis |
| `n-demand-shift-edge-ai-context-and-thermals` | “Always‑on local AI with context capture and thermal headroom becomes consumer device differentiator” | `demand_shift` | hypothesis |
| `n-demand-shift-pilot-and-downstream-bio` | “Pilot fermentation & downstream processing capacity become biotech’s AI‑scale bottleneck” | `demand_shift` | hypothesis |
| `n-demand-shift-agent-governance-platforms` | “Agent authority, audit, and rollback platforms separate from LLM API calls” | `demand_shift` | hypothesis |

# Proposed Edges

| Edge | Source -> Target | Relationship | Status |
|------|-----------------|--------------|--------|
| `e-frontier-shift-contains-theses` | `n-capability-frontier-what-comes-next` → `n-domain-what-comes-next-after-ai-093b9fee` | `summarizes` | hypothesis |
| `e-frontier-p1-link` | `n-capability-frontier-what-comes-next` → `n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf` | `exemplified_by` | hypothesis |
| `e-frontier-p2-link` | `n-capability-frontier-what-comes-next` → `n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc` | `exemplified_by` | hypothesis |
| `e-demand-shift-p1` | `n-demand-shift-site-development-as-ai-infra` → `n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b` | `resolves_constraint` | hypothesis |
| `e-demand-shift-p2` | `n-demand-shift-deployment-assurance-software` → `n-constraint-verified-task-data-sim-to-real-validation-workcell-commissioning-safe-1f01fc96` | `resolves_constraint` | hypothesis |
| … (similar edges for P3‑P6) … | | | hypothesis |

All edges linking new demand‑shift nodes to their corresponding constraints are tagged `hypothesis` until source‑verified.

---

# Evidence Needed

The following verification gaps must be closed to move the frontier finding from hypothesis to decision‑grade:

1. **Primary source packs** – Attach official URLs, dates, and quotes for every load‑bearing claim (Rhodium/LBL power projections, pv magazine transformer lead times, NVIDIA Isaac/Cosmos announcements, IDTechEx robotics data, DOE testbed awards, etc.). *Open tasks: u‑unknown‑p*‑source_pack.*  
2. **Substitute paths** – For each thesis, document alternatives that could collapse the bottleneck (e.g., massive grid interconnection acceleration, re‑usable task libraries becoming open‑source, lab‑on‑a‑chip breakthroughs). *Open tasks: u‑unknown‑p*‑substitute_path.*  
3. **Scenario branches** – Build base/upside/downside narratives with quantified triggers. *Open tasks: u‑unknown‑p*‑scenario_branch.*  
4. **Entity resolution** – Map named entities (Fervo‑style EGS operators, specific hyperscalers, robot integrators, national‑lab partners, biotech pilots) to canonical company/lab/project IDs. *Open tasks: u‑unknown‑p*‑entity_resolution.*  
5. **Cross‑thesis dependency** – Verify whether the P1 firm‑power constraint directly enables P3 lab throughput (e.g., labs need reliable power) or P6 agent governance (agents rely on always‑on inference). *New verification task recommended.*  

---

# Refutations

The meta‑thesis “the AI capability frontier shifts from models to physical/operational constraints” is falsifiable by:

- **Model‑centric breakthroughs**: If a new architecture (e.g., post‑transformer) reduces inference cost by orders of magnitude and eliminates the need for massive dedicated power or edge hardware, the power‑siting and edge‑device constraints may dissolve.
- **Regulatory flattening**: If nations accelerate grid interconnection, transformer manufacturing, and data‑center permitting such that the 24‑month backlog disappears in core markets by mid‑2028, P1 fails.
- **Turnkey deployment wins**: If robot OEMs deliver safe, repeatable tasks without separate software/integration line items and scale through hardware capex alone, P2 fails.
- **Lab‑free AI discovery**: If in‑silico validation reaches commercial acceptance without wet‑lab throughput expansion, P3 fails.
- **Cloud‑first consumers**: If users reject always‑on, privacy‑sensitive edge AI and stick to cloud‑chat as the primary interface, P4 fails.
- **Biomanufacturing leap**: If AI designs organisms that ferment at commodity scale with existing pilot capacity and minimal downstream tweaking, P5 fails.
- **Generic governance**: If enterprises deploy agents with simple prompt guardrails and no audit trail and incur no material incidents, P6 fails.

Each thesis already contains a kill condition; the meta‑thesis can be considered falsified if **≥4 of the 6 kill thresholds are met by their resolution dates**.

---

# Next Actions

1. **Complete source packs** – Agent A01 must attach primary references to every thesis node; priority: critical.
2. **Draft substitute paths** – Agent A10 to enumerate at least two refutation mechanisms per thesis.
3. **Build scenario branches** – Agent A11 to create quantified branches (e.g., “Geothermal boom: 5+ 100 MW campuses announced by Q2 2027” as upside for P1).
4. **Resolve entities** – Agent A01 to canonicalize all referenced organizations, projects, and equipment.
5. **Monitor watchlist signals** – Agent A13 to track the six watch items monthly; escalate if early kill conditions appear.
6. **New verification task** – Assign agent (suggest A10 or A11) to model cross‑constraint dependencies (e.g., how does firm‑power siting affect autonomous lab viability?) and link theses in the graph.

All outputs must remain falsifiable, sourced, and free of invented specifics.
