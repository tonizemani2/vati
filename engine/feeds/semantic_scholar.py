"""Semantic Scholar S2AG release manifest feed.

The full Semantic Scholar Academic Graph datasets are key-gated at the file-download endpoint. The
public release manifest is still keyless and small, so this collector lands what is honestly
available without a key: latest release date, dataset list, approximate record counts, and shard/file
counts. It deliberately does not pretend to ingest paper/author/citation rows.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

from engine import disk_guard

UA = "predictthefuture research (research@vaticinus.com)"
BASE = "https://api.semanticscholar.org/datasets/v1/release"
LATEST_URL = f"{BASE}/latest"
OUT_PATH = Path(__file__).resolve().parents[2] / "data" / "feeds" / "semantic_scholar.jsonl"


def _fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as resp:  # noqa: S310 official public API
        return json.loads(resp.read().decode("utf-8", "replace"))


def _parse_scaled_count(text: str, word: str) -> float | None:
    match = re.search(rf"(\d+(?:\.\d+)?)\s*([KMB])?\s+{re.escape(word)}\b", text, re.I)
    if not match:
        return None
    value = float(match.group(1))
    scale = (match.group(2) or "").upper()
    if scale == "K":
        value *= 1_000
    elif scale == "M":
        value *= 1_000_000
    elif scale == "B":
        value *= 1_000_000_000
    return value


def _parse_file_count(text: str) -> float | None:
    match = re.search(r"\bin\s+(\d+(?:\.\d+)?)\s+[\d.]+\s*(?:KB|MB|GB|TB)\s+files\b", text, re.I)
    if match:
        return float(match.group(1))
    match = re.search(r"\bin\s+(\d+(?:\.\d+)?)\s+files\b", text, re.I)
    return float(match.group(1)) if match else None


def _row(
    *,
    series_id: str,
    release_date: date,
    metric: str,
    value: float,
    unit: str,
    title: str,
) -> dict:
    return {
        "series_id": series_id,
        "date": release_date.isoformat(),
        "event_time": release_date.isoformat(),
        "published_at": release_date.isoformat(),
        "observed_at": release_date.isoformat(),
        "value": value,
        "unit": unit,
        "metric": metric,
        "title": title,
    }


def normalize_release(latest: dict, releases: list[str]) -> list[dict]:
    release_id = str(latest["release_id"])
    release_date = date.fromisoformat(release_id)
    datasets = latest.get("datasets") or []
    rows: list[dict] = [
        _row(
            series_id="semantic_scholar:release:known_releases",
            release_date=release_date,
            metric="s2ag_known_releases",
            value=float(len(releases)),
            unit="releases",
            title="Semantic Scholar S2AG - known release manifests",
        ),
        _row(
            series_id="semantic_scholar:release:dataset_count",
            release_date=release_date,
            metric="s2ag_dataset_count",
            value=float(len(datasets)),
            unit="datasets",
            title="Semantic Scholar S2AG - datasets in latest release",
        ),
    ]
    for dataset in datasets:
        name = str(dataset.get("name") or "").strip()
        if not name:
            continue
        description = str(dataset.get("description") or "")
        records = _parse_scaled_count(description, "records")
        files = _parse_file_count(description)
        if records is not None:
            rows.append(
                _row(
                    series_id=f"semantic_scholar:dataset:{name}:records",
                    release_date=release_date,
                    metric="s2ag_dataset_records_approx",
                    value=records,
                    unit="records",
                    title=f"Semantic Scholar S2AG - dataset {name} approximate records",
                )
            )
        if files is not None:
            rows.append(
                _row(
                    series_id=f"semantic_scholar:dataset:{name}:files",
                    release_date=release_date,
                    metric="s2ag_dataset_files",
                    value=files,
                    unit="files",
                    title=f"Semantic Scholar S2AG - dataset {name} shard files",
                )
            )
    rows.sort(key=lambda r: r["series_id"])
    return rows


def collect(*, log=print) -> list[dict]:
    stats = disk_guard.assert_safe(Path(__file__).resolve().parents[2], label="Semantic Scholar manifest collection")
    log(f"disk ok for Semantic Scholar manifest: free {stats['free_gb']:.1f}GiB, used {stats['used_pct']:.1f}%")
    latest = _fetch_json(LATEST_URL)
    releases = _fetch_json(BASE)
    if not isinstance(latest, dict) or "release_id" not in latest:
        raise RuntimeError("Semantic Scholar latest release manifest did not include release_id")
    if not isinstance(releases, list):
        releases = []
    rows = normalize_release(latest, [str(x) for x in releases])
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    log(
        f"wrote {len(rows)} Semantic Scholar release observations for "
        f"{latest['release_id']} -> {OUT_PATH}"
    )
    return rows


def probe_dataset_files(*, log=print) -> dict:
    """Probe a full dataset file endpoint without downloading files; returns the honest blocker."""
    url = f"{LATEST_URL}/dataset/papers"
    try:
        _fetch_json(url)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        out = {"ok": False, "http_status": exc.code, "detail": body}
        log(json.dumps(out, sort_keys=True))
        return out
    out = {"ok": True, "http_status": 200, "detail": "dataset endpoint reachable"}
    log(json.dumps(out, sort_keys=True))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe-dataset-files", action="store_true", help="probe key-gated file endpoint and exit")
    a = ap.parse_args()
    if a.probe_dataset_files:
        probe_dataset_files()
        return 0
    rows = collect()
    for row in rows[:6]:
        print("  " + json.dumps({k: row[k] for k in ("series_id", "date", "value", "unit", "title")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
