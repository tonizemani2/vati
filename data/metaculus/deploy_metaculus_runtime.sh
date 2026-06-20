#!/bin/zsh
# Sync the Metaculus Cup/FutureEval runtime out of ~/Desktop so cron can read it.
set -e

export PATH="/opt/homebrew/bin:/Users/emizemani/.local/bin:/usr/bin:/bin:$PATH"

SOURCE_ROOT=${METACULUS_SOURCE_ROOT:-/Users/emizemani/Desktop/predictthefuture}
RUNTIME_ROOT=${METACULUS_RUNTIME_ROOT:-/Users/emizemani/.forecastbench-runtime}

mkdir -p "$RUNTIME_ROOT/data/metaculus"

rsync -a --delete "$SOURCE_ROOT/engine" "$RUNTIME_ROOT/"
rsync -a --delete \
  --exclude=".human_session.json" \
  --exclude="private_slates/" \
  --exclude="cron_logs/" \
  "$SOURCE_ROOT/data/metaculus/" "$RUNTIME_ROOT/data/metaculus/"
rsync -a "$SOURCE_ROOT/pyproject.toml" "$SOURCE_ROOT/uv.lock" "$RUNTIME_ROOT/"
[ -f "$SOURCE_ROOT/.env" ] && rsync -a "$SOURCE_ROOT/.env" "$RUNTIME_ROOT/"

zsh -n "$RUNTIME_ROOT/data/metaculus/run_cup_update.sh"
zsh -n "$RUNTIME_ROOT/data/metaculus/run_pull_scores.sh"
zsh -n "$RUNTIME_ROOT/data/metaculus/run_futureeval_update.sh"

(
  cd "$RUNTIME_ROOT" || exit 1
  /Users/emizemani/.local/bin/uv run python -m py_compile \
    data/metaculus/cup_update.py \
    data/metaculus/cup_status.py \
    data/metaculus/human_slate.py \
    data/metaculus/pull_scores.py \
    data/metaculus/submit_slate.py
  /Users/emizemani/.local/bin/uv run python -m compileall -q engine/metaculus
)

echo "metaculus runtime synced -> $RUNTIME_ROOT"
