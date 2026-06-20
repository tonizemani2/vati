"""Score puller — the feedback loop the bot was missing. Reads every forecasts_*.jsonl submission
log, fetches each post's current resolution from Metaculus, and for resolved BINARY questions
computes our Brier AND the community's Brier on the same question. That crowd comparison is the
local proxy for Metaculus peer score (peer score = are you beating the crowd), the thing that
actually wins tournaments — and unlike the on-site score it's recomputable and honest.

  python data/metaculus/pull_scores.py            # refresh + print the board
  python data/metaculus/pull_scores.py --quiet    # refresh, write scores.json, no table

Writes data/metaculus/scores.json (per-tournament + overall + resolved detail).
Open questions are reported as "live, unresolved" — no win/loss until they resolve.
"""
import glob, json, os, sys, time
from collections import defaultdict
from datetime import datetime, timezone

from engine.metaculus import api

QUIET = "--quiet" in sys.argv
HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "scores.json")
PACE = 1.5      # seconds between requests (Metaculus Cloudflare throttles hard: 1015)
BACKOFF = 30    # seconds to wait on a 429/1015 before retrying


def _get_post(pid):
    """get_post with Cloudflare-aware backoff. Returns None after 4 throttled tries."""
    for _ in range(4):
        try:
            return api.get_post(pid)
        except Exception as e:
            s = str(e)
            if "429" in s or "1015" in s:
                time.sleep(BACKOFF); continue
            raise
    return None


def _latest_by_post():
    """Last (most recent) forecast we logged per post, per tournament. Daily re-forecasts append,
    so the final line for a post is the forecast Metaculus is actually scoring near resolution."""
    latest = {}  # post_id -> record (with tournament attached)
    for path in sorted(glob.glob(os.path.join(HERE, "forecasts_*.jsonl"))):
        slug = os.path.basename(path)[len("forecasts_"):-len(".jsonl")]
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                pid = rec.get("post_id")
                if pid is None or rec.get("error"):
                    continue
                rec["tournament"] = slug
                latest[pid] = rec  # later lines overwrite -> keeps the most recent
    return latest


def _outcome(resolution):
    """Map a binary resolution string to 1/0, or None if not a clean yes/no (annulled/ambiguous/open)."""
    if resolution is None:
        return None
    r = str(resolution).strip().lower()
    if r in ("yes", "true", "1"):
        return 1.0
    if r in ("no", "false", "0"):
        return 0.0
    return None  # annulled / ambiguous / not-resolved -> excluded from Brier


def main():
    latest = _latest_by_post()
    print(f"checking {len(latest)} forecasted posts for resolution...", file=sys.stderr)

    by_t = defaultdict(lambda: {"open": 0, "resolved": 0, "scored": 0,
                                "my_brier_sum": 0.0, "crowd_brier_sum": 0.0,
                                "wins": 0, "annulled": 0})
    resolved_detail = []

    for n, (pid, rec) in enumerate(sorted(latest.items()), 1):
        slug = rec["tournament"]
        try:
            post = _get_post(pid)
        except Exception as e:
            print(f"  skip post {pid}: {str(e)[:80]}", file=sys.stderr)
            continue
        if post is None:
            print(f"  skip post {pid}: rate-limited x4", file=sys.stderr)
            continue
        q = post.get("question") or {}
        resolution = q.get("resolution")
        t = by_t[slug]

        if resolution in (None, "", "null"):
            t["open"] += 1
            time.sleep(PACE)
            continue

        t["resolved"] += 1
        # Brier only for binary questions we have a prob for
        is_binary = (q.get("type") == "binary") and ("prob" in rec)
        outcome = _outcome(resolution) if is_binary else None
        if outcome is None:
            if is_binary:
                t["annulled"] += 1
            time.sleep(PACE)
            continue

        my_p = max(0.01, min(0.99, float(rec["prob"])))
        crowd = rec.get("crowd")
        if crowd is None:
            crowd = api.community_prob(post)
        my_brier = (my_p - outcome) ** 2
        t["scored"] += 1
        t["my_brier_sum"] += my_brier
        crowd_brier = None
        if crowd is not None:
            crowd = max(0.01, min(0.99, float(crowd)))
            crowd_brier = (crowd - outcome) ** 2
            t["crowd_brier_sum"] += crowd_brier
            if my_brier < crowd_brier:
                t["wins"] += 1
        resolved_detail.append({
            "tournament": slug, "post_id": pid, "title": rec.get("title", "")[:90],
            "resolution": resolution, "my_prob": round(my_p, 3),
            "crowd_prob": round(crowd, 3) if crowd is not None else None,
            "my_brier": round(my_brier, 4),
            "crowd_brier": round(crowd_brier, 4) if crowd_brier is not None else None,
            "beat_crowd": (crowd_brier is not None and my_brier < crowd_brier),
        })
        time.sleep(PACE)

    # ---- aggregate ----
    overall = {"open": 0, "resolved": 0, "scored": 0, "my_brier_sum": 0.0,
               "crowd_brier_sum": 0.0, "wins": 0, "annulled": 0}
    tournaments = {}
    for slug, t in sorted(by_t.items()):
        for k in overall:
            overall[k] += t[k]
        tournaments[slug] = {
            "open": t["open"], "resolved": t["resolved"], "scored": t["scored"],
            "annulled": t["annulled"],
            "my_brier": round(t["my_brier_sum"] / t["scored"], 4) if t["scored"] else None,
            "crowd_brier": round(t["crowd_brier_sum"] / t["scored"], 4) if t["scored"] else None,
            "beat_crowd_rate": round(t["wins"] / t["scored"], 3) if t["scored"] else None,
        }

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "forecasted_posts": len(latest),
            "open": overall["open"],
            "resolved": overall["resolved"],
            "scored_binary": overall["scored"],
            "annulled": overall["annulled"],
            "my_brier": round(overall["my_brier_sum"] / overall["scored"], 4) if overall["scored"] else None,
            "crowd_brier": round(overall["crowd_brier_sum"] / overall["scored"], 4) if overall["scored"] else None,
            "beat_crowd_rate": round(overall["wins"] / overall["scored"], 3) if overall["scored"] else None,
        },
        "tournaments": tournaments,
        "resolved_detail": sorted(resolved_detail, key=lambda d: d["my_brier"]),
    }
    with open(OUT, "w") as f:
        json.dump(summary, f, indent=2)

    if QUIET:
        return
    tot = summary["totals"]
    print(f"\n=== Metaculus scoreboard  ({summary['generated_at'][:16]}) ===")
    print(f"forecasted posts: {tot['forecasted_posts']}   open: {tot['open']}   "
          f"resolved: {tot['resolved']}   scored(binary): {tot['scored_binary']}")
    if tot["scored_binary"]:
        print(f"OUR Brier: {tot['my_brier']}   CROWD Brier: {tot['crowd_brier']}   "
              f"beat-crowd: {int(tot['beat_crowd_rate']*100)}%  (lower Brier = better)")
    else:
        print("nothing resolved yet — all forecasts live, no win/loss to score.")
    print(f"\n{'tournament':28} {'open':>4} {'res':>4} {'scd':>4} {'ourB':>6} {'crowdB':>7} {'beat%':>6}")
    for slug, t in tournaments.items():
        ob = f"{t['my_brier']:.3f}" if t["my_brier"] is not None else "  -  "
        cb = f"{t['crowd_brier']:.3f}" if t["crowd_brier"] is not None else "   -   "
        bc = f"{int(t['beat_crowd_rate']*100)}%" if t["beat_crowd_rate"] is not None else "  -  "
        print(f"{slug[:28]:28} {t['open']:>4} {t['resolved']:>4} {t['scored']:>4} {ob:>6} {cb:>7} {bc:>6}")
    if summary["resolved_detail"]:
        print(f"\nbest calls (lowest Brier):")
        for d in summary["resolved_detail"][:8]:
            flag = "WON " if d["beat_crowd"] else "    "
            print(f"  {flag}{d['title'][:50]:50} res={str(d['resolution'])[:4]:4} "
                  f"ours={d['my_prob']:.2f} crowd={d['crowd_prob']} B={d['my_brier']}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
