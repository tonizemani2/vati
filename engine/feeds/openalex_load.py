"""OpenAlex LAST-MILE loader — land the already-derived snapshot artifacts into foresight.db.

WHY (2026-06-15). The expensive part is done: the OpenAlex snapshot is frozen to our S3 bucket and
two 639 GB Athena CTAS passes (≈$6.40, see data/_collect_logs/athena_cost.log) already materialized
the full paper→paper citation graph (`citation_edges`, 35 GB Parquet) and per-work attributes
(`work_attrs`). The per-field citation SERIES (bridge fraction, cite velocity) are ingested too. But
two pieces of "water" never reached the tap — this module pumps them the last inch:

  1. CONCEPT INDEX → entities.  The 69k-concept index (data/feeds/openalex_concept_index.jsonl) is an
     authoritative OpenAlex id set, not a fuzzy match — so it lands as `entities` rows with
     confidence-by-construction (kind='research_concept', the OpenAlex id carried as an alias). This
     fills the "entity index barely exists (145)" gap (tier-2 of DATA_LAYER_PLAN). FREE, no network.

  2. FIELD→FIELD CITATION-FLOW GRAPH → graph_nodes / graph_edges.  We have each field's *scalar*
     outward-citation fraction, but not the directed who-draws-on-whom matrix. This aggregates the
     citation graph (citing→cited, joined to field on both ends) into a sparse, weighted, directed
     DEPENDENCY graph: edge A→B with weight = the share of field A's cross-field citations that land
     in field B = "how much A's knowledge base is built on B". chain='research_flow'. This is the
     literal dependency-graph layer the project says is empty (16 edges) — the substrate that makes a
     forward claim *intertwined* (traceable across fields) rather than rhetorically linked.
     COST: one Athena aggregation over the existing 35 GB Parquet, partition-pruned to recent citing
     years ≈ $0.10–0.20 (NOT a fresh 639 GB scan). Logged to athena_cost.log. >$0 → cost gate.

LEAK DISCIPLINE: the flow graph is built from edges whose CITING paper is recent (citing_year window below),
so it reflects the dependency structure as it stands now; each edge is dated by that window. Nothing is
interpolated; a field pair with no citations is simply absent.

USAGE
  uv run python -m engine.feeds.openalex_load --concepts                 # FREE: load the entity index
  uv run python -m engine.feeds.openalex_load --field-graph             # ~$0.16 Athena: flow graph
  uv run python -m engine.feeds.openalex_load --concepts --field-graph  # both
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from engine import db
from engine.entity import _upsert_entity
from engine.feeds import athena
from engine.graph import _upsert_edge, _upsert_node, _upsert_source
from engine.pillars.frontier import _log_cost
from engine.schemas import Entity, GraphEdge, GraphNode, Source, SourceKind

FEEDS_DIR = Path(__file__).resolve().parents[2] / "data" / "feeds"
CONCEPT_INDEX = FEEDS_DIR / "openalex_concept_index.jsonl"

DEP_PILLAR = 3            # Dependency graph
FLOW_CHAIN = "research_flow"
CITING_FROM_YEAR = 2015  # only edges whose CITING paper is >= this year (current structure; less scan)
MIN_EDGE_SHARE = 0.03    # keep an A→B edge only if B takes >=3% of A's cross-field citations (sparse)


# ── 1. concept index → entities (FREE) ───────────────────────────────────────


def load_concept_index(conn: sqlite3.Connection, *, max_level: int = 3, min_works: int = 1000,
                       log=print) -> dict:
    """Load the OpenAlex concept index into `entities` as authoritative research concepts.

    These are NOT fuzzy resolutions — each is the canonical OpenAlex concept id (carried as an alias
    so it is queryable), so the entity-resolution doctrine's merge risk does not apply. Filtered to a
    navigable backbone (level <= max_level, works_count >= min_works) so the index is substantial but
    not hyper-granular noise. Idempotent (upsert on kind+canonical_name). $0 — logged at the gate.
    """
    if not CONCEPT_INDEX.exists():
        log(f"  ! no concept index at {CONCEPT_INDEX}")
        return {"loaded": 0, "skipped": 0}

    loaded = skipped = 0
    for line in CONCEPT_INDEX.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = (o.get("name") or "").strip()
        level = o.get("level")
        works = o.get("works_count") or 0
        if not name or level is None or level > max_level or works < min_works:
            skipped += 1
            continue
        cid = o.get("id")
        note = (f"OpenAlex concept {cid} (level {level}); works_count={works:,}, "
                f"cited_by_count={o.get('cited_by_count') or 0:,}. Authoritative provider id "
                f"(not a fuzzy match). Pulled {o.get('pulled')}.")
        ent = Entity(kind="research_concept", canonical_name=name,
                     aliases=[f"oa:{cid}"] if cid else [], note=note)
        _upsert_entity(conn, ent)
        loaded += 1

    _log_cost(conn, "load_concept_index", "openalex", float(loaded))
    conn.commit()
    log(f"  concept index → entities: loaded {loaded:,} (skipped {skipped:,} "
        f"below level<={max_level}/works>={min_works})")
    return {"loaded": loaded, "skipped": skipped}


# ── 2. field→field citation-flow graph (ATHENA, ~$0.16) ───────────────────────


def _fetch_all_rows(qid: str) -> list[list[str]]:
    """Page through Athena results (skips the header row of the first page). Small result sets only."""
    rows: list[list[str]] = []
    token = None
    first = True
    while True:
        args = ["athena", "get-query-results", "--query-execution-id", qid, "--max-items", "1000"]
        if token:
            args += ["--starting-token", token]
        res = athena._aws(args)
        page = res.get("ResultSet", {}).get("Rows", [])
        if first and page:
            page = page[1:]  # header
            first = False
        for r in page:
            rows.append([c.get("VarCharValue", "") for c in r.get("Data", [])])
        token = res.get("NextToken")
        if not token:
            break
    return rows


def build_field_flow_graph(conn: sqlite3.Connection, *, citing_from: int = CITING_FROM_YEAR,
                           min_share: float = MIN_EDGE_SHARE, log=print) -> dict:
    """Derive the directed field→field citation-flow graph and land it in graph_nodes/graph_edges.

    edge A->B (rel='draws_on'): field A's papers cite field B's papers; weight = B's share of A's
    CROSS-field (A!=B) outbound citations. Sparse — only edges with weight >= min_share are kept.
    COST: scans citation_edges (partition-pruned to citing_year>=citing_from) JOIN work_attrs twice.
    """
    sql = f"""
    SELECT cf.field AS citing_field, df.field AS cited_field, count(*) AS n
    FROM citation_edges ce
    JOIN work_attrs cf ON ce.citing = cf.id
    JOIN work_attrs df ON ce.cited = df.id
    WHERE ce.citing_year >= {citing_from}
      AND cf.field IS NOT NULL AND df.field IS NOT NULL
      AND cf.field <> '' AND df.field <> ''
    GROUP BY cf.field, df.field
    """
    log(f"  [athena] field→field citation flow (citing_year>={citing_from}) ...")
    res = athena.run_query(sql, log=log)
    _log_cost(conn, "athena:field_flow_graph", "athena", res["gb"])
    rows = _fetch_all_rows(res["id"])
    if not rows:
        log("  ! no rows returned — flow graph not built")
        return {"nodes": 0, "edges": 0, "gb": res["gb"]}

    # tally: cross-field outbound per source field, and the raw A->B counts
    out_cross: dict[str, int] = {}
    pair: dict[tuple[str, str], int] = {}
    fields: set[str] = set()
    for citing, cited, n in rows:
        n = int(n)
        fields.add(citing)
        fields.add(cited)
        if citing == cited:
            continue
        pair[(citing, cited)] = pair.get((citing, cited), 0) + n
        out_cross[citing] = out_cross.get(citing, 0) + n

    # provenance source for every node + edge (GIGO gate, rule 1)
    src = Source(
        url="s3://openalex (citation_edges ⋈ work_attrs)",
        title="OpenAlex citation graph — directed field-to-field flow",
        pillar_id=DEP_PILLAR, kind=SourceKind.primary, trust_score=84,
        trust_rationale=(
            "Derived from the frozen OpenAlex snapshot's full paper→paper citation graph "
            f"(citing_year>={citing_from}), joined to each work's primary field on both ends. "
            "Authoritative scholarly graph; the directed flow is a measured count, not an estimate."))
    src_id = _upsert_source(conn, src)

    node_ids: dict[str, str] = {}
    for f in sorted(fields):
        node = GraphNode(chain=FLOW_CHAIN, name=f, kind="field", domain=f, source_id=src_id,
                         note="OpenAlex research field; a node in the knowledge-dependency graph.")
        node_ids[f] = _upsert_node(conn, node)

    n_edges = 0
    for (a, b), n in pair.items():
        denom = out_cross.get(a, 0)
        if denom <= 0:
            continue
        share = n / denom
        if share < min_share:
            continue
        edge = GraphEdge(
            chain=FLOW_CHAIN, src=node_ids[a], dst=node_ids[b], rel="draws_on",
            weight=round(share, 4), weight_sd=0.0, source_id=src_id,
            note=(f"{a} cites {b}: {n:,} edges = {share:.1%} of {a}'s cross-field outbound citations "
                  f"(citing_year>={citing_from}). Higher = {a}'s knowledge base leans more on {b}."))
        _upsert_edge(conn, edge)
        n_edges += 1

    conn.execute("UPDATE pillars SET status='in_progress' WHERE id=? AND status='untapped'", (DEP_PILLAR,))
    conn.commit()
    log(f"  research_flow graph: {len(node_ids)} field nodes, {n_edges} directed edges "
        f"(share>={min_share:.0%}), scanned {res['gb']:.1f} GB (~${res['gb']/1000*5:.3f})")
    return {"nodes": len(node_ids), "edges": n_edges, "gb": res["gb"]}


# ── 3. concept→concept citation-flow graph (ATHENA CTAS, ~$3.2 + agg) ─────────
# The needle-grade version of (2): instead of 26 coarse fields, the directed dependency graph at the
# CONCEPT level (thousands of nodes). Two steps: (a) a one-time CTAS that UNNESTs each work's concepts
# into a work→concept table (the only fresh full-works scan, ≈$3.2); (b) a cheap aggregation that
# joins the citation graph to concepts on both ends → concept A draws_on concept B. The "not a theme,
# a needle" substrate the gate/pope reason along.

BUCKET = "vaticinus-datalake-405844305300-us-east-1"
CONCEPT_CHAIN = "concept_flow"
WORK_CONCEPTS_S3 = f"s3://{BUCKET}/openalex/derived/work_concepts/"
WORK_PRIMARY_S3 = f"s3://{BUCKET}/openalex/derived/work_primary_concept/"
MAX_CITING_YEAR = 2025


def _ensure_work_concepts(*, force: bool, log=print) -> float:
    """CTAS the work→concept table from the snapshot (idempotent unless force). Returns GB scanned.

    Reads works/ once (≈639 GB compressed → ≈$3.2). Only concepts at level 1–3 with score>=0.3 are
    kept (the meaningful conceptual tags, not every faint co-mention), so the Parquet output is slim."""
    exists = bool(athena.subprocess.run(["aws", "s3", "ls", WORK_CONCEPTS_S3],
                                        capture_output=True, text=True).stdout.strip())
    if exists and not force:
        log("  [athena] work_concepts already materialized — reusing (no fresh works scan, $0)")
        return 0.0
    if exists and force:
        athena.subprocess.run(["aws", "s3", "rm", WORK_CONCEPTS_S3, "--recursive", "--only-show-errors"])
    # drop any orphan Glue entry so the CTAS dest is clean (harmless if absent)
    athena.run_query("DROP TABLE IF EXISTS vaticinus.work_concepts", log=log)

    athena.run_query(
        "CREATE EXTERNAL TABLE IF NOT EXISTS openalex_works_concepts ("
        "  id string,"
        "  concepts array<struct<id:string, display_name:string, level:int, score:double>>)"
        " ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'"
        " WITH SERDEPROPERTIES ('ignore.malformed.json'='true')"
        " STORED AS TEXTFILE LOCATION 's3://openalex/data/works'", log=log)

    log("  [athena] CTAS work_concepts (UNNEST concepts; the one full works scan ≈$3.2) ...")
    res = athena.run_query(
        f"CREATE TABLE vaticinus.work_concepts WITH (format='PARQUET',"
        f" external_location='{WORK_CONCEPTS_S3}') AS "
        "SELECT w.id AS work_id, c.id AS concept_id, c.display_name AS concept_name,"
        "       c.level AS lvl, c.score AS score "
        "FROM openalex_works_concepts w CROSS JOIN UNNEST(w.concepts) AS t(c) "
        "WHERE c.level BETWEEN 1 AND 3 AND c.score >= 0.3", log=log)
    return res["gb"]


def _ensure_work_primary(*, force: bool, log=print) -> float:
    """Collapse work_concepts to ONE row per work (its highest-score concept) → work_primary_concept.

    The full work_concepts table is the whole OpenAlex corpus (~336M works × ~5.8 concepts = ~1.95B
    rows); a concept→concept self-join on it explodes ~34x and times out. Reducing each work to its
    primary concept makes the citation join 1:1 — tractable. Cheap (scans the slim Parquet, ≈$0.07)."""
    exists = bool(athena.subprocess.run(["aws", "s3", "ls", WORK_PRIMARY_S3],
                                        capture_output=True, text=True).stdout.strip())
    if exists and not force:
        log("  [athena] work_primary_concept already materialized — reusing ($0)")
        return 0.0
    if exists:
        athena.subprocess.run(["aws", "s3", "rm", WORK_PRIMARY_S3, "--recursive", "--only-show-errors"])
    athena.run_query("DROP TABLE IF EXISTS vaticinus.work_primary_concept", log=log)
    res = athena.run_query(
        f"CREATE TABLE vaticinus.work_primary_concept WITH (format='PARQUET',"
        f" external_location='{WORK_PRIMARY_S3}') AS "
        "SELECT work_id, concept_id, concept_name FROM ("
        "  SELECT work_id, concept_id, concept_name,"
        "         row_number() OVER (PARTITION BY work_id ORDER BY score DESC) AS rn"
        "  FROM work_concepts) WHERE rn = 1", log=log)
    return res["gb"]


def build_concept_flow_graph(conn: sqlite3.Connection, *, citing_from: int = 2018, min_n: int = 500,
                             min_share: float = 0.03, top_per_src: int = 15, force_ctas: bool = False,
                             log=print) -> dict:
    """Build the directed concept→concept citation-dependency graph into graph_nodes/edges.

    edge A->B (rel='draws_on'): papers whose PRIMARY concept is A cite papers whose primary concept is
    B; weight = B's share of A's cross-concept outbound citations. Sparse (share>=min_share,
    top_per_src kept). The flow is aggregated PER citing-year (so no single join times out) and merged
    in Python. The works CTAS is the only fresh full scan; everything else is cheap. Cost-gate logged."""
    gb = _ensure_work_concepts(force=force_ctas, log=log)
    if gb:
        _log_cost(conn, "athena:work_concepts_ctas", "athena", gb)
    gp = _ensure_work_primary(force=force_ctas, log=log)
    if gp:
        _log_cost(conn, "athena:work_primary_ctas", "athena", gp)
    gb += gp

    # aggregate the concept flow one citing-year at a time (each query joins a single partition)
    out_total: dict[str, int] = {}
    pair: dict[tuple[str, str], int] = {}
    name: dict[str, str] = {}
    per_year_min = max(50, min_n // 8)
    for yr in range(citing_from, MAX_CITING_YEAR + 1):
        log(f"  [athena] concept→concept flow citing_year={yr} (n>={per_year_min}) ...")
        res = athena.run_query(
            "SELECT a.concept_id, max(a.concept_name), b.concept_id, max(b.concept_name), count(*) AS n "
            "FROM citation_edges ce "
            "JOIN work_primary_concept a ON ce.citing = a.work_id "
            "JOIN work_primary_concept b ON ce.cited = b.work_id "
            f"WHERE ce.citing_year = {yr} AND a.concept_id <> b.concept_id "
            f"GROUP BY a.concept_id, b.concept_id HAVING count(*) >= {per_year_min}", log=log)
        _log_cost(conn, f"athena:concept_flow_{yr}", "athena", res["gb"])
        gb += res["gb"]
        for a_id, a_name, b_id, b_name, n in _fetch_all_rows(res["id"]):
            n = int(n)
            a_id, b_id = a_id.split("/")[-1], b_id.split("/")[-1]   # C-id short form
            name.setdefault(a_id, a_name); name.setdefault(b_id, b_name)
            pair[(a_id, b_id)] = pair.get((a_id, b_id), 0) + n
            out_total[a_id] = out_total.get(a_id, 0) + n

    # drop pairs below the full-window threshold (per-year floor was looser)
    pair = {k: v for k, v in pair.items() if v >= min_n}
    if not pair:
        log("  ! no concept pairs cleared the threshold — graph not built")
        return {"nodes": 0, "edges": 0, "gb": gb}

    # sparsify: per source, keep the top-K strongest cross-concept edges above the share floor
    kept: list[tuple[str, str, int, float]] = []
    by_src: dict[str, list[tuple[str, int]]] = {}
    for (a, b), n in pair.items():
        by_src.setdefault(a, []).append((b, n))
    for a, bs in by_src.items():
        denom = out_total.get(a, 0) or 1
        ranked = sorted(((b, n, n / denom) for b, n in bs), key=lambda x: x[1], reverse=True)
        for b, n, share in ranked[:top_per_src]:
            if share >= min_share:
                kept.append((a, b, n, share))

    src = Source(
        url="s3://openalex (citation_edges ⋈ work_concepts ⋈ work_concepts)",
        title="OpenAlex citation graph — directed concept-to-concept flow",
        pillar_id=DEP_PILLAR, kind=SourceKind.primary, trust_score=82,
        trust_rationale=(
            "Derived from the frozen OpenAlex snapshot: each work's level-1–3 concepts (score>=0.3) "
            f"joined to the paper→paper citation graph (citing_year>={citing_from}) on both ends. The "
            "directed concept flow is a measured citation count, not an estimate; sparsified to the "
            "strongest cross-concept dependencies per source concept."))
    src_id = _upsert_source(conn, src)

    nodes_needed = {a for a, _, _, _ in kept} | {b for _, b, _, _ in kept}
    node_ids: dict[str, str] = {}
    for cid in nodes_needed:
        node = GraphNode(chain=CONCEPT_CHAIN, name=name.get(cid, cid), kind="concept", domain=None,
                         source_id=src_id, note=f"OpenAlex concept {cid} — node in the concept "
                         "knowledge-dependency graph (links to entities via alias oa:%s)." % cid)
        node_ids[cid] = _upsert_node(conn, node)

    n_edges = 0
    for a, b, n, share in kept:
        edge = GraphEdge(
            chain=CONCEPT_CHAIN, src=node_ids[a], dst=node_ids[b], rel="draws_on",
            weight=round(share, 4), weight_sd=0.0, source_id=src_id,
            note=(f"{name.get(a, a)} cites {name.get(b, b)}: {n:,} edges = {share:.1%} of "
                  f"{name.get(a, a)}'s cross-concept outbound citations (citing_year>={citing_from})."))
        _upsert_edge(conn, edge)
        n_edges += 1

    conn.execute("UPDATE pillars SET status='in_progress' WHERE id=? AND status='untapped'", (DEP_PILLAR,))
    conn.commit()
    log(f"  concept_flow graph: {len(node_ids):,} concept nodes, {n_edges:,} directed edges "
        f"(share>={min_share:.0%}, top{top_per_src}/src). Total scanned {gb:.1f} GB "
        f"(~${gb/1000*5:.2f}).")
    return {"nodes": len(node_ids), "edges": n_edges, "gb": gb}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--concepts", action="store_true", help="FREE: load concept index → entities")
    ap.add_argument("--field-graph", action="store_true", help="~$0.16 Athena: build field-flow graph")
    ap.add_argument("--concept-graph", action="store_true",
                    help="~$3.2 Athena: CTAS work→concept + build concept-flow graph")
    ap.add_argument("--force-ctas", action="store_true", help="re-run the work_concepts CTAS (re-scan)")
    ap.add_argument("--max-level", type=int, default=3, help="concept index: max OpenAlex level")
    ap.add_argument("--min-works", type=int, default=1000, help="concept index: min works_count")
    ap.add_argument("--citing-from", type=int, default=None,
                    help="override min citing year (field default 2015, concept default 2018)")
    a = ap.parse_args()
    if not (a.concepts or a.field_graph or a.concept_graph):
        ap.error("pick at least one of --concepts / --field-graph / --concept-graph")

    conn = db.connect()
    if a.concepts:
        load_concept_index(conn, max_level=a.max_level, min_works=a.min_works)
    if a.field_graph:
        build_field_flow_graph(conn, citing_from=a.citing_from or CITING_FROM_YEAR)
    if a.concept_graph:
        build_concept_flow_graph(conn, citing_from=a.citing_from or 2018, force_ctas=a.force_ctas)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
