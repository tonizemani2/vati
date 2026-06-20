from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import companies_house_enrich, gleif_enrich, rawstore, sec_company_enrich, wikidata_enrich, world_catalog
from tests.test_world_state import memory_db


class WorldCatalogTests(unittest.TestCase):
    def test_registry_has_unique_sources_and_global_coverage(self) -> None:
        ids = [s.id for s in world_catalog.DATA_SOURCES]

        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("google_patents", ids)
        self.assertIn("paper_patent_reliance", ids)
        self.assertIn("patentsview_odp", ids)
        self.assertIn("ilo_labor", ids)
        self.assertIn("gleif", ids)
        self.assertIn("wikidata_entities", ids)
        self.assertIn("gdelt", ids)
        self.assertIn("prediction_markets", ids)
        self.assertIn("wikipedia_pageviews", ids)
        self.assertTrue(any(s.coverage.startswith("global") for s in world_catalog.DATA_SOURCES))
        reliance = next(s for s in world_catalog.DATA_SOURCES if s.id == "paper_patent_reliance")
        self.assertEqual(reliance.status, "planned_metered")
        self.assertIn("worldwide", reliance.coverage)
        self.assertEqual(next(s for s in world_catalog.DATA_SOURCES if s.id == "patentsview_odp").status, "planned_keyed")

    def test_registry_has_global_land_permit_layer_planned_not_landed(self) -> None:
        by_id = {s.id: s for s in world_catalog.DATA_SOURCES}
        land_source_ids = {
            "land_permit_source_registry",
            "environmental_planning_eia",
            "land_permits_cadastre",
            "open_geospatial_land_context",
            "resource_concessions_contracts",
        }

        self.assertTrue(land_source_ids.issubset(by_id))
        seed = by_id["land_permit_source_registry"]
        self.assertEqual(seed.layer, "land_use")
        self.assertEqual(seed.priority, 1)
        self.assertEqual(seed.status, "partial")
        self.assertIn("source-target manifest", seed.coverage)
        permits = by_id["land_permits_cadastre"]
        self.assertEqual(permits.layer, "land_use")
        self.assertEqual(permits.priority, 1)
        self.assertEqual(permits.status, "partial_mixed")
        self.assertIn("global view", permits.coverage)
        self.assertIn("paid parcel vendors", permits.cost)
        self.assertIn("land-permit facts", permits.outputs)
        self.assertIn("land_parcel", permits.entities)
        concessions = by_id["resource_concessions_contracts"]
        self.assertEqual(concessions.status, "partial")
        self.assertIn("global", concessions.coverage)
        self.assertIn("concession facts", concessions.outputs)
        self.assertIn("material", concessions.entities)
        self.assertEqual(by_id["environmental_planning_eia"].layer, "land_use_policy")
        self.assertEqual(by_id["open_geospatial_land_context"].priority, 2)
        self.assertIn("not official permit decisions", by_id["open_geospatial_land_context"].coverage)

    def test_registry_has_research_expansion_sources_planned_not_collected(self) -> None:
        by_id = {s.id: s for s in world_catalog.DATA_SOURCES}

        self.assertIn("europe_pmc", by_id)
        self.assertIn("opencitations", by_id)
        self.assertEqual(by_id["europe_pmc"].layer, "research")
        self.assertEqual(by_id["europe_pmc"].status, "partial")
        self.assertIn("annotation facts", by_id["europe_pmc"].outputs)
        self.assertIn("approval", by_id["europe_pmc"].cost)
        self.assertEqual(by_id["opencitations"].layer, "research")
        self.assertEqual(by_id["opencitations"].status, "planned_free")
        self.assertIn("open citation facts", by_id["opencitations"].outputs)
        self.assertIn("approval", by_id["opencitations"].cost)

    def test_research_expansion_inventory_is_diverse_and_approval_gated(self) -> None:
        inventory = world_catalog.research_expansion_inventory()
        summary = inventory["summary"]
        by_id = {row["id"]: row for row in inventory["targets"]}

        self.assertTrue(inventory["ok"])
        self.assertEqual(inventory["status"], "plan_only_not_collection")
        self.assertGreaterEqual(summary["targets"], 8)
        self.assertGreaterEqual(summary["priority_1"], 5)
        self.assertEqual(summary["missing_source_ids"], [])
        self.assertIn("explicit approval", summary["collection_policy"])
        self.assertIn("LLM extraction", summary["approval_gates"])
        self.assertIn("openalex_snapshot", summary["source_coverage"])
        self.assertIn("europe_pmc", summary["source_coverage"])
        self.assertIn("opencitations", summary["source_coverage"])
        self.assertIn("europe_pmc_life_sciences", by_id)
        self.assertEqual(by_id["europe_pmc_life_sciences"]["status"], "partial_metadata")
        self.assertIn("annotation facts", by_id["europe_pmc_life_sciences"]["outputs"])
        self.assertIn("paper_patent_reliance_bridge", by_id)
        self.assertIn("Athena/cloud scan", by_id["paper_patent_reliance_bridge"]["approval_gates"])
        rendered = world_catalog.format_research_expansion_inventory(inventory, limit=4)
        csv_text = world_catalog.research_expansion_inventory_csv(inventory)
        self.assertIn("Research expansion inventory", rendered)
        self.assertIn("source coverage", rendered)
        self.assertIn("europe_pmc_life_sciences", csv_text)
        self.assertIn("approval_gates", csv_text)

    def test_research_expansion_inventory_filters_priority_and_status(self) -> None:
        p1 = world_catalog.research_expansion_inventory(priority=1)
        planned_free = world_catalog.research_expansion_inventory(status="planned_free")

        self.assertTrue(all(row["priority"] <= 1 for row in p1["targets"]))
        self.assertGreaterEqual(p1["summary"]["targets"], 1)
        self.assertTrue(all(row["status"] == "planned_free" for row in planned_free["targets"]))
        self.assertGreaterEqual(planned_free["summary"]["targets"], 1)

    def test_land_permit_layer_matrix_is_cloud_first_and_uncollected(self) -> None:
        conn = memory_db()
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                (root / "feeds").mkdir()
                with mock.patch.object(
                    world_catalog.disk_guard,
                    "usage",
                    return_value={
                        "total_gb": 100.0,
                        "used_gb": 10.0,
                        "free_gb": 90.0,
                        "used_pct": 10.0,
                    },
                ):
                    status = world_catalog.data_status(conn, priority=2, feed_dir=root / "feeds", repo_root=root)
            matrix = world_catalog.source_matrix(status)

            rows = {row["id"]: row for row in matrix["sources"]}
            permits = rows["land_permits_cadastre"]
            self.assertEqual(permits["operational_status"], "not_collected")
            self.assertEqual(permits["collection_readiness"], "safe_local_refresh_needed")
            self.assertEqual(permits["next_action_type"], "safe_local_refresh_due")
            self.assertTrue(permits["execution_risk"]["cloud_first"])
            self.assertTrue(permits["execution_risk"]["local_bulk_risk"])
            self.assertEqual(permits["coverage_scope"], "global")
            self.assertTrue(any("off-laptop" in note for note in permits["execution_risk"]["notes"]))
            self.assertTrue(any("blm_mining_claims" in command for command in permits["preflight_commands"]))
            self.assertTrue(any("world-data-approvals" in command for command in permits["preflight_commands"]))
            eia = rows["environmental_planning_eia"]
            self.assertEqual(eia["operational_status"], "not_collected")
            self.assertEqual(eia["collection_readiness"], "safe_local_refresh_needed")
            self.assertEqual(eia["next_action_type"], "safe_local_refresh_due")
            self.assertTrue(eia["execution_risk"]["cloud_first"])
            self.assertTrue(eia["execution_risk"]["local_bulk_risk"])
            self.assertTrue(any("land_permits_canada_iaac" in command for command in eia["preflight_commands"]))
            concessions = rows["resource_concessions_contracts"]
            self.assertEqual(concessions["operational_status"], "not_collected")
            self.assertEqual(concessions["collection_readiness"], "safe_local_refresh_needed")
            self.assertEqual(concessions["next_action_type"], "safe_local_refresh_due")
            self.assertTrue(concessions["execution_risk"]["cloud_first"])
            self.assertTrue(concessions["execution_risk"]["local_bulk_risk"])
            self.assertTrue(any("resourcecontracts" in command for command in concessions["preflight_commands"]))
            row = rows["open_geospatial_land_context"]
            self.assertEqual(row["operational_status"], "planned_not_collected")
            self.assertEqual(row["collection_readiness"], "planned_no_local_collector")
            self.assertEqual(row["next_action_type"], "needs_collector_or_keyed_pipeline")
            self.assertTrue(row["execution_risk"]["cloud_first"])
            self.assertTrue(row["execution_risk"]["local_bulk_risk"])
        finally:
            conn.close()

    def test_land_permit_inventory_is_global_planned_and_approval_gated(self) -> None:
        inventory = world_catalog.land_permit_inventory()
        summary = inventory["summary"]

        self.assertTrue(inventory["ok"])
        self.assertEqual(inventory["status"], "planned_not_collected")
        self.assertGreaterEqual(summary["jurisdictions"], 10)
        self.assertGreaterEqual(summary["priority_1"], 6)
        self.assertGreaterEqual(summary["regions"], 6)
        self.assertEqual(summary["missing_source_ids"], [])
        self.assertEqual(set(summary["source_ids"]), set(world_catalog.LAND_PERMIT_SOURCE_IDS))
        self.assertIn("land_permits_cadastre", summary["source_coverage"])
        self.assertIn("land_permit_source_registry", summary["source_coverage"])
        self.assertIn("resource_concessions_contracts", summary["source_coverage"])
        self.assertIn("cloud geospatial joins", summary["approval_gates"])
        self.assertIn("explicit approval", summary["collection_policy"])
        by_id = {row["id"]: row for row in inventory["jurisdictions"]}
        self.assertIn("us_federal_state_local", by_id)
        self.assertIn("africa_critical_minerals_energy", by_id)
        self.assertIn("global_open_geospatial_context", by_id)
        us = by_id["us_federal_state_local"]
        self.assertIn("official/open portals first", us["collection_policy"].lower())
        self.assertIn("paid parcel vendor", us["approval_gates"])
        self.assertIn("permit-stage facts", us["outputs"])
        rendered = world_catalog.format_land_permit_inventory(inventory, limit=3)
        csv_text = world_catalog.land_permit_inventory_csv(inventory)
        self.assertIn("Global land-permit/concession inventory", rendered)
        self.assertIn("official/open first", rendered)
        self.assertIn("approval gates", rendered)
        self.assertIn("us_federal_state_local", csv_text)
        self.assertIn("source_ids", csv_text)

    def test_land_permit_inventory_filters_priority_and_region(self) -> None:
        p1 = world_catalog.land_permit_inventory(priority=1)
        europe = world_catalog.land_permit_inventory(region="Europe")

        self.assertTrue(all(row["priority"] <= 1 for row in p1["jurisdictions"]))
        self.assertGreaterEqual(p1["summary"]["jurisdictions"], 1)
        self.assertTrue(all("Europe" in row["region"] or "Europe" in row["name"] for row in europe["jurisdictions"]))
        self.assertEqual(europe["summary"]["by_region"], {"Europe": len(europe["jurisdictions"])})

    def test_registry_has_physical_constraint_sources_and_land_first(self) -> None:
        by_id = {s.id: s for s in world_catalog.DATA_SOURCES}

        for source_id in (
            "grid_interconnection_transmission",
            "water_rights_stress",
            "industrial_facility_air_water_permits",
            "ports_logistics_capacity",
            "carbon_storage_pore_space",
        ):
            self.assertIn(source_id, by_id)

        self.assertEqual(by_id["grid_interconnection_transmission"].priority, 1)
        self.assertEqual(by_id["water_rights_stress"].priority, 1)
        self.assertEqual(by_id["ports_logistics_capacity"].status, "planned_mixed")
        self.assertIn("water-right facts", by_id["water_rights_stress"].outputs)
        self.assertIn("interconnection-stage facts", by_id["grid_interconnection_transmission"].outputs)
        self.assertIn("storage-permit facts", by_id["carbon_storage_pore_space"].outputs)

    def test_physical_constraint_inventory_keeps_land_research_patents_and_approval_gates(self) -> None:
        inventory = world_catalog.physical_constraint_inventory()
        summary = inventory["summary"]
        by_id = {row["id"]: row for row in inventory["targets"]}

        self.assertTrue(inventory["ok"])
        self.assertEqual(inventory["status"], "plan_only_not_collection")
        self.assertGreaterEqual(summary["targets"], 9)
        self.assertGreaterEqual(summary["priority_1"], 6)
        self.assertEqual(summary["missing_source_ids"], [])
        self.assertIn("explicit approval", summary["collection_policy"])
        self.assertIn("land_permits_cadastre", summary["source_coverage"])
        self.assertIn("land_permit_source_registry", summary["source_coverage"])
        self.assertIn("google_patents", summary["source_coverage"])
        self.assertIn("openalex_snapshot", summary["source_coverage"])
        self.assertIn("water_rights_stress", summary["source_coverage"])
        self.assertIn("land_permit_spine", by_id)
        self.assertEqual(by_id["land_permit_spine"]["priority"], 1)
        self.assertIn("Highest priority", by_id["land_permit_spine"]["notes"])
        self.assertIn("BigQuery dry-run approval", by_id["patent_rights_backbone"]["approval_gates"])
        self.assertIn("snapshot backfill", by_id["research_paper_backbone"]["refresh_model"])
        rendered = world_catalog.format_physical_constraint_inventory(inventory, limit=3)
        csv_text = world_catalog.physical_constraint_inventory_csv(inventory)
        self.assertIn("Physical constraint data inventory", rendered)
        self.assertIn("land_permit_spine", csv_text)
        self.assertIn("approval_gates", csv_text)

    def test_physical_constraint_inventory_filters_priority_and_status(self) -> None:
        p1 = world_catalog.physical_constraint_inventory(priority=1)
        partial = world_catalog.physical_constraint_inventory(status="partial")

        self.assertTrue(all(row["priority"] <= 1 for row in p1["targets"]))
        self.assertGreaterEqual(p1["summary"]["targets"], 1)
        self.assertTrue(all(row["status"] == "partial" for row in partial["targets"]))
        self.assertGreaterEqual(partial["summary"]["targets"], 1)

    def test_constraint_roi_queue_prioritizes_direct_roi_and_surfaces_approvals(self) -> None:
        conn = memory_db()
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                (root / "feeds").mkdir()
                with mock.patch.object(
                    world_catalog.disk_guard,
                    "usage",
                    return_value={
                        "total_gb": 100.0,
                        "used_gb": 20.0,
                        "free_gb": 80.0,
                        "used_pct": 20.0,
                    },
                ):
                    status = world_catalog.data_status(conn, feed_dir=root / "feeds", repo_root=root)
            report = world_catalog.constraint_roi_queue(status)
            queue = report["queue"]
            by_id = {row["id"]: row for row in queue}
            rendered = world_catalog.format_constraint_roi_queue(report, limit=9)

            self.assertTrue(report["ok"])
            self.assertEqual(report["status"], "read_only_no_collection")
            self.assertGreaterEqual(report["summary"]["targets"], 9)
            self.assertEqual(queue[0]["id"], "land_permit_spine")
            self.assertIn("permissioned land", queue[0]["direct_roi"])
            self.assertIn("research_paper_backbone", by_id)
            self.assertIn("patent_rights_backbone", by_id)
            self.assertIn("google_patents", by_id["patent_rights_backbone"]["paid_approval_sources"])
            self.assertIn("paper_patent_reliance", by_id["patent_rights_backbone"]["paid_approval_sources"])
            self.assertIn("BigQuery dry-run approval", by_id["patent_rights_backbone"]["approval_gates"])
            self.assertIn("water_rights_stress", by_id["water_constraint_layer"]["collector_gaps"])
            self.assertIn("Constraint ROI sprint queue", rendered)
            self.assertIn("ask before spend", rendered)
            self.assertIn("cloud/object-storage first", rendered)
        finally:
            conn.close()

    def test_registry_marks_landed_free_sources_as_partial_not_planned(self) -> None:
        status_by_id = {s.id: s.status for s in world_catalog.DATA_SOURCES}

        for source_id in ("companies_house", "policy_stack", "pubmed_pmc", "regulatory_health"):
            self.assertEqual(status_by_id[source_id], "partial")
        self.assertEqual(status_by_id["uspto_bulk"], "planned_free")
        self.assertEqual(status_by_id["epo_ops"], "planned_keyed")

    def test_data_status_maps_registry_to_feed_provider_counts(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
                VALUES ('nsf_s',1,'nsf_awards','ai','NSF AI awards','nsf_awards_per_year','awards','science','2024-01-01')
                """
            )
            conn.execute(
                """
                INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
                VALUES ('ai','technology','Artificial intelligence','technology','[]','test','2024-01-01')
                """
            )
            conn.execute(
                """
                INSERT INTO entity_links (
                    id,entity_id,ref_table,ref_id,ref_label,pillar_id,confidence,method,rationale,created_at
                ) VALUES (
                    'ai_nsf','ai','series','nsf_s','NSF AI awards',1,0.9,
                    'auto_exact','Exact fixture series subject','2024-01-01'
                )
                """
            )
            conn.execute(
                """
                INSERT INTO observations (id,series_id,as_of,value,unit,uncertainty,created_at)
                VALUES ('o1','nsf_s','2024-01-01',12,'awards',0,'2024-01-02')
                """
            )
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                feed_dir = root / "feeds"
                feed_dir.mkdir()
                (feed_dir / "nsf_awards.jsonl").write_text('{"x":1}\n{"x":2}\n', encoding="utf-8")
                with mock.patch.object(
                    world_catalog.disk_guard,
                    "usage",
                    return_value={
                        "total_gb": 100.0,
                        "used_gb": 40.0,
                        "free_gb": 60.0,
                        "used_pct": 40.0,
                    },
                ), mock.patch.object(world_catalog.disk_guard, "DEFAULT_MIN_FREE_GB", 50.0):
                    out = world_catalog.data_status(conn, priority=3, feed_dir=feed_dir, repo_root=root)

            nsf = next(row for row in out["sources"] if row["id"] == "nsf_awards")

            self.assertEqual(nsf["feed_rows"], 2)
            self.assertEqual(nsf["db_series"], 1)
            self.assertEqual(nsf["db_observations"], 1)
            self.assertEqual(nsf["entity_links"], 1)
            self.assertEqual(nsf["operational_status"], "ingested_series_only")
            self.assertEqual(nsf["collection_readiness"], "safe_local_collect_available")
            self.assertTrue(nsf["safe_local_refresh"])
            self.assertIn("nsf_awards", out["summary"]["safe_local_refresh_feeds"])
            self.assertTrue(any("timestamped world-state facts" in b for b in nsf["blockers"]))
            self.assertIn("world_state_facts", world_catalog.format_status(out))
        finally:
            conn.close()

    def test_data_status_includes_cost_ledger_summary(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO cost_ledger (
                    id,ts,action,provider,units,est_cost_cents,actual_cost_cents,
                    approval_status,approved_by,funded_ref
                ) VALUES
                    ('c1','2026-01-01','scan','athena',12,125,100,'approved','test',NULL),
                    ('c2','2026-01-01','dry_run','bigquery',20,250,NULL,'pending',NULL,NULL),
                    ('c3','2026-01-01','free','local',1,0,NULL,'auto',NULL,NULL)
                """
            )
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                log_dir = root / "data" / "_collect_logs"
                log_dir.mkdir(parents=True)
                (log_dir / "athena_cost.log").write_text(
                    "first scan 10 GB\nsecond scan 2.5 GB\n",
                    encoding="utf-8",
                )
                (log_dir / "google_patents_cost.log").write_text(
                    "dry run 100 GB\n",
                    encoding="utf-8",
                )
                out = world_catalog.data_status(conn, feed_dir=root, repo_root=root)

            costs = out["cost_ledger"]
            rendered = world_catalog.format_status(out)

            self.assertEqual(costs["entries"], 3)
            self.assertEqual(costs["estimated_usd"], 3.75)
            self.assertEqual(costs["actual_usd"], 1.0)
            self.assertEqual(costs["approved_usd"], 1.25)
            self.assertEqual(costs["pending_usd"], 2.5)
            self.assertEqual(costs["pending_entries"], 1)
            self.assertEqual(costs["pending"][0]["id"], "c2")
            self.assertEqual(costs["pending"][0]["provider"], "bigquery")
            self.assertEqual(costs["pending"][0]["estimated_usd"], 2.5)
            self.assertIn("cost ledger: entries=3 est=$3.75 actual=$1.00", rendered)
            self.assertIn("athena=$1.25", rendered)
            self.assertIn("bigquery=$2.50", rendered)
            self.assertIn("pending costs: c2 bigquery:dry_run $2.50", rendered)
            self.assertEqual(out["scan_logs"]["athena"]["gb_scanned"], 12.5)
            self.assertAlmostEqual(out["scan_logs"]["athena"]["estimated_usd"], 0.0625)
            self.assertEqual(out["scan_logs"]["google_patents_bigquery"]["gb_scanned"], 100.0)
            self.assertIn("scan logs: athena=12.5GB est=$0.06", rendered)
        finally:
            conn.close()

    def test_data_status_includes_action_plan_buckets(self) -> None:
        conn = memory_db()
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                feed_dir = root / "feeds"
                feed_dir.mkdir()
                (feed_dir / "nasa_gistemp.jsonl").write_text('{"x":1}\n', encoding="utf-8")
                (feed_dir / "metaculus.status.json").write_text(
                    json.dumps({
                        "feed": "metaculus",
                        "checked_at": "2026-06-18T00:00:00+00:00",
                        "needs_key": False,
                        "visibility_limited": True,
                        "works": False,
                        "reason": "visible posts; aggregate values hidden",
                        "rows": 0,
                    }),
                    encoding="utf-8",
                )
                out = world_catalog.data_status(conn, priority=4, feed_dir=feed_dir, repo_root=root)

            plan = out["action_plan"]
            rendered = world_catalog.format_status(out)

            self.assertIn("nasa_gistemp", {row["id"] for row in plan["safe_local_refreshable"]})
            self.assertTrue(
                set(out["summary"]["safe_local_due_feeds"]).issubset(
                    set(out["summary"]["safe_local_refresh_feeds"])
                )
            )
            self.assertIn("google_patents", {row["id"] for row in plan["metered_needs_approval"]})
            self.assertIn("prediction_markets", {row["id"] for row in plan["key_or_visibility_blocked"]})
            self.assertIn("wikidata_entities", {row["id"] for row in plan["provider_pipelines"]})
            self.assertIn("uspto_bulk", {row["id"] for row in plan["planned_no_local_collector"]})
            self.assertIn("epo_ops", {row["id"] for row in plan["planned_no_local_collector"]})
            self.assertIn("next-source actions:", rendered)
            self.assertIn("needs approval: google_patents", rendered)
            self.assertIn("--safe-local --stale-only --dry-run", rendered)
            self.assertIn("top-entity missing identifiers:", rendered)
            actions = world_catalog.format_actions(out)
            self.assertIn("World data next actions (read-only)", actions)
            self.assertIn("safe/local preflight:", actions)
            self.assertIn("safe/local due now:", actions)
            self.assertIn("safe/local refreshable later:", actions)
            self.assertIn("metered; needs approval:", actions)
            self.assertIn("P1 google_patents", actions)
            self.assertIn("top-entity identifiers:", actions)
            self.assertIn("top-entity missing identifiers:", actions)
            self.assertIn("company=", actions)
            approvals = world_catalog.approval_plan(out)
            approval_text = world_catalog.format_approval_plan(out)
            google = next(row for row in approvals["metered_needs_approval"] if row["id"] == "google_patents")
            self.assertIn("BigQuery", google["access"])
            self.assertIn("patent facts", google["outputs"])
            self.assertTrue(any("google_patents" in command and "--dry-run" in command for command in google["preflight_commands"]))
            self.assertTrue(any("dry-run" in step for step in google["unblock_steps"]))
            self.assertTrue(google["execution_risk"]["requires_paid_approval"])
            self.assertFalse(google["execution_risk"]["preflight_writes"])
            prediction = next(row for row in approvals["key_or_visibility_blocked"] if row["id"] == "prediction_markets")
            self.assertTrue(any("collect_all" in command and "--dry-run" in command for command in prediction["preflight_commands"]))
            self.assertTrue(any("Metaculus" in step for step in prediction["unblock_steps"]))
            self.assertTrue(prediction["execution_risk"]["requires_key"])
            self.assertTrue(prediction["execution_risk"]["preflight_writes"])
            self.assertIn("Needs spend approval:", approval_text)
            self.assertIn("Needs key/visibility fix:", approval_text)
            self.assertIn("P1 google_patents", approval_text)
            self.assertIn("cost=", approval_text)
            self.assertIn("risk:", approval_text)
            self.assertIn("paid=yes", approval_text)
            self.assertIn("preflight:", approval_text)
            self.assertIn("unblock:", approval_text)
            matrix = world_catalog.source_matrix(out)
            matrix_text = world_catalog.format_source_matrix(matrix, limit=60)
            matrix_csv = world_catalog.source_matrix_csv(matrix)
            matrix_google = next(row for row in matrix["sources"] if row["id"] == "google_patents")
            matrix_prediction = next(row for row in matrix["sources"] if row["id"] == "prediction_markets")
            self.assertGreaterEqual(matrix["summary"]["global_sources"], 1)
            self.assertEqual(matrix_google["coverage_scope"], "global")
            self.assertEqual(matrix_google["cost_posture"], "paid_approval_required")
            self.assertEqual(matrix_google["next_action_type"], "needs_spend_approval")
            self.assertTrue(any("dry-run" in command for command in matrix_google["preflight_commands"]))
            self.assertEqual(matrix_prediction["next_action_type"], "needs_key_or_visibility_fix")
            self.assertIn("World data source matrix", matrix_text)
            self.assertIn("google_patents", matrix_text)
            self.assertIn("id,name,priority,layer", matrix_csv)
            self.assertIn("prediction_markets", matrix_csv)
        finally:
            conn.close()

    def test_entity_identifier_status_summarizes_top_company_backbone(self) -> None:
        conn = memory_db()
        try:
            world_catalog.seed_top_entities(conn, log=lambda *_: None)
            nvda = conn.execute(
                "SELECT id FROM entities WHERE kind='company' AND canonical_name='NVIDIA'"
            ).fetchone()["id"]
            conn.execute(
                """
                INSERT INTO pillars (id,name,description,ord,status)
                VALUES (6,'Fixture','Fixture pillar',6,'active')
                """
            )
            conn.execute(
                """
                INSERT INTO entity_links (
                    id,entity_id,ref_table,ref_id,ref_label,pillar_id,confidence,method,rationale,created_at
                ) VALUES
                    ('nvda_ticker',?,'ticker','NVDA','NVIDIA CORP',6,1.0,'fixture','fixture','2026-01-01'),
                    ('nvda_cik',?,'cik','0001045810','NVIDIA CORP',6,1.0,'fixture','fixture','2026-01-01'),
                    ('nvda_lei',?,'lei','549300S4KLFTLO7GSQ80','NVIDIA CORP',6,1.0,'fixture','fixture','2026-01-01')
                """,
                (nvda, nvda, nvda),
            )

            status = world_catalog.entity_identifier_status(conn, kind="company", missing_only=True)
            rendered = world_catalog.format_entity_identifier_status(status)

            self.assertEqual(status["summary"]["top_entities"], 160)
            self.assertEqual(status["summary"]["seeded"], 160)
            self.assertEqual(status["summary"]["with_any_identifier"], 1)
            self.assertEqual(status["summary"]["missing_identifier"], 159)
            self.assertEqual(status["summary"]["reviewed_missing_identifier"], 0)
            self.assertEqual(status["summary"]["unreviewed_missing_identifier"], 159)
            self.assertEqual(status["summary"]["by_ref_table"]["ticker"], 1)
            self.assertEqual(status["summary"]["by_ref_table"]["cik"], 1)
            self.assertEqual(status["summary"]["by_ref_table"]["lei"], 1)
            self.assertIn("wikidata_qid", status["summary"]["by_ref_table"])
            self.assertNotIn("NVIDIA", {row["name"] for row in status["entities"]})
            self.assertIn("missing identifiers:", rendered)
        finally:
            conn.close()

    def test_entity_identifier_status_marks_reviewed_exact_id_gaps_without_counting_them_as_ids(self) -> None:
        conn = memory_db()
        try:
            world_catalog.seed_top_entities(conn, log=lambda *_: None)

            status = world_catalog.entity_identifier_status(conn, missing_only=True)
            rendered = world_catalog.format_entity_identifier_status(status)
            reviewed = [
                row["name"]
                for row in status["entities"]
                if row["missing_identifier"] and row.get("identifier_gap_review")
            ]

            self.assertEqual(status["summary"]["with_any_identifier"], 0)
            self.assertEqual(status["summary"]["missing_identifier"], 259)
            self.assertEqual(status["summary"]["reviewed_missing_identifier"], 4)
            self.assertEqual(status["summary"]["unreviewed_missing_identifier"], 255)
            self.assertEqual(
                set(reviewed),
                {
                    "Grain-oriented electrical steel",
                    "Grid interconnection",
                    "Radioligand therapy",
                    "mRNA therapeutics",
                },
            )
            self.assertIn("reviewed identifier gaps: 4/259", rendered)
        finally:
            conn.close()

    def test_top_entity_coverage_counts_facts_sources_and_series_links(self) -> None:
        conn = memory_db()
        try:
            world_catalog.seed_top_entities(conn, log=lambda *_: None)
            nvda = conn.execute(
                "SELECT id FROM entities WHERE kind='company' AND canonical_name='NVIDIA'"
            ).fetchone()["id"]
            conn.execute(
                """
                INSERT INTO pillars (id,name,description,ord,status)
                VALUES (6,'Fixture','Fixture pillar',6,'active')
                """
            )
            conn.execute(
                """
                INSERT INTO entity_links (
                    id,entity_id,ref_table,ref_id,ref_label,pillar_id,confidence,method,rationale,created_at
                ) VALUES
                    ('nvda_ticker',?,'ticker','NVDA','NVIDIA',6,1.0,'fixture','fixture','2026-01-01'),
                    ('nvda_series',?,'series','nvda_gpu_capacity','NVIDIA GPU capacity',6,0.9,'fixture','fixture','2026-01-01')
                """,
                (nvda, nvda),
            )
            conn.execute(
                """
                INSERT INTO sources (id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,cost_cents)
                VALUES ('src_nvda','https://example.test/nvda','NVIDIA fixture source',6,
                        'primary',90,'fixture','2024-01-03T00:00:00+00:00',0)
                """
            )
            conn.execute(
                """
                INSERT INTO raw_docs (content_hash,source_id,url,media_type,byte_len,path,fetched_at)
                VALUES ('hash_nvda','src_nvda','https://example.test/nvda',
                        'text/plain',4,'data/raw/hash_nvda.txt','2024-01-03T00:00:00+00:00')
                """
            )
            conn.execute(
                """
                INSERT INTO world_state_facts (
                    id,subject_entity_id,predicate,object_entity_id,value,unit,event_time,
                    published_at,observed_at,ingested_at,source_id,content_hash,confidence,
                    extractor,rationale,supersedes_fact_id,status,created_at
                ) VALUES (
                    'fact_nvda_capacity',?,'ai_gpu_capacity',NULL,1.0,'fact',
                    '2024-01-01','2024-01-02','2024-01-01','2024-01-03T00:00:00+00:00',
                    'src_nvda','hash_nvda',0.9,'fixture','NVIDIA capacity fixture',NULL,'active',
                    '2024-01-03T00:00:00+00:00'
                )
                """,
                (nvda,),
            )

            coverage = world_catalog.top_entity_coverage(conn, kind="company")
            rendered = world_catalog.format_top_entity_coverage(coverage, limit=12)
            csv_text = world_catalog.top_entity_coverage_csv(coverage)
            nvidia = next(row for row in coverage["entities"] if row["name"] == "NVIDIA")
            missing = world_catalog.top_entity_coverage(conn, kind="company", missing_only=True)

            self.assertEqual(coverage["summary"]["top_entities"], 160)
            self.assertEqual(coverage["summary"]["with_facts"], 1)
            self.assertEqual(coverage["summary"]["with_sources"], 1)
            self.assertEqual(nvidia["coverage_status"], "facts_with_sources")
            self.assertEqual(nvidia["active_fact_count"], 1)
            self.assertEqual(nvidia["source_count"], 1)
            self.assertEqual(nvidia["series_links"], 1)
            self.assertEqual(nvidia["identifier_count"], 1)
            self.assertEqual(nvidia["top_predicates"][0]["predicate"], "ai_gpu_capacity")
            self.assertNotIn("NVIDIA", {row["name"] for row in missing["entities"]})
            self.assertIn("Top entity world-state coverage", rendered)
            self.assertIn("kind,name,domain", csv_text)
            self.assertIn("facts_with_sources", csv_text)
        finally:
            conn.close()

    def test_data_status_surfaces_disk_and_prediction_market_blockers(self) -> None:
        conn = memory_db()
        try:
            with tempfile.TemporaryDirectory() as td, mock.patch.object(
                world_catalog.disk_guard,
                "usage",
                return_value={
                    "total_gb": 100.0,
                    "used_gb": 96.0,
                    "free_gb": 4.0,
                    "used_pct": 96.0,
                },
            ), mock.patch.object(world_catalog.disk_guard, "DEFAULT_MIN_FREE_GB", 50.0):
                out = world_catalog.data_status(conn, priority=2, feed_dir=Path(td), repo_root=Path(td))

            prediction = next(row for row in out["sources"] if row["id"] == "prediction_markets")
            openalex = next(row for row in out["sources"] if row["id"] == "openalex_snapshot")

            self.assertFalse(out["disk"]["safe_for_writes"])
            self.assertEqual(openalex["collection_readiness"], "disk_blocked")
            self.assertTrue(any("Metaculus" in b for b in prediction["blockers"]))
            self.assertIn("guard=BLOCKED", world_catalog.format_status(out))
        finally:
            conn.close()

    def test_data_status_surfaces_feed_status_sidecar(self) -> None:
        conn = memory_db()
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                feed_dir = root / "feeds"
                feed_dir.mkdir()
                (feed_dir / "metaculus.status.json").write_text(
                    json.dumps({
                        "feed": "metaculus",
                        "checked_at": "2026-06-18T00:00:00+00:00",
                        "needs_key": True,
                        "works": False,
                        "reason": "fixture auth wall",
                        "rows": 0,
                    }),
                    encoding="utf-8",
                )
                out = world_catalog.data_status(conn, priority=2, feed_dir=feed_dir, repo_root=root)

            prediction = next(row for row in out["sources"] if row["id"] == "prediction_markets")
            metaculus_file = next(f for f in prediction["feed_files"] if f["feed"] == "metaculus")
            rendered = world_catalog.format_status(out)

            self.assertEqual(out["summary"]["feed_diagnostics_blocked"], 1)
            self.assertTrue(metaculus_file["diagnostic"]["needs_key"])
            self.assertEqual(prediction["collection_readiness"], "key_or_visibility_blocked")
            self.assertIn("feed_blocked=1", rendered)
            self.assertIn("feed_blocked=metaculus", rendered)
        finally:
            conn.close()

    def test_data_status_includes_reviewed_series_health_failures(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO series (
                    id,pillar_id,provider,external_id,label,metric,unit,domain,created_at
                ) VALUES (
                    'germany_hs8541',1,'comtrade','comtrade:8541:276',
                    'Semiconductor diodes / photovoltaic cells imports — Germany',
                    'trade_value','USD','trade','2026-01-01T00:00:00+00:00'
                )
                """
            )
            conn.execute(
                """
                INSERT INTO series_health (
                    series_id,status,fresh_status,complete_status,valid_status,recon_status,prov_status,
                    days_stale,n_gaps,n_outliers,n_revisions,health_score,detail,audited_at
                ) VALUES (
                    'germany_hs8541','fail','fail','ok','ok','ok','ok',
                    2361,0,0,0,75.0,'{"fresh":"latest 2019 (7y lag >3)"}',
                    '2026-06-18T00:00:00+00:00'
                )
                """
            )
            conn.commit()
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                out = world_catalog.data_status(conn, feed_dir=root, repo_root=root)

            health = out["series_health"]
            rendered = world_catalog.format_status(out)
            actions = world_catalog.format_actions(out)

            self.assertEqual(health["fail"], 1)
            self.assertEqual(health["reviewed_failures"], 1)
            self.assertEqual(health["unreviewed_failures"], 0)
            self.assertEqual(health["reviewed_failure_providers"], {"comtrade": 1})
            self.assertEqual(
                health["failures"][0]["health_failure_review"]["status"],
                "reviewed_upstream_source_limit",
            )
            self.assertIn("series health: ok=0 warn=0 fail=1 reviewed_failures=1 unreviewed_failures=0", rendered)
            self.assertIn("series health: ok=0 warn=0 fail=1 reviewed_failures=1 unreviewed_failures=0", actions)
            self.assertIn("| comtrade=1", rendered)
            self.assertIn("| comtrade=1", actions)
        finally:
            conn.close()

    def test_data_status_surfaces_keyed_heavy_and_paid_blockers(self) -> None:
        conn = memory_db()
        try:
            with tempfile.TemporaryDirectory() as td:
                out = world_catalog.data_status(conn, feed_dir=Path(td), repo_root=Path(td))

            epo = next(row for row in out["sources"] if row["id"] == "epo_ops")
            common_crawl = next(row for row in out["sources"] if row["id"] == "common_crawl_news")
            talent = next(row for row in out["sources"] if row["id"] == "talent_stack")
            shipping = next(row for row in out["sources"] if row["id"] == "shipping_satellite")

            self.assertTrue(any("API key/terms" in b for b in epo["blockers"]))
            self.assertIn("patentsview", out["summary"]["keyed_feeds"])
            self.assertNotIn("patentsview", out["summary"]["metered_feeds"])
            self.assertTrue(any("cloud-first/object-storage-first" in b for b in common_crawl["blockers"]))
            self.assertTrue(any("mixed source" in b for b in talent["blockers"]))
            self.assertTrue(any("paid/alt-data" in b for b in shipping["blockers"]))
        finally:
            conn.close()

    def test_data_status_treats_visibility_limited_feed_as_blocked(self) -> None:
        conn = memory_db()
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                feed_dir = root / "feeds"
                feed_dir.mkdir()
                (feed_dir / "metaculus.status.json").write_text(
                    json.dumps({
                        "feed": "metaculus",
                        "checked_at": "2026-06-18T00:00:00+00:00",
                        "needs_key": False,
                        "visibility_limited": True,
                        "works": False,
                        "reason": "visible posts; aggregate values hidden",
                        "rows": 0,
                    }),
                    encoding="utf-8",
                )
                out = world_catalog.data_status(conn, priority=2, feed_dir=feed_dir, repo_root=root)

            prediction = next(row for row in out["sources"] if row["id"] == "prediction_markets")

            self.assertEqual(prediction["collection_readiness"], "key_or_visibility_blocked")
            self.assertFalse(prediction["safe_local_refresh"])
            self.assertNotIn("metaculus", out["summary"]["safe_local_refresh_feeds"])
            self.assertEqual(out["summary"]["feed_diagnostics_blocked"], 1)
            self.assertIn("--safe-local --stale-only --dry-run", out["summary"]["safe_local_dry_run_command"])
        finally:
            conn.close()

    def test_data_status_summary_does_not_mark_whole_mixed_bundle_slow(self) -> None:
        conn = memory_db()
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                feed_dir = root / "feeds"
                feed_dir.mkdir()
                for feed in ("world_bank", "imf", "oecd", "eurostat"):
                    (feed_dir / f"{feed}.jsonl").write_text('{"x":1}\n', encoding="utf-8")
                out = world_catalog.data_status(conn, priority=2, feed_dir=feed_dir, repo_root=root)

            self.assertIn("world_bank", out["summary"]["slow_keyless_feeds"])
            self.assertNotIn("imf", out["summary"]["slow_keyless_feeds"])
            self.assertNotIn("oecd", out["summary"]["slow_keyless_feeds"])
            self.assertNotIn("eurostat", out["summary"]["slow_keyless_feeds"])
            self.assertIn("imf", out["summary"]["safe_local_refresh_feeds"])
            self.assertIn("oecd", out["summary"]["safe_local_refresh_feeds"])
            self.assertIn("eurostat", out["summary"]["safe_local_refresh_feeds"])
        finally:
            conn.close()

    def test_data_status_counts_non_feed_entity_backbone_sources(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
                VALUES ('nvda','company','NVIDIA','semiconductors','[]','test','2024-01-01')
                """
            )
            conn.execute(
                """
                INSERT INTO sources (
                    id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,content_hash
                ) VALUES (
                    'gleifsrc','https://api.gleif.org/api/v1/lei-records','GLEIF LEI Records API',
                    1,'primary',95,'Official GLEIF fixture','2024-01-01','gleifhash'
                )
                """
            )
            conn.execute(
                """
                INSERT INTO raw_docs (content_hash,source_id,url,media_type,byte_len,path,fetched_at)
                VALUES ('gleifhash','gleifsrc','https://api.gleif.org/api/v1/lei-records',
                        'application/json',2,'data/raw/xx/gleifhash.json','2024-01-01')
                """
            )
            conn.execute(
                """
                INSERT INTO entity_links (
                    id,entity_id,ref_table,ref_id,ref_label,pillar_id,confidence,method,rationale,created_at
                ) VALUES (
                    'l1','nvda','lei','549300S4KLFTLO7GSQ80','NVIDIA CORPORATION',1,0.98,
                    'gleif_legal_name','Official active LEI fixture','2024-01-01'
                )
                """
            )
            with tempfile.TemporaryDirectory() as td, mock.patch.object(
                world_catalog.disk_guard,
                "usage",
                return_value={
                    "total_gb": 100.0,
                    "used_gb": 30.0,
                    "free_gb": 70.0,
                    "used_pct": 30.0,
                },
            ), mock.patch.object(world_catalog.disk_guard, "DEFAULT_MIN_FREE_GB", 50.0):
                out = world_catalog.data_status(conn, priority=1, feed_dir=Path(td), repo_root=Path(td))

            gleif = next(row for row in out["sources"] if row["id"] == "gleif")

            self.assertEqual(gleif["operational_status"], "entity_backbone_landed")
            self.assertEqual(gleif["collection_readiness"], "provider_pipeline_landed")
            self.assertIn("world-entity-enrich-gleif", gleif["collection_command"])
            self.assertEqual(gleif["auxiliary_records"], 1)
            self.assertEqual(gleif["entity_links"], 1)
            self.assertEqual(gleif["source_records"], 1)
            self.assertEqual(gleif["source_records_with_raw"], 1)
            self.assertTrue(any("not a numeric/fact" in b for b in gleif["blockers"]))
            self.assertIn("command: python3 -m engine.cli world-entity-enrich-gleif", world_catalog.format_status(out))
        finally:
            conn.close()

    def test_data_status_counts_gated_provider_sources_and_facts(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO sources (
                    id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,content_hash
                ) VALUES (
                    'pat_src','https://patents.google.com/xhr/query?url=q%3Dtest',
                    'Google Patents fixture',1,'primary',80,'fixture','2024-01-01','pathash'
                )
                """
            )
            conn.execute(
                """
                INSERT INTO raw_docs (content_hash,source_id,url,media_type,byte_len,path,fetched_at)
                VALUES ('pathash','pat_src','https://patents.google.com/xhr/query?url=q%3Dtest',
                        'application/json',2,'data/raw/xx/pathash.json','2024-01-01')
                """
            )
            conn.execute(
                """
                INSERT INTO series (
                    id,pillar_id,source_id,provider,external_id,label,metric,unit,domain,created_at
                ) VALUES (
                    'pat_series',1,'pat_src','google_patents','solid state battery',
                    'solid state battery patents','patents_per_priority_year','patents/year','patents','2024-01-01'
                )
                """
            )
            conn.execute(
                """
                INSERT INTO observations (id,series_id,as_of,value,unit,uncertainty,created_at)
                VALUES ('pat_obs','pat_series','2023-01-01',42,'patents/year',0,'2024-01-02')
                """
            )
            conn.execute(
                """
                INSERT INTO world_state_facts (
                    id,predicate,value,unit,event_time,published_at,observed_at,ingested_at,
                    source_id,content_hash,confidence,extractor,rationale,status,created_at
                ) VALUES (
                    'pat_fact','observed patents_per_priority_year',42,'patents/year','2023-01-01',
                    '2023-01-01','2023-01-01','2024-01-02','pat_src','pathash',0.8,
                    'series_observation_v1','fixture fact','active','2024-01-02'
                )
                """
            )
            with tempfile.TemporaryDirectory() as td, mock.patch.object(
                world_catalog.disk_guard,
                "usage",
                return_value={
                    "total_gb": 100.0,
                    "used_gb": 30.0,
                    "free_gb": 70.0,
                    "used_pct": 30.0,
                },
            ), mock.patch.object(world_catalog.disk_guard, "DEFAULT_MIN_FREE_GB", 50.0):
                out = world_catalog.data_status(conn, priority=1, feed_dir=Path(td), repo_root=Path(td))

            patents = next(row for row in out["sources"] if row["id"] == "google_patents")

            self.assertEqual(patents["operational_status"], "queryable_world_state")
            self.assertEqual(patents["db_series"], 1)
            self.assertEqual(patents["db_observations"], 1)
            self.assertEqual(patents["world_state_facts"], 1)
            self.assertEqual(patents["source_records"], 1)
            self.assertEqual(patents["source_records_with_raw"], 1)
            self.assertEqual(patents["collection_readiness"], "metered_needs_approval")
            self.assertIn("google_patents", out["summary"]["metered_feeds"])
            self.assertNotIn("patentsview", out["summary"]["metered_feeds"])
        finally:
            conn.close()

    def test_data_status_marks_oversized_local_feed_as_cloud_first(self) -> None:
        conn = memory_db()
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                feed_dir = root / "feeds"
                feed_dir.mkdir()
                (feed_dir / "fred_financial.jsonl").write_text('{"x":"' + ("y" * 4096) + '"}\n', encoding="utf-8")
                out = world_catalog.data_status(
                    conn,
                    priority=1,
                    feed_dir=feed_dir,
                    repo_root=root,
                    max_local_refresh_mb=0.001,
                )

            fred = next(row for row in out["sources"] if row["id"] == "fred_financial")

            self.assertEqual(fred["collection_readiness"], "local_file_too_large_use_cloud_first")
            self.assertFalse(fred["safe_local_refresh"])
            self.assertNotIn("fred_financial", out["summary"]["safe_local_refresh_feeds"])
        finally:
            conn.close()

    def test_arxiv_provider_only_status_counts_existing_series_without_feed_blocker(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO sources (
                    id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,content_hash,
                    raw_provenance_status
                ) VALUES (
                    'arxiv_src','https://export.arxiv.org/oai2?verb=ListRecords',
                    'arXiv topic fixture',1,'primary',80,'fixture','2024-01-01','arxivhash',
                    'legacy_hash_no_raw_doc'
                )
                """
            )
            conn.execute(
                """
                INSERT INTO series (
                    id,pillar_id,source_id,provider,external_id,label,metric,unit,domain,created_at
                ) VALUES (
                    'arxiv_series',1,'arxiv_src','arxiv','deep learning|topic_share',
                    'arXiv topic share - deep learning','topic_share','share','arxiv_topic','2024-01-01'
                )
                """
            )
            conn.execute(
                """
                INSERT INTO observations (id,series_id,as_of,value,unit,uncertainty,created_at)
                VALUES ('arxiv_obs','arxiv_series','2023-12-31',0.12,'share',0,'2024-01-02')
                """
            )
            conn.execute(
                """
                INSERT INTO world_state_facts (
                    id,predicate,value,unit,event_time,published_at,observed_at,ingested_at,
                    source_id,confidence,extractor,rationale,status,created_at
                ) VALUES (
                    'arxiv_fact','observed topic_share',0.12,'share','2023-12-31',
                    '2023-12-31','2023-12-31','2024-01-02','arxiv_src',0.8,
                    'fixture','fixture','active','2024-01-02'
                )
                """
            )
            with tempfile.TemporaryDirectory() as td:
                out = world_catalog.data_status(conn, priority=2, feed_dir=Path(td), repo_root=Path(td))

            arxiv = next(row for row in out["sources"] if row["id"] == "arxiv")

            self.assertEqual(arxiv["operational_status"], "queryable_world_state")
            self.assertEqual(arxiv["db_series"], 1)
            self.assertEqual(arxiv["world_state_facts"], 1)
            self.assertEqual(arxiv["collection_readiness"], "provider_pipeline_landed")
            self.assertEqual(arxiv["provider_only"], ["arxiv"])
            self.assertFalse(any("ingest metadata missing" in b for b in arxiv["blockers"]))
            self.assertFalse(any("collector not implemented" in b for b in arxiv["blockers"]))
        finally:
            conn.close()

    def test_data_status_distinguishes_legacy_raw_gap_from_unclassified_provenance(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO sources (
                    id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,content_hash,
                    raw_provenance_status,raw_provenance_reason,raw_provenance_checked_at
                ) VALUES (
                    'sec_legacy','https://www.sec.gov/Archives/fixture.json',
                    'SEC legacy fixture',1,'primary',90,'fixture','2024-01-01','legacyhash',
                    'legacy_hash_no_raw_doc','fixture legacy gap','2026-06-18'
                )
                """
            )
            conn.execute(
                """
                INSERT INTO series (
                    id,pillar_id,source_id,provider,external_id,label,metric,unit,domain,created_at
                ) VALUES (
                    'sec_series',1,'sec_legacy','sec_edgar','fixture',
                    'SEC fixture','capex_usd','USD/year','corporate','2024-01-01'
                )
                """
            )
            conn.execute(
                """
                INSERT INTO observations (id,series_id,as_of,value,unit,uncertainty,created_at)
                VALUES ('sec_obs','sec_series','2023-12-31',10,'USD/year',0,'2024-01-02')
                """
            )
            conn.execute(
                """
                INSERT INTO world_state_facts (
                    id,predicate,value,unit,event_time,published_at,observed_at,ingested_at,
                    source_id,confidence,extractor,rationale,status,created_at
                ) VALUES (
                    'sec_fact','observed capex_usd',10,'USD/year','2023-12-31',
                    '2023-12-31','2023-12-31','2024-01-02','sec_legacy',0.8,
                    'fixture','fixture','active','2024-01-02'
                )
                """
            )
            with tempfile.TemporaryDirectory() as td:
                out = world_catalog.data_status(conn, priority=1, feed_dir=Path(td), repo_root=Path(td))

            sec = next(row for row in out["sources"] if row["id"] == "sec_edgar")

            self.assertEqual(sec["source_records_legacy_raw_gap"], 1)
            self.assertEqual(sec["source_records_unclassified_raw"], 0)
            self.assertTrue(any("legacy raw-byte gaps remain" in b for b in sec["blockers"]))
            self.assertFalse(any("unclassified" in b for b in sec["blockers"]))
        finally:
            conn.close()

    def test_data_status_keeps_unclassified_raw_provenance_as_blocker(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO sources (
                    id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,content_hash
                ) VALUES (
                    'sec_unknown','https://www.sec.gov/Archives/unknown.json',
                    'SEC unknown fixture',1,'primary',90,'fixture','2024-01-01','unknownhash'
                )
                """
            )
            conn.execute(
                """
                INSERT INTO series (
                    id,pillar_id,source_id,provider,external_id,label,metric,unit,domain,created_at
                ) VALUES (
                    'sec_unknown_series',1,'sec_unknown','sec_edgar','unknown',
                    'SEC unknown fixture','capex_usd','USD/year','corporate','2024-01-01'
                )
                """
            )
            conn.execute(
                """
                INSERT INTO observations (id,series_id,as_of,value,unit,uncertainty,created_at)
                VALUES ('sec_unknown_obs','sec_unknown_series','2023-12-31',10,'USD/year',0,'2024-01-02')
                """
            )
            conn.execute(
                """
                INSERT INTO world_state_facts (
                    id,predicate,value,unit,event_time,published_at,observed_at,ingested_at,
                    source_id,confidence,extractor,rationale,status,created_at
                ) VALUES (
                    'sec_unknown_fact','observed capex_usd',10,'USD/year','2023-12-31',
                    '2023-12-31','2023-12-31','2024-01-02','sec_unknown',0.8,
                    'fixture','fixture','active','2024-01-02'
                )
                """
            )
            with tempfile.TemporaryDirectory() as td:
                out = world_catalog.data_status(conn, priority=1, feed_dir=Path(td), repo_root=Path(td))

            sec = next(row for row in out["sources"] if row["id"] == "sec_edgar")

            self.assertEqual(sec["source_records_unclassified_raw"], 1)
            self.assertTrue(any("unclassified" in b for b in sec["blockers"]))
        finally:
            conn.close()

    def test_semantic_scholar_manifest_keeps_full_dataset_blocker(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO sources (id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at)
                VALUES ('s2ag_src','https://api.semanticscholar.org/datasets/v1/release/latest',
                        'Semantic Scholar fixture',1,'primary',88,'fixture','2026-06-09')
                """
            )
            conn.execute(
                """
                INSERT INTO series (id,pillar_id,source_id,provider,external_id,label,metric,unit,domain,created_at)
                VALUES ('s2ag_s',1,'s2ag_src','semantic_scholar','semantic_scholar:release:dataset_count',
                        'Semantic Scholar S2AG - datasets in latest release',
                        's2ag_dataset_count','datasets','research','2026-06-09')
                """
            )
            conn.execute(
                """
                INSERT INTO observations (id,series_id,as_of,value,unit,uncertainty,created_at)
                VALUES ('s2ag_o','s2ag_s','2026-06-09',11,'datasets',0,'2026-06-09')
                """
            )
            conn.execute(
                """
                INSERT INTO world_state_facts
                    (id,predicate,value,unit,event_time,published_at,observed_at,ingested_at,source_id,
                     confidence,extractor,rationale,status,created_at)
                VALUES
                    ('s2ag_f','observed s2ag_dataset_count',11,'datasets','2026-06-09',
                     '2026-06-09','2026-06-09','2026-06-09T00:00:00+00:00','s2ag_src',
                     0.88,'fixture','fixture','active','2026-06-09T00:00:00+00:00')
                """
            )
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                feed_dir = root / "feeds"
                feed_dir.mkdir()
                (feed_dir / "semantic_scholar.jsonl").write_text('{"x":1}\n', encoding="utf-8")
                out = world_catalog.data_status(conn, priority=3, feed_dir=feed_dir, repo_root=root)

            s2 = next(row for row in out["sources"] if row["id"] == "semantic_scholar")

            self.assertEqual(s2["operational_status"], "queryable_world_state")
            self.assertTrue(any("only release manifest is landed" in b for b in s2["blockers"]))
        finally:
            conn.close()

    def test_research_layer_status_splits_world_state_papers_and_processing_policy(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO sources (
                    id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,content_hash
                ) VALUES (
                    'openalex_src','https://api.openalex.org/works',
                    'OpenAlex fixture',1,'primary',92,'fixture','2024-01-02','openalexhash'
                )
                """
            )
            conn.execute(
                """
                INSERT INTO raw_docs (content_hash,source_id,url,media_type,byte_len,path,fetched_at)
                VALUES ('openalexhash','openalex_src','https://api.openalex.org/works',
                        'application/json',2,'data/raw/xx/openalexhash.json','2024-01-02')
                """
            )
            conn.execute(
                """
                INSERT INTO series (
                    id,pillar_id,source_id,provider,external_id,label,metric,unit,domain,created_at
                ) VALUES (
                    'openalex_series',1,'openalex_src','openalex','C41008148',
                    'OpenAlex AI works','publication_count','works','research','2024-01-02'
                )
                """
            )
            conn.execute(
                """
                INSERT INTO observations (id,series_id,as_of,value,unit,uncertainty,created_at)
                VALUES ('openalex_obs','openalex_series','2023-12-31',100,'works',0,'2024-01-02')
                """
            )
            conn.execute(
                """
                INSERT INTO world_state_facts (
                    id,predicate,value,unit,event_time,published_at,observed_at,ingested_at,
                    source_id,content_hash,confidence,extractor,rationale,status,created_at
                ) VALUES (
                    'openalex_fact','observed publication_count',100,'works','2023-12-31',
                    '2024-01-01','2023-12-31','2024-01-02T00:00:00+00:00',
                    'openalex_src','openalexhash',0.9,'fixture','fixture','active',
                    '2024-01-02T00:00:00+00:00'
                )
                """
            )
            conn.execute(
                """
                INSERT INTO papers (
                    id,provider,external_id,published,updated,primary_category,categories,title,
                    abstract,authors,n_authors,content_hash,fetched_at
                ) VALUES
                    ('paper1','arxiv','2301.00001','2023-01-01',NULL,'cs.AI','cs.AI',
                     'Fixture one','Abstract','A',1,'arxivhash1','2023-01-02'),
                    ('paper2','arxiv','2401.00001','2024-01-01',NULL,'cs.LG','cs.LG',
                     'Fixture two','Abstract','B',1,'arxivhash2','2024-01-02')
                """
            )
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                out = world_catalog.research_layer_status(conn, feed_dir=root, repo_root=root)

            by_id = {row["id"]: row for row in out["sources"]}
            rendered = world_catalog.format_research_layer_status(out)
            csv_text = world_catalog.research_layer_status_csv(out)

            self.assertGreaterEqual(out["summary"]["sources"], 6)
            self.assertGreaterEqual(out["summary"]["global_sources"], 1)
            self.assertEqual(by_id["openalex_snapshot"]["llm_query_status"], "state_pack_ready")
            self.assertEqual(by_id["openalex_snapshot"]["time_query_status"], "as_of_world_state")
            self.assertEqual(by_id["openalex_snapshot"]["fact_timeline"]["published_start"], "2024-01-01")
            self.assertEqual(by_id["arxiv"]["time_query_status"], "paper_metadata_timeline")
            self.assertEqual(by_id["arxiv"]["llm_query_status"], "metadata_hashes_ready_for_extraction")
            self.assertEqual(by_id["arxiv"]["paper_stats"]["papers"], 2)
            self.assertEqual(by_id["arxiv"]["paper_stats"]["published_end"], "2024-01-01")
            self.assertEqual(by_id["arxiv"]["next_policy"], "storage_ok_keep_bulk_off_laptop")
            self.assertTrue(any("Semantic Scholar" in b for b in out["blockers"]))
            self.assertIn("approval", out["summary"]["processing_policy"])
            self.assertIn("world-state", " ".join(i["command"] for i in out["query_interfaces"]))
            self.assertIn("world-research-profile", " ".join(i["command"] for i in out["query_interfaces"]))
            self.assertIn("world-research-plan", " ".join(i["command"] for i in out["query_interfaces"]))
            self.assertIn("world-research-provenance", " ".join(i["command"] for i in out["query_interfaces"]))
            self.assertIn("Research layer status", rendered)
            self.assertIn("llm_query_status", csv_text)
        finally:
            conn.close()

    def test_research_provenance_gaps_report_exact_legacy_and_missing_raw(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO sources (
                    id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,
                    content_hash,raw_provenance_status,raw_provenance_reason
                ) VALUES
                    ('openalex_src','https://api.openalex.org/works','OpenAlex fixture',1,
                     'primary',92,'fixture','2024-01-02','openalexhash','exact_raw_doc','fixture exact'),
                    ('arxiv_src','https://export.arxiv.org/api/query','arXiv fixture',1,
                     'primary',85,'fixture','2024-01-02','arxivhash','legacy_hash_no_raw_doc','fixture legacy'),
                    ('crossref_src','https://api.crossref.org/works','Crossref fixture',1,
                     'primary',80,'fixture','2024-01-02',NULL,'legacy_no_content_hash','fixture legacy')
                """
            )
            conn.execute(
                """
                INSERT INTO raw_docs (content_hash,source_id,url,media_type,byte_len,path,fetched_at)
                VALUES ('openalexhash','openalex_src','https://api.openalex.org/works',
                        'application/json',2,'data/raw/xx/openalexhash.json','2024-01-02')
                """
            )
            conn.execute(
                """
                INSERT INTO series (
                    id,pillar_id,source_id,provider,external_id,label,metric,unit,domain,created_at
                ) VALUES
                    ('openalex_series',1,'openalex_src','openalex','C41008148',
                     'OpenAlex AI works','publication_count','works','research','2024-01-02'),
                    ('arxiv_series',1,'arxiv_src','arxiv','cs.AI',
                     'arXiv AI papers','publication_count','papers','research','2024-01-02'),
                    ('crossref_series',1,'crossref_src','crossref','ai',
                     'Crossref AI papers','publication_count','works','research','2024-01-02')
                """
            )
            conn.execute(
                """
                INSERT INTO world_state_facts (
                    id,predicate,value,unit,event_time,published_at,observed_at,ingested_at,
                    source_id,content_hash,confidence,extractor,rationale,status,created_at
                ) VALUES
                    ('openalex_fact','observed publication_count',100,'works','2023-12-31',
                     '2024-01-01','2023-12-31','2024-01-02T00:00:00+00:00',
                     'openalex_src','openalexhash',0.9,'fixture_bridge','fixture','active',
                     '2024-01-02T00:00:00+00:00'),
                    ('arxiv_fact','observed arxiv_publication_count',25,'papers','2023-12-31',
                     '2024-01-01','2023-12-31','2024-01-02T00:00:00+00:00',
                     'arxiv_src',NULL,0.8,'fixture_bridge','fixture','active',
                     '2024-01-02T00:00:00+00:00'),
                    ('crossref_fact','observed works_published',9,'works','2023-12-31',
                     '2024-01-01','2023-12-31','2024-01-02T00:00:00+00:00',
                     'crossref_src',NULL,0.8,'fixture_bridge','fixture','active',
                     '2024-01-02T00:00:00+00:00')
                """
            )

            report = world_catalog.research_provenance_gaps(conn, limit=10)
            rendered = world_catalog.format_research_provenance_gaps(report, limit=10)

            self.assertTrue(report["ok"])
            self.assertEqual(report["summary"]["source_records"], 3)
            self.assertEqual(report["summary"]["source_records_with_content_hash"], 2)
            self.assertEqual(report["summary"]["source_records_with_raw_doc"], 1)
            self.assertEqual(report["summary"]["source_records_legacy_raw_gap"], 2)
            self.assertEqual(report["summary"]["facts"], 3)
            self.assertEqual(report["summary"]["facts_with_content_hash"], 1)
            self.assertEqual(report["summary"]["facts_with_raw_doc"], 1)
            self.assertEqual(report["summary"]["facts_missing_content_hash"], 2)
            self.assertEqual(report["summary"]["facts_hash_without_raw_doc"], 0)
            self.assertEqual(report["summary"]["exact_fact_raw_doc_coverage_pct"], 33.33)
            by_source = {row["source_id"]: row for row in report["fact_gaps_by_source"]}
            self.assertEqual(by_source["arxiv_src"]["facts_missing_content_hash"], 1)
            self.assertEqual(by_source["crossref_src"]["facts_missing_content_hash"], 1)
            predicates = {row["predicate"]: row for row in report["fact_gaps_by_predicate"]}
            self.assertIn("observed arxiv_publication_count", predicates)
            self.assertIn("observed works_published", predicates)
            self.assertTrue(any("rawstore.put" in action for action in report["actions"]))
            self.assertIn("Research provenance gaps", rendered)
            self.assertIn("source gaps:", rendered)
            self.assertIn("predicate gaps:", rendered)
        finally:
            conn.close()

    def test_research_coverage_profile_reports_diversity_time_and_provenance(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO sources (
                    id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,content_hash
                ) VALUES
                    ('openalex_src','https://api.openalex.org/works','OpenAlex fixture',1,
                     'primary',92,'fixture','2024-01-02','openalexhash'),
                    ('arxiv_src','https://export.arxiv.org/api/query','arXiv fixture',1,
                     'primary',85,'fixture','2024-01-02',NULL)
                """
            )
            conn.execute(
                """
                INSERT INTO raw_docs (content_hash,source_id,url,media_type,byte_len,path,fetched_at)
                VALUES ('openalexhash','openalex_src','https://api.openalex.org/works',
                        'application/json',2,'data/raw/xx/openalexhash.json','2024-01-02')
                """
            )
            conn.execute(
                """
                INSERT INTO series (
                    id,pillar_id,source_id,provider,external_id,label,metric,unit,domain,created_at
                ) VALUES
                    ('openalex_series',1,'openalex_src','openalex','C41008148',
                     'OpenAlex AI works','publication_count','works','research','2024-01-02'),
                    ('arxiv_series',1,'arxiv_src','arxiv','cs.AI',
                     'arXiv AI papers','publication_count','papers','research','2024-01-02')
                """
            )
            conn.execute(
                """
                INSERT INTO observations (id,series_id,as_of,value,unit,uncertainty,created_at)
                VALUES
                    ('openalex_obs','openalex_series','2023-12-31',100,'works',0,'2024-01-02'),
                    ('arxiv_obs','arxiv_series','2023-12-31',25,'papers',0,'2024-01-02')
                """
            )
            conn.execute(
                """
                INSERT INTO world_state_facts (
                    id,predicate,value,unit,event_time,published_at,observed_at,ingested_at,
                    source_id,content_hash,confidence,extractor,rationale,status,created_at
                ) VALUES
                    ('openalex_fact','observed publication_count',100,'works','2023-12-31',
                     '2024-01-01','2023-12-31','2024-01-02T00:00:00+00:00',
                     'openalex_src','openalexhash',0.9,'fixture_bridge','fixture','active',
                     '2024-01-02T00:00:00+00:00'),
                    ('arxiv_fact','observed arxiv_publication_count',25,'papers','2023-12-31',
                     '2024-01-01','2023-12-31','2024-01-02T00:00:00+00:00',
                     'arxiv_src',NULL,0.8,'fixture_bridge','fixture','active',
                     '2024-01-02T00:00:00+00:00')
                """
            )
            conn.execute(
                """
                INSERT INTO papers (
                    id,provider,external_id,published,updated,primary_category,categories,title,
                    abstract,authors,n_authors,content_hash,fetched_at
                ) VALUES
                    ('paper1','arxiv','2301.00001','2023-01-01',NULL,'cs.AI','cs.AI',
                     'Fixture AI one','Abstract','A',1,'h1','2023-01-02'),
                    ('paper2','arxiv','2301.00002','2023-06-01',NULL,'cs.LG','cs.LG',
                     'Fixture AI two','Abstract','B',1,'h2','2023-06-02'),
                    ('paper3','pubmed','PMID1','2022-01-01',NULL,'medicine','medicine',
                     'Fixture biomed','Abstract','C',1,'h3','2022-01-02')
                """
            )

            profile = world_catalog.research_coverage_profile(conn, limit=10, include_paper_groups=True)
            rendered = world_catalog.format_research_coverage_profile(profile, limit=5)

            self.assertTrue(profile["ok"])
            self.assertEqual(profile["summary"]["papers"], 3)
            self.assertEqual(profile["summary"]["paper_providers"], 2)
            self.assertEqual(profile["summary"]["paper_primary_categories"], 3)
            self.assertTrue(profile["summary"]["paper_groups_complete"])
            self.assertEqual(profile["summary"]["research_facts"], 2)
            self.assertEqual(profile["summary"]["research_fact_predicates"], 2)
            self.assertEqual(profile["summary"]["research_facts_with_raw_doc"], 1)
            providers = {row["provider"]: row for row in profile["papers"]["by_provider"]}
            self.assertEqual(providers["arxiv"]["papers"], 2)
            self.assertEqual(providers["pubmed"]["papers"], 1)
            categories = {row["primary_category"]: row for row in profile["papers"]["by_primary_category"]}
            self.assertEqual(categories["cs.AI"]["papers"], 1)
            years = {row["year"]: row for row in profile["papers"]["by_year"]}
            self.assertEqual(years["2023"]["papers"], 2)
            predicates = {row["predicate"]: row for row in profile["facts"]["by_predicate"]}
            self.assertIn("observed publication_count", predicates)
            self.assertTrue(any("raw-byte coverage" in gap for gap in profile["gaps"]))
            self.assertTrue(any("approval" in gap for gap in profile["gaps"]))
            self.assertIn("Research coverage profile", rendered)
            self.assertIn("paper providers:", rendered)
            self.assertIn("top fact predicates:", rendered)
        finally:
            conn.close()

    def test_research_coverage_profile_default_avoids_full_status_scan(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO papers (
                    id,provider,external_id,published,updated,primary_category,categories,title,
                    abstract,authors,n_authors,content_hash,fetched_at
                ) VALUES
                    ('paper1','arxiv','2301.00001','2023-01-01',NULL,'cs.AI','cs.AI',
                     'Fixture AI one','Abstract','A',1,'h1','2023-01-02')
                """
            )
            with mock.patch.object(
                world_catalog,
                "research_layer_status",
                side_effect=AssertionError("heavy status path should be opt-in"),
            ):
                profile = world_catalog.research_coverage_profile(conn, limit=5)

            self.assertEqual(profile["summary"]["papers"], 1)
            self.assertIsNone(profile["summary"]["papers_with_hash"])
            self.assertFalse(profile["summary"]["paper_groups_complete"])
            self.assertFalse(profile["summary"]["source_status_complete"])
            self.assertTrue(any("fast profile mode" in gap for gap in profile["gaps"]))
            rendered = world_catalog.format_research_coverage_profile(profile, limit=5)
            self.assertIn("paper_hashes=not_counted", rendered)
        finally:
            conn.close()

    def test_top_entities_are_unique_and_cover_core_kinds(self) -> None:
        keys = [(e.kind, e.name) for e in world_catalog.TOP_ENTITIES]
        kinds = {e.kind for e in world_catalog.TOP_ENTITIES}
        names = {e.name for e in world_catalog.TOP_ENTITIES}

        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue({"country_region", "company", "technology", "material"}.issubset(kinds))
        self.assertIn("China", names)
        self.assertIn("NVIDIA", names)
        self.assertIn("Oracle", names)
        self.assertIn("Anthropic", names)
        self.assertIn("State Grid Corporation of China", names)
        self.assertIn("Linde", names)
        self.assertIn("A.P. Moller - Maersk", names)
        self.assertIn("Lockheed Martin", names)
        aliases_by_name = {e.name: e.aliases for e in world_catalog.TOP_ENTITIES}
        self.assertIn("Catalent Pharma Solutions", aliases_by_name["Catalent"])
        self.assertIn("LS Industrial Systems", aliases_by_name["LS Electric"])
        self.assertIn("LONGi Green Energy Technology", aliases_by_name["LONGi Green Energy"])
        self.assertIn("Federal Reserve System", aliases_by_name["Federal Reserve"])
        self.assertIn("large language model", aliases_by_name["Large language models"])
        self.assertIn("power transformer", aliases_by_name["Power transformers"])
        self.assertIn("reusable launch vehicle", aliases_by_name["Reusable launch"])
        msc = next(e for e in world_catalog.TOP_ENTITIES if e.name == "MSC Mediterranean Shipping Company")
        self.assertNotIn("MSC", msc.aliases)
        self.assertIn("Mediterranean Shipping Company", msc.aliases)
        self.assertIn("International Energy Agency", names)
        self.assertIn("Copper", names)
        self.assertIn("institution", kinds)
        self.assertTrue(all(e["kind"] == "material" for e in world_catalog.top_entities(kind="material")))

    def test_top_entity_seed_is_idempotent_and_preserves_existing_notes(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
                VALUES ('existing_nvda','company','NVIDIA','semiconductors','[]','keep this richer note','2024-01-01')
                """
            )

            first = world_catalog.seed_top_entities(conn, log=lambda *_: None)
            second = world_catalog.seed_top_entities(conn, log=lambda *_: None)
            nvda = conn.execute(
                "SELECT note, aliases FROM entities WHERE kind='company' AND canonical_name='NVIDIA'"
            ).fetchone()

            self.assertGreater(first["created"], 0)
            self.assertEqual(second["created"], 0)
            self.assertEqual(nvda["note"], "keep this richer note")
            self.assertIn("NVDA", nvda["aliases"])
        finally:
            conn.close()

    def test_gleif_best_match_prefers_active_exact_legal_name(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
                VALUES ('nvda','company','NVIDIA','semiconductors','["NVDA"]','test','2024-01-01')
                """
            )
            row = conn.execute("SELECT * FROM entities WHERE id='nvda'").fetchone()
            data = {
                "meta": {"goldenCopy": {"publishDate": "2026-06-17T08:00:00Z"}},
                "data": [
                    {
                        "id": "BAD",
                        "attributes": {
                            "lei": "BAD",
                            "entity": {"legalName": {"name": "NVIDIA INTERNATIONAL, INC."}, "status": "ACTIVE"},
                            "registration": {"status": "ISSUED"},
                        },
                    },
                    {
                        "id": "549300S4KLFTLO7GSQ80",
                        "attributes": {
                            "lei": "549300S4KLFTLO7GSQ80",
                            "entity": {
                                "legalName": {"name": "NVIDIA CORPORATION"},
                                "status": "ACTIVE",
                                "jurisdiction": "US-DE",
                                "registeredAs": "2862596",
                                "legalAddress": {"country": "US"},
                                "headquartersAddress": {"country": "US"},
                            },
                            "registration": {"status": "ISSUED"},
                        },
                    },
                ],
            }

            match = gleif_enrich.best_match(row, data, query="NVIDIA")

            self.assertIsNotNone(match)
            self.assertEqual(match.lei, "549300S4KLFTLO7GSQ80")
            self.assertEqual(match.legal_name, "NVIDIA CORPORATION")
            self.assertGreaterEqual(match.score, 0.9)
        finally:
            conn.close()

    def test_gleif_best_match_rejects_fund_name_containing_company_name(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
                VALUES ('sk','company','SK Hynix','semiconductors','["Hynix"]','test','2024-01-01')
                """
            )
            row = conn.execute("SELECT * FROM entities WHERE id='sk'").fetchone()
            data = {
                "meta": {"goldenCopy": {"publishDate": "2026-06-17T08:00:00Z"}},
                "data": [{
                    "id": "529900LXXAT281IGIR53",
                    "attributes": {
                        "lei": "529900LXXAT281IGIR53",
                        "entity": {
                            "legalName": {"name": "ProShares Ultra SK hynix"},
                            "status": "ACTIVE",
                        },
                        "registration": {"status": "ISSUED"},
                    },
                }],
            }

            match = gleif_enrich.best_match(row, data, query="SK Hynix")

            self.assertIsNone(match)
        finally:
            conn.close()

    def test_gleif_best_match_rejects_bare_one_token_branch_name(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
                VALUES ('tesla','company','Tesla','autos_energy','["TSLA"]','test','2024-01-01')
                """
            )
            row = conn.execute("SELECT * FROM entities WHERE id='tesla'").fetchone()
            data = {
                "meta": {"goldenCopy": {"publishDate": "2026-06-17T08:00:00Z"}},
                "data": [{
                    "id": "969500RFR6THHK28RD81",
                    "attributes": {
                        "lei": "969500RFR6THHK28RD81",
                        "entity": {
                            "legalName": {"name": "TESLA"},
                            "status": "ACTIVE",
                            "jurisdiction": "FR",
                            "headquartersAddress": {"country": "FR"},
                        },
                        "registration": {"status": "ISSUED"},
                    },
                }],
            }

            match = gleif_enrich.best_match(row, data, query="Tesla")

            self.assertIsNone(match)
        finally:
            conn.close()

    def test_gleif_best_match_accepts_exact_legal_alias(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
                VALUES ('tesla','company','Tesla','autos_energy','["Tesla, Inc.", "TSLA"]','test','2024-01-01')
                """
            )
            row = conn.execute("SELECT * FROM entities WHERE id='tesla'").fetchone()
            data = {
                "meta": {"goldenCopy": {"publishDate": "2026-06-17T08:00:00Z"}},
                "data": [{
                    "id": "54930043XZGB27CTOV49",
                    "attributes": {
                        "lei": "54930043XZGB27CTOV49",
                        "entity": {
                            "legalName": {"name": "TESLA, INC."},
                            "status": "ACTIVE",
                            "jurisdiction": "US-TX",
                            "headquartersAddress": {"country": "US"},
                        },
                        "registration": {"status": "ISSUED"},
                    },
                }],
            }

            match = gleif_enrich.best_match(row, data, query="Tesla, Inc.")

            self.assertIsNotNone(match)
            self.assertEqual(match.lei, "54930043XZGB27CTOV49")
        finally:
            conn.close()

    def test_gleif_query_filter_skips_shorter_aliases_for_legal_id_matching(self) -> None:
        queries = gleif_enrich._usable_queries("SK Hynix", ["Hynix", "005930.KS", "SK Hynix Inc"])

        self.assertEqual(queries, ["SK Hynix Inc"])

    def test_gleif_best_match_rejects_lapsed_registration(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
                VALUES ('jinko','company','JinkoSolar','solar','["JinkoSolar Holding Co., Ltd."]','test','2024-01-01')
                """
            )
            row = conn.execute("SELECT * FROM entities WHERE id='jinko'").fetchone()
            data = {
                "meta": {"goldenCopy": {"publishDate": "2026-06-17T08:00:00Z"}},
                "data": [{
                    "id": "529900Y93WNCS05FG852",
                    "attributes": {
                        "lei": "529900Y93WNCS05FG852",
                        "entity": {
                            "legalName": {"name": "JinkoSolar Holding Co., Ltd."},
                            "status": "ACTIVE",
                            "jurisdiction": "KY",
                        },
                        "registration": {"status": "LAPSED"},
                    },
                }],
            }

            match = gleif_enrich.best_match(row, data, query="JinkoSolar Holding Co., Ltd.")

            self.assertIsNone(match)
        finally:
            conn.close()

    def test_gleif_enrichment_updates_aliases_links_and_raw_source(self) -> None:
        conn = memory_db()
        old_fetch = gleif_enrich._fetch
        old_raw_root = rawstore.RAW_ROOT
        try:
            conn.execute(
                "INSERT OR IGNORE INTO pillars (id,name,description,ord,status) VALUES (6,'Capital','test',6,'in_progress')"
            )
            conn.execute(
                """
                INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
                VALUES ('nvda','company','NVIDIA','semiconductors','["NVDA"]','test note','2024-01-01')
                """
            )
            rawstore.RAW_ROOT = rawstore.RAW_ROOT / "_test_gleif"

            response = {
                "meta": {"goldenCopy": {"publishDate": "2026-06-17T08:00:00Z"}},
                "data": [{
                    "id": "549300S4KLFTLO7GSQ80",
                    "attributes": {
                        "lei": "549300S4KLFTLO7GSQ80",
                        "entity": {
                            "legalName": {"name": "NVIDIA CORPORATION"},
                            "status": "ACTIVE",
                            "jurisdiction": "US-DE",
                            "registeredAs": "2862596",
                            "legalAddress": {"country": "US"},
                            "headquartersAddress": {"country": "US"},
                        },
                        "registration": {"status": "ISSUED"},
                    },
                }],
            }

            def fake_fetch(_query, **_kwargs):
                raw = json.dumps(response).encode("utf-8")
                return raw, response

            gleif_enrich._fetch = fake_fetch
            out = gleif_enrich.enrich_top_entities(
                conn,
                limit=1,
                only=["NVIDIA"],
                log=lambda *_a, **_k: None,
            )
            row = conn.execute("SELECT aliases, note FROM entities WHERE id='nvda'").fetchone()
            link = conn.execute(
                "SELECT ref_table, ref_id, method FROM entity_links WHERE entity_id='nvda' AND ref_table='lei'"
            ).fetchone()
            raw_count = conn.execute("SELECT count(*) FROM raw_docs").fetchone()[0]

            self.assertEqual(out["matched"], 1)
            self.assertIn("LEI:549300S4KLFTLO7GSQ80", row["aliases"])
            self.assertIn("GLEIF LEI:549300S4KLFTLO7GSQ80", row["note"])
            self.assertEqual(link["ref_id"], "549300S4KLFTLO7GSQ80")
            self.assertEqual(link["method"], "gleif_legal_name")
            self.assertGreaterEqual(raw_count, 1)
        finally:
            gleif_enrich._fetch = old_fetch
            rawstore.RAW_ROOT = old_raw_root
            conn.close()

    def test_sec_company_enrichment_updates_ticker_cik_links_and_raw_source(self) -> None:
        conn = memory_db()
        old_fetch = sec_company_enrich._fetch_company_tickers
        old_raw_root = rawstore.RAW_ROOT
        try:
            conn.execute(
                "INSERT OR IGNORE INTO pillars (id,name,description,ord,status) VALUES (6,'Capital','test',6,'in_progress')"
            )
            rawstore.RAW_ROOT = rawstore.RAW_ROOT / "_test_sec_company"
            response = {
                "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
                "1": {"cik_str": 320193, "ticker": "AAPL", "title": "APPLE INC"},
            }
            raw = json.dumps(response).encode("utf-8")

            def fake_fetch():
                return raw, response

            sec_company_enrich._fetch_company_tickers = fake_fetch
            out = sec_company_enrich.enrich_top_entities(
                conn,
                limit=1,
                only=["NVIDIA"],
                log=lambda *_a, **_k: None,
            )
            row = conn.execute(
                "SELECT aliases, note FROM entities WHERE kind='company' AND canonical_name='NVIDIA'"
            ).fetchone()
            ticker = conn.execute(
                "SELECT ref_id, method FROM entity_links WHERE ref_table='ticker' AND ref_id='NVDA'"
            ).fetchone()
            cik = conn.execute(
                "SELECT ref_id, method FROM entity_links WHERE ref_table='cik' AND ref_id='0001045810'"
            ).fetchone()
            raw_count = conn.execute("SELECT count(*) FROM raw_docs").fetchone()[0]

            self.assertEqual(out["matched"], 1)
            self.assertIn("CIK:0001045810", row["aliases"])
            self.assertIn("SEC ticker:NVDA", row["note"])
            self.assertEqual(ticker["method"], "sec_ticker_alias")
            self.assertEqual(cik["method"], "sec_ticker_alias")
            self.assertGreaterEqual(raw_count, 1)
        finally:
            sec_company_enrich._fetch_company_tickers = old_fetch
            rawstore.RAW_ROOT = old_raw_root
            conn.close()

    def test_companies_house_enrichment_updates_company_number_and_raw_source(self) -> None:
        conn = memory_db()
        old_search = companies_house_enrich._search_company
        old_fetch = companies_house_enrich._fetch_company_json
        old_raw_root = rawstore.RAW_ROOT
        try:
            conn.execute(
                "INSERT OR IGNORE INTO pillars (id,name,description,ord,status) VALUES (6,'Capital','test',6,'in_progress')"
            )
            conn.execute(
                """
                INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
                VALUES ('azn','company','AstraZeneca','biotech','["AstraZeneca PLC","AZN"]','test note','2024-01-01')
                """
            )
            rawstore.RAW_ROOT = rawstore.RAW_ROOT / "_test_companies_house"

            def fake_search(_query):
                raw = b'<a href="/company/02723534">ASTRAZENECA PLC</a>'
                return raw, [companies_house_enrich.SearchResult("02723534", "ASTRAZENECA PLC", "/company/02723534")]

            def fake_fetch(_company_number):
                payload = {
                    "primaryTopic": {
                        "CompanyName": "ASTRAZENECA PLC",
                        "CompanyNumber": "02723534",
                        "CompanyStatus": "Active",
                        "CompanyCategory": "Public Limited Company",
                        "CountryOfOrigin": "United Kingdom",
                        "IncorporationDate": "17/06/1992",
                    }
                }
                return json.dumps(payload).encode("utf-8"), payload

            companies_house_enrich._search_company = fake_search
            companies_house_enrich._fetch_company_json = fake_fetch
            out = companies_house_enrich.enrich_top_entities(
                conn,
                limit=1,
                only=["AstraZeneca"],
                log=lambda *_a, **_k: None,
            )
            row = conn.execute("SELECT aliases, note FROM entities WHERE id='azn'").fetchone()
            link = conn.execute(
                "SELECT ref_id, method FROM entity_links WHERE entity_id='azn' AND ref_table='companies_house_number'"
            ).fetchone()
            raw_count = conn.execute("SELECT count(*) FROM raw_docs").fetchone()[0]

            self.assertEqual(out["matched"], 1)
            self.assertIn("CH:02723534", row["aliases"])
            self.assertIn("Companies House:02723534", row["note"])
            self.assertEqual(link["ref_id"], "02723534")
            self.assertEqual(link["method"], "companies_house_exact_search")
            self.assertGreaterEqual(raw_count, 1)
        finally:
            companies_house_enrich._search_company = old_search
            companies_house_enrich._fetch_company_json = old_fetch
            rawstore.RAW_ROOT = old_raw_root
            conn.close()

    def test_wikidata_enrichment_updates_qid_and_raw_source(self) -> None:
        conn = memory_db()
        old_search = wikidata_enrich._fetch_search
        old_entity = wikidata_enrich._fetch_entity
        old_raw_root = rawstore.RAW_ROOT
        try:
            conn.execute(
                "INSERT OR IGNORE INTO pillars (id,name,description,ord,status) VALUES (6,'Capital','test',6,'in_progress')"
            )
            conn.execute(
                """
                INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
                VALUES ('openai','company','OpenAI','AI','[]','test note','2024-01-01')
                """
            )
            rawstore.RAW_ROOT = rawstore.RAW_ROOT / "_test_wikidata"
            search_payload = {"search": [{"id": "Q21708200", "label": "OpenAI"}]}
            entity_payload = {
                "entities": {
                    "Q21708200": {
                        "labels": {"en": {"value": "OpenAI"}},
                        "aliases": {"en": []},
                        "descriptions": {"en": {"value": "American artificial intelligence company"}},
                        "claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q4830453"}}}}]},
                    }
                }
            }

            def fake_search(query):
                raw = json.dumps(search_payload).encode("utf-8")
                return raw, search_payload, wikidata_enrich._search_url(query)

            def fake_entity(qid):
                raw = json.dumps(entity_payload).encode("utf-8")
                return raw, entity_payload, wikidata_enrich._entity_url(qid)

            wikidata_enrich._fetch_search = fake_search
            wikidata_enrich._fetch_entity = fake_entity
            out = wikidata_enrich.enrich_top_entities(
                conn,
                limit=1,
                only=["OpenAI"],
                missing_only=False,
                log=lambda *_a, **_k: None,
            )
            row = conn.execute("SELECT aliases, note FROM entities WHERE id='openai'").fetchone()
            link = conn.execute(
                "SELECT ref_id, method FROM entity_links WHERE entity_id='openai' AND ref_table='wikidata_qid'"
            ).fetchone()
            source = conn.execute(
                "SELECT url, content_hash FROM sources WHERE url=?",
                (wikidata_enrich._entity_url("Q21708200"),),
            ).fetchone()
            raw_count = conn.execute("SELECT count(*) FROM raw_docs").fetchone()[0]

            self.assertEqual(out["matched"], 1)
            self.assertIn("Wikidata:Q21708200", row["aliases"])
            self.assertIn("Wikidata QID:Q21708200", row["note"])
            self.assertEqual(link["ref_id"], "Q21708200")
            self.assertEqual(link["method"], "wikidata_exact_label")
            self.assertIsNotNone(source["content_hash"])
            self.assertGreaterEqual(raw_count, 2)
        finally:
            wikidata_enrich._fetch_search = old_search
            wikidata_enrich._fetch_entity = old_entity
            rawstore.RAW_ROOT = old_raw_root
            conn.close()

    def test_wikidata_enrichment_supports_top_institution_kind(self) -> None:
        conn = memory_db()
        old_search = wikidata_enrich._fetch_search
        old_entity = wikidata_enrich._fetch_entity
        old_raw_root = rawstore.RAW_ROOT
        try:
            conn.execute(
                "INSERT OR IGNORE INTO pillars (id,name,description,ord,status) VALUES (6,'Capital','test',6,'in_progress')"
            )
            rawstore.RAW_ROOT = rawstore.RAW_ROOT / "_test_wikidata_institution"
            search_payload = {"search": [{"id": "Q7164", "label": "World Bank"}]}
            entity_payload = {
                "entities": {
                    "Q7164": {
                        "labels": {"en": {"value": "World Bank"}},
                        "aliases": {"en": []},
                        "descriptions": {"en": {"value": "international financial institution"}},
                        "claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q43229"}}}}]},
                    }
                }
            }

            def fake_search(query):
                raw = json.dumps(search_payload).encode("utf-8")
                return raw, search_payload, wikidata_enrich._search_url(query)

            def fake_entity(qid):
                raw = json.dumps(entity_payload).encode("utf-8")
                return raw, entity_payload, wikidata_enrich._entity_url(qid)

            wikidata_enrich._fetch_search = fake_search
            wikidata_enrich._fetch_entity = fake_entity
            out = wikidata_enrich.enrich_top_entities(
                conn,
                kind="institution",
                limit=1,
                only=["World Bank"],
                missing_only=False,
                log=lambda *_a, **_k: None,
            )
            link = conn.execute(
                "SELECT ref_id, method FROM entity_links WHERE ref_table='wikidata_qid' AND ref_id='Q7164'"
            ).fetchone()

            self.assertEqual(out["matched"], 1)
            self.assertEqual(link["method"], "wikidata_exact_label")
        finally:
            wikidata_enrich._fetch_search = old_search
            wikidata_enrich._fetch_entity = old_entity
            rawstore.RAW_ROOT = old_raw_root
            conn.close()

    def test_wikidata_match_accepts_parenthetical_disambiguation(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
                VALUES ('sc','company','S&C Electric','grid','["S&C Electric Company"]','test','2024-01-01')
                """
            )
            row = conn.execute("SELECT * FROM entities WHERE id='sc'").fetchone()
            rec = {
                "labels": {"en": {"value": "S&C Electric Company (United States)"}},
                "aliases": {"en": []},
                "descriptions": {"en": {"value": "company in Chicago, United States"}},
                "claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q4830453"}}}}]},
            }

            self.assertTrue(wikidata_enrich._matches_entity(row, rec))
            self.assertTrue(wikidata_enrich._looks_org_like(rec))
        finally:
            conn.close()

    def test_wikidata_technology_filter_rejects_non_technology_pages(self) -> None:
        company_rec = {
            "labels": {"en": {"value": "DroneS"}},
            "descriptions": {"en": {"value": "Company specializing in drone technology"}},
            "claims": {},
        }
        article_rec = {
            "labels": {"en": {"value": "Silicon Photonics"}},
            "descriptions": {"en": {"value": "scientific article published in a journal"}},
            "claims": {},
        }
        good_rec = {
            "labels": {"en": {"value": "solid-state battery"}},
            "descriptions": {"en": {"value": "battery that uses solid electrodes and solid electrolytes"}},
            "claims": {},
        }

        self.assertFalse(wikidata_enrich._looks_kind_like(company_rec, "technology"))
        self.assertFalse(wikidata_enrich._looks_kind_like(article_rec, "technology"))
        self.assertTrue(wikidata_enrich._looks_kind_like(good_rec, "technology"))

    def test_wikidata_institution_filter_accepts_authority_and_catalog(self) -> None:
        authority_rec = {
            "labels": {"en": {"value": "Companies House"}},
            "descriptions": {"en": {"value": "registration authority for companies in the UK"}},
            "claims": {},
        }
        catalog_rec = {
            "labels": {"en": {"value": "OpenAlex"}},
            "descriptions": {"en": {"value": "open catalog of scholarly papers"}},
            "claims": {},
        }

        self.assertTrue(wikidata_enrich._looks_kind_like(authority_rec, "institution"))
        self.assertTrue(wikidata_enrich._looks_kind_like(catalog_rec, "institution"))

    def test_wikidata_label_extraction_falls_back_to_mul_or_latin_label(self) -> None:
        rec = {
            "labels": {
                "ar": {"value": "الباحث الدلالي"},
                "mul": {"value": "Semantic Scholar"},
            },
            "aliases": {},
        }

        self.assertEqual(wikidata_enrich._primary_label(rec), "Semantic Scholar")
        self.assertIn("Semantic Scholar", wikidata_enrich._label_aliases(rec))

    def test_wikidata_non_company_match_ignores_learned_db_aliases(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
                VALUES (
                    'qc','technology','Quantum computing','compute',
                    '["quantum information science"]','test','2024-01-01'
                )
                """
            )
            row = conn.execute("SELECT * FROM entities WHERE id='qc'").fetchone()
            rec = {
                "labels": {"en": {"value": "quantum information science"}},
                "aliases": {"en": [{"value": "quantum computing"}]},
                "descriptions": {"en": {"value": "interdisciplinary theory behind quantum computing"}},
                "claims": {},
            }

            self.assertFalse(wikidata_enrich._matches_entity(row, rec, kind="technology"))
        finally:
            conn.close()

    def test_wikidata_non_company_queries_use_curated_aliases_only(self) -> None:
        queries = wikidata_enrich._usable_queries(
            "GLP-1 obesity drugs",
            ["clinicaltrials:glp1_obesity_drugs:snapshot:total_studies"],
            kind="technology",
        )

        self.assertIn("glucagon-like peptide-1 agonist", queries)
        self.assertNotIn("clinicaltrials:glp1_obesity_drugs:snapshot:total_studies", queries)

    def test_companies_house_rejects_non_exact_search_result(self) -> None:
        row = {
            "canonical_name": "BP",
            "aliases": json.dumps(["BP p.l.c."]),
        }
        conn = memory_db()
        try:
            conn.execute(
                "INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at) VALUES (?,?,?,?,?,?,?)",
                ("bp", "company", "BP", "energy", row["aliases"], "", "2024-01-01"),
            )
            db_row = conn.execute("SELECT * FROM entities WHERE id='bp'").fetchone()
            result = companies_house_enrich._best_result(
                db_row,
                "BP p.l.c.",
                [companies_house_enrich.SearchResult("10041931", "ASHTEAD TECHNOLOGY MIDCO LIMITED", "/company/10041931")],
            )
            self.assertIsNone(result)
        finally:
            conn.close()

    def test_companies_house_queries_only_uk_public_parent_aliases(self) -> None:
        self.assertEqual(
            companies_house_enrich._usable_queries(
                "Apple",
                ["Apple Inc.", "APPLE LTD", "AAPL", "CH:05588682"],
            ),
            [],
        )
        self.assertEqual(
            companies_house_enrich._usable_queries("BP", ["BP p.l.c.", "BP.L"]),
            ["BP p.l.c."],
        )
        self.assertEqual(
            companies_house_enrich._usable_queries("AstraZeneca", ["AstraZeneca PLC", "AZN"]),
            ["AstraZeneca PLC"],
        )

    def test_companies_house_rejects_dissolved_profile(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                "INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    "azn",
                    "company",
                    "AstraZeneca",
                    "biotech",
                    json.dumps(["AstraZeneca PLC"]),
                    "",
                    "2024-01-01",
                ),
            )
            row = conn.execute("SELECT * FROM entities WHERE id='azn'").fetchone()
            result = companies_house_enrich.SearchResult("02723534", "ASTRAZENECA PLC", "/company/02723534")
            match = companies_house_enrich._extract_match(
                row,
                "AstraZeneca PLC",
                result,
                {
                    "primaryTopic": {
                        "CompanyName": "ASTRAZENECA PLC",
                        "CompanyNumber": "02723534",
                        "CompanyStatus": "Dissolved",
                    }
                },
            )
            self.assertIsNone(match)
        finally:
            conn.close()

    def test_companies_house_enrichment_cleans_prior_permissive_links(self) -> None:
        conn = memory_db()
        old_search = companies_house_enrich._search_company
        old_fetch = companies_house_enrich._fetch_company_json
        old_raw_root = rawstore.RAW_ROOT
        try:
            conn.execute(
                "INSERT OR IGNORE INTO pillars (id,name,description,ord,status) VALUES (6,'Capital','test',6,'in_progress')"
            )
            conn.execute(
                """
                INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
                VALUES (
                    'apple','company','Apple','technology',
                    '["Apple Inc.","APPLE LTD","CH:05588682","CompaniesHouse:05588682"]',
                    'test note Companies House:05588682 name=APPLE LTD status=Dissolved incorporated=n/a.',
                    '2024-01-01'
                )
                """
            )
            conn.execute(
                """
                INSERT INTO entity_links (
                    id, entity_id, ref_table, ref_id, ref_label, pillar_id, confidence,
                    method, rationale, created_at
                ) VALUES (
                    'old_ch','apple','companies_house_number','05588682','APPLE LTD',6,0.98,
                    'companies_house_exact_search','old permissive fixture','2024-01-01'
                )
                """
            )
            rawstore.RAW_ROOT = rawstore.RAW_ROOT / "_test_companies_house_cleanup"
            companies_house_enrich._search_company = lambda _query: (b"", [])
            companies_house_enrich._fetch_company_json = lambda _company_number: (None, None)

            out = companies_house_enrich.enrich_top_entities(
                conn,
                limit=1,
                only=["Apple"],
                log=lambda *_a, **_k: None,
            )
            row = conn.execute("SELECT aliases, note FROM entities WHERE id='apple'").fetchone()
            link_count = conn.execute(
                "SELECT count(*) FROM entity_links WHERE entity_id='apple' AND ref_table='companies_house_number'"
            ).fetchone()[0]

            self.assertEqual(out["matched"], 0)
            self.assertEqual(out["cleaned"], 1)
            self.assertEqual(link_count, 0)
            self.assertNotIn("APPLE LTD", row["aliases"])
            self.assertNotIn("Companies House:05588682", row["note"])
        finally:
            companies_house_enrich._search_company = old_search
            companies_house_enrich._fetch_company_json = old_fetch
            rawstore.RAW_ROOT = old_raw_root
            conn.close()


if __name__ == "__main__":
    unittest.main()
