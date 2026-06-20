#!/usr/bin/env python3
"""Build the public AI campus power-claim diligence dossier.

This is a deterministic artifact builder. It turns the five specialist
workstreams into a public report without exposing internal model or workflow
labels on the deployed page/PDF.
"""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path


OUT = Path(__file__).resolve().parent


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def para(text: str) -> str:
    return f"<p>{esc(text)}</p>"


def cells(row: list[str]) -> str:
    return "".join(f"<td>{esc(x)}</td>" for x in row)


def table(headers: list[str], rows: list[list[str]], widths: list[str] | None = None) -> str:
    width_attr = widths or [""] * len(headers)
    head = "".join(
        f'<th style="width:{esc(width_attr[i])}">{esc(h)}</th>'
        for i, h in enumerate(headers)
    )
    body = "".join(f"<tr>{cells(row)}</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


DOCKETS = [
    {
        "id": "RM26-4-000",
        "jurisdiction": "FERC / interstate transmission",
        "status": "primary_verified",
        "issue": "Large-load interconnection rulemaking for data centers and other significant loads.",
        "next": "Watch the June 2026 Commission action and then the comment, rehearing, or compliance schedule.",
        "source": "https://www.ferc.gov/rm26-4",
    },
    {
        "id": "AD24-11-000",
        "jurisdiction": "FERC / co-location technical conference",
        "status": "primary_verified",
        "issue": "Technical record for large loads co-located at generating facilities.",
        "next": "Use as background when reviewing PJM co-location filings and project-specific claims.",
        "source": "https://www.ferc.gov/news-events/events/commissioner-led-technical-conference-regarding-large-loads-co-located",
    },
    {
        "id": "ER24-2172",
        "jurisdiction": "FERC / PJM",
        "status": "contested_primary_verified",
        "issue": "PJM/Susquehanna/Talen/Amazon ISA amendment rejected without prejudice.",
        "next": "Pull follow-on filings before treating Susquehanna as clean proof of power-secured capacity.",
        "source": "https://www.ferc.gov/sites/default/files/2024-11/20241101-3061_ER24-2172-000.pdf",
    },
    {
        "id": "EL25-49 / EL25-20 / AD24-11",
        "jurisdiction": "FERC / PJM",
        "status": "primary_verified",
        "issue": "PJM co-located load rules, transmission service treatment, and cost allocation.",
        "next": "Monitor compliance filings, rehearing, and paper-hearing replacement-rate issues.",
        "source": "https://www.ferc.gov/news-events/news/ferc-directs-nations-largest-grid-operator-create-new-rules-embrace-innovation-and",
    },
    {
        "id": "ER26-1088",
        "jurisdiction": "FERC / PJM",
        "status": "primary_verified",
        "issue": "PJM 30-day compliance filing from the co-location order; accepted in part and rejected in part.",
        "next": "Track further compliance after the April 2026 order.",
        "source": "https://www.ferc.gov/news-events/news/summaries-april-2026-commission-meeting",
    },
    {
        "id": "ER26-1479",
        "jurisdiction": "FERC / PJM",
        "status": "pending_primary_path",
        "issue": "PJM 60-day co-located-load tariff revisions covering BTM generation and transmission services.",
        "next": "Await FERC merits order and effective tariff language.",
        "source": "https://www.pjm.com/library/governing-documents/effective-documents",
    },
    {
        "id": "ER26-1563",
        "jurisdiction": "FERC / PJM",
        "status": "primary_verified_supply_side",
        "issue": "PJM Expedited Interconnection Track for shovel-ready generation projects.",
        "next": "Watch accepted EIT projects and whether any are tied to named large-load/data-center capacity.",
        "source": "https://www.ferc.gov/news-events/news/commissioner-rosners-concurrence-order-accepting-tariff-revisions-re-pjm-0",
    },
    {
        "id": "EL26-30",
        "jurisdiction": "FERC / PJM",
        "status": "source_verified_to_primary_lead",
        "issue": "Independent Market Monitor complaint on reliability and capacity treatment of large data-center loads.",
        "next": "Pull the latest docket sheet for order, settlement, dismissal, or consolidation.",
        "source": "https://www.pjm.com/-/media/DotCom/documents/ferc/filings/2025/20251125-el26-30-000.pdf",
    },
    {
        "id": "24-0508-EL-ATA",
        "jurisdiction": "PUCO / AEP Ohio",
        "status": "primary_verified",
        "issue": "Data-center tariff requiring binding commitments and collateral for large data-center load.",
        "next": "Track compliance tariff, rehearing, appeal, and AEP load updates.",
        "source": "https://www.aepohio.com/company/about/rates/data-center-tariff/",
    },
    {
        "id": "AEP DCT load-study letter",
        "jurisdiction": "Ohio / PJM",
        "status": "source_verified_official",
        "issue": "36 sites totaling 13,022.7 MW requested formal study; all require regional upgrades.",
        "next": "Compare signed contracts, PJM RTEP, and AEP cluster service dates.",
        "source": "https://www.aepohio.com/lib/docs/ratesandtariffs/ohio/AEP-Ohio_DCT_Load_Study_Letter_25.11.7.pdf",
    },
    {
        "id": "PUR-2025-00058",
        "jurisdiction": "Virginia SCC / Dominion",
        "status": "primary_verified",
        "issue": "GS-5 large-load class for 25 MW or larger customers, effective 2027-01-01.",
        "next": "Pull final Dominion tariff sheets and future cost-allocation filings.",
        "source": "https://www.scc.virginia.gov/about-the-scc/newsreleases/release/scc-issues-order-on-dev-biennial-review-2025/scc-rules-in-dev-biennial-review-case.html",
    },
    {
        "id": "PUR-2026-00011",
        "jurisdiction": "Virginia SCC / Dominion",
        "status": "primary_verified_process",
        "issue": "Large-load connection queue process standards for data-center delivery-point requests.",
        "next": "Pull post-hearing orders and match requests to named campus rows.",
        "source": "https://www.scc.virginia.gov/docketsearch/DOCS/8%40n101%21.PDF",
    },
    {
        "id": "PJM 2026 load forecast",
        "jurisdiction": "PJM",
        "status": "primary_verified_planning",
        "issue": "Firm vs non-firm large-load adjustments are now explicit in the planning record.",
        "next": "Compare utility submissions with accepted forecast values and RTEP upgrades.",
        "source": "https://www.pjm.com/-/media/DotCom/library/reports-notices/load-forecast/2026-load-report.pdf",
    },
    {
        "id": "PJM CIFP large-load additions",
        "jurisdiction": "PJM stakeholder process",
        "status": "primary_verified",
        "issue": "Board/stakeholder process for integrating large loads reliably.",
        "next": "Track manual changes, tariff filings, and final board actions.",
        "source": "https://www.pjm.com/committees-and-groups/cifp-lla",
    },
    {
        "id": "NERC emerging large loads",
        "jurisdiction": "NERC / reliability",
        "status": "primary_verified_event",
        "issue": "Reliability vocabulary for large-load behavior, sudden load drops, voltage, and frequency sensitivity.",
        "next": "Pull conference materials and map reliability concerns to project-specific rows.",
        "source": "https://www.ferc.gov/news-events/events/north-american-electric-reliability-corporation-emerging-large-loads-technical",
    },
]


PROJECTS = [
    {
        "name": "AWS / Talen Susquehanna data campus",
        "market": "PJM, Pennsylvania",
        "capacity": "Large co-located load tied to Susquehanna nuclear; treat larger multi-phase claims as live but not clean.",
        "status": "contested_primary_verified_asset",
        "path": "Co-located/direct-connect load model at a nuclear plant, with contested treatment of load and backup service.",
        "verified": "FERC rejected the amended ISA filings in ER24-2172 on 2024-11-01. Commercial story exists, but the docket narrows it.",
        "unresolved": "Replacement structure, enforceable MW schedule, cost allocation, backup/network service, appeal/rehearing posture.",
        "next": "Pull full ER24-2172 docket sheet and PJM co-location compliance filings before using any MW claim.",
        "implication": "The flagship refutation row: real commercial asset, not clean proof of a power-secured campus.",
    },
    {
        "name": "Constellation / Microsoft Crane Clean Energy Center",
        "market": "PJM, Pennsylvania",
        "capacity": "835 MW nuclear restart.",
        "status": "source_verified_restart_pending_nrc",
        "path": "Grid-connected nuclear restart with Microsoft 20-year PPA for PJM data-center power matching.",
        "verified": "Constellation, DOE, and NRC public pages verify the restart path and approval requirements.",
        "unresolved": "NRC approval timing, PJM deliverability, exact physical vs attribute structure, cost/schedule slippage.",
        "next": "Track NRC Crane restart filings, DOE loan milestones, and Constellation schedule updates.",
        "implication": "Strong firm-power procurement proof, but not a behind-the-meter campus proof.",
    },
    {
        "name": "Google / Brookfield Holtwood and Safe Harbor hydro",
        "market": "PJM, Pennsylvania",
        "capacity": "670 MW initial contracts; framework up to 3,000 MW across the United States.",
        "status": "source_verified_framework_regulatory_followup",
        "path": "Hydroelectric PPAs/framework supporting Google operations and 24/7 carbon-free energy goals.",
        "verified": "Brookfield/Google official agreement verifies the commercial framework.",
        "unresolved": "FERC hydro license posture, project delivery profile, incremental vs existing output, transmission constraints.",
        "next": "Pull FERC records for Holtwood and Safe Harbor, including Safe Harbor Project No. 1025.",
        "implication": "High-quality dispatchable clean-energy procurement evidence; delivery details still decide the diligence value.",
    },
    {
        "name": "Homer City Energy Campus",
        "market": "PJM, Pennsylvania",
        "capacity": "Official project page says up to 4.4 GW; GE Vernova release frames up to 4.5 GW.",
        "status": "official_lead_permit_contested_customer_unverified",
        "path": "Retired coal site converted toward on-site/adjacent gas generation for AI/HPC data centers.",
        "verified": "Official project and equipment partner sources support ambition and turbine/power-infrastructure claims.",
        "unresolved": "Named tenant, executed offtake, PA DEP permit status after appeal, gas pipeline capacity, PJM interconnection.",
        "next": "Pull PA DEP permit docket, PJM queue records, gas records, and signed tenant/offtake evidence.",
        "implication": "Too important to ignore, too incomplete to use as clean proof.",
    },
    {
        "name": "Amazon / AES Ohio 345 kV data-center service request",
        "market": "PJM, Ohio",
        "capacity": "65 MW at COD, rising to 480 MW by end of Phase I in PJM load-analysis material.",
        "status": "primary_rto_planning",
        "path": "345 kV grid service with transmission construction and service-agreement treatment.",
        "verified": "PJM presentation, FERC ER25-192 concurrence, and AES Ohio transmission-project route verify the planning spine.",
        "unresolved": "Phase II/III schedule, network-upgrade cost responsibility, OPSB/PUCO line and substation status.",
        "next": "Pull ER25-192 order and Ohio case 25-0743-EL-BLN for in-service dates and cost allocation.",
        "implication": "Clean utility/RTO-planning row and a useful contrast to splashier behind-the-meter claims.",
    },
    {
        "name": "Dominion Energy Culpeper Tech Zone buildout",
        "market": "PJM, Virginia",
        "capacity": "188 MW by 2028 and 1,164 MW by 2034 for Culpeper County/Town of Culpeper in SCC materials.",
        "status": "primary_utility_regulatory_unresolved_customer",
        "path": "230 kV transmission project, new substations, and network upgrades for data-center load.",
        "verified": "Dominion project page, SCC application, and PJM TEAC materials verify utility planning.",
        "unresolved": "Per-campus customer names, service agreements, local approvals, route opposition, substation energization schedule.",
        "next": "Pull SCC PUR-2025-00032 filings and match delivery points to county approvals and developer sites.",
        "implication": "Strong load-growth proof case; the buyer question is which campus has real service rights.",
    },
    {
        "name": "AEP Ohio / Bloom Energy fuel-cell projects for AWS and Cologix",
        "market": "PJM, Ohio",
        "capacity": "Hilliard page identifies 72.9 MW solid oxide fuel-cell facility for Amazon onsite demand.",
        "status": "primary_local_plus_company_mw_partial",
        "path": "On-site natural-gas fuel cells intended to serve data centers while grid capacity is constrained.",
        "verified": "AEP company release, Hilliard local project page, and PUCO public notice validate the pattern.",
        "unresolved": "PUCO case/order, Cologix facility MW, tariff treatment, gas supply terms, whether fuel cells reduce network obligations.",
        "next": "Pull PUCO onsite-generation order and site-by-site tariff filings.",
        "implication": "Concrete bridge-power pattern; only partially quantified until PUCO and second-site records are extracted.",
    },
    {
        "name": "Socrates North and South Power Solution Facilities",
        "market": "PJM / AEP Ohio region",
        "capacity": "Two 200 MW power-generation sites, 400 MW combined.",
        "status": "primary_regulator_btm_counterparty_unverified",
        "path": "Behind-the-meter natural-gas generation facilities for adjacent data-center load.",
        "verified": "OPSB says Socrates South will serve adjacent data-center load and not connect physically to the grid.",
        "unresolved": "Exact load owner, North facility OPSB status, gas-pipeline permits, air permit conditions, COD by facility.",
        "next": "Pull OPSB case documents for North and South and match applicant, consuming entity, pipeline applications, and COD.",
        "implication": "One of the cleaner BTM patterns, but customer identity and gas permits are still gates.",
    },
    {
        "name": "Apollo Power Generation Facility",
        "market": "Wood County, Ohio",
        "capacity": "350 MW natural-gas-fired generation plus about 120 MW of battery energy storage.",
        "status": "primary_regulator_btm_approved",
        "path": "Behind-the-meter facility serving adjacent data-center load; OPSB says no physical grid connection.",
        "verified": "OPSB authorization and case 25-973-EL-BGN verify the facility and adjacent load claim.",
        "unresolved": "Liames beneficial owner/end customer, Ohio EPA air permit, gas pipeline permits, enforceable COD, battery operation.",
        "next": "Pull OPSB filings, Ohio EPA permit materials, and Liames corporate linkage before naming a hyperscaler.",
        "implication": "Strong approved BTM gas-plus-storage comparison row; customer identity remains the first buyer question.",
    },
    {
        "name": "Meta Richland Parish data center / Entergy Louisiana",
        "market": "Louisiana / Entergy",
        "capacity": "Meta says over 2 GW of compute capacity; Entergy materials include 2,260 MW of planned generation.",
        "status": "source_verified_grid_buildout_lpsc_approved",
        "path": "Regulated utility buildout with generation, transmission, substations, storage/renewables commitments.",
        "verified": "Meta and Entergy official pages verify the scale and public utility-buildout framing.",
        "unresolved": "LPSC docket numbers, final cost allocation, expansion beyond initial service, gas-unit approvals.",
        "next": "Pull LPSC orders, service-agreement summaries, and confidential-redaction indexes.",
        "implication": "Looks power-secured in narrative, but is a regulated utility mega-build with approval and cost-allocation risk.",
    },
    {
        "name": "Meta / Constellation Clinton Clean Energy Center",
        "market": "Illinois / MISO",
        "capacity": "1,121 MW Meta/Constellation announcement; Clinton reactor page lists up to 1,092 MW before uprate context.",
        "status": "source_verified_nuclear_ppa_not_campus_power",
        "path": "20-year nuclear PPA/corporate nuclear-energy agreement for output/attributes.",
        "verified": "Meta and Constellation official sources verify the PPA and Clinton operations/relicensing link.",
        "unresolved": "Physical vs virtual/attribute-heavy structure, NRC/license milestones, MISO deliverability relevance.",
        "next": "Pull NRC Clinton license/relicensing records and MISO deliverability artifacts.",
        "implication": "Evidence of firm nuclear procurement, not evidence that a specific AI campus can energize faster.",
    },
    {
        "name": "Lancium / Crusoe Stargate 1 Abilene campus",
        "market": "ERCOT, Texas",
        "capacity": "Crusoe announced initial 200 MW; Lancium later describes 1.2 GW grid interconnect and onsite gas generation.",
        "status": "company_verified_comparison_primary_records_pending",
        "path": "ERCOT grid interconnect plus claimed onsite gas, storage, renewables, and power orchestration.",
        "verified": "Lancium and Crusoe official pages verify company claims and the Abilene comparison case.",
        "unresolved": "ERCOT interconnection record, TCEQ permit, direct offtake documentation, fully energized vs staged 1.2 GW.",
        "next": "Pull ERCOT interconnection and TCEQ air-permit records; split Abilene facts from national expansion claims.",
        "implication": "Useful outside-PJM comparison for speed and packaging, but cannot be imported into PJM diligence without records.",
    },
]


DEMOTIONS = [
    ["Quantum Loophole Frederick County", "demoted_press_release_site_lead", "Real site narrative, but this pass did not verify named tenant offtake, enforceable MW, interconnection service, utility upgrades, or current permit status."],
    ["EdgeCore Culpeper", "demoted_site_verified_power_path_unresolved", "Campus and load-intensity claim are visible, but project-specific service agreement and firm generation/path evidence remain unresolved."],
    ["Homer City as already power-secured", "demoted_scale_verified_customer_and_permit_risk", "Scale and project ambition are visible. Tenant, final permits, gas, and interconnection facts are not yet clean."],
    ["Stargate national expansion claims", "demoted_macro_expansion_claim", "Abilene has company evidence. National claims blend staged development, power procurement, and speculative site selection."],
]


STATUS_ROWS = [
    ["press_lead", "Mentioned in media, marketing, or rumor.", "URL only; not decision-grade."],
    ["official_claim", "Company, utility, agency, or project owner makes the claim.", "Official source naming project and at least one key field."],
    ["source_verified", "Official source verifies the claim but not the underlying record.", "Official source plus extracted field."],
    ["primary_docket_verified", "Primary regulatory/RTO/PUC/local record verifies a key field.", "Docket, order, queue, permit, tariff, or filed agreement."],
    ["counterparty_verified", "Official source names buyer, utility, offtaker, tenant, or PPA counterparty.", "Official source naming both sides and deal type."],
    ["mw_claim_verified", "Capacity figure is verified, but not necessarily energizable.", "MW tied to source, date, and scope."],
    ["power_path_verified", "Public record identifies grid service, co-location, BTM, PPA, or framework path.", "Source says how power reaches or matches the load."],
    ["time_to_power_plausible", "Evidence chain supports a reasonable energization window.", "MW, path, counterparty, regulatory status, and next dependency."],
    ["contested", "Commercial claim exists, but official record disputes it.", "Order, protest, appeal, tariff dispute, permit objection, or contradictory source."],
    ["unresolved_interconnection_risk", "MW/customer/project is real, but queue, upgrades, or deliverability are incomplete.", "Missing or pending interconnection/network-upgrade source."],
    ["demoted_missing_link", "A decisive field is missing after focused source passes.", "Missing-field note and next attempted source."],
    ["refuted", "Public evidence contradicts the marketed claim.", "Contradictory primary/official source."],
]


ICPS = [
    ["1", "Infrastructure investors underwriting AI/data-center platforms", "Partner, IC, head of digital infrastructure", "Commit equity/debt to campus, developer, generation JV, or acquisition", "Delay, reprice, condition, hedge, or reject."],
    ["2", "Lenders and credit investors", "Credit committee, project finance lead", "Size debt, covenants, draw schedule, or reserves", "Add evidence milestones and conditions precedent."],
    ["3", "Municipalities and economic-development bodies", "City/county administrator, planning lead", "Approve zoning, incentives, infrastructure, water/cooling, or grid coordination", "Demand missing evidence, phase approvals, or reject unsupported claims."],
    ["4", "Landowners and smaller developers", "Principal, CEO, head of development", "Sell, option, JV, or market a site as AI/data-center ready", "Convert the pitch into a verified data room or demote it first."],
    ["5", "Power developers packaging firm power", "Commercial origination, corp dev", "Choose which AI offtake, PPA, co-location, generation, or storage path to pursue", "Prioritize sites/customers where power can be evidenced fastest."],
    ["6", "Data-center developers below top-tier hyperscale sophistication", "COO, CDO, site acquisition, power procurement", "Market entry, campus phasing, utility negotiations, tenant commitment", "Shift from land/fiber screen to time-to-energize risk ranking."],
    ["7", "Strategic AI infrastructure buyers", "Infrastructure, compute procurement, finance", "Reserve capacity, sign colocation, support JV, or prepay", "Require evidence before reservation or prepay."],
    ["8", "Utilities/RTO-facing advisors and public agencies", "Regulatory affairs, planning, policy", "Track co-location, large-load, and cost-allocation disputes", "Build watchlists around public dockets and escalation thresholds."],
]


PRICING = [
    ["Free proof memo", "USD 0", "One public sample row and label legend.", "Prospect names a live asset or decision."],
    ["Design-partner sprint", "USD 12k-18k", "One market or 3-7 buyer-provided assets.", "Buyer has budget owner plus decision in 3-12 months."],
    ["Standard diligence sprint", "USD 25k-40k", "One market or 5-12 assets with full dossier and watchlist.", "Committee, approval, financing, or partner decision."],
    ["Portfolio screen", "USD 60k-120k", "15-40 assets across 2-4 markets.", "Buyer has portfolio exposure or acquisition pipeline."],
    ["Monitoring subscription", "USD 6k-15k/month", "Docket/source monitoring for selected assets/markets.", "Diligence creates recurring watch need."],
    ["Enterprise/API feed", "USD 150k+/year", "Structured campus power-claim database and alert feed.", "Repeated asset-review workflow exists."],
]


WATCHLIST = [
    ["P1-CANONICAL", "Original scored claim", "source_verified", "scorekeeper", "monthly/quarterly", "Do not edit; score on 2028-12-31."],
    ["P1-DEMAND-LBNL", "DOE/LBNL data-center load projection", "primary_verified", "grid_equipment", "monthly", "Watch updates to data-center electricity share and 2028 scenarios."],
    ["P1-FERC-RM26-4", "FERC large-load interconnection rulemaking", "primary_verified", "docket", "daily until action", "Escalate if FERC creates or delays large-load standards."],
    ["P1-PJM-COLOCATION", "PJM co-located load framework", "primary_verified", "docket", "daily/weekly", "Escalate on approved tariff, protest, or rejection."],
    ["P1-TALEN-SUSQUEHANNA", "AWS/Talen Susquehanna", "contested_primary_verified_asset", "docket", "daily/weekly", "Use as refutation row until final path is verified."],
    ["P1-CRANE-MICROSOFT", "Constellation/Microsoft Crane", "source_verified_restart_case", "projects", "weekly/monthly", "Watch NRC restart, DOE financing, PJM deliverability."],
    ["P1-GOOGLE-BROOKFIELD-HYDRO", "Google/Brookfield hydro", "source_verified_framework", "projects", "weekly/monthly", "Tie framework to FERC hydro project records."],
    ["P1-HOMER-CITY", "Homer City Energy Campus", "official_lead_not_customer_verified", "projects", "weekly", "Do not promote until tenant/offtake, permits, gas, and PJM path are verified."],
    ["P1-AES-OHIO-AMAZON", "Amazon/AES Ohio service request", "primary_rto_planning", "docket", "weekly", "Extract ESA, network upgrades, and cost allocation."],
    ["P1-DOMINION-CULPEPER", "Dominion Culpeper Tech Zone", "primary_utility_regulatory", "local_permits", "weekly", "Tie aggregate load to named campuses and delivery points."],
    ["P1-SOCRATES-WILL-POWER", "Socrates BTM gas plant", "primary_regulator_plus_company", "local_permits", "weekly", "Verify customer and gas/air permits."],
    ["P1-APOLLO-OHIO", "Apollo BTM gas and battery", "primary_regulator_lead", "local_permits", "weekly", "Verify Liames/end customer and EPA/gas permits."],
    ["P1-META-RICHLAND", "Meta Richland / Entergy", "demoted_comparison_case", "red_team", "weekly/monthly", "Treat as grid-buildout comparison unless LPSC filings prove a clean path."],
    ["P1-TRANSFORMER-LEADTIMES", "Transformer/interconnection delay kill leg", "lead_context", "grid_equipment", "weekly/monthly", "Escalate if lead times normalize below roughly 24 months."],
    ["P1-BUYER-PIPELINE", "Commercial wedge health", "operating_metric", "buyer_ops", "weekly/monthly", "Kill/demote wedge if qualified calls produce no buyer assets."],
]


CHILD_CLAUSES = [
    ["P1", "canonical", "By 2028-12-31, will the original firm-power siting claim resolve true?", "0.52", "2028-12-31"],
    ["P1-C1", "child_clause", "Will at least two hyperscaler-scale US campuses be primary/official verified as having secured BTM or direct firm clean generation as a core siting advantage?", "0.46", "2028-12-31"],
    ["P1-C2", "child_clause", "Will at least one FERC, PJM, PUC, or utility order materially change a named 100 MW plus campus path?", "0.62", "2027-12-31"],
    ["P1-C3", "child_clause", "Will the sample dossier contain at least one public AI campus power claim demoted or contested because primary review failed?", "0.70", "2027-06-30"],
    ["P1-C4", "child_clause", "Will transformer, interconnection, or HV equipment lead-time evidence remain generally above roughly 24 months in main AI data-center markets?", "0.58", "2027-12-31"],
    ["P1-C5", "child_clause", "Will one firm-power provider announce a 100 MW plus direct data-center offtake where time-to-energize or interconnection bypass is named?", "0.50", "2027-12-31"],
    ["P1-C6", "child_clause", "Will the diligence offer receive at least one buyer-provided asset, docket set, site list, or paid/LOI-backed sprint request by 2026-09-30?", "0.44", "2026-09-30"],
]


SOURCE_GROUPS = [
    ["Demand and load growth", "DOE/LBNL report release", "https://www.energy.gov/articles/doe-releases-new-report-evaluating-increase-electricity-demand-data-centers"],
    ["Demand and load growth", "DOE demand growth hub", "https://www.energy.gov/policy/electricity-demand-growth-resource-hub"],
    ["Federal large-load rules", "FERC RM26-4", "https://www.ferc.gov/rm26-4"],
    ["Federal large-load rules", "FERC large-load action timing", "https://www.ferc.gov/news-events/news/ferc-act-large-load-interconnection-docket-june-2026"],
    ["PJM co-location", "FERC PJM co-location order", "https://www.ferc.gov/news-events/news/ferc-directs-nations-largest-grid-operator-create-new-rules-embrace-innovation-and"],
    ["PJM co-location", "FERC ER24-2172 order", "https://www.ferc.gov/sites/default/files/2024-11/20241101-3061_ER24-2172-000.pdf"],
    ["PJM co-location", "PJM effective documents", "https://www.pjm.com/library/governing-documents/effective-documents"],
    ["Ohio large load", "AEP Ohio data-center tariff", "https://www.aepohio.com/company/about/rates/data-center-tariff/"],
    ["Ohio large load", "AEP DCT load-study letter", "https://www.aepohio.com/lib/docs/ratesandtariffs/ohio/AEP-Ohio_DCT_Load_Study_Letter_25.11.7.pdf"],
    ["Virginia large load", "Virginia SCC GS-5 order page", "https://www.scc.virginia.gov/about-the-scc/newsreleases/release/scc-issues-order-on-dev-biennial-review-2025/scc-rules-in-dev-biennial-review-case.html"],
    ["Virginia large load", "Dominion Culpeper Tech Zone", "https://www.dominionenergy.com/en/About/Delivering-Energy/Electric-Projects/Power-Line-Projects/Culpeper-Tech-Zone"],
    ["Nuclear and hydro procurement", "Constellation Crane / Microsoft", "https://www.constellationenergy.com/news/2024/Constellation-to-Launch-Crane-Clean-Energy-Center-Restoring-Jobs-and-Carbon-Free-Power-to-The-Grid.html"],
    ["Nuclear and hydro procurement", "DOE Crane Restart", "https://www.energy.gov/edf/crane-restart"],
    ["Nuclear and hydro procurement", "NRC Crane Clean Energy Center", "https://www.nrc.gov/info-finder/reactors/ccec"],
    ["Nuclear and hydro procurement", "Brookfield and Google hydro agreement", "https://bep.brookfield.com/press-releases/bep/brookfield-and-google-sign-hydro-framework-agreement-deliver-3000-mw-homegrown"],
    ["Project leads", "Homer City project overview", "https://www.homercityredevelopment.com/project-overview"],
    ["Project leads", "Williams Apollo project", "https://www.williams.com/expansion-project/apollo-power-generation-project/"],
    ["Project leads", "Crusoe 200 MW Abilene announcement", "https://www.crusoe.ai/resources/newsroom/crusoe-200mw-ai-data-center"],
]


CSS = """
@font-face{font-family:'Gt Standard';font-weight:400;font-style:normal;font-display:swap;src:url('https://cdn.prod.website-files.com/68907168d294618a86ec6518/689b297557d89256a5697b72_GT-Standard-L-Standard-Regular.woff2') format('woff2');}
@font-face{font-family:'Gt Standard';font-weight:500;font-style:normal;font-display:swap;src:url('https://cdn.prod.website-files.com/68907168d294618a86ec6518/689b2975a12fc701f9f074a9_GT-Standard-L-Standard-Medium.woff2') format('woff2');}
@font-face{font-family:'Gt Standard Mono';font-weight:500;font-style:normal;font-display:swap;src:url('https://cdn.prod.website-files.com/68907168d294618a86ec6518/689b29750af0e8f994b5a45e_GT-Standard-Mono-Narrow-Medium.woff2') format('woff2');}
:root{--page:#fbfaf7;--ink:#151515;--text:#33312d;--mut:#706c65;--quiet:#9b958d;--line:#d9d4cc;--accent:#244fd8;--soft:#eef2ff;--paper:#f2f0ea;}
@page{size:Letter;margin:17mm 16mm 17mm 16mm;@bottom-left{content:"Vaticinus";font-family:'Gt Standard Mono',monospace;font-size:7.2pt;color:#a7a19a;}@bottom-center{content:counter(page);font-family:'Gt Standard Mono',monospace;font-size:7.8pt;color:#a7a19a;}}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact;}
body{margin:0;background:var(--page);color:var(--text);font-family:'Gt Standard',Arial,sans-serif;font-size:9.45pt;line-height:1.42;}
h1,h2,h3,h4{margin:0;color:var(--ink);font-weight:500;line-height:1.06;letter-spacing:0;}
h1{max-width:650px;font-size:32pt;}
h2{font-size:17pt;}
h3{font-size:11.5pt;margin:12px 0 5px;}
h4{font-family:'Gt Standard Mono',monospace;color:var(--mut);font-size:7.5pt;margin:10px 0 4px;text-transform:uppercase;letter-spacing:.04em;}
p{margin:0 0 7px;}
a{color:var(--accent);text-decoration:none;}
.mono{font-family:'Gt Standard Mono',monospace;font-weight:500;}
.cover{min-height:239mm;display:flex;flex-direction:column;}
.mast{display:flex;justify-content:space-between;align-items:baseline;border-top:2px solid var(--ink);border-bottom:1px solid var(--line);padding:8px 0 10px;color:var(--mut);font-size:7.6pt;}
.mast span:last-child{color:var(--accent);}
.title-block{padding-top:31mm;}
.sub{max-width:620px;margin-top:10px;color:var(--mut);font-size:13pt;line-height:1.34;}
.frame{margin-top:auto;display:grid;grid-template-columns:1.08fr .92fr;gap:18px;border-top:2px solid var(--ink);border-bottom:1px solid var(--line);padding:14px 0;}
.label{display:block;margin-bottom:4px;color:var(--accent);font-family:'Gt Standard Mono',monospace;font-size:7.2pt;font-weight:500;text-transform:uppercase;letter-spacing:.04em;}
.meta{display:grid;gap:7px;font-size:8.7pt;}
.meta div{border-top:1px solid var(--line);padding-top:6px;}
.meta span{display:block;margin-bottom:1px;color:var(--quiet);font-family:'Gt Standard Mono',monospace;font-size:7pt;text-transform:uppercase;letter-spacing:.04em;}
.page{page-break-before:always;}
.rule{border-top:2px solid var(--ink);padding-top:10px;margin-bottom:12px;}
.lede{max-width:670px;color:var(--ink);font-size:11.2pt;line-height:1.38;}
.callout{margin:11px 0;padding:10px 12px;border-left:3px solid var(--accent);background:var(--soft);}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;}
.box{border-top:1.5px solid var(--ink);padding-top:8px;margin-top:10px;break-inside:avoid;}
.box p{color:var(--mut);}
.big-number{font-size:24pt;color:var(--accent);line-height:1;font-weight:500;}
table{width:100%;border-collapse:collapse;table-layout:fixed;margin:8px 0 10px;border-top:1.5px solid var(--ink);border-bottom:1px solid var(--line);font-size:7.65pt;line-height:1.24;}
th,td{text-align:left;vertical-align:top;padding:4.5px 5px;overflow-wrap:anywhere;}
thead th{border-bottom:1px solid var(--ink);color:var(--mut);font-family:'Gt Standard Mono',monospace;font-size:6.85pt;font-weight:500;text-transform:uppercase;letter-spacing:.03em;}
tbody tr+tr{border-top:1px solid var(--line);}
tbody tr:nth-child(even){background:rgba(242,240,234,.62);}
tr{break-inside:avoid;}
.project-head{display:grid;grid-template-columns:1fr 160px;gap:16px;align-items:start;border-top:2px solid var(--ink);padding-top:10px;margin-bottom:11px;}
.status{font-family:'Gt Standard Mono',monospace;color:var(--accent);font-size:8pt;text-align:right;overflow-wrap:anywhere;}
.facts{display:grid;grid-template-columns:145px 1fr;gap:9px 13px;border-top:1px solid var(--line);padding-top:8px;}
.facts dt{font-family:'Gt Standard Mono',monospace;color:var(--mut);font-size:7.1pt;text-transform:uppercase;letter-spacing:.04em;}
.facts dd{margin:0;}
.split-page{display:grid;grid-template-columns:1fr 1fr;gap:14px;}
.source-list td:nth-child(3){font-family:'Gt Standard Mono',monospace;font-size:6.8pt;}
.footer-note{margin-top:8px;color:var(--quiet);font-family:'Gt Standard Mono',monospace;font-size:7pt;}
"""


def section(title: str, inner: str, extra_class: str = "") -> str:
    klass = f"page {extra_class}".strip()
    return f'<section class="{klass}"><div class="rule"><h2>{esc(title)}</h2></div>{inner}</section>'


def build_html() -> str:
    parts: list[str] = []
    parts.append(f"""
<section class="cover">
  <div class="mast mono"><span>Vaticinus analyst dossier</span><span>Full public report</span></div>
  <div class="title-block">
    <h1>AI Campus Power-Claim Diligence</h1>
    <div class="sub">Our analyst team tested announced AI and data-center campus power claims against public dockets, utility records, permitting materials, and official company sources.</div>
  </div>
  <div class="frame">
    <div><span class="label">Frame</span>Power scarcity is now consensus. The sellable question is narrower: does a named campus prove capacity, counterparty, power path, and regulatory status before a buyer treats the claim as real?</div>
    <div class="meta">
      <div><span>Issued</span>2026-06-17</div>
      <div><span>Prepared by</span>Our analyst team</div>
      <div><span>Scope</span>PJM/Mid-Atlantic first, with Ohio, Louisiana, Illinois, and Texas comparisons</div>
      <div><span>Artifacts</span>Docket spine, project ledger, refute gate, buyer offer, monitoring scorecard</div>
    </div>
  </div>
</section>
""")

    verdict = """
<p class="lede">The broad thesis survived only after being narrowed. "AI/data-center power is scarce" is no longer a proprietary insight. DOE/LBNL, FERC, PJM, utilities, hyperscalers, infrastructure capital, and site-selection incumbents all see the problem.</p>
<div class="grid3">
  <div class="box"><div class="big-number">78%</div><span class="label">Structure</span><p>Probability that time-to-power and power rights matter more than ordinary land/fiber for AI campuses through 2028.</p></div>
  <div class="box"><div class="big-number">12%</div><span class="label">Generic edge</span><p>Probability that the broad insight is meaningfully unpriced. The headline thesis is already public.</p></div>
  <div class="box"><div class="big-number">42%</div><span class="label">Commercial wedge</span><p>Probability that a 10-business-day diligence sprint can close a first design partner if sold to exposed buyers with named assets.</p></div>
</div>
<div class="callout"><span class="label">Operating verdict</span>Do not sell a generic AI-power market report. Sell a bounded verification sprint that confirms, contests, demotes, or kills buyer-provided campus power claims.</div>
<div class="grid2">
  <div class="box"><h3>Bad pitch</h3><p>Power-secured AI campuses win. This is now too broad and too consensus-heavy.</p></div>
  <div class="box"><h3>Better pitch</h3><p>Before you underwrite, lend against, approve, option, reserve, or partner around a campus, test whether the named power claim survives primary-source diligence.</p></div>
</div>
"""
    parts.append(section("Executive Verdict", verdict))

    locked = """
<p class="lede">This dossier preserves the original scored forecast but changes the launch object from "power scarcity" to "power-claim verification."</p>
""" + table(
        ["Field", "Locked value"],
        [
            ["Headline", "The AI frontier moves from model access to firm-power siting."],
            ["Domain", "AI infrastructure / energy"],
            ["Structural case", "82%"],
            ["Exact dated call", "52%"],
            ["Resolves", "2028-12-31"],
            ["Metric", "Count 100 MW plus campuses with direct power-development partnerships; track announcements naming onsite firm power, geothermal, or interconnection bypass; track transformer lead times and local moratoria."],
            ["Kill", "Fewer than two qualifying hyperscaler-scale campuses by end 2028, or transformer/interconnection delays normalize below roughly 24 months in main US AI data-center markets."],
        ],
        ["26%", "74%"],
    ) + """
<div class="callout"><span class="label">Correction</span>The scored parent claim is structural. The launch product is operational: classify named campus rows by public evidence quality.</div>
"""
    parts.append(section("Locked Forecast And Correction", locked))

    method = """
<p class="lede">The rebuild used five specialist workstreams plus one integration pass. Public artifact language says "our analyst team" because the buyer should see the work, not the internal machinery.</p>
""" + table(
        ["Workstream", "Output", "What it changed"],
        [
            ["Regulatory/docket spine", "FERC, PJM, PUCO, SCC, PJM load forecast, NERC large-load surfaces.", "Turned the thesis into a docket-verification problem."],
            ["Project ledger", "12 named rows plus 4 demotions/refutations.", "Separated press-release MW from decision-grade MW."],
            ["Adversarial refute/pricing gate", "Consensus layer, strongest objections, product kill conditions.", "Demoted the broad insight and preserved only the verification wedge."],
            ["Buyer/ROI layer", "ICP ranking, offer, pricing ladder, qualification questions, deliverables.", "Converted the forecast into a paid diligence sprint."],
            ["Monitoring scorecard", "Status transitions, watchlist, cadence, child clauses, scorecard JSONL.", "Made the report a living operating system."],
            ["Integration pass", "Full dossier, PDF, site copy, source spine, deployment.", "Merged non-duplicative findings into one public artifact."],
        ],
        ["20%", "40%", "40%"],
    ) + """
<h3>Hard row rule</h3>
<p>No campus row can be called power secured unless public primary or official sources verify all four pillars: MW or capacity, counterparty/offtake, power path, and permit/regulatory status.</p>
"""
    parts.append(section("Method", method))

    parts.append(section("Status Vocabulary", table(["Status", "Meaning", "Minimum evidence"], STATUS_ROWS, ["24%", "39%", "37%"])))

    consensus = """
<p class="lede">The refute gate says the generic story is already visible. The surviving product must be narrower, more adversarial, and more useful at the point of decision.</p>
""" + table(
        ["Consensus surface", "What is already public", "What remains useful"],
        [
            ["DOE/LBNL", "Data-center demand growth and 2028 electricity-share scenarios.", "Use as demand anchor only, not edge."],
            ["FERC/PJM", "Large-load interconnection, co-location, tariff, and reliability issues are live regulatory topics.", "Track project-specific effects and status changes."],
            ["Utilities", "AEP Ohio, Dominion, and others are hardening large-load gates with tariffs, collateral, and queue procedures.", "Separate signed commitments from speculative MW."],
            ["Hyperscalers", "Microsoft, Meta, Google, Amazon, and others are actively contracting nuclear, hydro, co-located, or firm power.", "Verify whether a deal changes campus energization or only matches energy/attributes."],
            ["Infrastructure capital", "Private capital is integrating data centers plus power into platform strategy.", "Serve buyers exposed to someone else's claim or lacking hyperscaler-grade diligence."],
            ["Advisory incumbents", "CBRE, JLL, power consultants, and law firms already sell site-selection and power-procurement advice.", "Win through narrow evidence ledgers, refutation, speed, and status monitoring."],
        ],
        ["22%", "39%", "39%"],
    ) + """
<div class="callout"><span class="label">Product wedge</span>Press-release MW is not diligence-grade MW. The paid unit is a row that names the claimed MW, source of MW, counterparty, power path, docket/permit/queue status, open risk, and next check.</div>
"""
    parts.append(section("Consensus Gate", consensus))

    docket_rows = [[d["id"], d["jurisdiction"], d["status"], d["issue"], d["next"]] for d in DOCKETS[:8]]
    parts.append(section("Docket Spine: Federal And PJM", table(["Proceeding", "Jurisdiction", "Status", "Issue", "Next check"], docket_rows, ["16%", "18%", "16%", "30%", "20%"])))
    docket_rows2 = [[d["id"], d["jurisdiction"], d["status"], d["issue"], d["next"]] for d in DOCKETS[8:]]
    parts.append(section("Docket Spine: State, Utility, Planning", table(["Proceeding", "Jurisdiction", "Status", "Issue", "Next check"], docket_rows2, ["16%", "18%", "16%", "30%", "20%"])))

    for i, project in enumerate(PROJECTS, 1):
        inner = f"""
<div class="project-head"><div><span class="label">Project row {i:02d}</span><h2>{esc(project["name"])}</h2></div><div class="status">{esc(project["status"])}</div></div>
<dl class="facts">
  <dt>Market</dt><dd>{esc(project["market"])}</dd>
  <dt>Claimed capacity</dt><dd>{esc(project["capacity"])}</dd>
  <dt>Power path</dt><dd>{esc(project["path"])}</dd>
  <dt>Verified</dt><dd>{esc(project["verified"])}</dd>
  <dt>Unresolved</dt><dd>{esc(project["unresolved"])}</dd>
  <dt>Next check</dt><dd>{esc(project["next"])}</dd>
  <dt>Buyer implication</dt><dd>{esc(project["implication"])}</dd>
</dl>
"""
        parts.append(f'<section class="page">{inner}</section>')

    parts.append(section("Tempting Leads Demoted", table(["Lead", "Label", "Why not promoted"], DEMOTIONS, ["28%", "24%", "48%"])))

    buyer_offer = """
<p class="lede">The first paid offer is not a market overview. It is a 10-business-day AI Campus Power-Claim Diligence sprint for a buyer-provided asset list, market, docket set, campus proposal, loan, or approval decision.</p>
<div class="grid2">
  <div class="box"><span class="label">Entry price</span><p>USD 12k-18k for first two design partners, 50% upfront. Raise to USD 25k-40k after one anonymized sample dossier and buyer reference.</p></div>
  <div class="box"><span class="label">Minimum qualification</span><p>One named asset or docket, one budget owner, one live decision in 3-12 months, and permission to use public/non-confidential source materials.</p></div>
</div>
""" + table(
        ["Deliverable", "What it contains"],
        [
            ["Verification ledger", "Project, source URL, retrieval date, source tier, evidence span, extracted fields, open question, label."],
            ["Time-to-energize risk table", "MW, counterparty, grid/BTM path, permit/regulatory status, equipment, cooling/water, local consent, next date."],
            ["Refutation/demotion table", "At least one attractive lead that fails the hard label rule."],
            ["Action memo", "What to reserve, avoid, diligence further, negotiate, monitor, or kill."],
            ["Budget-owner summary", "One page committee-ready decision note with cost of waiting and stop rule."],
            ["30-day watchlist", "Owner, cadence, public source, threshold, escalation rule, and kill/stop condition."],
        ],
        ["28%", "72%"],
    )
    parts.append(section("Paid Offer", buyer_offer))

    parts.append(section("ICP Ranking", table(["Rank", "ICP", "Budget owner", "Live decision", "Decision changed"], ICPS, ["6%", "27%", "20%", "27%", "20%"])))
    parts.append(section("Pricing Ladder", table(["Tier", "Price", "Scope", "Conversion trigger"], PRICING, ["24%", "16%", "36%", "24%"])))

    qualification = """
<p class="lede">The discovery call must find a live decision, not perform free consulting. If the buyer cannot name an asset, docket, counterparty, site, PPA, loan, permit, land option, or approval decision, the free memo is enough.</p>
""" + table(
        ["Question", "Why it matters"],
        [
            ["Which named campus, asset list, market, docket, borrower, seller, or counterparty are you deciding on?", "No named object means no diligence sprint."],
            ["What decision has to be made in the next 3 to 12 months?", "The report must change timing, terms, approval, or monitoring."],
            ["Who owns the budget?", "Without a budget owner, the work becomes unpaid education."],
            ["What would change if MW, interconnection, PPA, permit, or co-location status is weaker than advertised?", "This identifies ROI and the action memo."],
            ["What evidence do you already have?", "RTO queue ID, FERC docket, utility filing, PPA summary, permit number, site-control document, or announcement."],
            ["What would make this a no-go after day 2?", "Protects the sprint from becoming bespoke, unbounded research."],
        ],
        ["45%", "55%"],
    )
    parts.append(section("Qualification And ROI", qualification))

    operations = """
<p class="lede">The operating system is mechanical: rows promote or demote only when source thresholds are met. Plausibility never upgrades a row.</p>
""" + table(
        ["Transition", "Exact condition"],
        [
            ["lead -> source_verified", "Official company, agency, utility, RTO/ISO, regulator, or project page confirms one material fact."],
            ["lead -> primary_verified", "Docket, queue, filing, permit, tariff, regulator order, or official agency record confirms the fact under review."],
            ["source_verified -> contested", "Primary record conflicts with or materially narrows the company/developer story."],
            ["primary_verified -> power_secured", "All four pillars are public-source verified and remaining contingencies are named with next check dates."],
            ["any active -> demoted", "Two focused source passes fail to verify MW, counterparty, power path, or permit/regulatory status."],
            ["any active -> killed", "Official cancellation, final adverse order, expired/withdrawn permit, abandoned queue, or customer/offtake termination removes the path."],
        ],
        ["32%", "68%"],
    ) + """
<div class="callout"><span class="label">Escalation</span>Same day if a primary source verifies all four pillars for a 100 MW plus campus, or if an order rejects, narrows, or materially disputes a power path.</div>
"""
    parts.append(section("Operating System", operations))

    parts.append(section("Watchlist", table(["Row", "Object", "Status", "Owner", "Cadence", "Action"], WATCHLIST, ["15%", "23%", "17%", "13%", "14%", "18%"])))
    parts.append(section("Scorecard", table(["ID", "Type", "Question", "Probability", "Resolves"], CHILD_CLAUSES, ["10%", "13%", "56%", "9%", "12%"])))

    queue = """
<p class="lede">The next work should deepen source quality before broadening the market. A good public sample needs one promoted row, one unresolved row, and one demoted/refuted row.</p>
""" + table(
        ["Window", "Task", "Owner"],
        [
            ["72 hours", "Pull FERC eLibrary sheets for RM26-4, EL25-49, ER26-1088, ER26-1479, ER24-2172, EL26-30, and ER26-1563 after the June 2026 open meeting.", "docket"],
            ["72 hours", "Pull PUCO documents linked from AEP's DCT page: order, stipulation, February 2026 update, and Schedule DCT.", "docket"],
            ["72 hours", "Pull post-hearing Virginia SCC PUR-2026-00011 records and GS-5 tariff-compliance sheets.", "local_permits"],
            ["7 days", "Separate load MW, generation MW, contracted offtake MW, and physically deliverable MW for every promoted row.", "projects"],
            ["7 days", "Build first anonymized buyer sample with Susquehanna contested, AES Ohio primary planning, and Homer City demoted/unresolved.", "editor"],
            ["30 days", "Run 20 high-fit manual outreaches plus 5 warm-path asks for the design-partner sprint.", "buyer_ops"],
        ],
        ["14%", "68%", "18%"],
    )
    parts.append(section("Next Work Queue", queue))

    source_rows = [[g, name, url] for g, name, url in SOURCE_GROUPS]
    parts.append(section("Source Spine", table(["Group", "Source", "URL"], source_rows, ["20%", "30%", "50%"]), "source-list"))

    disclaimer = """
<p class="lede">This dossier is an analyst-team public-source diligence artifact. It is not legal, engineering, tax, securities, investment, or grid-reliability advice. It does not certify interconnection, credit quality, feasibility, or project finance. Its value is the structured evidence ledger and the willingness to demote attractive claims.</p>
<div class="callout"><span class="label">Final rule</span>A story can be true and still not be decision-grade. The product earns trust by preserving that distinction.</div>
"""
    parts.append(section("Boundary", disclaimer))

    return f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>AI Campus Power-Claim Diligence</title><style>{CSS}</style></head><body>{"".join(parts)}</body></html>'


def build_markdown() -> str:
    lines = [
        "# AI Campus Power-Claim Diligence",
        "",
        "Prepared by our analyst team. Issued 2026-06-17.",
        "",
        "## Executive Verdict",
        "",
        "Power scarcity is now consensus. The sellable wedge is narrower: verify, contest, demote, or kill named AI campus power claims before a buyer treats them as real.",
        "",
        "## Hard Label Rule",
        "",
        "No campus row can be called power secured unless public primary or official sources verify MW or capacity, counterparty/offtake, power path, and permit/regulatory status.",
        "",
        "## Project Rows",
        "",
    ]
    for project in PROJECTS:
        lines += [
            f"### {project['name']}",
            "",
            f"- Market: {project['market']}",
            f"- Status: {project['status']}",
            f"- Capacity: {project['capacity']}",
            f"- Power path: {project['path']}",
            f"- Verified: {project['verified']}",
            f"- Unresolved: {project['unresolved']}",
            f"- Next check: {project['next']}",
            f"- Buyer implication: {project['implication']}",
            "",
        ]
    lines += [
        "## Source Spine",
        "",
    ]
    for group, name, url in SOURCE_GROUPS:
        lines.append(f"- {group}: {name} - {url}")
    lines.append("")
    return "\n".join(lines)


def write_sidecars() -> None:
    with (OUT / "watchlist.jsonl").open("w", encoding="utf-8") as fh:
        for row_id, obj, status, owner, cadence, action in WATCHLIST:
            fh.write(json.dumps({
                "row_id": row_id,
                "object": obj,
                "status": status,
                "owner": owner,
                "cadence": cadence,
                "action": action,
                "created_at": "2026-06-17",
            }, ensure_ascii=True) + "\n")

    with (OUT / "scorecard.jsonl").open("w", encoding="utf-8") as fh:
        for row_id, typ, question, probability, resolves in CHILD_CLAUSES:
            fh.write(json.dumps({
                "id": row_id,
                "type": typ,
                "question": question,
                "probability": float(probability),
                "resolution_date": resolves,
                "created_at": "2026-06-17",
                "do_not_edit_parent": row_id == "P1",
            }, ensure_ascii=True) + "\n")

    with (OUT / "project_ledger.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(PROJECTS[0].keys()))
        writer.writeheader()
        writer.writerows(PROJECTS)


def main() -> None:
    (OUT / "full_report.html").write_text(build_html(), encoding="utf-8")
    (OUT / "full_report.md").write_text(build_markdown(), encoding="utf-8")
    write_sidecars()
    print(f"wrote {OUT / 'full_report.html'}")
    print(f"wrote {OUT / 'full_report.md'}")
    print(f"wrote {OUT / 'watchlist.jsonl'}")
    print(f"wrote {OUT / 'scorecard.jsonl'}")
    print(f"wrote {OUT / 'project_ledger.csv'}")


if __name__ == "__main__":
    main()
