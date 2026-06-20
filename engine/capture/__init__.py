"""Capture — the low-volume, exactly-right outbound engine.

Turns a live forecast into POSITION: find the few right people/orgs at a bottleneck,
decide the play (capture ladder rung 1-2), draft an evidence-first opener AND a decision
tree of likely replies, and hold it all for review. Nothing sends. DeepSeek does the cheap
heavy lifting (discover/qualify/synth); the in-session model (Opus) rates and iterates until
the plays are genuinely strong.

See engine/capture/schema.py for the artifacts and engine/capture/run.py for the orchestrator.
"""
