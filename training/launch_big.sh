#!/bin/bash
# ONE-COMMAND launcher for the QUALITY run (g6e.12xlarge, 4x L40S, ~$250-400, ~24-36h, auto-stops;
# 40h hard cap ≈ $420 worst case). vLLM-server sweep at Mantic-floor coverage; see run_big.sh.
# Reuses the fc-key / fc-sg / AMI created for the first-signal run. Run from repo root:  bash training/launch_big.sh
# It launches the instance, uploads code+data, starts run_big.sh under nohup, and prints how to monitor.
set -e
export AWS_PROFILE=default
cd "$(dirname "$0")/.."
REGION=us-west-2                   # us-east-1 had NO g6e capacity (2026-06-10); us-west-2 did
AMI=ami-0ca70308d230e8a6e          # PyTorch 2.7 DLAMI in us-west-2; re-resolve if stale (AWS.md §4)
SG=sg-02bfe7647771ac44d            # fc-sg in us-west-2 (SSH from your IP — re-authorize if IP changed)
KEY=~/.ssh/fc-key.pem
# (us-east-1 equivalents if capacity returns there: AMI ami-012ba162b9cd2729c, SG sg-03d236ab088046d0a)

echo "=== re-merge latest SFT traces + build bundle ==="
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
"
tar czf /tmp/fc_big.tgz training/*.py training/requirements.txt \
  data/forecastbench/trainset/grpo_train.jsonl data/forecastbench/trainset/grpo_eval.jsonl data/forecastbench/trainset/sft_all.jsonl

echo "=== launch g6e.12xlarge ==="
IID=$(aws ec2 run-instances --region $REGION \
  --image-id $AMI --instance-type g6e.12xlarge --key-name fc-key --security-group-ids $SG \
  --instance-initiated-shutdown-behavior stop \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":300,"VolumeType":"gp3"}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Project,Value=predictthefuture},{Key=Name,Value=fc-big-sweep}]' \
  --query 'Instances[0].InstanceId' --output text)
echo "IID=$IID"; echo "$IID" > out/logs/fc_big_instance_id.txt
aws ec2 wait instance-running --instance-ids $IID --region $REGION
IP=$(aws ec2 describe-instances --instance-ids $IID --region $REGION --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "IP=$IP"; echo "$IP" > out/logs/fc_big_instance_ip.txt

echo "=== wait for SSH ==="
until ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i $KEY ubuntu@$IP 'echo ok' 2>/dev/null | grep -q ok; do sleep 10; done
echo "=== upload + launch run_big.sh (28h cap) ==="
scp -o StrictHostKeyChecking=no -i $KEY /tmp/fc_big.tgz ubuntu@$IP:~/fc.tgz
scp -o StrictHostKeyChecking=no -i $KEY training/run_big.sh ubuntu@$IP:~/
ssh -o StrictHostKeyChecking=no -i $KEY ubuntu@$IP 'chmod +x ~/run_big.sh; nohup timeout 40h bash ~/run_big.sh >/dev/null 2>&1 & echo "big sweep pid $!"'

echo
echo "BIG SWEEP LAUNCHED on $IID ($IP). It auto-stops when done."
echo "  monitor:   ssh -i $KEY ubuntu@$IP 'cat ~/RESULTS.txt; tail ~/run.log'"
echo "  stop now:  aws ec2 stop-instances --instance-ids $IID --region $REGION"
echo "  terminate: aws ec2 terminate-instances --instance-ids $IID --region $REGION"
