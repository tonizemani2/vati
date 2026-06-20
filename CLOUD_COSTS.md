# CLOUD_COSTS.md — the credit-coverage rule (read before using ANY paid cloud resource)

## HARD RULE
**Nothing runs on a cloud resource that is not confirmed credit-covered.** No exceptions.
Free/keyless first (per CLAUDE.md cost gate). A paid cloud call needs proof that credits absorb it,
or an explicit human OK with the dollar number named. "It's on AWS" is NOT "it's on credits."

## RESOLUTION 2026-06-16 (Ruben)
False alarm on this account: **Bedrock IS credit-covered** for `405844305300`. The credits are applied
at the **Org payer/management account**, so a member account's Cost Explorer shows `net==gross` with no
`Credit` line even though credits ARE absorbing the cost — that member-account blind spot is exactly the
gotcha. The $5,533 Qwen (`...mantle`) is **MiningTerminal** usage, on credits, expected — NOT a leak, NOT
a cron. So: **running Opus deep research on Bedrock, approved for ~3 days, then handled from sub usage.**
The HARD RULE below still stands generally (Marketplace ≠ credits; verify before trusting), but for THIS
account native Bedrock (incl. our Claude Opus) is covered. The original investigation is kept below.

## Incident 2026-06-16 — initial scare (Cost Explorer member-account view looked uncovered)
Built a Metaculus FutureEval forecasting loop on **Amazon Bedrock** (Claude Opus 4.8, account
`405844305300`, IAM user `chime-dev`, us-east-1) assuming AWS credits covered it. They do not.

Evidence (Cost Explorer, month-to-date Jun 1–16):
- **Amazon Bedrock = $5,533.29**, and `NetUnblendedCost == UnblendedCost` (after-credits == before-credits).
- Account `RECORD_TYPE` breakdown shows only **`Usage` $6,222.72** — there is **no `Credit` record type**.
- => **No credits are applied to this account/Bedrock.** Every Bedrock token is real USD.

Scope of OUR damage: **~$5** (143 `bedrock_completion` calls = native Claude Opus, 18:21–19:10 UTC,
in `cost_ledger`). Native Claude-on-Bedrock IS credit-eligible — the fix is just to run it in the
account that actually holds the credits.

**The $5,533 is NOT us and NOT Claude.** USAGE_TYPE breakdown: it is one model,
`qwen.qwen3-next-80b-a3b-instruct-mantle` ($4,408 output + $1,125 input) — a **Marketplace-served**
("mantle") Qwen model from another workload in this account (likely the `~/orca97-v2` biotech cron).
THAT is the real ~$5.5k/mo money leak; investigate/kill separately. Ruben's account HAS credits that
cover Bedrock but NOT Marketplace — and he got a "Claude Opus approved from **Marketplace**" email, so
the trap is enabling Opus via the Marketplace path (uncovered) vs the NATIVE `anthropic.claude-*`
inference profile (covered). Account `405844305300` shows zero credits applied → likely not the
credit account, or credits sit at the Org payer level (confirm in the payer Billing console).

## Action taken
- FutureEval cron flipped to the **$0 keyless path**: `run_futureeval_update.sh` now runs
  `--provider openrouter_free` (no AWS, no spend) until credits are confirmed / Ruben's sub resets
  Fri 2026-06-19. To restore Opus quality: swap `--provider openrouter_free` → `--provider bedrock`
  ONLY once native-Bedrock credit coverage is confirmed in the right account.

## How to verify credit coverage BEFORE using a cloud resource
```bash
# 1. Is there ANY credit being applied this month? (look for a negative 'Credit' RECORD_TYPE)
aws ce get-cost-and-usage --time-period Start=<month-start>,End=<today> --granularity MONTHLY \
  --metrics UnblendedCost --group-by Type=DIMENSION,Key=RECORD_TYPE
# 2. For the specific service, does NetUnblendedCost < UnblendedCost? (credits closing the gap)
aws ce get-cost-and-usage --time-period ... --metrics UnblendedCost NetUnblendedCost \
  --filter '{"Dimensions":{"Key":"SERVICE","Values":["Amazon Bedrock"]}}'
```
If `Net == Unblended` and there is no `Credit` line, the service is NOT credit-covered.
Caveat: in an AWS Organization, credits may apply at the **payer/management account** and be invisible
in a member account's CE — confirm in the payer account's Billing console before trusting coverage.

## Path forward (pick one before resuming any cloud spend)
1. **Confirm credits** in the payer account's Billing console actually cover Bedrock for `405844305300`.
   If yes (and the gap shows up), resume Bedrock by deleting the wrapper guard.
2. **Find a credit-covered account/route** for the Opus calls (e.g. an account where AWS/Azure/GCP
   credits demonstrably apply), repoint `AWS_*`/the provider there.
3. **Run the loop free** at $0 on `--provider openrouter_free` (lower quality than Opus, but keeps the
   FutureEval coverage alive and the scored record building while billing is sorted).
```
