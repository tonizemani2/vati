"""Orchestrator — discover -> qualify -> synth top-N -> write artifacts (dry-run, nothing sends).

Writes data/capture/<slug>/: targets.json (scored), plays.json (full), review.md (the human/Opus
rating surface). Re-run synth on one target with a revision note via resynth().
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from engine.capture import engine as ce
from engine.capture.schema import (
    Play, PlayBrief, Target, play_dir, read_json, write_json,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# --- preset briefs (reusable; the first one is v1's data-barter play) ------------------

BRIEFS: dict[str, PlayBrief] = {
    "minerals-barter": PlayBrief(
        slug="minerals-barter",
        objective=("Barter a dated slice of our critical-minerals constraint forecast for "
                   "proprietary supply/production data held by niche players at the bottleneck."),
        rung=1,
        target_criteria=("People or small orgs who hold non-public critical-minerals supply data: "
                         "specialist supply-chain analysts, trade-data firms, refining/processing "
                         "operators, industry-association data leads, niche consultancies. NOT the "
                         "household-name majors or pure news outlets."),
        discovery_queries=[
            "critical minerals supply chain intelligence analyst proprietary data",
            "rare earth production data analytics consultancy",
            "battery raw materials supply database provider",
            "lithium cobalt nickel supply chain data firm",
            "critical minerals refining capacity dataset analyst",
            "graphite gallium germanium supply concentration data",
        ],
        linked_forecast=("Our live, dated, Brier-scored board call on where the next critical-minerals "
                         "constraint binds (the move from raw extraction to refining/processing "
                         "chokepoints), with a probability + interval + kill-criterion fixed at publish."),
        value_hook=("The full dated forecast read + our concept-dependency view of which downstream "
                    "sectors reprice first. Free, before any ask. We are after a data trade, not a sale."),
    ),
}


def run_play(slug: str, *, top_n: int = 5, conn: sqlite3.Connection | None = None) -> dict:
    """Full dry-run pass. Returns a summary dict; writes artifacts to data/capture/<slug>/."""
    brief = BRIEFS.get(slug)
    if brief is None:
        raise ValueError(f"unknown brief {slug!r}; have {list(BRIEFS)}")
    own = conn is None
    if own:
        from engine import db
        conn = db.connect()
    try:
        targets = ce.discover(conn, brief)
        targets = ce.qualify(conn, brief, targets)
        top = targets[:top_n]
        plays = [ce.synth_play(conn, brief, t) for t in top]
    finally:
        if own:
            conn.close()

    d = play_dir(slug, REPO_ROOT)
    write_json(d / "brief.json", brief.to_dict())
    write_json(d / "targets.json", [t.to_dict() for t in targets])
    write_json(d / "plays.json", [p.to_dict() for p in plays])
    (d / "review.md").write_text(render_review(brief, plays))
    return {"slug": slug, "discovered": len(targets), "plays": len(plays), "dir": str(d)}


def resynth(slug: str, target_index: int, revision_note: str,
            conn: sqlite3.Connection | None = None) -> Play:
    """Re-draft ONE play with the rater's feedback folded in. Overwrites that play in plays.json."""
    d = play_dir(slug, REPO_ROOT)
    brief = BRIEFS[slug]
    plays = [Play.from_dict(p) for p in read_json(d / "plays.json")]
    own = conn is None
    if own:
        from engine import db
        conn = db.connect()
    try:
        new = ce.synth_play(conn, brief, plays[target_index].target, revision_note=revision_note)
    finally:
        if own:
            conn.close()
    plays[target_index] = new
    write_json(d / "plays.json", [p.to_dict() for p in plays])
    (d / "review.md").write_text(render_review(brief, plays))
    return new


# --- the rating surface ---------------------------------------------------------------

def _tree_md(nodes, depth: int = 0) -> str:
    pad = "  " * depth
    out = []
    for n in nodes:
        out.append(f"{pad}- **They:** {n.reply_type}\n{pad}  **Us:** {n.our_move}")
        if n.children:
            out.append(_tree_md(n.children, depth + 1))
    return "\n".join(out)


def render_review(brief: PlayBrief, plays: list[Play]) -> str:
    """Markdown the in-session model (or a human) reads to rate each play."""
    head = [f"# Capture review: {brief.slug}", "",
            f"**Objective:** {brief.objective}", f"**Rung:** {brief.rung}",
            f"**Hook anchor:** {brief.linked_forecast}", "", "---", ""]
    for i, p in enumerate(plays):
        t = p.target
        head += [
            f"## Play {i}: {t.name} — {t.org}",
            f"*{t.role}* | fit {t.fit} leverage {t.leverage} warm {t.warm_path} "
            f"reach {t.reach_ease} | score {t.score} | {t.reachability}",
            f"why: {t.why_them}", f"has: {t.what_they_have}", "",
            f"**Hook:** {p.hook}", "",
            f"**Opener ({p.channel}):**", "", p.opener, "",
            "**Tree:**", _tree_md(p.tree), "",
            "---", "",
        ]
    return "\n".join(head)
