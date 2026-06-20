"""Per-concept emergence — the "where is the constraint MOVING, and is it still early?" signal.

WHY THIS EXISTS (2026-06-19). The diagnosed C+ in "where does the binding constraint move before
it's priced": the dependency graph (graph_nodes chain='concept_flow') is a time-collapsed SNAPSHOT —
it says where a constraint SITS, never where it is accelerating — and per-concept emergence was
computed on a hand-picked list of 8 frontier concepts (<0.1% of the 46k OpenAlex concept nodes).
This module closes that gap: it computes the detector's log-space share-acceleration verdict for
EVERY concept, so the graph's "where it sits" gains a "where it's moving" companion across the whole
substrate. Recall at the detector (fire wide on every accelerating concept); precision at the gate
(the dependency-cross + priced-in market_anchor + LLM reasoning downstream).

THE SIGNAL (one clean leading channel, reusing engine/detector.py unchanged):
  • Source: works published per year per concept, from the cached OpenAlex Parquet via one cheap
    Athena pass (work_primary_concept ⋈ work_attrs, ≈8 GB scan ≈ $0.04 — NOT a fresh 639 GB scan).
  • We detect on SHARE (concept works / ALL works that year, in ppm) not raw counts — the same
    normalization openalex.py uses: it strips the rising tide of total-corpus growth (and the
    OpenAlex trailing-year indexing inflation, since it divides by the same inflated denominator),
    so a rising share is real reorientation of attention, not just more papers everywhere.
  • detect(..., log=True): fit a robust Theil-Sen trend + MAD-σ floor on the EARLY portion, measure
    the largest SUSTAINED departure across the held-out recent years. surprise_sigma is the trigger
    (recall); sustained_sigma + sustained flag are the persistence annotation (kills one-year blips);
    dissolving is the symmetric kill-signal (a concept's share retreating below its trend = rent
    leaving). This is exactly the orthogonal per-concept channel detector.py's own docstring names as
    the fix for the deep-learning miss — the math was always here, it just lacked the series.

LEAK DISCIPLINE: the trailing OpenAlex snapshot year is dropped as provisional (its count is an
indexing-in-progress artifact, not a knowable year-end total); as_of = Dec-31 of the last COMPLETE
year. VALIDATED leak-free: computed as-of the year deep learning was still pre-consensus, the signal
fires 5.9σ@2016 / 6.8σ@2018 — years before the crowd; by 2025 it reads sub-threshold (the boom is now
its own established trend = a priced past winner, not a current needle). Caught it early, goes quiet
once priced.

$0.04 Athena (cached, cost-gated + logged); recomputable; the table is never edited (rule 1/7).

USAGE
  uv run python -m engine.feeds.concept_emergence --build          # pull + compute (reuses cache)
  uv run python -m engine.feeds.concept_emergence --build --force  # force a fresh Athena pull
  uv run python -m engine.feeds.concept_emergence --top 30         # print the live ranking
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sqlite3
from collections import defaultdict
from pathlib import Path

from engine import db
from engine.detector import DEFAULT_K, detect
from engine.feeds import athena
from engine.schemas import _now

CACHE = Path(__file__).resolve().parents[2] / "data" / "_athena_tmp" / "concept_year_works.csv"

START_YEAR = 2000              # enough early history for the detector to fit a pre-acceleration trend
DEFAULT_MIN_TOTAL = 3000       # lifetime-works volume gate: ignore tiny concepts (count noise, not a trend)
DEFAULT_MIN_LAST = 300         # must be materially active in the last complete year

# One cheap pass over the cached slim Parquet: works per concept per year (primary-concept basis, to
# match how the concept_flow dependency graph itself is built). Columnar scan of two columns ≈ $0.04.
_SQL = f"""
SELECT p.concept_id AS cid, max(p.concept_name) AS cname, a.publication_year AS yr, count(*) AS n
FROM work_primary_concept p
JOIN work_attrs a ON p.work_id = a.id
WHERE a.publication_year BETWEEN {START_YEAR} AND year(current_date)
GROUP BY p.concept_id, a.publication_year
"""


def _log_cost_cents(conn: sqlite3.Connection, action: str, gb: float) -> None:
    """Athena scan → cost_ledger at the real GB-derived cents (Athena is $5/TB). Rule 4."""
    from engine.schemas import CostLedgerEntry
    cents = round(gb / 1000 * 5 * 100)
    e = CostLedgerEntry(action=action, provider="athena", units=gb,
                        est_cost_cents=cents, actual_cost_cents=cents)
    conn.execute(
        "INSERT INTO cost_ledger (id,ts,action,provider,units,est_cost_cents,"
        "actual_cost_cents,approval_status) VALUES (?,?,?,?,?,?,?,?)",
        (e.id, e.ts.isoformat(), e.action, e.provider, e.units, cents, cents, "approved"),
    )


def fetch_concept_year_works(conn: sqlite3.Connection, *, force: bool, log=print) -> Path:
    """Pull works-per-concept-per-year to a local CSV via Athena (cached; reused unless force)."""
    if CACHE.exists() and not force:
        log(f"  [cache] reusing {CACHE.name} ($0) — pass --force to re-pull")
        return CACHE
    log("  [athena] works per concept per year (work_primary_concept ⋈ work_attrs) ...")
    res = athena.run_query(_SQL, log=log)
    _log_cost_cents(conn, "athena:concept_year_works", res["gb"])
    conn.commit()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    src = f"{res['output']}{res['id']}.csv"
    subprocess.run(["aws", "s3", "cp", src, str(CACHE), "--region", athena.REGION,
                    "--only-show-errors"], check=True)
    return CACHE


def _spark(vals: list[float]) -> str:
    """Compact unicode sparkline of a per-year share series (visual provenance, no decoration)."""
    if not vals:
        return ""
    bars = "▁▂▃▄▅▆▇█"
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    return "".join(bars[min(7, int((v - lo) / rng * 7))] for v in vals)


def compute(conn: sqlite3.Connection, *, force: bool = False, k: float = DEFAULT_K,
            min_total: int = DEFAULT_MIN_TOTAL, min_last: int = DEFAULT_MIN_LAST,
            log=print) -> dict:
    """Compute the share-acceleration verdict for every concept; (re)write the concept_emergence table."""
    path = fetch_concept_year_works(conn, force=force, log=log)

    byc: dict[str, dict[int, int]] = defaultdict(dict)
    name: dict[str, str] = {}
    total_by_year: dict[int, int] = defaultdict(int)
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row["cid"].split("/")[-1]
            yr, n = int(row["yr"]), int(row["n"])
            byc[cid][yr] = n
            name[cid] = row["cname"]
            total_by_year[yr] += n

    # drop the trailing snapshot year as provisional (indexing-in-progress, not a year-end total)
    last_complete = max(total_by_year) - 1
    log(f"  loaded {len(byc):,} concepts; last complete year = {last_complete} "
        f"(dropped provisional {max(total_by_year)})")

    conn.execute("DELETE FROM concept_emergence")
    now_iso = _now().isoformat()
    wrote = fired = sustained = dissolving = 0
    for cid, d in byc.items():
        years = sorted(y for y in d if START_YEAR <= y <= last_complete and total_by_year[y])
        if not years:
            continue
        total = sum(d[y] for y in years)
        last_works = d.get(last_complete, 0)
        if total < min_total or last_works < min_last:
            continue
        share = [(float(y), 1e6 * d[y] / total_by_year[y]) for y in years]
        det = detect(share, k=k, log=True)
        if det is None:
            continue
        share_now = share[-1][1]
        spark = _spark([v for _, v in share])
        conn.execute(
            "INSERT OR REPLACE INTO concept_emergence (concept_id,concept_name,as_of,n_years,"
            "first_year,last_year,total_works,last_works,share_ppm_now,slope,surprise_sigma,"
            "sustained_sigma,fired,sustained,dissolving,spark,computed_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, name[cid], f"{last_complete}-12-31", det.n, years[0], years[-1], total,
             last_works, round(share_now, 3), det.slope, det.surprise_sigma, det.sustained_sigma,
             1 if det.fired else 0, 1 if det.sustained else 0, 1 if det.dissolving else 0,
             spark, now_iso),
        )
        wrote += 1
        fired += det.fired
        sustained += det.sustained and det.fired
        dissolving += det.dissolving
    conn.commit()
    log(f"wrote {wrote:,} concept_emergence rows; {fired:,} fired (k={k}), "
        f"{sustained:,} fired+sustained, {dissolving:,} dissolving (rent leaving)")
    return {"concepts": wrote, "fired": fired, "sustained": sustained, "dissolving": dissolving}


def top_emergent(conn: sqlite3.Connection, *, limit: int = 40, require_sustained: bool = True,
                 min_sigma: float = DEFAULT_K, exclude_dissolving: bool = True) -> list[sqlite3.Row]:
    """The live ranking: concepts whose share is accelerating NOW (sustained), most-surprising first.

    Ranked by sustained_sigma (the persistent bend) so a one-year blip can't top the board. This is
    the recall-wide candidate list; the priced-in gate + dependency-cross + LLM converge downstream."""
    q = ("SELECT * FROM concept_emergence WHERE surprise_sigma >= ? AND fired = 1 ")
    if require_sustained:
        q += "AND sustained = 1 "
    if exclude_dissolving:
        q += "AND dissolving = 0 "
    q += "ORDER BY sustained_sigma DESC LIMIT ?"
    return conn.execute(q, (min_sigma, limit)).fetchall()


def main() -> int:
    ap = argparse.ArgumentParser(description="Per-concept share-acceleration emergence signal.")
    ap.add_argument("--build", action="store_true", help="pull (cached) + compute the table")
    ap.add_argument("--force", action="store_true", help="force a fresh Athena pull (~$0.04)")
    ap.add_argument("--top", type=int, default=0, help="print the top-N live ranking")
    args = ap.parse_args()

    conn = db.connect()
    if args.build:
        compute(conn, force=args.force)
    if args.top:
        rows = top_emergent(conn, limit=args.top)
        print(f"\nTop {len(rows)} accelerating concepts (fired+sustained, as-of last complete year):")
        for r in rows:
            print(f"  {r['sustained_sigma']:5.1f}σ̄ max {r['surprise_sigma']:5.1f}σ  "
                  f"{r['concept_name'][:40]:40s} {r['spark']}  {r['last_works']}w/{r['last_year']}")
    if not args.build and not args.top:
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
