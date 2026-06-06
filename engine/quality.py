"""Component 16 — the data quality-control harness. "No unupdated or incomplete stuff."

Per-row validation (GIGO trust rationale, no-naked-numbers) already holds at write time. This adds
the checks that were missing entirely: is each series FRESH, COMPLETE, VALID, RECONCILED across
sources, and PROVENANCED — and it folds a health verdict onto a row (`series_health`) the same way
the detector folds its verdict onto `series`. The hard gate (engine/detector.run_detector) then
SKIPS any `fail` series, and forecast/bet refuse a `fail` seed — stale/incomplete data cannot
silently reach a bet. Run order: `collect → data-audit → detect`.

Six checks, each → `ok | warn | fail`; the series status is the worst of them. Pure functions on
top, a DB runner at the bottom — no network, no LLM, no scheduler (on-demand, off the §9 ops line).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from statistics import median

from engine.schemas import _now

# Per-provider expected cadence. "annual" series are fresh if their latest point is within
# max_lag_years of the current year (publication/indexing lag — so a correctly point-in-time-capped
# series is read as fresh, NOT stale). "snapshot" series (current totals) should be re-pulled within
# max_lag_days. "frozen" series are point-in-time corpora / controls — never stale.
CADENCE: dict[str, dict] = {
    "openalex":      {"kind": "annual", "max_lag_years": 2},
    "nih_reporter":  {"kind": "annual", "max_lag_years": 3},   # FY record-load lag
    "epoch_ai":      {"kind": "annual", "max_lag_years": 2},
    "google_patents": {"kind": "annual", "max_lag_years": 6},  # priority-year capped ~5y back: recent
                                                               # years under-report (pub lag), so the
                                                               # latest RELIABLE point is ~2021 by design
    "owid":          {"kind": "annual", "max_lag_years": 3},   # OWID/agency curves publish 1–3y behind
    "arxiv":         {"kind": "snapshot", "max_lag_days": 120},
    "retro":         {"kind": "frozen"},
    "synthetic":     {"kind": "frozen"},
}
_DEFAULT_CADENCE = {"kind": "annual", "max_lag_years": 2}

# Providers whose series are allowed to have no Source (intentional, not an orphan).
_SOURCELESS_OK = {"synthetic"}

WORST = {"ok": 0, "warn": 1, "fail": 2}
_CHECK_WEIGHTS = {"fresh": 0.25, "complete": 0.25, "valid": 0.20, "prov": 0.20, "recon": 0.10}
_STATUS_VALUE = {"ok": 1.0, "warn": 0.6, "fail": 0.0, "n/a": 1.0}


def _worst(*statuses: str) -> str:
    return max((s for s in statuses if s), key=lambda s: WORST.get(s, 0), default="ok")


# ── the six checks (pure) ────────────────────────────────────────────────────


def check_freshness(provider: str, last_as_of: date | None, today: date) -> tuple[str, int | None, str]:
    cad = CADENCE.get(provider, _DEFAULT_CADENCE)
    if cad["kind"] == "frozen":
        return "ok", None, "frozen (point-in-time corpus / control)"
    if last_as_of is None:
        return "fail", None, "no observations"
    days = (today - last_as_of).days
    if cad["kind"] == "snapshot":
        lim = cad["max_lag_days"]
        if days <= lim:
            return "ok", days, f"snapshot {days}d old (≤{lim})"
        return ("warn" if days <= 2 * lim else "fail"), days, f"snapshot {days}d old (>{lim})"
    # annual
    lag_years = today.year - last_as_of.year
    lim = cad["max_lag_years"]
    if lag_years <= lim:
        return "ok", days, f"latest {last_as_of.year} (≤{lim}y lag)"
    return ("warn" if lag_years <= lim + 1 else "fail"), days, f"latest {last_as_of.year} ({lag_years}y lag >{lim})"


def check_completeness(years: list[int]) -> tuple[str, int, str]:
    if len(years) < 2:
        return "ok", 0, "single point / snapshot"
    ys = sorted(set(years))
    expected = set(range(ys[0], ys[-1] + 1))
    missing = sorted(expected - set(ys))
    if not missing:
        return "ok", 0, "no gaps"
    # longest consecutive run of missing years
    longest = run = 1
    for a, b in zip(missing, missing[1:]):
        run = run + 1 if b == a + 1 else 1
        longest = max(longest, run)
    frac = len(missing) / len(expected)
    if frac > 0.20 or longest >= 3:
        return "fail", len(missing), f"{len(missing)} gaps (longest run {longest}, {frac:.0%} missing)"
    return "warn", len(missing), f"{len(missing)} interior gap(s)"


def check_validity(series_unit: str, obs: list[sqlite3.Row]) -> tuple[str, int, str]:
    if not obs:
        return "fail", 0, "no observations"
    # unit consistency — the $/W-vs-$/kWh category-error guard
    bad_unit = [o["unit"] for o in obs if o["unit"] != series_unit]
    if bad_unit:
        return "fail", 0, f"unit mismatch: {len(bad_unit)} obs ≠ series unit '{series_unit}'"
    vals = [o["value"] for o in obs]
    is_count = "/year" in series_unit or series_unit in ("works/year", "awards/year", "patents/year")
    if is_count and any(v < 0 for v in vals):
        return "fail", 0, "negative count value"
    if any((o["uncertainty"] or 0) < 0 for o in obs):
        return "fail", 0, "negative uncertainty"
    # outliers (flagged, never auto-deleted — GIGO is the human's call)
    nz = [v for v in vals if v > 0]
    n_out = 0
    if len(nz) >= 5:
        med = median(nz)
        if med > 0:
            n_out = sum(1 for v in nz if v > 100 * med or v < med / 100)
    if n_out:
        return "warn", n_out, f"{n_out} order-of-magnitude outlier(s)"
    return "ok", 0, "in range, units consistent"


def check_provenance(provider: str, source_id: str | None, source_ok: bool) -> tuple[str, str]:
    if source_id is None:
        if provider in _SOURCELESS_OK:
            return "ok", "source-less control (allowlisted)"
        return "fail", "no Source (orphan series — GIGO)"
    if not source_ok:
        return "fail", "source_id does not resolve / empty trust rationale"
    return "ok", "sourced"


# ── DB runner ────────────────────────────────────────────────────────────────


def _series_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, label, provider, unit, source_id, domain FROM series ORDER BY label"
    ).fetchall()


def _reconciliation(conn: sqlite3.Connection) -> dict[str, tuple[str, str]]:
    """Group series by resolved entity; within an entity, capability series should co-move in
    DIRECTION over their overlapping years. Opposite directions → warn (divergence) on each. Series
    with no entity link get 'n/a' (skipped, logged as a coverage gap — not a silent pass)."""
    links = conn.execute(
        "SELECT entity_id, ref_id FROM entity_links WHERE ref_table='series'"
    ).fetchall()
    by_entity: dict[str, list[str]] = {}
    series_entity: dict[str, str] = {}
    for l in links:
        by_entity.setdefault(l["entity_id"], []).append(l["ref_id"])
        series_entity[l["ref_id"]] = l["entity_id"]

    def direction(sid: str) -> int | None:
        rows = conn.execute(
            "SELECT value FROM observations WHERE series_id=? ORDER BY as_of", (sid,)
        ).fetchall()
        if len(rows) < 3:
            return None
        first, last = rows[0]["value"], rows[-1]["value"]
        if last > first * 1.05:
            return 1
        if last < first * 0.95:
            return -1
        return 0

    out: dict[str, tuple[str, str]] = {}
    for eid, sids in by_entity.items():
        if len(sids) < 2:
            for sid in sids:
                out[sid] = ("ok", "sole series for its entity")
            continue
        dirs = {sid: direction(sid) for sid in sids}
        known = [d for d in dirs.values() if d is not None]
        diverge = (1 in known) and (-1 in known)
        for sid, d in dirs.items():
            if d is None:
                out[sid] = ("ok", "too short to reconcile")
            elif diverge:
                out[sid] = ("warn", "diverges in direction from a co-entity series")
            else:
                out[sid] = ("ok", "co-moves with entity peers")
    return out


def run_audit(conn: sqlite3.Connection, *, today: date | None = None, log=print) -> dict:
    """Audit every series; write series_health; return the data-health summary. $0, read-mostly."""
    today = today or _now().date()
    recon = _reconciliation(conn)
    rows = _series_rows(conn)
    now_iso = _now().isoformat()
    counts = {"ok": 0, "warn": 0, "fail": 0}
    scored: list[float] = []

    for s in rows:
        sid = s["id"]
        obs = conn.execute(
            "SELECT as_of, value, unit, uncertainty FROM observations WHERE series_id=? ORDER BY as_of",
            (sid,),
        ).fetchall()
        years = [date.fromisoformat(o["as_of"]).year for o in obs]
        last_as_of = date.fromisoformat(obs[-1]["as_of"]) if obs else None

        fresh, days_stale, fresh_d = check_freshness(s["provider"], last_as_of, today)
        comp, n_gaps, comp_d = check_completeness(years)
        valid, n_out, valid_d = check_validity(s["unit"], obs)
        source_ok = True
        if s["source_id"]:
            src = conn.execute(
                "SELECT trust_rationale FROM sources WHERE id=?", (s["source_id"],)
            ).fetchone()
            source_ok = bool(src and (src["trust_rationale"] or "").strip())
        prov, prov_d = check_provenance(s["provider"], s["source_id"], source_ok)
        rec_status, rec_d = recon.get(sid, ("n/a", "no entity link (coverage gap)"))
        n_rev = conn.execute(
            "SELECT COUNT(*) FROM observation_revisions WHERE series_id=?", (sid,)
        ).fetchone()[0]

        status = _worst(fresh, comp, valid, prov, rec_status if rec_status != "n/a" else "ok")
        score = sum(_CHECK_WEIGHTS[k] * _STATUS_VALUE[v] for k, v in
                    {"fresh": fresh, "complete": comp, "valid": valid, "prov": prov,
                     "recon": rec_status}.items())
        counts[status] += 1
        scored.append(score)
        detail = json.dumps({"fresh": fresh_d, "complete": comp_d, "valid": valid_d,
                             "prov": prov_d, "recon": rec_d})
        conn.execute(
            "INSERT INTO series_health (series_id,status,fresh_status,complete_status,valid_status,"
            "recon_status,prov_status,days_stale,n_gaps,n_outliers,n_revisions,health_score,detail,"
            "audited_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(series_id) DO UPDATE SET status=excluded.status,fresh_status=excluded.fresh_status,"
            "complete_status=excluded.complete_status,valid_status=excluded.valid_status,"
            "recon_status=excluded.recon_status,prov_status=excluded.prov_status,"
            "days_stale=excluded.days_stale,n_gaps=excluded.n_gaps,n_outliers=excluded.n_outliers,"
            "n_revisions=excluded.n_revisions,health_score=excluded.health_score,detail=excluded.detail,"
            "audited_at=excluded.audited_at",
            (sid, status, fresh, comp, valid, rec_status, prov, days_stale, n_gaps, n_out,
             n_rev, round(score, 3), detail, now_iso),
        )
    # global orphan check (observations pointing at a missing series)
    orphans = conn.execute(
        "SELECT COUNT(*) FROM observations o WHERE NOT EXISTS "
        "(SELECT 1 FROM series s WHERE s.id=o.series_id)"
    ).fetchone()[0]
    conn.commit()

    n = len(rows)
    overall = round(100 * (sum(scored) / n), 1) if n else 0.0
    no_entity = sum(1 for v in recon.values() if v[0] == "n/a") + (n - len(recon))
    _report(counts, overall, orphans, no_entity, n, log)
    return {"n": n, "ok": counts["ok"], "warn": counts["warn"], "fail": counts["fail"],
            "score": overall, "orphans": orphans}


def _report(counts: dict, overall: float, orphans: int, no_entity: int, n: int, log) -> None:
    log(f"\n🩺 DATA AUDIT — {n} series")
    log(f"   health score                 {overall:5.1f} / 100")
    log(f"   ok / warn / fail             {counts['ok']} / {counts['warn']} / {counts['fail']}")
    log(f"   orphan observations          {orphans}")
    log(f"   series with no entity link   {no_entity}  (reconciliation coverage gap, logged)")
    if counts["fail"]:
        log("   ⊘ failing series are skipped by the detector + refused as forecast seeds.")
