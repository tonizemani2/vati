#!/bin/bash
# ONE-COMMAND smoke launcher (g6e.2xlarge, 1x L40S, ~$2.2/hr, ~40 min wall incl. setup, auto-stops).
# Proves the plain trl+peft stack before any 8B spend. Reuses fc-key / fc-sg / AMI from the big run.
# Run from repo root:  bash training/launch_smoke.sh
set -e
export AWS_PROFILE=default
cd "$(dirname "$0")/.."
REGION=us-west-2                   # us-east-1 had NO g6e capacity (2026-06-10); us-west-2 did
AMI=ami-0ca70308d230e8a6e          # PyTorch DLAMI in us-west-2; re-resolve if stale (AWS.md §4)
SG=sg-02bfe7647771ac44d            # fc-sg in us-west-2 (SSH from your IP — re-authorize if IP changed)
KEY=~/.ssh/fc-key.pem

echo "=== build bundle ==="
tar czf /tmp/fc_smoke.tgz training/*.py training/requirements.txt \
  data/forecastbench/trainset/grpo_train.jsonl data/forecastbench/trainset/grpo_eval.jsonl \
  data/forecastbench/trainset/sft_all.jsonl

echo "=== launch g6e.2xlarge ==="
mkdir -p out/logs
IID=$(aws ec2 run-instances --region $REGION \
  --image-id $AMI --instance-type g6e.2xlarge --key-name fc-key --security-group-ids $SG \
  --instance-initiated-shutdown-behavior stop \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":150,"VolumeType":"gp3"}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Project,Value=predictthefuture},{Key=Name,Value=fc-smoke}]' \
  --query 'Instances[0].InstanceId' --output text)
echo "IID=$IID"; echo "$IID" > out/logs/fc_smoke_instance_id.txt
aws ec2 wait instance-running --instance-ids $IID --region $REGION
IP=$(aws ec2 describe-instances --instance-ids $IID --region $REGION --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "IP=$IP"; echo "$IP" > out/logs/fc_smoke_instance_ip.txt

echo "=== wait for SSH ==="
until ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i $KEY ubuntu@$IP 'echo ok' 2>/dev/null | grep -q ok; do sleep 10; done
echo "=== upload + launch run_smoke.sh (2h cap) ==="
scp -o StrictHostKeyChecking=no -i $KEY /tmp/fc_smoke.tgz ubuntu@$IP:~/fc.tgz
scp -o StrictHostKeyChecking=no -i $KEY training/run_smoke.sh ubuntu@$IP:~/
ssh -o StrictHostKeyChecking=no -i $KEY ubuntu@$IP 'chmod +x ~/run_smoke.sh; nohup timeout 2h bash ~/run_smoke.sh >/dev/null 2>&1 & echo "smoke pid $!"'

echo
echo "SMOKE LAUNCHED on $IID ($IP). It auto-stops when done (~40 min)."
echo "  monitor:   ssh -i $KEY ubuntu@$IP 'cat ~/RESULTS.txt; tail -5 ~/run.log'"
echo "  stop now:  aws ec2 stop-instances --instance-ids $IID --region $REGION"
echo "  terminate: aws ec2 terminate-instances --instance-ids $IID --region $REGION"
