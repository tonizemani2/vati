from __future__ import annotations

import sqlite3
import unittest
from datetime import date

from engine import db, quality


def memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_db(conn)
    conn.execute(
        "INSERT OR IGNORE INTO pillars (id,name,description,ord,status) VALUES (1,'Frontier','test',1,'in_progress')"
    )
    conn.execute(
        """
        INSERT INTO sources (id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,cost_cents)
        VALUES ('src','https://example.test','Fixture Source',1,'primary',90,'test source',
                '2026-06-17T00:00:00+00:00',0)
        """
    )
    conn.commit()
    return conn


def insert_series(
    conn: sqlite3.Connection,
    *,
    series_id: str,
    provider: str,
    metric: str,
    unit: str,
    external_id: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO series (id,pillar_id,source_id,provider,external_id,label,metric,unit,domain,created_at)
        VALUES (?,1,'src',?,?,?,?,?,'test','2026-06-17T00:00:00+00:00')
        """,
        (series_id, provider, external_id or f"{provider}:{series_id}", series_id, metric, unit),
    )


def insert_obs(conn: sqlite3.Connection, series_id: str, rows: list[tuple[str, float]], unit: str) -> None:
    for as_of, value in rows:
        conn.execute(
            """
            INSERT INTO observations (id,series_id,as_of,value,unit,uncertainty,created_at)
            VALUES (?,?,?,?,?,0,'2026-06-17T00:00:00+00:00')
            """,
            (f"{series_id}:{as_of}", series_id, as_of, value, unit),
        )
    conn.commit()


class QualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = memory_db()

    def tearDown(self) -> None:
        self.conn.close()

    def _health(self, series_id: str) -> sqlite3.Row:
        return self.conn.execute(
            "SELECT * FROM series_health WHERE series_id=?",
            (series_id,),
        ).fetchone()

    def test_irregular_event_series_uses_source_freshness_not_last_event_date(self) -> None:
        insert_series(
            self.conn,
            series_id="tsunami_flagged",
            provider="usgs_earthquakes",
            metric="earthquakes_tsunami_flagged",
            unit="earthquakes",
        )
        insert_obs(
            self.conn,
            "tsunami_flagged",
            [("2026-01-01", 1), ("2026-04-20", 1)],
            "earthquakes",
        )

        quality.run_audit(self.conn, today=date(2026, 6, 18), log=lambda *_args, **_kwargs: None)
        h = self._health("tsunami_flagged")

        self.assertEqual(h["status"], "ok")
        self.assertEqual(h["fresh_status"], "ok")
        self.assertEqual(h["complete_status"], "ok")
        self.assertIn("irregular event source", h["detail"])

    def test_dense_annual_series_still_fails_large_gaps(self) -> None:
        insert_series(
            self.conn,
            series_id="dense_with_gaps",
            provider="world_bank",
            metric="macro_indicator",
            unit="current US$",
        )
        insert_obs(
            self.conn,
            "dense_with_gaps",
            [("2020-12-31", 10), ("2024-12-31", 20)],
            "current US$",
        )

        quality.run_audit(self.conn, today=date(2026, 6, 18), log=lambda *_args, **_kwargs: None)
        h = self._health("dense_with_gaps")

        self.assertEqual(h["status"], "fail")
        self.assertEqual(h["complete_status"], "fail")

    def test_zero_omitted_research_series_do_not_fail_sparse_years(self) -> None:
        insert_series(
            self.conn,
            series_id="openalex_sparse",
            provider="openalex",
            metric="works_per_year",
            unit="works/year",
            external_id="C2988773926",
        )
        insert_obs(
            self.conn,
            "openalex_sparse",
            [("2005-12-31", 1), ("2012-12-31", 10), ("2024-12-31", 100)],
            "works/year",
        )

        quality.run_audit(self.conn, today=date(2026, 6, 18), log=lambda *_args, **_kwargs: None)
        h = self._health("openalex_sparse")

        self.assertEqual(h["complete_status"], "ok")
        self.assertIn("zero-omitted sparse series", h["detail"])

    def test_arxiv_topic_snapshot_uses_source_access_and_zero_omitted_gaps(self) -> None:
        insert_series(
            self.conn,
            series_id="arxiv_foundation_topic",
            provider="arxiv",
            metric="topic_share",
            unit="fraction",
            external_id="foundation model|topic_share",
        )
        insert_obs(
            self.conn,
            "arxiv_foundation_topic",
            [("2013-12-31", 0.001), ("2020-12-31", 0.01), ("2025-12-31", 0.1)],
            "fraction",
        )

        quality.run_audit(self.conn, today=date(2026, 6, 18), log=lambda *_args, **_kwargs: None)
        h = self._health("arxiv_foundation_topic")

        self.assertEqual(h["fresh_status"], "ok")
        self.assertEqual(h["complete_status"], "ok")
        self.assertIn("snapshot source checked", h["detail"])

    def test_arxiv_category_counts_allow_zero_omitted_lifecycle_years(self) -> None:
        insert_series(
            self.conn,
            series_id="arxiv_cond_mat",
            provider="arxiv",
            metric="works_per_year",
            unit="papers/year",
            external_id="cond-mat|works_per_year",
        )
        insert_obs(
            self.conn,
            "arxiv_cond_mat",
            [("1995-12-31", 1000), ("2004-12-31", 40), ("2025-12-31", 3)],
            "papers/year",
        )

        quality.run_audit(self.conn, today=date(2026, 6, 18), log=lambda *_args, **_kwargs: None)
        h = self._health("arxiv_cond_mat")

        self.assertEqual(h["fresh_status"], "ok")
        self.assertEqual(h["complete_status"], "ok")
        self.assertIn("zero-omitted sparse series", h["detail"])

    def test_world_bank_official_lag_warns_but_ancient_series_still_fails(self) -> None:
        insert_series(
            self.conn,
            series_id="world_bank_2021",
            provider="world_bank",
            metric="macro_indicator",
            unit="% of total electricity output",
        )
        insert_obs(
            self.conn,
            "world_bank_2021",
            [("2020-12-31", 10), ("2021-12-31", 11)],
            "% of total electricity output",
        )
        insert_series(
            self.conn,
            series_id="world_bank_1960",
            provider="world_bank",
            metric="macro_indicator",
            unit="current US$",
        )
        insert_obs(self.conn, "world_bank_1960", [("1960-12-31", 1)], "current US$")

        quality.run_audit(self.conn, today=date(2026, 6, 18), log=lambda *_args, **_kwargs: None)
        lagged = self._health("world_bank_2021")
        ancient = self._health("world_bank_1960")

        self.assertEqual(lagged["status"], "warn")
        self.assertEqual(lagged["fresh_status"], "warn")
        self.assertEqual(ancient["status"], "fail")
        self.assertEqual(ancient["fresh_status"], "fail")

    def test_sec_companyfacts_capex_allows_sparse_reported_tag_years(self) -> None:
        insert_series(
            self.conn,
            series_id="nvda_capex",
            provider="sec_edgar",
            metric="capex_usd",
            unit="USD/year",
            external_id="NVDA capex",
        )
        insert_obs(
            self.conn,
            "nvda_capex",
            [
                ("2010-12-31", 77_601_000),
                ("2011-12-31", 97_890_000),
                ("2012-12-31", 138_735_000),
                ("2022-12-31", 976_000_000),
                ("2023-12-31", 1_833_000_000),
                ("2024-12-31", 1_069_000_000),
                ("2025-12-31", 3_236_000_000),
            ],
            "USD/year",
        )

        quality.run_audit(self.conn, today=date(2026, 6, 18), log=lambda *_args, **_kwargs: None)
        h = self._health("nvda_capex")

        self.assertEqual(h["complete_status"], "ok")
        self.assertIn("sparse reported-fact series", h["detail"])

    def test_ilo_labour_indicators_allow_sparse_reported_survey_years(self) -> None:
        insert_series(
            self.conn,
            series_id="ilo_india_sparse",
            provider="ilo",
            metric="labour_indicator",
            unit="% of labour force",
            external_id="ilo:UNE_DEAP_SEX_AGE_RT_A:IND",
        )
        insert_obs(
            self.conn,
            "ilo_india_sparse",
            [
                ("2010-12-31", 3.1),
                ("2012-12-31", 3.2),
                ("2018-12-31", 7.6),
                ("2025-12-31", 4.5),
            ],
            "% of labour force",
        )

        quality.run_audit(self.conn, today=date(2026, 6, 18), log=lambda *_args, **_kwargs: None)
        h = self._health("ilo_india_sparse")

        self.assertEqual(h["fresh_status"], "ok")
        self.assertEqual(h["complete_status"], "ok")
        self.assertIn("absent years are not imputed", h["detail"])

    def test_archival_source_fresh_series_uses_source_access_not_last_point(self) -> None:
        insert_series(
            self.conn,
            series_id="transistors_per_chip",
            provider="owid",
            metric="transistors_per_chip",
            unit="transistors",
            external_id="transistors-per-microprocessor:transistors",
        )
        insert_obs(
            self.conn,
            "transistors_per_chip",
            [
                ("1990-12-31", 1_000_000),
                ("1995-12-31", 5_000_000),
                ("2000-12-31", 40_000_000),
                ("2010-12-31", 1_000_000_000),
                ("2021-12-31", 50_000_000_000),
            ],
            "transistors",
        )

        quality.run_audit(self.conn, today=date(2026, 6, 18), log=lambda *_args, **_kwargs: None)
        h = self._health("transistors_per_chip")

        self.assertEqual(h["fresh_status"], "ok")
        self.assertIn("archival source checked", h["detail"])

    def test_archival_source_fresh_series_fails_when_source_not_checked_recently(self) -> None:
        self.conn.execute("UPDATE sources SET accessed_at='2023-01-01T00:00:00+00:00' WHERE id='src'")
        insert_series(
            self.conn,
            series_id="old_transistors_per_chip",
            provider="owid",
            metric="transistors_per_chip",
            unit="transistors",
        )
        insert_obs(
            self.conn,
            "old_transistors_per_chip",
            [("2021-12-31", 50_000_000_000)],
            "transistors",
        )

        quality.run_audit(self.conn, today=date(2026, 6, 18), log=lambda *_args, **_kwargs: None)
        h = self._health("old_transistors_per_chip")

        self.assertEqual(h["fresh_status"], "fail")
        self.assertIn("archival source checked", h["detail"])


if __name__ == "__main__":
    unittest.main()
