"""Local, offline Brier backtest for the Prophet Arena agent — the honest gate before submitting.

Reads resolved tasks straight from a local clone of ai-prophet-datasets (no network, no creds),
runs engine.prophet.agent.predict on each, and scores with Prophet's own multiclass Brier
(sum_i (p_i - 1[winner])^2, winner = resolved_outcome.value[0]). Reports mean Brier vs a uniform
baseline so we can see our real standing against the ~0.056 Brier (0.944 1-Brier) agent-board bar.

NOTE: dataset tasks carry NO Kalshi market_stats, so this measures the COLD research forecast
without the price anchor. On efficient sports markets that understates us badly (the live board
hands us the price); the signal here is the non-sports tail + end-to-end wiring.

Usage:
  python -m engine.prophet.backtest --repo /tmp/ai-prophet-datasets --dataset sample-resolved --limit 5
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from engine.prophet import agent


def _event_from_task(t: dict) -> dict:
    src = (t.get("metadata") or {}).get("source") or {}
    return {
        "event_ticker": src.get("event_ticker") or t.get("source") or t.get("task_id"),
        "market_ticker": t.get("task_id"),
        "title": t.get("title") or "",
        "subtitle": None,
        "description": t.get("context") or "",
        "category": (t.get("metadata") or {}).get("category") or "Unknown",
        "rules": src.get("rules") or t.get("context") or "",
        "close_time": src.get("close_time") or t.get("predict_by") or "",
        "outcomes": t.get("outcomes") or [],
    }


def _winner(t: dict) -> str | None:
    ro = t.get("resolved_outcome") or {}
    val = ro.get("value")
    if isinstance(val, list) and val:
        return str(val[0])
    if isinstance(val, str):
        return val
    return None


def _brier(probs: list[dict], winner: str) -> float:
    return sum((p["probability"] - (1.0 if p["market"] == winner else 0.0)) ** 2 for p in probs)


def main() -> None:
    args = sys.argv[1:]

    def opt(flag, default=None):
        return args[args.index(flag) + 1] if flag in args else default

    repo = opt("--repo", "/tmp/ai-prophet-datasets")
    dataset = opt("--dataset", "sample-resolved")
    release = opt("--release", "v1.0.0")
    limit = int(opt("--limit", "0") or 0)

    path = Path(repo) / "datasets" / dataset / "releases" / release / "tasks.jsonl"
    tasks = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    tasks = [t for t in tasks if _winner(t) is not None]
    if limit:
        tasks = tasks[:limit]

    print(f"Scoring {len(tasks)} resolved tasks from {dataset}/{release}\n")
    ours, unif = [], []
    for i, t in enumerate(tasks, 1):
        ev = _event_from_task(t)
        win = _winner(t)
        try:
            pred = agent.predict(ev)["probabilities"]
        except Exception as e:  # keep the run going; a dead event shouldn't tank the backtest
            print(f"[{i}] ERROR {ev['market_ticker']}: {e!r}")
            continue
        b = _brier(pred, win)
        n = len(ev["outcomes"]) or 2
        ub = sum((1.0 / n - (1.0 if o == win else 0.0)) ** 2 for o in ev["outcomes"])
        ours.append(b); unif.append(ub)
        pstr = ", ".join(f"{p['market'][:18]}={p['probability']:.2f}" for p in pred)
        print(f"[{i}] {ev['category']:<12} brier={b:.3f} (unif {ub:.3f}) win={win[:22]:<22} | {pstr}")

    if ours:
        mean = sum(ours) / len(ours)
        umean = sum(unif) / len(unif)
        print(f"\n== mean Brier {mean:.4f}  (1-Brier {1-mean:.4f})  | uniform {umean:.4f}  | n={len(ours)} ==")
        print("   agent-board bar: Agent GPT-5.5 1-Brier 0.9441 (Brier ~0.0559), market 0.8506 (~0.1494)")


if __name__ == "__main__":
    main()
