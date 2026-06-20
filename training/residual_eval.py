"""Honest eval for the residual-on-prior model — uses the corpus's OWN system+user prompt (so train and
eval are byte-identical, the discipline the overnight post-mortem stressed) and scores Brier/AUC/ECE on the
leak-clean held-out split, against the prior baseline the model was handed.

    .mlx-venv/bin/python training/residual_eval.py --adapter out/mlx-residual-sft --limit 204
    .mlx-venv/bin/python training/residual_eval.py --adapter "" --limit 204     # raw baseline
"""
from __future__ import annotations

import argparse
import json
import re
import statistics

from mlx_lm import generate, load
from mlx_lm.sample_utils import make_sampler

PROB_RE = re.compile(r"[Pp]robabilit(?:y|ies)\s*[:=]\s*\$?(\d*\.?\d+)")


def parse_prob(text):
    ms = PROB_RE.findall(text or "")
    if not ms:
        # fallback: last bare 0.NN
        ms = re.findall(r"\b(0?\.\d+)\b", text or "")
    if not ms:
        return None
    try:
        p = float(ms[-1])
    except ValueError:
        return None
    return min(0.99, max(0.01, p)) if 0 <= p <= 1 else None


def auc(ps, ys):
    pos = [p for p, y in zip(ps, ys) if y == 1]
    neg = [p for p, y in zip(ps, ys) if y == 0]
    if not pos or not neg:
        return None
    w = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return w / (len(pos) * len(neg))


def ece(ps, ys, bins=10):
    tot, acc = 0, 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, p in enumerate(ps) if (lo <= p < hi) or (b == bins - 1 and p == hi)]
        if not idx:
            continue
        acc += len(idx) * abs(statistics.mean(ps[i] for i in idx) - statistics.mean(ys[i] for i in idx))
        tot += len(idx)
    return acc / tot if tot else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="mlx-community/Qwen3-0.6B-4bit")
    ap.add_argument("--adapter", default="", help="LoRA adapter dir; empty = raw base")
    ap.add_argument("--data", default="data/forecastbench/trainset/residual_eval_sub.jsonl")
    ap.add_argument("--limit", type=int, default=204)
    ap.add_argument("--max-tokens", type=int, default=200)
    args = ap.parse_args()

    model, tok = load(args.model, adapter_path=(args.adapter or None))
    sampler = make_sampler(temp=0.0)                       # greedy = reproducible
    rows = [json.loads(l) for l in open(args.data)][: args.limit]

    ps, priors, tgts, ys, kinds, nparse = [], [], [], [], [], 0
    for i, r in enumerate(rows):
        msgs = [m for m in r["messages"] if m["role"] in ("system", "user")]
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
                                         enable_thinking=False)
        text = generate(model, tok, prompt, max_tokens=args.max_tokens, sampler=sampler, verbose=False)
        p = parse_prob(text)
        nparse += p is not None
        ps.append(p if p is not None else float(r["prior"]))   # unparseable -> fall back to prior
        priors.append(float(r["prior"])); tgts.append(float(r["target"]))
        ys.append(int(r["outcome"])); kinds.append(r["kind"])
        if (i + 1) % 20 == 0:
            print(f"  ...{i+1}/{len(rows)}", flush=True)

    def blk(sel):
        idx = [i for i in range(len(ys)) if sel(kinds[i])]
        if not idx:
            return None
        mp = [ps[i] for i in idx]; pr = [priors[i] for i in idx]; yy = [ys[i] for i in idx]
        return (len(idx),
                statistics.mean((a - b) ** 2 for a, b in zip(mp, yy)),
                statistics.mean((a - b) ** 2 for a, b in zip(pr, yy)),
                ece(mp, yy), auc(mp, yy))

    label = args.adapter or "RAW base"
    print(f"\n=== residual eval · {args.model} · adapter={label} · n={len(ys)} "
          f"· parsed {nparse}/{len(ys)} ===")
    print(f"  {'block':8} {'n':>4}  {'Brier model':>11}  {'Brier prior':>11}  {'ECE':>6}  {'AUC':>5}")
    for name, sel in [("ALL", lambda k: True), ("numeric", lambda k: k == "dataset"),
                      ("human", lambda k: k == "human")]:
        b = blk(sel)
        if b:
            n, bm, bp, e, a = b
            print(f"  {name:8} {n:>4}  {bm:>11.4f}  {bp:>11.4f}  {e:>6.3f}  "
                  f"{(a if a is not None else 0):>5.3f}")
    print("  (model beats its handed prior iff Brier model < Brier prior)\n")


if __name__ == "__main__":
    main()
