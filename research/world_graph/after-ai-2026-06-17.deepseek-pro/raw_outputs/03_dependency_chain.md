# Dependency Chain Analysis: One Layer Below the Next Constraint

## Findings (Source‑Verified from Atlas)

The atlas identifies **six forecast theses**, each with a **binding constraint**, a **metric**, a **kill condition**, winners/losers, and a **“next constraint”** node.  
For every thesis, the next constraint is stated broadly – it aggregates multiple sub‑factors, each of which is a distinct value‑chain.  
These aggregated next constraints are the obvious next bottleneck, but the **underlying supply‑chain, regulatory, or skill dependencies** that determine whether those bottlenecks actually tighten or release are not yet mapped. This analysis traces those one layer deeper.

## Proposed Nodes (Hypotheses & Leads)

All new nodes are hypotheses unless explicitly flagged as `lead` (based on known industry structure). Confidence values are initial guesses.

---

### P1: AI Frontier Moves to Firm‑Power Siting

**Existing next constraint**: `n-constraint-the-next-constraint-moves-to-drilling-capacity-high-voltage-equipment-6742ca22`  
Proposed deeper nodes:

| ID | Label | Kind | Confidence | Status | Rationale |
|----|-------|------|------------|--------|-----------|
| `hyp‑p1‑rig‑supply` | Geothermal drilling rig manufacturing capacity (U.S. + global) | constraint | 0.5 (hypothesis) | | EGS and deep geothermal require specialised rigs; only a handful of manufacturers (e.g., Huisman, Bentec) produce them. Rig count is a hard ceiling on how fast new geothermal sites can be developed. |
| `hyp‑p1‑drill‑labor` | High‑skill drilling crews for deep geothermal | constraint | 0.5 (hypothesis) | | Geothermal drilling demands experienced crews; labour competition with oil & gas and mining can limit availability. |
| `hyp‑p1‑transformer‑supply` | Large power transformer manufacturing slots (345 kV+) | constraint | 0.55 (lead) | Lead: transformer lead times are widely reported to exceed 2‑3 years; the bottleneck is winding capacity and electrical steel. |
| `hyp‑p1‑switchgear‑supply` | Medium‑/high‑voltage switchgear assembly capacity | constraint | 0.45 (hypothesis) | | Switchgear fabs compete for the same skilled workforce and components as transformers. |
| `hyp‑p1‑water‑rights` | Aquifer depletion and water‑rights permitting in key states (AZ, NV, TX) | constraint | 0.5 (hypothesis) | | Data centres’ water demand for cooling faces increasing regulatory pushback; water rights can be harder to secure than power. |
| `hyp‑p1‑cooling‑ip` | Liquid/immersion cooling IP and vendor lock‑in | constraint | 0.4 (hypothesis) | | If next‑gen cooling is monopolised by a few vendors, technology licensing could slow site development. |

---

### P2: Physical AI Bottleneck Is Certified Deployment

**Existing next constraint**: `n-constraint-the-next-constraint-becomes-high-quality-real-world-task-data-tactile-762add0c`  
Proposed deeper nodes:

| ID | Label | Kind | Confidence | Status | Rationale |
|----|-------|------|------------|--------|-----------|
| `hyp‑p2‑tactile‑mems` | Tactile sensor MEMS fabrication capacity | constraint | 0.5 (lead) | Lead: Advanced tactile sensors (e.g., GelSight, Touchlab) rely on specialised MEMS; scaling production could be constrained by fab capacity for non‑CMOS devices. |
| `hyp‑p2‑safety‑agency` | Safety certification agency throughput (TÜV, UL, national labs) | constraint | 0.5 (hypothesis) | | The number of certifiable robot systems per year is limited by how many safety assessors exist; e‑mobility certification backlogs already suggest this pattern. |
| `hyp‑p2‑task‑data‑platforms` | Application‑specific task‑data collection platforms (e.g., Flexiv, Covariant) | constraint | 0.45 (hypothesis) | | High‑quality task data requires real‑world sites with instrumented environments; these act as scarce data factories. |
| `hyp‑p2‑field‑service‑training` | Field service technician training pipelines for physical AI | constraint | 0.5 (lead) | Lead: Uptime guarantees depend on a skilled service workforce; robot OEMs already report technician shortages. |

---

### P3–P6 (Abbreviated)

Analogous deep‑constraint proposals can be made for each thesis, e.g.:  
- **P3 (Autonomous science)**: wet‑lab robotics standardisation, automated assay calibration, LIMS integration  
- **P4 (Edge AI)**: 3‑nm/2‑nm on‑device NPU fab capacity, thermoelectric cooling innovation  
- **P5 (Bio‑manufacturing)**: single‑use bioreactor supply, CMO fermentation slots  
- **P6 (Agentic AI)**: IAM market consolidation, actuarial models for agent liability  

I will focus the detailed graph additions on P1 and P2, but a full dependency map would add analogous nodes for all theses.

## Proposed Edges

From existing “next constraint” nodes to the deeper nodes, using `depends_on` and `creates_demand_for` relationships.  
All edges are hypothesis unless noted.

### P1 edges

```
e-hyp-p1-next-rig-supply
  src: n-constraint-the-next-constraint-moves-to-drilling-capacity-high-voltage-equipment-6742ca22
  dst: hyp-p1-rig-supply
  rel: depends_on
  rationale: Drilling capacity is gated by rig manufacturing slots and rig count.
  confidence: 0.65 (lead)

e-hyp-p1-next-drill-labor
  src: n-constraint-the-next-constraint-moves-to-drilling-capacity-high-voltage-equipment-6742ca22
  dst: hyp-p1-drill-labor
  rel: depends_on
  rationale: Even with rigs, crew availability determines well completion speed.
  confidence: 0.65

e-hyp-p1-next-transformer-supply
  src: n-constraint-the-next-constraint-moves-to-drilling-capacity-high-voltage-equipment-6742ca22
  dst: hyp-p1-transformer-supply
  rel: depends_on
  rationale: “High‑voltage equipment” is primarily large‑format transformers.
  confidence: 0.7 (lead)

e-hyp-p1-next-switchgear-supply
  src: n-constraint-the-next-constraint-moves-to-drilling-capacity-high-voltage-equipment-6742ca22
  dst: hyp-p1-switchgear-supply
  rel: depends_on
  rationale: Switchgear is the companion bottleneck to transformers.
  confidence: 0.6

e-hyp-p1-next-water-rights
  src: n-constraint-the-next-constraint-moves-to-drilling-capacity-high-voltage-equipment-6742ca22
  dst: hyp-p1-water-rights
  rel: depends_on
  rationale: Water and cooling permits hinge on local water rights and aquifer stress.
  confidence: 0.6

e-hyp-p1-next-cooling-ip
  src: n-constraint-the-next-constraint-moves-to-drilling-capacity-high-voltage-equipment-6742ca22
  dst: hyp-p1-cooling-ip
  rel: depends_on
  rationale: Advanced cooling could itself become a patent‑thicket bottleneck.
  confidence: 0.45
```

### P2 edges

```
e-hyp-p2-next-tactile-mems
  src: n-constraint-the-next-constraint-becomes-high-quality-real-world-task-data-tactile-762add0c
  dst: hyp-p2-tactile-mems
  rel: depends_on
  rationale: Tactile sensing is hardware‑bound; MEMS fab capacity will be the ceiling.
  confidence: 0.55 (lead)

e-hyp-p2-next-safety-agency
  src: n-constraint-the-next-constraint-becomes-high-quality-real-world-task-data-tactile-762add0c
  dst: hyp-p2-safety-agency
  rel: depends_on
  rationale: Safety certification is a human‑supply‑limited process.
  confidence: 0.6

e-hyp-p2-next-task-data-platforms
  src: n-constraint-the-next-constraint-becomes-high-quality-real-world-task-data-tactile-762add0c
  dst: hyp-p2-task-data-platforms
  rel: depends_on
  rationale: Real‑world task data must be produced in operational environments; the number of instrumented sites limits data volume.
  confidence: 0.5

e-hyp-p2-next-field-service
  src: n-constraint-the-next-constraint-becomes-high-quality-real-world-task-data-tactile-762add0c
  dst: hyp-p2-field-service-training
  rel: depends_on
  rationale: Maintenance networks require trained people; training capacity is the deep bottleneck.
  confidence: 0.55 (lead)
```

## Evidence Needed

For each proposed node, specific verification data would confirm or refute the dependency weight:

| Hypothesis Node | Evidence Needed |
|----------------|-----------------|
| `hyp‑p1‑rig‑supply` | Annual geothermal rig deliveries, order backlogs, utilisation rates; reports from Fervo, Eavor, Baker Hughes |
| `hyp‑p1‑drill‑labor` | Wage inflation for geothermal drilling crews; cross‑hire activity from shale basins |
| `hyp‑p1‑transformer‑supply` | Lead‑time data from Hitachi Energy, Siemens, GE Vernova; copper and GOES (electrical steel) price/availability |
| `hyp‑p1‑switchgear‑supply` | Same as transformers; factory capacity expansion announcements |
| `hyp‑p1‑water‑rights` | USGS groundwater depletion maps; state‑level moratoria on new water rights (e.g., Arizona 2026 announcements) |
| `hyp‑p1‑cooling‑ip` | Patent filings on immersion/liquid cooling; litigation or licensing deals |
| `hyp‑p2‑tactile‑mems` | Fab capacity for piezoresistive/optical tactile sensors; SEMI equipment bookings for MEMS |
| `hyp‑p2‑safety‑agency` | Number of certified robot safety assessors (e.g., TÜV Rheinland Functional Safety engineers); backlog duration |
| `hyp‑p2‑task‑data‑platforms` | Number of deployed instrumented cells by Covariant, Flexiv, etc.; total task‑sample hours logged |
| `hyp‑p2‑field‑service‑training` | Enrollment data in robotics technician programmes; wage inflation for field service roles |

## Refutations (If the Deeper Constraints Are Not Binding)

- **Rig supply is not a constraint if** modular, surface‑deployed geothermal (e.g., closed‑loop systems) can bypass deep drilling within the forecast horizon. This would sever `e‑hyp‑p1‑next‑rig‑supply` and `e‑hyp‑p1‑next‑drill‑labor`.
- **Large transformer lead times revert** if manufacturers double winding capacity by 2027 – then the transformer‑supply node becomes irrelevant.
- **Water rights are not binding if** dry‑cooling or air‑cooling technology becomes standard for 50 MW+ campuses, decoupling data‑centre siting from water.
- **Tactile sensor MEMS capacity is bypassed** if vision‑only manipulation (without tactile) achieves required reliability for general tasks.
- **Safety agency throughput can be scaled** by adopting digital twin‑based virtual assessment, reducing dependency on human assessors.
- **Field service labour can be alleviated** by remote‑operation/tele‑service models that require fewer on‑site technicians.

## Next Actions

1. **Source pack updates** (Agent A01): Extend the existing unknown source‑pack tasks to include the evidence items listed above for the theses with open source‑packs (P1–P6). Prioritise transformer lead times, rig counts, MEMS fab announcements, and safety certifier headcounts.
2. **Substitute path analysis** (Agent A10): For each deeper constraint, map substitute technologies or policies that could dissolve the bottleneck before it becomes the main constraint.
3. **Scenario branches** (Agent A11): Add scenario branches that differ in the tightness of these deep constraints (e.g., “constrained rig supply” vs. “dry‑cooling breakthrough” for P1).
4. **Entity resolution** (Agent A01): Resolve entities like “Fervo‑style EGS operators”, “NVIDIA Isaac/Cosmos ecosystems” to actual legal entities, then link their supply‑chain dependencies to the new nodes.
5. **Watchlist cadence refinement**: The current monthly cadence is too coarse for fast‑moving supply‑chain signals (e
