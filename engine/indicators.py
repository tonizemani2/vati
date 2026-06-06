"""Component 11d — the leading-indicator / driver tracker. Forecast the drivers, not the endpoints.

A thesis card (and a promoted/survived hypothesis) carries dated, numeric KILL-CRITERIA. Those are
not just falsifiers waiting for a 2027–28 resolution date — they are observable leading indicators
RIGHT NOW. This module makes a subset of them machine-readable: each `card_drivers` row links one
kill-criterion to an existing `series` + a falsification threshold + a direction. The tracker then
reads the latest observation and the series' own recent shape and emits, per driver, a status
(on_track | approaching | falsified) and a continuous fast-clock partial signal — so the oracle's
LIVE structural calls get a scoreboard years before the slow resolution date.

It is an OBSERVER. It never writes to `forecast_cards` / `hypotheses` and never moves a probability
(rule 7 — a card is immutable; only superseded). It mirrors the rest of the engine:
  • the GIGO gate at link time refuses a 'fail'-QC series (like forecast._assert_seed_qc),
  • the trend math is sharpen.extract (drift/vol/accel — no new statistics),
  • the value source is `observations` (single source of truth — nothing is cached on the link),
  • status/partial are COMPUTED on read, so they can never go stale (like series_health is recomputed).

This is the distinction the doctrine draws between *situational awareness* (a calibrated map + the
drivers to watch) and a tradeable bet: the driver tracker IS the map's live instrument panel.

Pure-ish: the only I/O is SQLite. No network, no LLM — which series proxies which kill-criterion is
Claude's judgment, in-session, logged at $0 like every other reasoning step. stdlib only.
"""

from __future__ import annotations

import math
import sqlite3
import uuid

from engine import sharpen
from engine.schemas import _now

DIRECTIONS = ("fails_below", "fails_above")   # which way the metric trips the kill-criterion
CONFIRM_DIRS = ("up", "down")                 # which trend direction moves TOWARD confirmation
APPROACH_SIGMA = 1.0                          # within ~1 annual step of the threshold = "approaching"


# --- the link (the in-session judgment, gated) -------------------------------


def _series_row(conn: sqlite3.Connection, series_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT id, label FROM series WHERE id=?", (series_id,)).fetchone()


def link_driver(conn: sqlite3.Connection, *, series_id: str, threshold: float, direction: str,
                confirm_dir: str, card_id: str | None = None, hypothesis_id: str | None = None,
                kill_index: int | None = None, note: str = "") -> dict:
    """Link one kill-criterion / driver to a series. Idempotent (upsert on the unique key).

    GIGO + invariants enforced here, never downstream:
      • exactly one of card_id / hypothesis_id,
      • direction ∈ DIRECTIONS, confirm_dir ∈ CONFIRM_DIRS,
      • the series exists AND has not failed data-audit (a 'fail' QC series cannot ground a driver,
        mirroring forecast._assert_seed_qc — stale/incomplete data must not pose as a live signal),
      • the parent card/hypothesis exists.
    """
    if bool(card_id) == bool(hypothesis_id):
        raise ValueError("exactly one of card_id / hypothesis_id must be set (a driver hangs off one).")
    if direction not in DIRECTIONS:
        raise ValueError(f"direction must be one of {DIRECTIONS}, got {direction!r}.")
    if confirm_dir not in CONFIRM_DIRS:
        raise ValueError(f"confirm_dir must be one of {CONFIRM_DIRS}, got {confirm_dir!r}.")
    if _series_row(conn, series_id) is None:
        raise ValueError(f"unknown series {series_id} — link a driver to a real series id.")
    health = conn.execute(
        "SELECT status, detail FROM series_health WHERE series_id=?", (series_id,)).fetchone()
    if health and health["status"] == "fail":
        raise ValueError(
            f"driver refused: series {series_id} failed data-audit ({health['detail']}). A stale/"
            f"incomplete series cannot ground a leading indicator — fix it and re-run `data-audit` "
            f"(GIGO gate, mirrors the forecast seed gate A5).")
    if card_id and conn.execute("SELECT 1 FROM forecast_cards WHERE id=?", (card_id,)).fetchone() is None:
        raise ValueError(f"no forecast card {card_id}.")
    if hypothesis_id and conn.execute("SELECT 1 FROM hypotheses WHERE id=?", (hypothesis_id,)).fetchone() is None:
        raise ValueError(f"no hypothesis {hypothesis_id}.")

    existing = conn.execute(
        "SELECT id FROM card_drivers WHERE card_id IS ? AND hypothesis_id IS ? AND series_id=? "
        "AND kill_index IS ?", (card_id, hypothesis_id, series_id, kill_index)).fetchone()
    if existing:
        conn.execute(
            "UPDATE card_drivers SET threshold=?, direction=?, confirm_dir=?, note=? WHERE id=?",
            (threshold, direction, confirm_dir, note, existing["id"]))
        conn.commit()
        return {"id": existing["id"], "updated": True}
    did = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO card_drivers "
        "(id, card_id, hypothesis_id, series_id, kill_index, threshold, direction, confirm_dir, "
        " note, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (did, card_id, hypothesis_id, series_id, kill_index, threshold, direction, confirm_dir,
         note, _now().isoformat()))
    conn.commit()
    return {"id": did, "updated": False}


# --- the read (status + fast-clock partial, computed, never stored) ----------


def _series_values(conn: sqlite3.Connection, series_id: str) -> list[tuple[str, float]]:
    return [(r["as_of"], float(r["value"])) for r in conn.execute(
        "SELECT as_of, value FROM observations WHERE series_id=? ORDER BY as_of", (series_id,))]


def driver_status(conn: sqlite3.Connection, driver: sqlite3.Row | dict) -> dict:
    """Read the series' latest value + recent trend → the driver's live verdict.

    Returns {series_id, label, value, as_of, threshold, direction, confirm_dir, margin_sigma, trend,
    partial, status}. `margin_sigma` is the signed distance to the threshold in units of one typical
    annual step (>0 = on the confirming side); `trend` ∈ {toward_confirm, toward_falsify, flat, n/a}
    is the series' drift judged against confirm_dir; `partial` ∈ [0,1] is the fast-clock signal
    (1 = comfortably confirming & trending right, 0 = falsified); `status` ∈ {on_track, approaching,
    falsified, no_data}.
    """
    d = dict(driver)
    sid = d["series_id"]
    threshold, direction, confirm_dir = d["threshold"], d["direction"], d["confirm_dir"]
    srow = _series_row(conn, sid)
    label = srow["label"] if srow else sid
    vals = _series_values(conn, sid)
    base = {"series_id": sid, "label": label, "threshold": threshold,
            "direction": direction, "confirm_dir": confirm_dir}
    if not vals:
        return {**base, "value": None, "as_of": None, "margin_sigma": None,
                "trend": "n/a", "partial": None, "status": "no_data"}
    as_of, value = vals[-1]

    # Signed margin to the threshold, on the CONFIRMING side (>0 = safe, <0 = the kill-criterion tripped).
    signed = (value - threshold) if direction == "fails_below" else (threshold - value)

    # Normalize by one typical annual step (value × log-return vol) so margins are comparable across
    # series of wildly different magnitude — the same vol sharpen.extract uses, no new statistics.
    feats = sharpen.extract([v for _, v in vals])      # [drift, vol, last, accel, ddown] or None
    if feats is not None:
        drift, vol = feats[0], feats[1]
        step = max(abs(value) * vol, 1e-9)
        margin_sigma = signed / step
        toward = drift if confirm_dir == "up" else -drift   # >0 = drifting toward confirmation
        trend_score = toward / vol                          # direction strength in vol units
        trend = "toward_confirm" if toward > vol * 0.1 else "toward_falsify" if toward < -vol * 0.1 else "flat"
    else:                                                   # too short to characterise — margin only
        margin_sigma = signed / max(abs(value), 1e-9)
        trend_score = 0.0
        trend = "n/a"

    # Fast-clock partial: a logistic of (distance-to-threshold in steps) blended with trend direction.
    # Falsified (margin_sigma well below 0) → partial → 0; comfortably safe & trending right → → 1.
    raw = 1.5 * margin_sigma + 0.8 * trend_score
    partial = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, raw))))

    # Status is TREND-AWARE, because a threshold is often a target to REACH by a future date, not just
    # a floor already breached. A metric below its FY2026 target but climbing toward it is *approaching*,
    # not falsified — only a wrong-side metric that is NOT recovering is genuinely falsified.
    if signed >= 0:                                          # on the confirming side
        status = "approaching" if (margin_sigma < APPROACH_SIGMA and trend == "toward_falsify") else "on_track"
    else:                                                    # on the wrong side of the threshold
        status = "approaching" if trend == "toward_confirm" else "falsified"
    return {**base, "value": value, "as_of": as_of, "margin_sigma": margin_sigma,
            "trend": trend, "partial": partial, "status": status}


_WORST_ORDER = {"falsified": 3, "approaching": 2, "no_data": 1, "on_track": 0}


def card_driver_health(conn: sqlite3.Connection, *, card_id: str | None = None,
                       hypothesis_id: str | None = None) -> dict:
    """Aggregate every driver of one card / hypothesis into a single live verdict.

    `signal` = mean partial across drivers with data — the card's fast-clock driver scoreboard number
    (the situational-awareness instrument, distinct from the card's own frozen issued probability)."""
    if bool(card_id) == bool(hypothesis_id):
        raise ValueError("pass exactly one of card_id / hypothesis_id.")
    col, val = ("card_id", card_id) if card_id else ("hypothesis_id", hypothesis_id)
    rows = conn.execute(f"SELECT * FROM card_drivers WHERE {col}=?", (val,)).fetchall()
    drivers = [driver_status(conn, r) for r in rows]
    scored = [x for x in drivers if x["partial"] is not None]
    counts = {"on_track": 0, "approaching": 0, "falsified": 0, "no_data": 0}
    for x in drivers:
        counts[x["status"]] += 1
    worst = max((x["status"] for x in drivers), key=lambda s: _WORST_ORDER[s], default="on_track")
    return {
        "card_id": card_id, "hypothesis_id": hypothesis_id,
        "n": len(drivers), "n_on_track": counts["on_track"], "n_approaching": counts["approaching"],
        "n_falsified": counts["falsified"], "n_no_data": counts["no_data"],
        "signal": (sum(x["partial"] for x in scored) / len(scored)) if scored else None,
        "worst_status": worst, "drivers": drivers,
    }


def all_driver_health(conn: sqlite3.Connection) -> list[dict]:
    """One health row per live (non-superseded) card and per promoted/survived hypothesis that has
    drivers linked — the cockpit read. Newest parent first."""
    out: list[dict] = []
    cards = conn.execute(
        "SELECT DISTINCT c.id, c.question, c.created_at FROM card_drivers d "
        "JOIN forecast_cards c ON c.id = d.card_id "
        "WHERE c.superseded_by IS NULL ORDER BY c.created_at DESC").fetchall()
    for c in cards:
        h = card_driver_health(conn, card_id=c["id"])
        out.append({**h, "kind": "card", "title": c["question"]})
    hyps = conn.execute(
        "SELECT DISTINCT h.id, h.title, h.created_at FROM card_drivers d "
        "JOIN hypotheses h ON h.id = d.hypothesis_id ORDER BY h.created_at DESC").fetchall()
    for hy in hyps:
        h = card_driver_health(conn, hypothesis_id=hy["id"])
        out.append({**h, "kind": "hypothesis", "title": hy["title"]})
    return out
