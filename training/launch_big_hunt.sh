#!/bin/bash
# Capacity-hunting launcher for the QUALITY 8B run. Rotates us-west-2 AZs trying g6e.12xlarge
# (4x L40S), retrying for ~30 min. If the 4-GPU box can't be had, falls back to g6e.2xlarge
# (1x L40S, proven available) running the single-GPU pipeline run_all.sh. Auto-stops either way.
# Run from repo root:  bash training/launch_big_hunt.sh
set -u
export AWS_PROFILE=default
cd "$(dirname "$0")/.."
REGION=us-west-2
AMI=ami-0ca70308d230e8a6e
SG=sg-02bfe7647771ac44d
KEY=~/.ssh/fc-key.pem
SUBNETS=(subnet-0480b80b285333f57 subnet-09f351475ec405356 subnet-0f2786564a7635c3b subnet-0328da6ca39b02388) # a b c d
LOG=out/logs/launch_big_hunt.log
mkdir -p out/logs
say(){ echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$LOG"; }

say "=== re-merge SFT traces + build bundle ==="
python3 -c "
import json, glob
seen=set(); rows=[]
for f in sorted(glob.glob('data/forecastbench/trainset/sft_*.jsonl')):
    if f.endswith('sft_all.jsonl'): continue
    for l in open(f):
        if not l.strip(): continue
        try: d=json.loads(l)
        except: continue
        a=''.join(m.get('content','') for m in d.get('messages',[]) if m.get('role')=='assistant')
        k=(d.get('id'), a[:200])
        if k in seen: continue
        seen.add(k); rows.append(l.rstrip(chr(10)))
open('data/forecastbench/trainset/sft_all.jsonl','w').write(chr(10).join(rows)+chr(10))
print('sft_all.jsonl ->', len(rows), 'traces')
" | tee -a "$LOG"
tar czf /tmp/fc_big.tgz training/*.py training/requirements.txt \
  data/forecastbench/trainset/grpo_train.jsonl data/forecastbench/trainset/grpo_eval.jsonl data/forecastbench/trainset/sft_all.jsonl

TYPE=g6e.12xlarge
RUNNER=run_big.sh
CAP=40h
IID=""
ROUNDS=20
for r in $(seq 1 $ROUNDS); do
  for i in 0 1 2 3; do
    AZ=$(("$i"+1)); SUB=${SUBNETS[$i]}
    say "round $r/$ROUNDS  try $TYPE in subnet $SUB"
    IID=$(aws ec2 run-instances --region $REGION \
      --image-id $AMI --instance-type $TYPE --key-name fc-key --security-group-ids $SG \
      --subnet-id $SUB --instance-initiated-shutdown-behavior stop \
      --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":300,"VolumeType":"gp3"}}]' \
      --tag-specifications 'ResourceType=instance,Tags=[{Key=Project,Value=predictthefuture},{Key=Name,Value=fc-big-sweep}]' \
      --query 'Instances[0].InstanceId' --output text 2>>"$LOG") && [ -n "$IID" ] && [ "$IID" != "None" ] && { say "GOT $TYPE -> $IID in $SUB"; break 2; }
    IID=""
  done
  say "round $r: no capacity for $TYPE, sleeping 90s"
  sleep 90
done

if [ -z "$IID" ]; then
  say "=== FALLBACK: g6e.2xlarge (1x L40S) single-GPU pipeline ==="
  TYPE=g6e.2xlarge; RUNNER=run_all.sh; CAP=28h
  for i in 0 1 2 3; do
    SUB=${SUBNETS[$i]}
    IID=$(aws ec2 run-instances --region $REGION \
      --image-id $AMI --instance-type $TYPE --key-name fc-key --security-group-ids $SG \
      --subnet-id $SUB --instance-initiated-shutdown-behavior stop \
      --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":300,"VolumeType":"gp3"}}]' \
      --tag-specifications 'ResourceType=instance,Tags=[{Key=Project,Value=predictthefuture},{Key=Name,Value=fc-big-fallback}]' \
      --query 'Instances[0].InstanceId' --output text 2>>"$LOG") && [ -n "$IID" ] && [ "$IID" != "None" ] && { say "GOT $TYPE -> $IID in $SUB"; break; }
    IID=""
  done
fi

[ -z "$IID" ] && { say "FATAL: no capacity for 12xlarge OR 2xlarge after hunt. Aborting, \$0 spent."; exit 1; }

echo "$IID" > out/logs/fc_big_instance_id.txt
echo "$TYPE" > out/logs/fc_big_instance_type.txt
say "wait instance-running $IID"
aws ec2 wait instance-running --instance-ids $IID --region $REGION
IP=$(aws ec2 describe-instances --instance-ids $IID --region $REGION --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "$IP" > out/logs/fc_big_instance_ip.txt
say "IP=$IP  type=$TYPE  runner=$RUNNER  cap=$CAP"

say "wait for SSH"
until ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i $KEY ubuntu@$IP 'echo ok' 2>/dev/null | grep -q ok; do sleep 10; done
say "upload + launch $RUNNER"
scp -o StrictHostKeyChecking=no -i $KEY /tmp/fc_big.tgz ubuntu@$IP:~/fc.tgz
scp -o StrictHostKeyChecking=no -i $KEY training/$RUNNER ubuntu@$IP:~/
ssh -o StrictHostKeyChecking=no -i $KEY ubuntu@$IP "chmod +x ~/$RUNNER; nohup timeout $CAP bash ~/$RUNNER >/dev/null 2>&1 & echo launched pid \$!" | tee -a "$LOG"

say "LAUNCHED on $IID ($IP) type=$TYPE. Auto-stops when done."
say "monitor:  ssh -i $KEY ubuntu@$IP 'cat ~/RESULTS.txt; tail ~/run.log'"
say "stop:     aws ec2 stop-instances --instance-ids $IID --region $REGION"
say "terminate:aws ec2 terminate-instances --instance-ids $IID --region $REGION"
