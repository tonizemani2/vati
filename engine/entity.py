"""Component 2 — entity resolution. The spine that connects the nine pillars.

Every pillar names the same real-world things under different surface forms. OpenAlex's
"Deep learning" concept, Epoch's per-domain compute curves, the "neural network" patent phrase
and the §8 AI retrodiction case are ONE technology. 10x Genomics is a consumable supplier in the
supply graph AND "TXG" to the market. Until those are linked, each pillar is an island and the
constraint can never be *traced* — frontier signal → dependency graph → supply elasticity →
market pricing → bet. That trace is the whole thesis; entity resolution is what makes it possible
(an independent 4-LLM read called this "the most neglected, most important layer").

This is deliberately NOT a fuzzy-matching engine (that would be the orca-platform anti-pattern,
§9). Resolution here is Claude-in-session judgment over a small, high-value set: we state WHY each
row is a given entity and how confident we are (GIGO, rule 1). It is as much about NOT merging
distinct things — NLP and computer vision are *application fields* of deep learning, not the same
concept — as about merging the same thing; the entity `note` records what was kept separate.

Additive: it links existing rows, never rewrites them. Two tables in the one DB (rule 5). $0 — no
network, no LLM; a $0 'auto' ledger row is still logged so the cost gate is exercised, not bypassed.
"""

from __future__ import annotations

import json
import sqlite3

from engine import db
from engine.pillars.frontier import _log_cost
from engine.schemas import Entity, EntityLink, _now


# ── upserts (validated through the Pydantic models — the GIGO gate) ───────────


def _upsert_entity(conn: sqlite3.Connection, e: Entity) -> str:
    row = conn.execute(
        "SELECT id FROM entities WHERE kind=? AND canonical_name=?", (e.kind, e.canonical_name)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE entities SET domain=?, aliases=?, note=? WHERE id=?",
            (e.domain, json.dumps(e.aliases), e.note, row["id"]),
        )
        return row["id"]
    conn.execute(
        "INSERT INTO entities (id,kind,canonical_name,domain,aliases,note,created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (e.id, e.kind, e.canonical_name, e.domain, json.dumps(e.aliases), e.note,
         e.created_at.isoformat()),
    )
    return e.id


def _upsert_link(conn: sqlite3.Connection, link: EntityLink) -> None:
    conn.execute(
        "INSERT INTO entity_links (id,entity_id,ref_table,ref_id,ref_label,pillar_id,"
        "confidence,method,rationale,created_at) VALUES (?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(entity_id,ref_table,ref_id) DO UPDATE SET ref_label=excluded.ref_label, "
        "pillar_id=excluded.pillar_id, confidence=excluded.confidence, "
        "method=excluded.method, rationale=excluded.rationale",
        (link.id, link.entity_id, link.ref_table, link.ref_id, link.ref_label, link.pillar_id,
         link.confidence, link.method, link.rationale, link.created_at.isoformat()),
    )


# ── resolvers: turn a natural key into the real row (id + pillar) ─────────────


def _series(conn: sqlite3.Connection, label: str) -> sqlite3.Row | None:
    return conn.execute("SELECT id, pillar_id, label FROM series WHERE label=?", (label,)).fetchone()


def _node(conn: sqlite3.Connection, chain: str, name: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, name FROM graph_nodes WHERE chain=? AND name=?", (chain, name)
    ).fetchone()


# ── the curated clusters (in-session resolution; every link a stated reason) ──
# A cluster = an Entity + its links. A link is (kind, key, confidence, rationale):
#   ("series", "<label>", ...)            → resolved to the series row (pillar from the row)
#   ("graph_nodes", ("scrna_seq","<name>")) → resolved to the graph node (pillar 3)
#   ("ticker", "TXG", ...)                → a market symbol (pillar 7), no row to join

CLUSTERS = [
    {
        "entity": Entity(
            kind="technology", canonical_name="Single-cell RNA sequencing",
            domain="single-cell genomics", aliases=["scRNA-seq", "single cell rna sequencing"],
            note=("The single-cell transcriptomics platform. Its frontier funding signal (pillar 1) "
                  "and its entire value chain (the scrna_seq supply graph, pillars 3–4) resolve to "
                  "this one node — so the constraint can be traced from signal to bottleneck. Kept "
                  "DISTINCT from the broader DNA-sequencing cost curve (linked as the enabling parent "
                  "at lower confidence) and from its supplier firms 10x Genomics / Illumina (own entities)."),
        ),
        "links": [
            ("series", "single cell rna sequencing (NIH grants)", 1.0,
             "NIH RePORTER grant-count series for this exact technology — the frontier funding-velocity "
             "signal the detector fired on (30σ). Same concept, authoritative source."),
            ("series", "DNA sequencing (next-gen sequencing cost collapse) — capability", 0.6,
             "The NGS cost-collapse curve scRNA-seq rides on — the ENABLING PARENT technology, not "
             "identical. Linked at low confidence to record the dependency, not to merge them."),
            ("graph_nodes", ("scrna_seq", "single-cell RNA-seq assay (demand origin)"), 1.0,
             "The assay node where a demand shock enters this technology's value chain (pillar 3-4)."),
            ("graph_nodes", ("scrna_seq", "droplet partitioning consumable (microfluidic chip + barcoded gel beads)"), 1.0,
             "The computed bottleneck node — the inelastic consumable where rent concentrates (pillar 3-4)."),
            ("graph_nodes", ("scrna_seq", "short-read sequencer capacity"), 1.0,
             "The elastic endpoint node — capability is there but rent does not land (pillar 3-4)."),
            ("graph_nodes", ("scrna_seq", "instrument-free combinatorial barcoding (Parse / SPLiT-seq)"), 1.0,
             "Substitute node — the rising substitutability that is the bet's first kill-criterion (pillar 3-4)."),
        ],
    },
    {
        "entity": Entity(
            kind="company", canonical_name="10x Genomics", domain="single-cell genomics",
            aliases=["TXG"],
            note=("Maker of the droplet partitioning consumable — the INELASTIC, rent-capturing layer "
                  "of the scRNA-seq chain. 'TXG' on NASDAQ. This entity bridges the supply graph "
                  "(pillars 3–4) to market pricing (pillar 7): the same firm, two surface forms."),
        ),
        "links": [
            ("ticker", "TXG", 1.0,
             "NASDAQ:TXG = 10x Genomics — the consumable layer the consensus gate prices long (consumable_sym)."),
            ("graph_nodes", ("scrna_seq", "droplet partitioning consumable (microfluidic chip + barcoded gel beads)"), 0.95,
             "10x manufactures this droplet partitioning consumable; its IP moat is why this node is inelastic."),
        ],
    },
    {
        "entity": Entity(
            kind="company", canonical_name="Illumina", domain="sequencing", aliases=["ILMN"],
            note=("Dominant short-read sequencer maker — the ELASTIC layer (≥4 vendors, falling $/base; "
                  "durable rent does not land here). 'ILMN' on NASDAQ. Bridges the supply graph to pricing."),
        ),
        "links": [
            ("ticker", "ILMN", 1.0,
             "NASDAQ:ILMN = Illumina — the elastic sequencer layer the consensus gate prices short (sequencer_sym)."),
            ("graph_nodes", ("scrna_seq", "short-read sequencer capacity"), 0.95,
             "Illumina dominates short-read sequencer capacity — the elastic node of the chain."),
        ],
    },
    {
        "entity": Entity(
            kind="technology", canonical_name="Deep learning", domain="AI",
            aliases=["neural network", "DNN", "deep neural network"],
            note=("ONE technology resolved across five providers — OpenAlex concept, Epoch compute "
                  "curves, the patent phrase, and the §8 retrodiction case. Its CAPABILITY signal "
                  "(Epoch compute) is the one Phase 6 missed; its ATTENTION signals (works, patents) "
                  "are abundant — resolving them onto one node makes the decoy problem legible. "
                  "Deliberately NOT merged with NLP / computer vision / RNN (application fields & "
                  "sub-techniques — distinct concepts, the over-merge error entity resolution must avoid)."),
        ),
        "links": [
            ("series", "Deep learning", 1.0,
             "OpenAlex 'Deep learning' concept — the canonical works/year id for this technology."),
            ("series", "Frontier training compute (Language)", 0.95,
             "Epoch frontier-compute curve for deep-learning language models — a capability curve for this entity."),
            ("series", "Frontier training compute (Vision)", 0.95,
             "Epoch frontier-compute curve for deep-learning vision models — a capability curve for this entity."),
            ("series", "Frontier training compute (Speech)", 0.95,
             "Epoch frontier-compute curve for deep-learning speech models — a capability curve for this entity."),
            ("series", "Frontier training compute (Games)", 0.95,
             "Epoch frontier-compute curve for deep-learning game-playing models — a capability curve for this entity."),
            ("series", "neural network (patents)", 0.9,
             "Google Patents 'neural network' phrase — a near-synonym patent filing-velocity signal for deep learning."),
            ("series", "AI accelerators / NVIDIA (compute-bound deep learning) — capability", 1.0,
             "The §8 retrodiction case IS deep-learning compute — the recall miss, now traceable to this entity."),
        ],
    },
    # ── cross-source technology clusters (2026-06-03): each tech now spans 3–5 pillars after the
    # demand/capital/policy/patents wave — linking them activates cross-source reconciliation + the
    # spine. Every entity is ONE distinct technology (no over-merge; sub-techs linked at lower conf).
    {
        "entity": Entity(
            kind="technology", canonical_name="CRISPR gene editing", domain="bio",
            aliases=["crispr", "gene editing", "cas9"],
            note="Genome-editing tool traced across funding (P1), patents (P1), public attention (P5), "
                 "capital (P6). DISTINCT from gene therapy (a delivery modality, its own entity).",
        ),
        "links": [
            ("series", "crispr (NIH grants)", 1.0, "NIH grant velocity for CRISPR (P1 funding)."),
            ("series", "crispr (patents)", 0.9, "Patent filing velocity (P1)."),
            ("series", "crispr (pageviews)", 0.85, "Wikipedia public-attention (P5 demand)."),
            ("series", "crispr (SEC filings)", 0.85, "SEC filing-mention velocity (P6 capital)."),
        ],
    },
    {
        "entity": Entity(
            kind="technology", canonical_name="Quantum computing", domain="compute",
            aliases=["quantum information science", "quantum"],
            note="Spans research (P1), patents (P1), attention (P5), capital (P6), policy (P8). Quantum "
                 "error correction / quantum dot kept SEPARATE (sub-fields, the over-merge guard).",
        ),
        "links": [
            ("series", "Quantum information science", 0.95, "OpenAlex research velocity — the broad QC concept."),
            ("series", "quantum computing (patents)", 0.9, "Patent velocity (P1)."),
            ("series", "quantum computing (pageviews)", 0.85, "Public attention (P5)."),
            ("series", "quantum computing (SEC filings)", 0.85, "Capital attention (P6)."),
            ("series", "quantum (Fed. Register)", 0.65, "Policy attention (P8) — broad 'quantum' term, lower conf."),
        ],
    },
    {
        "entity": Entity(
            kind="technology", canonical_name="Solar photovoltaics", domain="energy",
            aliases=["solar pv", "photovoltaic"],
            note="The PV capability + adoption + policy spine (P2/P5/P8/P9). Perovskite linked as a "
                 "next-gen PV SUB-technology (lower conf), not a merged identity.",
        ),
        "links": [
            ("series", "solar pv affordability", 1.0, "OWID module $/W affordability — the Wright's-law capability curve (P2)."),
            ("series", "solar lcoe affordability", 0.95, "OWID utility-solar LCOE affordability (P2)."),
            ("series", "Solar PV (Swanson's-law $/W collapse) — capability", 1.0, "The §8 solar winner case (P9)."),
            ("series", "perovskite solar cell (patents)", 0.8, "Next-gen PV sub-tech patent velocity (P1)."),
            ("series", "perovskite solar cell (pageviews)", 0.75, "Next-gen PV sub-tech attention (P5)."),
            ("series", "solar energy (Fed. Register)", 0.8, "Solar policy attention (P8)."),
        ],
    },
    {
        "entity": Entity(
            kind="technology", canonical_name="Lithium-ion battery", domain="energy",
            aliases=["li-ion", "lithium ion battery"],
            note="Battery capability + patents + attention + capital + policy + the §8 winner (P1/P5/P6/P8/P9).",
        ),
        "links": [
            ("series", "Lithium-ion battery", 0.95, "OpenAlex research velocity."),
            ("series", "lithium ion battery (patents)", 0.9, "Patent velocity (P1)."),
            ("series", "lithium-ion battery (pageviews)", 0.85, "Public attention (P5)."),
            ("series", "lithium ion battery (SEC filings)", 0.85, "Capital attention (P6)."),
            ("series", "Lithium-ion batteries / EVs ($/kWh collapse) — capability", 1.0, "The §8 battery winner case (P9)."),
        ],
    },
    {
        "entity": Entity(
            kind="technology", canonical_name="Gene therapy", domain="bio",
            aliases=["gene therapy"],
            note="A delivery/modality, DISTINCT from CRISPR (editing tool). Spans P1/P5/P6/P8.",
        ),
        "links": [
            ("series", "gene therapy (NIH grants)", 1.0, "NIH grant velocity (P1)."),
            ("series", "gene therapy (patents)", 0.9, "Patent velocity (P1)."),
            ("series", "gene therapy (pageviews)", 0.85, "Public attention (P5)."),
            ("series", "gene therapy (SEC filings)", 0.85, "Capital attention (P6)."),
            ("series", "gene therapy (Fed. Register)", 0.7, "Policy attention (P8)."),
        ],
    },
    {
        "entity": Entity(
            kind="technology", canonical_name="Autonomous driving", domain="AI",
            aliases=["self-driving car", "autonomous vehicle"],
            note="One technology under three surface forms across patents (P1), attention (P5), capital (P6).",
        ),
        "links": [
            ("series", "autonomous driving (patents)", 0.9, "Patent velocity (P1)."),
            ("series", "self-driving car (pageviews)", 0.9, "Public attention (P5)."),
            ("series", "autonomous vehicle (SEC filings)", 0.9, "Capital attention (P6)."),
        ],
    },
    {
        "entity": Entity(
            kind="technology", canonical_name="Blockchain", domain="compute",
            aliases=["blockchain", "distributed ledger"],
            note="Research + attention + capital (P1/P5/P6). A fizzle-prone darling — the entity makes "
                 "its attention-heavy / capability-light profile legible across sources.",
        ),
        "links": [
            ("series", "Blockchain", 0.95, "OpenAlex research velocity."),
            ("series", "blockchain (pageviews)", 0.85, "Public attention (P5)."),
            ("series", "blockchain (SEC filings)", 0.85, "Capital attention (P6)."),
        ],
    },
]


def seed(conn: sqlite3.Connection, *, log=print) -> dict:
    """Resolve the curated clusters into entities + links. Idempotent. $0.

    Missing refs are LOGGED, never silently skipped (a silent cap reads as full coverage).
    """
    _log_cost(conn, "entity_resolve", "in_session", float(len(CLUSTERS)))
    n_entities = n_links = n_missing = 0
    for c in CLUSTERS:
        e: Entity = c["entity"]
        eid = _upsert_entity(conn, e)
        n_entities += 1
        log(f"  ◆ {e.canonical_name} [{e.kind}]")
        for ref_table, key, conf, rationale in c["links"]:
            if ref_table == "series":
                row = _series(conn, key)
                if not row:
                    log(f"    ! missing series: {key!r} — link skipped (logged, not faked)")
                    n_missing += 1
                    continue
                ref_id, ref_label, pillar = row["id"], row["label"], row["pillar_id"]
            elif ref_table == "graph_nodes":
                chain, name = key
                row = _node(conn, chain, name)
                if not row:
                    log(f"    ! missing graph node: {name!r} — link skipped (logged, not faked)")
                    n_missing += 1
                    continue
                ref_id, ref_label, pillar = row["id"], row["name"], 3
            elif ref_table == "ticker":
                ref_id, ref_label, pillar = key, key, 7
            else:
                log(f"    ! unknown ref_table {ref_table!r} — skipped")
                n_missing += 1
                continue
            _upsert_link(conn, EntityLink(
                entity_id=eid, ref_table=ref_table, ref_id=ref_id, ref_label=ref_label,
                pillar_id=pillar, confidence=conf, rationale=rationale,
            ))
            n_links += 1
            log(f"    ↳ P{pillar} {ref_table:<11} {ref_label[:44]:<44} (conf {conf:.2f})")
    conn.commit()
    log(f"\n  resolved {n_entities} entities · {n_links} links · {n_missing} refs missing (logged)")
    return {"entities": n_entities, "links": n_links, "missing": n_missing}


def list_entities(conn: sqlite3.Connection, *, log=print) -> None:
    """Text view of resolved entities + the pillars each one spans (the cockpit is the real view)."""
    ents = conn.execute("SELECT * FROM entities ORDER BY kind, canonical_name").fetchall()
    if not ents:
        log("no entities resolved yet — run: python -m engine.cli entity-seed")
        return
    for e in ents:
        links = conn.execute(
            "SELECT ref_table, ref_label, pillar_id, confidence FROM entity_links "
            "WHERE entity_id=? ORDER BY pillar_id", (e["id"],)
        ).fetchall()
        pillars = sorted({l["pillar_id"] for l in links if l["pillar_id"] is not None})
        log(f"\n◆ {e['canonical_name']} [{e['kind']}] — spans pillars {pillars} ({len(links)} links)")
        for l in links:
            log(f"   P{l['pillar_id']} {l['ref_table']:<11} {l['ref_label'][:48]:<48} conf {l['confidence']:.2f}")
