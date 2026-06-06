"""Pillar 8 — Policy / geo (free / keyless). What bends supply by decree?

Policy can create scarcity overnight (an export ban) or destroy it (a subsidy → demand pull). v1
signal: **Federal Register** document velocity per topic per year (official US rulemaking/notices,
keyless API, 2000+). Rising mentions of "export control", "critical minerals", "semiconductor" etc.
flag where the state is actively reshaping a supply curve — a leading policy-attention signal.

This is policy ATTENTION velocity (a v2 upgrade is LLM event extraction → typed creates/destroys-
scarcity events feeding the supply graph; the extract pipeline is ready). Tagged domain="policy".
$0; a cost-ledger row is logged (rule 3).
"""

from __future__ import annotations

import json
import sqlite3
import time
import urllib.parse
import urllib.request
from datetime import date
from math import sqrt

from engine import store
from engine.pillars.frontier import UA, _content_hash, _log_cost, _upsert_series, _upsert_source
from engine.schemas import Observation, Series, Source, SourceKind

POLICY_PILLAR_ID = 8
FED_REGISTER = "https://www.federalregister.gov/api/v1/documents.json"
WINDOW_START, CUTOFF_YEAR = 2004, 2024

# Topics that bend supply (scarcity by decree) — export controls, inputs, subsidised sectors.
TERMS: list[str] = [
    "export control", "critical minerals", "rare earth", "semiconductor", "tariff",
    "artificial intelligence", "electric vehicle", "carbon capture", "hydrogen",
    "nuclear energy", "gene therapy", "quantum", "lithium", "solar energy", "data privacy",
]


def _doc_count(term: str, year: int, *, retries: int = 2) -> int | None:
    params = {
        "conditions[term]": term,
        "conditions[publication_date][gte]": f"{year}-01-01",
        "conditions[publication_date][lte]": f"{year}-12-31",
        "per_page": "1",
    }
    url = f"{FED_REGISTER}?{urllib.parse.urlencode(params)}"
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            data = json.loads(urllib.request.urlopen(req, timeout=30).read())
            return int(data.get("count", 0))
        except Exception:  # noqa: BLE001 — rate-limit/parse: back off, retry, then None
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            return None


def collect(conn: sqlite3.Connection | None = None, *, log=print) -> dict:
    """Federal Register document velocity per policy topic per year. Idempotent. $0."""
    from engine import db
    own = conn is None
    if own:
        conn = db.connect()
        db.init_db(conn)
    _log_cost(conn, "federal_register_collect", "federal_register", float(len(TERMS)))
    years = list(range(WINDOW_START, CUTOFF_YEAR + 1))
    if _doc_count(TERMS[0], CUTOFF_YEAR) is None:
        log("  ! Federal Register API unreachable — skipping policy this run. 0 series.")
        conn.commit()
        if own:
            conn.close()
        return {"series": 0, "obs": 0}
    n_series = n_obs = 0
    for term in TERMS:
        counts: dict[int, int] = {}
        for y in years:
            c = _doc_count(term, y)
            if c is not None:
                counts[y] = c
            time.sleep(0.15)
        counts = {y: v for y, v in counts.items() if v > 0}
        if len(counts) < 8:
            log(f"  - skip {term!r} ({len(counts)} yrs)")
            continue
        ys = sorted(counts)
        last = ys[-1]
        payload = {str(y): counts[y] for y in ys}
        src = Source(
            url=f"{FED_REGISTER}?conditions[term]={urllib.parse.quote(term)}",
            title=f'Federal Register documents — "{term}"',
            pillar_id=POLICY_PILLAR_ID, kind=SourceKind.filing, trust_score=80,
            trust_rationale=(
                "Federal Register API (keyless, official US rulemaking/notices): count of documents "
                "matching the term per year — a policy-attention velocity (policy that creates or "
                "destroys scarcity). Caveat: term match is broad; the rate-of-change is the signal."
            ),
            recency=date(last, 12, 31), content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=POLICY_PILLAR_ID, source_id=source_id, provider="federal_register",
            external_id=term, label=f"{term} (Fed. Register)", metric="federal_register_docs",
            unit="docs/year", domain="policy",
        )
        series_id = _upsert_series(conn, series)
        store.bulk_upsert_observations(conn, [
            Observation(series_id=series_id, as_of=date(y, 12, 31), value=float(counts[y]),
                        unit="docs/year", uncertainty=max(1.0, sqrt(counts[y])))
            for y in ys
        ])
        n_series += 1
        n_obs += len(ys)
        log(f"  + {term:<22} {ys[0]}–{last}  {counts[ys[0]]}→{counts[last]} docs/yr")
    conn.commit()
    if own:
        conn.close()
    return {"series": n_series, "obs": n_obs}
