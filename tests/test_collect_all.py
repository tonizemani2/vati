from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from engine.feeds import collect_all


class CollectAllSafetyTests(unittest.TestCase):
    def test_safe_local_skips_known_slow_and_oversized_existing_feeds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            feed_dir = Path(td)
            (feed_dir / "fred_financial.jsonl").write_bytes(b"x" * 4096)

            with mock.patch.object(collect_all, "FEEDS_DIR", feed_dir):
                names, skipped = collect_all.select_collectors(
                    ["openalex", "gdelt", "fred_financial"],
                    safe_local=True,
                    max_feed_mb=0.001,
                )

        self.assertEqual(names, ["openalex"])
        self.assertEqual(
            [(row["name"], row["reason"].split(">")[0]) for row in skipped],
            [
                ("gdelt", "known_slow_or_rate_limited"),
                ("fred_financial", "existing_feed_file"),
            ],
        )

    def test_safe_local_only_slow_feed_returns_empty_selection(self) -> None:
        names, skipped = collect_all.select_collectors(["gdelt"], safe_local=True)

        self.assertEqual(names, [])
        self.assertEqual(skipped[0]["reason"], "known_slow_or_rate_limited")

    def test_safe_local_skips_visibility_limited_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            feed_dir = Path(td)
            (feed_dir / "metaculus.status.json").write_text(
                json.dumps({
                    "feed": "metaculus",
                    "visibility_limited": True,
                    "works": False,
                    "rows": 0,
                    "reason": "dated community aggregates hidden",
                }),
                encoding="utf-8",
            )

            with mock.patch.object(collect_all, "FEEDS_DIR", feed_dir):
                names, skipped = collect_all.select_collectors(["metaculus"], safe_local=True)

        self.assertEqual(names, [])
        self.assertEqual(skipped[0]["reason"], "diagnostic_visibility_limited")

    def test_stale_only_skips_fresh_nonempty_feeds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            feed_dir = Path(td)
            (feed_dir / "openalex.jsonl").write_text("{}\n", encoding="utf-8")

            with mock.patch.object(collect_all, "FEEDS_DIR", feed_dir):
                names, skipped = collect_all.select_collectors(
                    ["openalex", "pubmed"],
                    stale_only=True,
                    stale_hours=24,
                )

        self.assertEqual(names, ["pubmed"])
        self.assertEqual(skipped[0]["name"], "openalex")
        self.assertEqual(skipped[0]["reason"], "fresh_feed_file<=24h")

    def test_stale_only_keeps_old_and_empty_feeds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            feed_dir = Path(td)
            old = feed_dir / "openalex.jsonl"
            old.write_text("{}\n", encoding="utf-8")
            empty = feed_dir / "pubmed.jsonl"
            empty.write_text("", encoding="utf-8")
            stale_ts = time.time() - 3 * 3600
            os.utime(old, (stale_ts, stale_ts))

            with mock.patch.object(collect_all, "FEEDS_DIR", feed_dir):
                names, skipped = collect_all.select_collectors(
                    ["openalex", "pubmed"],
                    stale_only=True,
                    stale_hours=1,
                )

        self.assertEqual(names, ["openalex", "pubmed"])
        self.assertEqual(skipped, [])

    def test_dry_run_does_not_spawn_collectors_or_ingest(self) -> None:
        stdout = io.StringIO()
        with (
            mock.patch.object(sys, "argv", ["prog", "--only", "openalex", "--dry-run"]),
            mock.patch.object(collect_all.subprocess, "run") as run,
            contextlib.redirect_stdout(stdout),
        ):
            code = collect_all.main()

        self.assertEqual(code, 0)
        run.assert_not_called()
        self.assertIn("dry run", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
