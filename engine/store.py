"""Observation storage with point-in-time integrity (A6).

The collectors used to do a bare `INSERT ... ON CONFLICT DO UPDATE` that silently overwrote a
historical value when a source revised it. That is a look-ahead leak in disguise: a 2019 count
read in 2024 may differ from one read in 2026, and the backtest at as_of must be able to know
which value was knowable *when*. So every change to an existing (series_id, as_of) value appends
the OLD value to `observation_revisions` before the upsert — the latest lives in `observations`,
the history is never destroyed (the same supersede-not-edit discipline as forecast cards, rule 7).

`bulk_upsert_observations` is the scale path: one transaction, `executemany`, the revision diff
done in batch. Pydantic validation still runs per-Observation upstream, so the GIGO gate stands.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict

from engine.schemas import Observation, _now, _uid


def _existing(conn: sqlite3.Connection, series_ids: set[str]) -> dict[tuple[str, str], sqlite3.Row]:
    """Map (series_id, as_of_iso) → existing row, for the series touched by a batch (one query each)."""
    out: dict[tuple[str, str], sqlite3.Row] = {}
    for sid in series_ids:
        for r in conn.execute(
            "SELECT as_of, value, uncertainty, created_at FROM observations WHERE series_id=?", (sid,)
        ):
            out[(sid, r["as_of"])] = r
    return out


def _revision_row(o: Observation, prev: sqlite3.Row, reason: str) -> tuple:
    return (
        _uid(), o.series_id, o.as_of.isoformat(), prev["value"], o.value,
        prev["uncertainty"], prev["created_at"], _now().isoformat(), reason,
    )


_OBS_INSERT = (
    "INSERT INTO observations (id,series_id,as_of,value,unit,uncertainty,created_at) "
    "VALUES (?,?,?,?,?,?,?) "
    "ON CONFLICT(series_id,as_of) DO UPDATE SET value=excluded.value, uncertainty=excluded.uncertainty"
)
_REV_INSERT = (
    "INSERT INTO observation_revisions "
    "(id,series_id,as_of,old_value,new_value,old_uncertainty,old_created_at,revised_at,reason) "
    "VALUES (?,?,?,?,?,?,?,?,?)"
)


def precompute_series(conn: sqlite3.Connection, series_id: str) -> dict:
    """Endpoints + sparkline for a series, computed once (A6). The detector folds this onto the
    series row so the cockpit list view reads a flat row and never scans observations."""
    rows = conn.execute(
        "SELECT as_of, value FROM observations WHERE series_id=? ORDER BY as_of", (series_id,)
    ).fetchall()
    if not rows:
        return {"n_obs": 0, "first_as_of": None, "last_as_of": None,
                "first_val": None, "last_val": None, "spark": None}
    vals = [r["value"] for r in rows]
    return {
        "n_obs": len(rows),
        "first_as_of": rows[0]["as_of"], "last_as_of": rows[-1]["as_of"],
        "first_val": vals[0], "last_val": vals[-1],
        "spark": ",".join(f"{v:g}" for v in vals),
    }


def write_precompute(conn: sqlite3.Connection, series_id: str) -> None:
    """Compute + persist the precompute fields onto the series row."""
    pc = precompute_series(conn, series_id)
    conn.execute(
        "UPDATE series SET n_obs=?, first_as_of=?, last_as_of=?, first_val=?, last_val=?, spark=? "
        "WHERE id=?",
        (pc["n_obs"], pc["first_as_of"], pc["last_as_of"], pc["first_val"], pc["last_val"],
         pc["spark"], series_id),
    )


def upsert_observation(conn: sqlite3.Connection, o: Observation, *,
                       reason: str = "collector_revision") -> None:
    """Upsert one observation; log a revision first if it CHANGES an existing point-in-time value."""
    prev = conn.execute(
        "SELECT value, uncertainty, created_at FROM observations WHERE series_id=? AND as_of=?",
        (o.series_id, o.as_of.isoformat()),
    ).fetchone()
    if prev is not None and prev["value"] != o.value:
        conn.execute(_REV_INSERT, _revision_row(o, prev, reason))
    conn.execute(_OBS_INSERT, (o.id, o.series_id, o.as_of.isoformat(), o.value, o.unit,
                               o.uncertainty, o.created_at.isoformat()))


def bulk_upsert_observations(conn: sqlite3.Connection, rows: list[Observation], *,
                             reason: str = "collector_revision") -> dict:
    """Batch upsert in one transaction with the revision hook. Returns counts (inserted/revised)."""
    if not rows:
        return {"written": 0, "revised": 0}
    by_series: dict[str, list[Observation]] = defaultdict(list)
    for o in rows:
        by_series[o.series_id].append(o)
    existing = _existing(conn, set(by_series))

    revisions: list[tuple] = []
    obs_params: list[tuple] = []
    for o in rows:
        prev = existing.get((o.series_id, o.as_of.isoformat()))
        if prev is not None and prev["value"] != o.value:
            revisions.append(_revision_row(o, prev, reason))
        obs_params.append((o.id, o.series_id, o.as_of.isoformat(), o.value, o.unit,
                           o.uncertainty, o.created_at.isoformat()))
    if revisions:
        conn.executemany(_REV_INSERT, revisions)
    conn.executemany(_OBS_INSERT, obs_params)
    conn.commit()
    return {"written": len(obs_params), "revised": len(revisions)}
