"""engine/experiment.py — the pre-registered, iterable detector experiment (Stage 1).

This is the orchestrator that turns engine/universe.py (the frozen, contamination-free, rolling-origin
backtest) into a SCIENTIFIC experiment you can iterate on without fooling yourself. It does three
things the bare backtest cannot:

  1. LEAKAGE GUARD — the sealed TEST origins (protocol_v1.yaml splits.test) are refused by run_config
     unless seal_unlocked=True, which only experiment-reveal sets, once. You can iterate freely on the
     SELECTION origins (train ∪ validation); the TEST block is touched exactly once, at the end.
  2. ANTI-OVERFITTING LEDGER — every config tried is written to experiment_ledger. The reported
     significance is DEFLATED by the number of configs in the pre-registered search space (Bonferroni),
     so trying more knobs cannot manufacture a result — the denominator is in the DB.
  3. SELECT → REVEAL — run the whole search space on the selection origins, promote argmax
     lift_declustered, then reveal it once on TEST. Whatever TEST says is THE RESULT (a null included).

The detector is non-parametric (nothing is FIT from data), so train and validation both serve as the
in-sample SELECTION set; TEST (2018, 2020) is the only true holdout. The seal is the git commit of
experiments/protocol_v1.yaml, which must predate the is_test_reveal=1 ledger row (verify via git log).

$0, stdlib only. Determinism: universe's block-null uses significance.SEED (fixed) → reruns identical.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import random
import sqlite3

from engine import universe
from engine.schemas import _now, _uid

# ── pre-registration mirror (the binding copy is experiments/protocol_v1.yaml) ──────────────────────
PROTOCOL_VERSION = 1
SPLITS = {
    "train": (2008, 2010, 2012),
    "validation": (2014, 2016),
    "test": (2018, 2020),            # SEALED — scored only via reveal_test
}
SELECT_ORIGINS = SPLITS["train"] + SPLITS["validation"]   # the in-sample selection set
TEST_ORIGINS = SPLITS["test"]
SEARCH_SPACE = {
    "k": [2.5, 3.0, 3.5],
    "gain_margin": [1.3, 1.5, 2.0],
    "channels": ["count", "count+diffusion", "count+diffusion+talent"],
}
N_CONFIGS_DECLARED = 27              # |k|·|gain_margin|·|channels| — the deflation denominator
PRIMARY_METRIC = "lift_declustered"


def _configs() -> list[dict]:
    """The full declared search space as a list of config dicts (deterministic order)."""
    keys = ("k", "gain_margin", "channels")
    return [dict(zip(keys, combo))
            for combo in itertools.product(SEARCH_SPACE["k"], SEARCH_SPACE["gain_margin"],
                                           SEARCH_SPACE["channels"])]


def _config_json(cfg: dict) -> str:
    return json.dumps({k: cfg[k] for k in ("k", "gain_margin", "channels")}, sort_keys=True)


def _assert_not_sealed(origins: tuple[int, ...], seal_unlocked: bool) -> None:
    """The mechanical tripwire: refuse to score any sealed-TEST origin unless explicitly unlocked."""
    if not seal_unlocked and any(o in TEST_ORIGINS for o in origins):
        raise RuntimeError(
            "TEST origins are SEALED (protocol_v1.yaml). Score them only via experiment-reveal, once.")


def run_config(conn: sqlite3.Connection, cfg: dict, origins: tuple[int, ...], *,
               seal_unlocked: bool = False, m: int = 2000) -> dict:
    """Score one config on `origins` with the block null. Never stores to universe_cases (a tuning run
    must not overwrite the canonical bench). Returns the primary (selected-channel) metrics dict."""
    _assert_not_sealed(origins, seal_unlocked)
    out = universe.run(conn, k=cfg["k"], origins=origins, gain_margin=cfg["gain_margin"],
                       channels=cfg["channels"], store=False, block_null=True, m=m,
                       log=lambda *a, **k: None)
    p = out["primary"]
    dc = p["declustered"]
    return {
        "n_scored": p["n"],
        "lift": p["lift"],
        "lift_declustered": dc["lift"],
        "p_fisher": dc.get("p_value"),
        "p_block": dc.get("p_block"),
        "lift_ci_low": dc.get("lift_ci", (None, None))[0],
        "lift_ci_high": dc.get("lift_ci", (None, None))[1],
        "brier_model": p.get("brier_model"),
        "brier_base": p.get("brier_base"),
    }


def _n_configs_seen(conn: sqlite3.Connection, pv: int = PROTOCOL_VERSION) -> int:
    return conn.execute(
        "SELECT COUNT(DISTINCT config_json) n FROM experiment_ledger WHERE protocol_version=?",
        (pv,),
    ).fetchone()["n"]


def _ledger_write(conn: sqlite3.Connection, *, split: str, cfg: dict, res: dict,
                  pv: int = PROTOCOL_VERSION, n_declared: int = N_CONFIGS_DECLARED,
                  is_test_reveal: bool = False) -> None:
    """Upsert one ledger row. UNIQUE(protocol, split, config) → re-runs overwrite (count stays honest).
    p_deflated is filled at reveal time (when the denominator is final); selection rows leave it NULL."""
    n_seen = max(_n_configs_seen(conn, pv), n_declared)   # the pre-registered family is the floor
    p_deflated = (None if not is_test_reveal or res.get("p_block") is None
                  else min(1.0, res["p_block"] * n_seen))
    conn.execute(
        "INSERT INTO experiment_ledger (id, protocol_version, split, config_json, n_scored, lift, "
        "lift_declustered, p_fisher, p_block, lift_ci_low, lift_ci_high, brier_model, brier_base, "
        "n_configs_seen, p_deflated, is_test_reveal, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(protocol_version, split, config_json) DO UPDATE SET "
        "n_scored=excluded.n_scored, lift=excluded.lift, lift_declustered=excluded.lift_declustered, "
        "p_fisher=excluded.p_fisher, p_block=excluded.p_block, lift_ci_low=excluded.lift_ci_low, "
        "lift_ci_high=excluded.lift_ci_high, brier_model=excluded.brier_model, "
        "brier_base=excluded.brier_base, n_configs_seen=excluded.n_configs_seen, "
        "p_deflated=excluded.p_deflated, is_test_reveal=excluded.is_test_reveal, "
        "created_at=excluded.created_at",
        (_uid(), pv, split, _config_json(cfg), res["n_scored"], res["lift"],
         res["lift_declustered"], res["p_fisher"], res["p_block"], res["lift_ci_low"],
         res["lift_ci_high"], res["brier_model"], res["brier_base"], n_seen, p_deflated,
         1 if is_test_reveal else 0, _now().isoformat()),
    )
    conn.commit()


def _promote(conn: sqlite3.Connection, pv: int = PROTOCOL_VERSION) -> tuple[dict, dict] | None:
    """The promoted config = argmax selection lift_declustered (tie → larger k, the conservative pick)
    among configs with a real de-clustered sample. Reads the ledgered selection rows."""
    rows = conn.execute(
        "SELECT config_json, lift_declustered, n_scored FROM experiment_ledger "
        "WHERE protocol_version=? AND split='select' AND n_scored > 0", (pv,),
    ).fetchall()
    if not rows:
        return None
    best = max(rows, key=lambda r: (r["lift_declustered"] or 0.0, json.loads(r["config_json"])["k"]))
    cfg = json.loads(best["config_json"])
    return cfg, {"lift_declustered": best["lift_declustered"], "n_scored": best["n_scored"]}


def select_and_seal(conn: sqlite3.Connection, *, m: int = 2000, log=print) -> dict:
    """Run the full search space on the SELECTION origins, ledger every config, promote the winner.
    Never touches the sealed TEST origins. Safe to re-run while iterating."""
    cfgs = _configs()
    log(f"\n🧪 EXPERIMENT v{PROTOCOL_VERSION} — SELECT (origins {SELECT_ORIGINS}, TEST {TEST_ORIGINS} SEALED)")
    log(f"   search space: {len(cfgs)} configs (k×gain_margin×channels) · primary metric = {PRIMARY_METRIC}")
    log(f"   block-permutation null + cluster-bootstrap CI, M={m} (deterministic seed)\n")
    log("   k     margin  channels                    n    lift   declust   p_block")
    for cfg in cfgs:
        res = run_config(conn, cfg, SELECT_ORIGINS, m=m)
        _ledger_write(conn, split="select", cfg=cfg, res=res)
        log(f"   {cfg['k']:<4g} {cfg['gain_margin']:<6g} {cfg['channels']:<26} {res['n_scored']:4d}  "
            f"{res['lift']:5.2f}×  {res['lift_declustered']:5.2f}×   "
            f"{(res['p_block'] if res['p_block'] is not None else float('nan')):.3f}")
    promoted = _promote(conn)
    if promoted is None:
        log("\n   ⚠️  no config produced a scorable de-clustered sample — nothing to promote.")
        return {"promoted": None, "n_configs": len(cfgs)}
    cfg, m_sel = promoted
    log(f"\n   ▶ PROMOTED (argmax selection {PRIMARY_METRIC}): k={cfg['k']:g} gain_margin={cfg['gain_margin']:g} "
        f"channels={cfg['channels']} → declustered lift {m_sel['lift_declustered']:.2f}× (n={m_sel['n_scored']})")
    log(f"   TEST still SEALED. Run `experiment-reveal` once to score it on {TEST_ORIGINS}.")
    return {"promoted": cfg, "selection_lift_declustered": m_sel["lift_declustered"],
            "n_configs": len(cfgs), "n_configs_seen": _n_configs_seen(conn)}


def reveal_test(conn: sqlite3.Connection, *, m: int = 2000, log=print) -> dict:
    """The one-time sealed-TEST reveal. Refuses if already revealed. Scores the promoted config on the
    TEST origins, ledgers it (is_test_reveal=1) with the deflated p, and prints the headline result."""
    existing = conn.execute(
        "SELECT config_json, lift_declustered, p_block, p_deflated FROM experiment_ledger "
        "WHERE protocol_version=? AND is_test_reveal=1", (PROTOCOL_VERSION,),
    ).fetchone()
    if existing is not None:
        log(f"\n🔒 TEST already revealed for protocol v{PROTOCOL_VERSION} (config {existing['config_json']}, "
            f"declustered lift {existing['lift_declustered']:.2f}×, p_deflated {existing['p_deflated']}). "
            f"Re-revealing is forbidden — write protocol_v2 with new test origins to iterate further.")
        return {"already_revealed": True}
    promoted = _promote(conn)
    if promoted is None:
        log("\n⚠️  nothing promoted — run `experiment-select` first.")
        return {"error": "no promoted config"}
    cfg, _ = promoted
    res = run_config(conn, cfg, TEST_ORIGINS, seal_unlocked=True, m=m)
    _ledger_write(conn, split="test", cfg=cfg, res=res, is_test_reveal=True)
    n_seen = max(_n_configs_seen(conn), N_CONFIGS_DECLARED)
    p_def = None if res["p_block"] is None else min(1.0, res["p_block"] * n_seen)
    verdict = ("SIGNIFICANT ✅" if (p_def is not None and p_def < 0.05)
               else "suggestive" if (p_def is not None and p_def < 0.10) else "NOT significant ❌")
    log(f"\n🎯 TEST REVEAL — protocol v{PROTOCOL_VERSION}, config k={cfg['k']:g} "
        f"gain_margin={cfg['gain_margin']:g} channels={cfg['channels']}, origins {TEST_ORIGINS}")
    log(f"   de-clustered lift   {res['lift_declustered']:.2f}×   "
        f"CI [{res['lift_ci_low']}, {res['lift_ci_high']}]")
    log(f"   block-permutation p {res['p_block']}   (Fisher {res['p_fisher']})")
    log(f"   DEFLATED p (×{n_seen} configs)  {p_def}   → {verdict}")
    log(f"   Brier model {res['brier_model']} vs base {res['brier_base']}")
    log(f"   ⚖️  this is THE RESULT — recorded immutably (experiment_ledger, is_test_reveal=1).")
    return {"config": cfg, "lift_declustered": res["lift_declustered"], "p_block": res["p_block"],
            "p_deflated": p_def, "n_configs_seen": n_seen}


def status(conn: sqlite3.Connection, *, log=print) -> dict:
    """Print the ledger: configs tried, the deflation denominator, current best selection lift, and
    whether TEST is still sealed. The visual-first surface (CONSTITUTION rule 8)."""
    n_seen = _n_configs_seen(conn)
    revealed = conn.execute(
        "SELECT COUNT(*) n FROM experiment_ledger WHERE protocol_version=? AND is_test_reveal=1",
        (PROTOCOL_VERSION,),
    ).fetchone()["n"]
    sel = conn.execute(
        "SELECT config_json, lift_declustered, p_block, n_scored FROM experiment_ledger "
        "WHERE protocol_version=? AND split='select' ORDER BY lift_declustered DESC", (PROTOCOL_VERSION,),
    ).fetchall()
    log(f"\n📋 EXPERIMENT LEDGER — protocol v{PROTOCOL_VERSION}")
    log(f"   configs tried: {n_seen} / {N_CONFIGS_DECLARED} declared (deflation denominator)")
    log(f"   TEST: {'🔓 REVEALED' if revealed else '🔒 sealed (run experiment-reveal once when ready)'}")
    if sel:
        log("\n   selection rows (best first):")
        log("   k    margin channels                   n    declust  p_block")
        for r in sel:
            c = json.loads(r["config_json"])
            pb = f"{r['p_block']:.3f}" if r["p_block"] is not None else "  -  "
            log(f"   {c['k']:<4g} {c['gain_margin']:<6g} {c['channels']:<26} {r['n_scored']:4d}  "
                f"{(r['lift_declustered'] or 0):5.2f}×   {pb}")
    if revealed:
        t = conn.execute(
            "SELECT config_json, lift_declustered, p_block, p_deflated FROM experiment_ledger "
            "WHERE protocol_version=? AND is_test_reveal=1", (PROTOCOL_VERSION,),
        ).fetchone()
        log(f"\n   🎯 SEALED-TEST RESULT: config {t['config_json']} → declustered lift "
            f"{t['lift_declustered']:.2f}×, p_block {t['p_block']}, DEFLATED p {t['p_deflated']}")
    return {"n_configs_seen": n_seen, "n_declared": N_CONFIGS_DECLARED, "test_revealed": bool(revealed)}


# ═══════════════════════════════════════════════════════════════════════════════════════════════════
# PROTOCOL v2 — the CONCEPT-DISJOINT, POWERED experiment (experiments/protocol_v2.yaml).
#
# Same frozen detector + same ledger + same block-null/deflation as v1. Two differences: the pool is
# OpenAlex + arXiv-category concepts (annual origins), and the split is CONCEPT-DISJOINT (a frozen hash
# partition) so select and test share zero concepts — the clean answer to v1's persistent-winner caveat.
# ═══════════════════════════════════════════════════════════════════════════════════════════════════
PROTOCOL_V2 = {
    "version": 2,
    "providers": ("openalex", "arxiv"),
    "origins": tuple(range(2008, 2022)),               # annual 2008–2021
    "salt": "v2-concept-disjoint-20260605",            # FRESH, unprobed → the reveal stays blind
    "n_configs_declared": 27,
}


def _concept_split(conn: sqlite3.Connection) -> tuple[set[str], set[str]]:
    """Partition the combined concept pool into SELECT (~2/3) and TEST (~1/3) by a frozen hash of the
    concept's external_id. Deterministic, declared in protocol_v2.yaml (salt). No concept is in both."""
    ph = ",".join("?" for _ in PROTOCOL_V2["providers"])
    rows = conn.execute(
        f"SELECT DISTINCT external_id FROM series WHERE provider IN ({ph}) AND metric='works_per_year'",
        tuple(PROTOCOL_V2["providers"]),
    ).fetchall()
    sel: set[str] = set()
    test: set[str] = set()
    for r in rows:
        key = r["external_id"]
        b = int(hashlib.md5((PROTOCOL_V2["salt"] + "|" + key).encode()).hexdigest()[:8], 16) % 3
        (test if b == 2 else sel).add(key)
    return sel, test


def run_config_v2(conn: sqlite3.Connection, cfg: dict, concept_set: set[str], *, m: int = 2000) -> dict:
    """Score one config on a concept set (SELECT or TEST), combined pool + annual origins, block null."""
    out = universe.run(conn, k=cfg["k"], origins=PROTOCOL_V2["origins"], gain_margin=cfg["gain_margin"],
                       channels=cfg["channels"], providers=PROTOCOL_V2["providers"],
                       concept_filter=concept_set, store=False, block_null=True, m=m,
                       log=lambda *a, **k: None)
    p = out["primary"]
    dc = p["declustered"]
    return {
        "n_scored": p["n"], "lift": p["lift"], "lift_declustered": dc["lift"],
        "p_fisher": dc.get("p_value"), "p_block": dc.get("p_block"),
        "lift_ci_low": dc.get("lift_ci", (None, None))[0],
        "lift_ci_high": dc.get("lift_ci", (None, None))[1],
        "brier_model": p.get("brier_model"), "brier_base": p.get("brier_base"),
    }


def select_and_seal_v2(conn: sqlite3.Connection, *, m: int = 2000, log=print) -> dict:
    """Run the search space on the SELECT concepts, ledger every config (protocol 2), promote the
    argmax de-clustered lift. Never scores the TEST concepts."""
    sel, test = _concept_split(conn)
    pv, nd = PROTOCOL_V2["version"], PROTOCOL_V2["n_configs_declared"]
    log(f"\n🧪 EXPERIMENT v2 — CONCEPT-DISJOINT SELECT ({len(sel)} concepts; {len(test)} TEST concepts SEALED)")
    log(f"   pool: {PROTOCOL_V2['providers']} works/year · annual origins {PROTOCOL_V2['origins'][0]}–{PROTOCOL_V2['origins'][-1]}")
    log("   k     margin  channels                    n    lift   declust   p_block")
    for cfg in _configs():
        res = run_config_v2(conn, cfg, sel, m=m)
        _ledger_write(conn, split="select", cfg=cfg, res=res, pv=pv, n_declared=nd)
        log(f"   {cfg['k']:<4g} {cfg['gain_margin']:<6g} {cfg['channels']:<26} {res['n_scored']:4d}  "
            f"{res['lift']:5.2f}×  {res['lift_declustered']:5.2f}×   "
            f"{(res['p_block'] if res['p_block'] is not None else float('nan')):.3f}")
    promoted = _promote(conn, pv)
    if promoted is None:
        log("\n   ⚠️  nothing scorable to promote."); return {"promoted": None}
    cfg, m_sel = promoted
    log(f"\n   ▶ PROMOTED (argmax SELECT lift_declustered): k={cfg['k']:g} gain_margin={cfg['gain_margin']:g} "
        f"channels={cfg['channels']} → declustered lift {m_sel['lift_declustered']:.2f}× (n={m_sel['n_scored']})")
    log(f"   TEST concepts still SEALED. Run experiment-v2-reveal once.")
    return {"promoted": cfg, "n_select": len(sel), "n_test_concepts": len(test)}


def reveal_test_v2(conn: sqlite3.Connection, *, m: int = 2000, log=print) -> dict:
    """One-time concept-disjoint TEST reveal. Refuses if already revealed. Also prints the per-provider
    breakdown (the grain finding: fine OpenAlex concepts vs coarse arXiv categories)."""
    pv, nd = PROTOCOL_V2["version"], PROTOCOL_V2["n_configs_declared"]
    if conn.execute("SELECT COUNT(*) n FROM experiment_ledger WHERE protocol_version=? AND is_test_reveal=1",
                    (pv,)).fetchone()["n"]:
        log(f"\n🔒 v2 TEST already revealed — re-revealing forbidden (write protocol_v3 to iterate).")
        return {"already_revealed": True}
    promoted = _promote(conn, pv)
    if promoted is None:
        log("\n⚠️  run experiment-v2-select first."); return {"error": "no promoted config"}
    cfg, _ = promoted
    sel, test = _concept_split(conn)
    res = run_config_v2(conn, cfg, test, m=m)
    _ledger_write(conn, split="test", cfg=cfg, res=res, pv=pv, n_declared=nd, is_test_reveal=True)
    n_seen = max(_n_configs_seen(conn, pv), nd)
    p_def = None if res["p_block"] is None else min(1.0, res["p_block"] * n_seen)
    verdict = ("SIGNIFICANT ✅" if (p_def is not None and p_def < 0.05)
               else "suggestive" if (p_def is not None and p_def < 0.10) else "NOT significant ❌")
    log(f"\n🎯 v2 TEST REVEAL (concept-disjoint) — config k={cfg['k']:g} gain_margin={cfg['gain_margin']:g} "
        f"channels={cfg['channels']}, {len(test)} held-out concepts")
    log(f"   de-clustered lift   {res['lift_declustered']:.2f}×   CI [{res['lift_ci_low']}, {res['lift_ci_high']}]   (n={res['n_scored']} pooled)")
    log(f"   block-permutation p {res['p_block']}   DEFLATED (×{n_seen}) {p_def}  → {verdict}")
    log(f"   Brier model {res['brier_model']} vs base {res['brier_base']}")
    # per-provider grain breakdown (reported, not a separate test)
    for prov in PROTOCOL_V2["providers"]:
        pr = universe.run(conn, k=cfg["k"], origins=PROTOCOL_V2["origins"], gain_margin=cfg["gain_margin"],
                          channels=cfg["channels"], providers=(prov,),
                          concept_filter={x for x in test}, store=False, block_null=False,
                          log=lambda *a, **k: None)["primary"]["declustered"]
        log(f"     · {prov:9} held-out: declust n={pr['n']:3d}  lift {pr['lift']:.2f}×")
    return {"config": cfg, "lift_declustered": res["lift_declustered"], "p_deflated": p_def,
            "n_test_concepts": len(test)}


# ═══════════════════════════════════════════════════════════════════════════════════════════════════
# POWER ANALYSIS — was the v2 null well-powered (signal dead) or under-powered (couldn't see a weak
# edge)? Read-only on an ALREADY-SPENT seal: re-score the SAME held-out concepts with the SAME promoted
# config, take the de-clustered events (the independent unit the reveal used), and feed them to
# significance.power_curve. No tuning, no new reveal — it only quantifies what the closed v2 test could
# have detected. The honest full-stop on the count detector.
# ═══════════════════════════════════════════════════════════════════════════════════════════════════

def _n_configs_cumulative(conn: sqlite3.Connection) -> int:
    """Every DISTINCT (protocol_version, config_json) ever ledgered — the TRUE family size across all
    protocol versions for the one hypothesis under test ("the detector has a gain-of-share edge").
    Resetting the denominator per protocol is the p-hacking hole; the honest deflation is cumulative."""
    row = conn.execute(
        "SELECT COUNT(DISTINCT protocol_version || '|' || config_json) n FROM experiment_ledger"
    ).fetchone()
    return int(row["n"]) if row and row["n"] else 0


def v2_declustered_test_events(conn: sqlite3.Connection) -> tuple[list[tuple], dict | None]:
    """Reconstruct the v2 sealed-TEST de-clustered ((origin,cohort), fired, winner) events for the
    revealed config — read-only (the v2 seal is already spent). Returns (events, cfg) or ([], None) if
    v2 was never revealed. These are the independent unit the v2 reveal's p_block was computed on."""
    row = conn.execute(
        "SELECT config_json FROM experiment_ledger WHERE protocol_version=2 AND is_test_reveal=1"
    ).fetchone()
    if row is None:
        return [], None
    cfg = json.loads(row["config_json"])
    _sel, test = _concept_split(conn)
    out = universe.run(conn, k=cfg["k"], origins=PROTOCOL_V2["origins"], gain_margin=cfg["gain_margin"],
                       channels=cfg["channels"], providers=PROTOCOL_V2["providers"],
                       concept_filter=test, store=False, block_null=False, log=lambda *a, **k: None)
    evs = out["primary"]["events_declustered"]          # (origin, cohort, fired, winner)
    return [((o, coh), bool(f), bool(w)) for (o, coh, f, w) in evs], cfg


def power_report(conn: sqlite3.Connection, *, m_inner: int = 2000, m_outer: int = 400,
                 log=print) -> dict:
    """Print the minimum-detectable-effect of the v2 sealed-TEST de-clustered test, raw and deflated
    by the CUMULATIVE config count (v1+v2+…). Decides whether v2 refuted the signal or just lacked
    power. Writes nothing — a pure read-only audit of a closed experiment. cost: $0.00."""
    import engine.significance as sig
    events, cfg = v2_declustered_test_events(conn)
    if not events:
        log("\n⚠️  v2 TEST has not been revealed — nothing to power-analyse. Run experiment-v2-reveal first.")
        return {"error": "no v2 reveal"}
    n_cum = _n_configs_cumulative(conn)
    obs_lift = sig._lift_of([(f, w) for (_bk, f, w) in events])
    rng = random.Random(sig.SEED)
    pc = sig.power_curve(events, m_inner=m_inner, m_outer=m_outer,
                         n_configs_variants=(1, n_cum), rng=rng)
    log(f"\n🔬 POWER ANALYSIS — v2 sealed-TEST de-clustered, config {_config_json(cfg)}")
    log(f"   observed: n={pc['n']} concepts · {pc['W']} winners (base {pc['base_rate']*100:.1f}%) · "
        f"{pc['F']} fired (rate {pc['fire_rate']*100:.1f}%) · observed lift {obs_lift:.2f}×")
    cap = pc["max_achievable_lift"]
    log(f"   max lift this fire-rate can even express: {cap:.2f}× (q_winner capped at 1.0 above it)")
    log(f"   simulation: {m_outer} synthetic sets × {m_inner} block-perms each, α=0.05\n")
    log("   assumed TRUE lift     power(raw)   power(×{n} cumulative deflation)".format(n=n_cum))
    for L in sorted(pc["power"][1]):
        capmark = " (lift capped)" if pc["caps"][L] else ""
        log(f"     {L:>4.1f}×              {pc['power'][1][L]*100:5.0f}%        "
            f"{pc['power'][n_cum][L]*100:5.0f}%{capmark}")
    mde_raw, mde_def = pc["mde_80"][1], pc["mde_80"][n_cum]
    sraw = f"{mde_raw:.2f}×" if mde_raw is not None else "off-grid (>max)"
    sdef = f"{mde_def:.2f}×" if mde_def is not None else "off-grid (>max)"
    log(f"\n   MDE_80 (raw)                 {sraw}   — smallest edge the test could flag 80% of the time")
    log(f"   MDE_80 (deflated ×{n_cum})        {sdef}   — after the honest multiple-testing tax")
    # the pre-committed interpretation (protocol_v3.yaml thresholds): ~1.7× = the fine-concept edge
    if mde_raw is not None and mde_raw <= 1.7:
        verdict = ("WELL-POWERED NULL — the test could see a fine-concept edge (~1.7×) and found none. "
                   "The count-acceleration signal is genuinely dead at this grain.")
    elif mde_raw is None or mde_raw >= 2.5:
        verdict = ("UNDER-POWERED — the test could not have detected a weak (≤2.5×) edge, so v2 did NOT "
                   "refute one. The de-clustered N is too small; the count chapter closes as a "
                   "non-result, not a refutation.")
    else:
        verdict = ("BORDERLINE — MDE_80 between 1.7× and 2.5×; the null is suggestive but not decisive.")
    log(f"\n   ⚖️  VERDICT: {verdict}")
    log(f"   (read-only audit of the closed v2 seal — no ledger row written.)")
    return {"n": pc["n"], "observed_lift": obs_lift, "mde_80_raw": mde_raw,
            "mde_80_deflated": mde_def, "n_configs_cumulative": n_cum,
            "max_achievable_lift": cap}
