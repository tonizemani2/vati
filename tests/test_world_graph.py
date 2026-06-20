from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine import world_graph


class WorldGraphTests(unittest.TestCase):
    def _board(self):
        return {
            "title": "After AI",
            "date": "2026-06-17",
            "domain": "AI infrastructure",
            "horizon": "2027 to 2029",
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
                    "price_channel": "Data-center site premiums and power-development contracts.",
                    "implications": {
                        "exposed": "Hyperscaler infrastructure teams and data-center developers.",
                        "action_now": "Map sites by firm-power time-to-energize.",
                        "decision_changed": "Data-center site selection and PPA strategy.",
                        "roi_logic": "Earlier energized capacity avoids stranded shells.",
                        "rent_path": "Firm-power optionality and interconnection-ready land.",
                        "next_constraint": "Gas pipeline laterals and switchgear procurement.",
                        "watch": "A 100 MW plus campus announced with behind-the-meter firm power.",
                        "winners": [{"who": "Power-secured campus developers", "why": "They control time-to-energize."}],
                        "losers": [{"who": "Power-light shell developers", "why": "They own buildings without energy."}],
                    },
                }
            ],
        }

    def test_builds_world_graph_atlas(self):
        atlas = world_graph.build_atlas(self._board(), "board.json")
        self.assertEqual(atlas["meta"]["run_mode"], "deterministic_world_graph_compile")
        self.assertEqual(len(atlas["forecast_clauses"]), 1)
        kinds = {node["kind"] for node in atlas["nodes"]}
        for kind in ("domain", "thesis", "constraint", "forecast_clause", "metric", "kill_condition", "observable"):
            self.assertIn(kind, kinds)
        rels = {edge["rel"] for edge in atlas["edges"]}
        self.assertIn("identifies_constraint", rels)
        self.assertIn("resolved_by", rels)
        self.assertIn("falsified_by", rels)
        self.assertTrue(atlas["unknown_queue"])
        self.assertTrue(atlas["watchlist"])
        self.assertGreaterEqual(atlas["coverage"]["score"], 50)
        self.assertEqual(atlas["agent_roster"][0]["role"], "graph_cartographer")
        self.assertRegex(atlas["snapshot_hash"], r"^[a-f0-9]{64}$")

    def test_writes_outputs(self):
        atlas = world_graph.build_atlas(self._board(), "board.json")
        md = world_graph.render_markdown(atlas)
        self.assertIn("World Graph Atlas", md)
        self.assertIn("Unknown Queue", md)
        with tempfile.TemporaryDirectory() as tmp:
            files = world_graph.write_outputs(atlas, tmp)
            self.assertTrue(Path(files["json"]).exists())
            self.assertTrue(Path(files["markdown"]).exists())
            self.assertTrue(Path(files["agent_roster"]).exists())
            loaded = json.loads(Path(files["json"]).read_text())
            self.assertEqual(loaded["meta"]["graph_version"], world_graph.GRAPH_VERSION)


if __name__ == "__main__":
    unittest.main()
