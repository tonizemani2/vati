"""Append-only forecast decision ledger and shadow scoring.

The ledger records what the system knew at submission time: final forecast,
shadow forecasts, anchors, model route, and calibration tag. Later, once
outcomes resolve, `score_binary_shadows` tells us which route would have won.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Any

DEFAULT_LEDGER = Path(__file__).resolve().parents[2] / "data" / "forecasting" / "decisions.jsonl"


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    return str(obj)


def stable_hash(record: dict) -> str:
    payload = {k: v for k, v in record.items() if k != "record_hash"}
    raw = json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def append_decision(record: dict, path: str | Path | None = None) -> dict:
    """Append one decision record and return the normalized record."""
    path = Path(path or DEFAULT_LEDGER)
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = _jsonable(dict(record))
    rec.setdefault("logged_at", datetime.now(timezone.utc).isoformat())
    rec["record_hash"] = stable_hash(rec)
    with path.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
    return rec


def load_decisions(path: str | Path | None = None) -> list[dict]:
    path = Path(path or DEFAULT_LEDGER)
    if not path.exists():
        return []
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def _as_prob(x: Any) -> float | None:
    try:
        p = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(p):
        return None
    return max(0.0, min(1.0, p))


def score_binary_shadows(records: Iterable[dict]) -> dict:
    """Score final and shadow probabilities on records that carry `outcome`.

    Returns {variant: {n, brier}}. Records without a binary outcome are ignored.
    """
    sums: dict[str, list[float]] = {}
    for rec in records:
        if rec.get("outcome") not in (0, 1, False, True):
            continue
        y = 1.0 if rec.get("outcome") in (1, True) else 0.0
        candidates = {}
        if "forecast" in rec:
            candidates["final"] = rec.get("forecast")
        candidates.update(rec.get("shadows") or {})
        for name, value in candidates.items():
            p = _as_prob(value)
            if p is None:
                continue
            sums.setdefault(str(name), []).append((p - y) ** 2)
    return {name: {"n": len(vals), "brier": sum(vals) / len(vals)}
            for name, vals in sorted(sums.items()) if vals}
