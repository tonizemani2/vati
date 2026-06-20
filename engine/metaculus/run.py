"""Orchestrator — pull a tournament's open binary questions, forecast each, dry-run or submit.

Safe by default: prints forecasts and does NOTHING to the live site unless you pass --submit.
Tracks which question_ids we've already forecast this run-set in a local log so a re-run only fills
gaps (and so --submit is idempotent within a season's cadence).

Usage:
  # smoke-test one local question, no network to Metaculus, $0:
  python -m engine.metaculus.run --selftest

  # dry-run a live tournament (reads Metaculus, forecasts, prints — NO submit):
  python -m engine.metaculus.run --tournament metaculus-cup-summer-2026 --limit 5 --proxy evomi

  # actually submit (needs METACULUS_TOKEN in .env + the account joined the tournament):
  python -m engine.metaculus.run --tournament metaculus-cup-summer-2026 --submit --comment

Known slug: 'metaculus-cup-summer-2026' (bot/proof-track Cup work). The FutureEval/AIB bot tournament
slug changes per season — pass the current one. Numeric tournament ids also work.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from engine.metaculus import api, forecast

LOG_DIR = Path(__file__).resolve().parents[2] / "data" / "metaculus"


def _opt(args, flag, default=None, cast=str):
    return cast(args[args.index(flag) + 1]) if flag in args else default


def _selftest(proxy):
    """End-to-end on one hand-written question — exercises research + ensemble + anchor at $0,
    with no Metaculus token required. The honest local proof the pipeline runs."""
    q = {
        "post_id": 0, "question_id": 0,
        "title": "Will OpenAI release a model branded 'GPT-6' before 2027-01-01?",
        "resolution_criteria": "Resolves YES if OpenAI publicly releases a model officially named "
                               "GPT-6 (general availability or API) before 1 Jan 2027.",
        "fine_print": "", "description": "", "url": "(selftest)",
    }
    print(f"SELFTEST — {q['title']}\n")
    out = forecast.forecast_question(q, crowd=0.20, n=2, proxy=proxy)
    print(json.dumps({k: v for k, v in out.items() if k != "sources"}, indent=2))
    print(f"\nsources ({len(out['sources'])}):")
    for s in out["sources"][:6]:
        print(f"  - [{s['source']}] {s['title'][:80]}")
    return out


def _log_path(tournament: str) -> Path:
    return LOG_DIR / f"forecasts_{tournament}.jsonl"


def _already_done(path: Path) -> set:
    if not path.exists():
        return set()
    return {json.loads(l)["question_id"] for l in path.open() if l.strip()}


def main():
    args = sys.argv[1:]
    proxy = _opt(args, "--proxy")
    # ensemble runs DIRECT by default (home IP gets more keyless models than the proxy on this Mac);
    # --ensemble-proxy <name> overrides if a future machine needs it.
    ens_proxy = _opt(args, "--ensemble-proxy", None)
    n = int(_opt(args, "--n", 2))
    with_markets = "--markets" in args

    if "--selftest" in args:
        _selftest(proxy)
        return

    tournament = _opt(args, "--tournament")
    if not tournament:
        print("need --tournament <slug|id>  (or --selftest)"); sys.exit(2)
    limit = _opt(args, "--limit", None, int)
    do_submit = "--submit" in args
    do_comment = "--comment" in args
    today = date.today().isoformat()

    posts = api.list_open_questions(tournament)
    binary = [p for p in posts if api.binary_question(p)]
    print(f"{tournament}: {len(posts)} open posts, {len(binary)} binary "
          f"({'SUBMIT' if do_submit else 'DRY-RUN'})", flush=True)
    if limit:
        binary = binary[:limit]

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = _log_path(tournament)
    done = _already_done(log)

    for i, post in enumerate(binary, 1):
        q = api.question_text(post)
        if q["question_id"] in done:
            print(f"[{i}/{len(binary)}] skip (done): {q['title'][:70]}")
            continue
        crowd = api.community_prob(post)
        out = forecast.forecast_question(q, today=today, crowd=crowd, n=n, proxy=proxy,
                                         with_markets=with_markets, ensemble_proxy=ens_proxy)
        print(f"[{i}/{len(binary)}] p={out['prob']:.2f} "
              f"(crowd={crowd if crowd is None else round(crowd,2)}, "
              f"models={out['n_models']}) {q['title'][:64]}", flush=True)

        rec = {"question_id": q["question_id"], "post_id": q["post_id"], "title": q["title"],
               "prob": out["prob"], "crowd": crowd, "reasoning": out["reasoning"],
               "at": datetime.now(timezone.utc).isoformat()}
        if do_submit:
            try:
                api.submit_binary(q["question_id"], out["prob"])
                if do_comment:
                    api.post_comment(q["post_id"], out["reasoning"], private=True)
                rec["submitted"] = True
            except Exception as e:
                rec["submitted"] = False
                rec["error"] = str(e)[:300]
                print(f"      submit FAILED: {rec['error']}", flush=True)
        with log.open("a") as f:
            f.write(json.dumps(rec) + "\n")

    print(f"\nlog → {log}")


if __name__ == "__main__":
    main()
