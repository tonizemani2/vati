"""Chat → engine bridge: turn a decomposed forecast spec into REAL engine numbers.

The chat app (../chat) shells out to this. It is the seam that makes the chat answer
with OUR backend, not an LLM's guessed probability: the model proposes the Fermi
decomposition (a measurable quantity, its current value, projected growth, and the
threshold that defines YES); THIS computes the probability, the 80% interval, and the
distribution by running the same Monte-Carlo engine the forecast cards use
(`engine.forecast.mc_quantity`). The number falls out of the samples (doctrine §2.2).

Pure + $0: stdlib `random` only, no network, no DB, no cost gate. Reads a JSON spec on
stdin, writes a JSON result on stdout.

Usage:
    echo '<spec json>' | uv run python -m engine.chat_bridge forecast
"""

from __future__ import annotations

import hashlib
import json
import sys

from engine.forecast import mc_quantity


def _seed_from(question: str) -> int:
    """Deterministic seed so the same question reproduces the same distribution."""
    return int(hashlib.sha256(question.encode("utf-8")).hexdigest()[:8], 16)


def _histogram(samples: list[float], bins: int = 28) -> dict:
    """Compact histogram over the central 96% of the samples, for a sparkline."""
    n = len(samples)
    lo = samples[int(0.02 * n)]
    hi = samples[int(0.98 * n)]
    if hi <= lo:
        hi = lo + 1.0
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in samples:
        if v < lo or v > hi:
            continue
        idx = min(bins - 1, int((v - lo) / width))
        counts[idx] += 1
    peak = max(counts) or 1
    return {"lo": lo, "hi": hi, "counts": counts, "peak": peak}


def forecast(spec: dict) -> dict:
    """Run the MC engine on a decomposed spec. Returns engine-computed P, CI, median, hist."""
    question = str(spec.get("question", "")).strip()
    base_value = float(spec["base_value"])
    horizon_years = int(spec["horizon_years"])
    g_mean = float(spec.get("g_mean", 1.0))
    g_sd = float(spec.get("g_sd", 0.1))
    decel = float(spec.get("decel", 0.0))
    threshold = float(spec["threshold"])
    direction = str(spec.get("threshold_dir", ">=")).strip() or ">="
    seed = int(spec.get("seed") or _seed_from(question or str(base_value)))
    # 80k samples keeps P accurate to ~0.2% and the histogram smooth, while staying
    # snappy enough for an interactive card (the full card pipeline uses 300k).
    n = int(spec.get("n") or 80_000)

    q = mc_quantity(
        base_value, horizon_years,
        g_mean=g_mean, g_sd=g_sd, decel=decel, seed=seed, n=n,
    )
    p = q.prob_beyond(threshold, direction)

    return {
        "ok": True,
        "engine": "monte_carlo_fermi",
        "probability": round(p, 3),
        "median": q.median,
        "ci_low": q.ci_low,
        "ci_high": q.ci_high,
        "threshold": threshold,
        "threshold_dir": direction,
        "horizon_years": horizon_years,
        "base_value": base_value,
        "n_samples": len(q.samples),
        "histogram": _histogram(q.samples),
    }


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "forecast"
    raw = sys.stdin.read()
    try:
        spec = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"bad spec json: {e}"}))
        return 1

    try:
        if cmd == "forecast":
            out = forecast(spec)
        elif cmd == "signals":
            # Topic → structural evidence pack from the data layer (grounds the forecast).
            from engine.signals import evidence_pack, format_pack
            topic = str(spec.get("topic") or spec.get("question") or "").strip()
            if not topic:
                out = {"ok": False, "error": "signals needs a 'topic' or 'question'"}
            else:
                pack = evidence_pack(topic)
                out = {"ok": True, "engine": "data_layer_signals",
                       "context": format_pack(pack), **pack}
        else:
            out = {"ok": False, "error": f"unknown command {cmd!r}"}
    except (KeyError, ValueError, TypeError) as e:
        out = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    print(json.dumps(out))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
