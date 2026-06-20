"""ONE CLICK: run every keyless collector → land it all into the DB.

This is the "all data, one command" entrypoint for the data layer. It runs each keyless feed
collector (engine/feeds/<name>.py, which self-runs via its __main__ and writes data/feeds/<name>.jsonl),
then calls engine.feeds.ingest to register sources + series and bulk-upsert observations into
data/foresight.db. Idempotent and $0 — re-running refreshes each jsonl and revises observations
in place.

COST GATE (CONSTITUTION). The metered/cloud collectors (google_patents, patentsview,
relianceonscience) are listed in GATED and are NOT run here: they scan paid quota or require
object-store/Athena work and need a label/terms + a nod. Run those explicitly with their own flags.
Everything in KEYLESS is free public data.

Run:
  uv run python -m engine.feeds.collect_all              # collect all keyless feeds, then ingest
  uv run python -m engine.feeds.collect_all --only openalex crossref   # subset
  uv run python -m engine.feeds.collect_all --ingest-only             # skip fetch, just land jsonl→DB
  uv run python -m engine.feeds.collect_all --skip-world-state         # ingest only; no derived facts
  uv run python -m engine.feeds.collect_all --audit                    # show feed files / staleness
  uv run python -m engine.feeds.collect_all --safe-local --stale-only  # laptop-safe, only missing/stale
  uv run python -m engine.feeds.collect_all --safe-local --dry-run     # show what would run, no spawns
  uv run python -m engine.feeds.collect_all --list                    # show the registry
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from engine import disk_guard

REPO = Path(__file__).resolve().parents[2]
FEEDS_DIR = REPO / "data" / "feeds"
MIB = 1024 ** 2
DEFAULT_MAX_FEED_MB = 100.0

# Keyless collectors that self-run with no args (their __main__ writes data/feeds/<name>.jsonl).
KEYLESS = [
    # research / frontier (LEADING)
    "openalex", "crossref", "biorxiv", "pubmed", "europe_pmc", "semantic_scholar", "epoch_ai", "nih_reporter", "nsf_awards", "cordis",
    # energy / supply / minerals
    "owid", "ember", "fred", "lbnl", "nasa_gistemp", "noaa_gml_greenhouse_gases", "noaa_enso", "noaa_climate_indices", "noaa_nsidc_sea_ice", "noaa_swpc_solar", "usgs_minerals", "faostat",
    # macro / capital
    "world_bank", "worldbank_wgi", "imf", "oecd", "eurostat", "ilo", "fred_financial", "ecb_fx", "sec_edgar", "usaspending_sam",
    # global capital + pricing (de-US-bias): BIS financial stats, World Bank capital flows
    "bis", "worldbank_capital",
    # trade / dependency
    "comtrade", "un_comtrade", "baci",
    # geopolitics / governance / conflict
    "gdelt", "eonet", "usgs_earthquakes", "gdacs_alerts", "vdem", "ucdp", "federal_register", "ofac_sdn", "eu_sanctions", "global_policy",
    # land / permits / physical constraints
    "land_permits_canada_iaac", "us_permitting_dashboard", "australia_epbc_referrals", "blm_mining_claims",
    "miningterminal_permits", "resourcecontracts", "land_matrix",
    # clinical / regulatory pipeline
    "clinicaltrials", "openfda_drugsfda",
    # markets / consensus (the GATE)
    "global_equities", "polymarket", "metaculus",
    # public attention / adoption proxy
    "wikipedia",
    # capability curves (L2) + real demand/adoption (L5) + supply elasticity (L4)
    "capability_curves", "adoption_curves", "tech_adoption", "supply_elasticity",
]

# Metered/cloud-gated — NOT run here; need --label/--terms + a cost nod.
GATED = ["google_patents", "patentsview", "relianceonscience"]
KNOWN_SLOW = {"baci", "crossref", "gdelt", "un_comtrade", "usgs_minerals", "world_bank",
              "global_policy", "worldbank_capital"}


def _line_count(name: str) -> int:
    p = FEEDS_DIR / f"{name}.jsonl"
    if not p.exists():
        return 0
    with p.open(encoding="utf-8") as fh:
        return sum(1 for _ in fh)


def _feed_file_status(name: str) -> dict:
    p = FEEDS_DIR / f"{name}.jsonl"
    status_path = FEEDS_DIR / f"{name}.status.json"
    diagnostic = None
    if status_path.exists():
        try:
            diagnostic = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            diagnostic = {"status_error": "unreadable status sidecar"}
    if not p.exists():
        return {
            "name": name,
            "exists": False,
            "rows": 0,
            "bytes": 0,
            "mtime": None,
            "age_hours": None,
            "known_slow": name in KNOWN_SLOW,
            "diagnostic": diagnostic,
        }
    st = p.stat()
    now = datetime.now(timezone.utc).timestamp()
    mtime = datetime.fromtimestamp(st.st_mtime, timezone.utc)
    return {
        "name": name,
        "exists": True,
        "rows": _line_count(name),
        "bytes": st.st_size,
        "mtime": mtime.isoformat(),
        "age_hours": round((now - st.st_mtime) / 3600, 2),
        "known_slow": name in KNOWN_SLOW,
        "diagnostic": diagnostic,
    }


def audit_feeds(names: list[str], *, stale_hours: float) -> list[dict]:
    rows = [_feed_file_status(n) for n in names]
    print("Feed file audit")
    print(f"stale threshold: {stale_hours:g}h")
    for r in rows:
        diag = r.get("diagnostic") or {}
        if _diagnostic_block_reason(diag):
            mark = "BLOCKED"
        elif diag:
            mark = "DIAG"
        elif not r["exists"]:
            mark = "MISSING"
        elif r["rows"] <= 0:
            mark = "EMPTY"
        elif r["age_hours"] is not None and r["age_hours"] > stale_hours:
            mark = "STALE"
        else:
            mark = "ok"
        slow = " slow" if r["known_slow"] else ""
        mtime = r["mtime"] or (diag.get("checked_at") if diag else None) or "n/a"
        suffix = f" reason={diag.get('reason')}" if diag and diag.get("reason") else ""
        print(
            f"  {mark:7s} {r['name']:16s} rows {r['rows']:7d} "
            f"bytes {r['bytes']:9d} age_h {str(r['age_hours']):>7s} {mtime}{slow}{suffix}"
        )
    return rows


def _diagnostic_block_reason(diag: dict | None) -> str | None:
    if not diag:
        return None
    if diag.get("needs_key"):
        return "diagnostic_needs_key"
    if diag.get("visibility_limited"):
        return "diagnostic_visibility_limited"
    if not diag.get("works", True) and int(diag.get("rows") or 0) == 0:
        return "diagnostic_unworkable_empty"
    return None


def select_collectors(
    requested: list[str] | None,
    *,
    skip_known_slow: bool = False,
    safe_local: bool = False,
    max_feed_mb: float = DEFAULT_MAX_FEED_MB,
    stale_only: bool = False,
    stale_hours: float = 24.0,
) -> tuple[list[str], list[dict]]:
    names = [n for n in (requested or KEYLESS) if n in KEYLESS]
    skipped: list[dict] = []
    if skip_known_slow or safe_local:
        keep: list[str] = []
        for n in names:
            if n in KNOWN_SLOW:
                skipped.append({"name": n, "reason": "known_slow_or_rate_limited"})
            else:
                keep.append(n)
        names = keep
    if safe_local:
        keep = []
        max_bytes = max_feed_mb * MIB
        for n in names:
            status = _feed_file_status(n)
            block_reason = _diagnostic_block_reason(status.get("diagnostic"))
            if block_reason:
                skipped.append({
                    "name": n,
                    "reason": block_reason,
                    "detail": (status.get("diagnostic") or {}).get("reason"),
                })
            elif status["exists"] and int(status["bytes"]) > max_bytes:
                skipped.append({
                    "name": n,
                    "reason": f"existing_feed_file>{max_feed_mb:g}MiB",
                    "bytes": int(status["bytes"]),
                })
            else:
                keep.append(n)
        names = keep
    if stale_only:
        keep = []
        for n in names:
            status = _feed_file_status(n)
            if (
                status["exists"]
                and int(status["rows"]) > 0
                and status["age_hours"] is not None
                and float(status["age_hours"]) <= stale_hours
            ):
                skipped.append({
                    "name": n,
                    "reason": f"fresh_feed_file<={stale_hours:g}h",
                    "age_hours": status["age_hours"],
                    "rows": status["rows"],
                })
            else:
                keep.append(n)
        names = keep
    return names, skipped


def run_collector(name: str, *, timeout: int = 600) -> dict:
    before = _line_count(name)
    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, "-m", f"engine.feeds.{name}"],
            cwd=REPO, capture_output=True, text=True, timeout=timeout,
        )
        ok = proc.returncode == 0
        err = "" if ok else (proc.stderr or proc.stdout or "")[-300:]
    except subprocess.TimeoutExpired:
        ok, err = False, f"timeout >{timeout}s"
    after = _line_count(name)
    return {"name": name, "ok": ok, "rows": after, "delta": after - before,
            "secs": round(time.time() - t0, 1), "err": err.strip()}


def print_dry_run(names: list[str], *, ingest_only: bool, skip_world_state: bool, subset_ingest: bool) -> None:
    print("dry run: no collectors, ingest, or world-state rebuild will be started.")
    if names:
        if ingest_only:
            print(f"would ingest existing feed files for {len(names)} selected feed(s): " + " ".join(names))
        else:
            print(f"would collect {len(names)} keyless feed(s): " + " ".join(names))
        scope = "selected feeds" if subset_ingest else "all present feeds"
        print(f"would ingest scope: {scope}")
    else:
        print("would collect: none")
        print("would ingest scope: none")
    refresh = bool(names) and not skip_world_state
    reason = " (no selected feeds)" if not names else ""
    print(f"would refresh world-state derived data: {'yes' if refresh else 'no'}{reason}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", help="run only these keyless collectors")
    ap.add_argument("--ingest-only", action="store_true", help="skip fetch; just land existing jsonl into the DB")
    ap.add_argument("--skip-world-state", action="store_true",
                    help="skip post-ingest entity autolink + derived world-state fact rebuild")
    ap.add_argument("--audit", action="store_true", help="show local feed file rows, age, and slow-feed flags")
    ap.add_argument("--dry-run", action="store_true",
                    help="print selected/skipped feeds and exit before spawning collectors or ingest")
    ap.add_argument("--stale-hours", type=float, default=24.0, help="stale threshold for --audit")
    ap.add_argument("--skip-known-slow", action="store_true",
                    help="skip feeds that commonly hit public rate/timeout walls")
    ap.add_argument("--safe-local", action="store_true",
                    help="laptop-safe mode: skip known slow feeds and oversized local feed refreshes")
    ap.add_argument("--stale-only", action="store_true",
                    help="collect only missing/empty/stale selected feeds; use --stale-hours as the cutoff")
    ap.add_argument("--max-feed-mb", type=float, default=DEFAULT_MAX_FEED_MB,
                    help="with --safe-local, skip feeds whose existing local file is larger than this")
    ap.add_argument("--list", action="store_true", help="print the registry and exit")
    ap.add_argument("--timeout", type=int, default=600, help="per-collector timeout (s)")
    ap.add_argument("--min-free-gb", type=float, default=disk_guard.DEFAULT_MIN_FREE_GB,
                    help="refuse write-heavy work below this free local disk threshold")
    ap.add_argument("--max-used-pct", type=float, default=disk_guard.DEFAULT_MAX_USED_PCT,
                    help="refuse write-heavy work above this local disk usage percentage")
    ap.add_argument("--allow-low-disk", action="store_true",
                    help="explicitly override disk guardrails for this run")
    a = ap.parse_args()

    if a.list:
        print(f"KEYLESS ({len(KEYLESS)}): " + " ".join(KEYLESS))
        print(f"GATED  ({len(GATED)}, metered, not auto-run): " + " ".join(GATED))
        return 0

    names, skipped = select_collectors(
        a.only,
        skip_known_slow=a.skip_known_slow,
        safe_local=a.safe_local,
        max_feed_mb=a.max_feed_mb,
        stale_only=a.stale_only,
        stale_hours=a.stale_hours,
    )
    requested_valid = [n for n in (a.only or []) if n in KEYLESS]
    if a.only and not requested_valid:
        print(f"none of {a.only} are keyless collectors; see --list")
        return 1
    if skipped:
        print("skipped collectors:")
        for row in skipped:
            detail = f" bytes={row['bytes']}" if "bytes" in row else ""
            print(f"  - {row['name']}: {row['reason']}{detail}")
    subset_ingest = bool(a.only or a.safe_local or a.skip_known_slow or a.stale_only)
    if not names:
        print("no collectors selected after safety filters.")
        if a.dry_run:
            print_dry_run(names, ingest_only=a.ingest_only, skip_world_state=a.skip_world_state, subset_ingest=subset_ingest)
        return 0 if (a.audit or a.dry_run or skipped) else 1
    if a.dry_run:
        print_dry_run(names, ingest_only=a.ingest_only, skip_world_state=a.skip_world_state, subset_ingest=subset_ingest)
        return 0
    if a.audit:
        audit_feeds(names, stale_hours=a.stale_hours)
        return 0

    def _guard(label: str) -> None:
        try:
            stats = disk_guard.assert_safe(
                REPO,
                min_free_gb=a.min_free_gb,
                max_used_pct=a.max_used_pct,
                label=label,
                allow_low_disk=a.allow_low_disk,
            )
        except disk_guard.DiskSpaceError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2) from None
        print(
            f"disk ok for {label}: free {stats['free_gb']:.1f}GiB, "
            f"used {stats['used_pct']:.1f}% "
            f"(floor {a.min_free_gb:.1f}GiB, cap {a.max_used_pct:.1f}%)",
            flush=True,
        )

    _guard("feed collection/ingest")

    if not a.ingest_only:
        print(f"== collecting {len(names)} keyless feeds (cost gate: $0) ==")
        results = []
        for n in names:
            print(f"  collecting {n}...", flush=True)
            results.append(run_collector(n, timeout=a.timeout))
        print(flush=True)
        ok = sum(r["ok"] for r in results)
        for r in sorted(results, key=lambda x: (x["ok"], -x["rows"])):
            mark = "ok " if r["ok"] else "FAIL"
            line = f"  {mark} {r['name']:16s} rows {r['rows']:6d} (Δ{r['delta']:+d})  {r['secs']:5.1f}s"
            print(line + (f"   {r['err']}" if not r["ok"] else ""), flush=True)
        print(f"\ncollected {ok}/{len(results)} feeds.", flush=True)

    # land everything present into the DB (ingest is idempotent + revises in place)
    _guard("feed ingest")
    print("\n== ingesting feeds → data/foresight.db ==", flush=True)
    ingest_names = names if subset_ingest else []
    ing = subprocess.run(
        [sys.executable, "-m", "engine.feeds.ingest", *ingest_names],
        cwd=REPO, text=True,
    )
    if ing.returncode != 0 or a.skip_world_state:
        return ing.returncode

    print("\n== refreshing world-state derived data ==")
    _guard("world-state entity autolink")
    link = subprocess.run([sys.executable, "-m", "engine.cli", "world-entity-autolink"], cwd=REPO, text=True)
    if link.returncode != 0:
        return link.returncode
    _guard("world-state observation fact backfill")
    facts = subprocess.run(
        [sys.executable, "-m", "engine.cli", "world-state-backfill-observations"],
        cwd=REPO, text=True,
    )
    return facts.returncode


if __name__ == "__main__":
    sys.exit(main())
