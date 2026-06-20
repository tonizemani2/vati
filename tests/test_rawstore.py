from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine import db, rawstore


def memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


class RawStoreOffloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = memory_db()

    def tearDown(self) -> None:
        self.conn.close()

    def _with_temp_repo(self):
        return tempfile.TemporaryDirectory()

    def _set_repo_root(self, root: Path) -> tuple[Path, Path]:
        old_repo_root = db.REPO_ROOT
        old_raw_root = rawstore.RAW_ROOT
        db.REPO_ROOT = root
        rawstore.RAW_ROOT = root / "data" / "raw"
        rawstore.RAW_ROOT.mkdir(parents=True, exist_ok=True)
        return old_repo_root, old_raw_root

    def _restore_repo_root(self, old_repo_root: Path, old_raw_root: Path) -> None:
        db.REPO_ROOT = old_repo_root
        rawstore.RAW_ROOT = old_raw_root

    def _write_manifest(self, root: Path, raw_root: Path) -> Path:
        manifest = root / "data" / "_offload_manifest.jsonl"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "ts": "2026-06-18T08:39:57+00:00",
                    "local_path": str(raw_root),
                    "remote_uri": "s3://example-bucket/world/data/raw",
                    "size_bytes": 1024,
                    "sha256": None,
                    "uploaded": True,
                    "deleted_local": True,
                    "estimated_storage_usd_month": 0.0,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return manifest

    def test_locate_distinguishes_local_offloaded_and_missing_index(self) -> None:
        with self._with_temp_repo() as tmp:
            root = Path(tmp)
            old_repo_root, old_raw_root = self._set_repo_root(root)
            try:
                manifest = self._write_manifest(root, rawstore.RAW_ROOT)
                local_bytes = b'{"where": "local"}'
                remote_bytes = b'{"where": "remote"}'
                local_hash = rawstore.content_hash(local_bytes)
                remote_hash = rawstore.content_hash(remote_bytes)
                local_rel = f"data/raw/{local_hash[:2]}/{local_hash}.json"
                remote_rel = f"data/raw/{remote_hash[:2]}/{remote_hash}.json"
                local_path = root / local_rel
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(local_bytes)
                self.conn.executemany(
                    """
                    INSERT INTO raw_docs (content_hash,source_id,url,media_type,byte_len,path,fetched_at)
                    VALUES (?,NULL,?,'application/json',?,?, '2026-06-18T00:00:00+00:00')
                    """,
                    [
                        (local_hash, "https://example.test/local", len(local_bytes), local_rel),
                        (remote_hash, "https://example.test/remote", len(remote_bytes), remote_rel),
                    ],
                )
                self.conn.commit()

                local = rawstore.locate(self.conn, local_hash, manifest_path=manifest)
                remote = rawstore.locate(self.conn, remote_hash, manifest_path=manifest)
                missing = rawstore.locate(self.conn, "c" * 64, manifest_path=manifest)

                self.assertEqual(local["status"], "local")
                self.assertTrue(local["exists_local"])
                self.assertIsNone(local["remote_uri"])
                self.assertEqual(remote["status"], "offloaded")
                self.assertFalse(remote["exists_local"])
                self.assertEqual(
                    remote["remote_uri"],
                    f"s3://example-bucket/world/data/raw/{remote_hash[:2]}/{remote_hash}.json",
                )
                self.assertEqual(missing["status"], "missing_index")
            finally:
                self._restore_repo_root(old_repo_root, old_raw_root)

    def test_restore_downloads_one_doc_and_verifies_hash(self) -> None:
        with self._with_temp_repo() as tmp:
            root = Path(tmp)
            old_repo_root, old_raw_root = self._set_repo_root(root)
            try:
                manifest = self._write_manifest(root, rawstore.RAW_ROOT)
                content = b'{"restore": true}'
                h = rawstore.content_hash(content)
                rel = f"data/raw/{h[:2]}/{h}.json"
                self.conn.execute(
                    """
                    INSERT INTO raw_docs (content_hash,source_id,url,media_type,byte_len,path,fetched_at)
                    VALUES (?,NULL,'https://example.test/remote','application/json',?,?, '2026-06-18T00:00:00+00:00')
                    """,
                    (h, len(content), rel),
                )
                self.conn.commit()

                def fake_run(args, capture_output, text):
                    self.assertEqual(args[0:4], ["aws", "s3", "cp", f"s3://example-bucket/world/data/raw/{h[:2]}/{h}.json"])
                    Path(args[4]).write_bytes(content)
                    return subprocess.CompletedProcess(args, 0, "", "")

                with patch.object(rawstore.subprocess, "run", side_effect=fake_run):
                    out = rawstore.restore(self.conn, h, max_bytes=1024, manifest_path=manifest)

                self.assertTrue(out["restored"])
                self.assertEqual(out["status"], "local")
                self.assertEqual((root / rel).read_bytes(), content)
            finally:
                self._restore_repo_root(old_repo_root, old_raw_root)

    def test_restore_refuses_docs_above_byte_cap_before_aws(self) -> None:
        with self._with_temp_repo() as tmp:
            root = Path(tmp)
            old_repo_root, old_raw_root = self._set_repo_root(root)
            try:
                manifest = self._write_manifest(root, rawstore.RAW_ROOT)
                h = "d" * 64
                rel = f"data/raw/{h[:2]}/{h}.json"
                self.conn.execute(
                    """
                    INSERT INTO raw_docs (content_hash,source_id,url,media_type,byte_len,path,fetched_at)
                    VALUES (?,NULL,'https://example.test/huge','application/json',2048,?, '2026-06-18T00:00:00+00:00')
                    """,
                    (h, rel),
                )
                self.conn.commit()

                with patch.object(rawstore.subprocess, "run") as run:
                    with self.assertRaises(ValueError):
                        rawstore.restore(self.conn, h, max_bytes=1024, manifest_path=manifest)
                    run.assert_not_called()
            finally:
                self._restore_repo_root(old_repo_root, old_raw_root)


if __name__ == "__main__":
    unittest.main()
