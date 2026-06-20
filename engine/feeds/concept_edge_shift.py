"""Per-EDGE dependency shift — "is the binding constraint MIGRATING along this link, and is it early?"

WHY THIS EXISTS (2026-06-19, fork A — "the other snapshot gap"). concept_emergence restored time to
the NODES (which concepts are accelerating). But the dependency graph itself — graph_nodes/edges
chain='concept_flow', "A draws_on B" — is still a time-collapsed SNAPSHOT: it says A leans on B, never
whether that reliance is TIGHTENING (the crowd is concentrating onto B = the constraint is migrating
there) or LOOSENING (B is being designed around = rent leaving the link). A constraint that is moving
is exactly what we want to catch before it is priced; a static edge can't show motion.

THE SIGNAL (reuses engine/detector.py unchanged, same recipe as concept_emergence but on the EDGE):
  • Source: the SAME per-citing-year concept->concept aggregation the concept-flow graph build already
    runs (citation_edges ⋈ work_primary_concept on both ends), but we KEEP the per-year breakdown
    instead of summing it into one weight. Reuses the cached work_primary_concept Parquet — NO fresh
    639 GB scan; each year is one partition-pruned aggregation (~$0.01–0.02), so a full back-run is
    ~$0.15. Cost-gated + logged.
  • For each directed pair A->B we form A->B's SHARE of A's outbound cross-concept citations PER YEAR
    (the same quantity the static edge weight measures, but as a series), and run detect(log=True):
    surprise_sigma triggers (the edge tightened sharply), sustained marks persistence (not a blip),
    dissolving is the symmetric loosening signal.
  • Share (not raw count) normalizes away A's own growth and the trailing-year indexing deficit (both
    numerator and denominator scale together), so a rising share is real RE-concentration of A's
    dependence onto B.

LEAK DISCIPLINE: the trailing citing-year is dropped as provisional (citations to recent work are
still accruing); as_of = the last complete citing-year. Recomputable; the table is never edited.

USAGE
  uv run python -m engine.feeds.concept_edge_shift --build           # per-year pull (cached CTAS) + compute
  uv run python -m engine.feeds.concept_edge_shift --top 30          # print the live tightening edges
"""
from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict

from engine import db
from engine.detector import DEFAULT_K, detect
from engine.feeds import athena
from engine.feeds.openalex_load import MAX_CITING_YEAR, _fetch_all_rows, _log_cost
from engine.schemas import _now

# Enough early citing-history to fit a pre-shift trend before the held-out recent window. 2013 gives
# ~12 complete years (to 2024), the same depth concept_emergence fits its node trend on.
START_CITING_YEAR = 2013
MIN_TOTAL_N = 500        # full-window A->B citation floor (mirror the graph build's min_n: real links only)
MIN_LAST_SHARE = 0.02    # the edge must still carry materially in the last complete year
MIN_YEARS = 7            # detector needs a trend + a held-out window


def _spark(vals: list[float]) -> str:
    if not vals:
        return ""
    bars = "▁▂▃▄▅▆▇█"
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    return "".join(bars[min(7, int((v - lo) / rng * 7))] for v in vals)


def fetch_per_year(conn: sqlite3.Connection, *, start: int = START_CITING_YEAR,
                   log=print) -> tuple[dict, dict, dict]:
    """Run the per-citing-year concept->concept aggregation; return pair counts, src out-totals, names.

    One partition-pruned aggregation per year over the cached work_primary_concept Parquet (NOT a
    fresh works scan). Each year's scan is cost-logged to the ledger."""
    pair_year: dict[tuple[str, str], dict[int, int]] = defaultdict(dict)
    out_year: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    name: dict[str, str] = {}
    for yr in range(start, MAX_CITING_YEAR + 1):
        log(f"  [athena] concept->concept flow citing_year={yr} ...")
        res = athena.run_query(
            "SELECT a.concept_id, max(a.concept_name), b.concept_id, max(b.concept_name), count(*) AS n "
            "FROM citation_edges ce "
            "JOIN work_primary_concept a ON ce.citing = a.work_id "
            "JOIN work_primary_concept b ON ce.cited = b.work_id "
            f"WHERE ce.citing_year = {yr} AND a.concept_id <> b.concept_id "
            "GROUP BY a.concept_id, b.concept_id HAVING count(*) >= 30", log=log)
        _log_cost(conn, f"athena:edge_shift_{yr}", "athena", res["gb"])
        conn.commit()
        for a_id, a_name, b_id, b_name, n in _fetch_all_rows(res["id"]):
            n = int(n)
            a_id, b_id = a_id.split("/")[-1], b_id.split("/")[-1]
            name.setdefault(a_id, a_name)
            name.setdefault(b_id, b_name)
            pair_year[(a_id, b_id)][yr] = n
            out_year[a_id][yr] += n
    return pair_year, out_year, name


def compute(conn: sqlite3.Connection, *, start: int = START_CITING_YEAR, k: float = DEFAULT_K,
            log=print) -> dict:
    """Compute the per-edge share-shift verdict; (re)write the concept_edge_shift table."""
    pair_year, out_year, name = fetch_per_year(conn, start=start, log=log)
    years_seen = {y for d in out_year.values() for y in d}
    if not years_seen:
        log("  ! no per-year edge data returned — table not built")
        return {"edges": 0, "tightening": 0, "loosening": 0}
    last_complete = max(years_seen) - 1   # drop the trailing provisional citing-year
    log(f"  pulled {len(pair_year):,} raw pairs across {len(years_seen)} years; "
        f"last complete = {last_complete} (dropped provisional {max(years_seen)})")

    conn.execute("DELETE FROM concept_edge_shift")
    now_iso = _now().isoformat()
    wrote = tightening = loosening = 0
    for (a, b), per_yr in pair_year.items():
        years = sorted(y for y in per_yr if start <= y <= last_complete and out_year[a].get(y))
        if len(years) < MIN_YEARS:
            continue
        total_n = sum(per_yr[y] for y in years)
        if total_n < MIN_TOTAL_N:
            continue
        last_n = per_yr.get(last_complete, 0)
        last_share = last_n / out_year[a][last_complete] if out_year[a].get(last_complete) else 0.0
        if last_share < MIN_LAST_SHARE:
            continue
        series = [(float(y), 1e4 * per_yr[y] / out_year[a][y]) for y in years]  # share in bps
        det = detect(series, k=k, log=True)
        if det is None:
            continue
        spark = _spark([v for _, v in series])
        conn.execute(
            "INSERT OR REPLACE INTO concept_edge_shift (src_id,dst_id,src_name,dst_name,as_of,n_years,"
            "last_share,last_n,slope,surprise_sigma,sustained_sigma,fired,sustained,dissolving,spark,"
            "computed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (a, b, name.get(a, a), name.get(b, b), f"{last_complete}-12-31", det.n,
             round(last_share, 5), last_n, det.slope, det.surprise_sigma, det.sustained_sigma,
             1 if det.fired else 0, 1 if det.sustained else 0, 1 if det.dissolving else 0,
             spark, now_iso))
        wrote += 1
        tightening += det.fired and det.sustained
        loosening += det.dissolving
    conn.commit()
    log(f"wrote {wrote:,} edge-shift rows; {tightening:,} TIGHTENING (constraint migrating onto dst), "
        f"{loosening:,} LOOSENING (dependency decaying, rent leaving)")
    return {"edges": wrote, "tightening": tightening, "loosening": loosening}


def shift_map(conn: sqlite3.Connection) -> dict:
    """(src_name.lower(), dst_name.lower()) -> the edge-shift verdict, for the grounding pack tag.

    Returns {} if the table isn't built yet (degrade gracefully)."""
    try:
        rows = conn.execute(
            "SELECT src_name, dst_name, sustained_sigma, fired, sustained, dissolving, spark "
            "FROM concept_edge_shift").fetchall()
    except sqlite3.OperationalError:
        return {}
    return {(r["src_name"].lower(), r["dst_name"].lower()): dict(r) for r in rows}


def shift_tag(sh: dict | None) -> str:
    """Compact inline tag for one dependency edge: ↗tightening / ↘loosening / ''."""
    if not sh:
        return ""
    if sh["fired"] and sh["sustained"]:
        return f" ↗{sh['sustained_sigma']:.0f}σ"   # the constraint is migrating onto this input
    if sh["dissolving"]:
        return " ↘loosening"
    return ""


def top_tightening(conn: sqlite3.Connection, *, limit: int = 40) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM concept_edge_shift WHERE fired=1 AND sustained=1 AND dissolving=0 "
        "ORDER BY sustained_sigma DESC LIMIT ?", (limit,)).fetchall()


def main() -> int:
    ap = argparse.ArgumentParser(description="Per-edge dependency-shift signal (constraint migration).")
    ap.add_argument("--build", action="store_true", help="per-year Athena pull (cached CTAS) + compute")
    ap.add_argument("--start", type=int, default=START_CITING_YEAR, help="first citing-year to pull")
    ap.add_argument("--top", type=int, default=0, help="print the top-N tightening edges")
    args = ap.parse_args()

    conn = db.connect()
    db.init_db(conn)
    if args.build:
        compute(conn, start=args.start)
    if args.top:
        for r in top_tightening(conn, limit=args.top):
            print(f"  {r['sustained_sigma']:5.1f}σ̄  {r['src_name'][:32]:32s} ↗ {r['dst_name'][:32]:32s} "
                  f"{r['spark']}  ({r['last_share']:.1%} of outbound, {r['last_n']}/{r['as_of'][:4]})")
    if not args.build and not args.top:
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
