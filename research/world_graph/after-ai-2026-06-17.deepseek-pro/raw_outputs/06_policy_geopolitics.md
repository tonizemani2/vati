# Policy & Geopolitics Mapping – After AI Forecast Board

## Findings

The board’s six theses describe shifts in binding constraints. Each thesis intersects with specific laws, permits, trade controls, regulators, and state chokepoints. The mapping below identifies plausible policy nodes that could accelerate, choke, or redirect the forecast outcomes. **All linkages are hypotheses** awaiting source verification.

### Per‑thesis summary

| Thesis | Core Policy/Geopolitics Touchpoints |
|--------|------------------------------------|
| **P1** Firm‑power siting | FERC interconnection rules, BLM geothermal leasing, IRA tax credits, transformer supply‑chain controls, state‑level data‑center moratoria / incentives |
| **P2** Physical AI certified deployment | Robot safety standards (ISO, OSHA, EU Machinery Regulation), export controls on simulation hardware |
| **P3** Autonomous science throughput | DOE national‑lab funding, export controls on lab equipment, FDA/EPA regulatory pathways |
| **P4** Consumer AI edge devices | Privacy law (GDPR, CCPA), chip export restrictions, FCC/FTB device certification, battery safety regulations |
| **P5** Biomanufacturing scale‑up | FDA/USDA bioproduct regulation, EPA TSCA, biosecurity oversight, export controls on fermentation equipment |
| **P6** Agentic AI governance | EU AI Act, US AI executive orders, FTC/SEC enforcement, legal duty for audit trails and rollback |

---

## Proposed Nodes (policy/regulatory)

Marked as **hypothesis** unless noted.  
`confidence` reflects lead strength from board text; higher if a known regulation is referenced.

```json
[
  {
    "id": "n-policy-ferc-interconnection-reforms",
    "kind": "policy",
    "label": "FERC interconnection reforms (Order 2023, future regional compliance)",
    "domain": "energy regulation",
    "status": "hypothesis",
    "confidence": 0.6,
    "note": "Could relieve grid queue delays, weakening the behind‑the‑meter advantage."
  },
  {
    "id": "n-permit-blm-geothermal-leasing",
    "kind": "permit",
    "label": "Bureau of Land Management geothermal leasing (EGS) on federal land",
    "domain": "energy / land-use",
    "status": "hypothesis",
    "confidence": 0.7,
    "note": "Directly gates firm‑power site availability for geothermal winners."
  },
  {
    "id": "n-policy-ira-clean-energy-credits",
    "kind": "policy",
    "label": "Inflation Reduction Act – ITC/PTC for geothermal, nuclear, and hydrogen",
    "domain": "tax / energy",
    "status": "hypothesis",
    "confidence": 0.7,
    "note": "Makes behind‑the‑meter projects more bankable; expiration or repeal would weaken the thesis."
  },
  {
    "id": "n-policy-state-dc-moratoria",
    "kind": "policy",
    "label": "State‑level data‑center moratoria and tax incentives (e.g., Virginia, Ohio, Texas)",
    "domain": "land-use / tax",
    "status": "hypothesis",
    "confidence": 0.6,
    "note": "Can block or accelerate grid‑dependent campuses, reinforcing the firm‑power siting advantage."
  },
  {
    "id": "n-trade-control-transformer-supply",
    "kind": "trade_control",
    "label": "US Section 232 tariffs or export controls on large power transformers",
    "domain": "trade / energy equipment",
    "status": "hypothesis",
    "confidence": 0.5,
    "note": "Extends transformer lead times, making behind‑the‑meter even more valuable."
  },
  {
    "id": "n-regulator-ferc",
    "kind": "regulator",
    "label": "Federal Energy Regulatory Commission (FERC)",
    "domain": "energy",
    "status": "hypothesis",
    "confidence": 0.8,
    "note": "Key decider of interconnection queue costs and speed."
  },
  {
    "id": "n-policy-iso-robot-safety",
    "kind": "policy",
    "label": "ISO 10218 / ISO/TS 15066 collaborative robot safety standards",
    "domain": "robotics / industrial safety",
    "status": "hypothesis",
    "confidence": 0.65,
    "note": "Safety certification is the bottleneck; standards dictate what must be validated."
  },
  {
    "id": "n-policy-eu-machinery-regulation",
    "kind": "policy",
    "label": "EU Machinery Regulation 2023/1230 (effective 2027) – mandatory third‑party conformity",
    "domain": "robotics / trade",
    "status": "hypothesis",
    "confidence": 0.6,
    "note": "Could create a regulatory chokepoint for robot deployment in Europe."
  },
  {
    "id": "n-policy-osha-robot-guidance",
    "kind": "policy",
    "label": "OSHA guidelines on industrial robot safety and AI‑enabled machinery",
    "domain": "workplace safety",
    "status": "hypothesis",
    "confidence": 0.5,
    "note": "US enforcement may lag, reducing the deployment‑assurance premium."
  },
  {
    "id": "n-trade-control-export-robot-sim",
    "kind": "trade_control",
    "label": "US EAR controls on high‑performance computing and simulation software for robotics",
    "domain": "trade / AI hardware",
    "status": "hypothesis",
    "confidence": 0.5,
    "note": "Could hinder simulation ecosystem winners if export restrictions tighten."
  },
  {
    "id": "n-policy-doe-national-lab-testbeds",
    "kind": "policy",
    "label": "DOE Office of Science / ARPA‑E funding and access to national lab facilities",
    "domain": "science / energy",
    "status": "hypothesis",
    "confidence": 0.6,
    "note": "Directly shapes experimental throughput constraint."
  },
  {
    "id": "n-policy-fda-cmc-for-ai-discovered",
    "
