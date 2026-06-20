"""Retrieval bridge: put the measured data layer in front of the forecaster.

Pope (and any forecasting agent) reasons from prompts + ad-hoc web search and never touches the 6GB
data layer. This composes the three retrieval primitives that DO read it into one grounding pack:

  1. world_seed.coverage   — the thesis-spine walk: which of the 9 causal layers the world graph can
                             SEE for this topic, and which are blank (the GAP = where you may have edge
                             the crowd has no structure on, or the part the structure is blind to).
  2. signals.evidence_pack — the dated, measured base: research/trade series with trends + detector
                             fires, patent HHI/concentration, and the measured citation-dependency
                             edges (draws_on / drawn_on_by) to name the inelastic input.
  3. market.market_anchor  — the priced-in gate: is a live prediction market already trading this?
                             PRICED => the edge is only the GAP to your P, not the level.

Usage:
    uv run python -m engine.ground "rare earth magnets"
    uv run python -m engine.ground --json "lithium"

The Pope channel + gate agents run this FIRST and reason from its output instead of from vibes.
Deterministic, keyless, $0 (market_anchor hits Manifold/Metaculus; degrades gracefully offline).
"""
from __future__ import annotations

import sys

from engine import db, market, signals, world_seed


def ground_pack(topic: str) -> dict:
    """Compose the three retrieval primitives into one grounding pack for a topic."""
    conn = db.connect()
    try:
        cov = world_seed.coverage(conn, topic)
    finally:
        conn.close()
    pack = signals.evidence_pack(topic)
    try:
        anchor = market.market_anchor(topic)
    except Exception as exc:  # keyless network call — never let the gate sink the whole pack
        anchor = {"query": topic, "markets": [], "verdict": "UNPRICED-UNSEEN",
                  "error": f"{type(exc).__name__}: {exc}"}
    return {"topic": topic, "coverage": cov, "signals": pack, "anchor": anchor}


HOWTO = (
    "HOW TO USE THIS PACK (do not ignore it and free-associate):\n"
    "  - The measured SIGNALS are your base rate. Cite the specific trend/fire you lean on; do not "
    "assert a number the data can contradict.\n"
    "  - Walk the DEPENDENCY edges to name the *inelastic input* (a mid-weight draws_on with a heavy "
    "inbound load), not the theme. The needle is the constraint, never the curve.\n"
    "  - A spine-layer marked GAP is either (a) genuine edge — the crowd has no structure where you "
    "do — or (b) the blind spot in your own call. Say which, explicitly.\n"
    "  - The MARKET ANCHOR is the gate. If a liquid market sits near your P, the thesis is PRICED: "
    "quote the GAP between your probability and the market's, or kill the call. UNPRICED-UNSEEN is "
    "NOT a green light.\n"
    "  - If a channel is empty here, forecast from first principles and SAY the data layer is blind "
    "to it — that honesty is the product."
)


def format_ground(g: dict) -> str:
    topic = g["topic"]
    bar = "=" * 76
    parts = [
        bar,
        f"WORLD-GROUNDING PACK — '{topic}'   (measured data layer: dated, leak-free, $0)",
        bar,
        "",
        "## 1. SPINE COVERAGE  (Frontier->Capability->Dependency->Supply->Demand->Capital->Pricing->Policy->Outcome)",
        world_seed.format_coverage(g["coverage"]),
        "",
        "## 2. MEASURED SIGNALS  (the dated base for the Fermi decomposition)",
        signals.format_pack(g["signals"]),
        "",
        "## 3. NAMED REAL-WORLD MATCHES  (who holds / operates / signed / owns it)",
        signals.format_entities(g["signals"].get("actors", [])),
        "",
        "## 4. PRICED-IN GATE  (correct + already priced = zero edge)",
        market.format_anchor(g["anchor"]),
        "",
        bar,
        HOWTO,
    ]
    return "\n".join(parts)


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a != "--json"]
    as_json = "--json" in argv
    topic = " ".join(args).strip()
    if not topic:
        print('usage: python -m engine.ground [--json] "<topic or claim>"', file=sys.stderr)
        return 1
    g = ground_pack(topic)
    if as_json:
        import json
        print(json.dumps(g, ensure_ascii=False, default=str))
    else:
        print(format_ground(g))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
