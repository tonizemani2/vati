"""Leak-free eval for the Mac smoke test: Brier / AUC on grpo_eval.jsonl via mlx-lm generation.

Loads the base model + the trained LoRA adapter, generates one forecast per question, parses with
the PRODUCTION parser (common.parse_prob), and scores Brier/AUC against the (post-cutoff, leak-free)
outcomes. Mirrors training/eval.py but on MLX. Smoke-scale — pass --limit.

    python training/mlx_eval.py --model mlx-community/Qwen3-1.7B-4bit --adapter out/mlx-grpo --limit 100

At 1.7B the Brier is NOT the point (the model is a throwaway). A sane number in ~[0.2,0.4] with
parseable outputs = the plumbing (prompt → generate → parse → score) is sound for the real 8B run.
"""
from __future__ import annotations

import argparse

from mlx_lm import generate, load

from common import SYSTEM, load_jsonl, parse_prob, user_prompt

D = "data/forecastbench/trainset"


def auc(ps, ys):
    """Mann-Whitney AUC (discrimination); None if only one class present."""
    pos = [p for p, y in zip(ps, ys) if y == 1]
    neg = [p for p, y in zip(ps, ys) if y == 0]
    if not pos or not neg:
        return None
    wins = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return wins / (len(pos) * len(neg))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="mlx-community/Qwen3-1.7B-4bit")
    ap.add_argument("--adapter", default="out/mlx-grpo", help="LoRA adapter dir; empty = base model")
    ap.add_argument("--data", default=f"{D}/grpo_eval.jsonl")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--max-tokens", type=int, default=1024)
    args = ap.parse_args()

    model, tok = load(args.model, adapter_path=(args.adapter or None))

    rows = load_jsonl(args.data)[: args.limit]
    ps, base_ps, ys = [], [], []
    for i, r in enumerate(rows):
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": user_prompt(r)}]
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
                                         enable_thinking=False)
        text = generate(model, tok, prompt, max_tokens=args.max_tokens, verbose=False)
        p = parse_prob(text)
        if p is None:
            p = 0.5
        base = r.get("model_prob") or r.get("crowd_prob") or 0.5
        ps.append(p); base_ps.append(float(base)); ys.append(int(float(r["outcome"])))
        print(f"  ...{i+1}/{len(rows)}  p={p:.2f} y={ys[-1]}", flush=True)

    n = len(ys)
    brier = sum((p - y) ** 2 for p, y in zip(ps, ys)) / n
    base_brier = sum((p - y) ** 2 for p, y in zip(base_ps, ys)) / n
    print(f"\n=== LEAK-FREE SMOKE EVAL · n={n} ===")
    print(f"  model    Brier {brier:.4f} | AUC {auc(ps, ys)}")
    print(f"  baseline Brier {base_brier:.4f}  (Δ {base_brier - brier:+.4f}; +ve = model beats baseline)")
    print("  (smoke test: parseable outputs + a sane Brier = plumbing OK; capability is NOT the point at 1.7B)")


if __name__ == "__main__":
    main()
