#!/bin/bash
# TOP-QUALITY residual-on-prior GRPO run (2026-06-14). g6e.12xlarge (4x L40S).
# Built on the 2026-06-14 findings: (1) imitation-SFT REGRESSED twice -> NO SFT stage, GRPO-from-BASE.
# (2) the original GRPO never put the prior in the prompt -> common.user_prompt now surfaces it
# (residual-on-prior). (3) train ONLY on the leak-clean NUMERIC set (unmemorizable -> GRPO can't
# reward-hack by recalling outcomes, the original failure). (4) no truncation (completion 640), KL kept
# (beta sweep = the calibration axis), eval-gated: base vs every config on the leak-free held-out.
# COST SAFETY: trap always stops the box; outer `timeout` (launcher) caps burn.
exec > ~/run.log 2>&1
set -x
trap 'C=$?; echo "=== PIPELINE EXIT code=$C $(date -u) ===" >> ~/RESULTS.txt; sync; sleep 300; sudo shutdown -h now' EXIT INT TERM

source /opt/pytorch/bin/activate
cd ~; tar xzf fc.tgz; mkdir -p out
DATA=data/forecastbench/trainset; R=~/RESULTS.txt; : > $R
TRAIN=$DATA/grpo_residual_train.jsonl; EVAL=$DATA/grpo_residual_eval.jsonl
BASE8B=Qwen/Qwen3-8B
fail(){ echo "=== FAILED: $1 $(date -u) ===" | tee -a $R; exit 1; }

echo "=== INSTALL $(date -u) ===" | tee -a $R
pip install -q --upgrade pip
pip install -q -U trl peft transformers datasets accelerate huggingface_hub 2>&1 | tail -5 | tee -a $R
python -c "import torch,trl,transformers,peft;assert torch.cuda.is_available();print('deps OK | GPUs',torch.cuda.device_count(),'| torch',torch.__version__,'| trl',trl.__version__)" 2>&1 | tee -a $R || fail "deps/cuda"
TRLV=$(python -c "import trl;print(trl.__version__)")
echo "=== build isolated vLLM venv (own torch) $(date -u) ===" | tee -a $R
python3 -m venv ~/vllmenv; ~/vllmenv/bin/pip install -q --upgrade pip
~/vllmenv/bin/pip install -q vllm "trl==$TRLV" 2>&1 | tail -4 | tee -a $R

# ---------- SMOKE: GRPO-from-base on 0.6B over the RESIDUAL data (validates prior-in-prompt + reward) ----------
echo "=== SMOKE GRPO-from-base 0.6B on residual data (8 steps) $(date -u) ===" | tee -a $R
python training/grpo.py --base Qwen/Qwen3-0.6B --data $TRAIN --out out/smoke-grpo \
  --steps 8 --gens 4 --max-seq 2048 --max-completion 256 2>&1 | tail -20 | tee -a $R
[ -f out/smoke-grpo/config.json ] || fail "smoke GRPO (residual data/prompt/reward bug — check run.log)"
echo "SMOKE PASSED $(date -u)" | tee -a $R

# ---------- SMOKE the vLLM server path (0.6B) → VLLM_OK ----------
echo "=== SMOKE vLLM path $(date -u) ===" | tee -a $R
VLLM_OK=0
CUDA_VISIBLE_DEVICES=0 ~/vllmenv/bin/trl vllm-serve --model Qwen/Qwen3-0.6B --port 8500 --max-model-len 2048 > out/vllm-smoke.log 2>&1 &
VPID=$!
for i in $(seq 1 60); do curl -sf localhost:8500/health >/dev/null 2>&1 && break; sleep 5; done
CUDA_VISIBLE_DEVICES=1 python training/grpo.py --base Qwen/Qwen3-0.6B --data $TRAIN \
  --out out/smoke-grpo-vllm --steps 4 --gens 4 --max-seq 2048 --max-completion 256 \
  --vllm-url http://localhost:8500 2>&1 | tail -15 | tee -a $R
[ -f out/smoke-grpo-vllm/config.json ] && VLLM_OK=1
kill $VPID 2>/dev/null; sleep 5
echo "VLLM_OK=$VLLM_OK $(date -u)" | tee -a $R

# ---------- GRPO-from-base 8B: beta sweep (calibration axis), eval-gated ----------
G="--max-seq 2048 --max-completion 640 --data $TRAIN --base $BASE8B --gens 8 --reward brier"
run_pair(){ # $1=server_gpu $2=train_gpu $3=name $4=extra
  local PORT=$((8200 + $2))
  CUDA_VISIBLE_DEVICES=$1 ~/vllmenv/bin/trl vllm-serve --model $BASE8B --port $PORT --max-model-len 2048 > out/vllm-$3.log 2>&1 &
  local SPID=$!
  for i in $(seq 1 120); do curl -sf localhost:$PORT/health >/dev/null 2>&1 && break; sleep 5; done
  CUDA_VISIBLE_DEVICES=$2 python training/grpo.py $G --vllm-url http://localhost:$PORT $4 --out out/grpo-$3 > out/grpo-$3.log 2>&1
  kill $SPID 2>/dev/null
}

if [ "$VLLM_OK" = "1" ]; then
  echo "=== GRPO-from-base 8B sweep (vLLM, 2 configs, 2000 steps) $(date -u) ===" | tee -a $R
  run_pair 0 1 a "--steps 2000 --beta 0.04" &
  run_pair 2 3 b "--steps 2000 --beta 0.08" &
  wait
else
  echo "=== GRPO-from-base 8B (no-vLLM fallback, trimmed) $(date -u) ===" | tee -a $R
  G="--max-seq 2048 --max-completion 512 --data $TRAIN --base $BASE8B --gens 8 --reward brier"
  CUDA_VISIBLE_DEVICES=0 python training/grpo.py $G --steps 700 --beta 0.04 --out out/grpo-a > out/grpo-a.log 2>&1 &
  CUDA_VISIBLE_DEVICES=1 python training/grpo.py $G --steps 700 --beta 0.08 --out out/grpo-b > out/grpo-b.log 2>&1 &
  wait
fi
echo "SWEEP DONE $(date -u)" | tee -a $R

# ---------- EVAL (leak-free): base zero-shot + each config, full held-out ----------
echo "=== EVAL (leak-free residual held-out) $(date -u) ===" | tee -a $R
[ -f out/grpo-a/config.json ] && CUDA_VISIBLE_DEVICES=0 python training/eval.py --model out/grpo-a --data $EVAL > out/eval-a.txt 2>&1 &
[ -f out/grpo-b/config.json ] && CUDA_VISIBLE_DEVICES=1 python training/eval.py --model out/grpo-b --data $EVAL > out/eval-b.txt 2>&1 &
CUDA_VISIBLE_DEVICES=2 python training/eval.py --model $BASE8B --data $EVAL > out/eval-base.txt 2>&1 &
wait
for f in out/eval-base.txt out/eval-a.txt out/eval-b.txt; do
  [ -f "$f" ] && { echo "===== $f ====="; cat "$f"; } | tee -a $R
done
echo "=== ALL DONE $(date -u) ===" | tee -a $R
