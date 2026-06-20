"""FutureEval bot-tournament daily loop — the reputation-grade ('#1 among bots') play.

The Metaculus FutureEval / AIB tournament drops questions DAILY with a short (~24h) forecast
window, then resolves in weeks → the tight short-feedback loop. The community prediction is HIDDEN
(crowd=None), so this is a pure test of standalone judgment: where a calibrated, decorrelated
council beats the overconfident raw-LLM bots. Run daily (cron) to catch each new batch before close.

Forecaster = the BEDROCK council (top-tier reasoning on OUR AWS account): Sonnet 4.6 analysts +
Opus 4.8 — the same Opus the in-session model runs. Mechanical median aggregation = the calibration.
Cost is gated + logged per call (engine.adapters.llm bedrock branch). Run keyless instead with
`--provider openrouter_free` for a $0 pass.

  DRY (default): uv run python data/metaculus/futureeval_update.py
  LIVE:          uv run python data/metaculus/futureeval_update.py --submit
  keyless $0:    uv run python data/metaculus/futureeval_update.py --submit --provider openrouter_free
"""
import json, os, sys, time
from datetime import datetime, timezone

from engine.metaculus import api, numeric, forecast, numeric_forecast, markets
from engine.adapters import llm
from engine.forecasting.ledger import append_decision

SLUG = os.getenv("FE_SLUG", "summer-futureeval-2026")  # FE_SLUG overrides for testing vs live Cup
LIVE = "--submit" in sys.argv
# Config from the 2026-resolved bake-off (data/metaculus/config_bakeoff.py): Opus 4.8 is the
# strongest single model; Sonnet correlates 0.80 with it and only drags the median, so it is DROPPED.
# We anchor on Opus with several samples (variance reduction). DeepSeek decorrelates (corr ~0.45) but
# flat-voting a weaker member hurt Brier → keep it as a synthesis challenger (TODO), not a flat vote.
N = 5  # Opus samples per question (cost no-object → more samples = tighter calibration)
LOG = f"data/metaculus/forecasts_{SLUG}.jsonl"
PROVIDER = sys.argv[sys.argv.index("--provider") + 1] if "--provider" in sys.argv else "bedrock"
if PROVIDER == "bedrock":
    MODELS = [llm.BEDROCK_DEFAULT_MODEL]  # Opus 4.8 anchor (Sonnet dropped — redundant + slight drag)
elif PROVIDER == "deepseek":
    MODELS = ["deepseek-chat"]
else:
    MODELS = None  # openrouter_free / keyless use their built-in leader roster

# Default (no explicit --provider) → Opus/deep-research routing. FutureEval hides its native CP, so
# we still look for liquid external markets, but those anchors are logged/shadow-tested by default.
# They are not blended into the submitted probability unless FE_USE_EXTERNAL_ANCHOR=1 is set.
ROUTED = "--provider" not in sys.argv
# Historical qbank simulation (2026-06-17) shows external anchors improve anchor *quality* after the
# hard gate, but still hurt when blended into a competent base forecast. So external anchors are logged
# and shadow-tested by default. Flip FE_USE_EXTERNAL_ANCHOR=1 only after live shadow Brier proves lift.
USE_EXTERNAL_ANCHOR = os.getenv("FE_USE_EXTERNAL_ANCHOR") == "1"


def anchor_weight(sim: float) -> float:
    """External fuzzy-matched market → weight below the native-CP 0.40, scaled by match confidence."""
    return round(0.20 + 0.30 * min(1.0, max(0.0, (sim - 0.55) / 0.45)), 2)


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


def _limit():
    if "--limit" in sys.argv:
        try: return int(sys.argv[sys.argv.index("--limit") + 1])
        except (ValueError, IndexError): pass
    return None


def _recent_submits(hours):
    """qids successfully submitted within the last `hours`. The cron fires 3x/day; without this
    guard each still-open question is re-forecast (and on Bedrock, RE-PAID ~$1) every run for no
    gain. Skip a question already submitted inside the window; new/unseen ones are always forecast.
    `--force` overrides. Window via FE_DEDUP_HOURS (default 18 ≈ once/day given the 8h cron spacing)."""
    from datetime import timedelta
    out = {}
    if not os.path.exists(LOG):
        return out
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    for line in open(LOG):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if not r.get("submitted"):
            continue
        qid, at = r.get("question_id"), r.get("at")
        if qid is None or not at:
            continue
        try:
            ts = datetime.fromisoformat(at)
        except Exception:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts >= cutoff and (qid not in out or ts > out[qid]):
            out[qid] = ts
    return out


def main():
    posts = api.list_open_questions(SLUG, forecast_type="binary,multiple_choice,numeric,discrete,date")
    # soonest-closing first — FutureEval windows are short, so forecast the about-to-close ones first.
    posts.sort(key=lambda p: (p.get("question") or {}).get("scheduled_close_time") or "9999")
    lim = _limit()
    if lim:
        posts = posts[:lim]
    print(f"{SLUG}: {len(posts)} open questions (soonest-closing first{f', capped {lim}' if lim else ''}) "
          f"| provider={PROVIDER} | mode={'LIVE' if LIVE else 'DRY-RUN'}\n")
    if not posts:
        print("no open questions right now (between batches) — cron will catch the next daily drop.")
        return
    dedup_h = int(os.getenv("FE_DEDUP_HOURS", "18"))
    recent = {} if "--force" in sys.argv else _recent_submits(dedup_h)
    if recent:
        print(f"dedup: skipping {len(recent)} question(s) already submitted within {dedup_h}h "
              f"(no paid re-forecast; --force to override).\n")
    ok = err = skipped = 0
    for i, p in enumerate(posts, 1):
        q = p.get("question") or {}
        typ = q.get("type"); qid = q.get("id")
        title = (p.get("title") or "")[:55]
        if qid in recent:
            skipped += 1
            print(f"[{i:2}/{len(posts)}] SKIP done<{dedup_h}h  {typ:14} {title}")
            continue
        rec = {"question_id": qid, "post_id": p.get("id"), "title": (p.get("title") or "")[:90],
               "type": typ, "provider": PROVIDER, "at": datetime.now(timezone.utc).isoformat()}
        decision = None
        try:
            if typ == "binary":
                qt = api.question_text(p)
                # external market on the SAME event (rare but high-value) → bounded anchor; else none.
                anc = markets.cross_market(p.get("title") or "") if ROUTED else None
                cw = anchor_weight(anc["sim"]) if (anc and USE_EXTERNAL_ANCHOR) else None
                if anc:
                    rec["anchor"] = {"prob": anc["prob"], "sim": round(anc["sim"], 2),
                                     "src": anc["source"], "w": cw, "used": USE_EXTERNAL_ANCHOR}
                anchor_prob = anc["prob"] if (anc and USE_EXTERNAL_ANCHOR) else None
                if ROUTED:   # Opus 4.8 ×N + DEEP agentic research (all Opus/Bedrock); anchor if found
                    out = forecast.forecast_question(qt, crowd=anchor_prob,
                                                     crowd_weight=cw, provider="bedrock",
                                                     ensemble_models=[llm.BEDROCK_DEFAULT_MODEL],
                                                     n=N, deep_research=True)
                    tier = ("opus+deep+anchor:" + anc["source"]) if anchor_prob is not None else "opus+deep"
                else:        # explicit --provider → flat that provider, shallow research
                    out = forecast.forecast_question(qt, crowd=anchor_prob,
                                                     crowd_weight=cw, provider=PROVIDER,
                                                     ensemble_models=MODELS, n=N, with_markets=True)
                    tier = PROVIDER
                prob = out["prob"]; rec["prob"] = prob; rec["tier"] = tier
                rec["reasoning"] = out.get("reasoning", "")[:300]
                rec["quality_flags"] = out.get("quality_flags", [])
                decision = {
                    "platform": "metaculus",
                    "tournament": SLUG,
                    "forecast_type": "binary",
                    "question_id": qid,
                    "post_id": p.get("id"),
                    "title": p.get("title") or "",
                    "route": tier,
                    "provider": PROVIDER,
                    "forecast": prob,
                    "shadows": out.get("shadows"),
                    "calibration": out.get("calibration"),
                    "anchor": rec.get("anchor"),
                    "prompt_hash": out.get("prompt_hash"),
                    "quality_flags": out.get("quality_flags", []),
                    "n_models": out.get("n_models"),
                    "n_samples": out.get("n_samples"),
                }
                disp = f"p={prob:.2f} [{tier}]"
                res, e = (backoff(api.submit_binary, qid, prob) if LIVE else (True, None))
            elif typ == "multiple_choice":
                meta = numeric.question_meta(p)
                out = numeric_forecast.forecast_mc(meta, n=N, provider=PROVIDER, models=MODELS)
                if not out: raise RuntimeError("mc forecaster returned None")
                vec = out["vector"]; rec["option_probs"] = vec
                decision = {
                    "platform": "metaculus",
                    "tournament": SLUG,
                    "forecast_type": "multiple_choice",
                    "question_id": qid,
                    "post_id": p.get("id"),
                    "title": p.get("title") or "",
                    "provider": PROVIDER,
                    "forecast": vec,
                    "n_models": out.get("n_models"),
                    "n_sources": out.get("n_sources"),
                }
                disp = "MC " + ",".join(f"{k[:8]}={v:.2f}" for k, v in list(vec.items())[:4])
                res, e = (backoff(numeric.submit_multiple_choice, qid, vec) if LIVE else (True, None))
            else:  # numeric / discrete / date
                meta = numeric.question_meta(p)
                out = numeric_forecast.forecast_numeric(meta, n=N, provider=PROVIDER, models=MODELS)
                if not out: raise RuntimeError("numeric forecaster returned None")
                rec["percentiles"] = out["percentiles"]
                decision = {
                    "platform": "metaculus",
                    "tournament": SLUG,
                    "forecast_type": typ,
                    "question_id": qid,
                    "post_id": p.get("id"),
                    "title": p.get("title") or "",
                    "provider": PROVIDER,
                    "forecast": out.get("percentiles"),
                    "n_models": out.get("n_models"),
                    "n_sources": out.get("n_sources"),
                }
                valid, msg = numeric.validate_cdf(out["cdf"], len(meta["continuous_range"]))
                disp = f"CDF len={len(out['cdf'])} valid={valid}"
                res, e = (backoff(numeric.submit_cdf, qid, out["cdf"]) if LIVE else (True, None))
        except Exception as ex:
            e = f"{type(ex).__name__}: {ex}"[:200]; disp = "ERR"
        rec["submitted"] = LIVE and (e is None)
        if e:
            rec["error"] = e; err += 1
            print(f"[{i:2}/{len(posts)}] FAIL {typ:14} {title}  -> {e[:70]}")
        else:
            ok += 1
            tag = "OK  " if LIVE else "DRY "
            print(f"[{i:2}/{len(posts)}] {tag} {typ:14} {title}  -> {disp}")
        if decision:
            try:
                decision["submitted"] = rec["submitted"]
                if e:
                    decision["error"] = e
                append_decision(decision)
            except Exception as log_ex:
                print(f"        ledger warn: {type(log_ex).__name__}: {str(log_ex)[:80]}")
        with open(LOG, "a") as f:
            f.write(json.dumps(rec) + "\n")
        if LIVE:
            time.sleep(8)
    print(f"\n{'SUBMITTED' if LIVE else 'DRY-RAN'}: ok={ok} err={err} skipped={skipped} / {len(posts)}")


if __name__ == "__main__":
    main()
