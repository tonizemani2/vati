from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import world_catalog, world_state
from engine.feeds import collect_all, ingest, miningterminal_permits
from tests.test_world_state import memory_db


def _feature(props: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-1, 1], [-1, 2], [0, 2], [0, 1], [-1, 1]]],
        },
        "properties": props,
    }


class MiningTerminalPermitsTests(unittest.TestCase):
    def test_summarize_streams_geojson_to_compact_rows_without_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sample_permits_20260528.geojson"
            payload = {
                "type": "FeatureCollection",
                "metadata": {
                    "source": "BC Mineral Titles (MTA)",
                    "country": "CAN",
                    "scraped_at": "2026-05-28T18:24:49Z",
                    "total_features": 2,
                },
                "features": [
                    _feature(
                        {
                            "permit_id": "201416",
                            "holder_name": "CATFACE COPPER MINES LIMITED",
                            "country": "CAN",
                            "jurisdiction": "British Columbia",
                            "permit_type": "Two Post Claim",
                            "phase": "exploration",
                            "status": "CLAIM",
                            "commodity": "Cu, Au",
                            "area_hectares": 25,
                            "grant_date": "2020-01-01",
                            "expiry_date": "2026-04-30",
                            "source_system": "BC Mineral Titles (MTA)",
                            "source_url": "https://example.test/bc",
                        }
                    ),
                    _feature(
                        {
                            "permit_id": "201417",
                            "holder_name": "CATFACE COPPER MINES LIMITED",
                            "country": "CAN",
                            "jurisdiction": "British Columbia",
                            "permit_type": "Two Post Claim",
                            "phase": "exploration",
                            "status": "CLAIM",
                            "commodity": "Cu",
                            "area_hectares": 35,
                            "grant_date": "2021-01-01",
                            "expiry_date": "2027-04-30",
                            "source_system": "BC Mineral Titles (MTA)",
                            "source_url": "https://example.test/bc",
                        }
                    ),
                ],
            }
            path.write_text(json.dumps(payload), encoding="utf-8")

            with mock.patch.object(
                miningterminal_permits,
                "_today",
                return_value=miningterminal_permits.date(2026, 6, 18),
            ):
                rows, status = miningterminal_permits.summarize([path], max_holder_groups=20)

        self.assertGreaterEqual(len(rows), 8)
        self.assertEqual(status["features_seen"], 2)
        self.assertEqual(status["holder_groups_kept"], 3)
        self.assertTrue(all("geometry" not in row for row in rows))
        copper_count = [
            row for row in rows
            if row["metric"] == "mining_land_permit_record_count"
            and row["commodity"] == "Copper"
            and row["holder_name"] == "CATFACE COPPER MINES LIMITED"
        ][0]
        self.assertEqual(copper_count["value"], 2.0)
        self.assertEqual(copper_count["published_at"], "2026-05-28")
        self.assertEqual(copper_count["earliest_grant_date"], "2020-01-01")
        self.assertEqual(copper_count["latest_expiry_date"], "2027-04-30")
        self.assertEqual(copper_count["provenance"], "derived_from_miningterminal_local_geojson_no_geometry")

    def test_collector_is_keyless_ingestable_and_mapped_to_land_cadastre(self) -> None:
        self.assertIn("miningterminal_permits", collect_all.KEYLESS)
        self.assertIn("miningterminal_permits", ingest.FEED_META)
        self.assertIn("miningterminal_permits", world_catalog.SOURCE_FEED_MAP["land_permits_cadastre"])
        self.assertIn("miningterminal_permits", world_state._PREFER_EXACT_SERIES_SUBJECT_PROVIDERS)

    def test_ingest_backfill_and_autolink_holder_series(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO pillars (id, name, description, ord, status)
                VALUES (5, 'Physical / supply', 'Physical supply and permitting.', 5, 'in_progress')
                """
            )
            rows = [
                {
                    "feed": "miningterminal_permits",
                    "series_id": "miningterminal_permits:holder:mining_land_permit_record_count:catface",
                    "date": "2026-05-28",
                    "as_of": "2026-05-28",
                    "event_time": "2026-05-28",
                    "published_at": "2026-05-28",
                    "observed_at": "2026-05-28",
                    "value": 2,
                    "unit": "permits",
                    "metric": "mining_land_permit_record_count",
                    "domain": "land_use",
                    "title": "MiningTerminal permit holder - CATFACE COPPER MINES LIMITED - CAN - BC Mineral Titles (MTA) - Copper - count",
                    "holder_name": "CATFACE COPPER MINES LIMITED",
                    "commodity": "Copper",
                    "provenance": "derived_from_miningterminal_local_geojson_no_geometry",
                }
            ]
            with tempfile.TemporaryDirectory() as td:
                feed_dir = Path(td)
                (feed_dir / "miningterminal_permits.jsonl").write_text(
                    "\n".join(json.dumps(row) for row in rows) + "\n",
                    encoding="utf-8",
                )
                with mock.patch.object(ingest, "FEEDS_DIR", feed_dir):
                    out = ingest.ingest_feed(conn, "miningterminal_permits")

            self.assertEqual(out["status"], "ok")
            self.assertEqual(out["series"], 1)
            self.assertEqual(out["obs"], 1)
            links = world_state.autolink_series_entities(conn, only_unlinked=True)
            self.assertEqual(links["links_written"], 1)
            entity = conn.execute(
                """
                SELECT e.kind, e.canonical_name
                FROM entity_links el
                JOIN entities e ON e.id=el.entity_id
                WHERE el.ref_table='series'
                """
            ).fetchone()
            self.assertEqual(entity["kind"], "permit_holder")
            self.assertEqual(entity["canonical_name"], "CATFACE COPPER MINES LIMITED")
            facts = world_state.backfill_observation_facts(conn, provider="miningterminal_permits")
            self.assertEqual(facts["seen"], 1)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
