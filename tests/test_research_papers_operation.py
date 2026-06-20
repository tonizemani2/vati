from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from engine import db, research_papers


def memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


class ResearchPapersOperationTests(unittest.TestCase):
    def test_plan_includes_arxiv_full_text_as_remote_metered_source(self) -> None:
        payload = research_papers.plan()
        sources = {row["id"]: row for row in payload["sources"]}

        self.assertIn("arxiv_full_text", sources)
        self.assertTrue(sources["arxiv_full_text"]["metered"])
        self.assertIn("remote-only", sources["arxiv_full_text"]["remote_action"])

    def test_execute_validation_requires_remote_metered_and_budget(self) -> None:
        blockers = research_papers.validate_execute(
            remote_prefix=None,
            budget_usd=0.0,
            allow_metered=False,
        )

        self.assertIn("remote_prefix_required_for_bulk_storage", blockers)
        self.assertIn("allow_metered_required_for_requester_pays_or_paid_snapshots", blockers)
        self.assertIn("positive_budget_usd_required", blockers)

    def test_bootstrap_writes_small_manifest_without_bulk_execution(self) -> None:
        conn = memory_db()
        with tempfile.TemporaryDirectory() as tmp:
            old_op_dir = research_papers.OP_DIR
            old_manifest = research_papers.MANIFEST_PATH
            old_run_log = research_papers.RUN_LOG_PATH
            try:
                research_papers.OP_DIR = Path(tmp) / "research_papers"
                research_papers.MANIFEST_PATH = research_papers.OP_DIR / "operation_manifest.json"
                research_papers.RUN_LOG_PATH = research_papers.OP_DIR / "run_log.jsonl"

                payload = research_papers.bootstrap(conn=conn)

                self.assertEqual(payload["status"], "planned")
                self.assertFalse(payload["execute_requested"])
                self.assertTrue(research_papers.MANIFEST_PATH.exists())
                written = json.loads(research_papers.MANIFEST_PATH.read_text(encoding="utf-8"))
                self.assertEqual(written["status"], "planned")
                self.assertEqual(written["local_status"]["db_counts"]["papers"], 0)
            finally:
                research_papers.OP_DIR = old_op_dir
                research_papers.MANIFEST_PATH = old_manifest
                research_papers.RUN_LOG_PATH = old_run_log
                conn.close()


if __name__ == "__main__":
    unittest.main()
