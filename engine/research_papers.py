"""Mac-safe control plane for the global research-papers lake.

This module deliberately separates "start the operation" from "download terabytes".
The operation manifest is tiny and local; bulk bytes must go to object storage and
metered/requester-pays sources need an explicit budget flag at execution time.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from engine import db, disk_guard

OP_DIR = db.REPO_ROOT / "data" / "research_papers"
MANIFEST_PATH = OP_DIR / "operation_manifest.json"
RUN_LOG_PATH = OP_DIR / "run_log.jsonl"


@dataclass(frozen=True)
class PaperSource:
    id: str
    label: str
    tier: str
    coverage: str
    full_text: str
    official_access: str
    cadence: str
    estimated_raw_gib: float | None
    estimated_kept_gib: float | None
    metered: bool
    legal_posture: str
    local_default: str
    remote_action: str
    notes: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


SOURCES: tuple[PaperSource, ...] = (
    PaperSource(
        id="openalex_snapshot",
        label="OpenAlex snapshot",
        tier="metadata_graph",
        coverage="global scholarly metadata, authors, institutions, citations, topics",
        full_text="metadata_only",
        official_access="s3://openalex/data, no-sign-request public snapshot",
        cadence="free public snapshot refresh; incremental by updated_date partitions",
        estimated_raw_gib=330.0,
        estimated_kept_gib=150.0,
        metered=False,
        legal_posture="open metadata",
        local_default="already partially represented by derived signals; do not copy raw to Mac",
        remote_action="sync/derive in-region to S3, then query via Athena/DuckDB",
        notes="source of truth for worldwide paper metadata and citation graph; no Floxy needed",
    ),
    PaperSource(
        id="crossref_metadata",
        label="Crossref metadata",
        tier="metadata",
        coverage="DOI-registered scholarly metadata across publishers",
        full_text="metadata_abstracts_when_available",
        official_access="REST API keyless for targeted pulls; Metadata Plus snapshots for full corpus",
        cadence="REST incremental; paid snapshots monthly",
        estimated_raw_gib=200.0,
        estimated_kept_gib=80.0,
        metered=True,
        legal_posture="metadata open; some abstracts may have rights limits",
        local_default="targeted keyless counts only",
        remote_action="snapshot to object storage only if paid access is approved",
        notes="fills DOI metadata gaps; not a blanket full-text source",
    ),
    PaperSource(
        id="pubmed_baseline_updates",
        label="PubMed baseline and daily updates",
        tier="metadata_biomed",
        coverage="biomedical citations and abstracts",
        full_text="metadata_abstracts",
        official_access="NCBI FTP baseline plus daily update XML files",
        cadence="annual baseline, daily update files",
        estimated_raw_gib=60.0,
        estimated_kept_gib=30.0,
        metered=False,
        legal_posture="official citation data; abstracts can have rights limits",
        local_default="topic counts only",
        remote_action="load baseline to object storage, apply daily update files in order",
        notes="gapless biomed metadata once baseline plus numbered daily files are tracked",
    ),
    PaperSource(
        id="pmc_oa_full_text",
        label="PubMed Central Open Access full text",
        tier="full_text_biomed",
        coverage="OA biomedical article XML/text, plus selected PDFs/media",
        full_text="xml_text_pdf_when_license_allows",
        official_access="NCBI PMC FTP bulk baseline and daily incremental packages",
        cadence="baseline packages plus daily incrementals",
        estimated_raw_gib=500.0,
        estimated_kept_gib=250.0,
        metered=False,
        legal_posture="OA subset only; license must be stored per article",
        local_default="manifest only",
        remote_action="store XML/text in object storage; PDF only when license/use allows",
        notes="best first full-text source after arXiv because XML is structured",
    ),
    PaperSource(
        id="semantic_scholar_s2ag",
        label="Semantic Scholar S2AG",
        tier="metadata_graph",
        coverage="papers, authors, citations, embeddings-adjacent metadata depending on dataset",
        full_text="metadata_only_or_s2orc_when_available",
        official_access="Datasets API; file downloads may require API key",
        cadence="monthly downloadable datasets",
        estimated_raw_gib=None,
        estimated_kept_gib=None,
        metered=False,
        legal_posture="API/data license applies",
        local_default="release manifest only",
        remote_action="request/use dataset key, mirror monthly release manifests and changed shards",
        notes="use as cross-check and enrichment layer, not the only global corpus",
    ),
    PaperSource(
        id="arxiv_metadata",
        label="arXiv metadata",
        tier="metadata_preprints",
        coverage="arXiv preprint metadata, categories, abstracts, versions",
        full_text="metadata_abstracts",
        official_access="OAI-PMH and existing local arXiv parquet ingest path",
        cadence="recurring OAI harvest; resumable by state",
        estimated_raw_gib=3.0,
        estimated_kept_gib=2.0,
        metered=False,
        legal_posture="official metadata",
        local_default="already local in papers table",
        remote_action="keep local derived DB plus offloaded parquet mirror",
        notes="current local papers table is mostly this substrate",
    ),
    PaperSource(
        id="arxiv_full_text",
        label="arXiv full text",
        tier="full_text_preprints",
        coverage="arXiv PDFs and source bundles",
        full_text="pdf_and_source",
        official_access="s3://arxiv requester-pays bucket, manifest-driven",
        cadence="monthly-ish bucket growth; inventory by S3 manifests",
        estimated_raw_gib=9200.0,
        estimated_kept_gib=9200.0,
        metered=True,
        legal_posture="index/link back; do not redistribute beyond licenses",
        local_default="never download to Mac by default",
        remote_action="remote-only S3-to-S3 or cloud worker; parse source before PDF; OCR last",
        notes="Floxy is the wrong path; official requester-pays S3 is the right path",
    ),
    PaperSource(
        id="regional_open_preprints",
        label="Regional OA and preprint indexes",
        tier="metadata_full_text_selected",
        coverage="SciELO, J-STAGE, ChinaXiv and other non-Western/open repositories",
        full_text="mixed_by_license",
        official_access="OAI/API/bulk where available; scrape only where allowed",
        cadence="source-specific weekly/monthly",
        estimated_raw_gib=None,
        estimated_kept_gib=None,
        metered=False,
        legal_posture="source/license specific",
        local_default="not started",
        remote_action="add one official/bulk connector at a time with license rows",
        notes="Floxy only if official access is blocked and terms permit collection",
    ),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_count(conn: sqlite3.Connection, table: str) -> int | None:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.Error:
        return None


def local_status(conn: sqlite3.Connection | None = None) -> dict[str, object]:
    close = False
    if conn is None:
        conn = db.connect()
        close = True
    try:
        counts = {
            table: _safe_count(conn, table)
            for table in (
                "papers",
                "raw_docs",
                "sources",
                "series",
                "observations",
                "entities",
                "graph_nodes",
                "graph_edges",
            )
        }
    finally:
        if close:
            conn.close()
    feed_dir = db.REPO_ROOT / "data" / "feeds"
    feed_files = sorted(feed_dir.glob("*.jsonl")) if feed_dir.exists() else []
    return {
        "repo": str(db.REPO_ROOT),
        "operation_dir": str(OP_DIR),
        "db_path": str(db.DB_PATH),
        "db_counts": counts,
        "feed_files": len(feed_files),
        "disk": disk_guard.usage(db.REPO_ROOT),
    }


def plan(*, remote_prefix: str | None = None, budget_usd: float = 0.0) -> dict[str, object]:
    total_known_raw = sum(s.estimated_raw_gib or 0.0 for s in SOURCES)
    total_known_kept = sum(s.estimated_kept_gib or 0.0 for s in SOURCES)
    return {
        "operation": "research_papers_global_lake",
        "generated_at": _now(),
        "remote_prefix": remote_prefix,
        "budget_usd": float(budget_usd),
        "source_count": len(SOURCES),
        "known_raw_gib": round(total_known_raw, 1),
        "known_kept_gib": round(total_known_kept, 1),
        "sources": [s.as_dict() for s in SOURCES],
        "ec2_worker_plan": ec2_worker_plan(remote_prefix=remote_prefix),
        "principles": [
            "object storage is the lake; the Mac is a control node",
            "metadata everywhere, full text where official access and license permit",
            "structured extraction rows beat dumping millions of pages into a prompt",
            "PDF text extraction before OCR; OCR only for scanned/low-text documents",
            "no metered/requester-pays bulk operation without explicit budget and execute flags",
        ],
        "next_safe_commands": [
            "uv run python -m engine.cli research-papers-operation --json",
            "uv run python -m engine.feeds.collect_all --audit",
            "uv run python -m engine.cli data-offload --root data --min-size-mb 100 --json",
        ],
    }


def ec2_worker_plan(*, remote_prefix: str | None = None) -> dict[str, object]:
    lake = remote_prefix or "s3://vaticinus-datalake-405844305300-us-east-1/research-papers"
    return {
        "region": "us-east-1",
        "lake_prefix": lake,
        "launch_posture": "not launched by this command; use after budget approval",
        "recommended_pilot": {
            "instance_family": "c7i.large or c7g.large spot/on-demand",
            "purpose": "copy source manifests and run one tiny arXiv/PMC shard through text extraction",
            "expected_runtime_hours": "1-3",
            "expected_cost_usd": "single-digit dollars excluding any full corpus storage",
        },
        "recommended_backfill": {
            "instance_family": "c7i.2xlarge/r7i.2xlarge or larger, remote scratch only",
            "purpose": "bulk manifest-driven mirror, parquet conversion, extraction batching",
            "expected_runtime": "days to weeks depending on source and extractor",
            "expected_cost_usd": "requires a separate named cap before launch",
        },
        "safe_first_phases": [
            {
                "phase": "manifest_inventory",
                "writes": f"{lake.rstrip('/')}/manifests/",
                "bulk_bytes": "no",
                "description": "copy or record official source manifests/file lists only",
            },
            {
                "phase": "one_shard_pilot",
                "writes": f"{lake.rstrip('/')}/pilot/",
                "bulk_bytes": "bounded",
                "description": "process one arXiv month/source shard plus one PMC OA package and validate extraction rows",
            },
            {
                "phase": "full_backfill",
                "writes": f"{lake.rstrip('/')}/raw/ and {lake.rstrip('/')}/parquet/",
                "bulk_bytes": "yes",
                "description": "remote-only mirror and extraction after pilot metrics pass",
            },
        ],
        "local_mac_rule": "no source PDFs, tarballs, or parquet shards should land on the Mac except tiny manifests",
    }


def validate_execute(*, remote_prefix: str | None, budget_usd: float, allow_metered: bool) -> list[str]:
    blockers: list[str] = []
    if not remote_prefix or not remote_prefix.startswith("s3://"):
        blockers.append("remote_prefix_required_for_bulk_storage")
    if not allow_metered:
        blockers.append("allow_metered_required_for_requester_pays_or_paid_snapshots")
    if budget_usd <= 0:
        blockers.append("positive_budget_usd_required")
    return blockers


def bootstrap(
    *,
    remote_prefix: str | None = None,
    budget_usd: float = 0.0,
    execute: bool = False,
    allow_metered: bool = False,
    allow_low_disk: bool = False,
    conn: sqlite3.Connection | None = None,
) -> dict[str, object]:
    disk = disk_guard.assert_safe(
        db.REPO_ROOT,
        label="research papers operation bootstrap",
        allow_low_disk=allow_low_disk,
    )
    blockers = validate_execute(
        remote_prefix=remote_prefix,
        budget_usd=budget_usd,
        allow_metered=allow_metered,
    ) if execute else []
    payload = {
        "status": "blocked" if blockers else ("execute_ready" if execute else "planned"),
        "execute_requested": bool(execute),
        "blockers": blockers,
        "local_status": local_status(conn),
        "disk_guard": disk,
        "plan": plan(remote_prefix=remote_prefix, budget_usd=budget_usd),
    }
    OP_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with RUN_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "ts": _now(),
            "status": payload["status"],
            "execute_requested": execute,
            "blockers": blockers,
            "remote_prefix": remote_prefix,
            "budget_usd": float(budget_usd),
        }, sort_keys=True) + "\n")
    return payload


def format_summary(payload: dict[str, object]) -> str:
    plan_payload = payload["plan"]
    local = payload["local_status"]
    counts = local["db_counts"]
    disk = local["disk"]
    lines = [
        f"research papers operation: {payload['status']}",
        f"manifest: {MANIFEST_PATH}",
        f"db papers={counts.get('papers')} raw_docs={counts.get('raw_docs')} entities={counts.get('entities')}",
        f"disk free={float(disk['free_gb']):.1f}GiB used={float(disk['used_pct']):.1f}%",
        f"sources={plan_payload['source_count']} known_raw={plan_payload['known_raw_gib']}GiB known_kept={plan_payload['known_kept_gib']}GiB",
    ]
    blockers = payload.get("blockers") or []
    if blockers:
        lines.append("blocked: " + ", ".join(str(b) for b in blockers))
    lines.append("no bulk bytes were downloaded by this command")
    return "\n".join(lines)
