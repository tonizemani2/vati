from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import world_catalog, world_state
from engine.feeds import blm_mining_claims, collect_all, ingest
from tests.test_world_state import memory_db


CLAIM_AGG = {
    "GEO_STATE": "NV",
    "CSE_DISP": "Active",
    "BLM_PROD": "Lode Claim",
    "claim_count": 123,
    "claim_acres": 4567.89,
}

PLAN = {
    "ID": "1121466416551374584",
    "ADMIN_STATE": "NV",
    "GEO_STATE": "NV",
    "BLM_PROD": "Surface Management Plan - Mining",
    "CSE_DISP": "Authorized",
    "CSE_TYPE_NR": "380910",
    "CSE_NR": "NVNV105921736",
    "LEG_CSE_NR": "NVN 12345",
    "CSE_NAME": "Thacker Pass",
    "CMMDTY": "LITHIUM",
    "EFF_DT": 1704067200000,
    "EXP_DT": None,
    "PRDCNG": "Producing",
    "CUST_NM_SEC": "Lithium Americas",
    "PCT_INT_SEC": 100.0,
    "INT_REL_SEC": "Operator",
    "CSE_DISP_DT": 1704067200000,
    "SRC": "LLD/CLS",
    "QLTY": "0",
    "RCRD_ACRS": 1000.5,
    "SF_ID": "abc123",
    "Created": 1704067200000,
    "Modified": 1717200000000,
}


class BLMMniningClaimsTests(unittest.TestCase):
    def test_normalize_emits_claim_count_acres_and_plan_rows(self) -> None:
        rows = blm_mining_claims.normalize([CLAIM_AGG], [PLAN], snapshot_date="2026-06-18")

        self.assertEqual(len(rows), 3)
        count, acres, plan = rows
        self.assertEqual(count["series_id"], "blm_mining_claims:active_claim_count:nv:active:lode_claim")
        self.assertEqual(count["metric"], "blm_active_mining_claim_count")
        self.assertEqual(count["value"], 123.0)
        self.assertEqual(acres["metric"], "blm_active_mining_claim_acres")
        self.assertEqual(acres["unit"], "acres")
        self.assertEqual(plan["series_id"], "blm_mining_claims:plan:nvnv105921736")
        self.assertEqual(plan["metric"], "blm_mining_plan_status")
        self.assertEqual(plan["published_at"], "2024-06-01")
        self.assertEqual(plan["event_time"], "2024-01-01")
        self.assertEqual(plan["commodity"], "LITHIUM")
        self.assertEqual(plan["operator"], "Lithium Americas")

    def test_collect_writes_jsonl_without_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            old_out = blm_mining_claims.OUT_PATH
            blm_mining_claims.OUT_PATH = Path(td) / "blm_mining_claims.jsonl"
            try:
                with (
                    mock.patch.object(blm_mining_claims, "_claim_aggregate_features", return_value=[CLAIM_AGG]),
                    mock.patch.object(blm_mining_claims, "_plan_features", return_value=[PLAN]),
                    mock.patch.object(blm_mining_claims, "_today", return_value="2026-06-18"),
                ):
                    rows = blm_mining_claims.collect(log=lambda *_: None)
                stored = [
                    json.loads(line)
                    for line in blm_mining_claims.OUT_PATH.read_text(encoding="utf-8").splitlines()
                ]
            finally:
                blm_mining_claims.OUT_PATH = old_out

        self.assertEqual(len(rows), 3)
        self.assertEqual(stored[0]["provenance"], "official_blm_arcgis_rest_aggregate_no_geometry")
        for row in stored:
            self.assertNotIn("geometry", row)
            self.assertNotIn("Shape", row)

    def test_collector_is_keyless_ingestable_and_mapped_to_land_cadastre(self) -> None:
        self.assertIn("blm_mining_claims", collect_all.KEYLESS)
        self.assertIn("blm_mining_claims", ingest.FEED_META)
        self.assertIn("blm_mining_claims", world_catalog.SOURCE_FEED_MAP["land_permits_cadastre"])
        self.assertIn("blm_mining_claims", world_state._PREFER_EXACT_SERIES_SUBJECT_PROVIDERS)

    def test_ingest_backfill_and_autolink(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO pillars (id, name, description, ord, status)
                VALUES (5, 'Physical / supply', 'Physical supply and permitting.', 5, 'in_progress')
                """
            )
            rows = blm_mining_claims.normalize([CLAIM_AGG], [PLAN], snapshot_date="2026-06-18")
            with tempfile.TemporaryDirectory() as td:
                feed_dir = Path(td)
                (feed_dir / "blm_mining_claims.jsonl").write_text(
                    "\n".join(json.dumps(row) for row in rows) + "\n",
                    encoding="utf-8",
                )
                with mock.patch.object(ingest, "FEEDS_DIR", feed_dir):
                    out = ingest.ingest_feed(conn, "blm_mining_claims")

            self.assertEqual(out["status"], "ok")
            self.assertEqual(out["series"], 3)
            self.assertEqual(out["obs"], 3)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM raw_docs").fetchone()[0], 1)
            links = world_state.autolink_series_entities(conn, only_unlinked=True)
            self.assertEqual(links["links_written"], 3)
            facts = world_state.backfill_observation_facts(conn, provider="blm_mining_claims")
            self.assertEqual(facts["seen"], 3)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
