# Findings

The atlas contains 6 forecast theses (P1–P6) with 116 nodes and 151 edges, but no “decision-grade source-verified” nodes exist and 6 open tasks per thesis gap remain for source packs and entity resolution.  
All load‑bearing facts (constraints, metrics, kill conditions, price channels, buyer segments, winners, losers) **trace only to the Pope board** (source artifact `n-source-research-pope-after-ai-2026-06-17-json-afabfe46`); no independent primary sources are attached.  
Named entities like “Rhodium”, “LBL”, “Fervo-style EGS”, “NVIDIA Isaac/Cosmos”, “IDTechEx”, “DOE”, “Google/Samsung/Apple/Meta”, etc. are not yet resolved to canonical companies, laboratories, or instruments.

The 12 tasks given to this role (6 `source_pack` + 6 `entity_resolution`) require:

- Attaching primary/official source URLs and dates to every load‑bearing node;
- Resolving all named entities to canonical organisations, products, or projects.

Until these gaps are closed, the entire world graph remains **derived from a single board** and cannot be considered source‑verified for decision‑grade use.

---

# Proposed Nodes

All nodes below are **hypothesis** until source‑verified.

## Canonical Entity Nodes (entity_resolution)

1. **`n-entity-rhodium-group`**  
   - label: “Rhodium Group”  
   - kind: organization  
   - referenced by: thesis P1 (LBL/Rhodium data on DC electricity demand)  
   - confidence: 0.85 (hypothesis)  

2. **`n-entity-lawrence-berkeley-national-lab`**  
   - label: “Lawrence Berkeley National Laboratory”  
   - kind: research_lab  
   - referenced by: thesis P1 (LBL projections)  

3. **`n-entity-pv-magazine`**  
   - label: “pv magazine”  
   - kind: publication  
   - referenced by: thesis P1 (May 2026 report on transformer wait times)  

4. **`n-entity-fervo-energy`**  
   - label: “Fervo Energy” (EGS geothermal developer)  
   - kind: company  
   - referenced by: thesis P1 (Fervo‑style EGS)  

5. **`n-entity-nvidia`**  
   - label: “NVIDIA Corporation”  
   - kind: company  
   - referenced by: thesis P2 (Isaac, Cosmos, GR00T)  

6. **`n-entity-idtechex`**  
   - label: “IDTechEx”  
   - kind: research_firm  
   - referenced by: thesis P2 (humanoid materials/robotics coverage)  

7. **`n-entity-us-department-of-energy`**  
   - label: “U.S. Department of Energy”  
   - kind: government_agency  
   - referenced by: thesis P3 (DOE testbed awards)  

8. **`n-entity-alphabet`**  
   - label: “Alphabet Inc. (Google)”  
   - kind: company  
   - referenced by: thesis P4 (AI feature launch)  

9. **`n-entity-samsung-electronics`**  
   - label: “Samsung Electronics”  
   - kind: company  

10. **`n-entity-apple-inc`**  
    - label: “Apple Inc.”  
    - kind: company  

11. **`n-entity-meta-platforms`**  
    - label: “Meta Platforms, Inc.”  
    - kind: company  

*All confidence ratings are hypothesis (~0.7–0.9) pending source verification.*

## Source Attachment Nodes (source_pack)

For each load‑bearing node that currently lacks a direct source, we propose a **source citation node** containing the URL and publication date. The following are key load‑bearing nodes requiring primary sources:

- `n-constraint-contiguous-land-fiber-proximity…` (P1 constraint)  
- `n-metric-track-hyperscaler…` (P1 metric)  
- `n-kill-condition-kill-if…` (P1 kill)  
- `n-price-channel-transformer…` (P1 price channel)  
- `n-observable-a-hyperscaler…` (P1 observable)  
- Analogous nodes for P2–P6.

Each such source node will have kind `source_attachment` and properties `source_url`, `source_date`, `quote_or_field`.  
For illustration, one prototype node:

- **`n-source-rhodium-us-dc-electricity-demand-projection`**  
  label: “Rhodium Group / LBL projection of US data center electricity demand to 7-12% by 2028”  
  kind: source_attachment  
  required_properties: `source_url`, `source_date` (publication date pre‑2026‑06‑17), `quote`, `trust_rationale`  
  confidence: hypothesis (source not yet located)

We do **not** populate the URLs because they are unknown; the task remains open.

---

# Proposed Edges

All edges are **hypothesis** (derived from board text without independent verification) unless marked with a pre‑existing `verification_status` from the board.

## Entity Resolution Edges

Link each thesis or constraint node to the canonical entity it names:

- `n-thesis-p1-…` → `n-entity-rhodium-group` (rel: `cites_data_from`)  
- `n-thesis-p1-…` → `n-entity-lawrence-berkeley-national-lab`  
- `n-thesis-p1-…` → `n-entity-pv-magazine`  
- `n-constraint-contiguous-land…` → `n-entity-fervo-energy` (rel: `exemplified_by`)  
- `n-thesis-p2-…` → `n-entity-nvidia`  
- `n-thesis-p2-…` → `n-entity-idtechex`  
- `n-thesis-p3-…` → `n-entity-us-department-of-energy`  
- `n-thesis-p4-…` → `n-entity-alphabet`, `n-entity-samsung-electronics`, `n-entity-apple-inc`, `n-entity-meta-platforms`

Rationale: The board mentions these entities by name or clear reference; making them explicit enables source‑verification.

## Source Attachment Edges

For each load‑bearing node, create an edge from the new source_attachment node back to the original node with relation `provides_primary_source_for`. Example:

- `n-source-rhodium-us-dc-electricity-demand-projection` → `n-thesis-p1-…` (rel: `provides_primary_source_for`)

Similarly for the metric, constraint, observable, etc. This will satisfy the requirement “Attach primary/official source URLs and publication dates to every load‑bearing node.”

---

# Evidence Needed

For each `entity_resolution` task (P1–P6), the following concrete evidence must be gathered:

- For every entity node:  
  official website, publicly available report, press release, or authoritative database entry that **unambiguously names** the company/lab/agency, along with a date and a brief quote or field showing why the entity matches the board’s reference.  
- Trust rationale: why the source is considered the canonical source (e.g., official company site, verified industry database).

For each `source_pack` task, for every load‑bearing fact node:

- The exact document/product announcement that justifies the fact, with:  
  - `source_url` (link to the document)  
  - `source_date` (publication date, must be ≤ 2026-06-17)  
  - `quote_or_field` (exact sentence or data field that supports the fact)  
  - `trust_rationale` (why this source is reliable)  

The atlas already provides the `required_evidence` specification; the tasks remain open until these are populated.

---

# Refutations

The entire set of proposed entity nodes and source edges is hypothetical.  
**Refutation risk**: if the board authors misremembered a source, used an ambiguous reference (e.g., “LBL” could mean Lawrence Livermore instead of Berkeley), or a later event invalidated the source’s claim, the attached source would not constitute **decision‑grade** verification.  
Without direct source verification, any downstream wagering or policy action based on these nodes is **non‑falsifiable** in the Vaticinus sense.

The kill conditions and metrics remain observation protocols; they are not verified until someone confirms that the proposed watch signals can be tracked against the actual named entities.

---

# Next Actions

1. **Resolve Entities (A01)**  
   - For each thesis P1–P6, locate the official, canonical entity that matches the board’s description.  
   - Create the canonical entity node (`n-entity-…`) with label and verified kind.  
   - Mark the entity node as `source_verified` only when a primary source (e.g., homepage, registry) confirms its identity.

2. **Attach Primary Sources (A01)**  
   - For every load‑bearing node (constraint, metric, kill, price channel, observable, winner/loser, etc.), find the exact public document that states the fact.  
   - Create a `source_attachment` node with `source_url`, `source_date`, `quote_or_field`, and `trust_rationale`.  
   - Link it to the original node via `provides_primary_source_for`.  
   - Mark the original node’s `verification_status` as `source_verified` once the attachment is complete and checked.

3. **Re‑evaluate Edge Confidences**  
   Once sources are attached, adjust the `confidence` values on the existing edges (many are low 0.55–0.8) based on the authority of the source.

4. **Schedule Verification Cadence**  
   For each watchlist item, confirm the monitoring cadence (monthly) by linking to the actual feed/tracker; if none exists, propose a method (e.g., Google Alerts, RSS) and create a `tracking_method` node.

5. **Repeat for Theses P3–P6**  
   The data for P3–P6 is less developed in the edge samples; after completing P1–P2, repeat source_pack and entity_resolution for the remaining theses.

---

**All proposed nodes and edges remain hypotheses until the evidence is gathered and attached.**
