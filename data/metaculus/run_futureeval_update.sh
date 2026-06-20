#!/bin/zsh
# FutureEval bot-tournament daily loop (cron wrapper) — the '#1 among bots' play.
# Bedrock council (Opus 4.8 analysts/synth + Sonnet 4.6), forecasts every open question and submits.
# No-op between batches (0 open → exits clean, $0). Logs to /tmp/futureeval_cron.log.
# PATH is set explicitly because cron runs with a minimal env and the council shells out to `aws`.
export PATH="/opt/homebrew/bin:/Users/emizemani/.local/bin:/usr/bin:/bin:$PATH"
export AWS_REGION="us-east-1"
cd /Users/emizemani/Desktop/predictthefuture || exit 1
echo "===== futureeval_update $(date) ====="
# 2026-06-16: Ruben APPROVED paid native-Bedrock Opus for FutureEval. VERIFIED (CE, this account):
# Opus spend = $0/day (no-ops between question drops); the $5.5k Bedrock is 100% Qwen/MiningTerminal,
# a separate workload (stopped Jun 14), NOT us. Credits NOT visible at this account level → treat Opus
# as real money: ~$1/binary Q, bounded by the dedup guard (FE_DEDUP_HOURS=18, stops the 3x/day cron from
# RE-PAYING to re-forecast the same open Q) + the 136-Q season cap. See CLOUD_COSTS.md.
/Users/emizemani/.local/bin/uv run python data/metaculus/futureeval_update.py --submit --limit 25
echo "===== done $(date) ====="
