"""Convert the real ForecastBench corpus → mlx-lm-lora data dirs for the Mac plumbing smoke test.

The smoke test (training/MLX.md) runs the full SFT→GRPO→eval loop on a tiny SAME-FAMILY model
(Qwen3-1.7B) on an 8GB Mac, to validate the data/reward/parser plumbing for $0 before renting a GPU.
Reuses the PRODUCTION helpers in common.py so the test exercises the real prompt + I/O contract,
not a re-implementation.

    python training/mlx_convert.py --grpo-limit 200          # from the training/ dir or repo root

Writes (under data/forecastbench/trainset/):
  mlx_sft/{train,valid}.jsonl   chat format: {"messages":[system,user,assistant]}  (mlx-lm reads only this)
  mlx_grpo/{train,valid}.jsonl  {"prompt","answer","system"}  (reward parses completion, scores vs answer)
"""
from __future__ import annotations

import argparse
import json
import os
import random

from common import SYSTEM, load_jsonl, user_prompt

D = "data/forecastbench/trainset"


def _sample(rows, limit):
    """Seeded shuffle THEN truncate — the corpus is grouped by source, so a raw head() can be
    single-class (e.g. an all-YES numeric block), which would make the Brier reward undiscriminating."""
    rows = list(rows)
    random.Random(0).shuffle(rows)
    return rows[:limit] if limit else rows


def _write_split(rows, out_dir, valid_frac=0.1):
    os.makedirs(out_dir, exist_ok=True)
    n_valid = max(1, int(len(rows) * valid_frac)) if len(rows) > 1 else 0
    valid, train = rows[:n_valid], rows[n_valid:]
    for name, part in (("train", train), ("valid", valid)):
        with open(os.path.join(out_dir, f"{name}.jsonl"), "w") as f:
            for r in part:
                f.write(json.dumps(r) + "\n")
    return len(train), len(valid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sft-in", default=f"{D}/sft_market.jsonl")
    ap.add_argument("--grpo-in", default=f"{D}/grpo_train.jsonl")
    ap.add_argument("--sft-limit", type=int, default=0, help="0 = all")
    ap.add_argument("--grpo-limit", type=int, default=200, help="keep the smoke test fast/light")
    args = ap.parse_args()

    # --- SFT: chat format (mlx-lm autodetects "messages") ---
    sft = _sample(load_jsonl(args.sft_in), args.sft_limit)
    sft_rows = [{"messages": r["messages"]} for r in sft if r.get("messages")]
    nt, nv = _write_split(sft_rows, f"{D}/mlx_sft")
    print(f"SFT  → {D}/mlx_sft   train={nt} valid={nv}")

    # --- GRPO: prompt/answer/system (mlx_rewards.brier_reward parses the completion, scores vs answer) ---
    grpo = _sample(load_jsonl(args.grpo_in), args.grpo_limit)
    grpo_rows = [
        {"prompt": user_prompt(r), "answer": str(r["outcome"]), "system": SYSTEM}
        for r in grpo
        if r.get("question") is not None and r.get("outcome") is not None
    ]
    nt, nv = _write_split(grpo_rows, f"{D}/mlx_grpo")
    print(f"GRPO → {D}/mlx_grpo  train={nt} valid={nv}")


if __name__ == "__main__":
    main()
