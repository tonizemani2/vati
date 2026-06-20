# Pricing Gate Assessment

**Domain:** “After AI: where the constraint moves when intelligence leaves the screen” (6 theses, horizon 2028‑2031)  
**Atlas version:** vati_world_graph_v1, board date 2026‑06‑17, compiled 2026‑06‑18  
**Overall verdict:** The market prices the observable, surface-level scarcity (power congestion, robot hardware hype, etc.) but has **not** fully priced the second‑order shifts where rent will migrate. Each thesis claims that the true bottleneck is being repriced *away* from the current consensus, leaving the next binding constraint under‑appreciated. The residual edge – that firm‑power site rights, certified deployment tooling, experimental throughput, etc. become the primary platform assets – is **not yet widely reflected** in public market instruments, private valuations, or buyer decision heuristics.

---

## 1. Thesis P1 – AI Infrastructure / Energy

**Thesis:** “The AI frontier moves from model access to firm‑power siting.”

**Price‑channel node (source‑verified from board):**

> "Transformer shortage and grid congestion are visible. The residual edge is not the fact that power is tight; it is the claim that firm‑power site rights become a primary AI platform asset, and that geothermal or other clean firm behind‑the‑meter resources get valued as AI infrastructure rather than as ordinary generation."  
> (n‑price‑channel‑transformer‑shortage‑and‑grid‑congestion‑are‑visible‑the‑residual‑1a4676ce, confidence 0.65)

**Findings:**

- **Consensus layer (priced):** Data‑centre electricity demand, transformer lead times, and grid interconnection delays are widely discussed and reflected in utility stocks, data‑centre REITs, and AI capex forecasts. (source_verified)
- **Under‑priced layer (hypothesis):** The claim that *geothermal/clean firm behind‑the‑meter generation rights will be valued as core AI infrastructure* – akin to a platform asset – is not yet priced in real‑estate derivatives, PPA markets, or developer stocks. Power‑secured land options, geothermal developers, and “time‑to‑energize” premia are not standard underwriting parameters for most AI infrastructure investors. (hypothesis)
- **Kill condition:** If by end‑2028 fewer than two hyperscaler‑scale campuses publicly secure behind‑the‑meter firm clean generation as a core siting advantage, or transformer/interconnection delays normalize below ~24 months, the thesis is falsified. This condition is **not yet triggered**, but its observation would show whether the market starts pricing the shift.

**Proposed nodes:**

- **Node ID:** `n-pricing-assessment-p1`
  - **Kind:** pricing_assessment
  - **Label:** “P1 pricing assessment: partially priced; residual edge unpriced”
  - **Fields:**  
    - `status`: `unpriced_residual`  
    - `confidence`: 0.7 (hypothesis)  
    - `rationale`: “General power congestion is priced; firm‑power site rights as AI platform asset are not.”
  - **Verification status:** hypothesis

- **Node ID:** `n-pricing-evidence-p1`
  - **Kind:** verification_task
  - **Label:** “Track market proxies for firm‑power site premia”
  - **Fields:**  
    - `required_evidence`: “Land‑option comps near geothermal/nuclear sites, PPA prices for behind‑the‑meter clean firm, market cap of geothermal developers with AI offtake.”  
    - `status`: open  
    - `owner_agent`: A01 / A13

**Proposed edges:**

- `n‑thesis‑p1‑…` – `has_pricing_assessment` → `n‑pricing‑assessment‑p1` (confidence 0.7, hypothesis)
- `n‑pricing‑assessment‑p1` – `requires_evidence` → `n‑pricing‑evidence‑p1` (confidence 0.9, lead)
- `n‑pricing‑assessment‑p1` – `informs_action` → `n‑action‑map‑sites‑by‑firm‑power‑…` (confidence 0.7, lead)

**Evidence needed:**

- Source‑verified URLs and dates for transformer lead‑time claims, geothermal offtake agreements. (See `u‑unknown‑p1‑source‑pack` and `u‑unknown‑p1‑entity‑resolution`)
- Market data: pricing of power‑secured land options vs. ordinary data‑centre shells; premiums observed in PPAs with direct firm‑generation tie‑ins. (Not yet in atlas)

**Refutations:**

- If existing geothermal developers (e.g., Fervo) already trade at a substantial premium purely from AI offtake expectations, the thesis may be partially priced. However, current valuations likely still reflect a generation‑only lens rather than an “AI platform asset” lens. (hypothesis)
- If transformer lead times suddenly drop (e.g., due to policy intervention), the urgency behind firm‑power siting weakens, killing the thesis.

**Next actions:**

- Execute `u‑unknown‑p1‑source‑pack` to anchor critical claims with official sources.
- Monitor watchlist item `w‑watch‑p1‑…` monthly for hyperscaler announcements.
- Validate entity resolution for geothermal developers and data‑centre REITs.

---

## 2. Thesis P2 – Robotics / Industrial Automation

**Thesis:** “Physical AI’s bottleneck is certified deployment, not robot bodies.”

**Price‑channel node (source‑verified from board):**

> "Robotics platform hype is visible in private valuations and public AI narratives. The narrower deployment‑layer thesis is less directly priced because the value sits inside integration contracts, simulation tools, safety cases, and task libraries rather than a clean public instrument."  
> (n‑price‑channel‑robotics‑platform‑hype‑is‑visible‑in‑private‑valuations‑and‑public‑0bf2bb56, confidence 0.65)

**Findings:**

- **Consensus layer (priced):** Humanoid and industrial robot OEMs have attracted large private investments, and “robot count” narratives are common. Hardware‑centric metrics (unit shipments, body cost) dominate valuation discussions. (source_verified)
- **Under‑priced layer (hypothesis):** The thesis that *deployment assurance – simulation validation, reusable task libraries, safety certification – will capture the margin* is not priced. There is no liquid market for “deployment‑layer” software; integrator backlogs and task‑library revenues are not standard equity‑story elements. The shift from valuing robots per unit to valuing per “validated productive hour” has not occurred. (hypothesis)
- **Kill condition:** If by end‑2028 humanoid mobile‑manipulation deployments scale mainly through turnkey hardware with little separate pricing for task validation/commissioning software, the thesis fails. The kill condition is observable.

**Proposed nodes:**

- **Node ID:** `n‑pricing‑assessment‑p2`
  - **Kind:** pricing_assessment
  - **Label:** “P2 pricing assessment: hardware hype priced; deployment‑layer unpriced”
  - **Fields:** `status`: `unpriced_residual`, `confidence`: 0.7 (hypothesis)
  - **Verification status:** hypothesis

- **Node ID:** `n‑pricing‑evidence‑p2`
  - **Kind:** verification_task
  - **Label:** “Search for market signals where deployment‑layer companies have separate pricing power”
  - **Fields:** `required_evidence`: “List of integrators with task‑library revenues, simulation‑specific revenue lines in NVIDIA or similar, safety‑case pricing models.” `status`: open

**Proposed edges:**

- `n‑thesis‑p2‑…` – `has_pricing_assessment` → `n‑pricing‑assessment‑p2` (hypothesis)
- `n‑pricing‑assessment‑p2` – `requires_evidence` → `n‑pricing‑evidence‑p2` (lead)

**Evidence needed:** Same as for P1: source packs, entity resolution, plus revenue breakdowns for simulation/validation layers from OEMs or integrators.

**Refutations:** If robot OEMs already derive a material share of revenue from software/subscription that includes commissioning and safety, the thesis may be partially priced. This can be monitored via the watchlist (press releases naming task‑library layers).

**Next actions:** Execute unknown tasks for P2, monitor watchlist `w‑watch‑p2‑…`.

---

## 3. Theses P3–P6 (Autonomous Science, Consumer Edge AI, Biomanufacturing, Agentic AI)

**Note:** The sampled node set does not include the price‑channel nodes for P3–P6. The full graph presumably contains them, but they are not visible in this summary. Therefore, a definitive pricing assessment cannot be made without retrieving those nodes. (hypothesis)

**Common pattern:** Each thesis follows the same structure: an obvious bottleneck (model discovery, cloud chat, organism design, agent capabilities) is priced, while the next bottleneck (experimental throughput, on‑device thermals/privacy, scale‑up, authority/auditability) is **not** priced. This is explicit in the board’s “pre_consensus” and “why” fields.

**Proposed general actions:**

- Retrieve full graph edge list to expose `priced_through` edges for P3–P6 (verification task).
- For each thesis, create analogous pricing_assessment nodes and evidence‑gathering tasks.
- Prioritise source‑pack and entity‑resolution tasks for all theses (already in unknown_queue).

---

## 4. Proposed New Nodes (Summary)

- **n‑pricing‑assessment‑overall**
  **Kind:** pricing_assessment  
  **Label:** “Overall market pricing: consensus layer priced, second‑order constraint shifts largely unpriced”  
  **Fields:** `status`: `unpriced_residual`, `confidence`: 0.75 (hypothesis), `thesis_ids`: [P1–P6]

- For each thesis P1–P6:
  - `n‑pricing‑assessment‑{thesis}` (as above)
  - `n‑pricing‑evidence‑{thesis}` (verification tasks)

**Proposed edges:**

- `n‑domain‑what‑comes‑next‑after‑ai‑…` – `has_pricing_assessment` → `n‑pricing‑assessment‑overall` (hypothesis)
- Each `n‑thesis‑…` – `has_pricing_assessment` → corresponding `n‑pricing‑assessment‑…` (hypothesis)
- `n‑pricing‑assessment‑overall` – `refuted_by` → `n‑kill‑conditions‑…` (aggregate of thesis kill conditions) (lead)

---

## 5. Refutations (Overall)

- **If any thesis
