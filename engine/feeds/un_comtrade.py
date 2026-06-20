"""UN Comtrade US dependency metrics, feed-backed.

This mirrors the DB-direct dependency pillar as a generic feed so the existing
provider="un_comtrade" series can move onto the rawstore-preserved path. It
emits the same external_id and metric keys as engine.pillars.dependency.
"""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable

from engine.pillars import dependency

OUT_PATH = Path(__file__).resolve().parents[2] / "data" / "feeds" / "un_comtrade.jsonl"
MIN_REFRESH_FRACTION = 0.8
PUBLISHED_LAG_MONTH = 12
PUBLISHED_LAG_DAY = 31


def _row_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("series_id") or ""), str(row.get("date") or "")


def _existing_rows() -> list[dict[str, Any]]:
    if not OUT_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    with OUT_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if _row_key(row) != ("", ""):
                rows.append(row)
    return rows


def _merge_rows(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {_row_key(row): row for row in old if _row_key(row) != ("", "")}
    for row in new:
        key = _row_key(row)
        if key != ("", ""):
            merged[key] = row
    return sorted(merged.values(), key=lambda row: (_row_key(row)[0], _row_key(row)[1]))


def _write_rows(rows: list[dict[str, Any]]) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_PATH.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(OUT_PATH)


def metric_rows(spec: dict[str, Any], stats_by_year: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for metric_suffix, label_tail, unit, key, uncertainty_of in (
        ("import_value", "value", "USD (current)", "value", lambda v: 0.03 * v),
        ("import_hhi", "partner concentration", "HHI (0-1)", "hhi", lambda _v: 0.01),
        ("net_import_reliance", "net-import-reliance (proxy)", "ratio (net M / M)", "nir", lambda _v: 0.03),
    ):
        for year in sorted(stats_by_year):
            value = float(stats_by_year[year][key])
            observed = date(year, 12, 31)
            published = date(year + 1, PUBLISHED_LAG_MONTH, PUBLISHED_LAG_DAY)
            rows.append({
                "series_id": f"{spec['cmd']}_{metric_suffix}",
                "date": observed.isoformat(),
                "as_of": observed.isoformat(),
                "event_time": observed.isoformat(),
                "observed_at": observed.isoformat(),
                "published_at": published.isoformat(),
                "value": value,
                "unit": unit,
                "uncertainty": float(uncertainty_of(value)),
                "metric": f"{spec['key']}_{metric_suffix}",
                "domain": spec["domain"],
                "title": f"{spec['label']} — {label_tail}",
                "cmd": spec["cmd"],
                "commodity": spec["label"],
                "top_supplier_code": stats_by_year[year].get("top_code"),
                "top_supplier_share": stats_by_year[year].get("top_share"),
                "partner_count": stats_by_year[year].get("n"),
            })
    return rows


def collect(
    *,
    log=print,
    year_stats: Callable[[str, int], dict[str, Any] | None] = dependency._year_stats,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in dependency.COMMODITIES:
        stats: dict[int, dict[str, Any]] = {}
        for year in range(dependency.WINDOW_START, dependency.CUTOFF_YEAR + 1):
            point = year_stats(spec["cmd"], year)
            if point:
                stats[year] = point
            time.sleep(0.15)
        if len(stats) < dependency.MIN_YEARS:
            log(f"  - skip {spec['label']} (only {len(stats)} usable years)")
            continue
        emitted = metric_rows(spec, stats)
        rows.extend(emitted)
        years = sorted(stats)
        log(f"  + HS{spec['cmd']:<7s} {spec['key']:<18s} {years[0]}-{years[-1]}  {len(emitted)} obs")

    existing = _existing_rows()
    if not rows:
        if existing:
            log(f"\nno observations fetched; preserved existing {len(existing)} rows at {OUT_PATH}")
        return []
    if existing and len(rows) < int(MIN_REFRESH_FRACTION * len(existing)):
        log(
            f"\npartial un_comtrade refresh fetched {len(rows)} rows < "
            f"{MIN_REFRESH_FRACTION:.0%} of existing {len(existing)}; preserved {OUT_PATH}"
        )
        return []
    merged = _merge_rows(existing, rows)
    _write_rows(merged)
    retained = len(merged) - len(rows)
    suffix = f" ({retained} prior rows retained)" if retained else ""
    log(f"\nwrote {len(merged)} observations -> {OUT_PATH}{suffix}")
    return merged


if __name__ == "__main__":
    print("UN Comtrade US dependency metrics (keyless preview):")
    observations = collect()
    print(f"\njsonl rows: {len(observations)}")
