"""Typed contract for world-state extraction pilots.

The pilot implementations can be LLM-backed or rule-backed, but they must emit this shape before any
row is allowed into world_state_facts. This keeps the expensive part swappable while the database,
evaluation, and forecast prompt path stay deterministic.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

PILOT_MAX_DOCS = 50_000
PILOT_MAX_LLM_SPEND_CENTS = 15_000
CRITICAL_EVAL_FIELDS = ("subject", "date", "predicate", "value")
CRITICAL_PRECISION_TARGET = 0.85


class ExtractionSourceKind(str, Enum):
    sec_filing = "sec_filing"
    patent = "patent"
    news_event = "news_event"
    research_abstract = "research_abstract"
    policy = "policy"
    other = "other"


class ExtractedEntity(BaseModel):
    name: str
    kind: str
    external_ids: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str

    @field_validator("name", "kind", "rationale")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("entity extraction fields must be non-empty")
        return v.strip()


class ExtractedFact(BaseModel):
    subject: str
    predicate: str
    object: str | None = None
    value: float | None = None
    unit: str | None = None
    event_time: date | None = None
    published_at: date | None = None
    observed_at: date | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    evidence_span: str

    @field_validator("subject", "predicate", "rationale", "evidence_span")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("fact extraction fields must be non-empty")
        return v.strip()


class ExtractedRelationship(BaseModel):
    src: str
    rel: str
    dst: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    evidence_span: str

    @field_validator("src", "rel", "dst", "rationale", "evidence_span")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("relationship extraction fields must be non-empty")
        return v.strip()


class ExtractionResult(BaseModel):
    extractor: str
    source_kind: ExtractionSourceKind
    source_id: str | None = None
    content_hash: str | None = None
    input_hash: str
    model: str | None = None
    entities: list[ExtractedEntity] = Field(default_factory=list)
    facts: list[ExtractedFact] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)
    cost_cents: int = Field(default=0, ge=0)

    @field_validator("extractor", "input_hash")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("extraction result fields must be non-empty")
        return v.strip()


def critical_precision(rows: list[dict[str, Any]]) -> float:
    """Compute strict all-critical-fields precision for a labeled eval result set."""

    if not rows:
        return 0.0
    correct = 0
    for row in rows:
        if all(bool(row.get(f"{field}_correct")) for field in CRITICAL_EVAL_FIELDS):
            correct += 1
    return correct / len(rows)

