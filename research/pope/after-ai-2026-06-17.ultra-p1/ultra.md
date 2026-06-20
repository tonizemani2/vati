# Pope Ultra - After AI: where the constraint moves when intelligence leaves the screen

- Source board: `research/pope/after-ai-2026-06-17.json`
- Generated: 2026-06-17T19:58:23+00:00
- Run mode: `deterministic_ultra_scaffold`

## Truth Rules

- Do not invent named permits, people, contacts, projects, companies, labs, or amounts.
- Unknowns become tasks. Leads become decision-grade only after source verification.
- Primary sources outrank polished secondary summaries.
- Contact paths must be public business routes from official sources; never infer emails.
- A money recommendation needs amount range, unit-cost basis, trigger, next tranche trigger, downside, and kill condition.

## P1 - The AI frontier moves from model access to firm-power siting.

- Domain: AI infrastructure / energy
- Vision P: 82%
- Clause P: 52%
- Resolves: 2028-12-31
- Metric: Track hyperscaler and data-center developer announcements that name on-site firm power, geothermal, or interconnection bypass as the reason for site selection; count 100 MW plus campuses with direct power-development partnerships; track transformer lead times and local moratoria.
- Kill: Kill if by end 2028 fewer than two hyperscaler-scale campuses publicly secure behind-the-meter firm clean generation as a core siting advantage, or if transformer and interconnection delays normalize below roughly 24 months in the main US AI data-center markets.

### Decision Core

- Exposed: Hyperscaler infrastructure teams, data-center developers, power developers, large AI labs with reserved compute needs, and investors underwriting AI infrastructure.
- Action now: Map sites by firm-power time-to-energize, not just land cost and fiber; secure options on campuses where geothermal, gas with carbon capture, nuclear restart, or other firm power can be contracted behind the meter.
- Decision changed: Data-center site selection, PPA strategy, power-development partnerships, capex phasing, and portfolio exposure to grid-dependent versus power-secured data-center assets.
- ROI logic: A site that energizes 12 to 24 months earlier can be worth more than a cheaper site with stranded shells and delayed transformers. The asymmetry is time: idle GPUs and delayed leases burn capital while power-secured campuses monetize demand.
- Watch: A hyperscaler or top data-center REIT announcing a 100 MW plus campus whose stated differentiator is behind-the-meter clean firm power rather than cheap land.

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
- **capex_siting**: Which physical site, asset, equipment, or capacity should be reserved or avoided? -> Map sites by firm-power time-to-energize, not just land cost and fiber; secure options on campuses where geothermal, gas with carbon capture, nuclear restart, or other firm power can be contracted behind the meter.
- **procurement**: Which scarce input should be contracted, dual-sourced, or monitored for lead-time blowout? -> Supplier list, lead-time source, quote/procurement evidence, and fallback.
- **research**: Which lab, method, or technical bottleneck should be funded or partnered with? -> Named labs, grants, PIs, papers, patents, and contact questions.
- **talent**: Which skill becomes scarce if the thesis is true? -> Role taxonomy, training path, hiring targets, salary/availability signals.
- **policy**: Which regulator, permit, standard, or public rule gates the outcome? -> Named docket/permit/standard with status and next hearing or deadline.
- **founder_product**: What company or tool should exist because this bottleneck appears? -> Pain owner, workflow, first buyer, wedge feature, and proof data.
- **monitoring**: Which signal changes the view fastest? -> Track hyperscaler and data-center developer announcements that name on-site firm power, geothermal, or interconnection bypass as the reason for site selection; count 100 MW plus campuses with direct power-development partnerships; track transformer lead times and local moratoria.

### Execution Packets

#### Permits, dockets, queues, and local approvals

- Kind: `permit_docket`
- Truth floor: `primary_verified`
- Why: The forecast only becomes actionable when the legal/permission path is named and current.
- Deliverable: A table of named permits/dockets with current status and next check date.
- Promotion rule: Do not promote this packet above 'primary_verified' until every named record has source_url, retrieved_at, quote_or_table_row, and a non-empty field set matching required_fields.
- Seed queries:
  - `"Contiguous land, fiber proximity, behind-the-meter firm generation rights, interconnection optionality" "AI infrastructure / energy" permit docket`
  - `"The AI frontier moves from model access to firm-power siting" permit OR docket OR interconnection`
  - `"Map sites by firm-power time-to-energize" site permit`
  - `"Track hyperscaler and data-center developer announcements that name on-site firm power, geothermal" "queue" "status"`
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
  - `"Contiguous land, fiber proximity, behind-the-meter firm generation rights, interconnection optionality" "AI infrastructure / energy" project`
  - `"Behind-the-meter firm power, geothermal-capable campuses, and data-center sites with power rights become strategic AI" developer site project`
  - `"Rent lands in developers and landowners with power-secured campuses, geothermal developers such" project capacity timeline`
  - `"A hyperscaler or top data-center REIT announcing a 100 MW plus campus" announced project`
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
  - `"Contiguous land, fiber proximity, behind-the-meter firm generation rights, interconnection optionality" supplier company`
  - `"Behind-the-meter firm power, geothermal-capable campuses, and data-center sites with power rights become strategic AI" "AI infrastructure / energy" company`
  - `"Rent lands in developers and landowners with power-secured campuses, geothermal developers such" "customer" OR "supplier"`
  - `"Hyperscaler infrastructure teams, data-center developers, power developers, large AI labs" "Contiguous land, fiber proximity, behind-the-meter firm generation rights, interconnection optionality"`
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
  - `"Contiguous land, fiber proximity, behind-the-meter firm generation rights, interconnection optionality" university lab`
  - `"Track hyperscaler and data-center developer announcements that name on-site firm power, geothermal" "NSF" OR "DOE" OR "NIH" grant`
  - `"AI infrastructure / energy" "Contiguous land, fiber proximity, behind-the-meter firm generation rights, interconnection optionality" principal investigator`
  - `"The next constraint moves to drilling capacity, high-voltage equipment, water and cooling" research group`
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
  - `"Contiguous land, fiber proximity, behind-the-meter firm generation rights, interconnection optionality" "AI infrastructure / energy" "vice president" OR director`
  - `"The AI frontier moves from model access to firm-power siting" "speaker" OR "principal investigator"`
  - `"Hyperscaler infrastructure teams, data-center developers, power developers, large AI labs" "Map sites by firm-power time-to-energize" contact`
  - `"Track hyperscaler and data-center developer announcements that name on-site firm power, geothermal" regulator contact OR staff`
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
  - `"Contiguous land, fiber proximity, behind-the-meter firm generation rights, interconnection optionality" cost per MW OR capex OR contract`
  - `"Map sites by firm-power time-to-energize" budget procurement`
  - `"Data-center site selection, PPA strategy, power-development partnerships, capex phasing, and" capex amount`
  - `"Power-secured land options, behind-the-meter PPAs, geothermal development rights, and data-center lease premiums" price contract premium`
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
  - `"Track hyperscaler and data-center developer announcements that name on-site firm power, geothermal" data source`
  - `"Kill if by end 2028 fewer than two hyperscaler-scale campuses publicly secure" evidence`
  - `"A hyperscaler or top data-center REIT announcing a 100 MW plus campus" source`
  - `"The next constraint moves to drilling capacity, high-voltage equipment, water and cooling" watch signal`
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

#### Power interconnection and behind-the-meter viability

- Kind: `interconnection_power`
- Truth floor: `primary_verified`
- Why: For AI infrastructure, the make-or-break fact is often whether power can be energized on the underwriting timeline.
- Deliverable: A site-by-site power realism table for time-to-energize.
- Promotion rule: Do not promote this packet above 'primary_verified' until every named record has source_url, retrieved_at, quote_or_table_row, and a non-empty field set matching required_fields.
- Seed queries:
  - `"data center" "behind-the-meter" "Contiguous land, fiber proximity, behind-the-meter firm generation rights, interconnection optionality"`
  - `"hyperscaler" "interconnection" "data center" "AI infrastructure / energy"`
  - `"geothermal" "data center" "power purchase agreement"`
  - `"data center" "transformer" "lead time" permit`
  - `"PJM" "data center" interconnection queue "A hyperscaler or top data-center REIT announcing a 100 MW plus campus"`
- Source priority:
  - PJM, ERCOT, MISO, CAISO, SPP, NYISO, ISO-NE queue
  - utility interconnection filing
  - county planning and zoning agenda
  - state PUC docket
  - EIA plant or generator data
  - developer or hyperscaler announcement
- Required fields:
  - `site_or_project`
  - `utility_or_iso`
  - `queue_position_or_docket`
  - `mw`
  - `expected_in_service_date`
  - `behind_the_meter_claim`
  - `transformer_or_switchgear_dependency`
  - `water_or_cooling_permit`
  - `source_url`

### Agent Brief

- Start from P1; do not alter its scored probability, resolution date, metric, or kill condition.
- Promote named facts only when they are source-verified; otherwise keep them as leads or tasks.
- Prefer primary sources: permits, dockets, filings, official project pages, grant records, regulator pages, and procurement portals.
- For people and contacts, use official public business contact paths only. Never infer emails.
- For each action, produce amount range, funded operation, trigger, next tranche trigger, reversibility, ROI/loss logic, owner, and kill condition.
- If evidence contradicts the thesis, mark the relevant record refuted and surface it before polishing the memo.
