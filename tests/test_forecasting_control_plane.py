import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from engine.forecasting.calibration import check_artifact
from engine.forecasting.ledger import append_decision, load_decisions, score_binary_shadows
from engine.metaculus import forecast as mc_forecast
from engine.metaculus import markets


class ForecastingControlPlaneTests(unittest.TestCase):
    def test_anchor_gate_rejects_threshold_false_positive_old_similarity_would_pass(self):
        title = "Will Bitcoin exceed $138,000 before August 1, 2025?"
        candidate = "Bitcoin exceeds $100,000 before August 1, 2025?"
        self.assertGreaterEqual(markets._similarity(title, candidate), markets.MIN_SIM)

        usable, reasons = markets._usable_match(title, candidate)
        self.assertFalse(usable)
        self.assertIn("money threshold mismatch", reasons)

    def test_anchor_gate_rejects_deadline_false_positive_old_similarity_would_pass(self):
        title = "Will Bitcoin exceed $138,000 before August 1, 2025?"
        candidate = "Bitcoin exceeds $138,000 before December 31, 2025?"
        self.assertGreaterEqual(markets._similarity(title, candidate), markets.MIN_SIM)

        usable, reasons = markets._usable_match(title, candidate)
        self.assertFalse(usable)
        self.assertIn("month/deadline mismatch", reasons)

    def test_anchor_gate_allows_exact_event_match(self):
        title = "Will China invade Taiwan by August 1, 2025?"
        candidate = "China invades Taiwan by August 1, 2025?"
        usable, reasons = markets._usable_match(title, candidate)
        self.assertTrue(usable, reasons)

    def test_calibration_artifact_guard_rejects_tiny_or_nan_artifacts(self):
        tiny = {"valid": True, "n": 3, "d_star": 0.8}
        self.assertFalse(check_artifact(tiny)["usable"])

        bad = {"valid": True, "n": 100, "d_star": float("nan")}
        verdict = check_artifact(bad)
        self.assertFalse(verdict["usable"])
        self.assertTrue(any("d_star" in r for r in verdict["reasons"]))

        good = {"valid": True, "n": 2260, "d_star": 0.8}
        self.assertTrue(check_artifact(good)["usable"])

    def test_ledger_scores_shadow_variants(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "decisions.jsonl"
            append_decision({
                "platform": "test",
                "forecast_type": "binary",
                "question_id": 1,
                "forecast": 0.60,
                "outcome": 1,
                "shadows": {"crowd_only": 0.80, "raw_ensemble": 0.55},
            }, path)
            append_decision({
                "platform": "test",
                "forecast_type": "binary",
                "question_id": 2,
                "forecast": 0.60,
                "outcome": 0,
                "shadows": {"crowd_only": 0.20, "raw_ensemble": 0.55},
            }, path)

            rows = load_decisions(path)
            self.assertEqual(len(rows), 2)
            self.assertTrue(all("record_hash" in r for r in rows))
            scores = score_binary_shadows(rows)
            self.assertLess(scores["crowd_only"]["brier"], scores["final"]["brier"])
            self.assertEqual(scores["crowd_only"]["n"], 2)

    def test_binary_forecast_returns_shadow_and_calibration_metadata_without_model_calls(self):
        old_gather = mc_forecast.research.gather
        old_sample_one = mc_forecast.sample_one
        try:
            mc_forecast.research.gather = lambda *a, **kw: ("dated evidence digest", ["source-a"])

            def fake_sample_one(prompt, models, n, provider, proxy_spec):
                return {str(models[0]): [0.70], str(models[1]): [0.60]}

            mc_forecast.sample_one = fake_sample_one
            out = mc_forecast.forecast_question(
                {"title": "Will the test event happen?", "resolution_criteria": "Test fixture."},
                crowd=0.40,
                n=1,
                min_models=2,
                fill_passes=1,
            )
        finally:
            mc_forecast.research.gather = old_gather
            mc_forecast.sample_one = old_sample_one

        self.assertIn("prompt_hash", out)
        self.assertIn("calibration", out)
        self.assertIn("tag", out["calibration"])
        self.assertIn("raw_ensemble", out["shadows"])
        self.assertIn("no_crowd", out["shadows"])
        self.assertIn("crowd_only", out["shadows"])
        self.assertGreater(out["prob"], 0.40)
        self.assertLess(out["prob"], out["shadows"]["raw_ensemble"])

    def test_binary_forecast_returns_world_state_metadata_when_enabled(self):
        old_gather = mc_forecast.research.gather
        old_sample_one = mc_forecast.sample_one
        captured = {}
        try:
            mc_forecast.research.gather = lambda *a, **kw: ("dated evidence digest", ["source-a"])

            def fake_sample_one(prompt, models, n, provider, proxy_spec):
                captured["prompt"] = prompt
                return {str(models[0]): [0.70], str(models[1]): [0.60]}

            mc_forecast.sample_one = fake_sample_one
            with (
                patch.dict(mc_forecast.os.environ, {"WORLD_STATE_PACK": "proof"}, clear=False),
                patch.object(
                    mc_forecast,
                    "_world_state_context",
                    return_value={
                        "block": "\nFrozen world-state proof:\nproof text",
                        "metadata": {
                            "mode": "proof",
                            "topic": "Will the test event happen?",
                            "as_of": "2026-06-18",
                            "snapshot_hash": "proof_hash",
                            "fact_count": 1,
                            "source_count": 1,
                            "facts": [
                                {
                                    "id": "fact1",
                                    "predicate": "observed test",
                                    "content_hash": "h1",
                                    "raw_doc_status": "offloaded",
                                    "raw_doc_remote_uri": "s3://example/raw/doc.json",
                                }
                            ],
                            "sources": [{"id": "src1", "raw_doc_status": "offloaded"}],
                            "all_visible_as_of_proven": True,
                        },
                    },
                ) as world_state_context,
            ):
                out = mc_forecast.forecast_question(
                    {"title": "Will the test event happen?", "resolution_criteria": "Test fixture."},
                    today="2026-06-18",
                    crowd=0.40,
                    n=1,
                    min_models=2,
                    fill_passes=1,
                )
        finally:
            mc_forecast.research.gather = old_gather
            mc_forecast.sample_one = old_sample_one

        world_state_context.assert_called_once()
        self.assertIn("Frozen world-state proof", captured["prompt"])
        self.assertIn("world_state", out)
        self.assertEqual(out["world_state"]["snapshot_hash"], "proof_hash")
        self.assertEqual(out["world_state"]["facts"][0]["id"], "fact1")
        self.assertEqual(out["world_state"]["facts"][0]["raw_doc_status"], "offloaded")
        self.assertTrue(out["world_state"]["all_visible_as_of_proven"])

    def test_binary_forecast_defers_more_to_native_crowd_when_signal_is_thin(self):
        old_gather = mc_forecast.research.gather
        old_sample_one = mc_forecast.sample_one
        try:
            mc_forecast.research.gather = lambda *a, **kw: ("(no current sources retrieved)", [])

            def fake_sample_one(prompt, models, n, provider, proxy_spec):
                return {str(models[0]): [0.90]}

            mc_forecast.sample_one = fake_sample_one
            out = mc_forecast.forecast_question(
                {"title": "Will the test event happen?", "resolution_criteria": "Test fixture."},
                crowd=0.20,
                n=1,
                min_models=4,
                fill_passes=1,
                ensemble_models=["a", "b", "c", "d"],
            )
        finally:
            mc_forecast.research.gather = old_gather
            mc_forecast.sample_one = old_sample_one

        old_fixed = mc_forecast._sigmoid(
            (1 - mc_forecast.CROWD_WEIGHT) * mc_forecast._logit(0.90)
            + mc_forecast.CROWD_WEIGHT * mc_forecast._logit(0.20)
        )
        self.assertIn("low_model_coverage:1/4", out["quality_flags"])
        self.assertIn("no_retrieved_evidence", out["quality_flags"])
        self.assertGreater(out["calibration"]["applied_crowd_weight"], mc_forecast.CROWD_WEIGHT)
        self.assertLess(out["prob"], round(old_fixed, 3))

    def test_binary_forecast_keeps_explicit_external_anchor_weight_fixed(self):
        old_gather = mc_forecast.research.gather
        old_sample_one = mc_forecast.sample_one
        try:
            mc_forecast.research.gather = lambda *a, **kw: ("(no current sources retrieved)", [])

            def fake_sample_one(prompt, models, n, provider, proxy_spec):
                return {str(models[0]): [0.90]}

            mc_forecast.sample_one = fake_sample_one
            out = mc_forecast.forecast_question(
                {"title": "Will the test event happen?", "resolution_criteria": "Test fixture."},
                crowd=0.20,
                crowd_weight=0.20,
                n=1,
                min_models=4,
                fill_passes=1,
                ensemble_models=["a", "b", "c", "d"],
            )
        finally:
            mc_forecast.research.gather = old_gather
            mc_forecast.sample_one = old_sample_one

        self.assertEqual(out["calibration"]["applied_crowd_weight"], 0.20)

    def test_binary_forecast_blind_low_coverage_shrinks_more_than_fixed_prior(self):
        old_gather = mc_forecast.research.gather
        old_sample_one = mc_forecast.sample_one
        try:
            mc_forecast.research.gather = lambda *a, **kw: ("(no current sources retrieved)", [])

            def fake_sample_one(prompt, models, n, provider, proxy_spec):
                return {str(models[0]): [0.90]}

            mc_forecast.sample_one = fake_sample_one
            out = mc_forecast.forecast_question(
                {"title": "Will the test event happen?", "resolution_criteria": "Test fixture."},
                crowd=None,
                n=1,
                min_models=4,
                fill_passes=1,
                ensemble_models=["a", "b", "c", "d"],
            )
        finally:
            mc_forecast.research.gather = old_gather
            mc_forecast.sample_one = old_sample_one

        old_fixed = mc_forecast._sigmoid(mc_forecast.BLIND_SHRINK * mc_forecast._logit(0.90))
        self.assertLess(out["calibration"]["applied_blind_shrink"], mc_forecast.BLIND_SHRINK)
        self.assertLess(out["prob"], round(old_fixed, 3))


if __name__ == "__main__":
    unittest.main()
