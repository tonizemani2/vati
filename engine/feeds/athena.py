"""Thin Athena runner — serverless SQL over the S3 data lake, all-AWS, no new deps.

Drives Athena through the `aws` CLI (subprocess, matching google_patents.py's shell-out style; no
boto3). Used to parse the OpenAlex snapshot that lives as gz-JSON in s3 (engine/feeds/openalex_snapshot
froze it) into derived Parquet + DB-bound aggregates, without ever leaving AWS.

COST GATE (CONSTITUTION): Athena bills $5 / TB scanned. Every run prints DataScannedInBytes and
appends it to data/_collect_logs/athena_cost.log. A full pass over works/ (~639 GB) ≈ $3.2; declare
only the columns you need so the JSON SerDe scans less.

USAGE
  uv run python -m engine.feeds.athena "SELECT 1"                       # ad-hoc, prints rows
  uv run python -m engine.feeds.athena --file ddl.sql                   # run SQL from a file
  from engine.feeds.athena import run_query                             # importable
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BUCKET = "vaticinus-datalake-405844305300-us-east-1"
DATABASE = "vaticinus"
OUTPUT = f"s3://{BUCKET}/athena-results/"
REGION = "us-east-1"
COST_LOG = Path(__file__).resolve().parents[2] / "data" / "_collect_logs" / "athena_cost.log"


def _aws(args: list[str]) -> dict:
    proc = subprocess.run(["aws", *args, "--region", REGION, "--output", "json"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"aws {' '.join(args[:2])} failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout or "{}")


def run_query(sql: str, *, database: str = DATABASE, log=print) -> dict:
    """Start a query, poll to completion, log bytes scanned. Returns the execution dict."""
    start = _aws(["athena", "start-query-execution",
                  "--query-string", sql,
                  "--query-execution-context", f"Database={database}",
                  "--result-configuration", f"OutputLocation={OUTPUT}"])
    qid = start["QueryExecutionId"]
    while True:
        ex = _aws(["athena", "get-query-execution", "--query-execution-id", qid])["QueryExecution"]
        state = ex["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(2)
    stats = ex.get("Statistics", {})
    gb = stats.get("DataScannedInBytes", 0) / 1e9
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with COST_LOG.open("a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()}\t{state}\t{gb:.2f} GB\t{sql[:60].strip()}\n")
    if state != "SUCCEEDED":
        reason = ex["Status"].get("StateChangeReason", "")
        raise RuntimeError(f"query {state}: {reason}\nSQL: {sql[:200]}")
    log(f"  [athena] SUCCEEDED  scanned {gb:.2f} GB (~${gb/1000*5:.3f})  id={qid}")
    return {"id": qid, "gb": gb, "output": OUTPUT}


def fetch_rows(qid: str, max_rows: int = 100) -> list[list[str]]:
    """Pull result rows for a small query (skips the header row)."""
    res = _aws(["athena", "get-query-results", "--query-execution-id", qid, "--max-items", str(max_rows)])
    rows = []
    for r in res.get("ResultSet", {}).get("Rows", [])[1:]:
        rows.append([c.get("VarCharValue", "") for c in r.get("Data", [])])
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sql", nargs="?", help="SQL string")
    ap.add_argument("--file", help="read SQL from a file")
    ap.add_argument("--database", default=DATABASE)
    a = ap.parse_args()
    sql = Path(a.file).read_text() if a.file else a.sql
    if not sql:
        print("no SQL given")
        return 1
    r = run_query(sql, database=a.database)
    rows = fetch_rows(r["id"])
    for row in rows[:50]:
        print("  " + " | ".join(row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
