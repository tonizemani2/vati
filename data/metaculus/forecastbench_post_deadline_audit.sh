#!/bin/zsh
# Post-deadline ForecastBench audit: verify the final upload or make failure loud.
set -e

export PATH="/opt/homebrew/bin:/Users/emizemani/.local/bin:/usr/bin:/bin:$PATH"

SCRIPT_DIR=${0:A:h}
WORKDIR=${FORECASTBENCH_WORKDIR:-${SCRIPT_DIR:h:h}}
cd "$WORKDIR" || exit 1

DUE=${FORECASTBENCH_DUE:-2026-06-21}
AUDIT_AFTER_UTC=${FORECASTBENCH_AUDIT_AFTER_UTC:-2026-06-22T00:15:00Z}
DATA_DIR="data/forecastbench"
FAIL_MARKER="$DATA_DIR/.audit_failed_${DUE}"
OK_MARKER="$DATA_DIR/.audit_ok_${DUE}"

audit_status=$(python3 - "$AUDIT_AFTER_UTC" <<'PY'
import sys
from datetime import datetime, timezone

deadline = datetime.fromisoformat(sys.argv[1].replace("Z", "+00:00"))
now = datetime.now(timezone.utc)
print("after" if now >= deadline else "before")
PY
)

if [ "${FORECASTBENCH_FORCE_AUDIT:-0}" != "1" ] && [ "$audit_status" != "after" ]; then
  echo "forecastbench audit skip: status=$audit_status due=$DUE now_utc=$(date -u +%FT%TZ) audit_after=$AUDIT_AFTER_UTC"
  exit 0
fi

mkdir -p "$DATA_DIR"
rm -f "$OK_MARKER" "$FAIL_MARKER"

VERIFY_LOG=$(mktemp /tmp/forecastbench_audit_verify_${DUE}.XXXXXX)
if FORECASTBENCH_DUE="$DUE" "$SCRIPT_DIR/verify_forecastbench_upload.sh" > "$VERIFY_LOG" 2>&1; then
  {
    printf '%s\n' "$(date -u +%FT%TZ)"
    printf '%s\n' "ForecastBench upload audit OK for $DUE"
    printf '%s\n' "--- verify output ---"
    cat "$VERIFY_LOG"
    printf '%s\n' "--- proof directories ---"
    find "$DATA_DIR/proofs" -maxdepth 1 -type d -name "${DUE}_*" -print 2>/dev/null | sort || true
  } > "$OK_MARKER"
  echo "forecastbench audit OK for $DUE"
  rm -f "$VERIFY_LOG"
  osascript -e "display notification \"ForecastBench $DUE upload verified\" with title \"ForecastBench OK\"" >/dev/null 2>&1 || true
else
  {
    printf '%s\n' "$(date -u +%FT%TZ)"
    printf '%s\n' "ForecastBench upload audit FAILED for $DUE"
    printf '%s\n' "--- verify output ---"
    cat "$VERIFY_LOG"
    printf '%s\n' "--- forecastbench_status ---"
    "$SCRIPT_DIR/forecastbench_status.sh" 2>&1 || true
    printf '%s\n' "--- recent submitter log ---"
    tail -n 80 /tmp/forecastbench_cron.log 2>/dev/null || true
    printf '%s\n' "--- recent poller log ---"
    tail -n 80 /tmp/forecastbench_poll.log 2>/dev/null || true
    printf '%s\n' "--- recent rescue log ---"
    tail -n 80 /tmp/forecastbench_rescue.log 2>/dev/null || true
    printf '%s\n' "--- proof directories ---"
    find "$DATA_DIR/proofs" -maxdepth 1 -type d -name "${DUE}_*" -print 2>/dev/null | sort || true
  } > "$FAIL_MARKER"
  rm -f "$VERIFY_LOG"
  echo "forecastbench audit FAILED for $DUE; wrote $FAIL_MARKER"
  osascript -e "display notification \"ForecastBench $DUE upload audit failed\" with title \"ForecastBench FAILED\"" >/dev/null 2>&1 || true
  exit 1
fi
