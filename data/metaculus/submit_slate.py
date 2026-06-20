"""Submit a slate of in-session (Opus) forecasts from a JSON file — generalizes the old hand-edited
submit_my_forecasts.py so the /metaculus ritual just writes JSON and runs this. No LLM call here ($0):
it posts the numbers already reasoned out, handling every question type.

Slate file = JSON list, one object per forecast:
  {"qid": 43363, "post_id": 43363, "tournament": "metaculus-cup-summer-2026",
   "type": "binary",          "prob": 0.72, "note": "why"}
  {"qid": 43519, "type": "multiple_choice", "options": {"Labour Party": 0.82, ...}, "note": "..."}
  {"qid": 43965, "type": "numeric",  "percentiles": {"0.1": 135, "0.5": 168, "0.9": 212}, "note": "..."}
(date/discrete use the same "percentiles" shape as numeric.)

  DRY:        python data/metaculus/submit_slate.py [slate.json]
  HUMAN LIVE: python data/metaculus/submit_slate.py [slate.json] --human --submit

Dry-runs do not append to the live forecast log unless --log-dry-run is passed. Human live submits
verify the short-lived Metaculus browser session before the first write.
Default slate path: /tmp/mtc_slate.json
"""
import json, sys, time
from datetime import datetime, timezone

from engine.metaculus import api, numeric


def _epoch(v):
    """Parse an ISO date/datetime string (or pass through a number) to unix seconds."""
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s).timestamp()
    except ValueError:
        return datetime.fromisoformat(s[:10]).timestamp()


LIVE = "--submit" in sys.argv
HUMAN = "--human" in sys.argv  # submit under YOUR logged-in account (cookies) instead of the bot token
LOG_DRY_RUN = "--log-dry-run" in sys.argv
NO_LOG = "--no-log" in sys.argv or (not LIVE and not LOG_DRY_RUN)
paths = [a for a in sys.argv[1:] if not a.startswith("--")]
SLATE = paths[0] if paths else "/tmp/mtc_slate.json"

if HUMAN:
    from engine.metaculus import human_api as HUMAN_API
    SUB_BINARY = HUMAN_API.submit_binary
    SUB_MC = HUMAN_API.submit_multiple_choice
    SUB_CDF = HUMAN_API.submit_cdf
    AUTHOR = "human-303699"
else:
    HUMAN_API = None
    SUB_BINARY = api.submit_binary
    SUB_MC = numeric.submit_multiple_choice
    SUB_CDF = numeric.submit_cdf
    AUTHOR = "vati-bot-proof-track"


def backoff(fn, *a):
    for _ in range(4):
        try:
            return fn(*a), None
        except Exception as e:
            s = str(e)
            if "429" in s or "1015" in s:
                time.sleep(35); continue
            return None, s[:200]
    return None, "rate-limited x4"


def main():
    slate = json.load(open(SLATE))
    if HUMAN and LIVE:
        me = HUMAN_API.me()
        print(f"human session OK: id={me.get('id')} username={me.get('username')}")
    target = "human" if HUMAN else "bot/proof-track"
    print(f"slate: {len(slate)} forecasts from {SLATE} | target={target} "
          f"| mode={'LIVE' if LIVE else 'DRY-RUN'} | log={'off' if NO_LOG else 'on'}\n")
    ok = err = 0
    for i, fc in enumerate(slate, 1):
        qid = fc.get("qid") or fc.get("question_id")
        typ = fc.get("type", "binary")
        slug = fc.get("tournament", "metaculus-cup-summer-2026")
        note = (fc.get("note") or "")[:90]
        rec = {"question_id": qid, "post_id": fc.get("post_id"), "type": typ,
               "note": note, "author": AUTHOR,
               "at": datetime.now(timezone.utc).isoformat()}
        disp = ""
        try:
            if typ == "binary":
                prob = float(fc["prob"]); rec["prob"] = prob
                rec["crowd"] = fc.get("crowd")
                disp = f"p={prob:.2f}"
                res, e = (backoff(SUB_BINARY, qid, prob) if LIVE else (True, None))
            elif typ == "multiple_choice":
                post, e = backoff(api.get_post, fc["post_id"])
                if e:
                    raise RuntimeError(f"get_post failed: {e}")
                meta = numeric.question_meta(post)
                vec = numeric.options_to_vector(fc["options"], meta["options"])
                rec["option_probs"] = vec
                disp = "MC " + ",".join(f"{k[:8]}={v:.2f}" for k, v in list(vec.items())[:3])
                res, e = (backoff(SUB_MC, qid, vec) if LIVE else (True, None))
            else:  # numeric / discrete / date
                post, e = backoff(api.get_post, fc["post_id"])
                if e:
                    raise RuntimeError(f"get_post failed: {e}")
                meta = numeric.question_meta(post)
                cr = meta["continuous_range"]
                if typ == "date":  # date grid + percentile values are ISO → convert both to epoch
                    cr = [_epoch(x) for x in cr]
                    pct = {float(k): _epoch(v) for k, v in fc["percentiles"].items()}
                else:
                    pct = {float(k): float(v) for k, v in fc["percentiles"].items()}
                cdf = numeric.percentiles_to_cdf(pct, cr,
                                                 meta["open_lower_bound"], meta["open_upper_bound"])
                valid, msg = numeric.validate_cdf(cdf, len(meta["continuous_range"]))
                if not valid:
                    raise RuntimeError(f"invalid cdf: {msg}")
                rec["percentiles"] = pct
                disp = f"CDF len={len(cdf)} valid"
                res, e = (backoff(SUB_CDF, qid, cdf) if LIVE else (True, None))
        except Exception as ex:
            e = f"{type(ex).__name__}: {ex}"[:200]; disp = "ERR"
        rec["submitted"] = LIVE and (e is None)
        if not NO_LOG:
            log = f"data/metaculus/forecasts_{slug}.jsonl"
            with open(log, "a") as f:
                f.write(json.dumps(rec) + "\n")
        if e:
            rec_err = e; err += 1
            print(f"[{i:2}/{len(slate)}] FAIL {typ:14} {note[:45]}  -> {e[:60]}")
        else:
            ok += 1
            tag = "OK  " if LIVE else "DRY "
            print(f"[{i:2}/{len(slate)}] {tag} {typ:14} {note[:45]}  -> {disp}")
        if LIVE:
            time.sleep(8)
    print(f"\n{'SUBMITTED' if LIVE else 'DRY-RAN'}: ok={ok} err={err} / {len(slate)}")


if __name__ == "__main__":
    main()
