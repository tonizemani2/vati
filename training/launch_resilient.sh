#!/bin/bash
# CAPACITY-RESILIENT first-signal launcher (2026-06-12). AWS g6e capacity is flaky: restarting the
# pinned stopped box hits InsufficientInstanceCapacity when its AZ is dry. This launcher tries the
# pinned box first (cached deps), and on capacity failure launches a FRESH g6e.2xlarge in ANY AZ
# AWS will give us, retrying across a 4h window. Launches EXACTLY ONE box, uploads code+data, runs
# run_all.sh under nohup (auto-stops, 26h cap). If SSH never connects, it STOPS the box so a running
# GPU can never silently bleed. Safe to run in the background and go to bed.
#   bash training/launch_resilient.sh
set -u
export AWS_PROFILE=default
cd "$(dirname "$0")/.."
REGION=us-west-2
PINNED=i-03275f813e2ef0ae5
AMI=ami-0ca70308d230e8a6e          # PyTorch 2.7 DLAMI, us-west-2 (re-resolve if stale: training/AWS.md)
SG=sg-02bfe7647771ac44d            # fc-sg us-west-2 (SSH from your IP)
KEY=~/.ssh/fc-key.pem
DEADLINE=$(( $(date +%s) + 4*3600 ))   # keep trying up to 4h, then give up
mkdir -p out/logs
LOG=out/logs/launch_resilient.log
exec >> "$LOG" 2>&1
echo "================ resilient launch start $(date -u) ================"

echo "=== build bundle ==="
tar czf /tmp/fc_signal.tgz training/*.py training/requirements.txt \
  data/forecastbench/trainset/grpo_train.jsonl data/forecastbench/trainset/grpo_eval.jsonl \
  data/forecastbench/trainset/sft_all.jsonl || { echo "bundle build FAILED"; exit 1; }

IID=""; FRESH=0
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  # 1) try the pinned stopped box (cached deps + HF model) first
  ST=$(aws ec2 describe-instances --instance-ids $PINNED --region $REGION \
        --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null)
  if [ "$ST" = "stopping" ]; then aws ec2 wait instance-stopped --instance-ids $PINNED --region $REGION 2>/dev/null; ST=stopped; fi
  if [ "$ST" = "running" ]; then IID=$PINNED; echo "pinned already running $(date -u)"; break; fi
  if [ "$ST" = "stopped" ]; then
    if aws ec2 start-instances --instance-ids $PINNED --region $REGION >/dev/null 2>>"$LOG"; then
      IID=$PINNED; echo "started pinned $PINNED $(date -u)"; break
    else
      echo "pinned start: no capacity $(date -u)"
    fi
  fi
  # 2) fall back to a FRESH g6e.2xlarge in whatever AZ has capacity
  NEW=$(aws ec2 run-instances --region $REGION --image-id $AMI --instance-type g6e.2xlarge \
    --key-name fc-key --security-group-ids $SG --instance-initiated-shutdown-behavior stop \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":200,"VolumeType":"gp3"}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Project,Value=predictthefuture},{Key=Name,Value=fc-signal-resilient}]' \
    --query 'Instances[0].InstanceId' --output text 2>>"$LOG")
  if [ -n "$NEW" ] && [ "$NEW" != "None" ]; then IID=$NEW; FRESH=1; echo "launched fresh $NEW $(date -u)"; break; fi
  echo "no g6e capacity (pinned+fresh) $(date -u); retry in 180s"; sleep 180
done

if [ -z "$IID" ]; then echo "=== GAVE UP: no g6e capacity in 4h window $(date -u) ==="; exit 1; fi
echo "$IID" > out/logs/fc_signal_instance_id.txt
echo "=== acquired $IID (fresh=$FRESH) — waiting for running $(date -u) ==="
aws ec2 wait instance-running --instance-ids $IID --region $REGION
IP=$(aws ec2 describe-instances --instance-ids $IID --region $REGION \
      --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "$IP" > out/logs/fc_signal_instance_ip.txt
echo "IP=$IP"

# bounded SSH wait — if it never connects, STOP the box so a running GPU can't bleed
SSH_OK=0
for i in $(seq 1 90); do  # 90 x 10s = 15 min
  if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i $KEY ubuntu@$IP 'echo ok' 2>/dev/null | grep -q ok; then SSH_OK=1; break; fi
  sleep 10
done
if [ "$SSH_OK" != "1" ]; then
  echo "=== SSH FAILED after 15min — STOPPING $IID to avoid bleed (check SG allows your IP) $(date -u) ==="
  aws ec2 stop-instances --instance-ids $IID --region $REGION >/dev/null 2>&1
  exit 1
fi

echo "=== upload + launch run_all.sh (26h cap) $(date -u) ==="
scp -o StrictHostKeyChecking=no -i $KEY /tmp/fc_signal.tgz ubuntu@$IP:~/fc.tgz
scp -o StrictHostKeyChecking=no -i $KEY training/run_all.sh ubuntu@$IP:~/
ssh -o StrictHostKeyChecking=no -i $KEY ubuntu@$IP \
  'chmod +x ~/run_all.sh; rm -f ~/RESULTS.txt; nohup timeout 26h bash ~/run_all.sh >/dev/null 2>&1 & echo "first-signal pid $!"'
echo "=== LAUNCHED on $IID ($IP) — auto-stops when done (~16-22h) $(date -u) ==="
