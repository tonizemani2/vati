"""Components 5 + 6 — the supply graph and the constraint-propagation engine.

This is the heart of Phase 4: it turns the scRNA-seq forward forecast's *asserted* bottleneck
("rent migrates to the single-cell partitioning consumable, not the sequencer") into a *derived*
one. We build one small, sparse, high-precision supply graph for the single-cell RNA-seq value
chain, then flow a 10x demand shock through it and let the first-saturating, least-substitutable
node fall out. The constraint is **computed under flow**, never stored as a label (execution §0.5).

Two hard guardrails, both from the constitution:
  • GIGO (rule 1): every critical edge carries a Source with a stated trust rationale. The chain
    is reasoned by Claude in-session and grounded in cited, checkable sources — not hallucinated.
  • Ask-don't-assume (rule 4 / §9): the suspected-bottleneck assumption is HUMAN-VERIFIED before
    propagation. `propose_verification` writes the Decision; the human confirms before we flow.

Pure-ish: the only I/O is SQLite. No network, no LLM. Reasoning is Claude's, in-session ($0).
"""

from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass
from datetime import date

from engine.schemas import (
    Decision,
    GraphEdge,
    GraphNode,
    Source,
    SourceKind,
    _now,
)

CHAIN = "scrna_seq"
DEP_PILLAR = 3      # Dependency graph — the chain structure
SUP_PILLAR = 4      # Supply elasticity — where the rent lands
SHOCK = 10.0        # the 10x demand shock on single-cell assays the forward card is about
MC_N = 200_000


# --- the sourced value chain (GIGO-gated) ------------------------------------
# Each Source is a real, checkable origin with a STATED reason to trust it (rule 1). Trust is the
# claim's verifiability, not search rank: courts/patents/NHGRI rank high; trade press is mid;
# a vendor's own press release is low (used only where it's the primary record of its own product).

SOURCES: list[dict] = [
    {"key": "tenx_patent", "pillar": DEP_PILLAR, "kind": SourceKind.primary, "trust": 82,
     "title": "US Patent 10,428,326 — droplet-based single-cell barcoding (10x Genomics)",
     "url": "https://patents.justia.com/patent/10428326",
     "rationale": "Primary legal instrument: the granted patent on gel-bead/droplet partitioning. "
                  "Authoritative origin for the claim that the partitioning consumable is IP-protected."},
    {"key": "cafc_biorad", "pillar": DEP_PILLAR, "kind": SourceKind.filing, "trust": 80,
     "title": "CAFC affirms ITC ruling: Bio-Rad infringed 10x Genomics droplet patents (2021)",
     "url": "https://ipwatchdog.com/2021/05/03/cafc-affirms-itc-ruling-10x-genomics-finding-bio-rad-infringed/id=133059/",
     "rationale": "Federal Circuit appellate ruling — a high-authority record that 10x's partitioning "
                  "IP has been enforced against a major rival, evidence the consumable layer is defended."},
    {"key": "nhgri_cost", "pillar": SUP_PILLAR, "kind": SourceKind.primary, "trust": 90,
     "title": "NHGRI DNA Sequencing Cost curve (cost per Mb / per genome)",
     "url": "https://www.genome.gov/about-genomics/fact-sheets/Sequencing-Human-Genome-Cost",
     "rationale": "US government primary dataset, transparent methodology — the canonical evidence that "
                  "short-read sequencing cost has collapsed and keeps falling (the sequencer is elastic)."},
    {"key": "ngs_competition", "pillar": SUP_PILLAR, "kind": SourceKind.news, "trust": 60,
     "title": "Four new short-read NGS platforms (MGI, Element AVITI, Ultima, Singular) launched 2023-24",
     "url": "https://www.genomeweb.com/sequencing/next-gen-sequencing-firms-expand-offerings-multiomics-capabilities-2024",
     "rationale": "Specialist trade press (GenomeWeb) corroborated across outlets — multiple independent "
                  "short-read vendors now compete, so sequencing capacity is substitutable and elastic."},
    {"key": "parse_ptab", "pillar": SUP_PILLAR, "kind": SourceKind.filing, "trust": 70,
     "title": "PTAB invalidates 10x patent claims; Parse instrument-free combinatorial barcoding (2024)",
     "url": "https://www.parsebiosciences.com/news/in-a-key-win-for-parse-patent-trial-and-appeal-board-invalidates-10x-genomics-patent-claims/",
     "rationale": "Records a PTAB ruling (a legal fact, checkable) + the existence of split-pool "
                  "barcoding that routes around droplet partitioning — the rising-substitute disconfirmer. "
                  "Vendor-published, so discounted, but the underlying PTAB decision is primary."},
]

# Nodes of the single-cell RNA-seq chain. `supply_multiple_3y` = how much this link can scale
# within the ~3-yr horizon under the 10x assay shock (its elasticity), with a 1σ. The assay is the
# demand origin (no supply param). Substitute nodes carry no supply param — they exist to receive
# `substitutes` edges. These numbers are in-session reasoned estimates, GROUNDED in the sources and
# explicitly HUMAN-VERIFIED before they are flowed (see propose_verification).
NODES: list[dict] = [
    {"key": "assay", "name": "single-cell RNA-seq assay (demand origin)", "kind": "assay",
     "sm": None, "sd": None, "src": None,
     "note": "The 10x demand shock enters here and propagates upstream through depends_on edges."},
    {"key": "consumable", "name": "droplet partitioning consumable (microfluidic chip + barcoded gel beads)",
     "kind": "consumable", "sm": 4.0, "sd": 1.2, "src": "tenx_patent",
     "note": "10x-dominant, proprietary microfluidics + beads, razor-blade model. Specialized "
             "manufacturing scales far slower than 10x demand → inelastic over 3y."},
    {"key": "prep", "name": "NGS library prep kits", "kind": "prep",
     "sm": 10.0, "sd": 2.0, "src": None,
     "note": "Commodity reagent kits, many interchangeable vendors → elastic."},
    {"key": "sequencer", "name": "short-read sequencer capacity", "kind": "equipment",
     "sm": 12.0, "sd": 3.0, "src": "nhgri_cost",
     "note": "NovaSeq X throughput jump + 4 new vendors; cost/Gb falling → highly elastic."},
    {"key": "reagents", "name": "sequencing reagents / flow cells", "kind": "reagent",
     "sm": 8.0, "sd": 2.0, "src": "ngs_competition",
     "note": "Tied to sequencer vendors; multi-vendor competition makes capacity reasonably elastic."},
    {"key": "sub_seq", "name": "alt short-read platforms (MGI / Element / Ultima)", "kind": "substitute",
     "sm": None, "sd": None, "src": "ngs_competition",
     "note": "Drop-in substitutes for Illumina short reads — why the sequencer is not the bottleneck."},
    {"key": "sub_combi", "name": "instrument-free combinatorial barcoding (Parse / SPLiT-seq)",
     "kind": "substitute", "sm": None, "sd": None, "src": "parse_ptab",
     "note": "Routes around droplet partitioning entirely. The rising substitute — and the live "
             "kill-criterion on the forward card."},
]

# Edges — sparse + high-precision. depends_on: the assay needs each input (pass-through ≈ 1.0).
# substitutes: an alternative that can absorb a fraction of demand (weight = that fraction, +1σ).
EDGES: list[dict] = [
    {"src": "assay", "dst": "consumable", "rel": "depends_on", "w": 1.0, "wsd": 0.0, "src_key": "tenx_patent",
     "note": "Every droplet single-cell assay consumes one chip lane + gel beads — 1:1."},
    {"src": "assay", "dst": "prep", "rel": "depends_on", "w": 1.0, "wsd": 0.0, "src_key": None,
     "note": "Each assay needs a library prep."},
    {"src": "assay", "dst": "sequencer", "rel": "depends_on", "w": 1.0, "wsd": 0.0, "src_key": "nhgri_cost",
     "note": "Each library must be sequenced (short read)."},
    {"src": "sequencer", "dst": "reagents", "rel": "depends_on", "w": 1.0, "wsd": 0.0, "src_key": "ngs_competition",
     "note": "Sequencing consumes flow cells / reagents proportionally."},
    {"src": "consumable", "dst": "sub_combi", "rel": "substitutes", "w": 0.35, "wsd": 0.12, "src_key": "parse_ptab",
     "note": "Combinatorial barcoding can absorb a rising minority of demand; PTAB invalidation lifts "
             "this. Modelled ~0.35 (1σ 0.12) — least-substitutable today, but moving."},
    {"src": "sequencer", "dst": "sub_seq", "rel": "substitutes", "w": 0.70, "wsd": 0.10, "src_key": "ngs_competition",
     "note": "Short-read sequencing is highly substitutable across ≥4 competing vendors."},
]


# --- the SECOND chain: the AI-power buildout (proves the engine generalizes) --
# Same structure, new domain. The thesis (the survived hypothesis): capital floods the GPU layer
# (elastic-ish — TSMC/CoWoS expanding, multiple foundries) but CANNOT fast-forward the electrical
# layer. We model supply ELASTICITY per node and let propagation compute the bottleneck under flow —
# we do NOT label it. The non-obvious answer the oracle is for: the constraint behind the constraint.

AI_POWER_CHAIN = "ai_power"
AI_POWER_SHOCK = 10.0   # the ~10x datacenter-power demand the AI buildout implies over the horizon

AI_POWER_SOURCES: list[dict] = [
    {"key": "fred_xfmr", "pillar": SUP_PILLAR, "kind": SourceKind.primary, "trust": 88,
     "title": "FRED/BLS PPI — Power & Distribution Transformer Mfg (PCU335311335311)",
     "url": "https://fred.stlouisfed.org/series/PCU335311335311",
     "rationale": "Official BLS producer-price index (keyless): the transformer layer's price broke "
                  "from ~250 (2020) to ~443 (2025) — the binding-constraint signature priced in real "
                  "time. Primary, high trust; a price proxy for lead-time scarcity (not lead times)."},
    {"key": "doe_lpt", "pillar": SUP_PILLAR, "kind": SourceKind.primary, "trust": 82,
     "title": "U.S. DOE — Large Power Transformers and the U.S. Electric Grid (report)",
     "url": "https://www.energy.gov/ceser/articles/large-power-transformers-and-us-electric-grid",
     "rationale": "U.S. government primary report documenting LPT lead times, import dependence, and "
                  "the grain-oriented-electrical-steel (GOES) input constraint. High trust: official, "
                  "the canonical record that the transformer/GOES layer is structurally inelastic."},
    {"key": "lbnl_queue", "pillar": SUP_PILLAR, "kind": SourceKind.primary, "trust": 85,
     "title": "LBNL 'Queued Up' — grid interconnection queue durations",
     "url": "https://emp.lbl.gov/queues",
     "rationale": "Lawrence Berkeley National Lab's primary dataset on interconnection-queue volumes "
                  "and the multi-year wait to connect. High trust (national lab, transparent); the "
                  "evidence the interconnection layer is slow + administratively constrained."},
    {"key": "ferc_2023", "pillar": 8, "kind": SourceKind.filing, "trust": 78,
     "title": "FERC Order No. 2023 — generator interconnection process reform",
     "url": "https://www.ferc.gov/news-events/news/ferc-issues-final-rule-improve-generator-interconnection-process",
     "rationale": "FERC's final rule to clear the interconnection backlog — the DISCONFIRMER on the "
                  "queue leg (if it works, the queue is elastic). A real regulatory instrument; "
                  "encoded as the substitutes/kill path, not hidden."},
    {"key": "btm_gen", "pillar": SUP_PILLAR, "kind": SourceKind.news, "trust": 58,
     "title": "Hyperscaler behind-the-meter generation (gas / SMR / solar+storage) buildouts",
     "url": "https://www.utilitydive.com/topic/data-center/",
     "rationale": "Trade-press corroborated across outlets: hyperscalers routing around the public-grid "
                  "queue with co-located generation. Mid trust (secondary). The disconfirmer to the "
                  "interconnection leg — but it STILL needs transformers/switchgear, so it relocates "
                  "the constraint within the electrical layer rather than removing it."},
    {"key": "goes_steel", "pillar": SUP_PILLAR, "kind": SourceKind.news, "trust": 60,
     "title": "Grain-oriented electrical steel (GOES) — concentrated global supply",
     "url": "https://www.cleveland-cliffs.com/products/category/electrical-steel",
     "rationale": "GOES is the magnetic core of every large transformer, made by a handful of global "
                  "producers (Nippon Steel, POSCO, Baowu, ThyssenKrupp, Cleveland-Cliffs in the US). "
                  "Mid trust (a producer page + widely corroborated): the constraint behind the "
                  "transformer — least-substitutable, slowest to add capacity."},
]

# supply_multiple_3y = how much this link can scale within the horizon under the 10x AI-power shock.
# Capital is flooding compute (foundries + CoWoS expanding) → GPU relatively ELASTIC; the electrical
# layer cannot be fast-forwarded → INELASTIC; GOES steel is the deepest, least-substitutable input.
AI_POWER_NODES: list[dict] = [
    {"key": "origin", "name": "AI datacenter capacity buildout (demand origin)", "kind": "assay",
     "sm": None, "sd": None, "src": None,
     "note": "The ~10x datacenter-power demand shock enters here and propagates upstream."},
    {"key": "gpu", "name": "AI accelerator + CoWoS advanced packaging", "kind": "equipment",
     "sm": 6.0, "sd": 2.0, "src": None,
     "note": "The obvious layer everyone prices (NVDA). Capital is flooding it — TSMC/Samsung/Intel "
             "+ aggressive CoWoS capacity adds → relatively elastic over the horizon vs the grid."},
    {"key": "transformer", "name": "large-power transformer (>=100 MVA)", "kind": "transformer",
     "sm": 2.0, "sd": 0.6, "src": "fred_xfmr",
     "note": "2–4 yr lead times, PPI +75% since 2020; specialized plants scale far slower than demand "
             "→ inelastic. No drop-in substitute for a large-power transformer."},
    {"key": "goes", "name": "grain-oriented electrical steel (GOES)", "kind": "material",
     "sm": 1.6, "sd": 0.5, "src": "goes_steel",
     "note": "The magnetic core input to every transformer; a handful of global producers, slowest "
             "capacity response → the constraint behind the constraint, least-substitutable."},
    {"key": "switchgear", "name": "high-voltage switchgear", "kind": "grid",
     "sm": 2.6, "sd": 0.8, "src": "fred_xfmr",
     "note": "Adjacent grid-gear layer, PPI +60% since 2020; tight but with a few more vendors than "
             "large-power transformers → inelastic, slightly less so."},
    {"key": "interconnection", "name": "grid interconnection queue / permitting", "kind": "grid",
     "sm": 1.8, "sd": 0.6, "src": "lbnl_queue",
     "note": "Multi-year ISO/RTO queues + permitting; administratively constrained. Behind-the-meter "
             "generation is a partial substitute (the disconfirmer), so not fully inelastic."},
    {"key": "sub_foundry", "name": "alt foundries / packaging (Samsung, Intel, Amkor, ASE)",
     "kind": "substitute", "sm": None, "sd": None, "src": None,
     "note": "Why the GPU layer is relatively elastic — multiple foundry + OSAT packaging routes."},
    {"key": "sub_btm", "name": "behind-the-meter generation (gas / SMR / solar+storage)",
     "kind": "substitute", "sm": None, "sd": None, "src": "btm_gen",
     "note": "Routes around the public-grid queue — but still needs transformers/switchgear, so it "
             "relocates the constraint within the electrical layer (the narrowed disconfirmer)."},
]

AI_POWER_EDGES: list[dict] = [
    {"src": "origin", "dst": "gpu", "rel": "depends_on", "w": 1.0, "wsd": 0.0, "src_key": None,
     "note": "Every unit of AI capacity needs accelerators."},
    {"src": "origin", "dst": "transformer", "rel": "depends_on", "w": 1.0, "wsd": 0.0, "src_key": "fred_xfmr",
     "note": "Every datacenter needs large-power transformers to take grid power."},
    {"src": "origin", "dst": "switchgear", "rel": "depends_on", "w": 1.0, "wsd": 0.0, "src_key": "fred_xfmr",
     "note": "And HV switchgear to distribute it."},
    {"src": "origin", "dst": "interconnection", "rel": "depends_on", "w": 1.0, "wsd": 0.0, "src_key": "lbnl_queue",
     "note": "And a grid interconnection to energize at all."},
    {"src": "transformer", "dst": "goes", "rel": "depends_on", "w": 1.0, "wsd": 0.0, "src_key": "goes_steel",
     "note": "Each large-power transformer requires grain-oriented electrical steel for its core — 1:1."},
    {"src": "gpu", "dst": "sub_foundry", "rel": "substitutes", "w": 0.40, "wsd": 0.10, "src_key": None,
     "note": "Multiple foundry/packaging routes absorb a meaningful fraction → GPU layer elastic-ish."},
    {"src": "interconnection", "dst": "sub_btm", "rel": "substitutes", "w": 0.30, "wsd": 0.12, "src_key": "btm_gen",
     "note": "Behind-the-meter generation absorbs ~0.3 of queue demand; FERC Order 2023 could lift it "
             "— but it relocates, not removes, the electrical constraint."},
]


# --- persistence (validated through the Pydantic models — GIGO gate) ----------


def _upsert_source(conn: sqlite3.Connection, src: Source) -> str:
    row = conn.execute("SELECT id FROM sources WHERE url=?", (src.url,)).fetchone()
    if row:
        return row["id"]
    conn.execute(
        "INSERT INTO sources (id,url,title,pillar_id,kind,trust_score,trust_rationale,"
        "recency,accessed_at,cost_cents,content_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (src.id, src.url, src.title, src.pillar_id, src.kind.value, src.trust_score,
         src.trust_rationale, None, src.accessed_at.isoformat(), 0, None),
    )
    return src.id


def _upsert_node(conn: sqlite3.Connection, n: GraphNode) -> str:
    row = conn.execute("SELECT id FROM graph_nodes WHERE chain=? AND name=?",
                       (n.chain, n.name)).fetchone()
    if row:
        conn.execute(
            "UPDATE graph_nodes SET kind=?, domain=?, supply_multiple_3y=?, supply_multiple_sd=?, "
            "source_id=?, note=?, layer=?, demand_kind=?, build_series_id=? WHERE id=?",
            (n.kind, n.domain, n.supply_multiple_3y, n.supply_multiple_sd, n.source_id, n.note,
             n.layer, n.demand_kind, n.build_series_id, row["id"]),
        )
        return row["id"]
    conn.execute(
        "INSERT INTO graph_nodes (id,chain,name,kind,domain,supply_multiple_3y,supply_multiple_sd,"
        "source_id,note,layer,demand_kind,build_series_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (n.id, n.chain, n.name, n.kind, n.domain, n.supply_multiple_3y, n.supply_multiple_sd,
         n.source_id, n.note, n.layer, n.demand_kind, n.build_series_id, n.created_at.isoformat()),
    )
    return n.id


def _upsert_edge(conn: sqlite3.Connection, e: GraphEdge) -> str:
    row = conn.execute("SELECT id FROM graph_edges WHERE chain=? AND src=? AND dst=? AND rel=?",
                       (e.chain, e.src, e.dst, e.rel)).fetchone()
    if row:
        conn.execute(
            "UPDATE graph_edges SET weight=?, weight_sd=?, source_id=?, note=? WHERE id=?",
            (e.weight, e.weight_sd, e.source_id, e.note, row["id"]),
        )
        return row["id"]
    conn.execute(
        "INSERT INTO graph_edges (id,chain,src,dst,rel,weight,weight_sd,source_id,note,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (e.id, e.chain, e.src, e.dst, e.rel, e.weight, e.weight_sd, e.source_id, e.note,
         e.created_at.isoformat()),
    )
    return e.id


def _seed_chain(conn: sqlite3.Connection, *, chain: str, sources: list[dict], nodes: list[dict],
                edges: list[dict], domain: str, log=print) -> dict:
    """Build ANY supply chain: sourced nodes + typed edges. Chain-agnostic — the same engine code
    runs scRNA-seq or AI-power; only the data differs. Idempotent. Opens pillars 3-4 (rule 2)."""
    src_ids: dict[str, str] = {}
    for s in sources:
        obj = Source(url=s["url"], title=s["title"], pillar_id=s["pillar"], kind=s["kind"],
                     trust_score=s["trust"], trust_rationale=s["rationale"])
        src_ids[s["key"]] = _upsert_source(conn, obj)

    node_ids: dict[str, str] = {}
    for n in nodes:
        obj = GraphNode(chain=chain, name=n["name"], kind=n["kind"], domain=domain,
                        supply_multiple_3y=n["sm"], supply_multiple_sd=n["sd"],
                        source_id=src_ids.get(n["src"]) if n["src"] else None, note=n["note"],
                        layer=n.get("layer"),
                        demand_kind="terminal" if n["kind"] == "assay" else n.get("demand_kind", "derived"))
        node_ids[n["key"]] = _upsert_node(conn, obj)

    n_edges = 0
    for e in edges:
        obj = GraphEdge(chain=chain, src=node_ids[e["src"]], dst=node_ids[e["dst"]], rel=e["rel"],
                        weight=e["w"], weight_sd=e["wsd"],
                        source_id=src_ids.get(e["src_key"]) if e["src_key"] else None, note=e["note"])
        _upsert_edge(conn, obj)
        n_edges += 1

    conn.execute("UPDATE pillars SET status='in_progress' WHERE id IN (?,?) AND status='untapped'",
                 (DEP_PILLAR, SUP_PILLAR))
    conn.commit()
    log(f"seeded chain '{chain}': {len(node_ids)} nodes, {n_edges} edges, {len(src_ids)} sources.")
    return {"nodes": len(node_ids), "edges": n_edges, "sources": len(src_ids)}


def seed_graph(conn: sqlite3.Connection, *, log=print) -> dict:
    """Build the scRNA-seq supply graph: sourced nodes + typed edges. Idempotent."""
    return _seed_chain(conn, chain=CHAIN, sources=SOURCES, nodes=NODES, edges=EDGES,
                       domain="genomics / single-cell", log=log)


def seed_ai_power(conn: sqlite3.Connection, *, log=print) -> dict:
    """Build the AI-power supply graph (the 2nd domain). Same engine, new data."""
    return _seed_chain(conn, chain=AI_POWER_CHAIN, sources=AI_POWER_SOURCES, nodes=AI_POWER_NODES,
                       edges=AI_POWER_EDGES, domain="energy / grid / AI infrastructure", log=log)


# --- the THIRD chain: metals/materials — the cross-DOMAIN extension --------------------------------
# This is the proof that the graph is one connected WORLD, not isolated silos. The AI-power chain's
# grid gear (transformer, switchgear) consumes refined copper; refined copper consumes mine supply.
# We attach this metals chain UNDER ai_power with cross-domain `depends_on` edges, then flow the SAME
# datacenter-power shock across the boundary. The bottleneck is recomputed over the connected world —
# and the question this answers is whether connecting the next domain migrates the constraint DEEPER
# (power → metals), exactly the constraint-migration thesis crossing a domain line. Mine supply is
# Ruben's domain (miningterminal): new copper mines take 10-15 yr, so the 3-yr horizon barely moves it.

METALS_CHAIN = "metals"

METALS_SOURCES: list[dict] = [
    {"key": "fred_copper", "pillar": SUP_PILLAR, "kind": SourceKind.primary, "trust": 86,
     "title": "FRED/BLS PPI — Copper & copper products (PCU331420331420)",
     "url": "https://fred.stlouisfed.org/series/PCU331420331420",
     "rationale": "Official BLS producer-price index (keyless): copper mill-product prices ran ~82 "
                  "(2020) → ~146 (2025). Primary, high trust — a price proxy for refined-copper "
                  "tightness as electrification + AI grid demand hit a slow-moving supply base."},
    {"key": "iea_copper", "pillar": SUP_PILLAR, "kind": SourceKind.primary, "trust": 84,
     "title": "IEA — The Role of Critical Minerals in Clean Energy Transitions (copper supply / lead times)",
     "url": "https://www.iea.org/reports/the-role-of-critical-minerals-in-clean-energy-transitions",
     "rationale": "IEA primary analysis documenting copper mine lead times (~10-16 yr discovery→production) "
                  "and declining ore grades. High trust (IGO, transparent method): the evidence that mine "
                  "supply is structurally inelastic over any 3-yr forecast horizon — the deep constraint."},
]

# supply_multiple_3y over the 10x datacenter-power shock. Refined copper (smelting/refining) can flex
# modestly; mine supply almost cannot within the horizon (new mines = a decade-plus). `layer` deepens
# from the ai_power grid gear (layer 3-4) into metals (5 = refined, 6 = mine — the floor).
METALS_NODES: list[dict] = [
    {"key": "copper_cathode", "name": "refined copper (cathode)", "kind": "material",
     "sm": 2.0, "sd": 0.6, "src": "fred_copper", "layer": 5,
     "note": "Refined/smelted copper for transformer windings + switchgear busbars. Some smelter "
             "flex, but feedstock-bound → modestly inelastic; PPI +~78% since 2020."},
    {"key": "copper_mine", "name": "copper mine supply (concentrate)", "kind": "material",
     "sm": 1.3, "sd": 0.35, "src": "iea_copper", "layer": 6,
     "note": "Primary mined copper. New mines take 10-16 yr; ore grades falling → barely scales within "
             "a 3-yr horizon. The least-substitutable input behind the grid — the constraint's floor."},
]

METALS_EDGES: list[dict] = [
    {"src": "copper_cathode", "dst": "copper_mine", "rel": "depends_on", "w": 1.0, "wsd": 0.0,
     "src_key": "iea_copper",
     "note": "Every tonne of refined copper needs mined concentrate — no synthetic substitute (1:1)."},
]

# The cross-DOMAIN edges: ai_power grid gear depends on metals refined copper. Tagged to the ai_power
# chain (the consumer side) so a world-scope query (chain IN ('ai_power','metals')) walks across them.
AI_POWER_METALS_LINKS: list[dict] = [
    {"src_chain": AI_POWER_CHAIN, "src_name": "high-voltage switchgear",
     "dst_chain": METALS_CHAIN, "dst_name": "refined copper (cathode)",
     "rel": "depends_on", "w": 1.0, "wsd": 0.0, "src_key": "fred_copper",
     "note": "HV switchgear is copper-intensive (busbars, contacts) → its supply rides on refined copper."},
    {"src_chain": AI_POWER_CHAIN, "src_name": "large-power transformer (>=100 MVA)",
     "dst_chain": METALS_CHAIN, "dst_name": "refined copper (cathode)",
     "rel": "depends_on", "w": 0.7, "wsd": 0.1, "src_key": "fred_copper",
     "note": "Transformer windings are copper (~0.7 pass-through alongside the GOES core constraint)."},
]


def seed_metals(conn: sqlite3.Connection, *, log=print) -> dict:
    """Build the metals chain AND wire the cross-domain edges from ai_power into it (rule 1: every
    cross edge carries a Source). Idempotent. Requires ai_power already seeded (the consumer side)."""
    out = _seed_chain(conn, chain=METALS_CHAIN, sources=METALS_SOURCES, nodes=METALS_NODES,
                      edges=METALS_EDGES, domain="metals / mining / raw materials", log=log)
    n_links = _link_chains(conn, AI_POWER_METALS_LINKS, sources=METALS_SOURCES, log=log)
    out["cross_edges"] = n_links
    return out


def _link_chains(conn: sqlite3.Connection, links: list[dict], *, sources: list[dict], log=print) -> int:
    """Add cross-domain `depends_on` edges between nodes in DIFFERENT chains. Looks up endpoints by
    (chain, name); the edge is tagged to the consumer (src) chain so a world-scope query includes it."""
    src_ids: dict[str, str] = {}
    for s in sources:
        obj = Source(url=s["url"], title=s["title"], pillar_id=s["pillar"], kind=s["kind"],
                     trust_score=s["trust"], trust_rationale=s["rationale"])
        src_ids[s["key"]] = _upsert_source(conn, obj)

    def node_id(chain: str, name: str) -> str:
        row = conn.execute("SELECT id FROM graph_nodes WHERE chain=? AND name=?", (chain, name)).fetchone()
        if row is None:
            raise ValueError(f"cross-domain link endpoint not found: {chain}/{name} (seed it first)")
        return row["id"]

    n = 0
    for lk in links:
        e = GraphEdge(chain=lk["src_chain"], src=node_id(lk["src_chain"], lk["src_name"]),
                      dst=node_id(lk["dst_chain"], lk["dst_name"]), rel=lk["rel"],
                      weight=lk["w"], weight_sd=lk["wsd"],
                      source_id=src_ids.get(lk["src_key"]) if lk["src_key"] else None, note=lk["note"])
        _upsert_edge(conn, e)
        n += 1
    conn.commit()
    log(f"linked {n} cross-domain edges (ai_power → metals).")
    return n


# --- the human-verify gate (rule 4 + §9) -------------------------------------


def propose_verification(conn: sqlite3.Connection) -> Decision:
    """Write the Decision the human must answer BEFORE we propagate (never flow an unverified chain).

    Surfaces the single pivotal assumption: that the partitioning consumable is the inelastic,
    least-substitutable node and the sequencer is elastic — with the per-edge sources behind it.
    """
    prompt = (
        "Verify the scRNA-seq supply chain before propagating the 10x demand shock. Critical "
        "assumption: the droplet partitioning consumable is the INELASTIC, least-substitutable "
        "link (supply_multiple≈4x/3y, substitutes≈0.35) while the short-read sequencer is ELASTIC "
        "(≈12x/3y, substitutes≈0.70). Sources: 10x patent + CAFC/Bio-Rad ruling (consumable IP "
        "defended); NHGRI cost curve + 4 new short-read vendors (sequencer elastic); PTAB "
        "invalidation + Parse combinatorial barcoding (the rising substitute = live kill-criterion). "
        "Is this chain sound enough to flow?"
    )
    opts = ["Confirm — flow the shock",
            "Adjust parameters first",
            "Reject — sequencer is the bottleneck"]
    rec = ("Confirm. The A-not-B structure is grounded in courts/NHGRI/trade press, and the one "
           "real risk (rising consumable substitutability) is already encoded as the substitutes "
           "edge + kill-criterion, not hidden.")
    return _open_decision(conn, prompt, opts, rec,
                          blocks="constraint propagation + the graph-backed scRNA-seq forecast")


def _open_decision(conn: sqlite3.Connection, prompt: str, opts: list[str], rec: str,
                   *, blocks: str) -> Decision:
    """Open (or return the already-open) verify-Decision. Idempotent on prompt."""
    existing = conn.execute(
        "SELECT id FROM decisions WHERE prompt=? AND status='open'", (prompt,)
    ).fetchone()
    if existing:
        return Decision(id=existing["id"], prompt=prompt, options=opts, recommendation=rec)
    d = Decision(prompt=prompt, options=opts, recommendation=rec, blocks=blocks)
    conn.execute(
        "INSERT INTO decisions (id,created_at,prompt,options,recommendation,context_source_ids,"
        "status,chosen_option,decided_at,blocks) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (d.id, d.created_at.isoformat(), d.prompt, _json(opts), d.recommendation,
         _json([]), d.status.value, None, None, d.blocks),
    )
    conn.commit()
    return d


def propose_ai_power_verification(conn: sqlite3.Connection) -> Decision:
    """The pivotal human gate for the AI-power chain (rule 4): which layer is the binding constraint,
    and is the chain sound enough to flow into a forecast? Surfaces the bottleneck fork explicitly."""
    prompt = (
        "Verify the AI-power supply chain before propagating the ~10x datacenter-power shock. Critical "
        "assumption: capital floods the GPU layer (elastic-ish — TSMC/CoWoS + multiple foundries, "
        "supply≈6x/3y, substitutes≈0.40), but the electrical layer CANNOT be fast-forwarded — large-"
        "power transformers (≈2x/3y, no substitute; PPI +75% since 2020), grain-oriented electrical "
        "steel / GOES (≈1.6x/3y, a handful of producers), HV switchgear (≈2.6x/3y), grid "
        "interconnection (≈1.8x/3y, behind-the-meter a partial substitute). Sources: FRED/BLS PPI "
        "(price break), DOE LPT report, LBNL Queued Up, FERC Order 2023 (the queue disconfirmer). "
        "Which layer is THE binding constraint to anchor the forecast on, and is the chain sound to flow?"
    )
    opts = ["Confirm — flow; anchor on GOES electrical steel (deepest, least-substitutable)",
            "Confirm — flow; anchor on the large-power transformer (the named layer)",
            "Confirm — flow; anchor on the grid-interconnection queue",
            "Reject / adjust — the electrical layer is more elastic than modeled"]
    rec = ("Confirm and flow. Propagation puts the deepest pressure on GOES electrical steel, then the "
           "transformer — the constraint behind the constraint. Anchor the FORECAST on the transformer "
           "PPI (the one clean keyless point-in-time series), but name GOES as the true bottleneck. The "
           "queue disconfirmer (FERC 2023 / behind-the-meter) is encoded as a substitutes edge + kill-"
           "criterion, not hidden.")
    return _open_decision(conn, prompt, opts, rec,
                          blocks="AI-power constraint propagation + promoting the 2nd forward forecast")


def record_decision(conn: sqlite3.Connection, decision_id: str, chosen: str) -> None:
    """Stamp the human's verification onto the Decision row (closes the gate)."""
    conn.execute(
        "UPDATE decisions SET status='decided', chosen_option=?, decided_at=? WHERE id=?",
        (chosen, _now().isoformat(), decision_id),
    )
    conn.commit()


def _json(x) -> str:
    import json
    return json.dumps(x)


# --- constraint propagation (component 6) ------------------------------------


@dataclass
class Pressure:
    node_id: str
    name: str
    kind: str
    required_multiple: float
    supply_multiple: float       # central estimate
    substitutability: float      # central, from substitutes edges
    pressure: float              # central (required/supply)·(1−substitutability)
    p_bottleneck: float          # MC: fraction of draws where this node is THE bottleneck


@dataclass
class Propagation:
    bottleneck: Pressure
    obvious_endpoint: Pressure | None    # the elastic node the naive eye would pick (the sequencer)
    pressures: list[Pressure]
    gap_median: float                    # supply shortfall multiple at the bottleneck (Y)
    gap_ci_low: float
    gap_ci_high: float
    shock: float


def _scope(chain: str, chains: tuple[str, ...] | None) -> tuple[str, ...]:
    """The set of chains the propagation walks. A single chain by default; pass `chains` to flow the
    shock across a CONNECTED WORLD (e.g. ai_power + metals) so cross-domain edges are traversed."""
    return tuple(chains) if chains else (chain,)


def _depends_required(conn: sqlite3.Connection, assay_id: str, *,
                      chain: str = CHAIN, chains: tuple[str, ...] | None = None,
                      shock: float = SHOCK) -> dict[str, float]:
    """Flow the shock from the assay along depends_on edges → required supply multiple per node.

    For this sparse chain it's a short BFS multiplying pass-through weights (≈1.0), so every
    reachable supply node must deliver ≈shock×. Kept general so a branching chain works too —
    including across the chain boundary when `chains` spans more than one domain.
    """
    scope = _scope(chain, chains)
    ph = ",".join("?" * len(scope))
    edges = conn.execute(
        f"SELECT src, dst, weight FROM graph_edges WHERE chain IN ({ph}) AND rel='depends_on'", scope
    ).fetchall()
    out: dict[str, float] = {assay_id: shock}
    frontier = [assay_id]
    while frontier:
        cur = frontier.pop()
        for e in edges:
            if e["src"] == cur:
                req = out[cur] * e["weight"]
                if req > out.get(e["dst"], 0.0):
                    out[e["dst"]] = req
                    frontier.append(e["dst"])
    return out


def propagate(conn: sqlite3.Connection, *, chain: str = CHAIN, chains: tuple[str, ...] | None = None,
              shock: float = SHOCK, seed: int = 4, n: int = MC_N) -> Propagation:
    """Flow the demand shock; Monte-Carlo the uncertain supply elasticities + substitute capacities.

    Per draw: each supply node's pressure = (required / supply_multiple)·(1 − substitutability),
    where substitutability is the summed capacity of its `substitutes` edges. The bottleneck is the
    argmax pressure — the first-saturating, least-substitutable node. Across draws we get P(each node
    is the bottleneck) and the 80% CI on the bottleneck's supply gap. The interval falls out of the
    sampling, never typed (execution §3). Chain-agnostic, and WORLD-agnostic: pass `chains` to flow
    the shock across a connected set of domains so the bottleneck is computed over the whole world.
    """
    scope = _scope(chain, chains)
    ph = ",".join("?" * len(scope))
    nodes = conn.execute(
        f"SELECT id, name, kind, chain, supply_multiple_3y, supply_multiple_sd, source_id "
        f"FROM graph_nodes WHERE chain IN ({ph})", scope,
    ).fetchall()
    by_id = {r["id"]: r for r in nodes}
    assay_id = next(r["id"] for r in nodes if r["kind"] == "assay")
    required = _depends_required(conn, assay_id, chain=chain, chains=chains, shock=shock)

    subs = conn.execute(
        f"SELECT src, weight, weight_sd FROM graph_edges WHERE chain IN ({ph}) AND rel='substitutes'", scope
    ).fetchall()
    subs_by_src: dict[str, list] = {}
    for s in subs:
        subs_by_src.setdefault(s["src"], []).append(s)

    # supply nodes = everything reachable by the shock that actually has a supply parameter. The
    # `nid in by_id` guard drops dependencies that cross OUT of the active scope (a cross-domain edge
    # tagged to ai_power points into metals, which a single-chain ai_power run hasn't loaded) — so a
    # narrow scope simply can't see, and won't wrongly bottleneck on, a domain it didn't include.
    supply_ids = [nid for nid in required
                  if nid in by_id and by_id[nid]["supply_multiple_3y"] is not None]

    rng = random.Random(seed)
    win = {nid: 0 for nid in supply_ids}
    gap_samples: dict[str, list[float]] = {nid: [] for nid in supply_ids}

    for _ in range(n):
        best_id, best_pressure, best_gap = None, -1.0, 1.0
        for nid in supply_ids:
            r = by_id[nid]
            sm = max(1.0, rng.gauss(r["supply_multiple_3y"], r["supply_multiple_sd"] or 0.0))
            sub = sum(max(0.0, rng.gauss(s["weight"], s["weight_sd"])) for s in subs_by_src.get(nid, []))
            sub = min(0.95, sub)
            req = required[nid]
            gap = req / sm
            pressure = gap * (1.0 - sub)
            if pressure > best_pressure:
                best_id, best_pressure, best_gap = nid, pressure, gap
        win[best_id] += 1
        gap_samples[best_id].append(best_gap)

    def central(nid: str) -> Pressure:
        r = by_id[nid]
        sm = r["supply_multiple_3y"]
        sub = min(0.95, sum(s["weight"] for s in subs_by_src.get(nid, [])))
        req = required[nid]
        return Pressure(node_id=nid, name=r["name"], kind=r["kind"], required_multiple=req,
                        supply_multiple=sm, substitutability=sub,
                        pressure=(req / sm) * (1.0 - sub), p_bottleneck=win[nid] / n)

    pressures = sorted((central(nid) for nid in supply_ids), key=lambda p: p.pressure, reverse=True)
    bottleneck = pressures[0]
    obvious = next((p for p in pressures if p.kind == "equipment"), None)

    gs = sorted(gap_samples[bottleneck.node_id])
    pct = lambda q: gs[min(len(gs) - 1, int(q * len(gs)))] if gs else float("nan")
    return Propagation(
        bottleneck=bottleneck, obvious_endpoint=obvious, pressures=pressures,
        gap_median=pct(0.50), gap_ci_low=pct(0.10), gap_ci_high=pct(0.90), shock=shock,
    )


# --- where to point the deep data: drill-score (data follows the graph) ----------------------------
# The graph says WHERE the constraint is; this says where our DATA is thinnest at that constraint, so
# the expensive miningterminal-grade extraction goes to the node that is both a likely bottleneck AND
# poorly measured. drill_score = P(bottleneck) × (1 − coverage). Coverage reuses what we already have:
# a node with an audited measured build-out series gets its series_health; a node whose supply
# PARAMETER is merely sourced gets partial credit; an unsourced node gets none. High pressure + thin
# data floats to the top — that's where data, not reasoning, is the binding constraint (this session's
# whole thesis). When build series are attached (next cut), this sharpens automatically.


@dataclass
class DrillTarget:
    node_id: str
    name: str
    chain: str
    p_bottleneck: float
    coverage: float        # 0..1 — how well this node is measured
    drill_score: float     # p_bottleneck × (1 − coverage): high pressure + thin data = drill here
    why: str


def drill_targets(conn: sqlite3.Connection, prop: Propagation, *,
                  chain: str = CHAIN, chains: tuple[str, ...] | None = None) -> list[DrillTarget]:
    """Rank the propagation's nodes by where to spend the deep-data budget (see header note)."""
    scope = _scope(chain, chains)
    ph = ",".join("?" * len(scope))
    rows = conn.execute(
        f"SELECT n.id, n.chain, n.build_series_id, s.trust_score AS trust, h.health_score AS health "
        f"FROM graph_nodes n LEFT JOIN sources s ON s.id = n.source_id "
        f"LEFT JOIN series_health h ON h.series_id = n.build_series_id WHERE n.chain IN ({ph})", scope
    ).fetchall()
    meta = {r["id"]: r for r in rows}

    out: list[DrillTarget] = []
    for p in prop.pressures:
        r = meta.get(p.node_id)
        if r and r["build_series_id"] and r["health"] is not None:
            coverage, why = float(r["health"]), f"measured build series (health {float(r['health']):.0%})"
        elif r and r["trust"]:
            coverage = (r["trust"] / 100) * 0.5     # a sourced PARAMETER ≠ a measured build series
            why = f"parameter sourced (trust {int(r['trust'])}), no build-out series yet"
        else:
            coverage, why = 0.0, "no source, no build series — unmeasured"
        out.append(DrillTarget(node_id=p.node_id, name=p.name, chain=(r["chain"] if r else "?"),
                               p_bottleneck=p.p_bottleneck, coverage=coverage,
                               drill_score=p.p_bottleneck * (1 - coverage), why=why))
    out.sort(key=lambda d: d.drill_score, reverse=True)
    return out


# --- value-of-information: which measurement collapses the most uncertainty? (execution §3) --------
# drill_targets says where DATA is thinnest at the constraint. This says something sharper: of all the
# uncertain INPUTS (each node's reasoned supply-elasticity σ, each substitute's capacity σ), which one,
# if measured PRECISELY (σ→0), would most sharpen our confidence in WHERE the bottleneck is? That input
# is the single cheapest measurement to take next — the operator payoff (Hubbard's value-of-information).
# We compute it the honest way: re-run the propagation Monte-Carlo with each input perfectly measured and
# see how much P(modal bottleneck) rises. The largest rise wins. $0, stdlib.


@dataclass
class VoITerm:
    input_name: str        # the uncertain input (a node's elasticity, or a substitute's capacity)
    kind: str              # 'elasticity' | 'substitutability'
    sigma: float           # the input's current 1σ (the uncertainty we'd be collapsing)
    voi: float             # rise in P(modal bottleneck) if this input were measured precisely
    why: str


def variance_budget(conn: sqlite3.Connection, *, chain: str = CHAIN, chains: tuple[str, ...] | None = None,
                    shock: float = SHOCK, seed: int = 4, n: int = 20_000) -> tuple[str, float, list[VoITerm]]:
    """Rank the uncertain inputs by value-of-information (see header). Returns (modal-bottleneck name,
    baseline P(modal), ranked VoI terms). The top term is the measurement that most sharpens the call."""
    scope = _scope(chain, chains)
    ph = ",".join("?" * len(scope))
    nodes = conn.execute(
        f"SELECT id, name, kind, supply_multiple_3y sm, supply_multiple_sd sd "
        f"FROM graph_nodes WHERE chain IN ({ph})", scope).fetchall()
    by_id = {r["id"]: r for r in nodes}
    assay_id = next(r["id"] for r in nodes if r["kind"] == "assay")
    required = _depends_required(conn, assay_id, chain=chain, chains=chains, shock=shock)
    subs = conn.execute(
        f"SELECT id, src, weight w, weight_sd wsd FROM graph_edges "
        f"WHERE chain IN ({ph}) AND rel='substitutes'", scope).fetchall()
    subs_by_src: dict[str, list] = {}
    for s in subs:
        subs_by_src.setdefault(s["src"], []).append(dict(s))
    supply_ids = [nid for nid in required if nid in by_id and by_id[nid]["sm"] is not None]

    def run(zero_node: str | None = None, zero_sub: str | None = None) -> dict[str, int]:
        rng = random.Random(seed)
        win = {nid: 0 for nid in supply_ids}
        for _ in range(n):
            best_id, best_p = None, -1.0
            for nid in supply_ids:
                r = by_id[nid]
                sd = 0.0 if zero_node == nid else (r["sd"] or 0.0)
                sm = max(1.0, rng.gauss(r["sm"], sd))
                sub = 0.0
                for s in subs_by_src.get(nid, []):
                    wsd = 0.0 if zero_sub == s["id"] else s["wsd"]
                    sub += max(0.0, rng.gauss(s["w"], wsd))
                pressure = (required[nid] / sm) * (1.0 - min(0.95, sub))
                if pressure > best_p:
                    best_id, best_p = nid, pressure
            win[best_id] += 1
        return win

    base = run()
    modal = max(base, key=base.get)
    base_p = base[modal] / n
    terms: list[VoITerm] = []
    for nid in supply_ids:                                   # each node's elasticity σ
        if (by_id[nid]["sd"] or 0) <= 0:
            continue
        p = run(zero_node=nid)[modal] / n
        terms.append(VoITerm(by_id[nid]["name"], "elasticity", float(by_id[nid]["sd"]), p - base_p,
            f"measuring {by_id[nid]['name']}'s supply elasticity (σ={by_id[nid]['sd']:.2f}) lifts "
            f"P(bottleneck) {base_p:.0%}→{p:.0%}"))
    for s in subs:                                           # each substitute's capacity σ
        if (s["wsd"] or 0) <= 0:
            continue
        p = run(zero_sub=s["id"])[modal] / n
        nm = by_id[s["src"]]["name"]
        terms.append(VoITerm(f"{nm} substitutability", "substitutability", float(s["wsd"]), p - base_p,
            f"measuring the substitute capacity around {nm} (σ={s['wsd']:.2f}) lifts P(bottleneck) "
            f"{base_p:.0%}→{p:.0%}"))
    terms.sort(key=lambda t: t.voi, reverse=True)
    return by_id[modal]["name"], base_p, terms


# --- attach a measured build series to a node (the demand-is-measurable drill) ----


def set_build_series(conn: sqlite3.Connection, *, chain: str, node_name: str, series_id: str | None,
                     log=print) -> bool:
    """Point a node's `build_series_id` at a measured build-out series — the deep-data drill landing.

    Flips the node from a *sourced parameter* (coverage ≈ trust×0.5) to a *measured series* (coverage
    = its QC health) in `drill_targets`, so the drill-score collapses once the data the graph asked
    for actually exists. Idempotent.
    """
    if not series_id:
        log(f"  ! no build series to attach to {chain}/{node_name}")
        return False
    row = conn.execute("SELECT id FROM graph_nodes WHERE chain=? AND name=?",
                       (chain, node_name)).fetchone()
    if row is None:
        log(f"  ! node not found: {chain}/{node_name}")
        return False
    conn.execute("UPDATE graph_nodes SET build_series_id=? WHERE id=?", (series_id, row["id"]))
    conn.commit()
    log(f"  attached measured build series → {node_name}")
    return True


# --- tie-back to the forecast registry (rule 7) ------------------------------


def graph_backed_forward_card(conn: sqlite3.Connection, prop: Propagation) -> dict:
    """Supersede the open scRNA-seq forward card with a now-GRAPH-DERIVED version (rule 7).

    The old card *asserted* the consumable bottleneck in prose. The new one cites the supply graph
    that DERIVES it under flow and adds the magnitude leg plan.md demands ("exceeds supply by Y
    [interval]"). The binary question + resolution date are unchanged so it still resolves the same
    way; the old card is retained verbatim for the track record. No-op if already done.
    """
    from engine import forecast

    old = conn.execute(
        "SELECT id, question, probability, resolution_date, ci_low, ci_high, ci_unit, "
        "seed_series_id, pillars_used, kill_criteria, rationale, superseded_by "
        "FROM forecast_cards WHERE question LIKE 'By FY2026, do NIH grant awards mentioning single-cell%' "
        "AND superseded_by IS NULL"
    ).fetchone()
    if old is None:
        return {"superseded": False, "reason": "no open forward card found"}
    if old["rationale"].startswith("GRAPH-DERIVED"):
        return {"superseded": False, "reason": "forward card is already graph-derived (idempotent)"}

    import json
    b, seq = prop.bottleneck, prop.obvious_endpoint
    edge_src_ids = [r["source_id"] for r in conn.execute(
        "SELECT DISTINCT source_id FROM graph_edges WHERE chain=? AND source_id IS NOT NULL", (CHAIN,)
    ).fetchall()]

    rationale = (
        "GRAPH-DERIVED constraint migration (Phase 4 — was asserted, now computed under flow). "
        f"A {prop.shock:.0f}x demand shock on single-cell assays, propagated through a human-verified "
        f"supply graph ({CHAIN}), saturates first at the LEAST-substitutable node: "
        f"'{b.name}' — pressure {b.pressure:.2f}, P(bottleneck)={b.p_bottleneck:.0%}, supply gap "
        f"{prop.gap_median:.1f}x (80% CI [{prop.gap_ci_low:.1f},{prop.gap_ci_high:.1f}]). "
        + (f"The obvious endpoint — '{seq.name}' — is ELASTIC (pressure {seq.pressure:.2f}, "
           f"substitutability {seq.substitutability:.0%}), so rent does NOT land there. "
           if seq else "")
        + "This DERIVES the A-not-B claim the prior card only asserted. The binary demand "
        "probability is unchanged (the grant-velocity Monte-Carlo); what is new is the magnitude "
        "leg — demand exceeds partitioning-consumable supply by the gap interval above. Live "
        "disconfirmer (kill-criterion): the consumable's substitutability is rising "
        f"(~{b.substitutability:.0%}, Parse/SPLiT-seq + PTAB invalidation), which would dissolve the rent."
    )
    kill = json.loads(old["kill_criteria"])
    kill = list(dict.fromkeys(kill + [
        f"Constraint-propagation no longer puts the partitioning consumable first (P(bottleneck) "
        f"falls below 50%) on refreshed supply data — the bottleneck moved (graph falsified)."
    ]))
    pillars = sorted(set(json.loads(old["pillars_used"]) + [DEP_PILLAR, SUP_PILLAR]))

    new = forecast.supersede(
        conn, old["id"], question=old["question"], probability=old["probability"],
        resolution_date=date.fromisoformat(old["resolution_date"]),
        ci_low=old["ci_low"], ci_high=old["ci_high"], ci_unit=old["ci_unit"],
        seed_series_id=old["seed_series_id"], rationale=rationale,
        kill_criteria=kill, pillars_used=pillars, source_ids=edge_src_ids,
    )
    return {"superseded": True, "old_id": old["id"], "new_id": new.id,
            "bottleneck": b.name, "gap": prop.gap_median}


# --- the CONSTRAINT card: probability FROM the graph, not the trend (redteam #2) ------------------
# The demand-count cards put a number on "does this series cross threshold X by date Z" — and that
# number is the series' OWN growth Monte-Carlo (momentum). The mechanism (the graph) only picked the
# noun. This is the missing object: a card whose PROBABILITY is the propagation's P(bottleneck) and
# whose magnitude is the supply-gap distribution. The constraint actually binding IS the credence; a
# monitor series only RESOLVES it. Pairs with — does not replace — the demand card (two honest
# objects: a demand call from the trend, a constraint call from the graph, no longer conflated).


def constraint_card(conn: sqlite3.Connection, prop: Propagation, *, chain: str, question: str,
                    resolution_date: date, monitor_series_id: str | None = None,
                    kill_extra: list[str] | None = None, pillars: list[int] | None = None) -> dict:
    """Write a NEW immutable, graph-derived ForecastCard whose probability = P(bottleneck) from the
    propagation MC (NOT a trend extrapolation) and whose 80% CI = the supply-gap distribution.
    Idempotent on the question text."""
    from engine import forecast

    if conn.execute("SELECT 1 FROM forecast_cards WHERE question=?", (question,)).fetchone():
        return {"created": False, "reason": "constraint card already exists", "question": question}

    b, obv = prop.bottleneck, prop.obvious_endpoint
    edge_src_ids = [r["source_id"] for r in conn.execute(
        "SELECT DISTINCT source_id FROM graph_edges WHERE chain=? AND source_id IS NOT NULL", (chain,)
    ).fetchall()]

    rationale = (
        "GRAPH-DERIVED PROBABILITY (fixes redteam #2 — the number IS the mechanism, not a trend "
        "follow). The probability is NOT the momentum of any series; it is P(bottleneck) straight "
        f"from the supply-graph propagation Monte-Carlo: a {prop.shock:.0f}x demand shock flowed "
        f"through the human-verified '{chain}' chain makes '{b.name}' the first-saturating, "
        f"least-substitutable node in {b.p_bottleneck:.0%} of draws. The 80% CI is the SUPPLY-GAP "
        f"distribution ({prop.gap_ci_low:.1f}–{prop.gap_ci_high:.1f}x, median {prop.gap_median:.1f}x): "
        "demand exceeds this layer's supply by that factor. "
        + (f"The obvious endpoint '{obv.name}' is ELASTIC (pressure {obv.pressure:.2f}, "
           f"substitutability {obv.substitutability:.0%}) — rent does NOT land there. " if obv else "")
        + ("The monitor series RESOLVES this card; it does NOT generate the probability."
           if monitor_series_id else
           "No public pure-play supply series for this node yet — resolved on refreshed propagation "
           "+ substitute-share (a [?] data gap, named not faked).")
    )
    kill = [
        f"Refreshed supply data drops P(bottleneck) for '{b.name}' below 50% in the propagation — "
        "the constraint moved (the graph is falsified).",
        "A substitute lifts this layer's elasticity so the modeled supply gap closes below 1x — the "
        "rent dissipates.",
    ] + (list(kill_extra) if kill_extra else [])

    card = forecast.create_card(
        conn, question=question, probability=round(b.p_bottleneck, 3),
        resolution_date=resolution_date,
        ci_low=round(prop.gap_ci_low, 2), ci_high=round(prop.gap_ci_high, 2),
        ci_unit="x supply gap", seed_series_id=monitor_series_id, rationale=rationale,
        kill_criteria=kill, pillars_used=pillars or [DEP_PILLAR, SUP_PILLAR], source_ids=edge_src_ids,
    )
    return {"created": True, "id": card.id, "bottleneck": b.name, "p": b.p_bottleneck,
            "gap": prop.gap_median}


def seed_constraint_cards(conn: sqlite3.Connection, *, log=print) -> dict:
    """Write the graph-derived constraint cards for both live chains (redteam #2). Ensures the chains
    are seeded (idempotent), propagates each, and writes a card whose probability = P(bottleneck).
    $0, stdlib only. Pairs with the existing demand-count cards — never supersedes them."""
    seed_graph(conn, log=lambda *_: None)
    seed_ai_power(conn, log=lambda *_: None)
    seed_metals(conn, log=lambda *_: None)

    results = []

    # scRNA-seq: the droplet partitioning consumable
    p1 = propagate(conn, chain=CHAIN, shock=SHOCK)
    results.append(constraint_card(
        conn, p1, chain=CHAIN,
        question=("GRAPH TEST — under a 10x single-cell-assay demand shock, is the droplet "
                  "partitioning consumable the BINDING supply constraint (first-saturating, supply "
                  "gap >=1x) of the scRNA-seq chain through 2027-06-30? [graph-derived, as-of 2026-06-03]"),
        resolution_date=date(2027, 6, 30),
        kill_extra=["A non-10x / open-source droplet method (Parse/SPLiT-seq, expired-patent generic) "
                    "takes the dominant share — the consumable layer was elastic, rent dissipated."],
    ))

    # AI-power: the electrical-steel / transformer layer, monitored by the transformer PPI series
    p2 = propagate(conn, chain=AI_POWER_CHAIN, shock=AI_POWER_SHOCK)
    mon = conn.execute(
        "SELECT id FROM series WHERE label LIKE '%ransformer PPI%' ORDER BY label LIMIT 1"
    ).fetchone()
    results.append(constraint_card(
        conn, p2, chain=AI_POWER_CHAIN,
        question=(f"GRAPH TEST — under the AI-datacenter buildout (~10x grid-power demand), is "
                  f"'{p2.bottleneck.name}' the BINDING supply constraint (first-saturating, supply "
                  f"gap >=1x) of the electrical chain through 2028-12-31? [graph-derived, as-of 2026-06-03]"),
        resolution_date=date(2028, 12, 31),
        monitor_series_id=mon["id"] if mon else None,
        kill_extra=["FERC Order 2023 / behind-the-meter generation / new GOES capacity clears the "
                    "electrical bottleneck — the layer was more elastic than modeled.",
                    "The obvious GPU / compute layer becomes the binding constraint instead."],
    ))

    created = sum(1 for r in results if r.get("created"))
    for r in results:
        if r.get("created"):
            log(f"  constraint card → {r['bottleneck']}  P(bottleneck)={r['p']:.0%}  "
                f"gap {r['gap']:.1f}x")
        else:
            log(f"  skipped (idempotent): {r['reason']}")
    return {"created": created, "results": results}
