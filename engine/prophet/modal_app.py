"""Modal deployment of the Prophet Arena `/predict` agent — a robust, non-AWS public URL.

The home network blocks cloudflared's data path, so we host the FastAPI server on Modal instead.
The agent runs entirely in the cloud container: research (Exa, DIRECT from Modal's IP — no residential
proxy) → openrouter `:free` ensemble (keyed, $0) → category-aware Kalshi-price anchor.

ONE-TIME (you, in a terminal):
    uv run modal setup                                   # browser auth, free tier
    uv run modal secret create prophet-openrouter \
        OPENROUTER_API_KEY=$(grep -m1 '^OPENROUTER_API_KEY=' .env | cut -d= -f2-)

DEPLOY:
    uv run modal deploy engine/prophet/modal_app.py
    # prints a public URL like https://<you>--vaticinus-prophet-fastapi-app.modal.run
    # Submit  <that-url>/predict  at  https://www.prophetarena.co/onboarding

TEST:
    curl -s <url>/health
    curl -s <url>/predict -H 'content-type: application/json' -d @event.json
"""
from __future__ import annotations

import modal

# Every third-party package imported anywhere in the engine import chain (generous = robust; a missing
# transitive import would crash the container at startup, not at request time).
DEPS = ["fastapi", "uvicorn", "httpx", "numpy", "pandas", "polars", "pydantic", "trafilatura", "typer"]

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(*DEPS)
    .env({"PROPHET_PROXY": "",             # research runs DIRECT from Modal's IP (no residential proxy)
          "PROPHET_BEARER": "vaticinus-prophet-2026"})  # Bearer token for the /chat/completions model path
    .add_local_python_source("engine")     # mount the engine package into the container
)

app = modal.App("vaticinus-prophet")


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("prophet-openrouter")],  # injects OPENROUTER_API_KEY into env
    timeout=3600,          # Prophet's compute budget is 1h/event
    min_containers=1,      # keep one container warm so the evaluator never eats a cold start
)
@modal.concurrent(max_inputs=4)            # a few events can forecast in parallel
@modal.asgi_app()
def fastapi_app():
    # Create the SQLite schema once per container so the $0 cost-ledger writes (llm.complete → cost.gate)
    # succeed on the ephemeral cloud filesystem.
    from engine import db
    conn = db.connect()
    db.init_db(conn)
    conn.close()
    from engine.prophet.server import app as _app
    return _app
