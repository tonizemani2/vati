"""Calibration artifact guards for live forecasting paths.

The forecasters deliberately use conservative constants, but the system should
still refuse to treat tiny or malformed backtests as decision-grade evidence.
This module is intentionally schema-light: it can inspect both the Metaculus
calibration JSON and the broader grid-report JSON used elsewhere in the repo.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def _is_finite(x: Any) -> bool:
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def sample_count(doc: dict) -> int:
    """Best-effort sample count across known calibration artifact shapes."""
    for key in ("n", "n_total", "samples", "rows"):
        try:
            n = int(doc.get(key))
            if n >= 0:
                return n
        except (TypeError, ValueError):
            pass
    parts = 0
    for key in ("n_manifold", "n_structural", "n_market", "n_dataset"):
        try:
            parts += int(doc.get(key) or 0)
        except (TypeError, ValueError):
            pass
    return parts


def check_artifact(doc: dict, *, min_n: int = 30,
                   finite_keys: tuple[str, ...] = ("d_star",)) -> dict:
    """Return a machine-readable quality verdict for a calibration artifact."""
    reasons: list[str] = []
    if doc.get("valid") is False:
        reasons.append("artifact marked invalid")
    n = sample_count(doc)
    if n < min_n:
        reasons.append(f"sample count {n} < required {min_n}")
    for key in finite_keys:
        if key in doc and not _is_finite(doc.get(key)):
            reasons.append(f"{key} is not finite")
    return {"usable": not reasons, "n": n, "reasons": reasons}


def calibration_tag(constants: dict, artifact: dict | None = None) -> str:
    """Stable short tag for logging which calibration settings produced a forecast."""
    payload = {"constants": constants, "artifact": artifact or {}}
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

