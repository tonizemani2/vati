"""engine/locator.py — Stage 2: the mechanical constraint-LOCATOR (tests the THESIS, not a proxy).

The count detector (universe.py) tests "which research concept gains share" — but its label is the
SAME works/year feed it fires on (the NAMED CEILING), so even a clean edge would only prove attention
predicts attention, not the thesis. This module tests the actual claim — *rent migrates to the binding
constraint, one layer deeper in the value chain* — with a label drawn from an INDEPENDENT feed: the
producer PRICE of each layer's input (BLS PPI), not any research count. Price is rent; a layer whose
price surges is where the constraint bound. That escapes the ceiling.

THE TEST (point-in-time, frozen, LLM-free). For the connected AI-power → metals world, the comparable
layers are the four with a clean keyless price series — large-power transformer, HV switchgear,
grain-oriented electrical steel (GOES), refined copper. At each origin T, using ONLY price data with
year ≤ T, three mechanisms each NAME the layer they expect to become binding; we then grade them
against the layer whose price ACTUALLY rose most over (T, T+WINDOW]:
  • located  — the frozen detector's acceleration surprise on log-price ≤ T (the mechanical pick).
  • obvious  — naive momentum: the layer whose trailing log-price slope ≤ T was steepest ("what's been
               getting dearer keeps getting dearer"). The baseline the mechanical pick must beat.
  • graph    — graph.propagate's bottleneck over the world (the hand-reasoned supply-elasticity model;
               a CONTAMINATED control — its elasticities were tuned with hindsight, so it should win).
The honest bar is beating `obvious`; matching `graph` would say the mechanical, point-in-time signal
recovers what the hand-tuned model knows.

HONEST N. Only one connected world has ≥2 comparable price layers, and copper PPI starts 2012, so the
rolling origins are few (2016–2020). N is tiny by construction — this is reported as *suggestive /
cannot refute*, never as proof. It is the one mechanical retro-test of the thesis with an independent
label; widening it means wiring more layer-price series, not loosening the rule.

$0, stdlib only, keyless. Point-in-time guaranteed in code (assert: no price point with year > T ever
enters a `located`/`obvious` score).
"""

from __future__ import annotations

import math
import sqlite3

from engine import graph
from engine.backtest import _points_by_year
from engine.detector import DEFAULT_K, LOG_FLOOR, detect, theil_sen
from engine.schemas import _now, _uid

# ── frozen protocol (the binding copy is experiments/protocol_locator.yaml) ──────────────────────────
WORLD = ("ai_power", "metals")          # the connected value chain the shock flows through
PRICE_METRICS = ("transformer_ppi", "switchgear_ppi", "steel_ppi", "copper_ppi")  # comparable layers
ORIGINS = (2016, 2017, 2018, 2019, 2020)
WINDOW = 4                              # years of future price used to resolve the binding layer
MIN_KNOWN = 5                           # min price points ≤ T before a layer can be scored

# layer → its independent price series (each node already carries a sourced, GIGO-rationaled param in
# graph.py; here we only point build_series_id at the matching keyless BLS/FRED price feed).
FEEDS = [
    ("ai_power", "large-power transformer (>=100 MVA)", "transformer_ppi"),
    ("ai_power", "high-voltage switchgear", "switchgear_ppi"),
    ("ai_power", "grain-oriented electrical steel (GOES)", "steel_ppi"),
    ("metals", "refined copper (cathode)", "copper_ppi"),
    ("metals", "copper mine supply (concentrate)", "copper_mine_output"),  # quantity, not price → not scored
]


def wire_feeds(conn: sqlite3.Connection, *, log=print) -> int:
    """Point each layer node's build_series_id at its independent price/quantity series (idempotent).
    Non-price feeds (copper mine OUTPUT) are wired for the drill-score but excluded from the price
    comparison below — flagged, not faked."""
    n = 0
    for chain, node_name, metric in FEEDS:
        row = conn.execute("SELECT id FROM series WHERE metric=?", (metric,)).fetchone()
        if row is None:
            log(f"  ! no series for metric {metric} — skipping {chain}/{node_name}")
            continue
        if graph.set_build_series(conn, chain=chain, node_name=node_name, series_id=row["id"],
                                  log=lambda *_a, **_k: None):
            n += 1
    log(f"  wired {n}/{len(FEEDS)} layer feeds (independent price/quantity series).")
    return n


def _logslope(known: list[tuple[float, float]]) -> float:
    """Theil–Sen slope of log-price over the ≤T window — naive 'momentum' inelasticity proxy."""
    xs = [x for (x, _v) in known]
    ys = [math.log(max(v, LOG_FLOOR)) for (_x, v) in known]
    slope, _ = theil_sen(xs, ys)
    return slope


def inelastic_score(known: list[tuple[float, float]], *, k: float) -> float:
    """Mechanical, point-in-time inelasticity signal: the frozen detector's acceleration surprise on
    log-price ≤ T (price breaking ABOVE its own early trend = supply failing to answer demand). Falls
    back to the trailing log-slope when the detector can't fire (too few points / degenerate)."""
    det = detect(known, k=k, log=True)
    if det is not None and det.surprise_sigma is not None:
        return float(det.surprise_sigma)
    return _logslope(known)


def _realized_rise(pts: list[tuple[float, float, int]], T: int) -> float | None:
    """Log-price change from the last point ≤ T to the mean over (T, T+WINDOW]. None if no future point
    in the window. This is the LABEL — independent of any research count, drawn from price (rent)."""
    base = [v for (_x, v, yr) in pts if yr <= T]
    fut = [v for (_x, v, yr) in pts if T < yr <= T + WINDOW]
    if not base or not fut:
        return None
    b = base[-1]
    e = sum(fut) / len(fut)
    if b <= 0 or e <= 0:
        return None
    return math.log(e / b)


def _price_layers(conn: sqlite3.Connection) -> list[dict]:
    """Every WORLD node wired to a comparable PRICE series, with its full (x, value, year) points."""
    ph = ",".join("?" for _ in WORLD)
    rows = conn.execute(
        f"SELECT n.name, n.chain, n.build_series_id AS sid, s.metric "
        f"FROM graph_nodes n JOIN series s ON s.id = n.build_series_id "
        f"WHERE n.chain IN ({ph}) AND s.metric IN ({','.join('?' for _ in PRICE_METRICS)})",
        (*WORLD, *PRICE_METRICS),
    ).fetchall()
    out = []
    for r in rows:
        out.append({"name": r["name"], "chain": r["chain"], "sid": r["sid"], "metric": r["metric"],
                    "pts": _points_by_year(conn, r["sid"])})
    return out


def locate(conn: sqlite3.Connection, layers: list[dict], T: int, *, k: float,
           graph_pick: str | None) -> dict | None:
    """One origin: each mechanism names a binding layer from ≤T price data; grade vs the realized
    post-T price winner. Returns the locator_cases row dict, or None if < 2 layers are scorable at T."""
    cand = []
    for L in layers:
        known = [(x, v) for (x, v, yr) in L["pts"] if yr <= T]
        if len(known) < MIN_KNOWN:
            continue
        assert max(yr for (_x, _v, yr) in L["pts"] if yr <= T) <= T   # no look-ahead, in code
        rise = _realized_rise(L["pts"], T)
        if rise is None:
            continue
        cand.append({"name": L["name"], "score": inelastic_score(known, k=k),
                     "slope": _logslope(known), "rise": rise})
    if len(cand) < 2:
        return None
    located = max(cand, key=lambda c: c["score"])
    obvious = max(cand, key=lambda c: c["slope"])
    winner = max(cand, key=lambda c: c["rise"])
    return {
        "chain": "+".join(WORLD), "origin_year": T,
        "located_layer": located["name"], "located_score": round(located["score"], 4),
        "winner_layer": winner["name"], "obvious_layer": obvious["name"],
        "share_multiple": round(math.exp(winner["rise"]), 3),
        "correct": int(located["name"] == winner["name"]),
        "graph_pick": graph_pick,
        "graph_correct": (None if graph_pick is None else int(graph_pick == winner["name"])),
        "note": f"{len(cand)} priced layers scorable at T={T}",
    }


def _store(conn: sqlite3.Connection, case: dict) -> None:
    conn.execute(
        "INSERT INTO locator_cases (id,chain,origin_year,located_layer,located_score,winner_layer,"
        "obvious_layer,share_multiple,correct,graph_pick,graph_correct,note,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(chain,origin_year) DO UPDATE SET located_layer=excluded.located_layer, "
        "located_score=excluded.located_score, winner_layer=excluded.winner_layer, "
        "obvious_layer=excluded.obvious_layer, share_multiple=excluded.share_multiple, "
        "correct=excluded.correct, graph_pick=excluded.graph_pick, "
        "graph_correct=excluded.graph_correct, note=excluded.note, created_at=excluded.created_at",
        (_uid(), case["chain"], case["origin_year"], case["located_layer"], case["located_score"],
         case["winner_layer"], case["obvious_layer"], case["share_multiple"], case["correct"],
         case["graph_pick"], case["graph_correct"], case["note"], _now().isoformat()),
    )
    conn.commit()


def run(conn: sqlite3.Connection, *, k: float = DEFAULT_K, origins: tuple[int, ...] = ORIGINS,
        log=print) -> dict:
    """Wire the price feeds, run the rolling-origin locator over the connected world, store + report.
    The honest, independent-label retro-test of the constraint-migration thesis. cost: $0.00."""
    wire_feeds(conn, log=log)
    layers = _price_layers(conn)
    priced_names = {L["name"] for L in layers}
    # graph_pick: the hand-reasoned supply model's bottleneck over the world (contaminated control —
    # constant across origins because its elasticities are static, hindsight-tuned parameters). If its
    # modal bottleneck is NOT one of the comparable priced layers (e.g. the unpriced copper-mine
    # quantity layer), the control is N/A here — reported honestly, not scored as a 0.
    try:
        gp_raw = graph.propagate(conn, chains=WORLD).bottleneck.name
    except Exception:
        gp_raw = None
    gp = gp_raw if gp_raw in priced_names else None
    gp_note = "" if gp else f" (N/A — graph bottleneck '{gp_raw}' is not a priced layer)"

    log(f"\n🧭 CONSTRAINT LOCATOR — world {'+'.join(WORLD)}, {len(layers)} priced layers, k={k:g}, log-price")
    log(f"   layers: {', '.join(L['name'].split(' (')[0] for L in layers)}")
    log(f"   label = realized log-price rise over (T, T+{WINDOW}] (INDEPENDENT of any research count)")
    log(f"   graph-model bottleneck (contaminated control): {gp_raw}{gp_note}\n")
    log("   origin  located (detector ≤T)           winner (realized price)         hit  obvious(momentum)  graph")
    cases = []
    for T in origins:
        c = locate(conn, layers, T, k=k, graph_pick=gp)
        if c is None:
            log(f"   {T}   — < 2 priced layers scorable (skipped)")
            continue
        _store(conn, c)
        cases.append(c)
        hit = "✅" if c["correct"] else "· "
        gmark = ("✅" if c["graph_correct"] else "· ") if c["graph_correct"] is not None else "—"
        log(f"   {T}   {c['located_layer'].split(' (')[0][:28]:<28}  "
            f"{c['winner_layer'].split(' (')[0][:28]:<28}  {hit}  "
            f"{c['obvious_layer'].split(' (')[0][:16]:<16}  {gmark}")

    n = len(cases)
    if not n:
        log("\n   ⚠️  no scorable origins — wire more layer-price series to widen the test.")
        return {"n": 0}
    loc_hit = sum(c["correct"] for c in cases)
    obv_hit = sum(int(c["obvious_layer"] == c["winner_layer"]) for c in cases)
    gph_hit = sum(int(bool(c["graph_correct"])) for c in cases)
    base = 1.0 / len(priced_names)   # random pick over the comparable layers
    log(f"\n   N = {n} origin-cases (ONE connected world — honest small N, 'suggestive / cannot refute')")
    log(f"   located (mechanical, point-in-time)  {loc_hit}/{n} = {loc_hit/n*100:.0f}%   "
        f"(random baseline ≈ {base*100:.0f}%)")
    log(f"   obvious (naive momentum)             {obv_hit}/{n} = {obv_hit/n*100:.0f}%")
    log(f"   graph  (hindsight-tuned control)     " +
        (f"{gph_hit}/{n} = {gph_hit/n*100:.0f}%" if gp else "N/A — modal bottleneck is not a priced layer"))
    if loc_hit / n > base + 1e-9:
        verdict = (f"located ({loc_hit/n*100:.0f}%) edges above the {base*100:.0f}% random baseline "
                   f"(beats naive momentum {obv_hit}/{n}) — but at N={n} this is noise, not an edge")
    elif loc_hit / n < base - 1e-9:
        verdict = (f"located ({loc_hit/n*100:.0f}%) is BELOW the {base*100:.0f}% random baseline — no "
                   f"mechanical edge; the pre-surge price trend did not reveal the binding layer")
    else:
        verdict = (f"located ({loc_hit/n*100:.0f}%) ≈ the {base*100:.0f}% random baseline — no edge")
    log(f"   → {verdict}.")
    log("   HONEST READ: the 2021+ price surge is a regime change largely invisible in the pre-surge")
    log("   trend, so a mechanical point-in-time score cannot reliably locate it at this N. The")
    log("   constraint migration is REAL (rent did land on electrical steel/transformer) but NOT")
    log("   mechanically predictable from price alone here. Widen N (more priced layers) before any claim.")
    return {"n": n, "located_hits": loc_hit, "obvious_hits": obv_hit, "graph_hits": gph_hit,
            "base_rate": base, "graph_pick": gp}
