#!/bin/bash
# Mumbai (ap-south-1) launcher for the QUALITY 8B run on g6e.12xlarge (4x L40S).
# Non-US region — US AZs get the g6e capacity grabbed first. Rotates the 2 Mumbai AZs that offer
# g6e.12xlarge, retries ~20 rounds. Auto-stops on completion. Run from repo root.
set -u
export AWS_PROFILE=default
cd "$(dirname "$0")/.."
REGION=ap-south-1
AMI=ami-0eb5a4f0d81f671e3
SG=sg-0be0ce8e2732e8230
KEY=~/.ssh/fc-key.pem
SUBNETS=(subnet-0d932ceebc50b6dff subnet-083e1c3e15e7438d6)   # 1a 1b (offer g6e.12xlarge)
LOG=out/logs/launch_mumbai.log
mkdir -p out/logs
say(){ echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$LOG"; }

[ -f /tmp/fc_big.tgz ] || { say "rebuild bundle"; tar czf /tmp/fc_big.tgz training/*.py training/requirements.txt \
  data/forecastbench/trainset/grpo_train.jsonl data/forecastbench/trainset/grpo_eval.jsonl data/forecastbench/trainset/sft_all.jsonl; }

TYPE=g6e.12xlarge; IID=""
for r in $(seq 1 20); do
  for SUB in "${SUBNETS[@]}"; do
    say "round $r/20  try $TYPE in $SUB"
    IID=$(aws ec2 run-instances --region $REGION \
      --image-id $AMI --instance-type $TYPE --key-name fc-key --security-group-ids $SG \
      --subnet-id $SUB --instance-initiated-shutdown-behavior stop \
      --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":300,"VolumeType":"gp3"}}]' \
      --tag-specifications 'ResourceType=instance,Tags=[{Key=Project,Value=predictthefuture},{Key=Name,Value=fc-big-mumbai}]' \
      --query 'Instances[0].InstanceId' --output text 2>>"$LOG") && [ -n "$IID" ] && [ "$IID" != "None" ] && { say "GOT $TYPE -> $IID in $SUB"; break 2; }
    IID=""
  done
  say "round $r: no capacity, sleep 90s"; sleep 90
done

[ -z "$IID" ] && { say "FATAL: no g6e.12xlarge capacity in Mumbai after 20 rounds. \$0 spent."; exit 1; }

echo "$IID" > out/logs/fc_mum_instance_id.txt
say "wait instance-running $IID"
aws ec2 wait instance-running --instance-ids $IID --region $REGION
IP=$(aws ec2 describe-instances --instance-ids $IID --region $REGION --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "$IP" > out/logs/fc_mum_instance_ip.txt
say "IP=$IP"
say "wait for SSH"
until ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i $KEY ubuntu@$IP 'echo ok' 2>/dev/null | grep -q ok; do sleep 10; done
say "upload + launch run_big.sh (40h cap)"
scp -o StrictHostKeyChecking=no -i $KEY /tmp/fc_big.tgz ubuntu@$IP:~/fc.tgz
scp -o StrictHostKeyChecking=no -i $KEY training/run_big.sh ubuntu@$IP:~/
ssh -o StrictHostKeyChecking=no -i $KEY ubuntu@$IP 'chmod +x ~/run_big.sh; nohup timeout 40h bash ~/run_big.sh >/dev/null 2>&1 & echo launched pid $!' | tee -a "$LOG"
say "LAUNCHED on $IID ($IP) g6e.12xlarge Mumbai. Auto-stops when done."
say "monitor:  ssh -i $KEY ubuntu@$IP 'cat ~/RESULTS.txt; tail ~/run.log'"
say "stop:     aws ec2 stop-instances --instance-ids $IID --region $REGION"
say "terminate:aws ec2 terminate-instances --instance-ids $IID --region $REGION"
