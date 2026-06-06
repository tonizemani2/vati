"""The CLI — the single seam the cockpit shells out to.

init-db / seed / status (foundation) + collect-frontier / detect (Phase 1). Keep this small:
each command is a thin wrapper; the work lives in engine.pillars.* and engine.detector.
"""

from __future__ import annotations

import typer

from datetime import date

from engine import backtest, bet, consensus, cost, db, decisions, detector, discover, entity, experiment, forecast, graph, holdout, hypothesis, indicators, ladder, locator, quality, retro, saturation, seed, significance, universe
from engine.schemas import ForecastOutcome
from engine.pillars import dependency, frontier, metals, power, research

app = typer.Typer(add_completion=False, help="Foresight engine CLI.")


@app.command("init-db")
def init_db() -> None:
    """Create the SQLite tables (idempotent)."""
    conn = db.connect()
    db.init_db(conn)
    tables = db.table_names(conn)
    conn.close()
    typer.echo(f"DB ready at {db.DB_PATH}")
    typer.echo(f"tables: {', '.join(tables)}")


@app.command("seed")
def seed_cmd() -> None:
    """Seed the 9 pillars (idempotent — never overwrites status)."""
    conn = db.connect()
    db.init_db(conn)  # safe if init-db wasn't run yet
    added = seed.seed_pillars(conn)
    total = conn.execute("SELECT COUNT(*) FROM pillars").fetchone()[0]
    conn.close()
    typer.echo(f"seeded {added} new pillar(s); {total} total.")


@app.command("collect-frontier")
def collect_frontier() -> None:
    """Pillar 1: collect OpenAlex concept velocity + arXiv presence (free/keyless, $0)."""
    conn = db.connect()
    db.init_db(conn)
    # exhausting Pillar 1 → mark it in progress (strict-layering visibility, rule 2)
    conn.execute("UPDATE pillars SET status='in_progress' WHERE id=? AND status='untapped'",
                 (frontier.FRONTIER_PILLAR_ID,))
    conn.commit()
    result = frontier.collect(conn, log=typer.echo)
    conn.close()
    typer.echo(
        f"done — openalex: {result['openalex_series']} series / {result['openalex_obs']} obs; "
        f"patents: {result['patent_series']}; grants: {result['grant_series']}; "
        f"benchmarks: {result['benchmark_series']}; arxiv: {result['arxiv_series']} series. "
        f"cost: $0.00"
    )


@app.command("collect-pillars")
def collect_pillars() -> None:
    """Pillars 2/5/6/8: capability curves (OWID) · demand (Wikipedia) · capital (SEC EDGAR) ·
    policy (Federal Register). All keyless. Runs collect → data-audit → detect so the QC gate
    vets every row. Local imports keep this independent of the contended top-level import block.
    """
    from engine.pillars import capability, demand, capital, policy
    conn = db.connect()
    db.init_db(conn)
    for pid, name, mod in [(2, "capability", capability), (5, "demand", demand),
                           (6, "capital", capital), (8, "policy", policy)]:
        conn.execute("UPDATE pillars SET status='in_progress' WHERE id=? AND status='untapped'", (pid,))
        conn.commit()
        typer.echo(f"\n— Pillar {pid}: {name} —")
        out = mod.collect(conn, log=typer.echo)
        typer.echo(f"  {name}: {out}")
    quality.run_audit(conn, log=typer.echo)
    detector.run_detector(conn, log=typer.echo)
    conn.close()


@app.command("collect-forces")
def collect_forces() -> None:
    """FORCES axis ($0, keyless): two channels of the politics/geo force.
    • geopolitics/news — GDELT event-velocity (ATTENTION/LAG; graceful when GDELT throttles).
    • decreed-scarcity — OFAC/BIS Federal-Register rule deltas, typed per cornered input, polarity-
      netted (the LEADING channel: a decree is the scarcity-creating act, ahead of the price).
    Runs collect → data-audit → detect so the QC gate vets every row."""
    from engine.pillars import forces
    conn = db.connect()
    db.init_db(conn)
    typer.echo("— Forces: geopolitics/news (GDELT, LAG) —")
    out = forces.collect(conn, log=typer.echo)
    typer.echo(f"  geo: {out}")
    typer.echo("— Forces: US decreed-scarcity (OFAC/BIS, LEADING) —")
    dec = forces.collect_decreed(conn, log=typer.echo)
    typer.echo(f"  decreed: {dec}")
    typer.echo("— Forces: China decrees (MOFCOM export-control network, LEADING) —")
    cd = forces.collect_china_decrees(conn, log=typer.echo)
    typer.echo(f"  china_decrees: {cd}")
    typer.echo("— Forces: China decree-footprint (Comtrade, CONFIRMATION/LAG) —")
    cn = forces.collect_china_footprint(conn, log=typer.echo)
    typer.echo(f"  china_footprint: {cn}")
    if out.get("series") or dec.get("series") or cd.get("series") or cn.get("series"):
        quality.run_audit(conn, log=typer.echo)
        detector.run_detector(conn, log=typer.echo)
    conn.close()


@app.command("collect-diffusion")
def collect_diffusion() -> None:
    """Pillar 1: the ORTHOGONAL early channel — cross-field diffusion per OpenAlex concept ($0, keyless).

    For every existing works series, build a point-in-time inverse-Simpson effective-field-count
    series (breadth of adoption, not volume) — a technique crossing field A→B fires here before its
    aggregate count saturates. Consumed by universe-run as a second detector channel (OR-recall).
    """
    conn = db.connect()
    db.init_db(conn)
    n = frontier.collect_diffusion(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {n} diffusion series. cost: $0.00")


@app.command("collect-research")
def collect_research(
    sets: list[str] = typer.Option(
        None, "--set", help="OAI set(s) to harvest (default: the seed fields cs/stat/q-bio/cond-mat/eess)."),
    max_pages: int = typer.Option(
        None, help="Cap pages PER SET for a quick slice (each page ~1000 papers). Omit = full gapless harvest."),
    signals_only: bool = typer.Option(
        False, help="Skip the harvest; just (re)compute signals from the existing `papers` table."),
) -> None:
    """Pillar 1 (fine grain): harvest arXiv over time (gapless) -> topic-share/diffusion/talent signals.

    The earliest, finest research grain the coarse-counts blind spot was missing (goal.md #2). Streams
    the official keyless OAI-PMH bulk protocol into the `papers` substrate (resumable; re-run continues),
    then derives three LEADING series per technique the existing detector/FDR/discover funnel consumes
    unchanged. A full seed-field harvest takes a while — safe to interrupt and resume. $0.
    """
    conn = db.connect()
    conn.execute("PRAGMA busy_timeout=300000")   # wait out concurrent writers (other collectors)
    try:
        db.init_db(conn)
    except Exception as e:  # noqa: BLE001 — a concurrent schema migration can race init_db's
        # check-then-ALTER (duplicate-column) or hold a lock; the tables already exist, so proceed.
        typer.echo(f"  · init_db skipped (concurrent migration: {type(e).__name__}: {e}); continuing")
    out = research.collect(conn, sets=list(sets) if sets else None, max_pages=max_pages,
                           signals_only=signals_only, log=typer.echo)
    conn.close()
    typer.echo(
        f"done — harvested {out['harvested']} this run; {out['papers_total']} papers total; "
        f"{out['series']} signal series ({out.get('share', 0)} share / {out.get('breadth', 0)} breadth"
        f" / {out.get('talent', 0)} talent). cost: $0.00"
    )


@app.command("collect-capex")
def collect_capex() -> None:
    """Pillar 6: per-company capex acceleration from SEC XBRL — the capital-flow elasticity tell.

    Actual $ incumbents pour into capacity, per fiscal year, across constraint layers (elastic
    compute vs inelastic grid/power vs bio). Capital flooding a layer = it turns elastic = where the
    bottleneck WON'T be. Keyless primary XBRL (SEC fair-access UA), $0. Runs collect → audit → detect.
    """
    from engine.pillars import capital
    conn = db.connect()
    db.init_db(conn)
    conn.execute("UPDATE pillars SET status='in_progress' WHERE id=6 AND status='untapped'")
    conn.commit()
    out = capital.collect_capex(conn, log=typer.echo)
    quality.run_audit(conn, log=lambda *_a, **_k: None)
    detector.run_detector(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {out['series']} capex series / {out['obs']} obs. cost: $0.00")


@app.command("collect-thesis-revenue")
def collect_thesis_revenue() -> None:
    """Pillar 6: annual revenue (SEC XBRL) for the inelastic-layer players that RESOLVE survived theses.

    The rent-capturing public company each constraint-migration hypothesis names (Centrus enrichment,
    West Pharma injection consumables) — revenue = rent landing at that layer, the point-in-time series
    a forward card resolves on. Keyless primary XBRL, $0. Runs collect → audit → detect.
    """
    from engine.pillars import capital
    conn = db.connect()
    db.init_db(conn)
    out = capital.collect_thesis_revenue(conn, log=typer.echo)
    quality.run_audit(conn, log=lambda *_a, **_k: None)
    detector.run_detector(conn, log=lambda *_a, **_k: None)
    conn.close()
    typer.echo(f"done — {out['series']} revenue series / {out['obs']} obs. cost: $0.00")


@app.command("collect-slow")
def collect_slow() -> None:
    """The SLOW-constraint aperture (execution §7/§10): demographics · aging · water · land.

    The acceleration detector is blind to constraints that bind by slowly crossing a mechanism
    threshold (a workforce peaking, water/arable per capita falling). This collects keyless World Bank
    WDI series and runs the THRESHOLD detector (years-to-bind, not σ). Runs collect → audit. $0.
    """
    from engine.pillars import slow
    conn = db.connect()
    db.init_db(conn)
    out = slow.collect(conn, log=typer.echo)
    quality.run_audit(conn, log=lambda *_a, **_k: None)
    detector.run_detector(conn, log=lambda *_a, **_k: None)
    conn.close()
    typer.echo(f"done — {out['series']} slow-constraint series, {out['binding']} binding now. cost: $0.00")


@app.command("forecast-slow")
def forecast_slow() -> None:
    """Turn the approaching slow constraints into immutable forward ForecastCards (scheduled bindings).

    'Does [metric] cross [threshold] by [year]?' — point-in-time falsifiable, P from the drift-MC over
    the WDI trend (not a story). Run after collect-slow. Immutable (rule 7); idempotent on the question. $0.
    """
    from engine.pillars import slow
    conn = db.connect()
    db.init_db(conn)
    out = slow.forecast_crossings(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {out['cards']} slow-constraint forecast cards. cost: $0.00")


@app.command("collect-procurement")
def collect_procurement() -> None:
    """Pillar 6: federal procurement obligations per product class (USAspending, keyless).

    The measurable DEMAND that resolves a thesis whose inelastic layer has no public pure-play —
    ammunition + explosives/propellant federal contract $/fiscal-year pulls on the energetics supply
    the re-armament thesis names. Keyless USAspending v2 API, $0. Runs collect → audit → detect.
    """
    from engine.pillars import capital
    conn = db.connect()
    db.init_db(conn)
    out = capital.collect_procurement(conn, log=typer.echo)
    quality.run_audit(conn, log=lambda *_a, **_k: None)
    detector.run_detector(conn, log=lambda *_a, **_k: None)
    conn.close()
    typer.echo(f"done — {out['series']} procurement series / {out['obs']} obs. cost: $0.00")


@app.command("collect-patents")
def collect_patents() -> None:
    """Pillar 1: refresh patent filing-velocity series (Google Patents, via resi proxy).

    Standalone entry point (was only reachable via collect-frontier). Google blocks DC+repeat IPs,
    so this prefers the residential proxy (Evomi) with a rotating IP per call. Runs collect →
    data-audit → detect. $0/keyless; resi bandwidth is metered → cost-gated before each batch.
    """
    conn = db.connect()
    db.init_db(conn)
    conn.execute("UPDATE pillars SET status='in_progress' WHERE id=? AND status='untapped'",
                 (frontier.FRONTIER_PILLAR_ID,))
    conn.commit()
    n = frontier.collect_patents(conn, log=typer.echo)
    quality.run_audit(conn, log=lambda *_a, **_k: None)
    detector.run_detector(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {n} patent series. cost: $0.00")


@app.command("collect-citations")
def collect_citations() -> None:
    """Pillar 1: citation-velocity channel (Semantic Scholar open graph, via DC proxy).

    Citations RECEIVED per year by each term's seminal corpus. Built as a candidate recall-fix
    (hypothesis: it leads the publication-count curve) but the data DISCONFIRMED that — it LAGS
    (papers must exist before being cited) and plateaus to silent at maturity; its one virtue is
    staying silent on fizzles the count channel false-positives on (a confirmer, not a lead signal).
    See the `citation-velocity-lags` memory / execution.md §3. Self-collected through the proxy
    (rotating IP). Runs collect → data-audit → detect. $0/keyless (DC bandwidth sub-cent).
    """
    conn = db.connect()
    db.init_db(conn)
    conn.execute("UPDATE pillars SET status='in_progress' WHERE id=? AND status='untapped'",
                 (frontier.FRONTIER_PILLAR_ID,))
    conn.commit()
    n = frontier.collect_citation_velocity(conn, log=typer.echo)
    quality.run_audit(conn, log=lambda *_a, **_k: None)
    detector.run_detector(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {n} citation-velocity series. cost: $0.00")


@app.command("collect-power")
def collect_power() -> None:
    """Pillar 4: collect the AI-power inelastic-layer price series (FRED transformer/switchgear PPI, $0).

    The 2nd domain's testable, point-in-time supply-elasticity signal — the falsifiable series the
    hypothesis gate demanded for the survived AI-buildout→electrical-interconnect thesis. Keyless.
    """
    conn = db.connect()
    db.init_db(conn)
    out = power.collect(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {out['series']} series / {out['obs']} obs. cost: $0.00")


@app.command("collect-metals")
def collect_metals() -> None:
    """Pillar 4 (metals/mining): collect the copper-mine supply-QUANTITY series and close the drill loop.

    The graph's drill-score named copper-mine supply the #1 deep-data target (high pressure × thin
    coverage). This collects the measured mine-output series (keyless FRED G.17), QC-audits it,
    attaches it to the copper-mine node, then re-flows the connected world — so you watch the
    drill-score collapse as the data the graph asked for arrives. $0.
    """
    conn = db.connect()
    db.init_db(conn)
    out = metals.collect(conn, log=typer.echo)
    # QC the new series so coverage reflects a MEASURED build series (health), not a parameter.
    quality.run_audit(conn, log=lambda *_a, **_k: None)
    # Attach the measured copper-mine output to the node the drill-score named (closes the loop).
    graph.set_build_series(conn, chain=metals.METALS_CHAIN, node_name=metals.COPPER_MINE_NODE,
                           series_id=out["build_series_id"], log=typer.echo)
    # Re-flow the connected world; show the drill-score now that copper-mine is measured.
    chains = ("ai_power", "metals")
    prop = graph.propagate(conn, chain="ai_power", chains=chains, shock=graph.AI_POWER_SHOCK)
    drills = graph.drill_targets(conn, prop, chain="ai_power", chains=chains)
    typer.echo("\nDrill targets after attaching the measured copper-mine series:")
    for d in drills[:5]:
        typer.echo(f"  {d.drill_score:>5.2f}  {d.name[:44]:<44} [{d.chain}]  cov {d.coverage:>3.0%}  · {d.why}")
    conn.close()
    typer.echo(f"\ndone — {out['series']} series / {out['obs']} obs. cost: $0.00")


@app.command("collect-dependency")
def collect_dependency() -> None:
    """Pillar 3 (dependency graph): collect UN Comtrade import-dependency series — value + supplier HHI.

    Opens the most-starved value layer (dependency graph was at 0 series). For each critical input the
    world graph names (refined copper, GOES steel, transformers, rare earths) it measures US import
    VALUE (magnitude) and partner CONCENTRATION (fragility) from keyless Comtrade, QC-audits them, then
    runs the frozen detector so you see which dependencies are ACCELERATING (rising concentration =
    deepening chokepoint) vs the deliberate elastic contrast (transformers, low HHI, should stay
    silent). $0 keyless.
    """
    conn = db.connect()
    conn.execute("PRAGMA busy_timeout=300000")   # wait out concurrent writers (background harvest)
    db.init_db(conn)
    out = dependency.collect(conn, log=typer.echo)
    # QC the new series so they pass the data-health gate before the detector reads them.
    quality.run_audit(conn, log=lambda *_a, **_k: None)
    # Run the frozen detector — the payoff: rising-concentration chokepoints fire, elastic stays silent.
    typer.echo("\nDetector over the dependency layer (frozen k — rising import-concentration = fires):")
    detector.run_detector(conn, log=typer.echo)
    conn.close()
    typer.echo(f"\ndone — {out['series']} series / {out['obs']} obs. cost: $0.00")


@app.command("detect")
def detect_cmd(
    k: float = typer.Option(detector.DEFAULT_K, help="σ threshold to fire"),
    require_qc: bool = typer.Option(True, help="Skip series flagged 'fail' by data-audit (the QC gate)."),
) -> None:
    """Run the domain-agnostic acceleration detector over all series; write verdicts back."""
    conn = db.connect()
    db.init_db(conn)
    detector.run_detector(conn, k=k, require_qc=require_qc, log=typer.echo)
    conn.close()


@app.command("significance")
def significance_cmd(
    k: float = typer.Option(detector.DEFAULT_K, help="σ threshold (match the detect run)."),
    q: float = typer.Option(significance.DEFAULT_Q, help="Benjamini-Hochberg false-discovery level."),
    m: int = typer.Option(significance.DEFAULT_M, help="Surrogate count (the p floor is 1/(M+1)). Higher = finer, slower."),
) -> None:
    """Component 4b: the look-elsewhere correction over the detector (run AFTER `detect`).

    For every scanned series, build an empirical null (early trend continues + bootstrapped early
    noise), run the FROZEN detector on M surrogates → an honest p-value, then Benjamini-Hochberg
    across the whole scan → which fires survive multiple testing + the expected false-discovery count.
    Replaces the Gaussian-σ fantasy (the "43345σ" tell) with p + a denominator. $0, stdlib only.
    """
    conn = db.connect()
    db.init_db(conn)
    significance.run_significance(conn, k=k, q=q, m=m, log=typer.echo)
    conn.close()
    typer.echo("cost: $0.00")


@app.command("discover")
def discover_cmd(
    rescan: bool = typer.Option(False, help="Re-run the full funnel (audit→detect→significance) first. Slow."),
    k: float = typer.Option(detector.DEFAULT_K, help="σ threshold (only used with --rescan)."),
    q: float = typer.Option(significance.DEFAULT_Q, help="BH-FDR level (only used with --rescan)."),
    m: int = typer.Option(significance.DEFAULT_M, help="Surrogate count (only used with --rescan)."),
) -> None:
    """Component 17: the OPEN, industry-agnostic discovery scan — find where the future is, gated.

    Surfaces the FDR-surviving signals across ALL feeds, then the PRE-CONSENSUS cross-reference:
    which technologies fire on a LEADING channel (capability/science/supply) while LAGGING channels
    (attention/capital/policy) are still flat = EARLY (real + not yet priced) vs PRICED vs the
    attention-only decoys. Most days EARLY is short or empty — that honest default is the point.
    Read-only by default ($0); --rescan re-runs the gates first. cost: $0.00.
    """
    conn = db.connect()
    db.init_db(conn)
    discover.run_scan(conn, k=k, q=q, m=m, rescan=rescan, log=typer.echo)
    conn.close()
    typer.echo("\ncost: $0.00")


@app.command("discover-instruments")
def discover_instruments(
    entity: str = typer.Argument(..., help="Entity id (8-char ok) or canonical name of a discovered signal."),
    provider: str = typer.Option("deepinfra_keyless", help="LLM provider (free keyless first; 'minimax' if it exhausts)."),
    est_cost_cents: int = typer.Option(0, help="Estimated cost for a keyed provider (cost-gated; 0 for keyless)."),
) -> None:
    """Stage 3 (propose): LLM proposes a tradeable ticker PAIR for a discovered constraint.

    The pair is CIK-verified against the SEC filer list (hallucinations dropped automatically) and
    written propose-only to entity_candidates. Confirm with `entity-accept <id>`, then `discover-price`.
    Free keyless by default; a keyed provider is cost-gated. Never auto-commits a bet.
    """
    conn = db.connect()
    db.init_db(conn)
    discover.propose_instruments(conn, entity, provider=provider, est_cost_cents=est_cost_cents,
                                 log=typer.echo)
    conn.close()


@app.command("discover-price")
def discover_price(
    entity: str = typer.Argument(..., help="Entity id (8-char ok) or canonical name with an accepted ticker pair."),
) -> None:
    """Stage 3 (gate): run the priced-in consensus gate on a discovered entity's accepted ticker pair.

    Reads the human-accepted inelastic/elastic ticker links, builds a ConsensusConfig, and runs the
    deterministic consensus gate on REAL Stooq + SEC data → edge | priced_in | inconclusive. cost: $0.00.
    """
    conn = db.connect()
    db.init_db(conn)
    score = discover.price_entity(conn, entity, log=typer.echo)
    conn.close()
    if score is None:
        raise typer.Exit(code=1)
    typer.echo("\ncost: $0.00")


@app.command("saturation-scan")
def saturation_scan(
    limit: int = typer.Option(12, help="How many of the top EARLY candidates to measure."),
) -> None:
    """Component 17b: MEASURE how known each EARLY discovery candidate already is (keyless, $0).

    For every EARLY entity it runs a keyless web search over public coverage (trade press / regulatory
    / finance — the channels the indexed lag-set misses) and scores narrative saturation. A 'priced/
    known' verdict HARD-DEMOTES the candidate EARLY→PRICED on the next scan: if it's already in the
    trade press, it is not pre-consensus. The honest fix for 'least-seen' being asserted, not measured.
    """
    conn = db.connect()
    db.init_db(conn)
    out = saturation.score_early_board(conn, limit=limit, log=typer.echo)
    conn.close()
    typer.echo(f"\ndone — {out['scored']} scored, {out['demoted']} demoted. cost: $0.00")


@app.command("saturation-topic")
def saturation_topic(
    topic: str = typer.Argument(..., help="A topic/thesis phrase to measure public-coverage saturation for."),
) -> None:
    """Measure narrative saturation for one ad-hoc topic — is this thesis already widely covered?

    Keyless web search ($0) → transparent volume×authority×recency score with the hit URLs cited. Use
    before pitching any thesis as 'pre-consensus': it returns 'priced/known' if the crowd is already here.
    """
    conn = db.connect()
    db.init_db(conn)
    s = saturation.score_topic(conn, topic, log=typer.echo)
    typer.echo(f"\n  → saturation {s.saturation:.2f} ({s.tier}) · {s.verdict}")
    typer.echo(f"  {s.rationale}")
    for u in s.evidence_urls[:6]:
        typer.echo(f"    · {u}")
    conn.close()
    typer.echo("\ncost: $0.00")


@app.command("consensus-eye")
def consensus_eye(
    claim: str = typer.Argument(..., help="The structural claim, in plain words (the sector/macro reorganization)."),
    ticker: str = typer.Option(None, help="OPTIONAL US ticker, only to add the price channel (financial-optional)."),
) -> None:
    """Is this structural forecast already priced — at the RIGHT altitude (not just a stock multiple)?

    Multi-channel, physical-primary: (1) NARRATIVE saturation, (2) the CONSENSUS-FORECAST channel — have
    the official forecasters (IEA/IMF/banks) already projected it? — and (3) an OPTIONAL price run-up if a
    ticker is given. A structural call with no instrument is still valid; price is never required. Keyless, $0.
    """
    conn = db.connect()
    db.init_db(conn)
    sat = saturation.score_topic(conn, claim, log=typer.echo)
    fc = saturation.consensus_forecast(conn, claim, log=typer.echo)
    price = consensus.price_runup(conn, ticker) if ticker else None
    if price:
        typer.echo(f"  price: {price['rationale']}")
    # HONEST ASYMMETRY (the calibration fix): the eye RELIABLY detects PRICED, it can NEVER certify
    # pre-consensus (keyless search is blind to sell-side / specialist press). So 'all quiet' is
    # UNCONFIRMED — your call, not a green light. PRICED if narrative known OR forecasters hold the base
    # case OR specialist/trade press covers it ('covered'); PARTLY on a lone forecaster / a hot price.
    priced = sat.verdict == "priced/known" or fc["verdict"] in ("priced", "covered")
    partly = fc["verdict"] == "partly" or bool(price and price.get("hot"))
    overall = "PRICED" if priced else ("PARTLY-PRICED" if partly else "UNCONFIRMED — judge in-session")
    typer.echo(f"\n  ═══ {overall} ═══")
    typer.echo(f"  narrative: {sat.tier} ({sat.saturation:.2f}) · forecasters/coverage: {fc['verdict']} "
               f"({fc['n_forecasters']}f/{fc.get('n_covered', 0)} broad) · "
               f"price: {(('hot' if price['hot'] else 'quiet') if price and price.get('measured') else 'n/a')}")
    if not priced and not partly:
        typer.echo("  ⚠ UNCONFIRMED ≠ pre-consensus: keyless search can't see paywalled sell-side / specialist "
                   "notes. If the obvious layer is covered, test the layer BENEATH it; then JUDGE in-session.")
    typer.echo("  → the eye certifies PRICED, never pre-consensus; physical metric is what scores, price is optional.")
    conn.close()
    typer.echo("\ncost: $0.00")


@app.command("data-audit")
def data_audit(
    strict: bool = typer.Option(False, help="Exit non-zero if any series fails QC (gate a collect→audit→detect chain)."),
) -> None:
    """Component 16: audit every series for freshness/completeness/validity/reconciliation/provenance.

    Writes a per-series health verdict; the detector then skips 'fail' series and forecasts refuse a
    'fail' seed — stale/incomplete data cannot silently feed a bet. Run order: collect → data-audit → detect.
    """
    conn = db.connect()
    db.init_db(conn)
    out = quality.run_audit(conn, log=typer.echo)
    conn.close()
    if strict and out["fail"] > 0:
        raise typer.Exit(code=1)


@app.command("backtest")
def backtest_cmd(
    cutoff: int = typer.Option(backtest.DEFAULT_CUTOFF, help="Cap data at this year; grade on what came after."),
    k: float = typer.Option(detector.DEFAULT_K, help="σ threshold for both firing and breakout."),
    target: str = typer.Option("gain_share", help="What to grade against: 'gain_share' (thesis) or 'acceleration'."),
    sweep: bool = typer.Option(False, help="Rolling-origin sweep (2008–2016): pooled lift, Fisher-exact p, honest LOCO Brier."),
) -> None:
    """Time-machine: blind detector calls at `cutoff`, graded against the known future (proof)."""
    conn = db.connect()
    db.init_db(conn)
    if sweep:
        backtest.run_sweep(conn, k=k, target=target, log=typer.echo)
    else:
        backtest.run_backtest(conn, cutoff=cutoff, k=k, target=target, log=typer.echo)
    conn.close()


@app.command("adapter-smoke")
def adapter_smoke() -> None:
    """Phase 2: smoke-test every adapter (cost gate, Exa, pdftotext, LLM). No spend."""
    from engine.adapters import smoke

    results = smoke.run_smoke()
    for name, ok, detail in results:
        typer.echo(f"  [{'PASS' if ok else 'FAIL'}] {name:<26} {detail}")
    passed = sum(1 for _, ok, _ in results if ok)
    typer.echo(f"{passed}/{len(results)} adapters passed.")
    if passed != len(results):
        raise typer.Exit(code=1)


@app.command("search")
def search_cmd(
    query: list[str] = typer.Argument(..., help="One or more search queries."),
    num: int = typer.Option(5, help="Results per query."),
) -> None:
    """Real keyless web search (Exa → DDG). Logs a $0 'auto' cost-ledger row before running."""
    from engine.adapters import search as search_adapter

    conn = db.connect()
    db.init_db(conn)
    out = search_adapter.search_multi(conn, query, num_results=num)
    conn.close()
    for q, results in out.items():
        typer.echo(f"\n# {q}  ({len(results)} hits)")
        for r in results:
            typer.echo(f"  - {r.title[:80]}  [{r.source}]")
            typer.echo(f"    {r.url}")


@app.command("answer")
def answer_cmd(
    question: list[str] = typer.Argument(..., help="A specific, non-interpretive factual question (a number/spec)."),
    steps: int = typer.Option(3, help="Max search/fetch rounds (1 = single-pass; >1 = multi-step agentic)."),
    proxy: str = typer.Option(None, help="Optional proxy URL to scale keyless LLM calls past per-IP limits."),
) -> None:
    """Keyless agentic hard-NUMBER lookup: search → (refine / drill into a source incl. PDFs) → ONE cited figure.

    Multi-step when needed, single-step when not — stops the instant it can answer. For settled,
    non-interpretive numbers only (specs, capacities, published counts) — never forecasts or opinion
    (that reasoning stays in-session). Always prints the source URL to verify against; degrades to the
    raw top hits rather than fabricate if the keyless LLM is down. $0 keyless.
    """
    from engine.adapters import answer as answer_adapter

    q = " ".join(question)
    conn = db.connect()
    db.init_db(conn)
    a = answer_adapter.find_number(conn, q, max_steps=steps, proxy=proxy, log=typer.echo)
    conn.close()
    typer.echo(f"\nQ: {a.question}")
    typer.echo(f"A: {a.value or '— not found —'}   ({a.steps} step{'s' if a.steps != 1 else ''})")
    typer.echo(f"   source: {a.source_url or 'n/a'}   confidence: {a.confidence}")
    if a.note:
        typer.echo(f"   note: {a.note}")
    if a.value is None and a.hits:
        typer.echo("   top hits (manual read):")
        for r in a.hits[:5]:
            typer.echo(f"     - {r.title[:70]}  {r.url}")
    typer.echo("cost: $0.00")


@app.command("approve-cost")
def approve_cost(
    ledger_id: str = typer.Argument(..., help="cost_ledger id to approve."),
    by: str = typer.Option(..., "--by", help="Who is approving (the human)."),
) -> None:
    """Approve a pending spend the cost gate blocked (rule 3)."""
    conn = db.connect()
    db.init_db(conn)
    ok = cost.approve(conn, ledger_id, by)
    conn.close()
    typer.echo(f"approved {ledger_id}" if ok else f"no pending row with id {ledger_id}")


@app.command("forecast-seed")
def forecast_seed() -> None:
    """Write the first ForecastCards from the scRNA-seq detector hit (reasoned in-session, $0)."""
    conn = db.connect()
    db.init_db(conn)
    out = forecast.seed_forecasts(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {out['created']} card(s) created, {out['resolved']} resolved. cost: $0.00")


@app.command("forecast-batch")
def forecast_batch() -> None:
    """Author the dozen FORWARD structural calls (the starved-instrument deliverable).

    Each is a one-layer-deeper, physical-primary structural forecast: P + 80% interval + a dated
    resolution metric + kill-criteria, adversarially challenged in-session. Idempotent on the
    question; several seed off real in-DB series so driver-status can track them now. $0."""
    conn = db.connect()
    db.init_db(conn)
    out = forecast.seed_forward_batch(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {out['created']} created, {out.get('superseded', 0)} superseded "
               f"(stock-pick → physical-primary), {out['skipped']} already present. cost: $0.00")


@app.command("scenario-seed")
def scenario_seed() -> None:
    """Author the forecast WEBS — linked, confidence-weighted scenario trees instead of one
    extrapolated statement. Currently: HVDC deployment · injectable delivery (GLP-1/biologics) ·
    ex-China rare-earth/critical-input refining · US electrification labour. Idempotent, $0."""
    conn = db.connect()
    db.init_db(conn)
    out = forecast.seed_all_webs(conn, log=typer.echo)
    total = out["created"]
    conn.close()
    typer.echo(f"done — {total} web node(s) written. cost: $0.00")


@app.command("scenario")
def scenario_show(scenario_id: str) -> None:
    """Print a forecast WEB as a tree: each node with its CONDITIONAL P and its MARGINAL P
    (= product of conditionals down its path)."""
    conn = db.connect()
    db.init_db(conn)
    tree = forecast.scenario_tree(conn, scenario_id)
    conn.close()

    def render(node: dict, depth: int) -> None:
        pad = "  " * depth
        tag = "" if depth == 0 else f"cond {node['conditional_p']:.0%} · "
        typer.echo(f"{pad}[{node['marginal_p']:.0%}] {tag}{node['question'][:96]}")
        for k in node["children"]:
            render(k, depth + 1)

    render(tree, 0)


@app.command("webs-v2")
def webs_v2() -> None:
    """Act on the 44/100 external review: author the 4 corrected webs (re-priced / MECE-fixed) + the
    new SiC / power-semiconductor web, supersede the v1 webs (rule 7), re-point the belief-net by
    question. Idempotent, $0."""
    conn = db.connect()
    db.init_db(conn)
    out = forecast.rebuild_v2(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {out['webs_created']} v2 node(s) + {out['edges']} belief edge(s). cost: $0.00")


@app.command("belief-seed")
def belief_seed() -> None:
    """Author the cross-thesis BELIEF-NET edges — one web's resolution shifting another web's P, where
    two webs share an inelastic input. Idempotent, $0."""
    conn = db.connect()
    db.init_db(conn)
    out = forecast.seed_belief_edges(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {out['created']} belief edge(s) written. cost: $0.00")


@app.command("belief-net")
def belief_net_show(resolve: list[str] = typer.Option(None, "--resolve", help="card-id-or-prefix=true/false")) -> None:
    """Show the belief-net: each cross-web edge with the target's baseline P and — if you pass
    --resolve <from>=true/false — the target's CONDITIONAL view. Pure read; never mutates a card.
    e.g. `belief-net --resolve db8b6288=true` (ex-China magnets bind) shifts the linked roots."""
    resolved = {}
    for r in (resolve or []):
        if "=" not in r:
            raise typer.BadParameter("use card=true / card=false")
        k, v = r.rsplit("=", 1)
        resolved[k.strip()] = v.strip().lower() in ("true", "t", "1", "yes")
    conn = db.connect()
    db.init_db(conn)
    net = forecast.belief_net(conn, resolved=resolved)
    conn.close()

    for e in net["edges"]:
        arrow = "↑" if e["sign"] == 1 else "↓"
        shift = "" if e["state"] == "prior" else f"  ⇒ {e['state']}: {e['p_to_baseline']:.0%} → {e['view']:.0%}"
        typer.echo(f"[{e['from_id'][:8]}] {e['from_q']}…  (P {e['p_from']:.0%})")
        typer.echo(f"   {arrow}{'+' if e['sign']==1 else '−'} → [{e['to_id'][:8]}] {e['to_q']}…  base {e['p_to_baseline']:.0%}{shift}")
        typer.echo(f"      ↳ {e['mechanism'][:110]}…")
    if net["islands"]:
        typer.echo("\nislands (no cross-web edge — honestly decoupled):")
        for i in net["islands"]:
            typer.echo(f"   ◦ [{i['root_id'][:8]}] {i['q']}…")


@app.command("constraint-cards")
def constraint_cards() -> None:
    """Write the GRAPH-DERIVED constraint cards (redteam #2): probability = P(bottleneck) from the
    supply-graph propagation, magnitude = the supply-gap CI — NOT a trend extrapolation. Pairs with
    the demand-count cards (whose probability is the series-growth MC). $0, idempotent."""
    conn = db.connect()
    db.init_db(conn)
    out = graph.seed_constraint_cards(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {out['created']} constraint card(s) written. cost: $0.00")


@app.command("ladder-run")
def ladder_run(
    horizon: int = typer.Option(ladder.H_YEARS, help="Rung horizon in years (intermediate metrics are annual)."),
    rebuild: bool = typer.Option(False, "--rebuild", help="Wipe existing rungs and rebuild — re-measure calibration cleanly after a method change."),
    point_estimate: bool = typer.Option(False, "--point-estimate", help="Use the old plug-in MC (no parameter-uncertainty tails) — for A/B against honest tails."),
    no_sharpen: bool = typer.Option(False, "--no-sharpen", help="Issue the univariate MC persistence P (calibrated, AUC ~0.5) instead of the sharpened model — for A/B against discrimination."),
) -> None:
    """The fast-resolution ladder (redteam #3): rolling-origin short-horizon micro-forecasts on EVERY
    QC-passing series, Brier-scored on resolution NOW. Calibrated (full-history drift + honest tails)
    AND discriminating (sharpen.py logistic, leak-free expanding window, AUC ~0.68). $0."""
    conn = db.connect()
    db.init_db(conn)
    out = ladder.run_ladder(conn, h=horizon, honest_tails=not point_estimate,
                            sharpen_p=not no_sharpen, clear=rebuild, log=typer.echo)
    conn.close()
    typer.echo(f"done — {out['new']} rungs ({out['resolved_now']} resolved this run); "
               f"{out['n_resolved']} total resolved. cost: $0.00")


def _echo_driver_health(h: dict) -> None:
    """Print one card/hypothesis's live driver verdict (the cockpit is the real view)."""
    sig = "—" if h["signal"] is None else f"{h['signal']:.0%}"
    head = h.get("title", h.get("card_id") or h.get("hypothesis_id"))
    typer.echo(f"\n{head}")
    typer.echo(f"  driver signal {sig}  ·  {h['n']} driver(s): {h['n_on_track']} on-track, "
               f"{h['n_approaching']} approaching, {h['n_falsified']} falsified, {h['n_no_data']} no-data "
               f"→ worst: {h['worst_status'].upper()}")
    for d in h["drivers"]:
        ms = "—" if d["margin_sigma"] is None else f"{d['margin_sigma']:+.2f}σ"
        val = "—" if d["value"] is None else f"{d['value']:g}"
        arrow = {"fails_below": ">=", "fails_above": "<="}[d["direction"]]
        typer.echo(f"    [{d['status']:<11}] {d['label'][:44]:<44} {val} {arrow} {d['threshold']:g} "
                   f"(margin {ms}, trend {d['trend']})")


@app.command("driver-link")
def driver_link(
    series: str = typer.Option(..., help="The leading-indicator series id this driver watches."),
    threshold: float = typer.Option(..., help="The falsification level (a kill-criterion's numeric bound)."),
    direction: str = typer.Option(..., help="'fails_below' | 'fails_above' — which way the metric trips the kill-criterion."),
    confirm: str = typer.Option(..., help="'up' | 'down' — which trend direction moves TOWARD confirmation."),
    card: str = typer.Option(None, help="Forecast card id this driver hangs off (xor --hypothesis)."),
    hypothesis_id: str = typer.Option(None, "--hypothesis", help="Hypothesis id this driver hangs off (xor --card)."),
    kill_index: int = typer.Option(None, "--kill-index", help="Which kill_criteria[i] this proxies (provenance only)."),
    note: str = typer.Option("", help="Why this series proxies this kill-criterion (GIGO)."),
) -> None:
    """Link one kill-criterion / driver to a series — forecast the DRIVERS, not the endpoint.

    The judgment (which series proxies which kill-criterion) is Claude's, in-session; this only records
    the link + threshold. Observe-only — it never edits the immutable card (rule 7). $0."""
    conn = db.connect()
    db.init_db(conn)
    out = indicators.link_driver(
        conn, series_id=series, threshold=threshold, direction=direction, confirm_dir=confirm,
        card_id=card, hypothesis_id=hypothesis_id, kill_index=kill_index, note=note)
    frontier._log_cost(conn, "driver_link", "in_session", 1.0)
    conn.commit()
    conn.close()
    typer.echo(f"{'updated' if out['updated'] else 'linked'} driver {out['id'][:8]}. cost: $0.00")


@app.command("driver-status")
def driver_status(
    card: str = typer.Option(None, help="Show one card's driver health (8-char id ok)."),
    hypothesis_id: str = typer.Option(None, "--hypothesis", help="Show one hypothesis's driver health."),
) -> None:
    """The leading-indicator scoreboard: are the drivers of our live calls trending toward confirmation
    or falsification NOW — years before the slow resolution date? Observe-only. $0."""
    conn = db.connect()
    db.init_db(conn)
    if card or hypothesis_id:
        _echo_driver_health(indicators.card_driver_health(conn, card_id=card, hypothesis_id=hypothesis_id))
    else:
        rows = indicators.all_driver_health(conn)
        if not rows:
            typer.echo("No drivers linked yet. Link one: "
                       "`driver-link --card <id> --series <id> --threshold <x> --direction fails_below --confirm up`.")
        for h in rows:
            _echo_driver_health(h)
    conn.close()


@app.command("driver-seed")
def driver_seed() -> None:
    """Link the obvious driver for the live scRNA-seq FORWARD card: its kill-criterion 'FY2026 awards
    < 6,500' → the seed series itself (awards/year, confirming = up). Idempotent; demonstrates the
    tracker end-to-end like `hypothesis-seed`. $0."""
    conn = db.connect()
    db.init_db(conn)
    row = conn.execute(
        "SELECT id, seed_series_id FROM forecast_cards WHERE question LIKE 'By FY2026,%single-cell RNA-seq%' "
        "AND superseded_by IS NULL ORDER BY created_at DESC LIMIT 1").fetchone()
    if row is None or not row["seed_series_id"]:
        typer.echo("scRNA-seq FORWARD card not found (run `seed-forecasts` first). nothing linked.")
        conn.close()
        return
    out = indicators.link_driver(
        conn, series_id=row["seed_series_id"], threshold=6500, direction="fails_below", confirm_dir="up",
        card_id=row["id"], kill_index=0,
        note="Kill-criterion 0 ('FY2026 awards < 6,500 — demand acceleration stalled') made machine-"
             "readable: the seed NIH-grant series IS the demand-leg leading indicator; rising = confirming.")
    frontier._log_cost(conn, "driver_link", "in_session", 1.0)
    conn.commit()
    h = indicators.card_driver_health(conn, card_id=row["id"])
    conn.close()
    typer.echo(f"{'updated' if out['updated'] else 'linked'} driver on card {row['id'][:8]}.")
    _echo_driver_health(h)
    typer.echo("\ncost: $0.00")


@app.command("forecast-add")
def forecast_add(
    question: str = typer.Option(..., help="The binary, point-in-time question with a clear resolution."),
    prob: float = typer.Option(..., help="P of the binary resolving true (0..1)."),
    resolution_date: str = typer.Option(..., help="ISO date when we'll know (YYYY-MM-DD)."),
    kill: list[str] = typer.Option(..., "--kill", help="A kill-criterion (repeat for several). Required."),
    rationale: str = typer.Option(..., help="The reasoning — base rate + decomposition."),
    ci_low: float = typer.Option(None, help="80% credible-interval low on the central quantity."),
    ci_high: float = typer.Option(None, help="80% credible-interval high."),
    ci_unit: str = typer.Option(None, help="Unit of the credible interval."),
    seed_series: str = typer.Option(None, help="series id this forecast grew from."),
    pillar: list[int] = typer.Option([], "--pillar", help="Pillar id(s) used."),
    source: list[str] = typer.Option([], "--source", help="Source id(s) cited."),
    saturation: float = typer.Option(None, help="Measured narrative-saturation at issue (0..1) — sets the consensus-echo tag (plan.md #6)."),
) -> None:
    """Write a new immutable ForecastCard via the CLI seam (rule 7 — never edited, only superseded)."""
    conn = db.connect()
    db.init_db(conn)
    card = forecast.create_card(
        conn, question=question, probability=prob,
        resolution_date=date.fromisoformat(resolution_date),
        ci_low=ci_low, ci_high=ci_high, ci_unit=ci_unit, seed_series_id=seed_series,
        rationale=rationale, kill_criteria=list(kill), saturation=saturation,
        pillars_used=list(pillar), source_ids=list(source),
    )
    conn.close()
    typer.echo(f"created {card.id}")


@app.command("forecast-supersede")
def forecast_supersede(
    old_id: str = typer.Argument(..., help="The card to supersede (retained, never edited)."),
    question: str = typer.Option(..., help="The revised question."),
    prob: float = typer.Option(..., help="Revised probability (0..1)."),
    resolution_date: str = typer.Option(..., help="ISO date (YYYY-MM-DD)."),
    kill: list[str] = typer.Option(..., "--kill", help="Kill-criterion (repeat). Required."),
    rationale: str = typer.Option(..., help="Why the revision."),
    ci_low: float = typer.Option(None), ci_high: float = typer.Option(None),
    ci_unit: str = typer.Option(None), seed_series: str = typer.Option(None),
    pillar: list[int] = typer.Option([], "--pillar"),
    source: list[str] = typer.Option([], "--source"),
) -> None:
    """Replace a card with a revised one; the old stays for the track record (rule 7)."""
    conn = db.connect()
    db.init_db(conn)
    new = forecast.supersede(
        conn, old_id, question=question, probability=prob,
        resolution_date=date.fromisoformat(resolution_date),
        ci_low=ci_low, ci_high=ci_high, ci_unit=ci_unit, seed_series_id=seed_series,
        rationale=rationale, kill_criteria=list(kill),
        pillars_used=list(pillar), source_ids=list(source),
    )
    conn.close()
    typer.echo(f"superseded {old_id} → {new.id}")


@app.command("forecast-resolve")
def forecast_resolve(
    card_id: str = typer.Argument(..., help="The card to resolve."),
    outcome: str = typer.Option(..., help="'true' or 'false'."),
) -> None:
    """Resolve a card and compute its Brier score = (p − outcome)²."""
    conn = db.connect()
    db.init_db(conn)
    brier = forecast.resolve(conn, card_id, ForecastOutcome(outcome))
    conn.close()
    typer.echo(f"resolved {card_id} as {outcome} → Brier {brier:.3f}")


@app.command("forecast-seal")
def forecast_seal() -> None:
    """Seal the live forward record: export every unresolved STRUCTURAL call to a deterministic,
    committable manifest + sha256. The git commit of those files is the un-backdateable timestamp
    (the moat — VATI §6). Re-running on an unchanged record is byte-identical. $0."""
    conn = db.connect()
    db.init_db(conn)
    r = forecast.export_seal(conn)
    conn.close()
    typer.echo(f"sealed {r['n_calls']} live forward structural calls → {r['path']}")
    typer.echo(f"sha256 {r['sha256']}")
    typer.echo("  next: git add experiments/forward_calls_seal.* && git commit  (commit = the timestamp seal;")
    typer.echo("        later `ots stamp experiments/forward_calls_seal.sha256` adds a blockchain proof)")


@app.command("forecast-list")
def forecast_list() -> None:
    """List live (non-superseded) cards + the calibration scoreboard vs the naive baseline."""
    conn = db.connect()
    db.init_db(conn)
    rows = conn.execute(
        "SELECT id, question, probability, resolution_date, outcome, brier_score "
        "FROM forecast_cards WHERE superseded_by IS NULL ORDER BY created_at"
    ).fetchall()
    cal = forecast.calibration(conn)
    conn.close()
    for r in rows:
        state = f"resolved {r['outcome']} (Brier {r['brier_score']:.3f})" if r["outcome"] else "open"
        typer.echo(f"  [{state}] p={r['probability']:.2f} by {r['resolution_date']}  {r['question'][:70]}")
    if cal["n_resolved"]:
        typer.echo(f"calibration: {cal['n_resolved']} resolved · mean Brier "
                   f"{cal['brier_model']:.3f} vs naive baseline {cal['brier_baseline']:.3f}")
    else:
        typer.echo("calibration: no resolved cards yet.")


@app.command("graph-seed")
def graph_seed(
    chain: str = typer.Option("scrna_seq", help="Chain to build: 'scrna_seq', 'ai_power', or 'metals'."),
) -> None:
    """Phase 4: build a supply graph (sourced nodes + typed edges) + the verify Decision. Chain-agnostic."""
    conn = db.connect()
    db.init_db(conn)
    if chain == "metals":
        # The cross-DOMAIN extension: metals chain + the ai_power→metals edges. Needs ai_power first.
        if not conn.execute("SELECT 1 FROM graph_nodes WHERE chain='ai_power' LIMIT 1").fetchone():
            graph.seed_ai_power(conn, log=typer.echo)
        out = graph.seed_metals(conn, log=typer.echo)
        conn.close()
        typer.echo(f"done — {out['nodes']} metals nodes / {out['edges']} edges + {out['cross_edges']} "
                   f"cross-domain edges into ai_power. Flow the connected world: "
                   f"graph-propagate --chain ai_power --world. cost: $0.00")
        return
    if chain == "ai_power":
        out = graph.seed_ai_power(conn, log=typer.echo)
        d = graph.propose_ai_power_verification(conn)
    else:
        out = graph.seed_graph(conn, log=typer.echo)
        d = graph.propose_verification(conn)
    conn.close()
    typer.echo(f"verify-decision open: {d.id}")
    typer.echo("  → " + d.prompt[:90] + "…")
    typer.echo(f"  HUMAN-VERIFY before propagating. Then: graph-propagate --chain {chain} --verify <decision_id>")
    typer.echo(f"done — {out['nodes']} nodes / {out['edges']} edges / {out['sources']} sources. cost: $0.00")


@app.command("graph-propagate")
def graph_propagate(
    chain: str = typer.Option("scrna_seq", help="Which chain to flow: 'scrna_seq' or 'ai_power'."),
    world: bool = typer.Option(
        False, "--world",
        help="Flow across the CONNECTED world (ai_power + metals), not one chain — cross-domain."),
    verify: str = typer.Option(
        None, "--verify",
        help="The decision id the human confirmed. Required to tie back to the forecast (the gate).",
    ),
    tie_back: bool = typer.Option(
        False, "--tie-back", help="Supersede the forward card with the graph-derived version (rule 7)."),
) -> None:
    """Flow the 10x shock → first-saturating, least-substitutable node + supply-gap interval."""
    conn = db.connect()
    db.init_db(conn)
    shock = graph.AI_POWER_SHOCK if chain == "ai_power" else graph.SHOCK
    chains = ("ai_power", "metals") if world else None
    scope_label = " + ".join(chains) if chains else chain
    prop = graph.propagate(conn, chain=chain, chains=chains, shock=shock)
    typer.echo(f"\n{shock:.0f}x demand shock → constraint propagation over '{scope_label}':")
    for p in prop.pressures:
        mark = "  ← BOTTLENECK" if p is prop.bottleneck else ""
        typer.echo(
            f"  {p.name[:48]:<48} req {p.required_multiple:>4.0f}x  supply {p.supply_multiple:>4.1f}x  "
            f"subst {p.substitutability:>3.0%}  pressure {p.pressure:>5.2f}  P(bn)={p.p_bottleneck:>4.0%}{mark}"
        )
    b = prop.bottleneck
    typer.echo(f"\nBOTTLENECK: {b.name}")
    typer.echo(f"  supply gap {prop.gap_median:.1f}x (80% CI [{prop.gap_ci_low:.1f},{prop.gap_ci_high:.1f}]) "
               f"· P(this is THE bottleneck) {b.p_bottleneck:.0%}")
    if prop.obvious_endpoint:
        o = prop.obvious_endpoint
        typer.echo(f"  (the obvious endpoint '{o.name[:40]}' is ELASTIC: pressure {o.pressure:.2f}, "
                   f"substitutability {o.substitutability:.0%} — rent does NOT land there)")

    # where to point the deep-data drill: high pressure × thin data coverage (data follows the graph)
    drills = graph.drill_targets(conn, prop, chain=chain, chains=chains)
    typer.echo("\nDRILL ORDER (where data, not reasoning, is binding — P(bn) × (1−coverage)):")
    for d in drills[:5]:
        typer.echo(f"  {d.drill_score:>5.2f}  {d.name[:44]:<44} [{d.chain}]  cov {d.coverage:>3.0%}  · {d.why}")

    # VALUE OF INFORMATION (execution §3 "spend the variance budget"): which single measurement most
    # sharpens WHERE the bottleneck is? The top term is the cheapest next measurement — the operator payoff.
    modal_name, base_p, voi = graph.variance_budget(conn, chain=chain, chains=chains, shock=shock)
    typer.echo(f"\nVALUE OF INFORMATION (measure-this-next — P(bottleneck '{modal_name[:30]}') = {base_p:.0%}):")
    for t in voi[:4]:
        typer.echo(f"  +{t.voi:>5.1%}  {t.input_name[:46]:<46} · {t.why}")
    if voi:
        typer.echo(f"  → measure FIRST: {voi[0].input_name} (collapses the most uncertainty about the bottleneck).")

    if tie_back:
        if chain == "ai_power":
            conn.close()
            typer.echo("\nNOTE: ai_power ties back via `hypothesis-promote` (the forward card is a fresh "
                       "promotion of the survived thesis, not a supersede). Confirm the verify-Decision "
                       "with `graph-verify`, then run hypothesis-promote.")
            raise typer.Exit(code=0)
        if not verify:
            conn.close()
            typer.echo("\nREFUSED: --tie-back needs --verify <decision_id> (rule 4 — never flow an "
                       "unverified chain into a forecast).")
            raise typer.Exit(code=1)
        row = conn.execute("SELECT status, chosen_option FROM decisions WHERE id=?", (verify,)).fetchone()
        if row is None or row["status"] != "decided":
            conn.close()
            typer.echo(f"\nREFUSED: decision {verify} is not confirmed yet (human-verify gate, §9).")
            raise typer.Exit(code=1)
        res = graph.graph_backed_forward_card(conn, prop)
        if res["superseded"]:
            typer.echo(f"\ntied back → superseded {res['old_id']} → {res['new_id']} "
                       f"(graph-derived; bottleneck '{res['bottleneck']}').")
        else:
            typer.echo(f"\ntie-back skipped: {res['reason']}")
    conn.close()
    typer.echo("cost: $0.00")


@app.command("graph-verify")
def graph_verify(
    decision_id: str = typer.Argument(..., help="The open verify-Decision id."),
    choose: str = typer.Option(..., "--choose", help="The option the human picked."),
) -> None:
    """Stamp the human's verification onto the supply-graph Decision (closes the gate, rule 4)."""
    conn = db.connect()
    db.init_db(conn)
    graph.record_decision(conn, decision_id, choose)
    conn.close()
    typer.echo(f"decision {decision_id} → decided: {choose!r}")


@app.command("consensus-score")
def consensus_score(
    chain: str = typer.Option("scrna_seq", help="Which thesis to gate: 'scrna_seq' or 'ai_power'."),
) -> None:
    """Phase 5 gate (pillar 7): is the constraint bottleneck already priced in?

    Pulls keyless market signals (Stooq close + SEC XBRL fundamentals), computes the numeric
    consensus delta = modeled fair premium − market-implied premium, and flags an edge only if it
    clears the threshold. Every fetch is logged to the cost ledger first ($0 auto). cost: $0.00.
    """
    cfg = consensus.AI_POWER_CFG if chain == "ai_power" else consensus.SCRNA_CFG
    conn = db.connect()
    db.init_db(conn)
    typer.echo(f"consensus gate — {cfg.chain}: inelastic ({cfg.consumable['sym']}) "
               f"vs obvious ({cfg.sequencer['sym']})")
    consensus.score_consensus(conn, cfg=cfg, log=typer.echo)
    conn.close()
    typer.echo("cost: $0.00")


@app.command("bet-translate")
def bet_translate(
    supersede: bool = typer.Option(
        False, "--supersede", help="Revise the live bet (old retained, rule 7) instead of skipping."),
) -> None:
    """Phase 5 half 2 (pillar 12): turn the scRNA-seq consensus EDGE into a sized PAPER bet.

    Maps the constraint → instrument(s) (long the inelastic consumable hedged short the elastic
    sequencer), sizes it (capped fractional Kelly from the edge magnitude + uncertainty), ties the
    horizon to the forecast card, and operationalizes the kill-criteria into monitorable triggers.
    Paper only — translation, NOT execution. No data fetch ⇒ no spend. cost: $0.00.
    """
    conn = db.connect()
    db.init_db(conn)
    typer.echo("bet translation — scRNA-seq: long consumable (TXG) / short sequencer (ILMN)")
    card = bet.translate(conn, supersede_live=supersede, log=typer.echo)
    conn.close()
    if card is None:
        raise typer.Exit(code=1)
    typer.echo("cost: $0.00")


@app.command("retro-run")
def retro_run(
    k: float = typer.Option(detector.DEFAULT_K, help="σ threshold (frozen at 3 — do NOT tune to the corpus)."),
) -> None:
    """Phase 6: run the §8 winners+fizzles corpus point-in-time with the method FROZEN.

    Seeds the corpus as point-in-time series, lets the EXISTING detector decide blindly on data
    ≤ each case's signal_date (no new forecasting logic), then scores precision + recall + lead-
    time + Brier vs the base-rate baseline. Look-ahead is verified absent. cost: $0.00.
    """
    conn = db.connect()
    db.init_db(conn)
    out = retro.run(conn, k=k, log=typer.echo)
    conn.close()
    typer.echo(f"\ndone — {out['cases']} cases, look-ahead violations: {out['look_ahead_violations']}. cost: $0.00")


@app.command("recall-probe")
def recall_probe(
    k: float = typer.Option(detector.DEFAULT_K, help="σ threshold (frozen at 3 — same as §8)."),
) -> None:
    """The §3 recall fix, VALIDATED: does a finer leading channel catch the AI-compute-class miss early?

    Rolls the cutoff back over the live monthly arXiv talent-inflow / topic-share channels
    (research.py) for the §8 ai_compute case and asks, point-in-time, at which cutoff each first fires.
    Uses the SAME frozen detector; NEVER edits the §8 scoreboard (that would be tuning, §9). Persists to
    recall_probe so the cockpit surfaces it. cost: $0.00.
    """
    conn = db.connect()
    db.init_db(conn)
    out = retro.recall_probe(conn, k=k, log=typer.echo)
    conn.close()
    typer.echo(f"\ndone — {out['recall_gains']}/{out['probes']} channels close the miss early. cost: $0.00")


@app.command("universe-run")
def universe_run(
    k: float = typer.Option(detector.DEFAULT_K, help="σ threshold (FROZEN at 3 — never tune to the universe)."),
    origins: str = typer.Option("", help="comma-separated origin years (default = the frozen 5). Ad-hoc only."),
    gain_margin: float = typer.Option(backtest.GAIN_MARGIN, help="share-gain label threshold (FROZEN at 1.5)."),
    channels: str = typer.Option("count", help="count | count+diffusion | count+diffusion+talent."),
    block_null: bool = typer.Option(False, help="also compute the block-permutation p + lift CI (slower)."),
) -> None:
    """Phase 6+: the survivorship-killer. Run the FROZEN method across a MECHANICALLY-DRAWN universe.

    Instead of 10 famous cases, the candidate set is drawn by a frozen rule from the OpenAlex concept
    pool (data ≤ each origin), the win/lose label is assigned by a frozen gain-of-share rule (data >
    origin), and the existing detector calls each blind. Reports the pooled + de-clustered confusion
    matrix, lift, lead-time, Fisher-p and honest LOCO Brier — nobody picked the cases or the outcomes.
    The knobs are ad-hoc exploration only; the PRE-REGISTERED experiment is `experiment-select`/
    `experiment-reveal` (experiments/protocol_v1.yaml). cost: $0.00.
    """
    conn = db.connect()
    db.init_db(conn)
    org = tuple(int(x) for x in origins.split(",") if x.strip()) or universe.ORIGINS
    out = universe.run(conn, k=k, origins=org, gain_margin=gain_margin, channels=channels,
                       block_null=block_null, log=typer.echo)
    conn.close()
    typer.echo(f"\ndone — {out['drawn']} drawn / {out['scored']} scored across {out['n_origins']} origins, "
               f"look-ahead violations: {out['look_ahead_violations']}. cost: $0.00")


@app.command("experiment-select")
def experiment_select(
    m: int = typer.Option(2000, help="block-permutation / bootstrap draws (deterministic seed)."),
) -> None:
    """Stage 1 (pre-registered): run the full search space on the SELECTION origins, ledger every
    config, promote argmax de-clustered lift. Never touches the sealed TEST origins. cost: $0.00."""
    conn = db.connect()
    db.init_db(conn)
    experiment.select_and_seal(conn, m=m, log=typer.echo)
    conn.close()


@app.command("experiment-reveal")
def experiment_reveal(
    m: int = typer.Option(2000, help="block-permutation / bootstrap draws (deterministic seed)."),
) -> None:
    """Stage 1: the ONE-TIME sealed-TEST reveal. Scores the promoted config on the held-out TEST
    origins, deflates the p by the configs tried, records it immutably. Refuses if already revealed.
    Ensure experiments/protocol_v1.yaml is committed FIRST (the seal). cost: $0.00."""
    conn = db.connect()
    db.init_db(conn)
    experiment.reveal_test(conn, m=m, log=typer.echo)
    conn.close()


@app.command("experiment-status")
def experiment_status() -> None:
    """Stage 1: print the experiment ledger — configs tried, the deflation denominator, the best
    selection lift, and whether TEST is still sealed. cost: $0.00."""
    conn = db.connect()
    db.init_db(conn)
    experiment.status(conn, log=typer.echo)
    conn.close()


@app.command("experiment-v2-select")
def experiment_v2_select(m: int = typer.Option(2000, help="block-perm / bootstrap draws.")) -> None:
    """protocol_v2 (concept-disjoint, powered): run the search space on the SELECT concepts, ledger,
    promote. Never scores the held-out TEST concepts. cost: $0.00."""
    conn = db.connect()
    db.init_db(conn)
    experiment.select_and_seal_v2(conn, m=m, log=typer.echo)
    conn.close()


@app.command("experiment-v2-reveal")
def experiment_v2_reveal(m: int = typer.Option(2000, help="block-perm / bootstrap draws.")) -> None:
    """protocol_v2: the ONE-TIME concept-disjoint TEST reveal + per-provider grain breakdown. Refuses
    if already revealed. Commit experiments/protocol_v2.yaml FIRST (the seal). cost: $0.00."""
    conn = db.connect()
    db.init_db(conn)
    experiment.reveal_test_v2(conn, m=m, log=typer.echo)
    conn.close()


@app.command("experiment-power")
def experiment_power(
    m_inner: int = typer.Option(2000, help="block-permutation draws per synthetic set (resolution)."),
    m_outer: int = typer.Option(400, help="synthetic datasets per assumed true lift (power estimate)."),
) -> None:
    """Power analysis of the v2 sealed-TEST: was the null well-powered (signal dead) or under-powered
    (couldn't see a weak edge)? Prints the power curve + MDE_80, raw and deflated by the CUMULATIVE
    config count. Read-only — writes nothing (audits a closed seal). cost: $0.00."""
    conn = db.connect()
    db.init_db(conn)
    experiment.power_report(conn, m_inner=m_inner, m_outer=m_outer, log=typer.echo)
    conn.close()


@app.command("locator-run")
def locator_run(
    k: float = typer.Option(detector.DEFAULT_K, help="detector σ threshold (frozen at 3)."),
) -> None:
    """Stage 2: the mechanical constraint-LOCATOR — the one retro-test of the THESIS with an
    INDEPENDENT (price) label. Wires layer-price feeds, runs the rolling-origin locator over the
    connected ai_power→metals world, grades located/obvious/graph picks vs the realized price winner.
    Honest small N — suggestive, not proof. Commit experiments/protocol_locator.yaml first. cost: $0.00."""
    conn = db.connect()
    db.init_db(conn)
    locator.run(conn, k=k, log=typer.echo)
    conn.close()


@app.command("holdout-run")
def holdout_run(
    provider: str = typer.Option("deepinfra_keyless", help="LLM provider: deepinfra_keyless ($0) | "
                                 "openrouter | minimax. An OLD-cutoff model (openrouter "
                                 "openai/gpt-3.5-turbo-0613) is required for a VALID run."),
    model: str = typer.Option("", help="explicit model id (e.g. openai/gpt-3.5-turbo-0613). Empty = roster."),
    est_cost_cents: int = typer.Option(0, help="estimated spend for the cost gate (keyed routes)."),
    proxy: bool = typer.Option(False, help="route keyless calls through the residential proxy."),
) -> None:
    """Stage 3: the older-model temporal holdout — the only leakage-bounded test of LLM JUDGMENT. Probes
    the model's effective cutoff FIRST and refuses to score unless it is provably blind to the outcomes
    (the leakage gate). Keyless/MiniMax are ~2025-cutoff → they fail the gate (the honest blocker until
    an old-cutoff model is wired). cost-gated (rule 3)."""
    from engine.adapters import proxy as proxymod
    conn = db.connect()
    db.init_db(conn)
    px = proxymod.proxy_url() if proxy and proxymod.available() else None
    holdout.run(conn, provider=provider, model=(model or None), est_cost_cents=est_cost_cents,
                proxy=px, log=typer.echo)
    conn.close()


@app.command("holdout-bench")
def holdout_bench(
    provider: str = typer.Option("openrouter", help="LLM provider (an OLD-cutoff model is required for a valid run)."),
    model: str = typer.Option("openai/gpt-3.5-turbo-0613", help="explicit old-cutoff model id."),
    est_cost_cents: int = typer.Option(5, help="estimated spend for the cost gate (keyed routes)."),
    proxy: bool = typer.Option(False, help="route keyless calls through the residential proxy."),
) -> None:
    """Stage 3 (defensible): score an old-cutoff model on EXTERNALLY-authored, resolved ForecastBench
    questions (experiments/holdout_questions.jsonl), gated by a NON-LEADING recall probe. Removes the
    'self-authored / N=7' critiques. cost-gated (rule 3)."""
    from engine.adapters import proxy as proxymod
    conn = db.connect()
    db.init_db(conn)
    px = proxymod.proxy_url() if proxy and proxymod.available() else None
    holdout.run_external(conn, provider=provider, model=(model or None), est_cost_cents=est_cost_cents,
                         proxy=px, log=typer.echo)
    conn.close()


@app.command("entity-seed")
def entity_seed() -> None:
    """Component 2: resolve the curated entity clusters (in-session judgment, GIGO-rationaled).

    Links existing rows — frontier series, supply-graph nodes, market tickers — onto canonical
    entities, so one technology/firm can be traced across pillars. Additive, idempotent, $0.
    """
    conn = db.connect()
    db.init_db(conn)
    out = entity.seed(conn, log=typer.echo)
    conn.close()
    typer.echo(f"\ndone — {out['entities']} entities, {out['links']} links, "
               f"{out['missing']} missing. cost: $0.00")


@app.command("entity-list")
def entity_list() -> None:
    """Show resolved entities + the pillars each spans (the cockpit is the real view)."""
    conn = db.connect()
    db.init_db(conn)
    entity.list_entities(conn, log=typer.echo)
    conn.close()


@app.command("entity-candidates")
def entity_candidates_cmd(
    generate: bool = typer.Option(False, help="Generate new candidate links for unlinked series."),
) -> None:
    """A7: propose entity links for unlinked rows (exact-id + string-blocking), then list them.

    Generators only PROPOSE; nothing commits without `entity-accept`. Fuzzy may propose, never commit.
    """
    from engine import entity_candidates as ec
    conn = db.connect()
    db.init_db(conn)
    if generate:
        ec.generate(conn, log=typer.echo)
    ec.list_proposed(conn, log=typer.echo)
    conn.close()


@app.command("entity-accept")
def entity_accept(candidate_id: str = typer.Argument(..., help="entity_candidates id (8-char ok).")) -> None:
    """Promote a proposed candidate to a committed entity_link (human/Claude verify gate)."""
    from engine import entity_candidates as ec
    conn = db.connect()
    db.init_db(conn)
    # accept by full or short id
    row = conn.execute("SELECT id FROM entity_candidates WHERE id=? OR id LIKE ?",
                       (candidate_id, candidate_id + "%")).fetchone()
    if not row:
        typer.echo(f"no candidate matching {candidate_id}")
        raise typer.Exit(code=1)
    typer.echo(ec.accept(conn, row["id"]))
    conn.close()


@app.command("entity-reject")
def entity_reject(candidate_id: str = typer.Argument(..., help="entity_candidates id (8-char ok).")) -> None:
    """Reject a proposed candidate (e.g. an over-merge like NLP→deep learning)."""
    from engine import entity_candidates as ec
    conn = db.connect()
    db.init_db(conn)
    row = conn.execute("SELECT id FROM entity_candidates WHERE id=? OR id LIKE ?",
                       (candidate_id, candidate_id + "%")).fetchone()
    if not row:
        typer.echo(f"no candidate matching {candidate_id}")
        raise typer.Exit(code=1)
    ec.reject(conn, row["id"])
    typer.echo(f"rejected {row['id'][:8]}")
    conn.close()


@app.command("entity-taxonomy")
def entity_taxonomy() -> None:
    """Component 2 (#4, heavy half): seed the canonical sub-topic vocabulary over every unlinked
    series. Each DISTINCT concept becomes its own entity (over-merge structurally impossible);
    only true cross-source/cross-pillar variants of the same concept fold. The payoff printed is
    the cross-pillar TRACE — a constraint followed across the value layers. $0, stdlib."""
    from engine import entity_candidates as ec
    conn = db.connect()
    db.init_db(conn)
    ec.seed_taxonomy(conn, log=typer.echo)
    conn.close()


@app.command("entity-supplier-edges")
def entity_supplier_edges() -> None:
    """Component 2 (#4, dependency half): seed the curated entity↔entity SUPPLIER edges — the supply
    structure between entities so a constraint can be traced one hop up/downstream. Each is a known
    real-world supplier relation, GIGO-rationaled (not a hallucinated chain); LLM 10-K extraction can
    propose more at scale under the same human-verify gate. $0."""
    from engine import entity_candidates as ec
    conn = db.connect()
    db.init_db(conn)
    ec.seed_supplier_edges(conn, log=typer.echo)
    conn.close()


@app.command("hypothesis-seed")
def hypothesis_seed() -> None:
    """Component 8: run the oracle pass — divergent, cross-domain constraint-migration hypotheses.

    Each is generated in-session through a Bucket-2 lens, then FORCED through the same gate a forecast
    obeys (outside-view base rate, disconfirmer-first, kill-criteria, projectibility). The gate verdict
    — survived / parked / killed — falls out. The seer proposes; the cold machine disposes. $0.
    """
    conn = db.connect()
    db.init_db(conn)
    out = hypothesis.seed(conn, log=typer.echo)
    conn.close()
    typer.echo(f"\ndone — {out['generated']} generated: {out['survived']} survived, "
               f"{out['parked']} parked, {out['killed']} killed. cost: $0.00")


@app.command("hypothesis-list")
def hypothesis_list() -> None:
    """Show generated hypotheses by verdict (the cockpit is the real view)."""
    conn = db.connect()
    db.init_db(conn)
    hypothesis.list_hypotheses(conn, log=typer.echo)
    conn.close()


@app.command("hypothesis-skeptic")
def hypothesis_skeptic(
    hypothesis_id: str = typer.Argument(..., help="The hypothesis to test (8-char id ok)."),
    votes: str = typer.Option(..., help="JSON list of INDEPENDENT skeptic votes: "
                              '[{"skeptic","refuted","reason","confidence"}]. A strict majority to '
                              "refute kills the thesis (§2.6). May be a @path to a JSON file."),
) -> None:
    """Component 9: fold an independent multi-skeptic panel onto a hypothesis (majority-refute → re-gate).

    The skeptics are run by Claude in-session (real, independent adversarial passes — each asked only
    to REFUTE, blind to the others); this records their votes and recomputes the gate verdict. A single
    in-session refutation can fool itself; a blind majority cannot as easily.
    """
    import json as _json
    raw = open(votes[1:], encoding="utf-8").read() if votes.startswith("@") else votes
    conn = db.connect()
    db.init_db(conn)
    out = hypothesis.record_skeptic_panel(conn, hypothesis_id, _json.loads(raw), log=typer.echo)
    conn.close()
    typer.echo(f"\npanel recorded: {out['n_refute']}/{out['n_skeptics']} refute → {out['status']}. $0.00")


@app.command("hypothesis-add")
def hypothesis_add(
    title: str = typer.Option(..., help="One-line thesis name."),
    lens: str = typer.Option(..., help=f"Bucket-2 lens: {', '.join(hypothesis.LENSES)}."),
    seed: str = typer.Option(..., help="The divergent spark (analogy / inversion / 'what must be true')."),
    claim: str = typer.Option(..., help="The constraint-migration thesis — where rent moves."),
    inelastic: str = typer.Option(..., "--inelastic", help="The non-obvious binding constraint (where rent lands)."),
    obvious: str = typer.Option(..., "--obvious", help="The obvious-but-wrong endpoint everyone prices."),
    ref_class: str = typer.Option(..., "--ref-class", help="The outside-view reference class (doctrine §2.1)."),
    disconfirmer: str = typer.Option(..., help="The strongest case AGAINST, sought FIRST (required, §2.6)."),
    refutation: str = typer.Option(..., help="The in-session adversarial verdict — why it survives/dies."),
    refuted: bool = typer.Option(False, help="Did the disconfirmer win? (→ killed)"),
    measurable: bool = typer.Option(False, help="Is there a point-in-time series that could test it? (§0.5)"),
    base_rate: float = typer.Option(None, help="The reference class's hit rate (the outside-view anchor)."),
    horizon: str = typer.Option(None, help="Rough resolution horizon (YYYY-MM-DD)."),
    kill: list[str] = typer.Option([], "--kill", help="A kill-criterion with a date (repeat)."),
    thesis_kind: str = typer.Option(None, "--thesis-kind",
        help=f"The SHAPE of the structural call: {', '.join(hypothesis.THESIS_KINDS)}."),
    mispricing_kind: str = typer.Option(None, "--mispricing-kind",
        help=f"WHY consensus is wrong: {', '.join(hypothesis.MISPRICING_KINDS)}."),
    horizon_years: int = typer.Option(None, "--horizon-years",
        help="Years until the structural claim binds (≤4 = harvestable; long+hot-narrative = hype-over-priced)."),
    note: str = typer.Option("", help="Optional note."),
) -> None:
    """Author one structural-foresight hypothesis in-session and run it through the gate.

    The output is a BIG falsifiable structural call (a sector/sub-sector/macro reorganization), not a
    stock pick: 'consensus believes X; I predict Y; resolved by [dated structural metric]'. The
    inelastic-layer decomposition is the MECHANISM, not the deliverable. Tag --thesis-kind /
    --mispricing-kind so the call feeds the measured base-rate-by-kind (`base-rates`)."""
    conn = db.connect()
    db.init_db(conn)
    h = hypothesis.add(
        conn, title=title, lens=lens, seed=seed, claim=claim, inelastic_layer=inelastic,
        obvious_layer=obvious, reference_class=ref_class, base_rate=base_rate,
        disconfirmer=disconfirmer, kill_criteria=list(kill),
        horizon=date.fromisoformat(horizon) if horizon else None,
        measurable=measurable, refuted=refuted, refutation=refutation,
        thesis_kind=thesis_kind, mispricing_kind=mispricing_kind, horizon_years=horizon_years,
        note=note,
    )
    conn.close()
    typer.echo(f"{h.title}\n→ gate verdict: {h.status.upper()}")


@app.command("base-rates")
def base_rates() -> None:
    """The closed loop: measured hit rate + Brier of each KIND of structural call.

    Combines the §8 retrodiction corpus (known outcomes, tagged by kind → non-empty now) with any
    resolved live cards. This is the outside view EARNED from our own record, not a typed-in prior —
    the thing no analyst has: not a pick, but a base rate of which kinds of where-rent-migrates calls pay."""
    conn = db.connect()
    db.init_db(conn)
    hypothesis.base_rates(conn, log=typer.echo)
    conn.close()


@app.command("hypothesis-promote")
def hypothesis_promote(
    hypothesis_id: str = typer.Argument(..., help="The SURVIVED hypothesis to promote (8-char ok)."),
    question: str = typer.Option(..., help="The binary, point-in-time forecast question."),
    prob: float = typer.Option(..., help="P of the binary resolving true (0..1)."),
    resolution_date: str = typer.Option(..., help="ISO date when we'll know (YYYY-MM-DD)."),
    ci_low: float = typer.Option(None), ci_high: float = typer.Option(None),
    ci_unit: str = typer.Option(None), seed_series: str = typer.Option(None),
    pillar: list[int] = typer.Option([], "--pillar"),
    source: list[str] = typer.Option([], "--source"),
) -> None:
    """Graduate a SURVIVED hypothesis into an immutable ForecastCard (rule 7). Refuses parked/killed."""
    conn = db.connect()
    db.init_db(conn)
    out = hypothesis.promote(
        conn, hypothesis_id, question=question, probability=prob,
        resolution_date=date.fromisoformat(resolution_date), ci_low=ci_low, ci_high=ci_high,
        ci_unit=ci_unit, seed_series_id=seed_series, pillars_used=list(pillar),
        source_ids=list(source), log=typer.echo,
    )
    conn.close()
    typer.echo(f"forecast {out['forecast_id']}")


@app.command("decision-open")
def decision_open(
    prompt: str = typer.Option(..., help="The pivotal fork, stated concisely (rule 4)."),
    option: list[str] = typer.Option(..., "--option", help="An option (repeat for each)."),
    rec: str = typer.Option(None, help="The recommended option + why (≤1 line)."),
    blocks: str = typer.Option(None, help="What is paused until this resolves."),
) -> None:
    """Component 14: log a pivotal steering fork → it surfaces in the cockpit's Decisions panel."""
    conn = db.connect()
    db.init_db(conn)
    d = decisions.open_decision(conn, prompt=prompt, options=list(option), recommendation=rec,
                                blocks=blocks, log=typer.echo)
    conn.close()
    typer.echo(f"decision {d.id}")


@app.command("decision-resolve")
def decision_resolve(
    decision_id: str = typer.Argument(..., help="Decision id (8-char ok)."),
    choice: str = typer.Argument(..., help="The chosen option (verbatim, 1-based index, or free text)."),
) -> None:
    """Component 14: stamp the human's choice onto an open decision (closes the fork)."""
    conn = db.connect()
    db.init_db(conn)
    out = decisions.resolve_decision(conn, decision_id, choice, log=typer.echo)
    conn.close()
    typer.echo(f"resolved {out['id'][:8]} → {out['chosen']}")


@app.command("decision-list")
def decision_list(open_only: bool = typer.Option(False, "--open", help="Only show open decisions.")) -> None:
    """Component 14: the steering log (the cockpit #decisions panel is the real view)."""
    conn = db.connect()
    db.init_db(conn)
    decisions.list_decisions(conn, only_open=open_only, log=typer.echo)
    conn.close()


@app.command("status")
def status() -> None:
    """Quick text view of the foundation state (the cockpit is the real view)."""
    conn = db.connect()
    db.init_db(conn)
    rows = conn.execute("SELECT ord, name, status FROM pillars ORDER BY ord").fetchall()
    spend = conn.execute(
        "SELECT COALESCE(SUM(COALESCE(actual_cost_cents, est_cost_cents)), 0) FROM cost_ledger"
    ).fetchone()[0]
    conn.close()
    typer.echo("Pillars (data-flow layers):")
    for r in rows:
        typer.echo(f"  {r['ord']}. {r['name']:<18} [{r['status']}]")
    typer.echo(f"Spend to date: ${spend / 100:.2f}")


if __name__ == "__main__":
    app()
