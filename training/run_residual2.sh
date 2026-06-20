#!/bin/bash
# CORRECTED vLLM sweep (2026-06-14). The first run's vLLM path failed because grpo.py ran in the training
# env (/opt/pytorch) which lacks vllm. Fix: run the GRPO trainer + the vLLM server BOTH from ~/vllmenv
# (which has vllm 0.23 + trl 1.6 + cuda). grpo.py is already trl-1.6-compatible (the no-vLLM grpo-b ran
# fine on trl 1.6). 4x L40S: two (server GPU + trainer GPU) pairs -> 2 configs (beta 0.04 / 0.08) at once.
exec > ~/run2.log 2>&1
set -x
trap 'C=$?; echo "=== RUN2 EXIT code=$C $(date -u) ===" >> ~/RESULTS2.txt; sync; sleep 300; sudo shutdown -h now' EXIT INT TERM

cd ~; mkdir -p out
PY=~/vllmenv/bin/python; TRL=~/vllmenv/bin/trl
DATA=data/forecastbench/trainset; R=~/RESULTS2.txt; : > $R
TRAIN=$DATA/grpo_residual_train.jsonl; EVAL=$DATA/grpo_residual_eval.jsonl
BASE8B=Qwen/Qwen3-8B
export PYTHONPATH=training

echo "=== ensure vllmenv has peft (grpo.py needs LoraConfig) $(date -u) ===" | tee -a $R
~/vllmenv/bin/pip install -q peft 2>&1 | tail -2 | tee -a $R
$PY -c "import torch,vllm,trl,peft,transformers,datasets;print('vllmenv OK | torch',torch.__version__,'cuda',torch.cuda.is_available(),'| trl',trl.__version__)" 2>&1 | tee -a $R || { echo "vllmenv import FAILED" | tee -a $R; exit 1; }

G="--max-seq 2048 --max-completion 640 --data $TRAIN --base $BASE8B --gens 8 --reward brier --steps 1500"
run_pair(){ # $1=server_gpu $2=train_gpu $3=name $4=beta
  local PORT=$((8300 + $2))
  echo "=== pair $3 (server GPU$1, train GPU$2, beta $4, port $PORT) $(date -u) ===" | tee -a $R
  CUDA_VISIBLE_DEVICES=$1 $TRL vllm-serve --model $BASE8B --port $PORT --max-model-len 2048 > out/vllm2-$3.log 2>&1 &
  local SPID=$!
  local up=0
  for i in $(seq 1 150); do curl -sf localhost:$PORT/health >/dev/null 2>&1 && { up=1; break; }; sleep 5; done
  echo "pair $3 vllm-server up=$up $(date -u)" | tee -a $R
  CUDA_VISIBLE_DEVICES=$2 $PY training/grpo.py $G --beta $4 --vllm-url http://localhost:$PORT --out out/grpo-$3 > out/grpo2-$3.log 2>&1
  kill $SPID 2>/dev/null
}

echo "=== GRPO-from-base 8B vLLM sweep (2 configs, 1500 steps) $(date -u) ===" | tee -a $R
run_pair 0 1 a 0.04 &
run_pair 2 3 b 0.08 &
wait
echo "SWEEP DONE $(date -u)" | tee -a $R

echo "=== EVAL (leak-free): base + each config $(date -u) ===" | tee -a $R
[ -f out/grpo-a/config.json ] && CUDA_VISIBLE_DEVICES=0 $PY training/eval.py --model out/grpo-a --data $EVAL > out/eval2-a.txt 2>&1 &
[ -f out/grpo-b/config.json ] && CUDA_VISIBLE_DEVICES=1 $PY training/eval.py --model out/grpo-b --data $EVAL > out/eval2-b.txt 2>&1 &
CUDA_VISIBLE_DEVICES=2 $PY training/eval.py --model $BASE8B --data $EVAL > out/eval2-base.txt 2>&1 &
wait
for f in out/eval2-base.txt out/eval2-a.txt out/eval2-b.txt; do
  [ -f "$f" ] && { echo "===== $f ====="; cat "$f"; } | tee -a $R
done
echo "=== ALL DONE $(date -u) ===" | tee -a $R
