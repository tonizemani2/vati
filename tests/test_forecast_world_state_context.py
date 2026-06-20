from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from engine.forecastbench import inference
from engine.metaculus import forecast as metaculus_forecast


class ForecastWorldStateContextTests(unittest.TestCase):
    def test_forecastbench_world_state_pack_is_read_only(self) -> None:
        conn = Mock()
        pack = {"snapshot": {"snapshot_hash": "pack_hash"}, "facts": []}
        with (
            patch.dict(os.environ, {"WORLD_STATE_PACK": "1"}, clear=False),
            patch("engine.db.connect", return_value=conn),
            patch("engine.db.init_db"),
            patch("engine.world_state.state_pack", return_value=pack) as state_pack,
            patch("engine.world_state.format_pack", return_value="pack text"),
            patch("engine.world_state.state_proof") as state_proof,
        ):
            block = inference._world_state_block({"question": "AI power bottlenecks"}, "2024-06-01")

        self.assertIn("Frozen world-state context", block)
        self.assertIn("pack text", block)
        state_pack.assert_called_once_with("AI power bottlenecks", "2024-06-01", conn=conn, record=False)
        state_proof.assert_not_called()
        conn.close.assert_called_once_with()

    def test_forecastbench_world_state_proof_mode_uses_proof_context(self) -> None:
        conn = Mock()
        proof = {"snapshot": {"snapshot_hash": "proof_hash"}, "facts": [], "all_visible_as_of_proven": True}
        with (
            patch.dict(os.environ, {"WORLD_STATE_PACK": "proof"}, clear=False),
            patch("engine.db.connect", return_value=conn),
            patch("engine.db.init_db"),
            patch("engine.world_state.state_pack") as state_pack,
            patch("engine.world_state.state_proof", return_value=proof) as state_proof,
            patch("engine.world_state.format_proof", return_value="proof text"),
        ):
            block = inference._world_state_block({"title": "solid state battery"}, "2024-12-31")

        self.assertIn("Frozen world-state proof", block)
        self.assertIn("proof text", block)
        state_proof.assert_called_once_with("solid state battery", "2024-12-31", conn=conn)
        state_pack.assert_not_called()
        conn.close.assert_called_once_with()

    def test_forecastbench_qset_prompt_enables_proof_mode(self) -> None:
        q = {"question": "solid state battery adoption", "source": "fixture"}
        with (
            patch.dict(os.environ, {"WORLD_STATE_PACK": "proof"}, clear=False),
            patch.object(
                inference,
                "_world_state_context",
                return_value={
                    "block": "\nFrozen world-state proof:\nproof text",
                    "metadata": {
                        "mode": "proof",
                        "topic": "solid state battery adoption",
                        "as_of": "2024-12-31",
                        "snapshot_hash": "proof_hash",
                        "fact_count": 1,
                        "source_count": 1,
                        "facts": [{"id": "fact1", "raw_doc_status": "offloaded"}],
                        "sources": [{"id": "src1", "raw_doc_status": "offloaded"}],
                        "all_visible_as_of_proven": True,
                    },
                },
            ) as context,
        ):
            prompt, meta = inference._qset_prompt_with_metadata(q, "2024-12-31")

        self.assertIn("Frozen world-state proof", prompt)
        self.assertEqual(meta["snapshot_hash"], "proof_hash")
        self.assertEqual(meta["facts"][0]["raw_doc_status"], "offloaded")
        self.assertTrue(meta["all_visible_as_of_proven"])
        context.assert_called_once_with(q, "2024-12-31")

    def test_forecastbench_world_state_sidecar_merges_on_resume(self) -> None:
        old_meta = {
            "mode": "proof",
            "topic": "old topic",
            "as_of": "2024-12-31",
            "snapshot_hash": "old_hash",
            "fact_count": 1,
            "source_count": 1,
            "facts": [{"id": "old_fact"}],
            "sources": [{"id": "old_source"}],
            "all_visible_as_of_proven": True,
        }
        new_meta = {
            "mode": "proof",
            "topic": "new topic",
            "as_of": "2024-12-31",
            "snapshot_hash": "new_hash",
            "fact_count": 2,
            "source_count": 1,
            "facts": [{"id": "new_fact"}],
            "sources": [{"id": "new_source"}],
            "all_visible_as_of_proven": True,
        }
        with tempfile.TemporaryDirectory() as td, patch.object(inference, "PRED_DIR", Path(td)):
            path, n_rows = inference._write_world_state_metadata([("q1", old_meta)], "fixture")
            self.assertEqual(n_rows, 1)
            path, n_rows = inference._write_world_state_metadata(
                [("q1", new_meta), ("q2", new_meta)],
                "fixture",
                resume=True,
            )

            rows = {row["id"]: row for row in (json.loads(line) for line in path.read_text().splitlines())}

        self.assertEqual(n_rows, 2)
        self.assertEqual(rows["q1"]["snapshot_hash"], "old_hash")
        self.assertEqual(rows["q2"]["snapshot_hash"], "new_hash")
        self.assertEqual(rows["q2"]["facts"][0]["id"], "new_fact")

    def test_forecastbench_qset_main_writes_world_state_sidecar_without_model_calls(self) -> None:
        qset = {
            "forecast_due_date": "2024-12-31",
            "questions": [{"id": "q1", "question": "AI power bottlenecks", "source": "fixture"}],
        }
        meta = {
            "mode": "proof",
            "topic": "AI power bottlenecks",
            "as_of": "2024-12-31",
            "snapshot_hash": "proof_hash",
            "fact_count": 1,
            "source_count": 1,
            "facts": [{"id": "fact1", "predicate": "capacity", "raw_doc_status": "offloaded"}],
            "sources": [{"id": "src1", "raw_doc_remote_uri": "s3://bucket/raw.json"}],
            "all_visible_as_of_proven": True,
        }
        with tempfile.TemporaryDirectory() as td:
            qset_path = Path(td) / "qset.json"
            qset_path.write_text(json.dumps(qset))
            with (
                patch.object(inference, "PRED_DIR", Path(td) / "preds"),
                patch.object(sys, "argv", ["prog", "--qset", str(qset_path), "--n", "1"]),
                patch("engine.forecastbench.score.single_questions", side_effect=lambda qs: qs),
                patch.object(inference, "_qset_prompt_with_metadata", return_value=("prompt", meta)) as prompt,
                patch.object(inference, "run", return_value=({}, {"q1": 0.42})) as run,
                patch.object(inference, "_write_preds", return_value=([], Path(td) / "pool.jsonl", 1)),
            ):
                inference.main()

            sidecar = Path(td) / "preds" / "world_state_qset_2024-12-31.jsonl"
            rows = [json.loads(line) for line in sidecar.read_text().splitlines()]

        prompt.assert_called_once()
        run.assert_called_once()
        self.assertEqual(rows[0]["id"], "q1")
        self.assertEqual(rows[0]["snapshot_hash"], "proof_hash")
        self.assertEqual(rows[0]["facts"][0]["predicate"], "capacity")
        self.assertEqual(rows[0]["sources"][0]["raw_doc_remote_uri"], "s3://bucket/raw.json")

    def test_metaculus_world_state_proof_mode_uses_proof_context(self) -> None:
        conn = Mock()
        proof = {"snapshot": {"snapshot_hash": "proof_hash"}, "facts": [], "all_visible_as_of_proven": True}
        with (
            patch.dict(os.environ, {"WORLD_STATE_PROOF": "1"}, clear=False),
            patch("engine.db.connect", return_value=conn),
            patch("engine.db.init_db"),
            patch("engine.world_state.state_pack") as state_pack,
            patch("engine.world_state.state_proof", return_value=proof) as state_proof,
            patch("engine.world_state.format_proof", return_value="proof text"),
        ):
            block = metaculus_forecast._world_state_block({"title": "AI power bottlenecks"}, "2024-06-01")

        self.assertIn("Frozen world-state proof", block)
        self.assertIn("proof text", block)
        state_proof.assert_called_once_with("AI power bottlenecks", "2024-06-01", conn=conn)
        state_pack.assert_not_called()
        conn.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
