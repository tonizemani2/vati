"""Assemble the unified residual-on-prior training corpus + a leak-clean eval split.

One schema, three layers, one idea (FORECAST_LLM.md + the 2026-06-14 findings):
  every row = (point-in-time context, a PRIOR anchor the model also gets at test time, a TARGET that is
  at least as good as the prior, the outcome). The model is trained to anchor on the prior and adjust —
  the move that broke last night when there was no prior in the data at all.

Layers:
  1. NUMERIC core  (dataset_calibrated.jsonl) — leak-clean by construction (unmemorizable series Qs).
     prior = quant model_prob (AUC 0.736 > raw-8B 0.668); target = OOF-isotonic calibrated value.
     This is the discrimination trainer + the GRPO-Brier RL set.
  2. MARKET policy (market_questions.jsonl, crowd.py-enriched) — prior = crowd anchor; target = OOF-
     isotonic calibrated crowd (population favorite-longshot correction — a leak-safe edge, NOT row-level
     outcome recall). Teaches calibrated crowd-anchor-then-adjust.
  3. HUMAN gold   (residual_expert.jsonl, 56) — prior = crowd; target = real superforecaster median
     (the only measured source that BEATS the crowd, 0.084 vs 0.131); trace = real human reasoning.

Leak-clean eval split: market/human rows go to EVAL only if they resolve after the base cutoff
(2024-10-01) so the model cannot have memorized them; numeric rows are split by id-hash (unmemorizable,
so a random hold-out is honest). Train Brier/AUC/ECE is vanity; the eval block is the only honest gate.

Run:  python -m engine.forecastbench.assemble        # build corpus + split + report
"""
from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path

from .calib import _fit_map, _apply, _brier, _ece, _auc

DATA = Path(__file__).resolve().parents[2] / "data" / "forecastbench" / "trainset"
NUMERIC = DATA / "dataset_calibrated.jsonl"
MARKET = DATA / "market_questions.jsonl"
HUMAN = DATA / "residual_expert.jsonl"
OUT_TRAIN = DATA / "residual_train.jsonl"
OUT_EVAL = DATA / "residual_eval.jsonl"
CUTOFF = "2024-10-01"

SYS = ("You are a careful, calibrated probabilistic forecaster. You are given ONE question, the information "
       "known as of a stated date, and a PRIOR probability (a mechanical model or the crowd/market). Use "
       "nothing from after the stated date. Reason briefly: (1) what the prior implies; (2) what the "
       "evidence in the context adds or subtracts; (3) decide how far to move off the prior — stay near it "
       "unless the context justifies otherwise, avoid 0 and 1, and do not be falsely confident on genuinely "
       "uncertain questions. End with exactly one line: 'Probability: 0.NN'.")


def _pp(p: float) -> str:
    return f"{min(0.99, max(0.01, p)):.2f}"


def _numeric_trace(r: dict) -> str:
    prior, tgt = r["model_prob"], r["calibrated_target"]
    move = ("a touch higher" if tgt > prior + 0.02 else
            "a touch lower" if tgt < prior - 0.02 else "essentially unchanged")
    return (f"The reference model reads the series history and puts P(YES) near {_pp(prior)}. Checked "
            f"against how series at this level and trend have actually resolved, that anchor is best left "
            f"{move}. Probability: {_pp(tgt)}")


def _market_trace(r: dict, tgt: float) -> str:
    prior = r["crowd_prob"]
    return (f"The crowd/market currently prices this at {_pp(prior)}. Markets at this level historically "
            f"resolve YES about {_pp(tgt)} of the time, and the as-of context gives no decisive reason to "
            f"override the crowd. Probability: {_pp(tgt)}")


def _user(question, rc, context, prior, as_of, kind):
    # Residual-on-prior leans on the PRIOR number, not the raw series — and a small model can't read a
    # 600-token series anyway. Keep only the recent tail of the context (most-recent obs sit at the end),
    # which keeps sequences short (fast training + the model anchors on the prior, by design).
    if context and len(context) > 340:
        context = "..." + context[-320:]
    ctx = f"\nContext: {context}" if context else ""
    label = "Mechanical model prior" if kind == "dataset" else "Crowd/market prior"
    return (f"Question: {question}\nResolution criteria: {rc}\nInformation as of {as_of}.{ctx}\n"
            f"{label} (anchor): {_pp(prior)}\n\nReason briefly, then give your calibrated probability of YES.")


def _row(kind, source, qid, rdate, prior, target, outcome, msgs):
    return {"kind": kind, "source": source, "id": str(qid), "resolution_date": rdate,
            "prior": round(prior, 4), "target": round(target, 4), "outcome": int(outcome),
            "messages": msgs}


def _is_eval(kind: str, qid: str, rdate: str | None) -> bool:
    if kind == "dataset":
        return int(hashlib.md5(str(qid).encode()).hexdigest(), 16) % 10 == 0
    return bool(rdate) and rdate >= CUTOFF        # market/human: leak-clean = post-cutoff only


def build() -> dict:
    train, ev = [], []

    # 1. NUMERIC core
    n_num = 0
    if NUMERIC.exists():
        for line in NUMERIC.open():
            r = json.loads(line)
            if r.get("calibrated_target") is None:
                continue
            msgs = [{"role": "system", "content": SYS},
                    {"role": "user", "content": _user(r["question"], r["resolution_criteria"],
                                                       r.get("context"), r["model_prob"],
                                                       r.get("as_of_date"), "dataset")},
                    {"role": "assistant", "content": _numeric_trace(r)}]
            row = _row("dataset", r.get("source"), r["id"], r.get("resolution_date"),
                       r["model_prob"], r["calibrated_target"], r["outcome"], msgs)
            (ev if _is_eval("dataset", r["id"], r.get("resolution_date")) else train).append(row)
            n_num += 1

    # 2. MARKET policy — calibrate the crowd prior OOF over rows crowd.py has enriched
    n_mkt = 0
    if MARKET.exists():
        mrows = []
        for line in MARKET.open():
            r = json.loads(line)
            if r.get("crowd_prob") is not None and r.get("outcome") in (0, 1):
                mrows.append(r)
        if len(mrows) >= 50:
            k = 5
            folds = [mrows[i::k] for i in range(k)]
            cal = {}
            for fi in range(k):
                tr = [r for fj in range(k) if fj != fi for r in folds[fj]]
                knots = _fit_map([(r["crowd_prob"], r["outcome"]) for r in tr])
                for r in folds[fi]:
                    cal[id(r)] = _apply(knots, r["crowd_prob"])
            for r in mrows:
                tgt = cal[id(r)]
                msgs = [{"role": "system", "content": SYS},
                        {"role": "user", "content": _user(r["question"], r["resolution_criteria"],
                                                           r.get("context"), r["crowd_prob"],
                                                           r.get("as_of_date"), "market")},
                        {"role": "assistant", "content": _market_trace(r, tgt)}]
                row = _row("market", r.get("source"), r["id"], r.get("resolution_date"),
                           r["crowd_prob"], tgt, r["outcome"], msgs)
                (ev if _is_eval("market", r["id"], r.get("resolution_date")) else train).append(row)
                n_mkt += 1

    # 3. HUMAN gold — real superforecaster target + real reasoning
    n_hum = 0
    if HUMAN.exists():
        for line in HUMAN.open():
            r = json.loads(line)
            traces = r.get("expert_traces") or []
            reasoning = next((t["reasoning"] for t in traces if t.get("reasoning")), "")
            tgt = r["expert_prob"]
            trace = ((reasoning[:700] + " " if reasoning else "")
                     + f"Probability: {_pp(tgt)}")
            msgs = [{"role": "system", "content": SYS},
                    {"role": "user", "content": _user(r["question"], r["resolution_criteria"],
                                                       r.get("background"), r["crowd_prob"],
                                                       r.get("as_of_date"), "market")},
                    {"role": "assistant", "content": trace}]
            row = _row("human", r.get("source"), r["id"], r.get("resolution_date"),
                       r["crowd_prob"], tgt, r["outcome"], msgs)
            row["gold"] = True
            (ev if _is_eval("market", r["id"], r.get("resolution_date")) else train).append(row)
            n_hum += 1

    OUT_TRAIN.write_text("".join(json.dumps(r) + "\n" for r in train))
    OUT_EVAL.write_text("".join(json.dumps(r) + "\n" for r in ev))

    # eval-block report: target vs prior on the HELD-OUT, leak-clean rows = the honest gate preview
    def block(rows, kind=None):
        rs = [r for r in rows if kind is None or r["kind"] == kind]
        if not rs:
            return None
        ys = [r["outcome"] for r in rs]
        return {"n": len(rs),
                "brier_prior": round(_brier([r["prior"] for r in rs], ys), 4),
                "brier_target": round(_brier([r["target"] for r in rs], ys), 4),
                "ece_prior": round(_ece([r["prior"] for r in rs], ys), 4),
                "ece_target": round(_ece([r["target"] for r in rs], ys), 4),
                "auc_target": round(_auc([r["target"] for r in rs], ys) or 0, 4)}

    print(f"\n=== unified corpus: train={len(train)}  eval={len(ev)}")
    print(f"  layers: numeric={n_num}  market={n_mkt}  human_gold={n_hum}")
    print(f"  -> {OUT_TRAIN.name} / {OUT_EVAL.name}")
    print("\n  EVAL block (leak-clean held-out) — target vs prior (the honest gate preview):")
    for name, kind in [("ALL", None), ("numeric", "dataset"), ("market", "market"), ("human", "human")]:
        b = block(ev, kind)
        if b:
            print(f"   {name:8} n={b['n']:5}  Brier prior={b['brier_prior']} -> target={b['brier_target']}"
                  f"   ECE {b['ece_prior']} -> {b['ece_target']}   AUC={b['auc_target']}")
    return {"train": len(train), "eval": len(ev), "numeric": n_num, "market": n_mkt, "human": n_hum}


if __name__ == "__main__":
    build()
