## Findings

The atlas maps six scored forecast clauses (P1–P6) across AI infrastructure, robotics, autonomous science, edge AI, biomanufacturing, and agentic governance, each with a binding constraint, metric, kill condition, and winner/loser ecosystem. All nodes are derived from a single 2026‑06‑17 research board; none are source‑verified. The watchlist flags six early‑observable signals, but no primary sources are attached. Twenty‑four verification tasks remain open (source packs, substitute paths, scenario branches, entity resolution).

**Highest‑value unsettled nodes** – the winners, losers, and the named constraints – represent concrete organizations, technologies, and regulatory choke points that can be turned into permits, projects, and contacts. The atlas itself does not yet contain canonical company names, permit classes, or specific people. Converting these abstractions into actionable leads is the immediate task.

## Proposed Nodes

All proposed nodes are hypotheses or leads until primary‑source evidence is attached. Only source‑verified facts will be marked as such.

### P1: Firm‑power siting

| ID | Label | Kind | Mark |
|----|-------|------|------|
| n‑lead‑p1‑fervo‑energy | Fervo Energy | company | lead |
| n‑lead‑p1‑google‑dc‑firmpower | Google data‑center team seeking behind‑the‑meter geothermal PPAs | project | lead |
| n‑lead‑p1‑coreweave‑firmpower | CoreWeave campus announcements with direct power‑development partnerships | project | lead |
| n‑hypothesis‑p1‑permit‑class | The hard permit bottleneck combines: (a) FERC NVIS/cogen permits, (b) state water appropriation permits for geothermal reinjection, (c) county conditional‑use permits for large generator‑tied loads, (d) BLM land rights for geothermal development. | permit_class | hypothesis |

### P2: Certified deployment

| ID | Label | Kind | Mark |
|----|-------|------|------|
| n‑lead‑p2‑nvidia‑isaac‑lab | NVIDIA Isaac Lab / Cosmos validation platform | product | lead |
| n‑lead‑p2‑thinklogical‑maas | ThinkLogical (or similar) offering task‑library‑as‑a‑service for automotive final assembly | company | lead |
| n‑lead‑p2‑ul‑4600‑safety | UL 4600 autonomous system safety case standard | standard | lead |
| n‑hypothesis‑p2‑project‑type | A “certified deployment project” structure: OEM + integrator + insurer + site owner, with separate contract for task validation and uptime guarantee, analogous to performance‑based contracting in aerospace. | project_type | hypothesis |

### P3: Autonomous science

| ID | Label | Kind | Mark |
|----|-------|------|------|
| n‑lead‑p3‑doe‑testbeds | DOE Advanced Scientific Computing Research autonomous lab testbed awards (e.g., Argonne, ORNL) | project | lead |
| n‑lead‑p3‑recursion‑pharma | Recursion Pharmaceuticals autonomous wet‑lab expansion | company | lead |
| n‑hypothesis‑p3‑permit‑class | Key permits: CLIA/GLP lab certifications, DEA controlled‑substance registrations for automated synthesis, and institutional biosafety committee approvals for high‑throughput experimentation. | permit_class | hypothesis |

### P4: Edge AI

| ID | Label | Kind | Mark |
|----|-------|------|------|
| n‑lead‑p4‑apple‑ambient‑ai | Apple “Private Cloud Compute / on‑device AI” product that runs persistent local model with all‑day context | product | lead |
| n‑lead‑p4‑qualcomm‑npu | Qualcomm Snapdragon NPU roadmaps for billion‑parameter local models | technology | lead |
| n‑hypothesis‑p4‑project‑type | A “local‑AI developer kit” launched by a silicon or OEM vendor, providing APIs for on‑device agents with privacy‑preserving data stores. | project_type | hypothesis |

### P5: Biomanufacturing scale‑up

| ID | Label | Kind | Mark |
|----|-------|------|------|
| n‑lead‑p5‑lanzatech‑scale | LanzaTech pilot‑fermentation capacity and COGS milestones | project | lead |
| n‑lead‑p5‑ginkgo‑bioworks | Ginkgo Bioworks downstream process bottlenecks in its foundry | company | lead |
| n‑hypothesis‑p5‑permit‑class | Scale‑up permits: EPA TSCA/Biotechnology pre‑manufacture notices, FDA food‑safety filings for novel ingredients, USDA APHIS permits for engineered organisms in open‑system fermentation, and local air‑quality permits for large fermenters. | permit_class | hypothesis |

### P6: Agentic governance

| ID | Label | Kind | Mark |
|----|-------|------|------|
| n‑lead‑p6‑sap‑agent‑control | SAP “agent guardrails” module requiring action‑audit and rollback | product | lead |
| n‑lead‑p6‑cyber‑insurance‑requirement | Cyber‑insurance carriers requiring agent audit trails as a condition of coverage for autonomous IT operations | standard | lead |
| n‑hypothesis‑p6‑project‑type | A “least‑privilege agent middleware” project that provisions temporary credentials, logs each state‑change attempt, and supports reversible transactions, likely emerging from a cloud provider. | project_type | hypothesis |

## Proposed Edges

| Source | Relation | Target | Rationale | Confidence | Mark |
|--------|----------|--------|-----------|------------|------|
| n‑thesis‑p1‑the‑ai‑frontier‑... | exposes | n‑lead‑p1‑fervo‑energy | Fervo is a named‑style EGS operator explicitly mentioned in the rent‑path constraint. | 0.75 | hypothesis |
| n‑lead‑p1‑fervo‑energy | requires_permit | n‑hypothesis‑p1‑permit‑class | Geothermal developers need FERC, water, and land‑use permits to offer behind‑the‑meter firm power. | 0.70 | hypothesis |
| n‑thesis‑p2‑physical‑ai‑... | creates_winner | n‑lead‑p2‑nvidia‑isaac‑lab | The thesis names NVIDIA Isaac/Cosmos as a winner. | 0.55 (board) | lead |
| n‑lead‑p2‑nvidia‑isaac‑lab | implements_standard | n‑lead‑p2‑ul‑4600‑safety | Simulation validation must interface with safety case standards like UL 4600. | 0.60 | hypothesis |
| n‑thesis‑p6‑agentic‑ai‑... | creates_winner | n‑lead‑p6‑sap‑agent‑control | Enterprise vendors selling action‑governance tools would be winners. | 0.55 (board) | lead |

## Evidence Needed

1. **Source pack for P1**: Official press releases from hyperscalers (AWS, Google, Microsoft, Meta) that explicitly name behind‑the‑meter geothermal or firm clean power as a siting differentiator for a campus ≥100 MW. (Critical; existing watchlist signal unverified)
2. **Entity resolution**: Map “Fervo‑style EGS operators” to canonical entities: Fervo Energy, Sage Geosystems, Eavor, others. Retrieve funding rounds and project permits.
3. **Substitute path**: Identify grid‑scale transmission projects (e.g., SunZia, TransWest) or advanced nuclear SMRs that could nullify the behind‑the‑meter advantage.
4. **P2 source pack**: Public quarterly filings or investor days from major automation integrators (ABB, Rockwell, Siemens) showing separate revenue lines for “digital validation / simulation services.”
5. **P4 source pack**: Tech media reviews and teardowns of on‑device LLM performance (e.g., Apple Intelligence, Samsung Gauss) noting battery life and thermal throttling.
6. **Scenario branch for P6**: If NIST or ENISA releases a prescriptive agent audit standard by 2027, the thesis accelerates; if regulators accept generic prompt‑level logging, it dies.

## Refutations

- **P1**: If transformer lead times drop below 18 months and interconnection queues are cleared via FERC Order 2023 reforms, the firm‑power advantage shrinks.
- **P2**: If a humanoid OEM (e.g., Tesla Optimus) vertically integrates deployment‑layer tooling and prices it at zero to gain market share, then certified deployment becomes a bundled feature, not a separate scarce layer.
- **P3**: If large pharma companies build their own in‑house autonomous labs at scale, the bottleneck remains inside the buyer, not as a separate market.
- **P4**: Cloud‑side inference latency drops low enough (sub‑10 ms RTT) that always‑on local context loses its advantage.
- **P5**: If USD SWITCH or other policy shifts subsidize pilot capacity en masse, the capacity constraint eases.
- **P6**: If major enterprises accept prompt‑level guardrails and insurance markets do not demand separate action‑audit, the thesis fails.

## Next Actions

1. **Immediate (this week)**: Assign A01 to complete the source pack for P1 watchlist signal, searching for hyperscaler announcements since 2026‑01.
2. **Contact leads**: Reach out to Fervo Energy business development and Google data‑center energy team for a briefing on pending behind‑the‑meter projects. (Responsibility: operator with A10.)
3. **Monitor feeds**: Set up Google Alerts for “UL 4600 robot deployment”, “agent audit trail enterprise RFP”, and “autonomous lab DOE award” to capture the first factual nodes that can be source‑verified.
4. **Permit mapping**: Engage a FERC/water‑rights attorney to detail the exact permitting path for a 100 MW behind‑the‑meter geothermal‑data‑center campus in Nevada, capturing the timeline and cost as a verifiable constraint node.
5. **Scenario workshop**: Organize a one‑hour expert call with A11 to draft at least one base/upside/downside scenario for P1 and P2, using the leads above as anchors.
