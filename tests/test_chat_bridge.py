from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from engine import chat_bridge, world_state


class ChatBridgeWorldStateProofTests(unittest.TestCase):
    def _run(self, cmd: str, spec: dict) -> tuple[int, dict]:
        old_stdin = chat_bridge.sys.stdin
        chat_bridge.sys.stdin = io.StringIO(json.dumps(spec))
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = chat_bridge.main(["chat_bridge", cmd])
            return code, json.loads(buf.getvalue())
        finally:
            chat_bridge.sys.stdin = old_stdin

    def test_world_state_proof_bridge_returns_context_and_does_not_record_snapshot(self) -> None:
        proof = {
            "ok": True,
            "engine": "world_state_v1_proof",
            "topic": "solid state battery",
            "as_of": "2024-12-31",
            "snapshot": {
                "topic": "solid state battery",
                "as_of": "2024-12-31",
                "created_at": "2026-06-18T00:00:00+00:00",
                "query_version": "world_state_v1",
                "fact_count": 1,
                "source_count": 1,
                "snapshot_hash": "abc123",
            },
            "facts": [
                {
                    "id": "fact1",
                    "predicate": "observed deployment",
                    "raw_doc_status": "offloaded",
                    "raw_doc_remote_uri": "s3://example/raw/doc.json",
                    "visible_as_of_proven": True,
                    "gates": {
                        "published_at": {"passes": True},
                        "observed_at": {"passes": True},
                        "event_time": {"passes": True},
                        "ingested_at": {"passes": True},
                    },
                }
            ],
            "sources": [],
            "exclusions": {},
            "all_visible_as_of_proven": True,
        }
        conn = Mock()
        with (
            patch("engine.db.connect", return_value=conn) as connect,
            patch("engine.db.init_db") as init_db,
            patch("engine.world_state.state_proof", return_value=proof) as state_proof,
            patch("engine.world_state.format_proof", return_value="proof context") as format_proof,
        ):
            code, out = self._run(
                "world_state_proof",
                {"topic": "solid state battery", "as_of": "2024-12-31", "limit": 3},
            )

        self.assertEqual(code, 0)
        self.assertTrue(out["ok"])
        self.assertEqual(out["engine"], "world_state_v1_proof")
        self.assertEqual(out["context"], "proof context")
        self.assertEqual(out["snapshot"]["snapshot_hash"], "abc123")
        self.assertEqual(out["facts"][0]["raw_doc_status"], "offloaded")
        self.assertTrue(out["all_visible_as_of_proven"])
        connect.assert_called_once_with()
        init_db.assert_called_once_with(conn)
        state_proof.assert_called_once_with("solid state battery", "2024-12-31", conn=conn, limit=3)
        format_proof.assert_called_once_with(proof)
        conn.close.assert_called_once_with()

    def test_world_state_proof_bridge_requires_topic(self) -> None:
        code, out = self._run("world_state_proof", {"as_of": "2024-12-31"})

        self.assertEqual(code, 1)
        self.assertFalse(out["ok"])
        self.assertIn("world_state_proof needs", out["error"])

    def test_world_state_bridge_can_run_without_recording_snapshot(self) -> None:
        pack = {
            "ok": True,
            "engine": "world_state_v1",
            "topic": "solid state battery",
            "as_of": "2024-12-31",
            "snapshot": {"snapshot_hash": "readonly_hash"},
            "facts": [],
            "sources": [],
            "exclusions": {},
        }
        conn = Mock()
        with (
            patch("engine.db.connect", return_value=conn),
            patch("engine.db.init_db"),
            patch("engine.world_state.state_pack", return_value=pack) as state_pack,
            patch("engine.world_state.format_pack", return_value="pack context"),
        ):
            code, out = self._run(
                "world_state",
                {"topic": "solid state battery", "as_of": "2024-12-31", "record": False},
            )

        self.assertEqual(code, 0)
        self.assertEqual(out["snapshot"]["snapshot_hash"], "readonly_hash")
        self.assertEqual(out["context"], "pack context")
        state_pack.assert_called_once_with("solid state battery", "2024-12-31", conn=conn, record=False)
        conn.close.assert_called_once_with()

    def test_world_state_bridge_records_by_default(self) -> None:
        pack = {
            "ok": True,
            "engine": "world_state_v1",
            "topic": "solid state battery",
            "as_of": "2024-12-31",
            "snapshot": {"snapshot_hash": "recorded_hash"},
            "facts": [],
            "sources": [],
            "exclusions": {},
        }
        conn = Mock()
        with (
            patch("engine.db.connect", return_value=conn),
            patch("engine.db.init_db"),
            patch("engine.world_state.state_pack", return_value=pack) as state_pack,
            patch("engine.world_state.format_pack", return_value="pack context"),
        ):
            code, _ = self._run(
                "world_state",
                {"topic": "solid state battery", "as_of": "2024-12-31"},
            )

        self.assertEqual(code, 0)
        state_pack.assert_called_once_with("solid state battery", "2024-12-31", conn=conn, record=True)

    def test_world_research_bridge_returns_context(self) -> None:
        pack = {
            "ok": True,
            "engine": "world_state_v1_research",
            "topic": "solid state battery",
            "as_of": "2023-12-31",
            "snapshot": {"snapshot_hash": "research_hash"},
            "facts": [],
            "papers": [{"id": "p1", "title": "Solid state battery", "published": "2023-01-01"}],
            "sources": [],
            "summaries": {},
            "exclusions": {},
        }
        conn = Mock()
        with (
            patch("engine.db.connect", return_value=conn),
            patch("engine.db.init_db"),
            patch("engine.world_state.research_pack", return_value=pack) as research_pack,
            patch("engine.world_state.format_research_pack", return_value="research context"),
        ):
            code, out = self._run(
                "world_research",
                {
                    "topic": "solid state battery",
                    "as_of": "2023-12-31",
                    "paper_limit": 5,
                    "fact_limit": 2,
                },
            )

        self.assertEqual(code, 0)
        self.assertEqual(out["snapshot"]["snapshot_hash"], "research_hash")
        self.assertEqual(out["context"], "research context")
        research_pack.assert_called_once_with(
            "solid state battery",
            "2023-12-31",
            conn=conn,
            paper_limit=5,
            fact_limit=2,
            count_fact_exclusions=False,
            count_paper_exclusions=False,
            search_abstracts=False,
            fill_token_fallback=False,
            full_paper_scan=False,
            paper_scan_rows=world_state.DEFAULT_RESEARCH_PAPER_SCAN_ROWS,
        )
        conn.close.assert_called_once_with()

    def test_world_research_bridge_requires_topic(self) -> None:
        code, out = self._run("world_research", {"as_of": "2023-12-31"})

        self.assertEqual(code, 1)
        self.assertFalse(out["ok"])
        self.assertIn("world_research needs", out["error"])


if __name__ == "__main__":
    unittest.main()
