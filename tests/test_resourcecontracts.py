from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import world_catalog
from engine.feeds import collect_all, ingest, resourcecontracts
from tests.test_world_state import memory_db


GROUP_DATA = {
    "result_total": 1,
    "results": [
        {
            "id": 6191,
            "name": "Saraya Energy Company, Exploration License, 2023",
            "year_signed": "2023",
            "resource": ["Lithium"],
            "countries": [{"code": "SN", "name": "Senegal"}],
        }
    ],
}

METADATA = {
    "id": 6191,
    "open_contracting_id": "ocds-591adf-test",
    "name": "Saraya Energy Company, Exploration License, 2023",
    "countries": [{"code": "SN", "name": "Senegal"}],
    "resource": ["Lithium", "Tin"],
    "published_at": "2024-02-01T12:00:00",
    "date_signed": "2023-06-15",
    "year_signed": 2023,
    "contract_type": ["Exploration License"],
    "document_type": "Company-State Contract",
    "participation": [{"company": {"name": "Saraya Energy Company"}}],
    "government_entity": [{"name": "Ministry of Mines"}],
    "concession": [{"name": "Saraya"}],
    "project": {"name": "Saraya Lithium"},
    "file": [{"url": "https://example.test/contract.pdf", "media_type": "application/pdf", "byte_size": 10}],
    "language": "fr",
    "is_contract_signed": True,
    "is_ocr_reviewed": True,
}


class ResourceContractsTests(unittest.TestCase):
    def test_row_uses_publication_date_for_as_of_and_signed_date_for_event(self) -> None:
        row = resourcecontracts._row_from_metadata(METADATA, matched_resources=["Lithium"])

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["series_id"], "resourcecontracts:contract:6191")
        self.assertEqual(row["date"], "2024-02-01")
        self.assertEqual(row["published_at"], "2024-02-01")
        self.assertEqual(row["event_time"], "2023-06-15")
        self.assertEqual(row["observed_at"], "2023-06-15")
        self.assertEqual(row["metric"], "resource_contract_publication")
        self.assertEqual(row["resources"], ["Lithium", "Tin"])
        self.assertEqual(row["companies"], ["Saraya Energy Company"])
        self.assertIn("ResourceContracts", row["title"])

    def test_collect_dedupes_metadata_and_writes_jsonl(self) -> None:
        def fake_fetch(url: str):
            if "/contracts/group" in url:
                return GROUP_DATA
            if "/contract/6191/metadata" in url:
                return METADATA
            return None

        with tempfile.TemporaryDirectory() as td:
            old_out = resourcecontracts.OUT_PATH
            old_filters = resourcecontracts.RESOURCE_FILTERS
            resourcecontracts.OUT_PATH = Path(td) / "resourcecontracts.jsonl"
            try:
                with (
                    mock.patch.object(resourcecontracts, "RESOURCE_FILTERS", ("Lithium", "Critical Minerals")),
                    mock.patch.object(resourcecontracts, "_fetch_json", side_effect=fake_fetch),
                ):
                    rows = resourcecontracts.collect(log=lambda *_: None, per_resource=5)
                stored = [
                    json.loads(line)
                    for line in resourcecontracts.OUT_PATH.read_text(encoding="utf-8").splitlines()
                ]
            finally:
                resourcecontracts.OUT_PATH = old_out
                resourcecontracts.RESOURCE_FILTERS = old_filters

        self.assertEqual(len(rows), 1)
        self.assertEqual(stored[0]["contract_id"], 6191)
        self.assertEqual(stored[0]["matched_resource_filters"], ["Critical Minerals", "Lithium"])
        self.assertEqual(stored[0]["provenance"], "official_resourcecontracts_api_metadata")

    def test_collector_is_keyless_ingestable_and_mapped_to_concessions(self) -> None:
        self.assertIn("resourcecontracts", collect_all.KEYLESS)
        self.assertIn("resourcecontracts", ingest.FEED_META)
        self.assertEqual(
            world_catalog.SOURCE_FEED_MAP["resource_concessions_contracts"],
            ("resourcecontracts",),
        )

    def test_ingest_lands_contract_as_series_and_raw_doc(self) -> None:
        conn = memory_db()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO pillars (id, name, description, ord, status)
                VALUES (5, 'Physical / supply', 'Physical supply, land, permitting, and infrastructure constraints.', 5, 'in_progress')
                """
            )
            with tempfile.TemporaryDirectory() as td:
                feed_dir = Path(td)
                path = feed_dir / "resourcecontracts.jsonl"
                row = resourcecontracts._row_from_metadata(METADATA, matched_resources=["Lithium"])
                path.write_text(json.dumps(row) + "\n", encoding="utf-8")
                with mock.patch.object(ingest, "FEEDS_DIR", feed_dir):
                    out = ingest.ingest_feed(conn, "resourcecontracts")

            self.assertEqual(out["status"], "ok")
            self.assertEqual(out["series"], 1)
            self.assertEqual(out["obs"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS n FROM raw_docs").fetchone()["n"], 1)
            series = conn.execute("SELECT provider, external_id, metric, label FROM series").fetchone()
            self.assertEqual(series["provider"], "resourcecontracts")
            self.assertEqual(series["external_id"], "resourcecontracts:contract:6191")
            self.assertIn("Saraya Energy Company", series["label"])
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
