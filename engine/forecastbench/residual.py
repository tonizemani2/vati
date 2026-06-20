"""Residual-on-prior training set — the fix for the calibration-tax failure.

Why this exists (read FORECAST_LLM.md + the 2026-06-14 diagnosis first). The overnight SFT/GRPO run
did NOT lose knowledge: discrimination (AUC) was unchanged (raw 0.668 -> 0.648, within noise). It lost
CALIBRATION — training on confident LLM-generated traces taught the model to sound certain, and Brier
murders overconfidence. The root cause in the DATA: `crowd_prob` is unpopulated on every market row, so
the model never once saw a real expert/crowd anchor that diverged from the mechanical quant prior. There
was no discrimination signal to distill. You cannot distill skill the teacher does not possess.

The fix is `residual-on-prior`: give the model the cheap, test-time-available prior (the crowd anchor it
is literally handed at ForecastBench freeze time) and train it on a TARGET that beats that prior — a real
superforecaster forecast, with the superforecaster's own reasoning. The model learns *when and which way*
to adjust off the crowd, which is exactly the discrimination the base lacks, while the soft expert target
keeps it calibrated.

The richest such signal was already on disk, unused: `human_super_2024-07-21.json` = 7,693 real
superforecaster forecasts WITH reasoning + searches, over ~189 ForecastBench questions, each question
carrying its crowd anchor (`freeze_datetime_value`) and a known outcome (`r_2024-07-21.json`). No scraping.

Leak-safety: the crowd anchor and the expert forecast are both strictly ex-ante (made at the freeze, before
resolution). The outcome is used only as the SCORING label (the gate below + any later RL reward), never as
a model input. This mirrors the live submission pipeline exactly (question + freeze anchor in, prob out).

THE GATE (run this first): the superforecaster aggregate must beat the crowd anchor on Brier here. If it
does not, this source adds no discrimination and we pivot to Manifold/Metaculus. The builder prints it.

Run:  python -m engine.forecastbench.residual            # build + print the gate
      python -m engine.forecastbench.residual --out PATH
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data" / "forecastbench"
HUMAN = DATA / "human_super_2024-07-21.json"
QFILE = DATA / "q_2024-07-21-human.json"
RFILE = DATA / "r_2024-07-21.json"
OUT_DEFAULT = DATA / "trainset" / "residual_expert.jsonl"


def _load_resolutions() -> dict:
    """(id, resolution_date) -> resolved_to, for string-id (non-combo) questions."""
    raw = json.loads(RFILE.read_text())
    rows = raw if isinstance(raw, list) else (raw.get("resolutions") or
            next(v for v in raw.values() if isinstance(v, list)))
    idx: dict = {}
    by_id: dict = defaultdict(list)
    for r in rows:
        if not isinstance(r.get("id"), str):
            continue                                    # list-id = numeric combo, handled elsewhere
        rd = r.get("resolution_date")
        try:
            out = float(r.get("resolved_to"))
        except (TypeError, ValueError):
            continue
        idx[(r["id"], rd)] = out
        by_id[r["id"]].append((rd, out))
    return idx, by_id


def _load_questions() -> dict:
    qs = json.loads(QFILE.read_text())["questions"]
    out = {}
    for q in qs:
        if isinstance(q.get("id"), str):
            out[q["id"]] = q
    return out


# Only true prediction-market / crowd sources carry a real P(YES) crowd anchor in `freeze_datetime_value`.
# Dataset sources (acled, dbnomics, fred, yfinance, wikipedia) put a SERIES LEVEL there, not a probability
# — e.g. acled's value is 1.0 by construction, which is not a crowd belief. Treating those as a crowd prior
# is the bug that faked a 6x Brier gap; restrict to genuine markets.
MARKET_SOURCES = {"manifold", "metaculus", "polymarket", "infer", "betfair", "predictit", "rcp"}


def _crowd_anchor(q: dict) -> float | None:
    """The crowd prob handed to forecasters at the freeze, if it is a genuine market P(YES) in [0,1]."""
    if (q.get("source") or "").lower() not in MARKET_SOURCES:
        return None
    v = q.get("freeze_datetime_value")
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if 0.0 <= f <= 1.0 else None


def build(out_path: Path = OUT_DEFAULT) -> dict:
    forecasts = json.loads(HUMAN.read_text())["forecasts"]
    ridx, rby_id = _load_resolutions()
    qidx = _load_questions()

    # group superforecaster forecasts by (id, resolution_date); null date broadcasts to the market's
    # single resolution.
    groups: dict = defaultdict(list)
    for f in forecasts:
        qid = f.get("id")
        if not isinstance(qid, str):
            continue
        try:
            p = float(f["forecast"])
        except (TypeError, ValueError, KeyError):
            continue
        rd = f.get("resolution_date")
        if rd is None:
            # market forecast with no explicit horizon -> attach to each known resolution of this id
            for rrd, _ in rby_id.get(qid, [(None, None)]):
                groups[(qid, rrd)].append((p, f))
        else:
            groups[(qid, rd)].append((p, f))

    rows = []
    skipped = defaultdict(int)
    for (qid, rd), fcs in groups.items():
        q = qidx.get(qid)
        if q is None:
            skipped["no_question"] += 1
            continue
        outcome = ridx.get((qid, rd))
        if outcome is None or outcome not in (0.0, 1.0):
            skipped["no_binary_outcome"] += 1
            continue
        crowd = _crowd_anchor(q)
        if crowd is None:
            skipped["no_crowd_anchor"] += 1
            continue
        probs = [p for p, _ in fcs]
        expert = statistics.median(probs)
        # rank reasonings: richest first (length + #searches) — the cheap "reorder" before DeepSeek refines
        ranked = sorted(
            ({"forecast": p,
              "reasoning": (f.get("reasoning") or "").strip(),
              "searches": f.get("searches") or [],
              "user_id": f.get("user_id")}
             for p, f in fcs),
            key=lambda r: (len(r["reasoning"]), len(r["searches"])), reverse=True)
        rows.append({
            "id": qid,
            "source": q.get("source"),
            "kind": "market",
            "question": q.get("question"),
            "resolution_criteria": q.get("resolution_criteria"),
            "background": (q.get("background") or "")[:600],
            "as_of_date": (q.get("freeze_datetime") or "")[:10],
            "resolution_date": rd,
            "crowd_prob": round(crowd, 4),
            "expert_prob": round(expert, 4),
            "n_experts": len(probs),
            "expert_spread": round(statistics.pstdev(probs), 4) if len(probs) > 1 else 0.0,
            "expert_traces": ranked,
            "outcome": int(outcome),
        })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    return _gate(rows, dict(skipped), out_path)


def _brier(p: float, y: int) -> float:
    return (p - y) ** 2


def _auc(pairs: list[tuple[float, int]]) -> float | None:
    pos = [p for p, y in pairs if y == 1]
    neg = [p for p, y in pairs if y == 0]
    if not pos or not neg:
        return None
    wins = ties = 0
    for a in pos:
        for b in neg:
            if a > b:
                wins += 1
            elif a == b:
                ties += 1
    return (wins + 0.5 * ties) / (len(pos) * len(neg))


def _gate(rows: list, skipped: dict, out_path: Path) -> dict:
    n = len(rows)
    if not n:
        print("NO ROWS BUILT. skipped:", skipped)
        return {"n": 0}
    cb = statistics.mean(_brier(r["crowd_prob"], r["outcome"]) for r in rows)
    eb = statistics.mean(_brier(r["expert_prob"], r["outcome"]) for r in rows)
    # 50/50 blend = the simplest "adjust off crowd" baseline
    bb = statistics.mean(_brier(0.5 * r["crowd_prob"] + 0.5 * r["expert_prob"], r["outcome"]) for r in rows)
    crowd_auc = _auc([(r["crowd_prob"], r["outcome"]) for r in rows])
    expert_auc = _auc([(r["expert_prob"], r["outcome"]) for r in rows])
    divergence = statistics.mean(abs(r["expert_prob"] - r["crowd_prob"]) for r in rows)
    base = statistics.mean(r["outcome"] for r in rows)

    print(f"\n=== residual_expert dataset: {n} rows -> {out_path}")
    print(f"  skipped: {skipped}")
    print(f"  base rate (YES): {base:.3f}   mean experts/question: "
          f"{statistics.mean(r['n_experts'] for r in rows):.1f}")
    print(f"  mean |expert - crowd| divergence: {divergence:.4f}  (the residual signal magnitude)")
    print("\n  --- THE GATE: does the superforecaster aggregate beat the crowd anchor? ---")
    print(f"  Brier  crowd-anchor : {cb:.4f}")
    print(f"  Brier  expert-median: {eb:.4f}   ({'BEATS' if eb < cb else 'LOSES TO'} crowd by {cb-eb:+.4f})")
    print(f"  Brier  50/50 blend  : {bb:.4f}")
    print(f"  AUC    crowd-anchor : {crowd_auc}")
    print(f"  AUC    expert-median: {expert_auc}")
    verdict = ("PASS — experts add discrimination over the crowd; this is real residual signal."
               if eb < cb else
               "FAIL — experts do not beat the crowd here; pivot to Manifold/Metaculus.")
    print(f"\n  VERDICT: {verdict}\n")
    return {"n": n, "crowd_brier": cb, "expert_brier": eb, "blend_brier": bb,
            "crowd_auc": crowd_auc, "expert_auc": expert_auc, "divergence": divergence,
            "pass": eb < cb}


if __name__ == "__main__":
    out = OUT_DEFAULT
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])
    build(out)
