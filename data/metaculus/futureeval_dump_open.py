"""Dump currently-open FutureEval BINARY questions to JSON for the /futureeval subagent council.

The Opus-subagent path (run inside a Claude Code session) needs the open questions as a plain
file it can read; this is the deterministic fetch half. Output = list of normalized question dicts
(title/description/resolution_criteria/fine_print/close_time/url). Binary-only by design: that is
where the Opus council earns its keep; MC/numeric stay on the mechanical/free path.

  uv run python data/metaculus/futureeval_dump_open.py [out_path]   # default /tmp/fe_open.json
"""
import json, os, sys

from engine.metaculus import api

SLUG = os.getenv("FE_SLUG", "summer-futureeval-2026")
out_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/fe_open.json"

posts = api.list_open_questions(SLUG, forecast_type="binary")
# soonest-closing first — FutureEval windows are short, forecast the about-to-close ones first.
posts.sort(key=lambda p: (p.get("question") or {}).get("scheduled_close_time") or "9999")
rows = [api.question_text(p) for p in posts]

json.dump(rows, open(out_path, "w"), indent=1)
print(f"{SLUG}: {len(rows)} open binary question(s) -> {out_path}")
