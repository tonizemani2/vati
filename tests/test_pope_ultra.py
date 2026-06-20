from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.pope.ultra import build_dossier, render_markdown, write_outputs


class PopeUltraTests(unittest.TestCase):
    def _board(self):
        return {
            "title": "After AI",
            "date": "2026-06-17",
            "theses": [
                {
                    "id": "P1",
                    "headline": "The AI frontier moves from model access to firm-power siting.",
                    "domain": "AI infrastructure / energy",
                    "vision_p": 82,
                    "clause_p": 52,
                    "resolves": "2028-12-31",
                    "needle": "Behind-the-meter firm generation rights and interconnection optionality.",
                    "metric": "Track 100 MW plus campuses with direct power-development partnerships.",
                    "kill": "Kill if transformer and interconnection delays normalize below 24 months.",
                    "implications": {
                        "exposed": "Hyperscaler infrastructure teams and data-center developers.",
                        "action_now": "Map sites by firm-power time-to-energize.",
                        "decision_changed": "Data-center site selection and PPA strategy.",
                        "roi_logic": "Earlier energized capacity avoids stranded shells.",
                        "watch": "A 100 MW plus campus announced with behind-the-meter firm power.",
                    },
                }
            ],
        }

    def test_builds_truth_seeking_dossier(self):
        ultra = build_dossier(self._board(), "board.json")
        self.assertEqual(len(ultra["dossiers"]), 1)
        dossier = ultra["dossiers"][0]
        self.assertEqual(dossier["thesis_id"], "P1")
        self.assertIn("Do not invent named permits", ultra["truth_rules"][0])
        self.assertGreaterEqual(len(dossier["execution_packets"]), 7)
        kinds = {p["kind"] for p in dossier["execution_packets"]}
        self.assertIn("permit_docket", kinds)
        self.assertIn("interconnection_power", kinds)
        self.assertIn("person_contact", kinds)
        for packet in dossier["execution_packets"]:
            self.assertEqual(packet["truth_status"], "unverified")
            self.assertTrue(packet["required_fields"])
            self.assertTrue(packet["seed_queries"])

    def test_thesis_filter(self):
        ultra = build_dossier(self._board(), "board.json", thesis_filter="P1")
        self.assertEqual(len(ultra["dossiers"]), 1)
        with self.assertRaises(SystemExit):
            build_dossier(self._board(), "board.json", thesis_filter="P9")

    def test_writes_outputs(self):
        ultra = build_dossier(self._board(), "board.json")
        md = render_markdown(ultra)
        self.assertIn("Execution Packets", md)
        self.assertIn("contact", md.lower())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            write_outputs(ultra, out)
            self.assertTrue((out / "ultra.json").exists())
            self.assertTrue((out / "ultra.md").exists())
            self.assertTrue((out / "task_queue.csv").exists())
            loaded = json.loads((out / "ultra.json").read_text())
            self.assertEqual(loaded["run_mode"], "deterministic_ultra_scaffold")


if __name__ == "__main__":
    unittest.main()
