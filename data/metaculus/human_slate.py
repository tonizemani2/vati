"""Generate a private human-review slate for the Metaculus Cup.

This does not forecast, submit, call LLMs, or write public proof logs. It turns the latest submitted
local bot/proof-track forecast for each currently open Cup question into a reviewable JSON list that
`submit_slate.py --human --submit` can post after the user has reviewed it and refreshed their human
Metaculus session cookie.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.metaculus import api

SLUG = "metaculus-cup-summer-2026"
ROOT = Path(__file__).resolve().parents[2]
META_DIR = ROOT / "data" / "metaculus"
PRIVATE_DIR = META_DIR / "private_slates"
FORECAST_LOGS = (
    META_DIR / f"forecasts_{SLUG}.jsonl",
    META_DIR / f"nonbinary_{SLUG}.jsonl",
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


def _records_for_post(records: list[dict[str, Any]], post_id: int) -> list[dict[str, Any]]:
    rows = [r for r in records if r.get("post_id") == post_id and r.get("submitted")]
    rows.sort(key=lambda r: _parse_time(r.get("at")) or datetime.min.replace(tzinfo=timezone.utc))
    return rows


def _payload(rec: dict[str, Any], typ: str) -> dict[str, Any]:
    if not rec:
        return {}
    if typ == "binary" and "prob" in rec:
        return {"prob": rec["prob"]}
    if typ == "multiple_choice":
        opts = rec.get("options") or rec.get("option_probs")
        return {"options": opts} if opts else {}
    if typ in {"numeric", "discrete", "date"} and rec.get("percentiles"):
        return {"percentiles": rec["percentiles"]}
    return {}


def _delta(current: dict[str, Any], previous: dict[str, Any] | None, typ: str) -> dict[str, Any]:
    if not current or not previous:
        return {}
    if typ == "binary" and "prob" in current and "prob" in previous:
        return {"prob_delta": round(float(current["prob"]) - float(previous["prob"]), 4)}
    if typ in {"numeric", "discrete", "date"}:
        cur = current.get("percentiles") or {}
        prev = previous.get("percentiles") or {}
        if "0.5" in cur and "0.5" in prev:
            c, p = float(cur["0.5"]), float(prev["0.5"])
            pct = None if p == 0 else round((c - p) / abs(p), 4)
            return {"median_delta": round(c - p, 4), "median_delta_pct": pct}
    if typ == "multiple_choice":
        cur = current.get("option_probs") or current.get("options") or {}
        prev = previous.get("option_probs") or previous.get("options") or {}
        if cur:
            top = max(cur, key=lambda k: cur[k])
            out = {"top_option": top, "top_probability": round(float(cur[top]), 4)}
            if top in prev:
                out["top_probability_delta"] = round(float(cur[top]) - float(prev[top]), 4)
            return out
    return {}


def _priority(close_time: str | None, typ: str, delta: dict[str, Any]) -> str:
    close = _parse_time(close_time)
    now = datetime.now(timezone.utc)
    if close and (close - now).days <= 7:
        return "urgent_close"
    if typ != "binary":
        return "nonbinary_review"
    if abs(float(delta.get("prob_delta", 0.0))) >= 0.05:
        return "large_move_review"
    return "routine"


def build_slate() -> list[dict[str, Any]]:
    posts = api.list_open_questions(SLUG, forecast_type="binary,multiple_choice,numeric,discrete,date")
    posts.sort(key=lambda p: (p.get("question") or {}).get("scheduled_close_time") or "9999")
    records = _records()
    slate: list[dict[str, Any]] = []
    generated = datetime.now(timezone.utc).isoformat()
    for p in posts:
        q = p.get("question") or {}
        post_id = int(p.get("id"))
        typ = q.get("type") or "binary"
        rows = _records_for_post(records, post_id)
        latest = rows[-1] if rows else {}
        previous = rows[-2] if len(rows) >= 2 else None
        payload = _payload(latest, typ)
        delta = _delta(latest, previous, typ)
        note = latest.get("note") or latest.get("reasoning") or "No local submitted forecast found; manual review required."
        item = {
            "qid": q.get("id"),
            "post_id": post_id,
            "tournament": SLUG,
            "type": typ,
            "title": p.get("title") or q.get("title") or "",
            "url": f"https://www.metaculus.com/questions/{post_id}/",
            "close_time": q.get("scheduled_close_time") or p.get("scheduled_close_time"),
            "priority": _priority(q.get("scheduled_close_time") or p.get("scheduled_close_time"), typ, delta),
            "note": str(note)[:500],
            "source_notes": [
                f"latest_log={latest.get('_log')}",
                f"latest_at={latest.get('at')}",
                f"latest_author={latest.get('author')}",
                f"latest_provider={latest.get('provider')}",
                "private human-review slate; not a prize-eligibility claim",
            ],
            "delta": delta,
            "generated_at": generated,
            "needs_manual_forecast": not bool(payload),
        }
        item.update(payload)
        slate.append(item)
    return slate


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a private Metaculus Cup human-review slate.")
    parser.add_argument("--out", help="Output path. Defaults to data/metaculus/private_slates/<date>-cup-human-slate.json")
    parser.add_argument("--stdout", action="store_true", help="Print the slate JSON to stdout.")
    parser.add_argument("--no-write", action="store_true", help="Do not write a slate file.")
    args = parser.parse_args()

    slate = build_slate()
    if args.stdout:
        print(json.dumps(slate, indent=2))
    if not args.no_write:
        PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
        out = Path(args.out) if args.out else PRIVATE_DIR / f"{datetime.now(timezone.utc).date()}-cup-human-slate.json"
        out.write_text(json.dumps(slate, indent=2) + "\n", encoding="utf-8")
        ready = sum(1 for x in slate if not x.get("needs_manual_forecast"))
        urgent = sum(1 for x in slate if x.get("priority") == "urgent_close")
        print(f"wrote {out} | questions={len(slate)} ready_payloads={ready} urgent_close={urgent}")


if __name__ == "__main__":
    main()
