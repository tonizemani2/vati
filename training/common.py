"""Shared helpers for the forecasting-LLM training scripts (sft.py / grpo.py / eval.py).

These scripts run on a rented GPU box (RunPod/AWS), NOT in the engine env — they import trl/peft/
torch, which are intentionally NOT engine dependencies (CLAUDE.md: the engine stays a thin scaffold).
They consume the corpus produced by engine/forecastbench/{trainset,harvest,corpus,traces}.py.
"""
from __future__ import annotations

import json
import re

# Identical to the trace-generator system prompt (engine/forecastbench/traces.py) so SFT, GRPO, and
# eval all speak the same format → the model learns one consistent I/O contract.
SYSTEM = (
    "You are a careful, calibrated probabilistic forecaster. You are given ONE forecasting question "
    "and the information known as of a stated date; use nothing from after that date. Reason briefly "
    "and concretely: (1) anchor on the right reference class / base rate — for a numeric series, its "
    "recent level, trend, seasonality, and volatility; for an event, how often such outcomes occur; "
    "(2) the main forces pushing the probability UP; (3) the main forces pushing it DOWN, and how far "
    "the as-of evidence should move you from the anchor; (4) reconcile into ONE calibrated probability "
    "— avoid 0 and 1, and don't be falsely confident on genuinely uncertain questions. End your answer "
    "with exactly one line: 'Probability: 0.NN'."
)

_PROB = re.compile(r"probability\s*[:=]\s*([01](?:\.\d+)?|\.\d+)", re.I)


def parse_prob(text: str):
    """Extract the final probability from a model answer; None if unparseable (→ format penalty)."""
    if not text:
        return None
    m = list(_PROB.finditer(text))
    if m:
        try:
            return min(0.99, max(0.01, float(m[-1].group(1))))
        except ValueError:
            return None
    for tok in reversed(re.findall(r"\d?\.\d+", text)):
        v = float(tok)
        if 0 <= v <= 1:
            return min(0.99, max(0.01, v))
    return None


def user_prompt(row: dict) -> str:
    """Build the user turn from a GRPO corpus row (question + frozen as-of context)."""
    parts = [f"Question: {row['question']}"]
    if row.get("resolution_criteria"):
        parts.append(f"Resolution criteria: {row['resolution_criteria'][:500]}")
    if row.get("context"):
        parts.append(f"Information as of {row.get('as_of_date')}:\n{row['context'][:1200]}")
    # Residual-on-prior (the fix for the original regression: the prior was NEVER in the prompt, so the
    # model never learned to anchor + adjust). Surface the cheap, test-time-available prior so GRPO learns
    # the RESIDUAL over it. model_prob = the mechanical quant model (numeric); crowd_prob = the market.
    prior = row.get("model_prob")
    if prior is None:
        prior = row.get("crowd_prob")
    if prior is not None:
        src = "A mechanical reference model" if row.get("model_prob") is not None else "The crowd/market"
        parts.append(f"{src} puts the prior probability at {float(prior):.2f} — anchor on it and adjust "
                     f"only as far as the as-of evidence warrants.")
    parts.append(f"Forecast the probability this resolves YES, as of {row.get('as_of_date')}.")
    return "\n".join(parts)


def messages(row: dict) -> list[dict]:
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_prompt(row)}]


def load_jsonl(path: str) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def completion_text(completion) -> str:
    """TRL passes completions as a string (standard) or a list of message dicts (conversational)."""
    if isinstance(completion, str):
        return completion
    if isinstance(completion, list) and completion:
        return completion[-1].get("content", "")
    return ""
