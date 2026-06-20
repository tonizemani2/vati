"""Chat → engine bridge: turn a decomposed forecast spec into REAL engine numbers.

The chat app (../chat) shells out to this. It is the seam that makes the chat answer
with OUR backend, not an LLM's guessed probability: the model proposes the Fermi
decomposition (a measurable quantity, its current value, projected growth, and the
threshold that defines YES); THIS computes the probability, the 80% interval, and the
distribution by running the same Monte-Carlo engine the forecast cards use
(`engine.forecast.mc_quantity`). The number falls out of the samples (doctrine §2.2).

$0 throughout. The `forecast` verb is pure (stdlib `random`, no I/O); `signals` reads the
data layer (SQLite + the derived feed artifacts); `market` does keyless prediction-market
reads (cost-gated $0); `world_state` reads the timestamped fact spine and returns a frozen
snapshot manifest; `world_research` returns dated paper/research context; `world_state_proof`
returns the same point-in-time gates and raw-byte provenance without recording a DB snapshot.
Each reads a JSON spec on stdin, writes a JSON result on stdout.

Usage:
    echo '<spec json>' | uv run python -m engine.chat_bridge forecast
    echo '{"topic":"deep learning"}' | uv run python -m engine.chat_bridge signals
    echo '{"topic":"AI power bottlenecks","as_of":"2024-06-01"}' | uv run python -m engine.chat_bridge world_state
    echo '{"topic":"solid state battery","as_of":"2023-12-31"}' | uv run python -m engine.chat_bridge world_research
    echo '{"topic":"AI power bottlenecks","as_of":"2024-06-01"}' | uv run python -m engine.chat_bridge world_state_proof
    echo '{"claim":"US recession in 2026"}' | uv run python -m engine.chat_bridge market
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


def _bool_spec(spec: dict, key: str, default: bool) -> bool:
    value = spec.get(key, default)
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "y", "on"}:
            return True
        if v in {"0", "false", "no", "n", "off"}:
            return False
    return default


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
        elif cmd == "world_state":
            # Topic + as_of -> frozen world-state context with snapshot hash and leak gates.
            from datetime import date

            from engine import db, world_state

            topic = str(spec.get("topic") or spec.get("question") or spec.get("claim") or "").strip()
            if not topic:
                out = {"ok": False, "error": "world_state needs a 'topic', 'question' or 'claim'"}
            else:
                as_of = str(spec.get("as_of") or date.today().isoformat())[:10]
                record = _bool_spec(spec, "record", True)
                conn = db.connect()
                db.init_db(conn)
                pack = world_state.state_pack(topic, as_of, conn=conn, record=record)
                conn.close()
                out = {"ok": True, "engine": "world_state", "context": world_state.format_pack(pack), **pack}
        elif cmd == "world_state_proof":
            # Topic + as_of -> read-only proof of the exact facts and leak gates.
            from datetime import date

            from engine import db, world_state

            topic = str(spec.get("topic") or spec.get("question") or spec.get("claim") or "").strip()
            if not topic:
                out = {"ok": False, "error": "world_state_proof needs a 'topic', 'question' or 'claim'"}
            else:
                as_of = str(spec.get("as_of") or date.today().isoformat())[:10]
                limit = int(spec.get("limit") or 12)
                conn = db.connect()
                db.init_db(conn)
                proof = world_state.state_proof(topic, as_of, conn=conn, limit=limit)
                conn.close()
                out = {"ok": True, "engine": "world_state_proof", "context": world_state.format_proof(proof), **proof}
        elif cmd == "world_research":
            # Topic + as_of -> read-only paper/research context under point-in-time gates.
            from datetime import date

            from engine import db, world_state

            topic = str(spec.get("topic") or spec.get("question") or spec.get("claim") or "").strip()
            if not topic:
                out = {"ok": False, "error": "world_research needs a 'topic', 'question' or 'claim'"}
            else:
                as_of = str(spec.get("as_of") or date.today().isoformat())[:10]
                paper_limit = int(spec.get("paper_limit") or world_state.DEFAULT_RESEARCH_PAPER_LIMIT)
                fact_limit = int(spec.get("fact_limit") or world_state.DEFAULT_RESEARCH_FACT_LIMIT)
                count_fact_exclusions = _bool_spec(spec, "count_fact_exclusions", False)
                count_paper_exclusions = _bool_spec(spec, "count_paper_exclusions", False)
                search_abstracts = _bool_spec(spec, "search_abstracts", False)
                fill_token_fallback = _bool_spec(spec, "fill_token_fallback", False)
                full_paper_scan = _bool_spec(spec, "full_paper_scan", False)
                paper_scan_rows = int(spec.get("paper_scan_rows") or world_state.DEFAULT_RESEARCH_PAPER_SCAN_ROWS)
                conn = db.connect()
                db.init_db(conn)
                pack = world_state.research_pack(
                    topic,
                    as_of,
                    conn=conn,
                    paper_limit=paper_limit,
                    fact_limit=fact_limit,
                    count_fact_exclusions=count_fact_exclusions,
                    count_paper_exclusions=count_paper_exclusions,
                    search_abstracts=search_abstracts,
                    fill_token_fallback=fill_token_fallback,
                    full_paper_scan=full_paper_scan,
                    paper_scan_rows=paper_scan_rows,
                )
                conn.close()
                out = {"ok": True, "engine": "world_research", "context": world_state.format_research_pack(pack), **pack}
        elif cmd == "market":
            # Claim → live prediction-market anchor (the 'already priced?' check, keyless).
            from engine.market import format_anchor, market_anchor
            claim = str(spec.get("claim") or spec.get("topic") or spec.get("question") or "").strip()
            if not claim:
                out = {"ok": False, "error": "market needs a 'claim', 'topic' or 'question'"}
            else:
                a = market_anchor(claim)
                out = {"ok": True, "engine": "prediction_market_anchor",
                       "context": format_anchor(a), **a}
        else:
            out = {"ok": False, "error": f"unknown command {cmd!r}"}
    except (KeyError, ValueError, TypeError) as e:
        out = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    print(json.dumps(out))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
