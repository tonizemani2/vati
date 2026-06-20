"""Phase 1, stage 2 — GRPO with a Brier reward (the heavy stage; Mantic's validated recipe).

The verifiable reward = the resolved outcome. For each prompt the trainer samples G completions, scores
each by Brier (proper, bounded, low-variance), and updates the policy toward the better-scored ones — no
critic model (low VRAM). A small format reward bootstraps parseable output and fights the hedge-to-0.5
collapse alongside the proper score. Reads the leak-split GRPO TRAIN set (engine/forecastbench/corpus.py).

Plain transformers + peft + trl (Unsloth dropped 2026-06-11 — see sft.py header). Rollouts use trl's
built-in HF generate, NOT vLLM: vLLM pins its own torch and re-creates the version-island problem that
killed the Unsloth attempts. ~3-5x slower generation, but on a dedicated L40S a 1500-step run is ~6-9h —
inside the sweep's 28h cap, and it cannot version-fight the stack. --base takes the MERGED model dir
saved by sft.py (or any HF model id).

Run after sft.py, on a single L40S/A100/H100 (or one GPU per config for the sweep):
    python training/grpo.py --data data/forecastbench/trainset/grpo_train.jsonl \
                            --base out/sft-qwen3-8b --out out/grpo-qwen3-8b
Then score on the leak-free held-out set with eval.py (the ONLY honest number).
"""
from __future__ import annotations

import argparse
import os

import torch
from datasets import Dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import GRPOConfig, GRPOTrainer

from common import SYSTEM, completion_text, load_jsonl, parse_prob, user_prompt


def brier_reward(completions, outcome, **kwargs):
    """1 - Brier on the parsed probability; unparseable → -1 (format penalty). Strictly proper."""
    out = []
    for comp, y in zip(completions, outcome):
        p = parse_prob(completion_text(comp))
        out.append(-1.0 if p is None else (1.0 - (p - float(y)) ** 2))
    return out


def make_composite_reward(acc_bonus: float):
    """Composite reward = proper Brier + a small bonus for getting the SIDE right (OpenForecaster
    arXiv 2512.25070 §reward; RLCR arXiv 2507.16806). The +acc_bonus at the 0.5 boundary pushes a
    hedging model OFF 0.5 toward the correct class — DISCRIMINATION (AUC) on top of calibration —
    while Brier still penalises committing the WRONG way (unit-tested).

    HONEST CAVEAT (do not self-deceive): OpenForecaster found the composite wins on OPEN-ENDED
    questions, where a pure score lets the model DODGE with 'Unknown' (~40% → ~4% with the composite).
    Our set is ALL-BINARY — there is no 'Unknown' escape, the model must emit a probability, and pure
    Brier is STRICTLY PROPER → the calibration-optimal reward. OpenForecaster's own binary ablation
    reported the accuracy term HURTS calibration; and calibration/decorrelation is precisely our edge
    (not raw discrimination). So this is a SPECULATIVE A/B knob, NOT a recommended default. The
    over-sharpening risk we actually face (arXiv 2508.11800) is handled by the KL anchor (beta) + no-std,
    not by an accuracy term. Keep `--reward brier` unless a leak-free eval.py run shows composite wins
    on BOTH Brier and the calibration (temp-scale) diagnostic. acc_bonus ≤ 1 keeps Brier primary."""
    def composite_reward(completions, outcome, **kwargs):
        out = []
        for comp, y in zip(completions, outcome):
            p = parse_prob(completion_text(comp))
            if p is None:
                out.append(-1.0)                      # same format penalty as brier_reward
                continue
            y = float(y)
            # Commitment bonus for landing on the correct SIDE of 0.5. An EXACT 0.5 hedge earns
            # nothing (no tie-break credit), so the indicator is a symmetric push OFF the hedge —
            # the model must commit to collect it, but Brier still penalises committing the wrong way.
            if p > 0.5:
                correct = 1.0 if y >= 0.5 else 0.0
            elif p < 0.5:
                correct = 1.0 if y < 0.5 else 0.0
            else:
                correct = 0.0
            out.append((1.0 - (p - y) ** 2) + acc_bonus * correct)
        return out
    return composite_reward


def format_reward(completions, **kwargs):
    """Small bonus for emitting a parseable 'Probability:' line — bootstraps the contract."""
    return [0.2 if parse_prob(completion_text(c)) is not None else 0.0 for c in completions]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="Qwen/Qwen3-8B", help="merged SFT model dir (from sft.py) or HF model id")
    ap.add_argument("--data", default="data/forecastbench/trainset/grpo_train.jsonl")
    ap.add_argument("--out", default="out/grpo-qwen3-8b")
    ap.add_argument("--max-seq", type=int, default=4096)
    ap.add_argument("--gens", type=int, default=8, help="G — completions per prompt")
    ap.add_argument("--steps", type=int, default=1500)
    ap.add_argument("--lr", type=float, default=1e-5, help="LoRA GRPO lr. NOT 1e-6 (that's the full-FT "
                    "value): 'LoRA Without Regret' (TML/HF) shows LoRA's 1/r scaling wants ~10x the "
                    "full-FT lr; 1e-6 barely moves an r=32 adapter. Sweep axis for run_big.sh.")
    ap.add_argument("--max-completion", type=int, default=1024, help="max gen tokens per completion")
    ap.add_argument("--beta", type=float, default=0.04, help="KL coeff to the SFT reference (calibration anchor)")
    ap.add_argument("--reward", choices=["brier", "composite"], default="brier",
                    help="brier = proper Brier+format (validated default). composite = Brier + acc-bonus "
                    "for the correct side (OpenForecaster/RLCR; fights hedge-to-0.5, adds AUC). A/B in the "
                    "signal run; flip the default only once eval.py shows the composite wins leak-free.")
    ap.add_argument("--acc-bonus", type=float, default=0.5, help="composite reward: weight on the "
                    "correct-side indicator (≤1 so proper Brier stays the primary signal)")
    ap.add_argument("--vllm-url", default="", help="optional `trl vllm-serve` base URL (e.g. http://localhost:8000); "
                    "vLLM lives in its OWN venv/GPU so it can't version-fight the training env")
    args = ap.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.base)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.base, dtype=torch.bfloat16)

    # Build the two needed columns in plain Python — datasets' JSON builder chokes on the corpus's
    # heterogeneous optional fields (a column that's null for the first rows gets schema 'null', then
    # "Couldn't cast double to null" when a real value appears). from_list sees only clean columns.
    rows = load_jsonl(args.data)
    ds = Dataset.from_list([
        {"prompt": [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user_prompt(r)}],
         "outcome": float(r["outcome"])}
        for r in rows
    ])

    lora = LoraConfig(
        r=32, lora_alpha=32, lora_dropout=0.0, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    )

    gcfg = GRPOConfig(
        output_dir=os.path.join(args.out, "checkpoints"), num_generations=args.gens,
        # 1024 (not 768): Qwen3 thinking-mode CoT can run long early in training and truncate
        # before the 'Probability:' line → false format penalty → reward-hacking. The SYSTEM
        # prompt demands BRIEF reasoning, so 1024 is ample headroom and leaves reward dynamics intact.
        # NOTE: no max_prompt_length — TRL ≥1.5 (box: 1.5.1) removed that GRPOConfig field and crashes
        # on it (TypeError, caught by the 0.6B smoke 2026-06-11). Prompt length is already bounded by
        # user_prompt()'s context cap (~500 tok ≪ max_seq − max_completion), so no truncation knob needed.
        max_completion_length=args.max_completion,
        per_device_train_batch_size=args.gens, gradient_accumulation_steps=4,
        learning_rate=args.lr, warmup_ratio=0.03, max_steps=args.steps,
        # KL to the SFT reference (beta>0) — the forecasting-specific tuning. "GRPO Induces
        # Overconfidence for Stochastic Outcomes" (arXiv 2508.11800) shows the group-relative
        # advantage sharpens probabilities toward 0/1 EVEN under a proper score like Brier, because
        # it rewards whichever outcome happened in the group. Math-RL (DAPO/Dr.GRPO) drops KL on
        # purpose (sharpening helps there); forecasting is the opposite — we anchor to the calibrated
        # SFT checkpoint to keep calibration. This is our doctrine §5.3 ("interpolate toward an
        # SFT-calibrated checkpoint") made concrete. With peft, trl gets the reference for free by
        # disabling the adapter — no second model copy. Watch eval.py's calibration + AUC; raise beta
        # if the reliability curve bows toward overconfidence, lower it if the model stops learning.
        beta=args.beta,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        logging_steps=5, save_steps=250, bf16=True, optim="adamw_torch",
        temperature=0.9, seed=42,
        report_to=("wandb" if os.getenv("WANDB_API_KEY") else "none"),
        **({"use_vllm": True, "vllm_mode": "server", "vllm_server_base_url": args.vllm_url}
           if args.vllm_url else {}),
    )
    # Dr.-GRPO: no division by the group's reward std (Mantic: more stable). The knob changed type
    # across trl versions (bool False → str "none"); set it to whichever form this trl expects.
    gcfg.scale_rewards = "none" if isinstance(getattr(gcfg, "scale_rewards", None), str) else False
    # Full Dr.-GRPO (arXiv 2503.20783): besides the std-division removed above, use the CONSTANT
    # (non-length) advantage normalizer so long, wrong completions aren't under-penalized per-token
    # (the default per-sequence 1/|o| norm dilutes the penalty on a verbose wrong answer → a subtle
    # length-hack incentive). Three independent papers (2503.20783, 2508.11800, 2505.17989) converge on
    # removing GRPO's per-question normalization for calibrated outcomes. We KEEP beta>0 (unlike math-RL
    # Dr.GRPO, which drops KL): forecasting wants calibration, so the SFT-anchor KL stays. Guarded —
    # older trl lacks the field and the trainer just uses its default normalizer.
    if hasattr(gcfg, "loss_type"):
        gcfg.loss_type = "dr_grpo"
    # Non-thinking contract: --base is normally the SFT checkpoint, trained with enable_thinking=False,
    # so rollouts already skip the <think> block (consistent with eval.py). When trl exposes
    # chat_template_kwargs, pin it explicitly so even a RAW Qwen3 base rolls out non-thinking instead
    # of burning the completion budget on a reasoning trace that truncates before 'Probability:'.
    if hasattr(gcfg, "chat_template_kwargs"):
        gcfg.chat_template_kwargs = {"enable_thinking": False}

    reward_funcs = ([make_composite_reward(args.acc_bonus), format_reward]
                    if args.reward == "composite" else [brier_reward, format_reward])
    print(f"reward = {args.reward}" + (f" (acc_bonus={args.acc_bonus})" if args.reward == "composite" else "")
          + f" | scale_rewards={gcfg.scale_rewards} | loss_type={getattr(gcfg, 'loss_type', 'n/a')} | beta={args.beta}")
    trainer = GRPOTrainer(
        model=model, processing_class=tokenizer,
        reward_funcs=reward_funcs,
        train_dataset=ds, args=gcfg, peft_config=lora,
    )
    trainer.train()

    # Merge the GRPO adapter into the (already SFT-merged) base → plain HF model dir for eval.py.
    merged = trainer.model.merge_and_unload()
    merged.save_pretrained(args.out)
    tokenizer.save_pretrained(args.out)
    print(f"GRPO model (merged) saved → {args.out}")


if __name__ == "__main__":
    main()
