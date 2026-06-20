#!/bin/bash
# FIRST-SIGNAL launcher: restarts the existing smoke box (i-03275f813e2ef0ae5, g6e.2xlarge, deps +
# smoke outputs cached on its disk) and runs the full single-GPU pipeline (run_all.sh: 8B SFT →
# GRPO 700 steps → leak-free eval vs zero-shot). ~16-22h, ~$35-55, auto-stops.
# Run from repo root:  bash training/launch_signal.sh
set -e
export AWS_PROFILE=default
cd "$(dirname "$0")/.."
REGION=us-west-2
IID=${1:-i-03275f813e2ef0ae5}
KEY=~/.ssh/fc-key.pem

echo "=== build bundle ==="
tar czf /tmp/fc_signal.tgz training/*.py training/requirements.txt \
  data/forecastbench/trainset/grpo_train.jsonl data/forecastbench/trainset/grpo_eval.jsonl \
  data/forecastbench/trainset/sft_all.jsonl

echo "=== start $IID ==="
mkdir -p out/logs
# Always cycle through a clean stop: a "running" box may have a pending trap shutdown (sleep N;
# shutdown) that `shutdown -c` can't cancel — launching into that race killed a run once (2026-06-11).
STATE=$(aws ec2 describe-instances --instance-ids $IID --region $REGION --query 'Reservations[0].Instances[0].State.Name' --output text)
if [ "$STATE" = "running" ]; then aws ec2 stop-instances --instance-ids $IID --region $REGION >/dev/null; fi
[ "$STATE" != "stopped" ] && aws ec2 wait instance-stopped --instance-ids $IID --region $REGION
aws ec2 start-instances --instance-ids $IID --region $REGION >/dev/null
aws ec2 wait instance-running --instance-ids $IID --region $REGION
IP=$(aws ec2 describe-instances --instance-ids $IID --region $REGION --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "IP=$IP"; echo "$IID" > out/logs/fc_signal_instance_id.txt; echo "$IP" > out/logs/fc_signal_instance_ip.txt

echo "=== wait for SSH ==="
until ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i $KEY ubuntu@$IP 'echo ok' 2>/dev/null | grep -q ok; do sleep 10; done
echo "=== upload + launch run_all.sh (26h cap) ==="
scp -o StrictHostKeyChecking=no -i $KEY /tmp/fc_signal.tgz ubuntu@$IP:~/fc.tgz
scp -o StrictHostKeyChecking=no -i $KEY training/run_all.sh ubuntu@$IP:~/
ssh -o StrictHostKeyChecking=no -i $KEY ubuntu@$IP 'chmod +x ~/run_all.sh; rm -f ~/RESULTS.txt; nohup timeout 26h bash ~/run_all.sh >/dev/null 2>&1 & echo "first-signal pid $!"'

echo
echo "FIRST-SIGNAL RUN LAUNCHED on $IID ($IP). Auto-stops when done (~16-22h)."
echo "  monitor:   ssh -i $KEY ubuntu@$IP 'cat ~/RESULTS.txt | tail; tail -3 ~/run.log'"
echo "  stop now:  aws ec2 stop-instances --instance-ids $IID --region $REGION"
