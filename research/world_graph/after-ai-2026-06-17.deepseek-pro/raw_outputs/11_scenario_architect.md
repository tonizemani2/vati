# Scenario Architecture: After AI Theses

## Common Findings
- All theses share a structural logic: a binding constraint → winners/losers → rent migration → forecast clause with a kill condition and observable metric.
- The board provides a deterministic derivation chain; no source-verified primary documents are attached, so all scenario components inherit the board’s confidence levels and verification status `derived_from_board`.
- Scenarios are constructed as **compatible branches** rather than isolated predictions—the same world can realize different branches across theses without logical contradiction, because each thesis operates in its own domain.
- For each thesis, three scenario branches are proposed:
  - **Base**: the thesis unfolds as described, the forecast clause resolves **True**, and the constraint remains binding through the resolution date.
  - **Upside**: the binding constraint tightens faster/earlier, advantages accrue more forcefully, and metrics overshoot.
  - **Downside**: the kill condition is triggered, or a substitute path undermines the bottleneck, rendering the forecast clause **False**.
- All proposed branches are hypotheses until anchored by source-verified evidence (e.g., official announcements, regulatory filings, price data). They are structured to be **falsifiable** and **source‑disciplined**.

Below, each thesis receives a compact scenario‑branch table, proposed new nodes and edges, evidence needed, refutations, and next actions.

---

## P1: The AI frontier moves from model access to firm‑power siting.
**Thesis Node:** `n-thesis-p1-…`  
**Constraint:** `n-constraint-contiguous-land-fiber-proximity-…`  
**Kill Condition:** < 2 hyperscaler‑scale campuses with behind‑the‑meter firm clean generation by end‑2028, or transformer & interconnection delays normalize below ~24 months in main US AI data‑center markets.  
**Resolution Date:** 2028-12-31

### Scenario Branches

| Branch | Description | Key Assumptions | Forecast Clause Result | Winner/Loser Intensity |
|--------|-------------|-----------------|------------------------|------------------------|
| **Base** | Between 2 and 5 hyperscaler‑scale campuses announce or break ground on sites where behind‑the‑meter firm clean power (geothermal, gas+CCS, nuclear restart) is the core siting differentiator by end‑2028. Transformer lead times stay above 24 months in primary markets. | – Grid interconnection queues worsen, not improve. <br> – Geothermal EGS developers deliver commercial‑scale power to at least two projects. <br> – Major data‑center REITs adjust site‑selection criteria to emphasize time‑to‑energize. | True | Winners: geothermal developers, power‑secured DC developers, flexible hyperscalers. Losers: grid‑dependent campus projects, shell‑only investors. |
| **Upside** | By mid‑2027, >5 100‑MW‑plus campuses with firm‑power siting are publicly committed, and transformer lead times exceed 36 months. Policy tailwinds (e.g., expedited geothermal permits) accelerate behind‑the‑meter generation. | – Geothermal drilling productivity improves rapidly, all‑in costs fall below $40/MWh for behind‑the‑meter PPAs. <br> – Hyperscalers begin paying premiums for power‑secured land options years before construction. <br> – Regulators treat data‑center load as a catalyst for clean firm power, streamlining permitting. | True (resolves early) | Winners accelerate: multiple geothermal developers become “AI infrastructure” plays, land‑option repricing happens in 2026‑2027. Losers face stranded asset write‑downs earlier. |
| **Downside** | Kill condition triggers: either fewer than 2 such campuses materialize by 2028‑12‑31, or transformer & interconnection delays normalize (e.g., domestic transformer production ramps, FERC Order 2023‑style reforms cut queue times to <18 months). Grid‑only solutions become economically viable again. | – Supply‑chain response halves transformer wait times by 2027. <br> – Interconnection reforms and new transmission corridors make grid‑connected projects timely. <br> – Behind‑the‑meter firm power hits cooling/water/local opposition hurdles that raise costs above grid‑PPA parity. | False | Winners invert: grid‑connected DC campuses in old hubs regain advantage. Geothermal developers tied to AI‑load lose bankability. Rent stays in traditional data‑center real estate. |

### Proposed New Nodes

- **`n-scenario-p1-base`** (kind: `scenario_branch`, confidence: hypothesis)  
  – Base assumptions: ≥2 firm‑power campuses by 2028‑12‑31; transformer delays ≥24 months; thesis forecast clause resolves True.  
- **`n-scenario-p1-upside`** (kind: `scenario_branch`, confidence: hypothesis)  
  – ≥5 campuses by mid‑2027; transformer delays ≥36 months; geothermal costs fall.  
- **`n-scenario-p1-downside`** (kind: `scenario_branch`, confidence: hypothesis)  
  – <2 campuses or transformer delays <18 months; thesis kill condition activated.

### Proposed Edges

| Edge ID | Source → Target | Relation | Confidence | Status |
|---------|-----------------|-----------|------------|--------|
| `e-scenario-p1-base→thesis` | `n-scenario-p1-base → n-thesis-p1` | `scenario_supports` | 0.85 (derived from board structure) | hypothesis |
| `e-scenario-p1-base→forecast` | `n-scenario-p1-base → n-forecast-clause-p1` | `scenario_resolves` | 0.85 | hypothesis |
| `e-scenario-p1-upside→constraint` | `n-scenario-p1-upside → n-constraint-p1` | `scenario_intensifies` | 0.7 | hypothesis |
| `e-scenario-p1-upside→winner` | `n-scenario-p1-upside → n-winner-geothermal-developers` | `scenario_accelerates` | 0.6 | hypothesis |
| `e-scenario-p1-downside→kill` | `n-scenario-p1-downside → n-kill-condition-p1` | `scenario_triggers` | 0.9 | hypothesis |
| `e-scenario-p1-downside→constraint` | `n-scenario-p1-downside → n-constraint-p1` | `scenario_weakens` | 0.7 | hypothesis |

### Evidence Needed (Verification Tasks)
- **[source_pack]** Primary source URLs for: transformer lead‑time indices (e.g., Power & Energy Report), FERC interconnection queue data, geothermal developer announcements, hyperscaler campus press releases.  
- **[lead]** Quarterly track of at least two major data‑center REITs’ site‑selection language regarding behind‑the‑meter power.  
- **[hypothesis]** Monitor for any legislation that would expedite HVAC/transformer manufacturing (e.g., Defense Production Act invocation).  
- **[refutation]** Watch for a substitute path: a large colocation deal where a new gas plant is built “at the fence” with grid backup, effectively bypassing the behind‑the‑meter constraint (would weaken the thesis without triggering the strict kill condition).

### Refutations & Next Actions
- **Refutation**: If transformer supply normalizes faster than consensus expects, the thesis becomes a temporary spike, not a structural shift. Verify industry capacity expansion timelines.
- **Next action**: Create verification task `u-unknown-p1-substitute-path` already exists; own agent A10 should map substitutes like on‑site nuclear SMRs, rapid grid‑interconnection reforms, and new transmission corridors that could bypass the bottleneck.

---

## P2: Physical AI’s bottleneck is certified deployment, not robot bodies.
**Thesis Node:** `n-thesis-p2-…`  
**Constraint:** Verified task data, sim‑to‑real validation, workcell commissioning, safety certification.  
**Kill Condition:** By end‑2028, humanoid/mobile manipulation deployments scale mainly through turnkey hardware with little separate pricing for task validation, commissioning software, or safety case tooling.  
**Resolution Date:** 2028-12-31

### Scenario Branches

| Branch | Description | Key Assumptions | Forecast Clause Result | Winner/Loser Intensity |
|--------|-------------|-----------------|------------------------|------------------------|
| **Base** | By end‑2028, at least two major automotive/logistics deployments publicly attribute scaling success to a simulation/task‑library/validation layer, and at least one large OEM or integrator sells commissioning software as a separate line item. Commissioning time reductions of ≥40% are claimed in media. | – NVIDIA Isaac/Cosmos ecosystem matures and gets referenced in customer rollouts. <br> – Safety certification tooling (e.g., TÜV, UL) begins to incorporate sim‑based evidence. <br> – Custom‑only integrators lose market share to reusable‑task‑library shops. | True | Winners: simulation ecosystems, integrators with reusable task libraries, standardized workcell owners. Losers: undifferentiated humanoid OEMs, custom‑only integrators. |
| **Upside** | By mid‑2028, more than five major deployments name validation/commissioning as the key enabler, and specialized “deployment‑as‑a‑service” startups raise capital at high valuations. Commissioning times drop below 50% of 2025 baselines. Robot OEMs separate hardware and deployment‑software pricing broadly. | – Sim‑to‑real gap closes faster than expected; tactile sensors and large‑scale task datasets accelerate. <br> – Automotive manufacturers publish ROI models in which commissioning labor is the primary cost, validating the deployment‑layer premium. <br> – Insurance carriers begin underwriting physical AI based on sim‑validated safety cases. | True (early resolution) | Winners capture significant value in deployment‑layer revenue; robot body commoditization accelerates. |
| **Downside** | By 2028, robot deployments still scale as turnkey hardware solutions; validation is done by the OEM for free as part of the sale; no separate line item for deployment software emerges. Alternatively, a substitute path—e.g., highly adaptive foundation models that can be deployed zero‑shot with minimal task‑specific commissioning—makes dedicated validation layers unnecessary. | – Robot OEMs absorb commissioning costs to win large deals, masking the bottleneck. <br> – “Generalist policy” models achieve reliable real‑world performance without per‑task validation, undermining the structural need for a deployment layer. <br> – Large integrators (e.g., Rockwell, Siemens) offer integrated turnkey solutions that include everything, so no separate margin pool appears. | False | Winners: turnkey OEMs, custom integrators. Losers: deployment‑layer‑only startups, validation‑platform plays. |

### Proposed New Nodes
- **`n-scenario-p2-base`** (hypothesis) – ≥2 deployment attribution events by 2028; separate line‑item commissioning software appears.
- **`n-scenario-p2-upside`** (hypothesis) – ≥5 deployments with validation attribution; separation of hardware/software pricing becomes standard.
- **`n-scenario-p2-downside`** (hypothesis) – Turnkey hardware dominates; no separate deployment pricing; substitute path (generalist policies) undermines constraint.

### Proposed Edges
| Edge ID | Source → Target | Relation | Confidence | Status |
|---------|-----------------|-----------|------------|--------|
| `e-scenario-p2-base→thesis` | `n-scenario-p2-base → n-thesis-p2` | `scenario_supports` | 0.85 | hypothesis |
| `e-scenario-p2-downside→kill` | `n-scenario-p2-downside → n-kill-condition-p2` | `scenario_triggers` | 0.9 | hypothesis |
| `e-scenario-p2-downside→substitute` | `n-scenario-p2-downside → n-substitute-generalist-policies` (needs creation) | `scenario_relies_on_substitute_path` | 0.6 | hypothesis |

### Evidence Needed
- [source_pack] Deployment‑case studies from automotive/logistics (e.g., BMW, DHL) that mention simulation or task validation. Track SI quotes about commissioning time reductions.
- [lead] Monitor NVIDIA Isaac/Cosmos press mentions in customer rollout announcements.
- [hypothesis] Track insurance industry guidance on robotics safety certification using simulation.
- [refutation] Existence of a zero‑shot generalist robot policy that demonstrably works in multiple factories without per‑task validation.

### Refutations & Next Actions
- **Refutation**: If no separate pricing layer appears because it is always absorbed by the system integrator in a turnkey contract, the thesis may be economically correct but not investable (the rent stays inside private integrator margins). Adjust forecast clause metric to detect “margin shifts
