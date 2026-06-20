#!/bin/zsh
# Quick operational status for the ForecastBench live round.

export PATH="/opt/homebrew/bin:/Users/emizemani/.local/bin:/usr/bin:/bin:$PATH"

SCRIPT_DIR=${0:A:h}
WORKDIR=${FORECASTBENCH_WORKDIR:-${SCRIPT_DIR:h:h}}
DUE=${FORECASTBENCH_DUE:-2026-06-21}
RAW_URL="https://raw.githubusercontent.com/forecastingresearch/forecastbench-datasets/main/datasets/question_sets/${DUE}-llm.json"
LATEST_URL="https://raw.githubusercontent.com/forecastingresearch/forecastbench-datasets/main/datasets/question_sets/latest-llm.json"
API_URL="https://api.github.com/repos/forecastingresearch/forecastbench-datasets/contents/datasets/question_sets/${DUE}-llm.json?ref=main"
DATA_DIR="$WORKDIR/data/forecastbench"

DEFAULT_WINDOW_START_UTC=$(python3 - "$DUE" <<'PY'
import sys
from datetime import datetime, timedelta, timezone

due = datetime.fromisoformat(sys.argv[1] + "T00:00:00+00:00")
print((due - timedelta(days=3)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
PY
)
DEFAULT_WINDOW_END_UTC=$(python3 - "$DUE" <<'PY'
import sys
from datetime import datetime, timedelta, timezone

due = datetime.fromisoformat(sys.argv[1] + "T00:00:00+00:00")
print((due + timedelta(days=1, minutes=10)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
PY
)
WINDOW_START_UTC=${FORECASTBENCH_WINDOW_START_UTC:-$DEFAULT_WINDOW_START_UTC}
WINDOW_END_UTC=${FORECASTBENCH_WINDOW_END_UTC:-$DEFAULT_WINDOW_END_UTC}
WINDOW_STATUS=$(python3 - "$WINDOW_START_UTC" "$WINDOW_END_UTC" <<'PY'
import sys
from datetime import datetime, timezone

start = datetime.fromisoformat(sys.argv[1].replace("Z", "+00:00"))
end = datetime.fromisoformat(sys.argv[2].replace("Z", "+00:00"))
now = datetime.now(timezone.utc)
if start <= now <= end:
    print("inside")
elif now < start:
    print("before")
else:
    print("after")
PY
)
POLL_WAIT_FOR_PUBLISH=${FORECASTBENCH_WAIT_FOR_PUBLISH:-0}
POLL_MODE=early_single_fetch
if [ "$DUE" = "$(date -u +%F)" ]; then
  POLL_WAIT_FOR_PUBLISH=1
  POLL_MODE=due_day_retry
fi

echo "forecastbench_status $(date) due=$DUE"
echo "workspace=$WORKDIR"
echo "poll_window_status=$WINDOW_STATUS start=$WINDOW_START_UTC end=$WINDOW_END_UTC now_utc=$(date -u +%FT%TZ)"
echo "poll_mode=$POLL_MODE wait_for_publish=$POLL_WAIT_FOR_PUBLISH"
echo "raw_http=$(curl -sS -o /tmp/forecastbench_status_${DUE}.json -w '%{http_code}' "$RAW_URL" 2>/dev/null || echo curl_failed)"
echo "api_http=$(curl -sS -o /tmp/forecastbench_status_api_${DUE}.json -w '%{http_code}' "$API_URL" 2>/dev/null || echo curl_failed)"
LATEST_REF=$(curl -fsS "$LATEST_URL" 2>/dev/null | head -c 120 | tr '\n' ' ' || true)
[ -n "$LATEST_REF" ] && echo "latest_ref=$LATEST_REF" || echo "latest_ref=unavailable"
echo "uv=$(/Users/emizemani/.local/bin/uv --version 2>/dev/null || echo missing)"
echo "gsutil=$(command -v gsutil 2>/dev/null || echo missing)"
if command -v gcloud >/dev/null 2>&1; then
  GCLOUD_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -n 1)
  [ -n "$GCLOUD_ACCOUNT" ] && echo "gcloud_account=$GCLOUD_ACCOUNT" || echo "gcloud_account=unavailable"
else
  echo "gcloud_account=missing"
fi
if command -v aws >/dev/null 2>&1; then
  AWS_ARN=$(AWS_MAX_ATTEMPTS=1 AWS_CLI_CONNECT_TIMEOUT=5 AWS_CLI_READ_TIMEOUT=5 aws sts get-caller-identity --query Arn --output text 2>/dev/null || true)
  [ -n "$AWS_ARN" ] && echo "aws_arn=$AWS_ARN" || echo "aws_arn=unavailable"
else
  echo "aws_arn=missing"
fi

echo "--- launchd submitter ---"
launchctl print "gui/$(id -u)/com.vaticinus.forecastbench.early" 2>/dev/null | sed -n '1,55p' || echo "launchd_submitter=missing"

echo "--- launchd poller ---"
launchctl print "gui/$(id -u)/com.vaticinus.forecastbench.poll" 2>/dev/null | sed -n '1,45p' || echo "launchd_poller=missing"
echo "--- poller log tail ---"
tail -n 8 /tmp/forecastbench_poll.log 2>/dev/null || echo "poller_log=missing"

echo "--- launchd rescue ---"
launchctl print "gui/$(id -u)/com.vaticinus.forecastbench.rescue" 2>/dev/null | sed -n '1,45p' || echo "launchd_rescue=missing"
echo "--- rescue log tail ---"
tail -n 8 /tmp/forecastbench_rescue.log 2>/dev/null || echo "rescue_log=missing"

echo "--- launchd audit ---"
launchctl print "gui/$(id -u)/com.vaticinus.forecastbench.audit" 2>/dev/null | sed -n '1,45p' || echo "launchd_audit=missing"

echo "--- awake guard ---"
launchctl print "gui/$(id -u)/com.vaticinus.forecastbench.caffeinate" 2>/dev/null | sed -n '1,45p' || echo "awake_guard=missing"
[ -f "$DATA_DIR/.caffeinate_${DUE}.pid" ] && cat "$DATA_DIR/.caffeinate_${DUE}.pid"

echo "--- artifacts ---"
for ARTIFACT_PATH in \
  "$DATA_DIR/q_${DUE}.json" \
  "$DATA_DIR/${DUE}.Vaticinus.1.json" \
  "$DATA_DIR/${DUE}.Vaticinus.2.json" \
  "$DATA_DIR/${DUE}.Vaticinus.3.json" \
  "$DATA_DIR/${DUE}.manifest.jsonl" \
  "$DATA_DIR/.uploaded_${DUE}" \
  "$DATA_DIR/.audit_ok_${DUE}" \
  "$DATA_DIR/.audit_failed_${DUE}" \
  "$DATA_DIR/.run_${DUE}.lock"
do
  if [ -e "$ARTIFACT_PATH" ]; then
    /bin/ls -ldh "$ARTIFACT_PATH"
  else
    echo "missing $ARTIFACT_PATH"
  fi
done

echo "--- proof directories ---"
if [ -d "$DATA_DIR/proofs" ]; then
  find "$DATA_DIR/proofs" -maxdepth 1 -type d \( -name "${DUE}_*" -o -name ".partial_${DUE}_*" \) -print 2>/dev/null | sort || true
else
  echo "proofs=none"
fi

echo "--- remote json objects ---"
DEFAULT_BUCKET=""
[ "$DUE" = "2026-06-21" ] && DEFAULT_BUCKET="forecastbench-submissions/2026-06-21/team26"
BUCKET_FROM_FILE=$(grep -E '^FORECASTBENCH_BUCKET=' "$WORKDIR/.env" 2>/dev/null | cut -d= -f2- | tr -d '"' )
BUCKET=${FORECASTBENCH_BUCKET:-$BUCKET_FROM_FILE}
[ -z "$BUCKET" ] && BUCKET="$DEFAULT_BUCKET"
if [ -n "$BUCKET" ] && command -v gsutil >/dev/null 2>&1; then
  DEST="$BUCKET"
  case "$DEST" in gs://*) ;; *) DEST="gs://${DEST}" ;; esac
  REMOTE_JSONS=$(gsutil ls "${DEST}/*.json" 2>/dev/null || true)
  [ -n "$REMOTE_JSONS" ] && printf '%s\n' "$REMOTE_JSONS" || echo "remote_json_objects=none"
else
  echo "remote_json_objects=skipped"
fi

if [ -f "$DATA_DIR/${DUE}.manifest.jsonl" ]; then
  echo "--- verify ---"
  "$SCRIPT_DIR/verify_forecastbench_upload.sh" || true
fi
