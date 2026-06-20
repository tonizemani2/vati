# One-Click Runbook - After AI: where the constraint moves when intelligence leaves the screen

These are the closest local equivalents to one-click actions.

## Regenerate Everything

```bash
python3 ~/.codex/skills/pope-mega/scripts/pope_board.py research/pope/after-ai-2026-06-17.json --emit-dir research/pope/after-ai-2026-06-17.formats
```

## Render The Research Note

```bash
python3 -m engine.pope.render research/pope/after-ai-2026-06-17.json research/pope/after-ai-2026-06-17
```

## Open The Operator Console

```bash
open research/pope/after-ai-2026-06-17.formats/operator_console.html
```

## Run The First Sales Motion

1. Open `sales_sequences.md`.
2. Copy the first email for the selected segment.
3. Attach or link the relevant `buyer_action_sheets.md` section.
4. Log response and update `action_plan.csv` status manually until a CRM exists.

## Monitor

1. Open `watchlist.csv` every week.
2. Mark each call unchanged, strengthened, weakened, killed, or resolved.
3. If strengthened, send a buyer update.
4. If killed, write a short postmortem and preserve the score.
