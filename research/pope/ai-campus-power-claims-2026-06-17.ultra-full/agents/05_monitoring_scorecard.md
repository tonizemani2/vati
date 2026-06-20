# Agent 5 - Monitoring, Watchlist, Operating System, And Scorecard

Generated: 2026-06-17

Mission: turn P1 into a live operating system for AI campus power-claim diligence. This file preserves the original scored claim. It does not rewrite the probability, resolution date, metric, or kill condition from `research/pope/after-ai-2026-06-17.json`.

Run mode: Codex-native operating pass, built from the Pope Mega doctrine, `FUTURE_MAP.md`, `VATI.md`, `BRIEFING.md`, `research/pope/after-ai-2026-06-17.json`, and the existing P1 Ultra files.

## Canonical Claim Lock

Do not edit this block when creating sales copy, watch rows, scorecard rows, or buyer memos.

| field | locked value |
|---|---|
| source board | `research/pope/after-ai-2026-06-17.json` |
| thesis id | `P1` |
| headline | The AI frontier moves from model access to firm-power siting. |
| domain | AI infrastructure / energy |
| vision_p | 82% |
| clause_p | 52% |
| resolves | 2028-12-31 |
| metric | Track hyperscaler and data-center developer announcements that name on-site firm power, geothermal, or interconnection bypass as the reason for site selection; count 100 MW plus campuses with direct power-development partnerships; track transformer lead times and local moratoria. |
| kill | Kill if by end 2028 fewer than two hyperscaler-scale campuses publicly secure behind-the-meter firm clean generation as a core siting advantage, or if transformer and interconnection delays normalize below roughly 24 months in the main US AI data-center markets. |

Operator translation: the broad power-scarcity story is now visible. The sellable product is not "power is scarce." The sellable product is: verify or refute whether a named AI campus power claim survives primary-source diligence before a buyer underwrites it.

## Operating Principle

No row is `power_secured` until public evidence verifies all four pillars:

1. MW or capacity.
2. Counterparty, offtake, customer, or load owner.
3. Power path: grid-connected, co-located, behind-the-meter, direct-connect, PPA, restart, generation buildout, or interconnection bypass.
4. Permit, regulatory, docket, tariff, queue, licensing, or local approval status.

If any pillar is absent, the row stays `lead`, `source_verified`, `contested`, `demoted`, or `unresolved_interconnection_risk`. This is the operating discipline. It is the product.

## Status Vocabulary

| status | meaning | allowed use |
|---|---|---|
| `lead` | Candidate found from press, search, buyer tip, trade press, or partial official source. | Can be used for research queue only. Not decision-grade. |
| `source_verified` | Official company, agency, utility, or developer source supports at least one material fact, but the underlying docket/filing/queue is not yet tied out. | Can be used in teaser as "not yet primary-diligenced." |
| `primary_verified` | Primary or official record verifies the material fact being claimed: docket, tariff, queue, permit, SEC/statutory filing, regulator order, utility filing, official project page, or official agency page. | Can be used in buyer memo, with open questions preserved. |
| `power_secured` | All four pillars are primary/official verified and remaining contingencies are named with next check dates. | Rare. Use only for rows that survive the full power-claim test. |
| `contested` | A real commercial story exists, but an order, protest, appeal, compliance filing, tariff dispute, permit objection, cost-allocation fight, or contradictory official source weakens or blocks the claim. | Use prominently. One contested row should appear in every sample dossier. |
| `unresolved_interconnection_risk` | MW/customer/project is real, but interconnection, network upgrades, cost allocation, deliverability, or behind-the-meter treatment is not resolved. | Use for rows that may become investable but are not yet clean. |
| `demoted` | After two focused source passes, at least one critical pillar remains missing, vague, press-only, or contradicted by primary records. | Keep in refutation appendix; do not use as proof of P1. |
| `killed` | The named row's thesis-relevant claim fails: capacity cancelled, permit denied without viable replacement, customer/offtake disproved, power path rejected, or original P1 kill condition becomes true. | Archive with evidence and feed the scorecard. |

## Exact Row Transition Conditions

These are mechanical. Do not promote rows by judgment alone.

| from | to | exact condition |
|---|---|---|
| `lead` | `source_verified` | An official company, agency, utility, RTO/ISO, regulator, or project page confirms one or more of: named project, MW/capacity, named customer/counterparty, power path, docket/permit/queue, or timeline. |
| `lead` | `primary_verified` | A docket, queue, filing, permit, official tariff record, regulator order, statutory filing, or official agency record confirms the specific fact under review, not merely the existence of the project. |
| `lead` | `contested` | The first primary/official record found is a rejection, protest, rehearing request, adverse staff report, permit objection, tariff dispute, cost-allocation dispute, or contradictory regulator/utility statement. |
| `lead` | `demoted` | Two focused source passes fail to verify MW, counterparty/offtake, power path, or regulatory/permit status, or the only sources remain press/trade summaries with no route to primary records. |
| `lead` | `killed` | Official source says the project is cancelled, the named capacity/customer is false, the permit or license is denied with no active replacement path, or the claimed power path cannot legally/physically serve the load. |
| `source_verified` | `primary_verified` | The official/company fact is traced to a primary record with matching project name, location, date, MW/capacity, party, and status. |
| `source_verified` | `power_secured` | All four pillars are primary/official verified, the next regulatory/permit deadline is known, and no unresolved interconnection/cost-allocation issue blocks the stated energization path. |
| `source_verified` | `contested` | A primary record conflicts with the company/developer story or puts the claimed path into an active dispute, rejection, appeal, protest, or compliance proceeding. |
| `source_verified` | `demoted` | Two source passes cannot connect the official claim to a docket, queue, permit, tariff, filing, or utility record, or a material pillar stays absent after the next-check date. |
| `primary_verified` | `power_secured` | The row has primary/official support for capacity, counterparty/offtake, power path, and permit/regulatory status, plus an explicit remaining-risk field and a dated next check. |
| `primary_verified` | `contested` | A later order, protest, rehearing, appeal, permit challenge, tariff change, or utility/regulator filing materially disputes or narrows the original verified claim. |
| `primary_verified` | `demoted` | New evidence shows the primary-verified fact is real but not thesis-relevant, such as grid buildout rather than behind-the-meter firm power, compute capacity rather than electrical capacity, or general load growth rather than a campus power path. |
| `primary_verified` | `killed` | Official cancellation, adverse final order, expired/withdrawn permit, failed license/restart, abandoned queue position, or customer/offtake termination removes the power path. |
| `contested` | `primary_verified` | The dispute is resolved by final order, compliance filing, settlement, approved tariff, permit, or other primary record that reinstates a specific verified path. |
| `contested` | `killed` | Final order or official record rejects the path and no replacement path is filed within the row's monitoring window. |
| `demoted` | `lead` | A new official source appears, but it still lacks at least one critical pillar. |
| `demoted` | `primary_verified` | A new primary record fills the missing pillar and ties it to the named project. |
| any active status | `killed` | Original P1 kill condition is met, or row-specific kill condition is met. |

## Owner Roles

| role | owner shorthand | accountable output | backup |
|---|---|---|---|
| Watchlist operator | `watch_ops` | Maintains active row table, next-check dates, and status changes. | Docket lead |
| Docket lead | `docket` | FERC, PJM, state PUC, RTO/ISO, and court docket extraction. | Watchlist operator |
| Project mapper | `projects` | Named project rows with MW, owner, customer, power path, and location. | Grid analyst |
| Grid and equipment analyst | `grid_equipment` | Interconnection, transformer, switchgear, generation, and energization risk. | Docket lead |
| Local permitting analyst | `local_permits` | County, municipal, environmental, water, air, land-use, and planning records. | Project mapper |
| Buyer operator | `buyer_ops` | Buyer-provided asset intake, outreach log, discovery-call handoff. | Editor |
| Scorekeeper | `scorekeeper` | JSONL scorecard, sealed-child clauses, Brier-ready event log. | Editor |
| Refutation lead | `red_team` | Demoted and contested rows; checks that no teaser overclaims. | Scorekeeper |
| Editor | `editor` | Weekly issue note and buyer-facing summary. | Watchlist operator |

## Cadence

| cadence | monitor | owner | output | escalation |
|---|---|---|---|---|
| Daily | FERC eLibrary hits for `RM26-4`, `EL25-49`, `ER24-2172`, `ER26-1088`, `ER26-1479`; official FERC news; PJM Inside Lines; buyer-provided docket list. | `docket` | New filings, orders, notices, deadline changes, docket IDs. | Same day if an order accepts/rejects a large-load, co-location, or direct-connect path. |
| Daily | Official company newsrooms for Talen, Constellation, Microsoft, AWS, Google, Brookfield, Meta, Entergy, Homer City, AES Ohio, Dominion, AEP Ohio, Bloom, data-center REITs. | `projects` | New project claims, MW claims, customer claims, power path language. | Same day if a 100 MW plus campus names behind-the-meter, geothermal, nuclear restart, direct connect, or interconnection bypass as differentiator. |
| Daily | State PUC and utility docket alerts for PJM/Mid-Atlantic first geography: PA PUC, PUCO, Virginia SCC, Maryland PSC, Louisiana PSC as comparison. | `local_permits` | New utility filings, ESA references, cost allocation, network upgrades. | Within 24 hours if a filed utility agreement verifies or contests a named row. |
| Daily | Local planning agendas and environmental permit pages for active rows. | `local_permits` | Hearing dates, permit status, public opposition, water/cooling conditions. | Within 24 hours if a moratorium, denial, water issue, or land-use condition changes a row. |
| Weekly | Full watchlist refresh. | `watch_ops` | Status, last checked, next check, open question, source URL, evidence note. | Escalate rows that missed next-check date or have stale evidence older than 14 days. |
| Weekly | Equipment and lead-time scan: transformers, HV switchgear, substations, turbines, fuel cells, geothermal drilling, pipeline lateral, water/cooling. | `grid_equipment` | Lead-time state, supply-risk note, new source URL. | Escalate if lead times normalize below 24 months or if a named campus cites equipment as delay. |
| Weekly | Refutation pass on one tempting lead. | `red_team` | One demoted, contested, or cleanly promoted row. | Mandatory inclusion in weekly memo. |
| Weekly | Buyer intake. | `buyer_ops` | Buyer-provided assets, active decision, budget owner, timing, source permission. | Escalate to sprint proposal only if buyer has a live decision in 3-12 months. |
| Monthly | Scorecard review. | `scorekeeper` | JSONL event append, child-clause status, calibration note. | Escalate if any row materially changes P1 evidence strength; do not alter canonical P1. |
| Monthly | Dossier issue note. | `editor` | One-page operating memo: what strengthened, what weakened, what is contested, what to do. | Send to buyers/advisors if at least one row changed status. |
| Quarterly | Forecast governance review. | `scorekeeper` and `red_team` | Preserve canonical claim, score resolved child clauses, mark unresolved. | If original kill condition begins to trigger, publish a kill memo before sales material. |

## Escalation Thresholds

| threshold | escalation level | action |
|---|---|---|
| A primary source verifies all four pillars for a 100 MW plus campus | Green escalation | Promote to `power_secured`, produce buyer note within 24 hours, add to sealed child-clause evidence. |
| A FERC/PJM/state order rejects, narrows, or materially disputes a power path | Red escalation | Mark `contested` or `killed`, notify editor and red-team, update teaser if row was used externally. |
| Two focused source passes fail to verify MW/counterparty/power path/permit status | Yellow escalation | Mark `demoted`, keep in refutation table, stop using as proof. |
| Transformer/interconnection delays normalize below 24 months in main US AI data-center markets | Thesis-level red escalation | Draft P1 weakening memo; this is part of the original kill path. |
| By 2028-12-31 fewer than two qualifying campuses are verified | Thesis-level kill | Score P1 false unless the alternative original metric leg clearly resolves true. |
| Buyer says internal team already has better source-level coverage twice in three serious calls | Commercial demotion | Move P1 behind P6 as launch wedge, but continue scorekeeping. |
| Three buyer calls in a row have no active asset, budget owner, or timing decision | Segment stop | Pause that segment and rewrite ICP. |

## Source URL Spine

Use these as the first-click source spine. Add row-specific URLs as evidence is found.

| source | exact URL | use |
|---|---|---|
| DOE/LBNL data-center load anchor | https://www.energy.gov/articles/doe-releases-new-report-evaluating-increase-electricity-demand-data-centers | Demand premise; U.S. data-center electricity share and 2028 scenario. |
| FERC RM26-4 large-load docket page | https://www.ferc.gov/rm26-4 | Rulemaking surface for large loads greater than 20 MW. |
| FERC news on RM26-4 action timing | https://www.ferc.gov/news-events/news/ferc-act-large-load-interconnection-docket-june-2026 | Monitor Commission timing and action language. |
| FERC PJM co-location order fact sheet | https://www.ferc.gov/news-events/news/fact-sheet-ferc-directs-nations-largest-grid-operator-create-new-rules-embrace | PJM co-location rule movement and compliance spine. |
| FERC ER24-2172 order PDF | https://www.ferc.gov/sites/default/files/2024-11/20241101-3061_ER24-2172-000.pdf | Talen/Amazon Susquehanna contested/refutation row. |
| FERC eLibrary docket sheet for ER24-2172 | https://elibrary.ferc.gov/eLibrary/docketsheet?docket_number=ER24-2172 | Continuing docket monitoring. |
| PJM large-load plan | https://insidelines.pjm.com/pjm-board-outlines-plans-to-integrate-large-loads-reliably/ | PJM planning context for large load integration. |
| PJM co-located-load guidance post | https://insidelines.pjm.com/pjm-to-ferc-colocated-load-growth-requires-guidance-to-manage-reliability-risks-cost-and-regulatory-issues/ | PJM framing on reliability, costs, and co-location. |
| PJM large-load workshop deck | https://www.pjm.com/-/media/DotCom/committees-groups/workshops/llaw/2025/20250509/20250509-item-02---large-load-additions-workshop---presentation.pdf | Workshop context for hyperscale data-center participation. |
| Talen power/data-center page | https://www.talenenergy.com/powering-data/ | Company source for Susquehanna direct-connect/grid-connected model; not proof by itself. |
| Constellation Crane/Microsoft release | https://www.constellationenergy.com/news/2024/Constellation-to-Launch-Crane-Clean-Energy-Center-Restoring-Jobs-and-Carbon-Free-Power-to-The-Grid.html | Company source for Crane Clean Energy Center restart and Microsoft PPA. |
| DOE Crane Restart loan page | https://www.energy.gov/edf/crane-restart | Official financing and 835 MW restart status anchor. |
| Meta Richland Parish data center | https://datacenters.atmeta.com/richland-parish-data-center/ | Official Meta site; demoted comparison until utility/PSC records are tied out. |
| Entergy/Meta Louisiana grid buildout | https://www.entergy.com/news/entergy-louisiana-announces-a-new-agreement-with-meta-that-will-deliver-an-additional-2b-in-customer-savings | Utility source for generation/transmission/storage buildout tied to Meta load. |
| FERC contact/eFiling path | https://www.ferc.gov/contact-us | Public route for monitoring protocol questions, not private lobbying. |
| DOE financing office contact | https://www.energy.gov/edf/contact-us | Public route for DOE loan/status questions. |

## Watchlist Table

Status as of this file: rows inherit status from the existing P1 Ultra materials unless marked as operating proposal. Every row needs a `last_checked` value when the first live run begins.

| row_id | object | current status | owner | cadence | source URLs | daily/weekly/monthly monitor | verified flip | contested flip | demoted flip | killed flip |
|---|---|---|---|---|---|---|---|---|---|---|
| `P1-CANONICAL` | Original P1 scored claim | `source_verified` | `scorekeeper` | monthly/quarterly | `research/pope/after-ai-2026-06-17.json`; https://www.energy.gov/articles/doe-releases-new-report-evaluating-increase-electricity-demand-data-centers; https://www.ferc.gov/rm26-4 | Monthly evidence memo; quarterly governance review. | Do not "verify" early unless the original metric resolves by 2028-12-31. | Any major regulatory or market evidence that power-secured site rights are not gating. | If evidence is real but not thesis-relevant, downgrade confidence note only. | Original kill condition met. |
| `P1-DEMAND-LBNL` | DOE/LBNL data-center load projection | `primary_verified` | `grid_equipment` | monthly | https://www.energy.gov/articles/doe-releases-new-report-evaluating-increase-electricity-demand-data-centers | Check DOE/LBNL updates, EIA power outlooks, NERC/FERC load growth reports. | Official updated report confirms continued high data-center electricity growth into 2028. | Official report sharply revises load growth down or attributes growth away from AI/data centers. | If useful only as generic demand story, move to context not proof. | Data-center load growth collapses enough that P1 demand premise no longer holds. |
| `P1-FERC-RM26-4` | FERC large-load interconnection rulemaking | `primary_verified` | `docket` | daily until action; weekly after | https://www.ferc.gov/rm26-4; https://www.ferc.gov/news-events/news/ferc-act-large-load-interconnection-docket-june-2026 | Docket, orders, comments, extensions, eLibrary filings. | Final or proposed FERC action creates monitorable standards for large loads/data centers. | Order/comment record shows deep disagreement, delay, or litigation risk for large-load path. | If action is too generic to help campus diligence. | FERC closes, withdraws, or finalizes without material relevance to large-load timing/cost. |
| `P1-PJM-COLOCATION` | PJM co-located load and large-load framework | `primary_verified` | `docket` | daily/weekly | https://www.ferc.gov/news-events/news/fact-sheet-ferc-directs-nations-largest-grid-operator-create-new-rules-embrace; https://insidelines.pjm.com/pjm-to-ferc-colocated-load-growth-requires-guidance-to-manage-reliability-risks-cost-and-regulatory-issues/ | EL25-49, AD24-11, ER26-1088, ER26-1479, PJM stakeholder pages. | Approved tariff/compliance filing gives clear requirements for co-located large loads. | Protest, partial rejection, rehearing, or cost-allocation dispute blocks clarity. | If rule is region-specific context but not tied to a named buyer row. | Final rule rejects the relevant co-location/direct-connect path without viable alternative. |
| `P1-TALEN-SUSQUEHANNA` | AWS / Talen Susquehanna data campus | `contested_primary_verified_asset` | `docket` | daily/weekly | https://www.ferc.gov/sites/default/files/2024-11/20241101-3061_ER24-2172-000.pdf; https://elibrary.ferc.gov/eLibrary/docketsheet?docket_number=ER24-2172; https://www.talenenergy.com/powering-data/ | FERC orders, appeals, PJM filings, Talen updates, AWS filings if any. | Final order/settlement/compliance path verifies MW, counterparty, grid/BTM treatment, and regulatory path. | Any active appeal/protest/rejection remains open or worsens. | If used only as cautionary example, not investable proof. | Final adverse order blocks the power path and no replacement filing appears. |
| `P1-CRANE-MICROSOFT` | Constellation / Microsoft Crane Clean Energy Center | `source_verified_restart_case` | `projects` | weekly/monthly | https://www.constellationenergy.com/news/2024/Constellation-to-Launch-Crane-Clean-Energy-Center-Restoring-Jobs-and-Carbon-Free-Power-to-The-Grid.html; https://www.energy.gov/edf/crane-restart | NRC restart/licensing, DOE loan status, PJM deliverability, Constellation updates. | NRC/DOE/PJM records plus company sources verify 835 MW restart path, Microsoft PPA linkage, and schedule. | NRC, DOE, PJM, or local record shows license, finance, or deliverability dispute. | If it is firm-power matching but not campus siting or time-to-energize proof. | Restart/licensing/financing fails or Microsoft power linkage is terminated. |
| `P1-GOOGLE-BROOKFIELD-HYDRO` | Google / Brookfield Holtwood and Safe Harbor hydro framework | `source_verified_framework` | `projects` | weekly/monthly | Add official Google/Brookfield source when verified; monitor FERC hydro project records. | FERC hydro dockets, Brookfield/Google official releases, deliverability treatment. | Official source plus FERC hydro records verify MW, offtake, project IDs, and delivery relationship. | Relicensing/deliverability dispute or mismatch between framework MW and actual campus supply. | If only broad clean-power procurement, not site-right advantage. | Framework cancelled or no project-level delivery path is verifiable after two source passes. |
| `P1-HOMER-CITY` | Homer City Energy Campus | `official_lead_not_customer_verified` | `projects` | weekly | Official project page if verified; PA DEP; PJM queue/utility records. | PA DEP permits, PJM interconnection, gas plant permits, tenant/customer evidence. | Primary/official records verify 4 GW plus power project, customer/load, grid/BTM treatment, permits. | Permit, fuel, interconnection, local, or tenant uncertainty creates schedule risk. | If customer/offtake remains unnamed after two focused passes. | Permit denied, interconnection fails, or project/customer claim is withdrawn. |
| `P1-AES-OHIO-AMAZON` | Amazon / AES Ohio data center service request | `primary_rto_planning` | `docket` | weekly | Add AES/PUCO docket when extracted; PJM/AES official filings. | PUCO electric service agreement, AES filings, PJM transmission plan, network upgrades. | ESA/PUCO/PJM records verify 65 MW COD and 480 MW phase path plus cost/timeline. | Upgrade cost, ratepayer allocation, or schedule becomes disputed. | If only grid upgrade planning and not a power-secured campus row. | ESA cancelled or required upgrades make stated COD infeasible. |
| `P1-DOMINION-CULPEPER` | Dominion Culpeper Tech Zone campuses | `primary_utility_regulatory` | `local_permits` | weekly | Virginia SCC case URLs to be added during live run; county approvals. | SCC case, Dominion filings, county planning, per-campus MW split. | SCC/local records verify named campuses, 188 MW by 2028, and 1,164 MW aggregate path. | SCC/local opposition, cost allocation, or county approvals threaten schedule. | If aggregate load is real but no campus-level power path can be tied out. | SCC denies required upgrades or local approvals block named campuses. |
| `P1-SOCRATES-WILL-POWER` | Socrates South / Will-Power behind-the-meter gas plant | `primary_regulator_plus_company` | `local_permits` | weekly | OPSB docket URL to be added; company source to be tied out. | OPSB docket, plant permit, data-center owner, physical grid connection statement. | OPSB/company records verify 200 MW South, 400 MW combined, BTM plant, adjacent data-center load. | Docket challenges physical BTM claim, emissions permit, or load owner. | If data-center owner remains unverified after two passes. | OPSB denies project or BTM path/customer claim fails. |
| `P1-APOLLO-OHIO` | Apollo Power Generation Facility | `primary_regulator_lead` | `local_permits` | weekly | OPSB/county URLs to be added. | OPSB, county planning, interconnection, data-center owner. | Primary records verify 350 MW plant, adjacent load/customer, permit path, and schedule. | Permit or interconnection dispute. | If generation is real but not tied to AI/data-center load. | Permit denied or customer/offtake absent after two passes and next-check date. |
| `P1-META-RICHLAND` | Meta Richland Parish data center | `demoted_comparison_case` | `red_team` | weekly/monthly | https://datacenters.atmeta.com/richland-parish-data-center/; https://www.entergy.com/news/entergy-louisiana-announces-a-new-agreement-with-meta-that-will-deliver-an-additional-2b-in-customer-savings | Louisiana PSC, Entergy filings, generation/transmission/storage package. | Verify as grid-buildout comparison, not BTM proof, if PSC filings match capacity, cost, and schedule. | PSC/cost allocation/local dispute alters buildout. | Already demoted as BTM proof; keep as comparison unless filings show power-secured path. | PSC rejects package or Meta/Entergy path materially fails. |
| `P1-TRANSFORMER-LEADTIMES` | Transformer/interconnection delay kill leg | `lead_context` | `grid_equipment` | weekly/monthly | Existing P1 source: https://pv-magazine-usa.com/2026/05/11/u-s-transformer-market-faces-severe-supply-constraints-as-lead-times-extend-to-four-years/; add primary supplier/procurement sources. | Lead times, procurement awards, DOE/FERC/NERC reports, utility IRPs, buyer quotes. | Multiple primary/procurement sources show main US AI markets remain above roughly 24 months. | Reliable primary/procurement sources show normalization below roughly 24 months. | If only trade press without buyer/procurement confirmation. | Normalization below 24 months becomes broad enough to trigger original kill leg. |
| `P1-LOCAL-MORATORIA` | Local consent, moratoria, zoning, ratepayer opposition | `lead_context` | `local_permits` | weekly/monthly | County/municipal agenda URLs per active geography. | Moratoria, hearings, tax incentives, zoning, water/noise/ratepayer issues. | Official local record ties moratorium/approval to a named 100 MW plus campus. | Local opposition introduces delay or conditions. | If not tied to named row or thesis metric. | Local action permanently blocks the named campus. |
| `P1-WATER-COOLING` | Cooling/water/thermal constraints under power-secured sites | `lead_context` | `local_permits` | weekly/monthly | Permit URLs per active row. | Water withdrawal, discharge, WUE targets, reclaimed-water agreements, district heat. | Official permit/source verifies water/cooling path for named campus. | Permit objection or unmet cooling condition blocks schedule. | If only generic sustainability claim. | Permit denied or cooling path physically unavailable. |
| `P1-BUYER-PIPELINE` | Commercial wedge health | `operating_metric` | `buyer_ops` | weekly/monthly | Outreach log, buyer-supplied asset list, discovery notes. | Qualified calls, buyer-provided assets, paid sprint conversion, objection pattern. | One paid sprint or LOI with buyer-provided asset/docket list. | Serious buyers say internal or incumbent coverage is better. | Five qualified calls produce zero buyer-supplied assets. | Segment or P1 wedge killed by repeated non-payment and no active decisions. |

## Daily Monitor Checklist

Every business day:

1. Check FERC news and eLibrary for `RM26-4`, `EL25-49`, `AD24-11`, `EL25-20`, `ER24-2172`, `ER26-1088`, `ER26-1479`.
2. Check PJM Inside Lines and PJM committee/workshop pages for large-load, co-location, reliability, and data-center items.
3. Check official company pages for rows in `contested`, `source_verified`, or `primary_verified`.
4. Check next-hearing dates for state PUC, county, municipal, environmental, water, and air permits due within 14 days.
5. Append a one-line event only when something changes. Do not create noise rows.

Daily event format:

```json
{"date":"YYYY-MM-DD","row_id":"P1-TALEN-SUSQUEHANNA","event_type":"filing|order|company_update|permit|buyer_input|no_change","source_url":"https://...","status_before":"contested_primary_verified_asset","status_after":"contested_primary_verified_asset","evidence_note":"one sentence","next_check":"YYYY-MM-DD","owner":"docket"}
```

## Weekly Monitor Checklist

Every Friday:

1. Promote, demote, contest, or kill rows using the transition table.
2. Choose one tempting press-release lead and attempt to refute it.
3. Update buyer-facing risk language for any row that changed status.
4. Update `next_check` dates so no active row goes stale.
5. Record whether P1 strengthened, weakened, or stayed unchanged. This is an evidence note only; the canonical probability remains unchanged unless a new sealed forecast supersedes it later.

Weekly issue memo sections:

```text
1. Rows promoted
2. Rows contested
3. Rows demoted or killed
4. Thesis-level evidence
5. Buyer implication
6. Next seven days
```

## Monthly Scorecard Checklist

Every month-end:

1. Freeze the watchlist snapshot.
2. Append scorecard events for status changes only.
3. Review sealed child clauses.
4. Publish one calibration note: "what would have fooled us this month?"
5. Do not edit P1. If needed, create a superseding child note or later board.

## Row Schema Proposal

Use this schema for a future `watchlist.jsonl` or Airtable/SQLite table.

```json
{
  "row_id": "P1-TALEN-SUSQUEHANNA",
  "parent_thesis_id": "P1",
  "object_type": "project|docket|source|market_metric|buyer_metric",
  "object_name": "AWS / Talen Susquehanna data campus",
  "market": "PJM, Pennsylvania",
  "status": "contested_primary_verified_asset",
  "status_reason": "FERC rejected the ISA amendment; company power story remains real but not clean proof.",
  "source_tier": "primary",
  "source_urls": ["https://www.ferc.gov/sites/default/files/2024-11/20241101-3061_ER24-2172-000.pdf"],
  "last_checked": "YYYY-MM-DD",
  "next_check": "YYYY-MM-DD",
  "mw": null,
  "counterparty_or_offtake": null,
  "power_path": null,
  "permit_or_regulatory_status": null,
  "open_question": "What final path, if any, survives FERC/PJM review?",
  "owner": "docket",
  "escalation_rule": "Escalate same day if a final order or settlement changes the power path.",
  "kill_condition": "Final adverse order with no replacement filing.",
  "buyer_implication": "Use as refutation row, not clean power-secured proof."
}
```

## Scorecard JSONL Proposal

This proposal has two layers:

1. `P1` canonical line: exact parent claim, preserved from the source board.
2. `P1-C*` child clauses: operational sub-clauses derived from P1 for shorter-cycle scoring. They do not replace or strengthen P1. They are evidence instruments.

Recommended rule: seal child clauses only after human approval. Once sealed, never edit. Supersede with a new line if necessary.

```jsonl
{"id":"P1","type":"canonical","source_board":"after-ai-2026-06-17","question":"By 2028-12-31, will this resolve true: The AI frontier moves from model access to firm-power siting.","probability":0.52,"resolution_date":"2028-12-31","resolution_metric":"Track hyperscaler and data-center developer announcements that name on-site firm power, geothermal, or interconnection bypass as the reason for site selection; count 100 MW plus campuses with direct power-development partnerships; track transformer lead times and local moratoria.","kill_condition":"Kill if by end 2028 fewer than two hyperscaler-scale campuses publicly secure behind-the-meter firm clean generation as a core siting advantage, or if transformer and interconnection delays normalize below roughly 24 months in the main US AI data-center markets.","created_at":"2026-06-17","do_not_edit":true}
{"id":"P1-C1","type":"child_clause","parent_id":"P1","question":"By 2028-12-31, will at least two hyperscaler-scale US AI/data-center campuses be primary/official verified as having secured behind-the-meter or direct firm clean generation as a core siting advantage, with each row verifying MW, counterparty/offtake, power path, and permit/regulatory status?","probability":0.46,"resolution_date":"2028-12-31","resolution_metric":"Count qualifying rows in the P1 watchlist with status `power_secured` and source URLs covering all four pillars.","kill_condition":"Fewer than two qualifying rows by 2028-12-31, or any counted row lacks one of the four evidence pillars.","created_at":"2026-06-17","derived_from":"P1 metric and kill condition","does_not_replace_parent":true}
{"id":"P1-C2","type":"child_clause","parent_id":"P1","question":"By 2027-12-31, will at least one FERC, PJM, state PUC, or utility order materially change the stated energization path, cost allocation, or regulatory status of a named 100 MW plus AI/data-center campus in the P1 watchlist?","probability":0.62,"resolution_date":"2027-12-31","resolution_metric":"A watchlist row moves to `contested`, `primary_verified`, `power_secured`, or `killed` because of a primary regulatory or utility record.","kill_condition":"No primary order/filing materially changes any named row by 2027-12-31.","created_at":"2026-06-17","derived_from":"P1 regulatory and interconnection monitoring layer","does_not_replace_parent":true}
{"id":"P1-C3","type":"child_clause","parent_id":"P1","question":"By 2027-06-30, will the P1 sample dossier contain at least one public AI campus power claim demoted or contested because primary-source review failed to verify MW, counterparty/offtake, power path, or permit/regulatory status?","probability":0.70,"resolution_date":"2027-06-30","resolution_metric":"At least one row in the watchlist has status `contested`, `demoted`, or `unresolved_interconnection_risk` with source URL and missing/contradicted pillar named.","kill_condition":"No sampled row is demoted or contested after two focused source passes, or demotion lacks primary/official evidence.","created_at":"2026-06-17","derived_from":"P1 launch wedge, not the parent forecast truth condition","does_not_replace_parent":true}
{"id":"P1-C4","type":"child_clause","parent_id":"P1","question":"By 2027-12-31, will transformer, interconnection, or high-voltage equipment lead-time evidence in the main US AI data-center markets remain generally above roughly 24 months for large campus-scale service?","probability":0.58,"resolution_date":"2027-12-31","resolution_metric":"Primary procurement records, utility filings, official reports, or buyer-provided sourceable evidence show lead times or service timelines above roughly 24 months for relevant markets.","kill_condition":"Primary/official evidence shows broad normalization below roughly 24 months in the main US AI data-center markets.","created_at":"2026-06-17","derived_from":"P1 kill-condition leg","does_not_replace_parent":true}
{"id":"P1-C5","type":"child_clause","parent_id":"P1","question":"By 2027-12-31, will at least one geothermal, nuclear restart, hydro, fuel-cell, or other firm-power provider announce a 100 MW plus direct data-center or AI-campus offtake where time-to-energize or interconnection bypass is named as a commercial rationale?","probability":0.50,"resolution_date":"2027-12-31","resolution_metric":"Official provider/customer source names 100 MW plus offtake and cites time-to-energize, firm power, co-location, direct-connect, or interconnection advantage.","kill_condition":"No official 100 MW plus direct firm-power offtake announcement names time-to-energize or interconnection advantage by 2027-12-31.","created_at":"2026-06-17","derived_from":"P1 watch signal and rent-path layer","does_not_replace_parent":true}
{"id":"P1-C6","type":"child_clause","parent_id":"P1","question":"By 2026-09-30, will the P1 diligence offer receive at least one buyer-provided asset, docket set, site list, or paid/LOI-backed sprint request from a lender, infrastructure investor, municipality, landowner, developer, power developer, or strategic buyer?","probability":0.44,"resolution_date":"2026-09-30","resolution_metric":"Outreach log or CRM record shows at least one qualified buyer supplied a concrete asset/docket/site list or signed a paid/LOI-backed sprint request.","kill_condition":"No qualified buyer supplies an asset/docket/site list and no paid/LOI-backed sprint emerges by 2026-09-30 after at least 20 high-fit manual sends.","created_at":"2026-06-17","derived_from":"P1 commercial operating system, not parent forecast truth condition","does_not_replace_parent":true}
```

## Scorecard Event Schema

Use event records rather than rewriting rows.

```json
{
  "event_id": "evt_YYYYMMDD_rowid_slug",
  "date": "YYYY-MM-DD",
  "parent_thesis_id": "P1",
  "child_clause_id": "P1-C2",
  "row_id": "P1-TALEN-SUSQUEHANNA",
  "event_type": "status_change|source_added|source_refuted|deadline_passed|resolved",
  "status_before": "source_verified",
  "status_after": "contested",
  "source_url": "https://...",
  "evidence_summary": "one sentence",
  "scoring_impact": "strengthens|weakens|neutral|resolves_true|resolves_false",
  "owner": "scorekeeper",
  "created_at": "YYYY-MM-DDTHH:MM:SSZ"
}
```

## Operating Workflow

### Intake

Every new candidate enters as `lead`. Required intake fields:

- `object_name`
- `market`
- `claim`
- `source_url`
- `source_tier`
- `claimed_mw`
- `claimed_counterparty`
- `claimed_power_path`
- `claimed_status`
- `first_open_question`
- `owner`
- `next_check`

If the candidate comes from a buyer, tag `buyer_supplied=true` and preserve the buyer's exact decision question.

### Verification

Verify in this order:

1. Project exists.
2. MW/capacity exists.
3. Counterparty/offtake/load owner exists.
4. Power path exists.
5. Regulatory/permit/docket/queue status exists.
6. Remaining risk is named.
7. Next check is dated.

Stop after two focused passes if a critical pillar stays missing. Mark `demoted`; do not keep polishing.

### Refutation

Each weekly issue must include one refutation attempt:

- A row that looks impressive in press.
- A row that buyers may already believe.
- A row that lacks one pillar.
- A row where a primary docket can contradict the story.

Outcome must be one of: `primary_verified`, `contested`, `demoted`, or `killed`. "Still researching" is allowed only once per row.

### Buyer Delivery

A buyer memo is allowed only when:

- At least one row is `primary_verified` or `power_secured`.
- At least one row is `contested` or `demoted`.
- Every row has a next-check date.
- The memo states the buyer decision changed: reserve, avoid, diligence, negotiate, monitor, or kill.

## 30/60/90 Day Delivery Plan

### First 30 Days - Build The Proof Spine

Goal: one sample operating dossier that proves the method catches both viable and overclaimed campus power stories.

Deliverables:

- Active watchlist with 12-15 rows, at least 6 with primary or official source URLs.
- Docket spine for `RM26-4`, PJM co-location, `ER24-2172`, and at least two state/utility cases.
- Three sample project rows:
  - One contested/refutation row: Talen/Amazon Susquehanna.
  - One restart/PPA milestone row: Constellation/Microsoft Crane.
  - One live power-campus lead from PJM or adjacent market.
- One non-PJM comparison row: Meta/Entergy Richland Parish, clearly labeled as grid-buildout comparison, not BTM proof.
- Scorecard JSONL approved or rejected by human operator.
- Outreach log: 15 manual buyer notes and 5 warm-path notes.
- First buyer discovery calls scoped around one question: "Which live site, PPA, interconnection, or capex decision could this change?"

30-day success metric:

- At least one row promoted to `primary_verified`.
- At least one row marked `contested` or `demoted`.
- At least one buyer provides an asset, docket, or site list for diligence.

30-day stop rule:

- If five qualified calls produce zero buyer-supplied assets, pause broad outreach and narrow ICP.
- If two serious buyers say internal coverage is better and no paid need exists, demote P1 behind P6 as launch wedge.

### First 60 Days - Convert Watchlist Into Repeatable Sprint

Goal: make the diligence process repeatable enough to sell and deliver without bespoke reinvention.

Deliverables:

- `watchlist.jsonl` or equivalent table using the row schema above.
- `scorecard_events.jsonl` or equivalent append-only event log.
- Docket extraction checklist for FERC, PJM, state PUC, county/municipal, environmental/water, and company sources.
- Buyer intake form requiring asset list, decision date, budget owner, source permission, and intended use.
- 10-business-day sprint template:
  - Day 1: buyer asset intake and source map.
  - Days 2-4: primary-source extraction.
  - Day 5: refutation pass.
  - Days 6-7: time-to-energize risk table.
  - Day 8: action memo.
  - Day 9: watchlist and escalation rules.
  - Day 10: buyer readout and next tranche decision.
- First paid or LOI-backed sprint target.

60-day success metric:

- One paid sprint, LOI, or design partner with a concrete asset/docket/site list.
- At least 10 rows with current source URLs and next-check dates.
- At least 3 status transitions logged in scorecard events.

60-day stop rule:

- Stop a row if public sources cannot verify MW, counterparty, power path, or regulatory status after two passes.
- Stop a buyer sprint if the buyer cannot provide a live decision or asset scope.

### First 90 Days - Turn It Into A Monitoring Product

Goal: move from one-off diligence to a small operating console and scored record.

Deliverables:

- Monthly issue note sent to relevant buyers/advisors.
- First anonymized sample dossier with:
  - one verified row,
  - one contested row,
  - one demoted row,
  - one action memo,
  - one watchlist table,
  - one scorecard excerpt.
- Repeatable source feed for:
  - FERC/eLibrary,
  - PJM,
  - state PUCs,
  - county/municipal agendas,
  - environmental/water permits,
  - company newsrooms,
  - official project pages,
  - buyer-provided sources.
- Calibration ritual: monthly scorecard review with child-clause status.
- Product field list implemented in the operating system:
  - `asset_id`
  - `market`
  - `mw`
  - `power_path`
  - `interconnection_status`
  - `co_location_status`
  - `generation_counterparty`
  - `cooling_water_status`
  - `local_permit_status`
  - `equipment_dependency`
  - `time_to_energize_score`
  - `source_tier`
  - `retrieved_at`
  - `quote_or_table_row`
  - `watch_signal`
  - `kill_condition`
  - `next_click`

90-day success metric:

- Two paid/design-partner workflows or one repeat buyer.
- 20 active rows, with at least 10 primary/official verified facts.
- A visible record of being wrong: at least 3 demoted, contested, or killed rows.
- No sales artifact that claims `power_secured` without all four pillars.

90-day stop rule:

- If no buyer pays or supplies a real asset after disciplined outreach and a sample dossier, treat P1 as a research track rather than the lead offer.
- If the watchlist cannot produce primary/official status changes within 90 days, reduce cadence and move operating focus to P6 or another thesis with faster buyer pull.

## Buyer-Facing Status Language

Use these exact phrases in memos:

- `Power-secured`: "All four diligence pillars are verified by primary or official sources: MW, counterparty/offtake, power path, and permit/regulatory status."
- `Contested`: "The project exists, but the public record disputes or narrows the claimed path."
- `Demoted`: "Useful as a lead, not investable proof. A critical pillar is missing or press-only."
- `Unresolved interconnection risk`: "The project/load exists, but the grid/co-location/cost-allocation path is not settled enough for underwriting."
- `Killed`: "The claimed path failed in official records or the required approval/counterparty/capacity disappeared."

## What Flips P1 Itself

P1 strengthens if:

- Two or more 100 MW plus campuses become `power_secured` with behind-the-meter/direct firm clean generation as a core siting advantage.
- Multiple primary records show sites winning because they can energize faster than grid-dependent alternatives.
- Buyer demand concentrates around time-to-energize diligence rather than generic power-market research.

P1 weakens if:

- Major AI campuses keep clearing power through ordinary grid buildouts without site-right premium or direct firm power.
- Transformer/interconnection lead times normalize below roughly 24 months in main AI data-center markets.
- Local permitting and interconnection disputes resolve fast enough that site rights stop being the scarce asset.

P1 is killed if:

- By 2028-12-31 fewer than two qualifying campuses are verified under the original metric, or
- Transformer and interconnection delays normalize below roughly 24 months in the main US AI data-center markets.

Do not wait until 2028 to surface weakening evidence. The watchlist exists to force early honesty.

