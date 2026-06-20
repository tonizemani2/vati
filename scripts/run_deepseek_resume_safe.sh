#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/emizemani/Desktop/predictthefuture"
cd "$ROOT"

WINDOW_MINUTES="${MAC_STABILITY_WINDOW_MINUTES:-20}"
POLL_SECONDS="${MAC_STABILITY_POLL_SECONDS:-30}"
export COST_AUTO_APPROVE_CENTS="${COST_AUTO_APPROVE_CENTS:-200}"

while true; do
  if /Users/emizemani/.local/bin/uv run python - "$WINDOW_MINUTES" <<'PY'
import json
import sys

from engine.world_graph_deepseek import mac_stability_report

window = int(sys.argv[1])
report = mac_stability_report(window_minutes=window)
print(json.dumps(report, sort_keys=True), flush=True)
sys.exit(0 if report["ok"] else 1)
PY
  then
    echo "mac stability guard clear; starting DeepSeek resume $(date '+%Y-%m-%d %H:%M:%S')"
    break
  fi
  echo "waiting for crash-report window to clear $(date '+%Y-%m-%d %H:%M:%S')"
  sleep "$POLL_SECONDS"
done

exec /usr/bin/nice -n 10 /usr/bin/caffeinate -disu \
  /Users/emizemani/.local/bin/uv run python -m engine.cli world-graph-deepseek \
  research/pope/after-ai-2026-06-17.json \
  --out-dir research/world_graph/after-ai-2026-06-17.deepseek-pro \
  --plan full \
  --model-flash deepseek-v4-pro \
  --model-pro deepseek-v4-pro \
  --execute
