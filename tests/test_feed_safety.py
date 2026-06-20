from __future__ import annotations

import tempfile
import unittest
import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from engine import db
from engine.feeds import baci, clinicaltrials, comtrade, cordis, ecb_fx, eonet, epoch_ai, eu_sanctions, federal_register, fred, fred_financial, gdacs_alerts, gdelt, global_equities, ilo, ingest, lbnl, metaculus, nasa_gistemp, nih_reporter, noaa_climate_indices, noaa_enso, noaa_gml_greenhouse_gases, noaa_nsidc_sea_ice, noaa_swpc_solar, nsf_awards, ofac_sdn, openfda_drugsfda, owid, patentsview, pubmed, semantic_scholar, un_comtrade, usaspending_sam, usgs_earthquakes, usgs_minerals, wikipedia, world_bank
from engine.feeds.collect_all import KEYLESS
from engine.feeds.ingest import FEED_META


class FeedSafetyTests(unittest.TestCase):
    def test_metaculus_token_can_load_from_env_file(self) -> None:
        old_env = metaculus.ENV_PATH
        old_token = metaculus.os.environ.pop("METACULUS_TOKEN", None)
        try:
            with tempfile.TemporaryDirectory() as td:
                metaculus.ENV_PATH = Path(td) / ".env"
                metaculus.ENV_PATH.write_text("OTHER=x\nMETACULUS_TOKEN='fixture-token'\n", encoding="utf-8")

                self.assertEqual(metaculus._token(), "fixture-token")
        finally:
            metaculus.ENV_PATH = old_env
            if old_token is not None:
                metaculus.os.environ["METACULUS_TOKEN"] = old_token

    def test_federal_register_is_registered_for_collection_and_ingest(self) -> None:
        self.assertIn("federal_register", KEYLESS)
        self.assertIn("federal_register", FEED_META)
        self.assertIn("ofac_sdn", KEYLESS)
        self.assertIn("ofac_sdn", FEED_META)
        self.assertIn("eu_sanctions", KEYLESS)
        self.assertIn("eu_sanctions", FEED_META)
        self.assertIn("clinicaltrials", KEYLESS)
        self.assertIn("clinicaltrials", FEED_META)
        self.assertIn("openfda_drugsfda", KEYLESS)
        self.assertIn("openfda_drugsfda", FEED_META)
        self.assertIn("fred_financial", KEYLESS)
        self.assertIn("fred_financial", FEED_META)
        self.assertIn("fred", KEYLESS)
        self.assertIn("fred", FEED_META)
        self.assertIn("lbnl", KEYLESS)
        self.assertIn("lbnl", FEED_META)
        self.assertIn("ecb_fx", KEYLESS)
        self.assertIn("ecb_fx", FEED_META)
        self.assertIn("global_equities", KEYLESS)
        self.assertIn("global_equities", FEED_META)
        self.assertIn("nih_reporter", KEYLESS)
        self.assertIn("nih_reporter", FEED_META)
        self.assertIn("nsf_awards", KEYLESS)
        self.assertIn("nsf_awards", FEED_META)
        self.assertIn("cordis", KEYLESS)
        self.assertIn("cordis", FEED_META)
        self.assertIn("usaspending_sam", KEYLESS)
        self.assertIn("usaspending_sam", FEED_META)
        self.assertIn("metaculus", KEYLESS)
        self.assertIn("metaculus", FEED_META)
        self.assertIn("eonet", KEYLESS)
        self.assertIn("eonet", FEED_META)
        self.assertIn("usgs_earthquakes", KEYLESS)
        self.assertIn("usgs_earthquakes", FEED_META)
        self.assertIn("gdacs_alerts", KEYLESS)
        self.assertIn("gdacs_alerts", FEED_META)
        self.assertIn("nasa_gistemp", KEYLESS)
        self.assertIn("nasa_gistemp", FEED_META)
        self.assertIn("noaa_gml_greenhouse_gases", KEYLESS)
        self.assertIn("noaa_gml_greenhouse_gases", FEED_META)
        self.assertIn("noaa_enso", KEYLESS)
        self.assertIn("noaa_enso", FEED_META)
        self.assertIn("noaa_climate_indices", KEYLESS)
        self.assertIn("noaa_climate_indices", FEED_META)
        self.assertIn("noaa_nsidc_sea_ice", KEYLESS)
        self.assertIn("noaa_nsidc_sea_ice", FEED_META)
        self.assertIn("noaa_swpc_solar", KEYLESS)
        self.assertIn("noaa_swpc_solar", FEED_META)
        self.assertIn("baci", KEYLESS)
        self.assertIn("baci", FEED_META)
        self.assertIn("un_comtrade", KEYLESS)
        self.assertIn("un_comtrade", FEED_META)
        self.assertIn("semantic_scholar", KEYLESS)
        self.assertIn("semantic_scholar", FEED_META)
        self.assertIn("epoch_ai", KEYLESS)
        self.assertIn("epoch_ai", FEED_META)
        self.assertIn("pubmed", KEYLESS)
        self.assertIn("pubmed", FEED_META)
        self.assertIn("wikipedia", KEYLESS)
        self.assertIn("wikipedia", FEED_META)

    def test_owid_capability_rows_match_existing_series_key(self) -> None:
        old_get_text = owid._get_text
        try:
            owid._get_text = lambda url: (
                "entity,code,year,cost\n"
                "World,OWID_WRL,1989,10\n"
                "World,OWID_WRL,1990,5\n"
                "World,OWID_WRL,1991,2\n"
                "United States,USA,1990,1\n"
            )
            rows = owid._fetch_capability_curve(
                {
                    "slug": "solar-pv-prices",
                    "col": "cost",
                    "entity": "World",
                    "ref": 1.0,
                    "metric": "solar_pv_affordability",
                    "unit": "W per $",
                    "domain": "energy",
                },
                log=lambda *_: None,
            )
        finally:
            owid._get_text = old_get_text

        self.assertEqual([r["series_id"] for r in rows], ["solar-pv-prices:cost", "solar-pv-prices:cost"])
        self.assertEqual(rows[0]["date"], "1990-12-31")
        self.assertEqual(rows[0]["value"], 0.2)
        self.assertEqual(rows[0]["metric"], "solar_pv_affordability")
        self.assertEqual(rows[0]["domain"], "energy")

    def test_ingest_refreshes_existing_series_source_and_domain(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        db.init_db(conn)
        conn.execute(
            "INSERT OR IGNORE INTO pillars (id,name,description,ord,status) VALUES (5,'Physical','test',5,'in_progress')"
        )
        for sid in ("old_source", "new_source"):
            conn.execute(
                """
                INSERT INTO sources
                    (id,url,title,pillar_id,kind,trust_score,trust_rationale,accessed_at,cost_cents,content_hash)
                VALUES
                    (?,?,?,?,?,?,?,?,?,?)
                """,
                (sid, f"https://example.test/{sid}", sid, 5, "primary", 90, "test", "2026-01-01T00:00:00+00:00", 0, sid),
            )
        conn.execute(
            """
            INSERT INTO series
                (id,pillar_id,source_id,provider,external_id,label,metric,unit,domain,created_at)
            VALUES
                ('series_1',5,'old_source','owid','solar-pv-prices:cost','old','solar_pv_affordability','old','legacy','2026-01-01T00:00:00+00:00')
            """
        )

        try:
            series_id = ingest._get_or_create_series(
                conn,
                "owid",
                "solar-pv-prices:cost",
                "solar_pv_affordability",
                pillar_id=5,
                source_id="new_source",
                label="solar pv affordability",
                unit="W per $",
                domain="energy",
            )
            row = conn.execute("SELECT source_id, label, unit, domain FROM series WHERE id='series_1'").fetchone()
        finally:
            conn.close()

        self.assertEqual(series_id, "series_1")
        self.assertEqual(row["source_id"], "new_source")
        self.assertEqual(row["label"], "solar pv affordability")
        self.assertEqual(row["unit"], "W per $")
        self.assertEqual(row["domain"], "energy")

    def test_baci_rows_carry_release_date_separate_from_trade_year(self) -> None:
        row = baci._series_row(
            series_id="baci:hs22:850760:2024:global_import_value",
            metric="baci_global_import_value",
            event_year=2024,
            value=123.0,
            unit="USD",
            title="BACI 2024 global import value — HS850760 Lithium-ion accumulators",
        )

        self.assertEqual(row["date"], "2024-12-31")
        self.assertEqual(row["event_time"], "2024-12-31")
        self.assertEqual(row["observed_at"], "2024-12-31")
        self.assertEqual(row["published_at"], "2026-01-22")

    def test_baci_hhi_and_top_share(self) -> None:
        hhi, top = baci._hhi_and_top_share({"A": 60.0, "B": 40.0})

        self.assertEqual(hhi, 5200.0)
        self.assertEqual(top, 0.6)

    def test_comtrade_merge_rows_retains_previous_official_rows(self) -> None:
        old = [
            {
                "series_id": "comtrade:8541:276",
                "date": "2022-12-31",
                "value": 1.0,
                "unit": "USD",
                "title": "old 2022",
            },
            {
                "series_id": "comtrade:8541:276",
                "date": "2023-12-31",
                "value": 2.0,
                "unit": "USD",
                "title": "old 2023",
            },
        ]
        new = [
            {
                "series_id": "comtrade:8541:276",
                "date": "2022-12-31",
                "value": 3.0,
                "unit": "USD",
                "title": "new 2022",
            }
        ]

        merged = comtrade._merge_rows(old, new)
        by_key = {(r["series_id"], r["date"]): r for r in merged}

        self.assertEqual(len(merged), 2)
        self.assertEqual(by_key[("comtrade:8541:276", "2022-12-31")]["value"], 3.0)
        self.assertEqual(by_key[("comtrade:8541:276", "2023-12-31")]["value"], 2.0)

    def test_un_comtrade_metric_rows_reuse_dependency_series_keys(self) -> None:
        rows = un_comtrade.metric_rows(
            {
                "cmd": "7403",
                "key": "refined_copper",
                "label": "Refined copper imports",
                "domain": "metals",
            },
            {
                2023: {
                    "value": 1000.0,
                    "hhi": 0.42,
                    "nir": 0.8,
                    "top_code": 152,
                    "top_share": 0.65,
                    "n": 12,
                }
            },
        )
        by_metric = {row["metric"]: row for row in rows}

        self.assertEqual(by_metric["refined_copper_import_value"]["series_id"], "7403_import_value")
        self.assertEqual(by_metric["refined_copper_import_hhi"]["series_id"], "7403_import_hhi")
        self.assertEqual(by_metric["refined_copper_net_import_reliance"]["series_id"], "7403_net_import_reliance")
        self.assertEqual(by_metric["refined_copper_import_value"]["date"], "2023-12-31")
        self.assertEqual(by_metric["refined_copper_import_value"]["published_at"], "2024-12-31")
        self.assertEqual(by_metric["refined_copper_import_value"]["observed_at"], "2023-12-31")
        self.assertEqual(by_metric["refined_copper_import_hhi"]["uncertainty"], 0.01)
        self.assertEqual(by_metric["refined_copper_net_import_reliance"]["domain"], "metals")

    def test_world_bank_merge_rows_retains_previous_official_rows(self) -> None:
        old = [
            {"series_id": "world_bank:NY.GDP.MKTP.CD:NGA", "date": "2023-12-31", "value": 1.0},
            {"series_id": "world_bank:NY.GDP.MKTP.CD:NGA", "date": "2024-12-31", "value": 2.0},
        ]
        new = [{"series_id": "world_bank:NY.GDP.MKTP.CD:NGA", "date": "2023-12-31", "value": 3.0}]

        merged = world_bank._merge_rows(old, new)
        by_key = {(r["series_id"], r["date"]): r for r in merged}

        self.assertEqual(len(merged), 2)
        self.assertEqual(by_key[("world_bank:NY.GDP.MKTP.CD:NGA", "2023-12-31")]["value"], 3.0)
        self.assertEqual(by_key[("world_bank:NY.GDP.MKTP.CD:NGA", "2024-12-31")]["value"], 2.0)

    def test_ilo_merge_rows_retains_previous_official_rows(self) -> None:
        old = [
            {"series_id": "ilo:UNE_DEAP_SEX_AGE_RT_A:IND", "date": "2024-12-31", "value": 1.0},
            {"series_id": "ilo:UNE_DEAP_SEX_AGE_RT_A:IND", "date": "2025-12-31", "value": 2.0},
        ]
        new = [{"series_id": "ilo:UNE_DEAP_SEX_AGE_RT_A:IND", "date": "2024-12-31", "value": 3.0}]

        merged = ilo._merge_rows(old, new)
        by_key = {(r["series_id"], r["date"]): r for r in merged}

        self.assertEqual(len(merged), 2)
        self.assertEqual(by_key[("ilo:UNE_DEAP_SEX_AGE_RT_A:IND", "2024-12-31")]["value"], 3.0)
        self.assertEqual(by_key[("ilo:UNE_DEAP_SEX_AGE_RT_A:IND", "2025-12-31")]["value"], 2.0)

    def test_semantic_scholar_manifest_normalize_release(self) -> None:
        rows = semantic_scholar.normalize_release(
            {
                "release_id": "2026-06-09",
                "datasets": [
                    {"name": "papers", "description": "214M records in 30 1.8GB files."},
                    {"name": "citations", "description": "2.4B records in 30 8.5GB files."},
                ],
            },
            ["2026-06-02", "2026-06-09"],
        )
        by_id = {r["series_id"]: r for r in rows}

        self.assertEqual(by_id["semantic_scholar:release:known_releases"]["value"], 2.0)
        self.assertEqual(by_id["semantic_scholar:release:dataset_count"]["value"], 2.0)
        self.assertEqual(by_id["semantic_scholar:dataset:papers:records"]["value"], 214_000_000.0)
        self.assertEqual(by_id["semantic_scholar:dataset:citations:records"]["value"], 2_400_000_000.0)
        self.assertEqual(by_id["semantic_scholar:dataset:papers:files"]["value"], 30.0)
        self.assertEqual(by_id["semantic_scholar:dataset:papers:records"]["published_at"], "2026-06-09")

    def test_epoch_ai_normalize_frontier_compute_by_domain_year(self) -> None:
        text = "\n".join(
            ["System,Domain,Publication date,Training compute (FLOP)"]
            + [f"Model {year},Language,{year}-06-01,{10 ** (year - 2000)}" for year in range(2010, 2018)]
            + [
                "Smaller 2012,Language,2012-08-01,1",
                "Vision short,Vision,2011-01-01,1000",
            ]
        )

        rows = epoch_ai.normalize(text)
        by_key = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0]["series_id"], "Language")
        self.assertEqual(rows[0]["metric"], "frontier_training_compute")
        self.assertEqual(rows[0]["domain"], "AI")
        self.assertEqual(by_key[("Language", "2012-12-31")]["value"], 10 ** 12)
        self.assertEqual(by_key[("Language", "2012-12-31")]["uncertainty"], 0.5 * 10 ** 12)
        self.assertNotIn(("Vision", "2011-12-31"), by_key)

    def test_global_equities_normalize_chart_caps_future_dates_and_keeps_close(self) -> None:
        payload = {
            "chart": {
                "result": [{
                    "meta": {"currency": "USD"},
                    "timestamp": [
                        int(datetime(2024, 1, 2, tzinfo=timezone.utc).timestamp()),
                        int(datetime(2026, 6, 20, tzinfo=timezone.utc).timestamp()),
                    ],
                    "indicators": {"quote": [{"close": [123.456789, 999.0], "volume": [1000, 2000]}]},
                }]
            }
        }

        rows = global_equities.normalize_chart(
            global_equities.EquitySpec("NVDA", "US", "NVIDIA"),
            payload,
            start=date(2020, 1, 1),
            today=date(2026, 6, 18),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["series_id"], "global_equities:NVDA:close")
        self.assertEqual(rows[0]["date"], "2024-01-02")
        self.assertEqual(rows[0]["value"], 123.456789)
        self.assertEqual(rows[0]["unit"], "USD")
        self.assertEqual(rows[0]["metric"], "equity_close")

    def test_usaspending_sam_normalize_summary_emits_count_and_obligation(self) -> None:
        rows = usaspending_sam.normalize_summary(
            usaspending_sam.Topic("semiconductors", ("semiconductor",), "Semiconductors"),
            2025,
            {"results": {"prime_awards_count": 12, "prime_awards_obligation_amount": 345.67}},
            today=date(2026, 6, 18),
        )
        by_metric = {r["metric"]: r for r in rows}

        self.assertEqual(by_metric["prime_awards_count"]["series_id"], "usaspending_sam:semiconductors:prime_awards_count")
        self.assertEqual(by_metric["prime_awards_count"]["date"], "2025-09-30")
        self.assertEqual(by_metric["prime_awards_count"]["value"], 12.0)
        self.assertEqual(by_metric["prime_awards_count"]["unit"], "awards")
        self.assertEqual(by_metric["prime_awards_obligation_amount"]["value"], 345.67)
        self.assertEqual(by_metric["prime_awards_obligation_amount"]["unit"], "USD")
        self.assertTrue(by_metric["prime_awards_obligation_amount"]["period_complete"])

    def test_usaspending_sam_current_fiscal_year_is_fytd(self) -> None:
        rows = usaspending_sam.normalize_summary(
            usaspending_sam.Topic("ai", ("artificial intelligence",), "Artificial intelligence"),
            2026,
            {"results": {"prime_awards_count": 5, "prime_awards_obligation_amount": 99}},
            today=date(2026, 6, 18),
        )

        self.assertTrue(all(r["date"] == "2026-06-18" for r in rows))
        self.assertTrue(all(not r["period_complete"] for r in rows))

    def test_usaspending_sam_merge_rows_replaces_same_series_date(self) -> None:
        old = [{"series_id": "s", "date": "2024-09-30", "value": 1}]
        new = [{"series_id": "s", "date": "2024-09-30", "value": 2}]

        self.assertEqual(usaspending_sam._merge_rows(old, new), new)

    def test_usaspending_sam_selected_topics_supports_resume_offset(self) -> None:
        topics = usaspending_sam.selected_topics(limit=1, offset=len(usaspending_sam.TOPICS) - 1)

        self.assertEqual([t.slug for t in topics], ["biomanufacturing"])

    def test_cordis_parse_decimal_supports_eu_decimal_comma(self) -> None:
        self.assertEqual(cordis._parse_decimal("1.234.567,89"), 1234567.89)
        self.assertEqual(cordis._parse_decimal("2073781,25"), 2073781.25)

    def test_cordis_normalize_projects_caps_current_year_and_drops_future(self) -> None:
        rows = cordis.normalize_projects(
            [
                {
                    "id": "p1",
                    "title": "Artificial intelligence for power grid operations",
                    "objective": "Machine learning for smart grid control",
                    "ecSignatureDate": "2026-02-01",
                    "ecMaxContribution": "1000,50",
                    "totalCost": "2000",
                    "_program": "HORIZON",
                },
                {
                    "id": "future",
                    "title": "Artificial intelligence after the cutoff",
                    "ecSignatureDate": "2027-01-01",
                    "ecMaxContribution": "9",
                    "totalCost": "9",
                },
            ],
            today=date(2026, 6, 18),
        )
        by_series = {r["series_id"]: r for r in rows}

        self.assertEqual(by_series["cordis:artificial_intelligence:projects"]["date"], "2026-06-18")
        self.assertEqual(by_series["cordis:artificial_intelligence:projects"]["value"], 1.0)
        self.assertEqual(by_series["cordis:artificial_intelligence:ec_contribution_eur"]["value"], 1000.5)
        self.assertNotIn("future", {p["id"] for r in rows for p in r["sample_projects"]})

    def test_cordis_normalize_projects_uses_topic_labels_for_matching(self) -> None:
        rows = cordis.normalize_projects(
            [
                {
                    "id": "p1",
                    "title": "A generic project title",
                    "ecSignatureDate": "2024-03-01",
                    "ecMaxContribution": "10",
                    "totalCost": "20",
                    "_program": "HORIZON",
                }
            ],
            labels={"p1": ["Quantum technologies", "engineering and technology/quantum computing"]},
            today=date(2026, 6, 18),
        )
        by_series = {r["series_id"]: r for r in rows}

        self.assertEqual(by_series["cordis:quantum:projects"]["date"], "2024-12-31")
        self.assertEqual(by_series["cordis:quantum:projects"]["value"], 1.0)

    def test_eonet_normalize_caps_future_dates_and_counts_open_events(self) -> None:
        events = [
            {
                "id": "EONET_1",
                "title": "Wildfire Test",
                "link": "https://example.test/eonet/1",
                "closed": None,
                "categories": [{"id": "wildfires", "title": "Wildfires"}],
                "sources": [{"id": "NASA", "url": "https://example.test"}],
                "geometry": [
                    {"date": "2026-06-16T12:00:00Z", "type": "Point", "coordinates": [1, 2]},
                    {"date": "2026-06-20T12:00:00Z", "type": "Point", "coordinates": [3, 4]},
                ],
            }
        ]

        rows = eonet.normalize(events, today=date(2026, 6, 17), window_days=30)
        by_key = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(by_key[("eonet:wildfires:event_updates", "2026-06-16")]["value"], 1.0)
        self.assertEqual(by_key[("eonet:wildfires:new_events", "2026-06-16")]["value"], 1.0)
        self.assertEqual(by_key[("eonet:wildfires:snapshot:open_events", "2026-06-17")]["value"], 1.0)
        self.assertNotIn(("eonet:wildfires:event_updates", "2026-06-20"), by_key)

    def test_usgs_earthquakes_normalize_caps_future_and_counts_bands(self) -> None:
        def feature(event_id: str, day: str, mag: float, **props) -> dict:
            millis = int(datetime.combine(date.fromisoformat(day), datetime.min.time(), timezone.utc).timestamp() * 1000)
            return {
                "id": event_id,
                "properties": {
                    "mag": mag,
                    "time": millis,
                    "title": f"M {mag}",
                    "place": "Test place",
                    "url": "https://example.test",
                    **props,
                },
                "geometry": {"type": "Point", "coordinates": [1, 2, 3]},
            }

        rows = usgs_earthquakes.normalize(
            [
                feature("a", "2026-06-16", 4.8),
                feature("b", "2026-06-16", 6.2, tsunami=1, sig=700, felt=4),
                feature("future", "2026-06-20", 7.1),
            ],
            today=date(2026, 6, 17),
            window_days=30,
        )
        by_key = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(by_key[("usgs_earthquakes:all_m45_plus", "2026-06-16")]["value"], 2.0)
        self.assertEqual(by_key[("usgs_earthquakes:m60_plus", "2026-06-16")]["value"], 1.0)
        self.assertEqual(by_key[("usgs_earthquakes:tsunami_flagged", "2026-06-16")]["value"], 1.0)
        self.assertEqual(by_key[("usgs_earthquakes:significant", "2026-06-16")]["value"], 1.0)
        self.assertEqual(by_key[("usgs_earthquakes:felt_reports", "2026-06-16")]["value"], 1.0)
        self.assertNotIn(("usgs_earthquakes:m70_plus", "2026-06-20"), by_key)

    def test_gdacs_alerts_normalize_caps_future_and_counts_country_level_type(self) -> None:
        def feature(event_id: int, fromdate: str, level: str, eventtype: str = "EQ") -> dict:
            return {
                "type": "Feature",
                "properties": {
                    "eventtype": eventtype,
                    "eventid": event_id,
                    "episodeid": 1,
                    "name": "Earthquake in China",
                    "alertlevel": level,
                    "alertscore": 3 if level == "Red" else 2,
                    "iscurrent": "true",
                    "country": "China",
                    "iso3": "CHN",
                    "fromdate": f"{fromdate}T00:00:00",
                    "todate": "2026-06-18T00:00:00",
                    "datemodified": f"{fromdate}T12:00:00",
                    "affectedcountries": [{"iso2": "CN", "iso3": "CHN", "countryname": "China"}],
                    "severitydata": {"severity": 6.4, "severityunit": "M"},
                    "url": {"report": "https://example.test/report"},
                },
                "geometry": {"type": "Point", "coordinates": [1, 2]},
            }

        rows = gdacs_alerts.normalize(
            [
                feature(1, "2026-06-16", "Red"),
                feature(2, "2026-06-20", "Orange"),
            ],
            today=date(2026, 6, 17),
            window_days=30,
        )
        by_key = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(by_key[("gdacs_alerts:all", "2026-06-16")]["value"], 1.0)
        self.assertEqual(by_key[("gdacs_alerts:type:EQ", "2026-06-16")]["value"], 1.0)
        self.assertEqual(by_key[("gdacs_alerts:level:red", "2026-06-16")]["value"], 1.0)
        self.assertEqual(by_key[("gdacs_alerts:country:CHN:china", "2026-06-16")]["value"], 1.0)
        self.assertEqual(by_key[("gdacs_alerts:current:all", "2026-06-17")]["value"], 1.0)
        self.assertNotIn(("gdacs_alerts:level:orange", "2026-06-20"), by_key)

    def test_nasa_gistemp_normalize_monthly_and_annual_anomalies(self) -> None:
        text = """Land-Ocean: Global Means
Year,Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec,J-D,D-N,DJF,MAM,JJA,SON
2025,1.38,1.26,1.37,1.24,1.08,1.07,1.02,1.18,1.25,1.19,1.21,1.05,1.19,1.21,1.30,1.23,1.09,1.22
2026,1.08,1.24,1.32,1.17,1.12,***,***,***,***,***,***,***,***,***,1.13,1.20,***,***
"""
        rows = nasa_gistemp.normalize_region({"slug": "global", "title": "Global"}, text)
        by_key = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(by_key[("nasa_gistemp:global:monthly_anomaly", "2025-02-28")]["value"], 1.26)
        self.assertEqual(by_key[("nasa_gistemp:global:annual_anomaly", "2025-12-31")]["value"], 1.19)
        self.assertEqual(by_key[("nasa_gistemp:global:monthly_anomaly", "2026-05-31")]["value"], 1.12)
        self.assertNotIn(("nasa_gistemp:global:monthly_anomaly", "2026-06-30"), by_key)
        self.assertNotIn(("nasa_gistemp:global:annual_anomaly", "2026-12-31"), by_key)

    def test_noaa_gml_greenhouse_gases_normalize_monthly_mean_and_trend(self) -> None:
        text = """# comment
  2026       1      2026.042        428.11          0.10        426.95          0.06
  2026       2      2026.125        428.55          0.10        427.17          0.06
"""
        rows = noaa_gml_greenhouse_gases.normalize_dataset(
            {
                "slug": "co2_global",
                "gas": "CO2",
                "region": "Global",
                "unit": "ppm",
                "mean_idx": 3,
                "trend_idx": 5,
                "trend_label": "trend",
            },
            text,
        )
        by_key = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(by_key[("noaa_gml:co2_global:monthly_mean", "2026-01-31")]["value"], 428.11)
        self.assertEqual(by_key[("noaa_gml:co2_global:trend", "2026-02-28")]["value"], 427.17)

    def test_noaa_enso_normalize_monthly_index_and_missing_values(self) -> None:
        text = """ 1950         2026
 2025   0.10   0.20 -99.99   0.40   0.50   0.60   0.70   0.80   0.90   1.00   1.10   1.20
"""
        rows = noaa_enso.normalize_dataset(
            {
                "slug": "oni",
                "title": "Oceanic Nino Index",
                "unit": "degC anomaly",
                "metric": "enso_oni",
            },
            text,
        )
        by_key = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(by_key[("noaa_enso:oni", "2025-02-28")]["value"], 0.2)
        self.assertNotIn(("noaa_enso:oni", "2025-03-31"), by_key)
        self.assertEqual(by_key[("noaa_enso:oni", "2025-12-31")]["value"], 1.2)

    def test_noaa_climate_indices_normalize_monthly_index_and_missing_values(self) -> None:
        text = """ 1950         2026
 2025   0.10 -99.90   0.30   0.40   0.50   0.60   0.70   0.80   0.90   1.00 -9.90   1.20
"""
        rows = noaa_climate_indices.normalize_dataset(
            {"slug": "pdo", "title": "Pacific Decadal Oscillation"},
            text,
        )
        by_key = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(by_key[("noaa_climate_indices:pdo", "2025-01-31")]["value"], 0.1)
        self.assertNotIn(("noaa_climate_indices:pdo", "2025-02-28"), by_key)
        self.assertNotIn(("noaa_climate_indices:pdo", "2025-11-30"), by_key)
        self.assertEqual(by_key[("noaa_climate_indices:pdo", "2025-12-31")]["value"], 1.2)

    def test_noaa_nsidc_sea_ice_normalize_extent_area_and_missing(self) -> None:
        text = """year, mo,source_dataset, region, extent,   area
2025,  5,    NSIDC-0803,      N,  12.14,  10.33
2026,  5,         -9999,      N,  -9999,  -9999
"""
        rows = noaa_nsidc_sea_ice.normalize_month_file(
            {"slug": "arctic", "title": "Arctic", "path": "north", "prefix": "N"},
            text,
        )
        by_key = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(by_key[("noaa_nsidc_sea_ice:arctic:sea_ice_extent", "2025-05-31")]["value"], 12.14)
        self.assertEqual(by_key[("noaa_nsidc_sea_ice:arctic:sea_ice_area", "2025-05-31")]["value"], 10.33)
        self.assertNotIn(("noaa_nsidc_sea_ice:arctic:sea_ice_extent", "2026-05-31"), by_key)

    def test_noaa_swpc_solar_normalize_observed_only_and_caps_future(self) -> None:
        rows = noaa_swpc_solar.normalize_solar_cycle(
            [
                {"time-tag": "2026-05", "ssn": 101.4, "smoothed_ssn": -1.0, "f10.7": 125.69},
                {"time-tag": "2026-06", "ssn": 99.0, "f10.7": 120.0},
            ],
            today=date(2026, 6, 17),
        )
        by_key = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(by_key[("noaa_swpc_solar:solar_cycle:ssn", "2026-05-31")]["value"], 101.4)
        self.assertEqual(by_key[("noaa_swpc_solar:solar_cycle:f107", "2026-05-31")]["value"], 125.69)
        self.assertNotIn(("noaa_swpc_solar:solar_cycle:smoothed_ssn", "2026-05-31"), by_key)
        self.assertNotIn(("noaa_swpc_solar:solar_cycle:ssn", "2026-06-30"), by_key)

    def test_noaa_swpc_solar_daily_aggregates_cap_future_rows(self) -> None:
        kp_rows = noaa_swpc_solar.normalize_kp(
            [
                {"time_tag": "2026-06-17T13:06:00", "estimated_kp": 2.0},
                {"time_tag": "2026-06-17T13:07:00", "estimated_kp": 5.33},
                {"time_tag": "2026-06-18T13:07:00", "estimated_kp": 6.0},
            ],
            today=date(2026, 6, 17),
        )
        xray_rows = noaa_swpc_solar.normalize_xrays(
            [
                {"time_tag": "2026-06-17T13:06:00Z", "energy": "0.1-0.8nm", "flux": 1e-6},
                {"time_tag": "2026-06-17T13:07:00Z", "energy": "0.1-0.8nm", "flux": 3e-6},
                {"time_tag": "2026-06-18T13:07:00Z", "energy": "0.1-0.8nm", "flux": 9e-6},
            ],
            today=date(2026, 6, 17),
        )
        kp = {(r["series_id"], r["date"]): r for r in kp_rows}
        xrays = {(r["series_id"], r["date"]): r for r in xray_rows}

        self.assertEqual(kp[("noaa_swpc_solar:geomagnetic:daily_max_estimated_kp", "2026-06-17")]["value"], 5.33)
        self.assertEqual(kp[("noaa_swpc_solar:geomagnetic:daily_minutes_kp_ge_5", "2026-06-17")]["value"], 1.0)
        self.assertNotIn(("noaa_swpc_solar:geomagnetic:daily_max_estimated_kp", "2026-06-18"), kp)
        self.assertEqual(xrays[("noaa_swpc_solar:goes_xray:0_1_0_8nm:daily_max_flux", "2026-06-17")]["value"], 3e-6)
        self.assertNotIn(("noaa_swpc_solar:goes_xray:0_1_0_8nm:daily_max_flux", "2026-06-18"), xrays)

    def test_fred_financial_normalize_skips_missing_and_future_values(self) -> None:
        text = """observation_date,DGS10
2026-06-12,4.48
2026-06-13,.
2026-06-18,4.50
"""
        rows = fred_financial.normalize_series(
            {"id": "DGS10", "title": "10-year Treasury yield", "metric": "treasury_yield", "unit": "percent"},
            text,
            today=date(2026, 6, 17),
        )
        by_key = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(by_key[("fred_financial:DGS10:level", "2026-06-12")]["value"], 4.48)
        self.assertNotIn(("fred_financial:DGS10:level", "2026-06-13"), by_key)
        self.assertNotIn(("fred_financial:DGS10:level", "2026-06-18"), by_key)
        self.assertEqual(rows[0]["title"], "FRED Financial Conditions - 10-year Treasury yield")

    def test_fred_supply_normalize_reuses_existing_annual_series_key(self) -> None:
        text = """observation_date,PCU335311335311
2004-01-01,10
2005-01-01,100
2025-01-01,443.2
2026-01-01,500
2024-01-01,.
"""
        rows = fred.normalize_series(
            {
                "id": "PCU335311335311",
                "title": "Large-power transformer PPI",
                "metric": "transformer_ppi",
                "unit": "index (1982=100)",
                "domain": "energy/grid",
            },
            text,
        )
        by_key = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(by_key[("PCU335311335311", "2005-12-31")]["value"], 100.0)
        self.assertEqual(by_key[("PCU335311335311", "2025-12-31")]["metric"], "transformer_ppi")
        self.assertEqual(by_key[("PCU335311335311", "2025-12-31")]["domain"], "energy/grid")
        self.assertNotIn(("PCU335311335311", "2004-12-31"), by_key)
        self.assertNotIn(("PCU335311335311", "2026-12-31"), by_key)
        self.assertNotIn(("PCU335311335311", "2024-12-31"), by_key)

    def test_lbnl_queue_normalize_reuses_existing_series_key(self) -> None:
        rows = lbnl.normalize_queue((
            {
                "year": 2023,
                "gw": 2600,
                "source_url": "https://example.test/queued-up",
                "note": "fixture",
            },
        ))

        self.assertEqual(rows[0]["series_id"], "queued_up_active_capacity")
        self.assertEqual(rows[0]["date"], "2023-12-31")
        self.assertEqual(rows[0]["published_at"], "2024-04-30")
        self.assertEqual(rows[0]["metric"], "interconnection_queue_capacity")
        self.assertEqual(rows[0]["domain"], "energy/grid")

    def test_ecb_fx_normalize_skips_missing_and_future_values(self) -> None:
        text = """Date,USD,JPY,GBP,
2026-06-17,1.1591,185.82,N/A,
2026-06-18,1.1600,186.00,N/A,
2026-06-16,N/A,184.50,N/A,
2026-06-01,N/A,N/A,0.84,
"""
        rows = ecb_fx.normalize_csv(text, today=date(2026, 6, 17))
        by_key = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(by_key[("ecb_fx:USD:eur_reference_rate", "2026-06-17")]["value"], 1.1591)
        self.assertEqual(by_key[("ecb_fx:JPY:eur_reference_rate", "2026-06-16")]["value"], 184.5)
        self.assertNotIn(("ecb_fx:USD:eur_reference_rate", "2026-06-16"), by_key)
        self.assertNotIn(("ecb_fx:USD:eur_reference_rate", "2026-06-18"), by_key)
        self.assertNotIn(("ecb_fx:GBP:eur_reference_rate", "2026-06-01"), by_key)
        self.assertEqual(by_key[("ecb_fx:USD:eur_reference_rate", "2026-06-17")]["unit"], "USD per EUR")

    def test_nih_reporter_normalize_topic_skips_missing_counts(self) -> None:
        rows = nih_reporter.normalize_topic(
            {"slug": "crispr_gene_editing", "title": "CRISPR gene editing", "term": "crispr"},
            {2022: 4500, 2023: None, 2024: 5100},
        )
        by_key = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(by_key[("nih_reporter:crispr_gene_editing:awards", "2022-12-31")]["value"], 4500.0)
        self.assertEqual(by_key[("nih_reporter:crispr_gene_editing:awards", "2024-12-31")]["unit"], "awards/year")
        self.assertNotIn(("nih_reporter:crispr_gene_editing:awards", "2023-12-31"), by_key)
        self.assertEqual(rows[0]["title"], "NIH RePORTER - CRISPR gene editing awards per fiscal year")

    def test_pubmed_normalize_topic_skips_missing_counts(self) -> None:
        rows = pubmed.normalize_topic(
            {"slug": "crispr_gene_editing", "title": "CRISPR gene editing", "term": "CRISPR"},
            {2021: 7000, 2022: None, 2023: 8161},
        )
        by_key = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(by_key[("pubmed:crispr_gene_editing:publications", "2021-12-31")]["value"], 7000.0)
        self.assertEqual(by_key[("pubmed:crispr_gene_editing:publications", "2023-12-31")]["unit"], "publications/year")
        self.assertNotIn(("pubmed:crispr_gene_editing:publications", "2022-12-31"), by_key)
        self.assertEqual(rows[0]["metric"], "pubmed_publications_per_year")

    def test_wikipedia_pageviews_normalize_annual_counts(self) -> None:
        counts = wikipedia.yearly_counts(
            [
                {"timestamp": "2021010100", "views": 10},
                {"timestamp": "2021020100", "views": 15},
                {"timestamp": "2022010100", "views": 7},
                {"timestamp": "bad", "views": 999},
            ]
        )
        rows = wikipedia.normalize_article(
            {"slug": "deep_learning", "topic": "Deep learning", "title": "Deep_learning"},
            counts,
        )
        by_key = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(by_key[("Deep_learning", "2021-12-31")]["value"], 25.0)
        self.assertEqual(by_key[("Deep_learning", "2022-12-31")]["unit"], "views/year")
        self.assertEqual(rows[0]["metric"], "wikipedia_pageviews")
        self.assertEqual(rows[0]["published_at"], "2021-12-31")

    def test_nsf_awards_normalize_topic_skips_missing_counts(self) -> None:
        rows = nsf_awards.normalize_topic(
            {"slug": "quantum_computing", "title": "Quantum computing", "term": "quantum computing"},
            {2021: 95, 2022: None, 2023: 124},
        )
        by_key = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(by_key[("nsf_awards:quantum_computing:awards", "2021-12-31")]["value"], 95.0)
        self.assertEqual(by_key[("nsf_awards:quantum_computing:awards", "2023-12-31")]["unit"], "awards/year")
        self.assertNotIn(("nsf_awards:quantum_computing:awards", "2022-12-31"), by_key)
        self.assertEqual(rows[0]["title"], "NSF Awards - Quantum computing awards per calendar year")

    def test_metaculus_normalize_reads_new_aggregation_latest(self) -> None:
        rows = metaculus.normalize({
            "id": 123,
            "title": "Will the test pass?",
            "published_at": "2026-06-17T00:00:00Z",
            "question": {
                "id": 456,
                "type": "binary",
                "cp_reveal_time": "2026-06-18T00:00:00Z",
                "aggregations": {
                    "recency_weighted": {
                        "latest": {
                            "start_time": "2026-06-19T12:00:00Z",
                            "centers": [0.37],
                        }
                    }
                },
            },
        })

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["series_id"], "metaculus:123:456")
        self.assertEqual(rows[0]["date"], "2026-06-19")
        self.assertEqual(rows[0]["value"], 0.37)
        self.assertEqual(rows[0]["metric"], "community_probability")

    def test_metaculus_collect_writes_status_sidecar_when_blocked(self) -> None:
        old_out = metaculus.OUT_PATH
        old_status = metaculus.STATUS_PATH
        old_probe = metaculus.probe_access
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                metaculus.OUT_PATH = root / "metaculus.jsonl"
                metaculus.STATUS_PATH = root / "metaculus.status.json"
                metaculus.probe_access = lambda: (False, "fixture auth wall")

                rows, needs_key, reason = metaculus.collect(log=lambda *_args, **_kwargs: None)
                status = json.loads(metaculus.STATUS_PATH.read_text(encoding="utf-8"))

                self.assertEqual(rows, [])
                self.assertTrue(needs_key)
                self.assertEqual(reason, "fixture auth wall")
                self.assertFalse(metaculus.OUT_PATH.exists())
                self.assertTrue(status["needs_key"])
                self.assertFalse(status["works"])
                self.assertEqual(status["rows"], 0)
        finally:
            metaculus.OUT_PATH = old_out
            metaculus.STATUS_PATH = old_status
            metaculus.probe_access = old_probe

    def test_metaculus_collect_marks_visible_posts_without_aggregates_as_visibility_limited(self) -> None:
        old_out = metaculus.OUT_PATH
        old_status = metaculus.STATUS_PATH
        old_probe = metaculus.probe_access
        old_fetch = metaculus.fetch_questions
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                metaculus.OUT_PATH = root / "metaculus.jsonl"
                metaculus.STATUS_PATH = root / "metaculus.status.json"
                metaculus.probe_access = lambda: (True, "fixture posts visible")
                metaculus.fetch_questions = lambda: [{
                    "id": 1,
                    "title": "Hidden aggregate fixture",
                    "published_at": "2026-06-17T00:00:00Z",
                    "question": {
                        "id": 2,
                        "type": "binary",
                        "aggregations": {"recency_weighted": {"latest": None, "history": None}},
                    },
                }]

                rows, needs_key, reason = metaculus.collect(log=lambda *_args, **_kwargs: None)
                status = json.loads(metaculus.STATUS_PATH.read_text(encoding="utf-8"))

                self.assertEqual(rows, [])
                self.assertFalse(needs_key)
                self.assertIn("null/hidden", reason)
                self.assertFalse(metaculus.OUT_PATH.exists())
                self.assertTrue(status["visibility_limited"])
                self.assertFalse(status["works"])
                self.assertEqual(status["rows"], 0)
        finally:
            metaculus.OUT_PATH = old_out
            metaculus.STATUS_PATH = old_status
            metaculus.probe_access = old_probe
            metaculus.fetch_questions = old_fetch

    def test_patentsview_collect_writes_status_sidecar_when_key_gated(self) -> None:
        old_out = patentsview.OUT_PATH
        old_status = patentsview.STATUS_PATH
        old_probe = patentsview._probe_keyless
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                patentsview.OUT_PATH = root / "patentsview.jsonl"
                patentsview.STATUS_PATH = root / "patentsview.status.json"
                patentsview._probe_keyless = lambda: (False, "fixture HTTP 401")

                result = patentsview.collect(log=lambda *_args, **_kwargs: None)
                status = json.loads(patentsview.STATUS_PATH.read_text(encoding="utf-8"))

                self.assertFalse(result["works"])
                self.assertTrue(result["needs_key"])
                self.assertEqual(result["obs"], 0)
                self.assertFalse(patentsview.OUT_PATH.exists())
                self.assertTrue(status["needs_key"])
                self.assertFalse(status["works"])
                self.assertEqual(status["rows"], 0)
                self.assertIn("fixture HTTP 401", status["detail"])
        finally:
            patentsview.OUT_PATH = old_out
            patentsview.STATUS_PATH = old_status
            patentsview._probe_keyless = old_probe

    def test_nsf_awards_collect_checkpoints_completed_topics(self) -> None:
        old_out = nsf_awards.OUT_PATH
        old_topics = nsf_awards.TOPICS
        old_start = nsf_awards.START_YEAR
        old_end = nsf_awards.END_YEAR
        old_failures = nsf_awards.MAX_CONSECUTIVE_FAILURES
        old_offset = nsf_awards.TOPIC_OFFSET
        old_limit = nsf_awards.TOPIC_LIMIT
        old_count = nsf_awards.count_topic_year
        old_sleep = nsf_awards.time.sleep
        try:
            with tempfile.TemporaryDirectory() as td:
                nsf_awards.OUT_PATH = Path(td) / "nsf_awards.jsonl"
                nsf_awards.TOPICS = (
                    {"slug": "old_topic", "title": "Old topic", "term": "old"},
                    {"slug": "ok_topic", "title": "OK topic", "term": "ok"},
                    {"slug": "bad_topic", "title": "Bad topic", "term": "bad"},
                )
                nsf_awards.START_YEAR = 2014
                nsf_awards.END_YEAR = 2023
                nsf_awards.MAX_CONSECUTIVE_FAILURES = 2
                nsf_awards.TOPIC_OFFSET = 1
                nsf_awards.TOPIC_LIMIT = 2
                nsf_awards.time.sleep = lambda *_a, **_k: None
                nsf_awards.OUT_PATH.write_text(
                    '{"date":"2020-12-31","metric":"nsf_awards_per_year","series_id":"nsf_awards:old_topic:awards","term":"old","title":"old","topic":"Old topic","unit":"awards/year","value":7.0,"year":2020}\n',
                    encoding="utf-8",
                )

                def fake_count(topic, year):
                    return year if topic["slug"] == "ok_topic" else None

                nsf_awards.count_topic_year = fake_count
                rows = nsf_awards.collect(log=lambda *_a, **_k: None)

                self.assertEqual(len(rows), 10)
                self.assertTrue(nsf_awards.OUT_PATH.exists())
                persisted = nsf_awards.OUT_PATH.read_text(encoding="utf-8").splitlines()
                self.assertEqual(len(persisted), 11)
                self.assertTrue(any("nsf_awards:old_topic:awards" in row for row in persisted))
                self.assertTrue(any("nsf_awards:ok_topic:awards" in row for row in persisted))
                self.assertFalse(any("nsf_awards:bad_topic:awards" in row for row in persisted))
        finally:
            nsf_awards.OUT_PATH = old_out
            nsf_awards.TOPICS = old_topics
            nsf_awards.START_YEAR = old_start
            nsf_awards.END_YEAR = old_end
            nsf_awards.MAX_CONSECUTIVE_FAILURES = old_failures
            nsf_awards.TOPIC_OFFSET = old_offset
            nsf_awards.TOPIC_LIMIT = old_limit
            nsf_awards.count_topic_year = old_count
            nsf_awards.time.sleep = old_sleep

    def test_clinicaltrials_normalize_uses_first_posted_and_snapshot_date(self) -> None:
        study = {
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT000001",
                    "briefTitle": "A CRISPR Study",
                },
                "statusModule": {
                    "overallStatus": "RECRUITING",
                    "studyFirstPostDateStruct": {"date": "2024-05-10", "type": "ACTUAL"},
                },
                "sponsorCollaboratorsModule": {
                    "leadSponsor": {"name": "Example Sponsor", "class": "INDUSTRY"},
                },
                "designModule": {
                    "phases": ["PHASE2"],
                    "enrollmentInfo": {"count": 42, "type": "ESTIMATED"},
                },
            }
        }

        rows = clinicaltrials.normalize(
            {"slug": "crispr_gene_editing", "title": "CRISPR gene editing", "term": "CRISPR"},
            [study],
            snapshot_date="2026-06-17",
        )
        by_series = {r["series_id"]: r for r in rows}

        self.assertEqual(
            by_series["clinicaltrials:crispr_gene_editing:posted_studies"]["date"],
            "2024-05-10",
        )
        self.assertEqual(
            by_series["clinicaltrials:crispr_gene_editing:snapshot:total_studies"]["date"],
            "2026-06-17",
        )
        self.assertEqual(
            by_series["clinicaltrials:crispr_gene_editing:snapshot:status:recruiting"]["value"],
            1.0,
        )
        self.assertEqual(
            by_series["clinicaltrials:crispr_gene_editing:snapshot:phase:phase2"]["value"],
            1.0,
        )

    def test_openfda_drugsfda_normalize_uses_approval_dates_and_snapshot_date(self) -> None:
        record = {
            "application_number": "NDA123",
            "products": [{"brand_name": "EXAMPLE"}],
            "submissions": [
                {
                    "submission_type": "ORIG",
                    "submission_number": "1",
                    "submission_status": "AP",
                    "submission_status_date": "20240102",
                    "submission_class_code": "TYPE 1",
                    "application_docs": [{"type": "Letter", "date": "20240103", "url": "https://example.test"}],
                },
                {
                    "submission_type": "SUPPL",
                    "submission_number": "2",
                    "submission_status": "AP",
                    "submission_status_date": "20240506",
                    "submission_class_code": "LABELING",
                },
                {
                    "submission_type": "SUPPL",
                    "submission_number": "3",
                    "submission_status": "TA",
                    "submission_status_date": "20240601",
                },
            ],
        }

        rows = openfda_drugsfda.normalize(
            {"slug": "gene_therapy", "title": "Gene therapy"},
            [record],
            snapshot_date="2026-06-16",
        )
        by_series = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(
            by_series[("openfda_drugsfda:gene_therapy:approved_submissions", "2024-01-02")]["value"],
            1.0,
        )
        self.assertEqual(
            by_series[("openfda_drugsfda:gene_therapy:original_approvals", "2024-01-02")]["value"],
            1.0,
        )
        self.assertEqual(
            by_series[("openfda_drugsfda:gene_therapy:snapshot:applications", "2026-06-16")]["value"],
            1.0,
        )
        self.assertEqual(
            by_series[("openfda_drugsfda:gene_therapy:snapshot:approved_submissions", "2026-06-16")]["value"],
            2.0,
        )

    def test_openfda_drugsfda_normalize_skips_empty_topics(self) -> None:
        rows = openfda_drugsfda.normalize(
            {"slug": "crispr_gene_editing", "title": "CRISPR gene editing"},
            [],
            snapshot_date=None,
        )

        self.assertEqual(rows, [])

    def test_ofac_sdn_parse_and_normalize_counts_snapshot_dimensions(self) -> None:
        raw = b'''<?xml version="1.0"?>
        <sdnList xmlns="https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/XML">
          <publshInformation>
            <Publish_Date>06/11/2026</Publish_Date>
            <Record_Count>2</Record_Count>
          </publshInformation>
          <sdnEntry>
            <uid>1</uid><lastName>ACME BANK</lastName><sdnType>Entity</sdnType>
            <programList><program>CYBER2</program><program>RUSSIA-EO14024</program></programList>
            <addressList><address><country>Russia</country></address></addressList>
          </sdnEntry>
          <sdnEntry>
            <uid>2</uid><firstName>Jane</firstName><lastName>Doe</lastName><sdnType>Individual</sdnType>
            <programList><program>CYBER2</program></programList>
            <addressList><address><country>China</country></address></addressList>
          </sdnEntry>
        </sdnList>'''

        publish_date, record_count, entries = ofac_sdn.parse_xml(raw)
        rows = ofac_sdn.normalize(publish_date, record_count, entries)
        by_series = {r["series_id"]: r for r in rows}

        self.assertEqual(publish_date, "2026-06-11")
        self.assertEqual(record_count, 2)
        self.assertEqual(by_series["ofac_sdn:total:entries"]["value"], 2.0)
        self.assertEqual(by_series["ofac_sdn:type:entity"]["value"], 1.0)
        self.assertEqual(by_series["ofac_sdn:program:cyber2"]["value"], 2.0)
        self.assertEqual(by_series["ofac_sdn:country:russia"]["value"], 1.0)
        self.assertEqual(by_series["ofac_sdn:country:china"]["value"], 1.0)

    def test_eu_sanctions_parse_and_normalize_counts_snapshot_dimensions(self) -> None:
        raw = b'''<?xml version="1.0" encoding="UTF-8"?>
        <export xmlns="http://eu.europa.ec/fpi/fsd/export" generationDate="2026-06-05T15:51:25.849+02:00" globalFileId="182848">
          <sanctionEntity logicalId="1" unitedNationId="">
            <regulation programme="RUS" publicationDate="2022-01-01" />
            <subjectType code="person" classificationCode="P" />
            <nameAlias wholeName="Jane Sanctioned" strong="true" />
            <citizenship countryIso2Code="RU" countryDescription="RUSSIA" />
          </sanctionEntity>
          <sanctionEntity logicalId="2" unitedNationId="QDi.123">
            <regulation programme="RUS" publicationDate="2022-01-01" />
            <regulation programme="CYB" publicationDate="2024-01-01" />
            <subjectType code="enterprise" classificationCode="E" />
            <nameAlias wholeName="Acme Entity" strong="true" />
            <address countryIso2Code="CN" countryDescription="CHINA" />
          </sanctionEntity>
        </export>'''

        generation_date, global_file_id, entries = eu_sanctions.parse_xml(raw)
        rows = eu_sanctions.normalize(generation_date, global_file_id, entries)
        by_series = {r["series_id"]: r for r in rows}

        self.assertEqual(generation_date, "2026-06-05")
        self.assertEqual(global_file_id, "182848")
        self.assertEqual(by_series["eu_sanctions:total:entries"]["value"], 2.0)
        self.assertEqual(by_series["eu_sanctions:programme:rus"]["value"], 2.0)
        self.assertEqual(by_series["eu_sanctions:programme:cyb"]["value"], 1.0)
        self.assertEqual(by_series["eu_sanctions:subject_type:person"]["value"], 1.0)
        self.assertEqual(by_series["eu_sanctions:country:russia"]["value"], 1.0)
        self.assertEqual(by_series["eu_sanctions:country:china"]["value"], 1.0)

    def test_federal_register_normalize_counts_documents_and_rulemaking(self) -> None:
        docs = [
            {
                "document_number": "2026-1",
                "publication_date": "2026-06-17",
                "title": "AI rule",
                "type": "Rule",
                "html_url": "https://example.test/1",
                "agencies": [{"name": "Agency One", "slug": "agency-one"}],
            },
            {
                "document_number": "2026-2",
                "publication_date": "2026-06-17",
                "title": "AI notice",
                "type": "Notice",
                "html_url": "https://example.test/2",
                "agencies": [{"name": "Agency Two", "slug": "agency-two"}],
            },
            {
                "document_number": "2026-3",
                "publication_date": "2026-06-18",
                "title": "AI proposed rule",
                "type": "Proposed Rule",
                "html_url": "https://example.test/3",
                "agencies": [],
            },
        ]

        rows = federal_register.normalize(
            {"slug": "artificial_intelligence", "term": "AI", "title": "Artificial intelligence"},
            docs,
        )
        by_key = {(r["series_id"], r["date"]): r for r in rows}

        self.assertEqual(
            by_key[("federal_register:artificial_intelligence:documents", "2026-06-17")]["value"],
            2.0,
        )
        self.assertEqual(
            by_key[("federal_register:artificial_intelligence:rulemaking", "2026-06-17")]["value"],
            1.0,
        )
        self.assertEqual(
            by_key[("federal_register:artificial_intelligence:rulemaking", "2026-06-18")]["value"],
            1.0,
        )
        self.assertEqual(
            by_key[("federal_register:artificial_intelligence:documents", "2026-06-17")]["documents"][0]["agencies"][0]["slug"],
            "agency-one",
        )

    def test_gdelt_preserves_existing_file_when_refresh_empty(self) -> None:
        old_path = gdelt.OUT_PATH
        old_themes = gdelt.THEMES
        old_modes = gdelt.MODES
        old_fetch = gdelt.fetch_timeline
        old_fallback = gdelt.collect_recent_exports
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "gdelt.jsonl"
                path.write_text('{"series_id":"old","date":"2024-01-01","value":1}\n', encoding="utf-8")
                gdelt.OUT_PATH = path
                gdelt.THEMES = [{"slug": "x", "query": "x", "title": "X", "domain": "test"}]
                gdelt.MODES = [{"mode": "timelinevol", "unit": "unit", "signal": "volume"}]
                gdelt.fetch_timeline = lambda *_a, **_k: []
                gdelt.collect_recent_exports = lambda *_a, **_k: []

                obs = gdelt.collect(log=lambda *_a, **_k: None)

                self.assertEqual(obs, [])
                self.assertEqual(path.read_text(encoding="utf-8").count("\n"), 1)
                self.assertIn('"series_id":"old"', path.read_text(encoding="utf-8"))
        finally:
            gdelt.OUT_PATH = old_path
            gdelt.THEMES = old_themes
            gdelt.MODES = old_modes
            gdelt.fetch_timeline = old_fetch
            gdelt.collect_recent_exports = old_fallback

    def test_gdelt_preserves_existing_file_when_refresh_partial(self) -> None:
        old_path = gdelt.OUT_PATH
        old_themes = gdelt.THEMES
        old_modes = gdelt.MODES
        old_fetch = gdelt.fetch_timeline
        old_fallback = gdelt.collect_recent_exports
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "gdelt.jsonl"
                path.write_text(
                    "".join(
                        f'{{"series_id":"old","date":"2024-01-{day:02d}","value":1}}\n'
                        for day in range(1, 11)
                    ),
                    encoding="utf-8",
                )
                gdelt.OUT_PATH = path
                gdelt.THEMES = [{"slug": "x", "query": "x", "title": "X", "domain": "test"}]
                gdelt.MODES = [{"mode": "timelinevol", "unit": "unit", "signal": "volume"}]
                gdelt.fetch_timeline = lambda *_a, **_k: [{"date": "20240101T000000Z", "value": 2}]
                gdelt.collect_recent_exports = lambda *_a, **_k: []

                obs = gdelt.collect(log=lambda *_a, **_k: None)

                self.assertEqual(obs, [])
                self.assertEqual(path.read_text(encoding="utf-8").count("\n"), 10)
                self.assertIn('"series_id":"old"', path.read_text(encoding="utf-8"))
        finally:
            gdelt.OUT_PATH = old_path
            gdelt.THEMES = old_themes
            gdelt.MODES = old_modes
            gdelt.fetch_timeline = old_fetch
            gdelt.collect_recent_exports = old_fallback

    def test_gdelt_export_rows_use_dateadded_and_country_counts(self) -> None:
        row = [""] * 61
        row[1] = "20160619"
        row[29] = "4"
        row[33] = "3"
        row[34] = "-2"
        row[53] = "US"
        row[59] = "20260617173000"
        row2 = list(row)
        row2[29] = "1"
        row2[33] = "1"
        row2[34] = "4"
        row2[53] = "CH"

        obs = gdelt._normalize_export_rows([row, row2])
        by_series = {o["series_id"]: o for o in obs}

        self.assertEqual(by_series["gdelt_export:global:event_count"]["date"], "2026-06-17")
        self.assertEqual(by_series["gdelt_export:global:event_count"]["value"], 2.0)
        self.assertEqual(by_series["gdelt_export:global:article_mentions"]["value"], 4.0)
        self.assertEqual(by_series["gdelt_export:global:hostile_event_count"]["value"], 1.0)
        self.assertEqual(by_series["gdelt_export:global:avg_tone"]["value"], -0.5)
        self.assertEqual(by_series["gdelt_export:country:united_states:event_count"]["value"], 1.0)
        self.assertEqual(by_series["gdelt_export:country:china:event_count"]["value"], 1.0)

    def test_usgs_preserves_existing_file_when_refresh_empty(self) -> None:
        old_path = usgs_minerals.OUT_PATH
        old_commodities = usgs_minerals.COMMODITIES
        old_collect = usgs_minerals.collect_commodity
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "usgs_minerals.jsonl"
                path.write_text('{"series_id":"old","date":"2024-12-31","value":1}\n', encoding="utf-8")
                usgs_minerals.OUT_PATH = path
                usgs_minerals.COMMODITIES = [{"name": "Empty"}]
                usgs_minerals.collect_commodity = lambda *_a, **_k: []

                obs = usgs_minerals.collect(log=lambda *_a, **_k: None)

                self.assertEqual(obs, [])
                self.assertEqual(path.read_text(encoding="utf-8").count("\n"), 1)
                self.assertIn('"series_id":"old"', path.read_text(encoding="utf-8"))
        finally:
            usgs_minerals.OUT_PATH = old_path
            usgs_minerals.COMMODITIES = old_commodities
            usgs_minerals.collect_commodity = old_collect

    def test_usgs_preserves_existing_file_when_refresh_partial(self) -> None:
        old_path = usgs_minerals.OUT_PATH
        old_commodities = usgs_minerals.COMMODITIES
        old_collect = usgs_minerals.collect_commodity
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "usgs_minerals.jsonl"
                path.write_text(
                    "".join(
                        f'{{"series_id":"old","date":"202{year}-12-31","value":1}}\n'
                        for year in range(0, 10)
                    ),
                    encoding="utf-8",
                )
                usgs_minerals.OUT_PATH = path
                usgs_minerals.COMMODITIES = [{"name": "Partial"}]
                usgs_minerals.collect_commodity = lambda *_a, **_k: [
                    {"series_id": "new", "date": "2024-12-31", "value": 2, "unit": "unit", "title": "new"}
                ]

                obs = usgs_minerals.collect(log=lambda *_a, **_k: None)

                self.assertEqual(obs, [])
                self.assertEqual(path.read_text(encoding="utf-8").count("\n"), 10)
                self.assertIn('"series_id":"old"', path.read_text(encoding="utf-8"))
        finally:
            usgs_minerals.OUT_PATH = old_path
            usgs_minerals.COMMODITIES = old_commodities
            usgs_minerals.collect_commodity = old_collect


if __name__ == "__main__":
    unittest.main()
