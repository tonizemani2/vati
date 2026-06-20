from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from engine import world_catalog, world_state
from engine.feeds import collect_all, europe_pmc, ingest
from tests.test_world_state import memory_db


TOPIC = {"slug": "crispr_gene_editing", "title": "CRISPR gene editing", "term": "CRISPR"}

PAPER = {
    "source": "MED",
    "id": "12345678",
    "pmid": "12345678",
    "doi": "10.1000/crispr.2024.1",
    "title": "CRISPR delivery systems for in vivo gene editing",
    "abstractText": "A review of CRISPR delivery systems and clinical translation.",
    "authorString": "Ada Lovelace, Grace Hopper",
    "firstPublicationDate": "2024-04-12",
    "firstIndexDate": "2024-04-13",
    "dateOfRevision": "2024-05-01",
    "journalInfo": {"journal": {"title": "Genome Medicine"}},
    "isOpenAccess": "Y",
    "hasTextMinedTerms": "Y",
}


class EuropePMCTests(unittest.TestCase):
    def test_normalize_topic_emits_count_and_paper_rows(self) -> None:
        rows = europe_pmc.normalize_topic(
            TOPIC,
            {2023: 10, 2024: 12},
            [PAPER],
            today=date(2026, 6, 18),
        )

        self.assertEqual(len(rows), 3)
        count = rows[0]
        paper = rows[-1]
        self.assertEqual(count["series_id"], "europe_pmc:crispr_gene_editing:publications")
        self.assertEqual(count["metric"], "europe_pmc_publications_per_year")
        self.assertEqual(count["date"], "2023-12-31")
        self.assertEqual(paper["series_id"], "europe_pmc:paper:crispr_gene_editing:MED:12345678")
        self.assertEqual(paper["metric"], "europe_pmc_paper_publication")
        self.assertEqual(paper["paper_external_id"], "MED:12345678")
        self.assertEqual(paper["paper_doi"], "10.1000/crispr.2024.1")
        self.assertIn("CRISPR delivery systems", paper["paper_title"])

    def test_collect_writes_bounded_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            old_out = europe_pmc.OUT_PATH
            europe_pmc.OUT_PATH = Path(td) / "europe_pmc.jsonl"
            try:
                with (
                    mock.patch.object(europe_pmc, "TOPICS", (TOPIC,)),
                    mock.patch.object(europe_pmc, "START_YEAR", 2023),
                    mock.patch.object(europe_pmc, "END_YEAR", 2024),
                    mock.patch.object(europe_pmc, "_hit_count", side_effect=[10, 12]),
                    mock.patch.object(europe_pmc, "_paper_results", return_value=[PAPER]),
                ):
                    rows = europe_pmc.collect(log=lambda *_: None, paper_page_size=1)
                stored = [
                    json.loads(line)
                    for line in europe_pmc.OUT_PATH.read_text(encoding="utf-8").splitlines()
                ]
            finally:
                europe_pmc.OUT_PATH = old_out

        self.assertEqual(len(rows), 3)
        self.assertEqual(stored[-1]["provenance"], "official_europe_pmc_rest_search_result")
        self.assertEqual(stored[-1]["cost_cents"], 0)

    def test_collector_is_keyless_ingestable_and_mapped_to_research(self) -> None:
        self.assertIn("europe_pmc", collect_all.KEYLESS)
        self.assertIn("europe_pmc", ingest.FEED_META)
        self.assertEqual(world_catalog.SOURCE_FEED_MAP["europe_pmc"], ("europe_pmc",))
        self.assertIn("europe_pmc", world_state.RESEARCH_PROVIDERS)

    def test_ingest_lands_papers_raw_docs_facts_and_research_pack(self) -> None:
        conn = memory_db()
        try:
            rows = europe_pmc.normalize_topic(
                TOPIC,
                {2024: 12},
                [PAPER],
                today=date(2026, 6, 18),
            )
            with tempfile.TemporaryDirectory() as td:
                feed_dir = Path(td)
                (feed_dir / "europe_pmc.jsonl").write_text(
                    "\n".join(json.dumps(row) for row in rows) + "\n",
                    encoding="utf-8",
                )
                with mock.patch.object(ingest, "FEEDS_DIR", feed_dir):
                    out = ingest.ingest_feed(conn, "europe_pmc")

            self.assertEqual(out["status"], "ok")
            self.assertEqual(out["series"], 2)
            self.assertEqual(out["obs"], 2)
            self.assertEqual(out["papers"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM raw_docs").fetchone()[0], 1)
            paper = conn.execute("SELECT provider, external_id, title, abstract FROM papers").fetchone()
            self.assertEqual(paper["provider"], "europe_pmc")
            self.assertEqual(paper["external_id"], "MED:12345678")
            self.assertIn("clinical translation", paper["abstract"])

            facts = world_state.backfill_observation_facts(conn, provider="europe_pmc")
            self.assertEqual(facts["seen"], 2)
            pack = world_state.research_pack("CRISPR delivery", "2024-12-31", conn=conn)
            self.assertGreaterEqual(pack["snapshot"]["fact_count"], 1)
            self.assertEqual(pack["papers"][0]["provider"], "europe_pmc")
            self.assertIn("CRISPR delivery systems", pack["papers"][0]["title"])
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
