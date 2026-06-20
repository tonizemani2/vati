"""Offline evaluation for external market anchor routing.

This uses the resolved Manifold qbank as a model-free simulator:

1. For each target title, find the highest-similarity other market title that
   the old title-only matcher would have accepted.
2. Score that candidate's historical crowd price against the target outcome.
3. Compare old behavior (blend every accepted external anchor) with new behavior
   (blend only hard-gate-accepted anchors; otherwise keep the base forecast).

The base forecast is the target market's own crowd price. That is intentionally
strong: it tests whether external anchors add value when a competent base signal
already exists. If an external-anchor rule cannot help there, it should be
logging/shadow-only until live hidden-crowd data proves otherwise.

Run:
  python -m engine.forecasting.eval_anchor_gate
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from engine.metaculus import markets

QBANK = Path(__file__).resolve().parents[2] / "data" / "metaculus" / "qbank.jsonl"


def _logit(p: float) -> float:
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-z))


def _anchor_weight(sim: float) -> float:
    return round(0.20 + 0.30 * min(1.0, max(0.0, (sim - 0.55) / 0.45)), 2)


def _blend(base: float, anchor: float, sim: float) -> float:
    w = _anchor_weight(sim)
    return _sigmoid((1 - w) * _logit(base) + w * _logit(anchor))


def _brier(rows: list[dict], key: str) -> float:
    return sum((r[key] - r["outcome"]) ** 2 for r in rows) / len(rows)


def evaluate(*, top_k: int = 60, min_shared_tokens: int = 2) -> dict:
    rows = [json.loads(line) for line in QBANK.open() if line.strip()]
    rows = [
        r for r in rows
        if r.get("crowd_final") is not None
        and r.get("outcome") in (True, False)
        and (r.get("vol") or 0) >= markets.MIN_VOLUME
    ]

    index: dict[str, list[int]] = defaultdict(list)
    tokens: list[set[str]] = []
    lowers: list[str] = []
    for i, row in enumerate(rows):
        ts = markets._norm(row["title"])
        tokens.append(ts)
        lowers.append(row["title"].lower())
        for token in ts:
            index[token].append(i)

    def similarity(i: int, j: int) -> float | None:
        ta, tb = tokens[i], tokens[j]
        jac = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
        if 0.6 * jac + 0.4 < markets.MIN_SIM:
            return None
        return 0.6 * jac + 0.4 * SequenceMatcher(None, lowers[i], lowers[j]).ratio()

    pairs: list[dict] = []
    for i, row in enumerate(rows):
        counts: Counter[int] = Counter()
        for token in tokens[i]:
            for j in index[token]:
                if j != i:
                    counts[j] += 1
        best = None
        for j, count in counts.most_common(top_k):
            if count < min_shared_tokens:
                continue
            sim = similarity(i, j)
            if sim is None or sim < markets.MIN_SIM:
                continue
            usable, reasons = markets._usable_match(row["title"], rows[j]["title"])
            if best is None or sim > best[0]:
                best = (sim, j, usable, reasons)
        if best is None:
            continue
        sim, j, usable, reasons = best
        outcome = 1.0 if row["outcome"] else 0.0
        base = float(row["crowd_final"])
        anchor = float(rows[j]["crowd_final"])
        old = _blend(base, anchor, sim)
        new = old if usable else base
        pairs.append({
            "outcome": outcome,
            "base": base,
            "anchor": anchor,
            "old_blend": old,
            "new_gate": new,
            "new_accept": usable,
            "reasons": reasons,
            "sim": sim,
        })

    accepted = [p for p in pairs if p["new_accept"]]
    rejected = [p for p in pairs if not p["new_accept"]]

    def block(name: str, subset: list[dict]) -> dict:
        if not subset:
            return {"n": 0}
        return {
            "n": len(subset),
            "base_brier": _brier(subset, "base"),
            "old_blend_brier": _brier(subset, "old_blend"),
            "new_gate_brier": _brier(subset, "new_gate"),
            "new_minus_old": _brier(subset, "new_gate") - _brier(subset, "old_blend"),
            "new_minus_base": _brier(subset, "new_gate") - _brier(subset, "base"),
        }

    return {
        "eligible_rows": len(rows),
        "old_accepted_pairs": len(pairs),
        "new_accepts": len(accepted),
        "new_rejects": len(rejected),
        "reject_reasons": Counter(reason for p in rejected for reason in p["reasons"]).most_common(),
        "all": block("all", pairs),
        "accepted": block("accepted", accepted),
        "rejected": block("rejected", rejected),
    }


def main() -> None:
    result = evaluate()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
