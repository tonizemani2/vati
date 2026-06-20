from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from engine import db, rawstore, world_state
from engine.feeds import ingest
from engine.schemas import WorldStateFact


def memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_db(conn)
    conn.execute(
        "INSERT OR IGNORE INTO pillars (id,name,description,ord,status) VALUES (1,'Frontier','test',1,'in_progress')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO pillars (id,name,description,ord,status) VALUES (9,'Outcomes','test',9,'untapped')"
    )
    return conn


class WorldStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = memory_db()

    def tearDown(self) -> None:
        self.conn.close()

    def _fact(self, fact_id: str, **kwargs) -> str:
        fact = WorldStateFact(
            id=fact_id,
            predicate=kwargs.pop("predicate", "scales_capacity"),
            published_at=kwargs.pop("published_at", date(2023, 6, 1)),
            observed_at=kwargs.pop("observed_at", date(2023, 6, 1)),
            event_time=kwargs.pop("event_time", date(2023, 6, 1)),
            ingested_at=kwargs.pop("ingested_at", datetime(2023, 6, 2, tzinfo=timezone.utc)),
            extractor="fixture",
            rationale=kwargs.pop("rationale", "solid state battery capacity expansion"),
            confidence=kwargs.pop("confidence", 0.9),
            **kwargs,
        )
        return world_state.insert_fact(self.conn, fact)

    def test_visible_facts_exclude_future_dates_and_ingestion(self) -> None:
        self._fact("visible")
        self._fact("future_published", published_at=date(2024, 1, 1))
        self._fact("future_observed", observed_at=date(2024, 1, 1))
        self._fact("future_event", event_time=date(2024, 1, 1))
        self._fact("future_ingested", ingested_at=datetime(2024, 1, 1, tzinfo=timezone.utc))

        facts, exclusions = world_state.visible_facts(
            self.conn,
            "solid state battery",
            date(2023, 12, 31),
            snapshot_created_at=datetime(2023, 12, 31, tzinfo=timezone.utc),
        )

        self.assertEqual([f["id"] for f in facts], ["visible"])
        self.assertGreaterEqual(exclusions["future_published"], 1)
        self.assertGreaterEqual(exclusions["future_observed"], 1)
        self.assertGreaterEqual(exclusions["future_event"], 1)
        self.assertGreaterEqual(exclusions["future_ingested"], 1)

    def test_snapshot_hash_is_stable_for_same_manifest(self) -> None:
        self._fact("a")
        self._fact("b", predicate="raises_output", value=42, unit="GWh")
        facts, _ = world_state.visible_facts(
            self.conn,
            "solid state battery",
            date(2023, 12, 31),
            snapshot_created_at=datetime(2023, 12, 31, tzinfo=timezone.utc),
        )

        h1 = world_state.snapshot_hash("solid state battery", date(2023, 12, 31), facts)
        h2 = world_state.snapshot_hash("solid state battery", date(2023, 12, 31), list(reversed(facts)))

        self.assertEqual(h1, h2)

    def test_superseded_facts_are_hidden_by_default(self) -> None:
        self._fact("old", predicate="capacity_target", value=10, unit="GWh")
        self._fact("new", predicate="capacity_target", value=12, unit="GWh", supersedes_fact_id="old")

        facts, exclusions = world_state.visible_facts(
            self.conn,
            "solid state battery",
            date(2023, 12, 31),
            snapshot_created_at=datetime(2023, 12, 31, tzinfo=timezone.utc),
        )

        self.assertEqual([f["id"] for f in facts], ["new"])
        self.assertEqual(exclusions["superseded"], 1)

    def test_state_proof_is_read_only_and_shows_gate_passes(self) -> None:
        self._fact("visible")
        self._fact("future_published", published_at=date(2024, 1, 1))

        before = self.conn.execute("SELECT count(*) FROM world_state_snapshots").fetchone()[0]
        proof = world_state.state_proof(
            "solid state battery",
            date(2023, 12, 31),
            conn=self.conn,
            limit=8,
        )
        after = self.conn.execute("SELECT count(*) FROM world_state_snapshots").fetchone()[0]

        self.assertEqual(before, 0)
        self.assertEqual(after, 0)
        self.assertEqual([f["id"] for f in proof["facts"]], ["visible"])
        self.assertTrue(proof["all_visible_as_of_proven"])
        self.assertTrue(all(gate["passes"] for gate in proof["facts"][0]["gates"].values()))
        self.assertGreaterEqual(proof["exclusions"]["future_published"], 1)
        self.assertIn("published/observed/event <= as_of", world_state.format_proof(proof))

    def test_state_proof_skips_unused_context_scans(self) -> None:
        self._fact("visible")

        with (
            patch.object(world_state, "_match_entities", side_effect=AssertionError("unused")),
            patch.object(world_state, "_series_summaries", side_effect=AssertionError("unused")),
            patch.object(world_state, "_entity_edges", side_effect=AssertionError("unused")),
        ):
            proof = world_state.state_proof(
                "solid state battery",
                date(2023, 12, 31),
                conn=self.conn,
                limit=4,
            )

        self.assertEqual([f["id"] for f in proof["facts"]], ["visible"])
        self.assertTrue(proof["all_visible_as_of_proven"])

    def test_research_pack_filters_papers_and_facts_as_of_cutoff(self) -> None:
        self.conn.execute(
            """
            INSERT INTO sources (id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at)
            VALUES ('research_src','https://example.test/research','Research fixture',1,'primary',90,'fixture','2023-01-02')
            """
        )
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,source_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('research_series',1,'research_src','arxiv','solid-state',
                    'solid state battery papers','publication_count','papers/year','research','2023-01-02')
            """
        )
        self._fact(
            "research_visible",
            predicate="observed publication_count",
            value=10,
            unit="papers/year",
            source_id="research_src",
            rationale="solid state battery research publications",
        )
        self._fact(
            "research_future",
            predicate="observed publication_count",
            value=12,
            unit="papers/year",
            source_id="research_src",
            published_at=date(2024, 1, 1),
            rationale="solid state battery research publications",
        )
        self.conn.execute(
            """
            INSERT INTO papers (
                id,provider,external_id,published,updated,primary_category,categories,title,
                abstract,authors,n_authors,content_hash,fetched_at
            ) VALUES
                ('paper_visible','arxiv','2301.00001','2023-01-01',NULL,'cs.AI','cs.AI',
                 'Solid state battery electrolyte search','solid state battery abstract','A',1,'h1','2023-01-02'),
                ('paper_future','arxiv','2401.00001','2024-01-01',NULL,'cs.AI','cs.AI',
                 'Solid state battery future result','solid state battery abstract','B',1,'h2','2024-01-02'),
                ('paper_unrelated','arxiv','2301.00002','2023-01-01',NULL,'cs.LG','cs.LG',
                 'Unrelated theorem','nothing to see','C',1,'h3','2023-01-02')
            """
        )

        before = self.conn.execute("SELECT count(*) FROM world_state_snapshots").fetchone()[0]
        pack = world_state.research_pack(
            "solid state battery",
            date(2023, 12, 31),
            conn=self.conn,
            paper_limit=8,
            fact_limit=8,
            count_fact_exclusions=True,
            count_paper_exclusions=True,
        )
        after = self.conn.execute("SELECT count(*) FROM world_state_snapshots").fetchone()[0]
        pack_again = world_state.research_pack(
            "solid state battery",
            date(2023, 12, 31),
            conn=self.conn,
            paper_limit=8,
            fact_limit=8,
            count_fact_exclusions=True,
            count_paper_exclusions=True,
        )

        self.assertEqual(before, after)
        self.assertEqual([f["id"] for f in pack["facts"]], ["research_visible"])
        self.assertEqual([p["id"] for p in pack["papers"]], ["paper_visible"])
        self.assertGreaterEqual(pack["exclusions"]["future_published"], 1)
        self.assertGreaterEqual(pack["exclusions"]["future_published_papers"], 1)
        self.assertEqual(pack["snapshot"]["snapshot_hash"], pack_again["snapshot"]["snapshot_hash"])
        self.assertTrue(pack["papers"][0]["phrase_match"])
        rendered = world_state.format_research_pack(pack)
        self.assertIn("Research pack: solid state battery as of 2023-12-31", rendered)
        self.assertEqual(pack["papers"][0]["id"], "paper_visible")

    def test_research_pack_full_scan_can_recover_hits_outside_bounded_window(self) -> None:
        self.conn.execute(
            """
            INSERT INTO papers (
                id,provider,external_id,published,updated,primary_category,categories,title,
                abstract,authors,n_authors,content_hash,fetched_at
            ) VALUES
                ('paper_recent_unrelated','arxiv','2301.00003','2023-12-31',NULL,'cs.LG','cs.LG',
                 'Unrelated recent work','nothing to see','C',1,'h3','2024-01-01'),
                ('paper_old_match','arxiv','2001.00001','2020-01-01',NULL,'cs.AI','cs.AI',
                 'Rare catalytic bottleneck architecture','rare catalytic bottleneck abstract','A',1,'h1','2020-01-02')
            """
        )

        bounded = world_state.research_pack(
            "rare catalytic bottleneck",
            date(2023, 12, 31),
            conn=self.conn,
            paper_limit=1,
            fact_limit=0,
            paper_scan_rows=1,
        )
        full = world_state.research_pack(
            "rare catalytic bottleneck",
            date(2023, 12, 31),
            conn=self.conn,
            paper_limit=1,
            fact_limit=0,
            full_paper_scan=True,
        )

        self.assertEqual(bounded["papers"], [])
        self.assertEqual([p["id"] for p in full["papers"]], ["paper_old_match"])
        self.assertFalse(bounded["snapshot"]["paper_full_scan"])
        self.assertTrue(full["snapshot"]["paper_full_scan"])

    def test_cost_guard_rejects_over_limit_scan(self) -> None:
        with self.assertRaises(world_state.CostGuardError):
            world_state.guard_scan_bytes("bigquery", 101 * world_state.GIB, max_gb=100)

        allowed = world_state.guard_scan_bytes(
            "bigquery", 101 * world_state.GIB, max_gb=100, allow_large=True
        )
        self.assertTrue(allowed["allowed"])
        self.assertGreaterEqual(allowed["estimated_cost_cents"], 0)

    def test_feed_ingest_preserves_raw_bytes_and_source_hash(self) -> None:
        old_dir = ingest.FEEDS_DIR
        old_root = rawstore.RAW_ROOT
        old_meta = ingest.FEED_META.get("fixture")
        temp_parent = db.REPO_ROOT / "data"
        temp_parent.mkdir(exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(dir=temp_parent) as tmp:
                root = Path(tmp)
                feeds_dir = root / "feeds"
                feeds_dir.mkdir()
                (feeds_dir / "fixture.jsonl").write_text(
                    json.dumps(
                        {
                            "series_id": "solid_state_battery_capacity",
                            "date": "2023-12-31",
                            "value": 1.0,
                            "unit": "GWh",
                            "title": "solid state battery capacity",
                        }
                    )
                    + "\n"
                )
                ingest.FEEDS_DIR = feeds_dir
                ingest.FEED_META["fixture"] = {
                    "pillar": 1,
                    "metric": "capacity",
                    "domain": "battery",
                    "title": "Fixture Feed",
                    "url": "https://example.test/fixture",
                    "trust": 90,
                    "leak": "leading",
                    "why": "fixture source with exact raw bytes",
                }
                rawstore.RAW_ROOT = root / "raw"

                out = ingest.ingest_feed(self.conn, "fixture")

                src = self.conn.execute(
                    "SELECT id, content_hash FROM sources WHERE url='https://example.test/fixture'"
                ).fetchone()
                raw = self.conn.execute(
                    "SELECT source_id, byte_len FROM raw_docs WHERE content_hash=?",
                    (src["content_hash"],),
                ).fetchone()

                self.assertEqual(out["status"], "ok")
                self.assertIsNotNone(src["content_hash"])
                self.assertEqual(raw["source_id"], src["id"])
                self.assertGreater(raw["byte_len"], 0)
        finally:
            ingest.FEEDS_DIR = old_dir
            rawstore.RAW_ROOT = old_root
            if old_meta is None:
                ingest.FEED_META.pop("fixture", None)
            else:
                ingest.FEED_META["fixture"] = old_meta

    def test_backfill_observation_facts_are_visible_point_in_time(self) -> None:
        self.conn.execute(
            """
            INSERT INTO sources (id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,cost_cents)
            VALUES ('src','https://example.test','Fixture Source',1,'primary',90,'test source',
                    '2023-01-02T00:00:00+00:00',0)
            """
        )
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,source_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('series1',1,'src','fixture','solid-state','solid state battery capacity',
                    'capacity','GWh','battery','2023-01-02T00:00:00+00:00')
            """
        )
        self.conn.execute(
            """
            INSERT INTO observations (id,series_id,as_of,value,unit,uncertainty,created_at)
            VALUES ('obs1','series1','2023-12-31',42,'GWh',0,'2024-01-01T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.backfill_observation_facts(self.conn)
        facts, exclusions = world_state.visible_facts(
            self.conn,
            "solid state battery",
            date(2023, 12, 31),
            snapshot_created_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
        future, _ = world_state.visible_facts(
            self.conn,
            "solid state battery",
            date(2023, 12, 30),
            snapshot_created_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )

        self.assertEqual(out["inserted"], 1)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["value"], 42)
        self.assertEqual(future, [])
        self.assertGreaterEqual(exclusions["future_published"], 0)

    def test_backfill_observation_metadata_blocks_lagged_release_leakage(self) -> None:
        self.conn.execute(
            """
            INSERT INTO sources (id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,cost_cents)
            VALUES ('baci_src','https://example.test/baci','BACI',1,'primary',90,'test source',
                    '2026-01-22T00:00:00+00:00',0)
            """
        )
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,source_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('baci_series',1,'baci_src','baci','baci:hs22:850760:2024:global_import_value',
                    'BACI 2024 global import value — lithium-ion accumulators',
                    'baci_global_import_value','USD','trade','2026-01-22T00:00:00+00:00')
            """
        )
        self.conn.execute(
            """
            INSERT INTO observations
                (id,series_id,as_of,event_time,published_at,observed_at,value,unit,uncertainty,created_at)
            VALUES
                ('baci_obs','baci_series','2026-01-22','2024-12-31','2026-01-22','2024-12-31',
                 123,'USD',0,'2026-01-22T00:00:00+00:00')
            """
        )
        self.conn.commit()

        world_state.backfill_observation_facts(self.conn, provider="baci")
        before_release, before_exclusions = world_state.visible_facts(
            self.conn,
            "lithium-ion accumulators",
            date(2025, 12, 31),
            snapshot_created_at=datetime(2026, 1, 23, tzinfo=timezone.utc),
        )
        after_release, _ = world_state.visible_facts(
            self.conn,
            "lithium-ion accumulators",
            date(2026, 1, 22),
            snapshot_created_at=datetime(2026, 1, 23, tzinfo=timezone.utc),
        )

        self.assertEqual(before_release, [])
        self.assertGreaterEqual(before_exclusions["future_published"], 1)
        self.assertEqual(len(after_release), 1)
        self.assertEqual(after_release[0]["event_time"], "2024-12-31")
        self.assertEqual(after_release[0]["published_at"], "2026-01-22")

    def test_backfill_observation_facts_can_filter_by_provider(self) -> None:
        self.conn.execute(
            """
            INSERT INTO sources (id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,cost_cents)
            VALUES ('src_nsf','https://example.test/nsf','NSF',1,'primary',90,'test',
                    '2023-01-02T00:00:00+00:00',0),
                   ('src_other','https://example.test/other','Other',1,'primary',90,'test',
                    '2023-01-02T00:00:00+00:00',0)
            """
        )
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,source_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('nsf_series',1,'src_nsf','nsf_awards','nsf_awards:ai:awards',
                    'NSF AI awards','nsf_awards_per_year','awards/year','science_funding',
                    '2023-01-02T00:00:00+00:00'),
                   ('other_series',1,'src_other','other_provider','other:ai',
                    'Other AI awards','other_metric','count','science_funding',
                    '2023-01-02T00:00:00+00:00')
            """
        )
        self.conn.execute(
            """
            INSERT INTO observations (id,series_id,as_of,value,unit,uncertainty,created_at)
            VALUES ('obs_nsf','nsf_series','2023-12-31',12,'awards/year',0,'2024-01-01T00:00:00+00:00'),
                   ('obs_other','other_series','2023-12-31',99,'count',0,'2024-01-01T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.backfill_observation_facts(self.conn, provider="nsf_awards")
        rows = self.conn.execute(
            "SELECT predicate, value, source_id FROM world_state_facts ORDER BY source_id"
        ).fetchall()

        self.assertEqual(out["seen"], 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["value"], 12)
        self.assertEqual(rows[0]["source_id"], "src_nsf")
        self.assertIn("nsf_awards_per_year", rows[0]["predicate"])

    def test_backfill_metric_entity_facts_bridges_interconnection_queue_to_grid_entity(self) -> None:
        self.conn.execute(
            """
            INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
            VALUES
                ('grid_interconnection','technology','Grid interconnection','grid','["interconnection queue"]',
                 'fixture','2024-01-01T00:00:00+00:00'),
                ('us','country_region','United States','geography','["US"]','fixture','2024-01-01T00:00:00+00:00')
            """
        )
        self.conn.execute(
            """
            INSERT INTO sources
                (id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,cost_cents,content_hash)
            VALUES
                ('lbnl_src','https://emp.lbl.gov/queued-up','LBNL Queued Up',
                 1,'primary',90,'fixture','2024-04-30T00:00:00+00:00',0,'hash_lbnl')
            """
        )
        self.conn.execute(
            """
            INSERT INTO raw_docs (content_hash,source_id,url,media_type,byte_len,path,fetched_at)
            VALUES ('hash_lbnl','lbnl_src','https://emp.lbl.gov/queued-up',
                    'text/html',4,'data/raw/lbnl.html','2024-04-30T00:00:00+00:00')
            """
        )
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,source_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('lbnl_queue',1,'lbnl_src','lbnl','queued_up_active_capacity',
                    'US interconnection-queue active capacity',
                    'interconnection_queue_capacity','GW (active)','energy/grid',
                    '2024-04-30T00:00:00+00:00')
            """
        )
        self.conn.execute(
            """
            INSERT INTO entity_links
                (id,entity_id,ref_table,ref_id,ref_label,pillar_id,confidence,method,rationale,created_at)
            VALUES
                ('us_lbnl_queue','us','series','lbnl_queue','US interconnection queue',
                 1,0.95,'fixture','fixture','2024-04-30T00:00:00+00:00')
            """
        )
        self.conn.execute(
            """
            INSERT INTO observations
                (id,series_id,as_of,event_time,published_at,observed_at,value,unit,uncertainty,created_at)
            VALUES
                ('lbnl_obs','lbnl_queue','2023-12-31','2023-12-31','2024-04-30','2023-12-31',
                 2600,'GW (active)',0,'2024-04-30T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.backfill_metric_entity_facts(self.conn)
        fact = self.conn.execute(
            """
            SELECT subject_entity_id, object_entity_id, predicate, value, unit, source_id, content_hash, rationale
            FROM world_state_facts
            WHERE extractor='series_metric_entity_bridge_v1'
            """
        ).fetchone()

        self.assertEqual(out["seen"], 1)
        self.assertEqual(out["after"], 1)
        self.assertEqual(fact["subject_entity_id"], "grid_interconnection")
        self.assertEqual(fact["object_entity_id"], "us")
        self.assertEqual(fact["predicate"], "observed interconnection_queue_capacity")
        self.assertEqual(fact["value"], 2600)
        self.assertEqual(fact["source_id"], "lbnl_src")
        self.assertEqual(fact["content_hash"], "hash_lbnl")
        self.assertIn("Grid interconnection", fact["rationale"])

    def test_backfill_entity_identifier_facts_uses_official_links_only(self) -> None:
        self.conn.execute(
            """
            INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
            VALUES ('nvda','company','NVIDIA','semiconductors','["NVDA"]','test','2024-01-01')
            """
        )
        self.conn.execute(
            """
            INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
            VALUES ('internal','technology','Internal','test','[]','test','2024-01-01')
            """
        )
        self.conn.execute(
            """
            INSERT INTO sources
                (id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,cost_cents,content_hash)
            VALUES
                ('sec_src','https://www.sec.gov/files/company_tickers.json','SEC company tickers',
                 1,'primary',95,'official SEC index','2024-01-01T00:00:00+00:00',0,'hash_sec')
            """
        )
        self.conn.execute(
            """
            INSERT INTO raw_docs (content_hash,source_id,url,media_type,byte_len,path,fetched_at)
            VALUES ('hash_sec','sec_src','https://www.sec.gov/files/company_tickers.json',
                    'application/json',2,'data/raw/sec.json','2024-01-01T00:00:00+00:00')
            """
        )
        self.conn.execute(
            """
            INSERT INTO entity_links
                (id,entity_id,ref_table,ref_id,ref_label,pillar_id,confidence,method,rationale,created_at)
            VALUES
                ('ticker_link','nvda','ticker','NVDA','NVIDIA CORP',6,1.0,'sec_ticker_alias',
                 'Exact ticker alias from SEC company_tickers.json.','2024-01-01T00:00:00+00:00'),
                ('internal_link','internal','series','series1','internal series',1,1.0,'auto_exact',
                 'Internal series link.','2024-01-01T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.backfill_entity_identifier_facts(self.conn)
        facts = self.conn.execute(
            """
            SELECT f.subject_entity_id, f.object_entity_id, f.predicate, f.unit, f.source_id,
                   f.content_hash, obj.kind, obj.canonical_name
            FROM world_state_facts f
            JOIN entities obj ON obj.id=f.object_entity_id
            WHERE f.extractor='entity_identifier_v1'
            """
        ).fetchall()

        self.assertEqual(out["seen"], 1)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["subject_entity_id"], "nvda")
        self.assertEqual(facts[0]["predicate"], "has ticker")
        self.assertEqual(facts[0]["unit"], "ticker")
        self.assertEqual(facts[0]["source_id"], "sec_src")
        self.assertEqual(facts[0]["content_hash"], "hash_sec")
        self.assertEqual(facts[0]["kind"], "identifier")
        self.assertEqual(facts[0]["canonical_name"], "Ticker: NVDA")

    def test_backfill_entity_identifier_facts_uses_exact_wikidata_source_url(self) -> None:
        self.conn.execute(
            """
            INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
            VALUES ('openai','company','OpenAI','AI','[]','test','2024-01-01')
            """
        )
        self.conn.execute(
            "INSERT OR IGNORE INTO pillars (id,name,description,ord,status) VALUES (6,'Capital','test',6,'in_progress')"
        )
        self.conn.execute(
            """
            INSERT INTO sources
                (id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,cost_cents,content_hash)
            VALUES
                ('wd_src','https://www.wikidata.org/wiki/Special:EntityData/Q21708200.json',
                 'Wikidata entity data for Q21708200',
                 6,'analyst',78,'exact QID fixture','2024-01-01T00:00:00+00:00',0,'hash_wd')
            """
        )
        self.conn.execute(
            """
            INSERT INTO raw_docs (content_hash,source_id,url,media_type,byte_len,path,fetched_at)
            VALUES ('hash_wd','wd_src','https://www.wikidata.org/wiki/Special:EntityData/Q21708200.json',
                    'application/json',2,'data/raw/wd.json','2024-01-01T00:00:00+00:00')
            """
        )
        self.conn.execute(
            """
            INSERT INTO entity_links
                (id,entity_id,ref_table,ref_id,ref_label,pillar_id,confidence,method,rationale,created_at)
            VALUES
                ('wd_link','openai','wikidata_qid','Q21708200','OpenAI',6,0.84,'wikidata_exact_label',
                 'Exact Wikidata label fixture.','2024-01-01T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.backfill_entity_identifier_facts(self.conn)
        fact = self.conn.execute(
            """
            SELECT predicate, unit, source_id, content_hash
            FROM world_state_facts
            WHERE extractor='entity_identifier_v1'
            """
        ).fetchone()

        self.assertEqual(out["seen"], 1)
        self.assertEqual(fact["predicate"], "has Wikidata QID")
        self.assertEqual(fact["unit"], "wikidata_qid")
        self.assertEqual(fact["source_id"], "wd_src")
        self.assertEqual(fact["content_hash"], "hash_wd")

    def test_state_pack_includes_offloaded_raw_doc_location(self) -> None:
        old_repo_root = world_state.db.REPO_ROOT
        old_raw_root = rawstore.RAW_ROOT
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                raw_root = root / "data" / "raw"
                raw_root.mkdir(parents=True)
                world_state.db.REPO_ROOT = root
                rawstore.RAW_ROOT = raw_root
                h = "a" * 64
                manifest = root / "data" / "_offload_manifest.jsonl"
                manifest.write_text(
                    json.dumps(
                        {
                            "ts": "2026-06-18T08:39:57+00:00",
                            "local_path": str(raw_root),
                            "remote_uri": "s3://example-bucket/world/raw",
                            "size_bytes": 128,
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
                self.conn.execute(
                    """
                    INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at)
                    VALUES ('battery','technology','solid state battery','energy','[]','test','2024-01-01')
                    """
                )
                self.conn.execute(
                    """
                    INSERT INTO sources
                        (id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,cost_cents,content_hash)
                    VALUES
                        ('src','https://example.test/battery','Battery source',1,'primary',91,'fixture',
                         '2024-01-01T00:00:00+00:00',0,?)
                    """,
                    (h,),
                )
                self.conn.execute(
                    """
                    INSERT INTO raw_docs (content_hash,source_id,url,media_type,byte_len,path,fetched_at)
                    VALUES (?,'src','https://example.test/battery','application/json',128,?,
                            '2024-01-01T00:00:00+00:00')
                    """,
                    (h, f"data/raw/{h[:2]}/{h}.json"),
                )
                self._fact(
                    "battery_fact",
                    subject_entity_id="battery",
                    predicate="observed deployment",
                    value=42,
                    unit="MWh",
                    source_id="src",
                    content_hash=h,
                    rationale="solid state battery deployment fixture",
                )
                self.conn.commit()

                pack = world_state.state_pack(
                    "solid state battery",
                    date(2024, 12, 31),
                    conn=self.conn,
                    record=False,
                )

                self.assertEqual(pack["facts"][0]["raw_doc_status"], "offloaded")
                self.assertEqual(pack["facts"][0]["raw_doc_byte_len"], 128)
                self.assertEqual(
                    pack["facts"][0]["raw_doc_remote_uri"],
                    f"s3://example-bucket/world/raw/{h[:2]}/{h}.json",
                )
                self.assertEqual(pack["sources"][0]["raw_doc_status"], "offloaded")
                self.assertEqual(pack["sources"][0]["content_hash"], h)

                proof = world_state.state_proof(
                    "solid state battery",
                    date(2024, 12, 31),
                    conn=self.conn,
                    limit=8,
                )
                self.assertEqual(proof["facts"][0]["raw_doc_status"], "offloaded")
                self.assertEqual(
                    proof["facts"][0]["raw_doc_remote_uri"],
                    f"s3://example-bucket/world/raw/{h[:2]}/{h}.json",
                )
                self.assertTrue(proof["facts"][0]["visible_as_of_proven"])
        finally:
            world_state.db.REPO_ROOT = old_repo_root
            rawstore.RAW_ROOT = old_raw_root

    def test_state_pack_reuses_raw_doc_location_cache(self) -> None:
        h = "b" * 64
        self.conn.execute(
            """
            INSERT INTO sources
                (id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,cost_cents,content_hash)
            VALUES
                ('shared_src','https://example.test/shared','Shared solid state battery source',
                 1,'primary',90,'fixture','2024-01-01T00:00:00+00:00',0,?)
            """,
            (h,),
        )
        self.conn.execute(
            """
            INSERT INTO raw_docs (content_hash,source_id,url,media_type,byte_len,path,fetched_at)
            VALUES (?,'shared_src','https://example.test/shared','application/json',10,?,
                    '2024-01-01T00:00:00+00:00')
            """,
            (h, f"data/raw/{h[:2]}/{h}.json"),
        )
        for fact_id, value in (("fact_a", 1), ("fact_b", 2)):
            self._fact(
                fact_id,
                predicate="observed deployment",
                value=value,
                unit="MWh",
                source_id="shared_src",
                content_hash=h,
                rationale="solid state battery deployment fixture",
            )
        self.conn.commit()

        with patch.object(
            world_state.rawstore,
            "locate",
            return_value={
                "status": "offloaded",
                "exists_local": False,
                "local_path": "/tmp/raw/doc.json",
                "remote_uri": "s3://example/raw/doc.json",
                "byte_len": 10,
            },
        ) as locate:
            pack = world_state.state_pack(
                "solid state battery",
                date(2024, 12, 31),
                conn=self.conn,
                limit=8,
                record=False,
            )

        self.assertEqual(len(pack["facts"]), 2)
        self.assertEqual(len(pack["sources"]), 1)
        self.assertEqual(pack["facts"][0]["raw_doc_status"], "offloaded")
        self.assertEqual(pack["sources"][0]["raw_doc_remote_uri"], "s3://example/raw/doc.json")
        locate.assert_called_once_with(self.conn, h)

    def test_autolink_series_entities_matches_country_iso(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('gdp_china',9,'world_bank','world_bank:NY.GDP.MKTP.CD:CHN',
                    'GDP (current US$) — CHN','macro_indicator','USD','macro',
                    '2023-01-02T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.canonical_name, el.confidence, el.method
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='gdp_china'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["canonical_name"], "China")
        self.assertEqual(link["method"], "auto_exact")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_series_entities_matches_country_iso2(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('gdp_france',9,'eurostat','eurostat:nama_10_gdp:FR',
                    'GDP (current prices) — FR','macro_indicator','EUR','macro',
                    '2023-01-02T00:00:00+00:00')
            """
        )
        self.conn.commit()

        world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.canonical_name, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='gdp_france'
            """
        ).fetchone()

        self.assertEqual(link["canonical_name"], "France")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_series_entities_creates_arxiv_field_subject(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('cs_ai',1,'arxiv','cs.AI|works_per_year',
                    'cs.AI (arXiv category works/yr)','works_per_year','works/year','arxiv_category',
                    '2023-01-02T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='cs_ai'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["kind"], "research_field")
        self.assertEqual(link["canonical_name"], "arXiv cs.AI")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_prefers_ofac_program_subject_over_country_surface_match(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('ofac_russia_program',9,'ofac_sdn','ofac_sdn:program:russia_eo14024',
                    'OFAC SDN — program RUSSIA-EO14024',
                    'sanctions_entries_by_program','entries','sanctions',
                    '2026-06-11T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        links = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='ofac_russia_program'
            """
        ).fetchall()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["kind"], "policy")
        self.assertEqual(links[0]["canonical_name"], "OFAC RUSSIA-EO14024 sanctions program")
        self.assertGreaterEqual(links[0]["confidence"], 0.9)

    def test_autolink_prefers_eu_programme_subject_over_country_surface_match(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('eu_rus_programme',9,'eu_sanctions','eu_sanctions:programme:rus',
                    'EU sanctions — programme RUS',
                    'sanctions_entries_by_programme','entries','sanctions',
                    '2026-06-05T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        links = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='eu_rus_programme'
            """
        ).fetchall()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["kind"], "policy")
        self.assertEqual(links[0]["canonical_name"], "EU RUS sanctions programme")
        self.assertGreaterEqual(links[0]["confidence"], 0.9)

    def test_autolink_clinicaltrials_topic_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('ct_glp1',9,'clinicaltrials','clinicaltrials:glp1_obesity_drugs:posted_studies',
                    'ClinicalTrials.gov — GLP-1 obesity drugs first posted studies',
                    'trial_registry_posts','studies','clinical_regulatory',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='ct_glp1'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["kind"], "technology")
        self.assertEqual(link["canonical_name"], "GLP-1 obesity drugs")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_semantic_scholar_dataset_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('s2ag_papers',1,'semantic_scholar','semantic_scholar:dataset:papers:records',
                    'Semantic Scholar S2AG - dataset papers approximate records',
                    's2ag_dataset_records_approx','records','research',
                    '2026-06-09T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, e.domain, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='s2ag_papers'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["kind"], "research_dataset")
        self.assertEqual(link["canonical_name"], "Semantic Scholar S2AG papers dataset")
        self.assertEqual(link["domain"], "research")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_eonet_event_category_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('eonet_wildfires',9,'eonet','eonet:wildfires:event_updates',
                    'NASA EONET — Wildfires event updates',
                    'earth_event_updates','events','earth_events',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, e.domain, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='eonet_wildfires'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["kind"], "earth_event_type")
        self.assertEqual(link["canonical_name"], "Wildfires")
        self.assertEqual(link["domain"], "earth_events")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_usgs_earthquake_band_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('usgs_quakes_m6',9,'usgs_earthquakes','usgs_earthquakes:m60_plus',
                    'USGS Earthquake Hazards — M6.0+ earthquakes',
                    'earthquakes_m60_plus','earthquakes','earth_events',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, e.domain, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='usgs_quakes_m6'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["kind"], "earth_event_type")
        self.assertEqual(link["canonical_name"], "Earthquakes")
        self.assertEqual(link["domain"], "earth_events")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_gdacs_alert_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('gdacs_quakes',9,'gdacs_alerts','gdacs_alerts:type:EQ',
                    'GDACS — Earthquake disaster alerts',
                    'gdacs_alerts_by_type','alerts','earth_events',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('gdacs_china',9,'gdacs_alerts','gdacs_alerts:country:CHN:china',
                    'GDACS — China disaster alerts',
                    'gdacs_alerts_by_country','alerts','earth_events',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        links = self.conn.execute(
            """
            SELECT el.ref_id, e.kind, e.canonical_name, e.domain, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id IN ('gdacs_quakes', 'gdacs_china')
            ORDER BY el.ref_id
            """
        ).fetchall()

        self.assertGreaterEqual(out["matched"], 2)
        self.assertEqual(links[0]["ref_id"], "gdacs_china")
        self.assertEqual(links[0]["kind"], "country_region")
        self.assertEqual(links[0]["canonical_name"], "China")
        self.assertEqual(links[1]["ref_id"], "gdacs_quakes")
        self.assertEqual(links[1]["kind"], "earth_event_type")
        self.assertEqual(links[1]["canonical_name"], "Earthquakes")

    def test_autolink_nasa_gistemp_climate_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('gistemp_global',9,'nasa_gistemp','nasa_gistemp:global:monthly_anomaly',
                    'NASA GISTEMP — Global monthly temperature anomaly',
                    'temperature_anomaly_monthly','degC anomaly vs 1951-1980','climate',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, e.domain, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='gistemp_global'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["kind"], "climate_indicator")
        self.assertEqual(link["canonical_name"], "Global temperature anomaly")
        self.assertEqual(link["domain"], "climate")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_noaa_gml_greenhouse_gas_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('co2_global',9,'noaa_gml_greenhouse_gases','noaa_gml:co2_global:monthly_mean',
                    'NOAA GML — Global CO2 monthly mean concentration',
                    'greenhouse_gas_monthly_mean','ppm','climate',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, e.domain, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='co2_global'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["kind"], "climate_indicator")
        self.assertEqual(link["canonical_name"], "Global CO2 atmospheric concentration")
        self.assertEqual(link["domain"], "climate")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_noaa_enso_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('oni',9,'noaa_enso','noaa_enso:oni',
                    'NOAA PSL ENSO — Oceanic Nino Index',
                    'enso_oni','degC anomaly','climate',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, e.domain, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='oni'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["kind"], "climate_indicator")
        self.assertEqual(link["canonical_name"], "Oceanic Nino Index")
        self.assertEqual(link["domain"], "climate")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_noaa_climate_index_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('pdo',9,'noaa_climate_indices','noaa_climate_indices:pdo',
                    'NOAA PSL Climate Indices — Pacific Decadal Oscillation',
                    'climate_regime_index','index','climate',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, e.domain, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='pdo'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["kind"], "climate_indicator")
        self.assertEqual(link["canonical_name"], "Pacific Decadal Oscillation")
        self.assertEqual(link["domain"], "climate")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_noaa_nsidc_sea_ice_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('arctic_extent',9,'noaa_nsidc_sea_ice','noaa_nsidc_sea_ice:arctic:sea_ice_extent',
                    'NOAA/NSIDC Sea Ice Index — Arctic sea ice extent',
                    'sea_ice_extent','million square kilometers','climate',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, e.domain, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='arctic_extent'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["kind"], "climate_indicator")
        self.assertEqual(link["canonical_name"], "Arctic sea ice extent")
        self.assertEqual(link["domain"], "climate")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_noaa_swpc_solar_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('solar_f107',9,'noaa_swpc_solar','noaa_swpc_solar:solar_cycle:f107',
                    'NOAA SWPC - F10.7 cm solar radio flux',
                    'solar_radio_flux_f107','sfu','space_weather',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, e.domain, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='solar_f107'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["kind"], "space_weather_indicator")
        self.assertEqual(link["canonical_name"], "F10.7 cm solar radio flux")
        self.assertEqual(link["domain"], "space_weather")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_fred_financial_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('dgs10',9,'fred_financial','fred_financial:DGS10:level',
                    'FRED Financial Conditions - 10-year Treasury yield',
                    'treasury_yield','percent','financial_conditions',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, e.domain, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='dgs10'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["kind"], "financial_indicator")
        self.assertEqual(link["canonical_name"], "10-year Treasury yield")
        self.assertEqual(link["domain"], "financial_conditions")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_ecb_fx_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('eur_usd',9,'ecb_fx','ecb_fx:USD:eur_reference_rate',
                    'ECB FX - USD per EUR reference rate',
                    'fx_reference_rate','USD per EUR','financial_conditions',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, e.domain, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='eur_usd'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["kind"], "financial_indicator")
        self.assertEqual(link["canonical_name"], "USD per EUR reference rate")
        self.assertEqual(link["domain"], "financial_conditions")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_nih_reporter_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('nih_crispr',1,'nih_reporter','nih_reporter:crispr_gene_editing:awards',
                    'NIH RePORTER - CRISPR gene editing awards per fiscal year',
                    'nih_awards_per_year','awards/year','biomed',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, e.domain, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='nih_crispr'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["kind"], "technology")
        self.assertEqual(link["canonical_name"], "CRISPR gene editing")
        self.assertEqual(link["domain"], "biomed")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_nsf_awards_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('nsf_quantum',1,'nsf_awards','nsf_awards:quantum_computing:awards',
                    'NSF Awards - Quantum computing awards per calendar year',
                    'nsf_awards_per_year','awards/year','science_funding',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, e.domain, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='nsf_quantum'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["kind"], "technology")
        self.assertEqual(link["canonical_name"], "Quantum computing")
        self.assertEqual(link["domain"], "science_funding")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_openfda_drugsfda_topic_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('fda_glp1',9,'openfda_drugsfda','openfda_drugsfda:glp1_obesity_drugs:approved_submissions',
                    'openFDA Drugs@FDA — GLP-1 obesity drugs approved submissions',
                    'fda_approved_submissions','submissions','clinical_regulatory',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('fda_glp1_type9',9,'openfda_drugsfda','openfda_drugsfda:glp1_obesity_drugs:snapshot:class:type_9',
                    'openFDA Drugs@FDA — GLP-1 obesity drugs current TYPE_9 approved submissions',
                    'fda_current_approved_submission_class','submissions','clinical_regulatory',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        links = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, e.domain, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id IN ('fda_glp1', 'fda_glp1_type9')
            ORDER BY el.ref_id
            """
        ).fetchall()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(len(links), 2)
        for link in links:
            self.assertEqual(link["kind"], "technology")
            self.assertEqual(link["canonical_name"], "GLP-1 obesity drugs")
            self.assertEqual(link["domain"], "clinical_regulatory")
            self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_cordis_topic_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('cordis_dac',1,'cordis','cordis:direct_air_capture:ec_contribution_eur',
                    'CORDIS - Direct air capture and carbon removal EC contribution',
                    'cordis_ec_contribution','EUR','science_funding',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, e.domain, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='cordis_dac'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["kind"], "technology")
        self.assertEqual(link["canonical_name"], "Direct air capture and carbon removal")
        self.assertEqual(link["domain"], "science_funding")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_usaspending_sam_topic_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('hypersonics_awards',1,'usaspending_sam',
                    'usaspending_sam:hypersonics:prime_awards_obligation_amount',
                    'USAspending - Hypersonics prime award obligations',
                    'prime_awards_obligation_amount','USD','defense_procurement',
                    '2026-06-17T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, e.domain, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='hypersonics_awards'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["kind"], "technology")
        self.assertEqual(link["canonical_name"], "Hypersonics")
        self.assertEqual(link["domain"], "defense_procurement")
        self.assertGreaterEqual(link["confidence"], 0.9)

    def test_autolink_synthetic_control_series(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (id,pillar_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES ('control_flat',1,'synthetic','control_flat',
                    'CONTROL (synthetic flat)',
                    'works_per_year','works/year','control',
                    '2023-01-02T00:00:00+00:00')
            """
        )
        self.conn.commit()

        out = world_state.autolink_series_entities(self.conn)
        link = self.conn.execute(
            """
            SELECT e.kind, e.canonical_name, e.domain, el.confidence
            FROM entity_links el
            JOIN entities e ON e.id=el.entity_id
            WHERE el.ref_table='series' AND el.ref_id='control_flat'
            """
        ).fetchone()

        self.assertGreaterEqual(out["matched"], 1)
        self.assertEqual(link["kind"], "synthetic_control")
        self.assertEqual(link["canonical_name"], "Synthetic flat control")
        self.assertEqual(link["domain"], "quality_control")
        self.assertEqual(link["confidence"], 1.0)

    def test_audit_surfaces_series_health_failures(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (
                id,pillar_id,provider,external_id,label,metric,unit,domain,created_at
            ) VALUES (
                'stale_macro',1,'world_bank','fixture.macro','Fixture stale macro',
                'macro_indicator','USD','macro','2026-01-01T00:00:00+00:00'
            )
            """
        )
        self.conn.execute(
            """
            INSERT INTO series_health (
                series_id,status,fresh_status,complete_status,valid_status,recon_status,prov_status,
                days_stale,n_gaps,n_outliers,n_revisions,health_score,detail,audited_at
            ) VALUES (
                'stale_macro','fail','fail','ok','ok','ok','ok',
                2000,0,0,0,75.0,'latest 2020 (6y lag >4)','2026-06-18T00:00:00+00:00'
            )
            """
        )
        self.conn.commit()

        out = world_state.audit(self.conn)
        rendered = world_state.format_audit(out)
        failure = out["series_health"]["failures"][0]

        self.assertEqual(out["series_health"]["fail"], 1)
        self.assertEqual(out["series_health"]["reviewed_failures"], 0)
        self.assertEqual(out["series_health"]["unreviewed_failures"], 1)
        self.assertEqual(failure["series_id"], "stale_macro")
        self.assertEqual(failure["provider"], "world_bank")
        self.assertIsNone(failure["health_failure_review"])
        self.assertIn("latest 2020", failure["detail"])
        self.assertIn("health failures:", rendered)
        self.assertIn("- world_bank:Fixture stale macro [stale_macro]", rendered)

    def test_audit_marks_reviewed_upstream_source_limited_health_failures(self) -> None:
        self.conn.execute(
            """
            INSERT INTO series (
                id,pillar_id,provider,external_id,label,metric,unit,domain,created_at
            ) VALUES (
                'germany_hs8541',1,'comtrade','comtrade:8541:276',
                'Semiconductor diodes / photovoltaic cells imports — Germany',
                'trade_value','USD','trade','2026-01-01T00:00:00+00:00'
            )
            """
        )
        self.conn.execute(
            """
            INSERT INTO series_health (
                series_id,status,fresh_status,complete_status,valid_status,recon_status,prov_status,
                days_stale,n_gaps,n_outliers,n_revisions,health_score,detail,audited_at
            ) VALUES (
                'germany_hs8541','fail','fail','ok','ok','ok','ok',
                2361,0,0,0,75.0,'{"fresh":"latest 2019 (7y lag >3)"}','2026-06-18T00:00:00+00:00'
            )
            """
        )
        self.conn.commit()

        out = world_state.audit(self.conn)
        rendered = world_state.format_audit(out)
        failure = out["series_health"]["failures"][0]

        self.assertEqual(out["series_health"]["fail"], 1)
        self.assertEqual(out["series_health"]["reviewed_failures"], 1)
        self.assertEqual(out["series_health"]["unreviewed_failures"], 0)
        self.assertEqual(failure["health_failure_review"]["status"], "reviewed_upstream_source_limit")
        self.assertIn("health failure review: reviewed=1 unreviewed=0", rendered)
        self.assertIn("reviewed=reviewed_upstream_source_limit", rendered)
        self.assertIn("health failure review notes:", rendered)
        self.assertIn("use paid/full Comtrade", rendered)

    def test_audit_separates_local_and_offloaded_raw_doc_bytes(self) -> None:
        old_repo_root = world_state.db.REPO_ROOT
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                raw_dir = root / "data" / "raw"
                (raw_dir / "aa").mkdir(parents=True)
                local_hash = "a" * 64
                remote_hash = "b" * 64
                local_path = raw_dir / "aa" / f"{local_hash}.json"
                local_path.write_bytes(b'{"ok": true}')
                manifest = root / "data" / "_offload_manifest.jsonl"
                manifest.write_text(
                    json.dumps(
                        {
                            "ts": "2026-06-18T08:39:57+00:00",
                            "local_path": str(raw_dir),
                            "remote_uri": "s3://example-bucket/raw",
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
                world_state.db.REPO_ROOT = root
                self.conn.execute(
                    """
                    INSERT INTO raw_docs (content_hash,source_id,url,media_type,byte_len,path,fetched_at)
                    VALUES
                      (?,NULL,'https://example.test/local','application/json',12,?,
                       '2026-06-18T00:00:00+00:00'),
                      (?,NULL,'https://example.test/remote','application/json',34,?,
                       '2026-06-18T00:00:00+00:00')
                    """,
                    (
                        local_hash,
                        f"data/raw/aa/{local_hash}.json",
                        remote_hash,
                        f"data/raw/bb/{remote_hash}.json",
                    ),
                )
                self.conn.commit()

                out = world_state.audit(self.conn)
                rendered = world_state.format_audit(out)
                raw = out["raw_doc_coverage"]

                self.assertEqual(raw["raw_docs_indexed"], 2)
                self.assertEqual(raw["raw_docs_present_local"], 1)
                self.assertEqual(raw["raw_docs_missing_local"], 1)
                self.assertEqual(raw["raw_docs_offloaded"], 1)
                self.assertEqual(raw["raw_docs_missing_unaccounted"], 0)
                self.assertEqual(raw["raw_doc_local_bytes"], 12)
                self.assertEqual(raw["raw_doc_offloaded_bytes_estimated"], 34)
                self.assertIn("raw byte files: indexed=2 local=1 offloaded=1 missing_unaccounted=0", rendered)
        finally:
            world_state.db.REPO_ROOT = old_repo_root

    def test_topic_matching_uses_token_boundaries(self) -> None:
        self._fact("ai", predicate="ai compute capacity", rationale="AI power bottleneck")
        self._fact("ukraine", predicate="conflict_deaths", rationale="Ukraine battle deaths")

        facts, _ = world_state.visible_facts(
            self.conn,
            "AI power",
            date(2023, 12, 31),
            snapshot_created_at=datetime(2023, 12, 31, tzinfo=timezone.utc),
        )

        self.assertEqual([f["id"] for f in facts], ["ai"])

    def test_topic_prefilter_keeps_source_title_matches(self) -> None:
        self.conn.execute(
            """
            INSERT INTO sources (id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,cost_cents)
            VALUES ('src','https://example.test/source-title','solid state battery source title',
                    1,'primary',90,'fixture','2023-01-01T00:00:00+00:00',0)
            """
        )
        self._fact(
            "source_title_only",
            predicate="observed deployment",
            rationale="unrelated metric fixture",
            source_id="src",
        )

        facts, _ = world_state.visible_facts(
            self.conn,
            "solid state battery",
            date(2023, 12, 31),
            snapshot_created_at=datetime(2023, 12, 31, tzinfo=timezone.utc),
        )

        self.assertEqual([f["id"] for f in facts], ["source_title_only"])
        self.assertEqual(facts[0]["source_title"], "solid state battery source title")

    def test_diverse_facts_keeps_unique_predicates_inside_limit(self) -> None:
        facts = [
            {"id": "a1", "predicate": "observed crowded_metric", "source_id": "src_a"},
            {"id": "a2", "predicate": "observed crowded_metric", "source_id": "src_a"},
            {"id": "b1", "predicate": "observed buried_metric", "source_id": "src_b"},
            {"id": "a3", "predicate": "observed crowded_metric", "source_id": "src_a"},
        ]

        selected = world_state._diverse_facts(facts, 2)

        self.assertEqual([f["id"] for f in selected], ["a1", "b1"])


if __name__ == "__main__":
    unittest.main()
