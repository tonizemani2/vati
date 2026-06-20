#!/bin/zsh
# Sync the ForecastBench auto-submit runtime out of ~/Desktop so launchd can read it.
set -e

export PATH="/opt/homebrew/bin:/Users/emizemani/.local/bin:/usr/bin:/bin:$PATH"

SOURCE_ROOT=${FORECASTBENCH_SOURCE_ROOT:-/Users/emizemani/Desktop/predictthefuture}
RUNTIME_ROOT=${FORECASTBENCH_RUNTIME_ROOT:-/Users/emizemani/.forecastbench-runtime}
DUE=${FORECASTBENCH_DUE:-2026-06-21}
LOCK_DIR="$RUNTIME_ROOT/data/forecastbench/.run_${DUE}.lock"

if [ "${FORECASTBENCH_DEPLOY_WHILE_RUNNING:-0}" != "1" ] && [ -d "$LOCK_DIR" ]; then
  LOCK_PID=$(cat "$LOCK_DIR/pid" 2>/dev/null || true)
  if [ -n "$LOCK_PID" ] && ps -p "$LOCK_PID" >/dev/null 2>&1; then
    echo "forecastbench runtime sync skipped: active run for $DUE (pid $LOCK_PID); set FORECASTBENCH_DEPLOY_WHILE_RUNNING=1 to override" >&2
    exit 2
  fi
  echo "removing stale ForecastBench deploy lock for $DUE"
  rm -rf "$LOCK_DIR"
fi

mkdir -p "$RUNTIME_ROOT/data"
rsync -a --delete "$SOURCE_ROOT/engine" "$RUNTIME_ROOT/"
rsync -a --delete "$SOURCE_ROOT/data/metaculus" "$RUNTIME_ROOT/data/"
mkdir -p "$RUNTIME_ROOT/data/forecastbench"
if [ -d "$SOURCE_ROOT/data/forecastbench" ]; then
  # Preserve runtime-only live artifacts (qset, submissions, manifest, done marker)
  # so a post-submit redeploy cannot erase the proof of upload.
  if [ "${FORECASTBENCH_SYNC_LIVE_ARTIFACTS:-0}" = "1" ]; then
    rsync -a "$SOURCE_ROOT/data/forecastbench/" "$RUNTIME_ROOT/data/forecastbench/"
  else
    rsync -a \
      --exclude="q_${DUE}.json" \
      --exclude="${DUE}.Vaticinus.[123].json" \
      --exclude="${DUE}.manifest.jsonl" \
      --exclude=".uploaded_${DUE}" \
      --exclude=".run_${DUE}.lock" \
      --exclude=".audit_ok_${DUE}" \
      --exclude=".audit_failed_${DUE}" \
      --exclude="${DUE}_*/" \
      --exclude="proofs/${DUE}_*/" \
      --exclude="proofs/.partial_${DUE}_*/" \
      "$SOURCE_ROOT/data/forecastbench/" "$RUNTIME_ROOT/data/forecastbench/"
  fi
fi
rsync -a "$SOURCE_ROOT/pyproject.toml" "$SOURCE_ROOT/uv.lock" "$RUNTIME_ROOT/"
[ -f "$SOURCE_ROOT/.env" ] && rsync -a "$SOURCE_ROOT/.env" "$RUNTIME_ROOT/"

zsh -n "$RUNTIME_ROOT/data/metaculus/run_forecastbench.sh"
zsh -n "$RUNTIME_ROOT/data/metaculus/run_forecastbench_due_window.sh"
zsh -n "$RUNTIME_ROOT/data/metaculus/verify_forecastbench_upload.sh"
zsh -n "$RUNTIME_ROOT/data/metaculus/forecastbench_post_deadline_audit.sh"
plutil -lint "$RUNTIME_ROOT"/data/metaculus/com.vaticinus.forecastbench.*.plist
(
  cd "$RUNTIME_ROOT" || exit 1
  /Users/emizemani/.local/bin/uv run python -m compileall -q engine/forecastbench
)

echo "forecastbench runtime synced -> $RUNTIME_ROOT"
