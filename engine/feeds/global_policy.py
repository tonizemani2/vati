"""Global (non-US) policy/regulatory activity — keyless collector for the Policy layer (pillar 8).

The substrate's policy layer was Western-and-US-skewed: Federal Register (US), OFAC/EU sanctions, plus
Australia/Canada permitting. This collector adds genuinely non-US regulatory-activity COUNT-OVER-TIME
series — the shape that fires a changepoint detector (a single decree has no time-series; an annual
count of acts matching a policy topic does) — from two keyless official sources:

  • UK — legislation.gov.uk Atom search. For each of ~50 structural policy topics (shared with the
    Federal Register taxonomy), the OpenSearch `totalResults` of UK legislation published in a year
    whose text matches the topic → one annual series per topic (`global_policy:uk:<slug>:per_year`).

  • EU — EUR-Lex CELLAR SPARQL (publications.europa.eu). Counts of EU legal acts per year by
    resource-type (regulations / directives / decisions) and the all-acts total → EU legislative-output
    series (`global_policy:eu:<type>:per_year`). This is the volume/tempo of EU lawmaking, a leading
    indicator of regulatory regime shifts.

Leak discipline: every observation is keyed on the REAL publication year and annual bins stop at the
last COMPLETE year (the partial current year is dropped). Counts are taken verbatim from the official
APIs; a topic/year that returns nothing is absent, never filled. Leak class = leading/coincident
(regulatory activity tends to move with or just ahead of the priced policy outcome). $0, keyless.

Run directly:  uv run python -m engine.feeds.global_policy
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Reuse the exact structural policy taxonomy used for the US Federal Register, so UK/EU/US are
# topic-comparable across jurisdictions.
from engine.feeds.federal_register import TOPICS

UA = "predictthefuture research (research@vaticinus.com)"
OUT_PATH = Path(__file__).resolve().parents[2] / "data" / "feeds" / "global_policy.jsonl"
START_YEAR = 2010
SPACING_S = 0.25

UK_BASE = "https://www.legislation.gov.uk/all"
EURLEX_SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"


def _last_full_year() -> int:
    return datetime.now(timezone.utc).year - 1


# ── UK: legislation.gov.uk Atom OpenSearch totalResults per topic-year ────────────────────────────
def _uk_count(term: str, year: int) -> int | None:
    # `text=` does a full-text search; `format=atom` returns an OpenSearch feed carrying totalResults.
    q = urllib.parse.urlencode({"text": term, "format": "atom"})
    url = f"{UK_BASE}/{year}?{q}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/atom+xml"})
        with urllib.request.urlopen(req, timeout=25) as resp:  # noqa: S310 official keyless API
            body = resp.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 — keyless endpoint; skip rather than fabricate
        return None
    m = re.search(r"totalResults[^>]*>\s*(\d+)", body) or re.search(r"totalResults[\"'>\s]+?(\d+)", body)
    return int(m.group(1)) if m else None


def _uk_topic_term(topic: dict) -> str:
    # Reuse the US term but strip boolean operators the UK text search does not parse the same way:
    # take the first quoted phrase or the first bare keyword as a robust query.
    term = topic["term"]
    mph = re.search(r'"([^"]+)"', term)
    if mph:
        return mph.group(1)
    return re.split(r"\s+OR\s+|\s+", term.strip())[0]


def collect_uk(*, log=print) -> list[dict]:
    rows: list[dict] = []
    last = _last_full_year()
    for topic in TOPICS:
        term = _uk_topic_term(topic)
        landed = 0
        for year in range(START_YEAR, last + 1):
            c = _uk_count(term, year)
            time.sleep(SPACING_S)
            if c is None or c <= 0:
                continue
            landed += 1
            rows.append({
                "series_id": f"global_policy:uk:{topic['slug']}:per_year",
                "date": f"{year}-12-31", "value": float(c),
                "unit": "acts/yr", "metric": "policy_docs_per_year", "domain": "policy",
                "title": f"UK legislation — {topic['title']} acts per year", "jurisdiction": "UK",
            })
        log(f"  + uk/{topic['slug']:<26s} {landed} yrs")
    return rows


# ── EU: EUR-Lex CELLAR SPARQL — legal acts per year by resource type ──────────────────────────────
_RESOURCE_TYPES = (("REG", "regulations"), ("DIR", "directives"), ("DEC", "decisions"))


def _eurlex_query(q: str) -> dict | None:
    url = f"{EURLEX_SPARQL}?query={urllib.parse.quote(q)}&format=json"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"}
        )
        with urllib.request.urlopen(req, timeout=70) as resp:  # noqa: S310 official keyless endpoint
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        return None


def collect_eu(*, log=print) -> list[dict]:
    rows: list[dict] = []
    last = _last_full_year()
    type_uris = ", ".join(  # SPARQL IN(...) requires comma-separated members
        f"<http://publications.europa.eu/resource/authority/resource-type/{code}>"
        for code, _ in _RESOURCE_TYPES
    )
    code_label = {code: lab for code, lab in _RESOURCE_TYPES}
    for year in range(START_YEAR, last + 1):
        q = (
            "PREFIX cdm:<http://publications.europa.eu/ontology/cdm#> "
            "SELECT ?rt (COUNT(DISTINCT ?w) AS ?n) WHERE { "
            "?w cdm:work_date_document ?d . ?w cdm:work_has_resource-type ?rt . "
            f'FILTER(STRSTARTS(STR(?d),"{year}")) FILTER(?rt IN ({type_uris})) '
            "} GROUP BY ?rt"
        )
        res = _eurlex_query(q)
        time.sleep(SPACING_S)
        if not res:
            log(f"  - eu {year}: unreachable")
            continue
        total = 0
        for b in res.get("results", {}).get("bindings", []):
            code = b["rt"]["value"].rsplit("/", 1)[-1]
            n = int(b["n"]["value"])
            total += n
            lab = code_label.get(code, code.lower())
            rows.append({
                "series_id": f"global_policy:eu:{lab}:per_year",
                "date": f"{year}-12-31", "value": float(n),
                "unit": "acts/yr", "metric": "policy_docs_per_year", "domain": "policy",
                "title": f"EU legal acts — {lab} per year", "jurisdiction": "EU",
            })
        if total:
            rows.append({
                "series_id": "global_policy:eu:all_acts:per_year",
                "date": f"{year}-12-31", "value": float(total),
                "unit": "acts/yr", "metric": "policy_docs_per_year", "domain": "policy",
                "title": "EU legal acts — all (reg+dir+dec) per year", "jurisdiction": "EU",
            })
        log(f"  + eu {year}: {total} acts")
    return rows


def collect(*, log=print) -> list[dict]:
    log("UK legislation.gov.uk (per-topic annual counts):")
    uk = collect_uk(log=log)
    log("\nEUR-Lex CELLAR SPARQL (EU legal acts per year by type):")
    eu = collect_eu(log=log)
    all_rows = uk + eu
    if not all_rows:
        log("\nno observations fetched (both jurisdictions unreachable); existing file preserved")
        return []
    all_rows.sort(key=lambda r: (r["series_id"], r["date"]))
    tmp = OUT_PATH.with_suffix(".jsonl.tmp")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w", encoding="utf-8") as f:
        for o in all_rows:
            f.write(json.dumps(o, ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(OUT_PATH)
    log(f"\nwrote {len(all_rows)} obs across {len({r['series_id'] for r in all_rows})} series "
        f"(UK {len({r['series_id'] for r in uk})} + EU {len({r['series_id'] for r in eu})}) → {OUT_PATH}")
    return all_rows


if __name__ == "__main__":
    observations = collect()
    if not observations:
        print("\nNO observations collected this run (no data written).")
    else:
        print(f"\n{len(observations)} obs across {len({o['series_id'] for o in observations})} series.")
