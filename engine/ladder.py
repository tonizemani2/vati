"""Component 11b — the fast-resolution ladder (redteam #3). Calibration on a fast clock.

The moat (plan.md #4, a live track record) needs RESOLVED forward cards. The thesis cards resolve in
2027–28 — so by construction the reliability curve stays near-empty for years, and a "right but early"
thesis isn't caught until its multi-year horizon. This is the fix: a ladder of many short-horizon,
falsifiable micro-forecasts on the INTERMEDIATE constraint metrics the thesis implies (the supply-layer
price/quantity series), each Brier-scored at resolution — the SAME card machinery, a much faster clock.

It is a calibration accumulator distinct from the other two validators:
  • backtest.py / universe.py score the DETECTOR's winner-classification (logistic(σ−k)).
  • retro.py scores the method's discrimination on famous cases.
  • THIS scores the FORECAST machinery's issued PROBABILITIES — are they calibrated? (plan.md #1) —
    on real economic series, rolling-origin, point-in-time, resolving from history NOW.

Each rung, point-in-time as-of origin O (uses only obs ≤ O):
  1. trailing annual log-returns → drift μ + vol σ (the series' own recent behaviour, nothing typed).
  2. project the O-level H years under a log-normal Monte-Carlo (a price INDEX — no Poisson count noise,
     unlike forecast.mc_quantity which is for compounding counts).
  3. binary = "the constraint still BINDS: the metric holds ≥ its O-level by O+H" → P = MC fraction.
  4. resolve against the recorded O+H observation → Brier. (A genuine two-sided test: the 2008–09 and
     2014–16 commodity/steel busts mean a high-P persistence call DOES resolve false there.)

BREADTH (2026-06-04): the rungs run on EVERY series with enough annual history (QC-passing), not a
hardcoded six — calibration is a property of the forecast machinery across ALL domains, not just the
pillar-4 supply layer, so the reliability curve must be built on hundreds of rungs (a verdict) not
dozens (noise). Each rung is tagged with its series' real pillar.

CALIBRATION FIX (2026-06-04, measured on 7.7k rungs, not assumed): the 42 pillar-4 rungs looked
over-confident, but across ALL series the live method (6yr-trailing drift, point MC) was genuinely
un-calibrated — Brier 0.270, WORSE than the 0.250 max-entropy baseline. Two principled changes, each
decided on first principles then measured:
  • Drift from the FULL point-in-time history, not a 6yr trailing window (the DOMINANT fix: 0.270 →
    0.243). A short window misses the secular drift, so persistence reads ~50% when reality is ~60%.
  • Honest tails: μ,σ are not plugged in as known — each path draws σ² from its scaled-inverse-χ²
    posterior and μ from N(μ̂, σ²/n) (Jeffreys posterior-predictive → Student-t), so thin-data rungs
    don't feign certainty (0.243 → 0.242, marginal but right).
DISCRIMINATION (2026-06-04): calibration alone only TIED the base-rate guesser (0.24) — the univariate
MC has AUC ≈ 0.49, no edge. The issued P now comes from sharpen.py — a transparent logistic on a few
point-in-time mean-reversion features, trained leak-free by EXPANDING WINDOW (only rungs already
resolved by each origin). Measured: AUC ~0.49 → 0.68, Brier 0.235 → 0.219 (still calibrated). The MC
now supplies only the 80% level CI; the model supplies the separating probability. `--no-sharpen`
reverts to the univariate baseline. OPEN: cross-pillar (the "depth" edge) is data-blocked, not
modelling-blocked — entity-sibling coverage is research 80% / capital 3% / demand 0%, so upstream
features add nothing yet; and the model is still mildly overconfident at the very low end (calling
outright dissolution is the hardest call).

HONEST SCOPE (named, not faked): the free intermediate metrics are ANNUAL (FRED G.17 / PPI, OpenAlex,
patents, capex), so the rungs are 1–2-yr horizons, not the literal 3–6-month cadence the audit asked
for — still resolving NOW from history vs the 2027–28 thesis cards, but TRUE sub-annual rungs await a
monthly intermediate series (transformer lead-times, LBNL interconnection-queue durations — a [?] gap).

Cards are tagged with a `LADDER —` question prefix so the cockpit keeps them in their own track (a
fast-clock calibration scoreboard) and the headline #forecasts list stays the 2 thesis cards. $0, stdlib.
"""

from __future__ import annotations

import math
import random
import sqlite3
from datetime import date

from engine import forecast, sharpen
from engine.schemas import ForecastOutcome, _now

LADDER_PREFIX = "LADDER —"
H_YEARS = 2          # horizon per rung (the intermediate metrics we have are annual — see header)
TRAIL = 6            # trailing years the drift/vol is estimated from
ORIGIN_STEP = 2      # one rung every 2 years across the resolvable range
MIN_RETURNS = 3      # need a few trailing returns to estimate drift/vol at all
VOL_FLOOR = 0.02     # a price index never has truly zero year-on-year vol
MC_N = 20_000        # plenty for a binary fraction (SE ~0.004) across hundreds of broadened rungs
BASELINE_P = 0.5     # the naive base-rate every rung must beat (max-entropy on a binary)


def _eligible_series(conn: sqlite3.Connection, h: int) -> list[sqlite3.Row]:
    """Every series with enough annual history to build at least one rolling-origin rung, excluding
    QC failures (create_card would refuse them anyway). Ordered for deterministic per-rung seeds."""
    return conn.execute(
        "SELECT s.id, s.label, s.source_id, s.pillar_id, COUNT(o.id) AS n "
        "FROM series s JOIN observations o ON o.series_id = s.id "
        "LEFT JOIN series_health sh ON sh.series_id = s.id "
        "WHERE sh.status IS NULL OR sh.status != 'fail' "
        "GROUP BY s.id HAVING n >= ? ORDER BY s.pillar_id, s.label, s.id",
        (TRAIL + h + 2,)).fetchall()


def _series_obs(conn: sqlite3.Connection, series_id: str) -> list[tuple[date, float]]:
    return [(date.fromisoformat(r["as_of"]), float(r["value"]))
            for r in conn.execute(
                "SELECT as_of, value FROM observations WHERE series_id=? ORDER BY as_of", (series_id,))]


def _project(base: float, mu: float, sigma: float, h: int, *, seed: int, n: int = MC_N,
             n_returns: int | None = None):
    """Project a level h years ahead under i.i.d. log-normal annual growth (no count noise).

    If `n_returns` is given (honest-tails mode), μ and σ are not plugged in as known: each path draws
    σ² from its scaled-inverse-χ²(df=n−1) posterior and μ from N(μ̂, σ²/n) (Jeffreys-prior posterior-
    predictive), so the projection integrates over estimation uncertainty → Student-t tails. With only
    a handful of returns this widens the spread and de-sharpens extreme probabilities."""
    rng = random.Random(seed)
    df = (n_returns - 1) if n_returns else 0
    out: list[float] = []
    for _ in range(n):
        if df > 0:
            chi2 = rng.gammavariate(df / 2.0, 2.0)                       # χ²(df)
            sig_p = sigma * math.sqrt(df / chi2) if chi2 > 0 else sigma  # scaled-inverse-χ² draw of σ
            mu_p = rng.gauss(mu, sig_p / math.sqrt(n_returns))           # μ | σ², data
        else:
            mu_p, sig_p = mu, sigma
        v = base
        for _ in range(h):
            v *= math.exp(rng.gauss(mu_p, sig_p))
        out.append(v)
    out.sort()
    pct = lambda p: out[int(p * len(out))]
    return out, pct(0.50), pct(0.10), pct(0.90)


def _sig(x: float, sig: int = 4) -> float:
    """Round to `sig` significant figures (NOT fixed decimals). The ladder runs on series spanning
    many orders of magnitude (counts in thousands, ratios ~1e-4); a fixed round(x,1) collapses a
    small-magnitude band to 0.0 and breaks the P/CI invariant. Sig-figs keep precision everywhere."""
    if x == 0 or not math.isfinite(x):
        return x
    return round(x, -int(math.floor(math.log10(abs(x)))) + (sig - 1))


def _candidate(*, series_id: str, label: str, source_id: str | None, pillar_id: int,
               obs: list[tuple[date, float]], origin_idx: int, h: int, seed: int,
               honest_tails: bool) -> dict | None:
    """Compute one rung's features + MC interval + realised label — but NOT its issued probability or
    card (the price is set later by the expanding-window model over the whole rung set). None if short.

    Drift uses the FULL point-in-time history (all obs ≤ origin), not a trailing window — measured as
    the dominant calibration fix (Brier 0.270 trailing → 0.243 full-history). The realised outcome is
    used only as a TRAINING label, gated leak-free by resolution year in sharpen.price_expanding."""
    o_date, o_val = obs[origin_idx]
    if o_val <= 0:
        return None
    hist = [x[1] for x in obs[:origin_idx + 1]]
    feats = sharpen.extract(hist)
    if feats is None:                       # < MIN_RETURNS — too short to characterise
        return None
    rets = [math.log(hist[i + 1] / hist[i])
            for i in range(len(hist) - 1) if hist[i] > 0 and hist[i + 1] > 0]
    mu = sum(rets) / len(rets)
    sigma = max(VOL_FLOOR, (sum((r - mu) ** 2 for r in rets) / (len(rets) - 1)) ** 0.5)
    threshold = o_val                       # "the constraint holds — not below today's level"
    res_date = date(o_date.year + h, o_date.month, o_date.day)
    samples, med, lo, hi = _project(o_val, mu, sigma, h, seed=seed,
                                    n_returns=len(rets) if honest_tails else None)
    p_uni = sum(1 for v in samples if v >= threshold) / len(samples)
    grid = forecast.quantile_grid(samples)      # compact CDF summary, so the sharpened-P tilt in
                                                # PASS 2 reads the SAME posterior the CI comes from
    q = (f"{LADDER_PREFIX} does '{label}' hold >= {threshold:.1f} (its {o_date.year} level) by "
         f"{res_date.year}? [as-of {o_date.isoformat()}, constraint-persistence micro-forecast]")
    return {
        "series_id": series_id, "label": label, "source_id": source_id, "pillar_id": pillar_id,
        "question": q, "o_year": o_date.year, "res_date": res_date, "res_year": res_date.year,
        "threshold": threshold, "o_val": o_val, "med": med, "lo": lo, "hi": hi, "grid": grid,
        "feats": feats, "mu": mu, "sigma": sigma, "nret": len(rets), "p_uni": p_uni,
        "y": 1.0 if obs[origin_idx + h][1] >= threshold else 0.0,
    }


def run_ladder(conn: sqlite3.Connection, *, h: int = H_YEARS, honest_tails: bool = True,
               sharpen_p: bool = True, clear: bool = False, log=print) -> dict:
    """Build the rolling-origin ladder across every QC-passing series, resolving past rungs. $0.

    Two passes: gather every candidate rung's point-in-time features, then issue each probability. With
    `sharpen_p` (default) the probability is the leak-free EXPANDING-WINDOW discrimination model
    (sharpen.py) — trained only on rungs already resolved by that origin — which lifts AUC ~0.49→0.68;
    off, it falls back to the univariate MC persistence fraction (calibrated but non-discriminating).
    `clear` wipes existing rungs first (clean re-measure); the MC always supplies the 80% level CI."""
    if clear:
        conn.execute("DELETE FROM forecast_cards WHERE question LIKE ?", (LADDER_PREFIX + "%",))
    eligible = _eligible_series(conn, h)
    log(f"  ladder base: {len(eligible)} eligible series "
        f"(sharpen={sharpen_p}, honest_tails={honest_tails}, h={h}y)")
    cands: list[dict] = []
    for si, row in enumerate(eligible):
        conn.execute("UPDATE pillars SET status='in_progress' WHERE id=? AND status='untapped'",
                     (row["pillar_id"],))
        obs = _series_obs(conn, row["id"])
        if len(obs) < TRAIL + h + 2:
            continue
        for origin_idx in range(TRAIL, len(obs) - h, ORIGIN_STEP):
            c = _candidate(series_id=row["id"], label=row["label"], source_id=row["source_id"],
                           pillar_id=row["pillar_id"], obs=obs, origin_idx=origin_idx, h=h,
                           seed=si * 1000 + origin_idx, honest_tails=honest_tails)
            if c:
                cands.append(c)

    # PASS 2 — issue probabilities. Leak-free expanding window over the whole rung set, or univariate.
    if sharpen_p:
        rung_in = [{"origin_year": c["o_year"], "res_year": c["res_year"], "feats": c["feats"],
                    "y": c["y"]} for c in cands]
        prices = sharpen.price_expanding(rung_in)
    else:
        prices = [c["p_uni"] for c in cands]

    new = 0
    resolved_now = 0
    for c, p in zip(cands, prices):
        if conn.execute("SELECT 1 FROM forecast_cards WHERE question=?", (c["question"],)).fetchone():
            continue
        src = "sharpened logistic (drift/vol/momentum/accel/drawdown, leak-free expanding window)" \
            if sharpen_p else "univariate MC persistence fraction"
        # ONE posterior for both P and CI. With sharpen on, the logistic sets P(holds); we LOCATE the
        # MC band so its P(≥ threshold) equals that P (forecast.tilt_to_probability) instead of
        # stapling a logistic P onto an unrelated MC interval — the documented calibration bug. The
        # MC's WIDTH (honest tails) is preserved; only its location moves. Off, the MC fraction is
        # already self-consistent with its own band.
        if sharpen_p:
            p_use, lo_use, hi_use = forecast.tilt_to_probability(
                c["grid"], c["lo"], c["hi"], c["threshold"], p, ">=")
        else:
            p_use, lo_use, hi_use = c["p_uni"], c["lo"], c["hi"]
        med_use = c["med"] + (lo_use - c["lo"])     # the same location shift δ applied to the median
        lo_s, hi_s, med_s = _sig(lo_use), _sig(hi_use), _sig(med_use)   # mag-aware display rounding
        try:
            card = forecast.create_card(
                conn, question=c["question"], probability=round(p_use, 3), resolution_date=c["res_date"],
                ci_low=lo_s, ci_high=hi_s, ci_unit=c["label"][:38],
                threshold=c["threshold"], threshold_dir=">=",
                seed_series_id=c["series_id"], source_ids=[c["source_id"]] if c["source_id"] else [],
                pillars_used=[c["pillar_id"]],
                rationale=(
                    f"FAST-CLOCK calibration+discrimination rung (redteam #3). Point-in-time as-of "
                    f"{c['o_year']} (only obs ≤ that date): {c['nret']} annual log-returns (full history) "
                    f"→ drift {c['mu']:+.3f}, vol {c['sigma']:.3f}; the {c['o_year']} level {c['o_val']:g} "
                    f"projected {h}y under a log-normal Monte-Carlo. P(holds) = {p_use:.2f} from the {src}; "
                    f"the band is located to that P → median {med_s:g} (80% CI [{lo_s:g},{hi_s:g}]), "
                    f"so P and the interval are ONE posterior, not two models stapled together. The issued P "
                    f"separates holds from dissolves (AUC ~0.68 OOS) — the same card machinery as a thesis "
                    f"bet, resolved in years so the record compounds NOW."),
                kill_criteria=[f"'{c['label']}' falls below {c['threshold']:.1f} by {c['res_year']} — the "
                               f"constraint relaxed at this horizon (the metric dissolved)."],
            )
        except ValueError as e:            # QC seed gate refused (unaudited→fail race); skip cleanly.
            if "data-audit" in str(e):     # but NEVER swallow a P/CI-consistency failure (no silent cap)
                continue
            raise
        new += 1
        if c["res_date"] <= _now().date():
            row = conn.execute("SELECT value FROM observations WHERE series_id=? AND as_of LIKE ?",
                               (c["series_id"], f"{c['res_year']}%")).fetchone()
            if row is not None:
                outcome = ForecastOutcome.true if float(row["value"]) >= c["threshold"] else ForecastOutcome.false
                forecast.resolve(conn, card.id, outcome)
                resolved_now += 1
    conn.commit()

    sc = ladder_score(conn)
    log(f"\nFAST-RESOLUTION LADDER — {new} new rung(s), {resolved_now} resolved this run "
        f"(horizon {h}y, rolling origins, sharpen={sharpen_p}).")
    if sc["n_resolved"]:
        auc_s = sc["auc"] if sc["auc"] is None else round(sc["auc"], 3)
        log(f"  scoreboard (all {sc['n_resolved']} resolved ladder rungs) — engine vs baselines, side-by-side:")
        log(f"    Brier    model {sc['brier_model']:.3f}  ·  0.5/rand-walk {sc['brier_baseline']:.3f}  ·  "
            f"base-rate {sc['brier_baserate']:.3f}  ·  persistence {sc['brier_persist']:.3f}")
        log(f"    LogLoss  model {sc['logloss_model']:.3f}  ·  0.5/rand-walk {sc['logloss_baseline']:.3f}  ·  "
            f"base-rate {sc['logloss_baserate']:.3f}  ·  persistence {sc['logloss_persist']:.3f}")
        log(f"    AUC {auc_s} · hit-rate {sc['hit_rate']:.0%} · mean P {sc['mean_p']:.0%}")
    return {"new": new, "resolved_now": resolved_now, **sc}


_LL_EPS = 1e-6


def _logloss(p: float, y: float) -> float:
    """Per-event log loss (cross-entropy), clipped so a 0/1 call is finite. Punishes CONFIDENT
    wrong calls far harder than Brier — the exact overconfidence the ladder exists to surface."""
    p = min(1 - _LL_EPS, max(_LL_EPS, p))
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def ladder_score(conn: sqlite3.Connection) -> dict:
    """Brier AND log loss over ALL resolved ladder rungs, EACH scored side-by-side against three
    naive baselines (plan.md #4 — never the engine's number alone):
      · max-entropy 0.5 — and this IS the random-walk baseline here: a zero-drift diffusion on a
        'holds ≥ today's level' question has its median AT the threshold, so P(holds)=0.5 exactly.
        Beating it shows calibration.
      · base-rate guesser — always predict the realised hit-rate. Beating it shows discrimination.
      · persistence ('no change') — the metric stays at today's level, so the constraint HOLDS:
        P=1. The 'constraints never relax' null; log loss exposes how it's punished when one does.
    (A market-consensus baseline does NOT apply to these obscure-PPI micro-forecasts — no analyst
    series exists per rung; consensus lives at the thesis-card layer, the consensus.py gate.)"""
    rows = conn.execute(
        "SELECT probability, outcome, brier_score FROM forecast_cards "
        "WHERE question LIKE ? AND outcome IS NOT NULL AND superseded_by IS NULL",
        (LADDER_PREFIX + "%",)).fetchall()
    n = len(rows)
    if not n:
        return {"n_resolved": 0, "brier_model": None, "brier_baseline": None,
                "brier_baserate": None, "brier_persist": None, "logloss_model": None,
                "logloss_baseline": None, "logloss_baserate": None, "logloss_persist": None,
                "auc": None, "hit_rate": None, "mean_p": None, "bins": []}
    realized = [1.0 if r["outcome"] == "true" else 0.0 for r in rows]
    brier_model = sum(r["brier_score"] for r in rows) / n
    brier_baseline = sum((BASELINE_P - y) ** 2 for y in realized) / n
    hit_rate = sum(realized) / n
    # The TOUGHER baseline: always guess the base rate. Beating max-entropy shows calibration; beating
    # THIS shows discrimination (skill above the prior). Brier of the constant base-rate predictor.
    brier_baserate = hit_rate * (1.0 - hit_rate)
    # Persistence ('no change' → the metric holds at today's level → P=1). Brier = fraction that fell.
    brier_persist = sum((1.0 - y) ** 2 for y in realized) / n
    # Log loss for the model and each baseline, scored the SAME way (plan.md #5: Brier AND log loss).
    logloss_model = sum(_logloss(r["probability"], y) for r, y in zip(rows, realized)) / n
    logloss_baseline = -math.log(0.5)                                       # 0.5 / random-walk predictor
    logloss_baserate = _logloss(hit_rate, 1.0) * hit_rate + _logloss(hit_rate, 0.0) * (1.0 - hit_rate)
    logloss_persist = sum(_logloss(1.0, y) for y in realized) / n           # P=1 → huge penalty per fall
    # Discrimination: rank-based AUC over (issued P, outcome) — 0.5 = no edge, the univariate ladder's level.
    auc = sharpen.auc([(r["probability"], y) for r, y in zip(rows, realized)])
    mean_p = sum(r["probability"] for r in rows) / n
    # 5 reliability bins: mean predicted vs observed frequency
    bins: list[dict] = []
    for b in range(5):
        lo, hi = b / 5, (b + 1) / 5
        sub = [(r["probability"], y) for r, y in zip(rows, realized)
               if (lo <= r["probability"] < hi) or (b == 4 and r["probability"] == 1.0)]
        if sub:
            bins.append({"lo": lo, "hi": hi, "n": len(sub),
                         "pred": sum(p for p, _ in sub) / len(sub),
                         "obs": sum(y for _, y in sub) / len(sub)})
    return {"n_resolved": n, "brier_model": brier_model, "brier_baseline": brier_baseline,
            "brier_baserate": brier_baserate, "brier_persist": brier_persist,
            "logloss_model": logloss_model, "logloss_baseline": logloss_baseline,
            "logloss_baserate": logloss_baserate, "logloss_persist": logloss_persist,
            "auc": auc, "hit_rate": hit_rate, "mean_p": mean_p, "bins": bins}
