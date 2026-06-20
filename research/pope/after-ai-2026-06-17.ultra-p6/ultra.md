# Pope Ultra - After AI: where the constraint moves when intelligence leaves the screen

- Source board: `research/pope/after-ai-2026-06-17.json`
- Generated: 2026-06-17T20:04:52+00:00
- Run mode: `deterministic_ultra_scaffold`

## Truth Rules

- Do not invent named permits, people, contacts, projects, companies, labs, or amounts.
- Unknowns become tasks. Leads become decision-grade only after source verification.
- Primary sources outrank polished secondary summaries.
- Contact paths must be public business routes from official sources; never infer emails.
- A money recommendation needs amount range, unit-cost basis, trigger, next tranche trigger, downside, and kill condition.

## P6 - Agentic AI's scarce layer becomes authority, auditability, and rollback.

- Domain: enterprise AI / security / governance
- Vision P: 74%
- Clause P: 48%
- Resolves: 2028-06-30
- Metric: Track enterprise RFPs requiring agent audit logs, least-privilege controls, rollback, or insurance support; track public agent incidents; track vendors selling action-governance rather than generic model monitoring.
- Kill: Kill if by mid-2028 large enterprises widely deploy multi-step agents with real system authority using mostly prompt-level guardrails and generic logging, without a separate action-governance budget.

### Decision Core

- Exposed: CISOs, CIOs, compliance leaders, insurers, enterprise software buyers, agent platform vendors, and legal teams.
- Action now: Design agent deployments around authority boundaries first: least privilege, approval ladders, audit logs, rollback, and evidence packets for regulated workflows.
- Decision changed: Enterprise AI procurement, security architecture, insurance underwriting, compliance budgets, and whether agents are allowed to touch systems of record.
- ROI logic: A controlled agent can be deployed into high-value workflows that an uncontrolled agent cannot enter. The upside is adoption; the avoided loss is incident cost, regulatory exposure, and procurement blockage.
- Watch: A Fortune 500 RFP, insurance policy, or regulator explicitly requiring agent action logs, approval chains, and rollback for production deployment.

### Layers

- **Claim integrity**: What exactly is scored, and what would kill it? -> Original dated clause, probability, metric, resolution, and kill condition preserved.
- **Decision surface**: Which decision changes if the claim is true? -> A named capex, procurement, siting, research, hiring, policy, portfolio, or partnership decision.
- **Named world map**: Which permits, projects, companies, labs, people, and contact paths exist in the real world? -> A source-verified map of named objects, not categories.
- **Verification ledger**: What is primary-verified, what is only a lead, and what is refuted? -> Status, source tier, URL, retrieved date, quote/span, and open questions for each named record.
- **Action economics**: How much money goes into what operation, under which trigger and kill condition? -> A trancheable amount/action memo with ROI logic, reversibility, and owner.
- **Outreach**: Who should be contacted and what answer would change the decision? -> Public contact paths, question scripts, and evidence attachments.
- **Monitoring**: How does the dossier stay alive? -> Cadence, watch signal, escalation threshold, and stop condition.

### Action Axes

- **capital**: What capital allocation changes before consensus catches up? -> Amount range, instrument or asset, timing trigger, downside, and benchmark.
- **capex_siting**: Which physical site, asset, equipment, or capacity should be reserved or avoided? -> Design agent deployments around authority boundaries first: least privilege, approval ladders, audit logs, rollback, and evidence packets for regulated workflows.
- **procurement**: Which scarce input should be contracted, dual-sourced, or monitored for lead-time blowout? -> Supplier list, lead-time source, quote/procurement evidence, and fallback.
- **research**: Which lab, method, or technical bottleneck should be funded or partnered with? -> Named labs, grants, PIs, papers, patents, and contact questions.
- **talent**: Which skill becomes scarce if the thesis is true? -> Role taxonomy, training path, hiring targets, salary/availability signals.
- **policy**: Which regulator, permit, standard, or public rule gates the outcome? -> Named docket/permit/standard with status and next hearing or deadline.
- **founder_product**: What company or tool should exist because this bottleneck appears? -> Pain owner, workflow, first buyer, wedge feature, and proof data.
- **monitoring**: Which signal changes the view fastest? -> Track enterprise RFPs requiring agent audit logs, least-privilege controls, rollback, or insurance support; track public agent incidents; track vendors selling action-governance rather than generic model monitoring.

### Execution Packets

#### Permits, dockets, queues, and local approvals

- Kind: `permit_docket`
- Truth floor: `primary_verified`
- Why: The forecast only becomes actionable when the legal/permission path is named and current.
- Deliverable: A table of named permits/dockets with current status and next check date.
- Promotion rule: Do not promote this packet above 'primary_verified' until every named record has source_url, retrieved_at, quote_or_table_row, and a non-empty field set matching required_fields.
- Seed queries:
  - `"Identity, permissioning, tool-access control, audit trails, reversible execution, human authorization" "enterprise AI / security / governance" permit docket`
  - `"Agentic AI's scarce layer becomes authority, auditability, and rollback" permit OR docket OR interconnection`
  - `"Design agent deployments around authority boundaries first" site permit`
  - `"Track enterprise RFPs requiring agent audit logs, least-privilege controls, rollback, or insurance" "queue" "status"`
- Source priority:
  - county or municipal planning agenda
  - state public utility commission docket
  - FERC eLibrary or federal docket
  - ISO/RTO interconnection queue
  - EPA, state environmental, water, or air permit database
  - company filing that names the permit or project
- Required fields:
  - `permit_or_docket_name`
  - `jurisdiction`
  - `applicant`
  - `project_or_asset`
  - `status`
  - `filed_date`
  - `next_hearing_or_deadline`
  - `capacity_or_scope`
  - `source_url`
  - `quote_or_table_row`

#### Named projects, assets, sites, and physical bottlenecks

- Kind: `project_asset`
- Truth floor: `primary_verified`
- Why: Buyers need named assets, not a category. The asset map says what can actually be bought, reserved, funded, or avoided.
- Deliverable: A ranked map of named projects/assets with why each matters to the constraint.
- Promotion rule: Do not promote this packet above 'primary_verified' until every named record has source_url, retrieved_at, quote_or_table_row, and a non-empty field set matching required_fields.
- Seed queries:
  - `"Identity, permissioning, tool-access control, audit trails, reversible execution, human authorization" "enterprise AI / security / governance" project`
  - `"Agent security, identity, execution controls, audit logs, insurance, and governance middleware become the enterprise" developer site project`
  - `"Rent lands in identity/security vendors, agent orchestration platforms with strong execution controls" project capacity timeline`
  - `"A Fortune 500 RFP, insurance policy, or regulator explicitly requiring agent action" announced project`
- Source priority:
  - official project page
  - developer announcement
  - permit filing
  - utility interconnection queue
  - investor presentation
  - local planning record
- Required fields:
  - `project_name`
  - `asset_owner`
  - `location`
  - `capacity_or_volume`
  - `timeline`
  - `constraint_link`
  - `commercial_status`
  - `source_url`
  - `quote_or_table_row`

#### Companies, suppliers, buyers, and counterparties

- Kind: `company_supplier`
- Truth floor: `primary_verified`
- Why: The forecast turns commercial when it names who can capture, relieve, or suffer the constraint.
- Deliverable: A counterparty table with role, proof, and public contact path.
- Promotion rule: Do not promote this packet above 'primary_verified' until every named record has source_url, retrieved_at, quote_or_table_row, and a non-empty field set matching required_fields.
- Seed queries:
  - `"Identity, permissioning, tool-access control, audit trails, reversible execution, human authorization" supplier company`
  - `"Agent security, identity, execution controls, audit logs, insurance, and governance middleware become the enterprise" "enterprise AI / security / governance" company`
  - `"Rent lands in identity/security vendors, agent orchestration platforms with strong execution controls" "customer" OR "supplier"`
  - `"CISOs, CIOs, compliance leaders, insurers, enterprise software buyers, agent platform" "Identity, permissioning, tool-access control, audit trails, reversible execution, human authorization"`
- Source priority:
  - official company page
  - 10-K, S-1, 8-K, annual report, or statutory filing
  - procurement portal
  - customer announcement
  - trade association member page
- Required fields:
  - `organization`
  - `role`
  - `evidence_of_role`
  - `product_or_asset`
  - `buyer_or_supplier_link`
  - `public_contact_path`
  - `source_url`
  - `quote_or_table_row`

#### Universities, labs, grants, and research groups

- Kind: `research_lab`
- Truth floor: `primary_verified`
- Why: Some constraints are solved first in labs. This packet finds who is already doing the hard part.
- Deliverable: A lab map with named people or groups and what question to ask them.
- Promotion rule: Do not promote this packet above 'primary_verified' until every named record has source_url, retrieved_at, quote_or_table_row, and a non-empty field set matching required_fields.
- Seed queries:
  - `"Identity, permissioning, tool-access control, audit trails, reversible execution, human authorization" university lab`
  - `"Track enterprise RFPs requiring agent audit logs, least-privilege controls, rollback, or insurance" "NSF" OR "DOE" OR "NIH" grant`
  - `"enterprise AI / security / governance" "Identity, permissioning, tool-access control, audit trails, reversible execution, human authorization" principal investigator`
  - `"The next constraint becomes standard evidence formats for agent actions and cross-vendor" research group`
- Source priority:
  - university lab page
  - grant award database
  - OpenAlex, Crossref, PubMed, arXiv, or patent record
  - conference program
  - technology-transfer page
- Required fields:
  - `institution`
  - `lab_or_center`
  - `principal_investigator_or_team`
  - `research_topic`
  - `grant_or_publication`
  - `evidence_span`
  - `public_contact_path`
  - `source_url`

#### People and public contact paths

- Kind: `person_contact`
- Truth floor: `contact_confirmed`
- Why: Agentic work needs who to call, but contact data must be public and verified.
- Deliverable: A public-contact task list with question scripts, not guessed emails.
- Promotion rule: Do not promote this packet above 'contact_confirmed' until every named record has source_url, retrieved_at, quote_or_table_row, and a non-empty field set matching required_fields.
- Seed queries:
  - `"Identity, permissioning, tool-access control, audit trails, reversible execution, human authorization" "enterprise AI / security / governance" "vice president" OR director`
  - `"Agentic AI's scarce layer becomes authority, auditability, and rollback" "speaker" OR "principal investigator"`
  - `"CISOs, CIOs, compliance leaders, insurers, enterprise software buyers, agent platform" "Design agent deployments around authority boundaries first" contact`
  - `"Track enterprise RFPs requiring agent audit logs, least-privilege controls, rollback, or insurance" regulator contact OR staff`
- Source priority:
  - official leadership page
  - public agency staff directory
  - university directory
  - permit filing contact page
  - conference speaker bio
  - company investor-relations or media contact page
- Required fields:
  - `person_or_role`
  - `organization`
  - `why_relevant`
  - `authority_or_expertise`
  - `public_contact_path`
  - `contact_source_url`
  - `do_not_guess_email`

#### Capital, procurement, and operating action

- Kind: `capital_operation`
- Truth floor: `primary_verified`
- Why: This is the bridge from interesting forecast to 'put this much money into this operation'.
- Deliverable: A trancheable action memo with amount, trigger, owner, ROI logic, and stop condition.
- Promotion rule: Do not promote this packet above 'primary_verified' until every named record has source_url, retrieved_at, quote_or_table_row, and a non-empty field set matching required_fields.
- Seed queries:
  - `"Identity, permissioning, tool-access control, audit trails, reversible execution, human authorization" cost per MW OR capex OR contract`
  - `"Design agent deployments around authority boundaries first" budget procurement`
  - `"Enterprise AI procurement, security architecture, insurance underwriting, compliance budgets, and" capex amount`
  - `"Agent security budgets, identity-control spend, audit-log infrastructure, and cyber insurance language should" price contract premium`
- Source priority:
  - vendor quote or rate card
  - filing with capex or contract data
  - public procurement award
  - project finance document
  - market price series
  - buyer-provided internal number
- Required fields:
  - `action`
  - `amount_range`
  - `unit_cost_basis`
  - `counterparty_or_asset`
  - `first_tranche_trigger`
  - `next_tranche_trigger`
  - `expected_roi_or_loss_avoided`
  - `reversibility`
  - `kill_condition`
  - `owner`
  - `source_url`

#### Watch signals and kill checks

- Kind: `watch_signal`
- Truth floor: `primary_verified`
- Why: A forecast without monitoring is a memo. Ultra makes it a live operating system.
- Deliverable: A monitoring table with cadence, threshold, and escalation rule.
- Promotion rule: Do not promote this packet above 'primary_verified' until every named record has source_url, retrieved_at, quote_or_table_row, and a non-empty field set matching required_fields.
- Seed queries:
  - `"Track enterprise RFPs requiring agent audit logs, least-privilege controls, rollback, or insurance" data source`
  - `"Kill if by mid-2028 large enterprises widely deploy multi-step agents with real" evidence`
  - `"A Fortune 500 RFP, insurance policy, or regulator explicitly requiring agent action" source`
  - `"The next constraint becomes standard evidence formats for agent actions and cross-vendor" watch signal`
- Source priority:
  - official time series
  - permit docket updates
  - interconnection queue
  - filing feed
  - grant/publication/patent feed
  - price series
- Required fields:
  - `signal`
  - `source`
  - `cadence`
  - `threshold`
  - `owner`
  - `escalation_rule`
  - `kill_or_premise_void`
  - `source_url`

### Agent Brief

- Start from P6; do not alter its scored probability, resolution date, metric, or kill condition.
- Promote named facts only when they are source-verified; otherwise keep them as leads or tasks.
- Prefer primary sources: permits, dockets, filings, official project pages, grant records, regulator pages, and procurement portals.
- For people and contacts, use official public business contact paths only. Never infer emails.
- For each action, produce amount range, funded operation, trigger, next tranche trigger, reversibility, ROI/loss logic, owner, and kill condition.
- If evidence contradicts the thesis, mark the relevant record refuted and surface it before polishing the memo.
