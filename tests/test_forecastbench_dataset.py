from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

from engine import db
from engine.forecastbench import check_submission
from engine.forecastbench import dataset as ds
from engine.forecastbench import diversify
from engine.forecastbench import llm_fill
from engine.forecastbench import market
from engine.forecastbench import opus_blend
from engine.forecastbench import opus_forecaster
from engine.forecastbench import submit


class ForecastBenchDatasetTests(unittest.TestCase):
    def test_seasonal_climatology_ignores_post_due_observations(self):
        due = date(2025, 6, 1)
        res = date(2026, 12, 15)
        history = []
        cur = date(2024, 1, 1)
        while cur < due:
            history.append((cur, 1.0))
            cur += timedelta(days=1)
        history.extend([
            (date(2025, 6, 1), 10.0),
            (date(2025, 12, 15), 100.0),
        ])

        p = ds.p_higher_seasonal(history, due, res, window=8)

        self.assertAlmostEqual(p, 1 / 19)

    def test_dbnomics_fetch_clears_stale_fail_marker_before_retry(self):
        old_cache = ds.CACHE
        old_get = ds._get
        payload = {
            "series": {
                "docs": [{
                    "period": ["2026-06-01", "2026-06-02"],
                    "value": [12.5, 13.75],
                }]
            }
        }
        try:
            with tempfile.TemporaryDirectory() as td:
                ds.CACHE = Path(td)
                fail = ds.CACHE / "dbn_meteofrance_TEMPERATURE_celsius.07481.D.json.fail"
                fail.write_text("HTTP Error 404: NOT FOUND")

                def fake_get(url, cache_key, ttl_days=3):
                    self.assertFalse(fail.exists())
                    return json.dumps(payload)

                ds._get = fake_get
                rows = ds.fetch_dbnomics(
                    "https://db.nomics.world/meteofrance/TEMPERATURE/celsius.07481.D"
                )
        finally:
            ds.CACHE = old_cache
            ds._get = old_get

        self.assertEqual(rows, [(date(2026, 6, 1), 12.5), (date(2026, 6, 2), 13.75)])

    def test_dbnomics_fetch_salvages_cached_json_after_transient_failure(self):
        old_cache = ds.CACHE
        old_get = ds._get
        payload = {
            "series": {
                "docs": [{
                    "period": ["2026-06-01"],
                    "value": [20.25],
                }]
            }
        }
        try:
            with tempfile.TemporaryDirectory() as td:
                ds.CACHE = Path(td)
                cache = ds.CACHE / "dbn_meteofrance_TEMPERATURE_celsius.07481.D.json"
                cache.write_text(json.dumps(payload))

                def fake_get(url, cache_key, ttl_days=3):
                    raise RuntimeError("transient DBnomics failure")

                ds._get = fake_get
                rows = ds.fetch_dbnomics(
                    "https://db.nomics.world/meteofrance/TEMPERATURE/celsius.07481.D"
                )
        finally:
            ds.CACHE = old_cache
            ds._get = old_get

        self.assertEqual(rows, [(date(2026, 6, 1), 20.25)])

    def test_dataset_calibration_keeps_yfinance_identity_but_moves_dbnomics(self):
        self.assertAlmostEqual(ds.calibrate_dataset_probability("yfinance", 0.60), 0.60)
        self.assertGreater(ds.calibrate_dataset_probability("dbnomics", 0.50), 0.60)

    def test_recent_dataset_calibration_only_applies_after_format_shift(self):
        old_due = date(2025, 8, 31)
        recent_due = date(2025, 10, 26)

        self.assertAlmostEqual(
            ds.calibrate_dataset_probability("yfinance", 0.60, old_due),
            0.60,
        )
        self.assertLess(
            ds.calibrate_dataset_probability("yfinance", 0.60, recent_due),
            0.60,
        )
        self.assertGreater(
            ds.calibrate_dataset_probability("fred", 0.50, recent_due),
            ds.calibrate_dataset_probability("fred", 0.50, old_due),
        )

    def test_market_calibration_applies_source_bias(self):
        self.assertLess(market.calibrate_market_probability("infer", 0.20), 0.20)
        self.assertLess(market.crowd_anchor([{
            "id": "m1",
            "source": "manifold",
            "freeze_datetime_value": 0.40,
        }])["m1"], 0.40)

    def test_submission_creates_missing_output_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            qset = root / "q.json"
            qset.write_text(json.dumps({
                "forecast_due_date": "2026-06-21",
                "question_set": "fixture",
                "questions": [],
            }))
            out = root / "missing" / "nested" / "2026-06-21.Vaticinus.1.json"

            with redirect_stdout(StringIO()):
                submit.make_submission(str(qset), str(out), use_llm=False)

            self.assertTrue(out.exists())
            payload = json.loads(out.read_text())
            self.assertEqual(set(payload), {
                "organization", "model", "model_organization", "question_set", "forecasts",
            })

    def test_fetch_question_set_creates_data_directory_before_download(self):
        old_data = submit.DATA
        old_urlopen = submit.urllib.request.urlopen

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"forecast_due_date":"2026-06-21","question_set":"2026-06-21-llm.json","questions":[{"id":"q1"}]}'

        try:
            with tempfile.TemporaryDirectory() as td:
                submit.DATA = Path(td) / "missing" / "forecastbench"
                submit.urllib.request.urlopen = lambda req, timeout=60: FakeResponse()

                got = submit.fetch_question_set("2026-06-21")

                self.assertEqual(Path(got), submit.DATA / "q_2026-06-21.json")
                self.assertTrue(Path(got).exists())
        finally:
            submit.DATA = old_data
            submit.urllib.request.urlopen = old_urlopen

    def test_fetch_question_set_replaces_stale_cached_question_set(self):
        old_data = submit.DATA
        old_urlopen = submit.urllib.request.urlopen

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({
                    "forecast_due_date": "2026-06-21",
                    "question_set": "2026-06-21-llm.json",
                    "questions": [{"id": "q1"}],
                }).encode()

        try:
            with tempfile.TemporaryDirectory() as td:
                submit.DATA = Path(td)
                stale = submit.DATA / "q_2026-06-21.json"
                stale.write_text(json.dumps({
                    "forecast_due_date": "2026-06-07",
                    "question_set": "2026-06-07-llm.json",
                    "questions": [{"id": "old"}],
                }))
                submit.urllib.request.urlopen = lambda req, timeout=60: FakeResponse()

                got = submit.fetch_question_set("2026-06-21")

                payload = json.loads(Path(got).read_text())
                self.assertEqual(payload["question_set"], "2026-06-21-llm.json")
        finally:
            submit.DATA = old_data
            submit.urllib.request.urlopen = old_urlopen

    def test_fetch_question_set_keeps_valid_cached_question_set(self):
        old_data = submit.DATA
        old_urlopen = submit.urllib.request.urlopen
        try:
            with tempfile.TemporaryDirectory() as td:
                submit.DATA = Path(td)
                cached = submit.DATA / "q_2026-06-21.json"
                cached.write_text(json.dumps({
                    "forecast_due_date": "2026-06-21",
                    "question_set": "2026-06-21-llm.json",
                    "questions": [{"id": "cached"}],
                }))

                def fail_urlopen(req, timeout=60):
                    raise AssertionError("valid cache should not be refetched")

                submit.urllib.request.urlopen = fail_urlopen

                got = submit.fetch_question_set("2026-06-21")

                self.assertEqual(Path(got), cached)
        finally:
            submit.DATA = old_data
            submit.urllib.request.urlopen = old_urlopen

    def test_fetch_question_set_force_refresh_replaces_valid_cached_question_set(self):
        old_data = submit.DATA
        old_urlopen = submit.urllib.request.urlopen

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({
                    "forecast_due_date": "2026-06-21",
                    "question_set": "2026-06-21-llm.json",
                    "questions": [{"id": "new"}],
                }).encode()

        try:
            with tempfile.TemporaryDirectory() as td:
                submit.DATA = Path(td)
                cached = submit.DATA / "q_2026-06-21.json"
                cached.write_text(json.dumps({
                    "forecast_due_date": "2026-06-21",
                    "question_set": "2026-06-21-llm.json",
                    "questions": [{"id": "cached"}],
                }))
                submit.urllib.request.urlopen = lambda req, timeout=60: FakeResponse()

                got = submit.fetch_question_set("2026-06-21", force_refresh=True)

                payload = json.loads(Path(got).read_text())
                self.assertEqual(payload["questions"], [{"id": "new"}])
        finally:
            submit.DATA = old_data
            submit.urllib.request.urlopen = old_urlopen

    def test_cached_question_set_current_check_detects_live_revision(self):
        old_data = submit.DATA
        old_urlopen = submit.urllib.request.urlopen

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({
                    "forecast_due_date": "2026-06-21",
                    "question_set": "2026-06-21-llm.json",
                    "questions": [{"id": "new"}],
                }).encode()

        try:
            with tempfile.TemporaryDirectory() as td:
                submit.DATA = Path(td)
                cached = submit.DATA / "q_2026-06-21.json"
                cached.write_text(json.dumps({
                    "forecast_due_date": "2026-06-21",
                    "question_set": "2026-06-21-llm.json",
                    "questions": [{"id": "cached"}],
                }))
                submit.urllib.request.urlopen = lambda req, timeout=60: FakeResponse()

                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    rc = submit.cached_question_set_is_current("2026-06-21", cached)

                self.assertEqual(rc, 1)
        finally:
            submit.DATA = old_data
            submit.urllib.request.urlopen = old_urlopen

    def test_fetch_question_set_can_follow_matching_latest_pointer(self):
        old_data = submit.DATA
        old_urlopen = submit.urllib.request.urlopen

        class FakeResponse:
            def __init__(self, body):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return self.body

        payload = json.dumps({
            "forecast_due_date": "2026-06-21",
            "question_set": "2026-06-21-llm.json",
            "questions": [{"id": "q1"}],
        }).encode()
        try:
            with tempfile.TemporaryDirectory() as td:
                submit.DATA = Path(td)
                calls = []

                def fake_urlopen(req, timeout=60):
                    url = req.full_url
                    calls.append(url)
                    if url.endswith("/2026-06-21-llm.json") and calls.count(url) == 1:
                        raise submit.urllib.error.HTTPError(url, 404, "not found", None, None)
                    if url.endswith("/latest-llm.json"):
                        return FakeResponse(b"2026-06-21-llm.json")
                    return FakeResponse(payload)

                submit.urllib.request.urlopen = fake_urlopen

                got = submit.fetch_question_set("2026-06-21")

                self.assertEqual(Path(got), submit.DATA / "q_2026-06-21.json")
                self.assertEqual(json.loads(Path(got).read_text())["question_set"], "2026-06-21-llm.json")
                self.assertTrue(any(url.endswith("/latest-llm.json") for url in calls))
        finally:
            submit.DATA = old_data
            submit.urllib.request.urlopen = old_urlopen

    def test_fetch_question_set_rejects_stale_latest_pointer(self):
        old_data = submit.DATA
        old_urlopen = submit.urllib.request.urlopen

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"2026-06-07-llm.json"

        try:
            with tempfile.TemporaryDirectory() as td:
                submit.DATA = Path(td)

                def fake_urlopen(req, timeout=60):
                    url = req.full_url
                    if url.endswith("/2026-06-21-llm.json"):
                        raise submit.urllib.error.HTTPError(url, 404, "not found", None, None)
                    return FakeResponse()

                submit.urllib.request.urlopen = fake_urlopen

                with self.assertRaises(submit.urllib.error.HTTPError):
                    submit.fetch_question_set("2026-06-21")
        finally:
            submit.DATA = old_data
            submit.urllib.request.urlopen = old_urlopen

    def test_fetch_question_set_uses_contents_api_when_raw_lags(self):
        old_data = submit.DATA
        old_urlopen = submit.urllib.request.urlopen

        class FakeResponse:
            def __init__(self, body):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return self.body

        qset = json.dumps({
            "forecast_due_date": "2026-06-21",
            "question_set": "2026-06-21-llm.json",
            "questions": [{"id": "q1"}],
        }).encode()
        api_body = json.dumps({
            "encoding": "base64",
            "content": base64.b64encode(qset).decode(),
        }).encode()
        try:
            with tempfile.TemporaryDirectory() as td:
                submit.DATA = Path(td)
                calls = []

                def fake_urlopen(req, timeout=60):
                    url = req.full_url
                    calls.append(url)
                    if url.endswith("/2026-06-21-llm.json"):
                        raise submit.urllib.error.HTTPError(url, 404, "not found", None, None)
                    if url.endswith("/latest-llm.json"):
                        return FakeResponse(b"2026-06-07-llm.json")
                    if "api.github.com/repos/forecastingresearch/forecastbench-datasets" in url:
                        return FakeResponse(api_body)
                    raise AssertionError(f"unexpected URL {url}")

                submit.urllib.request.urlopen = fake_urlopen

                got = submit.fetch_question_set("2026-06-21")

                self.assertEqual(Path(got), submit.DATA / "q_2026-06-21.json")
                self.assertEqual(json.loads(Path(got).read_text())["question_set"], "2026-06-21-llm.json")
                self.assertTrue(any("api.github.com/repos/forecastingresearch" in url for url in calls))
        finally:
            submit.DATA = old_data
            submit.urllib.request.urlopen = old_urlopen

    def test_submit_main_returns_distinct_unpublished_exit(self):
        old_fetch = submit.fetch_question_set
        try:
            def fake_fetch(date, force_refresh=False):
                raise submit.urllib.error.HTTPError(
                    f"https://example.test/{date}.json",
                    404,
                    "not found",
                    None,
                    None,
                )

            submit.fetch_question_set = fake_fetch

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                rc = submit.main(["2026-06-21"])

            self.assertEqual(rc, submit.UNPUBLISHED_EXIT)
        finally:
            submit.fetch_question_set = old_fetch

    def test_submit_main_no_llm_skips_gap_fill(self):
        old_fill = llm_fill.fill_gaps
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                qset = root / "q.json"
                out = root / "2026-06-21.Vaticinus.1.json"
                qset.write_text(json.dumps({
                    "forecast_due_date": "2026-06-21",
                    "question_set": "fixture.json",
                    "questions": [{
                        "id": "gap1",
                        "source": "manifold",
                        "question": "Fixture gap?",
                    }],
                }))

                def fail_fill(*args, **kwargs):
                    raise AssertionError("gap-fill should not run with --no-llm")

                llm_fill.fill_gaps = fail_fill
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    rc = submit.main(["--no-llm", str(qset), str(out)])

                self.assertEqual(rc, 0)
                payload = json.loads(out.read_text())
                self.assertEqual(payload["forecasts"][0]["forecast"], 0.5)
                self.assertIsNone(payload["forecasts"][0]["reasoning"])
        finally:
            llm_fill.fill_gaps = old_fill

    def test_opus_worklist_and_merge_create_missing_output_directories(self):
        qset = {
            "forecast_due_date": "2026-06-21",
            "question_set": "fixture",
            "questions": [{
                "id": "m1",
                "source": "metaculus",
                "question": "Will the test event happen?",
                "resolution_criteria": "Fixture resolves yes/no.",
                "freeze_datetime_value": 0.40,
            }],
        }
        opus = [{"id": "m1", "probability": 0.70, "edge": "weak", "reasoning": "fixture"}]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            qset_path = root / "q.json"
            qset_path.write_text(json.dumps(qset))
            worklist = root / "missing" / "work" / "opus.jsonl"
            opus_path = root / "missing" / "opus" / "opus.json"
            out = root / "missing" / "merge" / "2026-06-21.Vaticinus.1.json"
            opus_path.parent.mkdir(parents=True)
            opus_path.write_text(json.dumps(opus))

            with redirect_stdout(StringIO()):
                opus_blend.emit_worklist(str(qset_path), str(worklist))
                opus_blend.merge(str(qset_path), str(opus_path), str(out))

            self.assertTrue(worklist.exists())
            self.assertTrue(out.exists())
            payload = json.loads(out.read_text())
            self.assertEqual(len(payload["forecasts"]), 1)
            self.assertGreater(payload["forecasts"][0]["forecast"], 0.40)

    def test_opus_edge_none_keeps_calibrated_crowd_anchor(self):
        qset = {
            "forecast_due_date": "2026-06-21",
            "question_set": "fixture",
            "questions": [{
                "id": "m1",
                "source": "infer",
                "question": "Will the test event happen?",
                "resolution_criteria": "Fixture resolves yes/no.",
                "freeze_datetime_value": 0.40,
            }],
        }
        opus = [{"id": "m1", "probability": 0.95, "edge": "none", "reasoning": "fixture"}]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            qset_path = root / "q.json"
            opus_path = root / "opus.json"
            out = root / "out.json"
            qset_path.write_text(json.dumps(qset))
            opus_path.write_text(json.dumps(opus))

            with redirect_stdout(StringIO()):
                opus_blend.merge(str(qset_path), str(opus_path), str(out))

            payload = json.loads(out.read_text())
            p = payload["forecasts"][0]["forecast"]
            self.assertAlmostEqual(p, opus_blend._crowd_value(qset["questions"][0]), places=6)
            self.assertLess(p, 0.40)

    def test_opus_merge_can_write_distinct_model_name(self):
        qset = {
            "forecast_due_date": "2026-06-21",
            "question_set": "fixture",
            "questions": [{
                "id": "m1",
                "source": "metaculus",
                "question": "Will the test event happen?",
                "resolution_criteria": "Fixture resolves yes/no.",
                "freeze_datetime_value": 0.40,
            }],
        }
        opus = [{"id": "m1", "probability": 0.60, "edge": "weak", "reasoning": "fixture"}]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            qset_path = root / "q.json"
            opus_path = root / "opus.json"
            out = root / "2026-06-21.Vaticinus.2.json"
            qset_path.write_text(json.dumps(qset))
            opus_path.write_text(json.dumps(opus))

            with redirect_stdout(StringIO()):
                opus_blend.merge(str(qset_path), str(opus_path), str(out), model="vati-2.0-opus")

            payload = json.loads(out.read_text())
            self.assertEqual(payload["model"], "vati-2.0-opus")

    def test_opus_prompt_uses_calibrated_prior_and_shows_raw_freeze(self):
        prompt = opus_forecaster._prompt({
            "question": "Will the test event happen?",
            "resolution_criteria": "Fixture resolves yes/no.",
            "background": "",
            "crowd_value": 0.23,
            "raw_crowd_value": 0.40,
            "due": "2026-06-21",
            "source": "infer",
        }, "")

        self.assertIn("Raw crowd freeze value: 0.4", prompt)
        self.assertIn("Calibrated crowd prior: 0.23", prompt)

    def test_llm_gap_fill_initializes_blank_runtime_db_before_forecast(self):
        old_db_path = db.DB_PATH
        old_forecast_one = llm_fill.forecast_one
        try:
            with tempfile.TemporaryDirectory() as td:
                db.DB_PATH = Path(td) / "data" / "foresight.db"

                def fake_forecast_one(conn, q, due, model=None):
                    conn.execute("SELECT count(*) FROM cost_ledger").fetchone()
                    return 0.61, "schema initialized"

                llm_fill.forecast_one = fake_forecast_one
                got = llm_fill.fill_gaps([{"id": "gap1", "question": "Fixture?"}], date(2026, 6, 21))

                self.assertEqual(got["gap1"], (0.61, "schema initialized"))
                self.assertTrue(db.DB_PATH.exists())
        finally:
            db.DB_PATH = old_db_path
            llm_fill.forecast_one = old_forecast_one

    def test_opus_stage1_initializes_blank_runtime_db_before_research(self):
        old_db_path = db.DB_PATH
        old_research = opus_forecaster._research
        old_forecast_once = opus_forecaster._forecast_once
        try:
            with tempfile.TemporaryDirectory() as td:
                db.DB_PATH = Path(td) / "data" / "foresight.db"

                def fake_research(conn, q, proxy):
                    conn.execute("SELECT count(*) FROM cost_ledger").fetchone()
                    return "schema initialized"

                def fake_forecast_once(conn, q, model, context):
                    self.assertEqual(context, "schema initialized")
                    return 0.62, "none", "fixture"

                opus_forecaster._research = fake_research
                opus_forecaster._forecast_once = fake_forecast_once

                row = opus_forecaster._stage1({
                    "id": "m1",
                    "source": "metaculus",
                    "due": "2026-06-21",
                    "question": "Fixture?",
                    "crowd_value": 0.5,
                    "raw_crowd_value": 0.5,
                }, proxy=None)

                self.assertEqual(row["p"], 0.62)
                self.assertTrue(db.DB_PATH.exists())
        finally:
            db.DB_PATH = old_db_path
            opus_forecaster._research = old_research
            opus_forecaster._forecast_once = old_forecast_once

    def test_submission_checker_accepts_valid_single_and_combo_rows(self):
        qset = {
            "forecast_due_date": "2026-06-21",
            "question_set": "fixture.json",
            "questions": [
                {"id": "m1", "source": "manifold", "resolution_dates": "N/A"},
                {"id": "d1", "source": "fred", "resolution_dates": ["2026-07-01", "2026-08-01"]},
                {"id": "d2", "source": "fred", "resolution_dates": ["2026-07-01", "2026-08-01"]},
                {
                    "id": ["d1", "d2"],
                    "source": "fred",
                    "resolution_dates": "N/A",
                    "combination_of": [
                        {"id": "d1", "source": "fred", "resolution_dates": ["2026-07-01", "2026-08-01"]},
                        {"id": "d2", "source": "fred", "resolution_dates": ["2026-07-01", "2026-08-01"]},
                    ],
                },
            ],
        }
        forecasts = [
            {"id": "m1", "source": "manifold", "forecast": 0.4, "resolution_date": None, "direction": None, "reasoning": None},
            {"id": "d1", "source": "fred", "forecast": 0.6, "resolution_date": "2026-07-01", "direction": None, "reasoning": None},
            {"id": "d1", "source": "fred", "forecast": 0.7, "resolution_date": "2026-08-01", "direction": None, "reasoning": None},
            {"id": "d2", "source": "fred", "forecast": 0.4, "resolution_date": "2026-07-01", "direction": None, "reasoning": None},
            {"id": "d2", "source": "fred", "forecast": 0.3, "resolution_date": "2026-08-01", "direction": None, "reasoning": None},
        ]
        for rd in ("2026-07-01", "2026-08-01"):
            for direction, p in [([1, 1], 0.24), ([1, -1], 0.16), ([-1, 1], 0.36), ([-1, -1], 0.24)]:
                forecasts.append({
                    "id": ["d1", "d2"],
                    "source": "fred",
                    "forecast": p,
                    "resolution_date": rd,
                    "direction": direction,
                    "reasoning": None,
                })
        submission = {
            "organization": "Vaticinus",
            "model": "vati-2.0",
            "model_organization": "Vaticinus",
            "question_set": "fixture.json",
            "forecasts": forecasts,
        }

        errors, warnings, summary = check_submission.validate(qset, submission)

        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(summary["rows"], 13)

    def test_submission_checker_rejects_duplicate_rows(self):
        qset = {
            "forecast_due_date": "2026-06-21",
            "question_set": "fixture.json",
            "questions": [{"id": "m1", "source": "manifold", "resolution_dates": "N/A"}],
        }
        row = {"id": "m1", "source": "manifold", "forecast": 0.4, "resolution_date": None, "direction": None, "reasoning": None}
        submission = {
            "organization": "Vaticinus",
            "model": "vati-2.0",
            "model_organization": "Vaticinus",
            "question_set": "fixture.json",
            "forecasts": [row, dict(row)],
        }

        errors, _, _ = check_submission.validate(qset, submission)

        self.assertTrue(any("duplicate forecast key" in e for e in errors))

    def test_submission_checker_rejects_low_single_coverage(self):
        qset = {
            "forecast_due_date": "2026-06-21",
            "question_set": "fixture.json",
            "questions": [
                {"id": "d1", "source": "fred", "resolution_dates": ["2026-07-01"]},
                {"id": "d2", "source": "fred", "resolution_dates": ["2026-07-01"]},
            ],
        }
        submission = {
            "organization": "Vaticinus",
            "model": "vati-2.0",
            "model_organization": "Vaticinus",
            "question_set": "fixture.json",
            "forecasts": [
                {"id": "d1", "source": "fred", "forecast": 0.4, "resolution_date": "2026-07-01", "direction": None, "reasoning": None},
            ],
        }

        errors, _, _ = check_submission.validate(qset, submission)

        self.assertTrue(any("dataset single coverage" in e for e in errors))

    def test_soft_market_variant_preserves_dataset_rows_and_changes_model(self):
        qset = {
            "forecast_due_date": "2026-06-21",
            "question_set": "fixture.json",
            "questions": [
                {
                    "id": "m1",
                    "source": "manifold",
                    "freeze_datetime_value": 0.40,
                    "resolution_dates": "N/A",
                },
                {
                    "id": "d1",
                    "source": "fred",
                    "resolution_dates": ["2026-07-01"],
                },
            ],
        }
        primary = {
            "organization": "Vaticinus",
            "model": "vati-2.0",
            "model_organization": "Vaticinus",
            "question_set": "fixture.json",
            "forecasts": [
                {"id": "m1", "source": "manifold", "forecast": 0.30, "resolution_date": None, "direction": None, "reasoning": None},
                {"id": "d1", "source": "fred", "forecast": 0.61, "resolution_date": "2026-07-01", "direction": None, "reasoning": None},
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            qset_path = root / "q.json"
            primary_path = root / "primary.json"
            out_path = root / "2026-06-21.Vaticinus.3.json"
            qset_path.write_text(json.dumps(qset))
            primary_path.write_text(json.dumps(primary))

            with redirect_stdout(StringIO()):
                diversify.make_soft_market_variant(str(qset_path), str(primary_path), str(out_path))

            payload = json.loads(out_path.read_text())
            self.assertEqual(payload["model"], diversify.DIVERSE_MODEL)
            market_row, dataset_row = payload["forecasts"]
            self.assertNotEqual(market_row["forecast"], primary["forecasts"][0]["forecast"])
            self.assertEqual(dataset_row["forecast"], primary["forecasts"][1]["forecast"])

            errors, warnings, summary = check_submission.validate(qset, payload)
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])
            self.assertEqual(summary["rows"], 2)

    def test_raw_market_variant_preserves_dataset_rows_and_uses_raw_crowd(self):
        qset = {
            "forecast_due_date": "2026-06-21",
            "question_set": "fixture.json",
            "questions": [
                {
                    "id": "m1",
                    "source": "manifold",
                    "freeze_datetime_value": 0.40,
                    "resolution_dates": "N/A",
                },
                {
                    "id": "d1",
                    "source": "fred",
                    "resolution_dates": ["2026-07-01"],
                },
            ],
        }
        primary = {
            "organization": "Vaticinus",
            "model": "vati-2.0",
            "model_organization": "Vaticinus",
            "question_set": "fixture.json",
            "forecasts": [
                {"id": "m1", "source": "manifold", "forecast": 0.30, "resolution_date": None, "direction": None, "reasoning": None},
                {"id": "d1", "source": "fred", "forecast": 0.61, "resolution_date": "2026-07-01", "direction": None, "reasoning": None},
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            qset_path = root / "q.json"
            primary_path = root / "primary.json"
            out_path = root / "2026-06-21.Vaticinus.2.json"
            qset_path.write_text(json.dumps(qset))
            primary_path.write_text(json.dumps(primary))

            with redirect_stdout(StringIO()):
                diversify.make_raw_market_variant(str(qset_path), str(primary_path), str(out_path))

            payload = json.loads(out_path.read_text())
            self.assertEqual(payload["model"], diversify.RAW_MARKET_MODEL)
            market_row, dataset_row = payload["forecasts"]
            self.assertEqual(market_row["forecast"], 0.40)
            self.assertEqual(dataset_row["forecast"], primary["forecasts"][1]["forecast"])

            errors, warnings, summary = check_submission.validate(qset, payload)
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])
            self.assertEqual(summary["rows"], 2)

    def test_upload_verifier_accepts_older_matching_proof_after_newer_bad_proof(self):
        due = "2026-06-21"
        repo = Path(__file__).resolve().parents[1]

        def artifact(path: Path) -> dict:
            data = path.read_bytes()
            return {
                "path": str(path),
                "copied_basename": path.name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "md5_base64": base64.b64encode(hashlib.md5(data).digest()).decode(),
                "bytes": len(data),
            }

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "engine").symlink_to(repo / "engine", target_is_directory=True)
            for name in ("pyproject.toml", "uv.lock"):
                (root / name).symlink_to(repo / name)

            data_dir = root / "data" / "forecastbench"
            proof_root = data_dir / "proofs"
            data_dir.mkdir(parents=True)
            proof_root.mkdir()

            qset = data_dir / f"q_{due}.json"
            submission = data_dir / f"{due}.Vaticinus.1.json"
            manifest = data_dir / f"{due}.manifest.jsonl"
            done = data_dir / f".uploaded_{due}"

            qset.write_text(json.dumps({
                "forecast_due_date": due,
                "question_set": "fixture.json",
                "questions": [{
                    "id": "m1",
                    "source": "manifold",
                    "resolution_dates": "N/A",
                }],
            }))
            submission.write_text(json.dumps({
                "organization": "Vaticinus",
                "model": "vati-2.0",
                "model_organization": "Vaticinus",
                "question_set": "fixture.json",
                "forecasts": [{
                    "id": "m1",
                    "source": "manifold",
                    "forecast": 0.42,
                    "resolution_date": None,
                    "direction": None,
                    "reasoning": None,
                }],
            }))
            done.write_text("uploaded\n")
            manifest.write_text(json.dumps({
                "file": str(submission),
                **artifact(submission),
                "uploaded": False,
                "verified": False,
            }) + "\n")

            good = proof_root / f"{due}_20260618T000000Z_good"
            bad = proof_root / f"{due}_20260618T010000Z_bad"
            good.mkdir()
            bad.mkdir()
            for path in (qset, submission, manifest, done):
                (good / path.name).write_bytes(path.read_bytes())
            (good / "proof.json").write_text(json.dumps({
                "due": due,
                "artifacts": {
                    "question_set": artifact(qset),
                    "manifest": artifact(manifest),
                    "done_marker": artifact(done),
                    "submissions": [artifact(submission)],
                },
            }))
            (bad / "proof.json").write_text(json.dumps({
                "due": due,
                "artifacts": {},
            }))
            os.utime(good, (1, 1))
            os.utime(bad, (2, 2))

            env = os.environ.copy()
            env.update({
                "FORECASTBENCH_WORKDIR": str(root),
                "FORECASTBENCH_DUE": due,
                "FORECASTBENCH_REQUIRE_REMOTE": "0",
                "FORECASTBENCH_REQUIRE_DONE": "1",
                "FORECASTBENCH_REQUIRE_PROOF": "1",
            })
            result = subprocess.run(
                ["/bin/zsh", str(repo / "data" / "metaculus" / "verify_forecastbench_upload.sh")],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(f"proof OK: data/forecastbench/proofs/{good.name}", result.stdout)

    def test_soft_market_variant_refuses_combo_question_sets(self):
        qset = {
            "forecast_due_date": "2026-06-21",
            "question_set": "fixture.json",
            "questions": [{
                "id": ["a", "b"],
                "source": "manifold",
                "combination_of": [{"id": "a"}, {"id": "b"}],
            }],
        }
        primary = {
            "organization": "Vaticinus",
            "model": "vati-2.0",
            "model_organization": "Vaticinus",
            "question_set": "fixture.json",
            "forecasts": [],
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            qset_path = root / "q.json"
            primary_path = root / "primary.json"
            qset_path.write_text(json.dumps(qset))
            primary_path.write_text(json.dumps(primary))

            with self.assertRaises(ValueError):
                diversify.make_soft_market_variant(str(qset_path), str(primary_path), str(root / "out.json"))


if __name__ == "__main__":
    unittest.main()
