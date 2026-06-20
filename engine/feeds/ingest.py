"""Land the data-fleet feeds into the instrument's DB (source → series → observations).

The fleet collectors (engine/feeds/<name>.py) fetch keyless public data and write normalized
observations to data/feeds/<name>.jsonl ({series_id, date, value, unit, title}). They deliberately
do NOT touch the DB. This bridge is the one gated ingest path: it registers each feed as a Source
with a stated trust rationale (the GIGO gate, schemas.Source), creates a Series per provider key
(idempotent on provider+external_id+metric), and bulk-upserts the observations point-in-time
(store.bulk_upsert_observations → the revise-not-overwrite discipline).

Each feed is placed on its causal pillar and carries its leak class (leading vs lag/confirmation,
measured by the fleet). The leading feeds (IMF commodity prices, OECD CLI, OWID transition-shares)
are the prediction-valuable ones; the lag/confirmation feeds (World Bank, Ember, SEC, USGS) ground
kill-metrics. Leading/lag is enforced downstream by discover.py's LAG_PROVIDERS membership, not a
column here — this only lands the data honestly.

Idempotent: re-running upserts the same source/series and revises observations in place. $0.

Run:  uv run python -m engine.feeds.ingest            # all feeds present in data/feeds/
      uv run python -m engine.feeds.ingest imf oecd   # named subset
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from engine import db, rawstore
from engine.graph import _upsert_source
from engine.schemas import Observation, Source, SourceKind, _now, _uid
from engine.store import bulk_upsert_observations, write_precompute

FEEDS_DIR = Path(__file__).resolve().parents[2] / "data" / "feeds"

# Per-feed placement: pillar (1 Frontier … 9 Outcomes), the metric label (for the series UNIQUE key),
# domain bucket, the canonical endpoint (Source.url, also the idempotency key), a trust score+rationale
# (the GIGO gate — REQUIRED), and the fleet-measured leak class (documented; enforced in discover.py).
FEED_META = {
    "land_matrix": dict(
        pillar=4, metric="land_acquisition_deal", domain="land_use",
        title="Land Matrix Global Observatory", url="https://landmatrix.org/api",
        trust=80, leak="leading",
        why="Land Matrix is the reference public database of large-scale land acquisitions worldwide; "
            "keyless official API. One dated row per deal carries the target country, the operating "
            "company + investors (who holds the land), hectares, intended use, and the negotiation "
            "status (signed = land actually taken vs intended/failed). Land is the ultimate inelastic "
            "input and 'already concessioned/signed' is a leading supply-elasticity lockup signal."),
    "world_bank": dict(
        pillar=9, metric="macro_indicator", domain="macro",
        title="World Bank Indicators (v2)", url="https://api.worldbank.org/v2",
        trust=90, leak="lag",
        why="World Bank official national-accounts/energy/trade aggregates; keyless v2 JSON API; "
            "revised annual vintages (lag/confirmation)."),
    "owid": dict(
        pillar=5, metric="adoption_share", domain="energy",
        title="Our World in Data (grapher)", url="https://ourworldindata.org/grapher",
        trust=80, leak="leading",
        why="OWID compiles official energy-mix / EV-share / PV-cost series from primary agencies; "
            "keyless grapher CSV; mix-share leads stranded-asset repricing."),
    "ember": dict(
        pillar=5, metric="electricity_generation", domain="grid",
        title="Ember Electricity Data", url="https://ember-energy.org",
        trust=85, leak="confirmation",
        why="Ember monthly/yearly electricity generation by source; keyless public bucket; "
            "generation already produced (~1-2mo reporting lag)."),
    "nasa_gistemp": dict(
        pillar=5, metric="temperature_anomaly", domain="climate",
        title="NASA GISTEMP Surface Temperature Analysis",
        url="https://data.giss.nasa.gov/gistemp/tabledata_v4",
        trust=95, leak="lag",
        why="NASA GISS official surface-temperature analysis tables; monthly and annual "
            "land-ocean anomalies in degrees C relative to 1951-1980. Values are published after "
            "the reference month/year and used as a physical climate-state baseline."),
    "noaa_gml_greenhouse_gases": dict(
        pillar=5, metric="greenhouse_gas_concentration", domain="climate",
        title="NOAA GML Greenhouse Gas Trends",
        url="https://gml.noaa.gov/ccgg/trends/",
        trust=95, leak="lag",
        why="NOAA Global Monitoring Laboratory official public trend files for atmospheric CO2, "
            "CH4, and N2O. Monthly means and trend/seasonally adjusted concentrations are "
            "published after the reference month and ground the atmospheric forcing baseline."),
    "noaa_enso": dict(
        pillar=5, metric="enso_index", domain="climate",
        title="NOAA PSL ENSO Climate Indices",
        url="https://psl.noaa.gov/data/correlation/",
        trust=92, leak="lag",
        why="NOAA Physical Sciences Laboratory public monthly ENSO index files; Oceanic Nino "
            "Index, Nino 3.4 SST, and Southern Oscillation Index. These ocean-atmosphere state "
            "indices are published after the reference month and lead climate/agriculture shocks."),
    "noaa_climate_indices": dict(
        pillar=5, metric="climate_regime_index", domain="climate",
        title="NOAA PSL Broad Climate Regime Indices",
        url="https://psl.noaa.gov/data/correlation/",
        trust=90, leak="lag",
        why="NOAA Physical Sciences Laboratory public monthly climate-index files; PDO, NAO, AO, "
            "PNA, and West Pacific circulation indices. These regime-state indicators are "
            "published after the reference month and contextualize weather, crop, and energy shocks."),
    "noaa_nsidc_sea_ice": dict(
        pillar=5, metric="sea_ice_extent", domain="climate",
        title="NOAA/NSIDC Sea Ice Index",
        url="https://noaadata.apps.nsidc.org/NOAA/G02135",
        trust=94, leak="lag",
        why="NOAA@NSIDC Sea Ice Index v4 official monthly CSV files; Arctic and Antarctic sea-ice "
            "extent and area in million square kilometers. Values are reported after the reference "
            "month and ground polar climate, albedo, and Arctic-route physical state."),
    "noaa_swpc_solar": dict(
        pillar=5, metric="solar_activity", domain="space_weather",
        title="NOAA SWPC Observed Solar and Space Weather",
        url="https://services.swpc.noaa.gov/json",
        trust=95, leak="coincident",
        why="NOAA Space Weather Prediction Center official public JSON endpoints for observed "
            "monthly solar-cycle indices, rolling planetary Kp, and GOES X-ray flux. Forecast "
            "probability endpoints are excluded; high-frequency observations are daily aggregated "
            "before storage to provide leak-safe physical space-weather state."),
    "sec_edgar": dict(
        pillar=6, metric="xbrl_frame", domain="capital",
        title="SEC EDGAR XBRL Frames", url="https://data.sec.gov/api/xbrl/frames",
        trust=95, leak="lag",
        why="SEC official us-gaap XBRL filings; keyless with a descriptive UA header; "
            "files after period close (lag)."),
    "imf": dict(
        pillar=7, metric="commodity_price", domain="commodity",
        title="IMF PCPS Commodity Prices", url="https://api.imf.org/external/sdmx",
        trust=90, leak="leading",
        why="IMF Primary Commodity Price System; keyless SDMX 2.1; prices reprice ahead of "
            "CPI/IP/trade outcomes (leading)."),
    "bis": dict(
        pillar=7, metric="bis_policy_rate", domain="pricing",
        title="BIS global financial statistics", url="https://stats.bis.org/api/v2",
        trust=92, leak="leading",
        why="Bank for International Settlements official, globally-comparable financial statistics; "
            "keyless SDMX-REST v2. De-US-biases the pricing/capital layers with the SAME methodology "
            "across the G20: central-bank policy rates and nominal effective exchange rates (the price "
            "of money and of a currency — both turn ahead of the cycle) plus the BIS credit-to-GDP gap "
            "(its own crisis early-warning). Per-row metric/domain override routes the credit-gap rows "
            "to the capital read; rates/FX are leading pricing channels."),
    "worldbank_capital": dict(
        pillar=6, metric="fdi_inflow", domain="capital",
        title="World Bank capital-flow indicators", url="https://api.worldbank.org/v2",
        trust=90, leak="lag",
        why="World Bank official cross-country capital-account series; keyless v2 JSON. Fills the "
            "capital layer's biggest gap — GLOBAL private/portfolio/debt flows (FDI in/out, portfolio "
            "equity, external & private-nonguaranteed debt, gross capital formation, equity-market cap, "
            "private credit) across the G20 + emerging markets, where the layer had only US/grant data. "
            "Revised annual vintages → lag/confirmation baseline, not early-warning."),
    "global_policy": dict(
        pillar=8, metric="policy_docs_per_year", domain="policy",
        title="Global (UK + EU) regulatory activity",
        url="https://www.legislation.gov.uk/all",
        trust=88, leak="leading",
        why="Non-US official regulatory-activity counts-over-time; keyless. UK legislation.gov.uk "
            "OpenSearch totalResults per structural policy topic (same taxonomy as the US Federal "
            "Register) + EUR-Lex CELLAR SPARQL counts of EU legal acts per year by type. Adds UK + EU "
            "jurisdictions to a policy layer that was US/AU/CA-only; lawmaking tempo moves with or just "
            "ahead of the priced policy outcome (leading/coincident)."),
    "oecd": dict(
        pillar=7, metric="composite_leading_indicator", domain="macro",
        title="OECD Composite Leading Indicators", url="https://sdmx.oecd.org/public/rest",
        trust=90, leak="leading",
        why="OECD CLI engineered to turn 6-9 months ahead of business-cycle/IP turning points; "
            "keyless SDMX (leading)."),
    "usgs_minerals": dict(
        pillar=4, metric="mineral_production", domain="minerals",
        title="USGS Mineral Commodity Summaries", url="https://www.sciencebase.gov/catalog",
        trust=90, leak="lag",
        why="USGS NMIC official mineral production/import stocktake; keyless ScienceBase; "
            "annual, published the year after (lag/confirmation)."),
    "fred": dict(
        pillar=4, metric="supply_constraint_indicator", domain="physical_supply",
        title="FRED Physical Supply Bottleneck Indicators",
        url="https://fred.stlouisfed.org/graph/fredgraph.csv",
        trust=88, leak="coincident",
        why="Federal Reserve/BLS public FRED CSV series for annual transformer, switchgear, copper, "
            "steel, electrical-equipment, and metal-mining indicators. These are dated official "
            "price/output observations that expose physical supply constraints already knowable by "
            "the reference year; useful for AI power and materials bottleneck forecasts."),
    "lbnl": dict(
        pillar=4, metric="interconnection_queue_capacity", domain="energy/grid",
        title="LBNL Queued Up Active Interconnection Capacity",
        url="https://emp.lbl.gov/queues",
        trust=85, leak="lag",
        why="Lawrence Berkeley National Laboratory Queued Up headline totals for active US "
            "interconnection-queue capacity. The V1 feed stores only the conservative published "
            "year-end totals used by the existing pillar collector; queue duration/raw workbook "
            "parsing remains a logged gap."),
    # ---- physical-constraint DEPTH (2026-06-20): minerals history+concentration, full grid queue, energy ----
    "usgs_historical": dict(
        pillar=4, metric="world_mine_production", domain="minerals",
        title="USGS DS-140 Historical Statistics + MCS World Production/Reserves by Country",
        url="https://www.usgs.gov/centers/national-minerals-information-center",
        trust=92, leak="lag",
        why="USGS DS-140 century-deep per-commodity history (US+world production, unit value, "
            "consumption, 1900→present) plus the MCS world production/capacity/reserves BY COUNTRY "
            "tables. Grounds the minerals supply layer with both long-baseline regime breaks and the "
            "geopolitical concentration signal (a country's share of world output). Keyless; annual, "
            "published the year after (lag/confirmation)."),
    "lbnl_queue": dict(
        pillar=4, metric="interconnection_queue_capacity", domain="energy/grid",
        title="LBNL Queued Up — full interconnection-queue data file",
        url="https://emp.lbl.gov/queues",
        trust=88, leak="lag",
        why="Full LBNL Queued Up project-level data workbook (supersedes the 3-row headline 'lbnl' "
            "feed): active queue capacity by ISO/region × resource type × year, withdrawal volumes, "
            "completion rates by cohort, and time-in-queue. The grid interconnection queue is the "
            "binding physical constraint on new energy/datacenter supply. Keyless; annual stocktake."),
    "eia": dict(
        pillar=4, metric="electricity_net_generation", domain="energy",
        title="EIA Open Data — generation, production, prices",
        url="https://www.eia.gov/opendata/bulk/",
        trust=90, leak="lag",
        why="US EIA keyless bulk manifests: electricity net generation by source, primary-energy and "
            "crude/gas production (US + 227 countries via INTL), and WTI/Brent/Henry-Hub spot prices. "
            "Grounds the energy supply layer with physical MWh/barrels already flowed (lag/record)."),
    "mining_rights_global": dict(
        pillar=4, metric="mining_permits_dated", domain="minerals/land",
        title="Global mineral-title registries (MiningTerminal normalized)",
        url="https://miningterminal.com",
        trust=82, leak="leading",
        why="Government mineral-title registries from 30+ NON-US countries (Africa, South America, SE "
            "Asia, Europe, Canada), normalized to one schema and aggregated to permits-dated-per-year "
            "by country x phase (exploration->production) and by global critical-mineral. A mineral "
            "title is the earliest physical claim on future supply — it LEADS production by years and "
            "price by longer. The global, non-US-centric supply-pipeline signal the substrate lacked."),
    "land_ownership": dict(
        pillar=4, metric="land_use_area", domain="land",
        title="Global land use / tenure / agricultural-land structure (FAO, OWID, World Bank)",
        url="https://www.fao.org/faostat/en/#data/RL",
        trust=85, leak="lag",
        why="Keyless FAO/FAOSTAT, Our World in Data and World Bank land structure: agricultural / "
            "arable / cropland / pasture / forest area and shares by country and year (no global "
            "cadastre exists keyless, so this is the land-as-physical-constraint proxy alongside the "
            "land_matrix acquisition deals). Land is a fixed physical input; annual official stocktake "
            "(lag/confirmation)."),
    # ---- wave 2: geopolitics / politics / social / economy (fleet 2026-06-11) ----
    "gdelt": dict(
        pillar=8, metric="news_attention", domain="geopolitics",
        title="GDELT 2.0 News Attention", url="https://api.gdeltproject.org/api/v2/doc/doc",
        trust=70, leak="coincident",
        why="GDELT global news article-volume/tone by theme; keyless DOC 2.0 API; attention "
            "spikes WITH events (coincident; tone mildly leading)."),
    "eonet": dict(
        pillar=8, metric="earth_event_updates", domain="earth_events",
        title="NASA EONET Global Natural Events", url="https://eonet.gsfc.nasa.gov/api/v3/events",
        trust=90, leak="coincident",
        why="NASA Earth Observatory Natural Event Tracker official keyless API; global natural "
            "hazard events with category labels, event geometry dates, source links, and closure "
            "state. Rows are capped to collection date to avoid future-dated event leakage."),
    "usgs_earthquakes": dict(
        pillar=8, metric="earthquakes_m45_plus", domain="earth_events",
        title="USGS Earthquake Hazards Global Events",
        url="https://earthquake.usgs.gov/fdsnws/event/1/query",
        trust=95, leak="coincident",
        why="Official USGS Earthquake Hazards Program GeoJSON event API; global M4.5+ earthquake "
            "timestamps, magnitude, coordinates, tsunami flag, felt reports, and significance. "
            "Rows are capped to collection date to prevent future-dated event leakage."),
    "gdacs_alerts": dict(
        pillar=8, metric="gdacs_disaster_alerts", domain="earth_events",
        title="GDACS Global Disaster Alerts",
        url="https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH",
        trust=90, leak="coincident",
        why="Global Disaster Alert and Coordination System public-domain API; near-real-time "
            "natural-disaster alerts with event type, country, alert level, dates, affected "
            "countries, and severity data. Rows are capped to collection date."),
    "vdem": dict(
        pillar=8, metric="democracy_index", domain="governance",
        title="V-Dem Democracy Indices", url="https://v-dem.net (via OWID grapher)",
        trust=85, leak="lag",
        why="V-Dem expert-coded democracy indices (libdem/polyarchy/partipdem); keyless country-year "
            "CSV via OWID; coded after year-end, released months later (lag)."),
    "ucdp": dict(
        pillar=8, metric="conflict_deaths", domain="conflict",
        title="UCDP Georeferenced Events", url="https://ucdp.uu.se/downloads",
        trust=90, leak="lag",
        why="Uppsala UCDP GED battle-related deaths/events by country; keyless static export; coded "
            "with multi-month-to-annual lag (coincident-to-lag)."),
    "federal_register": dict(
        pillar=8, metric="policy_documents", domain="policy",
        title="Federal Register Policy Activity", url="https://www.federalregister.gov/api/v1/documents",
        trust=92, leak="coincident",
        why="Official US Federal Register documents API; publication-date-stamped rules, proposed "
            "rules, and notices across AI, chips, export controls, sanctions, critical minerals, "
            "energy, nuclear, and biotech. Coincident policy visibility: documents are knowable on "
            "their publication date, and rulemaking counts proxy regulatory pressure."),
    "ofac_sdn": dict(
        pillar=8, metric="sanctions_entries", domain="sanctions",
        title="OFAC SDN Sanctions List", url="https://sanctionslistservice.ofac.treas.gov",
        trust=95, leak="coincident",
        why="Official US Treasury OFAC SDN XML export; current sanctions-list snapshot with "
            "OFAC Publish_Date and Record_Count. Counts by program, entity type, and target country "
            "represent the sanctions state knowable on that publication date."),
    "eu_sanctions": dict(
        pillar=8, metric="sanctions_entries", domain="sanctions",
        title="EU Consolidated Financial Sanctions List",
        url="https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList/content",
        trust=95, leak="coincident",
        why="Official EU Financial Sanctions Database consolidated XML export; generation-date "
            "stamped sanctions snapshot. Counts by programme, subject type, and target country "
            "represent EU restrictive-measures state knowable on that generation date."),
    "land_permits_canada_iaac": dict(
        pillar=8, metric="impact_assessment_project_status", domain="land_use_policy",
        title="Canada IAAC Impact Assessment Project Register",
        url="https://iaac-aeic.gc.ca/050/evaluations/exploration?active=true&document_type=project",
        trust=92, leak="coincident",
        why="Official Impact Assessment Agency of Canada registry pages for active, permit-related, "
            "and federal-lands project search results. The feed stores one dated project-state row "
            "per reference number with status, assessment type, location, and description. It is a "
            "bounded V1 land-permit/EIA signal, not the full document corpus."),
    "us_permitting_dashboard": dict(
        pillar=8, metric="us_federal_permitting_project_status", domain="land_use_policy",
        title="U.S. Federal Permitting Dashboard Full Dataset",
        url="https://data.permits.performance.gov/resource/mcm3-xbid.json",
        trust=92, leak="coincident",
        why="Official U.S. Federal Permitting Dashboard public data portal dataset. The collector "
            "normalizes milestone-grain records into current project and permit/review action state "
            "rows dated to the dataset's last_data_fetched timestamp, avoiding historical milestone "
            "leakage while exposing mining, energy, transmission, water, AI/HPC, and infrastructure "
            "permitting state."),
    "blm_mining_claims": dict(
        pillar=4, metric="blm_active_mining_claim_count", domain="land_use",
        title="BLM MLRS Mining Claims and Locatable Plans",
        url="https://gis.blm.gov/nlsdb/rest/services/Mining_Claims/MiningClaims/MapServer/1",
        trust=92, leak="coincident",
        why="Official U.S. Bureau of Land Management MLRS ArcGIS REST services. The collector stores "
            "aggregate active mining-claim counts/acres by state/product/status plus non-geometry "
            "locatable plans-of-operations rows. It deliberately avoids downloading the full mining "
            "claim geometry corpus to keep the laptop thin."),
    "australia_epbc_referrals": dict(
        pillar=8, metric="australia_epbc_referral_status", domain="land_use_policy",
        title="Australia EPBC Referrals Spatial Database",
        url="https://gis.environment.gov.au/gispubmap/rest/services/ogc_services/EPBC_Referrals/MapServer/0",
        trust=92, leak="coincident",
        why="Official Australian DCCEEW EPBC Referrals Spatial Database public ArcGIS layer. The "
            "collector stores referral/project status rows without geometry; referral boundaries are "
            "maximum referral extents, not development footprints. Rows are dated to the public "
            "dataset snapshot date because the layer exposes referral year but not exact publication "
            "dates for every decision."),
    "resourcecontracts": dict(
        pillar=8, metric="resource_contract_publication", domain="land_use",
        title="ResourceContracts Critical-Resource Contract Metadata",
        url="https://api.resourcecontracts.org/contracts/group",
        trust=88, leak="lag",
        why="Official ResourceContracts.org API metadata for a bounded critical-resource slice. "
            "Rows are dated to the contract's publication date when available, with signed date as "
            "event time, so old contracts do not leak into state packs before they were published. "
            "PDF/text downloads are intentionally excluded from this keyless V1 collector."),
    "miningterminal_permits": dict(
        pillar=4, metric="mining_land_permits", domain="land_use",
        title="MiningTerminal Global Mining Permit Snapshot",
        url="miningterminal://scrapers/gov-mining-data/permits",
        trust=82, leak="coincident",
        why="Local MiningTerminal-derived compact snapshot of official/open mining cadastre, tenure, "
            "claim, concession, and mine-inventory GeoJSON artifacts. Geometry stays outside SQLite; "
            "this feed stores dated aggregate permit/area and holder facts with source artifact paths "
            "and official source URLs where present. Visibility is conservatively dated to the local "
            "artifact scrape/snapshot date rather than historical grant dates."),
    "clinicaltrials": dict(
        pillar=8, metric="trial_registry_posts", domain="clinical_regulatory",
        title="ClinicalTrials.gov Therapeutic Pipeline", url="https://clinicaltrials.gov/api/v2/studies",
        trust=92, leak="leading",
        why="Official NLM/NIH ClinicalTrials.gov API v2; first-posted study dates are public registry "
            "timestamps and current status/phase snapshots are dated to collection time. Trial posting "
            "activity is a leading biomedical/regulatory pipeline signal."),
    "openfda_drugsfda": dict(
        pillar=8, metric="fda_approved_submissions", domain="clinical_regulatory",
        title="openFDA Drugs@FDA Approval Activity", url="https://api.fda.gov/drug/drugsfda.json",
        trust=88, leak="lag",
        why="Official openFDA Drugs@FDA API; approval submission dates, application docs, and API "
            "last_updated metadata. Approval events confirm regulatory crossing after FDA action, "
            "while topic-level counts ground biomedical forecast state."),
    "worldbank_wgi": dict(
        pillar=8, metric="governance_indicator", domain="governance",
        title="World Bank Governance Indicators", url="https://api.worldbank.org/v2/wgi",
        trust=90, leak="lag",
        why="World Bank WGI (political stability / rule of law / gov effectiveness / corruption "
            "control); keyless v2 API; re-estimated annually ~9-12mo after the reference year (lag)."),
    "polymarket": dict(
        pillar=7, metric="market_implied_prob", domain="geopolitics",
        title="Polymarket Implied Probabilities", url="https://gamma-api.polymarket.com",
        trust=75, leak="leading",
        why="Polymarket prediction-market implied probability + volume; keyless gamma/clob API; a "
            "forward-looking crowd aggregate that re-prices on new information (leading)."),
    "global_equities": dict(
        pillar=7, metric="equity_close", domain="markets",
        title="Global Equity and Index Daily Closes",
        url="https://query2.finance.yahoo.com/v8/finance/chart",
        trust=70, leak="coincident",
        why="Yahoo Finance keyless chart endpoint for a bounded basket of major global indices and "
            "top-company tickers. Daily close prices are coincident market-pricing context, useful "
            "for knowing what public equities had already priced by an as-of date; this V1 feed is "
            "not a full survivorship-free securities master."),
    "metaculus": dict(
        pillar=7, metric="community_probability", domain="forecasting_markets",
        title="Metaculus Community Forecasts", url="https://www.metaculus.com/api/posts/",
        trust=82, leak="leading",
        why="Metaculus authenticated API posts endpoint; community aggregates are collected only "
            "when Metaculus exposes dated/current aggregation values. Most community predictions "
            "are intentionally hidden in the current API, so this feed degrades to no observations "
            "rather than fabricating crowd probabilities."),
    "wikipedia": dict(
        pillar=5, metric="wikipedia_pageviews", domain="demand_attention",
        title="Wikipedia Pageview Attention Signals",
        url="https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/all-agents",
        trust=70, leak="coincident",
        why="Official Wikimedia REST pageviews API; annual English Wikipedia article views for a "
            "bounded basket of forecast-relevant technology/adoption topics. This is an attention "
            "and public-awareness proxy, not a capability signal, and should only contextualize "
            "whether a topic was already visible or hype-heavy by an as-of date."),
    "ilo": dict(
        pillar=9, metric="labour_indicator", domain="social",
        title="ILOSTAT Labour Statistics", url="https://rplumber.ilo.org/data",
        trust=88, leak="lag",
        why="ILOSTAT unemployment/employment/wages by country-year; keyless rplumber API; annual "
            "~1y lag and recent years modelled (lag/confirmation)."),
    "fred_financial": dict(
        pillar=7, metric="financial_conditions", domain="financial_conditions",
        title="FRED Financial Conditions and Market Rates",
        url="https://fred.stlouisfed.org/graph/fredgraph.csv",
        trust=95, leak="coincident",
        why="Federal Reserve Bank of St. Louis FRED public CSV series for policy rates, Treasury "
            "yields, yield-curve spreads, credit spreads, financial conditions/stress indices, "
            "VIX, inflation expectations, mortgage rates, Fed assets, and M2. These are dated "
            "official/market financial-state observations knowable as published and useful for "
            "priced-in macro/credit context."),
    "ecb_fx": dict(
        pillar=7, metric="fx_reference_rate", domain="financial_conditions",
        title="ECB Euro Foreign Exchange Reference Rates",
        url="https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip",
        trust=95, leak="coincident",
        why="European Central Bank official euro foreign-exchange reference-rate historical ZIP. "
            "Each observation is a dated ECB reference rate quoted as foreign currency per EUR; "
            "missing N/A cells and future-dated rows are dropped. Useful for global FX/financial "
            "conditions context without paid market-data access."),
    # ---- wave 3: global research + supply + trade (data-layer build 2026-06-15) ----
    "openalex": dict(
        pillar=1, metric="research_works", domain="research",
        title="OpenAlex Leading Research Signals", url="https://api.openalex.org/works",
        trust=88, leak="leading",
        why="OpenAlex global scholarly graph (all fields/languages, keyless polite pool). Emits the "
            "blind-spot-fix LEADING channels: sub-topic SHARE of world literature + cross-field "
            "DIFFUSION breadth + works volume; share/diffusion reorient years before counts confirm."),
    "crossref": dict(
        pillar=1, metric="works_published", domain="research",
        title="Crossref Works Volume", url="https://api.crossref.org/works",
        trust=84, leak="leading",
        why="Crossref DOI registry, exact per-year works counts via keyless /works rows=0 + pub-date "
            "filter (polite pool, mailto UA); paper volume accelerates while a field is still "
            "pre-commercial, so it leads the constraint years before it is priced."),
    "biorxiv": dict(
        pillar=1, metric="preprints_posted", domain="research",
        title="bioRxiv/medRxiv Preprints", url="https://api.biorxiv.org",
        trust=82, leak="leading",
        why="Keyless annual count of NEW preprints posted per server; preprints land months-to-over-a-"
            "year before journal publication, so rising posting volume leads the research-effort signal."),
    "pubmed": dict(
        pillar=1, metric="pubmed_publications_per_year", domain="biomed",
        title="PubMed Topic Publication Counts",
        url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        trust=90, leak="leading",
        why="Official NCBI E-utilities ESearch API; keyless annual publication counts for bounded "
            "biomedical forecast topics. Publication-year counts are a global biomedical literature "
            "effort signal without downloading full text or abstracts."),
    "europe_pmc": dict(
        pillar=1, metric="europe_pmc_publications_per_year", domain="research",
        title="Europe PMC Bounded Paper Metadata",
        url="https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        trust=88, leak="leading",
        why="Official Europe PMC REST API; keyless bounded topic hit counts plus recent paper metadata "
            "for biomedical and life-sciences topics. Full-text/annotation extraction is intentionally "
            "not run here and remains approval-gated."),
    "semantic_scholar": dict(
        pillar=1, metric="s2ag_release_manifest", domain="research",
        title="Semantic Scholar S2AG Release Manifest",
        url="https://api.semanticscholar.org/datasets/v1/release/latest",
        trust=88, leak="coincident",
        why="Semantic Scholar official Datasets API release manifest. The manifest endpoint is public "
            "and provides the latest release date, dataset names, approximate record counts, and shard "
            "counts. Full dataset-file downloads and reliable high-volume paper access require an API "
            "key, so this feed is substrate visibility rather than full S2AG paper/citation ingestion."),
    "supply_elasticity": dict(
        pillar=4, metric="capacity_utilization_total", domain="industry",
        title="Supply Elasticity — Capacity Utilization & Backlog (FRED)",
        url="https://fred.stlouisfed.org/graph/fredgraph.csv",
        trust=92, leak="coincident",
        why="Direct read of how tight supply already is — the L4 layer's namesake signal, previously "
            "absent. Keyless FRED capacity-utilization series (total + mining, iron/steel, "
            "semiconductors, computers/electronics, motor vehicles, electric power, chemicals) plus "
            "manufacturers' unfilled orders (backlog) and inventories/sales. A sector pinned near full "
            "utilization is inelastic, so a demand shock lands as price/rent — exactly where the binding "
            "constraint pays. Monthly, released ~2-6wk after period end (near-coincident)."),
    "adoption_curves": dict(
        pillar=5, metric="adoption_curve", domain="demand_adoption",
        title="Technology Adoption / Diffusion Curves (OWID)",
        url="https://ourworldindata.org/grapher/",
        trust=88, leak="leading",
        why="Fills the REAL L5 demand layer (pillar 5 was full of mis-binned mining-permit records, so "
            "genuine demand was blind). Keyless redistributable OWID adoption S-curves — EV sales share, "
            "renewable/solar energy share, installed solar capacity, internet + mobile penetration — for "
            "World plus major economies. Adoption share is the diffusion signal that confirms a frontier "
            "capability is crossing into the real economy; it leads procurement, revenue, and pricing. "
            "Dated to reference year-end (never fetched_at)."),
    "tech_adoption": dict(
        pillar=5, metric="github_new_repos", domain="software_adoption",
        title="Software & Model Adoption (GitHub + HuggingFace creation counts)",
        url="https://api.github.com/search/repositories",
        trust=78, leak="leading",
        why="New open-source repositories (GitHub) and new HuggingFace models created per year for a "
            "bounded list of frontier topics, binned by CREATION date and capped at the cutoff year "
            "(leak-safe, never fetched_at). Developer build-out is a leading adoption signal for "
            "software-shaped frontiers — it rises while a technology is still pre-commercial, ahead of "
            "revenue and pricing. Lexical topic matching is imperfect, so treat as a relative-trend "
            "signal rather than an exact census."),
    "patent_fields": dict(
        pillar=2, metric="patent_grants", domain="capability",
        title="Global Patent Grants by CPC Technology Field (BigQuery patents-public-data)",
        url="https://console.cloud.google.com/bigquery?p=patents-public-data&d=patents&t=publications",
        trust=85, leak="leading",
        why="Worldwide patent GRANT counts per CPC 4-char technology field per year, from Google's "
            "patents-public-data.patents.publications (one 18GB grouped scan, within BQ free tier). "
            "Commercialised-capability is the L2 layer's namesake: a field's grant-rate inflecting "
            "upward is the canonical 'capability is crossing into the economy' signal — patents lead "
            "products. Counts only first-CPC grants, dated to grant year-end, capped at 2024 to avoid "
            "the recent-year grant-pendency undercount creating a false down-slope (leak-safe)."),
    "capability_curves": dict(
        pillar=2, metric="capability_curve", domain="capability",
        title="Capability & Cost Learning Curves (OWID + Epoch)",
        url="https://ourworldindata.org/grapher/",
        trust=85, leak="leading",
        why="Fills the previously-empty L2 capability layer — the second-derivative/learning-curve "
            "signal our thesis rests on. Keyless redistributable OWID cost curves (solar $/W, genome "
            "$/sequence, LCOE by tech, memory/storage $/TB, transistors/uP, supercomputer FLOP/s) plus "
            "Epoch AI ML-hardware-derived frontier perf/$ and perf/watt and frontier model training "
            "cost/power/params. Each point dated to reference year-end (never fetched_at); cost vintages "
            "publish after the reference year so the year-end stamp is conservative for forward use. A "
            "falling cost slope crossing a threshold is the canonical pre-consensus capability signal."),
    "epoch_ai": dict(
        pillar=1, metric="frontier_training_compute", domain="AI",
        title="Epoch AI Notable Models Training Compute",
        url="https://epoch.ai/data/notable_ai_models.csv",
        trust=80, leak="lag",
        why="Epoch AI public Notable AI Models CSV; curated model metadata and estimated training "
            "compute. The feed stores per-domain frontier/max FLOP by model publication year. Compute "
            "estimates are uncertain, so observations carry large uncertainty and should be treated as "
            "capability trend context rather than exact measurements."),
    "nih_reporter": dict(
        pillar=1, metric="nih_awards_per_year", domain="biomed",
        title="NIH RePORTER Biomedical Grant Counts",
        url="https://api.reporter.nih.gov/v2/projects/search",
        trust=85, leak="leading",
        why="Official NIH RePORTER v2 projects search API; keyless POST count of NIH-funded projects "
            "matching forecast-relevant biomedical topics by fiscal year. Lexical title/terms/abstract "
            "matches are imperfect and NIH-only, but funding intensity is a leading research-effort "
            "signal before publications, trials, and commercial outcomes."),
    "nsf_awards": dict(
        pillar=1, metric="nsf_awards_per_year", domain="science_funding",
        title="NSF Research.gov Award Counts",
        url="https://www.research.gov/awardapi-service/v1/awards.json",
        trust=88, leak="leading",
        why="Official NSF Research.gov Award API; keyless award-search metadata.totalCount by topic "
            "and calendar year. Lexical keyword counts are imperfect and do not sum dollars, but award "
            "volume is a leading public science/engineering funding-effort signal before papers, "
            "patents, deployments, and commercial outcomes."),
    "usaspending_sam": dict(
        pillar=6, metric="federal_procurement", domain="procurement",
        title="USAspending/SAM Procurement Topic Summaries",
        url="https://api.usaspending.gov/api/v2/search/transaction_spending_summary/",
        trust=90, leak="coincident",
        why="Official USAspending.gov no-auth transaction_spending_summary endpoint. The V1 feed "
            "stores aggregate prime-award counts and federal action obligations by topic and fiscal "
            "period, not award-row downloads. Keyword filters are imperfect, but dated procurement "
            "counts and obligations expose public demand/capital-flow pressure as-of the period end."),
    "cordis": dict(
        pillar=6, metric="cordis_grants", domain="science_funding",
        title="CORDIS EU Research Project Grants",
        url="https://cordis.europa.eu/data/",
        trust=90, leak="lag",
        why="Official CORDIS project CSV distributions for Horizon Europe and Horizon 2020, discovered "
            "through the European Data Portal/CORDIS catalog. The V1 feed stores topic-year signed "
            "project counts, EC contribution, and total project cost aggregates. Current-year rows are "
            "dated to collection day; complete prior-year rows are dated year-end to avoid future-year "
            "leakage."),
    "eurostat": dict(
        pillar=9, metric="macro_indicator", domain="macro",
        title="Eurostat Indicators",
        url="https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data",
        trust=90, leak="lag",
        why="Eurostat keyless JSON-stat 2.0 API; official EU national-accounts/population/energy-"
            "balance statistics; annual revised vintages published months-to-a-year after the "
            "reference year (lag). De-US-skews the macro pillar."),
    "faostat": dict(
        pillar=5, metric="ag_production", domain="agriculture",
        title="FAOSTAT Production", url="https://faostatservices.fao.org/api/v1/en/data",
        trust=88, leak="lag",
        why="FAO official agricultural production (QCL crops & livestock) via the keyless public "
            "bulk-download host (the JSON API now gate-checks a key); annual ~6-18mo lag + revised "
            "vintages = a lag/confirmation signal of physical food supply."),
    "comtrade": dict(
        pillar=4, metric="trade_value", domain="trade",
        title="UN Comtrade Trade Flows", url="https://comtradeapi.un.org/public/v1/preview",
        trust=88, leak="lag",
        why="UN Comtrade keyless preview API; official annual bilateral merchandise trade (critical-"
            "commodity imports); customs data lands months-to-a-year after year-end (lag), and cross-"
            "reporter import-share concentration (HHI) is the supply-dependency signal."),
    "un_comtrade": dict(
        pillar=3, metric="trade_dependency", domain="trade",
        title="UN Comtrade US Critical-Input Dependency Metrics",
        url="https://comtradeapi.un.org/public/v1/preview/C/A/HS",
        trust=80, leak="lag",
        why="UN Comtrade preview API, US reporter, annual partner rows for critical inputs. This "
            "feed derives import value, partner HHI, and net-import-reliance proxy from the same "
            "keyless substrate as the dependency pillar; customs data is lagged and preview-tier "
            "coverage is incomplete, so missing years are skipped rather than filled."),
    "baci": dict(
        pillar=4, metric="baci_trade_dependency", domain="trade",
        title="CEPII BACI Compact Trade Dependency Slice",
        url="https://www.cepii.fr/DATA_DOWNLOAD/baci/data/BACI_HS22_V202601.zip",
        trust=90, leak="lag",
        why="CEPII BACI harmonized bilateral trade flows at HS6 product level, derived from UN "
            "Comtrade and reconciled by CEPII. This compact HS22 slice keeps critical products, top "
            "economies, and supplier/importer concentration; rows carry BACI's 2026-01-22 release "
            "date separately from the trade reference year to avoid look-ahead leakage."),
    "openalex_citations": dict(
        pillar=1, metric="research_citation_edges", domain="research",
        title="OpenAlex Citation Graph", url="s3://vaticinus-datalake/openalex/derived/citation_edges",
        trust=88, leak="leading",
        why="Derived from the 3.0B-edge OpenAlex citation graph materialized as Parquet on our S3 lake "
            "(Athena CTAS over the frozen snapshot, all-AWS). Citations-made-per-year is the volume base; "
            "the graph enables citation-velocity + structural-hole/bridge channels the detector lacked."),
    "openalex_cite_velocity": dict(
        pillar=1, metric="research_field_citations", domain="research",
        title="OpenAlex Citation Velocity by Field",
        url="s3://vaticinus-datalake/openalex/derived/work_attrs",
        trust=90, leak="leading",
        why="OpenAlex OFFICIAL counts_by_year aggregated to field-year via Athena (clean of the raw-"
            "referenced_works spam cluster). Citations RECEIVED per field per year = which fields are "
            "heating up; a rising slope leads commercialization. Energy +2.3x 2018-24 = the live signal."),
    "openalex_bridge": dict(
        pillar=1, metric="research_bridge_fraction", domain="research",
        title="OpenAlex Cross-Field Bridge",
        url="s3://vaticinus-datalake/openalex/derived/citation_edges",
        trust=82, leak="leading",
        why="Per-field fraction of OUTGOING citations that cross into another field, from the citation "
            "graph (edges joined to field on both ends). The structural-hole/bridge channel the detector "
            "lacked: a rising cross-field fraction = a field going general-purpose. CAVEAT: physics self-"
            "citation mildly inflated by an OpenAlex duplicate-record cluster (despam is a follow-up)."),
}


def _get_or_create_series(conn, provider, external_id, metric, *, pillar_id, source_id,
                          label, unit, domain) -> str:
    row = conn.execute(
        "SELECT id FROM series WHERE provider=? AND external_id=? AND metric=?",
        (provider, external_id, metric)).fetchone()
    if row:
        conn.execute(
            """
            UPDATE series
            SET pillar_id=?,
                source_id=?,
                label=?,
                unit=?,
                domain=?
            WHERE id=?
            """,
            (pillar_id, source_id, label, unit[:40] or "unit", domain, row["id"]),
        )
        return row["id"]
    sid = _uid()
    conn.execute(
        "INSERT INTO series (id,pillar_id,source_id,provider,external_id,label,metric,unit,domain,"
        "created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (sid, pillar_id, source_id, provider, external_id, label, metric, unit[:40] or "unit",
         domain, _now().isoformat()))
    return sid


def _parse_feed_date(row: dict, *keys: str) -> date | None:
    for key in keys:
        raw = row.get(key)
        if raw is None or raw == "":
            continue
        try:
            return date.fromisoformat(str(raw)[:10])
        except (TypeError, ValueError):
            continue
    return None


def _upsert_feed_papers(conn, name: str, rows: list[dict], *, content_hash: str | None) -> int:
    paper_rows = [r for r in rows if str(r.get("paper_external_id") or "").strip()]
    if not paper_rows:
        return 0
    now_s = _now().isoformat()
    values = []
    for r in paper_rows:
        published = _parse_feed_date(r, "published_at", "date")
        if published is None:
            continue
        external_id = str(r.get("paper_external_id") or "").strip()
        title = " ".join(str(r.get("paper_title") or r.get("title") or "").split())
        if not external_id or not title:
            continue
        try:
            n_authors = int(r.get("paper_n_authors") or 0)
        except (TypeError, ValueError):
            n_authors = 0
        values.append(
            (
                _uid(),
                name,
                external_id,
                published.isoformat(),
                _parse_feed_date(r, "paper_updated", "updated", "date").isoformat()
                if _parse_feed_date(r, "paper_updated", "updated", "date")
                else None,
                str(r.get("paper_primary_category") or r.get("topic_slug") or "")[:80] or None,
                str(r.get("paper_categories") or r.get("topic_slug") or ""),
                title,
                str(r.get("paper_abstract") or ""),
                str(r.get("paper_authors") or ""),
                n_authors,
                content_hash,
                now_s,
            )
        )
    if not values:
        return 0
    conn.executemany(
        """
        INSERT INTO papers (
            id, provider, external_id, published, updated, primary_category, categories,
            title, abstract, authors, n_authors, content_hash, fetched_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(provider, external_id) DO UPDATE SET
            published=excluded.published,
            updated=excluded.updated,
            primary_category=excluded.primary_category,
            categories=excluded.categories,
            title=excluded.title,
            abstract=excluded.abstract,
            authors=excluded.authors,
            n_authors=excluded.n_authors,
            content_hash=excluded.content_hash,
            fetched_at=excluded.fetched_at
        """,
        values,
    )
    return len(values)


def ingest_feed(conn, name: str) -> dict:
    meta = FEED_META[name]
    path = FEEDS_DIR / f"{name}.jsonl"
    if not path.exists():
        return {"feed": name, "status": "no-file", "series": 0, "obs": 0}
    content = path.read_bytes()
    rows = []
    for line in content.decode("utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not rows:
        return {"feed": name, "status": "empty", "series": 0, "obs": 0}

    content_hash = rawstore.put(conn, content, url=meta["url"], media_type="application/json")
    src = Source(url=meta["url"], title=meta["title"], pillar_id=meta["pillar"],
                 kind=SourceKind.primary, trust_score=meta["trust"], trust_rationale=meta["why"],
                 content_hash=content_hash)
    source_id = _upsert_source(conn, src)
    rawstore.put(conn, content, source_id=source_id, url=meta["url"], media_type="application/json")
    papers_written = _upsert_feed_papers(conn, name, rows, content_hash=content_hash)

    # group rows by the provider's series key
    by_series: dict[str, list[dict]] = {}
    for r in rows:
        sid = r.get("series_id")
        if sid is not None:
            by_series.setdefault(str(sid), []).append(r)

    obs: list[Observation] = []
    series_uids = []
    for ext_id, recs in by_series.items():
        unit = str(recs[0].get("unit") or "unit")
        label = str(recs[0].get("title") or ext_id)[:120]
        # A feed may carry MULTIPLE metrics in one file (e.g. OpenAlex emits works/share/fields).
        # Honor a row-level `metric` when present; else fall back to the feed's default metric.
        metric = str(recs[0].get("metric") or meta["metric"])
        domain = str(recs[0].get("domain") or meta["domain"])
        suid = _get_or_create_series(
            conn, name, ext_id, metric, pillar_id=meta["pillar"],
            source_id=source_id, label=label, unit=unit, domain=domain)
        series_uids.append(suid)
        for r in recs:
            try:
                event_time = _parse_feed_date(r, "event_time", "date")
                published_at = _parse_feed_date(r, "published_at", "as_of", "date")
                observed_at = _parse_feed_date(r, "observed_at", "date")
                d = _parse_feed_date(r, "as_of", "published_at", "date")
                if d is None:
                    raise ValueError("missing date/as_of")
                v = float(r["value"])
                uncertainty = float(r.get("uncertainty") or 0.0)
            except (KeyError, ValueError, TypeError):
                continue
            obs.append(
                Observation(
                    series_id=suid,
                    as_of=d,
                    event_time=event_time,
                    published_at=published_at,
                    observed_at=observed_at,
                    value=v,
                    unit=str(r.get("unit") or unit)[:40],
                    uncertainty=uncertainty,
                )
            )
    res = bulk_upsert_observations(conn, obs)
    for suid in series_uids:
        write_precompute(conn, suid)
    conn.commit()
    return {"feed": name, "status": "ok", "leak": meta["leak"], "pillar": meta["pillar"],
            "series": len(series_uids), "obs": res["written"], "revised": res["revised"],
            "papers": papers_written}


def main():
    requested = sys.argv[1:]
    if requested:
        unknown = [a for a in requested if a not in FEED_META]
        if unknown:
            print(f"unknown feed(s): {', '.join(unknown)}", file=sys.stderr)
            return 1
        names = requested
    else:
        names = list(FEED_META)
    conn = db.connect()
    db.init_db(conn)
    print(f"ingesting {len(names)} feeds → DB ...")
    tot_s = tot_o = 0
    for name in names:
        r = ingest_feed(conn, name)
        tot_s += r["series"]; tot_o += r["obs"]
        leak = r.get("leak", "")
        print(f"  {name:16s} {r['status']:8s} p{r.get('pillar','?')} {leak:12s} "
              f"series +{r['series']:4d}  obs +{r['obs']:5d}"
              + (f"  (revised {r['revised']})" if r.get("revised") else ""))
    print(f"\nLANDED {tot_o} observations across {tot_s} new series.")
    print(f"DB now: sources {conn.execute('SELECT count(*) FROM sources').fetchone()[0]}, "
          f"series {conn.execute('SELECT count(*) FROM series').fetchone()[0]}, "
          f"observations {conn.execute('SELECT count(*) FROM observations').fetchone()[0]}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
