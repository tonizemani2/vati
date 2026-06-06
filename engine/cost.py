"""The cost gate (CONSTITUTION rule 3) — component 15 enforcement.

Every paid action is logged to `cost_ledger` *before* it runs, and anything over the
auto-approve threshold is **blocked** until a human approves it. Free/keyless work logs
at cost 0 with `approval_status='auto'` and proceeds. This module turns the cost_ledger
table (schema-only since Phase 0) into an enforced gate.

It also holds the repo-root-only `.env` loader: provider keys are read from THIS repo's
`.env` and nowhere else — the loader is hard-wired to `REPO_ROOT/.env` and never walks
parent directories, so it structurally cannot read another repo's secrets (rule 6).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from engine.schemas import ApprovalStatus, CostLedgerEntry

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"  # hard-wired: never a parent, never another repo (rule 6)

_env_loaded = False


class CostGateError(RuntimeError):
    """Raised when a spend exceeds the auto-approve threshold and is not yet approved.

    The ledger row is written (status 'pending') *before* this is raised, so the blocked
    spend is always on record — the gate fires before execution, never after.
    """

    def __init__(self, ledger_id: str, est_cost_cents: int, threshold_cents: int):
        self.ledger_id = ledger_id
        self.est_cost_cents = est_cost_cents
        self.threshold_cents = threshold_cents
        super().__init__(
            f"cost gate: ${est_cost_cents / 100:.2f} exceeds auto-approve "
            f"${threshold_cents / 100:.2f} — blocked, pending approval "
            f"(ledger {ledger_id}). Approve with: "
            f"python -m engine.cli approve-cost {ledger_id} --by <name>"
        )


def load_repo_env() -> None:
    """Load `REPO_ROOT/.env` into os.environ once (no python-dotenv dep, no parent walk).

    Existing env vars win — the shell can always override the file. Lines are `KEY=VALUE`;
    blanks and `#` comments are skipped. Only this repo's `.env` is ever opened.
    """
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    if not ENV_PATH.is_file():
        return
    for raw in ENV_PATH.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def auto_approve_cents() -> int:
    """The spend (in cents) that may run without human approval. Strict 0 by default."""
    load_repo_env()
    try:
        return int(os.getenv("COST_AUTO_APPROVE_CENTS", "0"))
    except ValueError:
        return 0


def gate(
    conn: sqlite3.Connection,
    *,
    action: str,
    provider: str,
    units: float = 0.0,
    est_cost_cents: int = 0,
    funded_ref: str | None = None,
) -> str:
    """Log an action to the cost ledger BEFORE it runs; enforce the approval threshold.

    Returns the ledger id (record actual spend later via `record_actual`). Decision:
      - est == 0            → 'auto'      (free/keyless; just runs)
      - 0 < est <= threshold → 'approved' (within budget; approved_by='auto-budget')
      - est > threshold     → write 'pending', then raise CostGateError (BLOCK)

    The row is always inserted first, so even a blocked spend is on record.
    """
    threshold = auto_approve_cents()
    if est_cost_cents <= 0:
        status, approved_by = ApprovalStatus.auto, None
    elif est_cost_cents <= threshold:
        status, approved_by = ApprovalStatus.approved, "auto-budget"
    else:
        status, approved_by = ApprovalStatus.pending, None

    entry = CostLedgerEntry(
        action=action,
        provider=provider,
        units=units,
        est_cost_cents=est_cost_cents,
        approval_status=status,
        approved_by=approved_by,
        funded_ref=funded_ref,
    )
    conn.execute(
        "INSERT INTO cost_ledger "
        "(id, ts, action, provider, units, est_cost_cents, actual_cost_cents, "
        " approval_status, approved_by, funded_ref) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            entry.id, entry.ts.isoformat(), entry.action, entry.provider, entry.units,
            entry.est_cost_cents, None, entry.approval_status.value,
            entry.approved_by, entry.funded_ref,
        ),
    )
    conn.commit()

    if status is ApprovalStatus.pending:
        raise CostGateError(entry.id, est_cost_cents, threshold)
    return entry.id


def record_actual(conn: sqlite3.Connection, ledger_id: str, actual_cost_cents: int) -> None:
    """After a run, write the actual spend onto its ledger row."""
    conn.execute(
        "UPDATE cost_ledger SET actual_cost_cents=? WHERE id=?",
        (actual_cost_cents, ledger_id),
    )
    conn.commit()


def approve(conn: sqlite3.Connection, ledger_id: str, approved_by: str) -> bool:
    """Human approval for a pending spend. Returns False if the id isn't pending."""
    cur = conn.execute(
        "UPDATE cost_ledger SET approval_status=?, approved_by=? "
        "WHERE id=? AND approval_status=?",
        (ApprovalStatus.approved.value, approved_by, ledger_id, ApprovalStatus.pending.value),
    )
    conn.commit()
    return cur.rowcount > 0
