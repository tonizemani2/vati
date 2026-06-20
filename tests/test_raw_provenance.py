from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from engine import db, raw_provenance, rawstore


def memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_db(conn)
    conn.execute(
        "INSERT OR IGNORE INTO pillars (id,name,description,ord,status) VALUES (1,'Frontier','test',1,'in_progress')"
    )
    return conn


def insert_source(conn: sqlite3.Connection, *, url: str, content_hash: str, source_id: str = "src") -> None:
    conn.execute(
        """
        INSERT INTO sources
            (id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,cost_cents,content_hash)
        VALUES
            (?,?,'Fixture Source',1,'primary',90,'test source','2026-01-01T00:00:00+00:00',0,?)
        """,
        (source_id, url, content_hash),
    )
    conn.commit()


class RawProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = memory_db()

    def tearDown(self) -> None:
        self.conn.close()

    def test_recovery_stores_only_exact_hash_match(self) -> None:
        old_root = rawstore.RAW_ROOT
        content = b'{"stable": true}\n'
        h = rawstore.content_hash(content)
        insert_source(self.conn, url="https://example.test/source.json", content_hash=h)

        def fetcher(url: str, *, max_bytes: int, timeout: float) -> raw_provenance.FetchedBytes:
            return raw_provenance.FetchedBytes(url=url, content=content, media_type="application/json")

        try:
            with tempfile.TemporaryDirectory(dir=db.REPO_ROOT / "data") as tmp:
                rawstore.RAW_ROOT = Path(tmp) / "raw"
                out = raw_provenance.recover_missing_raw_docs(
                    self.conn,
                    execute=True,
                    allow_prefixes=("https://example.test/",),
                    fetcher=fetcher,
                )
                raw = self.conn.execute(
                    "SELECT source_id, byte_len, media_type FROM raw_docs WHERE content_hash=?",
                    (h,),
                ).fetchone()
                src = self.conn.execute(
                    "SELECT raw_provenance_status, raw_provenance_reason FROM sources WHERE id='src'"
                ).fetchone()

                self.assertEqual(out["matched"], 1)
                self.assertEqual(out["stored"], 1)
                self.assertEqual(raw["source_id"], "src")
                self.assertEqual(raw["byte_len"], len(content))
                self.assertEqual(raw["media_type"], "application/json")
                self.assertEqual(src["raw_provenance_status"], raw_provenance.EXACT_RAW_DOC)
                self.assertIn("exact bytes", src["raw_provenance_reason"])
                self.assertEqual(rawstore.get(h), content)
        finally:
            rawstore.RAW_ROOT = old_root

    def test_recovery_refuses_hash_mismatch_even_in_execute_mode(self) -> None:
        old_root = rawstore.RAW_ROOT
        h = rawstore.content_hash(b"original bytes")
        insert_source(self.conn, url="https://example.test/source.json", content_hash=h)

        def fetcher(url: str, *, max_bytes: int, timeout: float) -> raw_provenance.FetchedBytes:
            return raw_provenance.FetchedBytes(url=url, content=b"changed bytes", media_type="application/json")

        try:
            with tempfile.TemporaryDirectory(dir=db.REPO_ROOT / "data") as tmp:
                rawstore.RAW_ROOT = Path(tmp) / "raw"
                out = raw_provenance.recover_missing_raw_docs(
                    self.conn,
                    execute=True,
                    allow_prefixes=("https://example.test/",),
                    fetcher=fetcher,
                )
                raw = self.conn.execute("SELECT 1 FROM raw_docs WHERE content_hash=?", (h,)).fetchone()

                self.assertEqual(out["matched"], 0)
                self.assertEqual(out["stored"], 0)
                self.assertEqual(out["mismatched"], 1)
                self.assertIsNone(raw)
                self.assertIsNone(rawstore.get(h))
        finally:
            rawstore.RAW_ROOT = old_root

    def test_recovery_skips_urls_outside_allowlist_without_fetching(self) -> None:
        h = rawstore.content_hash(b"payload")
        insert_source(self.conn, url="https://not-allowed.test/source.json", content_hash=h)

        def fetcher(url: str, *, max_bytes: int, timeout: float) -> raw_provenance.FetchedBytes:
            raise AssertionError("fetcher should not be called for disallowed URLs")

        out = raw_provenance.recover_missing_raw_docs(
            self.conn,
            execute=True,
            allow_prefixes=("https://example.test/",),
            fetcher=fetcher,
        )

        self.assertEqual(out["skipped"], 1)
        self.assertEqual(out["skip_reasons"]["prefix_not_allowed"], 1)
        self.assertEqual(out["fetched"], 0)

    def test_recovery_skips_malformed_urls_without_fetching(self) -> None:
        h = rawstore.content_hash(b"payload")
        insert_source(self.conn, url="https://example.test/source with spaces.json", content_hash=h)

        def fetcher(url: str, *, max_bytes: int, timeout: float) -> raw_provenance.FetchedBytes:
            raise AssertionError("fetcher should not be called for malformed URLs")

        out = raw_provenance.recover_missing_raw_docs(
            self.conn,
            execute=True,
            allow_prefixes=("https://example.test/",),
            fetcher=fetcher,
        )

        self.assertEqual(out["skipped"], 1)
        self.assertEqual(out["skip_reasons"]["url_has_spaces_or_control_chars"], 1)
        self.assertEqual(out["fetched"], 0)

    def test_raw_gap_summary_groups_missing_bytes_by_host_and_status(self) -> None:
        h1 = rawstore.content_hash(b"payload 1")
        h2 = rawstore.content_hash(b"payload 2")
        insert_source(
            self.conn,
            source_id="openalex_gap",
            url="https://api.openalex.org/works?filter=test",
            content_hash=h1,
        )
        insert_source(
            self.conn,
            source_id="malformed_gap",
            url="https://comtradeapi.un.org/public/v1/preview/C/A/HS (cmd 2846)",
            content_hash=h2,
        )
        self.conn.execute(
            "UPDATE sources SET raw_provenance_status=? WHERE id='openalex_gap'",
            (raw_provenance.LEGACY_HASH_NO_RAW_DOC,),
        )
        self.conn.commit()

        summary = raw_provenance.raw_gap_summary(self.conn)
        by_host = {row["host"]: row["sources"] for row in summary["top_hosts"]}

        self.assertEqual(summary["total"], 2)
        self.assertEqual(by_host["api.openalex.org"], 1)
        self.assertEqual(by_host["url_has_spaces_or_control_chars"], 1)
        self.assertEqual(summary["malformed_or_nonfetchable_url_count"], 1)
        self.assertEqual(summary["by_status"][raw_provenance.LEGACY_HASH_NO_RAW_DOC], 1)

    def test_mark_legacy_provenance_classifies_exact_and_legacy_sources(self) -> None:
        old_root = rawstore.RAW_ROOT
        exact = b"exact bytes"
        exact_hash = rawstore.content_hash(exact)
        legacy_hash = rawstore.content_hash(b"missing bytes")
        insert_source(
            self.conn,
            source_id="exact_src",
            url="https://example.test/exact.json",
            content_hash=exact_hash,
        )
        insert_source(
            self.conn,
            source_id="legacy_hash_src",
            url="https://example.test/legacy.json",
            content_hash=legacy_hash,
        )
        insert_source(
            self.conn,
            source_id="legacy_no_hash_src",
            url="https://example.test/no-hash.json",
            content_hash="",
        )

        try:
            with tempfile.TemporaryDirectory(dir=db.REPO_ROOT / "data") as tmp:
                rawstore.RAW_ROOT = Path(tmp) / "raw"
                rawstore.put(
                    self.conn,
                    exact,
                    source_id="exact_src",
                    url="https://example.test/exact.json",
                    media_type="application/json",
                )
                self.conn.execute(
                    "UPDATE sources SET raw_provenance_status='unknown' WHERE id='exact_src'"
                )
                self.conn.commit()

                out = raw_provenance.mark_legacy_provenance(self.conn)
                rows = {
                    r["id"]: r["raw_provenance_status"]
                    for r in self.conn.execute("SELECT id, raw_provenance_status FROM sources")
                }

                self.assertEqual(out["updated_exact_raw_doc"], 1)
                self.assertEqual(out["updated_legacy_hash_no_raw_doc"], 1)
                self.assertEqual(out["updated_legacy_no_content_hash"], 1)
                self.assertEqual(rows["exact_src"], raw_provenance.EXACT_RAW_DOC)
                self.assertEqual(rows["legacy_hash_src"], raw_provenance.LEGACY_HASH_NO_RAW_DOC)
                self.assertEqual(rows["legacy_no_hash_src"], raw_provenance.LEGACY_NO_CONTENT_HASH)
        finally:
            rawstore.RAW_ROOT = old_root


if __name__ == "__main__":
    unittest.main()
