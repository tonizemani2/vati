# Pope Ultra Wave 2 Results - P1 AI Campus Power Claims

Generated: 2026-06-17

This is the integrated output of the second agent wave. It changes the commercial
positioning: the product should not claim to discover that data-center power is
scarce. That is now public. The product should verify and refute campus power
claims with primary-source evidence before a buyer underwrites them.

## Verdict

P1 is still useful, but the launch wedge is narrower:

- Bad pitch: power-secured AI campuses win.
- Better pitch: prove whether a claimed power-secured AI campus survives
  primary-source diligence.

Top-tier hyperscalers and the largest developers likely solve much of this
internally. Start with lenders, infra investors, family offices, municipalities,
landowners, smaller developers, and strategics exposed to someone else's claim.

## Hard Label Rule

No row can be called `power_secured` unless primary or official sources verify:

- MW or capacity.
- Counterparty/offtake.
- Interconnection, grid-connected, co-located, or behind-the-meter path.
- Permit, regulatory, or docket status.
- Remaining open question and next check.

Otherwise use `lead`, `source_verified`, `contested`, `demoted`, or
`unresolved_interconnection_risk`.

## Docket Spine

| docket | status | issue | next action |
|---|---|---|---|
| `RM26-4-000` | primary_verified | FERC large-load interconnection ANOPR, including data centers and co-located/flexible load. | Watch for Commission action by end-June 2026. |
| `EL25-49-000`, `EL25-49-001`, `AD24-11-000`, `EL25-20-000` | primary_verified | PJM co-located load rules, BTMG netting, transmission service, and rate design. | Track compliance and paper-hearing replacement-rate issues. |
| `ER24-2172-000`, `ER24-2172-001` | primary_verified_contested | PJM/Susquehanna/Talen/Amazon ISA amendment; FERC rejected amendments on 2024-11-01. | Watch appellate review and generic PJM co-location dockets. |
| `ER26-1088-000` | primary_verified | PJM 30-day compliance filing from EL25-49; FERC accepted in part and rejected in part. | Track further compliance after FERC's 2026-04-16 order. |
| `ER26-1479-000` | primary_verified_pending | PJM 60-day co-located load tariff revisions filed 2026-02-23. | Await FERC merits order. |

Primary docket URLs:

- https://www.ferc.gov/rm26-4
- https://www.ferc.gov/news-events/news/ferc-act-large-load-interconnection-docket-june-2026
- https://www.ferc.gov/news-events/news/fact-sheet-ferc-directs-nations-largest-grid-operator-create-new-rules-embrace
- https://www.ferc.gov/sites/default/files/2024-11/20241101-3061_ER24-2172-000.pdf
- https://elibrary.ferc.gov/eLibrary/docketsheet?docket_number=ER24-2172

## Sample Dossier Rows

| project | market | current status | verified capacity | why it matters | next check |
|---|---|---:|---:|---|---|
| AWS / Talen Susquehanna data campus | PJM, Pennsylvania | `contested_primary_verified_asset` | Up to 960 MW initial, later company filings indicate revised front-of-meter supply up to 1,920 MW through 2042. | Core refutation case: commercial story exists, but FERC rejected the ISA amendment. | Pull ER24-2172, related appeals, and later PJM/FERC filings before using any MW claim. |
| Constellation / Microsoft Crane Clean Energy Center | PJM, Pennsylvania | `source_verified_restart_case` | 835 MW company/DOE restart figure. | Nuclear restart/PPA case tied to Microsoft data-center power matching in PJM. | Track NRC restart/license approvals and PJM deliverability materials. |
| Google / Brookfield Holtwood + Safe Harbor hydro | PJM, Pennsylvania | `source_verified_framework` | 670 MW initial, up to 3,000 MW framework. | Dispatchable hydro procurement for Google PJM operations. | Pull FERC hydro relicensing dockets, especially Safe Harbor No. 1025. |
| Meta / Constellation Clinton Clean Energy Center | MISO Zone 4, adjacent comparison | `source_verified_nuclear_ppa` | 1,121 MW. | Shows hyperscaler demand for firm nuclear output, though not PJM. | Track NRC renewal/uprate records and MISO deliverability treatment. |
| Homer City Energy Campus | PJM, Pennsylvania | `official_lead_not_customer_verified` | 4.4-4.5 GW project claim. | Retired coal site converted into gas-powered AI/HPC campus. | Verify PA DEP permits, PJM interconnection, and tenant energy service agreements. |
| Amazon / AES Ohio data center | PJM, Ohio | `primary_rto_planning` | 65 MW at COD; 480 MW by end of Phase I. | Named 345 kV service request with dated ramp schedule. | Pull AES/PUCO electric service agreement and network upgrade costs. |
| Dominion Culpeper Tech Zone campuses | PJM, Virginia | `primary_utility_regulatory` | 188 MW by 2028; 1,164 MW by 2034 aggregate. | Three named campuses driving 230 kV buildout and useful public load evidence. | Track SCC case status, per-campus MW split, and county approvals. |
| AEP Ohio / Bloom onsite power for AWS + Cologix | PJM, Ohio | `primary_company_no_mw` | MW not named in source. | Onsite fuel cells may let data centers energize while grid upgrades lag. | Pull PUCO order/case number, fuel-cell MW, and site-level agreements. |
| Socrates South / Will-Power BTM plant | PJM, Ohio | `primary_regulator_plus_company` | 200 MW South; 400 MW North+South combined. | Behind-the-meter gas plant serving adjacent data center, not physically grid-connected. | Pull OPSB case docket and confirm load owner. |
| Apollo Power Generation Facility | PJM, Ohio | `primary_regulator_lead` | 350 MW. | Another large BTM gas plant for adjacent data-center load. | Pull OPSB docket, county planning record, and identify data-center owner. |

## Demoted Leads

Talen/Amazon Susquehanna must not be sold as clean proof of a power-secured
campus. It is better as the flagship refutation row: a project with real
counterparties, real MW claims, and real FERC friction.

Meta Richland Parish should not be used as behind-the-meter proof. It is a
large utility/grid buildout and cost-allocation package with generation,
transmission, storage, uprates, and renewables.

## First Outreach Segment

Do not start with hyperscalers. Start with buyers exposed to claims made by
others:

- Infrastructure investors doing asset diligence.
- Lenders underwriting power-secured campuses.
- Family offices and smaller strategics with AI-infra exposure.
- Municipalities and landowners facing large campus proposals.
- Smaller developers that need independent credibility.

## Stop Rules

- Stop P1 outreach if five qualified calls produce zero buyer-supplied assets.
- Stop or demote P1 if two of three serious buyers say their internal team or
  incumbents already cover this view well enough.
- Stop any dossier row where the named MW, counterparty, power path, or
  regulatory status cannot be verified after two focused source passes.
- Make every teaser include one demoted/refuted lead. That is the product's
  proof of discipline.
