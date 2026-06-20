#!/bin/bash
# SMOKE-ONLY on-box run: prove the plain trl+peft stack end-to-end (SFT → GRPO → eval) on Qwen3-0.6B,
# ~25-35 min on one L40S (~$1.5), then stop the box. Gates on output files, not exit codes.
exec > ~/run.log 2>&1
set -x
trap 'C=$?; echo "=== SMOKE EXIT code=$C $(date -u) ===" >> ~/RESULTS.txt; sync; sleep 300; sudo shutdown -h now' EXIT INT TERM
# ^ 5-min grace before shutdown so the watcher can pull RESULTS/run.log after any exit.

source /opt/pytorch/bin/activate
cd ~; tar xzf fc.tgz; mkdir -p out
DATA=data/forecastbench/trainset; R=~/RESULTS.txt; : > $R
fail(){ echo "=== FAILED: $1 $(date -u) ===" | tee -a $R; exit 1; }

echo "=== INSTALL $(date -u) ===" | tee -a $R
pip install -q --upgrade pip
# Pure-python libs only — the DLAMI's vendor-tested torch/CUDA stays untouched (no unsloth/vllm/bnb).
pip install -q -U trl peft transformers datasets accelerate huggingface_hub 2>&1 | tail -5 | tee -a $R
python -c "import torch,trl,transformers,peft,datasets;assert torch.cuda.is_available();print('deps OK | torch',torch.__version__,'| trl',trl.__version__,'| transformers',transformers.__version__,'| peft',peft.__version__,'| datasets',datasets.__version__)" 2>&1 | tee -a $R
python -c "import torch;assert torch.cuda.is_available()" || fail "deps/cuda"

echo "=== SMOKE SFT (Qwen3-0.6B, 30 steps) $(date -u) ===" | tee -a $R
if [ -f out/smoke-sft/config.json ]; then
  echo "smoke SFT already done — skipping" | tee -a $R
else
  python training/sft.py --model Qwen/Qwen3-0.6B --data $DATA/sft_all.jsonl --out out/smoke-sft \
    --max-steps 30 --max-seq 2048 --batch 2 --accum 2 2>&1 | tail -30 | tee -a $R
fi
[ -f out/smoke-sft/config.json ] || fail "smoke SFT (no merged model saved)"

echo "=== SMOKE GRPO (from smoke-sft, 8 steps) $(date -u) ===" | tee -a $R
python training/grpo.py --base out/smoke-sft --data $DATA/grpo_train.jsonl --out out/smoke-grpo \
  --steps 8 --gens 4 --max-seq 2048 --max-completion 256 2>&1 | tail -30 | tee -a $R
[ -f out/smoke-grpo/config.json ] || fail "smoke GRPO (no merged model saved)"

echo "=== SMOKE EVAL (n=24) $(date -u) ===" | tee -a $R
python training/eval.py --model out/smoke-grpo --data $DATA/grpo_eval.jsonl --limit 24 --batch 8 2>&1 | tee -a $R

echo "=== SMOKE ALL PASSED $(date -u) ===" | tee -a $R
