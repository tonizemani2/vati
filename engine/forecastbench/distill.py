"""DeepSeek teacher pass over the residual-on-prior rows — measure cost + yield, mint clean SFT targets.

Two jobs (FORECAST_LLM.md + residual.py): (1) regenerate the SFT *target* as a calibrated house-format
trace that anchors on the crowd prior and adjusts — the antidote to last night's overconfident base traces;
(2) at scale, act as the rejection-sampling teacher: keep a teacher forecast only when it BEATS the crowd
anchor on the known outcome, manufacturing expert-quality targets from data we already have (no scraping).

This `--measure` run is the cheap gate before any full corpus spend: it reports real per-row cost (token
counts) and *yield* — does DeepSeek, given only the question + crowd anchor, beat the crowd Brier the way
the human superforecasters did (0.131 -> 0.084)? If yes, teacher-distill scales; if no, we need real human
targets (Metaculus/GJOpen scrape).

LEAKAGE NOTE: the 2024-07-21 set resolves within ~weeks, inside DeepSeek's training cutoff, so its score
here is an UPPER BOUND (it may recall outcomes). The honest scale corpus uses questions resolving AFTER the
teacher's cutoff — there the teacher is blind and we filter by outcome, which is leak-clean. This batch
measures cost + pipeline, not a deployable teacher skill number.

Run:  python -m engine.forecastbench.distill --measure --limit 56
      python -m engine.forecastbench.distill --measure --limit 56 --keyless   # $0 via DeepInfra+proxy
"""
from __future__ import annotations

import json
import re
import statistics
import sys
import time
from pathlib import Path

from engine import cost, db
from engine.adapters import llm

DATA = Path(__file__).resolve().parents[2] / "data" / "forecastbench"
SRC = DATA / "trainset" / "residual_expert.jsonl"
OUT = DATA / "trainset" / "residual_teacher.jsonl"

SYS = ("You are a careful, calibrated probabilistic forecaster. You are given ONE forecasting question, "
       "the information known as of a stated date, and the current crowd/market probability. Use nothing "
       "from after the stated date. Reason briefly: (1) state what the crowd prior implies; (2) the main "
       "force that should push the probability UP from it; (3) the main force pushing it DOWN; (4) decide "
       "whether to stay near the crowd or adjust, and how far — do not be falsely confident on genuinely "
       "uncertain questions, and avoid 0 and 1. End with exactly one line: 'Probability: 0.NN'.")

# DeepSeek keyed token prices (USD per 1M, cache-miss standard tier); off-peak is ~50-75% cheaper.
PRICE_IN, PRICE_OUT = 0.27, 1.10
PROB_RE = re.compile(r"[Pp]robability\s*[:=]\s*\$?(\d*\.?\d+)")


def _prompt(r: dict) -> str:
    bg = f"\nBackground: {r['background']}" if r.get("background") else ""
    return (f"Question: {r['question']}\n"
            f"Resolution criteria: {r['resolution_criteria']}{bg}\n"
            f"Information as of {r['as_of_date']}.\n"
            f"Current crowd/market probability (the prior to anchor on): {r['crowd_prob']:.2f}\n"
            f"Resolves by {r['resolution_date']}.\n\n"
            f"Reason briefly, then give your calibrated probability of YES.")


def _parse_prob(text: str) -> float | None:
    ms = PROB_RE.findall(text or "")
    if not ms:
        return None
    try:
        p = float(ms[-1])
    except ValueError:
        return None
    return min(0.99, max(0.01, p)) if 0.0 <= p <= 1.0 else None


def measure(limit: int, keyless: bool) -> None:
    rows = [json.loads(l) for l in SRC.open()][:limit]
    conn = db.connect()
    provider = "deepinfra_keyless" if keyless else "deepseek"
    model = "deepseek-ai/DeepSeek-V4-Pro" if keyless else "deepseek-chat"

    out_rows, in_tok, out_tok, fails = [], 0, 0, 0
    t0 = time.time()
    for i, r in enumerate(rows):
        prompt = _prompt(r)
        try:
            txt = llm.complete(conn, prompt, provider=provider, model=model,
                               system=SYS, max_tokens=700, est_cost_cents=0)
        except Exception as e:  # noqa: BLE001
            fails += 1
            print(f"  [{i}] FAIL {type(e).__name__}: {str(e)[:90]}", flush=True)
            continue
        p = _parse_prob(txt)
        in_tok += (len(SYS) + len(prompt)) // 4          # ~4 chars/token estimate
        out_tok += len(txt) // 4
        if p is None:
            fails += 1
            print(f"  [{i}] no prob parsed", flush=True)
            continue
        out_rows.append({**r, "teacher_prob": p, "teacher_trace": txt.strip()})
        print(f"  [{i}] crowd={r['crowd_prob']:.2f} expert={r['expert_prob']:.2f} "
              f"teacher={p:.2f} outcome={r['outcome']}", flush=True)
    conn.commit()
    dt = time.time() - t0

    OUT.write_text("\n".join(json.dumps(x) for x in out_rows) + "\n")
    n = len(out_rows)
    if not n:
        print(f"\nNo rows scored ({fails} fails). provider={provider}")
        return
    tb = statistics.mean((x["teacher_prob"] - x["outcome"]) ** 2 for x in out_rows)
    cb = statistics.mean((x["crowd_prob"] - x["outcome"]) ** 2 for x in out_rows)
    eb = statistics.mean((x["expert_prob"] - x["outcome"]) ** 2 for x in out_rows)
    beats = sum(1 for x in out_rows
                if (x["teacher_prob"] - x["outcome"]) ** 2 < (x["crowd_prob"] - x["outcome"]) ** 2)
    cost_usd = in_tok / 1e6 * PRICE_IN + out_tok / 1e6 * PRICE_OUT

    print(f"\n=== distill --measure: {n} scored, {fails} fails, {dt:.0f}s -> {OUT}")
    print(f"  provider={provider} model={model}")
    print(f"  tokens: in~{in_tok} out~{out_tok}   est cost (keyed std tier): ${cost_usd:.4f}  "
          f"(${cost_usd/n*1000:.3f}/1k rows; off-peak ~half)")
    print(f"  Brier  crowd : {cb:.4f}")
    print(f"  Brier  expert: {eb:.4f}")
    print(f"  Brier  TEACHER: {tb:.4f}   ({'BEATS' if tb < cb else 'LOSES TO'} crowd by {cb-tb:+.4f})")
    print(f"  YIELD: teacher beats crowd on {beats}/{n} = {beats/n:.0%} of rows")
    print("  NOTE: in-cutoff set -> teacher score is an UPPER BOUND (possible recall). Cost + pipeline "
          "are the real takeaways here.\n")


if __name__ == "__main__":
    a = sys.argv
    lim = int(a[a.index("--limit") + 1]) if "--limit" in a else 56
    measure(lim, keyless="--keyless" in a)
