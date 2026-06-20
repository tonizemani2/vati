from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.feeds import land_permit_sources
from tests.test_world_state import memory_db


class LandPermitSourcesTests(unittest.TestCase):
    def test_portal_seed_is_unique_and_roi_ordered(self) -> None:
        ids = [row["id"] for row in land_permit_sources.PORTALS]
        urls = [row["url"] for row in land_permit_sources.PORTALS]

        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(urls), len(set(urls)))
        self.assertGreaterEqual(len(ids), 8)
        self.assertEqual(land_permit_sources.PORTALS[0]["id"], "us_federal_permitting_dashboard")
        self.assertTrue(all(int(row["priority"]) == 1 for row in land_permit_sources.PORTALS))
        self.assertIn("drc_mining_cadastre", ids)
        self.assertIn("peru_geocatmin", ids)
        self.assertIn("resourcecontracts_global", ids)

    def test_write_manifest_outputs_jsonl_without_fetching_bulk(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "land_permit_sources.jsonl"
            out = land_permit_sources.write_manifest(path, collected_at="2026-06-18T00:00:00+00:00")
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

        self.assertTrue(out["ok"])
        self.assertEqual(out["rows"], len(land_permit_sources.PORTALS))
        self.assertEqual(len(rows), len(land_permit_sources.PORTALS))
        self.assertTrue(all(row["feed"] == "land_permit_sources" for row in rows))
        self.assertTrue(all(row["cost_cents"] == 0 for row in rows))
        self.assertTrue(all(row["provenance"] == "curated_official_source_seed" for row in rows))

    def test_seed_sources_registers_manifest_only_provenance(self) -> None:
        conn = memory_db()
        try:
            with tempfile.TemporaryDirectory() as td:
                path = Path(td) / "land_permit_sources.jsonl"
                land_permit_sources.write_manifest(path, collected_at="2026-06-18T00:00:00+00:00")
                out = land_permit_sources.seed_sources(conn, path=path)
            source_rows = conn.execute(
                "SELECT id, raw_provenance_status, content_hash FROM sources "
                "WHERE id LIKE 'land_permit_source:%'"
            ).fetchall()
            raw_docs = conn.execute("SELECT COUNT(*) AS n FROM raw_docs").fetchone()["n"]

            self.assertTrue(out["ok"])
            self.assertEqual(out["rows"], len(land_permit_sources.PORTALS))
            self.assertEqual(out["inserted"], len(land_permit_sources.PORTALS))
            self.assertEqual(len(source_rows), len(land_permit_sources.PORTALS))
            self.assertEqual(raw_docs, 1)
            self.assertTrue(all(row["raw_provenance_status"] == "catalog_manifest_only" for row in source_rows))
            self.assertTrue(all(row["content_hash"] == out["manifest_hash"] for row in source_rows))
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
