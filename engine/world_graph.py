"""Vati World Graph compiler.

This module turns one or more Pope boards into a persistent atlas shape:
typed nodes, causal edges, scored forecast clauses, watch signals, coverage
gaps, and the agent roster needed to deepen the graph.

It is deliberately deterministic. It does not fetch data, call LLMs, or claim
that unverified names are true. The output is a world-model scaffold plus a
truth-seeking work queue.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GRAPH_VERSION = "vati_world_graph_v1"
RUN_MODE = "deterministic_world_graph_compile"

CORE_NODE_KINDS: tuple[str, ...] = (
    "domain",
    "thesis",
    "constraint",
    "forecast_clause",
    "metric",
    "kill_condition",
    "observable",
    "buyer_segment",
    "action",
    "price_channel",
    "winner",
    "loser",
    "source",
)

COVERAGE_LAYERS: tuple[dict[str, str], ...] = (
    {"id": "frontier", "label": "Frontier", "test": "What capability changed?"},
    {"id": "capability", "label": "Capability", "test": "What can now be done cheaper, faster, or at larger scale?"},
    {"id": "dependency", "label": "Dependency graph", "test": "Which upstream inputs does the shift depend on?"},
    {"id": "supply", "label": "Supply elasticity", "test": "Which input cannot scale fast enough?"},
    {"id": "demand", "label": "Demand", "test": "Who pulls on the constraint and why now?"},
    {"id": "capital", "label": "Capital", "test": "What money is already moving, and where is it still blind?"},
    {"id": "pricing", "label": "Pricing", "test": "Is the thesis already priced?"},
    {"id": "policy", "label": "Policy and geopolitics", "test": "Which rule, permit, export control, or state actor changes the graph?"},
    {"id": "outcome", "label": "Outcome", "test": "What dated metric resolves the call?"},
    {"id": "forces", "label": "Forces", "test": "What social, talent, legal, climate, or narrative force relocates scarcity?"},
)

AGENT_ROSTER: tuple[dict[str, str], ...] = (
    {
        "id": "A01",
        "role": "graph_cartographer",
        "mission": "Map entities, constraints, dependencies, and missing edges before new theses are written.",
        "inputs": "Pope board, world-state pack, prior atlas",
        "outputs": "node_edge_patch.json, merge_notes.md",
    },
    {
        "id": "A02",
        "role": "frontier_capability",
        "mission": "Identify the capability frontier and the exact technical change that creates new demand.",
        "inputs": "papers, patents, model/cost curves, technical roadmaps",
        "outputs": "frontier_state.md, capability_edges.csv",
    },
    {
        "id": "A03",
        "role": "dependency_chain",
        "mission": "Trace value chains one layer deeper than the obvious bottleneck.",
        "inputs": "supplier data, bills of materials, process steps, physical constraints",
        "outputs": "dependency_edges.csv, weakest_link_notes.md",
    },
    {
        "id": "A04",
        "role": "supply_elasticity",
        "mission": "Estimate which nodes cannot scale on the forecast horizon and why.",
        "inputs": "capacity, lead times, permits, capex, qualification cycles",
        "outputs": "elasticity_table.csv, bottleneck_candidates.md",
    },
    {
        "id": "A05",
        "role": "pricing_gate",
        "mission": "Decide whether the market, buyers, and expert consensus already price the thesis.",
        "inputs": "prices, multiples, order books, analyst notes, public narratives",
        "outputs": "pricing_gate.md, saturation_score.json",
    },
    {
        "id": "A06",
        "role": "policy_geopolitics",
        "mission": "Map laws, permits, trade controls, regulators, and state chokepoints.",
        "inputs": "official rules, dockets, sanctions, export controls, permits",
        "outputs": "policy_edges.csv, docket_queue.csv",
    },
    {
        "id": "A07",
        "role": "capital_flows",
        "mission": "Track who is funding capacity and where capital cannot remove the constraint.",
        "inputs": "filings, grants, capex plans, project finance, procurement",
        "outputs": "capital_map.csv, capital_blind_spots.md",
    },
    {
        "id": "A08",
        "role": "demand_shock",
        "mission": "Quantify the downstream demand forcing function and its timing.",
        "inputs": "adoption data, customer announcements, orders, utilization",
        "outputs": "demand_trace.csv, demand_refute.md",
    },
    {
        "id": "A09",
        "role": "forces_scan",
        "mission": "Surface social, labor, legal, climate, and narrative forces the hard data may miss.",
        "inputs": "labor markets, litigation, acceptance, demographics, climate data",
        "outputs": "forces_edges.csv, blind_spots.md",
    },
    {
        "id": "A10",
        "role": "adversarial_refute",
        "mission": "Try to kill each promoted edge, especially with already-priced and substitute arguments.",
        "inputs": "candidate edges, price checks, substitutes, counterevidence",
        "outputs": "refute_log.md, demotions.json",
    },
    {
        "id": "A11",
        "role": "scenario_architect",
        "mission": "Build compatible future states instead of isolated predictions.",
        "inputs": "promoted graph edges, refute log, uncertainty queue",
        "outputs": "scenario_tree.json, branch_probabilities.csv",
    },
    {
        "id": "A12",
        "role": "ultra_operator",
        "mission": "Turn high-value nodes into permits, projects, people, contacts, and verification tasks.",
        "inputs": "promoted constraints, buyer segments, watchlist",
        "outputs": "task_queue.csv, contacts_seed.csv, verification_ledger.md",
    },
    {
        "id": "A13",
        "role": "monitoring_scorecard",
        "mission": "Define the exact observables, cadence, kill conditions, and scoring records.",
        "inputs": "forecast clauses, metrics, source availability",
        "outputs": "watchlist.csv, scorecard.jsonl, monitor_runbook.md",
    },
)


def load_board(path: str | Path) -> dict[str, Any]:
    """Load a Pope JSON board."""

    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def build_atlas(board: dict[str, Any], source_path: str | Path = "memory") -> dict[str, Any]:
    """Build a deterministic world graph atlas from a Pope board."""

    builder = _AtlasBuilder(board, str(source_path))
    atlas = builder.build()
    atlas["snapshot_hash"] = _stable_hash(atlas)
    return atlas


def write_outputs(atlas: dict[str, Any], out_dir: str | Path) -> dict[str, str]:
    """Write the atlas pack to disk and return file paths."""

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    files = {
        "json": out / "world_graph.json",
        "markdown": out / "world_graph.md",
        "nodes": out / "nodes.csv",
        "edges": out / "edges.csv",
        "agent_roster": out / "agent_roster.csv",
        "coverage_audit": out / "coverage_audit.csv",
        "unknown_queue": out / "unknown_queue.csv",
        "watchlist": out / "watchlist.csv",
    }

    files["json"].write_text(json.dumps(atlas, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    files["markdown"].write_text(render_markdown(atlas), encoding="utf-8")
    _write_csv(files["nodes"], atlas["nodes"])
    _write_csv(files["edges"], atlas["edges"])
    _write_csv(files["agent_roster"], atlas["agent_roster"])
    _write_csv(files["coverage_audit"], atlas["coverage"]["checks"])
    _write_csv(files["unknown_queue"], atlas["unknown_queue"])
    _write_csv(files["watchlist"], atlas["watchlist"])
    return {k: str(v) for k, v in files.items()}


def render_markdown(atlas: dict[str, Any]) -> str:
    """Render a human-readable atlas memo."""

    meta = atlas["meta"]
    summary = atlas["summary"]
    coverage = atlas["coverage"]
    lines = [
        f"# {meta['title']} - World Graph Atlas",
        "",
        f"Generated: {meta['generated_at']}",
        f"Source: `{meta['source_path']}`",
        f"Run mode: `{meta['run_mode']}`",
        f"Snapshot hash: `{atlas.get('snapshot_hash', 'pending')}`",
        "",
        "## Summary",
        "",
        f"- Nodes: {summary['node_count']}",
        f"- Edges: {summary['edge_count']}",
        f"- Forecast clauses: {summary['forecast_count']}",
        f"- Unknown tasks: {summary['unknown_count']}",
        f"- Watch signals: {summary['watch_count']}",
        f"- Coverage score: {coverage['score']} / 100",
        "",
        "## Doctrine",
        "",
        "This is not a pretty graph of claims. It is a dated world-state scaffold: facts and forecast clauses are separated, missing edges are kept visible, and no named entity becomes decision-grade until source-verified.",
        "",
        "## Core Constraints",
        "",
    ]

    constraints = [n for n in atlas["nodes"] if n["kind"] == "constraint"]
    if constraints:
        for node in constraints[:20]:
            lines.append(f"- `{node['id']}`: {node['label']}")
    else:
        lines.append("- No constraint nodes found.")

    lines.extend(["", "## Forecast Clauses", ""])
    for fc in atlas["forecast_clauses"]:
        lines.extend(
            [
                f"### {fc['id']} - {fc['headline']}",
                "",
                f"- Thesis: `{fc['thesis_id']}`",
                f"- Vision P: {fc.get('vision_p', 'unknown')}",
                f"- Clause P: {fc.get('clause_p', 'unknown')}",
                f"- Resolves: {fc.get('resolves', 'unknown')}",
                f"- Metric: {fc.get('metric') or 'missing'}",
                f"- Kill: {fc.get('kill') or 'missing'}",
                "",
            ]
        )

    lines.extend(["## Coverage Audit", ""])
    for check in coverage["checks"]:
        flag = "OK" if check["status"] == "covered" else "GAP"
        lines.append(f"- {flag} `{check['id']}`: {check['label']} - {check['note']}")

    lines.extend(["", "## Unknown Queue", ""])
    for task in atlas["unknown_queue"][:40]:
        lines.append(f"- `{task['id']}` [{task['priority']}] {task['question']} ({task['owner_agent']})")

    lines.extend(["", "## Agent Roster", ""])
    for agent in atlas["agent_roster"]:
        lines.append(f"- `{agent['id']}` {agent['role']}: {agent['mission']}")

    lines.extend(
        [
            "",
            "## Operating Rules",
            "",
            "- Do not run paid or Opus multi-agent workflows without approval and a cost estimate.",
            "- Promote source-verified facts; keep unverified names in the unknown queue.",
            "- Supersede forecasts and graph claims; do not silently edit old claims.",
            "- Every promoted forecast keeps a metric, resolve date, probability, watch signal, and kill condition.",
            "",
        ]
    )
    return "\n".join(lines)


class _AtlasBuilder:
    def __init__(self, board: dict[str, Any], source_path: str) -> None:
        self.board = board
        self.source_path = source_path
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self.forecasts: list[dict[str, Any]] = []
        self.unknown_queue: list[dict[str, Any]] = []
        self.watchlist: list[dict[str, Any]] = []
        self._node_index: dict[tuple[str, str], str] = {}
        self._edge_index: set[tuple[str, str, str]] = set()

    def build(self) -> dict[str, Any]:
        board_title = _clean(self.board.get("title")) or "Untitled Pope Board"
        board_domain = _clean(self.board.get("domain")) or board_title
        board_date = _clean(self.board.get("date")) or "unknown"
        source_node = self.add_node(
            "source",
            self.source_path,
            domain=board_domain,
            fields={"source_type": "pope_board", "authored_date": board_date},
            confidence=1.0,
        )
        domain_node = self.add_node(
            "domain",
            board_domain,
            domain=board_domain,
            fields={"title": board_title, "horizon": self.board.get("horizon")},
            confidence=0.95,
        )
        self.add_edge(source_node, domain_node, "describes", "The Pope board is the source artifact for this domain map.", 1.0)

        for thesis in self.board.get("theses", []):
            self._add_thesis(thesis, domain_node, source_node)

        coverage = self._coverage()
        atlas = {
            "meta": {
                "graph_version": GRAPH_VERSION,
                "run_mode": RUN_MODE,
                "title": board_title,
                "domain": board_domain,
                "board_date": board_date,
                "horizon": self.board.get("horizon"),
                "source_path": self.source_path,
                "generated_at": _now_iso(),
            },
            "summary": {
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
                "forecast_count": len(self.forecasts),
                "unknown_count": len(self.unknown_queue),
                "watch_count": len(self.watchlist),
            },
            "nodes": self.nodes,
            "edges": self.edges,
            "forecast_clauses": self.forecasts,
            "coverage": coverage,
            "agent_roster": [dict(a) for a in AGENT_ROSTER],
            "unknown_queue": self.unknown_queue,
            "watchlist": self.watchlist,
            "truth_rules": [
                "Do not promote unverified named permits, projects, companies, people, or dollar amounts.",
                "Facts require source URL, publication or observation date, trust rationale, and verification status.",
                "Forecast clauses require probability, resolve date, metric, watch signal, and kill condition.",
                "Unknowns become queued tasks, not prose filler.",
                "Opus or paid multi-agent runs require explicit user approval with agent count and rough cost.",
            ],
        }
        return atlas

    def _add_thesis(self, thesis: dict[str, Any], domain_node: str, source_node: str) -> None:
        thesis_id = _clean(thesis.get("id")) or f"T{len(self.forecasts) + 1}"
        headline = _clean(thesis.get("headline")) or _clean(thesis.get("boom")) or thesis_id
        domain = _clean(thesis.get("domain")) or self.board.get("domain") or self.board.get("title")
        thesis_node = self.add_node(
            "thesis",
            f"{thesis_id}: {headline}",
            domain=domain,
            fields={
                "thesis_id": thesis_id,
                "structural": thesis.get("structural"),
                "pre_consensus": thesis.get("pre_consensus"),
                "why": thesis.get("why"),
            },
            confidence=0.8,
        )
        self.add_edge(domain_node, thesis_node, "contains_thesis", "The board domain contains this forecast thesis.", 0.9)
        self.add_edge(source_node, thesis_node, "states", "The source board states this thesis.", 1.0)

        needle = _clean(thesis.get("needle")) or _clean(thesis.get("binding_constraint")) or _clean(thesis.get("boom"))
        if needle:
            constraint_node = self.add_node(
                "constraint",
                needle,
                domain=domain,
                fields={"source_thesis": thesis_id},
                confidence=0.7,
            )
            self.add_edge(thesis_node, constraint_node, "identifies_constraint", "The thesis claims this is the binding constraint.", 0.7)
        else:
            constraint_node = None
            self._unknown(thesis_id, "constraint_identification", "Find the binding constraint named by this thesis.", "A03", "high")

        metric = _clean(thesis.get("metric"))
        metric_node = None
        if metric:
            metric_node = self.add_node("metric", metric, domain=domain, fields={"source_thesis": thesis_id}, confidence=0.75)
            self.add_edge(thesis_node, metric_node, "resolved_by", "The forecast clause resolves through this metric.", 0.8)
            if constraint_node:
                self.add_edge(constraint_node, metric_node, "observed_by", "This metric is an observable proxy for the constraint.", 0.65)
        else:
            self._unknown(thesis_id, "metric", "Define a dated measurable metric for this thesis.", "A13", "critical")

        kill = _clean(thesis.get("kill"))
        if kill:
            kill_node = self.add_node("kill_condition", kill, domain=domain, fields={"source_thesis": thesis_id}, confidence=0.8)
            self.add_edge(thesis_node, kill_node, "falsified_by", "This condition kills or falsifies the thesis.", 0.9)
        else:
            self._unknown(thesis_id, "kill_condition", "Define the kill condition that would falsify this thesis.", "A10", "critical")

        price_channel = _clean(thesis.get("price_channel"))
        if price_channel:
            price_node = self.add_node("price_channel", price_channel, domain=domain, fields={"source_thesis": thesis_id}, confidence=0.65)
            self.add_edge(thesis_node, price_node, "priced_through", "The pricing gate should inspect this channel.", 0.65)
        else:
            self._unknown(thesis_id, "pricing_gate", "Run a price and consensus gate for whether this thesis is already believed.", "A05", "critical")

        implications = thesis.get("implications") or {}
        self._add_implications(thesis_id, thesis_node, constraint_node, implications, domain)
        self._add_forecast(thesis_id, headline, thesis, thesis_node, constraint_node, metric_node)
        self._add_default_unknowns(thesis_id)

    def _add_implications(
        self,
        thesis_id: str,
        thesis_node: str,
        constraint_node: str | None,
        implications: dict[str, Any],
        domain: str | None,
    ) -> None:
        exposed = _clean(implications.get("exposed"))
        if exposed:
            buyer_node = self.add_node("buyer_segment", exposed, domain=domain, fields={"source_thesis": thesis_id}, confidence=0.65)
            self.add_edge(thesis_node, buyer_node, "exposes", "This buyer or operator is exposed to the forecast.", 0.65)
        else:
            self._unknown(thesis_id, "buyer_segment", "Identify the exposed buyer, operator, investor, or policymaker.", "A12", "medium")

        action = _clean(implications.get("action_now"))
        if action:
            action_node = self.add_node("action", action, domain=domain, fields={"source_thesis": thesis_id}, confidence=0.65)
            self.add_edge(thesis_node, action_node, "changes_action", "If the thesis is right, this action changes now.", 0.65)
        else:
            self._unknown(thesis_id, "action", "Define the action changed by this forecast.", "A12", "medium")

        watch = _clean(implications.get("watch"))
        if watch:
            watch_node = self.add_node("observable", watch, domain=domain, fields={"source_thesis": thesis_id}, confidence=0.7)
            self.add_edge(thesis_node, watch_node, "watched_by", "This is the earliest observable signal to monitor.", 0.75)
            if constraint_node:
                self.add_edge(constraint_node, watch_node, "emits_signal", "The constraint should emit this signal if the thesis is becoming true.", 0.65)
            self.watchlist.append(
                {
                    "id": _slug(f"watch-{thesis_id}-{watch}", "w"),
                    "thesis_id": thesis_id,
                    "watch_signal": watch,
                    "metric": "",
                    "cadence": "monthly until a source-specific cadence is verified",
                    "owner_agent": "A13",
                    "status": "unverified_source_needed",
                }
            )
        else:
            self._unknown(thesis_id, "watch_signal", "Define the earliest observable signal to monitor.", "A13", "critical")

        for rel_kind, node_kind, rel, items in (
            ("winner", "winner", "creates_winner", _as_people(implications.get("winners"))),
            ("loser", "loser", "creates_loser", _as_people(implications.get("losers"))),
        ):
            if not items:
                self._unknown(thesis_id, rel_kind, f"Name the {rel_kind}s and why the graph moves against or toward them.", "A12", "medium")
                continue
            for item in items:
                label = item.get("who") if isinstance(item, dict) else str(item)
                why = item.get("why") if isinstance(item, dict) else ""
                node = self.add_node(node_kind, _clean(label), domain=domain, fields={"why": why, "source_thesis": thesis_id}, confidence=0.55)
                self.add_edge(thesis_node, node, rel, f"The thesis names this {rel_kind}: {why}", 0.55)

        for field, kind, rel, agent in (
            ("rent_path", "constraint", "moves_rent_to", "A03"),
            ("next_constraint", "constraint", "creates_next_constraint", "A03"),
            ("reprices", "price_channel", "reprices", "A05"),
            ("decision_changed", "action", "changes_decision", "A12"),
            ("roi_logic", "action", "justified_by_roi", "A12"),
        ):
            value = _clean(implications.get(field))
            if value:
                node = self.add_node(kind, value, domain=domain, fields={"source_field": field, "source_thesis": thesis_id}, confidence=0.55)
                self.add_edge(thesis_node, node, rel, f"Derived from implications.{field}.", 0.55)
                if constraint_node and kind == "constraint" and field == "next_constraint":
                    self.add_edge(constraint_node, node, "migrates_to", "The thesis says this constraint creates a next constraint.", 0.55)
            elif field in {"rent_path", "next_constraint"}:
                self._unknown(thesis_id, field, f"Map the {field.replace('_', ' ')} for this thesis.", agent, "medium")

    def _add_forecast(
        self,
        thesis_id: str,
        headline: str,
        thesis: dict[str, Any],
        thesis_node: str,
        constraint_node: str | None,
        metric_node: str | None,
    ) -> None:
        forecast_id = _slug(f"forecast-{thesis_id}-{headline}", "f")
        forecast_node = self.add_node(
            "forecast_clause",
            headline,
            domain=thesis.get("domain"),
            fields={"source_thesis": thesis_id, "resolves": thesis.get("resolves")},
            confidence=0.85,
        )
        self.add_edge(thesis_node, forecast_node, "states_forecast", "This thesis states a scored forecast clause.", 0.9)
        if constraint_node:
            self.add_edge(forecast_node, constraint_node, "conditional_on_constraint", "The forecast depends on this constraint being binding.", 0.75)
        if metric_node:
            self.add_edge(forecast_node, metric_node, "scored_by", "The forecast is scored through this metric.", 0.85)

        forecast = {
            "id": forecast_id,
            "node_id": forecast_node,
            "thesis_id": thesis_id,
            "headline": headline,
            "vision_p": thesis.get("vision_p"),
            "clause_p": thesis.get("clause_p"),
            "resolves": thesis.get("resolves"),
            "metric": thesis.get("metric"),
            "kill": thesis.get("kill"),
            "node_refs": [n for n in (forecast_node, thesis_node, constraint_node, metric_node) if n],
            "status": "scored_clause_from_board",
        }
        self.forecasts.append(forecast)

        watch = self.watchlist[-1] if self.watchlist and self.watchlist[-1]["thesis_id"] == thesis_id else None
        if watch:
            watch["metric"] = thesis.get("metric") or ""
            watch["kill"] = thesis.get("kill") or ""
            watch["resolves"] = thesis.get("resolves") or ""

    def _add_default_unknowns(self, thesis_id: str) -> None:
        for kind, question, agent, priority in (
            ("source_pack", "Attach primary/official source URLs and publication dates to every load-bearing node.", "A01", "critical"),
            ("substitute_path", "Map substitutes that would kill or weaken the bottleneck.", "A10", "high"),
            ("scenario_branch", "Create at least one base/upside/downside scenario branch around this thesis.", "A11", "medium"),
            ("entity_resolution", "Resolve named entities to canonical companies, agencies, labs, materials, and projects.", "A01", "high"),
        ):
            self._unknown(thesis_id, kind, question, agent, priority)

    def _coverage(self) -> dict[str, Any]:
        kind_counts: dict[str, int] = {}
        for node in self.nodes:
            kind_counts[node["kind"]] = kind_counts.get(node["kind"], 0) + 1

        checks: list[dict[str, str]] = []
        for kind in CORE_NODE_KINDS:
            count = kind_counts.get(kind, 0)
            checks.append(
                {
                    "id": f"node_kind_{kind}",
                    "label": f"Node kind: {kind}",
                    "status": "covered" if count else "gap",
                    "count": str(count),
                    "note": f"{count} node(s)" if count else "No node of this required kind yet.",
                }
            )

        edge_rels = {edge["rel"] for edge in self.edges}
        for rel in ("identifies_constraint", "resolved_by", "falsified_by", "priced_through", "watched_by"):
            checks.append(
                {
                    "id": f"edge_rel_{rel}",
                    "label": f"Edge relation: {rel}",
                    "status": "covered" if rel in edge_rels else "gap",
                    "count": "1" if rel in edge_rels else "0",
                    "note": "Relation exists." if rel in edge_rels else "Relation missing from this compile.",
                }
            )

        for layer in COVERAGE_LAYERS:
            status = "covered" if self._layer_is_covered(layer["id"]) else "gap"
            checks.append(
                {
                    "id": f"layer_{layer['id']}",
                    "label": layer["label"],
                    "status": status,
                    "count": "",
                    "note": layer["test"] if status == "gap" else "Layer has at least one proxy in the atlas.",
                }
            )

        open_tasks = {task["kind"]: 0 for task in self.unknown_queue}
        for task in self.unknown_queue:
            open_tasks[task["kind"]] = open_tasks.get(task["kind"], 0) + 1
        for kind, label in (
            ("source_pack", "Primary source packs"),
            ("substitute_path", "Substitute and refute paths"),
            ("scenario_branch", "Scenario branches"),
            ("entity_resolution", "Canonical entity resolution"),
        ):
            count = open_tasks.get(kind, 0)
            checks.append(
                {
                    "id": f"verification_{kind}",
                    "label": label,
                    "status": "gap" if count else "covered",
                    "count": str(count),
                    "note": f"{count} open task(s) remain." if count else "No open task of this kind.",
                }
            )

        verified_nodes = sum(1 for node in self.nodes if node.get("verification_status") == "source_verified")
        checks.append(
            {
                "id": "verification_source_verified_nodes",
                "label": "Source-verified decision-grade nodes",
                "status": "covered" if verified_nodes else "gap",
                "count": str(verified_nodes),
                "note": f"{verified_nodes} source-verified node(s)." if verified_nodes else "No decision-grade source-verified nodes yet.",
            }
        )

        covered = sum(1 for c in checks if c["status"] == "covered")
        score = round(100 * covered / max(1, len(checks)))
        return {"score": score, "checks": checks, "kind_counts": kind_counts}

    def _layer_is_covered(self, layer_id: str) -> bool:
        if layer_id == "frontier":
            return any("frontier" in _hay(n) or "capability" in _hay(n) for n in self.nodes)
        if layer_id == "capability":
            return any("capability" in _hay(n) or "can now" in _hay(n) for n in self.nodes)
        if layer_id == "dependency":
            return any(e["rel"] in {"identifies_constraint", "conditional_on_constraint", "migrates_to"} for e in self.edges)
        if layer_id == "supply":
            return any(n["kind"] == "constraint" for n in self.nodes)
        if layer_id == "demand":
            return any(n["kind"] == "buyer_segment" for n in self.nodes)
        if layer_id == "capital":
            return any("capital" in _hay(n) or "capex" in _hay(n) or "fund" in _hay(n) for n in self.nodes)
        if layer_id == "pricing":
            return any(n["kind"] == "price_channel" for n in self.nodes)
        if layer_id == "policy":
            return any("policy" in _hay(n) or "permit" in _hay(n) or "regulat" in _hay(n) or "export" in _hay(n) for n in self.nodes)
        if layer_id == "outcome":
            return any(n["kind"] in {"metric", "kill_condition", "observable"} for n in self.nodes)
        if layer_id == "forces":
            return any("talent" in _hay(n) or "labor" in _hay(n) or "climate" in _hay(n) or "social" in _hay(n) for n in self.nodes)
        return False

    def add_node(
        self,
        kind: str,
        label: str,
        *,
        domain: str | None = None,
        fields: dict[str, Any] | None = None,
        confidence: float = 0.5,
    ) -> str:
        label = _clean(label)
        key = (kind, label.lower())
        if key in self._node_index:
            return self._node_index[key]
        node_id = _slug(f"{kind}-{label}", "n")
        node = {
            "id": node_id,
            "kind": kind,
            "label": label,
            "domain": _clean(domain),
            "confidence": round(float(confidence), 3),
            "verification_status": "derived_from_board" if kind != "source" else "source_artifact",
            "fields": fields or {},
        }
        self.nodes.append(node)
        self._node_index[key] = node_id
        return node_id

    def add_edge(
        self,
        src: str,
        dst: str,
        rel: str,
        rationale: str,
        confidence: float = 0.5,
    ) -> str:
        key = (src, dst, rel)
        if key in self._edge_index:
            return _slug(f"{src}-{rel}-{dst}", "e")
        self._edge_index.add(key)
        edge_id = _slug(f"{src}-{rel}-{dst}", "e")
        self.edges.append(
            {
                "id": edge_id,
                "src": src,
                "dst": dst,
                "rel": rel,
                "confidence": round(float(confidence), 3),
                "verification_status": "derived_from_board",
                "rationale": _clean(rationale),
            }
        )
        return edge_id

    def _unknown(self, thesis_id: str, kind: str, question: str, owner_agent: str, priority: str) -> None:
        task_id = _slug(f"unknown-{thesis_id}-{kind}-{question}", "u")
        if any(t["id"] == task_id for t in self.unknown_queue):
            return
        self.unknown_queue.append(
            {
                "id": task_id,
                "thesis_id": thesis_id,
                "kind": kind,
                "priority": priority,
                "question": question,
                "owner_agent": owner_agent,
                "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
                "status": "open",
            }
        )


def _as_people(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        return [{"who": value.strip(), "why": ""}]
    return []


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _hay(node: dict[str, Any]) -> str:
    return json.dumps(node, ensure_ascii=False, sort_keys=True).lower()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slug(value: str, prefix: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    text = re.sub(r"-+", "-", text)[:80].strip("-")
    if not text:
        text = digest
    text = f"{text}-{digest}"
    if text.startswith(prefix + "-"):
        return text
    return f"{prefix}-{text}"


def _stable_hash(atlas: dict[str, Any]) -> str:
    payload = deepcopy(atlas)
    payload.get("meta", {}).pop("generated_at", None)
    payload.pop("snapshot_hash", None)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)
