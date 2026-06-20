"""Topic → structural evidence pack: the seam that grounds a forecast in the data layer.

This is the connection between the data layer (data/foresight.db series/observations + the S3
patent extracts) and the AI backend. Given a free-text topic or question, it resolves the relevant
LEADING signals we mint — sub-topic SHARE of world literature, cross-field DIFFUSION, citation
VELOCITY, cross-field BRIDGE, patent concentration (HHI), trade dependency — and returns a compact,
LLM-readable evidence block. The model reads it BEFORE proposing a Fermi decomposition, so the
probability is anchored to measured structure, not parametric memory.

Honest by construction: every figure is a real dated observation from the DB (or a logged patent
extract). Nothing is fabricated; a topic with no matching signal returns an empty pack and says so.
$0, stdlib + sqlite only. Reuses the chat_bridge shell-out seam (engine.chat_bridge signals).

Usage:
    uv run python -m engine.signals "solid state battery"
    echo '{"topic":"deep learning"}' | uv run python -m engine.chat_bridge signals
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from engine import db

PATENTS_JSONL = Path(__file__).resolve().parents[1] / "data" / "feeds" / "google_patents.jsonl"
STOP = {"the", "and", "for", "will", "with", "from", "into", "year", "years", "than", "what",
        "when", "does", "are", "is", "of", "in", "to", "a", "by", "reach", "be", "how", "many",
        "an", "or", "at", "on", "as", "it", "we", "do", "go", "vs", "per", "this", "that", "exceed",
        "share", "market", "units", "ship", "hit", "above", "below", "over", "under", "2030", "2025"}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _tokens(s: str) -> list[str]:
    """Content tokens (>=2 chars, non-stopword). Whole-token matching avoids substring noise."""
    return [t for t in re.split(r"[^a-z0-9]+", s.lower()) if len(t) >= 2 and t not in STOP]


def _tokset(*parts: str) -> set[str]:
    out: set[str] = set()
    for p in parts:
        out |= {t for t in re.split(r"[^a-z0-9]+", (p or "").lower()) if t}
    return out


def _fmt(v: float) -> float:
    """Adaptive precision: keep small fractions legible instead of rounding to 0.0."""
    a = abs(v)
    if a == 0:
        return 0.0
    if a < 0.01:
        return float(f"{v:.2g}")
    if a < 1:
        return round(v, 4)
    return round(v, 2)


def _trend(obs: list[tuple[str, float]]) -> dict:
    """Latest value, CAGR over the window, and acceleration sign from slope-of-slope."""
    obs = sorted(obs, key=lambda r: r[0])
    if not obs:
        return {}
    (d0, v0), (d1, v1) = obs[0], obs[-1]
    yrs = max(1, int(d1[:4]) - int(d0[:4]))
    cagr = ((v1 / v0) ** (1 / yrs) - 1) if v0 > 0 and v1 > 0 else None
    accel = None
    if len(obs) >= 5:
        mid = len(obs) // 2
        early = (obs[mid][1] - obs[0][1]) / max(1, mid)
        late = (obs[-1][1] - obs[mid][1]) / max(1, len(obs) - 1 - mid)
        accel = "accelerating" if late > early * 1.05 else (
            "decelerating" if late < early * 0.95 else "steady")
    return {"first": (d0[:4], _fmt(v0)), "latest": (d1[:4], _fmt(v1)),
            "cagr": round(cagr, 3) if cagr is not None else None, "trend": accel, "n": len(obs)}


# the channels we mint, in the order they best inform a forecast (leading first)
_CHANNEL_LABEL = {
    "research_share_ppm": "sub-topic share of world literature (ppm)",
    "research_field_breadth": "cross-field diffusion (# fields present)",
    "research_works": "research output (works/year)",
    "research_field_citations": "citation velocity — field citations received/year",
    "research_bridge_fraction": "cross-field bridge (outgoing cross-field citation fraction)",
    "works_published": "publication volume (Crossref works/year)",
    "preprints_posted": "preprint posting rate",
    "trade_value": "trade flow / supply dependency",
    "commodity_price": "commodity price (leading)",
    # L2 capability / cost learning curves (the second-derivative signal)
    "compute_flops_per_usd": "compute capability — FLOP/s per USD (frontier)",
    "compute_flops_per_watt": "compute capability — FLOP/s per watt (frontier)",
    "frontier_training_cost_usd": "frontier model training cost (USD)",
    "transistors_per_microprocessor": "transistor density (Moore's-law curve)",
    "supercomputer_flops": "fastest-supercomputer FLOP/s",
    # L5 demand / adoption diffusion
    "github_new_repos": "developer adoption — new GitHub repos/year",
    "hf_new_models": "model adoption — new HuggingFace models/year",
    # L4 supply elasticity
    "capacity_utilization_total": "capacity utilization — total industry (tightness)",
    "manufacturers_unfilled_orders": "order backlog (lead-time tightness)",
    # L6 capital flows
    "corporate_capex": "aggregate corporate capex",
    "corporate_rnd_expense": "aggregate corporate R&D spend",
    "ma_spend": "aggregate M&A spend",
}


# Metric-family rank: lower = surfaced first. Prefix rules cover the per-curve/per-sector
# metric families minted by the capability/adoption/supply/capital feeds without enumerating each.
_RANK_PREFIXES = (
    # L2 capability curves are a top leading channel (cost/perf slope leads commercialization)
    (("cost_per_", "lcoe_", "compute_flops_", "frontier_", "transistors_", "supercomputer_"), 1),
    # L5 adoption diffusion
    (("ev_", "renewable_", "solar_energy", "installed_solar", "internet_", "mobile_",
      "github_new_repos", "hf_new_models", "adoption_"), 3),
    # L4 supply elasticity (tightness — coincident but decision-relevant)
    (("capacity_utilization_", "manufacturers_", "total_business_"), 6),
    # L6 capital flows
    (("corporate_", "ma_spend", "equity_issuance", "debt_issuance", "installed_ppe"), 7),
)


def _metric_rank(metric: str) -> int:
    """Surfacing rank for a series metric: explicit map first, then metric-family prefixes."""
    if metric in _CHANNEL_RANK:
        return _CHANNEL_RANK[metric]
    for prefixes, rank in _RANK_PREFIXES:
        if metric.startswith(prefixes):
            return rank
    return 5


# leading channels first (the prediction-valuable ones), then volume, then market/lag
_CHANNEL_RANK = {
    "research_share_ppm": 0, "research_field_breadth": 1, "research_field_citations": 2,
    "research_bridge_fraction": 3, "talent_inflow": 4, "citations_received_per_year": 4,
    "topic_share": 1, "field_breadth": 1, "field_diffusion": 1,
    "research_works": 5, "works_published": 5, "works_per_year": 5, "preprints_posted": 5,
    "frontier_training_compute": 0, "commodity_price": 6, "market_implied_prob": 6,
    "trade_value": 7, "patents_per_priority_year": 7, "sec_filing_mentions": 8,
    "wikipedia_pageviews": 9, "federal_register_docs": 9,
}
_MAX_SERIES = 12


def _match_series(conn, topic: str) -> list[dict]:
    slug = _slug(topic)
    qtoks = set(_tokens(topic))
    if not qtoks:
        return []
    rows = conn.execute(
        "SELECT id, provider, external_id, label, metric, unit, "
        "COALESCE(last_fired,0) fired, last_surprise_sigma sig, COALESCE(last_fdr_survive,0) fdr "
        "FROM series").fetchall()
    scored = []
    for r in rows:
        ext = (r["external_id"] or "").lower()
        lab = (r["label"] or "").lower()
        stoks = _tokset(ext, lab)
        overlap = qtoks & stoks                       # WHOLE-token match — no substring noise
        if not overlap:
            continue
        score = 2 * len(overlap)
        # contiguous phrase bonus, but only for slugs long enough to be specific (avoid "ai" noise)
        if len(slug) >= 5 and (slug in ext or slug.replace("_", " ") in lab):
            score += 5
        scored.append((score, r))
    if not scored:
        return []
    # keep any genuine whole-token overlap (relevant neighbours like lithium-ion for solid-state are
    # worth seeing as comparators); the cap + leading-channel ordering surface the strongest first.
    scored.sort(key=lambda x: -x[0])
    kept = scored[:_MAX_SERIES]
    out = []
    for score, r in kept:
        obs = conn.execute(
            "SELECT as_of, value FROM observations WHERE series_id=? ORDER BY as_of", (r["id"],)
        ).fetchall()
        t = _trend([(o["as_of"], o["value"]) for o in obs])
        if not t:
            continue
        out.append({
            "label": r["label"], "metric": r["metric"],
            "channel": _CHANNEL_LABEL.get(r["metric"], r["metric"]),
            "provider": r["provider"], "unit": r["unit"], "score": score,
            "fired": r["fired"], "surprise_sigma": r["sig"], "fdr_survive": r["fdr"],
            **t,
        })
    # order leading-channels first, then by match score
    out.sort(key=lambda s: (_metric_rank(s["metric"]), -s["score"]))
    return out


def _match_patents(topic: str) -> list[dict]:
    if not PATENTS_JSONL.exists():
        return []
    toks = set(_tokens(topic))
    rows = [json.loads(l) for l in PATENTS_JSONL.open() if l.strip()]
    # group by label
    labels: dict[str, dict] = {}
    for r in rows:
        labels.setdefault(r["label"], {"conc": [], "trend": []})
        labels[r["label"]]["conc" if r["kind"] == "assignee_concentration" else "trend"].append(r)
    out = []
    for label, g in labels.items():
        ltoks = set(_tokens(label.replace("-", " ")))
        if not (toks & ltoks):
            continue
        conc = g["conc"]
        total = int(conc[0]["total_grants"]) if conc else 0
        hhi = round(sum((100.0 * int(r["n"]) / total) ** 2 for r in conc), 1) if total else 0
        top5 = round(sum(int(r["n"]) for r in sorted(conc, key=lambda r: -int(r["n"]))[:5]) / total, 3) if total else 0
        tr = sorted(g["trend"], key=lambda r: int(r["year"]))
        arrow = None
        if len(tr) >= 4:
            h = len(tr) // 2
            arrow = "accelerating" if sum(int(r["n"]) for r in tr[h:]) > sum(int(r["n"]) for r in tr[:h]) else "flat/declining"
        out.append({"label": label, "total_grants": total, "hhi_top": hhi,
                    "top5_share": top5, "grant_trend": arrow,
                    "top_assignees": [r["assignee"] for r in sorted(conc, key=lambda r: -int(r["n"]))[:5]]})
    return out


# ── dependency graph (concept_flow) — reason ALONG measured edges, don't assert links ─────────
# The concept_flow chain is the directed knowledge-dependency graph derived from the OpenAlex
# citation graph (13k concept nodes / 52k draws_on edges). edge A->B weight = the share of A's
# cross-concept citations that land on B = "how much A's knowledge base is built on B". Surfacing it
# here turns the /needle step-4 decompose ("walk DOWN the dependency graph to the inelastic input")
# and the /gate blast-radius read from free-association into a measured trace. HONEST CAVEAT carried
# into the render: the very top-weight outbound edge is often a hypernym (Deep learning -> AI), so
# the needle-useful signal is the MID-weight substantive edges + the inbound side (who leans on A).

_DEP_CHAIN = "concept_flow"
CONCEPT_PATENTS = Path(__file__).resolve().parents[1] / "data" / "feeds" / "openalex_concept_patents.jsonl"


def _concept_patents() -> dict:
    """name.lower() -> per-concept paper->patent reliance (worldwide citations, Reliance-on-Science).

    Built by engine/feeds/relianceonscience.py: how many distinct patents cite this concept's research =
    a measured commercialization-intensity overlay on the same concept nodes the dependency graph uses.
    """
    out: dict[str, dict] = {}
    if not CONCEPT_PATENTS.exists():
        return out
    for line in CONCEPT_PATENTS.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("name"):
            out[r["name"].lower()] = r
    return out


def _emergence_map(conn) -> dict:
    """name.lower() -> the concept_emergence acceleration verdict (WHERE the concept is moving NOW).

    The dependency graph says where a constraint sits; this says where it is accelerating. Loaded once
    per pack. Returns {} if the table isn't built yet (degrade gracefully, never crash the pack)."""
    try:
        rows = conn.execute(
            "SELECT concept_name, surprise_sigma, sustained_sigma, fired, sustained, dissolving, "
            "share_ppm_now, last_works, last_year, spark FROM concept_emergence").fetchall()
    except sqlite3.OperationalError:
        return {}
    return {r["concept_name"].lower(): dict(r) for r in rows}


def _emerge_tag(em: dict | None) -> str:
    """Compact inline tag for a neighbor concept: ↑accelerating / ↓rent-leaving / flat."""
    if not em:
        return ""
    if em["fired"] and em["sustained"]:
        return f" ↑{em['sustained_sigma']:.0f}σ"
    if em["dissolving"]:
        return " ↓diss"
    return ""


def _edge_shift_map(conn) -> dict:
    """(src_name.lower(), dst_name.lower()) -> the per-EDGE dependency-shift verdict (where the
    constraint is MIGRATING). The node-emergence map says a concept is accelerating; this says a
    specific A->B reliance is tightening (↗) or loosening (↘). {} if the table isn't built yet."""
    try:
        rows = conn.execute(
            "SELECT src_name, dst_name, sustained_sigma, fired, sustained, dissolving "
            "FROM concept_edge_shift").fetchall()
    except sqlite3.OperationalError:
        return {}
    return {(r["src_name"].lower(), r["dst_name"].lower()): dict(r) for r in rows}


def _shift_tag(sh: dict | None) -> str:
    """Compact inline tag for one dependency edge: ↗tightening / ↘loosening / ''."""
    if not sh:
        return ""
    if sh["fired"] and sh["sustained"]:
        return f" ↗{sh['sustained_sigma']:.0f}σ"   # the constraint is migrating onto this input
    if sh["dissolving"]:
        return " ↘loosening"
    return ""


def _match_concept_nodes(conn, topic: str, *, limit: int = 3) -> list[dict]:
    """Resolve a free-text topic to concept_flow node(s) by whole-token overlap on the concept name."""
    qtoks = set(_tokens(topic))
    if not qtoks:
        return []
    rows = conn.execute(
        "SELECT id, name FROM graph_nodes WHERE chain=?", (_DEP_CHAIN,)).fetchall()
    scored = []
    for r in rows:
        ntoks = {t for t in _tokset(r["name"]) if len(t) >= 2}
        overlap = qtoks & ntoks
        if not overlap:
            continue
        # multi-word topics must be FULLY covered by the concept name (drops "Associative learning"
        # for "deep learning"); single-token topics fall back to best overlap.
        if len(qtoks) >= 2 and overlap != qtoks:
            continue
        exact = topic.strip().lower() == (r["name"] or "").lower()
        score = (100 if exact else 0) + 4 * len(overlap) - 0.1 * len(ntoks)
        scored.append((score, r))
    scored.sort(key=lambda x: -x[0])
    return [{"id": r["id"], "name": r["name"]} for _, r in scored[:limit]]


def dependency_neighbors(conn, topic: str, *, top: int = 6, min_weight: float = 0.03) -> list[dict]:
    """For each matched concept, the measured draws_on edges both ways.

    outbound (A draws_on B) = what A's knowledge base leans on -> candidate binding inputs.
    inbound  (B draws_on A) = who leans on A -> A's blast radius if it is constrained / where rent lands.
    """
    out = []
    patents = _concept_patents()
    emap = _emergence_map(conn)
    shmap = _edge_shift_map(conn)
    for node in _match_concept_nodes(conn, topic):
        outbound = conn.execute(
            "SELECT n.name dst, e.weight w FROM graph_edges e JOIN graph_nodes n ON e.dst=n.id "
            "WHERE e.chain=? AND e.src=? AND e.weight>=? ORDER BY e.weight DESC LIMIT ?",
            (_DEP_CHAIN, node["id"], min_weight, top)).fetchall()
        inbound = conn.execute(
            "SELECT n.name src, e.weight w FROM graph_edges e JOIN graph_nodes n ON e.src=n.id "
            "WHERE e.chain=? AND e.dst=? AND e.weight>=? ORDER BY e.weight DESC LIMIT ?",
            (_DEP_CHAIN, node["id"], min_weight, top)).fetchall()
        if not (outbound or inbound):
            continue
        entry = {
            "concept": node["name"],
            "emergence": emap.get(node["name"].lower()),  # where THIS concept is moving (or None)
            # `emerge` = is the NEIGHBOR concept accelerating; `shift` = is THIS reliance edge
            # tightening/loosening (the constraint migrating along the link, not just the node moving).
            "draws_on": [{"name": r["dst"], "weight": _fmt(r["w"]),
                          "emerge": _emerge_tag(emap.get(r["dst"].lower())),
                          "shift": _shift_tag(shmap.get((node["name"].lower(), r["dst"].lower())))}
                         for r in outbound],
            "drawn_on_by": [{"name": r["src"], "weight": _fmt(r["w"]),
                             "emerge": _emerge_tag(emap.get(r["src"].lower())),
                             "shift": _shift_tag(shmap.get((r["src"].lower(), node["name"].lower())))}
                            for r in inbound],
        }
        rel = patents.get(node["name"].lower())
        if rel:
            entry["patent_reliance"] = {"n_patents": rel["n_patents"], "n_us": rel.get("n_us"),
                                        "n_nonus": rel.get("n_nonus"), "n_applicant": rel.get("n_applicant")}
        out.append(entry)

    # completeness: a concept can carry patent reliance without being a node in the sparse graph.
    # surface those too (empty edges) so any topic with measured commercialization shows it.
    seen = {e["concept"].lower() for e in out}
    qtoks = set(_tokens(topic))
    if qtoks:
        extra = []
        for name_l, rel in patents.items():
            if name_l in seen:
                continue
            ntoks = {t for t in re.split(r"[^a-z0-9]+", name_l) if len(t) >= 2}
            overlap = qtoks & ntoks
            if not overlap or (len(qtoks) >= 2 and overlap != qtoks):
                continue
            extra.append((rel["n_patents"], rel))
        for _, rel in sorted(extra, key=lambda x: -x[0])[:3]:
            out.append({"concept": rel["name"], "draws_on": [], "drawn_on_by": [],
                        "patent_reliance": {"n_patents": rel["n_patents"], "n_us": rel.get("n_us"),
                                            "n_nonus": rel.get("n_nonus"), "n_applicant": rel.get("n_applicant")}})
    return out


# the named-actor kinds worth surfacing for execution: who holds/operates/signed/owns the real thing.
# order = how directly each answers "to whom does this belong / who must act".
_ACTOR_KINDS = ("resource_contract", "permit_holder", "land_holder", "mining_plan",
                "infrastructure_project", "company", "institution", "policy", "country_region")
_ACTOR_LABEL = {
    "resource_contract": "signed resource/land contract", "permit_holder": "permit / claim holder",
    "land_holder": "land acquirer / holder", "mining_plan": "filed mining plan",
    "infrastructure_project": "infrastructure project", "company": "company",
    "institution": "institution", "policy": "policy instrument", "country_region": "jurisdiction"}


def match_entities(conn, topic: str, *, per_kind: int = 4, kinds=_ACTOR_KINDS) -> list[dict]:
    """Named real-world actors from the entity graph that match a call/needle: who holds the permit,
    operates the mine, signed the contract, acquired the land, runs the project. This is the
    'find the real thing + to whom it belongs' layer the execution step builds on.

    SQL substring prefilter (fast over 96k rows) then whole-token overlap for precision. Grouped by
    actor kind, most-direct-ownership first, capped per kind so one noisy kind can't crowd the rest.
    """
    qtoks = [t for t in set(_tokens(topic)) if len(t) >= 3]  # >=3 drops noisy 2-char substrings
    if not qtoks:
        return []
    name_likes = " OR ".join("lower(canonical_name) LIKE ?" for _ in qtoks)
    alias_likes = " OR ".join("lower(coalesce(aliases,'')) LIKE ?" for _ in qtoks)
    kind_ph = ",".join("?" for _ in kinds)
    params = list(kinds) + [f"%{t}%" for t in qtoks] + [f"%{t}%" for t in qtoks]
    rows = conn.execute(
        f"SELECT kind, canonical_name, aliases, note FROM entities "
        f"WHERE kind IN ({kind_ph}) AND canonical_name != '' AND (({name_likes}) OR ({alias_likes})) "
        f"LIMIT 6000", params).fetchall()
    qset = set(qtoks)
    scored = []
    for r in rows:
        etoks = {t for t in _tokset(r["canonical_name"], r["aliases"] or "") if len(t) >= 3 and t not in STOP}
        overlap = qset & etoks
        if not overlap:
            continue
        scored.append((len(overlap), r["kind"], r["canonical_name"], (r["note"] or "").strip()))
    scored.sort(key=lambda x: (-x[0], _ACTOR_KINDS.index(x[1]) if x[1] in _ACTOR_KINDS else 99))
    out: list[dict] = []
    seen: dict[str, int] = {}
    for score, kind, name, note in scored:
        if seen.get(kind, 0) >= per_kind:
            continue
        seen[kind] = seen.get(kind, 0) + 1
        out.append({"kind": kind, "name": name, "note": note[:140], "match": score})
    return out


def format_entities(rows: list[dict]) -> str:
    if not rows:
        return ("NAMED REAL-WORLD MATCHES: none in the entity graph for this needle. The execution "
                "step must name the real holders/operators itself via web search and say the graph is blind.")
    by_kind: dict[str, list[dict]] = {}
    for r in rows:
        by_kind.setdefault(r["kind"], []).append(r)
    lines = ["NAMED REAL-WORLD MATCHES (who holds / operates / signed / owns the real thing — from our entity graph):"]
    for kind in _ACTOR_KINDS:
        items = by_kind.get(kind)
        if not items:
            continue
        names = "; ".join(i["name"] for i in items)
        lines.append(f"  - {_ACTOR_LABEL.get(kind, kind)}: {names}")
    lines.append("These are real, dated rows from our data layer — use them to NAME the exposed/positioned "
                 "party in the execution brief, then verify each with one web search. Do not invent holders.")
    return "\n".join(lines)


def evidence_pack(topic: str) -> dict:
    conn = db.connect()
    try:
        series = _match_series(conn, topic)
        patents = _match_patents(topic)
        dependency = dependency_neighbors(conn, topic)
        actors = match_entities(conn, topic)
    finally:
        conn.close()
    return {"topic": topic, "series": series, "patents": patents, "dependency": dependency,
            "actors": actors, "found": bool(series or patents or dependency or actors)}


def format_pack(pack: dict) -> str:
    """Render the pack as a compact text block for the model's context."""
    if not pack["found"]:
        return (f"STRUCTURAL SIGNALS for '{pack['topic']}': none found in the data layer "
                f"(no matching research/patent/trade series). Forecast from first principles and say so.")
    lines = [f"STRUCTURAL SIGNALS (data layer, dated/real) for '{pack['topic']}':"]
    for s in pack["series"]:
        bits = [f"{s['channel']}: {s['first'][1]}→{s['latest'][1]} ({s['first'][0]}–{s['latest'][0]})"]
        if s.get("cagr") is not None:
            bits.append(f"CAGR {s['cagr']*100:+.0f}%/yr")
        if s.get("trend"):
            bits.append(s["trend"])
        if s.get("fired"):
            bits.append(f"detector FIRED ({s['surprise_sigma']:.1f}σ{', FDR-survived' if s['fdr_survive'] else ''})")
        lines.append(f"  - [{s['label']}] " + "; ".join(bits))
    for p in pack["patents"]:
        seg = (f"  - PATENTS [{p['label']}]: {p['total_grants']} grants, HHI {p['hhi_top']}, "
               f"top-5 share {p['top5_share']*100:.0f}%, {p['grant_trend'] or 'n/a'}; "
               f"leaders: {', '.join(p['top_assignees'][:3])}")
        lines.append(seg)
    for d in pack.get("dependency", []):
        has_edges = bool(d["draws_on"] or d["drawn_on_by"])
        em = d.get("emergence")
        em_str = ""
        if em and em["fired"] and em["sustained"]:
            em_str = (f"  [MOVING: share-acceleration FIRED {em['sustained_sigma']:.0f}σ̄ "
                      f"(max {em['surprise_sigma']:.0f}σ), still climbing as of {em['last_year']} "
                      f"{em['spark']} — early, not yet its own trend]")
        elif em and em["dissolving"]:
            em_str = "  [RENT LEAVING: share retreating below trend — a kill/short signal]"
        elif em:
            em_str = "  [flat: no share-acceleration — priced or dormant]"
        lines.append(f"  - DEPENDENCY GRAPH [{d['concept']}]{em_str} (measured citation flow):")
        if has_edges:
            on = ", ".join(f"{e['name']} ({e['weight']:.0%}){e.get('emerge','')}{e.get('shift','')}"
                           for e in d["draws_on"]) or "—"
            by = ", ".join(f"{e['name']} ({e['weight']:.0%}){e.get('emerge','')}{e.get('shift','')}"
                           for e in d["drawn_on_by"]) or "—"
            lines.append(f"      draws_on (its knowledge base leans on -> candidate binding inputs): {on}")
            lines.append(f"      drawn_on_by (who leans on it -> blast radius if constrained): {by}")
            if any(e.get("shift") for e in d["draws_on"] + d["drawn_on_by"]):
                lines.append("      (↗Nσ = that RELIANCE is tightening = the binding constraint is migrating "
                             "onto that input — the strongest pre-consensus tell; ↘ = link decaying)")
        pr = d.get("patent_reliance")
        if pr:
            lines.append(f"      paper->patent reliance (worldwide citations): {pr['n_patents']:,} patents "
                         f"cite this concept's research ({pr.get('n_us', 0):,} US / {pr.get('n_nonus', 0):,} "
                         f"non-US; {pr.get('n_applicant', 0):,} applicant-chosen) -> commercialization intensity")
    if any(d["draws_on"] or d["drawn_on_by"] for d in pack.get("dependency", [])):
        lines.append("  (dependency weights = share of cross-concept citations; the TOP edge is often a "
                     "hypernym — the needle is a MID-weight substantive input + a high inbound load.)")
    lines.append("Use these as the measured base for the Fermi decomposition; cite the trend you lean on. "
                 "Walk the dependency edges to name the inelastic input, do not assert links.")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    topic = " ".join(argv[1:]).strip()
    if not topic:
        print("usage: python -m engine.signals <topic>")
        return 1
    pack = evidence_pack(topic)
    print(format_pack(pack))
    print("\n--- json ---")
    print(json.dumps(pack, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
