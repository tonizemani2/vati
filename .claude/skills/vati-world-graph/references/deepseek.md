# DeepSeek V4 World Graph runs

Source facts checked against official DeepSeek API docs on 2026-06-18:

- Base URL: `https://api.deepseek.com`
- OpenAI ChatCompletions endpoint: `/chat/completions`
- Current V4 models: `deepseek-v4-flash`, `deepseek-v4-pro`
- Legacy aliases `deepseek-chat` and `deepseek-reasoner` retire on 2026-07-24 15:59 UTC.
- Both V4 models support 1M context, JSON output, tool calls, thinking and non-thinking modes.
- Cache-miss pricing per 1M tokens at check time:
  - `deepseek-v4-flash`: $0.14 input, $0.28 output
  - `deepseek-v4-pro`: $0.435 input, $0.87 output

## Plan sizes

- `lite`: 5 calls. Use for a quick smell test or prompt debugging.
- `standard`: 17 calls. Use for a serious single-board graph improvement run: 13 role agents plus integrator, critic, repair, and score.
- `full`: `13 + 4 * forecast_count + 3` calls. For a 6-thesis Pope board, this is 40 calls: 13 atlas roles, 24 per-thesis deepening calls, and 3 synthesis passes.

## Model assignment

- Use `deepseek-v4-flash` for breadth, extraction, cartography, source-pack scaffolds, and Ultra task generation.
- Use `deepseek-v4-pro` for pricing gate, adversarial refute, scenario architecture, integrator, critic, repair, and score.

## Cost rules

Always run dry-run first:

```bash
python3 -m engine.cli world-graph-deepseek <board.json> --out-dir <run-dir> --plan standard
```

Only execute after explicit approval:

```bash
python3 -m engine.cli world-graph-deepseek <board.json> --out-dir <run-dir> --plan full --execute
```

The runner reads `DEEPSEEK_API_KEY` only from the repo `.env` or existing environment and gates every paid call through `engine.cost`.
