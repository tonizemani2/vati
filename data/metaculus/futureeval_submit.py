"""Submit Opus-council binary forecasts to FutureEval — the deterministic write half.

The /futureeval command (a Claude Code session) does the judgment and writes a JSON list of
{question_id, prob, [title], [reasoning]}; this script POSTs each via the bot token. Submission
is plain Python on purpose: never trust the LLM to make the API call. Metaculus updates a forecast
in place (last-write-wins), so this is safe to run after the free baseline — it overwrites with the
better Opus number. Logs to the round jsonl + refreshes futureeval_submitted.json.

  DRY:  uv run python data/metaculus/futureeval_submit.py /tmp/fe_forecasts.json
  LIVE: uv run python data/metaculus/futureeval_submit.py /tmp/fe_forecasts.json --submit
"""
import json, os, sys, time
from datetime import datetime, timezone

from engine.metaculus import api

SLUG = os.getenv("FE_SLUG", "summer-futureeval-2026")
LIVE = "--submit" in sys.argv
path = next((a for a in sys.argv[1:] if not a.startswith("--")), "/tmp/fe_forecasts.json")
LOG = f"data/metaculus/forecasts_{SLUG}.jsonl"
STATE = "data/metaculus/futureeval_submitted.json"

rows = json.load(open(path))
try:
    state = {s.get("qid"): s for s in json.load(open(STATE))}
except Exception:
    state = {}

ok = err = 0
for r in rows:
    qid = r.get("question_id") or r.get("qid")
    prob = r.get("prob")
    if qid is None or prob is None:
        print("skip (missing qid/prob):", r)
        continue
    name = (r.get("title") or r.get("name") or "")[:80]
    rec = {"qid": qid, "prob": round(float(prob), 4), "name": name,
           "tier": "opus-subagent-council", "at": datetime.now(timezone.utc).isoformat(),
           "submitted": False}
    if LIVE:
        try:
            api.submit_binary(qid, float(prob))
            rec["submitted"] = True; ok += 1
            print(f"OK   {qid} p={float(prob):.2f} {name}")
            time.sleep(8)  # Metaculus/Cloudflare rate-limits; pace ~8s
        except Exception as e:
            rec["error"] = str(e)[:200]; err += 1
            print(f"FAIL {qid} -> {str(e)[:80]}")
    else:
        print(f"DRY  {qid} p={float(prob):.2f} {name}")
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")
    state[qid] = {"qid": qid, "prob": rec["prob"], "name": name, "submitted": rec["submitted"]}

json.dump(list(state.values()), open(STATE, "w"), indent=1)
print(f"\n{'SUBMITTED' if LIVE else 'DRY'}: ok={ok} err={err} / {len(rows)}")
