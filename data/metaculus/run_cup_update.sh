#!/bin/zsh
# Daily Metaculus Cup bot/proof-track re-forecast (cron wrapper).
# Default provider is $0 OpenRouter :free. Paid providers fail closed unless explicitly approved.
set -e

export PATH="/opt/homebrew/bin:/Users/emizemani/.local/bin:/usr/bin:/bin:$PATH"

SCRIPT_DIR=${0:A:h}
ROOT=${METACULUS_ROOT:-${SCRIPT_DIR}/../..}
PROVIDER=${CUP_PROVIDER:-openrouter_free}

if [ "$PROVIDER" != "openrouter_free" ] && [ "${CUP_ALLOW_PAID_PROVIDER:-0}" != "1" ]; then
  echo "refusing paid Cup provider '$PROVIDER'; set CUP_ALLOW_PAID_PROVIDER=1 only after approval" >&2
  exit 2
fi

cd "$ROOT" || exit 1

if [ "$1" = "--healthcheck" ]; then
  /Users/emizemani/.local/bin/uv run python data/metaculus/cup_update.py --healthcheck --provider "$PROVIDER"
  exit $?
fi

echo "===== cup_update $(date) ====="
/Users/emizemani/.local/bin/uv run python data/metaculus/cup_update.py --submit --provider "$PROVIDER" "$@"
echo "===== done $(date) ====="
