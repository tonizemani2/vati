# /world-graph

Build or update the Vati World Graph from a Pope board.

Default behavior:

1. Read `CLAUDE.md`, `VOICE.md`, `VATI_WORLD_GRAPH.md`, `FUTURE_MAP.md`, `VATI.md`, and `BRIEFING.md`.
2. Compile the requested board with:

```bash
python3 -m engine.cli world-graph-compile <board.json> --out-dir research/world_graph/<slug>
```

3. Report the atlas path, coverage score, top gaps, unknown queue size, and next agent topology.
4. Do not run paid or Opus agents without approval.

If no board is given, use the newest relevant `research/pope/*.json` after confirming it is the intended input.
