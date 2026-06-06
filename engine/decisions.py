"""Component 14 — the decision / steering log. The human-in-the-loop seam.

The constitution's rule 4 (*ask, don't assume*) says a pivotal fork becomes a concise Decision —
prompt + options + a recommendation — never a wall of text, never a silent assumption. The schema
(`schemas.Decision`) and the cockpit's "Decisions awaiting you" panel already exist; specific flows
(the supply-graph verify gate, the consensus mispricing fork) open decisions inline. This module is
the GENERAL write-flow: open any steering decision, list the open ones, resolve one with the human's
choice. That closes the loop — a fork is logged, surfaced in the cockpit, and answered, with the
answer stamped and dated. Steer-ability over autonomy, made first-class. $0, stdlib.
"""

from __future__ import annotations

import json
import sqlite3

from engine.schemas import Decision, _now


def open_decision(conn: sqlite3.Connection, *, prompt: str, options: list[str],
                  recommendation: str | None = None, blocks: str | None = None,
                  context_source_ids: list[str] | None = None, log=print) -> Decision:
    """Log a pivotal fork (rule 4). Idempotent on the prompt — re-opening the same fork is a no-op
    (returns the existing row) so a re-run never spawns duplicate decisions."""
    existing = conn.execute(
        "SELECT id, status, chosen_option FROM decisions WHERE prompt=?", (prompt,)).fetchone()
    if existing:
        log(f"  decision already logged [{existing['id'][:8]}] (status={existing['status']})")
        return Decision(id=existing["id"], prompt=prompt, options=options, recommendation=recommendation)
    d = Decision(prompt=prompt, options=options, recommendation=recommendation, blocks=blocks,
                 context_source_ids=context_source_ids or [])
    conn.execute(
        "INSERT INTO decisions (id,created_at,prompt,options,recommendation,context_source_ids,"
        "status,chosen_option,decided_at,blocks) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (d.id, d.created_at.isoformat(), d.prompt, json.dumps(d.options), d.recommendation,
         json.dumps(d.context_source_ids), d.status.value, None, None, d.blocks),
    )
    conn.commit()
    log(f"  opened decision [{d.id[:8]}] — {prompt[:70]}")
    return d


def resolve_decision(conn: sqlite3.Connection, decision_id: str, chosen: str, *, log=print) -> dict:
    """Stamp the human's choice onto an open decision (closes the fork). 8-char id ok."""
    row = conn.execute(
        "SELECT id, prompt, options, status FROM decisions WHERE id=? OR id LIKE ?",
        (decision_id, decision_id + "%")).fetchone()
    if row is None:
        raise ValueError(f"no decision matching {decision_id}")
    if row["status"] != "open":
        raise ValueError(f"decision {row['id'][:8]} is already '{row['status']}' — decisions resolve once")
    opts = json.loads(row["options"] or "[]")
    # Accept the chosen option verbatim, by 1-based index, or as a free-text answer (the human may
    # pick "Other"). We never silently coerce — an unrecognised non-numeric choice is kept as-is.
    if chosen.isdigit() and opts and 1 <= int(chosen) <= len(opts):
        chosen = opts[int(chosen) - 1]
    conn.execute("UPDATE decisions SET status='decided', chosen_option=?, decided_at=? WHERE id=?",
                 (chosen, _now().isoformat(), row["id"]))
    conn.commit()
    log(f"  resolved [{row['id'][:8]}] → {chosen}")
    return {"id": row["id"], "chosen": chosen}


def list_decisions(conn: sqlite3.Connection, *, only_open: bool = False, log=print) -> list[sqlite3.Row]:
    """Text view of the steering log (the cockpit #decisions panel is the real view)."""
    q = ("SELECT id, prompt, options, recommendation, status, chosen_option, blocks FROM decisions "
         + ("WHERE status='open' " if only_open else "") + "ORDER BY created_at DESC")
    rows = conn.execute(q).fetchall()
    if not rows:
        log("  no decisions logged" + (" that are open" if only_open else ""))
    for r in rows:
        mark = "● OPEN " if r["status"] == "open" else "✓ " + (r["chosen_option"] or r["status"])[:24]
        log(f"  [{r['id'][:8]}] {mark:<26} {r['prompt'][:64]}")
        if r["status"] == "open" and r["recommendation"]:
            log(f"             rec: {r['recommendation'][:70]}")
    return rows
