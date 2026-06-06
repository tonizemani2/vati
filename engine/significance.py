"""Component 4b — the look-elsewhere correction: an empirical null + BH-FDR over the detector.

The detector reports a surprise in σ (transformer 10.6σ, Epoch Vision "43345σ"). A raw σ is NOT a
reliability, two ways:
  1. The implied Gaussian tail p = P(Z ≥ σ) is a fantasy on ~8-30 autocorrelated points — "43345σ"
     just means a tiny noise estimate under a huge trend, not 1-in-10^N confidence.
  2. It carries no DENOMINATOR — scan 200 series and a few clear 3σ by pure chance (the
     look-elsewhere / multiple-comparisons effect). Aggregate σ with no N is unfalsifiable bravado.

This module adds the missing honesty WITHOUT touching the frozen detector. It is a pure wrapper that
RUNS the existing `detect()` on synthetic nulls. detector.py is unchanged — this only annotates its
verdicts, so Phase 6 / universe (which freeze the method) are unaffected.

Two outputs per scanned series:
  - p_mc — an EMPIRICAL p-value. The null is "the early trend simply CONTINUES (no acceleration),
    with noise drawn at the detector's OWN robust scale (MAD-σ of the early residuals — the exact
    noise model the detector assumes when it declares a detection at ~0.1% under normal noise)." We
    generate M surrogate series under that null, run the FROZEN detect() on each, and report
        p = (1 + #{surrogate surprise ≥ observed}) / (M + 1).
    This replaces the Gaussian-σ tail FANTASY (p = P(Z ≥ 43345) ≈ 0) with a bounded, honest number: a
    genuine acceleration lands at the floor 1/(M+1) (we cannot justify a smaller p with this little
    data — that is the point, not a defect); a marginal series gets a graded p.

    NOTE (2026-06-03): the first cut drew noise by a discrete BOOTSTRAP of the early residuals. It was
    CUT — empirically pathological. On ~6-point early windows a discrete resample frequently lands on a
    near-degenerate configuration whose re-fit MAD-σ collapses to the detector's floor, manufacturing a
    1e6-cap "surprise" in ~8.5% of surrogates (measured on the DNA-seq curve). That fat artificial tail
    pushed even a real 53566σ signal to p≈0.09 → it would have FALSELY rejected DNA-sequencing,
    lithium-ion, federated learning. The continuous Gaussian-at-MAD-σ null (consistent with the
    detector's own assumption) does not degenerate: the same signals land at p≈0 and only the marginal
    fires fall away. The bootstrap "result" was an artifact of the null, not a finding about the detector.
  - fdr_survive — Benjamini-Hochberg over the p_mc of EVERY scanned series at level q (default 0.10).
    The headline becomes: "fired M of N; M′ survive BH-FDR; expected false discoveries ≤ q·M′."
    This is the false-positive denominator AT THE DETECTOR. The supply-graph + consensus gates are
    the second, downstream filter (goal.md: recall at the detector, precision at the gate).

Honest limits (logged, not hidden):
  - The null draws i.i.d. Gaussian noise → it does NOT model autocorrelation or heavy tails. Real
    count/price noise is serially correlated and fatter-tailed, so true tails are a touch heavier and
    p_mc is mildly ANTI-conservative (the honest direction to flag, not hide).
  - MC resolution floors the smallest p at 1/(M+1), which bounds how many series can clear BH at
    small q (raise M to resolve more). With N≈200 and q=0.10 the rank-1 BH threshold is q/N≈5e-4, so
    M≥2000 is needed for the strongest signals to survive — the default.
  - It mirrors run_detector's call exactly: detect(pts, k=k) in LINEAR space (log=False). If the live
    detector's space ever changes, change it here too (they are one method).

$0, stdlib only (random). Deterministic: a fixed RNG seed → identical p_mc on re-run (a harness).
"""

from __future__ import annotations

import math
import random
import sqlite3
from statistics import pstdev

from engine.detector import (
    DEFAULT_K,
    HOLDOUT_FRAC,
    LOG_FLOOR,
    detect,
    theil_sen,
    _mad_sigma,
    _series_points,
)
from engine.schemas import _now

DEFAULT_Q = 0.10
DEFAULT_M = 2000
SEED = 20260603  # fixed → re-runs are deterministic (a harness, not a coin flip)


def _early_fit(points: list[tuple[float, float]], *, log: bool):
    """Replicate detect()'s early-portion robust fit, returning the pieces a surrogate needs:
    the working-space (xs, ys), the train/holdout split, the constant-slope trend, and the early
    residual pool the null draws its noise from. Faithful to the frozen detector by construction."""
    pts = sorted(points)
    n = len(pts)
    xs = [p[0] for p in pts]
    ys = [math.log(max(p[1], LOG_FLOOR)) for p in pts] if log else [p[1] for p in pts]
    holdout = max(2, round(HOLDOUT_FRAC * n))
    split = n - holdout
    slope, intercept = theil_sen(xs[:split], ys[:split])
    resid = [ys[i] - (slope * xs[i] + intercept) for i in range(split)]
    return xs, split, slope, intercept, resid


def _safe_exp(v: float) -> float:
    return math.exp(v) if v < 700 else math.exp(700)


def empirical_p(points, observed: float, *, k: float, log: bool, m: int,
                rng: random.Random) -> tuple[float | None, int]:
    """Monte-Carlo p-value for `observed` surprise under H0 = "early trend continues + early noise".

    Builds M surrogate series (the fitted constant-slope trend across ALL points + i.i.d. Gaussian
    noise at the detector's own robust scale — MAD-σ of the early residuals — so NO acceleration),
    runs the FROZEN detect() on each, and returns (p, M_eff) where
    p = (1 + #{null surprise ≥ observed}) / (M_eff + 1). Gaussian-at-MAD-σ, not a discrete bootstrap:
    the bootstrap degenerates on tiny early windows (see the module NOTE).
    """
    xs, split, slope, intercept, resid = _early_fit(points, log=log)
    n = len(xs)
    scale = _mad_sigma(resid)
    if scale <= 0:                       # perfectly clean early window — fall back to the plain spread
        scale = pstdev(resid) if len(resid) > 1 else 0.0
    if scale <= 0:                       # genuinely degenerate (all early residuals identical) — no null
        return None, 0
    null: list[float] = []
    for _ in range(m):
        ys_sur = [slope * xs[i] + intercept + rng.gauss(0.0, scale) for i in range(n)]
        raw = [(xs[i], _safe_exp(ys_sur[i]) if log else ys_sur[i]) for i in range(n)]
        det = detect(raw, k=k, log=log)
        if det is not None:
            null.append(det.surprise_sigma)
    if not null:
        return None, 0
    ge = sum(1 for s in null if s >= observed)
    return (1 + ge) / (len(null) + 1), len(null)


def benjamini_hochberg(pvals: list[float], q: float) -> list[bool]:
    """Standard BH step-up: reject every hypothesis up to the largest rank i with p_(i) ≤ (i/N)·q.
    Controls the false-discovery rate at q across the whole scanned family. Returns survive flags
    aligned to the input order."""
    n = len(pvals)
    survive = [False] * n
    if n == 0:
        return survive
    order = sorted(range(n), key=lambda i: pvals[i])
    kmax = 0
    for rank, idx in enumerate(order, start=1):
        if pvals[idx] <= rank / n * q:
            kmax = rank
    for rank, idx in enumerate(order, start=1):
        if rank <= kmax:
            survive[idx] = True
    return survive


# ─────────────────────────────────────────────────────────────────────────────────────────────────
# Block-level inference for the rolling-origin backtest (engine/universe.py, engine/experiment.py).
#
# The pooled Fisher-exact p in backtest/universe is OPTIMISTIC: it treats every (concept × origin)
# forecast as independent, but the same concept recurs across origins and cohort-mates share a year —
# the forecasts cluster. These functions give the HONEST replacements:
#   - block_permutation_lift: permute the FIRED label *within* correlation blocks (e.g. origin×cohort),
#     so a surrogate keeps each block's firing rate and winner labels but destroys the firing↔winning
#     association. p = (1 + #{surrogate lift ≥ observed}) / (M+1). The de-clustered events (one per
#     concept) are the independent unit → that p is the headline.
#   - block_bootstrap_lift_ci: resample whole blocks with replacement (cluster bootstrap) → a CI on
#     lift whose lower bound > 1 is the defensible "edge is real" statement.
#   - deflated_significance: Bonferroni across the pre-registered search space — every config we were
#     ALLOWED to try inflates the family, so the reported p is p_block × n_configs (capped at 1).
# Events are (block_key, fired, winner) triples; the caller chooses the block granularity. Same
# fixed-SEED determinism as the rest of this module.
# ─────────────────────────────────────────────────────────────────────────────────────────────────

def _lift_of(rows: list[tuple[bool, bool]]) -> float:
    """Lift = precision / base-rate for a set of (fired, winner) rows (0.0 if undefined)."""
    a = sum(1 for f, w in rows if f and w)
    b = sum(1 for f, w in rows if f and not w)
    c = sum(1 for f, w in rows if not f and w)
    d = sum(1 for f, w in rows if not f and not w)
    n = a + b + c + d
    if not n:
        return 0.0
    base = (a + c) / n
    precision = a / (a + b) if (a + b) else 0.0
    return precision / base if base else 0.0


def _percentile(sorted_vals: list[float], frac: float) -> float:
    if not sorted_vals:
        return 0.0
    i = min(len(sorted_vals) - 1, max(0, int(round(frac * (len(sorted_vals) - 1)))))
    return sorted_vals[i]


def _group_blocks(events: list[tuple]) -> dict:
    blocks: dict = {}
    for (bk, f, w) in events:
        blocks.setdefault(bk, []).append((bool(f), bool(w)))
    return blocks


def block_permutation_lift(events: list[tuple], *, m: int = DEFAULT_M,
                           rng: random.Random) -> dict:
    """Within-block permutation p for the observed lift. Each block's `fired` flags are shuffled
    (winners held fixed), so the null preserves block firing rates but breaks firing↔winning."""
    obs = _lift_of([(f, w) for (_, f, w) in events])
    blocks = _group_blocks(events)
    ge = 0
    for _ in range(m):
        rows: list[tuple[bool, bool]] = []
        for grp in blocks.values():
            fired = [f for (f, _) in grp]
            wins = [w for (_, w) in grp]
            rng.shuffle(fired)
            rows.extend(zip(fired, wins))
        if _lift_of(rows) >= obs:
            ge += 1
    return {"lift": obs, "p_block": (1 + ge) / (m + 1), "m": m, "n_blocks": len(blocks)}


def block_bootstrap_lift_ci(events: list[tuple], *, m: int = DEFAULT_M, rng: random.Random,
                            alpha: float = 0.10) -> tuple[float, float]:
    """Cluster bootstrap: resample whole blocks with replacement, recompute lift each draw, return
    the (alpha/2, 1-alpha/2) percentile CI. Respects within-block correlation the naive CI ignores."""
    blocks = list(_group_blocks(events).values())
    if not blocks:
        return (0.0, 0.0)
    lifts = []
    for _ in range(m):
        rows: list[tuple[bool, bool]] = []
        for _ in range(len(blocks)):
            rows.extend(blocks[rng.randrange(len(blocks))])
        lifts.append(_lift_of(rows))
    lifts.sort()
    return (_percentile(lifts, alpha / 2), _percentile(lifts, 1 - alpha / 2))


def deflated_significance(p_block: float, n_configs: int) -> float:
    """Bonferroni deflation across the pre-registered search space: the family-wise-corrected p for
    having been allowed to try `n_configs` configs. The honest headline number (capped at 1.0)."""
    return min(1.0, p_block * max(1, int(n_configs)))


# ─────────────────────────────────────────────────────────────────────────────────────────────────
# POWER ANALYSIS — close an already-revealed experiment honestly (engine/experiment.py reads this).
#
# A NULL reveal (v2: lift 0.00×, p=1.0) has two very different meanings: the signal is genuinely dead,
# OR the de-clustered test was too small to see a real-but-weak edge. The difference is POWER. Given a
# revealed test's block structure + base rate + observed fire rate, we ask: for an assumed TRUE lift L,
# how often WOULD this exact test have flagged it significant? The minimum-detectable-effect MDE_80 is
# the smallest L the test could catch ≥80% of the time. MDE_80 ≤ the fine-concept edge → the null is
# real (the test could see it and didn't); MDE_80 well above it → the null is under-powered, not a
# refutation. Reuses block_permutation_lift + deflated_significance verbatim — no new statistics, and
# it reads only ALREADY-SPENT sealed data (a closed experiment), so it burns no validity.
# ─────────────────────────────────────────────────────────────────────────────────────────────────

def _interp_mde(power_by_lift: dict, target: float = 0.80) -> float | None:
    """Smallest lift whose power ≥ target, linearly interpolated between adjacent grid points. None if
    the grid never reaches target (the test cannot reach `target` power at any lift on the grid)."""
    items = sorted(power_by_lift.items())
    for i, (L, p) in enumerate(items):
        if p >= target:
            if i == 0:
                return L
            L0, p0 = items[i - 1]
            if p <= p0:
                return L
            frac = (target - p0) / (p - p0)
            return L0 + frac * (L - L0)
    return None


def power_curve(events: list[tuple], *, lifts: tuple[float, ...] = (1.5, 2.0, 2.5, 3.0, 4.0, 5.0),
                m_inner: int = 2000, m_outer: int = 400, alpha: float = 0.05,
                n_configs_variants: tuple[int, ...] = (1,), rng: random.Random) -> dict:
    """Monte-Carlo POWER of a de-clustered block test, computed from its OWN structure.

    `events` = the OBSERVED (block_key, fired, winner) triples of the de-clustered reveal — the winner
    labels and the block partition are taken as ground truth; only `fired` is re-simulated. For each
    assumed TRUE lift L we draw m_outer synthetic datasets where each unit fires Bernoulli with a
    per-class rate that (i) preserves the observed marginal fire rate F/n and (ii) implies lift = L
    exactly in expectation: winners fire at q_w = L·F/n, losers at q_l = (F − W·q_w)/(n−W). We then run
    the SAME block_permutation_lift on each synthetic set and apply deflated_significance. power =
    P(deflated p < alpha). At L=1, q_w = q_l = F/n (pure null) → power ≈ alpha (a built-in calibration
    check). Returns one power curve per deflation denominator in `n_configs_variants` plus the
    interpolated MDE_80 for each. `max_achievable_lift` = n/F caps q_w at 1 (flagged in `caps`)."""
    units = [(bk, bool(w)) for (bk, _f, w) in events]
    n = len(units)
    W = sum(1 for (_bk, w) in units if w)
    Lo = n - W
    F = sum(1 for (_bk, f, _w) in events if f)
    result = {nc: {} for nc in n_configs_variants}
    caps: dict[float, bool] = {}
    for L in lifts:
        qw = (L * F / n) if n else 0.0
        caps[L] = qw > 1.0
        qw = min(1.0, qw)
        ql = ((F - W * qw) / Lo) if Lo > 0 else 0.0
        ql = min(1.0, max(0.0, ql))
        pblocks: list[float] = []
        for _ in range(m_outer):
            syn = [(bk, (rng.random() < (qw if w else ql)), w) for (bk, w) in units]
            pblocks.append(block_permutation_lift(syn, m=m_inner, rng=rng)["p_block"])
        for nc in n_configs_variants:
            hits = sum(1 for p in pblocks if deflated_significance(p, nc) < alpha)
            result[nc][L] = hits / m_outer if m_outer else 0.0
    return {
        "n": n, "W": W, "F": F, "Lo": Lo,
        "base_rate": (W / n if n else 0.0), "fire_rate": (F / n if n else 0.0),
        "max_achievable_lift": (n / F if F else None),
        "power": result, "caps": caps, "alpha": alpha,
        "mde_80": {nc: _interp_mde(result[nc], 0.80) for nc in n_configs_variants},
    }


def run_significance(conn: sqlite3.Connection, *, k: float = DEFAULT_K, q: float = DEFAULT_Q,
                     m: int = DEFAULT_M, require_qc: bool = True, log=print) -> dict:
    """Annotate every scanned series with an empirical p_mc + a BH-FDR survival flag.

    Mirrors run_detector's selection exactly (same QC gate, same detect() call) so N_scanned is the
    true look-elsewhere denominator. Writes last_p_mc / last_p_mc_m / last_fdr_survive / last_fdr_q
    onto the series row (folded on like the detector verdict). Run AFTER `detect`.
    """
    series = conn.execute("SELECT id, label, provider FROM series ORDER BY label").fetchall()
    health = {r["series_id"]: r["status"]
              for r in conn.execute("SELECT series_id, status FROM series_health")}
    rng = random.Random(SEED)
    scanned: list[dict] = []
    for s in series:
        if require_qc and health.get(s["id"]) == "fail":
            continue
        pts = _series_points(conn, s["id"])
        det = detect(pts, k=k)  # linear space — mirrors run_detector exactly
        if det is None:
            continue
        p, m_eff = empirical_p(pts, det.surprise_sigma, k=k, log=False, m=m, rng=rng)
        if p is None:
            continue
        scanned.append({"id": s["id"], "label": s["label"], "provider": s["provider"],
                        "observed": det.surprise_sigma, "fired": det.fired, "p": p, "m": m_eff})
        if len(scanned) % 25 == 0:
            log(f"  … {len(scanned)} series done")

    survive = benjamini_hochberg([r["p"] for r in scanned], q)
    fired_n = sum(1 for r in scanned if r["fired"])
    surv_fired = sum(1 for r, sv in zip(scanned, survive) if r["fired"] and sv)
    for r, sv in zip(scanned, survive):
        conn.execute(
            "UPDATE series SET last_p_mc=?, last_p_mc_m=?, last_fdr_survive=?, last_fdr_q=? WHERE id=?",
            (r["p"], r["m"], 1 if sv else 0, q, r["id"]),
        )
    conn.commit()

    n = len(scanned)
    n_survive = sum(1 for sv in survive if sv)
    exp_false = q * n_survive
    log(f"\nlook-elsewhere correction (empirical null, M={m}; BH-FDR q={q:.0%}):")
    log(f"  scanned {n} series · fired {fired_n} raw · {n_survive} survive BH-FDR "
        f"({surv_fired} of the fired) · expected false discoveries ≤ {exp_false:.1f}")
    floor = 1.0 / (m + 1)
    for r, sv in sorted(zip(scanned, survive), key=lambda t: t[0]["p"]):
        if not r["fired"]:
            continue
        pstr = f"p<{floor:.1g}" if r["p"] <= floor + 1e-12 else f"p={r['p']:.2g}"
        mark = "✓ survives" if sv else "✗ FDR-rejected (look-elsewhere)"
        log(f"  ⚡ {r['label'][:44]:<44} {r['observed']:>8.1f}σ  {pstr:>9}  {mark}")
    return {"scanned": n, "fired": fired_n, "fdr_survive": n_survive,
            "fired_survive": surv_fired, "q": q, "m": m, "exp_false": exp_false}
