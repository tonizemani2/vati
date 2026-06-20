"""Google Patents Public Data (BigQuery) — the STRUCTURAL-CAP patent channel.

WHY THIS EXISTS (2026-06-13). The keyless US patent firehose is dead: PatentsView's
query API is retired and USPTO's Open Data Portal now gate-checks an API key (see
engine/feeds/patentsview.py for the live-probe evidence). The one route that keeps the
*structure* we need — disambiguated assignees + the citation graph + CPC + dates — is
`patents-public-data` on BigQuery. We drive it through the authenticated `bq` CLI (no
extra Python dep, per repo minimalism), not the google-cloud-bigquery library.

INTENDED SIGNAL (leak-class = LEADING / STRUCTURAL):
  • assignee concentration (HHI + top-N share) over a topic's grants = the STRUCTURAL CAP.
    A high-concentration, few-supplier field with multi-year expansion lead is where rent
    lands when the watched top layer scales (the /needle 'inelastic input' confirmation).
  • grant-count trend by year = is the boom forming (capability accelerating)?
  Every row carries the patent's REAL grant date; nothing is synthesised.

COST GATE (CONSTITUTION rule). BigQuery free tier = 1 TB scanned / month. The
`publications` table is huge, so EVERY query is dry-run first and the byte estimate is
printed; a run aborts if it would scan more than --max-gb (default 40) unless --yes is
passed. Free-tier queries cost $0 but burn quota, so we treat GB-scanned as the spend
and log it.

USAGE
  uv run python -m engine.feeds.google_patents \
      --label "cryo-infrastructure" \
      --terms "dilution refrigerat,cryogenic refrigerat,cryostat" \
      --since 2014 --dry-run
  # then drop --dry-run to execute (subject to the --max-gb gate)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from engine import cost, db, world_state

PUBLICATIONS = "`patents-public-data.patents.publications`"
OUT_PATH = Path(__file__).resolve().parents[2] / "data" / "feeds" / "google_patents.jsonl"
COST_LOG = Path(__file__).resolve().parents[2] / "data" / "_collect_logs" / "google_patents_cost.log"
DEFAULT_MAX_GB = 40.0


def _title_predicate(terms: list[str]) -> str:
    """EXISTS over title_localized matching any term (case-insensitive substring)."""
    likes = " OR ".join(
        f"LOWER(t.text) LIKE '%{t.strip().lower()}%'" for t in terms if t.strip()
    )
    return (
        "EXISTS (SELECT 1 FROM UNNEST(title_localized) t "
        f"WHERE {likes})"
    )


def _sql_concentration(terms: list[str], start: int, end: int, topn: int) -> str:
    pred = _title_predicate(terms)
    return f"""
WITH base AS (
  SELECT a.name AS assignee
  FROM {PUBLICATIONS}, UNNEST(assignee_harmonized) AS a
  WHERE grant_date BETWEEN {start} AND {end} AND {pred}
)
SELECT assignee, COUNT(*) AS n, SUM(COUNT(*)) OVER () AS total
FROM base
GROUP BY assignee
ORDER BY n DESC
LIMIT {topn}
""".strip()


def _sql_trend(terms: list[str], start: int, end: int) -> str:
    pred = _title_predicate(terms)
    return f"""
SELECT CAST(grant_date / 10000 AS INT64) AS year, COUNT(*) AS n
FROM {PUBLICATIONS}
WHERE grant_date BETWEEN {start} AND {end} AND {pred}
GROUP BY year
ORDER BY year
""".strip()


def _bq(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bq", "query", "--use_legacy_sql=false", *args],
        capture_output=True,
        text=True,
    )


def dry_run_gb(sql: str) -> float:
    """Return GB this query would scan (the cost-gate input). Raises on auth/SQL error."""
    proc = _bq(["--dry_run", sql])
    out = proc.stdout + proc.stderr
    m = re.search(r"process (\d+) bytes", out)
    if not m:
        raise RuntimeError(f"dry-run failed:\n{out.strip()}")
    return int(m.group(1)) / 1e9


def run_json(sql: str, max_rows: int = 1000) -> list[dict]:
    proc = _bq([f"--max_rows={max_rows}", "--format=json", sql])
    if proc.returncode != 0:
        raise RuntimeError(f"query failed:\n{(proc.stdout + proc.stderr).strip()}")
    return json.loads(proc.stdout or "[]")


def _hhi_and_share(rows: list[dict]) -> tuple[float, float, int]:
    """HHI (on the returned top-N — a lower bound) + top-5 share + total grants."""
    if not rows:
        return 0.0, 0.0, 0
    total = int(rows[0].get("total") or 0) or sum(int(r["n"]) for r in rows)
    hhi = sum((100.0 * int(r["n"]) / total) ** 2 for r in rows) if total else 0.0
    top5 = sum(int(r["n"]) for r in rows[:5])
    return round(hhi, 1), round(top5 / total, 3) if total else 0.0, total


def _log_cost(label: str, gb: float) -> None:
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with COST_LOG.open("a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()}\t{label}\t{gb:.2f} GB\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--label", required=True, help="thesis/topic name for the output rows")
    ap.add_argument("--terms", required=True, help="comma-separated title substrings to match")
    ap.add_argument("--since", type=int, default=2014, help="first grant year (inclusive)")
    ap.add_argument("--until", type=int, default=2026, help="last grant year (inclusive)")
    ap.add_argument("--topn", type=int, default=25, help="top-N assignees to return")
    ap.add_argument("--max-gb", type=float, default=DEFAULT_MAX_GB, help="abort if a query scans more")
    ap.add_argument("--dry-run", action="store_true", help="price only; do not execute or write")
    ap.add_argument("--yes", action="store_true", help="run even if estimate exceeds --max-gb")
    a = ap.parse_args()

    terms = [t for t in a.terms.split(",") if t.strip()]
    start, end = a.since * 10000 + 101, a.until * 10000 + 1231
    queries = {
        "assignee_concentration": _sql_concentration(terms, start, end, a.topn),
        "grant_trend": _sql_trend(terms, start, end),
    }

    # --- cost gate: price every query first ---
    total_gb = 0.0
    estimates: dict[str, float] = {}
    for kind, sql in queries.items():
        gb = dry_run_gb(sql)
        estimates[kind] = gb
        total_gb += gb
        print(f"[dry-run] {kind:24s} {gb:6.2f} GB")
    print(f"[dry-run] {'TOTAL':24s} {total_gb:6.2f} GB  (free tier 1000 GB/mo)")

    if a.dry_run:
        print("dry-run only; nothing executed.")
        return 0
    try:
        scan = world_state.guard_scan_bytes(
            "bigquery", int(total_gb * 1_000_000_000), max_gb=a.max_gb, allow_large=a.yes
        )
    except world_state.CostGuardError as e:
        print(f"ABORT: {e}. Re-run with --yes to override the scan cap.")
        return 1
    conn = db.connect()
    db.init_db(conn)
    try:
        ledger_id = cost.gate(
            conn,
            action=f"bigquery:google_patents:{a.label}",
            provider="bigquery",
            units=scan["gb_scanned"],
            est_cost_cents=scan["estimated_cost_cents"],
            funded_ref="google_patents_dry_run",
        )
        conn.commit()
    except cost.CostGateError as e:
        conn.commit()
        conn.close()
        print(f"ABORT: {e}")
        return 1

    # --- execute + emit ---
    fetched = datetime.now(timezone.utc).isoformat()
    window = f"{a.since}-{a.until}"
    rows_out: list[dict] = []

    conc = run_json(queries["assignee_concentration"], max_rows=a.topn)
    hhi, top5_share, total = _hhi_and_share(conc)
    for r in conc:
        rows_out.append({
            "label": a.label, "kind": "assignee_concentration",
            "assignee": r["assignee"], "n": int(r["n"]),
            "total_grants": total, "grant_window": window, "fetched_at": fetched,
        })

    trend = run_json(queries["grant_trend"], max_rows=100)
    for r in trend:
        rows_out.append({
            "label": a.label, "kind": "grant_trend",
            "year": int(r["year"]), "n": int(r["n"]),
            "grant_window": window, "fetched_at": fetched,
        })

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("a") as f:
        for row in rows_out:
            f.write(json.dumps(row) + "\n")
    _log_cost(a.label, total_gb)
    cost.record_actual(conn, ledger_id, scan["estimated_cost_cents"])
    conn.commit()
    conn.close()

    # --- summary ---
    print(f"\n{a.label}: {total} grants {window} · HHI(top{a.topn})={hhi} · top-5 share={top5_share:.0%}")
    print("  top assignees:")
    for r in conc[:10]:
        print(f"    {int(r['n']):4d}  {r['assignee']}")
    if trend:
        early = sum(int(r["n"]) for r in trend[: len(trend) // 2])
        late = sum(int(r["n"]) for r in trend[len(trend) // 2 :])
        arrow = "accelerating" if late > early else "flat/declining"
        print(f"  trend: {arrow} (first half {early} vs second half {late} grants)")
    print(f"  wrote {len(rows_out)} rows -> {OUT_PATH}  ({total_gb:.1f} GB scanned, logged)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
