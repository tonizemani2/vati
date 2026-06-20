#!/bin/zsh
# ForecastBench biweekly auto-submit (launchd/cron). Builds the round's submission and uploads it to GCS.
# No-ops automatically on non-due Sundays (no question set published yet → fetch fails → exit clean).
# ONE-TIME setup to enable auto-upload: (1) email forecastbench@forecastingresearch.org from the
# Google account to get the bucket; (2) `gcloud auth login` on this Mac with that account; (3) add
# FORECASTBENCH_BUCKET=<bucket-name> to .env. Until then it BUILDS the file but won't upload.
export PATH="/opt/homebrew/bin:/Users/emizemani/.local/bin:/usr/bin:/bin:$PATH"
SCRIPT_DIR=${0:A:h}
WORKDIR=${FORECASTBENCH_WORKDIR:-${SCRIPT_DIR:h:h}}
cd "$WORKDIR" || exit 1
DUE=${FORECASTBENCH_DUE:-$(date -u +%F)}
TODAY_UTC=$(date -u +%F)
echo "===== forecastbench $(date) | due(UTC)=$DUE ====="
echo "workspace=$(pwd)"
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

seconds_until_utc() {
  python3 - "$1" <<'PY'
import sys
from datetime import datetime, timezone

raw = sys.argv[1].replace("Z", "+00:00")
deadline = datetime.fromisoformat(raw)
if deadline.tzinfo is None:
    deadline = deadline.replace(tzinfo=timezone.utc)
print(int((deadline.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds()))
PY
}

run_with_timeout() {
  local limit=$1
  shift
  python3 - "$limit" "$@" <<'PY'
import os
import signal
import subprocess
import sys
import time

limit = int(sys.argv[1])
cmd = sys.argv[2:]
proc = subprocess.Popen(cmd, start_new_session=True)
try:
    raise SystemExit(proc.wait(timeout=limit))
except subprocess.TimeoutExpired:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        time.sleep(1)
    raise SystemExit(124)
PY
}

write_proof_bundle() {
  local proof_root=${FORECASTBENCH_PROOF_ROOT:-data/forecastbench/proofs}
  local stamp=$(date -u +%Y%m%dT%H%M%SZ)
  local proof_name="${DUE}_${stamp}_$$"
  local proof_tmp="${proof_root}/.partial_${proof_name}"
  local proof_dir="${proof_root}/${proof_name}"
  mkdir -p "$proof_root" || return 1
  rm -rf "$proof_tmp" || return 1
  mkdir -p "$proof_tmp" || return 1
  cp -p "$QSET_FILE" "$MANIFEST" "$DONE_MARKER" "$proof_tmp/" || return 1
  for FILE in "${FILES[@]}"; do
    cp -p "$FILE" "$proof_tmp/" || return 1
  done
  if [ -n "$BUCKET" ] && command -v gsutil >/dev/null 2>&1; then
    local dest="$BUCKET"
    case "$dest" in gs://*) ;; *) dest="gs://${dest}" ;; esac
    for FILE in "${FILES[@]}"; do
      {
        printf '%s\n' "===== ${dest}/$(basename "$FILE") ====="
        gsutil stat "${dest}/$(basename "$FILE")" 2>&1 || true
      } >> "$proof_tmp/remote_stats.txt" || return 1
    done
  fi
  if ! python3 - "$proof_tmp/proof.json" "$DUE" "$OPUS_STATUS" "$BUCKET" "$QSET_FILE" "$MANIFEST" "$DONE_MARKER" "${FILES[@]}" <<'PY'
import base64
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

out = Path(sys.argv[1])
due = sys.argv[2]
opus_status = sys.argv[3]
bucket = sys.argv[4] or None
qset = sys.argv[5]
manifest = sys.argv[6]
done_marker = sys.argv[7]
files = sys.argv[8:]


def artifact(path_raw: str) -> dict:
    path = Path(path_raw)
    data = path.read_bytes()
    return {
        "path": str(path),
        "copied_basename": path.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "md5_base64": base64.b64encode(hashlib.md5(data).digest()).decode(),
        "bytes": len(data),
    }


payload = {
    "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "due": due,
    "opus_status": opus_status,
    "bucket": bucket,
    "question_set": qset,
    "manifest": manifest,
    "done_marker": done_marker,
    "submission_files": files,
    "artifacts": {
        "question_set": artifact(qset),
        "manifest": artifact(manifest),
        "done_marker": artifact(done_marker),
        "submissions": [artifact(path) for path in files],
    },
}
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
PY
  then
    return 1
  fi
  [ -f "$proof_tmp/proof.json" ] || return 1
  [ ! -e "$proof_dir" ] || return 1
  mv "$proof_tmp" "$proof_dir" || return 1
  echo "proof bundle wrote $proof_dir"
}
mkdir -p data/forecastbench
LOCK_DIR="data/forecastbench/.run_${DUE}.lock"
if mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "$$" > "$LOCK_DIR/pid"
  trap 'rm -rf "$LOCK_DIR"' EXIT INT TERM
else
  LOCK_PID=$(cat "$LOCK_DIR/pid" 2>/dev/null || true)
  if [ -n "$LOCK_PID" ] && ps -p "$LOCK_PID" >/dev/null 2>&1; then
    echo "another ForecastBench run for $DUE is active (pid $LOCK_PID) — skip"
    exit 0
  fi
  echo "removing stale ForecastBench lock for $DUE"
  rm -rf "$LOCK_DIR"
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$LOCK_DIR/pid"
    trap 'rm -rf "$LOCK_DIR"' EXIT INT TERM
  else
    echo "could not acquire ForecastBench lock for $DUE — skip"
    exit 0
  fi
fi
DONE_MARKER="data/forecastbench/.uploaded_${DUE}"
if [ -f "$DONE_MARKER" ] && [ "${FORECASTBENCH_FORCE:-0}" != "1" ]; then
  echo "done marker exists for $DUE ($DONE_MARKER); verifying before skip"
  QSET_CACHE="data/forecastbench/q_${DUE}.json"
  if [ -f "$QSET_CACHE" ]; then
    /Users/emizemani/.local/bin/uv run python -m engine.forecastbench.submit --check-current "$DUE" "$QSET_CACHE"
    QSET_CURRENT_RC=$?
    if [ "$QSET_CURRENT_RC" = "1" ]; then
      echo "cached question set is stale for $DUE — removing marker and retrying build/upload"
      rm -f "$DONE_MARKER"
    elif [ "$QSET_CURRENT_RC" != "0" ]; then
      echo "could not confirm live question set freshness for $DUE (rc=$QSET_CURRENT_RC); verifying existing upload without deleting marker"
    fi
  fi
fi
if [ -f "$DONE_MARKER" ] && [ "${FORECASTBENCH_FORCE:-0}" != "1" ]; then
  if FORECASTBENCH_DUE="$DUE" "$SCRIPT_DIR/verify_forecastbench_upload.sh"; then
    echo "already uploaded and verified for $DUE — skip; set FORECASTBENCH_FORCE=1 to override"
    exit 0
  fi
  echo "stale/unverified done marker for $DUE — removing marker and retrying build/upload"
  rm -f "$DONE_MARKER"
fi
# Build (downloads the round's question set + runs quant+crowd; fails cleanly if not a due date).
rm -f data/forecastbench/${DUE}.Vaticinus.[123].json(N)
LLM_FILL_EXPLICIT=${FORECASTBENCH_USE_LLM_FILL+x}
USE_LLM_FILL=${FORECASTBENCH_USE_LLM_FILL:-0}
if [ -z "$LLM_FILL_EXPLICIT" ]; then
  LLM_DEADLINE_UTC=${FORECASTBENCH_DEADLINE_UTC:-}
  [ "$DUE" = "2026-06-21" ] && LLM_DEADLINE_UTC=${FORECASTBENCH_DEADLINE_UTC:-2026-06-22T00:00:00Z}
  LLM_DEADLINE_SKIP_SECONDS=${FORECASTBENCH_OPUS_DEADLINE_SKIP_SECONDS:-7200}
  if [ -n "$LLM_DEADLINE_UTC" ]; then
    LLM_SECONDS_LEFT=$(seconds_until_utc "$LLM_DEADLINE_UTC" 2>/dev/null || echo "")
    if [[ "$LLM_SECONDS_LEFT" == -<-> || "$LLM_SECONDS_LEFT" == <-> ]] && [ "$LLM_SECONDS_LEFT" -le "$LLM_DEADLINE_SKIP_SECONDS" ]; then
      USE_LLM_FILL=0
    fi
  fi
fi
echo "llm_gap_fill=$USE_LLM_FILL"
WAIT_FOR_PUBLISH=${FORECASTBENCH_WAIT_FOR_PUBLISH:-0}
[ "$DUE" = "$TODAY_UTC" ] && [ "$DUE" = "2026-06-21" ] && WAIT_FOR_PUBLISH=1
FETCH_SLEEP=${FORECASTBENCH_FETCH_SLEEP:-60}
FETCH_TRIES=1
[ "$WAIT_FOR_PUBLISH" = "1" ] && FETCH_TRIES=${FORECASTBENCH_FETCH_TRIES:-12}
TRY=1
while true; do
  SUBMIT_ARGS=()
  REFRESH_QSET=${FORECASTBENCH_REFRESH_QSET:-0}
  [ "$DUE" = "2026-06-21" ] && REFRESH_QSET=${FORECASTBENCH_REFRESH_QSET:-1}
  [ "$REFRESH_QSET" = "1" ] && SUBMIT_ARGS+=(--refresh-qset)
  [ "$USE_LLM_FILL" = "1" ] || SUBMIT_ARGS+=(--no-llm)
  SUBMIT_ARGS+=("$DUE")
  /Users/emizemani/.local/bin/uv run python -m engine.forecastbench.submit "${SUBMIT_ARGS[@]}"
  SUBMIT_RC=$?
  if [ "$SUBMIT_RC" = "0" ]; then
    break
  fi
  if [ "$SUBMIT_RC" != "3" ]; then
    echo "ForecastBench submitter failed for $DUE with rc=$SUBMIT_RC — not treating this as unpublished"
    exit "$SUBMIT_RC"
  fi
  if [ "$TRY" -ge "$FETCH_TRIES" ]; then
    echo "no published question set for $DUE after $TRY attempt(s) — skip"; exit 0
  fi
  echo "question set for $DUE not published yet — retrying in ${FETCH_SLEEP}s ($TRY/$FETCH_TRIES)"
  sleep "$FETCH_SLEEP"
  TRY=$((TRY + 1))
done
USE_OPUS=${FORECASTBENCH_USE_OPUS:-0}
OPUS_STATUS=not_requested
if [ "$USE_OPUS" = "1" ]; then
  OPUS_STATUS=started
  QSET="data/forecastbench/q_${DUE}.json"
  OPUS_OUT=${FORECASTBENCH_OPUS_OUT:-/tmp/opus_${DUE}.json}
  OPUS_WORKLIST=${FORECASTBENCH_OPUS_WORKLIST:-/tmp/opus_work_${DUE}.jsonl}
  OPUS_COUNCIL=${FORECASTBENCH_OPUS_COUNCIL:-3}
  OPUS_PROXY=${FORECASTBENCH_OPUS_PROXY:-evomi}
  OPUS_WORKERS=${FORECASTBENCH_OPUS_WORKERS:-6}
  OPUS_TIMEOUT=${FORECASTBENCH_OPUS_TIMEOUT_SECONDS:-2700}
  OPUS_DEADLINE_UTC=${FORECASTBENCH_DEADLINE_UTC:-}
  [ "$DUE" = "2026-06-21" ] && OPUS_DEADLINE_UTC=${FORECASTBENCH_DEADLINE_UTC:-2026-06-22T00:00:00Z}
  OPUS_DEADLINE_SKIP_SECONDS=${FORECASTBENCH_OPUS_DEADLINE_SKIP_SECONDS:-7200}
  if [ -n "$OPUS_DEADLINE_UTC" ]; then
    OPUS_SECONDS_LEFT=$(seconds_until_utc "$OPUS_DEADLINE_UTC" 2>/dev/null || echo "")
    echo "opus_deadline_utc=${OPUS_DEADLINE_UTC} seconds_left=${OPUS_SECONDS_LEFT:-unknown}"
    if [[ "$OPUS_SECONDS_LEFT" == -<-> || "$OPUS_SECONDS_LEFT" == <-> ]] && [ "$OPUS_SECONDS_LEFT" -le "$OPUS_DEADLINE_SKIP_SECONDS" ]; then
      echo "skipping Opus: ${OPUS_SECONDS_LEFT}s left is inside ${OPUS_DEADLINE_SKIP_SECONDS}s deadline guard"
      USE_OPUS=0
      OPUS_STATUS=deadline_skip
    fi
  fi
  if [ "$USE_OPUS" = "1" ] && [ -f "$QSET" ]; then
    if [ "${FORECASTBENCH_OPUS_DRYRUN:-0}" = "1" ]; then
      /Users/emizemani/.local/bin/uv run python -m engine.forecastbench.opus_blend worklist "$QSET" "$OPUS_WORKLIST"
      echo "Opus dry-run wrote worklist only -> $OPUS_WORKLIST"
      USE_OPUS=0
      OPUS_STATUS=dryrun
    fi
  fi
  if [ "$USE_OPUS" = "1" ] && [ -f "$QSET" ]; then
    echo "running Opus judgmental leg -> $OPUS_OUT (timeout=${OPUS_TIMEOUT}s)"
    OPUS_SUBMISSION="data/forecastbench/${DUE}.Vaticinus.2.json"
    if run_with_timeout "$OPUS_TIMEOUT" /Users/emizemani/.local/bin/uv run python -m engine.forecastbench.opus_forecaster "$QSET" "$OPUS_OUT" \
        --council "$OPUS_COUNCIL" --proxy "$OPUS_PROXY" --workers "$OPUS_WORKERS" \
      && /Users/emizemani/.local/bin/uv run python -m engine.forecastbench.opus_blend merge \
        "$QSET" "$OPUS_OUT" "$OPUS_SUBMISSION" "vati-2.0-opus" \
      && /Users/emizemani/.local/bin/uv run python -m engine.forecastbench.check_submission \
        "$QSET" "$OPUS_SUBMISSION"; then
      echo "Opus blend merged and validated into $OPUS_SUBMISSION"
      OPUS_STATUS=merged
    else
      rc=$?
      rm -f "$OPUS_SUBMISSION"
      if [ "$rc" = "124" ]; then
        echo "Opus leg timed out after ${OPUS_TIMEOUT}s — keeping mechanical submission so upload is not blocked"
        OPUS_STATUS=timeout
      else
        echo "Opus leg failed — keeping mechanical submission so upload is not blocked"
        OPUS_STATUS=failed
      fi
    fi
  elif [ "$USE_OPUS" = "1" ]; then
    echo "Opus leg skipped — missing $QSET"
    OPUS_STATUS=missing_qset
  fi
fi
USE_DIVERSE=${FORECASTBENCH_USE_DIVERSE:-0}
[ "$DUE" = "2026-06-21" ] && USE_DIVERSE=${FORECASTBENCH_USE_DIVERSE:-1}
if [ "$USE_DIVERSE" = "1" ]; then
  QSET_FILE="data/forecastbench/q_${DUE}.json"
  PRIMARY_SUBMISSION="data/forecastbench/${DUE}.Vaticinus.1.json"
  FALLBACK_SECOND_SUBMISSION="data/forecastbench/${DUE}.Vaticinus.2.json"
  DIVERSE_SUBMISSION="data/forecastbench/${DUE}.Vaticinus.3.json"
  if [ -f "$QSET_FILE" ] && [ -f "$PRIMARY_SUBMISSION" ]; then
    if [ -f "$FALLBACK_SECOND_SUBMISSION" ]; then
      if /Users/emizemani/.local/bin/uv run python -m engine.forecastbench.check_submission \
          "$QSET_FILE" "$FALLBACK_SECOND_SUBMISSION"; then
        echo "second submission already present and valid -> $FALLBACK_SECOND_SUBMISSION"
      else
        echo "WARNING: existing second submission failed preflight; replacing with fallback"
        rm -f "$FALLBACK_SECOND_SUBMISSION"
      fi
    fi
    if [ ! -f "$FALLBACK_SECOND_SUBMISSION" ]; then
      if /Users/emizemani/.local/bin/uv run python -m engine.forecastbench.diversify \
          --mode raw-market "$QSET_FILE" "$PRIMARY_SUBMISSION" "$FALLBACK_SECOND_SUBMISSION" \
        && /Users/emizemani/.local/bin/uv run python -m engine.forecastbench.check_submission \
          "$QSET_FILE" "$FALLBACK_SECOND_SUBMISSION"; then
        echo "fallback second submission ready -> $FALLBACK_SECOND_SUBMISSION"
      else
        echo "WARNING: fallback second submission failed preflight; removing and continuing"
        rm -f "$FALLBACK_SECOND_SUBMISSION"
      fi
    fi
    if /Users/emizemani/.local/bin/uv run python -m engine.forecastbench.diversify \
        "$QSET_FILE" "$PRIMARY_SUBMISSION" "$DIVERSE_SUBMISSION" \
      && /Users/emizemani/.local/bin/uv run python -m engine.forecastbench.check_submission \
        "$QSET_FILE" "$DIVERSE_SUBMISSION"; then
      echo "diversified third submission ready -> $DIVERSE_SUBMISSION"
    else
      echo "WARNING: diversified third submission failed preflight; removing and continuing with primary submissions"
      rm -f "$DIVERSE_SUBMISSION"
    fi
  else
    echo "diversified third submission skipped — missing qset or primary submission"
  fi
fi
FILES=(data/forecastbench/${DUE}.Vaticinus.[123].json(N))
[ "${#FILES[@]}" -eq 0 ] && { echo "no submission file built — skip"; exit 0; }
QSET_FILE="data/forecastbench/q_${DUE}.json"
for FILE in "${FILES[@]}"; do
if ! /Users/emizemani/.local/bin/uv run python -m engine.forecastbench.check_submission "$QSET_FILE" "$FILE"
then
  echo "submission preflight failed — not uploading"; exit 1
fi
done
DEFAULT_BUCKET=""
[ "$DUE" = "2026-06-21" ] && DEFAULT_BUCKET="forecastbench-submissions/2026-06-21/team26"
BUCKET_FROM_FILE=$(grep -E '^FORECASTBENCH_BUCKET=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' )
BUCKET=${FORECASTBENCH_BUCKET:-$BUCKET_FROM_FILE}
[ -z "$BUCKET" ] && BUCKET="$DEFAULT_BUCKET"
[ -n "$BUCKET" ] && echo "bucket=$BUCKET" || echo "bucket=unset"
MARKER_TMP=$(mktemp /tmp/forecastbench_marker_${DUE}.XXXXXX)
printf '%s\n' "$(date -u +%FT%TZ)" > "$MARKER_TMP"
printf '%s\n' "opus_status=${OPUS_STATUS}" >> "$MARKER_TMP"
MANIFEST="data/forecastbench/${DUE}.manifest.jsonl"
: > "$MANIFEST"
UPLOAD_FAILED=0
UPLOAD_TRIES=${FORECASTBENCH_UPLOAD_TRIES:-3}
UPLOAD_SLEEP=${FORECASTBENCH_UPLOAD_SLEEP:-10}
for FILE in "${FILES[@]}"; do
  FILE_SHA=$(python3 - "$FILE" <<'PY'
import hashlib, sys
from pathlib import Path
print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)
  FILE_MD5=$(python3 - "$FILE" <<'PY'
import base64, hashlib, sys
from pathlib import Path
print(base64.b64encode(hashlib.md5(Path(sys.argv[1]).read_bytes()).digest()).decode())
PY
)
  FILE_SIZE=$(python3 - "$FILE" <<'PY'
import sys
from pathlib import Path
print(Path(sys.argv[1]).stat().st_size)
PY
)
  echo "submission sha256: $FILE_SHA  md5: $FILE_MD5  bytes: $FILE_SIZE  file: $FILE"
  REMOTE=""
  REMOTE_MD5=""
  REMOTE_SIZE=""
  UPLOADED=0
  VERIFIED=0
  if [ -n "$BUCKET" ]; then
    DEST="$BUCKET"
    case "$DEST" in gs://*) ;; *) DEST="gs://${DEST}" ;; esac
    REMOTE="${DEST}/$(basename "$FILE")"
    UPLOAD_TRY=1
    while [ "$UPLOAD_TRY" -le "$UPLOAD_TRIES" ]; do
      if gsutil cp "$FILE" "${DEST}/"; then
        echo "UPLOADED $FILE -> ${DEST}/ (attempt ${UPLOAD_TRY}/${UPLOAD_TRIES})"
        UPLOADED=1
        REMOTE_STAT=$(gsutil stat "$REMOTE" 2>/dev/null || true)
        REMOTE_MD5=$(printf '%s\n' "$REMOTE_STAT" | awk -F': *' 'index($0, "Hash (md5)") {print $2; exit}')
        REMOTE_SIZE=$(printf '%s\n' "$REMOTE_STAT" | awk -F': *' 'index($0, "Content-Length") {print $2; exit}')
        if [ "$REMOTE_MD5" = "$FILE_MD5" ] && [ "$REMOTE_SIZE" = "$FILE_SIZE" ]; then
          echo "UPLOAD VERIFIED $REMOTE (md5+bytes match)"
          VERIFIED=1
          printf '%s\n%s\n%s\n%s\n%s\n' "$REMOTE" "sha256:$(basename "$FILE")=${FILE_SHA}" "md5:$(basename "$FILE")=${FILE_MD5}" "bytes:$(basename "$FILE")=${FILE_SIZE}" "verified:$(basename "$FILE")=true" >> "$MARKER_TMP"
          break
        fi
        echo "UPLOAD VERIFY FAILED — remote md5/bytes mismatch for $REMOTE (local md5=$FILE_MD5 bytes=$FILE_SIZE remote md5=${REMOTE_MD5:-missing} bytes=${REMOTE_SIZE:-missing})"
      else
        echo "UPLOAD FAILED on attempt ${UPLOAD_TRY}/${UPLOAD_TRIES} — run 'gcloud auth login' with the FB-authorized account / check bucket if this persists"
      fi
      if [ "$UPLOAD_TRY" -lt "$UPLOAD_TRIES" ]; then
        echo "retrying upload for $FILE in ${UPLOAD_SLEEP}s"
        sleep "$UPLOAD_SLEEP"
      fi
      UPLOAD_TRY=$((UPLOAD_TRY + 1))
    done
    if [ "$VERIFIED" != "1" ]; then
      UPLOAD_FAILED=1
    fi
  else
    echo "FORECASTBENCH_BUCKET/default bucket unset — BUILT $FILE but did NOT upload (one-time setup pending)."
  fi
  python3 - "$FILE" "$FILE_SHA" "$FILE_MD5" "$FILE_SIZE" "$REMOTE" "$REMOTE_MD5" "$REMOTE_SIZE" "$UPLOADED" "$VERIFIED" "$OPUS_STATUS" <<'PY' >> "$MANIFEST"
import json, sys
from pathlib import Path

path = Path(sys.argv[1])
sha = sys.argv[2]
md5 = sys.argv[3]
size = int(sys.argv[4])
remote = sys.argv[5] or None
remote_md5 = sys.argv[6] or None
remote_size = int(sys.argv[7]) if sys.argv[7] else None
uploaded = sys.argv[8] == "1"
verified = sys.argv[9] == "1"
opus_status = sys.argv[10]
data = json.loads(path.read_text())
market = {"manifold", "metaculus", "polymarket", "infer"}
rows = data["forecasts"]
single = [r for r in rows if r.get("direction") is None]
dataset_rows = [r for r in rows if r.get("source") not in market]
market_rows = [r for r in rows if r.get("source") in market]
print(json.dumps({
    "file": str(path),
    "remote": remote,
    "uploaded": uploaded,
    "verified": verified,
    "sha256": sha,
    "md5_base64": md5,
    "bytes": size,
    "remote_md5_base64": remote_md5,
    "remote_bytes": remote_size,
    "organization": data.get("organization"),
    "model": data.get("model"),
    "question_set": data.get("question_set"),
    "forecast_rows": len(rows),
    "single_rows": len(single),
    "market_rows": len(market_rows),
    "dataset_rows": len(dataset_rows),
    "opus_status": opus_status,
}, sort_keys=True))
PY
done
if [ -n "$BUCKET" ] && [ "$UPLOAD_FAILED" = "1" ]; then
  exit 1
fi
if [ -n "$BUCKET" ] && [ "$OPUS_STATUS" != "failed" ] && [ "$OPUS_STATUS" != "missing_qset" ] && [ "$OPUS_STATUS" != "timeout" ] && [ "$OPUS_STATUS" != "dryrun" ]; then
  echo "running upload verifier before done marker"
  if ! FORECASTBENCH_DUE="$DUE" FORECASTBENCH_REQUIRE_DONE=0 "$SCRIPT_DIR/verify_forecastbench_upload.sh"; then
    echo "upload verifier failed before done marker — leaving run retryable"
    rm -f "$MARKER_TMP"
    exit 1
  fi
  mv "$MARKER_TMP" "$DONE_MARKER"
  if ! write_proof_bundle; then
    echo "proof bundle failed after verified upload — removing done marker so launchd can retry"
    rm -f "$DONE_MARKER"
    exit 1
  fi
  echo "running final upload verifier after done marker"
  if ! FORECASTBENCH_DUE="$DUE" "$SCRIPT_DIR/verify_forecastbench_upload.sh"; then
    echo "final upload verifier failed — removing done marker so launchd can retry"
    rm -f "$DONE_MARKER"
    exit 1
  fi
else
  rm -f "$MARKER_TMP"
  if [ "$OPUS_STATUS" = "failed" ] || [ "$OPUS_STATUS" = "missing_qset" ] || [ "$OPUS_STATUS" = "timeout" ] || [ "$OPUS_STATUS" = "dryrun" ]; then
    echo "not writing done marker because opus_status=${OPUS_STATUS}; later cron may retry Opus"
  fi
fi
echo "===== done $(date) ====="
