from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import data_offload


class DataOffloadTests(unittest.TestCase):
    def test_inventory_finds_large_files_and_marks_critical(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db_file = root / "data" / "foresight.db"
            small = root / "data" / "small.txt"
            db_file.parent.mkdir()
            db_file.write_bytes(b"x" * 2048)
            small.write_bytes(b"tiny")

            entries = data_offload.iter_large_files(root / "data", min_size_mb=0.001)

            self.assertEqual([e.path for e in entries], [db_file.resolve()])
            self.assertTrue(entries[0].critical)

    def test_s3_uri_preserves_repo_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            local = root / "data" / "corpus" / "arxiv.parquet"
            local.parent.mkdir(parents=True)
            local.write_bytes(b"x")

            uri = data_offload.s3_uri_for(local, base=root, dest_prefix="s3://bucket/vati")

            self.assertEqual(uri, "s3://bucket/vati/data/corpus/arxiv.parquet")

    def test_dry_run_does_not_upload_or_delete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            local = root / "data" / "big.bin"
            local.parent.mkdir()
            local.write_bytes(b"x" * 2048)
            entries = data_offload.iter_large_files(root / "data", min_size_mb=0.001)

            results = data_offload.offload(
                entries,
                base=root,
                dest_prefix="s3://bucket/vati",
                execute=False,
                delete_local=True,
            )

            self.assertTrue(local.exists())
            self.assertFalse(results[0].uploaded)
            self.assertFalse(results[0].deleted_local)
            rendered = data_offload.format_offload_plan(results, execute=False, delete_local=True)
            self.assertIn("--delete-local was ignored", rendered)

    def test_inventory_summary_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            db_file = root / "data" / "foresight.db"
            bin_file = root / "data" / "big.bin"
            db_file.parent.mkdir()
            db_file.write_bytes(b"x" * 2048)
            bin_file.write_bytes(b"y" * 4096)

            entries = data_offload.iter_large_files(root / "data", min_size_mb=0.001)
            summary = data_offload.inventory_summary(entries, base=root)

            self.assertEqual(summary["entries"], 2)
            self.assertEqual(summary["critical_entries"], 1)
            self.assertGreater(summary["estimated_storage_usd_month"], 0)
            self.assertEqual(summary["files"][0]["path"], "data/big.bin")

    def test_delete_local_refuses_critical_file_without_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            local = root / "data" / "foresight.db"
            local.parent.mkdir()
            local.write_bytes(b"x" * 2048)
            entries = data_offload.iter_large_files(root / "data", min_size_mb=0.001)

            with mock.patch.object(data_offload, "aws_cp") as aws_cp, mock.patch.object(
                data_offload,
                "aws_remote_size",
                return_value=local.stat().st_size,
            ):
                with self.assertRaises(data_offload.DataOffloadError):
                    data_offload.offload(
                        entries,
                        base=root,
                        dest_prefix="s3://bucket/vati",
                        execute=True,
                        delete_local=True,
                    )

            self.assertTrue(local.exists())
            aws_cp.assert_not_called()

    def test_execute_records_manifest_and_restore_plan(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            local = root / "data" / "big.bin"
            manifest = root / "data" / "_offload_manifest.jsonl"
            local.parent.mkdir()
            local.write_bytes(b"x" * 2048)
            entries = data_offload.iter_large_files(root / "data", min_size_mb=0.001)

            with mock.patch.object(data_offload, "aws_cp") as aws_cp, mock.patch.object(
                data_offload,
                "aws_remote_size",
                return_value=local.stat().st_size,
            ):
                results = data_offload.offload(
                    entries,
                    base=root,
                    dest_prefix="s3://bucket/vati",
                    execute=True,
                    manifest_path=manifest,
                )

            self.assertTrue(local.exists())
            self.assertTrue(results[0].uploaded)
            self.assertIsNotNone(results[0].sha256)
            self.assertGreater(results[0].estimated_storage_usd_month, 0)
            self.assertTrue(manifest.exists())
            recorded = data_offload.read_manifest(manifest)
            self.assertEqual(len(recorded), 1)
            self.assertEqual(recorded[0].remote_uri, "s3://bucket/vati/data/big.bin")
            self.assertGreater(recorded[0].estimated_storage_usd_month, 0)
            summary = data_offload.manifest_summary(recorded)
            self.assertEqual(summary["entries"], 1)
            self.assertEqual(summary["uploaded"], 1)
            self.assertEqual(summary["local_deleted"], 0)
            self.assertEqual(summary["files"][0]["remote_uri"], "s3://bucket/vati/data/big.bin")
            self.assertEqual(
                data_offload.restore_commands(recorded),
                [f"aws s3 cp s3://bucket/vati/data/big.bin {local} --only-show-errors"],
            )
            self.assertIn("est $", data_offload.format_manifest(recorded))
            self.assertIn("aws s3 cp s3://bucket/vati/data/big.bin", data_offload.format_restore_plan(recorded))
            aws_cp.assert_called_once()

    def test_execute_can_delete_noncritical_file_after_verified_upload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            local = root / "data" / "big.bin"
            local.parent.mkdir()
            local.write_bytes(b"x" * 2048)
            entries = data_offload.iter_large_files(root / "data", min_size_mb=0.001)

            with mock.patch.object(data_offload, "aws_cp"), mock.patch.object(
                data_offload,
                "aws_remote_size",
                return_value=local.stat().st_size,
            ):
                results = data_offload.offload(
                    entries,
                    base=root,
                    dest_prefix="s3://bucket/vati",
                    execute=True,
                    delete_local=True,
                )

            self.assertFalse(local.exists())
            self.assertTrue(results[0].uploaded)
            self.assertTrue(results[0].deleted_local)

    def test_missing_manifest_status_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            entries = data_offload.read_manifest(Path(td) / "missing.jsonl")

            self.assertEqual(entries, [])
            self.assertIn("No offload manifest", data_offload.format_manifest(entries))


if __name__ == "__main__":
    unittest.main()
