#!/bin/zsh
# Daily Metaculus score/resolution puller (cron wrapper). $0 (read-only GETs).
# Refreshes data/metaculus/scores.json: per-tournament resolved Brier + crowd-beat rate. Logs to /tmp/mtc_scores.log.
set -e

export PATH="/opt/homebrew/bin:/Users/emizemani/.local/bin:/usr/bin:/bin:$PATH"

SCRIPT_DIR=${0:A:h}
ROOT=${METACULUS_ROOT:-${SCRIPT_DIR}/../..}
cd "$ROOT" || exit 1

if [ "$1" = "--healthcheck" ]; then
  /Users/emizemani/.local/bin/uv run python data/metaculus/cup_status.py
  exit $?
fi

if [ "$#" -gt 0 ]; then
  echo "unknown run_pull_scores argument(s): $*" >&2
  exit 2
fi

echo "===== pull_scores $(date) ====="
/Users/emizemani/.local/bin/uv run python data/metaculus/pull_scores.py --quiet
echo "===== done $(date) ====="
