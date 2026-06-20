#!/bin/bash
# Watcher for the first-signal run: pulls RESULTS.txt + run.log locally every 5 min so results are
# preserved even if SSH is flaky or the box auto-stops (run_all.sh leaves a 10-min shutdown grace).
# Exits when the pipeline reports done/failed or the instance is no longer running. Self-bounded 24h.
set -u
export AWS_PROFILE=default
cd "$(dirname "$0")/.."
REGION=us-west-2
KEY=~/.ssh/fc-key.pem
IID=$(cat out/logs/fc_signal_instance_id.txt)
IP=$(cat out/logs/fc_signal_instance_ip.txt)
LOG=out/logs/watch_signal.log
exec >> "$LOG" 2>&1
echo "===== watch start $IID ($IP) $(date -u) ====="
DEADLINE=$(( $(date +%s) + 24*3600 ))
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  ST=$(aws ec2 describe-instances --instance-ids $IID --region $REGION --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null)
  scp -o StrictHostKeyChecking=no -o ConnectTimeout=15 -i $KEY ubuntu@$IP:~/RESULTS.txt out/logs/RESULTS_signal.txt 2>/dev/null \
    && echo "pulled RESULTS $(date -u)"
  scp -o StrictHostKeyChecking=no -o ConnectTimeout=15 -i $KEY ubuntu@$IP:~/run.log out/logs/run_signal.log 2>/dev/null
  if grep -qE 'ALL DONE|=== FAILED|PIPELINE EXIT' out/logs/RESULTS_signal.txt 2>/dev/null; then
    echo "===== pipeline terminal state seen $(date -u) ====="; sleep 30
    scp -o StrictHostKeyChecking=no -o ConnectTimeout=15 -i $KEY ubuntu@$IP:~/RESULTS.txt out/logs/RESULTS_signal.txt 2>/dev/null
    break
  fi
  if [ "$ST" != "running" ] && [ "$ST" != "pending" ]; then
    echo "===== instance state=$ST — stopping watch $(date -u) ====="; break
  fi
  sleep 300
done
echo "===== watch end $(date -u) ====="
