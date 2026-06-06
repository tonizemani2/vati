"""Component 17 — the open discovery funnel + the pre-consensus "are-we-early" filter.

The whole project's north star is to find where scarcity migrates *across any industry, before it's
priced in* — not to grade a thesis a human pre-picked. Everything needed already exists and already
runs blind across all ~220 series (the detector, the BH-FDR look-elsewhere gate in significance.py,
the QC gate in quality.py are all provider-agnostic). This module does NOT re-implement any of that.
It is a thin orchestrator + the one genuinely new idea: a PRE-CONSENSUS cross-reference.

The funnel (each stage is an existing gate; this just sequences + ranks + surfaces):
    collect → quality.run_audit → detector.run_detector → significance.run_significance
            → pre_consensus (NEW) → [priced-in gate, Stage 3] → Discovery Board (cockpit)

The pre-consensus filter — the live inversion of the retrodiction finding (capability = signal,
attention = decoy). For each entity we split its linked series into LEADING channels (mechanism-backed
capability + the science/supply that PRECEDES commercialization) and LAGGING channels (attention,
capital, policy, patents — the consensus confirming the crowd has noticed). Then:

    EARLY         leading fires (FDR-clean) AND lagging still flat  → the prize: real, not yet priced
    PRICED        leading fires AND lagging has caught up           → real but the crowd is here
    LAGGING-ONLY  lagging fires AND leading silent                  → attention without capability (the decoy/hype tell)
    QUIET         neither fires

This is what answers "it keeps saying priced in": it RANKS candidates by how un-priced they are.
Two filters in series — FDR (statistical) then lead-vs-lag (economic) — are the trustworthiness
mechanism: FDR kills multiple-comparisons flukes; requiring a LEADING channel kills the attention-only
false positives the universe benchmark already proved are noise.

$0, stdlib only — pure reads over the verdict columns the gates already wrote (no new tables/columns).
"""

from __future__ import annotations

import json
import re
import sqlite3
import urllib.request

from pydantic import BaseModel

from engine import detector, quality, significance

# The lead/lag doctrine, as code (not a table — rule 5). LEADING = mechanism-backed capability + the
# science/supply that runs AHEAD of commercialization. LAGGING = the consensus channels that only move
# once the crowd/market/policy has noticed (so they confirm a thing is being priced). Patents sit in
# LAG deliberately: a patent spike means commercial actors are already acting → the bar for "early"
# stays strict (fewer false earlies). Market price itself is checked downstream by the consensus gate.
#
# OpenAlex is LAGGING, not leading (2026-06-04 — the decoy-leak fix). Every OpenAlex series is
# `works_per_year` = a raw publication COUNT, and the §8 retrodiction corpus PROVED that channel is the
# DECOY: mechanism-free publication momentum that fires on the graphene fizzle (11σ) and is the §0.5
# "fizzle signature". An accelerating publication count is the research-world equivalent of ATTENTION —
# the field getting crowded — which confirms a topic is being noticed, it does not lead with a mechanism.
# So a count surge alone can NO LONGER mint an EARLY: it now reads as lagging (PRICED if a real lead also
# fires, the decoy/hype tell if it fires alone). The mechanism-backed RESEARCH lead is arXiv
# `topic_share`/`talent_inflow` (engine/pillars/research.py) — the finest grain, kept in LEAD.
LEAD_PROVIDERS = {"owid", "epoch_ai", "nih_reporter", "arxiv", "fred", "un_comtrade"}
LAG_PROVIDERS = {"openalex", "wikipedia", "sec_edgar", "federal_register", "google_patents",
                 "gdelt",            # forces geopolitics/news: event-velocity is ATTENTION (timing), not leading
                 "comtrade_china"}   # forces China decree-FOOTPRINT: annual export collapse CONFIRMS a decree
                                     # ~12mo after the price — corroboration, never a pre-consensus EARLY

# Within the leads, the FINE research grain vs the COARSE aggregate end-product curves. This is the
# anti-"supercomputing" rule (the /needle trap, doctrine §1.5): a single broad aggregate curve (owid
# `supercomputer flops`, an epoch_ai frontier-compute total, an fred macro index) fires with HUGE σ but
# σ is only MOVE MAGNITUDE — an aggregate count is the LAST place a signal appears, never the needle.
# The alpha is the FINE grain: arXiv topic_share / talent_inflow / cross-field diffusion, nih grant
# topics (the 2nd derivative bending up before the count saturates). So an EARLY whose ENTIRE leading
# evidence is coarse aggregates is "broad-curve only" — magnitude without grain; it is demoted out of
# the headline and never ranked first, because a theme is not a needle.
FINE_LEAD_PROVIDERS = {"arxiv", "nih_reporter"}

# Excluded from the LIVE scan: 'retro' = §8 benchmark fixtures (point-in-time frozen at old signal
# dates — historical test cases, not live signals); 'synthetic' = the detector's flat control. Both
# are legitimate elsewhere but would pollute a "where is the future NOW" scan with stale/known cases.
EXCLUDE_PROVIDERS = ("retro", "synthetic")


# ── Stage 2: the pre-consensus cross-reference (pure computed read) ────────────


def pre_consensus(conn: sqlite3.Connection) -> dict:
    """Classify every resolved entity as EARLY / PRICED / LAGGING-ONLY / QUIET from its linked series.

    Reuses entity_links (ref_table='series') joined to the detector+FDR verdicts already on each
    series row. Leading fire requires FDR survival (a real, look-elsewhere-corrected acceleration);
    lagging fire only requires a raw fire (any attention/capital/policy move = the crowd noticing),
    which keeps the EARLY bar strict. Returns the four buckets, EARLY ranked by leading σ.
    """
    rows = conn.execute(
        "SELECT e.id eid, e.canonical_name name, e.kind kind, e.domain domain, "
        "       s.provider provider, s.label slabel, "
        "       COALESCE(s.last_fired,0) fired, s.last_surprise_sigma sig, "
        "       COALESCE(s.last_fdr_survive,0) fdr "
        "FROM entities e "
        "JOIN entity_links l ON l.entity_id = e.id AND l.ref_table = 'series' "
        "JOIN series s ON s.id = l.ref_id "
        "WHERE s.provider NOT IN ('retro','synthetic') "
        "AND s.id NOT IN (SELECT series_id FROM series_health WHERE status='fail')"
    ).fetchall()

    ents: dict[str, dict] = {}
    for r in rows:
        e = ents.setdefault(r["eid"], {
            "name": r["name"], "kind": r["kind"], "domain": r["domain"],
            "lead_fire": False, "lag_fire": False, "lead_sig": 0.0,
            "lead_hits": [], "lag_hits": [], "n_lead": 0, "n_lag": 0,
        })
        prov = r["provider"]
        if prov in LEAD_PROVIDERS:
            e["n_lead"] += 1
            if r["fired"] and r["fdr"]:                       # FDR-clean leading acceleration
                e["lead_fire"] = True
                e["lead_sig"] = max(e["lead_sig"], r["sig"] or 0.0)
                e["lead_hits"].append((r["slabel"], prov, r["sig"]))
        elif prov in LAG_PROVIDERS:
            e["n_lag"] += 1
            if r["fired"]:                                    # any lagging fire = the crowd noticing
                e["lag_fire"] = True
                e["lag_hits"].append((r["slabel"], prov, r["sig"]))

    # which entities have a ticker link (ready for the Stage-3 priced-in gate)
    tickers = {r["entity_id"] for r in conn.execute(
        "SELECT DISTINCT entity_id FROM entity_links WHERE ref_table='ticker'")}

    # MEASURED pre-consensus (saturation.py): the indexed LAG channels above only cover OpenAlex/SEC/
    # patents/etc.; a topic saturating the trade press / regulatory / finance world reads as EARLY only
    # because we never looked. The saturation meter looked. A 'priced/known' verdict HARD-DEMOTES an
    # otherwise-EARLY candidate to PRICED (Ruben's locked rule: in the trade press ⇒ not pre-consensus).
    sat_rows = {r["entity_id"]: r for r in conn.execute(
        "SELECT entity_id, saturation, tier, verdict FROM saturation WHERE entity_id IS NOT NULL")}

    early, priced, lagging_only, quiet = [], [], [], []
    for eid, e in ents.items():
        e["has_ticker"] = eid in tickers
        e["eid"] = eid
        sr = sat_rows.get(eid)
        e["saturation"] = sr["saturation"] if sr else None
        e["sat_tier"] = sr["tier"] if sr else "unmeasured"
        e["sat_verdict"] = sr["verdict"] if sr else None
        e["sat_demoted"] = False
        # broad-curve only: the lead fired but NONE of the firing leads are the fine research grain →
        # magnitude without grain (the supercomputing trap). Kept in EARLY but never headlined.
        e["coarse_only"] = e["lead_fire"] and not any(
            h[1] in FINE_LEAD_PROVIDERS for h in e["lead_hits"])
        is_early = e["lead_fire"] and not e["lag_fire"]
        if is_early and sr and sr["verdict"] == "priced/known":
            e["sat_demoted"] = True            # measured coverage says the crowd/press is already here
            priced.append(e)
        elif is_early:
            early.append(e)
        elif e["lead_fire"] and e["lag_fire"]:
            priced.append(e)
        elif e["lag_fire"] and not e["lead_fire"]:
            lagging_only.append(e)
        else:
            quiet.append(e)
    # Rank EARLY by MEASURED pre-consensus, NOT by σ (σ is move magnitude, never the reason a thing is
    # un-priced — the /needle rule). Order: needle-able (fine grain) before broad-curve-only; then
    # lowest measured saturation first (the most genuinely un-narrated); unmeasured sinks below measured;
    # σ is only the final tiebreak.
    early.sort(key=lambda e: (
        e["coarse_only"],
        e["saturation"] if e["saturation"] is not None else 1.0,
        -e["lead_sig"]))
    priced.sort(key=lambda e: e["lead_sig"], reverse=True)
    return {"early": early, "priced": priced, "lagging_only": lagging_only, "quiet": quiet}


# ── Stage 1: the open scan (orchestrate the existing gates, then rank + cross-reference) ──


def _survivors(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """FDR-surviving fired series across ALL providers — the look-elsewhere-clean raw signals.

    A QC-FAILED series is excluded: the detector/significance skip it (`require_qc`) so its verdict
    columns are STALE (a frozen pre-gate value). If it still carried `last_fired=1` from an earlier
    run it would surface here with a stale σ — exactly how three field_breadth rows kept showing the
    old 1,000,000σ artifact after the σ-floor fix. The discovery board must honor the same QC gate
    every other consumer does, or it ranks on data the pipeline already disowned.
    """
    return conn.execute(
        "SELECT label, provider, domain, last_surprise_sigma sig, last_p_mc p, "
        "       last_p_mc_m mm, last_fdr_q q "
        "FROM series WHERE last_fired=1 AND last_fdr_survive=1 "
        "AND provider NOT IN ('retro','synthetic') "
        "AND id NOT IN (SELECT series_id FROM series_health WHERE status='fail') "
        "ORDER BY last_surprise_sigma DESC"
    ).fetchall()


def run_scan(conn: sqlite3.Connection, *, k: float = 3.0, q: float = 0.10, m: int = 2000,
             rescan: bool = False, log=print) -> dict:
    """Run (or read) the full open funnel, then rank survivors + the pre-consensus buckets.

    `rescan=True` re-runs the gates (audit → detect → significance) first — slow (M surrogates per
    series). Default reads the latest verdicts the gate commands already wrote, then computes the
    cheap pre-consensus cross-reference live. The honesty: it surfaces only FDR survivors and ranks
    the EARLY (un-priced) ones first; most days the EARLY list is short or empty — that is the truth.
    """
    if rescan:
        log("rescan: running the full funnel (audit → detect → significance)…\n")
        quality.run_audit(conn, log=log)
        detector.run_detector(conn, k=k, require_qc=True, log=log)
        significance.run_significance(conn, k=k, q=q, m=m, require_qc=True, log=log)
        log("")

    surv = _survivors(conn)
    if not surv:
        log("no FDR-surviving signals — run `detect` + `significance` first, or `discover --rescan`.")
        return {"survivors": 0, "early": 0, "priced": 0, "lagging_only": 0}

    providers = sorted({r["provider"] for r in surv})
    qv = surv[0]["q"] or q
    log(f"OPEN SCAN — {len(surv)} signals survive BH-FDR (q={qv:.0%}, expected false ≤ {qv*len(surv):.1f}) "
        f"across {len(providers)} feeds: {', '.join(providers)}")
    log("  (ranked by surprise; the FDR denominator — not raw σ — is the honest filter)")
    floor = 1.0 / ((surv[0]["mm"] or m) + 1)
    for r in surv[:20]:
        pstr = f"p<{floor:.1g}" if (r["p"] or 1) <= floor + 1e-12 else f"p={r['p']:.2g}"
        log(f"  ⚡ {r['label'][:42]:<42} {r['provider']:<14} {r['sig']:>8.1f}σ  {pstr}")
    if len(surv) > 20:
        log(f"  … +{len(surv) - 20} more")

    pc = pre_consensus(conn)
    log(f"\nPRE-CONSENSUS (are we early?) — {len(pc['early'])} EARLY · {len(pc['priced'])} priced · "
        f"{len(pc['lagging_only'])} lagging-only (decoy) · {len(pc['quiet'])} quiet")

    needles = [e for e in pc["early"] if not e.get("coarse_only")]
    broad = [e for e in pc["early"] if e.get("coarse_only")]
    if needles:
        log("\n  ★ EARLY — fine-grain capability accelerating while the crowd is still flat "
            "(ranked by MEASURED saturation, lowest = most un-priced — NOT by σ; σ is magnitude, "
            "never the reason):")
        n_unmeasured = sum(1 for e in needles if e.get("sat_tier") == "unmeasured")
        for e in needles:
            tick = " [ticker linked → ready for priced-in gate]" if e["has_ticker"] else " [needs ticker map]"
            leads = ", ".join(f"{lab[:22]}({prov} {sig:.0f}σ)" for lab, prov, sig in e["lead_hits"][:3])
            if e.get("sat_tier") == "unmeasured":
                sat = "saturation UNMEASURED — run `saturation-scan`; not yet confirmed pre-consensus"
            else:
                sat = f"saturation {e['saturation']:.2f} ({e['sat_tier']}) — measured low, coverage checked"
            log(f"     ◆ {e['name']:<28} sat {e['saturation'] if e['saturation'] is not None else float('nan'):.2f} · lead {e['lead_sig']:.0f}σ{tick}")
            log(f"       fires: {leads}")
            log(f"       {sat}")
        log("\n    → a theme is NOT a needle. Each line above is a coarse layer; the edge is the "
            "inelastic INPUT under it (named consumable/material/isotope + named suppliers + multi-year\n"
            "      expansion lead). Decompose down the dependency graph before pitching — run the "
            "/needle procedure; do NOT promote a theme to a card.")
        if n_unmeasured:
            log(f"\n    ⚠ {n_unmeasured}/{len(needles)} EARLY candidate(s) have UNMEASURED saturation — "
                "the engine has NOT confirmed they're un-narrated. Run `saturation-scan` before pitching "
                "any as pre-consensus (the critic's lesson: don't mistake un-indexed for un-covered).")
        if broad:
            log(f"\n  ↓ BROAD-CURVE ONLY ({len(broad)}) — single coarse aggregate lead (σ = magnitude, "
                "not grain); never a needle, not headlined: "
                + ", ".join(f"{e['name']} ({e['lead_hits'][0][1]} {e['lead_sig']:.0f}σ)" for e in broad[:6]))
        demoted = [e for e in pc["priced"] if e.get("sat_demoted")]
        if demoted:
            log(f"\n  ↓ HARD-DEMOTED EARLY→PRICED by measured saturation ({len(demoted)}): "
                + ", ".join(f"{e['name']} ({e['saturation']:.2f})" for e in demoted[:6]))
    else:
        log("\n  ★ EARLY — no needle-able candidate today (no FINE-grain capability lead with the crowd "
            "still flat). That is the honest default (the world is mostly priced); keep scanning / widen feeds.")
        if broad:
            log(f"\n  ↓ BROAD-CURVE ONLY ({len(broad)}) — coarse aggregate leads (magnitude, not grain); "
                "never a needle: "
                + ", ".join(f"{e['name']} ({e['lead_hits'][0][1]} {e['lead_sig']:.0f}σ)" for e in broad[:6]))

    if pc["lagging_only"]:
        names = ", ".join(e["name"] for e in pc["lagging_only"][:6])
        log(f"\n  ⚠ LAGGING-ONLY (attention without capability — the decoy/hype tell): {names}")

    return {"survivors": len(surv), "providers": providers,
            "early": len(pc["early"]), "priced": len(pc["priced"]),
            "lagging_only": len(pc["lagging_only"]), "quiet": len(pc["quiet"]),
            "early_names": [e["name"] for e in pc["early"]]}


# ── Stage 3: LLM ticker-proposer → priced-in at scale (cost-gated, propose→confirm) ──
# Maps a discovered EARLY entity → a tradeable ticker PAIR so the (deterministic) consensus gate can
# run without hand-curation. The one fabrication risk — a hallucinated ticker → a fake edge — is held
# by FOUR guards: (1) propose-only into entity_candidates (never auto-commits); (2) every proposed
# symbol is verified against the SEC company_tickers.json (the real universe of public filers) and
# DROPPED if it doesn't resolve to a real CIK; (3) human `entity-accept` before it can feed a bet;
# (4) the consensus math pulls REAL Stooq+SEC data, so an unreal ticker fails the fetch, never fakes.

UA = "predictthefuture research (ruben.stout@edu.escp.eu)"
_SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
_ticker_cache: dict[str, int] | None = None


class InstrumentProposal(BaseModel):
    """One LLM-proposed mapping of a constraint → a tradeable pair. Validated before it's stored."""
    inelastic_sym: str       # US-listed ticker of the inelastic, rent-capturing layer
    inelastic_name: str
    elastic_sym: str         # US-listed ticker of the elastic/obvious layer the market over-prices
    elastic_name: str
    r_fair: float            # fair relative P/S premium the inelastic layer deserves vs the obvious one
    reasoning: str


def _sec_ticker_map(*, log=print) -> dict[str, int]:
    """{TICKER: cik} from SEC's official company list — the real universe of public filers."""
    global _ticker_cache
    if _ticker_cache is not None:
        return _ticker_cache
    req = urllib.request.Request(_SEC_TICKERS, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 keyless public endpoint
        data = json.loads(r.read().decode())
    _ticker_cache = {v["ticker"].upper(): int(v["cik_str"]) for v in data.values()}
    return _ticker_cache


def _resolve_entity(conn: sqlite3.Connection, key: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, canonical_name, domain, note FROM entities "
        "WHERE id=? OR id LIKE ? OR lower(canonical_name)=lower(?)",
        (key, key + "%", key)).fetchone()


def propose_instruments(conn: sqlite3.Connection, entity_key: str, *,
                        provider: str = "deepinfra_keyless", est_cost_cents: int = 0,
                        log=print) -> dict:
    """LLM proposes a ticker pair for an entity → CIK-verify → write propose-only candidates. Gated."""
    from engine.adapters import extract

    ent = _resolve_entity(conn, entity_key)
    if ent is None:
        log(f"no entity matching {entity_key!r}")
        return {"proposed": 0}

    # what fired (leading channels) — give the model the evidence, ask for the rent-migration pair.
    pc = pre_consensus(conn)
    fired = next((e for bucket in (pc["early"], pc["priced"]) for e in bucket if e["eid"] == ent["id"]), None)
    leads = ", ".join(f"{lab} ({prov})" for lab, prov, _ in (fired["lead_hits"][:4] if fired else [])) or "n/a"

    instruction = (
        f"A pre-consensus signal fired for the technology/constraint: \"{ent['canonical_name']}\" "
        f"(domain: {ent['domain'] or 'n/a'}). Leading channels accelerating: {leads}. "
        "Rent accrues to the BINDING, least-substitutable constraint, NOT the obvious endpoint. "
        "Identify the INELASTIC rent-capturing layer (where scarcity concentrates) and the ELASTIC / "
        "obvious layer the market tends to over-price. For EACH, give the single closest US-listed "
        "public-company ticker (real, currently trading) and the company name. Estimate r_fair = the "
        "fair ratio of the inelastic layer's price/sales to the elastic layer's (your honest view; "
        "<1 if the obvious layer deserves a higher multiple on margins). One emit only — the best pair."
    )
    cands = extract.extract_typed(
        conn, text=f"Technology: {ent['canonical_name']}. Context: {ent['note'] or ''}",
        item_model=InstrumentProposal, instruction=instruction,
        provider=provider, est_cost_cents=est_cost_cents,
    )
    if not cands:
        log("  LLM returned no usable proposal (dropped to review). Try --provider minimax if keyless exhausted.")
        return {"proposed": 0}

    tmap = _sec_ticker_map(log=log)
    from engine import entity_candidates as ec
    from engine.schemas import EntityCandidate

    written = 0
    for c in cands:
        p: InstrumentProposal = c.item
        for sym, name, layer, rfair in (
            (p.inelastic_sym, p.inelastic_name, "inelastic", p.r_fair),
            (p.elastic_sym, p.elastic_name, "elastic", p.r_fair),
        ):
            sym = (sym or "").upper().strip()
            cik = tmap.get(sym)
            if cik is None:
                log(f"  ✗ dropped {sym!r} ({layer}) — not a real SEC filer (hallucination guard)")
                continue
            ref_label = f"{sym} [{layer}] {name[:40]}"
            rationale = (f"LLM-proposed {layer} layer for '{ent['canonical_name']}' (CIK {cik}); "
                         f"r_fair≈{rfair:.2f}. {p.reasoning[:240]} "
                         f"[conf {c.confidence:.2f}, tier {c.tier} — propose-only, accept to use].")
            ec._insert_candidate(conn, EntityCandidate(
                entity_id=ent["id"], ref_table="ticker", ref_id=sym, ref_label=ref_label,
                pillar_id=7, generator="llm", relation="same", confidence=min(c.confidence, 0.7),
                rationale=rationale,
            ))
            written += 1
            log(f"  ✓ proposed {sym} [{layer}] — {name[:40]} (CIK {cik}) — entity-accept to confirm")
    conn.commit()
    log(f"\n  {written} ticker candidate(s) proposed (CIK-verified, propose-only). "
        f"Review: `entity-candidates`; confirm: `entity-accept <id>`.")
    return {"proposed": written}


def price_entity(conn: sqlite3.Connection, entity_key: str, *, log=print):
    """Build a ConsensusConfig from an entity's ACCEPTED ticker links → run the priced-in gate."""
    from engine import consensus

    ent = _resolve_entity(conn, entity_key)
    if ent is None:
        log(f"no entity matching {entity_key!r}")
        return None
    links = conn.execute(
        "SELECT ref_id, ref_label, rationale FROM entity_links "
        "WHERE entity_id=? AND ref_table='ticker'", (ent["id"],)).fetchall()
    layers: dict[str, dict] = {}
    for l in links:
        m = re.search(r"\[(inelastic|elastic)\]", l["ref_label"])
        if not m:
            continue
        layers[m.group(1)] = {"sym": l["ref_id"], "label": l["ref_label"]}
    if "inelastic" not in layers or "elastic" not in layers:
        log(f"  {ent['canonical_name']}: needs an accepted inelastic + elastic ticker pair "
            f"(have: {sorted(layers)}). Run discover-instruments then entity-accept the pair.")
        return None

    tmap = _sec_ticker_map(log=log)
    cfg = consensus.ConsensusConfig(
        chain="disc_" + ent["id"][:8],
        thesis=f"{ent['canonical_name']}: rent migrates to the inelastic layer",
        consumable={"sym": layers["inelastic"]["sym"], "cik": tmap.get(layers["inelastic"]["sym"]),
                    "name": layers["inelastic"]["label"]},
        sequencer={"sym": layers["elastic"]["sym"], "cik": tmap.get(layers["elastic"]["sym"]),
                   "name": layers["elastic"]["label"]},
        r_fair_center=1.0, r_fair_log_sd=0.35, threshold=0.20,
        decision_options=["Real edge — the inelastic layer is under-priced",
                          "Market is right — the obvious layer's premium is justified",
                          "Inconclusive — collect more / the pure edge has no clean public play"],
        decision_rec="Discovered pair — treat the verdict as a first read; confirm the layer assignment.",
        edge_note=f"Auto-discovered pair for '{ent['canonical_name']}' (LLM-proposed, human-confirmed). "
                  "The layer assignment + r_fair are estimates — the consensus math itself is real.",
        confound_note="Discovered pair: r_fair is a wide default; verify margins are comparable.",
    )
    return consensus.score_consensus(conn, cfg=cfg, log=log)
