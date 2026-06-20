#!/bin/bash
# QUALITY run: g6e.12xlarge (4x L40S). SFT once, then a 4-config GRPO sweep at Mantic-floor coverage
# (2500 steps x 4 prompts/step = 10k unique questions/config), beta = the calibration sweep axis.
# Rollouts via `trl vllm-serve` in an ISOLATED venv (own torch, own GPU) — 2 waves of (server GPU +
# trainer GPU) pairs. If the vLLM path fails its 0.6B smoke, falls back to no-vLLM with trimmed steps.
# COST SAFETY: trap always stops the box; outer `timeout` (launch_big.sh) caps burn.
exec > ~/run.log 2>&1
set -x
trap 'C=$?; echo "=== PIPELINE EXIT code=$C $(date -u) ===" >> ~/RESULTS.txt; sync; sleep 300; sudo shutdown -h now' EXIT INT TERM

source /opt/pytorch/bin/activate
cd ~; tar xzf fc.tgz; mkdir -p out
DATA=data/forecastbench/trainset; R=~/RESULTS.txt; : > $R
fail(){ echo "=== FAILED: $1 $(date -u) ===" | tee -a $R; exit 1; }

echo "=== INSTALL $(date -u) ===" | tee -a $R
pip install -q --upgrade pip
# Training env: pure-python libs only — the DLAMI's vendor-tested torch/CUDA stays untouched.
pip install -q -U trl peft transformers datasets accelerate huggingface_hub 2>&1 | tail -5
python -c "import torch,trl,transformers,peft;assert torch.cuda.is_available();print('GPUs',torch.cuda.device_count(),'| torch',torch.__version__,'| trl',trl.__version__)" | tee -a $R
TRLV=$(python -c "import trl;print(trl.__version__)")
# vLLM env: fully isolated venv — vLLM pins its own torch HERE, never in the training env. Same trl
# version on both sides so the weight-sync protocol matches.
python3 -m venv ~/vllmenv
~/vllmenv/bin/pip install -q --upgrade pip
~/vllmenv/bin/pip install -q vllm "trl==$TRLV" 2>&1 | tail -5 | tee -a $R
BASE8B=Qwen/Qwen3-8B
echo "8B base = $BASE8B | trl $TRLV both envs" | tee -a $R

# ---------- SMOKE 0.6B (plain path; skip if this box already passed it) ----------
if [ ! -f out/smoke-sft/config.json ]; then
  CUDA_VISIBLE_DEVICES=0 python training/sft.py --model Qwen/Qwen3-0.6B --data $DATA/sft_all.jsonl \
    --out out/smoke-sft --max-steps 30 --max-seq 2048 --batch 2 --accum 2 2>&1 | tail -15 | tee -a $R
fi
[ -f out/smoke-sft/config.json ] || fail "smoke SFT"
if [ ! -f out/smoke-grpo/config.json ]; then
  CUDA_VISIBLE_DEVICES=0 python training/grpo.py --base out/smoke-sft --data $DATA/grpo_train.jsonl \
    --out out/smoke-grpo --steps 8 --gens 4 --max-seq 2048 --max-completion 256 2>&1 | tail -15 | tee -a $R
fi
[ -f out/smoke-grpo/config.json ] || fail "smoke GRPO"
echo "SMOKE (plain) PASSED $(date -u)" | tee -a $R

# ---------- SMOKE the vLLM server path (0.6B, 4 steps) → sets VLLM_OK ----------
echo "=== SMOKE vLLM server path $(date -u) ===" | tee -a $R
VLLM_OK=0
CUDA_VISIBLE_DEVICES=0 ~/vllmenv/bin/trl vllm-serve --model out/smoke-sft --port 8500 \
  --max-model-len 2048 > out/vllm-smoke.log 2>&1 &
VPID=$!
for i in $(seq 1 60); do curl -sf localhost:8500/health >/dev/null 2>&1 && break; sleep 5; done
rm -rf out/smoke-grpo-vllm
CUDA_VISIBLE_DEVICES=1 python training/grpo.py --base out/smoke-sft --data $DATA/grpo_train.jsonl \
  --out out/smoke-grpo-vllm --steps 4 --gens 4 --max-seq 2048 --max-completion 256 \
  --vllm-url http://localhost:8500 2>&1 | tail -15 | tee -a $R
[ -f out/smoke-grpo-vllm/config.json ] && VLLM_OK=1
kill $VPID 2>/dev/null; sleep 5
echo "VLLM_OK=$VLLM_OK $(date -u)" | tee -a $R

# ---------- SFT 8B once on GPU 0 (skip if reused from a prior box) ----------
if [ ! -f out/sft-8b/config.json ]; then
  echo "=== SFT 8B (2 epochs, batch 2 x seq 2048) $(date -u) ===" | tee -a $R
  CUDA_VISIBLE_DEVICES=0 python training/sft.py --model $BASE8B --data $DATA/sft_all.jsonl \
    --out out/sft-8b --epochs 2 --max-seq 2048 --batch 2 --accum 8 2>&1 | tail -25 | tee -a $R
fi
[ -f out/sft-8b/config.json ] || fail "SFT 8B (no merged model — likely OOM, see run.log)"
echo "SFT DONE $(date -u)" | tee -a $R

G="--max-seq 2048 --max-completion 640 --data $DATA/grpo_train.jsonl --base out/sft-8b"

run_pair(){ # $1=server_gpu $2=train_gpu $3=name $4=extra grpo args
  local PORT=$((8200 + $2))
  CUDA_VISIBLE_DEVICES=$1 ~/vllmenv/bin/trl vllm-serve --model out/sft-8b --port $PORT \
    --max-model-len 2048 > out/vllm-$3.log 2>&1 &
  local SPID=$!
  for i in $(seq 1 120); do curl -sf localhost:$PORT/health >/dev/null 2>&1 && break; sleep 5; done
  CUDA_VISIBLE_DEVICES=$2 python training/grpo.py $G --vllm-url http://localhost:$PORT $4 \
    --out out/grpo-$3 > out/grpo-$3.log 2>&1
  kill $SPID 2>/dev/null
}

if [ "$VLLM_OK" = "1" ]; then
  # 2 waves x 2 (server GPU + trainer GPU) pairs; 2500 steps = 10k unique Qs (Mantic floor)
  echo "=== GRPO SWEEP (vLLM server, 2 waves) $(date -u) ===" | tee -a $R
  run_pair 0 1 a "--steps 2500 --gens 8  --beta 0.04" &
  run_pair 2 3 b "--steps 2500 --gens 8  --beta 0.08" &
  wait
  echo "WAVE 1 DONE $(date -u)" | tee -a $R
  run_pair 0 1 c "--steps 2500 --gens 12 --beta 0.04" &
  run_pair 2 3 d "--steps 2500 --gens 8  --beta 0.02" &
  wait
else
  # Fallback: no-vLLM, 4 configs in parallel (1/GPU), trimmed steps + completion to fit the cap
  echo "=== GRPO SWEEP (no-vLLM fallback, trimmed) $(date -u) ===" | tee -a $R
  G="--max-seq 2048 --max-completion 448 --data $DATA/grpo_train.jsonl --base out/sft-8b"
  CUDA_VISIBLE_DEVICES=0 python training/grpo.py $G --steps 1200 --gens 8  --beta 0.04 --out out/grpo-a > out/grpo-a.log 2>&1 &
  CUDA_VISIBLE_DEVICES=1 python training/grpo.py $G --steps 1200 --gens 8  --beta 0.08 --out out/grpo-b > out/grpo-b.log 2>&1 &
  CUDA_VISIBLE_DEVICES=2 python training/grpo.py $G --steps 900  --gens 12 --beta 0.04 --out out/grpo-c > out/grpo-c.log 2>&1 &
  CUDA_VISIBLE_DEVICES=3 python training/grpo.py $G --steps 1200 --gens 8  --beta 0.02 --out out/grpo-d > out/grpo-d.log 2>&1 &
  wait
fi
echo "SWEEP DONE $(date -u)" | tee -a $R

# ---------- EVAL: 4 configs in parallel (1/GPU, n=3000) then zero-shot base ----------
echo "=== EVAL (leak-free, n=3000, parallel) $(date -u) ===" | tee -a $R
for i in 0 1 2 3; do
  m=$(echo a b c d | cut -d' ' -f$((i+1)))
  CUDA_VISIBLE_DEVICES=$i python training/eval.py --model out/grpo-$m --data $DATA/grpo_eval.jsonl \
    --limit 3000 > out/eval-$m.txt 2>&1 &
done
wait
CUDA_VISIBLE_DEVICES=0 python training/eval.py --model $BASE8B --data $DATA/grpo_eval.jsonl \
  --limit 3000 > out/eval-base.txt 2>&1 &
CUDA_VISIBLE_DEVICES=1 python training/eval.py --model out/sft-8b --data $DATA/grpo_eval.jsonl \
  --limit 3000 > out/eval-sft.txt 2>&1 &
wait
for f in out/eval-*.txt; do echo "===== $f ====="; cat "$f"; done | tee -a $R
echo "=== ALL DONE $(date -u) ===" | tee -a $R
