"""Phase 1 eval — the ONLY honest number: Brier / AUC / calibration on the LEAK-FREE held-out set.

grpo_eval.jsonl holds only questions resolving AFTER the base-model cutoff, so the model could not have
known the outcomes (engine/forecastbench/corpus.py). Train metrics lie (parametric leakage); this does not.
Compares the model against the simple baseline carried in each row (quant model_prob, else crowd, else 0.5).

    python training/eval.py --model out/grpo-qwen3-8b --data data/forecastbench/trainset/grpo_eval.jsonl
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from common import SYSTEM, load_jsonl, parse_prob, user_prompt


def auc(ps, ys):
    """Mann-Whitney AUC (discrimination) without sklearn. None if only one class present."""
    pos = [p for p, y in zip(ps, ys) if y == 1]
    neg = [p for p, y in zip(ps, ys) if y == 0]
    if not pos or not neg:
        return None
    wins = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return wins / (len(pos) * len(neg))


def _logit(p):
    p = min(1 - 1e-6, max(1e-6, p))
    import math
    return math.log(p / (1 - p))


def temp_scale(ps, ys):
    """Honest calibration diagnostic for the GRPO-overconfidence failure mode (arXiv 2508.11800).
    Fit a single temperature T on HALF the eval set (grid search minimising Brier), report the
    calibrated Brier on the OTHER half so the number isn't fit-on-itself. T>1 ⇒ the model was
    OVERCONFIDENT and softening toward 0.5 helps (the signal to raise grpo.py's beta); T≈1 ⇒ already
    calibrated; T<1 ⇒ under-confident. Returns (best_T, raw_brier_holdout, cal_brier_holdout)."""
    import math
    idx = list(range(len(ps)))
    fit, rep = idx[0::2], idx[1::2]
    if not fit or not rep:
        return None, None, None
    def brier_at(T, sub):
        b = 0.0
        for i in sub:
            q = 1 / (1 + math.exp(-_logit(ps[i]) / T))
            b += (q - ys[i]) ** 2
        return b / len(sub)
    best_T = min((x / 100 for x in range(50, 301, 5)), key=lambda T: brier_at(T, fit))
    return best_T, brier_at(1.0, rep), brier_at(best_T, rep)


def calibration(ps, ys, bins=10):
    buckets = defaultdict(lambda: [0, 0.0, 0.0])   # count, sum_p, sum_y
    for p, y in zip(ps, ys):
        b = min(bins - 1, int(p * bins))
        buckets[b][0] += 1; buckets[b][1] += p; buckets[b][2] += y
    return {b: (c, sp / c, sy / c) for b, (c, sp, sy) in sorted(buckets.items())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="out/grpo-qwen3-8b")
    ap.add_argument("--data", default="data/forecastbench/trainset/grpo_eval.jsonl")
    ap.add_argument("--max-seq", type=int, default=4096)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dump-preds", default="", help="write per-row {id,prob,resolution_date,outcome} "
                    "JSONL → feeds engine.forecastbench.ensemble as the LLM column (the decorrelation / "
                    "marginal-ensemble-value number) and submit.py as a blend input. The bridge from "
                    "this eval to the north-star artifact.")
    args = ap.parse_args()

    rows = load_jsonl(args.data)
    if args.limit:
        rows = rows[:args.limit]
    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"   # decoder-only batched generate: left-pad so the slice below is exact
    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.bfloat16, device_map="auto")
    model.eval()

    model_ps, base_ps, ys, dom, kinds, horizons = [], [], [], [], [], []
    pred_rows = []
    for i in range(0, len(rows), args.batch):
        chunk = rows[i:i + args.batch]
        # enable_thinking=False: match the non-thinking SFT/GRPO contract (no <think> block), so the
        # model spends its budget on the visible answer + the 'Probability:' line, not a reasoning trace
        # that truncates before it. 1024 new tokens = the same headroom as grpo.py's completion length.
        prompts = [tok.apply_chat_template(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_prompt(r)}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False) for r in chunk]
        enc = tok(prompts, return_tensors="pt", padding=True, truncation=True,
                  max_length=args.max_seq - 1024).to(model.device)
        with torch.no_grad():
            # Greedy (do_sample=False): the eval Brier is the headline number, so it must be the model's
            # single best answer and be REPRODUCIBLE. Sampling at temp 0.7 drew one random probability per
            # question → injected decode noise into the calibration curve and made re-runs disagree.
            gen = model.generate(**enc, max_new_tokens=1024, do_sample=False,
                                 pad_token_id=tok.pad_token_id)
        outs = tok.batch_decode(gen[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)
        for r, text in zip(chunk, outs):
            p = parse_prob(text)
            if p is None:
                p = 0.5
            base = r.get("model_prob")
            if base is None:
                base = r.get("crowd_prob")
            if base is None:
                base = 0.5
            model_ps.append(p); base_ps.append(float(base)); ys.append(int(r["outcome"]))
            dom.append(r.get("domain"))
            kinds.append(r.get("kind") or ("market" if r.get("source") in
                         ("manifold", "metaculus", "polymarket", "infer") else "dataset"))
            horizons.append(r.get("horizon_days"))
            if args.dump_preds:
                pred_rows.append({"id": r["id"], "prob": round(p, 6),
                                  "resolution_date": r.get("resolution_date"), "outcome": int(r["outcome"])})
        print(f"  ...{min(i+args.batch, len(rows))}/{len(rows)}", flush=True)

    if args.dump_preds:
        with open(args.dump_preds, "w") as f:
            for pr in pred_rows:
                f.write(json.dumps(pr) + "\n")
        print(f"  dumped {len(pred_rows)} predictions → {args.dump_preds} "
              f"(feed: python -m engine.forecastbench.ensemble --pred llm={args.dump_preds})")

    n = len(ys)
    brier = sum((p - y) ** 2 for p, y in zip(model_ps, ys)) / n
    base_brier = sum((p - y) ** 2 for p, y in zip(base_ps, ys)) / n
    print(f"\n=== LEAK-FREE EVAL · n={n} ===")
    print(f"  model   Brier {brier:.4f} | AUC {auc(model_ps, ys)}")
    print(f"  baseline Brier {base_brier:.4f}  (Δ {base_brier - brier:+.4f}; positive = model beats baseline)")
    T, raw_h, cal_h = temp_scale(model_ps, ys)
    if T is not None:
        verdict = ("OVERCONFIDENT — raise grpo.py beta" if T > 1.15 else
                   "under-confident" if T < 0.87 else "well-calibrated")
        print(f"  calibration diag: best T={T:.2f} ({verdict}); holdout Brier {raw_h:.4f} raw "
              f"→ {cal_h:.4f} temp-scaled (Δ {raw_h - cal_h:+.4f} = calibration headroom)")
    print("  calibration (bucket: n, mean_p, emp_rate):")
    for b, (c, mp, er) in calibration(model_ps, ys).items():
        print(f"    [{b/10:.1f},{(b+1)/10:.1f}) n={c:4d}  p̄={mp:.2f}  emp={er:.2f}")
    # By KIND — the thesis is "win on the dataset half"; this is where we prove (or disprove) it.
    # Reports model vs baseline Brier separately for market and dataset so the claim is auditable.
    print("  Brier by kind (model vs baseline — the dataset half is where bots beat supers):")
    by_kind = defaultdict(lambda: [0, 0.0, 0.0])
    for p, b, y, k in zip(model_ps, base_ps, ys, kinds):
        by_kind[k][0] += 1; by_kind[k][1] += (p - y) ** 2; by_kind[k][2] += (b - y) ** 2
    for k, (c, sm, sb) in sorted(by_kind.items()):
        print(f"    {k:10s} n={c:5d}  model {sm/c:.4f}  baseline {sb/c:.4f}  Δ {(sb-sm)/c:+.4f}")
    # By HORIZON bucket — short-horizon structural questions are our sweet spot ([[predictability-ceiling]]).
    def hbucket(h):
        if h is None: return "n/a"
        return "≤30d" if h <= 30 else "≤90d" if h <= 90 else "≤365d" if h <= 365 else ">365d"
    by_h = defaultdict(lambda: [0, 0.0])
    for p, y, h in zip(model_ps, ys, horizons):
        by_h[hbucket(h)][0] += 1; by_h[hbucket(h)][1] += (p - y) ** 2
    order = {"≤30d": 0, "≤90d": 1, "≤365d": 2, ">365d": 3, "n/a": 4}
    print("  Brier by horizon:")
    for hb in sorted(by_h, key=lambda x: order.get(x, 9)):
        c, s = by_h[hb]
        print(f"    {hb:8s} n={c:5d}  Brier {s/c:.4f}")
    by_dom = defaultdict(lambda: [0, 0.0])
    for p, y, d in zip(model_ps, ys, dom):
        by_dom[d][0] += 1; by_dom[d][1] += (p - y) ** 2
    print("  Brier by domain:")
    for d, (c, s) in sorted(by_dom.items(), key=lambda kv: -kv[1][0]):
        print(f"    {d:22s} n={c:4d}  Brier {s/c:.4f}")


if __name__ == "__main__":
    main()
