from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine import world_graph_deepseek


class WorldGraphDeepSeekTests(unittest.TestCase):
    def _board_path(self, tmp: str) -> Path:
        board = {
            "title": "After AI",
            "date": "2026-06-17",
            "domain": "AI infrastructure",
            "theses": [
                {
                    "id": "P1",
                    "headline": "The AI frontier moves from model access to firm-power siting.",
                    "domain": "AI infrastructure / energy",
                    "vision_p": 82,
                    "clause_p": 52,
                    "resolves": "2028-12-31",
                    "needle": "Firm power siting.",
                    "metric": "Count 100 MW plus sites with direct power partnerships.",
                    "kill": "Kill if interconnection and transformer delays normalize.",
                    "price_channel": "Site premiums.",
                    "implications": {
                        "exposed": "Data-center developers.",
                        "action_now": "Map firm-power sites.",
                        "watch": "A 100 MW campus announces behind-the-meter power.",
                    },
                }
            ],
        }
        path = Path(tmp) / "board.json"
        path.write_text(json.dumps(board), encoding="utf-8")
        return path

    def test_standard_plan_is_seventeen_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._board_path(tmp)
            pack = world_graph_deepseek.build_run_pack(path, out_dir=Path(tmp) / "ds", plan="standard")
            self.assertEqual(pack["call_count"], 17)
            ids = [call["id"] for call in pack["calls"]]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(ids[-4:], ["14_integrator", "15_critic", "16_repair", "17_score"])
            self.assertGreater(pack["estimate"]["total_cost_cents_cache_miss"], 0)
            self.assertTrue((Path(tmp) / "ds" / "RUN_MANIFEST.md").exists())
            self.assertTrue((Path(tmp) / "ds" / "call_plan.json").exists())

    def test_full_plan_scales_with_forecasts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._board_path(tmp)
            board = json.loads(path.read_text())
            board["theses"].append({**board["theses"][0], "id": "P2", "headline": "Second thesis"})
            path.write_text(json.dumps(board), encoding="utf-8")
            pack = world_graph_deepseek.build_run_pack(path, out_dir=Path(tmp) / "full", plan="full")
            self.assertEqual(pack["call_count"], 13 + 4 * 2 + 3)
            ids = [call["id"] for call in pack["calls"]]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(ids[-3:], ["22_integrator", "23_critic", "24_repair"])
            rows = json.loads((Path(tmp) / "full" / "call_plan.json").read_text())
            self.assertEqual(rows["plan"], "full")


if __name__ == "__main__":
    unittest.main()
