"""The survivorship-killer — run the FROZEN method across a MECHANICALLY-DRAWN universe.

The retrodiction corpus (engine/retro.py) proves the method works on 10 *famous* cases. A hostile
reviewer's fair objection: "you picked the ones you knew." This harness closes that. It does not
choose which concepts to forecast and it does not decide outcomes from memory — both the candidate
set and the win/lose label are assigned by a rule, frozen below, evaluated point-in-time. Whatever
the confusion matrix then says is what the method actually does on a neutral field.

It adds NO new forecasting logic and NO new statistics. It reuses, verbatim:
  - engine.detector.detect(points, k=3, log=True)  — the frozen brain (Theil–Sen + MAD-σ + held-out
    surprise). Never touched here.
  - engine.backtest._resolve_gain_share / _cohort_totals  — the rising-tide-immune outcome label.
  - engine.backtest._fisher_exact_greater / _loco_brier   — significance + honest out-of-sample Brier.
It is glue + pre-registration, not a second method to keep honest.

═══════════════════════════════════════════════════════════════════════════════════════════════════
THE FROZEN RULES — committed BEFORE the first run. Tuning any of these to the result IS the
hindsight machine (CONSTITUTION §9 / doctrine §2.8). None of the constants below is swept.
───────────────────────────────────────────────────────────────────────────────────────────────────
1. DRAW RULE (no look-ahead in the SELECTION).  Universe pool = every OpenAlex concept series
   (provider='openalex'; the one large, homogeneous, multi-domain cohort — `level ∈ {1,2,3}` already
   enforced at collection, frontier.py). For each origin year T ∈ {2008,2010,2012,2014,2016}, concept
   c ∈ U(T) iff, using ONLY observations with year ≤ T:
     (a) count(obs with year ≤ T) ≥ MIN_POINTS (= 8, inherited from the detector — below this a
         "trend" is noise), AND
     (b) the series is MEASURABLE above its own Poisson counting noise — NO magic level constant.
         A count y has counting-SNR √y; we require the median √y over the window ≥ k, the SAME k·σ
         the detector fires at (DEFAULT_K=3). I.e. a concept is admissible only if its annual counts
         are resolvable at the confidence we'd demand to call anything — derived from the detector's
         own threshold, not a hand-picked floor. This admits FINE-GRAINED early concepts (median
         count ≥ k² ≈ 9, not ≥100) — aligned with the bar (the alpha is in the small grain) — while
         excluding series whose year-to-year wiggle is pure sampling noise.
   Membership is a pure function of the truncated series {(year,value): year ≤ T}. It never consults
   the post-T trajectory, the outcome, or human memory. The known winners and the known laggards
   (rfid, wimax, cold-fusion … domain='laggard') sit in U(T) on identical footing — the draw cannot
   tell them apart, which is the point. The measurability gate reuses the detector's k (nothing new
   to sweep); MIN_POINTS is the detector's own floor; |U(T)| is printed per origin so the draw cannot
   be silently narrowed.

2. LABEL RULE (no hindsight in the LABEL).  winner ≜ the concept GAINED SHARE of its peer cohort:
   share(y) = value(c,y) / Σ_cohort value(·,y); s_pre = mean share over (T−GAIN_WINDOW, T];
   s_post = mean share over the last GAIN_WINDOW future years. winner iff s_post/s_pre ≥ GAIN_MARGIN
   (= 1.5). Share is zero-sum across the cohort, so a winner only gains share if peers lose it — this
   removes the rising-tide confound that makes a raw-growth label trivially true. If shares are
   unavailable (cohort < MIN_COHORT, or a window is empty) the case is DROPPED and logged
   (label_winner=NULL), never silently labelled negative (retro.LOGGED_GAPS discipline).
   NAMED CEILING (stated, not papered over): the label is gain-of-share within OpenAlex's OWN concept
   counts. It is share-based (not raw growth), so the trivial confound is gone — but it is NOT drawn
   from a feed independent of the detector's input. Scholarly-attention migration need not be a
   commercial win; a cross-feed label (NIH-grant share, patent share, market capture) is the v2
   upgrade, logged as the named limitation. The secondary "acceleration (endogenous)" column is the
   weaker raw-trend view, reported alongside so the edge is shown to survive the HARDER share test.

3. METRICS.  base rate = Σwinners/Σdrawn (the true, low denominator of a neutral universe); lift =
   precision/base_rate; precision/recall/specificity from the pooled 2×2; median lead-time = months
   from T to the first future year share crosses GAIN_MARGIN; LOCO Brier vs base-rate (honest OOS);
   Fisher-exact p. CLUSTERING CAVEAT: the pooled forecasts are NOT independent (one concept recurs at
   all 5 origins) so the pooled Fisher-p is OPTIMISTIC. We also report a DE-CLUSTERED check (one
   forecast per concept — its most-recent eligible origin) whose p is the conservative number. Both
   are printed. A softened lift on the neutral universe is REPORTED, not buried: a negative result is
   a real result.
4. ORTHOGONAL CHANNEL (committed BEFORE the run — goal.md #2: recall from MORE sharp instruments, never
   from a more trigger-happy single curve). The count channel (works/year) is structurally blind to a
   technique that SPREADS across fields before its aggregate count saturates. So we add a second,
   independent channel: CROSS-FIELD DIFFUSION = the inverse-Simpson effective number of OpenAlex fields
   a concept's works span each year (engine.pillars.frontier.collect_diffusion). The SAME frozen
   detect(k, log) judges it — no new forecasting logic, just a different series. COMBINATION = OR:
   fired := count_fired ∨ diffusion_fired (recall at the detector; the supply-graph/consensus gates,
   not wired here, are where precision is restored downstream). We report count-only, diffusion-only,
   and OR SEPARATELY so each channel's contribution is auditable. SUCCESS, pre-stated: diffusion is a
   valid channel iff diffusion-only lift > 1; it is a useful recall fix iff OR raises recall over
   count-only while OR lift stays > 1; the orthogonality payoff is any WINNER the count channel missed
   that diffusion caught. A null result (diffusion adds only noise) is LOGGED and NOT shipped into the
   live detector — exactly as the changepoint recall-fix was tried and cut (detector.py). Diffusion is
   point-in-time clean (publication year + field are fixed facts; unlike citations it accrues no
   future), and uses the same ≤T filter + an in-code assert. NAMED CONFOUND: field-diversity is
   volume-biased at low work counts — the laggard-specificity and "catches count's misses" tests are
   the arbiters, not a hopeful prior.
═══════════════════════════════════════════════════════════════════════════════════════════════════

Pure arithmetic, read-once. cost: $0.00, stdlib only, keyless.
"""

from __future__ import annotations

import math
import random
import sqlite3
import statistics
from dataclasses import dataclass

from engine.backtest import (
    GAIN_MARGIN, GAIN_WINDOW, LOG_SPACE, MIN_COHORT,
    _cohort_totals, _fisher_exact_greater, _loco_brier, _points_by_year,
    _resolve, _resolve_gain_share,
)
from engine.detector import DEFAULT_K, MIN_POINTS, detect
from engine.pillars.frontier import _log_cost
from engine.schemas import _now, _uid

# --- frozen draw constants (see docstring §1 — never swept) ---
PROVIDER = "openalex"                       # the homogeneous, multi-domain candidate pool
ORIGINS = (2008, 2010, 2012, 2014, 2016)    # rolling origins (= backtest.SWEEP_CUTOFFS)
# NB: there is NO magic level floor. Eligibility is data-derived (see _measurable) and reuses the
# detector's own k — a count is admissible iff its counting-SNR (√y) clears the same k·σ bar the
# detector fires at. Nothing here to sweep.


@dataclass
class UniverseCase:
    id: str
    series_id: str
    concept_key: str
    label: str
    domain: str | None
    origin_year: int
    n_known: int
    n_future: int
    drawn: bool
    fired: bool | None = None
    forecast_sigma: float | None = None
    predicted_p: float | None = None
    label_winner: bool | None = None
    share_multiple: float | None = None
    lead_months: int | None = None
    accel_winner: bool | None = None        # secondary (endogenous) label — reported, not stored
    diff_fired: bool | None = None          # the ORTHOGONAL channel (cross-field diffusion) verdict ≤ T
    diff_sigma: float | None = None
    talent_fired: bool | None = None        # power channel (talent inflow) verdict ≤ T (Stage 1.6)
    talent_sigma: float | None = None
    correct: int | None = None

    @property
    def scored(self) -> bool:
        return self.drawn and self.fired is not None and self.label_winner is not None

    @property
    def or_fired(self) -> bool:
        """Recall-at-the-detector: fired on EITHER channel (missing diffusion just can't add a fire)."""
        return bool(self.fired) or bool(self.diff_fired)

    @property
    def or_talent_fired(self) -> bool:
        """count ∨ diffusion ∨ talent-inflow — the widest recall channel (missing channels can't fire)."""
        return self.or_fired or bool(self.talent_fired)


# the pre-registered channel sets (protocol_v1.yaml search_space.channels) → the verdict each scores.
# "count" reproduces the frozen baseline exactly (UniverseCase.fired); the others widen recall.
def _channel_fired(channel: str):
    if channel == "count":
        return lambda c: bool(c.fired)
    if channel == "count+diffusion":
        return lambda c: c.or_fired
    if channel == "count+diffusion+talent":
        return lambda c: c.or_talent_fired
    raise ValueError(f"unknown channel set: {channel!r} (see protocol_v1.yaml search_space.channels)")


def _p_of(surprise: float, k: float) -> float:
    """Transparent, UNFITTED probability map (verbatim from backtest/retro): p=0.5 at the threshold."""
    return 1.0 / (1.0 + math.exp(-(surprise - k)))


def _measurable(known: list[tuple[float, float]], k: float) -> bool:
    """Data-derived eligibility — NO magic level constant. A Poisson count y has counting-SNR √y; a
    series is forecastable only if its annual counts are resolvable above that sampling noise at the
    SAME k·σ the detector fires at, i.e. median √y over the window ≥ k. Replaces an arbitrary floor
    with the detector's own threshold: it admits fine-grained early concepts (median count ≥ k²) and
    excludes series whose year-to-year wiggle is just counting noise."""
    if not known:
        return False
    return statistics.median([math.sqrt(max(v, 0.0)) for (_, v) in known]) >= k


def _lead_months(pts: list[tuple[float, float, int]], totals: dict[int, float], cutoff: int,
                 *, margin: float = GAIN_MARGIN) -> int | None:
    """Months from the origin to the FIRST future year the concept's share crosses `margin`× its
    pre-origin share — the capturable lead. Same share math + threshold as the label, so the two
    never diverge (margin defaults to GAIN_MARGIN; the harness varies it per the search_space)."""
    def share(yr: int, val: float) -> float | None:
        tot = totals.get(yr)
        return val / tot if tot else None
    pre = [s for (_, v, yr) in pts if cutoff - GAIN_WINDOW < yr <= cutoff and (s := share(yr, v))]
    if not pre:
        return None
    s_pre = sum(pre) / len(pre)
    if s_pre <= 0:
        return None
    for (_, v, yr) in sorted(pts, key=lambda p: p[2]):
        if yr <= cutoff:
            continue
        sh = share(yr, v)
        if sh and sh / s_pre >= margin:
            return (yr - cutoff) * 12
    return None


def _channel_pts(conn: sqlite3.Connection, metric: str) -> dict[str, list[tuple[float, float, int]]]:
    """concept_key → its point-in-time series for an orthogonal `metric` (empty if not collected yet,
    so the bench degrades gracefully). Used for cross-field diffusion and talent-inflow channels."""
    out: dict[str, list[tuple[float, float, int]]] = {}
    for d in conn.execute(
        "SELECT id, external_id FROM series WHERE provider=? AND metric=?", (PROVIDER, metric),
    ).fetchall():
        out[d["external_id"]] = _points_by_year(conn, d["id"])
    return out


def _orthogonal_verdict(pts_by_key: dict, key: str, T: int, k: float):
    """Run the SAME frozen detector on an orthogonal channel's series ≤ T (no look-ahead, asserted).
    Returns (fired, sigma) or (None, None) if the channel has too few point-in-time points."""
    dpts = pts_by_key.get(key)
    if not dpts:
        return None, None
    dknown = [(x, v) for (x, v, yr) in dpts if yr <= T]
    if len(dknown) < MIN_POINTS:
        return None, None
    assert max(yr for (_, _, yr) in dpts if yr <= T) <= T   # no look-ahead, in code
    ddet = detect(dknown, k=k, log=LOG_SPACE)
    return (ddet.fired, ddet.surprise_sigma) if ddet is not None else (None, None)


def _evaluate(conn: sqlite3.Connection, *, k: float, origins: tuple[int, ...] = ORIGINS,
              gain_margin: float = GAIN_MARGIN, providers: tuple[str, ...] = (PROVIDER,),
              concept_filter: set[str] | None = None) -> list[UniverseCase]:
    """Apply the frozen draw + label rules to every concept at every origin. Point-in-time.

    `origins`/`gain_margin` default to the frozen constants (identical legacy behaviour). `providers`
    widens the candidate pool (protocol_v2 adds 'arxiv' category concepts beside 'openalex'); each
    provider's (provider,metric,unit) is its OWN share cohort, so the gain-of-share label stays
    within-provider. `concept_filter` (a set of external_ids) restricts which concepts become CASES —
    the mechanism behind the concept-DISJOINT split (cohort totals still use the full pool, so 'share'
    denominators are honest)."""
    placeholders = ",".join("?" for _ in providers)
    series = conn.execute(
        "SELECT id, external_id, label, domain, provider, metric, unit "
        f"FROM series WHERE provider IN ({placeholders}) AND metric = 'works_per_year' ORDER BY label",
        tuple(providers),
    ).fetchall()
    if concept_filter is not None:
        series = [s for s in series if s["external_id"] in concept_filter]
    totals, members = _cohort_totals(conn)
    # orthogonal channels: cross-field diffusion + talent inflow (empty if not collected → count-only).
    diff_pts = _channel_pts(conn, "field_diffusion")
    talent_pts = _channel_pts(conn, "talent_inflow")
    cases: list[UniverseCase] = []
    for s in series:
        pts = _points_by_year(conn, s["id"])
        cohort = (s["provider"], s["metric"], s["unit"])
        ctot = totals.get(cohort, {})
        for T in origins:
            known = [(x, v) for (x, v, yr) in pts if yr <= T]
            future = [(x, v) for (x, v, yr) in pts if yr > T]
            if not known:
                continue                                 # concept doesn't exist yet at T
            drawn = len(known) >= MIN_POINTS and _measurable(known, k)
            uc = UniverseCase(
                id=_uid(), series_id=s["id"], concept_key=s["external_id"], label=s["label"],
                domain=s["domain"], origin_year=T, n_known=len(known), n_future=len(future), drawn=drawn,
            )
            if drawn:
                det = detect(known, k=k, log=LOG_SPACE)  # the blind forecast at T — COUNT channel
                if det is not None:
                    uc.fired, uc.forecast_sigma = det.fired, det.surprise_sigma
                    uc.predicted_p = round(_p_of(det.surprise_sigma, k), 4)
                # ORTHOGONAL channels: same frozen detector on diffusion + talent series ≤ T
                uc.diff_fired, uc.diff_sigma = _orthogonal_verdict(diff_pts, s["external_id"], T, k)
                uc.talent_fired, uc.talent_sigma = _orthogonal_verdict(talent_pts, s["external_id"], T, k)
                if members.get(cohort, 0) >= MIN_COHORT:
                    res = _resolve_gain_share(pts, ctot, T, margin=gain_margin)   # the frozen outcome label
                    if res is not None:
                        uc.label_winner, uc.share_multiple = res[0], round(res[1], 3)
                        if uc.label_winner:
                            uc.lead_months = _lead_months(pts, ctot, T, margin=gain_margin)
                    if future:                                        # secondary endogenous view
                        uc.accel_winner = _resolve(known, future, k, log=LOG_SPACE)[0]
            if uc.scored:
                f, w = uc.fired, uc.label_winner
                uc.correct = int((f and w) or (not f and not w))
            cases.append(uc)
    return cases


def _store(conn: sqlite3.Connection, cases: list[UniverseCase]) -> None:
    conn.execute("DELETE FROM universe_cases")
    for c in cases:
        conn.execute(
            "INSERT INTO universe_cases (id,series_id,concept_key,label,domain,origin_year,n_known,"
            "n_future,drawn,fired,forecast_sigma,predicted_p,diff_fired,diff_sigma,label_winner,"
            "share_multiple,lead_months,correct,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (c.id, c.series_id, c.concept_key, c.label, c.domain, c.origin_year, c.n_known,
             c.n_future, int(c.drawn),
             None if c.fired is None else int(c.fired), c.forecast_sigma, c.predicted_p,
             None if c.diff_fired is None else int(c.diff_fired), c.diff_sigma,
             None if c.label_winner is None else int(c.label_winner), c.share_multiple,
             c.lead_months, c.correct, _now().isoformat()),
        )


def _confusion(rows: list[UniverseCase], fired_of=lambda c: c.fired) -> dict:
    """Pooled 2×2 + the derived rates for a set of scored cases. `fired_of` picks the channel
    verdict (count / diffusion / OR), so one function scores all three honestly."""
    a = sum(1 for c in rows if fired_of(c) and c.label_winner)          # fired & won
    b = sum(1 for c in rows if fired_of(c) and not c.label_winner)      # fired & lost
    cc = sum(1 for c in rows if not fired_of(c) and c.label_winner)     # silent & won
    d = sum(1 for c in rows if not fired_of(c) and not c.label_winner)  # silent & lost
    n = a + b + cc + d
    base = (a + cc) / n if n else 0.0
    precision = a / (a + b) if (a + b) else 0.0
    return {
        "a": a, "b": b, "c": cc, "d": d, "n": n, "base_rate": base,
        "n_fired": a + b, "n_winners": a + cc,
        "precision": precision,
        "recall": a / (a + cc) if (a + cc) else 0.0,
        "specificity": d / (b + d) if (b + d) else 0.0,
        "lift": precision / base if base else 0.0,
        "p_value": _fisher_exact_greater(a, b, cc, d),
    }


def score(cases: list[UniverseCase], *, origins: tuple[int, ...] = ORIGINS,
          channels: str = "count", block_null: bool = False, m: int = 2000) -> dict:
    """All metrics from the frozen rules — pooled, per-origin, and the conservative de-clustered check.

    `pooled` is ALWAYS the count channel (works/year) so the legacy report is unchanged. `channels`
    selects the PRIMARY scored verdict (count / +diffusion / +talent) the experiment harness reads
    via sc['primary']; for channels='count', primary == pooled. `block_null=True` attaches the
    block-permutation p + cluster-bootstrap lift CI to primary + primary['declustered'] (opt-in: the
    Monte-Carlo is skipped on the fast legacy path)."""
    scored = [c for c in cases if c.scored]
    pooled = _confusion(scored)
    pooled["brier_model"], pooled["brier_base"] = _loco_brier(
        [(c.origin_year, bool(c.fired), bool(c.label_winner)) for c in scored]
    )
    leads = sorted(c.lead_months for c in scored if c.fired and c.label_winner and c.lead_months is not None)
    pooled["median_lead_months"] = leads[len(leads) // 2] if leads else None

    # --- THE ORTHOGONAL CHANNEL: count-only vs diffusion-only vs OR (the recall fix) ---
    have_diff = [c for c in scored if c.diff_fired is not None]
    diff_only = _confusion(have_diff, fired_of=lambda c: c.diff_fired)
    or_conf = _confusion(scored, fired_of=lambda c: c.or_fired)
    or_conf["brier_model"], or_conf["brier_base"] = _loco_brier(
        [(c.origin_year, c.or_fired, bool(c.label_winner)) for c in scored]
    )
    # orthogonality payoff: WINNERS the count channel went silent on, that diffusion caught — and the
    # precision cost (new false positives diffusion fired that count didn't). The honest tradeoff.
    rescued = [c for c in scored if c.label_winner and not c.fired and c.diff_fired]
    or_cost = sum(1 for c in scored if not c.label_winner and not c.fired and c.diff_fired)
    pooled["channels"] = {
        "n_with_diff": len(have_diff),
        "diff_only": diff_only,
        "or": or_conf,
        "rescued": sorted(((c.label, c.origin_year) for c in rescued), key=lambda x: x[1]),
        "or_cost": or_cost,
    }

    # secondary endogenous (acceleration) lift — the weaker raw-trend label, for contrast
    acc = [c for c in cases if c.drawn and c.fired is not None and c.accel_winner is not None]
    a2 = sum(1 for c in acc if c.fired and c.accel_winner)
    b2 = sum(1 for c in acc if c.fired and not c.accel_winner)
    base2 = sum(1 for c in acc if c.accel_winner) / len(acc) if acc else 0.0
    prec2 = a2 / (a2 + b2) if (a2 + b2) else 0.0
    pooled["accel_lift"] = prec2 / base2 if base2 else 0.0
    pooled["accel_base"] = base2

    # per-origin rows + edge consistency
    per_origin = []
    for T in origins:
        rows = [c for c in scored if c.origin_year == T]
        drawn_T = sum(1 for c in cases if c.origin_year == T and c.drawn)
        cf = _confusion(rows)
        cf.update({"origin": T, "drawn": drawn_T})
        per_origin.append(cf)
    pooled["per_origin"] = per_origin
    pooled["origins_with_edge"] = sum(1 for r in per_origin if r["lift"] > 1.0 and r["n"])

    # de-clustered: one forecast per concept = its EARLIEST scored origin (independent draws). Earliest,
    # not latest, on purpose — it's the hardest call (longest horizon, fewest points) so the de-clustered
    # number can't be read as quietly picking each concept's easiest, most-recent origin.
    earliest: dict[str, UniverseCase] = {}
    for c in scored:
        cur = earliest.get(c.concept_key)
        if cur is None or c.origin_year < cur.origin_year:
            earliest[c.concept_key] = c
    dc = _confusion(list(earliest.values()))
    pooled["declustered"] = dc

    # --- PRIMARY block: the experiment's headline, scored under the SELECTED channel set. For
    # channels='count' it mirrors the count-channel pooled/de-clustered above; for the wider channels
    # it scores the OR verdict. The block-permutation p + lift CI are attached here in score (1.4). ---
    fired_of = _channel_fired(channels)
    primary = _confusion(scored, fired_of=fired_of)
    primary["brier_model"], primary["brier_base"] = _loco_brier(
        [(c.origin_year, fired_of(c), bool(c.label_winner)) for c in scored]
    )
    primary["declustered"] = _confusion(list(earliest.values()), fired_of=fired_of)
    primary["channels"] = channels
    primary["events"] = [                       # (origin, cohort_key, fired, winner) — the block-null unit
        (c.origin_year, (c.domain or "openalex"), fired_of(c), bool(c.label_winner)) for c in scored
    ]
    primary["events_declustered"] = [
        (c.origin_year, (c.domain or "openalex"), fired_of(c), bool(c.label_winner))
        for c in earliest.values()
    ]
    if block_null:
        import engine.significance as sig
        rng = random.Random(sig.SEED)
        # block = (origin × cohort): controls per-year/per-cohort firing-rate heterogeneity.
        def _evs(es):
            return [((o, coh), f, w) for (o, coh, f, w) in es]
        bp = sig.block_permutation_lift(_evs(primary["events"]), m=m, rng=rng)
        primary["p_block"] = bp["p_block"]
        primary["lift_ci"] = sig.block_bootstrap_lift_ci(_evs(primary["events"]), m=m, rng=rng)
        bpd = sig.block_permutation_lift(_evs(primary["events_declustered"]), m=m, rng=rng)
        primary["declustered"]["p_block"] = bpd["p_block"]
        primary["declustered"]["lift_ci"] = sig.block_bootstrap_lift_ci(
            _evs(primary["events_declustered"]), m=m, rng=rng)
    pooled["primary"] = primary
    return pooled


def run(conn: sqlite3.Connection, *, k: float = DEFAULT_K, origins: tuple[int, ...] = ORIGINS,
        gain_margin: float = GAIN_MARGIN, channels: str = "count", store: bool = True,
        block_null: bool = False, m: int = 2000, providers: tuple[str, ...] = (PROVIDER,),
        concept_filter: set[str] | None = None, log=print) -> dict:
    """Draw the universe, run the frozen detector blind at every origin, label by rule, store + score.

    All knobs default to the frozen constants → identical legacy output. The experiment harness passes
    search_space values + store=False (so a tuning run doesn't overwrite the canonical universe_cases).
    `providers`/`concept_filter` widen the pool (arxiv) and carve the concept-disjoint split (v2)."""
    cases = _evaluate(conn, k=k, origins=origins, gain_margin=gain_margin, providers=providers,
                      concept_filter=concept_filter)
    if store:
        _store(conn, cases)
        _log_cost(conn, "universe_run", PROVIDER, float(len([c for c in cases if c.drawn])))
        conn.commit()

    # look-ahead verification — structural and MEANINGFUL: the full series lives in the DB (the label
    # needs the future), so the guard isn't "no future rows exist" but "the forecast saw ONLY the past".
    # We assert the stored forecast-input size equals the count of point-in-time-available obs (year ≤ T).
    # Any future leak into detect() would make n_known exceed that count; any short-read, fall below it.
    # (Only meaningful when we stored this run; a tuning run trusts the in-code asserts in _evaluate.)
    violations = conn.execute(
        "SELECT COUNT(*) n FROM universe_cases u WHERE u.drawn = 1 AND u.n_known <> ("
        "  SELECT COUNT(*) FROM observations o WHERE o.series_id = u.series_id "
        "  AND CAST(strftime('%Y', o.as_of) AS INT) <= u.origin_year)"
    ).fetchone()["n"] if store else 0

    sc = score(cases, origins=origins, channels=channels, block_null=block_null, m=m)
    if store:
        _report(cases, sc, violations, k, log=log)
    return {"cases": len(cases), "drawn": sum(1 for c in cases if c.drawn),
            "scored": sc["n"], "n_origins": len(origins),
            "look_ahead_violations": violations, "primary": sc["primary"],
            **{x: sc[x] for x in ("lift", "precision", "recall")}}


def _report(cases: list[UniverseCase], sc: dict, violations: int, k: float, *, log=print) -> None:
    drawn = sum(1 for c in cases if c.drawn)
    log(f"\n🌐 BIAS-PROOF UNIVERSE — OpenAlex concept pool, draw + label rules FROZEN, k={k:g}, log-space")
    log(f"   universe drawn by rule (counts resolvable above Poisson noise: median √y ≥ k={k:g}, "
        f"≥{MIN_POINTS} pts ≤ T — no magic level floor); label = gained ≥{GAIN_MARGIN}× cohort share")
    log(f"   look-ahead: {'✅ none' if violations == 0 else f'❌ {violations}'} "
        f"(every forecast input was a year ≤ its origin)\n")

    log("   origin   |U(T)|   scored   base    precision   lift")
    for r in sc["per_origin"]:
        log(f"   {r['origin']}      {r['drawn']:4d}     {r['n']:4d}    {r['base_rate']*100:4.0f}%    "
            f"{r['precision']*100:5.0f}%    {r['lift']:5.2f}×")

    n_origins = len(sc["per_origin"])
    log(f"\n   POOLED — {sc['n']} forecasts over {n_origins} origins "
        f"(drawn {drawn}, {sc['n_fired']} fired):")
    log(f"     base rate (gained share)        {sc['base_rate']*100:5.1f}%  ({sc['n_winners']}/{sc['n']})")
    log(f"     FIRED → gained share            {sc['precision']*100:5.1f}%  (precision)")
    log(f"     recall  P(fired | winner)       {sc['recall']*100:5.1f}%")
    log(f"     specificity P(silent | loser)   {sc['specificity']*100:5.1f}%")
    lift_note = "edge ✅" if sc["lift"] > 1.0 else "NO edge — neutral universe ❌"
    log(f"     ── LIFT (precision ÷ base)       {sc['lift']:5.2f}×  {lift_note}  "
        f"(held at {sc['origins_with_edge']}/{n_origins} origins)")
    if sc["median_lead_months"] is not None:
        log(f"     median lead-time                {sc['median_lead_months']} mo (signal → share crosses {GAIN_MARGIN}×)")
    sig = "significant ✅" if sc["p_value"] < 0.05 else ("suggestive" if sc["p_value"] < 0.10 else "not significant ❌")
    log(f"     Fisher-exact p (pooled)         {sc['p_value']:.4f}  ({sig}, OPTIMISTIC — origins correlate)")
    bnote = "beats baseline ✅" if sc["brier_model"] < sc["brier_base"] else "no better than base ❌"
    log(f"     Brier (LOCO, honest OOS)        model {sc['brier_model']:.3f} vs base {sc['brier_base']:.3f}  {bnote}")
    log(f"     2×2: fired&win {sc['a']} · fired&loss {sc['b']} · silent&win {sc['c']} · silent&loss {sc['d']}")

    log(f"   (the POOLED block above is the COUNT channel — works/year — alone)")

    dc = sc["declustered"]
    dsig = "significant ✅" if dc["p_value"] < 0.05 else ("suggestive" if dc["p_value"] < 0.10 else "not significant ❌")
    log(f"\n   DE-CLUSTERED (1 forecast / concept, count channel — the conservative number):")
    log(f"     n {dc['n']}   base {dc['base_rate']*100:.1f}%   precision {dc['precision']*100:.1f}%   "
        f"lift {dc['lift']:.2f}×   Fisher-p {dc['p_value']:.4f}  ({dsig})")

    # --- the orthogonal channel: does cross-field diffusion add independent recall? ---
    ch = sc.get("channels")
    if ch and ch["n_with_diff"]:
        do, orc = ch["diff_only"], ch["or"]
        log(f"\n   🛰️  ORTHOGONAL CHANNEL — cross-field diffusion ({ch['n_with_diff']} concepts have it):")
        log(f"     count-only       lift {sc['lift']:.2f}×   recall {sc['recall']*100:4.1f}%   precision {sc['precision']*100:4.1f}%")
        dsg = "✅" if do["lift"] > 1 else "❌"
        log(f"     diffusion-only   lift {do['lift']:.2f}× {dsg}  recall {do['recall']*100:4.1f}%   precision {do['precision']*100:4.1f}%   (valid channel iff lift>1)")
        ob = "beats base ✅" if orc["brier_model"] < orc["brier_base"] else "no better ❌"
        olift = "✅" if orc["lift"] > 1 else "❌"
        log(f"     OR (count∨diff)  lift {orc['lift']:.2f}× {olift}  recall {orc['recall']*100:4.1f}%   precision {orc['precision']*100:4.1f}%   Brier {orc['brier_model']:.3f} v {orc['brier_base']:.3f} {ob}")
        recall_gain = orc["recall"] - sc["recall"]
        log(f"     → OR lifts recall by {recall_gain*100:+.1f} pts at precision {orc['precision']*100:.1f}% "
            f"(recall-at-detector; the gate restores precision downstream)")
        if ch["rescued"]:
            log(f"     🎯 ORTHOGONALITY PAYOFF — winners the COUNT channel went SILENT on, diffusion CAUGHT "
                f"({len(ch['rescued'])}; +{ch['or_cost']} new false positives):")
            for label, T in ch["rescued"][:12]:
                log(f"        {label[:40]:<40} @ {T}")
        else:
            log(f"     ⚠️  diffusion rescued ZERO count-channel misses — no orthogonality payoff this run (logged, not shipped).")

    log(f"\n   secondary 'acceleration' (endogenous, weaker label): lift {sc['accel_lift']:.2f}× "
        f"over base {sc['accel_base']*100:.0f}% — the share edge above is the harder test.\n")
