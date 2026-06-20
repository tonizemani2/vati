"""Refresh queue — the worklist for an in-session Opus refresh. Collects every OPEN question across
the bot's tournaments, attaches the crowd anchor + how stale our last forecast is, and sorts by
urgency so the questions that win or lose peer score NOW float to the top:
  1. never-forecasted (a coverage gap — coverage is a literal prize multiplier),
  2. soonest-closing (last chance to be accurate before resolution),
  3. stalest (our live forecast has drifted furthest from current reality).

  python data/metaculus/refresh_queue.py                 # all tournaments, top 25
  python data/metaculus/refresh_queue.py --limit 15      # cap the list
  python data/metaculus/refresh_queue.py cup current-events   # only these slugs

Writes /tmp/mtc_queue.json (full question text + criteria + crowd + close + staleness) for the
in-session forecaster to read, and prints a ranked table.
"""
import glob, json, os, sys, time
from datetime import datetime, timezone

from engine.metaculus import api

HERE = os.path.dirname(__file__)
QUEUE = "/tmp/mtc_queue.json"
NOW = datetime.now(timezone.utc)

DEFAULT_SLUGS = [
    "metaculus-cup-summer-2026", "current-events", "midterms-2026", "POTUS-predictions",
    "ai-industry-milestones", "chinese-ai-chips", "taiwan", "sagan-tournament", "synbio",
    "space-tech-climate", "nuclear-horizons", "superconductors", "quantum-computing",
]
# short-slug aliases so `... cup` works
ALIAS = {"cup": "metaculus-cup-summer-2026", "potus": "POTUS-predictions",
         "midterms": "midterms-2026", "ai": "ai-industry-milestones"}


def _limit():
    if "--limit" in sys.argv:
        try: return int(sys.argv[sys.argv.index("--limit") + 1])
        except (ValueError, IndexError): pass
    return 25


def _slugs():
    args = [a for a in sys.argv[1:] if not a.startswith("--")
            and not a.isdigit()]
    if not args:
        return DEFAULT_SLUGS
    return [ALIAS.get(a, a) for a in args]


def _last_forecast_age():
    """post_id -> days since our most recent logged forecast (from forecasts_*.jsonl)."""
    latest = {}
    for path in glob.glob(os.path.join(HERE, "forecasts_*.jsonl")):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                pid, at = rec.get("post_id"), rec.get("at")
                if pid is None or not at or rec.get("error"):
                    continue
                if pid not in latest or at > latest[pid]:
                    latest[pid] = at
    ages = {}
    for pid, at in latest.items():
        try:
            dt = datetime.fromisoformat(at.replace("Z", "+00:00"))
            ages[pid] = (NOW - dt).total_seconds() / 86400.0
        except ValueError:
            pass
    return ages


def _days_to_close(iso):
    if not iso:
        return 9999.0
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return (dt - NOW).total_seconds() / 86400.0
    except ValueError:
        return 9999.0


def main():
    ages = _last_forecast_age()
    slugs = _slugs()
    rows = []
    seen = set()
    for slug in slugs:
        try:
            posts = api.list_open_questions(
                slug, forecast_type="binary,multiple_choice,numeric,discrete,date")
        except Exception as e:
            print(f"  ! {slug}: {str(e)[:80]}", file=sys.stderr)
            time.sleep(2)
            continue
        for p in posts:
            pid = p.get("id")
            if pid in seen:
                continue
            seen.add(pid)
            q = p.get("question") or {}
            qt = api.question_text(p)
            dtc = _days_to_close(qt["close_time"])
            age = ages.get(pid)  # None = never forecasted = coverage gap
            rows.append({
                "tournament": slug, "post_id": pid, "question_id": qt["question_id"],
                "type": q.get("type"), "title": qt["title"],
                "description": qt["description"][:1500],
                "resolution_criteria": qt["resolution_criteria"][:1200],
                "fine_print": qt["fine_print"][:600],
                "close_time": qt["close_time"], "days_to_close": round(dtc, 1),
                "crowd": api.community_prob(p),
                "last_forecast_age_days": round(age, 1) if age is not None else None,
                "url": qt["url"],
            })
        time.sleep(1.5)

    # urgency rank: coverage gaps first, then soonest-closing, then stalest
    def key(r):
        never = r["last_forecast_age_days"] is None
        return (0 if never else 1, r["days_to_close"],
                -(r["last_forecast_age_days"] or 0))
    rows.sort(key=key)
    lim = _limit()
    queued = rows[:lim]

    # crowd anchor lives only on the post DETAIL, not the list — enrich just the queued (capped) items
    # so the worklist carries the guardrail. Bounded to `lim` GETs, paced + backed-off for Cloudflare.
    for r in queued:
        if r["crowd"] is not None:
            continue
        for _ in range(3):
            try:
                r["crowd"] = api.community_prob(api.get_post(r["post_id"]))
                break
            except Exception as ex:
                if "429" in str(ex) or "1015" in str(ex):
                    time.sleep(30); continue
                break
        time.sleep(1.2)

    with open(QUEUE, "w") as f:
        json.dump(queued, f, indent=2)

    print(f"\n=== refresh queue: {len(rows)} open across {len(slugs)} tournaments, "
          f"top {len(queued)} queued -> {QUEUE} ===")
    print(f"{'#':>2} {'close(d)':>8} {'age(d)':>7} {'crowd':>6} {'type':12} title")
    for i, r in enumerate(queued, 1):
        age = "NEW" if r["last_forecast_age_days"] is None else f"{r['last_forecast_age_days']:.0f}"
        crowd = f"{r['crowd']:.2f}" if r["crowd"] is not None else "  -"
        print(f"{i:>2} {r['days_to_close']:>8.1f} {age:>7} {crowd:>6} "
              f"{(r['type'] or '?')[:12]:12} {r['title'][:60]}")
    if len(rows) > lim:
        print(f"\n(+{len(rows)-lim} more not queued — raise --limit to include them)")


if __name__ == "__main__":
    main()
