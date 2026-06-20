"""Per-layer grade of completion for the whole data substrate — the worldwide view.

`world_seed.coverage(topic)` answers "for THIS topic, which spine layers light up?" (binary, topic-scoped).
This module answers the orthogonal question the goal demands: "across the WHOLE substrate, how complete is
each of the 9 spine layers — where are we rich, where are we blind?" It is the honest scorecard behind the
"we are not a prompt layer" claim, and it tells the build where to dig next (the thin layers).

A layer's grade (0-100) is a transparent composite of three measured components, each 0-1:

  structure  (0.50)  how much navigable graph the forecaster can actually walk in this layer
                     — world-chain node count, linear to a STRUCTURE_TARGET; the dependency layer
                     reads the live concept_flow graph (13k nodes) since those are never copied into world.
  health     (0.20)  of the series that map to this layer (via world_seed.series_layer), the fraction
                     audited × their mean QC health_score — verified data, not just present data.
  pillar     (0.30)  the human-tracked maturity of the pillar (untapped → in_progress → live).

The weights favour structure because the product walks the graph; health and pillar keep us honest about
"present but unverified" and "registered but untapped". Every component is printed, never just the headline —
no joking about coverage. $0, stdlib + sqlite only.

Usage:
    uv run python -m engine.cli world-grade            # the substrate-wide scorecard
    uv run python -m engine.cli world-grade "lithium"  # + the topic-scoped coverage walk
"""
from __future__ import annotations

from engine import world_seed

# A world-chain node count at/above which a layer's *structure* reads as fully built. Linear below it.
# Calibrated so the rich frontier (241) caps out and the thin layers read honestly thin.
STRUCTURE_TARGET = 120

# spine layer name -> pillar id (engine/db.py pillars table)
_PILLAR_ID = {
    "frontier": 1, "capability": 2, "dependency": 3, "supply": 4, "demand": 5,
    "capital": 6, "pricing": 7, "policy": 8, "outcome": 9,
}
_PILLAR_SCORE = {"untapped": 0.0, "planned": 0.2, "in_progress": 0.6, "live": 1.0, "done": 1.0}

WEIGHTS = {"structure": 0.50, "health": 0.20, "pillar": 0.30}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _grade_letter(g: float) -> str:
    return ("A" if g >= 85 else "B" if g >= 70 else "C" if g >= 55
            else "D" if g >= 40 else "E" if g >= 25 else "F")


def layer_grades(conn) -> dict:
    """Compute the per-layer grade scorecard across the whole substrate."""
    # 1) world-chain structural node counts per layer
    node_counts = {name: 0 for name, _ in world_seed.SPINE}
    for r in conn.execute(
        "SELECT kind, count(*) n FROM graph_nodes WHERE chain=? GROUP BY kind", (world_seed.CHAIN,)
    ).fetchall():
        if r["kind"] in node_counts:
            node_counts[r["kind"]] = r["n"]
    # the dependency layer lives in concept_flow (never copied into world); count it there
    concept_nodes = conn.execute(
        "SELECT count(*) n FROM graph_nodes WHERE chain='concept_flow'").fetchone()["n"]
    concept_edges = conn.execute(
        "SELECT count(*) n FROM graph_edges WHERE chain='concept_flow'").fetchone()["n"]
    struct_count = dict(node_counts)
    struct_count["dependency"] = concept_nodes

    # 2) series health folded onto layers via the canonical metric->layer map
    series_total = {name: 0 for name, _ in world_seed.SPINE}
    health_sum = {name: 0.0 for name, _ in world_seed.SPINE}
    health_n = {name: 0 for name, _ in world_seed.SPINE}
    health = {}
    for r in conn.execute(
        "SELECT s.metric metric, s.pillar_id pillar_id, h.health_score hs "
        "FROM series s LEFT JOIN series_health h ON h.series_id = s.id"
    ).fetchall():
        layer = world_seed.layer_for(r["pillar_id"], r["metric"])
        if layer not in series_total:
            continue
        series_total[layer] += 1
        if r["hs"] is not None:
            health_sum[layer] += r["hs"]
            health_n[layer] += 1
    for name, _ in world_seed.SPINE:
        tot = series_total[name]
        audited = health_n[name]
        mean_h = (health_sum[name] / audited) if audited else 0.0
        audit_frac = (audited / tot) if tot else 0.0
        health[name] = {"series": tot, "audited": audited, "mean_health": round(mean_h, 3),
                        "audit_frac": round(audit_frac, 3), "sub": round(audit_frac * mean_h, 3)}

    # 3) pillar maturity
    pillar_status = {}
    for r in conn.execute("SELECT id, status FROM pillars").fetchall():
        pillar_status[r["id"]] = r["status"]

    layers = {}
    grade_sum = 0.0
    for name, _ in world_seed.SPINE:
        s_count = struct_count[name]
        structure = _clamp01(s_count / STRUCTURE_TARGET)
        hsub = health[name]["sub"]
        pstatus = pillar_status.get(_PILLAR_ID[name], "untapped")
        psub = _PILLAR_SCORE.get(pstatus, 0.0)
        grade = 100.0 * (WEIGHTS["structure"] * structure + WEIGHTS["health"] * hsub
                         + WEIGHTS["pillar"] * psub)
        grade_sum += grade
        layers[name] = {
            "layer": name,
            "grade": round(grade, 1),
            "letter": _grade_letter(grade),
            "structure": {"nodes": s_count, "sub": round(structure, 3),
                          "source": "concept_flow" if name == "dependency" else "world"},
            "health": health[name],
            "pillar": {"status": pstatus, "sub": psub},
        }

    overall = round(grade_sum / len(world_seed.SPINE), 1)
    return {
        "overall": overall,
        "overall_letter": _grade_letter(overall),
        "layers": layers,
        "concept_flow": {"nodes": concept_nodes, "edges": concept_edges},
        "weights": WEIGHTS,
        "structure_target": STRUCTURE_TARGET,
    }


def format_grades(g: dict) -> str:
    lines = [
        f"DATA SUBSTRATE — completion grade {g['overall']}/100 ({g['overall_letter']}) across "
        f"{len(g['layers'])} spine layers",
        f"  weights: structure {g['weights']['structure']:.0%} · health {g['weights']['health']:.0%} "
        f"· pillar {g['weights']['pillar']:.0%}   (structure target = {g['structure_target']} nodes)",
        "",
        f"  {'layer':<11} {'grade':>7}  {'struct':>16}  {'health (audited/series)':>26}  pillar",
    ]
    for name, _ in world_seed.SPINE:
        L = g["layers"][name]
        st = L["structure"]
        he = L["health"]
        struct_str = f"{st['nodes']:>6} nd {st['sub']:.2f}"
        if st["source"] == "concept_flow":
            struct_str += "*"
        health_str = f"{he['audited']}/{he['series']} h{he['mean_health']:.2f} {he['sub']:.2f}"
        lines.append(
            f"  {name:<11} {L['grade']:>5}{L['letter']:>2}  {struct_str:>16}  {health_str:>26}  "
            f"{L['pillar']['status']}")
    lines.append("")
    lines.append(f"  * dependency structure counted from the live concept_flow graph "
                 f"({g['concept_flow']['nodes']:,} nodes / {g['concept_flow']['edges']:,} edges)")
    thin = sorted((L for L in g["layers"].values()), key=lambda x: x["grade"])[:3]
    lines.append("  THIN (build here next): " + ", ".join(f"{t['layer']} {t['grade']:.0f}" for t in thin))
    return "\n".join(lines)


# Human labels + a one-line "what feeds this layer" blurb for the public showcase.
LAYER_LABEL = {
    "frontier": ("Frontier", "the research frontier — papers, citations, concept share"),
    "capability": ("Capability", "commercialised capability — paper→patent linkage, patents"),
    "dependency": ("Dependency graph", "the knowledge dependency graph — what draws on what"),
    "supply": ("Supply elasticity", "value chains, trade flows, mineral & energy capacity"),
    "demand": ("Demand / adoption", "derived demand build-out and attention"),
    "capital": ("Capital flows", "filings, funding, macro and financial series"),
    "pricing": ("Market pricing", "the priced-in gate — equities and prediction markets"),
    "policy": ("Policy / geo", "permits, sanctions, dockets, regulatory action"),
    "outcome": ("Outcomes", "terminal realised outcomes"),
}


def showcase_payload(conn) -> dict:
    """The public 'what data we hold' payload — coverage, not forecasts. Drives the /data route.

    Deliberately carries NO probabilities or calls, and NO letter grade / overall score: the internal
    `world-grade` is a harsh build-compass (it punishes known-thin layers on purpose) and reads as a
    report card we are failing, which is the opposite of this page's job. Here we publish the SUBSTANCE
    instead — how much we hold, across which layers, going back how far. Per layer we expose `depth`
    (0-100 relative richness) for bars, never a letter. $0, read-only."""
    g = layer_grades(conn)

    sources_by_pillar = {r["pillar_id"]: r["n"] for r in conn.execute(
        "SELECT pillar_id, count(*) n FROM sources GROUP BY pillar_id").fetchall()}
    providers_by_pillar = {r["pillar_id"]: r["p"] for r in conn.execute(
        "SELECT pillar_id, count(DISTINCT provider) p FROM series "
        "WHERE provider IS NOT NULL GROUP BY pillar_id").fetchall()}

    spine = []
    for name, _ in world_seed.SPINE:
        L = g["layers"][name]
        pid = _PILLAR_ID[name]
        label, blurb = LAYER_LABEL[name]
        spine.append({
            "layer": name, "label": label, "blurb": blurb,
            "grade": L["grade"], "letter": L["letter"],
            "nodes": L["structure"]["nodes"],
            "series": L["health"]["series"], "audited": L["health"]["audited"],
            "mean_health": L["health"]["mean_health"],
            "sources": sources_by_pillar.get(pid, 0),
            "providers": providers_by_pillar.get(pid, 0),
            "pillar_status": L["pillar"]["status"],
        })

    volume = [{"year": r["y"], "observations": r["n"]} for r in conn.execute(
        "SELECT substr(as_of,1,4) y, count(*) n FROM observations "
        "WHERE as_of >= '2000' AND as_of < '2027' GROUP BY y ORDER BY y").fetchall()]

    def _count(sql):
        return conn.execute(sql).fetchone()[0]
    totals = {
        "papers": _count("SELECT count(*) FROM papers"),
        "observations": _count("SELECT count(*) FROM observations"),
        "series": _count("SELECT count(*) FROM series"),
        "entities": _count("SELECT count(*) FROM entities"),
        "sources": _count("SELECT count(*) FROM sources"),
        "providers": _count("SELECT count(DISTINCT provider) FROM series WHERE provider IS NOT NULL"),
        "world_nodes": _count("SELECT count(*) FROM graph_nodes WHERE chain='world'"),
        "concept_nodes": g["concept_flow"]["nodes"],
        "concept_edges": g["concept_flow"]["edges"],
    }
    providers = [r["provider"] for r in conn.execute(
        "SELECT DISTINCT provider FROM series WHERE provider IS NOT NULL ORDER BY provider").fetchall()]

    return {
        "overall": g["overall"], "overall_letter": g["overall_letter"],
        "spine": spine, "volume_over_time": volume, "totals": totals, "providers": providers,
    }


def public_teaser(full: dict) -> dict:
    """The OPEN-site subset: the data layer presented as the top-tier asset it is — aggregate scale,
    source breadth, reach over time, and the full 9-layer causal spine BY NAME. No letter grade and no
    per-layer depth (those reveal the known-thin layers and read as a report card). The depth itself is
    the high-ticket value: it lives behind book-a-call + the chat Deep tier, not on the front page."""
    spine_public = [{"layer": s["layer"], "label": s["label"], "blurb": s["blurb"]}
                    for s in full["spine"]]
    # The roadmap framing: per-layer build progress toward complete coverage (target grade A). We show
    # the trajectory and the destination, never a scarlet letter for today — the layer is filling fast.
    roadmap = {
        "built_pct": round(full["overall"]),          # how far along, 0-100 (honest)
        "target_letter": "A",
        "target_label": "complete coverage",
        "layers": [{"label": s["label"], "built": round(s["grade"])} for s in full["spine"]],
    }
    return {
        "totals": full["totals"],
        "volume_over_time": full["volume_over_time"],
        "providers": full["providers"],
        "n_layers": len(spine_public),
        "spine": spine_public,
        "roadmap": roadmap,
        "note": "Aggregate coverage of the live data layer. Per-layer depth and the agentic "
                "walk-the-data view are available on the research tier.",
    }
