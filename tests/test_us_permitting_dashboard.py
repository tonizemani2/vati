from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import world_catalog, world_state
from engine.feeds import collect_all, ingest, us_permitting_dashboard
from tests.test_world_state import memory_db


MILESTONE_1 = {
    "project_id": "100",
    "project_title": "Thacker Pass Lithium Mine",
    "project_field_project_lead_agency": "Department of the Interior",
    "project_field_project_lead_agency_bureau": "Bureau of Land Management",
    "project_category": "FAST-41 Transparency Projects",
    "project_field_project_status": "In Progress",
    "project_sector": "Mining",
    "project_sector_type": "Geological Exploration",
    "project_field_location_state": "NV",
    "project_field_location_county": "Humboldt",
    "project_field_location_city": "Winnemucca",
    "project_field_location_other": "Humboldt County, Nevada",
    "project_lat": "41.7",
    "project_lon": "-118.0",
    "project_url": {"url": "https://www.permits.performance.gov/permitting-project/test"},
    "project_field_project_sponsor_agency": "Lithium Americas",
    "total_estimated_project_cost": "$2,200,000,000.00",
    "major_project": True,
    "action_id": "200",
    "action_type": "Mine Plan of Operations",
    "action_status": "In Progress",
    "action_agency": "Bureau of Land Management",
    "milestone_id": "300",
    "action_milestone_name": "Permit application submitted",
    "action_milestone_group": "authorization_milestones",
    "action_milestone_completion_actual": "2025-01-15T00:00:00.000",
    "action_milestone_complete": True,
    "last_data_fetched": "2026-06-18T06:05:45.000",
}

MILESTONE_2 = {
    **MILESTONE_1,
    "milestone_id": "301",
    "action_milestone_name": "Issuance of final decision",
    "action_milestone_completion_actual": "",
    "action_milestone_completion_target": "2026-09-01T00:00:00.000",
    "action_milestone_complete": False,
}


class USPermittingDashboardTests(unittest.TestCase):
    def test_normalize_rows_outputs_project_and_action_state(self) -> None:
        rows = us_permitting_dashboard.normalize_rows([MILESTONE_1, MILESTONE_2])

        self.assertEqual(len(rows), 2)
        project, action = rows
        self.assertEqual(project["series_id"], "us_permitting_dashboard:project:100")
        self.assertEqual(project["metric"], "us_federal_permitting_project_status")
        self.assertEqual(project["date"], "2026-06-18")
        self.assertEqual(project["project_sector"], "Mining")
        self.assertEqual(project["total_estimated_project_cost_usd"], 2_200_000_000.0)
        self.assertEqual(action["series_id"], "us_permitting_dashboard:action:200")
        self.assertEqual(action["metric"], "us_federal_permitting_action_status")
        self.assertEqual(action["milestone_count"], 2)
        self.assertEqual(action["completed_milestones"], 1)
        self.assertEqual(action["latest_milestone_date"], "2026-09-01")
        self.assertEqual(action["event_time"], "2026-06-18")

    def test_collect_writes_jsonl_from_public_data_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            old_out = us_permitting_dashboard.OUT_PATH
            us_permitting_dashboard.OUT_PATH = Path(td) / "us_permitting_dashboard.jsonl"
            try:
                with mock.patch.object(us_permitting_dashboard, "_fetch_rows", return_value=[MILESTONE_1, MILESTONE_2]):
                    rows = us_permitting_dashboard.collect(log=lambda *_: None)
                stored = [
                    json.loads(line)
                    for line in us_permitting_dashboard.OUT_PATH.read_text(encoding="utf-8").splitlines()
                ]
            finally:
                us_permitting_dashboard.OUT_PATH = old_out

        self.assertEqual(len(rows), 2)
        self.assertEqual(stored[0]["provenance"], "official_us_permitting_dashboard_data_portal")
        self.assertEqual(stored[0]["cost_cents"], 0)

    def test_collector_is_keyless_ingestable_and_mapped_to_eia(self) -> None:
        self.assertIn("us_permitting_dashboard", collect_all.KEYLESS)
        self.assertIn("us_permitting_dashboard", ingest.FEED_META)
        self.assertIn("us_permitting_dashboard", world_catalog.SOURCE_FEED_MAP["environmental_planning_eia"])

    def test_ingest_backfill_and_autolink(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO pillars (id, name, description, ord, status)
                VALUES (5, 'Physical / supply', 'Physical supply and permitting.', 5, 'in_progress')
                """
            )
            rows = us_permitting_dashboard.normalize_rows([MILESTONE_1, MILESTONE_2])
            with tempfile.TemporaryDirectory() as td:
                feed_dir = Path(td)
                (feed_dir / "us_permitting_dashboard.jsonl").write_text(
                    "\n".join(json.dumps(row) for row in rows) + "\n",
                    encoding="utf-8",
                )
                with mock.patch.object(ingest, "FEEDS_DIR", feed_dir):
                    out = ingest.ingest_feed(conn, "us_permitting_dashboard")

            self.assertEqual(out["status"], "ok")
            self.assertEqual(out["series"], 2)
            self.assertEqual(out["obs"], 2)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM raw_docs").fetchone()[0], 1)
            links = world_state.autolink_series_entities(conn, only_unlinked=True)
            self.assertGreaterEqual(links["links_written"], 2)
            facts = world_state.backfill_observation_facts(conn, provider="us_permitting_dashboard")
            self.assertEqual(facts["seen"], 2)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
