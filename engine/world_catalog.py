"""Global data coverage registry and top-entity seed.

This is the machine-readable version of the world-data plan: what sources cover the planet, what
they become in the timestamped state layer, and which canonical entities should exist before every
source is linked. It is intentionally a registry, not a collector: collectors read from here later.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine import data_offload, db as _db, disk_guard
from engine.schemas import Entity, _now

MIB = 1024 ** 2
GIB = 1024 ** 3
DEFAULT_STALE_HOURS = 24.0
DEFAULT_MAX_LOCAL_REFRESH_MB = 100.0
RESEARCH_LAYER = "research"
RESEARCH_QUERY_INTERFACES = (
    {
        "name": "frozen state pack",
        "command": 'python3 -m engine.cli world-state "<topic>" --as-of YYYY-MM-DD --json',
        "machine_role": "LLM/machine point-in-time context with snapshot hash and citations",
        "cost": "$0 local read",
    },
    {
        "name": "source matrix",
        "command": "python3 -m engine.cli world-data-matrix --json",
        "machine_role": "source coverage, processing, output, blocker, and cost posture rows",
        "cost": "$0 local read",
    },
    {
        "name": "research layer status",
        "command": "python3 -m engine.cli world-research-status --json",
        "machine_role": "research-specific diversity, time coverage, and next-step policy",
        "cost": "$0 local read",
    },
    {
        "name": "research coverage profile",
        "command": "python3 -m engine.cli world-research-profile --json",
        "machine_role": "research providers, paper/fact timelines, predicates, provenance gaps, and approval gates",
        "cost": "$0 local read",
    },
    {
        "name": "research expansion plan",
        "command": "python3 -m engine.cli world-research-plan --json",
        "machine_role": "research corpus expansion targets, processing policy, approval gates, and diversity gaps",
        "cost": "$0 local read",
    },
    {
        "name": "research provenance gaps",
        "command": "python3 -m engine.cli world-research-provenance --json",
        "machine_role": "research raw-doc/source/fact provenance coverage and exact-byte gap triage",
        "cost": "$0 local read",
    },
    {
        "name": "top entity coverage",
        "command": "python3 -m engine.cli world-entity-coverage --json",
        "machine_role": "global entity fact/source coverage for topic routing and grounding",
        "cost": "$0 local read",
    },
)


@dataclass(frozen=True)
class DataSourceSpec:
    id: str
    name: str
    layer: str
    priority: int
    status: str
    coverage: str
    access: str
    storage: str
    cost: str
    process: tuple[str, ...]
    outputs: tuple[str, ...]
    entities: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class TopEntitySpec:
    kind: str
    name: str
    domain: str
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class LandPermitJurisdictionSpec:
    id: str
    name: str
    region: str
    priority: int
    status: str
    source_ids: tuple[str, ...]
    source_types: tuple[str, ...]
    official_source_examples: tuple[str, ...]
    outputs: tuple[str, ...]
    entities: tuple[str, ...]
    cost: str
    storage: str
    collection_policy: str
    approval_gates: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True)
class ResearchExpansionSpec:
    id: str
    name: str
    priority: int
    status: str
    source_ids: tuple[str, ...]
    corpus_role: str
    coverage: str
    access: str
    outputs: tuple[str, ...]
    entities: tuple[str, ...]
    cost: str
    storage: str
    processing_policy: str
    approval_gates: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True)
class PhysicalConstraintSpec:
    id: str
    name: str
    priority: int
    status: str
    constraint_role: str
    source_ids: tuple[str, ...]
    why_it_matters: str
    coverage: str
    outputs: tuple[str, ...]
    entities: tuple[str, ...]
    collector_policy: str
    refresh_model: str
    storage: str
    cost: str
    approval_gates: tuple[str, ...]
    notes: str = ""


RESEARCH_EXPANSION_SOURCE_IDS = (
    "openalex_snapshot",
    "arxiv",
    "crossref",
    "pubmed_pmc",
    "semantic_scholar",
    "europe_pmc",
    "opencitations",
    "paper_patent_reliance",
)


LAND_PERMIT_SOURCE_IDS = (
    "land_permit_source_registry",
    "land_permits_cadastre",
    "resource_concessions_contracts",
    "environmental_planning_eia",
    "open_geospatial_land_context",
)

PHYSICAL_CONSTRAINT_SOURCE_IDS = (
    "land_permit_source_registry",
    "land_permits_cadastre",
    "resource_concessions_contracts",
    "environmental_planning_eia",
    "open_geospatial_land_context",
    "grid_interconnection_transmission",
    "grid_power_bottlenecks",
    "eia_iea_ember_owid",
    "policy_stack",
    "water_rights_stress",
    "industrial_facility_air_water_permits",
    "usgs_minerals",
    "un_comtrade",
    "baci",
    "faostat",
    "noaa_climate_indices",
    "ports_logistics_capacity",
    "shipping_satellite",
    "carbon_storage_pore_space",
    "openalex_snapshot",
    "arxiv",
    "crossref",
    "pubmed_pmc",
    "semantic_scholar",
    "europe_pmc",
    "opencitations",
    "google_patents",
    "paper_patent_reliance",
    "uspto_bulk",
    "epo_ops",
)

RESEARCH_EXPANSION_TARGETS: tuple[ResearchExpansionSpec, ...] = (
    ResearchExpansionSpec(
        "openalex_backbone",
        "OpenAlex global works/concepts/institutions backbone",
        1,
        "landed_partial",
        ("openalex_snapshot",),
        "global research graph backbone",
        "global all-field works, authors, institutions, concepts, venues, and citation context where available",
        "public snapshot/API",
        ("dated publication facts", "concept/institution entities", "topic-share series", "citation velocity features"),
        ("research_concept", "institution", "technology"),
        "$0 public snapshot/API; Athena/cloud scans require approval",
        "object storage snapshot/extracts + SQLite derived facts/features",
        "Use as the broad research backbone; keep bulk files off laptop and promote only derived facts.",
        ("Athena/cloud scan", "bulk snapshot refresh", "LLM extraction"),
        "Already partially landed; next value is richer concept/institution linking and better raw provenance for new extracts.",
    ),
    ResearchExpansionSpec(
        "arxiv_preprints",
        "arXiv preprint timeline",
        1,
        "landed_partial",
        ("arxiv",),
        "early research signal",
        "global but discipline-skewed preprints, strongest in physics, math, CS, and quantitative domains",
        "metadata API/OAI and optional full-text sources",
        ("paper metadata timeline", "fast topic emergence signals", "category diffusion facts", "approved extraction candidates"),
        ("technology", "research_concept", "institution"),
        "$0 metadata; defer full-text egress and extraction",
        "SQLite paper metadata; optional object storage full text",
        "Keep as the fast public frontier signal, but never treat it as all-field research coverage.",
        ("full-text bulk download", "LLM extraction", "cloud text processing"),
        "Currently the paper table is arXiv-heavy, so complementary corpora are required before broad research-diversity claims.",
    ),
    ResearchExpansionSpec(
        "crossref_doi_metadata",
        "Crossref DOI metadata and references",
        1,
        "partial",
        ("crossref",),
        "DOI and publication metadata normalization",
        "global DOI registry with publisher metadata and references where available",
        "public REST/dumps",
        ("DOI provenance facts", "publication count series", "venue/publisher links", "OpenAlex/Crossref reconciliation"),
        ("research_concept", "institution", "publisher"),
        "$0 polite access; bulk/cloud joins require approval",
        "feed JSONL/object extracts + SQLite derived facts",
        "Use as DOI/provenance glue rather than a full-text source.",
        ("bulk dump processing", "cloud DOI joins"),
        "Important for deduping OpenAlex/arXiv/PubMed and for citation provenance.",
    ),
    ResearchExpansionSpec(
        "pubmed_pmc_biomed",
        "PubMed / PMC biomedical literature and open full text",
        1,
        "partial",
        ("pubmed_pmc",),
        "biomedical research depth",
        "global biomedical abstracts plus PMC open-access full text where available",
        "NCBI APIs/FTP/open access subsets",
        ("biomedical publication facts", "drug/target/disease links", "clinical/translational trend series", "full-text extraction candidates"),
        ("technology", "institution", "company", "drug", "target", "disease"),
        "$0 public data; OCR/LLM/full-text extraction requires approval",
        "object storage OA full text + SQLite derived facts",
        "Prioritize biomedical depth because arXiv undercovers medicine, devices, trials, and translational science.",
        ("full-text extraction", "LLM extraction", "large FTP refresh"),
        "Pairs with ClinicalTrials.gov/openFDA to connect research to regulatory progress.",
    ),
    ResearchExpansionSpec(
        "semantic_scholar_s2ag",
        "Semantic Scholar S2AG metadata/citations/abstracts",
        1,
        "partial_manifest",
        ("semantic_scholar",),
        "citation and abstract enrichment",
        "global scholarly graph with downloadable datasets/API subject to access/rate limits",
        "Datasets API and Academic Graph API",
        ("abstract-backed paper facts", "citation graph features", "author/paper/institution links", "cross-corpus dedupe diagnostics"),
        ("research_concept", "institution", "author", "paper"),
        "$0/free access path, but API key/rate/dataset access may be required",
        "object storage dataset extracts + SQLite facts/features",
        "Use as enrichment after access is confirmed; do not fabricate hidden/unavailable aggregates.",
        ("API key", "dataset download", "bulk extraction", "LLM extraction"),
        "Current local state is manifest/limited; broad S2AG use remains blocked on access and approved processing.",
    ),
    ResearchExpansionSpec(
        "europe_pmc_life_sciences",
        "Europe PMC life-sciences metadata, full text, and annotations",
        2,
        "partial_metadata",
        ("europe_pmc",),
        "life-sciences text-mining diversity",
        "biomedical and life-sciences literature, open full text, and text-mining annotations where exposed",
        "Europe PMC REST and annotations APIs",
        ("life-sciences article facts", "annotation facts", "open full-text extraction candidates", "PubMed/PMC reconciliation"),
        ("drug", "target", "disease", "technology", "institution"),
        "$0 APIs; bulk full-text extraction/OCR/LLM requires approval",
        "raw docs/object storage for text extracts + SQLite derived facts",
        "Bounded metadata collector is live; bulk full text, annotations, and extraction still need approval.",
        ("bulk full-text processing", "LLM extraction", "OCR/translation"),
        "Complements PubMed/PMC with annotation-oriented access for machine extraction.",
    ),
    ResearchExpansionSpec(
        "opencitations_open_citations",
        "OpenCitations open citation and bibliographic data",
        2,
        "planned_free",
        ("opencitations",),
        "open citation graph enrichment",
        "open bibliographic/citation metadata and indexes for scholarly citations",
        "public dumps/APIs",
        ("open citation facts", "DOI-to-DOI citation edges", "citation velocity features", "Crossref/OpenAlex reconciliation"),
        ("research_concept", "paper", "publisher"),
        "$0 open data; cloud joins and graph processing require approval",
        "object storage dumps + SQLite compact citation features",
        "Use to strengthen citation features without relying only on paid/proprietary citation indexes.",
        ("bulk dump processing", "cloud joins", "graph materialization"),
        "Low-cost complement to OpenAlex/Crossref for open citation provenance.",
    ),
    ResearchExpansionSpec(
        "paper_patent_reliance_bridge",
        "Paper-to-patent reliance bridge",
        2,
        "planned_metered",
        ("paper_patent_reliance",),
        "research commercialization signal",
        "paper-to-patent citation and reliance links across patent jurisdictions where available",
        "public dataset plus S3/Athena-style joins",
        ("paper-patent reliance facts", "commercialization-intensity series", "technology/patent/paper edges", "applicant citation features"),
        ("research_concept", "technology", "patent", "company"),
        "$0 download path; Athena/cloud scan approval required before joins",
        "object storage raw links + SQLite derived facts/edges",
        "Keep download/storage separate from paid scan joins; require dry-run bytes before execution.",
        ("Athena/cloud scan", "large join", "entity resolution at scale"),
        "Forecast-critical for turning research into commercial/industrial capacity signals.",
    ),
)

LAND_PERMIT_JURISDICTIONS: tuple[LandPermitJurisdictionSpec, ...] = (
    LandPermitJurisdictionSpec(
        "us_federal_state_local",
        "United States federal/state/local land permits",
        "North America",
        1,
        "planned_inventory",
        ("land_permits_cadastre", "resource_concessions_contracts", "environmental_planning_eia", "open_geospatial_land_context"),
        (
            "federal land and right-of-way records",
            "state mining/oil/gas/energy permits",
            "NEPA/EIA notices and decisions",
            "county/city parcel, zoning, and building permits",
            "grid/interconnection siting records",
        ),
        (
            "BLM/Interior land and mineral records",
            "EPA/agency NEPA and environmental-impact registers",
            "state natural-resource and utility-commission portals",
            "county/city open-data planning and parcel portals",
        ),
        (
            "permit-stage facts",
            "parcel/project/company/county/state edges",
            "concession/lease facts",
            "environmental-review decision facts",
        ),
        ("company", "country_region", "project", "land_parcel", "permit", "infrastructure_asset"),
        "$0 for official/open portals first; paid parcel vendors require approval",
        "object storage for raw PDFs/geospatial layers; SQLite derived facts/edges only",
        "Start with official/open portals first: federal/state portals and large local permitting portals; do not buy parcel data first.",
        ("paid parcel vendor", "bulk geospatial joins", "OCR/LLM extraction", "cloud processing"),
        "High-value early layer for mines, data centers, transmission, factories, and energy projects.",
    ),
    LandPermitJurisdictionSpec(
        "canada_provincial_federal",
        "Canada federal/provincial land, mining, and impact permits",
        "North America",
        1,
        "planned_inventory",
        ("resource_concessions_contracts", "environmental_planning_eia", "land_permits_cadastre", "open_geospatial_land_context"),
        (
            "provincial mining claims and tenures",
            "federal/provincial impact assessments",
            "municipal planning/building permits",
            "crown-land dispositions and leases",
        ),
        (
            "Impact Assessment Registry of Canada and provincial equivalents",
            "provincial mining tenure/cadastre portals",
            "provincial open-data parcel and land-use layers",
            "municipal planning/open-data portals",
        ),
        (
            "mining tenure facts",
            "impact-assessment facts",
            "project/commodity/province edges",
            "permit-stage series",
        ),
        ("company", "country_region", "project", "material", "land_parcel", "permit"),
        "$0/open portals first; geocoding and paid parcel enrichment require approval",
        "object storage raw registers/map layers + SQLite derived facts",
        "Prioritize critical-minerals provinces and energy/transmission corridors.",
        ("paid geocoding", "bulk geospatial joins", "OCR/LLM extraction"),
        "Strong fit for battery minerals, uranium, LNG, grid, and hydro forecasts.",
    ),
    LandPermitJurisdictionSpec(
        "europe_uk_eea",
        "Europe/UK/EEA planning, EIA, cadastral, and concessions",
        "Europe",
        1,
        "planned_inventory",
        ("environmental_planning_eia", "land_permits_cadastre", "resource_concessions_contracts", "open_geospatial_land_context"),
        (
            "national and local planning applications",
            "EIA/SEA/public consultation registers",
            "cadastre and INSPIRE-style land layers where open",
            "mining/geothermal/offshore energy licenses",
        ),
        (
            "national planning and EIA portals",
            "local authority planning portals",
            "national cadastral/open-geodata portals",
            "energy/mining licensing authorities",
        ),
        (
            "planning-approval facts",
            "EIA/public-comment window facts",
            "license/concession facts",
            "project/local-authority/country edges",
        ),
        ("company", "country_region", "project", "land_parcel", "permit", "policy"),
        "$0/open portals first; paid cadastral vendors and translation/OCR require approval",
        "object storage for raw notices/attachments/geodata + SQLite derived facts",
        "Inventory country-by-country; local authority fragmentation is the main blocker.",
        ("paid cadastral data", "OCR/translation", "cloud geospatial joins", "scrape at scale"),
        "Useful for factories, grid, offshore wind, mining, nuclear, and data-center siting.",
    ),
    LandPermitJurisdictionSpec(
        "australia_state_commonwealth",
        "Australia state/Commonwealth tenements, EPBC, and planning",
        "Asia-Pacific",
        1,
        "planned_inventory",
        ("resource_concessions_contracts", "environmental_planning_eia", "land_permits_cadastre", "open_geospatial_land_context"),
        (
            "state mining tenements and exploration licenses",
            "EPBC referrals and approvals",
            "state planning and major-project registers",
            "cadastral/open geospatial layers",
        ),
        (
            "state mining/tenement portals",
            "Commonwealth environmental referrals/approvals",
            "state major-project and planning portals",
            "state open-geodata/cadastre portals",
        ),
        (
            "tenement/license facts",
            "environmental-approval facts",
            "project/material/state edges",
            "land-context features",
        ),
        ("company", "country_region", "project", "material", "land_parcel", "permit"),
        "$0/open portals first; bulk geospatial processing requires approval",
        "object storage raw geodata/documents + SQLite facts/edges",
        "Prioritize lithium, iron ore, rare earths, transmission, and hydrogen corridors.",
        ("cloud geospatial joins", "OCR/LLM extraction", "large bulk downloads"),
        "Good early signal for critical minerals and energy-transition supply.",
    ),
    LandPermitJurisdictionSpec(
        "latin_america_mining_energy",
        "Latin America mining, energy, land, and EIA permits",
        "Latin America",
        1,
        "planned_inventory",
        ("resource_concessions_contracts", "environmental_planning_eia", "land_permits_cadastre", "open_geospatial_land_context"),
        (
            "mining concessions and exploration rights",
            "EIA approvals and public consultations",
            "energy/transmission project permits",
            "land/cadastre layers where open",
        ),
        (
            "national mining cadastres",
            "environmental authority EIA portals",
            "energy/ministry project registers",
            "national/subnational open-geodata portals",
        ),
        (
            "concession facts",
            "EIA approval/appeal facts",
            "company/project/material/country edges",
            "permit-stage series",
        ),
        ("company", "country_region", "project", "material", "land_parcel", "permit"),
        "$0/open portals first; translation/OCR/geocoding require approval",
        "object storage raw Spanish/Portuguese docs/geodata + SQLite facts/edges",
        "Prioritize Chile, Argentina, Brazil, Mexico, Peru, and battery/copper grids.",
        ("translation/OCR", "cloud geospatial joins", "paid geocoding", "scrape at scale"),
        "Essential for lithium, copper, iron ore, renewables, and transmission forecasts.",
    ),
    LandPermitJurisdictionSpec(
        "africa_critical_minerals_energy",
        "Africa critical-minerals, energy, land, and EIA permissions",
        "Africa",
        1,
        "planned_inventory",
        ("resource_concessions_contracts", "environmental_planning_eia", "land_permits_cadastre", "open_geospatial_land_context"),
        (
            "mining cadastre licenses and concessions",
            "contract and beneficial-ownership disclosures where open",
            "EIA/public notice registers",
            "land-use/geospatial context layers",
        ),
        (
            "national mining cadastre portals",
            "EITI-style disclosures and open contract registers",
            "environmental authority EIA portals",
            "national open-geodata portals where available",
        ),
        (
            "license/concession facts",
            "contract/project/company edges",
            "EIA decision facts",
            "material/country supply-option signals",
        ),
        ("company", "country_region", "project", "material", "land_parcel", "permit"),
        "$0/open portals first; translation/OCR and paid registry enrichment require approval",
        "object storage raw docs/geodata + SQLite derived facts/edges",
        "Prioritize DRC, Zambia, South Africa, Ghana, Namibia, Tanzania, and grid/mining corridors.",
        ("translation/OCR", "paid registry enrichment", "cloud geospatial joins", "scrape at scale"),
        "Critical for cobalt, copper, graphite, uranium, PGMs, and power bottleneck forecasts.",
    ),
    LandPermitJurisdictionSpec(
        "asia_india_china_se_asia",
        "China/India/Southeast Asia land, EIA, industrial, and resource permits",
        "Asia-Pacific",
        2,
        "planned_inventory",
        ("environmental_planning_eia", "land_permits_cadastre", "resource_concessions_contracts", "open_geospatial_land_context"),
        (
            "environmental-impact and public notice registers",
            "industrial park/project approval notices",
            "land/natural-resources notices",
            "mining/energy license records where open",
        ),
        (
            "environment/ministry EIA portals",
            "natural-resources/land-use portals",
            "industrial development and local-government notices",
            "national/subnational open-geodata portals",
        ),
        (
            "project approval facts",
            "EIA/public notice facts",
            "company/project/country edges",
            "land-context risk flags",
        ),
        ("company", "country_region", "project", "land_parcel", "permit", "policy"),
        "$0/open portals first; translation/proxy/OCR/cloud extraction require approval",
        "object storage raw notices/docs + SQLite facts/edges",
        "Use official pages and conservative provenance; do not infer approvals from news alone.",
        ("translation/OCR", "cloud extraction", "proxy/network access", "scrape at scale"),
        "Important for batteries, solar, semiconductors, industrial capacity, ports, and data centers.",
    ),
    LandPermitJurisdictionSpec(
        "middle_east_energy_industrial_land",
        "Middle East energy, industrial land, and giga-project permits",
        "Middle East",
        2,
        "planned_inventory",
        ("land_permits_cadastre", "environmental_planning_eia", "open_geospatial_land_context"),
        (
            "industrial-zone and special-economic-zone permits",
            "energy/desalination/project approvals",
            "municipal planning notices where open",
            "land/geospatial context layers",
        ),
        (
            "national/local planning portals",
            "investment-zone and industrial-city portals",
            "energy/water authority project registers",
            "open-geodata portals where available",
        ),
        (
            "industrial land-permit facts",
            "energy/water project approval facts",
            "project/company/country edges",
            "land-context features",
        ),
        ("company", "country_region", "project", "land_parcel", "permit", "infrastructure_asset"),
        "$0/open portals first; paid/closed registry data requires approval",
        "object storage raw docs/geodata + SQLite derived facts",
        "Treat PR/news as discovery only; official permit source is required for world-state facts.",
        ("paid/closed registry access", "translation/OCR", "cloud geospatial joins"),
        "Useful for AI/data-center power, ports, hydrogen, water, and logistics infrastructure.",
    ),
    LandPermitJurisdictionSpec(
        "global_contracts_eiti_disclosures",
        "Global concessions/contracts/EITI disclosure backbone",
        "Global",
        2,
        "planned_inventory",
        ("resource_concessions_contracts",),
        (
            "open land/resource contracts",
            "extractive-industry transparency disclosures",
            "beneficial ownership and license-holder disclosures",
        ),
        (
            "OpenLandContracts-style repositories",
            "ResourceContracts-style repositories",
            "EITI-style country disclosures",
            "national contract/license publication portals",
        ),
        (
            "contract/license facts",
            "holder/project/material/country edges",
            "expiry/renewal/status facts",
        ),
        ("company", "country_region", "project", "material", "permit"),
        "$0/open repositories first; OCR/translation/entity resolution require approval",
        "object storage raw contracts + SQLite derived facts/edges",
        "Use as global backbone where official cadastre APIs are weak or fragmented.",
        ("OCR/translation", "LLM extraction", "entity resolution at scale"),
        "Backstops concession visibility across jurisdictions with weak structured portals.",
    ),
    LandPermitJurisdictionSpec(
        "global_open_geospatial_context",
        "Global open geospatial land-use context",
        "Global",
        2,
        "planned_inventory",
        ("open_geospatial_land_context",),
        (
            "roads/buildings/places",
            "land cover and protected areas",
            "forest, water, and settlement context",
            "project proximity layers",
        ),
        (
            "OpenStreetMap/Overture-style open map layers",
            "public land-cover layers",
            "protected-area and forest-monitoring layers",
            "national open-geodata portals",
        ),
        (
            "project proximity features",
            "parcel/location context facts",
            "protected-area and land-cover risk flags",
        ),
        ("country_region", "project", "land_parcel", "infrastructure_asset"),
        "$0/open layers first; tiling/cloud joins require approval",
        "object storage geospatial partitions + SQLite compact derived features",
        "Context only: never treat map-layer proximity as proof that a permit exists.",
        ("bulk download", "tiling", "cloud geospatial joins"),
        "Needed to compare permitted land with actual siting constraints and infrastructure proximity.",
    ),
)

PHYSICAL_CONSTRAINT_TARGETS: tuple[PhysicalConstraintSpec, ...] = (
    PhysicalConstraintSpec(
        "land_permit_spine",
        "Land permits, zoning, parcels, cadastre, EIA, and concessions",
        1,
        "planned_not_collected",
        "permissioned land and siting",
        (
            "land_permit_source_registry",
            "land_permits_cadastre",
            "resource_concessions_contracts",
            "environmental_planning_eia",
            "open_geospatial_land_context",
        ),
        "This is the first physical bottleneck because mines, fabs, data centers, grid corridors, energy projects, and factories need permissioned land before capacity exists.",
        "global view assembled jurisdiction by jurisdiction; completeness varies by country, state, province, and local authority",
        (
            "permit-stage facts",
            "parcel/project/company/country edges",
            "EIA/public-comment/appeal facts",
            "lease/concession/expiry facts",
            "zoning/land-use status facts",
        ),
        ("company", "country_region", "project", "land_parcel", "permit", "infrastructure_asset"),
        "Build collectors from official/open portals first; use news only as discovery, never as proof of approval.",
        "bulk inventory/backfill first, then dated delta collectors for decisions, appeals, expiries, renewals, and new notices",
        "raw docs/geospatial files to object storage; SQLite stores facts, links, compact spatial features, and snapshot manifests",
        "$0/open sources first; paid parcel vendors, OCR/translation, LLM extraction, and cloud geospatial joins require approval",
        ("paid parcel vendor", "OCR/translation", "LLM extraction", "cloud geospatial joins", "scrape at scale"),
        "Highest priority. One-time bulk is enough only for historical cadastre/concession snapshots; permit decisions need ongoing refresh.",
    ),
    PhysicalConstraintSpec(
        "research_paper_backbone",
        "All-field research paper and citation backbone",
        1,
        "partial",
        "frontier knowledge substrate",
        ("openalex_snapshot", "arxiv", "crossref", "pubmed_pmc", "semantic_scholar", "europe_pmc", "opencitations"),
        "Research papers reveal where capability is emerging before capacity and markets reprice, but only if coverage is diverse and dated.",
        "global, but current local state is still skewed toward arXiv/OpenAlex-style metadata; biomedical, citation, institution, and non-English coverage need expansion",
        (
            "paper metadata facts",
            "concept/institution/author entities",
            "citation and reference edges",
            "topic emergence series",
            "full-text/annotation extraction candidates",
        ),
        ("research_concept", "paper", "institution", "author", "technology", "drug", "target", "disease"),
        "Use bulk snapshots/dumps for the historical corpus and small incremental/API collectors for freshness; keep full text off the laptop.",
        "snapshot backfill is generally enough for cold history; daily/weekly/monthly deltas needed for frontier topics and forecast-time evidence",
        "bulk papers/citations in object storage; SQLite holds metadata, facts, embeddings/features if approved, and citation-derived signals",
        "$0 metadata/dumps first; full-text bulk processing, embeddings, and LLM extraction require approval",
        ("bulk snapshot refresh", "full-text extraction", "embedding build", "LLM extraction", "cloud graph joins"),
        "The goal is not merely more papers; it is point-in-time paper facts machines can query without leakage.",
    ),
    PhysicalConstraintSpec(
        "patent_rights_backbone",
        "Patents, patent families, claims, assignees, CPC classes, and paper-to-patent reliance",
        1,
        "partial_metered",
        "commercialized knowledge and IP position",
        ("google_patents", "paper_patent_reliance", "uspto_bulk", "patentsview_odp", "epo_ops"),
        "Patents are the bridge from research to protected technical position, assignee concentration, manufacturing claims, and jurisdictional capacity signals.",
        "global if using Google Patents/Public Data and family enrichment; US-only if relying on USPTO/PatentsView alone",
        (
            "patent publication/grant facts",
            "priority-date and family facts",
            "assignee/company edges",
            "CPC/technology trend series",
            "paper-to-patent reliance facts",
            "claim/abstract extraction candidates",
        ),
        ("company", "patent", "technology", "research_concept", "country_region"),
        "Use dry-run-gated BigQuery/cloud extracts for global coverage; use USPTO/ODP as a free US fallback where keys permit.",
        "bulk/global snapshot enough for historical patent landscape; incremental refresh needed for new applications, grants, continuations, assignments, and citations",
        "raw/global extracts in object storage; SQLite stores compact patent facts, assignee links, HHI/concentration, and paper-patent edges",
        "Google Patents/large joins require explicit spend approval; USPTO/ODP key setup is free but gated by terms/key",
        ("BigQuery dry-run approval", "Athena/cloud scan", "API key", "large join", "LLM extraction"),
        "Do not let US-only patents masquerade as global coverage.",
    ),
    PhysicalConstraintSpec(
        "grid_power_connection",
        "Grid interconnection, transmission siting, energy supply, and power bottlenecks",
        1,
        "partial",
        "electrical permission and deliverable power",
        ("grid_interconnection_transmission", "grid_power_bottlenecks", "eia_iea_ember_owid", "policy_stack"),
        "Power availability is becoming a binding constraint for AI, mining, fabs, industrial electrification, and hydrogen; queue position matters more than headline MW announcements.",
        "US coverage is already queryable through grid bottleneck proxies; global interconnection/transmission permit coverage is planned and fragmented",
        (
            "interconnection queue facts",
            "withdrawal/approval/delay facts",
            "transmission-siting facts",
            "power supply and generation mix facts",
            "project/grid-node/company edges",
        ),
        ("company", "country_region", "project", "permit", "infrastructure_asset", "technology"),
        "Backfill official queue/utility/regulator snapshots, then poll for status changes and withdrawals.",
        "one-time bulk is not enough for queues; delta collectors needed because projects enter, withdraw, slip, and interconnection costs change",
        "official snapshots/docs to object storage; SQLite compact queue-stage facts and time series",
        "$0/open portals first; paid geospatial/electric-node datasets and cloud joins require approval",
        ("cloud geospatial joins", "paid grid-node data", "scrape at scale", "OCR/LLM extraction"),
        "This should link directly to land permits: land without power is not capacity.",
    ),
    PhysicalConstraintSpec(
        "water_constraint_layer",
        "Water rights, basin stress, discharge permits, and water-intensive capacity",
        1,
        "planned_not_collected",
        "water permission and hydrological scarcity",
        ("water_rights_stress", "environmental_planning_eia", "open_geospatial_land_context", "faostat", "noaa_climate_indices"),
        "Water can gate mining, data centers, fabs, chemicals, agriculture, hydrogen, and thermal power even when land and capital are available.",
        "global context layers are feasible; official permit/right records are jurisdiction-fragmented",
        (
            "water-right and withdrawal facts",
            "discharge permit facts",
            "basin/aquifer stress features",
            "drought/climate context series",
            "project/water-source/company edges",
        ),
        ("company", "country_region", "project", "permit", "water_basin", "infrastructure_asset"),
        "Start with official/open water-rights and environmental portals plus public hydrology/stress layers; paid water datasets are deferred.",
        "bulk context is enough for slow basin-risk layers; active permits/restrictions need periodic refresh",
        "raw permits/geodata to object storage; compact basin/project features in SQLite",
        "$0/open first; paid water datasets, geocoding, OCR/translation, and cloud geospatial joins require approval",
        ("paid water data", "geocoding", "OCR/translation", "cloud geospatial joins"),
        "Treat water as a siting layer next to land, not as a generic climate indicator.",
    ),
    PhysicalConstraintSpec(
        "minerals_and_materials_supply",
        "Critical minerals, reserves, production, concessions, and trade concentration",
        1,
        "partial",
        "material supply elasticity",
        ("resource_concessions_contracts", "usgs_minerals", "un_comtrade", "baci", "faostat"),
        "Materials determine whether technologies scale; mining concessions and trade concentration are leading indicators before production appears.",
        "global production/trade is partially queryable; project-level concessions and permits are planned and should connect to the user's mining DB",
        (
            "mineral production/reserve facts",
            "concession/project/material edges",
            "trade-dependency and HHI series",
            "pre-production supply-option signals",
            "country/material risk facts",
        ),
        ("company", "country_region", "project", "material", "permit", "land_parcel"),
        "Use your existing mining DB as a source to reconcile projects/companies, then add official concession and permit records around it.",
        "annual bulk is enough for historical production/reserves; concessions, permits, strikes, restrictions, and export controls need refresh",
        "bulk trade/mineral files and permit docs to object storage; SQLite stores derived facts and project/entity edges",
        "$0/open sources first; paid registry enrichment, translation/OCR, and large geospatial joins require approval",
        ("paid registry enrichment", "translation/OCR", "cloud geospatial joins", "entity resolution at scale"),
        "Mining is one domain of the land-permit layer, not the whole layer.",
    ),
    PhysicalConstraintSpec(
        "industrial_facility_permission",
        "Industrial facility, air, water, waste, construction, and operating permits",
        2,
        "planned_not_collected",
        "permissioned industrial capacity",
        ("industrial_facility_air_water_permits", "environmental_planning_eia", "land_permits_cadastre", "open_geospatial_land_context"),
        "Factories, fabs, smelters, LNG plants, battery plants, chemical plants, and data centers can be announced long before they are permitted to operate.",
        "official registers exist unevenly across national, state/provincial, and local agencies",
        (
            "facility permit facts",
            "capacity-permission facts",
            "environmental condition facts",
            "appeal/renewal/expiry facts",
            "facility/company/project edges",
        ),
        ("company", "country_region", "project", "permit", "infrastructure_asset", "material", "technology"),
        "Collect official agency registers and local planning portals; use company/news only to discover candidate facilities.",
        "one-time bulk is enough for historical facility baselines; operating permits, appeals, and renewals need refresh",
        "raw docs/PDFs to object storage; SQLite stores extracted permission facts and facility edges",
        "$0/open first; OCR, translation, paid facility databases, and LLM extraction require approval",
        ("OCR/translation", "paid facility database", "LLM extraction", "scrape at scale"),
        "This is the non-mining sibling of land permits: real-world capacity that needs formal permission.",
    ),
    PhysicalConstraintSpec(
        "logistics_and_route_capacity",
        "Ports, terminals, rail corridors, shipping, and logistics chokepoints",
        2,
        "planned_mixed",
        "deliverable capacity and route bottlenecks",
        ("ports_logistics_capacity", "shipping_satellite", "un_comtrade", "baci"),
        "Supply can exist upstream but fail to reach market because terminal capacity, shipping routes, rail corridors, or port permits bind.",
        "global trade flows are partially queryable; live logistics capacity and AIS/satellite are deferred or paid",
        (
            "port/terminal capacity facts",
            "corridor disruption facts",
            "route/material dependency edges",
            "expansion-permit facts",
            "trade-flow concentration series",
        ),
        ("company", "country_region", "project", "infrastructure_asset", "material"),
        "Start with official port/rail/project sources and trade data; defer paid AIS/satellite until a forecast needs it.",
        "annual/monthly bulk is enough for historical trade concentration; disruptions and capacity expansions need rolling refresh",
        "raw official releases/geodata to object storage; SQLite compact logistics facts and route/material edges",
        "$0/open first; AIS/satellite/paid logistics feeds and cloud joins require approval",
        ("paid AIS/satellite", "paid logistics data", "cloud geospatial joins", "scrape at scale"),
        "This is lower priority than land/grid/water unless a specific bottleneck thesis points here.",
    ),
    PhysicalConstraintSpec(
        "carbon_storage_and_pore_space",
        "CO2 storage pore space, injection permits, pipelines, and sequestration sites",
        2,
        "planned_not_collected",
        "subsurface permission and storage scarcity",
        ("carbon_storage_pore_space", "land_permits_cadastre", "environmental_planning_eia", "open_geospatial_land_context"),
        "For CCS/DAC, rent can migrate from capture equipment to scarce permitted pore space and pipeline-connected storage.",
        "US is the most tractable first market; global coverage requires national/regional regulator inventories",
        (
            "storage permit facts",
            "pore-space lease/status facts",
            "injection-volume facts",
            "operator/site/pipeline edges",
            "permitted-storage-capacity series",
        ),
        ("company", "country_region", "project", "permit", "land_parcel", "infrastructure_asset"),
        "Start with official regulator dockets and agency permit tables; keep subsurface commercial data deferred.",
        "one-time bulk is enough for old permit history; active permit applications, approvals, and withdrawals need refresh",
        "raw dockets/maps to object storage; SQLite compact permit/storage facts and edges",
        "$0/open first; paid subsurface data, OCR, and geospatial joins require approval",
        ("paid subsurface data", "OCR/translation", "cloud geospatial joins", "LLM extraction"),
        "A specialized but high-value land-permit variant.",
    ),
)


DATA_SOURCES: tuple[DataSourceSpec, ...] = (
    DataSourceSpec(
        "openalex_snapshot", "OpenAlex full snapshot", "research", 1, "landed_partial",
        "global all-field research graph", "S3 public snapshot", "S3 Parquet + SQLite derived",
        "$0 public snapshot; Athena only for derived scans",
        ("freeze dated snapshot", "derive works/concepts/institutions", "citation velocity", "bridge metrics"),
        ("research facts", "concept entities", "institution entities", "citation-derived series"),
        ("research_concept", "institution"),
    ),
    DataSourceSpec(
        "arxiv", "arXiv metadata/full text", "research", 2, "partial",
        "global but discipline-skewed preprints", "OAI/API/S3 requester-pays", "SQLite papers; optional S3 text",
        "$0 metadata; defer full-text egress", ("harvest metadata", "optional LaTeX full-text parse", "extract methods/results"),
        ("paper facts", "research trend series", "technology entities"),
    ),
    DataSourceSpec(
        "crossref", "Crossref works", "research", 2, "partial",
        "global DOI registry", "REST/dump", "feed JSONL + derived series", "$0 polite pool",
        ("backfill yearly counts", "link DOI to OpenAlex where possible"), ("publication series", "DOI provenance"),
    ),
    DataSourceSpec(
        "semantic_scholar", "Semantic Scholar S2AG", "research", 3, "partial_manifest",
        "global scholarly graph with abstracts/citations", "S2AG dumps/API", "object storage extracts",
        "$0 with free key", ("load paper metadata", "dedupe with OpenAlex", "extract abstracts"),
        ("paper facts", "author/institution links", "citation features"),
    ),
    DataSourceSpec(
        "epoch_ai", "Epoch AI notable AI models", "research", 2, "partial",
        "global notable AI model training compute estimates", "public CSV", "feed JSONL + derived series",
        "$0", ("load notable-models CSV", "derive per-domain frontier compute by publication year"),
        ("frontier compute facts", "AI capability trend series"),
        ("technology",),
        "Curated model set with estimated compute; useful as capability context, not exact census.",
    ),
    DataSourceSpec(
        "pubmed_pmc", "PubMed / PMC Open Access", "research", 3, "partial",
        "global biomedical literature", "NCBI FTP/API", "object storage text extracts", "$0",
        ("load OA full text", "extract trials/targets/modalities", "link MeSH/DOI"),
        ("biomed facts", "drug/target entities", "trial/paper links"),
    ),
    DataSourceSpec(
        "europe_pmc", "Europe PMC life-sciences metadata/annotations", "research", 2, "partial",
        "global life-sciences and biomedical literature with open full-text/annotation access where available",
        "REST/annotations APIs", "object storage text extracts + SQLite derived facts",
        "$0 APIs; bulk full-text extraction/OCR/LLM requires approval",
        (
            "load life-sciences metadata",
            "preserve annotation/full-text extracts with hashes where fetched",
            "link PubMed/PMC/DOI identifiers",
            "extract genes/proteins/diseases/chemicals only after approved extraction pilot",
        ),
        (
            "life-sciences article facts",
            "annotation facts",
            "biomedical entity links",
            "full-text extraction candidates",
        ),
        ("technology", "institution", "drug", "target", "disease"),
        "Adds biomedical diversity beyond arXiv and complements PubMed/PMC.",
    ),
    DataSourceSpec(
        "opencitations", "OpenCitations open citation data", "research", 3, "planned_free",
        "global open bibliographic and citation metadata/indexes",
        "public dumps/APIs", "object storage dumps + SQLite derived citation features",
        "$0 open data; cloud joins and graph materialization require approval",
        (
            "load open citation dumps/API slices",
            "normalize DOI-to-DOI citation edges",
            "join to Crossref/OpenAlex concepts",
            "derive citation velocity/reliance features",
        ),
        (
            "open citation facts",
            "paper citation edges",
            "citation velocity series",
            "DOI provenance links",
        ),
        ("research_concept", "paper", "publisher"),
        "Strengthens citation provenance without paid citation indexes.",
    ),
    DataSourceSpec(
        "google_patents", "Google Patents Public Data", "patents", 1, "partial_metered",
        "global patents including CN", "BigQuery", "S3/Parquet extracts + SQLite facts",
        "metered by dry-run bytes; cap 40-100GB/query",
        ("dry-run query", "extract title/abstract/claims/CPC/assignee/citations", "hash batch outputs"),
        ("patent facts", "assignee entities", "patent HHI series", "paper-patent links"),
        ("company", "technology"),
    ),
    DataSourceSpec(
        "paper_patent_reliance", "Reliance on Science paper→patent citations", "patents", 2, "planned_metered",
        "worldwide patent-to-paper citation links across US/EP/CN/KR/WO patents",
        "Zenodo download + S3/Athena join", "S3 gzip/Parquet + feed JSONL + SQLite facts",
        "download $0; Athena scan logged and approval-gated",
        (
            "download/gzip Reliance on Science PCS OpenAlex file",
            "join cited OpenAlex paper IDs to primary concepts",
            "derive per-concept patent reliance and applicant-citation intensity",
        ),
        ("paper→patent reliance facts", "commercialization-intensity series", "concept patent-link metrics"),
        ("research_concept", "technology", "patent"),
        "Collector exists as engine.feeds.relianceonscience, but it is cloud/Athena-gated and not run in keyless refreshes.",
    ),
    DataSourceSpec(
        "uspto_bulk", "USPTO bulk XML", "patents", 3, "planned_free",
        "US patents only", "bulk download/S3", "object storage", "$0 except storage",
        ("load grants/apps", "parse assignees/CPC/claims", "dedupe against Google Patents"),
        ("US patent facts", "assignee links"),
    ),
    DataSourceSpec(
        "patentsview_odp", "PatentsView / USPTO Open Data Portal", "patents", 3, "planned_keyed",
        "US patent applications/grants by CPC class", "API", "feed JSONL + derived series",
        "$0 API usage but ODP API key required",
        ("provision USPTO ODP key", "wire ODP search schema", "aggregate CPC patent counts by grant/application date"),
        ("US patent count facts", "CPC technology trend series", "innovation leading indicators"),
        ("technology", "patent"),
        "Legacy keyless PatentsView search is retired; collector now probes and reports key requirement without fabricating counts.",
    ),
    DataSourceSpec(
        "epo_ops", "EPO OPS / DOCDB", "patents", 4, "planned_keyed",
        "international patent families", "API", "derived facts only", "free quota/key; defer heavy use",
        ("enrich patent families", "resolve jurisdictions"), ("family facts", "priority-date facts"),
    ),
    DataSourceSpec(
        "gleif", "GLEIF LEI", "entities", 1, "partial",
        "global legal entities", "open daily file", "object storage + entity table", "$0",
        ("load LEI records", "normalize names/addresses", "merge into company entities"),
        ("company entities", "legal IDs", "parent relationships"),
        ("company", "country_region"),
    ),
    DataSourceSpec(
        "companies_house", "UK Companies House", "entities", 2, "partial",
        "UK companies/officers", "bulk/API", "object storage + entity table", "$0 with free key",
        ("load company profile/officers", "link LEI/tickers"), ("company entities", "officer facts"),
    ),
    DataSourceSpec(
        "wikidata_entities", "Wikidata entity IDs", "entities", 2, "partial",
        "global cross-domain entity identifiers", "API/entity JSON", "raw docs + entity links", "$0",
        ("search exact labels/aliases", "fetch entity JSON", "link QIDs to top entities"),
        ("Wikidata QID links", "global non-US/private entity anchors"),
        ("company", "institution", "technology", "material"),
        "Community-curated identifier backbone; exact-match identity anchor only, not a primary fact source.",
    ),
    DataSourceSpec(
        "sec_edgar", "SEC EDGAR filings/XBRL", "corporate", 1, "partial",
        "US-listed and SEC-reporting companies", "bulk/API", "raw docs + SQLite facts", "$0",
        ("store filings raw", "parse XBRL", "extract capacity/contracts/risk factors"),
        ("filing facts", "capital series", "company links"),
        ("company",),
    ),
    DataSourceSpec(
        "sec_company_tickers", "SEC company tickers / CIK index", "entities", 1, "partial",
        "US-listed and SEC-reporting companies", "official JSON index", "raw docs + entity links",
        "$0", ("load company_tickers.json", "match exact ticker/legal aliases", "link CIKs and tickers"),
        ("company ticker links", "CIK links", "filing/entity join keys"),
        ("company",),
    ),
    DataSourceSpec(
        "global_equities", "Global equities/tickers", "markets", 2, "partial",
        "listed companies across major exchanges", "Stooq/Yahoo/exchange files", "S3 price shards + SQLite summaries",
        "$0 core feeds", ("load OHLCV", "link ticker to legal entity", "derive valuation anchors"),
        ("price series", "ticker links", "market-pricing facts"),
        ("company",),
    ),
    DataSourceSpec(
        "prediction_markets", "Prediction markets and crowd forecasts", "markets", 2, "partial_limited",
        "global event markets where public/authorized aggregates are visible", "Polymarket keyless; Metaculus authenticated API",
        "feed JSONL + derived series", "$0 API usage; Metaculus community aggregates now visibility-limited",
        ("load Polymarket implied probabilities", "probe Metaculus authenticated posts API", "only store visible dated aggregates"),
        ("market-implied probability facts", "crowd-forecast availability diagnostics", "priced-in context"),
        ("forecast_market", "technology", "country_region"),
        "Metaculus token access works, but current API policy hides most community predictions; do not fabricate missing aggregates.",
    ),
    DataSourceSpec(
        "wikipedia_pageviews", "Wikipedia pageview attention", "public_attention", 2, "partial",
        "global public-awareness proxy, English Wikipedia article-level", "Wikimedia REST API",
        "feed JSONL + derived series", "$0",
        ("load bounded article pageview histories", "aggregate monthly API rows to annual topic totals"),
        ("attention facts", "topic visibility series", "hype/obviousness context"),
        ("technology", "policy"),
        "Attention/adoption proxy only; should contextualize visibility, not substitute for capability or supply facts.",
    ),
    DataSourceSpec(
        "fred_financial", "FRED financial conditions and rates", "financial_conditions", 1, "partial",
        "US/global-dollar financial conditions: policy rates, yields, spreads, stress, volatility, inflation expectations",
        "CSV", "feed JSONL + derived series", "$0",
        ("load public FRED CSV series", "drop missing sentinels", "emit dated financial-state observations"),
        ("financial condition facts", "priced-in macro context", "credit/rates series"),
        ("financial_indicator", "country_region"),
    ),
    DataSourceSpec(
        "bis_financial_stats", "BIS global financial statistics", "financial_conditions", 1, "partial",
        "globally-comparable central-bank policy rates, nominal effective exchange rates, and the "
        "credit-to-GDP gap across the G20 + key emerging markets",
        "REST/SDMX", "feed JSONL + derived series", "$0",
        ("GET keyless BIS SDMX-REST v2 per economy", "parse SDMX-JSON observations",
         "emit dated policy-rate / EER / credit-gap series"),
        ("global cost-of-money facts", "FX/credit-cycle pricing context", "capital-leverage early-warning"),
        ("country_region", "financial_indicator"),
        "De-US-biases the pricing/capital layers with one consistent cross-country methodology.",
    ),
    DataSourceSpec(
        "worldbank_capital_flows", "World Bank capital-flow indicators", "capital", 1, "partial",
        "global cross-country capital account: FDI in/out, portfolio equity/investment, external & "
        "private-nonguaranteed debt, gross capital formation, equity-market cap, private credit",
        "REST", "feed JSONL + derived series", "$0",
        ("GET keyless World Bank v2 per indicator/country", "drop null vintages",
         "emit dated capital-flow series routed to the capital layer"),
        ("global capital-flow facts", "private/portfolio/debt flow series", "leverage build-up baseline"),
        ("country_region", "financial_indicator"),
        "Fills the capital layer's biggest gap — non-US private/portfolio/debt flows.",
    ),
    DataSourceSpec(
        "global_policy_activity", "Global (UK + EU) regulatory activity", "policy", 1, "partial",
        "non-US regulatory-activity counts over time: UK legislation per structural policy topic + "
        "EU legal acts per year by type (EUR-Lex)",
        "REST/SPARQL", "feed JSONL + derived series", "$0",
        ("GET UK legislation.gov.uk OpenSearch totalResults per topic-year",
         "query EUR-Lex CELLAR SPARQL for EU acts per year by resource type",
         "emit annual policy-activity count series"),
        ("non-US policy-tempo facts", "UK/EU regulatory-activity series", "regime-shift leading context"),
        ("policy", "country_region"),
        "Adds UK + EU jurisdictions to a policy layer that was US/AU/CA-only.",
    ),
    DataSourceSpec(
        "grid_power_bottlenecks", "FRED/LBNL grid and materials bottlenecks", "physical_supply", 1, "partial",
        "US grid-equipment prices, metal-mining output, and interconnection queue capacity",
        "FRED CSV + LBNL published queue totals", "feed JSONL + derived series", "$0",
        ("load public annual FRED CSVs", "preserve LBNL queue-capacity feed bytes", "reuse existing series keys"),
        ("grid bottleneck facts", "materials supply series", "AI power constraint context"),
        ("material", "technology", "country_region"),
        "US-centric but forecast-critical for AI power and electrical infrastructure bottlenecks.",
    ),
    DataSourceSpec(
        "ecb_fx", "ECB euro foreign-exchange reference rates", "financial_conditions", 1, "partial",
        "global FX rates against EUR across major currencies", "official ZIP/CSV",
        "feed JSONL + derived series", "$0",
        ("load ECB historical ZIP", "drop N/A cells", "emit dated currency-per-EUR observations"),
        ("FX reference-rate facts", "global financial conditions", "currency series"),
        ("financial_indicator", "country_region"),
    ),
    DataSourceSpec(
        "nih_reporter", "NIH RePORTER grants", "capital_flows", 2, "partial",
        "US biomedical grants", "API/export", "derived series + raw responses", "$0",
        ("backfill awards", "extract diseases/modalities/institutions"), ("grant facts", "funding series"),
    ),
    DataSourceSpec(
        "nsf_awards", "NSF awards", "capital_flows", 3, "partial",
        "US science/engineering grants", "Research.gov Award API", "feed JSONL + derived series", "$0",
        ("load topic-year award counts", "link technology subjects", "preserve feed raw bytes"),
        ("grant facts", "science funding series", "institution links"),
    ),
    DataSourceSpec(
        "cordis", "EU CORDIS grants", "capital_flows", 3, "partial",
        "EU R&D grants", "bulk/API", "derived series", "$0",
        ("load projects", "link organizations/countries/topics"), ("grant facts", "EU funding series"),
    ),
    DataSourceSpec(
        "usaspending_sam", "USAspending / SAM.gov", "capital_flows", 3, "partial",
        "US contracts/procurement", "official API", "feed JSONL + derived facts", "$0/no auth",
        ("load topic-year aggregate awards/obligations", "preserve feed raw bytes", "link procurement topics"),
        ("contract facts", "procurement obligation series", "public demand-pressure context"),
    ),
    DataSourceSpec(
        "un_comtrade", "UN Comtrade", "trade", 1, "partial",
        "global bilateral trade", "API", "derived series + raw batches", "$0 preview/free key",
        ("backfill HS flows", "compute supplier concentration", "link commodities/countries"),
        ("trade facts", "import-dependency series", "HHI edges"),
        ("country_region", "material"),
    ),
    DataSourceSpec(
        "baci", "CEPII BACI", "trade", 2, "partial",
        "harmonized global bilateral trade", "flat files", "Parquet + derived series", "$0",
        ("load yearly HS flows", "compute concentration by importer/material"), ("supply-dependency edges",),
    ),
    DataSourceSpec(
        "usgs_minerals", "USGS minerals", "physical_supply", 1, "partial",
        "global/US mineral production and reserves", "bulk/static", "derived series", "$0",
        ("parse mineral summaries", "extract production/reserves/import reliance"), ("mineral facts", "supply series"),
        ("material", "country_region"),
    ),
    DataSourceSpec(
        "eia_iea_ember_owid", "Energy stack: EIA/IEA/Ember/OWID", "physical_supply", 1, "partial",
        "global energy production, mix, prices, adoption", "API/bulk", "derived series", "$0 core; IEA may be limited",
        ("backfill energy histories", "link countries/fuels/technologies"), ("energy facts", "adoption series"),
    ),
    DataSourceSpec(
        "nasa_gistemp", "NASA GISTEMP temperature anomalies", "climate", 1, "partial",
        "global and hemispheric monthly/annual surface-temperature anomalies", "CSV", "feed JSONL + derived series", "$0",
        ("load official NASA GISS tables", "emit monthly and annual anomaly series"),
        ("climate baseline facts", "temperature anomaly series", "physical risk context"),
        ("climate_indicator", "country_region"),
    ),
    DataSourceSpec(
        "noaa_gml_greenhouse_gases", "NOAA GML greenhouse gas trends", "climate", 1, "partial",
        "global monthly CO2/CH4/N2O and Mauna Loa CO2 atmospheric concentrations", "text tables",
        "feed JSONL + derived series", "$0",
        ("load official NOAA GML trend files", "emit monthly means and trend/adjusted series"),
        ("atmospheric concentration facts", "climate forcing baseline series"),
        ("climate_indicator",),
    ),
    DataSourceSpec(
        "noaa_enso", "NOAA PSL ENSO indices", "climate", 1, "partial",
        "monthly ocean-atmosphere state: ONI, Nino 3.4 SST, SOI", "text tables",
        "feed JSONL + derived series", "$0",
        ("load official NOAA PSL correlation files", "emit monthly ENSO index series"),
        ("ENSO state facts", "climate regime series", "agriculture/weather risk context"),
        ("climate_indicator",),
    ),
    DataSourceSpec(
        "noaa_climate_indices", "NOAA PSL broad climate indices", "climate", 2, "partial",
        "monthly PDO, NAO, AO, PNA, and West Pacific circulation regimes", "text tables",
        "feed JSONL + derived series", "$0",
        ("load official NOAA PSL correlation files", "drop missing sentinels", "emit monthly regime-index series"),
        ("climate regime facts", "teleconnection series", "weather/energy/agriculture context"),
        ("climate_indicator",),
    ),
    DataSourceSpec(
        "noaa_nsidc_sea_ice", "NOAA/NSIDC Sea Ice Index", "climate", 1, "partial",
        "monthly Arctic and Antarctic sea-ice extent and area", "CSV",
        "feed JSONL + derived series", "$0",
        ("load official v4 monthly CSV files", "drop -9999 sentinels", "emit extent and area series"),
        ("sea-ice state facts", "polar climate series", "shipping/albedo context"),
        ("climate_indicator",),
    ),
    DataSourceSpec(
        "noaa_swpc_solar", "NOAA SWPC observed solar and space weather", "space_weather", 1, "partial",
        "global solar-cycle, geomagnetic, and X-ray flux physical state", "JSON API",
        "feed JSONL + derived series", "$0",
        ("load observed SWPC JSON endpoints", "exclude forecast probability endpoints", "daily-aggregate rolling feeds"),
        ("solar-cycle facts", "geomagnetic Kp facts", "GOES X-ray flux facts"),
        ("space_weather_indicator",),
    ),
    DataSourceSpec(
        "world_bank_imf_oecd_eurostat_bis", "Macro stack", "macro", 2, "partial",
        "global country macro/financial indicators", "REST/SDMX", "derived series", "$0",
        ("backfill country-year/month series", "quality audit freshness/completeness"), ("macro facts", "country series"),
    ),
    DataSourceSpec(
        "ilo_labor", "ILO labour-market indicators", "labour", 2, "partial",
        "major-economy annual labour-market indicators", "ILOSTAT CSV API", "feed JSONL + derived series", "$0",
        ("load pinned annual unemployment and employment-ratio slices", "drop missing values", "audit country gaps"),
        ("labour-market facts", "employment/unemployment series", "social-economy baseline"),
        ("country_region", "labour_indicator"),
    ),
    DataSourceSpec(
        "faostat", "FAOSTAT agriculture", "physical_supply", 2, "partial",
        "global agricultural production", "bulk/API", "derived series", "$0",
        ("load production/trade balances", "link crops/countries"), ("agriculture facts", "food supply series"),
    ),
    DataSourceSpec(
        "gdelt", "GDELT events/news", "news_events", 1, "partial_metered",
        "global news/event firehose", "API/BigQuery", "rolling raw snippets + event facts",
        "API $0; BigQuery scan-capped", ("query rolling windows", "extract event facts", "discard bulk raw after hash"),
        ("event facts", "narrative saturation", "country/company/technology mentions"),
        ("country_region", "company", "technology"),
    ),
    DataSourceSpec(
        "eonet", "NASA EONET natural events", "earth_events", 2, "partial",
        "global natural hazards and Earth-observed events", "API", "feed JSONL + derived series", "$0",
        ("collect rolling event list", "cap future-dated geometry rows", "aggregate by category/date/open state"),
        ("hazard event facts", "open natural-event series", "category-linked event context"),
        ("earth_event_type", "country_region"),
    ),
    DataSourceSpec(
        "usgs_earthquakes", "USGS Earthquake Hazards", "earth_events", 2, "partial",
        "global earthquake events M4.5+ with magnitude and impact flags", "API", "feed JSONL + derived series", "$0",
        ("collect rolling GeoJSON events", "cap future-dated event rows", "aggregate by magnitude/tsunami/felt/significance"),
        ("earthquake event facts", "magnitude-band series", "hazard severity context"),
        ("earth_event_type", "country_region"),
    ),
    DataSourceSpec(
        "gdacs_alerts", "GDACS global disaster alerts", "earth_events", 2, "partial",
        "global disaster alerts with humanitarian-impact severity", "API", "feed JSONL + derived series", "$0",
        ("collect rolling public GeoJSON alerts", "aggregate by type/alert/country/open state"),
        ("disaster alert facts", "alert-level series", "country hazard context"),
        ("earth_event_type", "country_region"),
    ),
    DataSourceSpec(
        "common_crawl_news", "Common Crawl News", "news_events", 4, "deferred_heavy",
        "global web news corpus", "S3/WARC", "object storage extracts", "storage/compute heavy; defer",
        ("sample domain whitelist", "extract article text", "dedupe GDELT"), ("article facts", "source credibility"),
    ),
    DataSourceSpec(
        "acled_ucdp", "ACLED / UCDP conflict", "geopolitics", 2, "partial",
        "global conflict events", "download/API", "derived event facts", "$0/free key",
        ("load event rows", "aggregate by actor/country/month"), ("conflict facts", "risk series"),
    ),
    DataSourceSpec(
        "vdem_wgi", "V-Dem / WGI governance", "geopolitics", 2, "partial",
        "global governance country-year", "download/API", "derived series", "$0",
        ("load country-year indices", "audit lag/staleness"), ("governance facts", "country series"),
    ),
    DataSourceSpec(
        "policy_stack", "Policy stack: Federal Register, EUR-Lex, BIS, OFAC, MOFCOM", "policy", 1, "partial",
        "US/EU/China/export-control/sanctions policy", "API/scrape", "raw docs + extracted facts",
        "$0; possible proxy for CN", ("store exact text", "extract entity/action/effective date", "link entities"),
        ("policy facts", "sanctions/export-control edges", "regulatory risk series"),
    ),
    DataSourceSpec(
        "land_permit_source_registry", "Official/open land-permit source registry", "land_use", 1, "partial",
        "global official/open source-target manifest for land permits, EIA registers, concessions, and mining cadastres",
        "curated official/open URLs; no portal scraping by default", "feed JSONL + SQLite source target rows",
        "$0; no bulk fetch; no paid processing",
        (
            "write source-target manifest",
            "register official/open source targets with manifest provenance",
            "rank portals for later jurisdiction collectors",
        ),
        (
            "official source target facts",
            "jurisdiction/source-type coverage map",
            "collector backlog targets",
            "approval-gated scrape/geospatial/OCR plan",
        ),
        ("country_region", "project", "permit", "land_parcel"),
        "This is the tactical source map for the land-permit sprint; it is not a claim that permit rows are collected.",
    ),
    DataSourceSpec(
        "land_permits_cadastre", "Land permits, cadastre, zoning, and parcels", "land_use", 1, "partial_mixed",
        "global view assembled from national/subnational planning, zoning, cadastre, parcel, and building-permit portals; completeness varies by jurisdiction",
        "open government portals first; paid parcel vendors deferred", "object storage geospatial/raw docs + SQLite derived facts/edges",
        "$0 open portals first; paid parcel vendors and cloud geospatial joins require approval",
        (
            "inventory jurisdiction feeds by country/region",
            "store raw permit pages, notices, and geospatial extracts with hashes",
            "normalize parcel/project/company identifiers",
            "extract permit stage, decision, expiry, appeal, and effective dates",
            "snapshot as-of visibility for leak-safe forecasting",
        ),
        (
            "land-permit facts",
            "parcel/project/company/country edges",
            "permit-stage time series",
            "zoning and land-use status facts",
        ),
        ("company", "country_region", "project", "land_parcel", "permit"),
        "This is not a single worldwide feed; it is a jurisdiction-by-jurisdiction spine for official land-use decisions.",
    ),
    DataSourceSpec(
        "resource_concessions_contracts", "Mining/energy concessions, leases, and land contracts", "land_use", 1, "partial",
        "global but jurisdiction-fragmented concessions, leases, licenses, and land contracts for mining, energy, and infrastructure",
        "national mining/energy cadastres, open contract registries, and EITI-style disclosures",
        "object storage raw docs/geospatial extracts + SQLite derived facts/edges", "$0/open portals first; paid or metered geocoding requires approval",
        (
            "collect open concession/license registers by jurisdiction",
            "preserve contract/license documents and map layers by content hash",
            "extract holder, commodity, area, grant, renewal, expiry, and status dates",
            "link company, project, material, country, and parcel entities",
        ),
        (
            "concession facts",
            "lease/license status facts",
            "company/project/material/country edges",
            "pre-production capacity and supply-option signals",
        ),
        ("company", "country_region", "project", "material", "land_parcel", "permit"),
        "Priority because concessions are early signals for mines, wells, power projects, factories, and grid corridors.",
    ),
    DataSourceSpec(
        "environmental_planning_eia", "Environmental impact and planning approvals", "land_use_policy", 1, "partial",
        "global/national EIA, planning, public-comment, and approval registers where official portals expose dated decisions",
        "official EIA/planning registers and public notice portals", "raw docs + object storage attachments + SQLite derived facts",
        "$0/open portals first; OCR, translation, and cloud extraction require approval",
        (
            "collect dated public notices, EIA filings, hearing records, and decisions",
            "hash raw PDFs/HTML and preserve source URLs",
            "extract project, sponsor, location, approval condition, appeal, and public-comment windows",
            "bridge decisions into land-permit and project-state facts",
        ),
        (
            "EIA facts",
            "planning-approval facts",
            "appeal/public-comment facts",
            "project regulatory-stage series",
        ),
        ("company", "country_region", "project", "permit", "policy"),
        "Captures the official process around a permit, not only the final land-use record.",
    ),
    DataSourceSpec(
        "open_geospatial_land_context", "Open geospatial land-use context", "land_use_context", 2, "planned_free",
        "global open land-use, buildings, roads, places, forest, and land-cover context; not official permit decisions",
        "OpenStreetMap/Overture-style extracts, public land-cover layers, and forest/protected-area layers",
        "object storage geospatial partitions + SQLite derived spatial summaries", "$0 downloads; tiling and cloud joins require approval",
        (
            "keep bulk geospatial layers off laptop",
            "derive compact country/project/parcel context summaries",
            "join permits and concessions to nearby infrastructure, protected areas, and land-cover classes",
        ),
        (
            "land-context facts",
            "project proximity features",
            "parcel/location risk flags",
            "infrastructure and land-cover edges",
        ),
        ("country_region", "project", "land_parcel", "infrastructure_asset"),
        "Support layer only: useful for siting and risk context, but it must not be mistaken for an approval record.",
    ),
    DataSourceSpec(
        "grid_interconnection_transmission", "Grid interconnection, transmission siting, and right-of-way queues",
        "physical_supply", 1, "planned_free",
        "global but utility/ISO/regulator-fragmented interconnection queues, transmission permits, right-of-way decisions, and grid-connection stages",
        "ISO/RTO queues, utility/regulator portals, transmission-planning dockets, and official siting registers",
        "object storage raw queue snapshots/docs + SQLite derived facts/edges",
        "$0/open portals first; cloud joins, paid geospatial layers, and scrape-at-scale require approval",
        (
            "inventory queue and siting portals by market/jurisdiction",
            "preserve dated queue snapshots, dockets, and planning notices by content hash",
            "extract project, sponsor, MW, technology, interconnection point, queue status, withdrawal, and approval dates",
            "link grid nodes/corridors to land-permit and project entities",
        ),
        (
            "interconnection-stage facts",
            "transmission-siting facts",
            "project/grid-node/company edges",
            "queue-withdrawal and queue-duration series",
        ),
        ("company", "country_region", "project", "permit", "infrastructure_asset", "technology"),
        "Often the binding constraint after a project has land and capital; especially important for AI campuses, renewables, storage, mines, and factories.",
    ),
    DataSourceSpec(
        "water_rights_stress", "Water rights, withdrawals, basin stress, and discharge permissions",
        "physical_supply", 1, "planned_free",
        "global/regional water-rights and withdrawal permits where exposed, plus basin stress, drought, aquifer, and discharge context",
        "official water-rights registers, environmental agencies, hydrology datasets, and open basin-stress layers",
        "object storage raw registers/geodata + SQLite compact facts/features",
        "$0/open portals first; paid water datasets, geocoding, and cloud geospatial joins require approval",
        (
            "inventory water-rights and discharge-permit portals by jurisdiction",
            "store raw permit pages, basin layers, and hydrology snapshots by content hash",
            "extract holder, source basin/aquifer, withdrawal/discharge volume, permit status, expiry, and restrictions",
            "join project locations to basin stress and protected/wetland context",
        ),
        (
            "water-right facts",
            "withdrawal/discharge permit facts",
            "basin-stress features",
            "project/water-source/country edges",
        ),
        ("company", "country_region", "project", "permit", "water_basin", "infrastructure_asset"),
        "Water is a first-order siting constraint for data centers, mining, semiconductors, hydrogen, agriculture, and thermal power.",
    ),
    DataSourceSpec(
        "industrial_facility_air_water_permits", "Industrial facility air, water, waste, and construction permits",
        "physical_supply", 2, "planned_free",
        "global/national facility permit registers where official portals expose dated industrial air, water, waste, construction, or operating approvals",
        "environmental agencies, facility registries, industrial-zone portals, and local planning/building permit portals",
        "object storage raw notices/PDFs + SQLite derived facility facts",
        "$0/open portals first; OCR, translation, paid facility databases, and LLM extraction require approval",
        (
            "collect official facility permit notices and decision registers",
            "hash raw permit PDFs/HTML and preserve source URLs",
            "extract facility, sponsor, process type, capacity, pollutant/waste stream, permit condition, appeal, and effective dates",
            "link facilities to company, project, land parcel, material, and technology entities",
        ),
        (
            "facility-permit facts",
            "capacity-permission facts",
            "air/water/waste condition facts",
            "facility/company/project edges",
        ),
        ("company", "country_region", "project", "permit", "infrastructure_asset", "material", "technology"),
        "This catches factories, smelters, fabs, battery plants, chemical plants, LNG, cement, data centers, and other capacity that never becomes real without permits.",
    ),
    DataSourceSpec(
        "ports_logistics_capacity", "Ports, terminals, rail corridors, and logistics capacity",
        "physical_supply", 2, "planned_mixed",
        "global port/terminal/rail/logistics capacity, congestion, expansion permits, and route chokepoints assembled from open official sources first",
        "port authorities, customs/trade releases, infrastructure project registers, rail/terminal filings, and deferred AIS/satellite vendors",
        "object storage raw releases/geodata + SQLite derived logistics facts",
        "$0/open portals first; AIS/satellite/paid logistics data and cloud joins require approval",
        (
            "inventory official port, terminal, rail, and corridor sources",
            "preserve dated capacity/congestion/project releases and map layers by content hash",
            "extract berth/terminal/rail capacity, expansion stage, disruption, permit, and commissioning dates",
            "join logistics corridors to trade, materials, project, and company entities",
        ),
        (
            "logistics-capacity facts",
            "port/terminal expansion facts",
            "corridor disruption facts",
            "material-route dependency edges",
        ),
        ("company", "country_region", "project", "infrastructure_asset", "material"),
        "Useful when supply exists on paper but export corridors, terminals, or chokepoint routes ration what can reach market.",
    ),
    DataSourceSpec(
        "carbon_storage_pore_space", "Carbon storage pore-space, Class VI, and sequestration permits",
        "land_use_policy", 2, "planned_free",
        "global/national carbon storage leases, Class VI-style injection permits, pore-space rights, and storage-site approvals where official portals expose dated records",
        "environmental regulators, energy ministries, state/provincial primacy agencies, and offshore leasing portals",
        "object storage raw permit docs/geodata + SQLite derived storage facts",
        "$0/open portals first; OCR/geospatial joins and paid subsurface data require approval",
        (
            "collect dated storage/injection permit applications, approvals, withdrawals, and conditions",
            "preserve raw dockets, maps, and public notices by content hash",
            "extract operator, site, pore-space owner, injection volume, permit class, status, expiry, and appeal dates",
            "link storage sites to land, pipeline, company, industrial-source, and policy entities",
        ),
        (
            "storage-permit facts",
            "pore-space lease/status facts",
            "operator/site/pipeline edges",
            "permitted-storage-capacity series",
        ),
        ("company", "country_region", "project", "permit", "land_parcel", "infrastructure_asset"),
        "Pore space is a land-permit cousin: CCS/DAC economics can move from capture technology to scarce permitted storage sites.",
    ),
    DataSourceSpec(
        "regulatory_health", "FDA / EMA / clinical/regulatory", "policy", 3, "partial",
        "drug/device approvals, safety, trials", "API/bulk", "derived facts", "$0",
        ("load approvals/trials", "link drug/company/target"), ("approval facts", "trial progress series"),
    ),
    DataSourceSpec(
        "clinicaltrials_gov", "ClinicalTrials.gov", "clinical_regulatory", 2, "partial",
        "global trial registry with strong US/NLM coverage", "API", "feed JSONL + derived series", "$0",
        ("query forecast-relevant therapeutic topics", "aggregate first-posted studies", "snapshot status/phase counts"),
        ("trial posting facts", "pipeline phase/status series", "therapeutic technology links"),
        ("technology", "company", "institution"),
    ),
    DataSourceSpec(
        "openfda_drugsfda", "openFDA Drugs@FDA", "clinical_regulatory", 2, "partial",
        "US FDA drug applications and approval submissions", "API", "feed JSONL + derived series", "$0",
        ("query forecast-relevant approved drugs", "aggregate approved submissions", "snapshot application/class counts"),
        ("approval facts", "regulatory crossing series", "application document provenance"),
        ("technology", "company"),
    ),
    DataSourceSpec(
        "talent_stack", "ORCID / GitHub Archive / job postings", "talent", 4, "planned_mixed",
        "global talent and labor movement proxies", "dumps/BigQuery/APIs", "derived series",
        "$0 for ORCID/GH; job postings likely paid/deferred", ("extract affiliations/repos/skills", "link institutions"),
        ("talent-flow facts", "skill-demand series"),
    ),
    DataSourceSpec(
        "shipping_satellite", "AIS / satellite / alt-data", "physical_supply", 5, "deferred_paid",
        "global logistics and physical activity", "paid APIs", "derived facts only", "paid; defer until measured ROI",
        ("pilot only for validated bottlenecks", "compare to free proxies"), ("logistics facts", "capacity signals"),
    ),
)


TOP_ENTITIES: tuple[TopEntitySpec, ...] = (
    # Regions / countries.
    *(
        TopEntitySpec("country_region", name, "geography", aliases, ("global_view", "country_region"), note)
        for name, aliases, note in (
            ("World", ("WLD", "Global", "Earth"), "Aggregate global reference entity."),
            ("United States", ("USA", "US", "America"), "Top economy, capital market, science and policy source."),
            ("China", ("CHN", "People's Republic of China", "PRC"), "Manufacturing, patents, critical minerals, policy."),
            ("European Union", ("EU", "Europe"), "Policy, markets, industrial capacity and regulation."),
            ("India", ("IND",), "Population, demand growth, services, manufacturing shift."),
            ("Japan", ("JPN",), "Advanced manufacturing, robotics, energy import exposure."),
            ("South Korea", ("KOR", "Republic of Korea"), "Memory, batteries, shipbuilding, electronics."),
            ("Taiwan", ("TWN",), "Semiconductor manufacturing concentration."),
            ("Germany", ("DEU",), "Industrial manufacturing, autos, chemicals, energy transition."),
            ("United Kingdom", ("GBR", "UK"), "Finance, biotech, AI policy, Companies House backbone."),
            ("France", ("FRA",), "Nuclear, aerospace, EU policy."),
            ("Canada", ("CAN",), "Mining, energy, AI research."),
            ("Australia", ("AUS",), "Lithium, iron ore, LNG, critical minerals."),
            ("Brazil", ("BRA",), "Agriculture, iron ore, energy, emerging-market demand."),
            ("Mexico", ("MEX",), "Nearshoring, autos, electronics."),
            ("Vietnam", ("VNM",), "Manufacturing relocation, electronics supply chain."),
            ("Indonesia", ("IDN",), "Nickel, batteries, emerging-market demand."),
            ("Saudi Arabia", ("SAU",), "Oil, capital flows, energy transition strategy."),
            ("United Arab Emirates", ("ARE", "UAE"), "Energy, capital, AI infrastructure."),
            ("Russia", ("RUS",), "Energy, uranium, sanctions, conflict risk."),
            ("Ukraine", ("UKR",), "Conflict, agriculture, defense, energy infrastructure."),
            ("South Africa", ("ZAF",), "PGMs, mining, power constraints."),
            ("Democratic Republic of the Congo", ("DRC", "COD"), "Cobalt and copper supply concentration."),
            ("Chile", ("CHL",), "Copper and lithium supply."),
            ("Argentina", ("ARG",), "Lithium triangle and agriculture."),
        )
    ),
    # Companies and institutions.
    *(
        TopEntitySpec("company", name, domain, aliases, ("global_view", "company"), note)
        for name, domain, aliases, note in (
            ("NVIDIA", "semiconductors", ("NVIDIA Corporation", "NVDA"), "AI accelerator demand and software moat."),
            ("Taiwan Semiconductor Manufacturing Company", "semiconductors", ("Taiwan Semiconductor Manufacturing Company Limited", "TSMC", "TSM"), "Leading foundry and geopolitical choke point."),
            ("ASML", "semiconductor equipment", ("ASML Holding",), "EUV lithography bottleneck."),
            ("Samsung Electronics", "semiconductors", ("Samsung Electronics Co Ltd", "Samsung", "005930.KS"), "Memory, foundry, electronics."),
            ("SK Hynix", "semiconductors", ("SK hynix Inc", "Hynix"), "HBM and memory supply."),
            ("Intel", "semiconductors", ("Intel Corporation", "INTC"), "Foundry and CPU incumbent."),
            ("AMD", "semiconductors", ("Advanced Micro Devices, Inc.", "Advanced Micro Devices", "AMD"), "AI accelerator and CPU competitor."),
            ("Broadcom", "semiconductors", ("Broadcom Inc.", "AVGO"), "ASIC/networking exposure."),
            ("Qualcomm", "semiconductors", ("Qualcomm Incorporated", "QCOM"), "Mobile and edge AI chips."),
            ("Apple", "technology", ("Apple Inc.", "AAPL"), "Consumer hardware, silicon demand, services."),
            ("Microsoft", "technology", ("Microsoft Corporation", "MSFT"), "Cloud/AI capital spending."),
            ("Alphabet", "technology", ("Alphabet Inc.", "Google", "GOOGL", "GOOG"), "Cloud, AI models, advertising."),
            ("Amazon", "technology", ("Amazon.com, Inc.", "AMZN", "AWS"), "Cloud/AI infrastructure and logistics."),
            ("Meta Platforms", "technology", ("Meta", "META"), "AI capex and social distribution."),
            ("OpenAI", "AI", (), "Frontier model developer and demand driver."),
            ("Anthropic", "AI", ("Anthropic PBC",), "Frontier model developer and enterprise AI demand signal."),
            ("xAI", "AI", ("X.AI Corp.", "XAI"), "Frontier model developer and AI infrastructure demand signal."),
            ("Mistral AI", "AI", (), "European frontier/open-weight model developer."),
            ("Databricks", "technology", (), "Enterprise data/AI platform and model-serving demand signal."),
            ("Snowflake", "technology", ("Snowflake Inc.", "SNOW"), "Enterprise data cloud and AI data-platform demand signal."),
            ("Oracle", "technology", ("Oracle Corporation", "ORCL"), "Cloud database and AI infrastructure capacity."),
            ("CoreWeave", "technology", ("CoreWeave, Inc.", "CRWV"), "GPU cloud capacity and AI infrastructure financing signal."),
            ("Dell Technologies", "technology", ("Dell Technologies Inc.", "DELL"), "AI servers, storage and enterprise infrastructure."),
            ("Super Micro Computer", "technology", ("Super Micro Computer, Inc.", "Supermicro", "SMCI"), "AI server integration and rack-scale supply."),
            ("Arista Networks", "technology", ("Arista Networks, Inc.", "ANET"), "AI data-center networking and switching."),
            ("Digital Realty", "data_centers", ("Digital Realty Trust, Inc.", "DLR"), "Global data-center real estate and power demand."),
            ("Equinix", "data_centers", ("Equinix, Inc.", "EQIX"), "Global colocation/data-center interconnect footprint."),
            ("ARM Holdings", "semiconductors", ("ARM Holdings plc", "ARM", "ARM.L"), "CPU/IP architecture for mobile, edge and AI silicon."),
            ("Tesla", "autos_energy", ("Tesla, Inc.", "TSLA"), "EVs, batteries, autonomy, humanoid robotics."),
            ("BYD", "autos_energy", ("BYD Company Limited", "BYD Company", "1211.HK"), "EVs and battery vertical integration."),
            ("CATL", "batteries", ("Contemporary Amperex Technology Co., Limited", "Contemporary Amperex Technology",), "Largest EV battery supplier."),
            ("Samsung SDI", "batteries", ("Samsung SDI Co., Ltd.", "006400.KS"), "Battery cells and energy-storage supply."),
            ("POSCO Holdings", "materials", ("POSCO Holdings Inc.", "PKX", "005490.KS"), "Steel and battery-materials supply chain."),
            ("Toyota", "autos", ("Toyota Motor Corporation", "TM"), "Auto incumbent and solid-state battery signal."),
            ("Panasonic", "batteries", ("Panasonic Holdings Corporation", "PCRFY"), "Battery supplier and Toyota/Tesla ecosystem."),
            ("LG Energy Solution", "batteries", ("LG Energy Solution Ltd", "LGES"), "Major global battery supplier."),
            ("Siemens Energy", "grid", ("Siemens Energy AG", "ENR.DE"), "Grid equipment and turbines."),
            ("Hitachi Energy", "grid", (), "Transformers and grid equipment."),
            ("Schneider Electric", "grid", ("Schneider Electric SE", "SU.PA"), "Electrical equipment and automation."),
            ("Eaton", "grid", ("Eaton Corporation plc", "ETN"), "Electrical equipment and power distribution."),
            ("GE Vernova", "grid", ("GE Vernova Inc.", "GEV"), "Power generation and grid equipment."),
            ("ABB", "grid", ("ABB Ltd", "ABBN.SW"), "Electrification and industrial automation."),
            ("Vertiv", "grid", ("Vertiv Holdings Co", "VRT"), "Data-center power, cooling and thermal-management equipment."),
            ("Quanta Services", "grid", ("Quanta Services, Inc.", "PWR"), "Grid construction, transmission and utility infrastructure services."),
            ("Hubbell", "grid", ("Hubbell Incorporated", "HUBB"), "Electrical and utility components."),
            ("Prysmian", "grid", ("Prysmian S.p.A.", "PRY.MI"), "Power cables and grid interconnect materials."),
            ("Nexans", "grid", ("Nexans S.A.", "NEX.PA"), "Power cables and electrification infrastructure."),
            ("NKT", "grid", ("NKT A/S", "NKT.CO"), "High-voltage power cables."),
            ("Mitsubishi Electric", "grid", ("Mitsubishi Electric Corporation", "6503.T"), "Power systems, factory automation and electrical equipment."),
            ("Toshiba", "grid", ("Toshiba Corporation", "6502.T"), "Power systems, grid and industrial equipment."),
            ("LS Electric", "grid", ("LS ELECTRIC Co., Ltd.", "LS Industrial Systems", "010120.KS"), "Korean grid equipment and automation."),
            ("State Grid Corporation of China", "grid", ("State Grid", "SGCC"), "China transmission and grid investment anchor."),
            ("China Southern Power Grid", "grid", ("CSG",), "Southern China transmission and distribution grid operator."),
            ("WEG", "grid", ("WEG S.A.", "WEGE3.SA"), "Motors, transformers and electrification equipment."),
            ("S&C Electric", "grid", ("S&C Electric Company",), "Switchgear, grid automation and distribution equipment."),
            ("HD Hyundai Electric", "grid", ("HD Hyundai Electric Co., Ltd.", "Hyundai Electric", "267260.KS"), "Transformers and high-voltage electrical equipment."),
            ("Larsen & Toubro", "grid", ("L&T", "Larsen & Toubro Limited"), "Engineering, grid, power and infrastructure construction."),
            ("First Solar", "solar", ("First Solar, Inc.", "FSLR"), "Thin-film solar manufacturing."),
            ("LONGi Green Energy", "solar", ("LONGi", "LONGi Green Energy Technology"), "Solar PV manufacturing."),
            ("JinkoSolar", "solar", ("JinkoSolar Holding Co., Ltd.", "JKS"), "Solar module manufacturing."),
            ("Trina Solar", "solar", ("Trina Solar Co., Ltd.",), "Global solar module and tracker supplier."),
            ("Canadian Solar", "solar", ("Canadian Solar Inc.", "CSIQ"), "Solar modules, projects and storage."),
            ("Applied Materials", "semiconductor equipment", ("Applied Materials, Inc.", "AMAT"), "Semiconductor process equipment and AI capex exposure."),
            ("Lam Research", "semiconductor equipment", ("Lam Research Corporation", "LRCX"), "Etch/deposition equipment for advanced chips and memory."),
            ("KLA", "semiconductor equipment", ("KLA Corporation", "KLAC"), "Process control and semiconductor inspection equipment."),
            ("Tokyo Electron", "semiconductor equipment", ("Tokyo Electron Limited", "8035.T"), "Semiconductor production equipment."),
            ("ASM International", "semiconductor equipment", ("ASM International N.V.", "ASM.AS"), "Atomic-layer deposition and advanced process equipment."),
            ("Advantest", "semiconductor equipment", ("Advantest Corporation", "6857.T"), "Semiconductor test equipment for advanced chips."),
            ("Teradyne", "semiconductor equipment", ("Teradyne, Inc.", "TER"), "Automated semiconductor test equipment."),
            ("BE Semiconductor Industries", "semiconductor equipment", ("Besi", "BESI.AS"), "Advanced packaging and assembly equipment."),
            ("ASMPT", "semiconductor equipment", ("ASM Pacific Technology", "0522.HK"), "Semiconductor assembly and packaging equipment."),
            ("Micron Technology", "semiconductors", ("Micron Technology, Inc.", "MU"), "DRAM/NAND and HBM supply."),
            ("Marvell Technology", "semiconductors", ("Marvell Technology, Inc.", "MRVL"), "AI networking, custom silicon and storage semiconductors."),
            ("GlobalFoundries", "semiconductors", ("GlobalFoundries Inc.", "GFS"), "Specialty foundry capacity outside leading-edge Taiwan concentration."),
            ("United Microelectronics", "semiconductors", ("UMC", "United Microelectronics Corporation"), "Taiwan specialty foundry capacity."),
            ("Semiconductor Manufacturing International Corporation", "semiconductors", ("SMIC", "0981.HK"), "China foundry capacity and policy-sensitive semiconductor supply."),
            ("Hua Hong Semiconductor", "semiconductors", ("Hua Hong", "1347.HK"), "China specialty foundry capacity."),
            ("Infineon Technologies", "semiconductors", ("Infineon Technologies AG", "IFX.DE"), "Power semiconductors and automotive chips."),
            ("NXP Semiconductors", "semiconductors", ("NXP Semiconductors N.V.", "NXPI"), "Automotive and industrial semiconductors."),
            ("Renesas Electronics", "semiconductors", ("Renesas Electronics Corporation", "6723.T"), "Automotive and industrial microcontrollers."),
            ("Synopsys", "semiconductor software", ("Synopsys, Inc.", "SNPS"), "EDA and semiconductor IP tooling."),
            ("Cadence Design Systems", "semiconductor software", ("Cadence Design Systems, Inc.", "CDNS"), "EDA software and chip-design tooling."),
            ("Tencent", "technology", ("Tencent Holdings Limited", "TCEHY", "0700.HK"), "China cloud, games, payments and AI platform."),
            ("Alibaba", "technology", ("Alibaba Group Holding Limited", "BABA", "9988.HK"), "China cloud, ecommerce and AI infrastructure."),
            ("Albemarle", "materials", ("Albemarle Corporation", "ALB"), "Lithium chemicals."),
            ("SQM", "materials", ("Sociedad Quimica y Minera", "SQM"), "Lithium and iodine producer."),
            ("Glencore", "materials", ("GLEN.L",), "Metals, coal, trading."),
            ("BHP", "materials", ("BHP Group",), "Mining major."),
            ("Rio Tinto", "materials", ("Rio Tinto plc", "RIO"), "Mining major."),
            ("Shell", "energy", ("Shell plc", "SHEL", "SHEL.L"), "Oil, gas, LNG and energy-transition capital allocation."),
            ("BP", "energy", ("BP p.l.c.", "BP PLC", "BP.L"), "Oil, gas, trading and energy-transition capital allocation."),
            ("Saudi Aramco", "energy", ("Saudi Arabian Oil Company", "2222.SR"), "Oil supply, petrochemicals and capital allocation."),
            ("Exxon Mobil", "energy", ("Exxon Mobil Corporation", "XOM"), "Oil, gas, LNG, chemicals and carbon-management capital allocation."),
            ("Chevron", "energy", ("Chevron Corporation", "CVX"), "Oil, gas and LNG capital allocation."),
            ("TotalEnergies", "energy", ("TotalEnergies SE", "TTE"), "Oil, gas, LNG and energy-transition capital allocation."),
            ("Constellation Energy", "energy", ("Constellation Energy Corporation", "CEG"), "US nuclear generation and data-center power contracting."),
            ("Vistra", "energy", ("Vistra Corp.", "VST"), "US power generation and data-center power market exposure."),
            ("Talen Energy", "energy", ("Talen Energy Corporation", "TLN"), "US power generation and data-center nuclear/power contracting exposure."),
            ("NextEra Energy", "energy", ("NextEra Energy, Inc.", "NEE"), "US renewables, transmission and power-market capacity."),
            ("Iberdrola", "energy", ("Iberdrola, S.A.", "IBE.MC"), "Global renewables and grid utility investment."),
            ("Enel", "energy", ("Enel S.p.A.", "ENEL.MI"), "Global utility, renewables and distribution grid investment."),
            ("EDF", "energy", ("Electricite de France",), "Nuclear generation, grid and European power-system anchor."),
            ("Cameco", "energy", ("Cameco Corporation", "CCJ"), "Uranium mining and nuclear-fuel supply."),
            ("Centrus Energy", "energy", ("Centrus Energy Corp.", "LEU"), "Uranium enrichment and HALEU supply."),
            ("Kazatomprom", "energy", ("National Atomic Company Kazatomprom",), "Largest uranium producer and nuclear-fuel supply anchor."),
            ("Orano", "energy", ("Orano SA",), "Uranium mining, conversion, enrichment and nuclear fuel-cycle services."),
            ("Westinghouse Electric Company", "energy", ("Westinghouse Electric",), "Nuclear reactor technology and services."),
            ("Brookfield Renewable", "energy", ("Brookfield Renewable Partners", "BEP"), "Renewable power owner/operator and project-finance signal."),
            ("Vale", "materials", ("Vale S.A.", "VALE"), "Iron ore and nickel exposure."),
            ("Freeport-McMoRan", "materials", ("Freeport-McMoRan Inc.", "FCX"), "Copper producer."),
            ("Codelco", "materials", (), "State copper producer."),
            ("Anglo American", "materials", ("Anglo American plc", "AAL.L"), "Copper, iron ore, PGMs and diversified mining."),
            ("Teck Resources", "materials", ("Teck Resources Limited", "TECK"), "Copper and zinc mining exposure."),
            ("Antofagasta", "materials", ("Antofagasta plc", "ANTO.L"), "Copper producer."),
            ("Zijin Mining", "materials", ("Zijin Mining Group Co., Ltd.", "2899.HK"), "Copper, gold and lithium mining."),
            ("CMOC Group", "materials", ("China Molybdenum", "CMOC", "3993.HK"), "Cobalt, copper and molybdenum supply."),
            ("Ivanhoe Mines", "materials", ("Ivanhoe Mines Ltd.", "IVN.TO"), "Copper mining growth exposure."),
            ("First Quantum Minerals", "materials", ("First Quantum Minerals Ltd.", "FM.TO"), "Copper mining exposure."),
            ("Southern Copper", "materials", ("Southern Copper Corporation", "SCCO"), "Copper producer."),
            ("Linde", "industrial_gases", ("Linde plc", "LIN"), "Industrial gases for semiconductors, hydrogen and manufacturing."),
            ("Air Liquide", "industrial_gases", ("L'Air Liquide S.A.", "AI.PA"), "Industrial gases for hydrogen, semiconductors and healthcare."),
            ("Air Products and Chemicals", "industrial_gases", ("Air Products", "APD"), "Industrial gases and hydrogen projects."),
            ("BASF", "chemicals", ("BASF SE", "BAS.DE"), "Chemicals, battery materials and industrial demand signal."),
            ("Novo Nordisk", "biotech", ("Novo Nordisk A/S", "NVO"), "GLP-1 obesity/diabetes leader."),
            ("Eli Lilly", "biotech", ("Eli Lilly and Company", "LLY"), "GLP-1 obesity/diabetes leader."),
            ("AstraZeneca", "biotech", ("AstraZeneca PLC", "AZN", "AZN.L"), "Oncology, respiratory, rare disease and UK/EU pharma anchor."),
            ("GSK", "biotech", ("GSK plc", "GSK", "GSK.L"), "Vaccines, specialty medicines and UK pharma anchor."),
            ("Novartis", "biotech", ("NVS",), "Radioligand therapy and pharma."),
            ("Roche", "biotech", ("Roche Holding AG", "ROG.SW"), "Diagnostics and pharma."),
            ("Pfizer", "biotech", ("Pfizer Inc.", "PFE"), "Pharma and mRNA ecosystem."),
            ("Moderna", "biotech", ("Moderna, Inc.", "MRNA"), "mRNA platform company."),
            ("Thermo Fisher Scientific", "biotech", ("Thermo Fisher Scientific Inc.", "TMO"), "Life-science tools, bioprocessing and lab-equipment demand."),
            ("Danaher", "biotech", ("Danaher Corporation", "DHR"), "Life-science tools, diagnostics and bioprocessing equipment."),
            ("West Pharmaceutical Services", "biotech", ("West Pharmaceutical Services, Inc.", "WST"), "Injectable drug-delivery components and GLP-1 packaging bottleneck."),
            ("Catalent", "biotech", ("Catalent, Inc.", "Catalent Pharma Solutions", "CTLT"), "Biologics fill-finish and drug-manufacturing capacity."),
            ("Lonza", "biotech", ("Lonza Group AG", "LONN.SW"), "Biologics and pharmaceutical contract manufacturing."),
            ("Sartorius", "biotech", ("Sartorius AG", "SRT.DE"), "Bioprocessing equipment and consumables."),
            ("Illumina", "biotech", ("Illumina, Inc.", "ILMN"), "Sequencing equipment and genomics platform."),
            ("10x Genomics", "biotech", ("10x Genomics, Inc.", "TXG"), "Single-cell sequencing consumables and instruments."),
            ("Unilever", "consumer", ("Unilever PLC", "ULVR.L", "UL"), "Global consumer staples demand and commodity input exposure."),
            ("HSBC Holdings", "financials", ("HSBC Holdings plc", "HSBC", "HSBA.L"), "Global bank with Asia/UK credit and trade-finance exposure."),
            ("JPMorgan Chase", "financials", ("JPMorgan Chase & Co.", "JPM"), "Global bank, credit and capital-market conditions signal."),
            ("Goldman Sachs", "financials", ("The Goldman Sachs Group, Inc.", "GS"), "Investment banking, capital markets and financing conditions."),
            ("Morgan Stanley", "financials", ("Morgan Stanley", "MS"), "Capital markets, wealth and financing conditions."),
            ("BlackRock", "financials", ("BlackRock, Inc.", "BLK"), "Largest asset manager and ETF/capital-flow signal."),
            ("SoftBank Group", "financials", ("SoftBank Group Corp.", "9984.T"), "Technology investment capital allocator."),
            ("Diageo", "consumer", ("Diageo plc", "DGE.L", "DEO"), "Global spirits and consumer demand signal."),
            ("A.P. Moller - Maersk", "logistics", ("Maersk", "MAERSK-B.CO"), "Container shipping and global logistics signal."),
            ("MSC Mediterranean Shipping Company", "logistics", ("Mediterranean Shipping Company",), "Container shipping capacity and global logistics signal."),
            ("COSCO Shipping", "logistics", ("China COSCO Shipping", "COSCO Shipping Holdings", "1919.HK"), "China-linked container shipping and logistics signal."),
            ("DHL Group", "logistics", ("Deutsche Post DHL Group", "DHL.DE"), "Air/parcel/logistics demand signal."),
            ("Union Pacific", "logistics", ("Union Pacific Corporation", "UNP"), "North American rail freight signal."),
            ("Canadian Pacific Kansas City", "logistics", ("CPKC", "Canadian Pacific Kansas City Limited", "CP"), "North American rail and Mexico nearshoring freight signal."),
            ("Lockheed Martin", "defense", ("Lockheed Martin Corporation", "LMT"), "Defense prime and aerospace/munitions demand signal."),
            ("RTX", "defense", ("RTX Corporation", "Raytheon", "RTX"), "Defense, missiles, engines and aerospace supply signal."),
            ("Northrop Grumman", "defense", ("Northrop Grumman Corporation", "NOC"), "Defense prime, space and munitions supply signal."),
            ("Boeing", "aerospace", ("The Boeing Company", "BA"), "Commercial aerospace and defense production signal."),
            ("Airbus", "aerospace", ("Airbus SE", "AIR.PA"), "Commercial aerospace and defense production signal."),
            ("Rocket Lab", "space", ("Rocket Lab USA, Inc.", "RKLB"), "Small-launch and space-systems capacity signal."),
            ("SpaceX", "space", (), "Launch and satellite infrastructure."),
        )
    ),
    # Institutions and public bodies.
    *(
        TopEntitySpec("institution", name, domain, aliases, ("global_view", "institution"), note)
        for name, domain, aliases, note in (
            ("International Energy Agency", "energy", ("IEA",), "Energy statistics, forecasts and transition policy."),
            ("International Atomic Energy Agency", "energy", ("IAEA",), "Nuclear safety, safeguards and reactor/fuel-cycle data."),
            ("U.S. Department of Energy", "energy", ("DOE", "US DOE"), "US energy research, loans, grid and nuclear policy."),
            ("Federal Energy Regulatory Commission", "energy", ("FERC",), "US electricity market, pipeline and interconnection regulation."),
            ("North American Electric Reliability Corporation", "grid", ("NERC",), "Grid reliability, power adequacy and transmission risk."),
            ("U.S. Securities and Exchange Commission", "capital", ("SEC",), "US public-company filings and market regulation."),
            ("Bureau of Industry and Security", "policy", ("BIS",), "US export controls and industrial security policy."),
            ("Office of Foreign Assets Control", "policy", ("OFAC",), "US sanctions designations and enforcement."),
            ("Federal Reserve", "financial_conditions", ("Fed", "FRB", "Federal Reserve System"), "US rates, liquidity and financial conditions."),
            ("European Central Bank", "financial_conditions", ("ECB",), "Euro-area monetary policy and reference FX rates."),
            ("European Commission", "policy", ("EC", "Commission of the European Union"), "EU industrial, competition, trade and technology policy."),
            ("People's Bank of China", "financial_conditions", ("PBOC", "PBC"), "China monetary policy and financial conditions."),
            ("Ministry of Industry and Information Technology", "policy", ("MIIT",), "China industrial and technology policy."),
            ("National Development and Reform Commission", "policy", ("NDRC",), "China planning, energy and industrial investment policy."),
            ("NASA", "climate_space", ("National Aeronautics and Space Administration",), "Climate, Earth observation and space infrastructure data."),
            ("NOAA", "climate_space", ("National Oceanic and Atmospheric Administration",), "Climate, ocean, weather and space-weather observations."),
            ("NIST", "standards", ("National Institute of Standards and Technology",), "Standards, measurement and AI/semiconductor programs."),
            ("World Bank", "macro", ("IBRD",), "Global macro, development and governance indicators."),
            ("International Monetary Fund", "macro", ("IMF",), "Macro, financial and commodity data."),
            ("Organisation for Economic Co-operation and Development", "macro", ("OECD",), "Leading indicators, productivity and policy data."),
            ("World Trade Organization", "trade", ("WTO",), "Global trade rules and dispute data."),
            ("GLEIF", "entities", ("Global Legal Entity Identifier Foundation",), "Legal-entity identifier backbone."),
            ("Companies House", "entities", ("UK Companies House",), "UK company registry."),
            ("OpenAlex", "research", (), "Open scholarly metadata and concept graph."),
            ("arXiv", "research", (), "Preprint metadata and full-text source."),
            ("Semantic Scholar", "research", ("S2AG",), "Scholarly graph and citation metadata."),
            ("GDELT Project", "news_events", ("GDELT",), "Global news and event attention data."),
        )
    ),
    # Technologies.
    *(
        TopEntitySpec("technology", name, domain, aliases, ("global_view", "technology"), note)
        for name, domain, aliases, note in (
            ("Deep learning", "AI", ("neural network", "DNN"), "Core AI capability curve."),
            ("Large language models", "AI", ("LLM", "foundation models", "large language model"), "AI demand and productivity channel."),
            ("AI accelerators", "semiconductors", ("AI accelerator", "GPU", "TPU", "NPU"), "AI compute bottleneck layer."),
            ("Advanced semiconductor packaging", "semiconductors", ("CoWoS", "HBM packaging", "advanced packaging"), "AI chip supply bottleneck."),
            ("EUV lithography", "semiconductors", ("extreme ultraviolet lithography",), "Leading-edge chip bottleneck."),
            ("High-bandwidth memory", "semiconductors", ("HBM", "High Bandwidth Memory"), "AI accelerator memory bottleneck."),
            ("Power transformers", "grid", ("power transformer", "large power transformer", "LPT"), "Grid bottleneck for electrification/AI load."),
            ("Grid interconnection", "grid", ("interconnection queue",), "Electrical bottleneck for new load/generation."),
            ("Lithium-ion battery", "energy", ("li-ion",), "Battery cost/adoption backbone."),
            ("Solid-state battery", "energy", ("solid state battery", "SSB"), "Next-generation battery capacity signal."),
            ("Grid-scale storage", "energy", ("grid energy storage", "battery energy storage", "BESS"), "Renewables/grid flexibility layer."),
            ("Solar photovoltaics", "energy", ("solar PV", "photovoltaics"), "Energy cost/adoption curve."),
            ("Perovskite solar cells", "energy", ("perovskite solar cell", "perovskite PV"), "Next-gen PV technology."),
            ("Green hydrogen", "energy", ("electrolytic hydrogen",), "Industrial decarbonization pathway."),
            ("Carbon capture", "energy", ("carbon capture and storage", "CCUS", "CCS"), "Industrial/climate technology."),
            ("Nuclear fission", "energy", ("nuclear fission", "SMR", "small modular reactor"), "Firm clean power and uranium demand."),
            ("Nuclear fusion", "energy", ("nuclear fusion", "fusion energy"), "Long-horizon energy technology."),
            ("CRISPR gene editing", "bio", ("CRISPR-Cas method", "CRISPR", "Cas9"), "Genome-editing tool."),
            ("Gene therapy", "bio", ("AAV gene therapy",), "Therapeutic modality."),
            ("mRNA therapeutics", "bio", ("mRNA vaccines",), "Programmable medicine platform."),
            ("GLP-1 obesity drugs", "bio", ("glucagon-like peptide-1 agonist", "semaglutide", "tirzepatide"), "Metabolic drug demand shock."),
            ("Radioligand therapy", "bio", ("RLT", "radiopharmaceuticals"), "Isotope supply bottleneck channel."),
            ("Quantum computing", "compute", ("quantum computing",), "Long-horizon compute platform."),
            ("Photonic computing", "compute", ("optical computer",), "AI/compute interconnect and acceleration."),
            ("Neuromorphic computing", "compute", (), "Alternative compute architecture."),
            ("Autonomous driving", "AI", ("self-driving car", "autonomous vehicle"), "Robotics/autos AI application."),
            ("Humanoid robotics", "robotics", ("humanoid robot",), "Embodied AI manufacturing channel."),
            ("Drones", "robotics_defense", ("UAV", "unmanned aerial vehicle"), "Defense/logistics platform."),
            ("Reusable launch", "space", ("reusable launch vehicle", "reusable rockets"), "Space access cost curve."),
        )
    ),
    # Materials / physical inputs.
    *(
        TopEntitySpec("material", name, domain, aliases, ("global_view", "material"), note)
        for name, domain, aliases, note in (
            ("Copper", "materials", ("Cu",), "Electrification and grid input."),
            ("Lithium", "materials", ("Li",), "Battery supply input."),
            ("Nickel", "materials", ("Ni",), "Battery/stainless input."),
            ("Cobalt", "materials", ("Co",), "Battery/superalloy input."),
            ("Graphite", "materials", ("natural graphite", "synthetic graphite"), "Battery anode input."),
            ("Rare earth elements", "materials", ("REE", "rare earths", "rare earth element"), "Magnets and defense inputs."),
            ("Neodymium", "materials", ("NdPr",), "Permanent magnet input."),
            ("Gallium", "materials", ("Ga",), "Compound semiconductor input."),
            ("Germanium", "materials", ("Ge",), "Optics/semiconductor input."),
            ("Uranium", "materials", ("U3O8",), "Nuclear fuel input."),
            ("Grain-oriented electrical steel", "materials", ("GOES",), "Transformer core bottleneck."),
            ("Silicon carbide", "materials", ("SiC",), "Power electronics substrate."),
            ("Gallium nitride", "materials", ("GaN",), "Power/RF semiconductor material."),
            ("Polysilicon", "materials", ("polycrystalline silicon",), "Solar PV upstream input."),
            ("Silver", "materials", ("Ag",), "Solar/electronics input."),
            ("Platinum group metals", "materials", ("PGM", "platinum group"), "Catalysts, hydrogen, autos."),
            ("Helium", "materials", ("He",), "Cryogenic and semiconductor input."),
            ("Actinium-225", "materials", ("Ac-225",), "Radioligand isotope bottleneck."),
        )
    ),
)


# Registry ids are the strategic source layer; feed/provider names are the operational layer.
# A registry row may be a bundle (macro stack, policy stack, prediction markets), so keep this
# explicit instead of pretending every source has a one-to-one collector.
SOURCE_FEED_MAP: dict[str, tuple[str, ...]] = {
    "openalex_snapshot": ("openalex", "openalex_citations", "openalex_cite_velocity", "openalex_bridge"),
    "arxiv": ("arxiv",),
    "crossref": ("crossref",),
    "europe_pmc": ("europe_pmc",),
    "semantic_scholar": ("semantic_scholar",),
    "epoch_ai": ("epoch_ai",),
    "pubmed_pmc": ("biorxiv", "pubmed"),
    "google_patents": ("google_patents",),
    "paper_patent_reliance": ("relianceonscience",),
    "patentsview_odp": ("patentsview",),
    "land_permits_cadastre": ("blm_mining_claims", "miningterminal_permits"),
    "baci": ("baci",),
    "sec_edgar": ("sec_edgar",),
    "sec_company_tickers": (),
    "global_equities": ("global_equities",),
    "prediction_markets": ("polymarket", "metaculus"),
    "wikipedia_pageviews": ("wikipedia",),
    "fred_financial": ("fred_financial",),
    "bis_financial_stats": ("bis",),
    "worldbank_capital_flows": ("worldbank_capital",),
    "global_policy_activity": ("global_policy",),
    "grid_power_bottlenecks": ("fred", "lbnl"),
    "ecb_fx": ("ecb_fx",),
    "nih_reporter": ("nih_reporter",),
    "nsf_awards": ("nsf_awards",),
    "cordis": ("cordis",),
    "usaspending_sam": ("usaspending_sam",),
    "un_comtrade": ("un_comtrade", "comtrade"),
    "usgs_minerals": ("usgs_minerals",),
    "eia_iea_ember_owid": ("owid", "ember"),
    "nasa_gistemp": ("nasa_gistemp",),
    "noaa_gml_greenhouse_gases": ("noaa_gml_greenhouse_gases",),
    "noaa_enso": ("noaa_enso",),
    "noaa_climate_indices": ("noaa_climate_indices",),
    "noaa_nsidc_sea_ice": ("noaa_nsidc_sea_ice",),
    "noaa_swpc_solar": ("noaa_swpc_solar",),
    "world_bank_imf_oecd_eurostat_bis": ("world_bank", "imf", "oecd", "eurostat"),
    "ilo_labor": ("ilo",),
    "faostat": ("faostat",),
    "gdelt": ("gdelt",),
    "eonet": ("eonet",),
    "usgs_earthquakes": ("usgs_earthquakes",),
    "gdacs_alerts": ("gdacs_alerts",),
    "acled_ucdp": ("ucdp",),
    "vdem_wgi": ("vdem", "worldbank_wgi"),
    "policy_stack": ("federal_register", "ofac_sdn", "eu_sanctions"),
    "environmental_planning_eia": ("land_permits_canada_iaac", "us_permitting_dashboard", "australia_epbc_referrals"),
    "resource_concessions_contracts": ("resourcecontracts",),
    "regulatory_health": ("clinicaltrials", "openfda_drugsfda"),
    "clinicaltrials_gov": ("clinicaltrials",),
    "openfda_drugsfda": ("openfda_drugsfda",),
}

SOURCE_URL_MAP: dict[str, tuple[str, ...]] = {
    "gleif": ("https://api.gleif.org/api/v1/lei-records",),
    "sec_company_tickers": ("https://www.sec.gov/files/company_tickers.json",),
    "companies_house": ("https://find-and-update.company-information.service.gov.uk/search/companies",),
    "land_permit_source_registry": (
        "https://www.permits.performance.gov/projects",
        "https://iaac-aeic.gc.ca/050/evaluations?culture=en-CA",
        "https://epbcpublicportal.environment.gov.au/",
        "https://www.sea.gob.cl/en/",
        "https://resourcecontracts.org/",
        "https://eiti.org/guidance-notes/contracts-and-licenses",
        "https://drclicences.cami.cd/",
        "https://portal.miningcadastre.com/",
        "https://geocatmin.ingemmet.gob.pe/geocatmin/",
    ),
}

ENTITY_LINK_METHOD_MAP: dict[str, tuple[str, ...]] = {
    "gleif": ("gleif_legal_name",),
    "sec_company_tickers": ("sec_ticker_alias", "sec_legal_name"),
    "companies_house": ("companies_house_exact_search",),
    "wikidata_entities": ("wikidata_exact_label",),
}

# Providers that are landed through specialist pipeline code or corpus imports rather than the
# generic data/feeds/*.jsonl bridge. They should count for status/facts, but should not be treated
# as missing collect_all modules or missing generic ingest metadata.
PROVIDER_ONLY_FEEDS = {"arxiv"}

# Source rows without data/feeds/*.jsonl can still have a real refresh path through a typed
# provider/enrichment pipeline. Surface those commands in status output so "planned" does not
# get confused with "not implemented" once links/facts have landed.
SOURCE_PIPELINE_COMMANDS: dict[str, str] = {
    "land_permit_source_registry": "python3 -m engine.cli world-land-source-seed --register",
    "gleif": "python3 -m engine.cli world-entity-enrich-gleif --limit 300",
    "sec_company_tickers": "python3 -m engine.cli world-entity-enrich-sec --limit 300",
    "companies_house": "python3 -m engine.cli world-entity-enrich-companies-house --limit 100",
    "wikidata_entities": "python3 -m engine.cli world-entity-enrich-wikidata --missing-only --limit 100",
}

IDENTIFIER_REF_TABLES = ("ticker", "cik", "lei", "companies_house_number", "wikidata_qid")
IDENTIFIER_GAP_REVIEWS: dict[tuple[str, str], dict[str, str]] = {
    (
        "material",
        "Grain-oriented electrical steel",
    ): {
        "status": "reviewed_no_exact_external_id",
        "reviewed_at": "2026-06-18",
        "method": "wikidata_exact_label_probe",
        "rationale": "No exact Wikidata QID was accepted for the canonical material label or GOES alias.",
    },
    (
        "technology",
        "Grid interconnection",
    ): {
        "status": "reviewed_no_exact_external_id",
        "reviewed_at": "2026-06-18",
        "method": "wikidata_exact_label_probe",
        "rationale": "No exact Wikidata QID was accepted for the canonical grid-technology label.",
    },
    (
        "technology",
        "Radioligand therapy",
    ): {
        "status": "reviewed_no_exact_external_id",
        "reviewed_at": "2026-06-18",
        "method": "wikidata_exact_label_probe",
        "rationale": "No exact Wikidata QID was accepted for the canonical therapeutic-technology label.",
    },
    (
        "technology",
        "mRNA therapeutics",
    ): {
        "status": "reviewed_no_exact_external_id",
        "reviewed_at": "2026-06-18",
        "method": "wikidata_exact_label_probe",
        "rationale": "No exact Wikidata QID was accepted for the canonical therapeutic-technology label.",
    },
}


def registry(*, priority: int | None = None, status: str | None = None) -> list[dict[str, Any]]:
    specs = DATA_SOURCES
    if priority is not None:
        specs = tuple(s for s in specs if s.priority <= priority)
    if status:
        specs = tuple(s for s in specs if s.status == status)
    return [asdict(s) for s in sorted(specs, key=lambda s: (s.priority, s.layer, s.id))]


def top_entities(*, kind: str | None = None) -> list[dict[str, Any]]:
    ents = TOP_ENTITIES
    if kind:
        ents = tuple(e for e in ents if e.kind == kind)
    return [asdict(e) for e in sorted(ents, key=lambda e: (e.kind, e.domain, e.name))]


def global_view() -> dict[str, Any]:
    by_layer: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    for s in DATA_SOURCES:
        by_layer[s.layer] = by_layer.get(s.layer, 0) + 1
        by_status[s.status] = by_status.get(s.status, 0) + 1
    for e in TOP_ENTITIES:
        by_kind[e.kind] = by_kind.get(e.kind, 0) + 1
    return {
        "sources": len(DATA_SOURCES),
        "sources_by_layer": dict(sorted(by_layer.items())),
        "sources_by_status": dict(sorted(by_status.items())),
        "top_entities": len(TOP_ENTITIES),
        "top_entities_by_kind": dict(sorted(by_kind.items())),
        "priority_1_sources": [s.id for s in DATA_SOURCES if s.priority == 1],
    }


def research_expansion_inventory(
    *,
    priority: int | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Read-only research expansion inventory.

    This is a no-spend plan for making the research layer stronger and more diverse; it does not
    imply any corpus has been fetched or extracted.
    """
    rows = list(RESEARCH_EXPANSION_TARGETS)
    if priority is not None:
        rows = [row for row in rows if row.priority <= priority]
    if status:
        rows = [row for row in rows if row.status == status]

    registered_ids = {spec.id for spec in DATA_SOURCES}
    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    by_role: dict[str, int] = {}
    source_coverage = {source_id: 0 for source_id in RESEARCH_EXPANSION_SOURCE_IDS}
    approval_gates: dict[str, int] = {}
    missing_source_ids: set[str] = set()
    for row in rows:
        by_status[row.status] = by_status.get(row.status, 0) + 1
        by_priority[str(row.priority)] = by_priority.get(str(row.priority), 0) + 1
        by_role[row.corpus_role] = by_role.get(row.corpus_role, 0) + 1
        for source_id in row.source_ids:
            source_coverage[source_id] = source_coverage.get(source_id, 0) + 1
            if source_id not in registered_ids:
                missing_source_ids.add(source_id)
        for gate in row.approval_gates:
            approval_gates[gate] = approval_gates.get(gate, 0) + 1

    return {
        "ok": True,
        "inventory_version": "research_expansion_v1",
        "status": "plan_only_not_collection",
        "summary": {
            "targets": len(rows),
            "priority_1": sum(1 for row in rows if row.priority == 1),
            "priority_2": sum(1 for row in rows if row.priority == 2),
            "source_ids": list(RESEARCH_EXPANSION_SOURCE_IDS),
            "by_status": dict(sorted(by_status.items())),
            "by_priority": dict(sorted(by_priority.items())),
            "by_role": dict(sorted(by_role.items())),
            "source_coverage": dict(sorted(source_coverage.items())),
            "approval_gates": dict(sorted(approval_gates.items())),
            "missing_source_ids": sorted(missing_source_ids),
            "collection_policy": "storage/offload ok; metadata and registry reads are safe only after preflight; paid scans, bulk extraction, LLM extraction, and cloud joins require explicit approval",
        },
        "targets": [asdict(row) for row in sorted(rows, key=lambda r: (r.priority, r.id))],
    }


def format_research_expansion_inventory(inventory: dict[str, Any], *, limit: int | None = 20) -> str:
    summary = inventory.get("summary") or {}
    rows = list(inventory.get("targets") or [])
    shown = rows if limit is None else rows[:limit]
    lines = [
        "Research expansion inventory (read-only)",
        f"status={inventory.get('status')} targets={summary.get('targets', 0)} "
        f"priority_1={summary.get('priority_1', 0)} priority_2={summary.get('priority_2', 0)}",
        "policy: " + str(summary.get("collection_policy") or ""),
        "source coverage: " + ", ".join(
            f"{k}={v}" for k, v in (summary.get("source_coverage") or {}).items()
        ),
    ]
    if summary.get("missing_source_ids"):
        lines.append("registry mismatch: " + ", ".join(summary["missing_source_ids"]))
    if shown:
        lines.extend(["", "targets:"])
    for row in shown:
        gates = ", ".join(str(g) for g in row.get("approval_gates") or [])
        outputs = "; ".join(str(o) for o in (row.get("outputs") or [])[:4])
        lines.append(
            f"- P{row['priority']} {row['id']} [{row['status']}]: {row['name']} "
            f"| role={row['corpus_role']} | sources={', '.join(row.get('source_ids') or [])}"
        )
        lines.append(f"  coverage: {row['coverage']}")
        lines.append(f"  outputs: {outputs}")
        lines.append(f"  gates: {gates}")
    if limit is not None and len(rows) > len(shown):
        lines.append(f"- ... {len(rows) - len(shown)} more")
    return "\n".join(lines)


def research_expansion_inventory_csv(inventory: dict[str, Any]) -> str:
    import csv
    import io

    fields = [
        "id", "name", "priority", "status", "source_ids", "corpus_role", "coverage",
        "access", "outputs", "entities", "cost", "storage", "processing_policy",
        "approval_gates", "notes",
    ]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in inventory.get("targets") or []:
        flat = dict(row)
        for key in ("source_ids", "outputs", "entities", "approval_gates"):
            flat[key] = " | ".join(str(item) for item in row.get(key) or [])
        writer.writerow(flat)
    return out.getvalue()


def land_permit_inventory(
    *,
    priority: int | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """Read-only global land-permit/concession source inventory.

    This is planning metadata, not a claim that the rows are collected. It gives machines a
    jurisdiction-by-jurisdiction map of where official/open land-use evidence should come from.
    """
    rows = list(LAND_PERMIT_JURISDICTIONS)
    if priority is not None:
        rows = [row for row in rows if row.priority <= priority]
    if region:
        region_l = region.lower()
        rows = [row for row in rows if region_l in row.region.lower() or region_l in row.name.lower()]

    by_region: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    source_coverage = {source_id: 0 for source_id in LAND_PERMIT_SOURCE_IDS}
    approval_gates: dict[str, int] = {}
    for row in rows:
        by_region[row.region] = by_region.get(row.region, 0) + 1
        by_status[row.status] = by_status.get(row.status, 0) + 1
        by_priority[str(row.priority)] = by_priority.get(str(row.priority), 0) + 1
        for source_id in row.source_ids:
            source_coverage[source_id] = source_coverage.get(source_id, 0) + 1
        for gate in row.approval_gates:
            approval_gates[gate] = approval_gates.get(gate, 0) + 1

    missing_source_ids = sorted(
        {
            source_id
            for row in rows
            for source_id in row.source_ids
            if source_id not in LAND_PERMIT_SOURCE_IDS
        }
    )
    return {
        "ok": True,
        "inventory_version": "land_permits_v1",
        "status": "planned_not_collected",
        "summary": {
            "jurisdictions": len(rows),
            "priority_1": sum(1 for row in rows if row.priority == 1),
            "priority_2": sum(1 for row in rows if row.priority == 2),
            "regions": len(by_region),
            "source_ids": list(LAND_PERMIT_SOURCE_IDS),
            "by_region": dict(sorted(by_region.items())),
            "by_status": dict(sorted(by_status.items())),
            "by_priority": dict(sorted(by_priority.items())),
            "source_coverage": dict(sorted(source_coverage.items())),
            "approval_gates": dict(sorted(approval_gates.items())),
            "missing_source_ids": missing_source_ids,
            "collection_policy": "official/open portals first; storage/offload ok; paid vendors, OCR/translation, LLM extraction, and cloud geospatial joins require explicit approval",
        },
        "jurisdictions": [asdict(row) for row in sorted(rows, key=lambda r: (r.priority, r.region, r.id))],
    }


def format_land_permit_inventory(inventory: dict[str, Any], *, limit: int | None = 20) -> str:
    summary = inventory.get("summary") or {}
    rows = list(inventory.get("jurisdictions") or [])
    shown = rows if limit is None else rows[:limit]
    lines = [
        "Global land-permit/concession inventory (read-only)",
        f"status={inventory.get('status')} jurisdictions={summary.get('jurisdictions', 0)} "
        f"priority_1={summary.get('priority_1', 0)} regions={summary.get('regions', 0)}",
        "policy: " + str(summary.get("collection_policy") or ""),
        "source coverage: " + ", ".join(
            f"{k}={v}" for k, v in (summary.get("source_coverage") or {}).items()
        ),
    ]
    if summary.get("missing_source_ids"):
        lines.append("registry mismatch: " + ", ".join(summary["missing_source_ids"]))
    if shown:
        lines.extend(["", "jurisdictions:"])
    for row in shown:
        gates = ", ".join(str(g) for g in row.get("approval_gates") or [])
        sources = ", ".join(str(s) for s in row.get("source_ids") or [])
        examples = "; ".join(str(e) for e in (row.get("official_source_examples") or [])[:3])
        lines.append(
            f"- P{row['priority']} {row['id']} [{row['region']}]: {row['name']} "
            f"| sources={sources} | cost={row['cost']}"
        )
        lines.append(f"  official/open first: {examples}")
        lines.append(f"  outputs: {'; '.join(str(o) for o in row.get('outputs', [])[:4])}")
        lines.append(f"  approval gates: {gates}")
    if limit is not None and len(rows) > len(shown):
        lines.append(f"- ... {len(rows) - len(shown)} more")
    return "\n".join(lines)


def land_permit_inventory_csv(inventory: dict[str, Any]) -> str:
    import csv
    import io

    fields = [
        "id", "name", "region", "priority", "status", "source_ids", "source_types",
        "official_source_examples", "outputs", "entities", "cost", "storage",
        "collection_policy", "approval_gates", "notes",
    ]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in inventory.get("jurisdictions") or []:
        flat = dict(row)
        for key in ("source_ids", "source_types", "official_source_examples", "outputs", "entities", "approval_gates"):
            flat[key] = " | ".join(str(item) for item in row.get(key) or [])
        writer.writerow(flat)
    return out.getvalue()


def physical_constraint_inventory(
    *,
    priority: int | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Read-only physical-constraint data inventory.

    This is the constraint-data spine: research and patents explain what could be built, while
    permits, grid, water, materials, and logistics explain what can physically scale.
    """
    rows = list(PHYSICAL_CONSTRAINT_TARGETS)
    if priority is not None:
        rows = [row for row in rows if row.priority <= priority]
    if status:
        rows = [row for row in rows if row.status == status]

    registered_ids = {spec.id for spec in DATA_SOURCES}
    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    by_role: dict[str, int] = {}
    source_coverage = {source_id: 0 for source_id in PHYSICAL_CONSTRAINT_SOURCE_IDS}
    approval_gates: dict[str, int] = {}
    missing_source_ids: set[str] = set()
    for row in rows:
        by_status[row.status] = by_status.get(row.status, 0) + 1
        by_priority[str(row.priority)] = by_priority.get(str(row.priority), 0) + 1
        by_role[row.constraint_role] = by_role.get(row.constraint_role, 0) + 1
        for source_id in row.source_ids:
            source_coverage[source_id] = source_coverage.get(source_id, 0) + 1
            if source_id not in registered_ids:
                missing_source_ids.add(source_id)
        for gate in row.approval_gates:
            approval_gates[gate] = approval_gates.get(gate, 0) + 1

    return {
        "ok": True,
        "inventory_version": "physical_constraints_v1",
        "status": "plan_only_not_collection",
        "summary": {
            "targets": len(rows),
            "priority_1": sum(1 for row in rows if row.priority == 1),
            "priority_2": sum(1 for row in rows if row.priority == 2),
            "source_ids": list(PHYSICAL_CONSTRAINT_SOURCE_IDS),
            "by_status": dict(sorted(by_status.items())),
            "by_priority": dict(sorted(by_priority.items())),
            "by_role": dict(sorted(by_role.items())),
            "source_coverage": dict(sorted(source_coverage.items())),
            "approval_gates": dict(sorted(approval_gates.items())),
            "missing_source_ids": sorted(missing_source_ids),
            "collection_policy": "land permits first; official/open sources first; storage/offload ok; paid vendors, cloud joins, bulk extraction, OCR/translation, and LLM extraction require explicit approval",
        },
        "targets": [asdict(row) for row in sorted(rows, key=lambda r: (r.priority, r.id))],
    }


def format_physical_constraint_inventory(inventory: dict[str, Any], *, limit: int | None = 20) -> str:
    summary = inventory.get("summary") or {}
    rows = list(inventory.get("targets") or [])
    shown = rows if limit is None else rows[:limit]
    lines = [
        "Physical constraint data inventory (read-only)",
        f"status={inventory.get('status')} targets={summary.get('targets', 0)} "
        f"priority_1={summary.get('priority_1', 0)} priority_2={summary.get('priority_2', 0)}",
        "policy: " + str(summary.get("collection_policy") or ""),
        "roles: " + ", ".join(f"{k}={v}" for k, v in (summary.get("by_role") or {}).items()),
    ]
    if summary.get("missing_source_ids"):
        lines.append("registry mismatch: " + ", ".join(summary["missing_source_ids"]))
    if shown:
        lines.extend(["", "targets:"])
    for row in shown:
        gates = ", ".join(str(g) for g in row.get("approval_gates") or [])
        sources = ", ".join(str(s) for s in row.get("source_ids") or [])
        outputs = "; ".join(str(o) for o in (row.get("outputs") or [])[:5])
        lines.append(
            f"- P{row['priority']} {row['id']} [{row['status']}]: {row['name']} "
            f"| role={row['constraint_role']}"
        )
        lines.append(f"  why: {row['why_it_matters']}")
        lines.append(f"  sources: {sources}")
        lines.append(f"  outputs: {outputs}")
        lines.append(f"  refresh: {row['refresh_model']}")
        lines.append(f"  gates: {gates}")
    if limit is not None and len(rows) > len(shown):
        lines.append(f"- ... {len(rows) - len(shown)} more")
    return "\n".join(lines)


def physical_constraint_inventory_csv(inventory: dict[str, Any]) -> str:
    import csv
    import io

    fields = [
        "id", "name", "priority", "status", "constraint_role", "source_ids",
        "why_it_matters", "coverage", "outputs", "entities", "collector_policy",
        "refresh_model", "storage", "cost", "approval_gates", "notes",
    ]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in inventory.get("targets") or []:
        flat = dict(row)
        for key in ("source_ids", "outputs", "entities", "approval_gates"):
            flat[key] = " | ".join(str(item) for item in row.get(key) or [])
        writer.writerow(flat)
    return out.getvalue()


CONSTRAINT_ROI_PROFILES: dict[str, dict[str, Any]] = {
    "land_permit_spine": {
        "roi_score": 100,
        "edge": "highest",
        "direct_roi": "Find projects where physical capacity is gated by permissioned land before capex/news fully prices it.",
        "now_action": "Build official/open land-permit, concession, and EIA collectors first; start with jurisdictions that expose dated registers.",
        "approval_ask": "Only ask for paid parcel vendors, OCR/translation, LLM extraction, or cloud geospatial joins after official/open portals prove value.",
    },
    "research_paper_backbone": {
        "roi_score": 95,
        "edge": "highest",
        "direct_roi": "Detect frontier capability shifts and cross-field diffusion before patents, capex, and markets catch up.",
        "now_action": "Strengthen official metadata/citation coverage: OpenAlex, arXiv, Crossref, PubMed/PMC, Europe PMC, OpenCitations, Semantic Scholar manifests.",
        "approval_ask": "Ask before full-text bulk processing, embeddings, LLM extraction, or cloud graph joins.",
    },
    "patent_rights_backbone": {
        "roi_score": 93,
        "edge": "highest",
        "direct_roi": "Turn research into commercialization, assignee concentration, claims, and jurisdictional IP/capacity signals.",
        "now_action": "Use existing Google Patents dry-run gate for targeted global extracts; keep USPTO/ODP as US fallback after key setup.",
        "approval_ask": "Ask before BigQuery extracts, Athena paper-patent joins, or claims/abstract extraction at scale.",
    },
    "grid_power_connection": {
        "roi_score": 90,
        "edge": "very_high",
        "direct_roi": "Separate announced capacity from energized/deliverable capacity, especially for AI campuses, mines, fabs, hydrogen, and renewables.",
        "now_action": "Inventory official queue, utility, regulator, and transmission-siting sources; link them to projects and land permits.",
        "approval_ask": "Ask before paid grid-node datasets, cloud geospatial joins, or scrape-at-scale.",
    },
    "water_constraint_layer": {
        "roi_score": 88,
        "edge": "very_high",
        "direct_roi": "Expose projects whose scale is capped by withdrawal rights, discharge permits, basin stress, drought, or aquifer constraints.",
        "now_action": "Add official water-rights/discharge permit registers and basin-stress layers beside land/EIA records.",
        "approval_ask": "Ask before paid water datasets, geocoding, OCR/translation, or cloud geospatial joins.",
    },
    "minerals_and_materials_supply": {
        "roi_score": 86,
        "edge": "very_high",
        "direct_roi": "Connect material scarcity to concessions, reserves, production, trade concentration, and pre-production supply options.",
        "now_action": "Reconcile the existing mining DB with official concession/permit records, then connect to USGS, Comtrade, BACI, and FAOSTAT facts.",
        "approval_ask": "Ask before paid registry enrichment, translation/OCR, entity resolution at scale, or geospatial joins.",
    },
    "industrial_facility_permission": {
        "roi_score": 78,
        "edge": "high",
        "direct_roi": "Catch factories, fabs, smelters, chemical plants, LNG, battery plants, and data centers before operating capacity is real.",
        "now_action": "Add official facility air/water/waste/construction permit registers after the land-permit spine exists.",
        "approval_ask": "Ask before OCR, translation, paid facility databases, or LLM extraction.",
    },
    "logistics_and_route_capacity": {
        "roi_score": 72,
        "edge": "medium_high",
        "direct_roi": "Find cases where supply exists upstream but terminals, ports, rail, or routes ration delivery.",
        "now_action": "Use official port/rail/project sources and existing trade data; defer paid AIS/satellite until a thesis needs it.",
        "approval_ask": "Ask before AIS/satellite, paid logistics feeds, or cloud joins.",
    },
    "carbon_storage_and_pore_space": {
        "roi_score": 68,
        "edge": "focused_high",
        "direct_roi": "Detect CCS/DAC value migration from capture equipment to scarce permitted pore space and pipeline-connected storage.",
        "now_action": "Collect official storage/injection permit dockets after land/EIA collector patterns are reusable.",
        "approval_ask": "Ask before paid subsurface data, OCR, LLM extraction, or geospatial joins.",
    },
}


def _source_status_summary(source_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_readiness: dict[str, int] = {}
    by_action: dict[str, int] = {}
    for row in source_rows:
        readiness = str(row.get("collection_readiness") or "unknown")
        action = str(row.get("next_action_type") or "unknown")
        by_readiness[readiness] = by_readiness.get(readiness, 0) + 1
        by_action[action] = by_action.get(action, 0) + 1
    return {
        "sources": len(source_rows),
        "queryable_sources": sum(1 for row in source_rows if row.get("operational_status") == "queryable_world_state"),
        "planned_sources": sum(1 for row in source_rows if row.get("operational_status") == "planned_not_collected"),
        "world_state_facts": sum(int(row.get("world_state_facts") or 0) for row in source_rows),
        "by_readiness": dict(sorted(by_readiness.items())),
        "by_next_action_type": dict(sorted(by_action.items())),
    }


def constraint_roi_queue(status: dict[str, Any], *, limit: int | None = None) -> dict[str, Any]:
    """ROI-ranked, read-only acquisition queue for the physical constraint sprint.

    This does not execute collectors. It answers: which layer most improves forecast edge per
    hour/dollar/disk risk, what can happen without paid processing, and where approval is required.
    """
    matrix = source_matrix(status)
    sources_by_id = {row["id"]: row for row in matrix.get("sources") or []}
    inventory = physical_constraint_inventory()
    queue: list[dict[str, Any]] = []
    for target in inventory.get("targets") or []:
        profile = CONSTRAINT_ROI_PROFILES.get(target["id"], {})
        source_ids = list(target.get("source_ids") or [])
        source_rows = [sources_by_id[sid] for sid in source_ids if sid in sources_by_id]
        missing_source_ids = [sid for sid in source_ids if sid not in sources_by_id]
        source_summary = _source_status_summary(source_rows)
        paid_source_ids = {"google_patents", "paper_patent_reliance", "shipping_satellite"}
        paid_sources = [
            row for row in source_rows
            if (row.get("execution_risk") or {}).get("requires_paid_approval")
            or row.get("cost_posture") == "paid_approval_required"
            or row.get("id") in paid_source_ids
        ]
        keyed_sources = [
            row for row in source_rows
            if (row.get("execution_risk") or {}).get("requires_key")
        ]
        cloud_first_sources = [
            row for row in source_rows
            if (row.get("execution_risk") or {}).get("cloud_first")
        ]
        no_paid_commands = sorted(
            {
                command
                for row in source_rows
                if not (row.get("execution_risk") or {}).get("requires_paid_approval")
                for command in (row.get("preflight_commands") or [])
                if command
            }
        )
        collector_gaps = [
            row["id"] for row in source_rows
            if row.get("next_action_type") == "needs_collector_or_keyed_pipeline"
        ]
        visible_gap = (
            f"{source_summary['planned_sources']}/{source_summary['sources']} source(s) planned/not collected"
            if source_summary["planned_sources"] else
            f"{source_summary['queryable_sources']}/{source_summary['sources']} source(s) already queryable"
        )
        base_score = int(profile.get("roi_score") or max(40, 100 - int(target["priority"]) * 10))
        urgency_bonus = 6 if source_summary["planned_sources"] else 0
        cost_penalty = 4 * len(paid_sources) + 2 * len(keyed_sources)
        roi_score = max(1, min(100, base_score + urgency_bonus - cost_penalty))
        queue.append(
            {
                "id": target["id"],
                "name": target["name"],
                "priority": target["priority"],
                "roi_score": roi_score,
                "edge": profile.get("edge") or "unknown",
                "direct_roi": profile.get("direct_roi") or target.get("why_it_matters"),
                "current_gap": visible_gap,
                "current_status": target["status"],
                "source_summary": source_summary,
                "source_ids": source_ids,
                "missing_source_ids": missing_source_ids,
                "collector_gaps": collector_gaps,
                "cloud_first_sources": [row["id"] for row in cloud_first_sources],
                "paid_approval_sources": [row["id"] for row in paid_sources],
                "key_or_visibility_sources": [row["id"] for row in keyed_sources],
                "next_no_paid_action": profile.get("now_action") or target.get("collector_policy"),
                "no_paid_preflight_commands": no_paid_commands[:8],
                "approval_ask": profile.get("approval_ask") or target.get("cost"),
                "approval_gates": list(target.get("approval_gates") or []),
                "storage": target.get("storage"),
                "refresh_model": target.get("refresh_model"),
            }
        )
    queue.sort(key=lambda row: (-int(row["roi_score"]), int(row["priority"]), str(row["id"])))
    if limit is not None:
        queue = queue[:limit]
    return {
        "ok": True,
        "queue_version": "constraint_roi_sprint_v1",
        "status": "read_only_no_collection",
        "summary": {
            "targets": len(queue),
            "priority_1": sum(1 for row in queue if int(row.get("priority") or 0) == 1),
            "paid_approval_targets": sum(1 for row in queue if row.get("paid_approval_sources")),
            "key_or_visibility_targets": sum(1 for row in queue if row.get("key_or_visibility_sources")),
            "cloud_first_targets": sum(1 for row in queue if row.get("cloud_first_sources")),
            "safe_local_due_sources": matrix.get("summary", {}).get("safe_local_due_sources", 0),
            "ledger_actual_usd": float((matrix.get("cost_ledger") or {}).get("actual_usd") or 0.0),
            "ledger_estimated_usd": float((matrix.get("cost_ledger") or {}).get("estimated_usd") or 0.0),
            "disk_free_gb": float((matrix.get("disk") or {}).get("free_gb") or 0.0),
            "policy": "rank by direct forecast ROI; execute $0/read-only preflights first; ask before processing spend, paid data, cloud joins, LLM extraction, OCR/translation, or scrape-at-scale",
        },
        "queue": queue,
    }


def format_constraint_roi_queue(report: dict[str, Any], *, limit: int | None = 12) -> str:
    summary = report.get("summary") or {}
    rows = list(report.get("queue") or [])
    shown = rows if limit is None else rows[:limit]
    lines = [
        "Constraint ROI sprint queue (read-only)",
        f"targets={summary.get('targets', 0)} priority_1={summary.get('priority_1', 0)} "
        f"paid_targets={summary.get('paid_approval_targets', 0)} "
        f"cloud_first={summary.get('cloud_first_targets', 0)} "
        f"safe_due={summary.get('safe_local_due_sources', 0)}",
        f"disk_free={float(summary.get('disk_free_gb') or 0):.1f}GiB "
        f"ledger_actual=${float(summary.get('ledger_actual_usd') or 0):.2f} "
        f"ledger_est=${float(summary.get('ledger_estimated_usd') or 0):.2f}",
        "policy: " + str(summary.get("policy") or ""),
    ]
    if shown:
        lines.extend(["", "queue:"])
    for idx, row in enumerate(shown, start=1):
        lines.append(
            f"- #{idx} score={row['roi_score']} P{row['priority']} {row['id']} "
            f"[{row['edge']}]: {row['current_gap']}"
        )
        lines.append(f"  ROI: {row['direct_roi']}")
        lines.append(f"  now: {row['next_no_paid_action']}")
        if row.get("collector_gaps"):
            lines.append("  collector gaps: " + ", ".join(row["collector_gaps"]))
        if row.get("paid_approval_sources"):
            lines.append("  ask before spend: " + ", ".join(row["paid_approval_sources"]))
        if row.get("key_or_visibility_sources"):
            lines.append("  keys/visibility: " + ", ".join(row["key_or_visibility_sources"]))
        if row.get("cloud_first_sources"):
            lines.append("  cloud/object-storage first: " + ", ".join(row["cloud_first_sources"]))
        if row.get("no_paid_preflight_commands"):
            lines.append("  preflight: " + " ; ".join(row["no_paid_preflight_commands"][:3]))
    if limit is not None and len(rows) > len(shown):
        lines.append(f"- ... {len(rows) - len(shown)} more")
    return "\n".join(lines)


def entity_identifier_status(
    conn: sqlite3.Connection,
    *,
    kind: str | None = None,
    missing_only: bool = False,
) -> dict[str, Any]:
    """Read-only coverage of hard identifiers on top global entities."""
    specs = [e for e in TOP_ENTITIES if kind is None or e.kind == kind]
    if not specs:
        return {
            "summary": {
                "top_entities": 0,
                "seeded": 0,
                "with_any_identifier": 0,
                "missing_identifier": 0,
                "identifier_links": 0,
                "reviewed_missing_identifier": 0,
                "unreviewed_missing_identifier": 0,
                "by_ref_table": {ref: 0 for ref in IDENTIFIER_REF_TABLES},
                "by_kind": {},
            },
            "entities": [],
        }
    names_by_kind: dict[str, set[str]] = {}
    for spec in specs:
        names_by_kind.setdefault(spec.kind, set()).add(spec.name)
    clauses: list[str] = []
    params: list[Any] = []
    for entity_kind, names in names_by_kind.items():
        placeholders = ",".join("?" for _ in names)
        clauses.append(f"(kind=? AND canonical_name IN ({placeholders}))")
        params.append(entity_kind)
        params.extend(sorted(names))
    entity_rows = conn.execute(
        "SELECT id, kind, canonical_name FROM entities WHERE " + " OR ".join(clauses),
        params,
    ).fetchall()
    by_key = {(row["kind"], row["canonical_name"]): dict(row) for row in entity_rows}
    entity_ids = [row["id"] for row in entity_rows]
    refs_by_entity: dict[str, dict[str, list[str]]] = {eid: {ref: [] for ref in IDENTIFIER_REF_TABLES} for eid in entity_ids}
    if entity_ids:
        placeholders = ",".join("?" for _ in entity_ids)
        ref_placeholders = ",".join("?" for _ in IDENTIFIER_REF_TABLES)
        link_rows = conn.execute(
            f"""
            SELECT entity_id, ref_table, ref_id
            FROM entity_links
            WHERE entity_id IN ({placeholders})
              AND ref_table IN ({ref_placeholders})
            ORDER BY ref_table, ref_id
            """,
            [*entity_ids, *IDENTIFIER_REF_TABLES],
        ).fetchall()
        for row in link_rows:
            refs_by_entity.setdefault(row["entity_id"], {ref: [] for ref in IDENTIFIER_REF_TABLES})
            refs_by_entity[row["entity_id"]].setdefault(row["ref_table"], []).append(row["ref_id"])

    rows: list[dict[str, Any]] = []
    summary_by_kind: dict[str, dict[str, int]] = {}
    by_ref_table = {ref: 0 for ref in IDENTIFIER_REF_TABLES}
    seeded = 0
    with_any = 0
    identifier_links = 0
    reviewed_missing = 0
    for spec in sorted(specs, key=lambda e: (e.kind, e.domain, e.name)):
        entity = by_key.get((spec.kind, spec.name))
        refs = {ref: [] for ref in IDENTIFIER_REF_TABLES}
        if entity:
            seeded += 1
            refs = {ref: sorted(set(refs_by_entity.get(entity["id"], {}).get(ref, []))) for ref in IDENTIFIER_REF_TABLES}
        total_refs = sum(len(v) for v in refs.values())
        if total_refs:
            with_any += 1
        identifier_links += total_refs
        for ref, values in refs.items():
            if values:
                by_ref_table[ref] += 1
        missing_identifier = total_refs == 0
        review = IDENTIFIER_GAP_REVIEWS.get((spec.kind, spec.name))
        if missing_identifier and review:
            reviewed_missing += 1
        kind_summary = summary_by_kind.setdefault(
            spec.kind,
            {
                "total": 0,
                "seeded": 0,
                "with_any_identifier": 0,
                "missing_identifier": 0,
                "reviewed_missing_identifier": 0,
                "unreviewed_missing_identifier": 0,
            },
        )
        kind_summary["total"] += 1
        if entity:
            kind_summary["seeded"] += 1
        if total_refs:
            kind_summary["with_any_identifier"] += 1
        else:
            kind_summary["missing_identifier"] += 1
            if review:
                kind_summary["reviewed_missing_identifier"] += 1
            else:
                kind_summary["unreviewed_missing_identifier"] += 1
        row = {
            "kind": spec.kind,
            "name": spec.name,
            "domain": spec.domain,
            "entity_id": entity["id"] if entity else None,
            "seeded": bool(entity),
            "identifiers": refs,
            "identifier_count": total_refs,
            "missing_identifier": missing_identifier,
            "identifier_gap_review": review,
        }
        if not missing_only or row["missing_identifier"]:
            rows.append(row)
    missing_count = len(specs) - with_any
    return {
        "summary": {
            "top_entities": len(specs),
            "seeded": seeded,
            "with_any_identifier": with_any,
            "missing_identifier": missing_count,
            "identifier_links": identifier_links,
            "reviewed_missing_identifier": reviewed_missing,
            "unreviewed_missing_identifier": max(missing_count - reviewed_missing, 0),
            "by_ref_table": by_ref_table,
            "by_kind": dict(sorted(summary_by_kind.items())),
        },
        "entities": rows,
    }


def _top_entity_rows(conn: sqlite3.Connection, specs: list[TopEntitySpec]) -> dict[tuple[str, str], dict[str, Any]]:
    if not specs:
        return {}
    names_by_kind: dict[str, set[str]] = {}
    for spec in specs:
        names_by_kind.setdefault(spec.kind, set()).add(spec.name)
    clauses: list[str] = []
    params: list[Any] = []
    for entity_kind, names in names_by_kind.items():
        placeholders = ",".join("?" for _ in names)
        clauses.append(f"(kind=? AND canonical_name IN ({placeholders}))")
        params.append(entity_kind)
        params.extend(sorted(names))
    try:
        rows = conn.execute(
            "SELECT id, kind, canonical_name FROM entities WHERE " + " OR ".join(clauses),
            params,
        ).fetchall()
    except sqlite3.Error:
        return {}
    return {(row["kind"], row["canonical_name"]): dict(row) for row in rows}


def _empty_entity_coverage_summary(specs: list[TopEntitySpec]) -> dict[str, Any]:
    by_kind: dict[str, dict[str, int]] = {}
    for spec in specs:
        row = by_kind.setdefault(
            spec.kind,
            {
                "total": 0,
                "seeded": 0,
                "with_facts": 0,
                "with_sources": 0,
                "with_series_links": 0,
                "missing_facts": 0,
                "no_coverage": 0,
            },
        )
        row["total"] += 1
    return {
        "top_entities": len(specs),
        "seeded": 0,
        "with_facts": 0,
        "with_sources": 0,
        "with_series_links": 0,
        "missing_facts": 0,
        "no_coverage": 0,
        "by_kind": dict(sorted(by_kind.items())),
    }


def top_entity_coverage(
    conn: sqlite3.Connection,
    *,
    kind: str | None = None,
    missing_only: bool = False,
) -> dict[str, Any]:
    """Read-only coverage of timestamped facts/source context for the top global entities."""
    specs = [e for e in TOP_ENTITIES if kind is None or e.kind == kind]
    if not specs:
        return {"summary": _empty_entity_coverage_summary([]), "entities": []}

    entity_by_key = _top_entity_rows(conn, specs)
    identifier_status = entity_identifier_status(conn, kind=kind, missing_only=False)
    identifiers_by_key = {
        (row["kind"], row["name"]): row
        for row in identifier_status.get("entities", [])
    }
    entity_ids = [row["id"] for row in entity_by_key.values()]

    fact_stats: dict[str, dict[str, Any]] = {}
    subject_counts: dict[str, int] = {}
    object_counts: dict[str, int] = {}
    link_counts: dict[str, dict[str, int]] = {}
    predicates: dict[str, list[dict[str, Any]]] = {}
    if entity_ids:
        placeholders = ",".join("?" for _ in entity_ids)
        try:
            for row in conn.execute(
                f"""
                SELECT subject_entity_id AS entity_id, count(*) AS n
                FROM world_state_facts
                WHERE subject_entity_id IN ({placeholders})
                  AND COALESCE(status,'active')='active'
                GROUP BY subject_entity_id
                """,
                entity_ids,
            ):
                subject_counts[str(row["entity_id"])] = int(row["n"] or 0)
            for row in conn.execute(
                f"""
                SELECT object_entity_id AS entity_id, count(*) AS n
                FROM world_state_facts
                WHERE object_entity_id IN ({placeholders})
                  AND COALESCE(status,'active')='active'
                GROUP BY object_entity_id
                """,
                entity_ids,
            ):
                object_counts[str(row["entity_id"])] = int(row["n"] or 0)
            union_sql = f"""
                SELECT id, subject_entity_id AS entity_id, predicate, source_id, published_at
                FROM world_state_facts
                WHERE subject_entity_id IN ({placeholders})
                  AND COALESCE(status,'active')='active'
                UNION
                SELECT id, object_entity_id AS entity_id, predicate, source_id, published_at
                FROM world_state_facts
                WHERE object_entity_id IN ({placeholders})
                  AND COALESCE(status,'active')='active'
            """
            for row in conn.execute(
                f"""
                SELECT entity_id,
                       count(*) AS active_fact_count,
                       count(DISTINCT source_id) AS source_count,
                       count(DISTINCT predicate) AS predicate_count,
                       min(published_at) AS first_published_at,
                       max(published_at) AS latest_published_at
                FROM ({union_sql})
                GROUP BY entity_id
                """,
                [*entity_ids, *entity_ids],
            ):
                fact_stats[str(row["entity_id"])] = {
                    "active_fact_count": int(row["active_fact_count"] or 0),
                    "source_count": int(row["source_count"] or 0),
                    "predicate_count": int(row["predicate_count"] or 0),
                    "first_published_at": row["first_published_at"],
                    "latest_published_at": row["latest_published_at"],
                }
            for row in conn.execute(
                f"""
                SELECT entity_id, predicate, count(*) AS n
                FROM ({union_sql})
                GROUP BY entity_id, predicate
                ORDER BY entity_id, n DESC, predicate
                """,
                [*entity_ids, *entity_ids],
            ):
                items = predicates.setdefault(str(row["entity_id"]), [])
                if len(items) < 8:
                    items.append({"predicate": row["predicate"], "facts": int(row["n"] or 0)})
            for row in conn.execute(
                f"""
                SELECT entity_id, ref_table, count(*) AS n
                FROM entity_links
                WHERE entity_id IN ({placeholders})
                GROUP BY entity_id, ref_table
                """,
                entity_ids,
            ):
                link_counts.setdefault(str(row["entity_id"]), {})[str(row["ref_table"])] = int(row["n"] or 0)
        except sqlite3.Error:
            fact_stats = {}
            subject_counts = {}
            object_counts = {}
            link_counts = {}
            predicates = {}

    summary = _empty_entity_coverage_summary(specs)
    rows: list[dict[str, Any]] = []
    for spec in sorted(specs, key=lambda e: (e.kind, e.domain, e.name)):
        entity = entity_by_key.get((spec.kind, spec.name))
        identifier_row = identifiers_by_key.get((spec.kind, spec.name), {})
        entity_id = str(entity["id"]) if entity else None
        stats = fact_stats.get(entity_id or "", {})
        links = link_counts.get(entity_id or "", {})
        series_links = int(links.get("series") or 0)
        identifier_count = int(identifier_row.get("identifier_count") or 0)
        active_facts = int(stats.get("active_fact_count") or 0)
        source_count = int(stats.get("source_count") or 0)
        if not entity:
            coverage_status = "not_seeded"
        elif active_facts and source_count:
            coverage_status = "facts_with_sources"
        elif active_facts:
            coverage_status = "facts_without_sources"
        elif series_links:
            coverage_status = "series_link_only"
        elif identifier_count:
            coverage_status = "identifier_only"
        else:
            coverage_status = "no_coverage"

        row = {
            "kind": spec.kind,
            "name": spec.name,
            "domain": spec.domain,
            "entity_id": entity_id,
            "seeded": bool(entity),
            "coverage_status": coverage_status,
            "active_fact_count": active_facts,
            "subject_fact_count": int(subject_counts.get(entity_id or "", 0)),
            "object_fact_count": int(object_counts.get(entity_id or "", 0)),
            "source_count": source_count,
            "predicate_count": int(stats.get("predicate_count") or 0),
            "top_predicates": predicates.get(entity_id or "", []),
            "first_published_at": stats.get("first_published_at"),
            "latest_published_at": stats.get("latest_published_at"),
            "series_links": series_links,
            "entity_links": sum(int(v) for v in links.values()),
            "identifier_count": identifier_count,
            "identifiers": identifier_row.get("identifiers") or {ref: [] for ref in IDENTIFIER_REF_TABLES},
        }
        kind_summary = summary["by_kind"][spec.kind]
        if row["seeded"]:
            summary["seeded"] += 1
            kind_summary["seeded"] += 1
        if active_facts:
            summary["with_facts"] += 1
            kind_summary["with_facts"] += 1
        else:
            summary["missing_facts"] += 1
            kind_summary["missing_facts"] += 1
        if source_count:
            summary["with_sources"] += 1
            kind_summary["with_sources"] += 1
        if series_links:
            summary["with_series_links"] += 1
            kind_summary["with_series_links"] += 1
        if coverage_status in {"not_seeded", "no_coverage", "identifier_only"}:
            summary["no_coverage"] += 1
            kind_summary["no_coverage"] += 1
        if not missing_only or active_facts == 0:
            rows.append(row)

    return {"summary": summary, "entities": rows}


def format_top_entity_coverage(status: dict[str, Any], *, limit: int | None = 80) -> str:
    summary = status["summary"]
    rows = list(status.get("entities") or [])
    shown = rows if limit is None else rows[:limit]
    lines = [
        "Top entity world-state coverage (read-only)",
        f"top_entities={summary['top_entities']} seeded={summary['seeded']} "
        f"with_facts={summary['with_facts']} with_sources={summary['with_sources']} "
        f"series_links={summary['with_series_links']} missing_facts={summary['missing_facts']} "
        f"no_coverage={summary['no_coverage']}",
    ]
    for kind, row in summary.get("by_kind", {}).items():
        lines.append(
            f"{kind}: total={row['total']} seeded={row['seeded']} "
            f"facts={row['with_facts']} sources={row['with_sources']} "
            f"missing_facts={row['missing_facts']} no_coverage={row['no_coverage']}"
        )
    if shown:
        lines.append("entities:")
    for row in shown:
        preds = ", ".join(p["predicate"] for p in row.get("top_predicates", [])[:4])
        suffix = f" predicates={preds}" if preds else ""
        lines.append(
            f"- {row['kind']} {row['name']}: status={row['coverage_status']} "
            f"facts={row['active_fact_count']} sources={row['source_count']} "
            f"ids={row['identifier_count']} series_links={row['series_links']}{suffix}"
        )
    if limit is not None and len(rows) > len(shown):
        lines.append(f"- ... {len(rows) - len(shown)} more")
    return "\n".join(lines)


def top_entity_coverage_csv(status: dict[str, Any]) -> str:
    import csv
    import io

    fields = [
        "kind", "name", "domain", "entity_id", "seeded", "coverage_status",
        "active_fact_count", "source_count", "predicate_count", "series_links",
        "entity_links", "identifier_count", "first_published_at", "latest_published_at",
    ]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in status.get("entities") or []:
        writer.writerow(row)
    return out.getvalue()


def _table_count(conn: sqlite3.Connection, table: str, where: str = "", params: tuple[Any, ...] = ()) -> int:
    try:
        sql = f"SELECT count(*) FROM {table}" + (f" WHERE {where}" if where else "")
        return int(conn.execute(sql, params).fetchone()[0])
    except sqlite3.Error:
        return 0


def _feed_file_status(feed: str, feed_dir: Path) -> dict[str, Any]:
    path = feed_dir / f"{feed}.jsonl"
    status_path = feed_dir / f"{feed}.status.json"
    diagnostic = None
    if status_path.exists():
        try:
            diagnostic = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            diagnostic = {"status_error": "unreadable status sidecar"}
    if not path.exists():
        return {
            "feed": feed,
            "exists": False,
            "rows": 0,
            "bytes": 0,
            "mtime": None,
            "age_hours": None,
            "diagnostic": diagnostic,
        }
    stat = path.stat()
    try:
        with path.open("r", encoding="utf-8") as fh:
            rows = sum(1 for _ in fh)
    except OSError:
        rows = 0
    now_ts = datetime.now(timezone.utc).timestamp()
    mtime = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
    return {
        "feed": feed,
        "exists": True,
        "rows": rows,
        "bytes": stat.st_size,
        "mtime": mtime.isoformat(),
        "age_hours": round((now_ts - stat.st_mtime) / 3600, 2),
        "diagnostic": diagnostic,
    }


def _series_health_status(conn: sqlite3.Connection) -> dict[str, Any]:
    """Read-only summary of QC health and reviewed hard failures."""
    try:
        total = _table_count(conn, "series_health")
        if total == 0:
            return {
                "ok": 0,
                "warn": 0,
                "fail": 0,
                "audited": 0,
                "reviewed_failures": 0,
                "unreviewed_failures": 0,
                "failures": [],
            }
        rows = conn.execute("SELECT status, count(*) AS n FROM series_health GROUP BY status").fetchall()
        counts = {str(row["status"]): int(row["n"] or 0) for row in rows}
        failure_rows = conn.execute(
            """
            SELECT
                sh.series_id, s.provider, s.external_id, s.label, s.metric,
                sh.fresh_status, sh.complete_status, sh.valid_status,
                sh.recon_status, sh.prov_status, sh.days_stale, sh.n_gaps,
                sh.health_score, sh.detail
            FROM series_health sh
            LEFT JOIN series s ON s.id=sh.series_id
            WHERE sh.status='fail'
            ORDER BY sh.health_score ASC, sh.days_stale DESC, sh.series_id
            """
        ).fetchall()
    except sqlite3.Error:
        return {
            "ok": 0,
            "warn": 0,
            "fail": 0,
            "audited": 0,
            "reviewed_failures": 0,
            "unreviewed_failures": 0,
            "failures": [],
        }

    from engine.world_state import HEALTH_FAILURE_REVIEWS

    failures: list[dict[str, Any]] = []
    for row in failure_rows:
        item = dict(row)
        item["health_failure_review"] = HEALTH_FAILURE_REVIEWS.get(
            (str(item.get("provider") or ""), str(item.get("external_id") or ""))
        )
        failures.append(item)
    reviewed = sum(1 for row in failures if row.get("health_failure_review"))
    reviewed_by_provider: dict[str, int] = {}
    for row in failures:
        if not row.get("health_failure_review"):
            continue
        provider = str(row.get("provider") or "unknown")
        reviewed_by_provider[provider] = reviewed_by_provider.get(provider, 0) + 1
    fail = int(counts.get("fail", 0))
    return {
        "ok": int(counts.get("ok", 0)),
        "warn": int(counts.get("warn", 0)),
        "fail": fail,
        "audited": sum(int(v) for v in counts.values()),
        "reviewed_failures": reviewed,
        "unreviewed_failures": max(fail - reviewed, 0),
        "reviewed_failure_providers": dict(sorted(reviewed_by_provider.items())),
        "failures": failures[:20],
    }


def _provider_counts(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    try:
        for row in conn.execute("SELECT provider, count(*) AS n FROM series GROUP BY provider"):
            out.setdefault(row["provider"], {})["series"] = int(row["n"])
    except sqlite3.Error:
        pass
    try:
        for row in conn.execute(
            """
            SELECT s.provider, count(o.id) AS n
            FROM observations o
            JOIN series s ON s.id=o.series_id
            GROUP BY s.provider
            """
        ):
            out.setdefault(row["provider"], {})["observations"] = int(row["n"])
    except sqlite3.Error:
        pass
    for provider in list(out):
        out[provider].setdefault("series", 0)
        out[provider].setdefault("observations", 0)
    return out


def _source_counts_by_url(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    try:
        rows = conn.execute(
            """
            SELECT
                s.url,
                count(DISTINCT s.id) AS sources,
                count(DISTINCT CASE
                    WHEN s.content_hash IS NOT NULL AND length(s.content_hash)>0 THEN s.id
                END) AS hashed_sources,
                count(DISTINCT CASE WHEN rd.content_hash IS NOT NULL THEN s.id END) AS raw_linked_sources,
                count(DISTINCT CASE
                    WHEN s.content_hash IS NOT NULL AND length(s.content_hash)>0 AND rd.content_hash IS NULL THEN s.id
                END) AS hashes_without_bytes,
                count(DISTINCT CASE WHEN rd.content_hash IS NOT NULL THEN s.id END) AS exact_raw_sources,
                count(DISTINCT CASE
                    WHEN (
                        s.content_hash IS NOT NULL AND length(s.content_hash)>0 AND rd.content_hash IS NULL
                        AND COALESCE(s.raw_provenance_status, 'unknown')='legacy_hash_no_raw_doc'
                    )
                    OR (
                        (s.content_hash IS NULL OR length(s.content_hash)=0)
                        AND COALESCE(s.raw_provenance_status, 'unknown')='legacy_no_content_hash'
                    )
                    THEN s.id
                END) AS legacy_raw_gap_sources,
                count(DISTINCT CASE
                    WHEN (
                        s.content_hash IS NOT NULL AND length(s.content_hash)>0 AND rd.content_hash IS NULL
                        AND COALESCE(s.raw_provenance_status, 'unknown') NOT IN ('legacy_hash_no_raw_doc')
                    )
                    OR (
                        (s.content_hash IS NULL OR length(s.content_hash)=0)
                        AND COALESCE(s.raw_provenance_status, 'unknown') NOT IN ('legacy_no_content_hash')
                    )
                    THEN s.id
                END) AS unclassified_raw_sources
            FROM sources s
            LEFT JOIN raw_docs rd ON rd.content_hash=s.content_hash
            GROUP BY s.url
            """
        ).fetchall()
    except sqlite3.Error:
        return {}
    return {
        row["url"]: {
            "sources": int(row["sources"] or 0),
            "hashed_sources": int(row["hashed_sources"] or 0),
            "raw_linked_sources": int(row["raw_linked_sources"] or 0),
            "hashes_without_bytes": int(row["hashes_without_bytes"] or 0),
            "exact_raw_sources": int(row["exact_raw_sources"] or 0),
            "legacy_raw_gap_sources": int(row["legacy_raw_gap_sources"] or 0),
            "unclassified_raw_sources": int(row["unclassified_raw_sources"] or 0),
        }
        for row in rows
    }


def _source_counts_by_provider(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    try:
        rows = conn.execute(
            """
            SELECT
                s.provider,
                count(DISTINCT src.id) AS sources,
                count(DISTINCT CASE
                    WHEN src.content_hash IS NOT NULL AND length(src.content_hash)>0 THEN src.id
                END) AS hashed_sources,
                count(DISTINCT CASE WHEN rd.content_hash IS NOT NULL THEN src.id END) AS raw_linked_sources,
                count(DISTINCT CASE
                    WHEN src.content_hash IS NOT NULL AND length(src.content_hash)>0 AND rd.content_hash IS NULL THEN src.id
                END) AS hashes_without_bytes,
                count(DISTINCT CASE WHEN rd.content_hash IS NOT NULL THEN src.id END) AS exact_raw_sources,
                count(DISTINCT CASE
                    WHEN (
                        src.content_hash IS NOT NULL AND length(src.content_hash)>0 AND rd.content_hash IS NULL
                        AND COALESCE(src.raw_provenance_status, 'unknown')='legacy_hash_no_raw_doc'
                    )
                    OR (
                        (src.content_hash IS NULL OR length(src.content_hash)=0)
                        AND COALESCE(src.raw_provenance_status, 'unknown')='legacy_no_content_hash'
                    )
                    THEN src.id
                END) AS legacy_raw_gap_sources,
                count(DISTINCT CASE
                    WHEN (
                        src.content_hash IS NOT NULL AND length(src.content_hash)>0 AND rd.content_hash IS NULL
                        AND COALESCE(src.raw_provenance_status, 'unknown') NOT IN ('legacy_hash_no_raw_doc')
                    )
                    OR (
                        (src.content_hash IS NULL OR length(src.content_hash)=0)
                        AND COALESCE(src.raw_provenance_status, 'unknown') NOT IN ('legacy_no_content_hash')
                    )
                    THEN src.id
                END) AS unclassified_raw_sources
            FROM series s
            LEFT JOIN sources src ON src.id=s.source_id
            LEFT JOIN raw_docs rd ON rd.content_hash=src.content_hash
            GROUP BY s.provider
            """
        ).fetchall()
    except sqlite3.Error:
        return {}
    return {
        row["provider"]: {
            "sources": int(row["sources"] or 0),
            "hashed_sources": int(row["hashed_sources"] or 0),
            "raw_linked_sources": int(row["raw_linked_sources"] or 0),
            "hashes_without_bytes": int(row["hashes_without_bytes"] or 0),
            "exact_raw_sources": int(row["exact_raw_sources"] or 0),
            "legacy_raw_gap_sources": int(row["legacy_raw_gap_sources"] or 0),
            "unclassified_raw_sources": int(row["unclassified_raw_sources"] or 0),
        }
        for row in rows
    }


def _source_ids_by_provider(conn: sqlite3.Connection) -> dict[str, set[str]]:
    try:
        rows = conn.execute(
            """
            SELECT provider, source_id
            FROM series
            WHERE source_id IS NOT NULL
            GROUP BY provider, source_id
            """
        ).fetchall()
    except sqlite3.Error:
        return {}
    out: dict[str, set[str]] = {}
    for row in rows:
        out.setdefault(row["provider"], set()).add(row["source_id"])
    return out


def _fact_counts_by_source_id(conn: sqlite3.Connection) -> dict[str, int]:
    try:
        rows = conn.execute(
            """
            SELECT source_id, count(*) AS n
            FROM world_state_facts
            WHERE status='active'
              AND source_id IS NOT NULL
            GROUP BY source_id
            """
        ).fetchall()
    except sqlite3.Error:
        return {}
    return {row["source_id"]: int(row["n"] or 0) for row in rows}


def _fact_counts_by_source_url(conn: sqlite3.Connection, facts_by_source: dict[str, int] | None = None) -> dict[str, int]:
    facts_by_source = facts_by_source if facts_by_source is not None else _fact_counts_by_source_id(conn)
    if not facts_by_source:
        return {}
    try:
        rows = conn.execute("SELECT id, url FROM sources").fetchall()
    except sqlite3.Error:
        return {}
    out: dict[str, int] = {}
    for row in rows:
        count = facts_by_source.get(row["id"], 0)
        if count:
            out[row["url"]] = out.get(row["url"], 0) + count
    return out


def _fact_counts_by_provider(conn: sqlite3.Connection, facts_by_source: dict[str, int] | None = None) -> dict[str, int]:
    source_ids = _source_ids_by_provider(conn)
    if not source_ids:
        return {}
    facts_by_source = facts_by_source if facts_by_source is not None else _fact_counts_by_source_id(conn)
    return {
        provider: sum(facts_by_source.get(source_id, 0) for source_id in ids)
        for provider, ids in source_ids.items()
    }


def _entity_link_counts_by_method(conn: sqlite3.Connection) -> dict[str, int]:
    try:
        rows = conn.execute("SELECT method, count(*) AS n FROM entity_links GROUP BY method").fetchall()
    except sqlite3.Error:
        return {}
    return {row["method"]: int(row["n"] or 0) for row in rows}


def _series_entity_link_counts_by_provider(conn: sqlite3.Connection) -> dict[str, int]:
    try:
        rows = conn.execute(
            """
            SELECT s.provider, count(*) AS n
            FROM entity_links el
            JOIN series s ON s.id=el.ref_id
            WHERE el.ref_table='series'
            GROUP BY s.provider
            """
        ).fetchall()
    except sqlite3.Error:
        return {}
    return {row["provider"]: int(row["n"] or 0) for row in rows}


def _disk_status(repo_root: Path) -> dict[str, Any]:
    usage = disk_guard.usage(repo_root)
    safe = usage["free_gb"] >= disk_guard.DEFAULT_MIN_FREE_GB and usage["used_pct"] <= disk_guard.DEFAULT_MAX_USED_PCT
    return {
        **{k: round(v, 2) for k, v in usage.items()},
        "min_free_gb": disk_guard.DEFAULT_MIN_FREE_GB,
        "max_used_pct": disk_guard.DEFAULT_MAX_USED_PCT,
        "safe_for_writes": bool(safe),
    }


def _offload_status(repo_root: Path) -> dict[str, Any]:
    manifest = repo_root / "data" / "_offload_manifest.jsonl"
    try:
        entries = data_offload.read_manifest(manifest)
    except data_offload.DataOffloadError as exc:
        return {"manifest": str(manifest), "error": str(exc), "entries": 0}
    summary = data_offload.manifest_summary(entries)
    return {
        "manifest": str(manifest),
        "entries": summary["entries"],
        "uploaded": summary["uploaded"],
        "local_deleted": summary["local_deleted"],
        "recorded_gib": summary["recorded_gib"],
        "estimated_storage_usd_month": summary["estimated_storage_usd_month"],
    }


def _cost_status(conn: sqlite3.Connection) -> dict[str, Any]:
    try:
        total = conn.execute(
            """
            SELECT count(*) AS entries,
                   COALESCE(sum(est_cost_cents),0) AS estimated_cents,
                   COALESCE(sum(actual_cost_cents),0) AS actual_cents,
                   COALESCE(sum(CASE WHEN approval_status='approved' THEN est_cost_cents ELSE 0 END),0)
                     AS approved_cents,
                   COALESCE(sum(CASE WHEN approval_status='auto' THEN est_cost_cents ELSE 0 END),0)
                     AS auto_cents,
                   COALESCE(sum(CASE WHEN approval_status='pending' THEN est_cost_cents ELSE 0 END),0)
                     AS pending_cents,
                   COALESCE(sum(CASE WHEN approval_status='pending' THEN 1 ELSE 0 END),0)
                     AS pending_entries
            FROM cost_ledger
            """
        ).fetchone()
        providers = conn.execute(
            """
            SELECT provider,
                   count(*) AS entries,
                   COALESCE(sum(est_cost_cents),0) AS estimated_cents,
                   COALESCE(sum(actual_cost_cents),0) AS actual_cents
            FROM cost_ledger
            GROUP BY provider
            ORDER BY estimated_cents DESC, provider
            LIMIT 12
            """
        ).fetchall()
        pending = conn.execute(
            """
            SELECT id, ts, action, provider, units, est_cost_cents, funded_ref
            FROM cost_ledger
            WHERE approval_status='pending'
            ORDER BY est_cost_cents DESC, ts DESC
            LIMIT 5
            """
        ).fetchall()
    except sqlite3.Error:
        return {
            "entries": 0,
            "estimated_usd": 0.0,
            "actual_usd": 0.0,
            "approved_usd": 0.0,
            "auto_usd": 0.0,
            "pending_usd": 0.0,
            "pending_entries": 0,
            "providers": [],
            "pending": [],
        }
    return {
        "entries": int(total["entries"] or 0),
        "estimated_usd": round(int(total["estimated_cents"] or 0) / 100, 4),
        "actual_usd": round(int(total["actual_cents"] or 0) / 100, 4),
        "approved_usd": round(int(total["approved_cents"] or 0) / 100, 4),
        "auto_usd": round(int(total["auto_cents"] or 0) / 100, 4),
        "pending_usd": round(int(total["pending_cents"] or 0) / 100, 4),
        "pending_entries": int(total["pending_entries"] or 0),
        "providers": [
            {
                "provider": str(row["provider"]),
                "entries": int(row["entries"] or 0),
                "estimated_usd": round(int(row["estimated_cents"] or 0) / 100, 4),
                "actual_usd": round(int(row["actual_cents"] or 0) / 100, 4),
            }
            for row in providers
        ],
        "pending": [
            {
                "id": str(row["id"]),
                "ts": str(row["ts"]),
                "action": str(row["action"]),
                "provider": str(row["provider"]),
                "units": float(row["units"] or 0),
                "estimated_usd": round(int(row["est_cost_cents"] or 0) / 100, 4),
                "funded_ref": row["funded_ref"],
            }
            for row in pending
        ],
    }


def _scan_log_status(repo_root: Path) -> dict[str, Any]:
    """Summarize paid-scan logs that are separate from model/API cost ledger rows."""
    logs = {
        "athena": repo_root / "data" / "_collect_logs" / "athena_cost.log",
        "google_patents_bigquery": repo_root / "data" / "_collect_logs" / "google_patents_cost.log",
    }
    out: dict[str, Any] = {}
    for name, path in logs.items():
        if not path.exists():
            out[name] = {
                "exists": False,
                "gb_scanned": 0.0,
                "estimated_usd": 0.0,
                "pricing": "$5/TB scanned" if name == "athena" else "$6.25/TiB after free tier",
                "log": str(path),
            }
            continue
        text = path.read_text(errors="ignore")
        gb = sum(float(x) for x in re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*GB", text))
        if name == "athena":
            estimated_usd = (gb / 1000.0) * 5.0
            pricing = "$5/TB scanned"
        else:
            estimated_usd = (gb * GIB / (1024 ** 4)) * 6.25
            pricing = "$6.25/TiB after free tier"
        out[name] = {
            "exists": True,
            "gb_scanned": round(gb, 3),
            "estimated_usd": round(estimated_usd, 4),
            "pricing": pricing,
            "log": str(path),
        }
    return out


def _operational_status(
    spec: DataSourceSpec,
    *,
    facts: int,
    observations: int,
    feed_rows: int,
    source_count: int,
    auxiliary_records: int,
) -> str:
    if facts > 0:
        return "queryable_world_state"
    if observations > 0:
        return "ingested_series_only"
    if spec.layer == "entities" and auxiliary_records > 0:
        return "entity_backbone_landed"
    if auxiliary_records > 0:
        return "substrate_landed"
    if feed_rows > 0:
        return "collected_not_ingested"
    if source_count > 0:
        return "source_registered_only"
    if spec.status.startswith("deferred"):
        return "deferred"
    if spec.status.startswith("planned"):
        return "planned_not_collected"
    return "not_collected"


def _feed_needs_refresh(feed_status: dict[str, Any], *, stale_hours: float) -> bool:
    if not feed_status.get("exists"):
        return True
    if int(feed_status.get("rows") or 0) <= 0:
        return True
    age = feed_status.get("age_hours")
    return bool(age is not None and float(age) > stale_hours)


def _diagnostic_blocks_collection(diag: dict[str, Any]) -> bool:
    if not diag:
        return False
    if diag.get("needs_key") or diag.get("visibility_limited"):
        return True
    return bool(not diag.get("works", True) and int(diag.get("rows") or 0) == 0)


def _collection_readiness(
    spec: DataSourceSpec,
    *,
    feeds: tuple[str, ...],
    collector_feeds: tuple[str, ...],
    provider_only_feeds: tuple[str, ...] = (),
    keyless: set[str],
    gated: set[str],
    ingestable: set[str],
    known_slow: set[str],
    feed_statuses: list[dict[str, Any]],
    feed_bytes: int,
    disk_safe: bool,
    op_status: str,
    missing_collectors: list[str],
    stale_hours: float,
    max_local_refresh_mb: float,
) -> tuple[str, str | None, bool]:
    """Classify what it would take to collect/refresh this source safely.

    The status is intentionally operational, not strategic: it answers "can this be
    refreshed on the laptop now without surprise spend or a bulky corpus pull?"
    """
    if not disk_safe and (feeds or spec.status in {"partial", "landed_partial", "partial_metered"}):
        return "disk_blocked", None, False
    if spec.status == "planned_keyed" and any(f in gated for f in collector_feeds):
        return "key_or_visibility_blocked", None, False
    if any(f in gated for f in collector_feeds):
        return "metered_needs_approval", None, False
    if any(_diagnostic_blocks_collection(f.get("diagnostic") or {}) for f in feed_statuses):
        return "key_or_visibility_blocked", None, False
    if missing_collectors:
        return "collector_missing_or_unmapped", None, False
    if spec.status.startswith("deferred") or spec.status in {"planned_mixed", "deferred_heavy", "deferred_paid"}:
        return "cloud_first_or_deferred", None, False
    if not feeds:
        command = SOURCE_PIPELINE_COMMANDS.get(spec.id)
        if op_status in {"queryable_world_state", "entity_backbone_landed", "substrate_landed", "source_registered_only"}:
            return "provider_pipeline_landed", command, False
        if command:
            return "provider_pipeline_available", command, False
        return "planned_no_local_collector", None, False
    if provider_only_feeds and op_status in {"queryable_world_state", "substrate_landed"}:
        return "provider_pipeline_landed", None, False
    if not collector_feeds:
        return "planned_no_local_collector", None, False

    if not all(f in keyless for f in collector_feeds):
        return "non_keyless_or_manual", None, False
    if not all(f in ingestable for f in feeds):
        return "ingest_metadata_missing", None, False

    needs_refresh = any(_feed_needs_refresh(f, stale_hours=stale_hours) for f in feed_statuses)
    local_bytes_mb = feed_bytes / MIB
    if local_bytes_mb > max_local_refresh_mb:
        return "local_file_too_large_use_cloud_first", None, False

    slow = any(f in known_slow for f in collector_feeds)
    if slow:
        command = "python3 -m engine.feeds.collect_all --only " + " ".join(collector_feeds)
        if needs_refresh:
            return "slow_keyless_refresh_available", command, False
        return "slow_keyless_collected", command, False

    command = "python3 -m engine.feeds.collect_all --only " + " ".join(collector_feeds)
    if needs_refresh:
        return "safe_local_refresh_needed", command, True
    if op_status == "queryable_world_state":
        return "safe_local_refresh_available", command, True
    return "safe_local_collect_available", command, True


def data_status(
    conn: sqlite3.Connection,
    *,
    priority: int | None = None,
    status: str | None = None,
    feed_dir: Path | None = None,
    repo_root: Path | None = None,
    stale_hours: float = DEFAULT_STALE_HOURS,
    max_local_refresh_mb: float = DEFAULT_MAX_LOCAL_REFRESH_MB,
) -> dict[str, Any]:
    """Read-only operational status for the global source plan.

    This answers the practical question: which planned global sources have local feed files,
    ingested series, timestamped facts, raw-byte provenance, or blockers.
    """
    from engine.feeds import collect_all, ingest

    repo_root = repo_root or _db.REPO_ROOT
    feed_dir = feed_dir or repo_root / "data" / "feeds"
    specs = [DataSourceSpec(**row) for row in registry(priority=priority, status=status)]
    provider_counts = _provider_counts(conn)
    source_by_url = _source_counts_by_url(conn)
    source_by_provider = _source_counts_by_provider(conn)
    facts_by_source = _fact_counts_by_source_id(conn)
    facts_by_url = _fact_counts_by_source_url(conn, facts_by_source)
    facts_by_provider = _fact_counts_by_provider(conn, facts_by_source)
    entity_links_by_method = _entity_link_counts_by_method(conn)
    series_entity_links_by_provider = _series_entity_link_counts_by_provider(conn)
    disk = _disk_status(repo_root)
    offload = _offload_status(repo_root)
    cost_status = _cost_status(conn)
    scan_logs = _scan_log_status(repo_root)
    entity_identifiers = entity_identifier_status(conn)
    series_health = _series_health_status(conn)
    all_feeds = sorted({feed for feeds in SOURCE_FEED_MAP.values() for feed in feeds})
    feed_files = {feed: _feed_file_status(feed, feed_dir) for feed in all_feeds}
    keyless = set(collect_all.KEYLESS)
    gated = set(collect_all.GATED)
    known_slow = set(getattr(collect_all, "KNOWN_SLOW", set()))
    ingestable = set(ingest.FEED_META)
    db_counts = {
        "sources": _table_count(conn, "sources"),
        "series": _table_count(conn, "series"),
        "observations": _table_count(conn, "observations"),
        "world_state_facts": _table_count(conn, "world_state_facts"),
        "raw_docs": _table_count(conn, "raw_docs"),
        "papers": _table_count(conn, "papers"),
        "entities": _table_count(conn, "entities"),
        "entity_links": _table_count(conn, "entity_links"),
    }

    rows: list[dict[str, Any]] = []
    global_blockers: list[str] = []
    for spec in specs:
        feeds = SOURCE_FEED_MAP.get(spec.id, (spec.id,) if spec.id in ingestable or spec.id in keyless or spec.id in gated else ())
        urls = sorted(
            {
                *[ingest.FEED_META[f]["url"] for f in feeds if f in ingest.FEED_META],
                *SOURCE_URL_MAP.get(spec.id, ()),
            }
        )
        feed_statuses = [feed_files.get(f) or _feed_file_status(f, feed_dir) for f in feeds]
        feed_rows = sum(int(f["rows"]) for f in feed_statuses)
        feed_bytes = sum(int(f["bytes"]) for f in feed_statuses)
        series = sum(provider_counts.get(f, {}).get("series", 0) for f in feeds)
        observations = sum(provider_counts.get(f, {}).get("observations", 0) for f in feeds)
        url_source_count = sum(source_by_url.get(url, {}).get("sources", 0) for url in urls)
        url_hashed_sources = sum(source_by_url.get(url, {}).get("hashed_sources", 0) for url in urls)
        url_raw_linked_sources = sum(source_by_url.get(url, {}).get("raw_linked_sources", 0) for url in urls)
        url_hashes_without_bytes = sum(source_by_url.get(url, {}).get("hashes_without_bytes", 0) for url in urls)
        url_exact_raw_sources = sum(source_by_url.get(url, {}).get("exact_raw_sources", 0) for url in urls)
        url_legacy_raw_gap_sources = sum(source_by_url.get(url, {}).get("legacy_raw_gap_sources", 0) for url in urls)
        url_unclassified_raw_sources = sum(source_by_url.get(url, {}).get("unclassified_raw_sources", 0) for url in urls)
        url_facts = sum(facts_by_url.get(url, 0) for url in urls)
        provider_source_count = sum(source_by_provider.get(f, {}).get("sources", 0) for f in feeds)
        provider_hashed_sources = sum(source_by_provider.get(f, {}).get("hashed_sources", 0) for f in feeds)
        provider_raw_linked_sources = sum(source_by_provider.get(f, {}).get("raw_linked_sources", 0) for f in feeds)
        provider_hashes_without_bytes = sum(source_by_provider.get(f, {}).get("hashes_without_bytes", 0) for f in feeds)
        provider_exact_raw_sources = sum(source_by_provider.get(f, {}).get("exact_raw_sources", 0) for f in feeds)
        provider_legacy_raw_gap_sources = sum(source_by_provider.get(f, {}).get("legacy_raw_gap_sources", 0) for f in feeds)
        provider_unclassified_raw_sources = sum(source_by_provider.get(f, {}).get("unclassified_raw_sources", 0) for f in feeds)
        provider_facts = sum(facts_by_provider.get(f, 0) for f in feeds)
        source_count = max(url_source_count, provider_source_count)
        hashed_sources = max(url_hashed_sources, provider_hashed_sources)
        raw_linked_sources = max(url_raw_linked_sources, provider_raw_linked_sources)
        hashes_without_bytes = max(url_hashes_without_bytes, provider_hashes_without_bytes)
        exact_raw_sources = max(url_exact_raw_sources, provider_exact_raw_sources)
        legacy_raw_gap_sources = max(url_legacy_raw_gap_sources, provider_legacy_raw_gap_sources)
        unclassified_raw_sources = max(url_unclassified_raw_sources, provider_unclassified_raw_sources)
        facts = max(url_facts, provider_facts)
        auxiliary_records = _table_count(conn, "papers", "provider=?", ("arxiv",)) if spec.id == "arxiv" else 0
        entity_links = sum(entity_links_by_method.get(m, 0) for m in ENTITY_LINK_METHOD_MAP.get(spec.id, ()))
        entity_links += sum(series_entity_links_by_provider.get(f, 0) for f in feeds)
        auxiliary_records += entity_links
        op_status = _operational_status(
            spec,
            facts=facts,
            observations=observations,
            feed_rows=feed_rows,
            source_count=source_count,
            auxiliary_records=auxiliary_records,
        )
        blockers: list[str] = []
        provider_only = [f for f in feeds if f in PROVIDER_ONLY_FEEDS]
        collector_feeds = tuple(f for f in feeds if f in keyless or f in gated)
        collector_feed_statuses = [feed_files.get(f) or _feed_file_status(f, feed_dir) for f in collector_feeds]
        collector_feed_bytes = sum(int(f["bytes"]) for f in collector_feed_statuses)
        missing_collectors = [
            f for f in feeds
            if f not in keyless and f not in gated and f not in ingestable and f not in PROVIDER_ONLY_FEEDS
        ]
        gated_collectors = [f for f in feeds if f in gated]
        readiness, command, safe_local_refresh = _collection_readiness(
            spec,
            feeds=feeds,
            collector_feeds=collector_feeds,
            provider_only_feeds=tuple(provider_only),
            keyless=keyless,
            gated=gated,
            ingestable=ingestable,
            known_slow=known_slow,
            feed_statuses=collector_feed_statuses or feed_statuses,
            feed_bytes=collector_feed_bytes or feed_bytes,
            disk_safe=disk["safe_for_writes"],
            op_status=op_status,
            missing_collectors=missing_collectors,
            stale_hours=stale_hours,
            max_local_refresh_mb=max_local_refresh_mb,
        )
        safe_local_due = bool(
            safe_local_refresh
            and any(_feed_needs_refresh(f, stale_hours=stale_hours) for f in collector_feed_statuses)
        )
        if not disk["safe_for_writes"] and (feeds or spec.status in {"partial", "landed_partial", "partial_metered"}):
            blockers.append("local disk guard currently blocks write-heavy collection/backfills")
        if gated_collectors and spec.status == "planned_keyed":
            blockers.append("keyed collector requires API key/terms before collection: " + ", ".join(gated_collectors))
        elif gated_collectors:
            blockers.append("metered collector requires explicit cost approval: " + ", ".join(gated_collectors))
        if missing_collectors and op_status in {"planned_not_collected", "not_collected"}:
            blockers.append("collector not implemented/mapped: " + ", ".join(missing_collectors))
        missing_ingest_metadata = [
            f for f in feeds if f not in ingestable and f not in gated and f not in PROVIDER_ONLY_FEEDS
        ]
        if missing_ingest_metadata:
            blockers.append("ingest metadata missing for mapped feeds: " + ", ".join(missing_ingest_metadata))
        if spec.status == "planned_keyed":
            blockers.append("planned source requires an API key/terms before collection")
        if spec.status == "planned_mixed":
            blockers.append("planned mixed source contains free and likely paid/keyed subfeeds; split before collection")
        if spec.status == "deferred_heavy":
            blockers.append("deferred heavy corpus; collect cloud-first/object-storage-first, not onto laptop")
        if spec.status == "deferred_paid":
            blockers.append("deferred paid/alt-data source; requires explicit ROI and spend approval")
        if spec.layer == "entities" and auxiliary_records > 0 and facts == 0:
            blockers.append("entity identifiers landed; not a numeric/fact time-series source")
        if feed_rows > 0 and observations == 0:
            blockers.append("feed file exists but no DB observations for mapped provider")
        if observations > 0 and facts == 0:
            blockers.append("observations landed but timestamped world-state facts are not present")
        if source_count > 0 and unclassified_raw_sources > 0:
            blockers.append("source raw-byte provenance is unclassified")
        elif source_count > 0 and legacy_raw_gap_sources > 0:
            blockers.append("legacy raw-byte gaps remain; explicitly marked as non-exact provenance")
        if spec.id == "prediction_markets" and provider_counts.get("metaculus", {}).get("observations", 0) == 0:
            blockers.append("Metaculus community aggregates are visibility-limited; store only exposed dated aggregates")
        if spec.id == "semantic_scholar" and facts > 0:
            blockers.append("Semantic Scholar full dataset files/API scale require an API key; only release manifest is landed")
        if spec.id == "semantic_scholar" and facts == 0:
            blockers.append("Semantic Scholar API/dataset access is rate/key limited; no local API key detected")
        if spec.id == "uspto_bulk" and op_status in {"planned_not_collected", "not_collected"}:
            blockers.append("USPTO PatentsView keyless path retired; ODP requires API key or use metered Google Patents")
        for blocker in blockers:
            if blocker not in global_blockers:
                global_blockers.append(blocker)
        rows.append(
            {
                **asdict(spec),
                "feeds": list(feeds),
                "collector_keyless": [f for f in feeds if f in keyless],
                "collector_gated": [f for f in feeds if f in gated],
                "provider_only": provider_only,
                "ingest_available": [f for f in feeds if f in ingestable],
                "feed_files": feed_statuses,
                "feed_rows": feed_rows,
                "feed_bytes": feed_bytes,
                "db_series": series,
                "db_observations": observations,
                "world_state_facts": facts,
                "auxiliary_records": auxiliary_records,
                "entity_links": entity_links,
                "source_records": source_count,
                "source_records_with_hash": hashed_sources,
                "source_records_with_raw": raw_linked_sources,
                "source_hashes_without_bytes": hashes_without_bytes,
                "source_records_exact_raw": exact_raw_sources,
                "source_records_legacy_raw_gap": legacy_raw_gap_sources,
                "source_records_unclassified_raw": unclassified_raw_sources,
                "operational_status": op_status,
                "collection_readiness": readiness,
                "safe_local_refresh": safe_local_refresh,
                "safe_local_due": safe_local_due,
                "collection_command": command,
                "blockers": blockers,
            }
        )

    by_operational_status: dict[str, int] = {}
    by_collection_readiness: dict[str, int] = {}
    safe_local_feeds: list[str] = []
    safe_local_due_feeds: list[str] = []
    slow_keyless_feeds: list[str] = []
    metered_feeds: list[str] = []
    keyed_feeds: list[str] = []
    for row in rows:
        op = row["operational_status"]
        by_operational_status[op] = by_operational_status.get(op, 0) + 1
        readiness = row["collection_readiness"]
        by_collection_readiness[readiness] = by_collection_readiness.get(readiness, 0) + 1
        for feed in row["collector_keyless"]:
            feed_status = feed_files.get(feed) or _feed_file_status(feed, feed_dir)
            diag = feed_status.get("diagnostic") or {}
            if feed in known_slow:
                slow_keyless_feeds.append(feed)
                continue
            if feed not in ingestable:
                continue
            if diag.get("needs_key") or diag.get("visibility_limited"):
                continue
            if diag and not diag.get("works", True) and int(diag.get("rows") or 0) == 0:
                continue
            if (int(feed_status.get("bytes") or 0) / MIB) > max_local_refresh_mb:
                continue
            safe_local_feeds.append(feed)
            if _feed_needs_refresh(feed_status, stale_hours=stale_hours):
                safe_local_due_feeds.append(feed)
        if row["status"] == "planned_keyed":
            keyed_feeds.extend(row["collector_gated"])
        else:
            metered_feeds.extend(row["collector_gated"])
    safe_local_feeds = sorted(set(safe_local_feeds))
    safe_local_due_feeds = sorted(set(safe_local_due_feeds))
    slow_keyless_feeds = sorted(set(slow_keyless_feeds))
    metered_feeds = sorted(set(metered_feeds))
    keyed_feeds = sorted(set(keyed_feeds))
    return {
        "summary": {
            **global_view(),
            "shown_sources": len(rows),
            "operational_status": dict(sorted(by_operational_status.items())),
            "collection_readiness": dict(sorted(by_collection_readiness.items())),
            "feed_files_present": sum(1 for f in feed_files.values() if f["exists"]),
            "feed_diagnostics": sum(1 for f in feed_files.values() if f.get("diagnostic")),
            "feed_diagnostics_blocked": sum(
                1 for f in feed_files.values() if _diagnostic_blocks_collection(f.get("diagnostic") or {})
            ),
            "feed_rows_total": sum(int(f["rows"]) for f in feed_files.values()),
            "mapped_feeds": len(all_feeds),
            "disk_safe_for_writes": disk["safe_for_writes"],
            "safe_local_refresh_feeds": safe_local_feeds,
            "safe_local_due_feeds": safe_local_due_feeds,
            "safe_local_refresh_command": (
                "python3 -m engine.feeds.collect_all --safe-local --stale-only"
                if safe_local_due_feeds else None
            ),
            "safe_local_dry_run_command": "python3 -m engine.feeds.collect_all --safe-local --stale-only --dry-run",
            "slow_keyless_feeds": slow_keyless_feeds,
            "metered_feeds": metered_feeds,
            "keyed_feeds": keyed_feeds,
            "stale_hours": stale_hours,
            "max_local_refresh_mb": max_local_refresh_mb,
        },
        "db": db_counts,
        "disk": disk,
        "offload": offload,
        "cost_ledger": cost_status,
        "scan_logs": scan_logs,
        "entity_identifiers": entity_identifiers,
        "series_health": series_health,
        "action_plan": _source_action_plan(rows),
        "blockers": global_blockers,
        "sources": rows,
    }


def seed_top_entities(conn: sqlite3.Connection, *, log=print) -> dict[str, int]:
    created = existing = 0
    for spec in TOP_ENTITIES:
        ent = Entity(
            kind=spec.kind,
            canonical_name=spec.name,
            domain=spec.domain,
            aliases=list(spec.aliases),
            note=spec.note or f"Global-view seed entity tagged {', '.join(spec.tags)}.",
        )
        row = conn.execute(
            "SELECT id, aliases, note FROM entities WHERE kind=? AND canonical_name=?",
            (ent.kind, ent.canonical_name),
        ).fetchone()
        if row:
            existing += 1
            try:
                old_aliases = json.loads(row["aliases"] or "[]")
            except json.JSONDecodeError:
                old_aliases = []
            merged = sorted({*old_aliases, *ent.aliases})
            conn.execute(
                "UPDATE entities SET aliases=?, domain=COALESCE(domain, ?) WHERE id=?",
                (json.dumps(merged), ent.domain, row["id"]),
            )
            continue
        conn.execute(
            "INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                ent.id, ent.kind, ent.canonical_name, ent.domain, json.dumps(ent.aliases),
                ent.note, _now().isoformat(),
            ),
        )
        created += 1
        log(f"  + {ent.canonical_name} [{ent.kind}]")
    conn.commit()
    return {"created": created, "existing": existing, "total": len(TOP_ENTITIES)}


def format_plan(rows: list[dict[str, Any]] | None = None, *, include_entities: bool = False) -> str:
    rows = rows or registry()
    view = global_view()
    lines = [
        "Global world-data coverage plan",
        f"sources={view['sources']} top_entities={view['top_entities']}",
        "sources by layer: " + ", ".join(f"{k}={v}" for k, v in view["sources_by_layer"].items()),
        "sources by status: " + ", ".join(f"{k}={v}" for k, v in view["sources_by_status"].items()),
        "priority-1 sources: " + ", ".join(view["priority_1_sources"]),
        "",
        "source registry:",
    ]
    for r in rows:
        lines.append(
            f"- P{r['priority']} {r['id']} [{r['layer']}/{r['status']}]: {r['coverage']} | "
            f"cost: {r['cost']} | outputs: {', '.join(r['outputs'])}"
        )
    if include_entities:
        lines.extend(["", "top global entities:"])
        by_kind: dict[str, list[dict[str, Any]]] = {}
        for e in top_entities():
            by_kind.setdefault(e["kind"], []).append(e)
        for kind, ents in by_kind.items():
            names = ", ".join(e["name"] for e in ents)
            lines.append(f"- {kind} ({len(ents)}): {names}")
    return "\n".join(lines)


def _short_int(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def _unblock_steps_for_source(row: dict[str, Any], *, readiness: str) -> list[str]:
    sid = str(row.get("id") or "")
    command = row.get("collection_command")
    if readiness == "metered_needs_approval":
        specific = {
            "google_patents": [
                "Run BigQuery dry-run with the configured scan cap before any extract.",
                "Approve only a targeted extract whose estimated bytes fit the budget.",
                "Write extracted batches to object storage/raw provenance, then rebuild derived patent facts.",
            ],
            "paper_patent_reliance": [
                "Estimate Athena/S3 scan size before running the paper-patent join.",
                "Approve the cost-ledger entry only if the scan fits the patent budget.",
                "Store derived reliance facts and paper->patent edges; keep raw/bulk files off the laptop.",
            ],
        }
        return specific.get(sid, [
            "Run the source-specific dry-run or scan estimator first.",
            "Approve the generated cost-ledger entry if it fits the budget.",
            "Collect only the targeted extract and preserve provenance.",
        ])
    if readiness == "key_or_visibility_blocked":
        specific = {
            "prediction_markets": [
                "Use Polymarket-only facts until authenticated Metaculus dated aggregates are visible.",
                "If Metaculus access is granted, rerun the status probe and store only exposed dated aggregates.",
                "Keep hidden/community-only values out of world-state facts.",
            ],
            "patentsview_odp": [
                "Provision a USPTO Open Data Portal API key and confirm terms.",
                "Wire the ODP query schema into the PatentsView collector.",
                "Run a status probe before collecting CPC/application/grant facts.",
            ],
        }
        return specific.get(sid, [
            "Acquire the required API key, credentials, or visibility permission.",
            "Run a status probe before collection.",
            "Only ingest dated facts that are visible and provenance-backed.",
        ])
    if readiness == "cloud_first_or_deferred":
        specific = {
            "common_crawl_news": [
                "Do not collect WARC/news bodies onto the laptop.",
                "Design an object-storage-first sampled extraction job with domain/date partitions.",
                "Land only derived article/event facts and citations into SQLite.",
            ],
            "land_permits_cadastre": [
                "Inventory jurisdictions and portals before collecting any bulk geospatial or parcel data.",
                "Start with official/open permit and planning feeds; defer paid parcel vendors until a forecast use case justifies them.",
                "Keep raw map layers and documents in object storage, then land only permit facts, parcel edges, and citations in SQLite.",
            ],
            "talent_stack": [
                "Split free ORCID/GitHub sources from paid job-posting sources.",
                "Collect free/open talent signals first with object-storage/raw provenance.",
                "Defer paid hiring data until a forecast use case justifies spend.",
            ],
            "shipping_satellite": [
                "Define a narrow bottleneck/ROI pilot before buying alt-data.",
                "Approve a paid-data budget only for that pilot.",
                "Store derived logistics/capacity signals, not large raw imagery/AIS dumps, in SQLite.",
            ],
        }
        return specific.get(sid, [
            "Keep bulk/raw collection cloud-first or deferred.",
            "Use object storage for raw corpora and SQLite only for derived facts.",
            "Run a small sampled pilot before broad collection.",
        ])
    if readiness == "planned_no_local_collector":
        specific = {
            "environmental_planning_eia": [
                "Implement a small official-portal collector for dated EIA/planning notices and decisions.",
                "Preserve raw PDF/HTML notices with hashes before extracting project, sponsor, location, and decision dates.",
                "Keep OCR/translation or cloud extraction approval-gated until the open-pilot precision is measured.",
            ],
            "open_geospatial_land_context": [
                "Design an object-storage-first geospatial partition layout before downloading bulk map layers.",
                "Derive compact project/parcel/country context summaries for SQLite.",
                "Keep this layer labeled as context so it is never confused with official permit approval.",
            ],
            "resource_concessions_contracts": [
                "Implement jurisdiction-by-jurisdiction collectors for open concession/license registers.",
                "Preserve contracts, license notices, and map layers with content hashes in object storage.",
                "Extract holder, commodity, grant, renewal, expiry, and status dates into world-state facts.",
            ],
            "uspto_bulk": [
                "Implement a streaming USPTO bulk XML loader.",
                "Write raw XML/bulk artifacts to object storage, not the laptop.",
                "Derive patent/assignee/CPC facts and dedupe against Google Patents.",
            ],
            "epo_ops": [
                "Provision EPO OPS credentials or confirm free-quota access.",
                "Implement family/priority-date enrichment before broad collection.",
                "Store family facts and jurisdiction links with source hashes.",
            ],
        }
        return specific.get(sid, [
            "Implement or map the collector.",
            "Add ingest metadata and provenance requirements.",
            "Run dry-run/status checks before broad collection.",
        ])
    if readiness in {"provider_pipeline_available", "provider_pipeline_landed"} and command:
        return [f"Run `{command}` when refreshing provider-side entity enrichment is needed."]
    if str(readiness).startswith("safe_local_") and command:
        return [f"Use stale-only preflight first, then run `{command}` only if the feed is due."]
    return []


def _preflight_commands_for_source(row: dict[str, Any], *, readiness: str) -> list[str]:
    sid = str(row.get("id") or "")
    specific: dict[str, list[str]] = {
        "google_patents": [
            "python3 -m engine.feeds.google_patents --label <topic_slug> --terms \"<term1>,<term2>\" --since 2014 --dry-run --max-gb 40"
        ],
        "paper_patent_reliance": [
            "python3 -m engine.cli world-data-approvals --json",
            "tail -n 20 data/_collect_logs/athena_cost.log",
        ],
        "prediction_markets": [
            "python3 -m engine.cli world-data-status --priority 2",
            "python3 -m engine.feeds.collect_all --only polymarket --dry-run",
        ],
        "patentsview_odp": [
            "python3 -m engine.feeds.patentsview",
        ],
        "common_crawl_news": [
            "python3 -m engine.cli world-data-approvals --json",
        ],
        "environmental_planning_eia": [
            "python3 -m engine.feeds.collect_all --only land_permits_canada_iaac --dry-run",
            "python3 -m engine.feeds.collect_all --only us_permitting_dashboard --dry-run",
            "python3 -m engine.feeds.collect_all --only australia_epbc_referrals --dry-run",
            "python3 -m engine.cli world-data-approvals --json",
        ],
        "land_permits_cadastre": [
            "python3 -m engine.feeds.collect_all --only blm_mining_claims --dry-run",
            "python3 -m engine.feeds.collect_all --only miningterminal_permits --dry-run",
            "python3 -m engine.cli world-data-approvals --json",
        ],
        "open_geospatial_land_context": [
            "python3 -m engine.cli world-data-approvals --json",
        ],
        "resource_concessions_contracts": [
            "python3 -m engine.feeds.collect_all --only resourcecontracts --dry-run",
            "python3 -m engine.cli world-data-approvals --json",
        ],
        "talent_stack": [
            "python3 -m engine.cli world-data-approvals --json",
        ],
        "shipping_satellite": [
            "python3 -m engine.cli world-data-approvals --json",
        ],
        "uspto_bulk": [
            "python3 -m engine.cli world-data-approvals --json",
        ],
        "epo_ops": [
            "python3 -m engine.cli world-data-approvals --json",
        ],
    }
    if sid in specific:
        return specific[sid]
    command = row.get("collection_command")
    if readiness in {"provider_pipeline_available", "provider_pipeline_landed"} and command:
        return [str(command)]
    if str(readiness).startswith("safe_local_"):
        return ["python3 -m engine.feeds.collect_all --safe-local --stale-only --dry-run"]
    return []


def _execution_risk_for_source(row: dict[str, Any], *, readiness: str) -> dict[str, Any]:
    sid = str(row.get("id") or "")
    preflight_writes = sid in {"patentsview_odp", "prediction_markets"}
    land_use_bulk_sources = {
        "environmental_planning_eia",
        "land_permits_cadastre",
        "open_geospatial_land_context",
        "resource_concessions_contracts",
    }
    return {
        "preflight_writes": preflight_writes,
        "requires_paid_approval": readiness == "metered_needs_approval" or sid == "shipping_satellite",
        "requires_key": readiness == "key_or_visibility_blocked" or sid in {"epo_ops"},
        "cloud_first": (
            readiness == "cloud_first_or_deferred"
            or sid in {"uspto_bulk", "epo_ops", "paper_patent_reliance"}
            or sid in land_use_bulk_sources
        ),
        "local_bulk_risk": sid in {"common_crawl_news", "uspto_bulk", "shipping_satellite"} or sid in land_use_bulk_sources,
        "notes": _risk_notes_for_source(sid, readiness=readiness, preflight_writes=preflight_writes),
    }


def _risk_notes_for_source(sid: str, *, readiness: str, preflight_writes: bool) -> list[str]:
    notes: list[str] = []
    if preflight_writes:
        notes.append("preflight may update a small status/feed sidecar")
    else:
        notes.append("listed preflight is read-only/no-spawn")
    if readiness == "metered_needs_approval":
        notes.append("execution after preflight requires cost-ledger approval")
    if sid in {
        "common_crawl_news",
        "environmental_planning_eia",
        "land_permits_cadastre",
        "open_geospatial_land_context",
        "resource_concessions_contracts",
        "uspto_bulk",
        "shipping_satellite",
    }:
        notes.append("bulk/raw data must stay off-laptop in object storage")
    if sid in {"patentsview_odp", "epo_ops", "prediction_markets"}:
        notes.append("credential or visibility state must be resolved before broad collection")
    return notes


def _source_action_plan(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compact operator plan from source readiness rows.

    This is intentionally a status artifact, not an executor. It tells the user/operator what
    commands are safe/free now, what is slow/manual, and what needs explicit approval or keys.
    """
    buckets = {
        "safe_local_due": [],
        "safe_local_refreshable": [],
        "provider_pipelines": [],
        "slow_keyless_manual": [],
        "metered_needs_approval": [],
        "key_or_visibility_blocked": [],
        "cloud_first_or_deferred": [],
        "planned_no_local_collector": [],
    }
    for row in rows:
        readiness = row["collection_readiness"]
        item = {
            "id": row["id"],
            "name": row["name"],
            "priority": row["priority"],
            "layer": row["layer"],
            "status": row["status"],
            "readiness": readiness,
            "cost": row.get("cost"),
            "access": row.get("access"),
            "coverage": row.get("coverage"),
            "process": list(row.get("process") or []),
            "outputs": list(row.get("outputs") or []),
            "command": row.get("collection_command"),
            "facts": int(row["world_state_facts"]),
            "raw_sources": int(row["source_records_with_raw"]),
            "blocker": row["blockers"][0] if row["blockers"] else None,
        }
        item["preflight_commands"] = _preflight_commands_for_source(row, readiness=readiness)
        item["unblock_steps"] = _unblock_steps_for_source(row, readiness=readiness)
        item["execution_risk"] = _execution_risk_for_source(row, readiness=readiness)
        if str(readiness).startswith("safe_local_"):
            if row.get("safe_local_due"):
                buckets["safe_local_due"].append(item)
            else:
                buckets["safe_local_refreshable"].append(item)
        elif readiness in {"provider_pipeline_available", "provider_pipeline_landed"}:
            buckets["provider_pipelines"].append(item)
        elif readiness in {"slow_keyless_collected", "slow_keyless_refresh_available"}:
            buckets["slow_keyless_manual"].append(item)
        elif readiness == "metered_needs_approval":
            buckets["metered_needs_approval"].append(item)
        elif readiness == "key_or_visibility_blocked":
            buckets["key_or_visibility_blocked"].append(item)
        elif readiness == "cloud_first_or_deferred":
            buckets["cloud_first_or_deferred"].append(item)
        elif readiness == "planned_no_local_collector":
            buckets["planned_no_local_collector"].append(item)
    for key, values in buckets.items():
        values.sort(key=lambda row: (int(row["priority"]), str(row["id"])))
    return {
        "summary": {key: len(values) for key, values in buckets.items()},
        **buckets,
    }


def approval_plan(status: dict[str, Any]) -> dict[str, Any]:
    """Compact read-only packet for deciding what needs approval, keys, or cloud-first handling."""
    summary = status["summary"]
    actions = status.get("action_plan") or {}
    return {
        "summary": {
            "safe_local_due_feeds": len(summary.get("safe_local_due_feeds") or []),
            "safe_local_refreshable_feeds": len(summary.get("safe_local_refresh_feeds") or []),
            "safe_local_dry_run_command": summary.get("safe_local_dry_run_command"),
            "safe_local_refresh_command": summary.get("safe_local_refresh_command"),
            "metered_sources": len(actions.get("metered_needs_approval") or []),
            "key_or_visibility_blocked_sources": len(actions.get("key_or_visibility_blocked") or []),
            "cloud_first_or_deferred_sources": len(actions.get("cloud_first_or_deferred") or []),
            "planned_no_local_collector_sources": len(actions.get("planned_no_local_collector") or []),
        },
        "cost_ledger": status.get("cost_ledger", {}),
        "metered_needs_approval": actions.get("metered_needs_approval") or [],
        "key_or_visibility_blocked": actions.get("key_or_visibility_blocked") or [],
        "cloud_first_or_deferred": actions.get("cloud_first_or_deferred") or [],
        "planned_no_local_collector": actions.get("planned_no_local_collector") or [],
        "blockers": status.get("blockers") or [],
    }


def _format_execution_risk(risk: dict[str, Any]) -> str:
    if not risk:
        return ""
    bits = [
        f"preflight_writes={'yes' if risk.get('preflight_writes') else 'no'}",
        f"paid={'yes' if risk.get('requires_paid_approval') else 'no'}",
        f"key={'yes' if risk.get('requires_key') else 'no'}",
        f"cloud_first={'yes' if risk.get('cloud_first') else 'no'}",
        f"local_bulk={'yes' if risk.get('local_bulk_risk') else 'no'}",
    ]
    notes = [str(note) for note in (risk.get("notes") or []) if note]
    if notes:
        bits.append("notes=" + "; ".join(notes[:3]))
    return "; ".join(bits)


def _coverage_scope(coverage: str) -> str:
    text = coverage.lower()
    if any(token in text for token in ("global", "worldwide", "international", "across major exchanges")):
        return "global"
    if any(token in text for token in ("us/", "us ", "u.s.", "united states")):
        return "us"
    if any(token in text for token in ("uk ", "eu ", "europe", "euro")):
        return "regional"
    return "mixed_or_topic"


def _cost_posture(row: dict[str, Any], risk: dict[str, Any]) -> str:
    cost = str(row.get("cost") or "").lower()
    if risk.get("requires_paid_approval"):
        return "paid_approval_required"
    if "paid" in cost or "metered" in cost:
        return "paid_or_metered"
    if "key" in cost or "quota" in cost:
        return "free_keyed_or_quota"
    if "$0" in cost or "free" in cost or "public" in cost:
        return "free_or_keyless"
    return "unknown_or_mixed"


def _storage_posture(row: dict[str, Any], risk: dict[str, Any]) -> str:
    storage = str(row.get("storage") or "").lower()
    if risk.get("local_bulk_risk") or "object storage" in storage or "s3" in storage or "parquet" in storage:
        return "object_storage_or_cloud_first"
    if "raw docs" in storage or "raw" in storage:
        return "raw_docs_plus_derived_sqlite"
    if "sqlite" in storage or "feed jsonl" in storage or "derived" in storage:
        return "derived_sqlite_or_feed_jsonl"
    return "unspecified"


def _next_action_type(row: dict[str, Any]) -> str:
    readiness = str(row.get("collection_readiness") or "")
    if readiness == "safe_local_collect_available":
        return "safe_local_collect_available"
    if readiness == "safe_local_refresh_needed":
        return "safe_local_refresh_due"
    if readiness == "safe_local_refresh_available":
        return "safe_local_refresh_due" if row.get("safe_local_due") else "safe_local_refresh_available"
    if readiness in {"provider_pipeline_available", "provider_pipeline_landed"}:
        return "provider_entity_enrichment"
    if readiness == "slow_keyless_collected":
        return "slow_keyless_manual_refresh"
    if readiness == "slow_keyless_refresh_available":
        return "slow_keyless_manual_collect"
    if readiness == "metered_needs_approval":
        return "needs_spend_approval"
    if readiness == "key_or_visibility_blocked":
        return "needs_key_or_visibility_fix"
    if readiness == "cloud_first_or_deferred":
        return "cloud_first_or_deferred"
    if readiness == "planned_no_local_collector":
        return "needs_collector_or_keyed_pipeline"
    if readiness == "disk_blocked":
        return "disk_blocked"
    return readiness or "unknown"


def source_matrix(status: dict[str, Any]) -> dict[str, Any]:
    """Joined source registry + operational state for data planning.

    This is the granular, read-only "what data, how processed, what cost, what next" view. It does
    not execute collectors and is safe to render in the cockpit or export for review.
    """
    rows: list[dict[str, Any]] = []
    for row in status.get("sources") or []:
        readiness = str(row.get("collection_readiness") or "")
        risk = _execution_risk_for_source(row, readiness=readiness)
        preflight = _preflight_commands_for_source(row, readiness=readiness)
        unblock = _unblock_steps_for_source(row, readiness=readiness)
        matrix_row = {
            "id": row["id"],
            "name": row["name"],
            "priority": row["priority"],
            "layer": row["layer"],
            "registry_status": row["status"],
            "coverage": row.get("coverage"),
            "coverage_scope": _coverage_scope(str(row.get("coverage") or "")),
            "access": row.get("access"),
            "storage": row.get("storage"),
            "storage_posture": _storage_posture(row, risk),
            "cost": row.get("cost"),
            "cost_posture": _cost_posture(row, risk),
            "process": list(row.get("process") or []),
            "outputs": list(row.get("outputs") or []),
            "entities": list(row.get("entities") or []),
            "operational_status": row.get("operational_status"),
            "collection_readiness": readiness,
            "next_action_type": _next_action_type(row),
            "collection_command": row.get("collection_command"),
            "preflight_commands": preflight,
            "unblock_steps": unblock,
            "execution_risk": risk,
            "feed_rows": int(row.get("feed_rows") or 0),
            "feed_bytes": int(row.get("feed_bytes") or 0),
            "db_series": int(row.get("db_series") or 0),
            "db_observations": int(row.get("db_observations") or 0),
            "world_state_facts": int(row.get("world_state_facts") or 0),
            "entity_links": int(row.get("entity_links") or 0),
            "source_records": int(row.get("source_records") or 0),
            "source_records_with_raw": int(row.get("source_records_with_raw") or 0),
            "source_records_legacy_raw_gap": int(row.get("source_records_legacy_raw_gap") or 0),
            "blockers": list(row.get("blockers") or []),
        }
        rows.append(matrix_row)
    rows.sort(key=lambda r: (int(r["priority"]), str(r["layer"]), str(r["id"])))
    return {
        "summary": {
            "sources": len(rows),
            "global_sources": sum(1 for row in rows if row["coverage_scope"] == "global"),
            "queryable_world_state_sources": sum(
                1 for row in rows if row.get("operational_status") == "queryable_world_state"
            ),
            "safe_local_due_sources": sum(1 for row in rows if row["next_action_type"] == "safe_local_refresh_due"),
            "paid_approval_sources": sum(1 for row in rows if row["cost_posture"] == "paid_approval_required"),
            "key_or_visibility_sources": sum(
                1 for row in rows if row["next_action_type"] == "needs_key_or_visibility_fix"
            ),
            "cloud_first_sources": sum(1 for row in rows if row["storage_posture"] == "object_storage_or_cloud_first"),
            "world_state_facts": int((status.get("db") or {}).get("world_state_facts") or 0),
        },
        "disk": status.get("disk", {}),
        "cost_ledger": status.get("cost_ledger", {}),
        "sources": rows,
    }


def format_source_matrix(status_or_matrix: dict[str, Any], *, limit: int | None = None) -> str:
    summary_in = status_or_matrix.get("summary") or {}
    matrix = status_or_matrix if "global_sources" in summary_in else source_matrix(status_or_matrix)
    summary = matrix.get("summary") or {}
    disk = matrix.get("disk") or {}
    costs = matrix.get("cost_ledger") or {}
    rows = list(matrix.get("sources") or [])
    if limit is not None:
        rows = rows[:limit]
    lines = [
        "World data source matrix (read-only)",
        f"sources={summary.get('sources', 0)} global={summary.get('global_sources', 0)} "
        f"queryable={summary.get('queryable_world_state_sources', 0)} "
        f"facts={_short_int(int(summary.get('world_state_facts') or 0))}",
        f"safe_due={summary.get('safe_local_due_sources', 0)} "
        f"paid_approval={summary.get('paid_approval_sources', 0)} "
        f"key_or_visibility={summary.get('key_or_visibility_sources', 0)} "
        f"cloud_first={summary.get('cloud_first_sources', 0)}",
        f"disk_free={float(disk.get('free_gb', 0)):.1f}GiB "
        f"ledger_actual=${float(costs.get('actual_usd', 0)):.2f} "
        f"ledger_est=${float(costs.get('estimated_usd', 0)):.2f}",
    ]
    for row in rows:
        lines.append(
            f"- P{row['priority']} {row['id']} [{row['layer']}/{row['coverage_scope']}] "
            f"state={row['operational_status']} next={row['next_action_type']} "
            f"cost={row['cost_posture']} facts={_short_int(int(row['world_state_facts']))}"
        )
        lines.append(f"  process: {'; '.join(str(p) for p in row['process'][:3])}")
        lines.append(f"  outputs: {'; '.join(str(o) for o in row['outputs'][:3])}")
        if row.get("preflight_commands"):
            lines.append("  preflight: " + "; ".join(str(c) for c in row["preflight_commands"][:2]))
        elif row.get("collection_command"):
            lines.append(f"  command: {row['collection_command']}")
        if row.get("blockers"):
            lines.append("  blocker: " + str(row["blockers"][0]))
    if limit is not None and int(summary.get("sources") or 0) > len(rows):
        lines.append(f"- ... {int(summary.get('sources') or 0) - len(rows)} more")
    return "\n".join(lines)


def source_matrix_csv(matrix: dict[str, Any]) -> str:
    import csv
    import io

    fields = [
        "id", "name", "priority", "layer", "registry_status", "coverage_scope",
        "operational_status", "collection_readiness", "next_action_type",
        "cost_posture", "storage_posture", "world_state_facts", "db_series",
        "db_observations", "feed_rows", "source_records_with_raw", "blockers",
    ]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in matrix.get("sources") or []:
        flat = dict(row)
        flat["blockers"] = " | ".join(str(b) for b in row.get("blockers") or [])
        writer.writerow(flat)
    return out.getvalue()


def _source_ids_for_spec(conn: sqlite3.Connection, spec: DataSourceSpec) -> list[str]:
    """Best-effort map from registry source to concrete source ids already in SQLite."""
    from engine.feeds import ingest

    feeds = SOURCE_FEED_MAP.get(
        spec.id,
        (spec.id,) if spec.id in ingest.FEED_META else (),
    )
    urls = sorted(
        {
            *[ingest.FEED_META[f]["url"] for f in feeds if f in ingest.FEED_META],
            *SOURCE_URL_MAP.get(spec.id, ()),
        }
    )
    ids: set[str] = set()
    if feeds:
        placeholders = ",".join("?" for _ in feeds)
        try:
            for row in conn.execute(
                f"""
                SELECT DISTINCT source_id
                FROM series
                WHERE provider IN ({placeholders})
                  AND source_id IS NOT NULL
                  AND length(source_id)>0
                """,
                list(feeds),
            ):
                ids.add(str(row["source_id"]))
        except sqlite3.Error:
            pass
    if urls:
        placeholders = ",".join("?" for _ in urls)
        try:
            for row in conn.execute(
                f"SELECT id FROM sources WHERE url IN ({placeholders})",
                urls,
            ):
                ids.add(str(row["id"]))
        except sqlite3.Error:
            pass
    return sorted(ids)


def _fact_time_stats_for_sources(conn: sqlite3.Connection, source_ids: list[str]) -> dict[str, Any]:
    if not source_ids:
        return {
            "facts": 0,
            "predicates": 0,
            "sources": 0,
            "content_hashes": 0,
            "facts_with_raw_doc": 0,
            "event_start": None,
            "event_end": None,
            "published_start": None,
            "published_end": None,
            "observed_start": None,
            "observed_end": None,
        }
    placeholders = ",".join("?" for _ in source_ids)
    try:
        row = conn.execute(
            f"""
            SELECT
                count(*) AS facts,
                count(DISTINCT predicate) AS predicates,
                count(DISTINCT f.source_id) AS sources,
                count(DISTINCT f.content_hash) AS content_hashes,
                count(rd.content_hash) AS facts_with_raw_doc,
                min(substr(event_time,1,10)) AS event_start,
                max(substr(event_time,1,10)) AS event_end,
                min(substr(published_at,1,10)) AS published_start,
                max(substr(published_at,1,10)) AS published_end,
                min(substr(observed_at,1,10)) AS observed_start,
                max(substr(observed_at,1,10)) AS observed_end
            FROM world_state_facts f
            LEFT JOIN raw_docs rd ON rd.content_hash=f.content_hash
            WHERE f.source_id IN ({placeholders})
              AND COALESCE(f.status,'active')='active'
            """,
            source_ids,
        ).fetchone()
    except sqlite3.Error:
        row = None
    if not row:
        return {
            "facts": 0,
            "predicates": 0,
            "sources": 0,
            "content_hashes": 0,
            "facts_with_raw_doc": 0,
            "event_start": None,
            "event_end": None,
            "published_start": None,
            "published_end": None,
            "observed_start": None,
            "observed_end": None,
        }
    return {
        "facts": int(row["facts"] or 0),
        "predicates": int(row["predicates"] or 0),
        "sources": int(row["sources"] or 0),
        "content_hashes": int(row["content_hashes"] or 0),
        "facts_with_raw_doc": int(row["facts_with_raw_doc"] or 0),
        "event_start": row["event_start"],
        "event_end": row["event_end"],
        "published_start": row["published_start"],
        "published_end": row["published_end"],
        "observed_start": row["observed_start"],
        "observed_end": row["observed_end"],
    }


def _paper_stats_for_providers(conn: sqlite3.Connection, providers: tuple[str, ...]) -> dict[str, Any]:
    if not providers:
        return {
            "papers": 0,
            "papers_with_hash": 0,
            "published_start": None,
            "published_end": None,
            "fetched_start": None,
            "fetched_end": None,
            "primary_categories": 0,
        }
    placeholders = ",".join("?" for _ in providers)
    try:
        row = conn.execute(
            f"""
            SELECT
                count(*) AS papers,
                count(CASE WHEN content_hash IS NOT NULL AND length(content_hash)>0 THEN 1 END) AS papers_with_hash,
                min(substr(published,1,10)) AS published_start,
                max(substr(published,1,10)) AS published_end,
                min(substr(fetched_at,1,10)) AS fetched_start,
                max(substr(fetched_at,1,10)) AS fetched_end,
                count(DISTINCT primary_category) AS primary_categories
            FROM papers
            WHERE provider IN ({placeholders})
            """,
            list(providers),
        ).fetchone()
    except sqlite3.Error:
        row = None
    if not row:
        return {
            "papers": 0,
            "papers_with_hash": 0,
            "published_start": None,
            "published_end": None,
            "fetched_start": None,
            "fetched_end": None,
            "primary_categories": 0,
        }
    return {
        "papers": int(row["papers"] or 0),
        "papers_with_hash": int(row["papers_with_hash"] or 0),
        "published_start": row["published_start"],
        "published_end": row["published_end"],
        "fetched_start": row["fetched_start"],
        "fetched_end": row["fetched_end"],
        "primary_categories": int(row["primary_categories"] or 0),
    }


def _time_query_status(row: dict[str, Any], paper_stats: dict[str, Any]) -> str:
    if int(row.get("world_state_facts") or 0) > 0:
        return "as_of_world_state"
    if int(row.get("db_observations") or 0) > 0:
        return "dated_series_only"
    if int(paper_stats.get("papers") or 0) > 0:
        return "paper_metadata_timeline"
    if int(row.get("feed_rows") or 0) > 0:
        return "collected_feed_only"
    return "planned_or_blocked"


def _llm_query_status(row: dict[str, Any], paper_stats: dict[str, Any]) -> str:
    if int(row.get("world_state_facts") or 0) > 0:
        return "state_pack_ready"
    if int(paper_stats.get("papers") or 0) > 0:
        if int(paper_stats.get("papers_with_hash") or 0) > 0:
            return "metadata_hashes_ready_for_extraction"
        return "metadata_only_needs_extraction"
    if int(row.get("db_observations") or 0) > 0:
        return "series_only_needs_fact_bridge"
    if int(row.get("feed_rows") or 0) > 0:
        return "feed_only_needs_ingest_or_extraction"
    return "not_ready"


def _research_next_policy(row: dict[str, Any]) -> str:
    cost_posture = str(row.get("cost_posture") or "")
    storage_posture = str(row.get("storage_posture") or "")
    next_action = str(row.get("next_action_type") or "")
    cost = str(row.get("cost") or "").lower()
    access = str(row.get("access") or "").lower()
    if cost_posture == "paid_approval_required" or next_action == "needs_spend_approval":
        return "processing_approval_required"
    if next_action == "needs_key_or_visibility_fix":
        return "key_or_terms_required"
    if "athena" in cost or "bigquery" in cost or "bigquery" in access:
        return "storage_ok_processing_approval_required"
    if storage_posture == "object_storage_or_cloud_first":
        return "storage_ok_keep_bulk_off_laptop"
    if next_action.startswith("safe_local_"):
        return "safe_local_preflight_then_refresh"
    return "local_read_or_optional_refresh"


def research_layer_status(
    conn: sqlite3.Connection,
    *,
    feed_dir: Path | None = None,
    repo_root: Path | None = None,
    stale_hours: float = DEFAULT_STALE_HOURS,
    max_local_refresh_mb: float = DEFAULT_MAX_LOCAL_REFRESH_MB,
) -> dict[str, Any]:
    """Read-only status of the research layer as a dated machine/LLM substrate."""
    base = data_status(
        conn,
        feed_dir=feed_dir,
        repo_root=repo_root,
        stale_hours=stale_hours,
        max_local_refresh_mb=max_local_refresh_mb,
    )
    matrix = source_matrix(base)
    base_by_id = {row["id"]: row for row in base.get("sources") or []}
    spec_by_id = {spec.id: spec for spec in DATA_SOURCES}
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    for matrix_row in matrix.get("sources") or []:
        if matrix_row.get("layer") != RESEARCH_LAYER:
            continue
        sid = str(matrix_row["id"])
        spec = spec_by_id.get(sid)
        feeds = SOURCE_FEED_MAP.get(sid, ())
        paper_stats = _paper_stats_for_providers(conn, feeds)
        source_ids = _source_ids_for_spec(conn, spec) if spec else []
        timeline = _fact_time_stats_for_sources(conn, source_ids)
        data_row = base_by_id.get(sid, {})
        row = {
            **matrix_row,
            "feeds": list(data_row.get("feeds") or feeds),
            "time_query_status": _time_query_status(matrix_row, paper_stats),
            "llm_query_status": _llm_query_status(matrix_row, paper_stats),
            "next_policy": _research_next_policy(matrix_row),
            "paper_stats": paper_stats,
            "fact_timeline": timeline,
            "source_ids": source_ids[:12],
            "source_ids_total": len(source_ids),
        }
        rows.append(row)
        for blocker in row.get("blockers") or []:
            if blocker not in blockers:
                blockers.append(str(blocker))

    by_status: dict[str, int] = {}
    by_llm: dict[str, int] = {}
    by_policy: dict[str, int] = {}
    by_coverage: dict[str, int] = {}
    for row in rows:
        by_status[row["time_query_status"]] = by_status.get(row["time_query_status"], 0) + 1
        by_llm[row["llm_query_status"]] = by_llm.get(row["llm_query_status"], 0) + 1
        by_policy[row["next_policy"]] = by_policy.get(row["next_policy"], 0) + 1
        by_coverage[row["coverage_scope"]] = by_coverage.get(row["coverage_scope"], 0) + 1

    if rows and not any(row["llm_query_status"] == "state_pack_ready" for row in rows):
        blockers.append("research facts are not yet promoted enough for state_pack-ready LLM context")
    if any(row["id"] == "semantic_scholar" for row in rows):
        blockers.append("Semantic Scholar broad S2AG use needs API key/dataset access before full-scale extraction")
    blockers.append("LLM/full-text extraction is a processing step and needs explicit approval before spend")

    return {
        "summary": {
            "sources": len(rows),
            "global_sources": sum(1 for row in rows if row["coverage_scope"] == "global"),
            "queryable_world_state_sources": sum(
                1 for row in rows if row.get("operational_status") == "queryable_world_state"
            ),
            "state_pack_ready_sources": sum(1 for row in rows if row["llm_query_status"] == "state_pack_ready"),
            "time_indexed_sources": sum(
                1 for row in rows if row["time_query_status"] != "planned_or_blocked"
            ),
            "facts": sum(int(row.get("world_state_facts") or 0) for row in rows),
            "series": sum(int(row.get("db_series") or 0) for row in rows),
            "observations": sum(int(row.get("db_observations") or 0) for row in rows),
            "papers": sum(int(row["paper_stats"].get("papers") or 0) for row in rows),
            "papers_with_hash": sum(int(row["paper_stats"].get("papers_with_hash") or 0) for row in rows),
            "feed_rows": sum(int(row.get("feed_rows") or 0) for row in rows),
            "source_records": sum(int(row.get("source_records") or 0) for row in rows),
            "source_records_with_raw": sum(int(row.get("source_records_with_raw") or 0) for row in rows),
            "source_records_legacy_raw_gap": sum(
                int(row.get("source_records_legacy_raw_gap") or 0) for row in rows
            ),
            "by_time_query_status": dict(sorted(by_status.items())),
            "by_llm_query_status": dict(sorted(by_llm.items())),
            "by_next_policy": dict(sorted(by_policy.items())),
            "by_coverage_scope": dict(sorted(by_coverage.items())),
            "processing_policy": "storage/offload ok; paid scans, LLM extraction, Athena/BigQuery joins need explicit approval",
        },
        "disk": base.get("disk", {}),
        "offload": base.get("offload", {}),
        "cost_ledger": base.get("cost_ledger", {}),
        "query_interfaces": list(RESEARCH_QUERY_INTERFACES),
        "blockers": blockers,
        "sources": rows,
    }


def format_research_layer_status(status: dict[str, Any], *, limit: int | None = 20) -> str:
    summary = status.get("summary") or {}
    disk = status.get("disk") or {}
    offload = status.get("offload") or {}
    costs = status.get("cost_ledger") or {}
    rows = list(status.get("sources") or [])
    shown = rows if limit is None else rows[:limit]
    lines = [
        "Research layer status (read-only)",
        f"sources={summary.get('sources', 0)} global={summary.get('global_sources', 0)} "
        f"time_indexed={summary.get('time_indexed_sources', 0)} "
        f"state_pack_ready={summary.get('state_pack_ready_sources', 0)} "
        f"facts={_short_int(int(summary.get('facts') or 0))} "
        f"papers={_short_int(int(summary.get('papers') or 0))} "
        f"series={_short_int(int(summary.get('series') or 0))} "
        f"obs={_short_int(int(summary.get('observations') or 0))}",
        f"raw_sources={_short_int(int(summary.get('source_records_with_raw') or 0))}/"
        f"{_short_int(int(summary.get('source_records') or 0))} "
        f"legacy_raw_gaps={_short_int(int(summary.get('source_records_legacy_raw_gap') or 0))} "
        f"paper_hashes={_short_int(int(summary.get('papers_with_hash') or 0))}",
        f"disk_free={float(disk.get('free_gb', 0)):.1f}GiB "
        f"offloaded={float(offload.get('recorded_gib', 0)):.2f}GiB "
        f"storage_est=${float(offload.get('estimated_storage_usd_month', 0)):.2f}/mo "
        f"ledger_actual=${float(costs.get('actual_usd', 0)):.2f}",
        "policy: " + str(summary.get("processing_policy") or ""),
        "time status: " + ", ".join(f"{k}={v}" for k, v in summary.get("by_time_query_status", {}).items()),
        "LLM status: " + ", ".join(f"{k}={v}" for k, v in summary.get("by_llm_query_status", {}).items()),
        "next policy: " + ", ".join(f"{k}={v}" for k, v in summary.get("by_next_policy", {}).items()),
        "",
        "machine interfaces:",
    ]
    for interface in status.get("query_interfaces") or []:
        lines.append(f"- {interface['name']}: {interface['command']} | {interface['cost']}")
    if status.get("blockers"):
        lines.extend(["", "blockers:"])
        for blocker in status["blockers"][:8]:
            lines.append(f"- {blocker}")
    if shown:
        lines.extend(["", "sources:"])
    for row in shown:
        timeline = row.get("fact_timeline") or {}
        paper = row.get("paper_stats") or {}
        date_bits: list[str] = []
        if timeline.get("published_start") or timeline.get("published_end"):
            date_bits.append(f"facts_pub={timeline.get('published_start')}..{timeline.get('published_end')}")
        if paper.get("published_start") or paper.get("published_end"):
            date_bits.append(f"papers_pub={paper.get('published_start')}..{paper.get('published_end')}")
        dates = " " + " ".join(date_bits) if date_bits else ""
        lines.append(
            f"- P{row['priority']} {row['id']} [{row['coverage_scope']}] "
            f"time={row['time_query_status']} llm={row['llm_query_status']} "
            f"next={row['next_policy']} facts={_short_int(int(row.get('world_state_facts') or 0))} "
            f"papers={_short_int(int(paper.get('papers') or 0))}{dates}"
        )
        if row.get("blockers"):
            lines.append("  blocker: " + str(row["blockers"][0]))
    if limit is not None and len(rows) > len(shown):
        lines.append(f"- ... {len(rows) - len(shown)} more")
    return "\n".join(lines)


def research_layer_status_csv(status: dict[str, Any]) -> str:
    import csv
    import io

    fields = [
        "id", "name", "priority", "coverage_scope", "operational_status",
        "time_query_status", "llm_query_status", "next_policy", "cost_posture",
        "storage_posture", "world_state_facts", "db_series", "db_observations",
        "feed_rows", "source_records", "source_records_with_raw", "papers",
        "papers_with_hash", "paper_published_start", "paper_published_end",
        "fact_published_start", "fact_published_end", "blockers",
    ]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in status.get("sources") or []:
        paper = row.get("paper_stats") or {}
        timeline = row.get("fact_timeline") or {}
        flat = {
            **row,
            "papers": int(paper.get("papers") or 0),
            "papers_with_hash": int(paper.get("papers_with_hash") or 0),
            "paper_published_start": paper.get("published_start"),
            "paper_published_end": paper.get("published_end"),
            "fact_published_start": timeline.get("published_start"),
            "fact_published_end": timeline.get("published_end"),
            "blockers": " | ".join(str(b) for b in row.get("blockers") or []),
        }
        writer.writerow(flat)
    return out.getvalue()


def _query_dicts(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    except sqlite3.Error:
        return []


def _research_source_ids_from_status(status: dict[str, Any]) -> list[str]:
    ids: set[str] = set()
    for row in status.get("sources") or []:
        ids.update(str(source_id) for source_id in row.get("source_ids") or [] if source_id)
    return sorted(ids)


def _research_source_ids(conn: sqlite3.Connection) -> list[str]:
    ids: set[str] = set()
    for spec in DATA_SOURCES:
        if spec.layer != RESEARCH_LAYER:
            continue
        ids.update(_source_ids_for_spec(conn, spec))
    return sorted(ids)


def _research_fact_profile(
    conn: sqlite3.Connection,
    source_ids: list[str],
    *,
    limit: int,
) -> dict[str, Any]:
    if not source_ids:
        return {
            "source_ids": [],
            "summary": {
                "facts": 0,
                "sources": 0,
                "predicates": 0,
                "extractors": 0,
                "content_hashes": 0,
                "facts_with_raw_doc": 0,
                "published_start": None,
                "published_end": None,
                "observed_start": None,
                "observed_end": None,
                "event_start": None,
                "event_end": None,
            },
            "by_predicate": [],
            "by_source": [],
            "by_year": [],
            "by_extractor": [],
        }
    placeholders = ",".join("?" for _ in source_ids)
    summary = _query_dicts(
        conn,
        f"""
        SELECT
            count(*) AS facts,
            count(DISTINCT f.source_id) AS sources,
            count(DISTINCT predicate) AS predicates,
            count(DISTINCT extractor) AS extractors,
            count(DISTINCT f.content_hash) AS content_hashes,
            count(rd.content_hash) AS facts_with_raw_doc,
            min(substr(published_at,1,10)) AS published_start,
            max(substr(published_at,1,10)) AS published_end,
            min(substr(observed_at,1,10)) AS observed_start,
            max(substr(observed_at,1,10)) AS observed_end,
            min(substr(event_time,1,10)) AS event_start,
            max(substr(event_time,1,10)) AS event_end
        FROM world_state_facts f
        LEFT JOIN raw_docs rd ON rd.content_hash=f.content_hash
        WHERE f.source_id IN ({placeholders})
          AND COALESCE(f.status,'active')='active'
        """,
        tuple(source_ids),
    )
    by_predicate = _query_dicts(
        conn,
        f"""
        SELECT predicate, count(*) AS facts,
               min(substr(published_at,1,10)) AS first_published_at,
               max(substr(published_at,1,10)) AS latest_published_at
        FROM world_state_facts
        WHERE source_id IN ({placeholders})
          AND COALESCE(status,'active')='active'
        GROUP BY predicate
        ORDER BY facts DESC, predicate
        LIMIT ?
        """,
        (*source_ids, int(limit)),
    )
    by_source = _query_dicts(
        conn,
        f"""
        SELECT
            f.source_id,
            COALESCE(s.title, f.source_id, 'unknown') AS title,
            COALESCE(s.url, '') AS url,
            count(*) AS facts,
            count(DISTINCT f.predicate) AS predicates,
            count(rd.content_hash) AS facts_with_raw_doc,
            min(substr(f.published_at,1,10)) AS first_published_at,
            max(substr(f.published_at,1,10)) AS latest_published_at
        FROM world_state_facts f
        LEFT JOIN sources s ON s.id=f.source_id
        LEFT JOIN raw_docs rd ON rd.content_hash=f.content_hash
        WHERE f.source_id IN ({placeholders})
          AND COALESCE(f.status,'active')='active'
        GROUP BY f.source_id, COALESCE(s.title, f.source_id, 'unknown'), COALESCE(s.url, '')
        ORDER BY facts DESC, title
        LIMIT ?
        """,
        (*source_ids, int(limit)),
    )
    by_year = _query_dicts(
        conn,
        f"""
        SELECT
            COALESCE(
                NULLIF(substr(published_at,1,4), ''),
                NULLIF(substr(observed_at,1,4), ''),
                NULLIF(substr(event_time,1,4), ''),
                'unknown'
            ) AS year,
            count(*) AS facts,
            count(DISTINCT source_id) AS sources,
            count(DISTINCT predicate) AS predicates
        FROM world_state_facts
        WHERE source_id IN ({placeholders})
          AND COALESCE(status,'active')='active'
        GROUP BY year
        ORDER BY year
        """,
        tuple(source_ids),
    )
    by_extractor = _query_dicts(
        conn,
        f"""
        SELECT extractor, count(*) AS facts,
               count(DISTINCT predicate) AS predicates,
               count(DISTINCT source_id) AS sources
        FROM world_state_facts
        WHERE source_id IN ({placeholders})
          AND COALESCE(status,'active')='active'
        GROUP BY extractor
        ORDER BY facts DESC, extractor
        LIMIT ?
        """,
        (*source_ids, int(limit)),
    )
    return {
        "source_ids": source_ids,
        "summary": summary[0] if summary else {},
        "by_predicate": by_predicate,
        "by_source": by_source,
        "by_year": by_year,
        "by_extractor": by_extractor,
    }


def _research_paper_profile(
    conn: sqlite3.Connection,
    *,
    limit: int,
    include_groups: bool,
) -> dict[str, Any]:
    summary = _query_dicts(
        conn,
        """
        SELECT
            count(*) AS papers,
            count(DISTINCT provider) AS providers,
            count(DISTINCT primary_category) AS primary_categories,
            count(CASE WHEN content_hash IS NOT NULL AND length(content_hash)>0 THEN 1 END) AS papers_with_hash,
            min(substr(published,1,10)) AS published_start,
            max(substr(published,1,10)) AS published_end,
            min(substr(fetched_at,1,10)) AS fetched_start,
            max(substr(fetched_at,1,10)) AS fetched_end
        FROM papers
        """,
    )
    by_provider = _query_dicts(
        conn,
        """
        SELECT
            provider,
            count(*) AS papers,
            count(CASE WHEN content_hash IS NOT NULL AND length(content_hash)>0 THEN 1 END) AS papers_with_hash,
            count(DISTINCT primary_category) AS primary_categories,
            min(substr(published,1,10)) AS published_start,
            max(substr(published,1,10)) AS published_end,
            min(substr(fetched_at,1,10)) AS fetched_start,
            max(substr(fetched_at,1,10)) AS fetched_end
        FROM papers
        GROUP BY provider
        ORDER BY papers DESC, provider
        LIMIT ?
        """,
        (int(limit),),
    )
    by_year: list[dict[str, Any]] = []
    by_category: list[dict[str, Any]] = []
    if include_groups:
        by_year = _query_dicts(
            conn,
            """
            SELECT substr(published,1,4) AS year,
                   count(*) AS papers,
                   count(DISTINCT provider) AS providers,
                   count(DISTINCT primary_category) AS primary_categories
            FROM papers
            WHERE published IS NOT NULL AND length(published) >= 4
            GROUP BY substr(published,1,4)
            ORDER BY year
            """,
        )
        by_category = _query_dicts(
            conn,
            """
            SELECT
                COALESCE(NULLIF(primary_category,''), 'unknown') AS primary_category,
                count(*) AS papers,
                count(DISTINCT provider) AS providers,
                min(substr(published,1,10)) AS published_start,
                max(substr(published,1,10)) AS published_end
            FROM papers
            GROUP BY COALESCE(NULLIF(primary_category,''), 'unknown')
            ORDER BY papers DESC, primary_category
            LIMIT ?
            """,
            (int(limit),),
        )
    return {
        "summary": summary[0] if summary else {},
        "by_provider": by_provider,
        "by_year": by_year,
        "by_primary_category": by_category,
        "groups_complete": bool(include_groups),
        "groups_note": "" if include_groups else "exact paper year/category histograms skipped; rerun with full_paper_groups for the heavier local scan",
    }


def _research_paper_profile_from_status(status: dict[str, Any], *, limit: int) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in status.get("sources") or []:
        stats = row.get("paper_stats") or {}
        papers = int(stats.get("papers") or 0)
        if papers <= 0:
            continue
        feeds = [str(feed) for feed in row.get("feeds") or [] if feed]
        provider = feeds[0] if len(feeds) == 1 else str(row.get("id") or "research")
        rows.append({
            "provider": provider,
            "source_id": row.get("id"),
            "papers": papers,
            "papers_with_hash": int(stats.get("papers_with_hash") or 0),
            "primary_categories": int(stats.get("primary_categories") or 0),
            "published_start": stats.get("published_start"),
            "published_end": stats.get("published_end"),
            "fetched_start": stats.get("fetched_start"),
            "fetched_end": stats.get("fetched_end"),
        })
    rows.sort(key=lambda item: (-int(item.get("papers") or 0), str(item.get("provider") or "")))
    published_starts = [str(row["published_start"]) for row in rows if row.get("published_start")]
    published_ends = [str(row["published_end"]) for row in rows if row.get("published_end")]
    fetched_starts = [str(row["fetched_start"]) for row in rows if row.get("fetched_start")]
    fetched_ends = [str(row["fetched_end"]) for row in rows if row.get("fetched_end")]
    return {
        "summary": {
            "papers": sum(int(row.get("papers") or 0) for row in rows),
            "providers": len(rows),
            "primary_categories": sum(int(row.get("primary_categories") or 0) for row in rows),
            "papers_with_hash": sum(int(row.get("papers_with_hash") or 0) for row in rows),
            "published_start": min(published_starts) if published_starts else None,
            "published_end": max(published_ends) if published_ends else None,
            "fetched_start": min(fetched_starts) if fetched_starts else None,
            "fetched_end": max(fetched_ends) if fetched_ends else None,
        },
        "by_provider": rows[:limit],
        "by_year": [],
        "by_primary_category": [],
        "groups_complete": False,
        "groups_note": "using status-derived provider stats; rerun with full_paper_groups for exact paper year/category histograms",
    }


def _research_paper_profile_fast(conn: sqlite3.Connection, *, limit: int) -> dict[str, Any]:
    """Fast default paper profile.

    Avoid exact category/hash/date histograms over the full paper table unless the caller asks for
    the heavier profile. Provider counts are enough for the default health/readiness path.
    """
    by_provider = _query_dicts(
        conn,
        """
        SELECT provider, count(*) AS papers
        FROM papers
        GROUP BY provider
        ORDER BY papers DESC, provider
        LIMIT ?
        """,
        (int(limit),),
    )
    total = _table_count(conn, "papers")
    rows = [
        {
            "provider": row.get("provider"),
            "papers": int(row.get("papers") or 0),
            "papers_with_hash": None,
            "primary_categories": None,
            "published_start": None,
            "published_end": None,
            "fetched_start": None,
            "fetched_end": None,
        }
        for row in by_provider
    ]
    return {
        "summary": {
            "papers": total,
            "providers": len(rows),
            "primary_categories": None,
            "papers_with_hash": None,
            "published_start": None,
            "published_end": None,
            "fetched_start": None,
            "fetched_end": None,
        },
        "by_provider": rows,
        "by_year": [],
        "by_primary_category": [],
        "groups_complete": False,
        "groups_note": "fast provider counts only; rerun with full_paper_groups for exact paper hashes, dates, years, and categories",
    }


def _source_record_raw_stats(conn: sqlite3.Connection, source_ids: list[str]) -> dict[str, int]:
    if not source_ids:
        return {
            "source_records": 0,
            "source_records_with_raw": 0,
            "source_records_legacy_raw_gap": 0,
        }
    placeholders = ",".join("?" for _ in source_ids)
    row = _query_dicts(
        conn,
        f"""
        SELECT
            count(*) AS source_records,
            count(DISTINCT CASE WHEN rd.content_hash IS NOT NULL THEN s.id END) AS source_records_with_raw,
            count(DISTINCT CASE
                WHEN COALESCE(s.raw_provenance_status, '') IN ('legacy_hash_no_raw_doc','legacy_no_content_hash')
                THEN s.id
            END) AS source_records_legacy_raw_gap
        FROM sources s
        LEFT JOIN raw_docs rd ON rd.content_hash=s.content_hash
        WHERE s.id IN ({placeholders})
        """,
        tuple(source_ids),
    )
    if not row:
        return {
            "source_records": 0,
            "source_records_with_raw": 0,
            "source_records_legacy_raw_gap": 0,
        }
    return {
        "source_records": int(row[0].get("source_records") or 0),
        "source_records_with_raw": int(row[0].get("source_records_with_raw") or 0),
        "source_records_legacy_raw_gap": int(row[0].get("source_records_legacy_raw_gap") or 0),
    }


def _research_source_status_fast(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in DATA_SOURCES:
        if spec.layer != RESEARCH_LAYER:
            continue
        source_ids = _source_ids_for_spec(conn, spec)
        facts = _fact_time_stats_for_sources(conn, source_ids)
        raw = _source_record_raw_stats(conn, source_ids)
        fact_count = int(facts.get("facts") or 0)
        rows.append({
            "id": spec.id,
            "name": spec.name,
            "time_query_status": "as_of_world_state" if fact_count else "planned_or_blocked",
            "llm_query_status": "state_pack_ready" if fact_count else "not_ready",
            "next_policy": _research_next_policy({
                "cost": spec.cost,
                "access": spec.access,
                "cost_posture": "free_or_keyless" if "$0" in spec.cost or "free" in spec.cost else "unknown_or_mixed",
                "storage_posture": "object_storage_or_cloud_first" if any(
                    token in spec.storage.lower() for token in ("object storage", "s3", "parquet")
                ) else "derived_sqlite_or_feed_jsonl",
                "next_action_type": "local_read_or_optional_refresh",
            }),
            "world_state_facts": fact_count,
            "db_observations": 0,
            "source_records": raw["source_records"],
            "source_records_with_raw": raw["source_records_with_raw"],
            "source_records_legacy_raw_gap": raw["source_records_legacy_raw_gap"],
            "source_ids": source_ids[:12],
            "source_ids_total": len(source_ids),
            "blockers": [
                "Semantic Scholar remains manifest/limited until API key or dataset access is approved"
            ] if spec.id == "semantic_scholar" else [],
        })
    return rows


def _research_status_summary_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "sources": len(rows),
        "state_pack_ready_sources": sum(1 for row in rows if row.get("llm_query_status") == "state_pack_ready"),
        "time_indexed_sources": sum(1 for row in rows if row.get("time_query_status") != "planned_or_blocked"),
        "source_records": sum(int(row.get("source_records") or 0) for row in rows),
        "source_records_with_raw": sum(int(row.get("source_records_with_raw") or 0) for row in rows),
        "source_records_legacy_raw_gap": sum(int(row.get("source_records_legacy_raw_gap") or 0) for row in rows),
        "processing_policy": "storage/offload ok; paid scans, LLM extraction, Athena/BigQuery joins need explicit approval",
    }


def _research_profile_gaps(status: dict[str, Any], fact_profile: dict[str, Any], paper_profile: dict[str, Any]) -> list[str]:
    summary = status.get("summary") or {}
    papers = paper_profile.get("summary") or {}
    facts = fact_profile.get("summary") or {}
    gaps: list[str] = []
    source_records = int(summary.get("source_records") or 0)
    source_records_with_raw = int(summary.get("source_records_with_raw") or 0)
    legacy_raw = int(summary.get("source_records_legacy_raw_gap") or 0)
    paper_count = int(papers.get("papers") or 0)
    paper_hashes_raw = papers.get("papers_with_hash")
    facts_count = int(facts.get("facts") or 0)
    facts_with_raw = int(facts.get("facts_with_raw_doc") or 0)
    if source_records and source_records_with_raw < source_records:
        gaps.append(
            f"research source raw-byte coverage is {source_records_with_raw}/{source_records}; "
            f"{legacy_raw} legacy source records are explicitly not exact raw-doc provenance"
        )
    if paper_count and paper_hashes_raw is None:
        gaps.append("paper metadata hash coverage was not counted in fast profile mode")
    elif paper_count:
        paper_hashes = int(paper_hashes_raw or 0)
        if paper_hashes < paper_count:
            gaps.append(f"paper metadata hash coverage is {paper_hashes}/{paper_count}")
    if facts_count and facts_with_raw < facts_count:
        gaps.append(f"research fact exact raw-doc coverage is {facts_with_raw}/{facts_count}")
    if any(row.get("id") == "semantic_scholar" for row in status.get("sources") or []):
        gaps.append("Semantic Scholar remains manifest/limited until API key or dataset access is approved")
    gaps.append("LLM/full-text extraction, OCR, translation, and cloud joins remain processing steps requiring explicit approval")
    return gaps


def research_provenance_gaps(
    conn: sqlite3.Connection,
    *,
    limit: int = 25,
) -> dict[str, Any]:
    """Read-only research raw-byte provenance triage."""
    source_ids = _research_source_ids(conn)
    if not source_ids:
        return {
            "ok": True,
            "profile_version": "research_provenance_v1",
            "summary": {
                "research_source_ids": 0,
                "source_records": 0,
                "source_records_with_content_hash": 0,
                "source_records_with_raw_doc": 0,
                "source_records_legacy_raw_gap": 0,
                "source_records_unclassified": 0,
                "facts": 0,
                "facts_with_content_hash": 0,
                "facts_with_raw_doc": 0,
                "facts_missing_content_hash": 0,
                "facts_hash_without_raw_doc": 0,
                "exact_fact_raw_doc_coverage_pct": 0.0,
                "exact_source_raw_doc_coverage_pct": 0.0,
                "policy": "read-only; no refetch, no mutation, no paid processing",
            },
            "source_status": [],
            "fact_gaps_by_source": [],
            "fact_gaps_by_predicate": [],
            "actions": [],
        }
    placeholders = ",".join("?" for _ in source_ids)
    source_summary = _query_dicts(
        conn,
        f"""
        SELECT
            count(*) AS source_records,
            count(CASE WHEN s.content_hash IS NOT NULL AND length(s.content_hash)>0 THEN 1 END)
              AS source_records_with_content_hash,
            count(CASE WHEN rd.content_hash IS NOT NULL THEN 1 END) AS source_records_with_raw_doc,
            count(CASE
                WHEN COALESCE(s.raw_provenance_status, '') IN ('legacy_hash_no_raw_doc','legacy_no_content_hash')
                THEN 1
            END) AS source_records_legacy_raw_gap,
            count(CASE WHEN COALESCE(s.raw_provenance_status, 'unknown')='unknown' THEN 1 END)
              AS source_records_unclassified
        FROM sources s
        LEFT JOIN raw_docs rd ON rd.content_hash=s.content_hash
        WHERE s.id IN ({placeholders})
        """,
        tuple(source_ids),
    )
    fact_summary = _query_dicts(
        conn,
        f"""
        SELECT
            count(*) AS facts,
            count(CASE WHEN f.content_hash IS NOT NULL AND length(f.content_hash)>0 THEN 1 END)
              AS facts_with_content_hash,
            count(CASE WHEN rd.content_hash IS NOT NULL THEN 1 END) AS facts_with_raw_doc,
            count(CASE WHEN f.content_hash IS NULL OR length(f.content_hash)=0 THEN 1 END)
              AS facts_missing_content_hash,
            count(CASE
                WHEN f.content_hash IS NOT NULL AND length(f.content_hash)>0 AND rd.content_hash IS NULL THEN 1
            END) AS facts_hash_without_raw_doc
        FROM world_state_facts f
        LEFT JOIN raw_docs rd ON rd.content_hash=f.content_hash
        WHERE f.source_id IN ({placeholders})
          AND COALESCE(f.status,'active')='active'
        """,
        tuple(source_ids),
    )
    source_rows = _query_dicts(
        conn,
        f"""
        WITH fact_stats AS (
            SELECT
                f.source_id,
                count(*) AS facts,
                count(CASE WHEN f.content_hash IS NOT NULL AND length(f.content_hash)>0 THEN 1 END)
                  AS facts_with_content_hash,
                count(CASE WHEN rd.content_hash IS NOT NULL THEN 1 END) AS facts_with_raw_doc,
                count(CASE WHEN f.content_hash IS NULL OR length(f.content_hash)=0 THEN 1 END)
                  AS facts_missing_content_hash,
                count(CASE
                    WHEN f.content_hash IS NOT NULL AND length(f.content_hash)>0 AND rd.content_hash IS NULL THEN 1
                END) AS facts_hash_without_raw_doc
            FROM world_state_facts f
            LEFT JOIN raw_docs rd ON rd.content_hash=f.content_hash
            WHERE f.source_id IN ({placeholders})
              AND COALESCE(f.status,'active')='active'
            GROUP BY f.source_id
        )
        SELECT
            s.id AS source_id,
            COALESCE(s.title, s.id) AS title,
            COALESCE(s.url, '') AS url,
            s.content_hash,
            COALESCE(s.raw_provenance_status, 'unknown') AS raw_provenance_status,
            COALESCE(s.raw_provenance_reason, '') AS raw_provenance_reason,
            CASE WHEN rd.content_hash IS NOT NULL THEN 1 ELSE 0 END AS has_raw_doc,
            COALESCE(fs.facts, 0) AS facts,
            COALESCE(fs.facts_with_content_hash, 0) AS facts_with_content_hash,
            COALESCE(fs.facts_with_raw_doc, 0) AS facts_with_raw_doc,
            COALESCE(fs.facts_missing_content_hash, 0) AS facts_missing_content_hash,
            COALESCE(fs.facts_hash_without_raw_doc, 0) AS facts_hash_without_raw_doc
        FROM sources s
        LEFT JOIN raw_docs rd ON rd.content_hash=s.content_hash
        LEFT JOIN fact_stats fs ON fs.source_id=s.id
        WHERE s.id IN ({placeholders})
        ORDER BY
            (COALESCE(fs.facts, 0) - COALESCE(fs.facts_with_raw_doc, 0)) DESC,
            has_raw_doc ASC,
            source_id
        LIMIT ?
        """,
        (*source_ids, *source_ids, int(limit)),
    )
    predicate_rows = _query_dicts(
        conn,
        f"""
        SELECT
            f.predicate,
            count(*) AS facts_missing_raw,
            count(DISTINCT f.source_id) AS sources,
            min(substr(f.published_at,1,10)) AS first_published_at,
            max(substr(f.published_at,1,10)) AS latest_published_at
        FROM world_state_facts f
        LEFT JOIN raw_docs rd ON rd.content_hash=f.content_hash
        WHERE f.source_id IN ({placeholders})
          AND COALESCE(f.status,'active')='active'
          AND (f.content_hash IS NULL OR length(f.content_hash)=0 OR rd.content_hash IS NULL)
        GROUP BY f.predicate
        ORDER BY facts_missing_raw DESC, f.predicate
        LIMIT ?
        """,
        (*source_ids, int(limit)),
    )
    source_counts = source_summary[0] if source_summary else {}
    fact_counts = fact_summary[0] if fact_summary else {}
    sources_total = int(source_counts.get("source_records") or 0)
    facts_total = int(fact_counts.get("facts") or 0)
    source_exact = int(source_counts.get("source_records_with_raw_doc") or 0)
    fact_exact = int(fact_counts.get("facts_with_raw_doc") or 0)
    actions: list[str] = []
    if int(source_counts.get("source_records_unclassified") or 0):
        actions.append("classify unknown research source raw_provenance_status before trusting provenance metrics")
    if int(source_counts.get("source_records_legacy_raw_gap") or 0):
        actions.append("do not fake legacy raw docs; refetch only when bytes hash-match existing source content_hash")
    if int(fact_counts.get("facts_missing_content_hash") or 0):
        actions.append("future extractors must attach content_hash or explicit legacy/no-raw reason")
    if int(fact_counts.get("facts_hash_without_raw_doc") or 0):
        actions.append("restore/offload-linked raw bytes or rerun exact refetch before high-trust extraction")
    actions.append("new research collectors must flow through rawstore.put before derived facts are inserted")
    return {
        "ok": True,
        "profile_version": "research_provenance_v1",
        "summary": {
            "research_source_ids": len(source_ids),
            "source_records": sources_total,
            "source_records_with_content_hash": int(source_counts.get("source_records_with_content_hash") or 0),
            "source_records_with_raw_doc": source_exact,
            "source_records_legacy_raw_gap": int(source_counts.get("source_records_legacy_raw_gap") or 0),
            "source_records_unclassified": int(source_counts.get("source_records_unclassified") or 0),
            "facts": facts_total,
            "facts_with_content_hash": int(fact_counts.get("facts_with_content_hash") or 0),
            "facts_with_raw_doc": fact_exact,
            "facts_missing_content_hash": int(fact_counts.get("facts_missing_content_hash") or 0),
            "facts_hash_without_raw_doc": int(fact_counts.get("facts_hash_without_raw_doc") or 0),
            "exact_fact_raw_doc_coverage_pct": round((fact_exact / facts_total) * 100, 2) if facts_total else 0.0,
            "exact_source_raw_doc_coverage_pct": round((source_exact / sources_total) * 100, 2) if sources_total else 0.0,
            "policy": "read-only; no refetch, no mutation, no paid processing",
        },
        "source_status": source_rows,
        "fact_gaps_by_source": [
            row for row in source_rows
            if int(row.get("facts_missing_content_hash") or 0) or int(row.get("facts_hash_without_raw_doc") or 0)
        ],
        "fact_gaps_by_predicate": predicate_rows,
        "actions": actions,
    }


def format_research_provenance_gaps(report: dict[str, Any], *, limit: int | None = 20) -> str:
    summary = report.get("summary") or {}
    source_rows = list(report.get("fact_gaps_by_source") or [])
    predicate_rows = list(report.get("fact_gaps_by_predicate") or [])
    shown_sources = source_rows if limit is None else source_rows[:limit]
    shown_predicates = predicate_rows if limit is None else predicate_rows[:limit]
    lines = [
        "Research provenance gaps (read-only)",
        f"sources={summary.get('source_records_with_raw_doc', 0)}/{summary.get('source_records', 0)} exact_raw "
        f"({float(summary.get('exact_source_raw_doc_coverage_pct') or 0):.2f}%) "
        f"facts={summary.get('facts_with_raw_doc', 0)}/{summary.get('facts', 0)} exact_raw "
        f"({float(summary.get('exact_fact_raw_doc_coverage_pct') or 0):.2f}%)",
        f"source_hashes={summary.get('source_records_with_content_hash', 0)} "
        f"legacy_sources={summary.get('source_records_legacy_raw_gap', 0)} "
        f"unclassified_sources={summary.get('source_records_unclassified', 0)} "
        f"facts_missing_hash={summary.get('facts_missing_content_hash', 0)} "
        f"facts_hash_without_raw={summary.get('facts_hash_without_raw_doc', 0)}",
        "policy: " + str(summary.get("policy") or ""),
    ]
    if report.get("actions"):
        lines.extend(["", "actions:"])
        for action in list(report["actions"])[:6]:
            lines.append(f"- {action}")
    if shown_sources:
        lines.extend(["", "source gaps:"])
        for row in shown_sources:
            lines.append(
                f"- {row['source_id']}: facts={row['facts']} exact={row['facts_with_raw_doc']} "
                f"missing_hash={row['facts_missing_content_hash']} "
                f"hash_without_raw={row['facts_hash_without_raw_doc']} "
                f"source_raw={bool(row['has_raw_doc'])} status={row['raw_provenance_status']}"
            )
    if shown_predicates:
        lines.extend(["", "predicate gaps:"])
        for row in shown_predicates:
            lines.append(
                f"- {row['predicate']}: missing_raw={row['facts_missing_raw']} "
                f"sources={row['sources']} published={row.get('first_published_at')}..{row.get('latest_published_at')}"
            )
    return "\n".join(lines)


def research_coverage_profile(
    conn: sqlite3.Connection,
    *,
    limit: int = 25,
    include_paper_groups: bool = False,
    include_source_status: bool = False,
) -> dict[str, Any]:
    """Read-only research diversity, provenance, and time-coverage profile.

    This is intentionally a profile, not a collector: it scans only local SQLite tables and existing
    status metadata so LLMs/machines can understand what the research layer really covers.
    """
    if include_source_status:
        status = research_layer_status(conn)
        source_status = [
            {
                "id": row.get("id"),
                "name": row.get("name"),
                "time_query_status": row.get("time_query_status"),
                "llm_query_status": row.get("llm_query_status"),
                "next_policy": row.get("next_policy"),
                "world_state_facts": row.get("world_state_facts"),
                "db_observations": row.get("db_observations"),
                "source_records": row.get("source_records"),
                "source_records_with_raw": row.get("source_records_with_raw"),
                "source_records_legacy_raw_gap": row.get("source_records_legacy_raw_gap"),
                "blockers": row.get("blockers") or [],
            }
            for row in status.get("sources") or []
        ]
        status_summary = status.get("summary") or {}
        query_interfaces = status.get("query_interfaces") or list(RESEARCH_QUERY_INTERFACES)
        disk = status.get("disk") or _disk_status(_db.REPO_ROOT)
        offload = status.get("offload") or _offload_status(_db.REPO_ROOT)
        cost_ledger = status.get("cost_ledger") or _cost_status(conn)
    else:
        source_status = _research_source_status_fast(conn)
        status_summary = _research_status_summary_from_rows(source_status)
        status = {"sources": source_status, "summary": status_summary}
        query_interfaces = list(RESEARCH_QUERY_INTERFACES)
        disk = _disk_status(_db.REPO_ROOT)
        offload = _offload_status(_db.REPO_ROOT)
        cost_ledger = _cost_status(conn)
    research_source_ids = _research_source_ids(conn)
    fact_profile = _research_fact_profile(conn, research_source_ids, limit=limit)
    paper_profile = (
        _research_paper_profile(conn, limit=limit, include_groups=True)
        if include_paper_groups
        else _research_paper_profile_fast(conn, limit=limit)
    )
    profile = {
        "ok": True,
        "profile_version": "research_coverage_v1",
        "summary": {
            "research_sources": int(status_summary.get("sources") or 0),
            "state_pack_ready_sources": int(status_summary.get("state_pack_ready_sources") or 0),
            "time_indexed_sources": int(status_summary.get("time_indexed_sources") or 0),
            "papers": int((paper_profile.get("summary") or {}).get("papers") or 0),
            "paper_providers": int((paper_profile.get("summary") or {}).get("providers") or 0),
            "paper_primary_categories": (
                None
                if (paper_profile.get("summary") or {}).get("primary_categories") is None
                else int((paper_profile.get("summary") or {}).get("primary_categories") or 0)
            ),
            "papers_with_hash": (paper_profile.get("summary") or {}).get("papers_with_hash"),
            "research_facts": int((fact_profile.get("summary") or {}).get("facts") or 0),
            "research_fact_sources": int((fact_profile.get("summary") or {}).get("sources") or 0),
            "research_fact_predicates": int((fact_profile.get("summary") or {}).get("predicates") or 0),
            "research_fact_extractors": int((fact_profile.get("summary") or {}).get("extractors") or 0),
            "research_facts_with_raw_doc": int((fact_profile.get("summary") or {}).get("facts_with_raw_doc") or 0),
            "source_records": int(status_summary.get("source_records") or 0),
            "source_records_with_raw": int(status_summary.get("source_records_with_raw") or 0),
            "source_records_legacy_raw_gap": int(status_summary.get("source_records_legacy_raw_gap") or 0),
            "processing_policy": status_summary.get("processing_policy"),
            "paper_groups_complete": bool(paper_profile.get("groups_complete")),
            "source_status_complete": bool(include_source_status),
        },
        "papers": paper_profile,
        "facts": fact_profile,
        "source_status": source_status,
        "query_interfaces": query_interfaces,
        "gaps": _research_profile_gaps(status, fact_profile, paper_profile),
        "cost_ledger": cost_ledger,
        "disk": disk,
        "offload": offload,
    }
    return profile


def format_research_coverage_profile(profile: dict[str, Any], *, limit: int = 12) -> str:
    summary = profile.get("summary") or {}
    papers = profile.get("papers") or {}
    facts = profile.get("facts") or {}
    disk = profile.get("disk") or {}
    offload = profile.get("offload") or {}
    lines = [
        "Research coverage profile (read-only)",
    ]
    categories = summary.get("paper_primary_categories")
    category_text = "not_counted" if categories is None else str(categories)
    lines.extend([
        f"sources={summary.get('research_sources', 0)} "
        f"state_pack_ready={summary.get('state_pack_ready_sources', 0)} "
        f"facts={_short_int(int(summary.get('research_facts') or 0))} "
        f"predicates={_short_int(int(summary.get('research_fact_predicates') or 0))} "
        f"papers={_short_int(int(summary.get('papers') or 0))} "
        f"providers={summary.get('paper_providers', 0)} "
        f"categories={category_text}",
        f"raw: source_records={_short_int(int(summary.get('source_records_with_raw') or 0))}/"
        f"{_short_int(int(summary.get('source_records') or 0))} "
        f"facts_with_raw={_short_int(int(summary.get('research_facts_with_raw_doc') or 0))}/"
        f"{_short_int(int(summary.get('research_facts') or 0))} "
        f"paper_hashes={_short_int(int(summary.get('papers_with_hash') or 0))}",
        f"disk_free={float(disk.get('free_gb', 0)):.1f}GiB "
        f"offloaded={float(offload.get('recorded_gib', 0)):.2f}GiB",
        "policy: " + str(summary.get("processing_policy") or ""),
    ])
    if not summary.get("paper_groups_complete"):
        note = (papers.get("groups_note") or "").strip()
        if note:
            lines.append("paper groups: " + note)
    paper_hashes = summary.get("papers_with_hash")
    paper_hash_text = "not_counted" if paper_hashes is None else _short_int(int(paper_hashes or 0))
    lines[2] = (
        f"raw: source_records={_short_int(int(summary.get('source_records_with_raw') or 0))}/"
        f"{_short_int(int(summary.get('source_records') or 0))} "
        f"facts_with_raw={_short_int(int(summary.get('research_facts_with_raw_doc') or 0))}/"
        f"{_short_int(int(summary.get('research_facts') or 0))} "
        f"paper_hashes={paper_hash_text}"
    )
    paper_summary = papers.get("summary") or {}
    if paper_summary.get("published_start") or paper_summary.get("published_end"):
        lines.append(f"paper dates: {paper_summary.get('published_start')}..{paper_summary.get('published_end')}")
    fact_summary = facts.get("summary") or {}
    if fact_summary.get("published_start") or fact_summary.get("published_end"):
        lines.append(f"fact publication dates: {fact_summary.get('published_start')}..{fact_summary.get('published_end')}")
    provider_rows = list(papers.get("by_provider") or [])[:limit]
    if provider_rows:
        lines.extend(["", "paper providers:"])
        for row in provider_rows:
            cats = row.get("primary_categories")
            categories = "not_counted" if cats is None else str(cats)
            hashes = row.get("papers_with_hash")
            hash_text = "not_counted" if hashes is None else _short_int(int(hashes or 0))
            lines.append(
                f"- {row['provider']}: papers={_short_int(int(row.get('papers') or 0))} "
                f"hashes={hash_text} "
                f"categories={categories} "
                f"dates={row.get('published_start')}..{row.get('published_end')}"
            )
    category_rows = list(papers.get("by_primary_category") or [])[:limit]
    if category_rows:
        lines.extend(["", "top paper categories:"])
        for row in category_rows:
            lines.append(
                f"- {row['primary_category']}: papers={_short_int(int(row.get('papers') or 0))} "
                f"providers={row.get('providers', 0)} dates={row.get('published_start')}..{row.get('published_end')}"
            )
    predicate_rows = list(facts.get("by_predicate") or [])[:limit]
    if predicate_rows:
        lines.extend(["", "top fact predicates:"])
        for row in predicate_rows:
            lines.append(
                f"- {row['predicate']}: facts={_short_int(int(row.get('facts') or 0))} "
                f"published={row.get('first_published_at')}..{row.get('latest_published_at')}"
            )
    if profile.get("gaps"):
        lines.extend(["", "gaps/approval gates:"])
        for gap in list(profile["gaps"])[:limit]:
            lines.append(f"- {gap}")
    return "\n".join(lines)


def format_approval_plan(status: dict[str, Any]) -> str:
    plan = approval_plan(status)
    summary = plan["summary"]
    costs = plan.get("cost_ledger") or {}
    lines = [
        "World data approval packet (read-only)",
        f"safe local due now={summary['safe_local_due_feeds']} "
        f"refreshable={summary['safe_local_refreshable_feeds']} "
        f"preflight={summary.get('safe_local_dry_run_command')}",
        f"ledger actual=${float(costs.get('actual_usd', 0)):.2f} "
        f"estimated=${float(costs.get('estimated_usd', 0)):.2f} "
        f"approved=${float(costs.get('approved_usd', 0)):.2f} "
        f"pending=${float(costs.get('pending_usd', 0)):.2f}/{int(costs.get('pending_entries', 0))}",
    ]

    sections = (
        ("metered_needs_approval", "Needs spend approval"),
        ("key_or_visibility_blocked", "Needs key/visibility fix"),
        ("cloud_first_or_deferred", "Cloud-first/deferred"),
        ("planned_no_local_collector", "No local collector yet"),
    )
    for key, title in sections:
        rows = plan.get(key) or []
        if not rows:
            continue
        lines.extend(["", f"{title}:"])
        for row in rows[:12]:
            bits = [
                f"P{row['priority']} {row['id']}",
                f"layer={row['layer']}",
                f"cost={row.get('cost') or 'unknown'}",
            ]
            if row.get("coverage"):
                bits.append(f"coverage={row['coverage']}")
            if row.get("blocker"):
                bits.append(f"blocker={row['blocker']}")
            lines.append("- " + " | ".join(bits))
            if row.get("process"):
                lines.append("  process: " + "; ".join(str(p) for p in row["process"][:3]))
            if row.get("outputs"):
                lines.append("  outputs: " + "; ".join(str(o) for o in row["outputs"][:3]))
            risk = _format_execution_risk(row.get("execution_risk") or {})
            if risk:
                lines.append("  risk: " + risk)
            if row.get("preflight_commands"):
                lines.append("  preflight: " + "; ".join(str(c) for c in row["preflight_commands"][:3]))
            if row.get("unblock_steps"):
                lines.append("  unblock: " + "; ".join(str(s) for s in row["unblock_steps"][:3]))
        if len(rows) > 12:
            lines.append(f"- ... {len(rows) - 12} more")
    return "\n".join(lines)


def _missing_identifier_summary(entity_ids: dict[str, Any], *, per_kind_limit: int = 8) -> str:
    """Compact grouped names for top entities that still lack hard IDs."""
    missing = [
        row
        for row in entity_ids.get("entities", [])
        if row.get("missing_identifier")
    ]
    if not missing:
        return ""

    by_kind: dict[str, list[str]] = {}
    for row in missing:
        by_kind.setdefault(str(row.get("kind") or "unknown"), []).append(str(row.get("name") or ""))

    parts: list[str] = []
    for kind, names in sorted(by_kind.items()):
        unique_names = sorted({name for name in names if name})
        if not unique_names:
            continue
        shown = unique_names[:per_kind_limit]
        more = len(unique_names) - len(shown)
        suffix = f", +{more} more" if more > 0 else ""
        parts.append(f"{kind}: {', '.join(shown)}{suffix}")
    return "; ".join(parts)


def _reviewed_identifier_gap_summary(entity_ids: dict[str, Any], *, per_kind_limit: int = 8) -> str:
    reviewed = [
        row
        for row in entity_ids.get("entities", [])
        if row.get("missing_identifier") and row.get("identifier_gap_review")
    ]
    if not reviewed:
        return ""

    by_kind: dict[str, list[str]] = {}
    for row in reviewed:
        by_kind.setdefault(str(row.get("kind") or "unknown"), []).append(str(row.get("name") or ""))

    parts: list[str] = []
    for kind, names in sorted(by_kind.items()):
        unique_names = sorted({name for name in names if name})
        if not unique_names:
            continue
        shown = unique_names[:per_kind_limit]
        more = len(unique_names) - len(shown)
        suffix = f", +{more} more" if more > 0 else ""
        parts.append(f"{kind}: {', '.join(shown)}{suffix}")
    return "; ".join(parts)


def format_actions(status: dict[str, Any]) -> str:
    """Human-sized next-action view for collection without printing every source row."""
    summary = status["summary"]
    disk = status["disk"]
    costs = status.get("cost_ledger", {})
    scans = status.get("scan_logs", {})
    entity_ids = status.get("entity_identifiers", {})
    entity_summary = entity_ids.get("summary") or {}
    health = status.get("series_health", {})
    action_plan = status.get("action_plan") or {}
    action_summary = action_plan.get("summary") or {}
    guard = "OK" if disk["safe_for_writes"] else "BLOCKED"
    lines = [
        "World data next actions (read-only)",
        f"disk guard={guard} free={disk['free_gb']:.1f}GiB used={disk['used_pct']:.1f}%",
        f"queryable_sources={summary['operational_status'].get('queryable_world_state', 0)} "
        f"top_entities={summary['top_entities']} facts={_short_int(int(status['db']['world_state_facts']))}",
        f"ledger actual=${float(costs.get('actual_usd', 0)):.2f} "
        f"estimated=${float(costs.get('estimated_usd', 0)):.2f} "
        f"pending=${float(costs.get('pending_usd', 0)):.2f}/{int(costs.get('pending_entries', 0))}",
    ]
    if health:
        provider_counts = health.get("reviewed_failure_providers") or {}
        provider_bits = ", ".join(f"{k}={v}" for k, v in provider_counts.items())
        lines.append(
            "series health: "
            f"ok={int(health.get('ok', 0))} warn={int(health.get('warn', 0))} "
            f"fail={int(health.get('fail', 0))} "
            f"reviewed_failures={int(health.get('reviewed_failures', 0))} "
            f"unreviewed_failures={int(health.get('unreviewed_failures', 0))}"
            + (f" | {provider_bits}" if provider_bits else "")
        )
    if entity_summary:
        ref_counts = entity_summary.get("by_ref_table") or {}
        by_kind = entity_summary.get("by_kind") or {}
        kind_bits = [
            f"{kind}={int(row.get('with_any_identifier', 0))}/{int(row.get('total', 0))}"
            for kind, row in sorted(by_kind.items())
        ]
        lines.append(
            "top-entity identifiers: "
            f"any={int(entity_summary.get('with_any_identifier', 0))}/{int(entity_summary.get('top_entities', 0))} "
            f"missing={int(entity_summary.get('missing_identifier', 0))}"
            + (" | " + ", ".join(kind_bits) if kind_bits else "")
            + " | "
            + ", ".join(f"{ref}={int(ref_counts.get(ref, 0))}" for ref in IDENTIFIER_REF_TABLES)
        )
        missing_names = _missing_identifier_summary(entity_ids)
        if missing_names:
            lines.append("top-entity missing identifiers: " + missing_names)
        reviewed_names = _reviewed_identifier_gap_summary(entity_ids)
        if reviewed_names:
            lines.append(
                "top-entity reviewed identifier gaps: "
                f"{int(entity_summary.get('reviewed_missing_identifier', 0))}/"
                f"{int(entity_summary.get('missing_identifier', 0))} | "
                + reviewed_names
            )
    if any(row.get("exists") for row in scans.values()):
        rendered = ", ".join(
            f"{name}={float(row.get('gb_scanned', 0)):.1f}GB est=${float(row.get('estimated_usd', 0)):.2f}"
            for name, row in scans.items()
            if row.get("exists")
        )
        lines.append("scan logs: " + rendered)
    if action_summary:
        lines.append(
            "buckets: "
            + ", ".join(f"{k}={v}" for k, v in action_summary.items() if int(v) > 0)
        )
    dry_cmd = summary.get("safe_local_dry_run_command")
    if dry_cmd:
        lines.append(f"safe/local preflight: {dry_cmd}")
    due_feeds = summary.get("safe_local_due_feeds") or []
    refreshable_feeds = summary.get("safe_local_refresh_feeds") or []
    lines.append(
        "safe/local due now: "
        f"{len(due_feeds)} feed(s) "
        f"(refreshable={len(refreshable_feeds)}, stale_hours={float(summary.get('stale_hours', 0)):g})"
    )
    bucket_labels = (
        ("safe_local_due", "safe/local due now"),
        ("safe_local_refreshable", "safe/local refreshable later"),
        ("provider_pipelines", "provider/enrichment pipeline"),
        ("slow_keyless_manual", "slow keyless/manual"),
        ("metered_needs_approval", "metered; needs approval"),
        ("key_or_visibility_blocked", "key or visibility blocked"),
        ("cloud_first_or_deferred", "cloud-first/deferred"),
        ("planned_no_local_collector", "planned/no local collector"),
    )
    for bucket, label in bucket_labels:
        rows = action_plan.get(bucket) or []
        if not rows:
            continue
        lines.append("")
        lines.append(f"{label}:")
        for row in rows[:10]:
            bits = [
                f"P{row['priority']} {row['id']}",
                f"layer={row['layer']}",
                f"facts={_short_int(int(row['facts']))}",
            ]
            if row.get("command"):
                bits.append(f"cmd={row['command']}")
            if row.get("blocker"):
                bits.append(f"blocker={row['blocker']}")
            lines.append("- " + " | ".join(bits))
        if len(rows) > 10:
            lines.append(f"- ... {len(rows) - 10} more")
    return "\n".join(lines)


def format_entity_identifier_status(status: dict[str, Any]) -> str:
    summary = status["summary"]
    lines = [
        "Top entity identifier status (read-only)",
        f"top_entities={summary['top_entities']} seeded={summary['seeded']} "
        f"any_identifier={summary['with_any_identifier']} missing={summary['missing_identifier']} "
        f"identifier_links={summary['identifier_links']}",
        "identifier coverage: "
        + ", ".join(f"{ref}={count}" for ref, count in summary["by_ref_table"].items()),
    ]
    for kind, row in summary.get("by_kind", {}).items():
        lines.append(
            f"{kind}: total={row['total']} seeded={row['seeded']} "
            f"any={row['with_any_identifier']} missing={row['missing_identifier']} "
            f"reviewed_missing={row.get('reviewed_missing_identifier', 0)} "
            f"unreviewed_missing={row.get('unreviewed_missing_identifier', 0)}"
        )
    missing = [row for row in status["entities"] if row["missing_identifier"]]
    if missing:
        names = ", ".join(row["name"] for row in missing[:40])
        more = len(missing) - 40
        suffix = f", +{more} more" if more > 0 else ""
        lines.append(f"missing identifiers: {names}{suffix}")
    reviewed_names = _reviewed_identifier_gap_summary(status)
    if reviewed_names:
        lines.append(
            "reviewed identifier gaps: "
            f"{summary.get('reviewed_missing_identifier', 0)}/{summary.get('missing_identifier', 0)} | "
            + reviewed_names
        )
    return "\n".join(lines)


def format_status(status: dict[str, Any]) -> str:
    summary = status["summary"]
    db_counts = status["db"]
    disk = status["disk"]
    offload = status["offload"]
    costs = status.get("cost_ledger", {})
    scan_logs = status.get("scan_logs", {})
    entity_ids = status.get("entity_identifiers", {})
    entity_summary = entity_ids.get("summary") or {}
    health = status.get("series_health", {})
    guard = "OK" if disk["safe_for_writes"] else "BLOCKED"
    lines = [
        "World data status (read-only)",
        f"registry_sources={summary['sources']} shown={summary['shown_sources']} "
        f"mapped_feeds={summary['mapped_feeds']} feed_files_present={summary['feed_files_present']} "
        f"feed_diag={summary.get('feed_diagnostics', 0)} "
        f"feed_blocked={summary.get('feed_diagnostics_blocked', 0)}",
        "operational status: "
        + ", ".join(f"{k}={v}" for k, v in summary["operational_status"].items()),
        "db: "
        + ", ".join(
            f"{k}={_short_int(int(v))}"
            for k, v in db_counts.items()
            if k in {"sources", "series", "observations", "world_state_facts", "raw_docs", "papers", "entities", "entity_links"}
        ),
        f"local disk: free={disk['free_gb']:.1f}GiB used={disk['used_pct']:.1f}% "
        f"guard={guard} floor={disk['min_free_gb']:.1f}GiB cap={disk['max_used_pct']:.1f}%",
        f"offload: entries={offload.get('entries', 0)} uploaded={offload.get('uploaded', 0)} "
        f"local_deleted={offload.get('local_deleted', 0)} recorded={offload.get('recorded_gib', 0):.2f}GiB "
        f"est=${offload.get('estimated_storage_usd_month', 0):.2f}/mo",
        f"cost ledger: entries={int(costs.get('entries', 0))} "
        f"est=${float(costs.get('estimated_usd', 0)):.2f} "
        f"actual=${float(costs.get('actual_usd', 0)):.2f} "
        f"approved=${float(costs.get('approved_usd', 0)):.2f} "
        f"pending=${float(costs.get('pending_usd', 0)):.2f}/{int(costs.get('pending_entries', 0))}",
        "collection readiness: "
        + ", ".join(f"{k}={v}" for k, v in summary.get("collection_readiness", {}).items()),
    ]
    if health:
        provider_counts = health.get("reviewed_failure_providers") or {}
        provider_bits = ", ".join(f"{k}={v}" for k, v in provider_counts.items())
        lines.append(
            "series health: "
            f"ok={int(health.get('ok', 0))} warn={int(health.get('warn', 0))} "
            f"fail={int(health.get('fail', 0))} "
            f"reviewed_failures={int(health.get('reviewed_failures', 0))} "
            f"unreviewed_failures={int(health.get('unreviewed_failures', 0))}"
            + (f" | {provider_bits}" if provider_bits else "")
        )
    if entity_summary:
        by_kind = entity_summary.get("by_kind") or {}
        kind_bits = [
            f"{kind}={int(row.get('with_any_identifier', 0))}/{int(row.get('total', 0))}"
            for kind, row in sorted(by_kind.items())
        ]
        lines.append(
            "top-entity identifiers: "
            f"any={int(entity_summary.get('with_any_identifier', 0))}/{int(entity_summary.get('top_entities', 0))} "
            f"missing={int(entity_summary.get('missing_identifier', 0))}"
            + (" | " + ", ".join(kind_bits) if kind_bits else "")
        )
        missing_names = _missing_identifier_summary(entity_ids)
        if missing_names:
            lines.append("top-entity missing identifiers: " + missing_names)
        reviewed_names = _reviewed_identifier_gap_summary(entity_ids)
        if reviewed_names:
            lines.append(
                "top-entity reviewed identifier gaps: "
                f"{int(entity_summary.get('reviewed_missing_identifier', 0))}/"
                f"{int(entity_summary.get('missing_identifier', 0))} | "
                + reviewed_names
            )
    providers = costs.get("providers") or []
    if providers:
        rendered = ", ".join(
            f"{p['provider']}=${float(p.get('estimated_usd', 0)):.2f}"
            for p in providers[:6]
        )
        lines.append("cost providers: " + rendered)
    pending_costs = costs.get("pending") or []
    if pending_costs:
        rendered = "; ".join(
            f"{p['id']} {p['provider']}:{p['action']} ${float(p.get('estimated_usd', 0)):.2f}"
            for p in pending_costs[:5]
        )
        lines.append("pending costs: " + rendered)
    if any(row.get("exists") for row in scan_logs.values()):
        rendered = ", ".join(
            f"{name}={float(row.get('gb_scanned', 0)):.1f}GB est=${float(row.get('estimated_usd', 0)):.2f}"
            for name, row in scan_logs.items()
            if row.get("exists")
        )
        lines.append("scan logs: " + rendered)
    action_plan = status.get("action_plan") or {}
    action_summary = action_plan.get("summary") or {}
    if action_summary:
        lines.append(
            "next-source actions: "
            + ", ".join(f"{k}={v}" for k, v in action_summary.items() if int(v) > 0)
        )
        for bucket, label in (
            ("metered_needs_approval", "needs approval"),
            ("key_or_visibility_blocked", "key/visibility blocked"),
            ("planned_no_local_collector", "not collected/no collector"),
        ):
            rows = action_plan.get(bucket) or []
            if rows:
                rendered = ", ".join(str(r["id"]) for r in rows[:6])
                more = len(rows) - 6
                suffix = f", +{more} more" if more > 0 else ""
                lines.append(f"{label}: {rendered}{suffix}")
    safe_cmd = summary.get("safe_local_refresh_command")
    dry_cmd = summary.get("safe_local_dry_run_command")
    if dry_cmd:
        lines.append(f"safe local preflight: {dry_cmd}")
    due_feeds = summary.get("safe_local_due_feeds") or []
    refreshable_feeds = summary.get("safe_local_refresh_feeds") or []
    if due_feeds:
        due_rendered = ", ".join(due_feeds[:20])
        due_more = len(due_feeds) - 20
        due_suffix = f", +{due_more} more" if due_more > 0 else ""
        lines.append(f"safe local due now: {due_rendered}{due_suffix}")
    else:
        lines.append(
            "safe local due now: none "
            f"(refreshable={len(refreshable_feeds)}, stale_hours={float(summary.get('stale_hours', 0)):g})"
        )
    if safe_cmd:
        safe_feeds = ", ".join(due_feeds[:20])
        more = len(due_feeds) - 20
        suffix = f", +{more} more" if more > 0 else ""
        lines.append(f"safe local refresh: {safe_cmd}  feeds={safe_feeds}{suffix}")
    if summary.get("slow_keyless_feeds"):
        lines.append("slow keyless/manual feeds: " + ", ".join(summary["slow_keyless_feeds"]))
    if summary.get("metered_feeds"):
        lines.append("metered feeds need approval: " + ", ".join(summary["metered_feeds"]))
    if summary.get("keyed_feeds"):
        lines.append("keyed feeds need credentials/terms: " + ", ".join(summary["keyed_feeds"]))
    if status["blockers"]:
        lines.append("blockers:")
        for blocker in status["blockers"][:10]:
            lines.append(f"- {blocker}")
    lines.append("")
    lines.append("sources:")
    for row in status["sources"]:
        feeds = ",".join(row["feeds"]) if row["feeds"] else "none"
        counts = (
            f"feed_rows={_short_int(row['feed_rows'])} "
            f"series={_short_int(row['db_series'])} "
            f"obs={_short_int(row['db_observations'])} "
            f"facts={_short_int(row['world_state_facts'])}"
        )
        if row["auxiliary_records"]:
            counts += f" aux={_short_int(row['auxiliary_records'])}"
        raw = (
            f"sources={row['source_records']}"
            f"/hash={row['source_records_with_hash']}"
            f"/raw={row['source_records_with_raw']}"
        )
        blocker = f" blockers={len(row['blockers'])}" if row["blockers"] else ""
        diagnostic = ""
        diag_feeds = [
            f["feed"]
            for f in row.get("feed_files", [])
            if f.get("diagnostic")
        ]
        blocked_feeds = [
            f["feed"]
            for f in row.get("feed_files", [])
            if (f.get("diagnostic") or {}).get("needs_key")
        ]
        if blocked_feeds:
            diagnostic = " feed_blocked=" + ",".join(blocked_feeds)
        elif diag_feeds:
            diagnostic = " feed_diag=" + ",".join(diag_feeds)
        lines.append(
            f"- P{row['priority']} {row['id']} [{row['layer']}/{row['status']}] "
            f"op={row['operational_status']} ready={row.get('collection_readiness', 'unknown')} "
            f"feeds={feeds} {counts} {raw}{diagnostic}{blocker}"
        )
        if row.get("collection_command") and not row.get("safe_local_refresh"):
            lines.append(f"  command: {row['collection_command']}")
        if row["blockers"]:
            lines.append(f"  blocker: {row['blockers'][0]}")
    return "\n".join(lines)
