# Demand Shock Quantification

**Role:** demand_shock  
**Focus:** Quantify the downstream demand forcing function and its timing across six theses from the board.  
**Status:** All proposed elements are **hypothesis** unless marked as derived from board; no external source verification has been performed yet.

---

## Findings

The board describes six parallel demand shocks, each a structural reallocation of spending from a currently visible bottleneck (models, GPUs, robot bodies, lab discovery, cloud chat, organism design) toward a downstream constraint that will capture rent and drive capex/opex decisions. Each shock has:

- A **probability of materializing** (`clause_p`),
- A **resolution horizon** (when the shift should be measurably dominant),
- An **observable metric** and **watch signal** for early detection,
- A **kill condition** that would falsify the shift.

The shocks are not independent; they share a common logic of “bottleneck migration” after AI commoditizes a layer. The demand forcing functions can be viewed as step changes in the **elasticity of substitution** between the old scarce input and the new scarce input, with timing dictated by capacity deployment cycles (data centers, robot integration, lab build‑outs, device hardware cycles).

---

## Proposed Nodes

Each node captures the core demand shock for one thesis. Properties include a magnitude estimate (the board’s own `clause_p` and `vision_p`), timing, the affected buyer segments and the reallocation mechanism.

| node\_id | kind | label | properties (key fields) | verification\_status |
|----------|------|-------|--------------------------|----------------------|
| n-demand-shock-p1 | demand\_shock | P1 – Firm‑power siting demand shock | **description:** Data‑center capex shifts from generic shell capacity to power‑secured campuses with behind‑the‑meter clean firm generation. **magnitude\_estimate:** clause\_p=52 (probability shock dominates by end 2028); vision\_p=82. **timing:** resolves 2028‑12‑31; early signals through 2026‑2027. **affected\_segments:** hyperscaler infrastructure teams, data‑center developers, power developers, AI labs, infrastructure investors. **reallocation:** rent flows from grid‑dependent campuses to geothermal/firm‑power developers and power‑secured land. **trigger\_observable:** hyperscaler or top REIT announces 100 MW+ campus with behind‑the‑meter clean firm power as differentiator. | hypothesis |
| n-demand-shock-p2 | demand\_shock | P2 – Certified‑deployment demand shock | **description:** Automation spending shifts from undifferentiated robot hardware to deployment software/services (task libraries, simulation validation, commissioning, safety). **magnitude\_estimate:** clause\_p=46; vision\_p=78. **timing:** resolves 2028‑12‑31. **affected\_segments:** manufacturing COOs, logistics operators, integrators, robot OEMs, investors. **reallocation:** rent flows to simulation ecosystems (NVIDIA Isaac/Cosmos‑style), integrators with reusable task libraries, and OEMs proving uptime/safety; custom integrators and commoditized humanoid OEMs lose. **trigger\_observable:** major deployment press release naming validation/simulation layer as scaling reason. | hypothesis |
| n-demand-shock-p3 | demand\_shock | P3 – Autonomous‑science experimental‑throughput demand shock | **description:** R&D spending shifts from model‑only AI discovery to high‑throughput experimental capacity (robotic labs, assay availability). **magnitude\_estimate:** clause\_p=44; vision\_p=76. **timing:** resolves 2029‑12‑31. **affected\_segments:** pharma, materials, chemicals companies, national labs, AI‑discovery startups. **reallocation:** resource allocation moves toward autonomous wet‑lab capacity and assay throughput rather than foundational model training. **trigger\_observable:** major pharma/material company publicly states AI bottleneck is lab throughput, not model quality. | hypothesis |
| n-demand-shock-p4 | demand\_shock | P4 – Edge‑AI always‑on demand shock | **description:** Consumer device spend and usage time shift from cloud‑based chat interfaces to persistent on‑device AI (wearables, glasses, phones) with local context, privacy, sensors. **magnitude\_estimate:** clause\_p=43; vision\_p=70. **timing:** resolves 2028‑12‑31. **affected\_segments:** device OEMs (Apple, Google, Samsung, Meta), consumer AI app developers, cloud‑AI providers. **reallocation:** semiconductor/IP investment flows to low‑power NPUs, sensor fusion, local memory; cloud‑chat dominance declines if shock materializes. **trigger\_observable:** product launch where lead AI feature runs persistently on‑device marketed around private context. | hypothesis |
| n-demand-shock-p5 | demand\_shock | P5 – Biomanufacturing scale‑up demand shock | **description:** Bioeconomy investment shifts from AI‑organism design to scale‑up infrastructure (pilot fermentation, downstream processing, process development labor). **magnitude\_estimate:** clause\_p=41; vision\_p=72. **timing:** resolves 2030‑12‑31. **affected\_segments:** synthetic biology companies, industrial biotech, biomanufacturing CDMOs, ag/chemical/fuel offtakers. **reallocation:** capex/partnering dollars flow to pilot/commercial‑scale capacity rather than design‑only platforms. **trigger\_observable:** well‑funded AI‑bio company delays launch due to pilot capacity or COGS failure despite successful lab design. | hypothesis |
| n-demand-shock-p6 | demand\_shock | P6 – Agentic‑AI governance demand shock | **description:** Enterprise AI spending shifts from model capability to action‑governance tooling (audit logs, least‑privilege controls, rollback, insurance). **magnitude\_estimate:** clause\_p=48; vision\_p=74. **timing:** resolves 2028‑06‑30. **affected\_segments:** enterprise IT, procurement, risk management, agent‑platform vendors, security/compliance tools. **reallocation:** separate “action‑governance” line items emerge in RFPs and budgets; platforms without explicit authority management lose adoption for high‑stakes tasks. **trigger\_observable:** Fortune 500 RFP, insurance policy, or regulator requiring agent action logs, approval chains, and rollback. | hypothesis |

---

## Proposed Edges

Edges link each demand shock node to the corresponding thesis, constraint, metric, watch observable, kill condition, and price channel. They follow the existing naming convention with temporary IDs.

| edge\_id | src | dst | rel | confidence | rationale | verification\_status |
|----------|-----|-----|-----|------------|-----------|----------------------|
| e-n-demand-shock-p1‑is‑shock‑of‑thesis‑P1 | n-demand-shock-p1 | n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf | is\_demand\_shock\_of | 0.8 | The shock quantifies the downstream forcing function implied by thesis P1. | hypothesis |
| e-n-demand-shock-p1‑conditional‑on‑constraint | n-demand-shock-p1 | n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b | conditional\_on | 0.75 | Shock materializes only if the named constraint remains binding. | hypothesis |
| e-n-demand-shock-p1‑observed‑by‑metric | n-demand-shock-p1 | n-metric-track-hyperscaler-and-data-center-developer-announcements-that-name-on-si-f5493b8f | observed\_by | 0.85 | The board metric tracks the shock’s occurrence. | hypothesis |
| e-n-demand-shock-p1‑triggered‑by‑watch | n-demand-shock-p1 | w-watch-p1-a-hyperscaler-or-top-data-center-reit-announcing-a-100-mw-plus-campus-w-e28b84f7 | triggered\_by | 0.7 | The watch signal provides an early indicator. | hypothesis |
| e-n-demand-shock-p1‑invalidated‑by‑kill | n-demand-shock-p1 | n-kill-condition-kill-if-by-end-2028-fewer-than-two-hyperscaler-scale-campuses-pub-495cf67f | invalidated\_by | 0.9 | The kill condition defines when the shock hypothesis is falsified. | hypothesis |
| e-n-demand-shock-p1‑reprices | n-demand-shock-p1 | n-price-channel-power-secured-land-options-behind-the-meter-ppas-geothermal-develo-8b047c51 | reprices | 0.65 | Shock implies repricing of certain assets. | hypothesis |
| e-n-demand-shock-p2‑is‑shock‑of‑thesis‑P2 | n-demand-shock-p2 | n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc | is\_demand\_shock\_of | 0.8 | — | hypothesis |
| e-n-demand-shock-p2‑conditional‑on‑constraint | n-demand-shock-p2 | n-constraint-verified-task-data-sim-to-real-validation-workcell-commissioning-safe-1f01fc96 | conditional\_on | 0.75 | — | hypothesis |
| e-n-demand-shock-p2‑observed‑by‑metric | n-demand-shock-p2 | n-metric-track-robot-oems-or-large-integrators-selling-task-libraries-simulation-v-3d361480 | observed\_by | 0.85 | — | hypothesis |
| e-n-demand-shock-p2‑triggered‑by‑watch | n-demand-shock-p2 | w-watch-p2-a-major-automotive-or-logistics-deployment-where-the-press-release-name-f3d2c000 | triggered\_by | 0.7 | — | hypothesis |
| e-n-demand-shock-p2‑invalidated‑by‑kill | n-demand-shock-p2 | n-kill-condition-kill-if-by-end-2028-humanoid-or-mobile-manipulation-deployments-s-775de1ac | invalidated\_by | 0.9 | — | hypothesis |
| e-n-demand-shock-p2‑reprices | n-demand-shock-p2 | n-price-channel-physical-ai-valuation-should-migrate-from-unit-shipments-to-deploy-e5cd43e2 | reprices | 0.65 | — | hypothesis |
| (P3–P6 analogous edges follow the same pattern, mapping to each thesis’s corresponding constraint, metric, watch, kill, and price channel nodes.) | | | | | | |
| e-n-demand-shock-p3‑is‑shock‑of‑thesis‑P3 | n-demand-shock-p3 | n-thesis-p3-autonomous-science-shifts-the-bottleneck-from-model-discovery-to-exper-2d0ad3e9 | is\_demand\_shock\_of | 0.8 | — | hypothesis |
| e-n-demand-shock-p3‑conditional‑on‑constraint | n-demand-shock-p3 | n-constraint-robotic-experimental-throughput-with-standardized-metadata-reliable-a-6881a685 | conditional\_on | 0.75 | — | hypothesis |
| e
