#!/bin/bash
set -Eeuo pipefail

export AWS_EC2_METADATA_DISABLED=true
REGION="${REGION:-us-east-1}"
LAKE_PREFIX="${LAKE_PREFIX:-s3://vaticinus-datalake-405844305300-us-east-1/research-papers}"
BUDGET_USD="${BUDGET_USD:-25}"
INSTANCE_TYPE="${INSTANCE_TYPE:-c7i.large}"
ROLE_NAME="${ROLE_NAME:-research-papers-ec2-role-20260618}"
PROFILE_NAME="${PROFILE_NAME:-research-papers-ec2-profile-20260618}"
POLICY_NAME="${POLICY_NAME:-research-papers-pilot-s3}"
RUN_ID="${RUN_ID:-pilot-$(date -u +%Y%m%dT%H%M%SZ)}"
SUBNET_ID="${SUBNET_ID:-subnet-014dd360c58a24b90}"
SECURITY_GROUP_ID="${SECURITY_GROUP_ID:-sg-0252baa695b9522de}"
MAX_RUNTIME_SECONDS="${MAX_RUNTIME_SECONDS:-7200}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$REPO_ROOT/data/research_papers"
mkdir -p "$OUT_DIR"

if [[ "$BUDGET_USD" != "25" ]]; then
  echo "refusing: this pilot was approved for BUDGET_USD=25; got $BUDGET_USD" >&2
  exit 2
fi

if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
    >/dev/null
fi

aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore \
  >/dev/null || true

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "$POLICY_NAME" \
  --policy-document '{
    "Version":"2012-10-17",
    "Statement":[
      {
        "Effect":"Allow",
        "Action":["s3:ListBucket"],
        "Resource":[
          "arn:aws:s3:::vaticinus-datalake-405844305300-us-east-1",
          "arn:aws:s3:::arxiv",
          "arn:aws:s3:::openalex"
        ]
      },
      {
        "Effect":"Allow",
        "Action":["s3:GetObject"],
        "Resource":[
          "arn:aws:s3:::arxiv/*",
          "arn:aws:s3:::openalex/*",
          "arn:aws:s3:::vaticinus-datalake-405844305300-us-east-1/research-papers/*"
        ]
      },
      {
        "Effect":"Allow",
        "Action":["s3:PutObject","s3:AbortMultipartUpload","s3:ListMultipartUploadParts"],
        "Resource":"arn:aws:s3:::vaticinus-datalake-405844305300-us-east-1/research-papers/*"
      }
    ]
  }' >/dev/null

if ! aws iam get-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null
fi
if ! aws iam get-instance-profile --instance-profile-name "$PROFILE_NAME" \
  --query "InstanceProfile.Roles[?RoleName=='$ROLE_NAME'].RoleName" --output text | grep -q "$ROLE_NAME"; then
  aws iam add-role-to-instance-profile --instance-profile-name "$PROFILE_NAME" --role-name "$ROLE_NAME" >/dev/null
  sleep 15
fi

AMI_ID="$(aws ssm get-parameter \
  --region "$REGION" \
  --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --query 'Parameter.Value' --output text)"

USER_DATA="$(mktemp)"
{
  echo '#!/bin/bash'
  echo "export REGION='$REGION'"
  echo "export LAKE_PREFIX='$LAKE_PREFIX'"
  echo "export RUN_ID='$RUN_ID'"
  echo "export MAX_RUNTIME_SECONDS='$MAX_RUNTIME_SECONDS'"
  echo "export DOWNLOAD_ARXIV_SHARD='1'"
  echo "export MAX_ARXIV_TAR_MB='700'"
  sed '1d' "$REPO_ROOT/scripts/research_papers_ec2_pilot.sh"
} > "$USER_DATA"

LAUNCH_JSON="$(aws ec2 run-instances \
  --region "$REGION" \
  --image-id "$AMI_ID" \
  --instance-type "$INSTANCE_TYPE" \
  --iam-instance-profile "Name=$PROFILE_NAME" \
  --subnet-id "$SUBNET_ID" \
  --security-group-ids "$SECURITY_GROUP_ID" \
  --instance-initiated-shutdown-behavior terminate \
  --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":30,"VolumeType":"gp3","DeleteOnTermination":true}}]' \
  --user-data "file://$USER_DATA" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=research-papers-pilot},{Key=Project,Value=research-papers-global-lake},{Key=RunId,Value=$RUN_ID},{Key=BudgetUSD,Value=$BUDGET_USD},{Key=Owner,Value=codex}]" \
  --output json)"
rm -f "$USER_DATA"

INSTANCE_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["Instances"][0]["InstanceId"])' <<<"$LAUNCH_JSON")"
OUT="$OUT_DIR/ec2_pilot_launch_${RUN_ID}.json"
python3 - <<PY > "$OUT"
import json
launch = json.loads("""$LAUNCH_JSON""")
print(json.dumps({
    "run_id": "$RUN_ID",
    "instance_id": "$INSTANCE_ID",
    "region": "$REGION",
    "ami_id": "$AMI_ID",
    "instance_type": "$INSTANCE_TYPE",
    "lake_prefix": "$LAKE_PREFIX",
    "budget_usd": float("$BUDGET_USD"),
    "profile_name": "$PROFILE_NAME",
    "role_name": "$ROLE_NAME",
    "max_runtime_seconds": int("$MAX_RUNTIME_SECONDS"),
    "launch": launch,
}, indent=2, sort_keys=True))
PY

echo "$OUT"
echo "$INSTANCE_ID"
