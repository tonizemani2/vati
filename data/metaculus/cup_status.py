"""Read-only Metaculus Cup operator status.

This command is intentionally boring: GET live open questions, read local logs, read cron metadata, and
print the state. It never forecasts, submits, writes files, or calls an LLM.

Usage:
  python data/metaculus/cup_status.py
  python data/metaculus/cup_status.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.metaculus import api

SLUG = "metaculus-cup-summer-2026"
ROOT = Path(__file__).resolve().parents[2]
META_DIR = ROOT / "data" / "metaculus"
FORECAST_LOGS = (
    META_DIR / f"forecasts_{SLUG}.jsonl",
    META_DIR / f"nonbinary_{SLUG}.jsonl",
)
CRON_LOGS = (
    Path("/tmp/cup_cron.log"),
    Path("/tmp/mtc_scores.log"),
)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _records() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in FORECAST_LOGS:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            rec["_log"] = str(path.relative_to(ROOT))
            out.append(rec)
    return out


def _latest_by_post(records: list[dict[str, Any]], *, submitted_only: bool) -> dict[int, dict[str, Any]]:
    latest: dict[int, dict[str, Any]] = {}
    for rec in records:
        if submitted_only and not rec.get("submitted"):
            continue
        pid = rec.get("post_id")
        if pid is None:
            continue
        ts = _parse_time(rec.get("at"))
        old = latest.get(pid)
        old_ts = _parse_time(old.get("at")) if old else None
        if old is None or (ts and (old_ts is None or ts > old_ts)):
            latest[int(pid)] = rec
    return latest


def _tail_status(path: Path, n: int = 80) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "errors": []}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    needles = ("can't open", "traceback", "error", "failed", "http 4", "http 5", "rate-limited")
    errors = [ln for ln in lines if any(x in ln.lower() for x in needles)]
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    return {"path": str(path), "exists": True, "mtime": mtime, "errors": errors[-8:]}


def _crontab() -> list[str]:
    try:
        out = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
    except Exception as exc:  # noqa: BLE001 - read-only status should degrade, not crash.
        return [f"crontab read failed: {exc}"]
    if out.returncode != 0:
        return [out.stderr.strip() or "crontab read failed"]
    return [ln for ln in out.stdout.splitlines() if "metaculus" in ln.lower() or "cup_" in ln.lower()]


def build_status() -> dict[str, Any]:
    posts = api.list_open_questions(SLUG, forecast_type="binary,multiple_choice,numeric,discrete,date")
    posts.sort(key=lambda p: (p.get("question") or {}).get("scheduled_close_time") or "9999")
    records = _records()
    latest_submitted = _latest_by_post(records, submitted_only=True)
    latest_any = _latest_by_post(records, submitted_only=False)
    open_ids = [int(p.get("id")) for p in posts if p.get("id") is not None]

    missing_submitted = [pid for pid in open_ids if pid not in latest_submitted]
    latest_ts = None
    for rec in latest_submitted.values():
        ts = _parse_time(rec.get("at"))
        if ts and (latest_ts is None or ts > latest_ts):
            latest_ts = ts

    type_counts = Counter((p.get("question") or {}).get("type") or "unknown" for p in posts)
    next_closes = []
    for p in posts[:10]:
        q = p.get("question") or {}
        pid = int(p.get("id"))
        rec = latest_submitted.get(pid) or latest_any.get(pid) or {}
        next_closes.append({
            "close": q.get("scheduled_close_time") or p.get("scheduled_close_time"),
            "type": q.get("type"),
            "post_id": pid,
            "question_id": q.get("id"),
            "title": p.get("title") or q.get("title") or "",
            "latest_at": rec.get("at"),
            "latest_submitted": rec.get("submitted"),
            "latest_author": rec.get("author"),
            "latest_provider": rec.get("provider"),
        })

    cron_lines = _crontab()
    runtime_cron = any(".forecastbench-runtime" in ln for ln in cron_lines)
    by_type_missing = defaultdict(int)
    for p in posts:
        pid = int(p.get("id"))
        if pid in missing_submitted:
            by_type_missing[(p.get("question") or {}).get("type") or "unknown"] += 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tournament": SLUG,
        "open_count": len(posts),
        "type_counts": dict(sorted(type_counts.items())),
        "coverage": {
            "with_submitted_local_log": len(open_ids) - len(missing_submitted),
            "missing_submitted_local_log": len(missing_submitted),
            "missing_by_type": dict(sorted(by_type_missing.items())),
            "latest_submitted_at": latest_ts.isoformat() if latest_ts else None,
        },
        "provider_cost_mode": {
            "default_provider": os.getenv("CUP_PROVIDER", "openrouter_free"),
            "paid_provider_allowed": os.getenv("CUP_ALLOW_PAID_PROVIDER") == "1",
            "opus_allowed": False,
        },
        "cron": {
            "uses_non_desktop_runtime": runtime_cron,
            "lines": cron_lines,
            "logs": [_tail_status(p) for p in CRON_LOGS],
        },
        "next_closes": next_closes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Metaculus Cup status.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()
    status = build_status()
    if args.json:
        print(json.dumps(status, indent=2))
        return

    cov = status["coverage"]
    mode = status["provider_cost_mode"]
    print(f"{status['tournament']} status @ {status['generated_at'][:16]}Z")
    print(f"open={status['open_count']} types={status['type_counts']}")
    print(f"coverage={cov['with_submitted_local_log']}/{status['open_count']} "
          f"latest_submitted={cov['latest_submitted_at']}")
    print(f"provider_default={mode['default_provider']} paid_allowed={mode['paid_provider_allowed']} "
          f"opus_allowed={mode['opus_allowed']}")
    print(f"cron_runtime_ok={status['cron']['uses_non_desktop_runtime']}")
    for log in status["cron"]["logs"]:
        errors = log.get("errors") or []
        label = Path(log["path"]).name
        if not log.get("exists"):
            print(f"{label}: missing")
        elif errors:
            print(f"{label}: {len(errors)} recent error line(s); latest: {errors[-1][:140]}")
        else:
            print(f"{label}: no recent error lines")
    print("\nnext closes:")
    for row in status["next_closes"]:
        print(f"{row['close']}\t{row['type']:15}\tpost={row['post_id']}\t"
              f"latest={str(row['latest_at'])[:19]}\t{row['title'][:80]}")


if __name__ == "__main__":
    main()
