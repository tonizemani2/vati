from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import world_catalog, world_state
from engine.feeds import australia_epbc_referrals, collect_all, ingest
from tests.test_world_state import memory_db


REFERRAL = {
    "REFERENCE_NUMBER": "2024/09876",
    "PROPOSAL_ID": 9876,
    "NAME": "Pilbara Critical Minerals Processing Facility",
    "PRIMARY_JURISDICTION": "WA",
    "REFERRAL_DECISION": "Controlled Action",
    "STANDARD_DETERMINATION": "CA",
    "STATUS_DESCRIPTION": "Assessment",
    "STAGE_NAME": "Assessment",
    "REFERRAL_TYPE": "Referral (S68)",
    "YEAR": 2024.0,
    "CATEGORY": "Mining",
    "REFERRAL_URL": "http:\\\\epbcnotices.environment.gov.au\\referralslist",
    "CRM_ID": "crm-123",
    "OBJECTID": 42,
    "SHAPE.AREA": 0.0123,
    "SHAPE.LEN": 0.45,
}


class AustraliaEPBCReferralsTests(unittest.TestCase):
    def test_normalize_emits_leak_safe_referral_row_without_geometry(self) -> None:
        rows = australia_epbc_referrals.normalize([REFERRAL], snapshot_date="2026-06-18")

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["series_id"], "australia_epbc_referrals:referral:2024_09876_42")
        self.assertEqual(row["metric"], "australia_epbc_referral_status")
        self.assertEqual(row["published_at"], "2026-06-18")
        self.assertEqual(row["event_time"], "2024-12-31")
        self.assertEqual(row["primary_jurisdiction"], "WA")
        self.assertEqual(row["category"], "Mining")
        self.assertIn("not development footprints", row["boundary_caveat"])
        self.assertNotIn("geometry", row)

    def test_collect_writes_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            old_out = australia_epbc_referrals.OUT_PATH
            australia_epbc_referrals.OUT_PATH = Path(td) / "australia_epbc_referrals.jsonl"
            try:
                with (
                    mock.patch.object(australia_epbc_referrals, "_snapshot_date", return_value="2026-06-18"),
                    mock.patch.object(australia_epbc_referrals, "_fetch_rows", return_value=[REFERRAL]),
                ):
                    rows = australia_epbc_referrals.collect(log=lambda *_: None)
                stored = [
                    json.loads(line)
                    for line in australia_epbc_referrals.OUT_PATH.read_text(encoding="utf-8").splitlines()
                ]
            finally:
                australia_epbc_referrals.OUT_PATH = old_out

        self.assertEqual(len(rows), 1)
        self.assertEqual(stored[0]["provenance"], "official_australia_epbc_referrals_arcgis_no_geometry")
        self.assertEqual(stored[0]["cost_cents"], 0)

    def test_collector_is_keyless_ingestable_and_mapped_to_eia(self) -> None:
        self.assertIn("australia_epbc_referrals", collect_all.KEYLESS)
        self.assertIn("australia_epbc_referrals", ingest.FEED_META)
        self.assertIn("australia_epbc_referrals", world_catalog.SOURCE_FEED_MAP["environmental_planning_eia"])
        self.assertIn("australia_epbc_referrals", world_state._PREFER_EXACT_SERIES_SUBJECT_PROVIDERS)

    def test_ingest_backfill_and_autolink(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO pillars (id, name, description, ord, status)
                VALUES (5, 'Physical / supply', 'Physical supply and permitting.', 5, 'in_progress')
                """
            )
            rows = australia_epbc_referrals.normalize([REFERRAL], snapshot_date="2026-06-18")
            with tempfile.TemporaryDirectory() as td:
                feed_dir = Path(td)
                (feed_dir / "australia_epbc_referrals.jsonl").write_text(
                    "\n".join(json.dumps(row) for row in rows) + "\n",
                    encoding="utf-8",
                )
                with mock.patch.object(ingest, "FEEDS_DIR", feed_dir):
                    out = ingest.ingest_feed(conn, "australia_epbc_referrals")

            self.assertEqual(out["status"], "ok")
            self.assertEqual(out["series"], 1)
            self.assertEqual(out["obs"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM raw_docs").fetchone()[0], 1)
            links = world_state.autolink_series_entities(conn, only_unlinked=True)
            self.assertEqual(links["links_written"], 1)
            facts = world_state.backfill_observation_facts(conn, provider="australia_epbc_referrals")
            self.assertEqual(facts["seen"], 1)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
