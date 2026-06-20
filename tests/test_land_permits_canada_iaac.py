from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine.feeds import collect_all, ingest, land_permits_canada_iaac
from engine import world_catalog
from tests.test_world_state import memory_db


ACTIVE_HTML = """
<article>
  <a class="resultJobItem" href="https://iaac-aeic.gc.ca/050/evaluations/proj/90051">
    <h3 class="title"><span class="noctitle">Baptiste Nickel Project</span></h3>
    <ul class="list-unstyled">
      <li class="location"><span class="wb-inv">Location</span> (80 kilometres northwest of Fort St. James, British Columbia)</li>
      <li class="salary"><strong>Assessment Type: </strong>Planning Phase for Impact Assessment</li>
      <li class="salary"><strong>Status: </strong>Suspended</li>
      <li class="salary"><strong>Reference Number: </strong>90051</li>
      <li class="salary"><strong>Last Modified: </strong>2026-06-17</li>
      <li class="salary relevance_score"><strong>Relevance: </strong>799.89</li>
      <li class="business">FPX Nickel Corp. is proposing a new open-pit nickel mine and transmission line.</li>
    </ul>
  </a>
</article>
"""

PERMITS_HTML = """
<article>
  <a class="resultJobItem" href="/050/evaluations/proj/90051">
    <h3 class="title"><span class="noctitle">Baptiste Nickel Project</span></h3>
    <ul class="list-unstyled">
      <li class="location"><span class="wb-inv">Location</span> British Columbia</li>
      <li class="salary"><strong>Assessment Type: </strong>Planning Phase for Impact Assessment</li>
      <li class="salary"><strong>Status: </strong>Suspended</li>
      <li class="salary"><strong>Reference Number: </strong>90051</li>
      <li class="salary"><strong>Last Modified: </strong>2026-06-18</li>
      <li class="business">Permit-related project listing.</li>
    </ul>
  </a>
</article>
"""


class CanadaIAACLandPermitTests(unittest.TestCase):
    def test_parse_pages_dedupes_project_and_keeps_scope(self) -> None:
        rows = land_permits_canada_iaac.parse_pages(
            [
                (land_permits_canada_iaac.PAGES[0], ACTIVE_HTML),
                (land_permits_canada_iaac.PAGES[1], PERMITS_HTML),
            ]
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["reference_number"], "90051")
        self.assertEqual(row["project"], "Baptiste Nickel Project")
        self.assertEqual(row["date"], "2026-06-18")
        self.assertIn("active_projects", row["source_page_scope"])
        self.assertIn("permits", row["source_page_scope"])
        self.assertEqual(row["series_id"], "land_permits_canada_iaac:project:90051")
        self.assertEqual(row["metric"], "impact_assessment_project_status")
        self.assertEqual(row["value"], 1.0)
        self.assertIn("Baptiste Nickel", row["title"])

    def test_collect_writes_jsonl_from_official_pages(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            old_out = land_permits_canada_iaac.OUT_PATH
            land_permits_canada_iaac.OUT_PATH = Path(td) / "land_permits_canada_iaac.jsonl"
            try:
                with mock.patch.object(
                    land_permits_canada_iaac,
                    "_fetch_text",
                    side_effect=[ACTIVE_HTML, PERMITS_HTML, ""],
                ):
                    rows = land_permits_canada_iaac.collect(log=lambda *_: None)
                stored = [
                    json.loads(line)
                    for line in land_permits_canada_iaac.OUT_PATH.read_text(encoding="utf-8").splitlines()
                ]
            finally:
                land_permits_canada_iaac.OUT_PATH = old_out

        self.assertEqual(len(rows), 1)
        self.assertEqual(stored[0]["feed"], "land_permits_canada_iaac")
        self.assertEqual(stored[0]["cost_cents"], 0)
        self.assertEqual(stored[0]["provenance"], "official_iaac_search_result_page")

    def test_collector_is_keyless_ingestable_and_mapped_to_eia_source(self) -> None:
        self.assertIn("land_permits_canada_iaac", collect_all.KEYLESS)
        self.assertIn("land_permits_canada_iaac", ingest.FEED_META)
        self.assertIn("land_permits_canada_iaac", world_catalog.SOURCE_FEED_MAP["environmental_planning_eia"])

    def test_ingest_lands_project_rows_as_series_and_raw_doc(self) -> None:
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
                path = feed_dir / "land_permits_canada_iaac.jsonl"
                row = land_permits_canada_iaac.parse_pages(
                    [(land_permits_canada_iaac.PAGES[0], ACTIVE_HTML)]
                )[0]
                path.write_text(json.dumps(row) + "\n", encoding="utf-8")
                with mock.patch.object(ingest, "FEEDS_DIR", feed_dir):
                    out = ingest.ingest_feed(conn, "land_permits_canada_iaac")

            self.assertEqual(out["status"], "ok")
            self.assertEqual(out["series"], 1)
            self.assertEqual(out["obs"], 1)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS n FROM raw_docs").fetchone()["n"],
                1,
            )
            series = conn.execute(
                "SELECT provider, external_id, metric, label FROM series"
            ).fetchone()
            self.assertEqual(series["provider"], "land_permits_canada_iaac")
            self.assertEqual(series["external_id"], "land_permits_canada_iaac:project:90051")
            self.assertIn("Baptiste Nickel Project", series["label"])
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
