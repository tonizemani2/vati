"""Cup updater — re-forecast EVERY open question in metaculus-cup-summer-2026 with the $0 council
and submit each as a fresh bot/proof-track forecast. Metaculus scores the latest forecast over the
question's open life, so updating as news moves is the real win lever. Unlike submit_pool this is NOT
idempotent: it always re-forecasts + re-submits unless --healthcheck is used.

  DRY (default): python data/metaculus/cup_update.py
  LIVE:          python data/metaculus/cup_update.py --submit
  READ-ONLY:     python data/metaculus/cup_update.py --healthcheck

Default models are OpenRouter `:free` (provider=openrouter_free) — no billed LLM usage. Paid
providers are fail-closed unless CUP_ALLOW_PAID_PROVIDER=1 is set in the environment.
"""
import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone

from engine.metaculus import api, numeric, forecast, numeric_forecast

SLUG = "metaculus-cup-summer-2026"
LOG = f"data/metaculus/forecasts_{SLUG}.jsonl"
FREE_PROVIDER = "openrouter_free"
PAID_PROVIDERS = {"deepseek"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Refresh Metaculus Cup bot/proof-track forecasts.")
    p.add_argument("--submit", action="store_true", help="Submit forecasts for real.")
    p.add_argument("--provider", default=os.getenv("CUP_PROVIDER", FREE_PROVIDER),
                   choices=[FREE_PROVIDER, "deepseek"],
                   help="Forecast provider. Default is OpenRouter :free.")
    p.add_argument("--limit", type=int, help="Cap the number of soonest-closing questions.")
    p.add_argument("--n", type=int, default=int(os.getenv("CUP_SAMPLES", "2")),
                   help="Samples per model.")
    p.add_argument("--healthcheck", action="store_true",
                   help="Read-only: list live questions and exit. No forecasts, submissions, or logs.")
    p.add_argument("--no-log", action="store_true",
                   help="Do not append to the local forecast log. Not allowed with --submit.")
    args = p.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        p.error("--limit must be >= 1")
    if args.submit and args.no_log:
        p.error("--no-log cannot be combined with --submit; live writes need an audit trail")
    if (args.provider in PAID_PROVIDERS and not args.healthcheck
            and os.getenv("CUP_ALLOW_PAID_PROVIDER") != "1"):
        p.error(f"--provider {args.provider!r} is paid; set CUP_ALLOW_PAID_PROVIDER=1 after approval")
    return args


def backoff(fn, *a):
    for _ in range(4):
        try:
            return fn(*a), None
        except Exception as e:
            s = str(e)
            if "429" in s or "1015" in s:
                time.sleep(40); continue
            return None, s[:300]
    return None, "rate-limited x4"


def _open_posts(args: argparse.Namespace) -> list[dict]:
    posts = api.list_open_questions(SLUG, forecast_type="binary,multiple_choice,numeric,discrete,date")
    posts.sort(key=lambda p: (p.get("question") or {}).get("scheduled_close_time") or "9999")
    if args.limit:
        posts = posts[:args.limit]
    return posts


def _healthcheck(posts: list[dict], args: argparse.Namespace) -> None:
    counts = Counter((p.get("question") or {}).get("type") or "unknown" for p in posts)
    cap = f", capped {args.limit}" if args.limit else ""
    print(f"{SLUG}: {len(posts)} open questions (soonest-closing first{cap})")
    print(f"types: {dict(sorted(counts.items()))}")
    print(f"provider_default: {args.provider} | paid_allowed={os.getenv('CUP_ALLOW_PAID_PROVIDER') == '1'}")
    print("mode: HEALTHCHECK (read-only; no forecasts, submissions, or logs)\n")
    for p in posts:
        q = p.get("question") or {}
        close = q.get("scheduled_close_time") or p.get("scheduled_close_time") or "-"
        typ = q.get("type") or "unknown"
        title = (p.get("title") or q.get("title") or "").replace("\n", " ")
        print(f"{close}\t{typ:15}\tpost={p.get('id')}\tqid={q.get('id')}\t{title[:100]}")


def main(argv: list[str] | None = None):
    args = parse_args(argv)
    posts = _open_posts(args)
    if args.healthcheck:
        _healthcheck(posts, args)
        return

    # DeepSeek = one keyed model; openrouter_free uses its multi-model leader roster.
    models = ["deepseek-chat"] if args.provider == "deepseek" else None
    cap = f", capped {args.limit}" if args.limit else ""
    print(f"{SLUG}: {len(posts)} questions (soonest-closing first{cap}) "
          f"| provider={args.provider} | mode={'LIVE' if args.submit else 'DRY-RUN'}\n")
    ok = err = 0
    for i, p in enumerate(posts, 1):
        q = p.get("question") or {}
        typ = q.get("type"); qid = q.get("id")
        title = (p.get("title") or "")[:55]
        rec = {"question_id": qid, "post_id": p.get("id"), "title": (p.get("title") or "")[:90],
               "type": typ, "at": datetime.now(timezone.utc).isoformat()}
        try:
            if typ == "binary":
                crowd = api.community_prob(p)
                out = forecast.forecast_question(api.question_text(p), crowd=crowd, n=args.n,
                                                 provider=args.provider, ensemble_models=models)
                prob = out["prob"]; rec["prob"] = prob; rec["crowd"] = crowd
                rec["reasoning"] = out.get("reasoning", "")[:300]
                disp = f"p={prob:.2f} (crowd {crowd})" if crowd is not None else f"p={prob:.2f}"
                res, e = (backoff(api.submit_binary, qid, prob) if args.submit else (True, None))
            elif typ == "multiple_choice":
                meta = numeric.question_meta(p)
                out = numeric_forecast.forecast_mc(meta, n=args.n, provider=args.provider, models=models)
                if not out: raise RuntimeError("mc forecaster returned None")
                vec = out["vector"]; rec["option_probs"] = vec
                disp = "MC " + ",".join(f"{k[:8]}={v:.2f}" for k, v in list(vec.items())[:4])
                res, e = (backoff(numeric.submit_multiple_choice, qid, vec) if args.submit else (True, None))
            else:  # numeric / discrete / date
                meta = numeric.question_meta(p)
                out = numeric_forecast.forecast_numeric(meta, n=args.n, provider=args.provider, models=models)
                if not out: raise RuntimeError("numeric forecaster returned None")
                rec["percentiles"] = out["percentiles"]
                valid, msg = numeric.validate_cdf(out["cdf"], len(meta["continuous_range"]))
                disp = f"CDF len={len(out['cdf'])} valid={valid}"
                res, e = (backoff(numeric.submit_cdf, qid, out["cdf"]) if args.submit else (True, None))
        except Exception as ex:
            e = f"{type(ex).__name__}: {ex}"[:200]; disp = "ERR"
        rec["submitted"] = args.submit and (e is None)
        rec["provider"] = args.provider
        if e:
            rec["error"] = e; err += 1
            print(f"[{i:2}/{len(posts)}] FAIL {typ:14} {title}  -> {e[:70]}")
        else:
            ok += 1
            tag = "OK  " if args.submit else "DRY "
            print(f"[{i:2}/{len(posts)}] {tag} {typ:14} {title}  -> {disp}")
        if not args.no_log:
            with open(LOG, "a") as f:
                f.write(json.dumps(rec) + "\n")
        if args.submit:
            time.sleep(8)
    log_note = "" if not args.no_log else " (no log written)"
    print(f"\n{'SUBMITTED' if args.submit else 'DRY-RAN'}: ok={ok} err={err} / {len(posts)}{log_note}")


if __name__ == "__main__":
    main(sys.argv[1:])
