"""LLM structured-extraction pipeline (A3) — typed, validated, span-grounded, tiered.

`llm.complete` returns a raw string. This turns it into VALIDATED data without ever propagating a
hallucinated chain (§9). The contract:
  • JSON-only prompt → parse (markdown-fence-tolerant) → validate each item against a Pydantic model
    (the schema gate; malformed output is dropped, not stored).
  • Bounded retry: on parse/validation failure, re-prompt once with the error appended; after N
    failures the batch is dropped to a human-verify queue — never store garbage.
  • Cost-gated batching: one est_cost_cents per batch, via llm.complete's gate (can't bypass).
  • Confidence tiers — the anti-hallucination spine:
      HIGH  = self-rated confidence ≥ HIGH_CONF AND the cited `span` is found verbatim in the source
              text → safe to auto-store (as SourceKind.model_output, the lowest trust).
      LOW   = anything else → caller routes to a human-verify Decision, never auto-propagated.
    CRITICAL edges (a suspected bottleneck) are ALWAYS human-verified regardless of tier — that
    gate lives in graph.py (`graph-propagate --tie-back`); this module proposes, it never forecasts.

No LLM key configured → LLMConfigError (clean, no network), exactly like the underlying adapter.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Type

from pydantic import BaseModel, ValidationError

from engine.adapters import llm

HIGH_CONF = 0.80


@dataclass
class Candidate:
    item: BaseModel          # the validated Pydantic instance
    confidence: float        # the model's self-rated confidence (0..1)
    span: str                # the verbatim supporting quote it cited
    span_found: bool         # did that span actually appear in the source text? (grounding)
    tier: str                # "high" | "low"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _strip_fences(raw: str) -> str:
    """Pull the JSON out of a ```json ... ``` fence or surrounding prose."""
    m = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    if m:
        return m.group(1).strip()
    # else take the outermost [ ... ] or { ... }
    m = re.search(r"(\[.*\]|\{.*\})", raw, re.DOTALL)
    return m.group(1).strip() if m else raw.strip()


def _field_list(model: Type[BaseModel]) -> str:
    return ", ".join(model.model_fields.keys())


def _build_prompt(text: str, model: Type[BaseModel], instruction: str) -> str:
    return (
        f"{instruction}\n\n"
        f"Return ONLY a JSON array (no prose). Each object must have these fields: "
        f"{_field_list(model)} — plus \"confidence\" (0..1, your calibrated confidence this item is "
        f"correct) and \"span\" (a SHORT verbatim quote copied from the source text that supports "
        f"this item; if you cannot quote support, do not emit the item).\n\n"
        f"SOURCE TEXT:\n\"\"\"\n{text}\n\"\"\"\n"
    )


def extract_typed(
    conn: sqlite3.Connection,
    text: str,
    *,
    item_model: Type[BaseModel],
    instruction: str,
    est_cost_cents: int = 0,
    provider: str = "deepinfra_keyless",
    proxy: str | None = None,
    retries: int = 1,
    max_tokens: int = 2048,
) -> list[Candidate]:
    """Extract a list of `item_model` instances from `text`, validated + span-grounded + tiered.

    Raises LLMConfigError if no key; CostGateError if the batch exceeds the auto-approve cap.
    Returns [] (not an exception) if the model can't produce parseable, valid output after retries —
    that drop is the caller's signal to route to human review, logged not faked.
    """
    prompt = _build_prompt(text, item_model, instruction)
    last_err = ""
    for attempt in range(retries + 1):
        p = prompt if attempt == 0 else (
            prompt + f"\n\nYour previous reply could not be used: {last_err}. "
            f"Reply with ONLY the JSON array."
        )
        raw = llm.complete(conn, p, provider=provider, est_cost_cents=est_cost_cents,
                           max_tokens=max_tokens, proxy=proxy,
                           system="You are a precise information-extraction engine. Output strict JSON only.")
        try:
            data = json.loads(_strip_fences(raw))
        except json.JSONDecodeError as e:
            last_err = f"invalid JSON ({e})"
            continue
        if not isinstance(data, list):
            last_err = "top-level JSON was not an array"
            continue
        cands: list[Candidate] = []
        for obj in data:
            if not isinstance(obj, dict):
                continue
            conf = float(obj.pop("confidence", 0.0) or 0.0)
            span = str(obj.pop("span", "") or "")
            try:
                item = item_model(**obj)
            except ValidationError:
                continue  # drop the malformed item, keep the valid ones
            found = bool(span) and _norm(span) in _norm(text)
            tier = "high" if (conf >= HIGH_CONF and found) else "low"
            cands.append(Candidate(item=item, confidence=conf, span=span, span_found=found, tier=tier))
        return cands  # parsed successfully (even if some items were dropped)
    return []  # exhausted retries → caller routes to human review
