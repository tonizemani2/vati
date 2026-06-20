#!/bin/zsh
# Redundant due-window poller for the ForecastBench live round.
#
# This is intentionally tiny: launchd can call it frequently, but it only runs
# the expensive submitter during the UTC window around the official due date.
set -e

export PATH="/opt/homebrew/bin:/Users/emizemani/.local/bin:/usr/bin:/bin:$PATH"

SCRIPT_DIR=${0:A:h}
DUE=${FORECASTBENCH_DUE:-2026-06-21}
TODAY_UTC=$(date -u +%F)
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

window_status=$(python3 - "$WINDOW_START_UTC" "$WINDOW_END_UTC" <<'PY'
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

if [ "${FORECASTBENCH_FORCE_WINDOW:-0}" != "1" ] && [ "$window_status" != "inside" ]; then
  echo "forecastbench poll window skip: status=$window_status due=$DUE start=$WINDOW_START_UTC end=$WINDOW_END_UTC now_utc=$(date -u +%FT%TZ)"
  exit 0
fi

WAIT_FOR_PUBLISH=${FORECASTBENCH_WAIT_FOR_PUBLISH:-0}
POLL_MODE=early_single_fetch
if [ "$DUE" = "$TODAY_UTC" ]; then
  WAIT_FOR_PUBLISH=1
  POLL_MODE=due_day_retry
fi

echo "forecastbench poll window active: status=$window_status mode=$POLL_MODE wait_for_publish=$WAIT_FOR_PUBLISH due=$DUE start=$WINDOW_START_UTC end=$WINDOW_END_UTC now_utc=$(date -u +%FT%TZ)"

export FORECASTBENCH_DUE="$DUE"
export FORECASTBENCH_FETCH_TRIES=${FORECASTBENCH_FETCH_TRIES:-20}
export FORECASTBENCH_FETCH_SLEEP=${FORECASTBENCH_FETCH_SLEEP:-30}
export FORECASTBENCH_WAIT_FOR_PUBLISH="$WAIT_FOR_PUBLISH"

exec "$SCRIPT_DIR/run_forecastbench.sh"
