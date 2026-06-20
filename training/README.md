# training/ — Phase 1: SFT → GRPO a forecasting LLM

Standalone GPU-box scripts (RunPod/AWS/Vast). **Not part of the engine** — they import trl/peft/torch,
which are deliberately not engine deps. They consume the leak-gated corpus built by
`engine/forecastbench/{trainset,harvest,corpus,traces}.py`. Full plan + costs: `../FORECAST_LLM.md`.

**Stack: plain transformers + peft + trl, bf16 LoRA.** Unsloth was dropped 2026-06-11 — its global
monkeypatching of trl/transformers broke four times in a row on the modern DLAMI stack (arg renames,
placeholder-token crashes, unpicklable compile-config in `datasets.map` fingerprinting). vLLM and
bitsandbytes went with it (vLLM pins its own torch; bf16 LoRA fits 8B on a 48GB L40S). ~20% slower,
zero version-fighting. Each stage saves a **fully merged HF model dir** — the next stage just loads it.

## What it does
1. **`sft.py`** — bf16 LoRA warmup on best-of-N reasoning traces (`sft_*.jsonl`). Locks the output
   format + reasoning shape. ~5–10 GPU-hr.
2. **`grpo.py`** — GRPO with a **Brier reward** (Dr.-GRPO, no std-division — Mantic's recipe) on the
   leak-split TRAIN set. The verifiable reward = the resolved outcome. ~30–70 GPU-hr.
3. **`eval.py`** — Brier / AUC / calibration on the **leak-free** held-out EVAL set. *The only honest
   number* — train metrics are inflated by parametric leakage.

## Run order
```bash
# 0) build the corpus (on your normal machine, $0 keyless)
python -m engine.forecastbench.trainset --cutoff 2024-10-01 --anchors 10 --sources fred,dbnomics --balance
python -m engine.forecastbench.harvest  --cutoff 2024-10-01 --balance
# SFT traces — generate BOTH halves (dataset = the bot's edge, market = world-reasoning). Keyless
# DeepInfra is per-IP rate-limited: workers≤4 + a proxy + the in-adapter roster-shuffle is the
# sustainable rate (~37% keep). Each writes a sft_*.jsonl shard; streams to disk so it's resumable.
python -m engine.forecastbench.traces --in data/forecastbench/trainset/pool_dataset.jsonl \
        --out data/forecastbench/trainset/sft_dataset.jsonl --proxy evomi --workers 4 --n 5 --keep 2
python -m engine.forecastbench.traces --in data/forecastbench/trainset/pool_market.jsonl \
        --out data/forecastbench/trainset/sft_market_more.jsonl --proxy floxy --workers 4 --n 5 --keep 2
python -m engine.forecastbench.corpus    # → grpo_{train,eval}.jsonl + merges sft_*.jsonl → sft_all.jsonl

# 1) on a GPU box (single L40S/A100/H100), copy data/ + training/ over, then:
pip install -r training/requirements.txt
python training/sft.py   --data data/forecastbench/trainset/sft_all.jsonl --out out/sft-qwen3-8b
python training/grpo.py  --base out/sft-qwen3-8b --data data/forecastbench/trainset/grpo_train.jsonl --out out/grpo-qwen3-8b
python training/eval.py  --model out/grpo-qwen3-8b --data data/forecastbench/trainset/grpo_eval.jsonl
```

## Model + hardware
- Default base **Qwen3-8B** (Apache-2.0, native thinking-mode CoT). Swap with `--model`. Never <3B for the
  capability claim. Scale to Qwen3-32B / gpt-oss-120b on an 8×H100 node post-raise.
- POC fits one GPU. AWS: no cheap single H100 → use `g6e.xlarge` (L40S 48GB) for serial dev, or a
  `p5.48xlarge` node (~$55/hr) to run an 8-way iteration sweep. RunPod/Vast cheaper. POC < $2.5k of credits.

## Success gate
GRPO model beats Qwen3-8B zero-shot on `eval.py` Brier by a clear margin **and** shows low correlation
with frontier models (ensemble diversity = the headline). That's the news artifact.

## Caveats (read before trusting a result)
- **Only eval.py numbers are honest.** Forward / leak-free; everything else can be memorized.
- **Watch hedge-to-0.5 and RL overconfidence** — track AUC + calibration, not just Brier (eval.py prints both).
- Verify package APIs against installed versions (TRL GRPO/SFT signatures move between releases).
