#!/usr/bin/env bash
# Sync the live foresight.db to the data-layer EC2 box (hermes-handoff) that serves the chat's
# Deep/Capture grounding via https://data.vaticinus.com. The sidecar opens the DB read-only and
# fresh on every query, so replacing the file is enough — no service restart needed.
#
# Consistency: we take an online sqlite .backup first (safe even while the ingest pipeline is
# writing, and it folds the WAL into one clean file), then push it with an incremental in-place
# rsync (delta = only changed blocks, so a daily run is cheap over a home uplink). Scheduled for
# 04:15 local by the launchd job so the brief in-place window never overlaps real chat traffic.
set -euo pipefail

REPO=/Users/emizemani/Desktop/predictthefuture
SRC="$REPO/data/foresight.db"
SNAP="$REPO/data/.foresight.sync.db"
KEY=/Users/emizemani/.ssh/hermes-handoff.pem
BOX=ubuntu@44.202.64.144
LOG="$REPO/data/.foresight_sync.log"

ts() { date '+%F %T'; }
echo "[$(ts)] start" >> "$LOG"

# 1. consistent online snapshot (online backup API; survives concurrent writers)
/usr/bin/python3 - "$SRC" "$SNAP" <<'PY'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
s = sqlite3.connect(src)
d = sqlite3.connect(dst)
with d:
    s.backup(d)
d.close(); s.close()
PY

# 2. incremental, in-place push (delta vs the box's current copy)
/usr/bin/rsync -z --inplace --partial \
  -e "ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=20" \
  "$SNAP" "$BOX:/home/ubuntu/data/foresight.db" >> "$LOG" 2>&1

rm -f "$SNAP"
echo "[$(ts)] done -> box updated" >> "$LOG"
