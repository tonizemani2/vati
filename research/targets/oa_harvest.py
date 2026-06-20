#!/usr/bin/env python3
"""Deterministic researcher harvest via OpenAlex (keyless).

For each topic query, pull recent works, aggregate the authors, and emit the
most-frequent real authors with their institution + ORCID. Zero hallucination:
every name comes straight from OpenAlex author records.

Writes JSONL rows to research/targets/researchers_openalex.jsonl
"""
import json
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

MAILTO = "research@vaticinus.com"  # OpenAlex polite-pool courtesy
OUT = Path(__file__).parent / "researchers_openalex.jsonl"

# (segment, query, min_year)
QUERIES = [
    ("forecasting-science", "judgmental forecasting accuracy", 2015),
    ("forecasting-science", "superforecasting calibration", 2015),
    ("forecasting-science", "wisdom of crowds prediction aggregation", 2014),
    ("forecasting-science", "probabilistic forecasting calibration scoring", 2015),
    ("forecasting-science", "geopolitical forecasting tournament", 2014),
    ("llm-forecasting", "large language model forecasting", 2022),
    ("llm-forecasting", "language model prediction calibration", 2022),
    ("llm-forecasting", "AI forecasting benchmark evaluation", 2022),
    ("prediction-markets", "prediction market accuracy information aggregation", 2012),
    ("prediction-markets", "prediction market design futarchy", 2010),
    ("decision-science", "overconfidence probability judgment", 2015),
    ("decision-science", "expert elicitation uncertainty quantification", 2015),
]


def fetch(query: str, year: int, per_page: int = 200) -> list[dict]:
    params = {
        "search": query,
        "filter": f"from_publication_date:{year}-01-01",
        "per_page": str(per_page),
        "sort": "cited_by_count:desc",
        "mailto": MAILTO,
    }
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": f"vaticinus ({MAILTO})"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read()).get("results", [])


def main():
    # author_id -> aggregate record
    authors: dict[str, dict] = {}
    counts: dict[str, int] = defaultdict(int)
    topics: dict[str, set] = defaultdict(set)
    for segment, q, year in QUERIES:
        try:
            works = fetch(q, year)
        except Exception as e:
            print(f"  ! {q}: {e}")
            continue
        for w in works:
            for a in w.get("authorships", []):
                au = a.get("author", {})
                aid = au.get("id")
                name = au.get("display_name")
                if not aid or not name:
                    continue
                counts[aid] += 1
                topics[aid].add(q)
                if aid not in authors:
                    inst = ""
                    insts = a.get("institutions", [])
                    if insts:
                        inst = insts[0].get("display_name", "") or ""
                    authors[aid] = {
                        "name": name,
                        "affiliation": inst,
                        "orcid": (au.get("orcid") or "").replace("https://orcid.org/", ""),
                        "openalex": aid,
                        "segment": "researcher",
                        "vein": segment,
                    }
        print(f"  {q}: {len(works)} works")
        time.sleep(0.3)

    rows = []
    for aid, rec in authors.items():
        rec["works_on_topic"] = counts[aid]
        rec["topics"] = sorted(topics[aid])
        rows.append(rec)
    # keep authors appearing on >=2 topic-works (filters one-off coauthors)
    rows = [r for r in rows if r["works_on_topic"] >= 2]
    rows.sort(key=lambda r: r["works_on_topic"], reverse=True)

    with OUT.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(rows)} researchers -> {OUT}")


if __name__ == "__main__":
    main()
