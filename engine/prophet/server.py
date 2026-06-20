"""HTTP endpoint for Prophet Arena's agent leaderboard.

Prophet's evaluator POSTs one event per request; we return per-outcome probabilities.
This is a thin shell over engine.prophet.agent.predict (research → keyless ensemble via proxy →
calibrate → Kalshi-price anchor). Compute budget is 1 hour/event; one forecast is ~1-2 min.

Run:   uv run uvicorn engine.prophet.server:app --host 0.0.0.0 --port 8000
Test:  curl -s localhost:8000/predict -H 'content-type: application/json' -d @event.json
Submit the public URL of /predict at https://www.prophetarena.co/onboarding.
"""
from __future__ import annotations

import os
import time
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from engine.prophet import agent

app = FastAPI(title="Vaticinus Forecast Agent")

# Bearer token Prophet's model harness must present (the value you paste into the onboarding "API Key"
# field). Override with PROPHET_BEARER in the Modal secret/env.
PROPHET_BEARER = os.environ.get("PROPHET_BEARER", "vaticinus-prophet-2026")
_security = HTTPBearer(auto_error=True)


def _verify(creds: HTTPAuthorizationCredentials = Depends(_security)) -> str:
    if creds.credentials != PROPHET_BEARER:
        raise HTTPException(status_code=401, detail="Invalid authentication token",
                            headers={"WWW-Authenticate": "Bearer"})
    return creds.credentials


class EventRequest(BaseModel):
    event_ticker: str | None = None
    market_ticker: str | None = None
    title: str
    subtitle: str | None = None
    description: str | None = None
    category: str | None = None
    rules: str | None = None
    close_time: str | None = None
    outcomes: list[str] | None = None
    market_stats: dict[str, Any] | None = None  # live Kalshi prices, when supplied


class MarketProbability(BaseModel):
    market: str
    probability: float


class PredictionResponse(BaseModel):
    probabilities: list[MarketProbability]


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/predict", response_model=PredictionResponse)
def predict_endpoint(event: EventRequest) -> PredictionResponse:
    out = agent.predict(event.model_dump())
    return PredictionResponse(**out)


# ── OpenAI-compatible /chat/completions — Prophet Arena's MODEL onboarding path ──────────────────────
# Prophet POSTs an OpenAI chat request describing one event; we reply with the
# {"probabilities": {label: p}, "rationale": "..."} JSON as the message content (parallel free-model
# ensemble). This is what the onboarding form's compatibility test calls. Base URL = this server's URL.

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "vaticinus"
    messages: list[ChatMessage]
    max_tokens: int | None = 512
    temperature: float | None = 0.1
    stream: bool | None = False


@app.post("/chat/completions")
def chat_completions(req: ChatCompletionRequest, _token: str = Depends(_verify)) -> dict:
    from engine.prophet import openai_api
    prompt = "\n\n".join(f"{m.role}: {m.content}" for m in req.messages) or (
        req.messages[-1].content if req.messages else "")
    content = openai_api.forecast_chat(prompt)
    return {
        "id": "chatcmpl-vaticinus",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
