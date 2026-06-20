"""Third-slot diversified ForecastBench submission variants.

ForecastBench allows up to three forecast sets per round. The primary file keeps
our best recent-round backtest score; this module builds an extra, non-blocking
variant from the already-built primary submission so the runner can use the
third slot without re-fetching dataset series or risking the main path.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from . import submit as S
from .market import MARKET_CALIBRATION
from .score import MARKET_SOURCES

SOFT_MARKET_SCALE = 0.75
DIVERSE_MODEL = "vati-2.0-soft-market"
RAW_MARKET_MODEL = "vati-2.0-raw-market"


def _key(qid):
    return tuple(qid) if isinstance(qid, list) else qid


def _logit(p: float) -> float:
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-z))


def _soft_market_probability(src: str, raw_p: float) -> float:
    params = MARKET_CALIBRATION.get(str(src).lower())
    if params is None:
        return min(max(float(raw_p), 0.02), 0.98)
    slope, intercept = params
    q = _sigmoid((slope * SOFT_MARKET_SCALE) * _logit(raw_p) + (intercept * SOFT_MARKET_SCALE))
    return min(max(q, 0.02), 0.98)


def _raw_market_probability(src: str, raw_p: float) -> float:
    return min(max(float(raw_p), 0.02), 0.98)


def make_market_variant(
    qset_path: str,
    primary_path: str,
    out_path: str | None = None,
    mode: str = "soft-market",
) -> str:
    """Copy the primary submission and vary market-source calibration only.

    Dataset rows stay byte-for-byte identical in probability to the primary file,
    preserving the stronger dataset calibration. Current ForecastBench rounds are
    single-only; if a legacy combo qset is supplied, fail closed rather than
    producing inconsistent combo probabilities.
    """
    if mode not in {"soft-market", "raw-market"}:
        raise ValueError(f"unknown market variant mode: {mode}")

    qd = json.loads(Path(qset_path).read_text())
    questions = qd.get("questions", [])
    if any(isinstance(q.get("id"), list) for q in questions):
        raise ValueError("market variants only support single-only question sets")

    primary = json.loads(Path(primary_path).read_text())
    if primary.get("question_set") != qd.get("question_set"):
        raise ValueError("primary submission question_set does not match qset")

    q_by_key = {
        (q.get("source"), _key(q.get("id"))): q
        for q in questions
        if q.get("source") in MARKET_SOURCES
    }

    rows = []
    moved = 0
    for row in primary.get("forecasts", []):
        new = dict(row)
        if new.get("source") in MARKET_SOURCES and new.get("direction") is None:
            q = q_by_key.get((new.get("source"), _key(new.get("id"))))
            if q is not None:
                try:
                    raw_p = float(q["freeze_datetime_value"])
                    if mode == "raw-market":
                        p = _raw_market_probability(q["source"], raw_p)
                    else:
                        p = _soft_market_probability(q["source"], raw_p)
                except (KeyError, TypeError, ValueError):
                    p = None
                if p is not None:
                    p = round(float(p), 6)
                    moved += int(abs(p - float(new["forecast"])) > 1e-9)
                    new["forecast"] = p
                    if new.get("reasoning"):
                        new["reasoning"] = f"{new['reasoning']} {mode} variant."
        rows.append(new)

    due = qd["forecast_due_date"]
    default_slot = 2 if mode == "raw-market" else 3
    out_path = out_path or f"data/forecastbench/{due}.{S.ORG}.{default_slot}.json"
    model = RAW_MARKET_MODEL if mode == "raw-market" else DIVERSE_MODEL
    out = {
        "organization": primary.get("organization", S.ORG),
        "model": model,
        "model_organization": primary.get("model_organization", S.ORG),
        "question_set": qd["question_set"],
        "forecasts": rows,
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(out))
    print(f"wrote {out_path}: {mode} variant moved {moved} market rows")
    return out_path


def make_soft_market_variant(qset_path: str, primary_path: str, out_path: str | None = None) -> str:
    return make_market_variant(qset_path, primary_path, out_path, mode="soft-market")


def make_raw_market_variant(qset_path: str, primary_path: str, out_path: str | None = None) -> str:
    return make_market_variant(qset_path, primary_path, out_path, mode="raw-market")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    mode = "soft-market"
    if argv and argv[0] == "--mode":
        if len(argv) < 2:
            print("error: --mode requires a value", file=sys.stderr)
            return 2
        mode = argv[1]
        argv = argv[2:]
    if len(argv) not in (2, 3):
        print(
            "usage: python -m engine.forecastbench.diversify "
            "[--mode soft-market|raw-market] <qset.json> <primary.json> [out.json]",
            file=sys.stderr,
        )
        return 2
    make_market_variant(argv[0], argv[1], argv[2] if len(argv) == 3 else None, mode=mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
