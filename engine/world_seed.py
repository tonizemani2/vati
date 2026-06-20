"""The unifying world graph: one spine-typed `chain='world'` skeleton over the islands.

The DB already holds three disconnected graphs — the measured concept-dependency graph
(`chain='concept_flow'`, 13k nodes / 52k draws_on edges), a small hand-seeded value-chain supply
graph (`ai_power`/`scrna_seq`/`metals`), and ~130k metric series — plus an entity spine that links
series to real-world actors but barely touches the graph nodes. None of them is typed onto the
causal thesis spine, and the `layer` (causal depth) column is NULL everywhere.

This module mints the seam: a bounded `chain='world'` graph where every node is grounded in real
data (a value-chain link or a series that actually FIRED the detector / survived FDR) and tagged by
its position on the spine

    Frontier → Capability → Dependency → Supply → Demand → Capital → Pricing → Policy → Outcome

so a forecast can be read against the whole structure, not one topic in isolation. We deliberately do
NOT copy the 13k concepts or 130k raw series into `world` — that is noise. The big graphs stay as the
substrate you walk INTO (concept_flow via dependency_neighbors, a series via build_series_id); `world`
is the navigable skeleton and the merge target that Pope/Vati atlases accumulate into.

Honest by construction: a `world` node carries a build_series_id (a dated, measured series) or comes
from a concrete value-chain link. Nothing is asserted that the data layer cannot see. Idempotent
(deterministic ids + INSERT OR IGNORE), additive (only the new `world` chain is written), $0,
stdlib + sqlite only.

Usage:
    uv run python -m engine.cli world-seed
    uv run python -m engine.cli world-coverage "AI datacenter power"
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from engine import db, signals

CHAIN = "world"
_VALUE_CHAINS = ("ai_power", "scrna_seq", "metals")

# The thesis spine as a causal-depth ladder. Per the graph_nodes.layer convention
# (0 = terminal demand/outcome, larger = deeper input), the frontier is the deepest input.
SPINE: list[tuple[str, int]] = [
    ("frontier", 8),     # the research / capability frontier — deepest input
    ("capability", 7),   # commercialised capability (paper→patent, patents)
    ("dependency", 6),   # the knowledge / input dependency graph
    ("supply", 5),       # supply elasticity / value-chain links
    ("demand", 4),       # derived demand build-out / attention
    ("capital", 3),      # money: filings, funding, macro
    ("pricing", 2),      # the gate — is it already priced?
    ("policy", 1),       # permits, sanctions, regulatory action
    ("outcome", 0),      # terminal outcome
]
LAYER_INT = dict(SPINE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _nid(name: str) -> str:
    """Deterministic node id so re-seeding never duplicates (UNIQUE(chain,name) also guards)."""
    return hashlib.md5(f"{CHAIN}|{name}".encode()).hexdigest()


def _eid(src: str, dst: str, rel: str) -> str:
    return hashlib.md5(f"{CHAIN}|{src}|{dst}|{rel}".encode()).hexdigest()


def series_layer(metric: str) -> str:
    """Map a series metric to its spine layer. The default lands on 'capability' (a frontier signal)
    and is flagged in the node note so an unmapped metric is auditable, never silently mis-placed."""
    m = (metric or "").lower()
    if m in {
        "research_share_ppm", "research_field_breadth", "research_works", "research_field_citations",
        "research_bridge_fraction", "works_published", "works_per_year", "preprints_posted",
        "europe_pmc_paper_publication", "topic_share", "field_diffusion", "field_breadth",
        "talent_inflow", "citations_received_per_year", "frontier_training_compute",
    }:
        return "frontier"
    if "patent" in m:
        return "capability"
    if m.startswith("baci_") or m == "trade_value" or "supplier" in m or "import" in m:
        return "supply"
    if m in {"sec_filing_mentions", "macro_indicator", "science_funding"} or "funding" in m:
        return "capital"
    if m in {"commodity_price", "market_implied_prob", "equity_close"} or "price" in m or "close" in m:
        return "pricing"
    if (
        "permit" in m or "regulat" in m or m == "federal_register_docs" or m.startswith("sanctions")
        or "referral" in m or "epbc" in m or m.startswith("blm_") or "impact_assessment" in m
        or "resource_contract" in m or "trial_current" in m or m.endswith("_status")
    ):
        return "policy"
    if "pageview" in m or "alert" in m:
        return "demand"
    return "capability"


# The curated causal pillar (engine/db.py pillars table, assigned per-feed in feeds/ingest.py
# FEED_META with a written trust rationale) IS the authoritative spine layer. 1:1 with SPINE.
_PILLAR_LAYER = {1: "frontier", 2: "capability", 3: "dependency", 4: "supply",
                 5: "demand", 6: "capital", 7: "pricing", 8: "policy", 9: "outcome"}


def layer_for(pillar_id, metric: str) -> str:
    """Bin a series to its spine layer. Prefer the curated `pillar_id` (the human-assigned causal
    pillar carries a per-feed trust rationale); fall back to the metric heuristic only when a series
    has no pillar. This corrects the old metric-substring routing that silently dumped most demand /
    outcome / supply metrics into the 'capability' catch-all and routed nothing to 'outcome'."""
    name = _PILLAR_LAYER.get(pillar_id)
    if name:
        return name
    return series_layer(metric)


def _put_node(conn, name: str, layer: str, *, domain: str | None = None, note: str = "",
              build_series_id: str | None = None, demand_kind: str = "derived", now: str) -> str:
    nid = _nid(name)
    conn.execute(
        "INSERT OR IGNORE INTO graph_nodes "
        "(id, chain, name, kind, domain, note, layer, demand_kind, build_series_id, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (nid, CHAIN, name, layer, domain, note, LAYER_INT[layer], demand_kind, build_series_id, now),
    )
    return nid


def _put_edge(conn, src: str, dst: str, rel: str, *, weight: float = 1.0, note: str = "", now: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO graph_edges (id, chain, src, dst, rel, weight, note, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (_eid(src, dst, rel), CHAIN, src, dst, rel, weight, note, now),
    )


def seed_world(conn, *, log=print) -> dict:
    """Mint / refresh the `chain='world'` skeleton from existing data. Returns a counts summary."""
    now = _now()

    # 1) Value-chain supply links → world supply nodes, carrying their typed edges.
    vc = conn.execute(
        "SELECT id, chain, name, kind, demand_kind FROM graph_nodes WHERE chain IN (?,?,?)",
        _VALUE_CHAINS,
    ).fetchall()
    idmap: dict[str, str] = {}
    for r in vc:
        nid = _put_node(conn, r["name"], "supply", domain=r["chain"],
                        note=f"value-chain link: {r['kind']}", demand_kind=r["demand_kind"], now=now)
        idmap[r["id"]] = nid
    n_vc_nodes = len(idmap)

    n_vc_edges = 0
    ve = conn.execute(
        "SELECT src, dst, rel, weight FROM graph_edges WHERE chain IN (?,?,?)", _VALUE_CHAINS
    ).fetchall()
    for e in ve:
        if e["src"] in idmap and e["dst"] in idmap:
            _put_edge(conn, idmap[e["src"]], idmap[e["dst"]], e["rel"], weight=e["weight"] or 1.0,
                      note="value-chain", now=now)
            n_vc_edges += 1

    # 2) Series that actually fired the detector OR survived FDR → spine nodes, one per series,
    #    grounded by build_series_id. This is the multi-layer backbone (frontier..policy), and the
    #    fired/fdr gate naturally drops the ~110k inert land-use permit series.
    srows = conn.execute(
        "SELECT id, label, metric, domain, pillar_id, last_surprise_sigma sig "
        "FROM series WHERE COALESCE(last_fired,0)=1 OR COALESCE(last_fdr_survive,0)=1"
    ).fetchall()
    per_layer: dict[str, int] = {}
    n_series_nodes = 0
    for r in srows:
        layer = layer_for(r["pillar_id"], r["metric"])
        sig = r["sig"]
        note = f"series metric={r['metric']}" + (f"; surprise={sig:.1f}σ" if sig is not None else "")
        _put_node(conn, r["label"], layer, domain=r["domain"], note=note,
                  build_series_id=r["id"], now=now)
        per_layer[layer] = per_layer.get(layer, 0) + 1
        n_series_nodes += 1

    conn.commit()

    total_nodes = conn.execute(
        "SELECT count(*) FROM graph_nodes WHERE chain=?", (CHAIN,)).fetchone()[0]
    total_edges = conn.execute(
        "SELECT count(*) FROM graph_edges WHERE chain=?", (CHAIN,)).fetchone()[0]

    log(f"world graph: {total_nodes} nodes, {total_edges} edges (chain='{CHAIN}')")
    log(f"  value-chain: {n_vc_nodes} supply nodes, {n_vc_edges} edges")
    log(f"  series-grounded: {n_series_nodes} nodes across layers")
    for name, _ in SPINE:
        if per_layer.get(name):
            log(f"    {name:<11} {per_layer[name]}")
    return {
        "chain": CHAIN, "total_nodes": total_nodes, "total_edges": total_edges,
        "value_chain_nodes": n_vc_nodes, "value_chain_edges": n_vc_edges,
        "series_nodes": n_series_nodes, "per_layer": per_layer,
    }


def coverage(conn, topic: str) -> dict:
    """The coverage critic: for a topic, which spine layers does the world graph cover, and which are
    blank (unaccounted for)? Token-overlap match on world nodes per layer, plus a live walk into the
    measured concept-dependency graph (concept_flow) so the dependency layer reflects the 52k edges
    even though we never copied the concepts."""
    qtoks = set(signals._tokens(topic))
    by_layer: dict[str, list[dict]] = {name: [] for name, _ in SPINE}
    if qtoks:
        rows = conn.execute(
            "SELECT name, kind, domain, note, build_series_id FROM graph_nodes WHERE chain=?",
            (CHAIN,)).fetchall()
        for n in rows:
            keep = lambda toks: {t for t in toks if len(t) >= 2 and t not in signals.STOP}
            name_ov = qtoks & keep(signals._tokset(n["name"]))
            meta_ov = qtoks & keep(signals._tokset(n["domain"] or "", n["note"] or ""))
            # Anchor on the node NAME: a single shared name-token qualifies (e.g. "lithium").
            # A metadata-only match (domain/note) needs >=2 tokens, so a lone generic word like
            # "earth" can't drag every `earth_events` disaster node into a rare-earth query.
            if name_ov or len(meta_ov) >= 2:
                by_layer.setdefault(n["kind"], []).append(
                    {"name": n["name"], "domain": n["domain"], "grounded": bool(n["build_series_id"])})

    # live bridge into the measured dependency graph (not copied into `world`)
    dep = signals.dependency_neighbors(conn, topic)
    if dep:
        by_layer["dependency"].extend(
            {"name": d["concept"], "domain": "concept_flow",
             "draws_on": [x["name"] for x in d["draws_on"][:4]],
             "drawn_on_by": [x["name"] for x in d["drawn_on_by"][:4]],
             "patent_reliance": d.get("patent_reliance", {}).get("n_patents")} for d in dep)

    covered = [name for name, _ in SPINE if by_layer.get(name)]
    gaps = [name for name, _ in SPINE if not by_layer.get(name)]
    return {"topic": topic, "covered_layers": covered, "gap_layers": gaps,
            "by_layer": by_layer, "coverage_score": round(len(covered) / len(SPINE), 2)}


def format_coverage(cov: dict) -> str:
    lines = [f"WORLD-GRAPH COVERAGE for '{cov['topic']}' — {cov['coverage_score']:.0%} "
             f"({len(cov['covered_layers'])}/{len(SPINE)} spine layers)"]
    for name, _ in SPINE:
        items = cov["by_layer"].get(name) or []
        if not items:
            lines.append(f"  [{name:<11}] —  GAP (unaccounted for)")
            continue
        head = items[:4]
        bits = []
        for it in head:
            tag = "✓" if it.get("grounded") or name == "dependency" else "·"
            extra = ""
            if it.get("patent_reliance"):
                extra = f" ({it['patent_reliance']:,} patents cite it)"
            elif it.get("draws_on"):
                extra = f" → {', '.join(it['draws_on'][:2])}"
            bits.append(f"{tag} {it['name']}{extra}")
        more = f"  (+{len(items) - len(head)} more)" if len(items) > len(head) else ""
        lines.append(f"  [{name:<11}] " + " | ".join(bits) + more)
    if cov["gap_layers"]:
        lines.append("GAPS → the layers above with no node are the data-layer feeds to wire next, "
                     "or the part of the call the structure currently can't see.")
    return "\n".join(lines)
