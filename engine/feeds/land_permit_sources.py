"""Official/open land-permit source seed.

This is not a permit scraper. It is the small, high-ROI source-target manifest that tells the
world-state build where to aim first for land, EIA, concession, and cadastre collectors.

The output is intentionally tiny and laptop-safe: `data/feeds/land_permit_sources.jsonl`.
Use `seed_sources()` to also register these source targets in SQLite with provenance that points
to the manifest, not to fetched portal bytes.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine import db, rawstore
from engine.schemas import SourceKind, _now, _uid

OUT_PATH = Path(__file__).resolve().parents[2] / "data" / "feeds" / "land_permit_sources.jsonl"


PORTALS: tuple[dict[str, Any], ...] = (
    {
        "id": "us_federal_permitting_dashboard",
        "name": "United States Federal Permitting Dashboard projects",
        "jurisdiction": "United States",
        "region": "North America",
        "priority": 1,
        "source_type": "federal_permitting_dashboard",
        "url": "https://www.permits.performance.gov/projects",
        "source_authority": "Federal Permitting Improvement Steering Council / Performance.gov",
        "expected_fields": ("project", "sector", "sponsor", "agency", "milestone", "timeline", "status"),
        "collector_status": "needs_project_export_or_page_collector",
        "refresh_model": "bulk project export/backfill plus weekly delta check",
        "roi_reason": "Fast US signal for infrastructure projects whose timing is gated by federal reviews and permits.",
    },
    {
        "id": "canada_impact_assessment_registry",
        "name": "Canadian Impact Assessment Registry",
        "jurisdiction": "Canada",
        "region": "North America",
        "priority": 1,
        "source_type": "impact_assessment_register",
        "url": "https://iaac-aeic.gc.ca/050/evaluations?culture=en-CA",
        "source_authority": "Impact Assessment Agency of Canada",
        "expected_fields": ("project", "proponent", "assessment_type", "status", "location", "documents", "decision"),
        "collector_status": "needs_search_result_collector",
        "refresh_model": "official register backfill plus weekly project-status delta",
        "roi_reason": "High-value source for Canadian mines, energy corridors, LNG, hydro, grid, and critical-minerals projects.",
    },
    {
        "id": "australia_epbc_public_portal",
        "name": "Australia EPBC Act Public Portal",
        "jurisdiction": "Australia",
        "region": "Asia-Pacific",
        "priority": 1,
        "source_type": "environmental_referral_approval_register",
        "url": "https://epbcpublicportal.environment.gov.au/",
        "source_authority": "Australian Government Department of Climate Change, Energy, the Environment and Water",
        "expected_fields": ("project", "proponent", "referral", "controlled_action", "decision", "public_comment", "status"),
        "collector_status": "needs_portal_export_or_browser_collector",
        "refresh_model": "official portal backfill plus weekly notices/decision delta",
        "roi_reason": "Early permitting signal for lithium, iron ore, renewables, transmission, hydrogen, ports, and industrial projects.",
    },
    {
        "id": "chile_seia_projects",
        "name": "Chile SEIA environmental assessment projects",
        "jurisdiction": "Chile",
        "region": "Latin America",
        "priority": 1,
        "source_type": "environmental_impact_assessment_register",
        "url": "https://www.sea.gob.cl/en/",
        "source_authority": "Servicio de Evaluacion Ambiental",
        "expected_fields": ("project", "holder", "region", "sector", "assessment_type", "status", "decision_date"),
        "collector_status": "needs_advanced_search_collector",
        "refresh_model": "official project search backfill plus weekly decision/status delta",
        "roi_reason": "Critical for copper, lithium, desalination, transmission, ports, and renewables capacity timing.",
    },
    {
        "id": "resourcecontracts_global",
        "name": "ResourceContracts petroleum and mining contracts",
        "jurisdiction": "Global",
        "region": "Global",
        "priority": 1,
        "source_type": "open_contract_repository",
        "url": "https://resourcecontracts.org/",
        "source_authority": "ResourceContracts.org open repository",
        "expected_fields": ("contract", "country", "resource", "company", "project", "signature_date", "document"),
        "collector_status": "needs_repository_api_or_search_collector",
        "refresh_model": "repository backfill plus monthly new-contract delta",
        "roi_reason": "Global fallback when national cadastres are fragmented; useful for concession holder/project edges.",
    },
    {
        "id": "eiti_contracts_licenses",
        "name": "EITI contracts and licenses disclosure guidance",
        "jurisdiction": "Global",
        "region": "Global",
        "priority": 1,
        "source_type": "disclosure_backbone",
        "url": "https://eiti.org/guidance-notes/contracts-and-licenses",
        "source_authority": "Extractive Industries Transparency Initiative",
        "expected_fields": ("country", "license", "contract", "award_date", "holder", "commodity", "disclosure_status"),
        "collector_status": "needs_country_disclosure_inventory",
        "refresh_model": "country inventory backfill plus monthly disclosure update",
        "roi_reason": "Maps where official contract/license disclosure should exist before paying for registry enrichment.",
    },
    {
        "id": "drc_mining_cadastre",
        "name": "DRC Mining Cadastre Map Portal",
        "jurisdiction": "Democratic Republic of the Congo",
        "region": "Africa",
        "priority": 1,
        "source_type": "mining_cadastre",
        "url": "https://drclicences.cami.cd/",
        "source_authority": "Cadastre Minier CAMI",
        "expected_fields": ("license", "holder", "license_type", "status", "commodity", "geometry", "expiry"),
        "collector_status": "needs_map_layer_inventory",
        "refresh_model": "map layer backfill plus monthly license/status delta",
        "roi_reason": "Cobalt/copper supply option visibility; high value for battery and grid-material forecasts.",
    },
    {
        "id": "zambia_mining_cadastre",
        "name": "Zambia Mining Cadastre eGov Portal",
        "jurisdiction": "Zambia",
        "region": "Africa",
        "priority": 1,
        "source_type": "mining_cadastre",
        "url": "https://portal.miningcadastre.com/",
        "source_authority": "Ministry of Mines and Minerals Development",
        "expected_fields": ("license", "application", "holder", "license_type", "status", "payment", "renewal"),
        "collector_status": "needs_portal_inventory_and_terms_review",
        "refresh_model": "portal/license inventory plus monthly status delta after terms review",
        "roi_reason": "Copperbelt project pipeline and license-stage visibility before production changes show up.",
    },
    {
        "id": "peru_geocatmin",
        "name": "Peru GEOCATMIN mining and geological geoportal",
        "jurisdiction": "Peru",
        "region": "Latin America",
        "priority": 1,
        "source_type": "mining_cadastre_geoportal",
        "url": "https://geocatmin.ingemmet.gob.pe/geocatmin/",
        "source_authority": "INGEMMET",
        "expected_fields": ("concession", "holder", "status", "geometry", "zone", "commodity", "environmental_authorization"),
        "collector_status": "needs_geoportal_layer_inventory",
        "refresh_model": "geospatial layer inventory plus monthly concession/status delta",
        "roi_reason": "Copper/gold/zinc concession visibility and project land context in a major mining jurisdiction.",
    },
)


def manifest_rows(*, collected_at: str | None = None) -> list[dict[str, Any]]:
    ts = collected_at or datetime.now(timezone.utc).isoformat()
    return [
        {
            **row,
            "feed": "land_permit_sources",
            "date": ts[:10],
            "collected_at": ts,
            "cost_cents": 0,
            "provenance": "curated_official_source_seed",
        }
        for row in PORTALS
    ]


def write_manifest(path: Path = OUT_PATH, *, collected_at: str | None = None) -> dict[str, Any]:
    rows = manifest_rows(collected_at=collected_at)
    tmp = path.with_suffix(".jsonl.tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(path)
    return {
        "ok": True,
        "feed": "land_permit_sources",
        "rows": len(rows),
        "path": str(path),
        "cost_cents": 0,
    }


def seed_sources(conn: sqlite3.Connection, *, path: Path = OUT_PATH) -> dict[str, Any]:
    if not path.exists():
        write_manifest(path)
    content = path.read_bytes()
    manifest_hash = rawstore.put(conn, content, url=str(path), media_type="application/jsonl")
    now = _now().isoformat()
    conn.execute(
        """
        INSERT OR IGNORE INTO pillars (id, name, description, ord, status)
        VALUES (5, 'Physical / supply', 'Physical supply, land, permitting, and infrastructure constraints.', 5, 'in_progress')
        """
    )
    inserted = updated = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            source_id = f"land_permit_source:{row['id']}"
            exists = conn.execute("SELECT 1 FROM sources WHERE id=?", (source_id,)).fetchone()
            conn.execute(
                """
                INSERT INTO sources (
                    id, url, title, pillar_id, kind, trust_score, trust_rationale,
                    recency, accessed_at, cost_cents, content_hash,
                    raw_provenance_status, raw_provenance_reason, raw_provenance_checked_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    url=excluded.url,
                    title=excluded.title,
                    accessed_at=excluded.accessed_at,
                    content_hash=excluded.content_hash,
                    raw_provenance_status=excluded.raw_provenance_status,
                    raw_provenance_reason=excluded.raw_provenance_reason,
                    raw_provenance_checked_at=excluded.raw_provenance_checked_at
                """,
                (
                    source_id,
                    row["url"],
                    row["name"],
                    5,
                    SourceKind.primary.value,
                    85,
                    f"Official/open land-permit source seed for {row['jurisdiction']}; target for a future collector, not a scraped permit fact.",
                    row.get("date"),
                    now,
                    0,
                    manifest_hash,
                    "catalog_manifest_only",
                    "portal metadata is exact in the land_permit_sources manifest; target portal bytes not fetched by this seed",
                    now,
                ),
            )
            if exists:
                updated += 1
            else:
                inserted += 1
    conn.commit()
    return {
        "ok": True,
        "feed": "land_permit_sources",
        "rows": inserted + updated,
        "inserted": inserted,
        "updated": updated,
        "manifest_hash": manifest_hash,
        "cost_cents": 0,
    }


def main() -> None:
    out = write_manifest()
    print(
        f"land_permit_sources: rows={out['rows']} path={out['path']} cost=$0.00 "
        "bulk_fetch=no paid_processing=no"
    )


if __name__ == "__main__":
    main()
