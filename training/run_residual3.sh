#!/bin/bash
# RELIABLE no-vLLM GRPO sweep (2026-06-14). The vLLM path is dead here: trl 1.6 supports vLLM <=0.19 but
# the box has 0.23 -> the generation/weight-sync hangs. The no-vLLM HF-generation path is PROVEN on this
# box (grpo-b stepped fine at ~40s/step from /opt/pytorch). 4x L40S -> run the full beta sweep as 4
# independent 1-GPU trainers (one per GPU) in parallel: same wall-time as a single config, free sweep.
# GRPO-from-base Qwen3-8B, residual-on-prior (prior in prompt), leak-clean numeric, Brier reward.
exec > ~/run3.log 2>&1
set -x
trap 'C=$?; echo "=== RUN3 EXIT code=$C $(date -u) ===" >> ~/RESULTS3.txt; sync; sleep 300; sudo shutdown -h now' EXIT INT TERM

source /opt/pytorch/bin/activate
cd ~; mkdir -p out
DATA=data/forecastbench/trainset; R=~/RESULTS3.txt; : > $R
TRAIN=$DATA/grpo_residual_train.jsonl; EVAL=$DATA/grpo_residual_eval.jsonl
BASE8B=Qwen/Qwen3-8B
export PYTHONPATH=training PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

python -c "import torch,trl,peft;assert torch.cuda.is_available();print('env OK | torch',torch.__version__,'| trl',trl.__version__,'| GPUs',torch.cuda.device_count())" 2>&1 | tee -a $R

G="--max-seq 2048 --max-completion 512 --data $TRAIN --base $BASE8B --gens 8 --reward brier --steps 600"
echo "=== GRPO-from-base 8B no-vLLM 4-beta sweep (600 steps each, 1 GPU/config) $(date -u) ===" | tee -a $R
CUDA_VISIBLE_DEVICES=0 python training/grpo.py $G --beta 0.02 --out out/grpo-a > out/grpo3-a.log 2>&1 &
CUDA_VISIBLE_DEVICES=1 python training/grpo.py $G --beta 0.04 --out out/grpo-b > out/grpo3-b.log 2>&1 &
CUDA_VISIBLE_DEVICES=2 python training/grpo.py $G --beta 0.06 --out out/grpo-c > out/grpo3-c.log 2>&1 &
CUDA_VISIBLE_DEVICES=3 python training/grpo.py $G --beta 0.08 --out out/grpo-d > out/grpo3-d.log 2>&1 &
wait
echo "SWEEP DONE $(date -u)" | tee -a $R

echo "=== EVAL (leak-free): 4 configs in parallel (1/GPU), then base $(date -u) ===" | tee -a $R
[ -f out/grpo-a/config.json ] && CUDA_VISIBLE_DEVICES=0 python training/eval.py --model out/grpo-a --data $EVAL > out/eval3-a.txt 2>&1 &
[ -f out/grpo-b/config.json ] && CUDA_VISIBLE_DEVICES=1 python training/eval.py --model out/grpo-b --data $EVAL > out/eval3-b.txt 2>&1 &
[ -f out/grpo-c/config.json ] && CUDA_VISIBLE_DEVICES=2 python training/eval.py --model out/grpo-c --data $EVAL > out/eval3-c.txt 2>&1 &
[ -f out/grpo-d/config.json ] && CUDA_VISIBLE_DEVICES=3 python training/eval.py --model out/grpo-d --data $EVAL > out/eval3-d.txt 2>&1 &
wait
CUDA_VISIBLE_DEVICES=0 python training/eval.py --model $BASE8B --data $EVAL > out/eval3-base.txt 2>&1
wait
for f in out/eval3-base.txt out/eval3-a.txt out/eval3-b.txt out/eval3-c.txt out/eval3-d.txt; do
  [ -f "$f" ] && { echo "===== $f ====="; cat "$f"; } | tee -a $R
done
echo "=== ALL DONE $(date -u) ===" | tee -a $R
