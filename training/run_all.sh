#!/bin/bash
# Self-driving first-signal pipeline (g6e single-GPU). Robust: NO set -e (CUDA teardown can exit
# non-zero even on success); instead every stage tees full output (incl. tracebacks) into
# ~/RESULTS.txt (reliably scp-able) and we gate on OUTPUT-FILE existence. trap always stops the box.
exec > ~/run.log 2>&1
set -x
trap 'C=$?; echo "=== PIPELINE EXIT code=$C $(date -u) ===" >> ~/RESULTS.txt; sync; sleep 600; sudo shutdown -h now' EXIT INT TERM
# ^ 10-min grace before shutdown so the watcher can always pull RESULTS/run.log after any exit.

source /opt/pytorch/bin/activate
cd ~; tar xzf fc.tgz; mkdir -p out
DATA=data/forecastbench/trainset; R=~/RESULTS.txt; : > $R
fail(){ echo "=== FAILED: $1 $(date -u) ===" | tee -a $R; exit 1; }

echo "=== INSTALL $(date -u) ===" | tee -a $R
pip install -q --upgrade pip
# Pure-python libs only — the DLAMI's vendor-tested torch/CUDA stays untouched (no unsloth/vllm/bnb).
pip install -q -U trl peft transformers datasets accelerate huggingface_hub 2>&1 | tail -5 | tee -a $R
python -c "import torch,trl,transformers,peft;assert torch.cuda.is_available();print('deps OK | torch',torch.__version__,'| trl',trl.__version__,'| transformers',transformers.__version__,'| peft',peft.__version__)" 2>&1 | tee -a $R
python -c "import torch;assert torch.cuda.is_available()" || fail "deps/cuda"

BASE8B=Qwen/Qwen3-8B
echo "8B base = $BASE8B" | tee -a $R

# ---------- SMOKE on 0.6B (gate on saved merged model, NOT exit code; skip if already green) ----------
echo "=== SMOKE SFT (Qwen3-0.6B, 30 steps) $(date -u) ===" | tee -a $R
if [ -f out/smoke-sft/config.json ]; then echo "smoke SFT already done — skipping" | tee -a $R; else
  python training/sft.py  --model Qwen/Qwen3-0.6B --data $DATA/sft_all.jsonl --out out/smoke-sft \
    --max-steps 30 --max-seq 2048 --batch 2 --accum 2 2>&1 | tee -a $R
fi
[ -f out/smoke-sft/config.json ] || fail "smoke SFT (no merged model saved)"
echo "=== SMOKE GRPO (from smoke-sft, 8 steps) $(date -u) ===" | tee -a $R
if [ -f out/smoke-grpo/config.json ]; then echo "smoke GRPO already done — skipping" | tee -a $R; else
  python training/grpo.py --base out/smoke-sft --data $DATA/grpo_train.jsonl --out out/smoke-grpo \
    --steps 8 --gens 4 --max-seq 2048 --max-completion 256 2>&1 | tee -a $R
fi
[ -f out/smoke-grpo/config.json ] || fail "smoke GRPO (no merged model saved)"
echo "SMOKE PASSED $(date -u)" | tee -a $R

# ---------- REAL 8B ----------
echo "=== SFT 8B (1 epoch POC, batch 2 x seq 2048) $(date -u) ===" | tee -a $R
python training/sft.py --model $BASE8B --data $DATA/sft_all.jsonl --out out/sft-8b --epochs 1 \
  --max-seq 2048 --batch 2 --accum 8 2>&1 | tail -40 | tee -a $R
[ -f out/sft-8b/config.json ] || fail "SFT 8B (no merged model — see tail above, likely OOM)"
echo "=== GRPO 8B (400 steps POC, G=6) $(date -u) ===" | tee -a $R
python training/grpo.py --base out/sft-8b --data $DATA/grpo_train.jsonl --out out/grpo-8b \
  --steps 400 --gens 6 --max-seq 2048 --max-completion 640 2>&1 | tail -50 | tee -a $R
[ -f out/grpo-8b/config.json ] || fail "GRPO 8B (no merged model — see tail above)"
echo "=== EVAL trained (leak-free, n=1500) $(date -u) ===" | tee -a $R
python training/eval.py --model out/grpo-8b --data $DATA/grpo_eval.jsonl --limit 1500 2>&1 | tee -a $R
echo "=== EVAL zero-shot base (lift baseline) $(date -u) ===" | tee -a $R
python training/eval.py --model $BASE8B --data $DATA/grpo_eval.jsonl --limit 1500 2>&1 | tee -a $R
echo "=== ALL DONE $(date -u) ===" | tee -a $R
