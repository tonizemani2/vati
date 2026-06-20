# Agent 02 - Project Fact Ledger for AI Campus Power-Claim Diligence

Generated: 2026-06-17  
Run mode: Codex-native diligence pass, not a deployed site change.  
Scope: Project-level fact ledger for P1, "AI frontier moves from model access to firm-power siting."  
Use: Buyer-facing diligence seed. A row is not `power_secured` unless MW, counterparty/offtake, power path, docket/permit/utility record, current status, and unresolved risks survive primary or official-source review.

## Source-Tier Legend

- `Tier 1 - primary regulator / official public record`: FERC, NRC, DOE, state public utility commission, state siting board, PJM, SCC, LPSC, county or municipal permit record.
- `Tier 2 - official company / utility source`: owner, utility, offtaker, project sponsor, official project page, investor-facing release.
- `Tier 3 - credible trade / local confirmation`: trade press, local news, specialist trackers. Useful for leads, not enough for "power-secured."

## Decision Ledger

### 1. AWS / Talen Susquehanna Data Campus

- Owner: Talen Energy / Susquehanna Nuclear, with Amazon Web Services / Amazon Data Services as data-center buyer/counterparty.
- Location: Susquehanna nuclear plant area, Luzerne County, Pennsylvania; PJM.
- MW/GW claim: The public diligence floor is a large co-located load tied to the Susquehanna nuclear station. Treat "up to 960 MW" and larger multi-phase claims as live but not clean until the current Talen/Amazon/PJM filing stack is pulled; FERC's order cites the 2,520 MW Susquehanna nuclear generator and 1,247 MW interconnection rights context.
- Counterparty/offtake: Amazon / AWS data-center load; Talen/Susquehanna generation and PJM transmission service are the relevant counterparties.
- Power path: Co-located/direct-connect load model at a nuclear plant, with contested treatment of load, backup service, and PJM interconnection service.
- Docket/permit/utility record: FERC `ER24-2172-000` / `ER24-2172-001`; FERC rejected the amended ISA filings in the November 1, 2024 order.
- Current status label: `contested_primary_verified_asset`.
- Source tier: Tier 1 for FERC docket/order; Tier 2 for Talen project/commercial description.
- Source URLs: https://www.ferc.gov/sites/default/files/2024-11/20241101-3061_ER24-2172-000.pdf ; https://elibrary.ferc.gov/eLibrary/docketsheet?docket_number=ER24-2172 ; https://www.talenenergy.com/powering-data/
- Retrieved date: 2026-06-17.
- Unresolved facts: Current replacement tariff status; exact enforceable MW schedule; whether the post-rejection structure is front-of-meter, behind-the-meter, or hybrid; cost allocation for backup/network service; appeal or rehearing posture.
- Next check: Pull the full FERC docket sheet for `ER24-2172`, PJM follow-on co-location compliance dockets, and the latest Talen investor or project filings before using any MW larger than the FERC order context.
- Diligence implication: This is the flagship "real counterparty, real asset, not cleanly power-secured" case, proving the product must refute as well as confirm.

### 2. Constellation / Microsoft Crane Clean Energy Center

- Owner: Constellation Energy Generation, LLC; formerly Three Mile Island Unit 1.
- Location: Londonderry Township, Dauphin County, Pennsylvania; PJM.
- MW/GW claim: 835 MW nuclear restart.
- Counterparty/offtake: Microsoft under a 20-year power purchase agreement intended to match power consumed by Microsoft data centers in PJM.
- Power path: Restart of an existing nuclear unit delivering grid-connected carbon-free generation, not a physically behind-the-meter campus.
- Docket/permit/utility record: NRC Crane Clean Energy Center restart/licensing process; DOE Energy Dominance Financing loan page for the Crane restart.
- Current status label: `source_verified_restart_pending_nrc`.
- Source tier: Tier 1 for DOE/NRC status; Tier 2 for Constellation/Microsoft commercial PPA.
- Source URLs: https://www.constellationenergy.com/news/2024/Constellation-to-Launch-Crane-Clean-Energy-Center-Restoring-Jobs-and-Carbon-Free-Power-to-The-Grid.html ; https://www.energy.gov/edf/crane-restart ; https://www.nrc.gov/info-finder/reactors/ccec
- Retrieved date: 2026-06-17.
- Unresolved facts: NRC approval timing; specific PJM deliverability and interconnection treatment after restart; whether Microsoft receives energy, attributes, or matching treatment only; any restart cost overrun or schedule slippage.
- Next check: Track NRC CCEC restart filings and Constellation's next restart schedule update; compare against DOE loan milestones.
- Diligence implication: Strong firm-power procurement proof, but it should be sold as nuclear restart/PPA evidence, not as a behind-the-meter AI campus.

### 3. Google / Brookfield Holtwood and Safe Harbor Hydro Framework

- Owner: Brookfield Renewable / Brookfield Asset Management affiliates for Holtwood and Safe Harbor hydro assets.
- Location: Pennsylvania hydroelectric facilities in PJM.
- MW/GW claim: 670 MW initial contracts for Holtwood and Safe Harbor; framework up to 3,000 MW across the United States.
- Counterparty/offtake: Google.
- Power path: 20-year hydroelectric PPAs / hydro framework agreement supporting Google's PJM operations and 24/7 carbon-free energy goals.
- Docket/permit/utility record: FERC hydro license surfaces should be checked, especially Safe Harbor Project No. 1025 and Holtwood licensing records; no row should assume relicensing or upgrade status without the FERC hydro record.
- Current status label: `source_verified_framework_regulatory_followup`.
- Source tier: Tier 2 for Brookfield/Google agreement; Tier 1 pending FERC hydro-license extraction.
- Source URLs: https://bep.brookfield.com/press-releases/bep/brookfield-and-google-sign-hydro-framework-agreement-deliver-3000-mw-homegrown
- Retrieved date: 2026-06-17.
- Unresolved facts: FERC license/relicensing posture; exact delivery profile by facility; whether any capacity is incremental vs contracted existing output; local transmission constraints.
- Next check: Pull FERC hydro project records for Holtwood and Safe Harbor, then add expiration, relicensing, and upgrade deadlines to the watchlist.
- Diligence implication: This is high-quality offtake proof for dispatchable clean energy, but the diligence edge is whether the hydro assets can actually deliver the timing and capacity implied by the framework.

### 4. Homer City Energy Campus

- Owner: Homer City Redevelopment, with Kiewit and GE Vernova named in the project execution stack.
- Location: Former Homer City coal plant site, Indiana County, Pennsylvania; PJM.
- MW/GW claim: Official project page says up to 4.4 GW of power; GE Vernova release frames the facility as up to 4.5 GW powered by seven GE Vernova turbines.
- Counterparty/offtake: Hyperscale data-center / AI and HPC demand is claimed, but named tenant/offtake is not verified in the sources reviewed.
- Power path: Large on-site / adjacent natural-gas generation at a retired coal site, expected to support data centers and local grid needs.
- Docket/permit/utility record: PA environmental/air permit and any appeal record; PJM interconnection and FirstEnergy/transmission records still need primary extraction.
- Current status label: `official_lead_permit_contested_customer_unverified`.
- Source tier: Tier 2 for project/company claims; Tier 3 for reported permit appeal; Tier 1 not complete until PA DEP/PJM records are pulled.
- Source URLs: https://www.homercityredevelopment.com/project-overview ; https://www.gevernova.com/news/press-releases/homer-city-redevelopment-kiewit-announce-country-largest-natural-gas-powered-data-center-support-ai-hpc-demand ; https://www.alleghenyfront.org/pennsylvania-homer-city-data-center-power-plant-permit-appeal/
- Retrieved date: 2026-06-17.
- Unresolved facts: Named data-center tenant; executed energy-services or offtake contract; PJM interconnection position; PA DEP permit status after appeal; gas pipeline capacity and delivery schedule.
- Next check: Pull PA DEP permit docket and PJM queue/interconnection records; do not promote beyond `official_lead` until tenant/offtake is named in a primary or official source.
- Diligence implication: Enormous and strategically relevant, but the buyer risk is exactly that the press-release scale outruns verified tenant, permit, gas, and interconnection facts.

### 5. Amazon / AES Ohio 345 kV Data-Center Service Request

- Owner: Amazon / Amazon Data Services as customer; AES Ohio as utility/transmission service provider.
- Location: AES Ohio service territory, Ohio; PJM.
- MW/GW claim: PJM load-analysis material states Phase I starts at 65 MW at COD and rises to 480 MW by the end of Phase I; trade references indicate larger later phases, but this row uses the PJM-verified floor.
- Counterparty/offtake: Amazon taking service from AES Ohio.
- Power path: 345 kV grid service, with transmission construction and service agreement treatment.
- Docket/permit/utility record: PJM Load Analysis Committee AES Ohio data-center presentation; FERC `ER25-192` transmission construction service agreement; AES Ohio Fayette Customer West 345 kV transmission line case `25-0743-EL-BLN`.
- Current status label: `primary_rto_planning`.
- Source tier: Tier 1 for PJM/FERC/OPSB-AES project records; Tier 2 for AES project page.
- Source URLs: https://www.pjm.com/-/media/DotCom/committees-groups/subcommittees/las/2024/20241125/20241125-item-x----aes-ohio-data-center.pdf ; https://www.ferc.gov/news-events/news/commissioner-christies-concurrence-aes-ohio-dayton-amazon-agreement-er25-192 ; https://www.aes-ohio.com/Fayette-Customer-West-345kV-Transmission-Line-Project
- Retrieved date: 2026-06-17.
- Unresolved facts: Full phase II/III MW schedule; network-upgrade cost responsibility; PUCO/OPSB siting status for all associated lines/substations; customer protections and collateral.
- Next check: Pull `ER25-192` order and the Ohio case file for `25-0743-EL-BLN`; extract in-service dates, upgrade costs, and cost-allocation language.
- Diligence implication: This is a clean utility/RTO-planning row and a useful contrast to splashier behind-the-meter claims because the source trail names load ramp and grid assets.

### 6. Dominion Energy Culpeper Tech Zone Transmission Buildout

- Owner: Dominion Energy Virginia / Virginia Electric and Power Company, serving data-center load growth; individual campus owners partly unnamed in utility records.
- Location: Culpeper, Orange, and Fauquier County areas, Virginia; PJM / Dominion zone.
- MW/GW claim: Dominion SCC application material cites 188 MW initially by 2028 and growth of 1,164 MW by 2034 for Culpeper County and the Town of Culpeper; PJM TEAC materials name multiple 230 kV delivery points for data-center customers over 100 MW.
- Counterparty/offtake: Data-center customers in the Culpeper Tech Zone; named customer-level offtake is not fully public in the utility records reviewed.
- Power path: 230 kV transmission project, new substations, and related network upgrades to serve data-center load and area reliability.
- Docket/permit/utility record: Virginia SCC transmission line project listing `PUR-2025-00032`; Dominion Culpeper Tech Zone project page and SCC application; PJM TEAC Dominion supplemental projects.
- Current status label: `primary_utility_regulatory_unresolved_customer`.
- Source tier: Tier 1 for SCC/PJM utility planning; Tier 2 for Dominion project page.
- Source URLs: https://www.dominionenergy.com/en/About/Delivering-Energy/Electric-Projects/Power-Line-Projects/Culpeper-Tech-Zone ; https://www.scc.virginia.gov/consumers/public-utility/electricity-faqs/transmission-line-projects/ ; https://www.dominionenergy.com/-/media/content/about/power-line-projects/culpeper-tech-zone/pdfs/2024-culpeper-tech-zone-scc-application-volume-1-of-5-part-1-of-3.pdf ; https://www.pjm.com/-/media/DotCom/committees-groups/committees/teac/2025/20250204/20250204-item-11---dominion-supplemental-projects.pdf
- Retrieved date: 2026-06-17.
- Unresolved facts: Per-campus customer names; whether each campus has signed service agreements; local land-use approvals; transmission route opposition; exact energization schedule by substation.
- Next check: Pull SCC `PUR-2025-00032` docket filings and match the Chandler, McDevitt, and Mt. Pony PJM delivery points to county approvals and developer sites.
- Diligence implication: Culpeper is a strong PJM/Mid-Atlantic load-growth proof case, but the buyer question is which specific campus has real service rights versus exposure to a contested transmission schedule.

### 7. AEP Ohio / Bloom Energy On-Site Fuel-Cell Projects for AWS and Cologix

- Owner: AEP Ohio / Ohio Power Company; Bloom Energy to build and maintain fuel-cell systems; customers include AWS and Cologix.
- Location: Central Ohio, including Hilliard for the Amazon-linked facility; PJM / AEP Ohio.
- MW/GW claim: Hilliard local project page identifies a proposed 72.9 MW solid oxide fuel-cell facility for Amazon's onsite electricity demand; the second customer/site MW was not verified in the AEP source reviewed.
- Counterparty/offtake: Amazon / AWS and Cologix data centers.
- Power path: On-site natural-gas-fueled solid oxide fuel cells / generation units intended to serve data centers while grid capacity is constrained.
- Docket/permit/utility record: PUCO approval referenced by AEP; Hilliard local project page for the Amazon facility; underlying PUCO case number still needs extraction.
- Current status label: `primary_local_plus_company_mw_partial`.
- Source tier: Tier 2 for AEP company release; Tier 1/local official page for Hilliard project specifics; Tier 1 PUCO docket pending.
- Source URLs: https://www.aep.com/news/stories/view/10262/ ; https://hilliardohio.gov/fuel-cells/ ; https://content.govdelivery.com/accounts/OHPUC/bulletins/3e8bb79
- Retrieved date: 2026-06-17.
- Unresolved facts: PUCO case number/order; Cologix facility MW; customer tariff treatment; gas supply terms; whether fuel cells reduce network-upgrade obligations or merely bridge timing.
- Next check: Pull the PUCO onsite-generation order and AEP tariff filings; add site-by-site MW, owner, rate treatment, and commissioning dates.
- Diligence implication: This is a concrete bridge-power pattern, but the row is only partially quantified until the PUCO order and second-site MW are extracted.

### 8. Socrates North and South Power Solution Facilities

- Owner: Will-Power OH, LLC / Williams Companies.
- Location: New Albany, Licking County, Ohio; PJM / AEP Ohio region.
- MW/GW claim: Two 200 MW power generation sites, 400 MW combined.
- Counterparty/offtake: Adjacent data-center load; trade/local sources identify Meta-related load, but the official Williams page reviewed does not by itself establish the ultimate data-center owner.
- Power path: Behind-the-meter natural-gas generation facilities; OPSB says Socrates South will serve adjacent data-center load and will not be physically connected to the electric grid.
- Docket/permit/utility record: Ohio Power Siting Board approval for Socrates South; Williams project page for Socrates North and South.
- Current status label: `primary_regulator_btm_counterparty_unverified`.
- Source tier: Tier 1 for OPSB approval/status; Tier 2 for Williams project description.
- Source URLs: https://opsb.ohio.gov/news/opsb-approves-construction-of-licking-county-natural-gas-fired-power-plant ; https://www.williams.com/expansion-project/socrates-power-solution-facilities/ ; https://newalbanyohio.org/natural-gas-power/
- Retrieved date: 2026-06-17.
- Unresolved facts: Exact load owner and contractual offtaker; north-facility OPSB status; gas-pipeline permits; emissions permit conditions; construction and COD by facility.
- Next check: Pull OPSB case documents for Socrates South and North, then match applicant, consuming entity, gas pipeline applications, and COD.
- Diligence implication: This is one of the cleanest behind-the-meter patterns reviewed, but customer identity and gas-permit dependencies remain diligence gates.

### 9. Apollo Power Generation Facility

- Owner: Will-Power OH, LLC / Williams Companies.
- Location: Near Mercer Road and Middleton Pike, Middleton Township, Wood County, Ohio.
- MW/GW claim: 350 MW natural-gas-fired generation plus approximately 120 MW of battery energy storage.
- Counterparty/offtake: Liames, LLC will consume the power; Liames is constructing the adjacent data-center campus.
- Power path: Behind-the-meter facility serving adjacent data-center load; OPSB says it will not be physically connected to the electric power grid.
- Docket/permit/utility record: Ohio Power Siting Board case `25-973-EL-BGN`; OPSB authorization announced February 3, 2026.
- Current status label: `primary_regulator_btm_approved`.
- Source tier: Tier 1 for OPSB approval and case number; Tier 2 for Williams project page.
- Source URLs: https://content.govdelivery.com/accounts/OHPUC/bulletins/4077fa5 ; https://opsb.ohio.gov/news/opsb-authorizes-construction-of-wood-county-power-plant ; https://www.williams.com/expansion-project/apollo-power-generation-project/
- Retrieved date: 2026-06-17.
- Unresolved facts: Liames beneficial owner / end customer; Ohio EPA air permit status; gas pipeline permits; enforceable COD and construction milestones; battery-storage interconnection/operating conditions.
- Next check: Pull OPSB `25-973-EL-BGN` filings and Ohio EPA air permit comments/permit, then verify Liames corporate linkage before naming Meta or any hyperscaler.
- Diligence implication: Apollo is a strong comparison case for approved BTM gas plus storage, but the customer-identity question is still the buyer's first unresolved fact.

### 10. Meta Richland Parish Data Center / Entergy Louisiana Buildout

- Owner: Meta for the data center; Entergy Louisiana for utility infrastructure; Mortenson, Turner, and DPR named on the project site as builders.
- Location: Richland Parish, Louisiana; MISO/Entergy Louisiana territory, outside PJM.
- MW/GW claim: Meta says the campus will deliver over 2 GW of compute capacity; Entergy's initial utility plan includes three combined-cycle combustion turbines totaling 2,260 MW, major transmission, substations, and additional clean-energy commitments. Later Entergy materials point to expanded agreements and larger customer-savings/cost-recovery structures.
- Counterparty/offtake: Meta and Entergy Louisiana.
- Power path: Utility-scale grid buildout with new generation, 500 kV and 230 kV transmission, substations, storage/renewables commitments, and LPSC approvals; not behind-the-meter proof.
- Docket/permit/utility record: Louisiana Public Service Commission approval and Entergy Louisiana filings/announcements for Meta infrastructure investments.
- Current status label: `source_verified_grid_buildout_lpsc_approved`.
- Source tier: Tier 2 for Meta and Entergy official pages; Tier 1 follow-up required for the full LPSC docket and transcript stack.
- Source URLs: https://datacenters.atmeta.com/richland-parish-data-center/ ; https://www.entergy.com/news/entergy-louisiana-power-meta-s-data-center-in-richland-parish ; https://www.entergy.com/news/entergy-louisiana-receives-lpsc-approval-for-major-infrastructure-investments-to-support-metas-data-center-and-improve-reliability ; https://www.entergy.com/news/entergy-louisiana-announces-a-new-agreement-with-meta-that-will-deliver-an-additional-2b-in-customer-savings
- Retrieved date: 2026-06-17.
- Unresolved facts: Exact LPSC docket numbers and attachments; final cost allocation and customer protections; expansion path from 2 GW compute to larger utility service; gas-unit approvals not yet final for any later expansion.
- Next check: Pull LPSC orders, electric service agreement summaries if public, and all confidential-redaction indexes; separate approved infrastructure from proposed expansion.
- Diligence implication: Richland Parish is a key comparison case because it looks "power secured" in public narrative but is actually a regulated utility mega-build with cost-allocation and approval risk.

### 11. Meta / Constellation Clinton Clean Energy Center

- Owner: Constellation Energy, Clinton Clean Energy Center.
- Location: Clinton, Illinois; MISO Zone 4, outside PJM.
- MW/GW claim: 1,121 MW under the Meta/Constellation PPA announcement; Constellation's location page lists the Clinton reactor as capable of up to 1,092 MW before uprate context.
- Counterparty/offtake: Meta.
- Power path: 20-year nuclear PPA / corporate nuclear energy agreement for output/attributes supporting Meta's clean-energy goals and regional operations.
- Docket/permit/utility record: NRC operating/relicensing and Illinois ZEC-expiration context should be pulled; company announcement says agreement supports relicensing and operations after the ZEC program expires.
- Current status label: `source_verified_nuclear_ppa_not_campus_power`.
- Source tier: Tier 2 for Meta/Constellation official PPA; Tier 1 pending NRC/license and any MISO deliverability extraction.
- Source URLs: https://www.constellationenergy.com/news/2025/constellation-meta-sign-20-year-deal-for-clean-reliable-nuclear-energy-in-illinois.html ; https://about.fb.com/news/2025/06/meta-constellation-partner-clean-energy-project/ ; https://www.constellationenergy.com/about/locations/clinton-clean-energy-center.html
- Retrieved date: 2026-06-17.
- Unresolved facts: Whether the PPA is physical, virtual, or attribute-heavy in its final structure; NRC/license renewal milestones; treatment of uprate from 1,092 MW to 1,121 MW claim; MISO deliverability relevance to Meta load.
- Next check: Pull NRC Clinton license/relicensing records and any MISO queue/deliverability artifacts; do not describe as direct data-center power without contractual confirmation.
- Diligence implication: Strong evidence that hyperscalers will contract for firm nuclear, but not proof that a specific AI campus can energize faster.

### 12. Lancium / Crusoe Stargate 1 Abilene Campus

- Owner: Lancium for clean-campus infrastructure; Crusoe as data-center developer/operator in the official 200 MW announcement; broader Stargate/OpenAI/Oracle/SoftBank ecosystem claims require separate verification.
- Location: Abilene, Taylor County, Texas; ERCOT, outside PJM.
- MW/GW claim: Crusoe announced an initial 200 MW data center at the Lancium Clean Campus; Lancium later describes Stargate 1 as a gigawatt-scale campus with 1.2 GW grid interconnect and onsite gas generation complete by 2025.
- Counterparty/offtake: Crusoe's 200 MW announcement says the first phase is leased to a Fortune 100 company; OpenAI/Oracle/Stargate association is widely reported but should not be treated as the offtake record for this row without a primary contract or permit tie.
- Power path: ERCOT grid interconnect plus claimed onsite gas generation, storage, renewables, and power orchestration.
- Docket/permit/utility record: Lancium says ERCOT approved / 1.2 GW grid interconnect; TCEQ and ERCOT records need primary extraction before promoting beyond company-verified.
- Current status label: `company_verified_comparison_primary_records_pending`.
- Source tier: Tier 2 for Lancium/Crusoe official pages; Tier 1 pending ERCOT/TCEQ permit and interconnection records.
- Source URLs: https://www.crusoe.ai/resources/newsroom/crusoe-200mw-ai-data-center ; https://lancium.com/locations/ ; https://lancium.com/2025/03/18/crusoe-expands-ai-data-center-campus-in-abilene-to-1-2-gigawatts/
- Retrieved date: 2026-06-17.
- Unresolved facts: ERCOT interconnection record; TCEQ permit capacity and turbine count; direct OpenAI/Oracle offtake documentation; whether 1.2 GW is fully energized, contracted, or staged.
- Next check: Pull ERCOT interconnection and TCEQ air-permit records; split verified Abilene campus facts from national Stargate expansion claims.
- Diligence implication: Useful outside-PJM comparison for speed and power-stack packaging, but it must not be imported into PJM diligence without the underlying Texas records.

## Tempting Lead Demotions / Refutations

### A. Quantum Loophole Frederick County, Maryland

- Tempting claim: Gigawatt-scale master-planned data-center community in PJM/Mid-Atlantic with land, power, fiber, and cooling water.
- Sources reviewed: https://quantumloophole.com/ ; https://business.maryland.gov/news/quantum-loophole-plans-develop-data-center-campus-maryland/ ; https://frederickcountymd.gov/DocumentCenter/View/349295/DCWG---Public-Comments-as-of-20231213-w-attach
- Retrieved date: 2026-06-17.
- Demotion: `demoted_press_release_site_lead`.
- Why not promoted: The sources support a real site and master-plan narrative, but this pass did not verify named tenant offtake, enforceable MW, interconnection service, utility upgrades, or current permit status adequate for a firm-power row.
- Next check: Pull county planning approvals, Potomac Edison / FirstEnergy service records, PJM upgrade records, and any named tenant filings.
- Diligence implication: Strong site lead for a buyer-provided asset list, weak proof for "power-secured AI campus" until utility and permit records are tied to a named load.

### B. EdgeCore Culpeper Data Centers

- Tempting claim: Culpeper campus initially supporting roughly 196-216 MW of IT load, with high-density AI/cloud positioning near Northern Virginia.
- Sources reviewed: https://edgecore.com/locations/culpeper-data-centers ; https://chooseculpeper.com/culpeper-tech-zone/edgecore-digital-infrastructure-announces-new-hyperscale-data-center-market-in-culpeper-virginia/ ; https://www.dominionenergy.com/en/About/Delivering-Energy/Electric-Projects/Power-Line-Projects/Culpeper-Tech-Zone
- Retrieved date: 2026-06-17.
- Demotion: `demoted_site_verified_power_path_unresolved`.
- Why not promoted: EdgeCore verifies a campus and load-intensity claim, while Dominion/SCC records verify the broader transmission buildout; the row still lacks a project-specific firm generation source, executed service agreement, and clean energization proof.
- Next check: Match EdgeCore parcel/campus approvals to SCC/PJM delivery-point records and local permits; extract whether Rappahannock Electric Cooperative or Dominion holds the actual service path.
- Diligence implication: This is a good case for time-to-energize risk scoring, not a standalone firm-power proof.

### C. Homer City as "Already Power-Secured"

- Tempting claim: The former coal site becomes the largest gas-powered AI data-center campus in the United States, with 4.4-4.5 GW available for hyperscale load.
- Sources reviewed: https://www.homercityredevelopment.com/project-overview ; https://www.gevernova.com/news/press-releases/homer-city-redevelopment-kiewit-announce-country-largest-natural-gas-powered-data-center-support-ai-hpc-demand ; https://www.alleghenyfront.org/pennsylvania-homer-city-data-center-power-plant-permit-appeal/
- Retrieved date: 2026-06-17.
- Demotion: `demoted_scale_verified_customer_and_permit_risk`.
- Why not promoted: Official sources support the project ambition and turbine/power-infrastructure claim, but this pass did not verify a named hyperscale tenant, enforceable offtake, final environmental-permit status after appeal, gas capacity, or PJM interconnection terms.
- Next check: Pull PA DEP air-permit and appeal documents, PJM queue records, gas-pipeline records, and any signed tenant/offtake announcements.
- Diligence implication: The project is too important to ignore and too incomplete to use as clean proof.

### D. Stargate National Expansion Claims

- Tempting claim: "Stargate" as a multi-gigawatt or national AI-infrastructure buildout proves massive firm-power campus demand is already secured.
- Sources reviewed: https://lancium.com/locations/ ; https://www.crusoe.ai/resources/newsroom/crusoe-200mw-ai-data-center ; https://lancium.com/2025/03/18/crusoe-expands-ai-data-center-campus-in-abilene-to-1-2-gigawatts/
- Retrieved date: 2026-06-17.
- Demotion: `demoted_macro_expansion_claim`.
- Why not promoted: Abilene has official company evidence, but national Stargate capacity claims blend partnership announcements, staged campus development, power procurement, and speculative site selection; they are not a single project-level power-secured record.
- Next check: Treat each Stargate site as a separate diligence row and require local interconnection, generation permit, utility agreement, named offtaker, and construction status before adding it to the promoted ledger.
- Diligence implication: The marketing label is less useful than the parcel-by-parcel power record; buyers need the latter.

## Cross-Case Read

The current ledger supports the P1 launch wedge, but with a sharp correction: "AI campus power is scarce" is no longer proprietary. The sellable object is the verification grammar.

The strongest `primary_verified` rows are not always the flashiest. AWS/AES Ohio, Dominion Culpeper, Socrates, and Apollo have useful utility/regulatory trails. Talen/Amazon Susquehanna is commercially real but contested. Crane, Clinton, and Google/Brookfield show hyperscaler appetite for firm or dispatchable clean power, but they mostly prove procurement strategy, not direct campus energization. Richland Parish proves the opposite of a simple behind-the-meter story: a giant AI campus may be a regulated utility buildout with public cost-allocation risk.

## Next 48-Hour Checks

1. Pull FERC `ER24-2172`, `ER25-192`, `RM26-4`, `EL25-49`, and PJM co-location compliance filings; create a docket spine with filing date, issue, order status, and next deadline.
2. Pull state records for OPSB `25-973-EL-BGN`, Socrates South/North, AES Ohio `25-0743-EL-BLN`, SCC `PUR-2025-00032`, and LPSC Meta/Entergy approvals.
3. For each promoted row, separate four facts: load MW, generation MW, contracted offtake MW, and physically deliverable MW. These are currently blurred in many public claims.
4. Add a `time_to_energize_score` only after the row has a docket/permit status and an in-service date from a primary or official source.
5. Keep one demoted lead in every sample buyer memo. Refutation is the product proof.
