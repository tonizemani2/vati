"""Component 4 — the domain-agnostic curve/anomaly detector.

The question for every series is not "is it big?" but "is it accelerating beyond its own
noise floor?" We answer it the way an experimentalist declares a detection — against a stated
σ, with a robust trend so a couple of outliers can't manufacture a signal:

  1. Fit a robust trend (Theil–Sen slope + median intercept) on the EARLY portion of the series.
  2. Estimate the noise floor σ from that early portion's residuals (MAD-based, outlier-resistant).
  3. Extrapolate the trend across the HELD-OUT recent portion and measure the largest upward
     residual in units of σ — the "surprise."
  4. Fire iff surprise ≥ k·σ (k = 3 by default: physics-style, ~0.1% one-sided under normal noise).

A genuine acceleration (deep learning, 2008→2023) blows past its early-linear trend → large
surprise → fires. A flat/linearly-growing series stays within a few σ → silent. That asymmetry —
fire on the boom, stay quiet on the control — is the whole point (CONSTITUTION: no cry-wolf).

PERSISTENCE (redteam #1): the trigger is `max()` of the held-out window — the single largest
upward residual — chosen so a faint, early bend in ONE bin still fires (recall is sacred:
"recall at the detector, precision at the gate"; a lone spike that is noise gets killed by the
QC/FDR/supply gates downstream). But `max()` alone can't tell a genuine bend from a one-year
revision/COVID spike, and that spike would otherwise masquerade as a sustained acceleration in
the σ shown, the FDR input and the retro scoreboard. So each detection also carries a
persistence annotation — `sustained_sigma` (the MEAN held-out residual: does the whole window
sit above trend?), `n_consecutive` (longest run of points above trend) and a `sustained` flag.
This ANNOTATES the fire; it never gates it (the firing logic is unchanged — §8/universe precision
is identical by construction). A sustained fire is high-confidence; a fired-but-not-sustained one
is a likely transient.

SYMMETRY (redteam #6): the detector was one-sided — it only saw a constraint *forming* (upward
surprise). Constraint migration is half about where rent *leaves*: a bottleneck relaxing because
capital flooded in (the GPU-is-elastic story). Each detection now also carries `down_surprise_sigma`
(largest downward departure) and a `dissolving` flag (a *sustained* downturn below the established
trend) — the natural kill-signal for a live bet (the thing you shorted just got un-stuck) and a
leading demand-shift indicator. Same frozen-split caveat as the up side: it sees departure-below-
established-trend, not an in-window peak. Additive — `fired` (the up trigger) is untouched.

NOTE (2026-06-03, recall blind-spot investigation): a changepoint/slope-of-slope scan was tried
to catch an EARLY in-window break (AI-compute's 2012, only 3 pre-break points by the 2017 cutoff).
It was CUT — every variant either manufactured a false positive on the flat control (a spurious
slope fit on a short anchor) or, normalised honestly, left the break statistically indistinct from
noise. Buying that one case's recall cost sweep precision (1.93×→1.41×) and lit up pure noise — the
hindsight-machine trap. The real fix for that class of miss is an ORTHOGONAL leading channel
(citation velocity, cross-field diffusion, talent inflow), not a more trigger-happy single curve.
See execution.md §3/§8. The fixed-split detector below stands as the honest best single-channel.

Pure functions here; the DB runner at the bottom writes the verdict back onto each series row.
No network, no LLM — just arithmetic.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import date
from statistics import median, pstdev

from engine import store
from engine.schemas import _now

DEFAULT_K = 3.0
MIN_POINTS = 8          # below this, a "trend" is noise
HOLDOUT_FRAC = 0.30     # last ~30% of points are the held-out recent window
LOG_FLOOR = 0.5         # log-space guard so a zero/near-zero count can't blow up log(y)


@dataclass
class Detection:
    n: int
    slope: float            # robust units/x (here: works per year)
    sigma: float            # noise floor (1σ of early-portion residuals)
    surprise_sigma: float   # largest upward held-out residual, in units of σ — the TRIGGER (recall)
    fired: bool
    k: float
    split_index: int        # first index of the held-out window
    # --- persistence annotation (redteam #1: max() can't tell a one-point spike from a bend) ----
    # We DELIBERATELY keep firing on max() (recall — never go blind to a faint early move; the
    # gates downstream buy precision). These two carry whether that fire is a SUSTAINED bend or a
    # lone spike, so a revision/COVID-blip can't masquerade as a sustained acceleration in the σ
    # shown, the FDR input, or the retro scoreboard. Annotate, don't gate.
    sustained_sigma: float = 0.0   # MEAN held-out residual in σ — does the WHOLE window sit above trend?
    n_consecutive: int = 0         # longest run of consecutive held-out points above the trend
    sustained: bool = False        # the bend held across ≥half the held-out window (not one point)
    # --- symmetric channel (redteam #6): the constraint DISSOLVING, not forming ----
    down_surprise_sigma: float = 0.0  # largest DOWNWARD held-out departure, in units of σ
    n_consecutive_down: int = 0       # longest run of held-out points BELOW the trend
    dissolving: bool = False          # sustained downturn below the established trend (the kill-signal)


def theil_sen(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Robust line fit: slope = median of pairwise slopes; intercept = median(y - slope·x)."""
    slopes = [
        (ys[j] - ys[i]) / (xs[j] - xs[i])
        for i in range(len(xs)) for j in range(i + 1, len(xs))
        if xs[j] != xs[i]
    ]
    slope = median(slopes) if slopes else 0.0
    intercept = median([y - slope * x for x, y in zip(xs, ys)])
    return slope, intercept


def _mad_sigma(residuals: list[float]) -> float:
    """Robust σ via the median absolute deviation (1.4826·MAD ≈ σ for normal noise)."""
    if not residuals:
        return 0.0
    med = median(residuals)
    mad = median([abs(r - med) for r in residuals])
    return 1.4826 * mad


def detect(points: list[tuple[float, float]], *, k: float = DEFAULT_K, log: bool = False) -> Detection | None:
    """Core detector. `points` = [(x, y)] ordered by x. Returns None if too few points.

    Trains the robust trend + noise floor on the early portion, then measures the largest
    upward surprise across the held-out recent portion in units of σ.

    `log=True` fits everything in log(y) — the right space for multiplicative growth (research
    counts, compute). It absorbs a common rising tide into each series' own exponential slope,
    so "surprise" means accelerated *beyond its established exponential*, and the σ floor stays
    relative (it doesn't collapse to ~0 on a clean early series). Default False = unchanged.
    """
    pts = sorted(points)
    n = len(pts)
    if n < MIN_POINTS:
        return None
    xs = [p[0] for p in pts]
    ys = [math.log(max(p[1], LOG_FLOOR)) for p in pts] if log else [p[1] for p in pts]

    holdout = max(2, round(HOLDOUT_FRAC * n))
    split = n - holdout
    if split < 4:  # need a few points to fit a trend at all
        return None

    slope, intercept = theil_sen(xs[:split], ys[:split])
    train_resid = [ys[i] - (slope * xs[i] + intercept) for i in range(split)]

    sigma = _mad_sigma(train_resid)
    if sigma <= 0:
        # MAD is blind to the noise scale on a clean OR quantized early window — e.g. small-integer
        # counts like field_breadth (fields spanned/month), where the early portion barely moves.
        # The old fallback (spread·1e-6) collapsed σ to ~0, so ANY later jump exploded to the 1e6 cap
        # — the artifact that buried the real signals under fake 1,000,000σ rows. Floor honestly: the
        # residual stdev (catches variation MAD misses on tiny samples), else a scale-aware floor (5%
        # of the early level/range) so a genuine departure reads in believable σ, not infinity.
        sd = pstdev(train_resid) if len(train_resid) > 1 else 0.0
        scale = max(max(ys[:split]) - min(ys[:split]), abs(median(ys[:split])))
        sigma = max(sd, scale * 0.05, 1e-9)

    # departure from the extrapolated trend over the held-out window, in units of σ
    surprises = [(ys[i] - (slope * xs[i] + intercept)) / sigma for i in range(split, n)]
    surprise = max(surprises) if surprises else 0.0           # the TRIGGER — max, for recall
    surprise = min(surprise, 1e6)  # guard pathological blow-ups

    # persistence annotation (NOT a trigger): is the held-out window sustained-above-trend or a spike?
    sustained_sigma = sum(surprises) / len(surprises) if surprises else 0.0
    best = run = 0
    for sv in surprises:
        run = run + 1 if sv > 0 else 0
        best = max(best, run)
    sustained = best >= max(2, math.ceil(holdout / 2))

    # SYMMETRIC channel (redteam #6): the largest DOWNWARD departure — a constraint *dissolving*. The
    # up-surprise sees a bottleneck forming; this sees one relaxing (capital flooded in, supply caught
    # up), the natural kill-signal for a live bet + a leading demand-shift tell. `dissolving` requires a
    # SUSTAINED downturn (same persistence bar), so a one-point dip isn't mistaken for a regime change.
    down_surprise = min(max(0.0, -min(surprises)) if surprises else 0.0, 1e6)
    best_d = run_d = 0
    for sv in surprises:
        run_d = run_d + 1 if sv < 0 else 0
        best_d = max(best_d, run_d)
    dissolving = down_surprise >= k and best_d >= max(2, math.ceil(holdout / 2))

    return Detection(
        n=n, slope=slope, sigma=sigma, surprise_sigma=surprise,
        fired=surprise >= k, k=k, split_index=split,
        sustained_sigma=min(sustained_sigma, 1e6), n_consecutive=best, sustained=sustained,
        down_surprise_sigma=down_surprise, n_consecutive_down=best_d, dissolving=dissolving,
    )


# --- threshold detector: the SLOW-constraint sibling (the aperture, 2026-06-04) ------------------
# The detector above hunts ACCELERATION (2nd derivative) — a tech-buildout signature. But constraints
# also migrate from SLOW, non-exponential forces that trip no σ-detector: demographics (a workforce
# peaking), resource depletion (water/arable per capita falling), aging (dependency rising). These bind
# by crossing a MECHANISM-DEFINED THRESHOLD on a slow trend, not by surprising a noise floor. So this is
# a different instrument: a robust trend → does the LEVEL cross a sourced threshold, and when? The signal
# is years-to-bind, not σ. (execution §7 — the largest honest gap, now opened.)


@dataclass
class ThresholdSignal:
    current: float          # latest value
    slope: float            # robust units/year over the recent window (Theil–Sen)
    threshold: float | None # the mechanism-defined binding level (None for a 'peak' constraint)
    direction: str          # 'falling' (binds below) | 'rising' (binds above) | 'peak' (binds when slope<0)
    crossed: bool           # the constraint is binding NOW
    years_to_cross: float | None  # years until it binds, if approaching; None if crossed/moving away
    status: str             # 'binding' | 'crossing_soon' | 'approaching' | 'stable'


def detect_threshold(points: list[tuple[float, float]], *, threshold: float | None = None,
                     direction: str = "falling", window: int = 12, soon: float = 10.0,
                     horizon: float = 30.0) -> ThresholdSignal | None:
    """Slow-constraint signal: a robust recent trend vs a mechanism threshold → years-to-bind.

    `direction='peak'` (no level): binding once the recent slope turns negative (the quantity peaked —
    e.g. a working-age population). 'falling'/'rising': binding once the level is past `threshold`;
    otherwise project the robust slope to estimate years-to-cross. Pure arithmetic, no network.
    """
    pts = sorted(points)
    if len(pts) < MIN_POINTS:
        return None
    recent = pts[-window:] if len(pts) > window else pts
    xs = [p[0] for p in recent]
    ys = [p[1] for p in recent]
    slope, _ = theil_sen(xs, ys)
    current = pts[-1][1]

    if direction == "peak":
        crossed = slope < 0                       # already declining from the peak = binding
        status = "binding" if crossed else "approaching"
        return ThresholdSignal(current, slope, None, "peak", crossed, None, status)

    if threshold is None:
        return None
    if direction == "falling":
        crossed = current <= threshold
        ytc = (current - threshold) / (-slope) if (slope < 0 and not crossed) else None
    else:  # rising
        crossed = current >= threshold
        ytc = (threshold - current) / slope if (slope > 0 and not crossed) else None

    if crossed:
        status = "binding"
    elif ytc is not None and ytc <= soon:
        status = "crossing_soon"
    elif ytc is not None and ytc <= horizon:
        status = "approaching"
    else:
        status = "stable"
    return ThresholdSignal(current, slope, threshold, direction, crossed, ytc, status)


# --- DB runner ----------------------------------------------------------------


def _series_points(conn: sqlite3.Connection, series_id: str) -> list[tuple[float, float]]:
    """Observations as (x=fractional year, y=value), ordered."""
    rows = conn.execute(
        "SELECT as_of, value FROM observations WHERE series_id = ? ORDER BY as_of",
        (series_id,),
    ).fetchall()
    out = []
    for r in rows:
        d = date.fromisoformat(r["as_of"])
        x = d.year + (d.timetuple().tm_yday - 1) / 365.25
        out.append((float(x), float(r["value"])))
    return out


def run_detector(conn: sqlite3.Connection, *, k: float = DEFAULT_K, require_qc: bool = True,
                 log=print) -> dict:
    """Run the detector over every series; write the verdict + precompute onto each series row.

    The QC gate (A5): when `require_qc`, a series whose `series_health.status='fail'` is SKIPPED
    with a logged reason — stale/incomplete data cannot silently feed a forecast. `warn`/unaudited
    series still run (the warning rides along on the forecast). Precompute (A6) is folded on for
    EVERY series (even ones too short to detect) so the cockpit list view never scans observations.
    """
    series = conn.execute("SELECT id, label, metric FROM series ORDER BY label").fetchall()
    health = {r["series_id"]: r["status"]
              for r in conn.execute("SELECT series_id, status FROM series_health")}
    fired = skipped = scanned = gated = dissolving = 0
    now_iso = _now().isoformat()
    fired_labels: list[str] = []
    dissolving_labels: list[str] = []
    for s in series:
        store.write_precompute(conn, s["id"])     # A6 — always, even if too short to detect
        if require_qc and health.get(s["id"]) == "fail":
            gated += 1
            log(f"  ⊘ QC-gated (data-health fail): {s['label']}")
            continue
        pts = _series_points(conn, s["id"])
        det = detect(pts, k=k)
        if det is None:
            skipped += 1
            continue
        scanned += 1
        conn.execute(
            "UPDATE series SET last_run_at=?, last_slope=?, last_sigma=?, "
            "last_surprise_sigma=?, last_fired=?, last_k=?, "
            "last_sustained_sigma=?, last_n_consecutive=?, "
            "last_down_surprise_sigma=?, last_dissolving=? WHERE id=?",
            (now_iso, det.slope, det.sigma, det.surprise_sigma,
             1 if det.fired else 0, det.k, det.sustained_sigma, det.n_consecutive,
             det.down_surprise_sigma, 1 if det.dissolving else 0, s["id"]),
        )
        if det.fired:
            fired += 1
            tag = "sustained" if det.sustained else "⚠ transient (1-pt spike?)"
            fired_labels.append(
                f"{s['label']} ({det.surprise_sigma:.1f}σ; mean {det.sustained_sigma:.1f}σ, "
                f"{det.n_consecutive} consec — {tag})")
        if det.dissolving:
            dissolving += 1
            dissolving_labels.append(f"{s['label']} (↓{det.down_surprise_sigma:.1f}σ, "
                                     f"{det.n_consecutive_down} consec below trend)")
    conn.commit()
    gate_note = f"; {gated} QC-gated" if gated else ""
    diss_note = f"; {dissolving} dissolving (↓ kill-signal)" if dissolving else ""
    log(f"scanned {scanned} series (skipped {skipped} as too short{gate_note}); "
        f"{fired} fired at k={k}{diss_note}")
    for lbl in sorted(fired_labels):
        log(f"  ⚡ {lbl}")
    for lbl in sorted(dissolving_labels):
        log(f"  ✦ dissolving: {lbl}")
    return {"scanned": scanned, "fired": fired, "skipped": skipped, "qc_gated": gated,
            "dissolving": dissolving}
