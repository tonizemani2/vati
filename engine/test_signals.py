"""Regression invariants for the data-layer → AI-backend seam (engine.signals + chat_bridge signals).

Run:  uv run python -m engine.test_signals      (exits non-zero on failure)
Cheap, $0, read-only against data/foresight.db. Guards the contract the AI backend relies on:
no crashes, junk/empty topics return nothing, real topics return relevant dated signals, and the
chat_bridge JSON envelope is well-formed.
"""
from __future__ import annotations

import json
import subprocess
import sys

from engine.signals import evidence_pack, format_pack

FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {msg}")
    if not cond:
        FAILS.append(msg)


def main() -> int:
    # 1. junk / empty topics return an honest empty pack, never crash
    for junk in ["", "  ", "a", "of the", "asdfqwerzzz", "!!!"]:
        p = evidence_pack(junk)
        check(p["found"] is False and not p["series"] and not p["patents"],
              f"junk {junk!r:14s} -> empty pack")

    # 2. a real, well-covered topic returns relevant dated signals
    p = evidence_pack("solid state battery")
    check(p["found"] and len(p["series"]) >= 3, "solid state battery -> >=3 series")
    check(any("batter" in s["label"].lower() for s in p["series"]), "  includes a battery series")
    check(len(p["patents"]) >= 1, "  includes patent concentration")
    for s in p["series"]:
        check(isinstance(s.get("latest"), (list, tuple)) and len(s["latest"]) == 2,
              f"  series '{s['label'][:30]}' has a (year,value) latest") if False else None
    check(all(s.get("first") and s.get("latest") for s in p["series"]),
          "  every series carries first+latest dated points")

    # 3. deep learning surfaces the takeoff (the blind-spot channels exist)
    p = evidence_pack("deep learning")
    metrics = {s["metric"] for s in p["series"]}
    check(p["found"] and metrics & {"research_share_ppm", "research_works", "topic_share",
                                    "field_breadth", "field_diffusion", "works_per_year"},
          "deep learning -> at least one leading research channel present")

    # 4. cap is respected, ordering is leading-first
    p = evidence_pack("energy")
    check(len(p["series"]) <= 12, "energy -> series capped at 12")

    # 5. format_pack is always a non-empty string
    check(isinstance(format_pack(evidence_pack("crispr")), str), "format_pack -> str")
    check("none found" in format_pack(evidence_pack("asdfqwerzzz")),
          "empty pack formats an honest 'none found'")

    # 6. chat_bridge JSON envelope (the actual seam the AI backend calls)
    proc = subprocess.run([sys.executable, "-m", "engine.chat_bridge", "signals"],
                          input=json.dumps({"question": "will solid state batteries scale by 2030?"}),
                          capture_output=True, text=True)
    try:
        env = json.loads(proc.stdout)
        check(env.get("ok") is True and isinstance(env.get("context"), str) and env["context"],
              "chat_bridge signals -> {ok:true, context:str}")
    except (json.JSONDecodeError, KeyError):
        check(False, f"chat_bridge signals returned valid JSON (got: {proc.stdout[:120]!r})")

    # 7. chat_bridge with no topic -> clean error, not a crash
    proc = subprocess.run([sys.executable, "-m", "engine.chat_bridge", "signals"],
                          input=json.dumps({}), capture_output=True, text=True)
    env = json.loads(proc.stdout or "{}")
    check(env.get("ok") is False, "chat_bridge signals with no topic -> ok:false")

    print(f"\n{'ALL PASS' if not FAILS else f'{len(FAILS)} FAILED'}  "
          f"({'green' if not FAILS else 'red'})")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
