#!/bin/bash
# Overnight finetune-fix experiment on the single-GPU POC box. Self-contained, AUTO-STOPS.
# Goal: produce a trained 8B checkpoint that beats RAW zero-shot 8B (Brier 0.2322), leak-free n=1500.
# Hypothesis: POC GRPO (beta=0.04, 400 steps) over-sharpened -> overconfident + lost discrimination.
# Fix tested: strong KL anchor to the SFT reference (beta=0.2) + fewer steps (250).
trap 'echo "=== PIPELINE EXIT code=$? $(date -u) ===" >> /home/ubuntu/RESULTS_overnight.txt; sync; sleep 240; sudo shutdown -h now' EXIT INT TERM
cd /home/ubuntu
source /opt/pytorch/bin/activate 2>/dev/null
R=/home/ubuntu/RESULTS_overnight.txt
DATA=data/forecastbench/trainset
: > $R
{
echo "=== OVERNIGHT FINETUNE-FIX $(date -u) ==="
echo "BAR: raw zero-shot 8B  Brier=0.2322 AUC=0.668"
echo "known SFT+GRPO(beta0.04,400)  Brier=0.2458 AUC=0.656 (regressed)"
echo "WIN = a checkpoint with Brier < 0.2322 leak-free n=1500"
} >> $R

echo "=== [1] EVAL SFT-only (out/sft-8b) $(date -u) ===" >> $R
python training/eval.py --model out/sft-8b --data $DATA/grpo_eval.jsonl --limit 1500 >> $R 2>&1 || echo "!! SFT-only eval FAILED" >> $R

echo "=== [2] GRPO fix beta=0.2 steps=250 (strong anchor, fewer steps) $(date -u) ===" >> $R
python training/grpo.py --base out/sft-8b --data $DATA/grpo_train.jsonl --out out/grpo-fix \
  --steps 250 --gens 6 --max-seq 2048 --max-completion 640 --beta 0.2 >> $R 2>&1 || echo "!! GRPO fix FAILED" >> $R

if [ -f out/grpo-fix/config.json ]; then
  echo "=== [3] EVAL GRPO-fix (out/grpo-fix) $(date -u) ===" >> $R
  python training/eval.py --model out/grpo-fix --data $DATA/grpo_eval.jsonl --limit 1500 >> $R 2>&1 || echo "!! grpo-fix eval FAILED" >> $R
else
  echo "!! grpo-fix checkpoint not saved -> skip eval" >> $R
fi

echo "=== ALL DONE $(date -u) ===" >> $R
