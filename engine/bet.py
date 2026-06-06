"""Component 12 — the bet / decision translator. The last mile of Phase 5.

A consensus EDGE says *where the constraint is and that it's mispriced*. It is not yet a bet. This
module turns that into *what to do about it*: instrument(s) + sizing + horizon + triggers — a
sized, monitorable PAPER bet. It is the first time the system acts on a forecast.

Three disciplines shape every choice here:

  1. REFLEXIVITY / "right but early" (§0.5). The dominant failure of a correct constraint call is
     being early — the rent-capturing layer re-rates late, or the obvious champion gets bid up on
     sector beta first. So we express the bet through the most INELASTIC layer as a PAIR: LONG the
     droplet-partitioning consumable (TXG) HEDGED with a SHORT in the elastic sequencer (ILMN).
     The hedge strips out sequencing/sector beta so the position isolates the one thing we have an
     edge on — *constraint migration*, the relative re-rate of consumable vs sequencer.

  2. SIZE SMALL (capped fractional Kelly). The size falls out of the edge magnitude AND its
     uncertainty via a stdlib Monte-Carlo of the pair's relative re-rate, then a conservative
     Kelly fraction, then a HARD CAP. The cap binds on purpose: the edge is contested (see #3),
     and an uncapped Kelly on a contested, illiquid-tail thesis is how you blow up being right.

  3. CONDITIONAL on the open Decision (rule 4). The consensus gate already surfaced the honest
     fork: the market's refusal to pay up either is mispricing (our edge) OR is the market
     correctly pricing the moat dissolving (the forward card's own kill-criterion). We do NOT
     paper over it — the bet's central thesis IS that fork ("the consumable moat holds longer than
     the market fears"), and its FIRST kill-trigger is that Decision resolving the other way.

p_thesis (the chance the constraint is real) is pulled LIVE from the supply-graph propagation
(`graph.propagate` → P(bottleneck)), so the size is tied to the graph + forecast + consensus, not
a typed constant. Pure-ish: the only I/O is SQLite. No network, no LLM, $0 — reasoning is Claude's,
in-session; no data fetch ⇒ no cost-ledger row needed (rule 3 logs before a *fetch*).
"""

from __future__ import annotations

import json
import random
import sqlite3
from dataclasses import dataclass
from datetime import date

from engine import graph
from engine.schemas import BetCard, BetLeg, _now

CHAIN = "scrna_seq"

# --- sizing policy (conservative, capped) ------------------------------------
KELLY_FRACTION = 0.25      # quarter-Kelly: we bet a quarter of the growth-optimal fraction
SIZE_CAP = 0.03            # hard cap at 3% of risk capital — the edge is contested + illiquid-tail
MC_N = 200_000

# The miss scenario: if the market is right (moat dissolves via Parse/SPLiT-seq substitution), the
# consumable's slim premium DE-rates toward parity-and-below. A reference-class anchor, held wide.
R_MISS_CENTER = 0.85       # relative P/S the pair drifts to if the thesis is wrong (< 1 = de-rate)
R_MISS_LOG_SD = 0.20
# The hedge is imperfect (no clean keyless beta to neutralize precisely — a [?] gap): a TXG/ILMN
# pair still carries idiosyncratic slippage. Carried as multiplicative noise so it WIDENS σ and
# LOWERS Kelly — conservative, never flattering.
HEDGE_SLIPPAGE_SD = 0.12


@dataclass
class PairPayoff:
    """The distribution of the pair's relative re-rate return, summarized (MC outputs)."""

    ret_median: float
    ret_ci_low: float
    ret_ci_high: float
    p_win: float
    kelly_full: float        # uncapped growth-optimal fraction (surfaced, not hidden)
    kelly_ci_low: float      # Kelly under the pessimistic edge assumption
    kelly_ci_high: float     # Kelly under the optimistic edge assumption


def _percentile(sorted_vals: list[float], p: float) -> float:
    return sorted_vals[min(int(p * len(sorted_vals)), len(sorted_vals) - 1)]


def mc_pair_payoff(
    r_market: float,
    r_fair_center: float,
    r_fair_log_sd: float,
    p_bottleneck: float,
    *,
    seed: int = 12,
    n: int = MC_N,
) -> PairPayoff:
    """Monte-Carlo the LONG-consumable / SHORT-sequencer pair's relative return over the horizon.

    Each draw mixes two worlds, weighted by whether the constraint thesis holds:
      • THESIS HOLDS  (prob p_thesis, itself drawn ~ Beta around the graph's P(bottleneck) so the
        size carries the graph's uncertainty): the relative multiple re-rates from r_market toward
        the modeled fair premium r_fair (a lognormal draw). Pair return = r_target / r_market − 1.
      • THESIS WRONG  (market is right / moat dissolves): the multiple DE-rates toward R_MISS_CENTER.
    Imperfect-hedge slippage is layered on multiplicatively (widens σ). The return distribution,
    P(win), and Kelly all fall out of the samples — never typed (execution §3).
    """
    rng = random.Random(seed)
    # p_thesis ~ Beta centred on the live P(bottleneck), with a spread that reflects the OPEN
    # Decision's contestedness (κ≈14 → 80% CI roughly ±0.15 around the mean). Honest, not tuned.
    m = min(max(p_bottleneck, 0.05), 0.95)
    kappa = 14.0
    a, b = m * kappa, (1.0 - m) * kappa

    rets: list[float] = []
    wins = 0
    for _ in range(n):
        p_thesis = rng.betavariate(a, b)
        if rng.random() < p_thesis:
            r_target = r_fair_center * (2.718281828 ** rng.gauss(0.0, r_fair_log_sd))
        else:
            r_target = R_MISS_CENTER * (2.718281828 ** rng.gauss(0.0, R_MISS_LOG_SD))
        g = (r_target / r_market) - 1.0
        g = (1.0 + g) * rng.gauss(1.0, HEDGE_SLIPPAGE_SD) - 1.0  # imperfect hedge widens the tails
        rets.append(g)
        wins += g > 0
    rets.sort()

    mean = sum(rets) / n
    var = sum((g - mean) ** 2 for g in rets) / n
    kelly_full = mean / var if var > 0 else 0.0

    # Size band: Kelly is one number per distribution, so we report its sensitivity to the edge by
    # recomputing under the pessimistic (10th-pct re-rate) and optimistic (90th-pct) worlds —
    # value + unit + UNCERTAINTY, no naked size.
    lo, hi = _percentile(rets, 0.10), _percentile(rets, 0.90)
    kelly_lo = lo / var if var > 0 else 0.0
    kelly_hi = hi / var if var > 0 else 0.0
    return PairPayoff(
        ret_median=_percentile(rets, 0.50), ret_ci_low=lo, ret_ci_high=hi,
        p_win=wins / n, kelly_full=kelly_full,
        kelly_ci_low=max(kelly_lo, 0.0), kelly_ci_high=max(kelly_hi, 0.0),
    )


def _capped(fraction: float) -> float:
    """Quarter-Kelly, floored at 0, capped at SIZE_CAP — small because the edge is contested."""
    return max(0.0, min(KELLY_FRACTION * fraction, SIZE_CAP))


# --- the immutable write path (mirror forecast.py, rule 7) -------------------


def _insert(conn: sqlite3.Connection, card: BetCard) -> str:
    conn.execute(
        "INSERT INTO bets "
        "(id,chain,thesis,created_at,as_of,horizon_date,direction,legs,size_fraction,"
        " size_ci_low,size_ci_high,size_unit,kelly_full,kelly_fraction,size_cap,"
        " exp_return_median,exp_return_ci_low,exp_return_ci_high,p_win,"
        " entry_triggers,exit_triggers,kill_triggers,rationale,consensus_id,"
        " forecast_card_id,decision_id,source_ids,status,superseded_by) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            card.id, card.chain, card.thesis, card.created_at.isoformat(), card.as_of.isoformat(),
            card.horizon_date.isoformat(), card.direction,
            json.dumps([leg.model_dump() for leg in card.legs]),
            card.size_fraction, card.size_ci_low, card.size_ci_high, card.size_unit,
            card.kelly_full, card.kelly_fraction, card.size_cap,
            card.exp_return_median, card.exp_return_ci_low, card.exp_return_ci_high, card.p_win,
            json.dumps(card.entry_triggers), json.dumps(card.exit_triggers),
            json.dumps(card.kill_triggers), card.rationale, card.consensus_id,
            card.forecast_card_id, card.decision_id, json.dumps(card.source_ids),
            card.status, card.superseded_by,
        ),
    )
    conn.commit()
    return card.id


def create_bet(conn: sqlite3.Connection, **fields) -> BetCard:
    """Validate (≥1 leg, ≥1 kill-trigger) and write a new immutable paper bet."""
    card = BetCard(**fields)
    _insert(conn, card)
    return card


def supersede(conn: sqlite3.Connection, old_id: str, **fields) -> BetCard:
    """Replace a bet with a revised one — never edit the old (rule 7); it stays for the record."""
    row = conn.execute("SELECT id, superseded_by FROM bets WHERE id=?", (old_id,)).fetchone()
    if row is None:
        raise ValueError(f"no bet {old_id}")
    if row["superseded_by"]:
        raise ValueError(f"bet {old_id} is already superseded by {row['superseded_by']}")
    new = create_bet(conn, **fields)
    conn.execute("UPDATE bets SET superseded_by=? WHERE id=?", (new.id, old_id))
    conn.commit()
    return new


# --- the one entry point: translate the scRNA-seq edge into a bet ------------


def _live_consensus(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM consensus WHERE chain=? ORDER BY created_at DESC LIMIT 1", (CHAIN,)
    ).fetchone()


def _live_forward_card(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM forecast_cards WHERE superseded_by IS NULL AND outcome IS NULL "
        "ORDER BY created_at DESC LIMIT 1"
    ).fetchone()


def _open_consensus_decision(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM decisions WHERE status='open' AND prompt LIKE 'Consensus gate:%' "
        "ORDER BY created_at DESC LIMIT 1"
    ).fetchone()


def translate(conn: sqlite3.Connection, *, supersede_live: bool = False, log=print) -> BetCard | None:
    """Read the live edge + forecast + graph, size a paper pair-bet, write it immutable.

    Refuses (rule 4) if the consensus gate does NOT show an edge: there is nothing to bet on.
    Idempotent: if a live (non-superseded) bet for the chain already exists, leaves it unless
    `supersede_live` is set, in which case the old card is retained and a fresh one supersedes it.
    """
    c = _live_consensus(conn)
    if c is None:
        log("no consensus read yet — run consensus-score first. nothing written.")
        return None
    if c["verdict"] != "edge":
        log(f"consensus verdict is '{c['verdict']}', not 'edge' — no bet to translate "
            "(correct + priced = zero return). nothing written.")
        return None

    fwd = _live_forward_card(conn)
    decision = _open_consensus_decision(conn)

    existing = conn.execute(
        "SELECT id FROM bets WHERE chain=? AND superseded_by IS NULL", (CHAIN,)
    ).fetchone()
    if existing and not supersede_live:
        log(f"a live bet already exists ({existing['id']}). Use --supersede to revise it (rule 7).")
        return None

    # p_thesis from the LIVE supply-graph propagation (ties the size to the graph, not a constant).
    prop = graph.propagate(conn)
    p_bottleneck = prop.bottleneck.p_bottleneck
    gap_median = prop.gap_median

    payoff = mc_pair_payoff(
        r_market=c["r_market"], r_fair_center=c["r_fair"], r_fair_log_sd=0.22,
        p_bottleneck=p_bottleneck,
    )
    size = _capped(payoff.kelly_full)
    size_lo = _capped(payoff.kelly_ci_low)
    size_hi = _capped(payoff.kelly_ci_high)
    capped = KELLY_FRACTION * payoff.kelly_full > SIZE_CAP

    cons_sym, seq_sym = c["consumable_sym"], c["sequencer_sym"]
    horizon = date.fromisoformat(fwd["resolution_date"]) if fwd else date(2027, 6, 30)

    legs = [
        BetLeg(
            sym=cons_sym, role="consumable", side="long", weight=0.6,
            rationale=(
                "The inelastic, rent-capturing layer: 10x Genomics' droplet-partitioning consumables "
                "(Chromium/Xenium), IP-defended and the binding constraint in the graph "
                f"(P(bottleneck)={p_bottleneck:.0%}, supply gap {gap_median:.1f}×). Express the edge "
                "HERE, not in the obvious champion — the rent accrues to the constraint."
            ),
        ),
        BetLeg(
            sym=seq_sym, role="sequencer", side="short", weight=0.4,
            rationale=(
                "Hedge in the ELASTIC layer: Illumina's short-read sequencers commoditize (≥4 vendors, "
                "falling $/Gb). Shorting it strips sequencing/sector beta so the pair isolates the one "
                "thing we have an edge on — the relative re-rate of consumable vs sequencer. Precise "
                "beta-neutral hedge ratio is a [?] gap (no keyless beta secured); default ~1.5:1 dollar "
                "tilt to the long, refine when betas are sourced — NOT fabricated."
            ),
        ),
    ]

    who_captures = (
        f"WHO CAPTURES THE RENT: the consumable franchise ({cons_sym}) — IF its moat holds. TIMING "
        "RISK: 'right but early' is the dominant failure (§0.5) — the re-rate may lag the horizon, or "
        "substitutes (Parse/SPLiT-seq) may erode the moat before it is priced. The short-sequencer leg "
        "buys time by removing sector beta, but cannot hedge moat-erosion — that is the kill-trigger."
    )
    dec_note = (
        f"CONDITIONAL on the open consensus Decision ({decision['id']}): this bet only makes sense if "
        "the edge is REAL mispricing, not the market correctly pricing the moat dissolving. That fork "
        "IS the thesis; its resolution the wrong way is the first kill-trigger below."
        if decision else
        "NOTE: the consensus Decision is not open in this DB — the mispricing-vs-market-right fork "
        "should be carried as the bet's central risk regardless."
    )
    cap_note = (
        f"Quarter-Kelly on the modeled edge would imply {KELLY_FRACTION * payoff.kelly_full:.1%} of "
        f"risk capital; we HARD-CAP at {SIZE_CAP:.0%} because the edge is contested (open Decision) and "
        "'right but early' dominates — sizing up a contested thesis is how you blow up being right."
        if capped else
        f"Quarter-Kelly on the modeled edge sits under the {SIZE_CAP:.0%} cap; size as computed."
    )

    rationale = (
        f"BET TRANSLATION (component 12) of the scRNA-seq consensus EDGE. The gate found the market "
        f"prices the consumable at only r_market {c['r_market']:.2f}× the sequencer's P/S vs a modeled "
        f"fair ~{c['r_fair']:.1f}× → consensus delta +{c['delta_median']:.2f}× "
        f"[{c['delta_ci_low']:.2f},{c['delta_ci_high']:.2f}]. EXPRESSION: long {cons_sym} (inelastic "
        f"consumable) hedged short {seq_sym} (elastic sequencer) — a PAIR that isolates constraint "
        f"migration from sector beta (§0.5). PAYOFF (MC over the re-rate, p_thesis~Beta around the "
        f"graph's P(bottleneck)={p_bottleneck:.0%}): relative return median {payoff.ret_median:+.0%} "
        f"(80% CI [{payoff.ret_ci_low:+.0%},{payoff.ret_ci_high:+.0%}]), P(win) {payoff.p_win:.0%}. "
        f"SIZING: full Kelly {payoff.kelly_full:.2f} → ¼-Kelly capped → {size:.1%} of risk capital "
        f"(80% band [{size_lo:.1%},{size_hi:.1%}]). {cap_note} {who_captures} {dec_note}"
    )

    entry = [
        f"Consensus delta stays > threshold ({c['threshold']:.1f}×) AND graph P(bottleneck) > 50% on "
        "refresh — enter only while the edge is live and the constraint still binds.",
        f"Pair relative P/S ({cons_sym}÷{seq_sym}) still near r_market {c['r_market']:.2f}× — do NOT "
        "chase if it has already re-rated toward fair (the edge would be gone).",
    ]
    exit_ = [
        f"Pair relative P/S re-rates to ≥ ~{(c['r_market'] + c['r_fair']) / 2:.1f}× (delta compresses "
        "toward 0 → now priced in): edge captured, take profit.",
        f"Horizon reached ({horizon}) without re-rate: close and re-evaluate — 'right but early' "
        "should not be held indefinitely.",
    ]
    kill = [
        f"The open consensus Decision ({decision['id'] if decision else 'n/a'}) resolves to "
        "'market is right': a non-10x / open-source droplet-partitioning method (Parse/SPLiT-seq) "
        "takes dominant share of new scRNA-seq methods — moat dissolved, thesis dead.",
        "Graph P(bottleneck) for the partitioning consumable falls below 50% on refreshed supply "
        "data — the constraint moved; the bet's premise is falsified.",
        "Consensus delta compresses to ≤ 0 (r_market ≥ r_fair) — fully priced in, no edge left to "
        "harvest (and any further move is now sector beta, which we are hedging away).",
    ]

    src_ids = list(json.loads(c["source_ids"] or "[]"))
    if fwd:
        src_ids += list(json.loads(fwd["source_ids"] or "[]"))
    src_ids = list(dict.fromkeys(src_ids))  # dedupe, keep order

    thesis = (
        "The droplet-partitioning consumable moat holds longer than the market fears: the consumable "
        f"({cons_sym}) re-rates relative to the elastic sequencer ({seq_sym}) toward the modeled "
        f"~{c['r_fair']:.1f}× premium before substitutes erode it. [conditional on the mispricing fork]"
    )
    direction = f"long {cons_sym} / short {seq_sym} (pair) — express the edge in the inelastic layer"

    fields = dict(
        chain=CHAIN, thesis=thesis, as_of=date.fromisoformat(c["as_of"]), horizon_date=horizon,
        direction=direction, legs=legs,
        size_fraction=round(size, 4), size_ci_low=round(size_lo, 4), size_ci_high=round(size_hi, 4),
        kelly_full=round(payoff.kelly_full, 3), kelly_fraction=KELLY_FRACTION, size_cap=SIZE_CAP,
        exp_return_median=round(payoff.ret_median, 4), exp_return_ci_low=round(payoff.ret_ci_low, 4),
        exp_return_ci_high=round(payoff.ret_ci_high, 4), p_win=round(payoff.p_win, 3),
        entry_triggers=entry, exit_triggers=exit_, kill_triggers=kill, rationale=rationale,
        consensus_id=c["id"], forecast_card_id=fwd["id"] if fwd else None,
        decision_id=decision["id"] if decision else None, source_ids=src_ids, status="paper",
    )

    if existing and supersede_live:
        card = supersede(conn, existing["id"], **fields)
        log(f"superseded live bet {existing['id']} → {card.id} (old retained, rule 7).")
    else:
        card = create_bet(conn, **fields)
        log(f"created paper bet {card.id}.")

    log(f"\n  {direction}")
    log(f"  size {size:.1%} of risk capital  (¼-Kelly capped; 80% band [{size_lo:.1%},{size_hi:.1%}], "
        f"full Kelly {payoff.kelly_full:.2f})")
    log(f"  pair return median {payoff.ret_median:+.0%} [{payoff.ret_ci_low:+.0%},"
        f"{payoff.ret_ci_high:+.0%}]  P(win) {payoff.p_win:.0%}")
    log(f"  horizon {horizon}  ·  conditional on Decision {decision['id'] if decision else 'n/a'}")
    return card
