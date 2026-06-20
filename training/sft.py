"""Phase 1, stage 1 — SFT warmup (plain transformers + peft, bf16 LoRA) on best-of-N reasoning traces.

Teaches the output format + reasoning skeleton so the GRPO stage only has to sharpen calibration.
Reads the SFT chat-format JSONL from engine/forecastbench/traces.py (messages: system/user/assistant).

Unsloth was DROPPED 2026-06-11 after four stacked incompatibilities on the modern DLAMI stack
(trl-0.24 arg renames, '<EOS_TOKEN>'/'<|PAD_TOKEN|>' placeholder crashes, and finally an unpicklable
torch ConfigModuleInstance polluting datasets.map fingerprinting — Unsloth's global monkeypatching is
the root of all four). Plain transformers+peft+trl is ~20% slower and 100% boring: the right trade for
first signal. bf16 LoRA (no 4-bit) — an 8B fits an L40S 48GB without quantization, so bitsandbytes is
gone too. Each stage saves a FULL merged model dir (config.json + safetensors), so downstream stages
load it like any HF model — no adapter-resolution chains.

Run on a single GPU (L40S 48GB / A100 / H100):
    pip install -r training/requirements.txt
    python training/sft.py --data data/forecastbench/trainset/sft_all.jsonl --out out/sft-qwen3-8b
(sft_all.jsonl = market + dataset traces, merged by engine/forecastbench/corpus.py)
"""
from __future__ import annotations

import argparse
import os

import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-8B")
    ap.add_argument("--data", default="data/forecastbench/trainset/sft_all.jsonl")
    ap.add_argument("--out", default="out/sft-qwen3-8b")
    ap.add_argument("--max-seq", type=int, default=4096)
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--max-steps", type=int, default=0, help=">0 caps optimizer steps (smoke tests)")
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--batch", type=int, default=4, help="per-device batch")
    ap.add_argument("--accum", type=int, default=4, help="grad accumulation steps")
    args = ap.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.bfloat16)

    ds = load_dataset("json", data_files=args.data, split="train")

    def to_pc(ex):
        # Split each row into prompt (system+user) and completion (assistant) so SFTTrainer's
        # completion_only_loss masks the prompt: we train ONLY on the assistant's reasoning + answer,
        # NOT on the long numeric/as-of context. Modelling that context wastes adapter capacity on a
        # distribution that differs at eval and dilutes the calibration signal — the whole point of the
        # warmup is the OUTPUT (the 4-part reasoning + 'Probability:' line), not reproducing the prompt.
        # enable_thinking=False + add_generation_prompt=True renders the prompt EXACTLY as eval.py does
        # (incl. Qwen3's empty <think></think>), so train/infer match; the raw assistant text is the
        # completion and SFTTrainer appends the <|im_end|> EOS. (enable_thinking ignored by non-Qwen3.)
        msgs = ex["messages"]
        prompt = tokenizer.apply_chat_template(msgs[:-1], tokenize=False,
                                               add_generation_prompt=True, enable_thinking=False)
        return {"prompt": prompt, "completion": msgs[-1]["content"]}
    ds = ds.map(to_pc, remove_columns=ds.column_names)

    lora = LoraConfig(
        r=32, lora_alpha=32, lora_dropout=0.0, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    )

    cfg = SFTConfig(
        output_dir=os.path.join(args.out, "checkpoints"),
        completion_only_loss=True, max_length=args.max_seq,
        per_device_train_batch_size=args.batch, gradient_accumulation_steps=args.accum,
        num_train_epochs=args.epochs, max_steps=(args.max_steps or -1),
        learning_rate=args.lr, warmup_ratio=0.05,
        gradient_checkpointing=True,
        # non-reentrant checkpointing: the reentrant default breaks PEFT ("element 0 ... requires_grad")
        gradient_checkpointing_kwargs={"use_reentrant": False},
        logging_steps=10, save_strategy="epoch", bf16=True, optim="adamw_torch",
        lr_scheduler_type="cosine", seed=42,
        report_to=("wandb" if os.getenv("WANDB_API_KEY") else "none"),
    )
    trainer = SFTTrainer(
        model=model, processing_class=tokenizer, train_dataset=ds, args=cfg, peft_config=lora,
    )
    trainer.train()

    # Merge the adapter into the base and save a plain HF model dir — grpo.py/eval.py just load it.
    merged = trainer.model.merge_and_unload()
    merged.save_pretrained(args.out)
    tokenizer.save_pretrained(args.out)
    print(f"SFT model (merged) saved → {args.out}")


if __name__ == "__main__":
    main()
