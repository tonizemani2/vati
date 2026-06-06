"""Component 7 — the consensus / pricing overlay. THE GATE.

The whole thesis hinges on one question: the constraint model (pillars 3-4) says the rent in the
single-cell RNA-seq chain migrates to the *droplet partitioning consumable* (inelastic, IP-defended)
and NOT to the *short-read sequencer* (elastic, competed). Fine — but is that already priced in?
A correct forecast that the market already holds returns nothing (execution §9, the "priced-in" killer).

So we measure what's priced in with a RELATIVE valuation, the cleanest free/keyless market signal:

    r_market = P/S(consumable layer)  ÷  P/S(sequencer layer)

i.e. what the market actually pays for a dollar of the consumable's revenue vs a dollar of the
sequencer's. If the market already believed the consumable is the scarce, rent-capturing layer it
would award it a premium (r_market ≫ 1). We compare that to what our constraint model says the
premium SHOULD be (`r_fair`, a reference-class anchor held deliberately wide — Bucket-2, not tuned).

    consensus_delta = r_fair − r_market

is the edge. It's a distribution, never a naked number (execution §3): we Monte-Carlo the uncertain
inputs (stdlib `random`, $0) → median + 80% CI + P(delta>0). The gate flags an edge only if the delta
robustly clears a threshold; a null/negative delta is a real result (the thesis is priced in), not a
failure — and when an edge IS found it is surfaced as a pivotal Decision, never buried (rule 4).

Public-company mapping (stated, not hidden):
  • consumable layer  →  10x Genomics (TXG): revenue is ~dominated by Chromium/Xenium consumables —
    the closest public pure-play for the droplet partitioning consumable in the graph.
  • sequencer layer   →  Illumina (ILMN): the elastic short-read sequencer + its reagents.
  • substitute layer  →  Parse Biosciences / Scale Bio are PRIVATE → no clean public ticker → left a
    [?] gap, NOT faked (the rising-substitute disconfirmer is already a kill-criterion on the card).

Data, all free/keyless, each fetch logged to the cost ledger BEFORE it runs (rule 3, $0 auto):
  • price       — Stooq last-quote CSV (keyless; daily-history is captcha-gated so we use the snapshot).
  • revenue +
    shares      — SEC XBRL companyconcept JSON (primary regulatory filings; keyless, UA header).
  short pos.   — FINRA reg-SHO daily short-volume CSV (keyless, cdn.finra.org): relative crowdedness leg.
Honestly-marked gaps still open [?] (NOT faked — paid/keyed): settlement short-interest %-of-float,
forward analyst estimates, options IV/skew. They are the next rung, mapped in execution §2 pillar 7.

Pure-ish: I/O is SQLite + two read-only HTTP GETs per ticker. Reasoning is Claude's, in-session.
"""

from __future__ import annotations

import csv
import io
import json
import random
import re
import sqlite3
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta

from engine import cost
from engine.schemas import ConsensusScore, Source, SourceKind, _now

MARKET_PILLAR = 7          # Market pricing — THE GATE
MC_N = 200_000
UA = "predictthefuture research (ruben.stout@edu.escp.eu)"


@dataclass
class ConsensusConfig:
    """Everything chain-specific about a priced-in gate. The gate ENGINE is chain-agnostic; only this
    differs between scRNA-seq and AI-power — the proof that the pipeline generalizes (one engine, +data).

    `consumable` = the inelastic, rent-capturing layer; `sequencer` = the elastic/obvious layer the
    market prices. r_market = P/S(consumable) ÷ P/S(sequencer). r_fair is the modeled fair relative
    premium (a wide reference-class anchor, never tuned). edge only if delta robustly clears threshold.
    """

    chain: str
    thesis: str
    consumable: dict           # {sym, cik, name} — inelastic layer
    sequencer: dict            # {sym, cik, name} — elastic/obvious layer
    r_fair_center: float
    r_fair_log_sd: float
    threshold: float
    decision_options: list[str]
    decision_rec: str
    edge_note: str             # the chain-specific honest twist appended to the Decision prompt
    confound_note: str = ""    # any modeling caveat surfaced in the rationale (not hidden)
    # redteam #5: a P/S LEVEL is not an EXPECTATION — a high multiple already prices growth/margin, so a
    # relative-P/S snapshot can read "cheap" exactly when the market has CORRECTLY priced the moat eroding.
    # Until a forward-estimates or short-interest leg lands, the gate is LOW-CONFIDENCE BY CONSTRUCTION:
    # we inject an extra "expectations-proxy" uncertainty on r_market (the level mis-measures the premium),
    # and a would-be EDGE is downgraded to `edge_low_conf` — a thin P/S snapshot can never alone flip a
    # card to a clean, bettable EDGE.
    expectations_leg: bool = False         # True once forward-estimates / short-interest is wired in
    expectations_proxy_log_sd: float = 0.30  # how badly a P/S level proxies the true expected premium


SCRNA_CFG = ConsensusConfig(
    chain="scrna_seq",
    thesis="scRNA-seq rent migrates to the droplet partitioning consumable",
    consumable={"sym": "TXG", "cik": 1770787, "name": "10x Genomics (Chromium/Xenium consumables)"},
    sequencer={"sym": "ILMN", "cik": 1110803, "name": "Illumina (short-read sequencer + reagents)"},
    # Bucket-2 anchor (held wide, not tuned): a razor-blade, IP-defended consumable that IS the binding
    # constraint earns ~1.5–3× the sales multiple of a competed, commoditizing instrument vendor.
    r_fair_center=2.0, r_fair_log_sd=0.22, threshold=0.5,
    decision_options=["Treat as real edge — proceed to bet translation (Phase 5 half 2)",
                      "Market is right — rent dissipating; downgrade the thesis",
                      "Inconclusive — collect short-interest / options IV to disambiguate the gap"],
    decision_rec=("Proceed, but sized small and hedged: the delta is robust, yet it overlaps our own "
                  "disconfirmer — so the bet's thesis is 'the consumable moat holds longer than the "
                  "market fears,' and its kill-criterion (substitute share) is the thing to watch."),
    edge_note=("BUT the market's refusal to pay up aligns with this card's OWN kill-criterion (rising "
               "substitutability via Parse/SPLiT-seq + PTAB). Is this real mispricing, or is the market "
               "correctly pricing the moat dissolving?"),
)

# AI-power: the inelastic layer is the electrical/grid-gear maker (GEV, GE Vernova), the obvious layer
# everyone prices is the GPU (NVDA). The honest modeling fork (surfaced, not faked): GEV (~20% margin
# industrial) and NVDA (~75% margin, hyper-growth) are NOT margin-comparable, so a simple relative-P/S
# r_fair is held DELIBERATELY conservative (well below parity) and wide — and the deepest edge (GOES
# steel, the queue itself) has no public pure-play, a [?] gap the gate names rather than fabricating.
AI_POWER_CFG = ConsensusConfig(
    chain="ai_power",
    thesis="AI-buildout rent migrates from the GPU to the electrical interconnect / transformers",
    consumable={"sym": "GEV", "cik": 1996810, "name": "GE Vernova (grid + power equipment)"},
    sequencer={"sym": "NVDA", "cik": 1045810, "name": "NVIDIA (AI accelerators — the obvious layer)"},
    # r_fair < 1: even if rent accrues to the binding electrical layer, NVDA's ~75% margins + growth
    # justify a higher P/S than a ~20%-margin industrial. So "fair" is the electrical layer trading at
    # ~0.45× the GPU's P/S (margin-adjusted, with a scarcity-premium nudge), held wide. Conservative.
    r_fair_center=0.45, r_fair_log_sd=0.30, threshold=0.20,
    decision_options=["Treat as real edge — the binding electrical layer is under-priced vs the GPU",
                      "Market is right — NVDA's premium is justified by margins; electrical fairly priced",
                      "Inconclusive — the obvious electrical play (GEV) is already re-rated; the pure "
                      "edge (GOES steel / the queue) has no public instrument [?]"],
    decision_rec=("Lean inconclusive→honest: GEV has ALREADY re-rated hugely on the AI-power narrative "
                  "(~7× sales, rich for an industrial), so the LIQUID edge is largely priced; the "
                  "residual pre-consensus edge sits in the deep layer (GOES electrical steel, the "
                  "interconnection queue) with no clean public pure-play — name it, do not fake a bet."),
    edge_note=("CAVEAT (not faked): GEV (~20% margin) and NVDA (~75% margin) are NOT margin-comparable, "
               "so part of NVDA's P/S premium is margins, not scarcity-mispricing. And the deepest "
               "constraint the graph found (GOES electrical steel) has no public pure-play. Is the "
               "electrical layer genuinely under-priced, or is the GPU premium margin-justified?"),
    confound_note=("Margin confound: NVDA's higher P/S partly reflects ~75% gross margins vs GEV's "
                   "~20%, not only scarcity — r_fair is held conservatively below parity for this. "
                   "Deepest edge (GOES steel / interconnection queue) has no public pure-play [?]."),
)


# --- the cost-gated, keyless fetchers ----------------------------------------


def _gated_get(conn: sqlite3.Connection, url: str, *, action: str, provider: str) -> str:
    """Log a $0 'auto' ledger row BEFORE the fetch (rule 3), then GET keyless. Returns text."""
    cost.gate(conn, action=action, provider=provider, units=1, est_cost_cents=0)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (keyless public endpoints)
        return r.read().decode("utf-8", "replace")


def fetch_price(conn: sqlite3.Connection, sym: str) -> tuple[float, date]:
    """Latest close + its date from Stooq's keyless last-quote CSV."""
    txt = _gated_get(conn, f"https://stooq.com/q/l/?s={sym.lower()}.us&f=sd2t2ohlcv&h&e=csv",
                     action=f"stooq_quote_{sym}", provider="stooq")
    row = next(csv.DictReader(io.StringIO(txt)))
    close = float(row["Close"])
    as_of = date.fromisoformat(row["Date"])
    if close <= 0:
        raise ValueError(f"stooq returned no usable close for {sym}: {row}")
    return close, as_of


# --- the OPTIONAL financial channel (physical-primary, financial-optional) --------------------
# A structural forecast scores on its constraint metric, never a stock. But when a named instrument
# exists, the market price is the SHARPEST priced-in signal — and the two misses that let momentum
# names (AXTI +2,268%, AMSC ~7x) pass as "pre-consensus" were here: the engine saw only today's close,
# never the multi-year run-up or absolute valuation. These helpers close that, kept OPTIONAL: a
# structural call with no clean instrument is still valid (just say so), never killed for lacking one.


def price_runup(conn: sqlite3.Connection, sym: str) -> dict:
    """Multi-year run-up from Stooq's keyless daily-history CSV: has the instrument already run?

    Returns trailing ~1y / ~3y total return + a `hot` flag (a >3x 3-year move = the structure is
    likely already bid up — the AXTI/AMSC tell). Stooq daily history is sometimes captcha-gated; on
    any failure we degrade to a flagged UNMEASURED read (never assert pre-consensus from a dead fetch).
    """
    try:
        txt = _gated_get(conn, f"https://stooq.com/q/d/l/?s={sym.lower()}.us&i=d",
                         action=f"stooq_hist_{sym}", provider="stooq")
        rows = [r for r in csv.DictReader(io.StringIO(txt)) if r.get("Close")]
        closes = [(date.fromisoformat(r["Date"]), float(r["Close"])) for r in rows if float(r["Close"]) > 0]
        if len(closes) < 30:
            raise ValueError("too few points")
    except Exception as e:  # noqa: BLE001 — captcha / blocked / empty → honest UNMEASURED
        return {"measured": False, "rationale": f"Stooq daily history unavailable ({str(e)[:40]}) — "
                "run-up UNMEASURED (not evidence of anything)."}
    closes.sort()
    last_d, last = closes[-1]
    def _ret(days: int) -> float | None:
        cutoff = last_d - timedelta(days=days)
        prior = [c for d, c in closes if d <= cutoff]
        return (last / prior[-1] - 1.0) if prior else None
    r1, r3 = _ret(365), _ret(365 * 3)
    hot = (r3 is not None and r3 >= 2.0) or (r1 is not None and r1 >= 1.5)
    parts = []
    if r1 is not None:
        parts.append(f"1y {r1:+.0%}")
    if r3 is not None:
        parts.append(f"3y {r3:+.0%}")
    return {"measured": True, "hot": hot, "ret_1y": r1, "ret_3y": r3, "last": last,
            "rationale": f"{sym.upper()} {' · '.join(parts) or 'flat'} → "
                         + ("HOT: already run hard, the structure is likely bid up (priced)"
                            if hot else "no extreme run-up on the price channel")}


def _xbrl_concept(conn: sqlite3.Connection, cik: int, taxonomy: str, tag: str, unit: str) -> list[dict]:
    """Return the unit rows for a company concept, or [] if the tag/unit is absent (404/missing)."""
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/{taxonomy}/{tag}.json"
    try:
        data = json.loads(_gated_get(conn, url, action=f"sec_{tag}_{cik}", provider="sec_edgar"))
    except Exception:  # noqa: BLE001 — a missing tag is a normal "try the next one" case
        return []
    return data.get("units", {}).get(unit, [])


# Revenue lives under different tags across filers (and NVDA's late-January fiscal year does NOT
# tag clean `CYxxxx` full-year frames). So we try several tags and accept a full-year row if it
# either carries a `CYxxxx` frame OR is a 10-K covering ~one year — then take the latest end date.
_REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
)


def _is_full_year(r: dict) -> bool:
    if re.fullmatch(r"CY\d{4}", str(r.get("frame", ""))):
        return True
    try:
        start = date.fromisoformat(r["start"])
        end = date.fromisoformat(r["end"])
    except (KeyError, ValueError):
        return False
    return r.get("form") == "10-K" and 350 <= (end - start).days <= 380


def fetch_revenue_fy(conn: sqlite3.Connection, cik: int) -> tuple[float, str]:
    """Latest full-year revenue (USD) from SEC XBRL — robust to tag choice + non-calendar fiscal years."""
    candidates: list[dict] = []
    for tag in _REVENUE_TAGS:
        candidates += [r for r in _xbrl_concept(conn, cik, "us-gaap", tag, "USD") if _is_full_year(r)]
    if not candidates:
        raise ValueError(f"no full-year revenue row for CIK {cik}")
    latest = max(candidates, key=lambda r: r["end"])
    return float(latest["val"]), latest["end"]


def fetch_shares(conn: sqlite3.Connection, cik: int) -> tuple[float, str]:
    """Latest cover-page shares outstanding (count) from the newest 10-K."""
    rows = _xbrl_concept(conn, cik, "us-gaap", "CommonStockSharesOutstanding", "shares")
    tenk = [r for r in rows if r.get("form") == "10-K"] or rows
    latest = max(tenk, key=lambda r: r["end"])
    return float(latest["val"]), latest["end"]


# --- the price/sales of one layer --------------------------------------------


@dataclass
class Layer:
    sym: str
    name: str
    price: float
    price_date: date
    shares: float
    revenue: float
    rev_period: str

    @property
    def market_cap(self) -> float:
        return self.price * self.shares

    @property
    def ps(self) -> float:
        return self.market_cap / self.revenue


def read_layer(conn: sqlite3.Connection, player: dict) -> Layer:
    price, pdate = fetch_price(conn, player["sym"])
    shares, _ = fetch_shares(conn, player["cik"])
    revenue, rev_period = fetch_revenue_fy(conn, player["cik"])
    return Layer(sym=player["sym"], name=player["name"], price=price, price_date=pdate,
                 shares=shares, revenue=revenue, rev_period=rev_period)


# --- the Monte-Carlo consensus delta -----------------------------------------


@dataclass
class Delta:
    median: float
    ci_low: float
    ci_high: float
    p_positive: float
    p_over_threshold: float


def mc_delta(consumable: Layer, sequencer: Layer, *, r_fair_center: float, r_fair_log_sd: float,
             threshold: float, expectations_proxy_log_sd: float = 0.0, seed: int = 7,
             n: int = MC_N) -> Delta:
    """Propagate the input uncertainty into the consensus delta = r_fair − r_market.

    Each draw perturbs price (4% 1σ — a single-session close on a volatile name), revenue (5% 1σ —
    drift since the last full-year filing) and shares (2% 1σ — dilution/buyback), forms each layer's
    P/S and their ratio r_market, draws r_fair from its wide reference-class band, and subtracts.
    The delta's interval falls out of the sampling — never typed (execution §3).

    `expectations_proxy_log_sd` (redteam #5) adds a log-normal factor to r_market modelling the fact
    that a P/S LEVEL is a noisy proxy for the market's true expected premium (growth + margin are
    already in the multiple). It widens the band so a thin snapshot cannot robustly clear the edge bar.
    """
    rng = random.Random(seed)
    out: list[float] = []
    pos = over = 0
    for _ in range(n):
        def ps(layer: Layer) -> float:
            price = layer.price * rng.gauss(1.0, 0.04)
            shares = layer.shares * rng.gauss(1.0, 0.02)
            rev = layer.revenue * rng.gauss(1.0, 0.05)
            return (price * shares) / max(rev, 1.0)
        # the expectations-proxy factor: the level mis-measures the true premium (redteam #5)
        proxy = 2.718281828 ** rng.gauss(0.0, expectations_proxy_log_sd) if expectations_proxy_log_sd else 1.0
        r_market = (ps(consumable) / ps(sequencer)) * proxy
        r_fair = r_fair_center * (2.718281828 ** rng.gauss(0.0, r_fair_log_sd))
        d = r_fair - r_market
        out.append(d)
        pos += d > 0
        over += d > threshold
    out.sort()
    pct = lambda p: out[int(p * len(out))]
    return Delta(median=pct(0.50), ci_low=pct(0.10), ci_high=pct(0.90),
                 p_positive=pos / n, p_over_threshold=over / n)


# --- keyless expectations leg: 10-K supply-constraint language (component 7) ---
# redteam #5 found a P/S LEVEL is not an EXPECTATION, and capped the verdict at edge_low_conf behind a
# FLAT expectations-proxy σ (a guess). This grounds that σ in a real keyless signal: how often each
# layer's OWN 10-Ks flag a binding supply constraint (backlog / capacity / shortage / lead-time
# language). If the INELASTIC layer flags constraints materially more than the ELASTIC one, the
# disclosed reality CORROBORATES that the rent layer is genuinely supply-bound (the premium a P/S level
# may under-price) → the band tightens. It is a weak corroborator, NOT a forward estimate: it grounds
# the σ and is shown, but full confidence (EDGE) still waits on a PAID positioning/estimates leg.
# Active-voice BINDING-constraint phrases (not boilerplate: a broad "backlog OR capacity" saturates —
# nearly every 10-K mentions those once in risk factors). These target a company actually flagging it
# could not / cannot meet demand. Denominator is the same EFTS window (q='"fiscal year"' ≈ every 10-K),
# so numerator and denominator are measured the SAME way (the earlier submissions-vs-EFTS window mismatch
# made every density read 1.0 — fixed).
_CONSTRAINT_Q = '"unable to meet" OR "capacity constraints" OR "supply constraints" OR "constrained our ability"'
_ALL10K_Q = '"fiscal year"'
_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"


def _http_json(url: str, *, retries: int = 2) -> dict | None:
    """Keyless GET → JSON, with polite back-off; None on any failure (SEC 500/403/rate-limit)."""
    import time
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return json.loads(urllib.request.urlopen(req, timeout=30).read())  # noqa: S310 keyless
        except Exception:  # noqa: BLE001 — back off, retry, then give up gracefully
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            return None


def _efts_count(query: str, cik: int) -> int | None:
    import urllib.parse
    res = _http_json(f"{_EFTS_URL}?q={urllib.parse.quote(query)}&forms=10-K&ciks={cik:010d}")
    return None if res is None else int(res.get("hits", {}).get("total", {}).get("value", 0))


def constraint_language_signal(conn: sqlite3.Connection, cik: int | None) -> dict | None:
    """Fraction of a filer's 10-Ks that flag a BINDING supply constraint. None if EDGAR is unreachable.

    Both numerator and denominator via EDGAR full-text search over the same 10-K window (denominator =
    10-Ks containing '"fiscal year"' ≈ all of them), so the ratio is internally consistent. Keyless, $0."""
    if not cik:
        return None
    n_total = _efts_count(_ALL10K_Q, cik)
    if not n_total:
        return None
    n_constraint = _efts_count(_CONSTRAINT_Q, cik)
    if n_constraint is None:
        return None
    n_constraint = min(n_constraint, n_total)
    return {"density": n_constraint / n_total, "n_constraint": n_constraint, "n_total": n_total}


def expectations_language_leg(conn: sqlite3.Connection, consumable_cik: int | None,
                              sequencer_cik: int | None, *, base_sd: float, log=print) -> tuple[float, bool, str]:
    """Ground the expectations-proxy σ in 10-K constraint language. Returns (proxy_sd, confident, note).

    If the inelastic (consumable) layer flags supply constraints materially more than the elastic
    (sequencer) layer, the disclosed reality corroborates the premium → tighten the band. `confident`
    stays False (full EDGE still needs the PAID leg — disclosure language is a weak corroborator,
    redteam #5 honesty). On any fetch failure, falls back to (base_sd, False, '') — flat proxy, unchanged.
    """
    c = constraint_language_signal(conn, consumable_cik)
    s = constraint_language_signal(conn, sequencer_cik)
    if not c or not s:
        return base_sd, False, " (10-K constraint-language leg: EDGAR unreachable this run — flat proxy σ kept.)"
    corroborated = c["density"] >= s["density"] + 0.20   # inelastic flags constraints ≥20pp more often
    sd = round(base_sd * 0.6, 3) if corroborated else base_sd
    note = (
        f" 10-K CONSTRAINT-LANGUAGE LEG (keyless, $0): the inelastic layer flags supply constraints in "
        f"{c['n_constraint']}/{c['n_total']} 10-Ks ({c['density']:.0%}) vs {s['n_constraint']}/{s['n_total']} "
        f"({s['density']:.0%}) for the elastic layer — "
        + (f"CORROBORATES the constraint premium → band tightened (expectations-proxy σ {base_sd:.2f}→{sd:.2f}). "
           "Still edge_low_conf: disclosure language is a weak corroborator, not a forward estimate."
           if corroborated else
           "does NOT clearly out-flag the elastic layer → no corroboration; flat proxy σ kept.")
    )
    return sd, False, note


# --- keyless expectations leg #2: FINRA short-volume positioning (component 7) ----------------
# The redteam #5 note names "forward-estimates OR short-interest" as the two legs that ground the
# flat proxy σ. This is the short-side, keyless: FINRA publishes the consolidated reg-SHO DAILY
# short-volume file (ShortVolume/TotalVolume per symbol) keyless at cdn.finra.org. Averaged over the
# last few trading days it is a crowdedness read — IS the market already positioned against this layer?
# Honest scope: short VOLUME (daily, includes market-maker hedging) is a PROXY for short INTEREST (the
# settlement %-of-float figure, biweekly, behind a key) — noisier and not a forward estimate. So it
# grounds the σ in real positioning but does NOT flip `confident` to True (full EDGE still waits on the
# settlement short-interest / forward-estimates leg). Reading: if the INELASTIC (rent-capturing) layer
# is crowded SHORT relative to the elastic one, the market is actively betting the moat fails → that
# leans AGAINST our under-pricing edge → widen the band. If it is LESS shorted, positioning isn't
# crowded against the thesis → mild corroboration → tighten.
_REGSHO_URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{ymd}.txt"


def short_volume_ratio(conn: sqlite3.Connection, sym: str, *, want_days: int = 5,
                       max_lookback: int = 21) -> float | None:
    """Mean daily short-volume ratio (ShortVolume/TotalVolume) over the last few FINRA trading days.

    Keyless, $0 (each daily file is cost-gated before the fetch). Walks back from today, skipping
    weekends and any missing/holiday file, until it has `want_days` good observations or exhausts
    `max_lookback` calendar days. Returns None if FINRA is unreachable / the symbol never appears.
    """
    from datetime import timedelta

    ratios: list[float] = []
    d = date.today()
    sym_u = sym.upper()
    for _ in range(max_lookback):
        if len(ratios) >= want_days:
            break
        d -= timedelta(days=1)
        if d.weekday() >= 5:  # Sat/Sun — no file
            continue
        ymd = d.strftime("%Y%m%d")
        try:
            txt = _gated_get(conn, _REGSHO_URL.format(ymd=ymd),
                             action=f"finra_regsho_{ymd}", provider="finra")
        except Exception:  # noqa: BLE001 — missing file (holiday/not-yet-posted) → try the prior day
            continue
        for line in txt.splitlines():
            parts = line.split("|")
            if len(parts) >= 5 and parts[1] == sym_u:
                try:
                    short_v, total_v = float(parts[2]), float(parts[4])
                except ValueError:
                    break
                if total_v > 0:
                    ratios.append(short_v / total_v)
                break
    if not ratios:
        return None
    return sum(ratios) / len(ratios)


def short_pressure_leg(conn: sqlite3.Connection, consumable_sym: str, sequencer_sym: str, *,
                       proxy_sd: float, log=print) -> tuple[float, str]:
    """Adjust the expectations-proxy σ by relative short crowdedness. Returns (proxy_sd, note).

    Compares the inelastic layer's short-volume ratio to the elastic layer's. A materially MORE-shorted
    inelastic layer (≥5pp) = the crowd betting against the very moat our edge rests on → widen σ (×1.25).
    A materially LESS-shorted one = positioning not against the thesis → tighten σ (×0.8). On any FINRA
    failure, returns proxy_sd unchanged with an honest 'unreachable' note. Never flips confidence."""
    c = short_volume_ratio(conn, consumable_sym)
    s = short_volume_ratio(conn, sequencer_sym)
    if c is None or s is None:
        return proxy_sd, (" FINRA SHORT-VOLUME LEG: reg-SHO file unreachable this run — proxy σ unchanged.")
    gap = c - s
    if gap >= 0.05:
        sd, lean = round(proxy_sd * 1.25, 3), "WIDENS"
        verdict = ("the inelastic layer is more crowded-short than the elastic one → the market is "
                   "actively positioned AGAINST this moat → band widened")
    elif gap <= -0.05:
        sd, lean = round(proxy_sd * 0.80, 3), "tightens"
        verdict = ("the inelastic layer is LESS shorted than the elastic one → positioning is not "
                   "crowded against the thesis → band tightened")
    else:
        sd, lean = proxy_sd, "≈neutral"
        verdict = "short crowdedness is comparable across the two layers → no adjustment"
    note = (
        f" FINRA SHORT-VOLUME LEG (keyless daily reg-SHO, $0): {consumable_sym} short-vol ratio "
        f"{c:.0%} vs {sequencer_sym} {s:.0%} (Δ {gap:+.0%}) → {verdict} (proxy σ {proxy_sd:.2f}→{sd:.2f}, "
        f"{lean}). Caveat: daily short VOLUME proxies settlement short INTEREST (noisier, MM hedging "
        f"included) — grounds σ but does not flip to a confident EDGE."
    )
    return sd, note


def verdict_of(delta: Delta, threshold: float, *, confident: bool = True) -> str:
    """edge | edge_low_conf | priced_in | inconclusive — the gate's honest outcomes.

    `confident=False` (redteam #5: no forward-expectations / short-interest leg yet) downgrades a
    would-be EDGE to `edge_low_conf` — a thin P/S snapshot can never alone flip a card to a bettable
    EDGE. The priced_in / inconclusive verdicts are unchanged (a thin read that says 'already priced'
    or 'no gap' is still honest information)."""
    if delta.median > threshold and delta.ci_low > 0:
        return "edge" if confident else "edge_low_conf"
    if delta.ci_high < 0:
        return "priced_in"            # market prices MORE premium than the model → already in (or over)
    return "inconclusive"             # the band straddles / sits below the edge bar


# --- persistence (Sources are GIGO-gated) ------------------------------------


def _market_sources(conn: sqlite3.Connection, consumable: Layer, sequencer: Layer) -> list[str]:
    """Record the two keyless market-signal Sources with stated trust rationales (rule 1)."""
    specs = [
        {"url": "https://stooq.com/q/l/?s=txg.us",
         "title": f"Stooq last-quote close — {consumable.sym} ${consumable.price:.2f} & "
                  f"{sequencer.sym} ${sequencer.price:.2f} (as-of {consumable.price_date})",
         "kind": SourceKind.news, "trust": 70,
         "rationale": "Keyless market-data redistributor (point-in-time daily close). Mid trust: a "
                      "redistributor, not the exchange tape, but its closes are widely cross-validated; "
                      "single-session snapshot, so a 4% 1σ is carried into the Monte-Carlo."},
        {"url": "https://data.sec.gov/api/xbrl/companyconcept/",
         "title": f"SEC XBRL company facts — revenue & shares ({consumable.sym} FY{consumable.rev_period[:4]}, "
                  f"{sequencer.sym} FY{sequencer.rev_period[:4]})",
         "kind": SourceKind.filing, "trust": 92,
         "rationale": "Primary regulatory filings (audited 10-K financials via SEC's structured XBRL "
                      "API, keyless). High trust: the authoritative origin for revenue and share count; "
                      "TTM drift since the last full-year filing carried as a 5% 1σ."},
    ]
    ids: list[str] = []
    for s in specs:
        row = conn.execute("SELECT id FROM sources WHERE url=?", (s["url"],)).fetchone()
        if row:
            conn.execute("UPDATE sources SET title=?, trust_score=?, trust_rationale=?, accessed_at=? "
                         "WHERE id=?", (s["title"], s["trust"], s["rationale"],
                                        _now().isoformat(), row["id"]))
            ids.append(row["id"])
            continue
        obj = Source(url=s["url"], title=s["title"], pillar_id=MARKET_PILLAR, kind=s["kind"],
                     trust_score=s["trust"], trust_rationale=s["rationale"])
        conn.execute(
            "INSERT INTO sources (id,url,title,pillar_id,kind,trust_score,trust_rationale,"
            "recency,accessed_at,cost_cents,content_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (obj.id, obj.url, obj.title, obj.pillar_id, obj.kind.value, obj.trust_score,
             obj.trust_rationale, None, obj.accessed_at.isoformat(), 0, None),
        )
        ids.append(obj.id)
    return ids


def _save(conn: sqlite3.Connection, score: ConsensusScore) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO consensus "
        "(id,chain,thesis,as_of,consumable_sym,sequencer_sym,ps_consumable,ps_sequencer,"
        " r_market,r_fair,delta_median,delta_ci_low,delta_ci_high,delta_unit,p_positive,"
        " threshold,verdict,rationale,source_ids,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (score.id, score.chain, score.thesis, score.as_of.isoformat(), score.consumable_sym,
         score.sequencer_sym, score.ps_consumable, score.ps_sequencer, score.r_market, score.r_fair,
         score.delta_median, score.delta_ci_low, score.delta_ci_high, score.delta_unit,
         score.p_positive, score.threshold, score.verdict, score.rationale,
         json.dumps(score.source_ids), score.created_at.isoformat()),
    )
    conn.commit()


# --- the pivotal Decision (rule 4 — never bury an edge) ----------------------


def _surface_decision(conn: sqlite3.Connection, score: ConsensusScore, cfg: ConsensusConfig) -> str | None:
    """Raise the interpretive fork — is the gap real mispricing, or is the market right? The honest
    twist (cfg.edge_note) is chain-specific; the fork itself is always the central thesis (rule 4)."""
    from engine.schemas import Decision

    prompt = (
        f"Consensus gate: {score.verdict.upper()} on the {cfg.chain} thesis. The market prices the "
        f"inelastic layer ({score.consumable_sym}) at r_market {score.r_market:.2f}× the obvious "
        f"layer's ({score.sequencer_sym}) P/S, vs a modeled fair ~{score.r_fair:.2f}× → consensus "
        f"delta {score.delta_median:+.2f}× [{score.delta_ci_low:.2f},{score.delta_ci_high:.2f}] "
        f"(P(delta>0)={score.p_positive:.0%}). {cfg.edge_note}"
    )
    existing = conn.execute("SELECT id FROM decisions WHERE prompt=? AND status='open'",
                            (prompt,)).fetchone()
    if existing:
        return existing["id"]
    d = Decision(prompt=prompt, options=cfg.decision_options, recommendation=cfg.decision_rec,
                 blocks=f"bet translation on the {cfg.chain} thesis")
    conn.execute(
        "INSERT INTO decisions (id,created_at,prompt,options,recommendation,context_source_ids,"
        "status,chosen_option,decided_at,blocks) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (d.id, d.created_at.isoformat(), d.prompt, json.dumps(cfg.decision_options), d.recommendation,
         json.dumps(score.source_ids), d.status.value, None, None, d.blocks),
    )
    conn.commit()
    return d.id


# --- the one entry point -----------------------------------------------------


def score_consensus(conn: sqlite3.Connection, *, cfg: ConsensusConfig = SCRNA_CFG, log=print) -> ConsensusScore:
    """Read the market, compute the consensus delta, gate it, persist, surface the fork. Chain-agnostic."""
    # Opening pillar 7 (the gate) → mark it in_progress (strict-layering visibility, rule 2).
    conn.execute("UPDATE pillars SET status='in_progress' WHERE id=? AND status='untapped'",
                 (MARKET_PILLAR,))
    conn.commit()

    consumable = read_layer(conn, cfg.consumable)
    sequencer = read_layer(conn, cfg.sequencer)
    log(f"  {consumable.sym}: ${consumable.price:.2f} × {consumable.shares/1e6:.1f}M sh ÷ "
        f"${consumable.revenue/1e6:.0f}M rev → P/S {consumable.ps:.2f}")
    log(f"  {sequencer.sym}: ${sequencer.price:.2f} × {sequencer.shares/1e6:.1f}M sh ÷ "
        f"${sequencer.revenue/1e6:.0f}M rev → P/S {sequencer.ps:.2f}")

    r_market = consumable.ps / sequencer.ps
    # redteam #5: with no forward-expectations/short-interest leg, the P/S snapshot is a noisy proxy for
    # the true expected premium → widen the band and cap the verdict at low-confidence. Phase 3 (2026-
    # 06-04): GROUND that flat proxy σ in a keyless 10-K constraint-language read — when the inelastic
    # layer out-discloses the elastic one on supply-constraint language, the band tightens (the disclosed
    # reality corroborates the premium); confident still needs the PAID leg, so the cap holds.
    lang_note = short_note = ""
    if cfg.expectations_leg:
        proxy_sd, confident = 0.0, True
    else:
        proxy_sd, confident, lang_note = expectations_language_leg(
            conn, cfg.consumable.get("cik"), cfg.sequencer.get("cik"),
            base_sd=cfg.expectations_proxy_log_sd, log=log)
        # second keyless leg: relative short crowdedness (FINRA reg-SHO daily) further grounds σ.
        proxy_sd, short_note = short_pressure_leg(
            conn, cfg.consumable["sym"], cfg.sequencer["sym"], proxy_sd=proxy_sd, log=log)
    delta = mc_delta(consumable, sequencer, r_fair_center=cfg.r_fair_center,
                     r_fair_log_sd=cfg.r_fair_log_sd, threshold=cfg.threshold,
                     expectations_proxy_log_sd=proxy_sd)
    verdict = verdict_of(delta, cfg.threshold, confident=confident)
    src_ids = _market_sources(conn, consumable, sequencer)

    conf_note = (
        "" if cfg.expectations_leg else
        " LOW-CONFIDENCE BY CONSTRUCTION (redteam #5): this rests on a P/S *level*, not an *expectation* "
        "— a high multiple already prices growth/margin, so relative P/S can read 'cheap' precisely when "
        "the market has correctly priced the moat eroding. The band carries an extra expectations-proxy "
        f"σ (log {cfg.expectations_proxy_log_sd:.2f}) and a would-be EDGE is capped at edge_low_conf "
        "until a forward-estimates or short-interest leg lands. A thin snapshot never alone flips a bet."
    )
    rationale = (
        f"PRICED-IN GATE (pillar 7), chain '{cfg.chain}'. Relative valuation: the market pays P/S "
        f"{consumable.ps:.2f} for the inelastic rent-capturing layer ({consumable.sym}) vs "
        f"{sequencer.ps:.2f} for the obvious layer ({sequencer.sym}) → r_market {r_market:.2f}×. The "
        f"model's reference-class fair relative premium is ~{cfg.r_fair_center:.2f}× (held wide, "
        f"Bucket-2). CONSENSUS DELTA = r_fair − r_market = {delta.median:+.2f}× (80% CI "
        f"[{delta.ci_low:.2f},{delta.ci_high:.2f}], P(delta>0)={delta.p_positive:.0%}), vs edge "
        f"threshold {cfg.threshold:.2f}× → {verdict.upper()}.{conf_note}{lang_note}{short_note} "
        + (cfg.confound_note or
           "Remaining gaps not faked [?] (paid Decisions): settlement short-interest %-of-float, "
           "forward analyst estimates, options IV/skew.")
    )

    score = ConsensusScore(
        chain=cfg.chain, thesis=cfg.thesis,
        as_of=consumable.price_date, consumable_sym=consumable.sym, sequencer_sym=sequencer.sym,
        ps_consumable=round(consumable.ps, 3), ps_sequencer=round(sequencer.ps, 3),
        r_market=round(r_market, 3), r_fair=cfg.r_fair_center,
        delta_median=round(delta.median, 3), delta_ci_low=round(delta.ci_low, 3),
        delta_ci_high=round(delta.ci_high, 3), p_positive=round(delta.p_positive, 3),
        threshold=cfg.threshold, verdict=verdict, rationale=rationale, source_ids=src_ids,
    )
    _save(conn, score)

    log(f"\nr_market {r_market:.2f}×  vs  r_fair {cfg.r_fair_center:.2f}×  →  consensus delta "
        f"{delta.median:+.2f}× [{delta.ci_low:.2f},{delta.ci_high:.2f}]  ({score.delta_unit})")
    log(f"verdict: {verdict.upper()}  (threshold {cfg.threshold:.2f}×, P(delta>0)={delta.p_positive:.0%})")
    if verdict in ("edge", "edge_low_conf", "inconclusive"):
        did = _surface_decision(conn, score, cfg)
        log(f"→ {verdict.upper()} is pivotal: opened Decision {did} (is it mispricing, or is the market right?).")
    return score
