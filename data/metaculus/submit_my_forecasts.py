"""Submit a hand-authored Cup forecast slate (Claude in-session reasoning + live web research,
2026-06-13). No LLM call here — just posts the numbers I reasoned out. $0.
  DRY:  python data/metaculus/submit_my_forecasts.py
  LIVE: python data/metaculus/submit_my_forecasts.py --submit
"""
import sys, time, json
from datetime import datetime, timezone
from engine.metaculus import api, numeric

LIVE = "--submit" in sys.argv
LOG = "data/metaculus/forecasts_metaculus-cup-summer-2026.jsonl"

# qid -> {post_id, type, options, scaling} from the slate we dumped to /tmp/cup_q.json
QMAP = {q["qid"]: q for q in json.load(open("/tmp/cup_q.json"))}

F = {
    43465: {"p": 0.12, "t": "MV Hondius >=5 non-passenger cases"},
    43343: {"p": 0.15, "t": "WC match delayed >30min by heat"},
    43430: {"p": 0.14, "t": "Pope non-Spain/Italy trip May18-Sep1 (Africa was April)"},
    43612: {"p": 0.42, "t": "Dai Dai peaks >=#37 (now #38)"},
    43360: {"p": 0.17, "t": "UK threat down from SEVERE (raised Apr30)"},
    43522: {"p": 0.33, "t": "ChatGPT Atlas Windows before Sep1"},
    43363: {"p": 0.72, "t": "Community beats Dylan Matthews"},
    43498: {"p": 0.13, "t": "Bosnia new HR before Sep2 (PIC deadlocked)"},
    43506: {"p": 0.10, "t": "Instructure another hack before Sep1"},
    43501: {"p": 0.95, "t": "US state/EU data-center grid restriction (NY Jun5 + NL)"},
    43336: {"p": 0.10, "t": "OPEC/OPEC+ member announces quit"},
    43510: {"p": 0.08, "t": "Senate removes Sara Duterte (trial starts Jul6)"},
    43519: {"opts": {"Conservative Party": 0.003, "Labour Party": 0.82, "Green Party": 0.004,
                     "Reform UK": 0.155, "Liberal Democrats": 0.003, "Restore Britain": 0.010,
                     "Other party or candidate": 0.005}, "t": "Makerfield (Burnham/Lab +~8)"},
    43437: {"pct": {0.1: 23000, 0.25: 25000, 0.5: 27000, 0.75: 29000, 0.9: 31000}, "t": "CA building permits"},
    43474: {"pct": {0.1: 17, 0.25: 20, 0.5: 23, 0.75: 27, 0.9: 31}, "t": "Algeria turnout (~23% in 2021)"},
    43965: {"pct": {0.1: 135, 0.25: 150, 0.5: 168, 0.75: 188, 0.9: 212}, "t": "SpaceX end-Aug (IPO Jun12 ~$161)"},
    43333: {"pct": {0.1: 34, 0.25: 37, 0.5: 40, 0.75: 43, 0.9: 46}, "t": "WC weakest-advancer rank"},
    43495: {"pct": {0.1: 1, 0.25: 1, 0.5: 1, 0.75: 2, 0.9: 3}, "t": "WSOP ME winner bracelets"},
}


def backoff(fn, *a):
    for _ in range(4):
        try:
            return fn(*a), None
        except Exception as e:
            s = str(e)
            if "429" in s or "1015" in s:
                time.sleep(30); continue
            return None, s[:200]
    return None, "rate-limited"


def main():
    ok = err = 0
    for qid, fc in F.items():
        info = QMAP.get(qid, {})
        rec = {"question_id": qid, "post_id": info.get("post"), "note": fc["t"],
               "author": "claude-in-session", "at": datetime.now(timezone.utc).isoformat()}
        try:
            if "p" in fc:
                rec["type"] = "binary"; rec["prob"] = fc["p"]
                res, e = (backoff(api.submit_binary, qid, fc["p"]) if LIVE else (True, None))
                disp = f"p={fc['p']}"
            elif "opts" in fc:
                rec["type"] = "multiple_choice"
                post = api.get_post(info["post"]); options = (post.get("question") or {}).get("options")
                vec = numeric.options_to_vector(fc["opts"], options); rec["option_probs"] = vec
                res, e = (backoff(numeric.submit_multiple_choice, qid, vec) if LIVE else (True, None))
                disp = "MC " + ",".join(f"{k[:6]}={v:.2f}" for k, v in list(vec.items())[:4])
            else:
                rec["type"] = "numeric"
                post = api.get_post(info["post"]); m = numeric.question_meta(post)
                cdf = numeric.percentiles_to_cdf({float(k): float(v) for k, v in fc["pct"].items()},
                                                 m["continuous_range"], m["open_lower_bound"], m["open_upper_bound"])
                rec["percentiles"] = fc["pct"]
                valid, msg = numeric.validate_cdf(cdf, len(m["continuous_range"]))
                if not valid:
                    raise RuntimeError(f"invalid cdf: {msg}")
                res, e = (backoff(numeric.submit_cdf, qid, cdf) if LIVE else (True, None))
                disp = f"CDF valid={valid}"
        except Exception as ex:
            e = f"{type(ex).__name__}: {ex}"[:150]; disp = "ERR"
        rec["submitted"] = LIVE and (e is None)
        if e:
            err += 1; rec["error"] = e; print(f"FAIL {qid} {fc['t'][:38]} -> {e[:80]}")
        else:
            ok += 1; print(f"{'OK  ' if LIVE else 'DRY '} {qid} {rec['type']:14} {disp:26} {fc['t'][:34]}")
        with open(LOG, "a") as f:
            f.write(json.dumps(rec) + "\n")
        if LIVE:
            time.sleep(8)
    print(f"\n{'SUBMITTED' if LIVE else 'DRY'}: ok={ok} err={err} / {len(F)}")


if __name__ == "__main__":
    main()
