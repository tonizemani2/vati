# training/MLX.md — local plumbing smoke test on an 8 GB Apple-Silicon Mac

**What this is.** A $0, Mac-native dry run of the *entire* SFT→GRPO→eval loop on a tiny throwaway
model, to prove the data / reward / parser plumbing **before** you rent the g6e GPU. It replaces the
"Step 0 smoke test" in `AWS.md` — do it here, locally, first, and arrive at the GPU box already
confident, then go straight to the real 8B job.

**This is NOT the POC.** You cannot fine-tune Qwen3-**8B** on 8 GB, and the production scripts
(`sft.py`/`grpo.py`) are CUDA-only (unsloth/vllm/bitsandbytes won't import on a Mac). The 8B stays on
the rented GPU. The Mac's job is to validate the *contract*, not the *capability*.

## ✅ VERIFIED 2026-06-10 (this whole runbook was actually run)
Every stage below ran on an 8 GB M-series Mac. Outcome:
- Install ✓ · convert ✓ (balanced 95/85) · **SFT ✓** (Qwen3-0.6B, loss 3.22→3.05, adapter saved,
  peak **1.82 GB**) · **GRPO loop turns ✓** (generation → custom Brier reward → Dr.GRPO update; the
  trainer logged `Using custom reward functions: brier_reward, format_reward`) · **eval ✓**
  (generate → `parse_prob` → Brier/AUC, all rows parseable).
- **8 GB memory wall (the real finding):** GRPO loads a **2nd reference-model copy for the KL term**;
  2× model + group rollouts spikes memory. Even a minimal GRPO (group-size 2, 64-tok completions)
  drove free RAM to ~13%. Use the **watchdog** below so a run can never freeze the machine — and
  understand that *fully* completing multi-iter GRPO is the GPU's job. The Mac proves the loop turns.

## Model choice
Use **`mlx-community/Qwen3-0.6B-4bit`** on 8 GB (same family as the production Qwen3-8B → exercises the
real chat-template / non-thinking / `parse_prob` path; 1.7B at seq 2048 **OOM-killed** on 8 GB). 0.6B
weights are ~320 MB; SFT peaks ~1.8 GB. Everything takes `--model`, so scale up on a bigger Mac.

## 0. Install (Mac only) — VERIFIED
```bash
cd ~/Desktop/predictthefuture
python3.12 -m venv .mlx-venv && source .mlx-venv/bin/activate   # 3.12; keep OFF the engine env
pip install -r training/requirements-mlx.txt                     # installs mlx-lm-lora 1.0.0 + deps
python -c "import mlx_lm, mlx_lm_lora; print('mlx stack ok')"
```

## 1. Convert the real corpus → mlx data dirs (reuses production common.py) — VERIFIED
```bash
python training/mlx_convert.py --grpo-limit 200    # run from REPO ROOT (puts training/ on sys.path)
# writes data/forecastbench/trainset/{mlx_sft,mlx_grpo}/{train,valid}.jsonl
```

## 2. SFT warmup (locks the output format) — VERIFIED, lean config fits 8 GB
```bash
python -m mlx_lm_lora.train \
  --model mlx-community/Qwen3-0.6B-4bit --train --train-mode sft --train-type lora \
  --data data/forecastbench/trainset/mlx_sft \
  --batch-size 1 --iters 40 --max-seq-length 1024 --num-layers 8 --grad-checkpoint \
  --steps-per-report 5 --save-every 40 --adapter-path out/mlx-sft
# Saves out/mlx-sft/adapters.safetensors (+ a fused model.safetensors). peak ~1.8 GB.
```

## 3. GRPO with the Brier reward — VERIFIED the loop turns (memory-bound on 8 GB)
Two gotchas learned the hard way:
- **Run off the BASE model, not the fused `out/mlx-sft` dir** — that dir contains both a fused model
  *and* a leftover adapter → `ValueError: Received N parameters not in model`. Use the base; the SFT
  stage is already independently proven. (On the real GPU box, Unsloth handles the SFT→GRPO handoff;
  the MLX fused-dir quirk is not representative.)
- **`PYTHONPATH=training`** so the reward file's `from common import parse_prob` resolves while
  `--data` stays repo-root-relative.

```bash
PYTHONPATH=training python -m mlx_lm_lora.train \
  --model mlx-community/Qwen3-0.6B-4bit --train --train-mode grpo --train-type lora \
  --data data/forecastbench/trainset/mlx_grpo \
  --group-size 2 --max-completion-length 64 --iters 2 \
  --max-seq-length 448 --num-layers 2 --grad-checkpoint --grpo-loss-type dr_grpo \
  --steps-per-eval 1000 --steps-per-report 1 --save-every 2 \
  --reward-functions-file training/mlx_rewards.py \
  --reward-functions "brier_reward,format_reward" --reward-weights "[1.0,0.2]" \
  --adapter-path out/mlx-grpo
```
**Always wrap GRPO in the memory watchdog** (it killed a run at 13% free and prevented a system freeze):
```bash
<the train command above> > out/logs/grpo.log 2>&1 &
GP=$!
while ps -p $GP >/dev/null 2>&1; do
  free=$(memory_pressure | awk -F': ' '/free perc/{gsub(/%/,"",$2); print $2+0}')
  [ "$free" -lt 15 ] && { kill -9 $GP; echo "watchdog killed: free ${free}%"; break; }
  sleep 3
done
```
On 8 GB, expect the watchdog to fire before many iters complete — that's fine; the goal here is to
see `Using custom reward functions: brier_reward, format_reward` + at least one iter's loss. Full GRPO
runs on the GPU.

## 4. Leak-free eval — VERIFIED (light: single model, no reference)
```bash
python training/mlx_eval.py --model mlx-community/Qwen3-0.6B-4bit --adapter out/mlx-sft --limit 50
```

## Success criterion (what "passed" means) — MET
The loop runs without crashing the box, the GRPO trainer accepts + uses the custom Brier reward, and
`mlx_eval` prints parseable probabilities with a Brier/baseline line. The 0.6B's *accuracy* is
irrelevant (it scored ~0.70 — confidently wrong on a 6-row all-YES slice; AUC needs both classes). You
have de-risked: install, data format, reward registration (incl. the v1.0.0 batched-signature API),
the SFT→eval path, and the GRPO reward integration — so the paid 8B run won't die on a plumbing bug.

## Notes for the GPU run (carried back from this dry run)
- `mlx-lm-lora 1.0.0` reward API = **batched** `(prompts, completions, answer, types)` at
  `mlx_lm_lora.trainer.grpo_reward_functions` (NOT the singular form some docs show). `mlx_rewards.py`
  is written to this; if you bump the version, re-check `--list-reward-functions`.
- The CUDA scripts (`sft.py`/`grpo.py`) are the real path — MLX here is purely the plumbing rehearsal.
