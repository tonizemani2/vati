"""The time-machine — does the detector's call at a past cutoff hold up against what
actually happened?

This is the strongest proof the system can have: instead of waiting years for a track
record, we manufacture one from history. Cap every series at year C (the AI sees nothing
after it), let the *detector* — never a human — decide blindly where the constraint is
breaking out, then grade those calls against the future we already know (years > C).

The honesty rule is the whole point: we never hand-pick which series to forecast. The
proof is not "we called deep learning" — it's that series the method FIRED on at C
outgrew the ones it stayed silent on, by a measurable lift over the base rate. If the
fired set doesn't beat the base rate, the detector has no edge and we want to know.

Forecast (at C):   detect() on obs ≤ C  → fired? (its acceleration call, point-in-time)
Resolution (>C):   fit the ≤C trend, extrapolate, ask whether the actual future broke
                   that trend upward by ≥ k·σ — the same claim the detector makes, graded
                   on data it never saw.

Pure arithmetic, read-only (writes nothing back). Reuses the detector's robust trend +
noise floor verbatim — no second method to keep honest.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import date
from statistics import median

from engine.detector import DEFAULT_K, LOG_FLOOR, MIN_POINTS, _mad_sigma, detect, theil_sen

DEFAULT_CUTOFF = 2010
MIN_FUTURE_POINTS = 3   # need a few post-cutoff points to grade a breakout at all
# Research counts are multiplicative growth → we grade acceleration in log space, so a common
# rising tide (total science output tripled 2000–2024) is absorbed into each series' own
# exponential trend. "Broke out" then means accelerated BEYOND its established exponential,
# not merely "grew" — and the σ floor stays relative instead of collapsing on clean series.
LOG_SPACE = True

# Gain-share target: the thesis-aligned question — did rent/attention migrate *toward* this concept
# relative to its peers? We measure each concept's share of its unit-cohort's total, and call it a
# breakout if its share at the horizon is ≥ GAIN_MARGIN× its share at the cutoff (averaged over a
# small window each side, so a single noisy year can't swing it). Share is zero-sum across the
# cohort, so this can't suffer the rising-tide confound — a winner only gains share if others lose it.
GAIN_MARGIN = 1.5       # ≥50% relative share gain to count as "value migrated here"
GAIN_WINDOW = 3         # years averaged each side of the cutoff to de-noise the share estimate
MIN_COHORT = 5          # a "share" needs a real field of peers to be meaningful


@dataclass
class SeriesVerdict:
    label: str
    domain: str | None
    n_known: int
    n_future: int
    fired: bool                 # the detector's call at the cutoff (forecast)
    forecast_sigma: float       # surprise in σ within the ≤C window
    broke_out: bool             # did the actual future exceed the ≤C trend by ≥k·σ?
    future_sigma: float         # largest upward future surprise vs the ≤C trend


def _points_by_year(conn: sqlite3.Connection, series_id: str) -> list[tuple[float, float, int]]:
    """Observations as (x=fractional year, value, calendar_year), ordered by date."""
    rows = conn.execute(
        "SELECT as_of, value FROM observations WHERE series_id = ? ORDER BY as_of",
        (series_id,),
    ).fetchall()
    out = []
    for r in rows:
        d = date.fromisoformat(r["as_of"])
        x = d.year + (d.timetuple().tm_yday - 1) / 365.25
        out.append((x, float(r["value"]), d.year))
    return out


def _resolve(known: list[tuple[float, float]], future: list[tuple[float, float]],
             k: float, *, log: bool = False) -> tuple[bool, float]:
    """Grade the future against the ≤C trend: did it break out upward by ≥k·σ?

    Same robust machinery the detector uses — Theil–Sen trend + MAD noise floor — but fit
    on ALL known points and extrapolated across the held-out future the AI never saw. With
    `log`, the trend is fit in log(y), so a breakout is acceleration beyond the established
    exponential (tide-independent) and σ stays relative — matching the detector's forecast space.
    """
    def t(y: float) -> float:
        return math.log(max(y, LOG_FLOOR)) if log else y
    xs = [p[0] for p in known]
    ys = [t(p[1]) for p in known]
    slope, intercept = theil_sen(xs, ys)
    resid = [ys[i] - (slope * xs[i] + intercept) for i in range(len(xs))]
    sigma = _mad_sigma(resid)
    if sigma <= 0:  # perfectly clean early trend — same scale-aware floor as the detector
        sigma = max((max(ys) - min(ys)) * 1e-6, 1e-9)
    surprises = [(t(y) - (slope * x + intercept)) / sigma for x, y in future]
    future_sigma = min(max(surprises), 1e6) if surprises else 0.0
    return future_sigma >= k, future_sigma


def _cohort_totals(conn: sqlite3.Connection) -> tuple[dict, dict]:
    """Per unit-cohort yearly totals + member counts. A cohort = (provider, metric, unit), so
    'share' is only ever computed among genuinely comparable series (works/year vs works/year)."""
    rows = conn.execute(
        "SELECT s.provider, s.metric, s.unit, CAST(strftime('%Y', o.as_of) AS INT) yr, "
        "SUM(o.value) tot, COUNT(DISTINCT s.id) n "
        "FROM series s JOIN observations o ON o.series_id = s.id "
        "GROUP BY s.provider, s.metric, s.unit, yr"
    ).fetchall()
    totals: dict = {}
    members: dict = {}
    for r in rows:
        key = (r["provider"], r["metric"], r["unit"])
        totals.setdefault(key, {})[r["yr"]] = r["tot"]
        members[key] = max(members.get(key, 0), r["n"])
    return totals, members


def _resolve_gain_share(pts: list[tuple[float, float, int]], totals: dict[int, float],
                        cutoff: int, *, margin: float = GAIN_MARGIN) -> tuple[bool, float] | None:
    """Did this concept gain share of its cohort by the horizon? Share = value / cohort total that
    year; compare the mean share over the last GAIN_WINDOW known years to the mean over the last
    GAIN_WINDOW future years. Returns (gained, share-multiple), or None if shares are unavailable.

    `margin` is the share-gain threshold (default GAIN_MARGIN, frozen); the experiment harness varies
    it only within the pre-registered search_space (experiments/protocol_v1.yaml)."""
    def share(yr: int, val: float) -> float | None:
        tot = totals.get(yr)
        return val / tot if tot else None
    start = [share(yr, v) for (_, v, yr) in pts if cutoff - GAIN_WINDOW < yr <= cutoff]
    fut_years = sorted({yr for (_, _, yr) in pts if yr > cutoff})
    end_years = set(fut_years[-GAIN_WINDOW:])
    end = [share(yr, v) for (_, v, yr) in pts if yr in end_years]
    start = [s for s in start if s]
    end = [s for s in end if s]
    if not start or not end:
        return None
    ss, se = sum(start) / len(start), sum(end) / len(end)
    mult = se / ss if ss > 0 else float("inf")
    return mult >= margin, min(mult, 1e6)


def backtest(conn: sqlite3.Connection, *, cutoff: int = DEFAULT_CUTOFF, k: float = DEFAULT_K,
             target: str = "gain_share") -> dict:
    """Run the time-machine at `cutoff` across every eligible series. Read-only.

    `target` picks what the forecast is graded against:
      - "gain_share"   — did the concept gain share of its peer cohort by the horizon? (thesis-aligned)
      - "acceleration" — did it accelerate beyond its own established (log) trend? (the curve view)
    The forecast itself — the detector firing at the cutoff — is identical either way.
    """
    series = conn.execute(
        "SELECT id, label, domain, provider, metric, unit FROM series ORDER BY label"
    ).fetchall()
    totals, members = _cohort_totals(conn)
    verdicts: list[SeriesVerdict] = []
    skipped = 0
    for s in series:
        pts = _points_by_year(conn, s["id"])
        known = [(x, v) for (x, v, yr) in pts if yr <= cutoff]
        future = [(x, v) for (x, v, yr) in pts if yr > cutoff]
        if len(known) < MIN_POINTS or len(future) < MIN_FUTURE_POINTS:
            skipped += 1
            continue
        # no look-ahead, enforced (not just claimed): the forecast input ends at the cutoff and
        # every graded fact comes strictly after it. This is the skeptic's kill for Rung 3.
        known_years = [yr for (_, _, yr) in pts if yr <= cutoff]
        assert max(known_years) <= cutoff < min(yr for (_, _, yr) in pts if yr > cutoff)
        det = detect(known, k=k, log=LOG_SPACE)         # the forecast: blind call at the cutoff
        if det is None:
            skipped += 1
            continue
        if target == "gain_share":
            cohort = (s["provider"], s["metric"], s["unit"])
            if members.get(cohort, 0) < MIN_COHORT:      # share needs a real field of peers
                skipped += 1
                continue
            res = _resolve_gain_share(pts, totals.get(cohort, {}), cutoff)
            if res is None:
                skipped += 1
                continue
            broke, fut_sigma = res
        else:
            broke, fut_sigma = _resolve(known, future, k, log=LOG_SPACE)
        verdicts.append(SeriesVerdict(
            label=s["label"], domain=s["domain"],
            n_known=len(known), n_future=len(future),
            fired=det.fired, forecast_sigma=det.surprise_sigma,
            broke_out=broke, future_sigma=fut_sigma,
        ))

    n = len(verdicts)
    n_broke = sum(1 for v in verdicts if v.broke_out)
    base_rate = n_broke / n if n else 0.0
    fired = [v for v in verdicts if v.fired]
    silent = [v for v in verdicts if not v.fired]
    hit_fired = sum(1 for v in fired if v.broke_out)
    hit_silent = sum(1 for v in silent if v.broke_out)
    precision = hit_fired / len(fired) if fired else 0.0      # P(broke | fired)
    silent_rate = hit_silent / len(silent) if silent else 0.0  # P(broke | silent)
    recall = hit_fired / n_broke if n_broke else 0.0           # P(fired | broke)
    lift = precision / base_rate if base_rate else 0.0

    # Brier with a transparent, *unfitted* probability map: p = logistic(surprise − k),
    # so the call sits at p=0.5 exactly at the firing threshold. Compared against the
    # naive baseline of always predicting the base rate — the bar any real edge must clear.
    def p_of(v: SeriesVerdict) -> float:
        return 1.0 / (1.0 + math.exp(-(v.forecast_sigma - k)))
    brier_model = (sum((p_of(v) - (1.0 if v.broke_out else 0.0)) ** 2 for v in verdicts) / n) if n else 0.0
    brier_base = (sum((base_rate - (1.0 if v.broke_out else 0.0)) ** 2 for v in verdicts) / n) if n else 0.0

    return {
        "cutoff": cutoff, "k": k, "target": target, "scored": n, "skipped": skipped,
        "base_rate": base_rate, "n_broke": n_broke,
        "n_fired": len(fired), "precision": precision, "recall": recall,
        "silent_rate": silent_rate, "lift": lift,
        "brier_model": brier_model, "brier_base": brier_base,
        "verdicts": verdicts,
    }


def run_backtest(conn: sqlite3.Connection, *, cutoff: int = DEFAULT_CUTOFF, k: float = DEFAULT_K,
                 target: str = "gain_share", log=print) -> dict:
    """Run the backtest and print the honest report — confusion, lift, Brier, hits & misses."""
    r = backtest(conn, cutoff=cutoff, k=k, target=target)
    is_share = r["target"] == "gain_share"
    headline = "gained share of its field" if is_share else "accelerated beyond its own trend"
    fut = (lambda v: f"{v.future_sigma:5.1f}× share") if is_share else (lambda v: f"{v.future_sigma:6.1f}σ")
    log(f"\n⏳ TIME-MACHINE — data capped at {r['cutoff']}, graded on {r['cutoff']+1}–2024 "
        f"(k={r['k']}, target: {r['target']})")
    log(f"   breakout := concept {headline} by the horizon")
    log(f"   scored {r['scored']} series ({r['skipped']} skipped: too few points / no peer field)\n")

    log(f"   base rate (any series breaks out)      {r['base_rate']*100:5.1f}%  ({r['n_broke']}/{r['scored']})")
    log(f"   detector FIRED at {r['cutoff']} → broke out   {r['precision']*100:5.1f}%  (precision)")
    log(f"   detector SILENT  → broke out           {r['silent_rate']*100:5.1f}%")
    log(f"   recall (of breakouts, % caught)        {r['recall']*100:5.1f}%")
    lift_note = "edge ✅" if r["lift"] > 1.0 else "NO edge ❌"
    log(f"   ── LIFT (precision ÷ base rate)         {r['lift']:5.2f}×  {lift_note}")
    brier_note = "beats baseline ✅" if r["brier_model"] < r["brier_base"] else "no better than base rate ❌"
    log(f"   Brier  model {r['brier_model']:.3f}  vs  baseline {r['brier_base']:.3f}   {brier_note}\n")

    # specificity on the known laggards — series a 2010 observer would call hyped/uncertain.
    # The detector SHOULD mostly stay silent on these; if it fires on them, that's a false alarm.
    laggards = [v for v in r["verdicts"] if (v.domain or "") == "laggard"]
    if laggards:
        silent = sum(1 for v in laggards if not v.fired)
        log(f"   🧪 known laggards: detector stayed silent on {silent}/{len(laggards)} "
            f"(specificity {silent/len(laggards)*100:.0f}%)\n")

    hits = sorted([v for v in r["verdicts"] if v.fired and v.broke_out],
                  key=lambda v: -v.forecast_sigma)
    misses = sorted([v for v in r["verdicts"] if v.fired and not v.broke_out],
                    key=lambda v: -v.forecast_sigma)
    surprises = sorted([v for v in r["verdicts"] if not v.fired and v.broke_out],
                       key=lambda v: -v.future_sigma)
    if hits:
        log("   ✅ called it (fired → broke out):")
        for v in hits:
            log(f"      {v.label[:38]:<38} forecast {v.forecast_sigma:6.1f}σ → {fut(v)}")
    if misses:
        log("   ❌ false alarm (fired → stayed flat):")
        for v in misses:
            log(f"      {v.label[:38]:<38} forecast {v.forecast_sigma:6.1f}σ → {fut(v)}")
    if surprises:
        log("   ⚠️  missed it (silent → broke out anyway):")
        for v in surprises:
            log(f"      {v.label[:38]:<38} {fut(v)}")
    return r


# --- rolling-origin sweep: turn one cutoff into a significance-tested, honestly-calibrated edge ---
# A single cutoff can be a lucky year. We re-run the time-machine at several origins, pool the
# forecasts, and ask three harder questions: does the edge hold at EVERY origin (consistency),
# could it be chance (Fisher exact), and are the probabilities honest OUT of sample (LOCO Brier)?

SWEEP_CUTOFFS = (2008, 2010, 2012, 2014, 2016)


def _fisher_exact_greater(a: int, b: int, c: int, d: int) -> float:
    """One-sided Fisher exact p for the 2×2 [[fired&broke, fired&flat],[silent&broke, silent&flat]]:
    the probability of ≥ this many 'fired & broke' by chance given the margins. Exact, deterministic,
    dependency-free (hypergeometric tail via math.comb) — a proof artifact must be reproducible."""
    row1, row2, col1, n = a + b, c + d, a + c, a + b + c + d
    if row1 in (0, n) or col1 in (0, n):
        return 1.0
    denom = math.comb(n, col1)
    p = 0.0
    for x in range(a, min(row1, col1) + 1):
        y = col1 - x
        if 0 <= y <= row2:
            p += math.comb(row1, x) * math.comb(row2, y) / denom
    return min(p, 1.0)


def _loco_brier(events: list[tuple[int, bool, bool]]) -> tuple[float, float]:
    """Honest out-of-sample calibration. For each held-out cutoff, learn the breakout rate when the
    detector FIRES vs stays SILENT from the *other* cutoffs only, then score the held-out events with
    that 2-bucket map (the least it can overfit). Baseline = the (also-LOCO) constant base rate. If
    model Brier < baseline, firing carries real predictive information the map never saw in advance."""
    cutoffs = sorted({c for (c, _, _) in events})
    if len(cutoffs) < 2:
        return 0.0, 0.0
    se_m = se_b = 0.0
    n = 0
    for held in cutoffs:
        train = [(f, br) for (c, f, br) in events if c != held]
        test = [(f, br) for (c, f, br) in events if c == held]
        if not train or not test:
            continue
        base = sum(br for (_, br) in train) / len(train)
        fired_tr = [br for (f, br) in train if f]
        silent_tr = [br for (f, br) in train if not f]
        p_fired = sum(fired_tr) / len(fired_tr) if fired_tr else base
        p_silent = sum(silent_tr) / len(silent_tr) if silent_tr else base
        for (f, br) in test:
            y = 1.0 if br else 0.0
            p = p_fired if f else p_silent
            se_m += (p - y) ** 2
            se_b += (base - y) ** 2
            n += 1
    return (se_m / n, se_b / n) if n else (0.0, 0.0)


def sweep_backtest(conn: sqlite3.Connection, *, cutoffs: tuple[int, ...] = SWEEP_CUTOFFS,
                   k: float = DEFAULT_K, target: str = "gain_share") -> dict:
    """Run the backtest at each origin, pool the forecasts, and compute the harder statistics."""
    per_cutoff = [backtest(conn, cutoff=C, k=k, target=target) for C in cutoffs]
    events = [(r["cutoff"], v.fired, v.broke_out) for r in per_cutoff for v in r["verdicts"]]
    a = sum(1 for (_, f, br) in events if f and br)
    b = sum(1 for (_, f, br) in events if f and not br)
    c = sum(1 for (_, f, br) in events if not f and br)
    d = sum(1 for (_, f, br) in events if not f and not br)
    n = a + b + c + d
    base_rate = (a + c) / n if n else 0.0
    precision = a / (a + b) if (a + b) else 0.0
    silent_rate = c / (c + d) if (c + d) else 0.0
    recall = a / (a + c) if (a + c) else 0.0
    brier_model, brier_base = _loco_brier(events)
    return {
        "cutoffs": list(cutoffs), "target": target, "k": k,
        "n": n, "n_fired": a + b, "n_broke": a + c, "a": a, "b": b, "c": c, "d": d,
        "base_rate": base_rate, "precision": precision, "silent_rate": silent_rate,
        "recall": recall, "lift": precision / base_rate if base_rate else 0.0,
        "p_value": _fisher_exact_greater(a, b, c, d),
        "brier_model": brier_model, "brier_base": brier_base, "per_cutoff": per_cutoff,
    }


def run_sweep(conn: sqlite3.Connection, *, cutoffs: tuple[int, ...] = SWEEP_CUTOFFS,
              k: float = DEFAULT_K, target: str = "gain_share", log=print) -> dict:
    """Run the rolling-origin sweep and print the hardened, honest report."""
    s = sweep_backtest(conn, cutoffs=cutoffs, k=k, target=target)
    log(f"\n⏳⏳ ROLLING-ORIGIN SWEEP — origins {s['cutoffs']}  (target: {s['target']}, k={s['k']})")
    log("   one row per time-machine origin — does the edge hold at EVERY origin, or one lucky year?\n")
    log("   origin   scored   base   precision   lift")
    n_edge = 0
    for r in s["per_cutoff"]:
        n_edge += 1 if r["lift"] > 1.0 else 0
        log(f"   {r['cutoff']}      {r['scored']:4d}   {r['base_rate']*100:4.0f}%    "
            f"{r['precision']*100:5.0f}%    {r['lift']:5.2f}×")
    log(f"\n   POOLED — {s['n']} forecasts across {len(s['cutoffs'])} origins ({s['n_fired']} fired):")
    log(f"     base rate                {s['base_rate']*100:5.1f}%")
    log(f"     FIRED → gained share     {s['precision']*100:5.1f}%   (precision)")
    log(f"     SILENT → gained share    {s['silent_rate']*100:5.1f}%")
    log(f"     recall                   {s['recall']*100:5.1f}%")
    lift_note = "edge ✅" if s["lift"] > 1.0 else "NO edge ❌"
    log(f"     ── LIFT                   {s['lift']:5.2f}×  {lift_note}  (held at {n_edge}/{len(s['cutoffs'])} origins)")
    sig = "significant ✅" if s["p_value"] < 0.05 else ("suggestive" if s["p_value"] < 0.10 else "not significant ❌")
    log(f"     Fisher exact p           {s['p_value']:.4f}   ({sig} — P(edge this large by chance))")
    bnote = "beats baseline ✅" if s["brier_model"] < s["brier_base"] else "no better ❌"
    log(f"     Brier (LOCO, honest)     model {s['brier_model']:.3f} vs baseline {s['brier_base']:.3f}   {bnote}")
    log(f"     2×2: fired&gain {s['a']} · fired&flat {s['b']} · silent&gain {s['c']} · silent&flat {s['d']}\n")
    return s
