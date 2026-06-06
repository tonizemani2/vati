"""The 9 pillars — data-flow layers in causal order.

Value concentrates in layers 3-4 (where scarcity rent migrates); layer 7 is the gate
(correct + already priced = zero edge). Layering rule: exhaust one before the next.
"""

from __future__ import annotations

import sqlite3

# (ord, name, description)
PILLARS: list[tuple[int, str, str]] = [
    (1, "Frontier",
     "What is becoming newly possible: science, papers, patents, grants, talent moves. Earliest signal (~5-10yr lead)."),
    (2, "Capability curves",
     "Is it accelerating? Performance/$, perf/watt, cost/unit, yield, efficacy. Track the SECOND derivative, not the level."),
    (3, "Dependency graph",
     "If this 10x's, what breaks first? Bills-of-materials, suppliers, materials, equipment, energy. The core."),
    (4, "Supply elasticity",
     "Where does scarcity rent land? Capacity, utilization, lead times, backlog, concentration, switching costs. The money."),
    (5, "Demand / adoption",
     "Is it really diffusing? Procurement, API usage, job posts, repos, RFPs, approvals (~2-4yr lead)."),
    (6, "Capital flows",
     "Where is money already going? VC rounds, public capex, subsidies, M&A, insider activity, bond issuance."),
    (7, "Market pricing",
     "Is it STILL mispriced? Valuations, margins, consensus estimates, short interest. The gate: priced-in = no edge."),
    (8, "Policy / geo",
     "What bends supply by decree? Sanctions, export controls, permits, tax credits, procurement, standards."),
    (9, "Outcomes",
     "What actually happened — winners AND fizzles. The calibration labels. This is the compounding moat."),
]


def seed_pillars(conn: sqlite3.Connection) -> int:
    """Insert the 9 pillars if missing. Idempotent; never overwrites a pillar's status."""
    before = conn.execute("SELECT COUNT(*) FROM pillars").fetchone()[0]
    conn.executemany(
        "INSERT OR IGNORE INTO pillars (id, ord, name, description, status) "
        "VALUES (?, ?, ?, ?, 'untapped')",
        [(ord_, ord_, name, desc) for (ord_, name, desc) in PILLARS],
    )
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM pillars").fetchone()[0]
    return after - before
