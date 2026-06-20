# training/AWS.md — best-practice AWS setup for the forecasting-LLM POC

Account-verified runbook (checked 2026-06). Goal: train Qwen3-8B (SFT→GRPO→eval) on AWS using the
**credit account**, isolated from the miningterminal work, no wasted credits.

## 0. Account & isolation (verified)
- **Use the `default` profile → account `405844305300` (user `chime-dev`), region `us-east-1`.**
- The `orebody` (mining) profile keys are **dead** (`InvalidClientTokenId`) → you literally cannot run
  on the mining account by accident. Isolation is automatic.
- ⚠️ **Confirm your credits are on `405844305300`** (Console → Billing → Credits). If they're on another
  account, configure that account's access key as a new profile and use it below.
- Before every launch: `export AWS_PROFILE=default && aws sts get-caller-identity` → must show `405844305300`.
- Tag everything `Project=predictthefuture` so the spend is cleanly separable from mining in Cost Explorer.

## 1. Quotas — already fine (no request needed)
- Running On-Demand **G** instances: **256 vCPU** (L40S/A10G) ✅
- Running On-Demand **P** instances: **384 vCPU** (H100/A100) ✅  (enough for a full p5.48xlarge = 192 vCPU)

## 2. Pre-flight (5 min, console or CLI)
- **Budget alarm:** Billing → Budgets → cap (e.g. $800) with an email alert. Don't silently burn credits.
- **Key pair:** `aws ec2 create-key-pair --key-name fc-key --query KeyMaterial --output text > ~/.ssh/fc-key.pem && chmod 600 ~/.ssh/fc-key.pem`
- **Security group (SSH from your IP only):**
  ```bash
  MYIP=$(curl -s https://checkip.amazonaws.com)
  SG=$(aws ec2 create-security-group --group-name fc-sg --description "forecast-llm ssh" --query GroupId --output text)
  aws ec2 authorize-security-group-ingress --group-id $SG --protocol tcp --port 22 --cidr ${MYIP}/32
  ```

## 3. Instance — pick by credit appetite (all on `default`/us-east-1)
| Goal | Instance | GPUs | ~$/hr | POC time | ~credits |
|---|---|---|---|---|---|
| Cheap + reliable | `g6e.2xlarge` | 1× L40S 48GB | ~2.2 | 3–4 days | $200–500 |
| **Best balance (rec)** | **`g6e.12xlarge`** | **4× L40S 48GB** | ~10.5 | 1.5–2 days | $400–700 |
| Max speed | `p5.48xlarge` | 8× H100 80GB | ~55 | ~1 day | $1.3–2.6k |

- **Recommendation: `g6e.12xlarge`** — 4× L40S is on-demand-available (no capacity-block fight that p5
  often needs), enough VRAM (48GB) for 8B QLoRA+vLLM, and lets you run SFT then a **4-way parallel GRPO
  sweep** (see §6) to land a *tuned* model in ~1.5 days. Single L40S (`g6e.2xlarge`) is the frugal fallback.
- Only use `p5.48xlarge` if you want H100 speed AND reserve a **Capacity Block** first (p5 on-demand often
  returns `InsufficientInstanceCapacity`).

## 4. AMI
Use the **AWS Deep Learning OSS Nvidia Driver AMI (GPU PyTorch 2.x, Ubuntu 22.04)** — drivers + CUDA + conda
preinstalled (no driver hell). Find the latest id:
```bash
aws ssm get-parameters-by-path --path /aws/service/deeplearning/ami/x86_64/ \
  --query "Parameters[?contains(Name,'pytorch') && contains(Name,'ubuntu-22.04')].[Name,Value]" \
  --output text --region us-east-1 | sort | tail -5      # pick the newest oss-nvidia pytorch ami-id
AMI=ami-xxxxxxxx   # paste the ami-id from above
```

## 5. Launch
```bash
INSTANCE=g6e.12xlarge          # or g6e.2xlarge / p5.48xlarge
aws ec2 run-instances \
  --image-id $AMI --instance-type $INSTANCE --key-name fc-key --security-group-ids $SG \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":200,"VolumeType":"gp3"}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Project,Value=predictthefuture}]' \
  --query 'Instances[0].InstanceId' --output text
# get the public IP:
aws ec2 describe-instances --filters Name=tag:Project,Values=predictthefuture \
  Name=instance-state-name,Values=running --query 'Reservations[].Instances[].PublicIpAddress' --output text
```

## 6. Run
```bash
# --- Mac: bundle code + data (~60MB) ---
cd ~/Desktop/predictthefuture
cat data/forecastbench/trainset/sft_market.jsonl data/forecastbench/trainset/sft_dataset.jsonl \
    > data/forecastbench/trainset/sft_all.jsonl 2>/dev/null || cp data/forecastbench/trainset/sft_market.jsonl data/forecastbench/trainset/sft_all.jsonl
tar czf fc.tgz training/ data/forecastbench/trainset/grpo_train.jsonl \
    data/forecastbench/trainset/grpo_eval.jsonl data/forecastbench/trainset/sft_all.jsonl
scp -i ~/.ssh/fc-key.pem fc.tgz ubuntu@<PUBLIC_IP>:~/

# --- on the box ---
ssh -i ~/.ssh/fc-key.pem ubuntu@<PUBLIC_IP>
tar xzf fc.tgz
# Install into a FRESH env, not the AMI base — pip-installing unsloth/vllm over the DLAMI's
# preinstalled torch is the #1 way to waste GPU hours. Verify versions resolve before the big run.
pip install -r training/requirements.txt
python -c "import torch,unsloth,trl,vllm; print('torch',torch.__version__,'cuda',torch.cuda.is_available(),torch.cuda.device_count(),'GPUs')"
# ^ must print cuda True and 4 GPUs (on g6e.12xlarge) before proceeding.

# --- STEP 0: SMOKE TEST (do this FIRST — proves the whole loop in ~15 min on a throwaway 1.7B) ---
# Catches dep/parse/format breakage before you burn hours on 8B. FORECAST_LLM §2 calls for this.
python training/sft.py  --model unsloth/Qwen3-1.7B --data data/forecastbench/trainset/sft_market.jsonl \
    --out out/smoke-sft --epochs 1
python training/grpo.py --model unsloth/Qwen3-1.7B --base out/smoke-sft --steps 10 --out out/smoke-grpo
python training/eval.py --model out/smoke-grpo --limit 50
# If all three complete and eval prints a Brier line → the pipeline is sound. Now run the real 8B job.

# --- REAL RUN ---
# NOTE: sft_dataset.jsonl (numeric traces) never finished — SFT runs on the 342 market traces only,
# which is enough to lock the OUTPUT FORMAT (GRPO does the real calibration on 19k rows). The cat
# below falls back to sft_market.jsonl alone, which is the intended behavior for now.
python training/sft.py  --data data/forecastbench/trainset/sft_all.jsonl --out out/sft-qwen3-8b

# single GPU:
python training/grpo.py --base out/sft-qwen3-8b --data data/forecastbench/trainset/grpo_train.jsonl --out out/grpo
# OR 4-way parallel sweep on g6e.12xlarge (one config per GPU; vary reward/lr/steps):
CUDA_VISIBLE_DEVICES=0 python training/grpo.py --base out/sft-qwen3-8b --steps 1500 --out out/grpo-a &
CUDA_VISIBLE_DEVICES=1 python training/grpo.py --base out/sft-qwen3-8b --steps 2500 --out out/grpo-b &
CUDA_VISIBLE_DEVICES=2 python training/grpo.py --base out/sft-qwen3-8b --gens 12   --out out/grpo-c &
CUDA_VISIBLE_DEVICES=3 python training/grpo.py --base out/sft-qwen3-8b --gens 6    --out out/grpo-d &
wait

python training/eval.py --model out/grpo-a --data data/forecastbench/trainset/grpo_eval.jsonl --limit 2000
# (eval each; keep the best by leak-free Brier/AUC)
```

## 7. Cost hygiene (don't waste credits)
- You pay for every **running** hour, even idle. **STOP** the instance the moment a run finishes:
  `aws ec2 stop-instances --instance-ids <id>` (keeps the EBS so you can restart).
- **Terminate** when fully done: `aws ec2 terminate-instances --instance-ids <id>` (also delete the EBS).
- The instance runs training locally — it does **not** need or use your `~/.aws` keys, so no credential
  ever lands on the box. You only use the `default` profile to launch/stop. Clean.
