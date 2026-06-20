#!/usr/bin/env python3
"""Pope MEGA, DeepSeek edition — the deep tier on a cheap, decorrelated (non-Claude) model.

Why this exists. The `.claude/workflows/pope-mega.js` tier runs ~49 Claude agents WITH tools (they
loop `engine.cli` + web search). DeepSeek via `engine.adapters.llm` is text-in/text-out: no tools.
So the agentic grounding is moved OUT of the model and INTO Python — we compute the measured
grounding pack deterministically (coverage + dated signals + dependency edges + the LIVE priced-in
market anchor, all from `engine.ground`) and inject it into every prompt. The model reasons FROM the
substrate instead of being trusted to fetch it. Cheap (~$1-3/run on deepseek-v4-pro), and a genuine
second opinion decorrelated from our Claude stack.

Pipeline (faithful to pope-mega.js): 10 orthogonal channel miners x N -> per-candidate adversarial
gate+refute+dual-probability -> cross-cutting synthesis (top_k) -> per-call implications/capture.
Emits a render.py-compatible JSON to research/pope/<slug>-<date>.json.

    uv run python -m engine.pope.mega_deepseek --domain "critical minerals" --horizon long \
        --channels 10 --per-channel 3 --top-k 8

Then: render -> publish_site -> `cd site && pnpm ship`.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from engine import db, ground, market
from engine.adapters.llm import complete
from engine.emergent_scan import _extract_json

MODEL = "deepseek-v4-pro"
PROVIDER = "deepseek"
REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "research" / "pope"

STYLE = ("Write prose in plain, human English. No em-dashes. No promotional filler. Mechanism first. "
         "Name the specific input or event, never a vague theme. No hedging.")

# ---------------------------------------------------------------- channel sets
LONG_CHANNELS = [
    ("physical-limits", "a hard physical or thermodynamic limit (energy, heat, mass, rate, conservation law) that forces a shift almost nobody is pricing"),
    ("demographic-locks", "an already-determined demographic or biological fact (cohorts already born, aging, fixed fertility) that guarantees future demand or scarcity"),
    ("materials-chokepoint", "an inelastic upstream material or midstream processing chokepoint hidden beneath a popular theme; a granular sub-node nobody stockpiled"),
    ("constraint-migration", "a constraint-migration cascade: once the obvious bottleneck gets funded, rent jumps one layer upstream to an unpriced node"),
    ("methods-diffusion", "a research method or technique quietly crossing from one field into another and repricing the scarce input (data, verifier, reference set)"),
    ("policy-weaponization", "a geopolitical capture or export-control / licensing move on a specific granular sub-node, below the level of headline metals"),
    ("pricing-arbitrage", "something structurally true and near-certain markets have not priced because it is boring, invisible, or hard to financialize (human capital, permits, disposal capacity)"),
    ("patent-tell", "a tight cluster of <6 assignees fencing IP around an inelastic node, an early tell of where rent will concentrate"),
    ("second-order", "the second-order consequence the obvious trend forces next, which the loud first-order narrative ignores"),
    ("wildcard", "a deliberately contrarian, anti-consensus, maximally disruptive call; aperture fully open, generate boldly (the gate keeps it honest later)"),
]
SHORT_CHANNELS = [
    ("scheduled-catalyst", "a specific DATED event in the next 3-18 months (regulatory ruling, court decision, election, launch, contract/treaty expiry, guidance/print) whose outcome the market is mis-handicapping"),
    ("flow-imbalance", "a near-term supply/demand or inventory imbalance (shortage or glut) that will visibly clear within months and reprice a specific input"),
    ("capacity-online", "specific new capacity, a new entrant, or a ramp coming online inside the window that breaks or makes a current price the market still assumes holds"),
    ("policy-pending", "a pending policy, export-control, tariff, or subsidy decision with a KNOWN decision date inside the window whose direction is underpriced"),
    ("positioning-unwind", "a crowded consensus trade or narrative about to break on a specific near-term data print or event; the consensus is the mispricing"),
    ("second-order-shock", "the near-term second-order consequence of a RECENT shock (last 1-6 months) the market has not yet propagated to the dependent input"),
    ("demand-inflection", "a near-term demand inflection: an adoption curve crossing a threshold, a mandate/standard start date, or a seasonal swing that forces a measurable move"),
    ("supply-disruption", "a near-term supply disruption already in motion (outage, strike, sanction, weather, depletion) whose price bite has not yet landed"),
    ("refinance-wall", "a debt maturity, funding wall, or covenant trip inside the window that forces a sale, cut, or repricing the market treats as distant"),
    ("wildcard-near", "a deliberately contrarian near-term call; aperture fully open, generate boldly (the gate keeps it honest later)"),
]


def _llm(conn, prompt: str, system: str, *, max_tokens: int) -> dict | None:
    """One DeepSeek call -> parsed JSON, robust to reasoner chain-of-thought. Retries once."""
    for attempt in range(2):
        p = prompt if attempt == 0 else prompt + "\n\nReturn ONLY the JSON object, nothing else."
        try:
            raw = complete(conn, p, provider=PROVIDER, system=system, model=MODEL,
                           max_tokens=max_tokens, est_cost_cents=0,
                           extra_body={"response_format": {"type": "json_object"}})
        except Exception as exc:  # noqa: BLE001
            return {"_error": f"{type(exc).__name__}: {exc}"}
        parsed = _extract_json(raw)
        if parsed is not None:
            return parsed
    return None


def _scrub(o):
    """Strip AI-tell dash variants from all strings (Ruben's no-em-dash / no-slop rule). Em/en/bar
    dashes -> comma clauses; numeric en-dash and non-breaking/figure hyphens -> plain hyphen."""
    if isinstance(o, dict):
        return {k: _scrub(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_scrub(x) for x in o]
    if not isinstance(o, str):
        return o
    s = re.sub(r"[‐‑‒]", "-", o)
    s = re.sub(r"(?<=\d)–(?=\d)", "-", s)
    s = re.sub(r"\s*[–―—]\s*", ", ", s)
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r",\s*,", ",", s)
    return s


def _pool_map(fn, items, workers: int = 4):
    """Run fn over items concurrently (network-bound LLM calls), preserving order."""
    out: list = [None] * len(items)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, it): i for i, it in enumerate(items)}
        for f in as_completed(futs):
            out[futs[f]] = f.result()
    return out


def run(domain: str, *, horizon: str = "long", channels: int = 10, per_channel: int = 3,
        top_k: int = 8, date: str | None = None, workers: int = 4, log=print) -> dict:
    date = date or _dt.date.today().isoformat()
    short = horizon.lower() in ("short", "near", "near-term")
    chans = (SHORT_CHANNELS if short else LONG_CHANNELS)[:channels]
    resolve_window = ("resolve in the next 3 to 18 months, with resolution dates between 2026-09-30 and 2027-12-31"
                      if short else "resolve 2030 to 2040")
    horizon_str = "next 3 to 18 months (through 2027)" if short else "2030 to 2040"
    obj = ("a SPECIFIC, dated, near-certain CATALYST or clearing imbalance that forces a repricing the "
           "market has NOT yet handicapped." if short
           else "a specific BINDING CONSTRAINT (the inelastic input), not a theme.")

    # ---- ground ONCE on the domain (deterministic; includes the live market anchor) -------------
    log(f"grounding the data layer on '{domain}' ...")
    gconn = db.connect()
    try:
        pack_text = ground.format_ground(ground.ground_pack(domain))
    finally:
        gconn.close()
    GROUND = ("Below is the MEASURED grounding pack from our worldwide data layer (dated, leak-free). "
              "Reason FROM it: anchor every number in a specific trend/fire it shows, walk the dependency "
              "edges to the inelastic input, and treat the MARKET ANCHOR as the priced-in gate. Do not "
              "free-associate around it; where a layer is a GAP, say whether that is your edge or your "
              "blind spot.\n\n" + pack_text)

    # ---- 1. GENERATE (10 channels) --------------------------------------------------------------
    log(f"Pope MEGA/DeepSeek [{'SHORT' if short else 'LONG'}] on: {domain} ({len(chans)} channels x {per_channel})")
    gen_sys = "You are a pre-consensus foresight miner. Output strict JSON only."

    def gen_prompt(key, lens):
        return (f"You are a {'near-term catalyst forecaster' if short else 'pre-consensus foresight miner'} "
                f"on the \"{key}\" channel. Target area: {domain}. Your lens: {lens}.\n\n{GROUND}\n\n"
                f"Generate {per_channel} of the most DISRUPTIVE, unaccounted-for, confident "
                f"{'short-horizon' if short else 'long-horizon'} calls through this lens. Each must {resolve_window}. "
                f"Be bold and non-obvious. Each must name {obj}\n"
                f"For each: 'needle' = the specific inelastic input or dated catalyst; 'metric' = a leading "
                f"indicator to track now; 'kill' = the falsifier; 'resolves' = resolution date (YYYY-MM-DD).\n"
                f"{STYLE}\n\n"
                'Return JSON: {"theses":[{"headline","boom","domain","structural","pre_consensus",'
                '"needle","metric","kill","resolves"}]}')

    def do_gen(ch):
        conn = db.connect()
        try:
            return _llm(conn, gen_prompt(*ch), gen_sys, max_tokens=8000)
        finally:
            conn.close()

    gen = _pool_map(do_gen, chans, workers)
    candidates = [t for g in gen if g and not g.get("_error") for t in (g.get("theses") or [])]
    log(f"generated {len(candidates)} candidates; gating + refuting")
    if not candidates:
        raise SystemExit("no candidates generated — check the DeepSeek key / model")

    # ---- 2. GATE + REFUTE (per candidate) -------------------------------------------------------
    gate_sys = "You are the adversarial gate of the Pope System. Be skeptical. Output strict JSON only."

    def gate_prompt(c):
        return (f"You are the adversarial gate for the Pope System{' (SHORT-horizon)' if short else ''}. "
                f"Candidate:\n{json.dumps(c, ensure_ascii=False)}\n\n{GROUND}\n\n"
                "Use the MARKET ANCHOR as the priced-in gate (a liquid market near your clause_p = PRICED: "
                "quote the gap or DEMOTE) and the SIGNALS + DEPENDENCY edges as the measured reality.\n"
                "1. PRE-CONSENSUS + PRICE CHANNEL: narrative-obscure is not unpriced. If already in spot "
                "prices / equity coverage / sell-side models / market odds, lean DEMOTE.\n"
                f"2. {'WINDOW: confirm it resolves in 3-18 months; if it can slip years, DEMOTE.' if short else 'SUPPLY ELASTICITY: confirm the input is genuinely inelastic; if elastic, DEMOTE.'}\n"
                "3. ADVERSARIAL REFUTE: actively try to prove it is wrong or already priced; if it survives, say precisely why.\n"
                "4. SCORE: vision_p = strength of the structural/catalyst case (can be high). clause_p = "
                "calibrated odds the EXACT dated clause resolves YES by its date (<= vision_p; near 50 is fine). Do not inflate.\n"
                "5. Tighten and echo all fields. PROMOTE only if pre-consensus, inelastic/in-window, and survives refute.\n"
                f"{STYLE}\n\n"
                'Return JSON: {"verdict":"PROMOTE|DEMOTE","vision_p":<0-100>,"clause_p":<0-100>,'
                '"price_channel","refute","headline","boom","domain","structural","pre_consensus",'
                '"needle","metric","kill","resolves","why"}')

    def do_gate(c):
        conn = db.connect()
        try:
            return _llm(conn, gate_prompt(c), gate_sys, max_tokens=8000)
        finally:
            conn.close()

    gated = _pool_map(do_gate, candidates, workers)
    promoted = [g for g in gated if g and not g.get("_error") and g.get("verdict") == "PROMOTE"]
    log(f"{len(promoted)}/{len(candidates)} promoted")
    # graceful fallback chain: promoted -> any non-error gated (even DEMOTE) -> raw candidates.
    # A board always renders; a thin gate never sinks the whole run.
    pool = promoted or [g for g in gated if g and not g.get("_error")] or candidates
    log(f"synthesis pool: {len(pool)} ({'promoted' if promoted else 'fallback'})")

    # ---- 3. SYNTHESIZE --------------------------------------------------------------------------
    # Synthesis only SELECTS + writes the cross-cutting read; it returns ids, not full theses, so a
    # reasoner can never truncate the echo. We reconstruct the calls in Python from the gated pool.
    log("synthesizing the board ...")
    for i, c in enumerate(pool):
        c["_cid"] = f"C{i}"
    digest = [{"_cid": c["_cid"], "headline": c.get("headline"), "domain": c.get("domain"),
               "needle": c.get("needle"), "vision_p": c.get("vision_p"), "clause_p": c.get("clause_p"),
               "why": c.get("why", "")[:240]} for c in pool]
    synth_sys = "You are the synthesis layer of the Pope System. Output strict JSON only."
    synth_prompt = (
        f"You are the synthesis layer of the Pope System ({'SHORT-horizon catalyst' if short else 'long-horizon structural'} board). "
        f"Target area: {domain}.\nGate survivors (each with a _cid):\n{json.dumps(digest, ensure_ascii=False)}\n\n"
        f"Select the strongest {top_k} by _cid (favor diverse mechanisms and the highest, most defensible edge; "
        f"drop near-duplicates), in descending conviction order. Write a one-paragraph cross-cutting synthesis "
        f"naming the loudest shared shift, a title, and an italic subtitle. List 2-4 borderline calls as runner_ups.\n"
        f"In all prose, refer to calls by their mechanism or by P1..P{top_k}, NEVER by their _cid.\n"
        f"{STYLE}\n\n"
        'Return JSON: {"title","subtitle","synthesis","selected":["C3","C7",...],'
        '"runner_ups":[{"seed","case","why_not"}]}')
    sconn = db.connect()
    try:
        spec = _llm(sconn, synth_prompt, synth_sys, max_tokens=6000)
    finally:
        sconn.close()
    if not spec or spec.get("_error"):
        raise SystemExit(f"synthesis failed: {spec}")
    by_cid = {c["_cid"]: c for c in pool}
    sel_ids = [s for s in (spec.get("selected") or []) if s in by_cid][:top_k]
    if not sel_ids:  # synth didn't pick cleanly — fall back to top of pool by clause_p
        pool_sorted = sorted(pool, key=lambda c: float(c.get("clause_p") or 0), reverse=True)
        sel_ids = [c["_cid"] for c in pool_sorted[:top_k]]
    selected = []
    for n, cid in enumerate(sel_ids, 1):
        t = {k: v for k, v in by_cid[cid].items() if k != "_cid"}
        t["id"] = f"P{n}"
        selected.append(t)

    # ---- 4. IMPLICATIONS / CAPTURE (per call) ---------------------------------------------------
    log(f"deriving implications for {len(selected)} calls ...")
    impl_sys = "You are the implications/capture layer of the Pope System. Output strict JSON only."

    def impl_prompt(t):
        return (
            "You are the implications layer of the Pope System. This call already survived the adversarial "
            "gate. Work out the real-world consequences IF it resolves true, at the same rigor as the call. "
            f"Assume the needle binds. Do NOT re-argue the call.\nCall:\n{json.dumps(t, ensure_ascii=False)}\n\n"
            "Derive, every item concrete and falsifiable:\n"
            "- exposed: the buyer/stakeholder who should care now (name the desk/function or asset owner).\n"
            "- action_now: the practical step to consider before the market or budget cycle catches up.\n"
            "- decision_changed: the concrete investment/procurement/capex/hedge/partnership/policy/research decision this alters.\n"
            "- roi_logic: why acting early is worth money or avoided loss (asymmetry, timing edge, cost of waiting).\n"
            "- rent_path: where value actually lands. Name real companies, assets, or regions, never 'the industry'.\n"
            "- winners and losers: 2-3 each, NAMED, each with the one-line mechanism.\n"
            "- reprices: the specific instrument/contract that moves and the direction; if nothing prices it cleanly, say so.\n"
            "- next_constraint: where the binding constraint moves one layer deeper once this one binds.\n"
            "- watch: the earliest observable, ideally dated, marker the cascade has started.\n"
            f"{STYLE}\n\n"
            'Return JSON: {"exposed","action_now","decision_changed","roi_logic","rent_path",'
            '"winners":[{"who","why"}],"losers":[{"who","why"}],"reprices","next_constraint","watch"}')

    def do_impl(t):
        conn = db.connect()
        try:
            return _llm(conn, impl_prompt(t), impl_sys, max_tokens=6000)
        finally:
            conn.close()

    impls = _pool_map(do_impl, selected, workers)

    # attach implications + a fresh per-needle priced-in check; normalise probabilities to strings
    theses = []
    for t, im in zip(selected, impls):
        t = dict(t)
        for k in ("vision_p", "clause_p"):
            if k in t and t[k] is not None:
                t[k] = str(int(round(float(t[k])))) if str(t[k]).replace(".", "", 1).isdigit() else str(t[k])
        if im and not im.get("_error"):
            t["implications"] = im
        try:  # nail the priced-in gate per call (keyless; never sink the board)
            anc = market.market_anchor(t.get("needle") or t.get("headline") or domain)
            t["market_check"] = {"verdict": anc.get("verdict"),
                                 "markets": [{"p": m.get("prob"), "q": m.get("question")} for m in anc.get("markets", [])[:3]]}
        except Exception:  # noqa: BLE001
            pass
        theses.append(t)

    return _scrub({
        "title": spec.get("title", domain.title()),
        "subtitle": spec.get("subtitle", ""),
        "domain": domain,
        "date": date,
        "horizon": horizon_str,
        "regime": "short" if short else "long",
        "run_mode": f"pope-mega-deepseek-{MODEL}",
        "synthesis": spec.get("synthesis", ""),
        "theses": theses,
        "runner_ups": spec.get("runner_ups", []),
    })


def _slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")[:60] or "board"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Pope MEGA on DeepSeek")
    ap.add_argument("--domain", required=True)
    ap.add_argument("--horizon", default="long")
    ap.add_argument("--channels", type=int, default=10)
    ap.add_argument("--per-channel", type=int, default=3)
    ap.add_argument("--top-k", type=int, default=8)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--slug", default=None)
    a = ap.parse_args(argv[1:])

    board = run(a.domain, horizon=a.horizon, channels=a.channels, per_channel=a.per_channel,
                top_k=a.top_k, workers=a.workers)
    slug = a.slug or _slug(board.get("title") or a.domain)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{slug}-{board['date']}.json"
    path.write_text(json.dumps(board, ensure_ascii=False, indent=2))
    print(f"\nwrote {path}  ({len(board['theses'])} calls, {len(board.get('runner_ups', []))} runner-ups)")
    print(f"next: uv run python -m engine.pope.render {path}  ->  publish_site  ->  cd site && pnpm ship")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
