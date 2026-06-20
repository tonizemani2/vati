# Agent 01 - Regulatory / Docket Spine

Generated: 2026-06-17

Assignment: build the regulatory and docket spine for AI/data-center campus power-claim diligence. This file is intentionally scoped to dockets, official proceedings, utility tariffs, and public regulatory sources. It does not edit site files and does not deploy anything.

## Executive Read

The public asset was too thin because it treated "power-secured AI campus" as a story. The diligence-grade version has to treat it as a docket claim.

The regulatory spine says the live question is not "is data-center power demand large?" That is consensus. The live question is whether a named campus can prove, in primary or official sources, all of the following:

- MW or contracted capacity.
- Counterparty or responsible utility/offtaker.
- Interconnection, co-location, behind-the-meter, or grid-service path.
- Tariff/cost-allocation treatment.
- Permit, docket, or queue status.
- Next regulatory date that can change the time-to-energize.

The strongest current evidence surfaces are PJM/FERC co-location dockets, AEP Ohio/PUCO data-center tariff materials, Dominion/Virginia SCC GS-5 and queue proceedings, and PJM large-load forecast/interconnection materials. The first commercial move should be to verify or demote named power claims, not to sell the already-obvious conclusion that power is scarce.

## Verification Legend

`primary_verified`: primary regulator, official docket, FERC eLibrary, SCC/PUCO order, PJM tariff/official report, or other official public record directly supports the fact.

`source_verified`: official company, utility, trade, or government summary supports the fact, but the underlying docket/permit/agreement has not yet been pulled.

`lead`: plausible and useful for research, but not decision-grade. Needs at least one official docket, permit, queue, tariff, or filed agreement.

`contested_primary_verified`: the asset exists and the dispute is visible in primary sources, but the claimed power path is not cleanly approved.

`demoted`: useful as a refutation example or comparison case, not as proof of a power-secured campus.

## Docket Map

| ID | Proceeding / official source | Jurisdiction | Status on 2026-06-17 | Issue for AI/data-center power claims | Deadline / next check | Project link | Evidence grade | Source URL |
|---|---|---|---|---|---|---|---|---|
| `RM26-4-000` | FERC, Interconnection of Large Loads to the Interstate Transmission System | Federal / interstate transmission | Open ANOPR/rulemaking track. FERC said it will act by June 2026. June 18, 2026 open meeting is the immediate watch item. | Standardizing how large loads, including data centers and co-located/flexible loads, interconnect to interstate transmission. This is the national rules spine. | 2026-06-18 FERC open meeting and any order/NOPR posted to eLibrary; then comment/rehearing deadlines. | All transmission-level AI campuses; especially projects claiming fast interconnection or flexible/curtailable treatment. | primary_verified | https://www.ferc.gov/rm26-4 ; https://www.ferc.gov/news-events/news/ferc-act-large-load-interconnection-docket-june-2026 |
| `AD24-11-000` | FERC technical conference, Large Loads Co-Located at Generating Facilities | Federal / generic co-location | Technical-conference record. Used as a record source in later PJM co-location proceedings. | Generic issues for loads physically or electrically adjacent to generation, including whether the grid is used for backup, balancing, ancillary services, or capacity. | Check when parties cite AD24-11 testimony in `EL25-49`, `ER26-1479`, and rehearing/appellate filings. | Any direct-connect or behind-generator-meter data-center claim. | primary_verified | https://www.ferc.gov/news-events/events/commissioner-led-technical-conference-regarding-large-loads-co-located ; https://elibrary.ferc.gov/eLibrary/docketsheet?docket=AD24-11-000 |
| `ER24-2172-000`, `ER24-2172-001` | PJM / Susquehanna Nuclear / PPL amended ISA | FERC / PJM | FERC rejected PJM's amended ISA on 2024-11-01, without prejudice. Existing 300 MW arrangement and proposed increase are not the same thing. | Flagship refutation case: a real commercial co-location story with real MW, but the incremental power path failed the docket test. | Watch rehearing/appellate posture and any new PJM/FERC filings that replace or repackage the ISA. Also cross-check `EL25-49` replacement rules. | Talen/Amazon/Cumulus Susquehanna data-campus power claim. | contested_primary_verified | https://www.ferc.gov/sites/default/files/2024-11/20241101-3061_ER24-2172-000.pdf ; https://www.ferc.gov/news-events/news/commissioner-christies-concurrence-pjms-susquehanna-co-location-proposal-er24-2172 |
| `EL25-49-000`, `EL25-49-001`, `EL25-20-000`, `ER24-2888-001`, consolidated with `AD24-11-000` | FERC PJM co-location show-cause / complaint stack | FERC / PJM | FERC issued December 18, 2025 order directing PJM to establish transparent rules and compliance filings. | Core PJM co-location rules: what service a co-located load must take, whether PJM tariff is just and reasonable, how costs are allocated, and what "co-located load" means. | Pull current eLibrary docket sheet after June 18, 2026; monitor rehearing, paper-hearing replacement-rate issues, and linked compliance dockets. | Every PJM campus claiming generation co-location, grid backup, or behind-the-meter power. | primary_verified | https://www.ferc.gov/news-events/news/ferc-directs-nations-largest-grid-operator-create-new-rules-embrace-innovation-and ; https://www.ferc.gov/sites/default/files/2025-12/E-1%20EL25-49-000.pdf |
| `ER26-1088-000` | PJM 30-day compliance filing from `EL25-49` | FERC / PJM | FERC April 2026 summary says accepted in part, rejected in part, and directed further compliance within 30 days. | Tests whether PJM's first compliance language matches FERC's co-located-load directives. | Deadline from the April 16, 2026 order has passed. Next check: eLibrary for PJM further compliance, deficiency notices, protests, and acceptance/rejection orders. | Near-term PJM co-location claims relying on revised PJM tariff language. | primary_verified | https://www.ferc.gov/news-events/news/summaries-april-2026-commission-meeting ; https://www.pjm.com/library/governing-documents/effective-documents |
| `ER26-1479-000` | PJM 60-day co-located-load tariff revisions | FERC / PJM | Pending at FERC on PJM effective-documents page. Filed February 23, 2026; comments due March 16, 2026. | Behind-the-meter generation, transmission services, necessary studies, and interconnection procedure changes for co-located load. | Next check: FERC merits order, protests, answers, and effective tariff language. | PJM projects that claim a new co-location service path, grid-reliance charge treatment, or BTMG exception. | primary_verified | https://www.pjm.com/library/governing-documents/effective-documents ; https://elibrary.ferc.gov/eLibrary/filelist?accession_number=20260223-5181&optimized=false |
| `ER26-1563-000`, `ER26-1563-001` | PJM Expedited Interconnection Track for generation | FERC / PJM | FERC accepted PJM's EIT on June 9, 2026. | Not a large-load tariff by itself, but it is the supply-side companion: expedited interconnection for shovel-ready generation that can address PJM resource adequacy pressure created by load growth. | Watch first EIT solicitation/list of accepted projects; check whether projects are tied to large-load/data-center capacity claims. | AI campus claims that depend on new generation being accelerated into PJM. | primary_verified | https://www.ferc.gov/news-events/news/commissioner-rosners-concurrence-order-accepting-tariff-revisions-re-pjm-0 ; https://www.pjm.com/-/media/DotCom/documents/ferc/orders/2026/20260609-er26-1563-000.PDF |
| `EL26-30-000` | Independent Market Monitor for PJM v. PJM Interconnection | FERC / PJM | Complaint filed November 25, 2025; live FERC complaint surface for reliability/capacity treatment of large data-center loads. | Whether PJM may add large data-center loads only when all customers can be served reliably, including capacity adequacy, not merely transmission. | Pull latest FERC docket sheet; next useful check is any order, settlement, dismissal, or consolidation with RM26-4/PJM proceedings. | Any PJM campus whose "power path" assumes curtailment/flexibility instead of firm capacity. | source_verified_to_primary_lead | https://www.pjm.com/-/media/DotCom/documents/ferc/filings/2025/20251125-el26-30-000.pdf ; https://www.monitoringanalytics.com/filings/2025/IMM_Complaint_re_Data_Center_Loads_Docket_No_EL26-XX_20251125.pdf |
| `24-0508-EL-ATA` | PUCO / AEP Ohio Data Center Tariff | Ohio retail/distribution + PJM interface | PUCO adopted settlement July 9, 2025; AEP Ohio says compliance tariff effective July 23, 2025. | Data centers must make binding commitments/collateral so speculative MW do not force overbuilt grid investment. This is the strongest state-level tariff proof that "claimed MW" has to be de-risked. | Next check: PUCO docket for compliance filings, rehearing/appeal, and AEP's subsequent load updates to PJM. | Central Ohio/AEP Ohio data-center queue and any campus claiming service before 2031/2033. | primary_verified | https://www.aepohio.com/company/about/rates/data-center-tariff/ ; https://puco.ohio.gov/news/puco-orders-aep-ohio-to-create-data-center-specific-tariff |
| AEP Ohio DCT Load Study Letter, dated 2025-11-07 | AEP Ohio official tariff implementation source | Ohio / PJM | AEP says 36 sites totaling 13,022.7 MW paid for formal study; all require regional upgrades; estimated service dates Q4 2031 / 2033 depending cluster. | Turns "Ohio data-center demand" into time-to-energize evidence. The gating asset is not local service only; it is regional transmission. | Next check: PJM 2026 RTEP analysis and any AEP updates after customers execute/forfeit LOAs/ESAs. | AEP Ohio / Central Ohio data-center service claims; PJM 2025W1-570 765 kV solution. | source_verified_official; several facts primary once matched to PUCO docket | https://www.aepohio.com/lib/docs/ratesandtariffs/ohio/AEP-Ohio_DCT_Load_Study_Letter_25.11.7.pdf |
| AEP Ohio February 2026 update | AEP Ohio official news / PUCO update | Ohio / PJM | AEP says contracted data-center projects total 17,861 MW: 5,642 MW under DCT plus 12,219 MW before tariff. Pre-tariff interest exceeded 30,000 MW. | Demonstrates tariff filtering: speculative claims fell sharply when collateral/binding contracts were required. | Pull the linked PUCO filing behind AEP's update and compare to PJM load forecast inputs. | Any diligence row using Central Ohio MW as demand proof. | source_verified_official | https://www.aepohio.com/company/news/view?releaseID=10753 |
| `PUR-2025-00058` | Virginia SCC / Dominion 2025 biennial review and GS-5 class | Virginia retail/transmission interface + PJM DOM Zone | Final order issued November 25, 2025. SCC created GS-5 large-load rate class, effective January 1, 2027. | Separates large loads/data centers into a rate class and imposes minimum obligations/collateral to reduce cost shifting. | Next check: Dominion tariff filings implementing GS-5; future SCC cost-allocation proposals for generation/transmission. | Dominion Virginia data centers, including hyperscale loads in DOM Zone. | primary_verified | https://www.scc.virginia.gov/about-the-scc/newsreleases/release/scc-issues-order-on-dev-biennial-review-2025/scc-rules-in-dev-biennial-review-case.html ; https://www.scc.virginia.gov/docketsearch/DOCS/89g601%21.PDF |
| `PUR-2026-00011` | Virginia SCC / Dominion large-load connection queue process standards | Virginia / Dominion Zone / PJM | Application filed February 2, 2026; order for notice/hearing issued February 19, 2026. | Queue process for delivery-point requests associated with large data-center loads; proposed applicability around 100 MW+ and 300 MW individual request cap. | Hearing was set for April 28, 2026. Next check: SCC docket for final order or hearing-examiner report after that date. | Dominion Zone data-center service requests, including EDC requests for large campuses. | primary_verified | https://www.scc.virginia.gov/docketsearch/DOCS/8%40n101%21.PDF ; https://www.scc.virginia.gov/docketsearch/DOCS/8%40%23101%21.PDF |
| Dominion 2025 20-Year Data Center Forecast to PJM LAS | PJM/Dominion planning source | PJM DOM Zone | PJM-posted September 2025 forecast deck. Dominion states forecasted 2025 billing demand of 4.2 GW and says major transmission energization changes 2026 growth. | Planning proof for the scale and concentration of Dominion data-center load. | Match deck assumptions to PJM 2026 load forecast and SCC GS-5/queue records. | primary_verified_planning | https://www.pjm.com/-/media/DotCom/committees-groups/subcommittees/las/2025/20250916/20250916-item-04ai---dominion-data-center-large-load-request.pdf |
| PJM 2026 Load Forecast Report and large-load adjustment docs | PJM planning | PJM footprint | 2026 forecast distinguishes firm vs non-firm large-load additions and derates uncertainty. PJM says improved vetting reduced near-term load compared with 2025 forecast. | The forecast itself has become a regulatory object. Data-center MW that is non-firm or speculative should not be treated as investable energized capacity. | Next check: PJM 2027 load forecast process; compare utility submissions to accepted load forecast values. | All PJM campuses and utility-zone forecasts. | primary_verified | https://www.pjm.com/-/media/DotCom/library/reports-notices/load-forecast/2026-load-report.pdf ; https://insidelines.pjm.com/pjms-updated-20-year-forecast-continues-to-see-significant-long-term-load-growth/ |
| PJM Critical Issue Fast Path - Large Load Additions | PJM stakeholder process | PJM footprint | Board/stakeholder process launched August 2025; by January 2026 PJM outlined actions after 12 proposals. | Reliability-focused solutions for integrating large loads while respecting state jurisdiction and data-center/LSE/EDC relationships. | Track final board actions, manual/tariff filings, and how concepts map into FERC dockets. | primary_verified | https://www.pjm.com/committees-and-groups/cifp-lla ; https://www.pjm.com/-/media/DotCom/about-pjm/newsroom/2026-releases/20260116-pjm-board-outlines-plans-to-integrate-large-loads-reliably.pdf |
| NERC Emerging Large Loads Technical Conference | NERC/FERC-referenced technical conference | North America / reliability | February 24-25, 2026 conference. FERC page lists related dockets including `EL25-49`, `AD24-11`, `EL25-20`, `EL26-30`, and multiple large-load matters. | Reliability facts and operating-risk vocabulary for large loads, including sudden load drops, voltage/frequency sensitivity, and flexible load claims. | Pull NERC materials/transcripts and map reliability concerns to project-specific claims. | primary_verified_event | https://www.ferc.gov/news-events/events/north-american-electric-reliability-corporation-emerging-large-loads-technical |

## Evidence Extracts And Short Quotes

Keep these as source spans for the dossier. Quotes are intentionally short; use the URLs for full context.

### FERC / Federal

- `RM26-4-000`: FERC says the ANOPR concerns "significant electrical loads" including data centers and the nation's transmission infrastructure. Source: https://www.ferc.gov/news-events/news/ferc-act-large-load-interconnection-docket-june-2026
- `RM26-4-000`: FERC's explainer frames the goal as stakeholder input on "timely, orderly, reliable, and non-discriminatory" large-load interconnection. Source: https://www.ferc.gov/rm26-4
- `EL25-49`: FERC says PJM must create transparent rules for "AI-driven data centers" and other co-located large loads. Source: https://www.ferc.gov/news-events/news/ferc-directs-nations-largest-grid-operator-create-new-rules-embrace-innovation-and
- `ER24-2172`: FERC's Susquehanna order is a direct refutation anchor: the amended ISA was rejected, so the project cannot be sold as clean approval for the incremental co-located load path. Source: https://www.ferc.gov/sites/default/files/2024-11/20241101-3061_ER24-2172-000.pdf
- `ER26-1563`: FERC accepted PJM's EIT for up to 20 shovel-ready generation projects over two years, a supply-side response to resource adequacy pressure. Source: https://www.ferc.gov/news-events/news/commissioner-rosners-concurrence-order-accepting-tariff-revisions-re-pjm-0

### PJM

- PJM effective documents page lists `ER26-1088-000` and `ER26-1479-000` as pending/active co-located-load tariff compliance surfaces. Source: https://www.pjm.com/library/governing-documents/effective-documents
- PJM describes `ER26-1479-000` as covering BTM generation, transmission services, necessary studies, and interconnection procedures. Source: https://www.pjm.com/library/governing-documents/effective-documents
- PJM's load forecast update says improved vetting of requested adjustments for data centers and large loads reduced the near-term forecast. Source: https://insidelines.pjm.com/pjms-updated-20-year-forecast-continues-to-see-significant-long-term-load-growth/
- Dominion's PJM-posted forecast deck says 2025 data-center billing demand was forecast at 4.2 GW and that seven customers accounted for 72% of YTD demand. Source: https://www.pjm.com/-/media/DotCom/committees-groups/subcommittees/las/2025/20250916/20250916-item-04ai---dominion-data-center-large-load-request.pdf

### AEP Ohio / PUCO

- AEP Ohio says PUCO adopted the 2024 DCT settlement on July 9, 2025, and the compliance tariff became effective July 23, 2025. Source: https://www.aepohio.com/company/about/rates/data-center-tariff/
- AEP's load-study letter says 36 sites totaling 13,022.7 MW requested formal study by September 8, 2025. Source: https://www.aepohio.com/lib/docs/ratesandtariffs/ohio/AEP-Ohio_DCT_Load_Study_Letter_25.11.7.pdf
- AEP's load-study letter says none of the 13,022.7 MW can be reliably served before the 2025W1-570 or comparable regional solution, expected around Q4 2031. Source: https://www.aepohio.com/lib/docs/ratesandtariffs/ohio/AEP-Ohio_DCT_Load_Study_Letter_25.11.7.pdf
- AEP Ohio's February 2026 update says binding contracts under the tariff fell to 5,642 MW from 13,022.7 MW studied, while pre-tariff interest exceeded 30,000 MW. Source: https://www.aepohio.com/company/news/view?releaseID=10753
- OCC says the settlement is meant to shield residential and small-business customers from unfair data-center infrastructure costs. Source: https://www.occ.ohio.gov/content/data-center-costs-24-0508-el-ata

### Dominion / Virginia SCC

- SCC says GS-5 will comprise customers demanding 25 MW or more and will be effective January 1, 2027. Source: https://www.scc.virginia.gov/about-the-scc/newsreleases/release/scc-issues-order-on-dev-biennial-review-2025/scc-rules-in-dev-biennial-review-case.html
- SCC says large-load customers will pay at least 85% of transmission/distribution costs each month regardless of actual usage, with exemptions for certain older service. Source: https://www.scc.virginia.gov/media/sccvirginiagov-home/about-the-scc/fact-sheets/scc-data-center-initiatives-02-2026.pdf
- SCC fact sheet says new large-load customers contracting after January 1, 2027 face at least 14 years of service/payment obligation. Source: https://www.scc.virginia.gov/media/sccvirginiagov-home/about-the-scc/fact-sheets/scc-data-center-initiatives-02-2026.pdf
- `PUR-2026-00011`: Dominion's proposed standards apply to DP requests associated with data-center large loads of approximately 100 MW or more, with individual DP requests proposed at a maximum of 300 MW. Source: https://www.scc.virginia.gov/docketsearch/DOCS/8%40n101%21.PDF
- `PUR-2026-00011`: Dominion testimony states roughly 70,000 MW of large-load DP requests were in the queue/study process as of December 31, 2025, nearly triple the DOM Zone all-time peak cited in the filing. Source: https://www.scc.virginia.gov/docketsearch/DOCS/8%40%23101%21.PDF

## Project / Asset Linkage Table

| Project or claim | Market | Docket/source spine | Current diligence label | What is verified | What is not yet verified | Next check |
|---|---|---|---|---|---|---|
| Talen/Amazon/Cumulus Susquehanna data-campus power claim | PJM / Pennsylvania | `ER24-2172`; `EL25-49`; `AD24-11` | contested_primary_verified | FERC rejected the amended ISA; existing/proposed co-location distinction is visible in FERC record. | Current commercial structure after FERC rejection; any revised ISA; appellate outcome; actual deliverable MW path. | Pull latest ER24-2172/EL25-49 eLibrary sheets and any court docket before using as proof. |
| Generic PJM co-located-load campus | PJM | `EL25-49`; `ER26-1088`; `ER26-1479` | primary_verified_regulatory_path, asset_unverified | FERC/PJM rule path exists; tariff language is being revised. | Whether a named project qualifies and at what transmission-service price/curtailment right. | Do not call any named campus power-secured until matched to final tariff and project-specific agreement. |
| Central Ohio AEP data-center queue | PJM / Ohio | PUCO `24-0508-EL-ATA`; AEP DCT; PJM RTEP | source_verified_official, tariff_primary_pending docket extraction | 36 studied sites, 13,022.7 MW studied, all require regional upgrades; Q4 2031/2033 service estimates; 5,642 MW signed under DCT as of Feb. 2026 update. | Which named sites signed; customer names; final PJM upgrade assignments; local service-plan costs. | Pull PUCO filings linked from AEP page; match AEP updates to PJM RTEP/load forecast records. |
| Dominion GS-5 / large-load class | PJM / Virginia | SCC `PUR-2025-00058` | primary_verified | Separate GS-5 class, minimum demand obligations, collateral, 14-year term, future cost-allocation proposals. | Final tariff sheets and how individual data centers are assigned; actual customer collateral levels. | Pull Dominion tariff compliance filings and future SCC cost-allocation proposals. |
| Dominion large-load connection queue | PJM / Virginia DOM Zone | SCC `PUR-2026-00011`; PJM Dominion forecast deck | primary_verified_process, asset_unverified | Application/hearing record; proposed 100 MW+ applicability; 300 MW DP cap; staged queue process; huge DP-request volume. | Final SCC-approved queue standards; project names; per-project dates; whether requests convert to ESAs. | Pull post-April 28, 2026 SCC orders/hearing record. |
| PJM EIT generation acceleration | PJM | `ER26-1563` | primary_verified_supply_side | FERC accepted EIT for limited expedited generation interconnections. | Which projects enter; whether they serve data-center load; commercial offtake or capacity accreditation. | Watch PJM EIT project list and RTEP/capacity linkage. |
| PJM large-load forecast claims | PJM footprint | PJM 2026 Load Forecast; utility-zone docs | primary_verified_planning | PJM now distinguishes firm/non-firm large-load requests and derates uncertainty. | Whether any single campus will be energized on schedule. | Compare utility customer commitments, tariff collateral, and PJM accepted forecast MW. |

## Diligence Questions By Regulator / Operator

### FERC

- Does the project need new or revised interconnection agreement language?
- Is the load using the transmission system for backup, balancing, ancillary services, black start, or capacity adequacy even if marketed as behind-the-meter?
- Which tariff service will the co-located load take: NITS, interim non-firm, firm contract demand, non-firm contract demand, or another final PJM-approved service?
- Is the project relying on a tariff provision that is still pending, contested, or subject to rehearing?
- Has FERC accepted, rejected, or required further compliance on the relevant PJM tariff?

### PJM

- Is the load included in a utility load forecast adjustment, and is it firm or non-firm?
- Does the project create transmission violations under N-1, N-1-1 thermal, voltage magnitude, or voltage drop analysis?
- Does a service date depend on a named RTEP project, competitive window, or EIT generation project?
- Is the load curtailable in a way PJM can operationally rely on, or is flexibility only a commercial claim?
- Are capacity adequacy and transmission adequacy both solved, or only one?

### PUCO / AEP Ohio

- Is the project grandfathered, under Schedule DCT, or only in the inquiry/study pipeline?
- Did the customer sign LOA/ESA within the required window and post required collateral?
- Is the project in AEP Cluster 1, 2, or 3?
- Does the project depend on 2025W1-570 or another PJM-selected regional solution?
- Has AEP submitted the signed load to PJM, and did PJM identify additional upgrades?

### Virginia SCC / Dominion

- Is the customer in GS-5 or grandfathered outside it?
- Is the load above the 25 MW GS-5 threshold or the proposed 100 MW queue-process applicability threshold?
- Does the customer have a CLOA/ESA, projected connection date, and assigned DP request stage?
- Is the individual delivery-point request capped at or below 300 MW?
- Is the cost allocation direct, collateralized, or still subject to future SCC allocation proposals?

## Red Flags

- Press release says "secured power" but no docket, tariff, ESA/LOA, interconnection agreement, or utility filing names the MW.
- Claimed behind-the-meter project still relies on grid backup, black start, balancing, ancillary services, or capacity market treatment that is not paid for.
- Project cites a FERC/PJM tariff path that is still pending, partially rejected, or under rehearing.
- MW appears in a utility or developer announcement but not in accepted PJM load forecast, RTEP, state PUC docket, or signed service agreement.
- Data-center queue position exists, but regional upgrades move the in-service date to 2031 or later.
- Customer can reduce/cancel load without enough collateral, exit fee, or reassignment protection to prevent stranded cost.
- Utility study assumes adequate generation supply but explicitly does not evaluate generation adequacy or wholesale price impact.
- Project depends on a named regional transmission project that PJM has not selected, approved, or placed in RTEP.
- "Flexible load" claim is not backed by operational telemetry, curtailment priority, contractual penalties, and tariff-recognized service class.
- Retail tariff solves distribution cost but leaves PJM capacity, transmission, or interconnection exposure unresolved.

## Kill Conditions

Kill or demote a campus row if any of the following are true after two focused source passes:

- No primary or official source verifies named MW.
- No primary or official source verifies the load-serving path: grid, co-location, behind-the-meter, or hybrid.
- The relevant FERC/PJM tariff remains pending or rejected, and the project depends on that tariff to energize.
- A required regional transmission project is not selected or slips beyond the underwritten energization date.
- State PUC/SCC/PUCO record shows the customer did not sign, post collateral, or maintain queue position.
- The project is included only in non-firm or speculative load forecast categories and has no signed ESA/LOA/interconnection document.
- The project depends on curtailment/flexibility but has no tariff-recognized curtailment product or enforcement mechanism.
- Cost allocation is unresolved and exposed non-data-center customers remain likely to challenge or appeal.
- The claimed "clean firm" power is only an annual matching PPA and does not change time-to-energize or grid deliverability.
- The asset's official source confirms generation adequacy was outside the scope of the study used to justify the service date.

## Next 72-Hour Work Queue

1. Pull FERC eLibrary sheets for `RM26-4`, `EL25-49`, `ER26-1088`, `ER26-1479`, `ER24-2172`, `EL26-30`, and `ER26-1563` after the June 18, 2026 FERC open meeting.
2. For AEP Ohio, pull the underlying PUCO documents linked from AEP's DCT page: Opinion & Order, approved stipulation, February 2026 update, and Schedule DCT.
3. For Dominion, pull post-hearing `PUR-2026-00011` records and the tariff-compliance sheets implementing GS-5 under `PUR-2025-00058`.
4. Build an asset ledger with one row each for Susquehanna, a generic PJM co-location tariff row, Central Ohio AEP queue, Dominion GS-5/queue, and one EIT generation project once PJM lists candidates.
5. Force one demotion into the public sample: Susquehanna should be framed as "contested primary-verified," not as proof of power-secured AI campus.

## Bottom Line For The Ultra Rebuild

The regulatory spine changes the product from "AI campuses need power" to "show me the docket proof that this campus can energize." That is the sellable diligence wedge. In PJM, Ohio, and Virginia, the official record is already rich enough to build a real verification ledger: federal co-location rules, PJM compliance dockets, AEP/PUCO financial-commitment filters, and Dominion/SCC large-load rate and queue rules.

Any Vaticinus public artifact should show at least one promoted row, one unresolved row, and one demoted/refuted row. Otherwise it will read like marketing again.
