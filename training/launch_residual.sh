#!/bin/bash
# Launch the TOP-QUALITY residual-on-prior GRPO run on g6e.12xlarge (4x L40S), ON-DEMAND for guaranteed
# completion (no spot reclaim mid-GRPO). Uploads code+residual data, runs run_residual.sh under nohup
# with a 10h timeout (hard cost cap ~$105; expected ~$50-70). Auto-stops the box on SSH failure so a
# running GPU can never silently bleed. Safe to background.
#   bash training/launch_residual.sh
set -u
export AWS_PROFILE=default
cd "$(dirname "$0")/.."
REGION=us-west-2
AMI=ami-0ca70308d230e8a6e          # PyTorch 2.7 DLAMI us-west-2 (verified live 2026-06-14)
SG=sg-02bfe7647771ac44d            # fc-sg (SSH from your IP)
KEY=~/.ssh/fc-key.pem
TYPE=g6e.12xlarge
mkdir -p out/logs
LOG=out/logs/launch_residual.log
exec >> "$LOG" 2>&1
echo "================ residual GRPO launch $(date -u) ================"

echo "=== build bundle ==="
tar czf /tmp/fc_residual.tgz training/*.py training/requirements.txt \
  data/forecastbench/trainset/grpo_residual_train.jsonl \
  data/forecastbench/trainset/grpo_residual_eval.jsonl || { echo "bundle FAILED"; exit 1; }
echo "bundle: $(du -h /tmp/fc_residual.tgz | cut -f1)"

# launch on-demand, retry across a 30-min window on capacity errors
IID=""; DEADLINE=$(( $(date +%s) + 1800 ))
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  IID=$(aws ec2 run-instances --region $REGION --image-id $AMI --instance-type $TYPE \
    --key-name fc-key --security-group-ids $SG --instance-initiated-shutdown-behavior stop \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":250,"VolumeType":"gp3"}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Project,Value=predictthefuture},{Key=Name,Value=fc-residual-grpo}]' \
    --query 'Instances[0].InstanceId' --output text 2>>"$LOG")
  [ -n "$IID" ] && [ "$IID" != "None" ] && { echo "launched $IID $(date -u)"; break; }
  echo "no $TYPE capacity $(date -u); retry in 120s"; IID=""; sleep 120
done
[ -z "$IID" ] && { echo "=== GAVE UP: no $TYPE capacity in 30min ==="; exit 1; }
echo "$IID" > out/logs/fc_residual_instance_id.txt

aws ec2 wait instance-running --instance-ids $IID --region $REGION
IP=$(aws ec2 describe-instances --instance-ids $IID --region $REGION \
      --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "$IP" > out/logs/fc_residual_instance_ip.txt
echo "IID=$IID IP=$IP"

SSH_OK=0
for i in $(seq 1 90); do  # 15 min
  if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i $KEY ubuntu@$IP 'echo ok' 2>/dev/null | grep -q ok; then SSH_OK=1; break; fi
  sleep 10
done
if [ "$SSH_OK" != "1" ]; then
  echo "=== SSH FAILED 15min — STOPPING $IID to avoid bleed (check SG allows your IP) ==="
  aws ec2 stop-instances --instance-ids $IID --region $REGION >/dev/null 2>&1
  exit 1
fi

echo "=== upload + launch run_residual.sh (10h cap) $(date -u) ==="
scp -o StrictHostKeyChecking=no -i $KEY /tmp/fc_residual.tgz ubuntu@$IP:~/fc.tgz
scp -o StrictHostKeyChecking=no -i $KEY training/run_residual.sh ubuntu@$IP:~/
ssh -o StrictHostKeyChecking=no -i $KEY ubuntu@$IP \
  'chmod +x ~/run_residual.sh; rm -f ~/RESULTS.txt; nohup timeout 10h bash ~/run_residual.sh >/dev/null 2>&1 & echo "residual-grpo pid $!"'
echo "=== LAUNCHED on $IID ($IP) — auto-stops when done (~4-5h) $(date -u) ==="
