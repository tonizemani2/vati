"""Adapter smoke tests — the Phase-2 'each adapter has a passing smoke test' bar.

Deliberately dependency-free (no pytest — rule 5): each check is a function returning
(name, ok, detail). They run against an in-memory SQLite DB so the real cost_ledger is
never polluted, and they NEVER spend: the priced-run check asserts the gate BLOCKS, and
the LLM check asserts a clean 'no key' error with no network. The one real (keyless, $0)
ledger artifact is produced by `python -m engine.cli search`, not here.
"""

from __future__ import annotations

import sqlite3

from engine import cost, db
from engine.adapters import llm, pdf_to_text, search


def _mem_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(db.SCHEMA)
    return conn


def _check_cost_gate_free() -> tuple[str, bool, str]:
    conn = _mem_db()
    lid = cost.gate(conn, action="smoke_free", provider="test", est_cost_cents=0)
    row = conn.execute("SELECT approval_status FROM cost_ledger WHERE id=?", (lid,)).fetchone()
    ok = row is not None and row["approval_status"] == "auto"
    return ("cost_gate:free→auto", ok, f"logged id={lid[:8]} status={row['approval_status']}")


def _check_cost_gate_blocks() -> tuple[str, bool, str]:
    """Priced bulk over threshold: row written 'pending' FIRST, then blocked."""
    conn = _mem_db()
    try:
        cost.gate(conn, action="smoke_bulk_extract", provider="deepinfra", units=10_000,
                  est_cost_cents=500)
        return ("cost_gate:priced→block", False, "did NOT block a $5.00 spend")
    except cost.CostGateError as e:
        row = conn.execute("SELECT approval_status, est_cost_cents FROM cost_ledger WHERE id=?",
                           (e.ledger_id,)).fetchone()
        ok = row is not None and row["approval_status"] == "pending" and row["est_cost_cents"] == 500
        return ("cost_gate:priced→block", ok,
                f"blocked & logged pending BEFORE execute (id={e.ledger_id[:8]})")


def _check_exa_keyless() -> tuple[str, bool, str]:
    """Keyless bulk search logs a $0 'auto' row before running; tolerant of no network."""
    conn = _mem_db()
    res = search.search_multi(conn, ["binding constraint forecasting"], num_results=3)
    row = conn.execute(
        "SELECT approval_status, est_cost_cents FROM cost_ledger WHERE action='exa_keyless_search_bulk'"
    ).fetchone()
    logged = row is not None and row["approval_status"] == "auto" and row["est_cost_cents"] == 0
    hits = sum(len(v) for v in res.values())
    return ("exa:keyless+gate", logged,
            f"$0 'auto' row logged before call; {hits} live hit(s) (0 ok if offline)")


def _check_pdftotext() -> tuple[str, bool, str]:
    conn = _mem_db()  # unused, keeps signature uniform
    if not pdf_to_text.available():
        return ("pdf_to_text", False, "pdftotext not on PATH")
    try:
        pdf_to_text.pdf_to_text("/no/such/file.pdf")
        return ("pdf_to_text", False, "missing file did not raise")
    except FileNotFoundError:
        return ("pdf_to_text", True, "binary present; missing-file raises cleanly")


def _check_llm_no_key() -> tuple[str, bool, str]:
    """No key ⇒ clean LLMConfigError, no network, no foreign-.env read (guardrail 1)."""
    conn = _mem_db()
    try:
        llm.complete(conn, "hi", provider="deepinfra", est_cost_cents=1)
        return ("llm:no-key→error", False, "did not raise without a key")
    except llm.LLMConfigError:
        n = conn.execute("SELECT COUNT(*) FROM cost_ledger").fetchone()[0]
        return ("llm:no-key→error", n == 0, "clean error, nothing spent/logged")


CHECKS = [
    _check_cost_gate_free,
    _check_cost_gate_blocks,
    _check_exa_keyless,
    _check_pdftotext,
    _check_llm_no_key,
]


def run_smoke() -> list[tuple[str, bool, str]]:
    return [c() for c in CHECKS]
