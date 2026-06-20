#!/usr/bin/env python3
"""GDELT v1 daily event aggregator — full history 2015-01-01 to present.

Streams each day's zip, aggregates in memory, emits JSONL shards to /tmp/gdelt_stage/,
uploads monthly gzip shards to S3, then deletes local files. Never accumulates raw events.

Column indices (0-based, tab-separated, no header):
  0  GlobalEventID
  1  SQLDATE (YYYYMMDD of event, may differ from file date)
  26 EventCode
  27 EventBaseCode
  28 EventRootCode
  29 QuadClass (1=VerbalCoop 2=MatCoop 3=VerbalConflict 4=MatConflict)
  30 GoldsteinScale
  31 NumMentions
  32 NumSources
  33 NumArticles
  34 AvgTone
  51 ActionGeo_CountryCode
  56 DATEADDED (YYYYMMDD the article was added to GDELT — the file date)
"""

from __future__ import annotations

import gzip
import io
import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("gdelt")

# ─── Config ─────────────────────────────────────────────────────────────────
STAGE_DIR = Path("/tmp/gdelt_stage")
S3_PREFIX = "s3://mining-terminal-research-405844305300-us-east-1/predict/events/gdelt"
START = date(2015, 1, 1)
END = date.today()
STAGE_LIMIT_BYTES = 1_400_000_000  # 1.4 GB safety limit

# GDELT v1 daily zip URL pattern
GDELT_URL = "http://data.gdeltproject.org/events/{date}.export.CSV.zip"

# Column indices
COL_SQLDATE = 1
COL_EVENTROOT = 28
COL_QUADCLASS = 29
COL_GOLDSTEIN = 30
COL_MENTIONS = 31
COL_AVGTONE = 34
COL_COUNTRY = 51

# ─── Helpers ────────────────────────────────────────────────────────────────

def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def stage_size() -> int:
    total = 0
    for p in STAGE_DIR.glob("**/*"):
        if p.is_file():
            total += p.stat().st_size
    return total


def fetch_day_zip(day: date, proxy_url: str | None = None) -> bytes | None:
    """Download the GDELT v1 zip for `day`. Returns raw bytes or None on permanent 404."""
    url = GDELT_URL.format(date=day.strftime("%Y%m%d"))
    req = urllib.request.Request(url, headers={"User-Agent": "gdelt-research/1.0"})
    handlers: list[Any] = []
    if proxy_url:
        handlers.append(urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url}))
    opener = urllib.request.build_opener(*handlers)

    for attempt in range(4):
        try:
            with opener.open(req, timeout=90) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None  # day doesn't exist (future or gap)
            log.warning("HTTP %d on %s attempt %d", e.code, day, attempt + 1)
            time.sleep(5 * (attempt + 1))
        except Exception as exc:
            log.warning("Fetch error %s on %s attempt %d", exc, day, attempt + 1)
            time.sleep(5 * (attempt + 1))
    return None  # exhausted retries


def aggregate_day(raw_zip: bytes, file_date: date) -> dict:
    """Stream-aggregate a GDELT zip into daily summary dicts.

    Returns:
      {
        "by_country_code": {(country, event_root_code): {n,tone_sum,goldstein_sum,mentions}},
        "global_by_quad": {quadclass: {n,tone_sum,goldstein_sum,mentions}},
        "total": {n,tone_sum,goldstein_sum,mentions}
      }
    """
    by_cc: dict[tuple, dict] = defaultdict(lambda: {"n": 0, "tone_sum": 0.0, "goldstein_sum": 0.0, "mentions": 0})
    by_quad: dict[str, dict] = defaultdict(lambda: {"n": 0, "tone_sum": 0.0, "goldstein_sum": 0.0, "mentions": 0})
    total: dict = {"n": 0, "tone_sum": 0.0, "goldstein_sum": 0.0, "mentions": 0}

    try:
        zf = zipfile.ZipFile(io.BytesIO(raw_zip))
    except zipfile.BadZipFile:
        log.warning("Bad zip for %s", file_date)
        return {"by_country_code": {}, "by_quad": {}, "total": total}

    fname = zf.namelist()[0]
    with zf.open(fname) as f:
        for raw_line in f:
            try:
                line = raw_line.decode("latin-1").rstrip("\n").split("\t")
                if len(line) < 57:
                    continue

                country = line[COL_COUNTRY].strip()
                event_root = line[COL_EVENTROOT].strip()
                quad = line[COL_QUADCLASS].strip()

                try:
                    goldstein = float(line[COL_GOLDSTEIN]) if line[COL_GOLDSTEIN] else 0.0
                except ValueError:
                    goldstein = 0.0
                try:
                    tone = float(line[COL_AVGTONE]) if line[COL_AVGTONE] else 0.0
                except ValueError:
                    tone = 0.0
                try:
                    mentions = int(line[COL_MENTIONS]) if line[COL_MENTIONS] else 0
                except ValueError:
                    mentions = 0

                # country × event_root_code bucket
                key = (country, event_root)
                bcc = by_cc[key]
                bcc["n"] += 1
                bcc["tone_sum"] += tone
                bcc["goldstein_sum"] += goldstein
                bcc["mentions"] += mentions

                # global by quad
                bq = by_quad[quad]
                bq["n"] += 1
                bq["tone_sum"] += tone
                bq["goldstein_sum"] += goldstein
                bq["mentions"] += mentions

                # global total
                total["n"] += 1
                total["tone_sum"] += tone
                total["goldstein_sum"] += goldstein
                total["mentions"] += mentions

            except Exception:
                continue  # skip malformed rows silently

    return {"by_country_code": dict(by_cc), "by_quad": dict(by_quad), "total": total}


def emit_records(day: date, agg: dict) -> list[dict]:
    """Convert aggregation dict into a list of JSONL-ready record dicts."""
    date_str = day.isoformat()
    records = []

    # Per-country × event_root_code rows
    for (country, event_root), v in agg["by_country_code"].items():
        n = v["n"]
        if n == 0:
            continue
        records.append({
            "date": date_str,
            "country": country,
            "event_root_code": event_root,
            "n_events": n,
            "avg_tone": round(v["tone_sum"] / n, 4),
            "avg_goldstein": round(v["goldstein_sum"] / n, 4),
            "sum_mentions": v["mentions"],
        })

    # Global daily panel rows (one per QuadClass)
    for quad, v in agg["by_quad"].items():
        n = v["n"]
        if n == 0:
            continue
        records.append({
            "date": date_str,
            "country": "_GLOBAL_",
            "event_root_code": f"QUAD{quad}",
            "n_events": n,
            "avg_tone": round(v["tone_sum"] / n, 4),
            "avg_goldstein": round(v["goldstein_sum"] / n, 4),
            "sum_mentions": v["mentions"],
        })

    # Global daily total
    v = agg["total"]
    if v["n"] > 0:
        n = v["n"]
        records.append({
            "date": date_str,
            "country": "_GLOBAL_",
            "event_root_code": "ALL",
            "n_events": n,
            "avg_tone": round(v["tone_sum"] / n, 4),
            "avg_goldstein": round(v["goldstein_sum"] / n, 4),
            "sum_mentions": v["mentions"],
        })

    return records


def shard_path(day: date) -> Path:
    """Monthly gzip JSONL shard path under STAGE_DIR."""
    return STAGE_DIR / f"gdelt_{day.year}{day.month:02d}.jsonl.gz"


def flush_shard_to_s3(shard_file: Path) -> bool:
    """Upload one shard to S3 and delete locally. Returns True on success."""
    s3_key = f"{S3_PREFIX}/{shard_file.name}"
    result = subprocess.run(
        ["aws", "s3", "cp", str(shard_file), s3_key],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        log.info("Uploaded %s → %s", shard_file.name, s3_key)
        shard_file.unlink()
        return True
    else:
        log.error("S3 upload failed for %s: %s", shard_file.name, result.stderr)
        return False


def write_record_batch(day: date, records: list[dict]) -> None:
    """Append records to the appropriate monthly shard (gzip JSONL)."""
    shard = shard_path(day)
    with gzip.open(shard, "at", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")


def get_proxy_url() -> str | None:
    """Try to get floxy proxy URL; fall back to None (direct)."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from engine.adapters import proxy as proxy_mod
        return proxy_mod.proxy_url("floxy")
    except Exception as e:
        log.info("Proxy unavailable (%s), using direct", e)
        return None


def main():
    STAGE_DIR.mkdir(parents=True, exist_ok=True)

    proxy_url = get_proxy_url()
    if proxy_url:
        log.info("Using floxy proxy")
    else:
        log.info("Direct fetch (no proxy)")

    all_days = list(daterange(START, END))
    total_days = len(all_days)
    log.info("Planning %d days: %s → %s", total_days, START, END)

    missing_days: list[str] = []
    processed_days: list[str] = []
    countries_seen: set[str] = set()
    codes_seen: set[str] = set()
    total_rows = 0

    current_month = (START.year, START.month)
    uploaded_shards: list[str] = []

    for i, day in enumerate(all_days):
        month = (day.year, day.month)

        # When month rolls over, flush previous month's shard
        if month != current_month:
            prev_shard = STAGE_DIR / f"gdelt_{current_month[0]}{current_month[1]:02d}.jsonl.gz"
            if prev_shard.exists():
                if flush_shard_to_s3(prev_shard):
                    uploaded_shards.append(prev_shard.name)
            current_month = month

        # Safety: check stage dir size
        sz = stage_size()
        if sz > STAGE_LIMIT_BYTES:
            log.warning("Stage dir at %.1f MB, flushing all shards", sz / 1e6)
            for sf in sorted(STAGE_DIR.glob("*.jsonl.gz")):
                if flush_shard_to_s3(sf):
                    uploaded_shards.append(sf.name)

        log.info("[%d/%d] Fetching %s...", i + 1, total_days, day)
        raw = fetch_day_zip(day, proxy_url)

        if raw is None:
            log.warning("No data for %s (404 or fetch failure)", day)
            missing_days.append(day.isoformat())
            # Still emit a placeholder so the series is continuous
            placeholder = [{
                "date": day.isoformat(),
                "country": "_MISSING_",
                "event_root_code": "MISSING",
                "n_events": 0,
                "avg_tone": None,
                "avg_goldstein": None,
                "sum_mentions": 0,
            }]
            write_record_batch(day, placeholder)
            continue

        agg = aggregate_day(raw, day)
        records = emit_records(day, agg)

        # Track metadata
        for rec in records:
            if rec["country"] not in ("_GLOBAL_", "_MISSING_"):
                countries_seen.add(rec["country"])
            if not rec["event_root_code"].startswith(("QUAD", "ALL", "MISS")):
                codes_seen.add(rec["event_root_code"])
        total_rows += len(records)

        write_record_batch(day, records)
        processed_days.append(day.isoformat())
        log.info("  → %d rows (stage %.1f MB)", len(records), stage_size() / 1e6)

        # Pace: GDELT is public but polite
        time.sleep(0.3)

    # Flush final shard
    for sf in sorted(STAGE_DIR.glob("*.jsonl.gz")):
        if flush_shard_to_s3(sf):
            uploaded_shards.append(sf.name)

    # Write manifest
    manifest = {
        "date_range": [START.isoformat(), END.isoformat()],
        "n_days_planned": total_days,
        "n_days_processed": len(processed_days),
        "n_days_missing": len(missing_days),
        "missing_days": missing_days,
        "n_countries": len(countries_seen),
        "n_event_root_codes": len(codes_seen),
        "total_aggregate_rows": total_rows,
        "uploaded_shards": uploaded_shards,
        "s3_prefix": S3_PREFIX,
        "generated_at": date.today().isoformat(),
    }
    manifest_path = STAGE_DIR / "_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    s3_manifest = f"{S3_PREFIX}/_manifest.json"
    subprocess.run(["aws", "s3", "cp", str(manifest_path), s3_manifest], check=True)
    log.info("Manifest uploaded to %s", s3_manifest)

    print("\n=== GDELT COLLECTION COMPLETE ===")
    print(f"Date range:       {START} → {END}")
    print(f"Days planned:     {total_days}")
    print(f"Days processed:   {len(processed_days)}")
    print(f"Days missing:     {len(missing_days)}")
    print(f"Countries seen:   {len(countries_seen)}")
    print(f"Event root codes: {len(codes_seen)}")
    print(f"Total agg rows:   {total_rows:,}")
    print(f"Shards uploaded:  {len(uploaded_shards)}")
    print(f"S3 prefix:        {S3_PREFIX}")
    if missing_days[:10]:
        print(f"First missing:    {missing_days[:10]}")


if __name__ == "__main__":
    main()
