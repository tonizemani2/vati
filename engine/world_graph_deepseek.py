"""DeepSeek V4 E2E runner for the Vati World Graph.

The deterministic world graph compiler creates the atlas and work queue. This
module creates an API-backed improvement run: role prompts, cost estimates,
optional execution, raw outputs, and an integration/critique/repair loop.

No network call happens unless execute=True. All paid calls go through
engine.adapters.llm.complete, which reads DEEPSEEK_API_KEY from this repo's .env
and hits the cost gate before each request.
"""

from __future__ import annotations

import json
import math
import platform
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine import db, world_graph
from engine.adapters import llm


MODEL_FLASH = "deepseek-v4-flash"
MODEL_PRO = "deepseek-v4-pro"
RUN_VERSION = "deepseek_world_graph_v1"

PRICING_PER_1M = {
    MODEL_FLASH: {"input_cache_miss": 0.14, "output": 0.28},
    MODEL_PRO: {"input_cache_miss": 0.435, "output": 0.87},
}

SYSTEM = """You are a Vaticinus World Graph specialist.
Return compact, source-disciplined output. Separate facts from hypotheses.
Do not invent permits, people, contacts, projects, prices, or dates.
If evidence is missing, create verification tasks.
Prefer JSON when asked. Keep forecast clauses falsifiable."""


@dataclass(frozen=True)
class PlannedCall:
    id: str
    role: str
    model: str
    max_tokens: int
    prompt: str
    reasoning_effort: str = "high"


def build_run_pack(
    board_path: str | Path,
    *,
    out_dir: str | Path,
    plan: str = "standard",
    model_flash: str = MODEL_FLASH,
    model_pro: str = MODEL_PRO,
) -> dict[str, Any]:
    """Compile the base atlas and write a DeepSeek dry-run pack."""

    board_path = Path(board_path)
    board = world_graph.load_board(board_path)
    atlas = world_graph.build_atlas(board, board_path)
    calls = plan_calls(atlas, plan=plan, model_flash=model_flash, model_pro=model_pro)
    estimate = estimate_calls(calls)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    graph_files = world_graph.write_outputs(atlas, out / "base_graph")
    pack = {
        "run_version": RUN_VERSION,
        "run_mode": "dry_run_call_plan",
        "plan": plan,
        "board_path": str(board_path),
        "created_at": _now(),
        "call_count": len(calls),
        "models": sorted({c.model for c in calls}),
        "estimate": estimate,
        "base_graph": graph_files,
        "calls": [_call_meta(c) for c in calls],
        "requires": {
            "api_key": "DEEPSEEK_API_KEY in repo .env",
            "execute_flag": "--execute",
            "cost_gate": "COST_AUTO_APPROVE_CENTS or explicit approval before paid calls",
        },
    }
    return _write_pack(out, pack, calls)


def execute_run(
    board_path: str | Path,
    *,
    out_dir: str | Path,
    plan: str = "standard",
    model_flash: str = MODEL_FLASH,
    model_pro: str = MODEL_PRO,
    allow_unstable_mac: bool = False,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Run the DeepSeek call plan and write raw outputs plus an integration pass."""

    if not allow_unstable_mac:
        guard = mac_stability_report()
        if not guard["ok"]:
            raise RuntimeError(
                "refusing paid DeepSeek execution because the Mac looks unstable: "
                + "; ".join(guard["issues"])
                + ". Re-run with --allow-unstable-mac only if you explicitly accept the risk."
            )

    own_conn = conn is None
    if conn is None:
        conn = db.connect()
        db.init_db(conn)
    try:
        pack = build_run_pack(
            board_path,
            out_dir=out_dir,
            plan=plan,
            model_flash=model_flash,
            model_pro=model_pro,
        )
        out = Path(out_dir)
        calls = [
            PlannedCall(
                id=c["id"],
                role=c["role"],
                model=c["model"],
                max_tokens=int(c["max_tokens"]),
                prompt=(out / "prompts" / f"{c['id']}.md").read_text(encoding="utf-8"),
                reasoning_effort=c.get("reasoning_effort", "high"),
            )
            for c in pack["calls"]
        ]
        raw_dir = out / "raw_outputs"
        raw_dir.mkdir(parents=True, exist_ok=True)
        outputs = []
        for idx, call in enumerate(calls, start=1):
            path = raw_dir / f"{call.id}.md"
            if path.exists() and path.stat().st_size > 0:
                print(f"[{idx}/{len(calls)}] skip existing {call.id} ({call.role})", flush=True)
                outputs.append({"id": call.id, "role": call.role, "model": call.model, "path": str(path), "status": "existing"})
                continue
            est = estimate_call(call)
            print(
                f"[{idx}/{len(calls)}] call {call.id} ({call.role}) "
                f"model={call.model} est=${est['cost_usd']:.4f}",
                flush=True,
            )
            text = llm.complete(
                conn,
                call.prompt,
                provider="deepseek",
                model=call.model,
                system=SYSTEM,
                max_tokens=call.max_tokens,
                est_cost_cents=math.ceil(est["cost_usd"] * 100),
                reasoning_effort=call.reasoning_effort,
                extra_body={"thinking": {"type": "enabled"}},
            )
            path.write_text(text.strip() + "\n", encoding="utf-8")
            print(f"[{idx}/{len(calls)}] wrote {path}", flush=True)
            outputs.append({"id": call.id, "role": call.role, "model": call.model, "path": str(path), "status": "written"})
        result = {
            **pack,
            "run_mode": "executed",
            "outputs": outputs,
            "finished_at": _now(),
        }
        (out / "run_results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (out / "RUN_MANIFEST.md").write_text(render_manifest(result), encoding="utf-8")
        return result
    finally:
        if own_conn:
            conn.close()


def mac_stability_report(window_minutes: int = 20) -> dict[str, Any]:
    """Return whether it is safe to start a long paid local run on this Mac.

    This is intentionally narrow: it catches the Codex/Dock crash loop seen on
    macOS 13.5, where Codex's Dock tile plugin crashes Dock's external-extra
    helper and launch-services-helper reports a newer-macOS symbol dependency.
    """

    if platform.system() != "Darwin":
        return {"ok": True, "issues": [], "window_minutes": window_minutes}
    cutoff = time.time() - window_minutes * 60
    roots = [
        Path.home() / "Library" / "Logs" / "DiagnosticReports",
        Path("/Library/Logs/DiagnosticReports"),
    ]
    issues: list[str] = []
    matches: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.glob("*.ips"):
            try:
                if path.stat().st_mtime < cutoff:
                    continue
                text = path.read_text(errors="ignore")[:12000]
            except OSError:
                continue
            name = path.name
            if "com.apple.dock.external.extra" in name and "CodexDockTilePlugin" in text:
                issues.append("recent Dock external-extra crash involving CodexDockTilePlugin")
                matches.append(str(path))
            if "launch-services-helper" in name and "built for macOS 26" in text and "Codex.app" in text:
                issues.append("recent Codex launch-services-helper crash from newer-macOS symbol dependency")
                matches.append(str(path))
    return {
        "ok": not issues,
        "issues": sorted(set(issues)),
        "matches": sorted(set(matches))[:10],
        "window_minutes": window_minutes,
    }


def plan_calls(
    atlas: dict[str, Any],
    *,
    plan: str = "standard",
    model_flash: str = MODEL_FLASH,
    model_pro: str = MODEL_PRO,
) -> list[PlannedCall]:
    """Return the call plan. Plans: lite=5, standard=17, full=13+4/thesis+3."""

    plan = plan.lower().strip()
    if plan not in {"lite", "standard", "full"}:
        raise ValueError("plan must be lite, standard, or full")
    calls: list[PlannedCall] = []
    agents = atlas["agent_roster"]
    if plan == "lite":
        roles = {"graph_cartographer", "dependency_chain", "pricing_gate", "adversarial_refute"}
        selected = [a for a in agents if a["role"] in roles]
    else:
        selected = agents
    for agent in selected:
        model = model_pro if agent["role"] in {"pricing_gate", "adversarial_refute", "scenario_architect"} else model_flash
        calls.append(
            PlannedCall(
                id=f"{len(calls)+1:02d}_{agent['role']}",
                role=agent["role"],
                model=model,
                max_tokens=4200 if model == model_pro else 2600,
                prompt=_agent_prompt(atlas, agent),
            )
        )

    if plan == "full":
        for fc in atlas["forecast_clauses"]:
            for role, model in (
                ("source_pack", model_flash),
                ("substitute_refute", model_pro),
                ("scenario_branch", model_pro),
                ("ultra_verification", model_flash),
            ):
                calls.append(
                    PlannedCall(
                        id=f"{len(calls)+1:02d}_{fc['thesis_id'].lower()}_{role}",
                        role=role,
                        model=model,
                        max_tokens=3400 if model == model_pro else 2400,
                        prompt=_forecast_prompt(atlas, fc, role),
                    )
                )

    for role, max_tokens, prompt in (
        ("integrator", 5200, _integrator_prompt(atlas, plan)),
        ("critic", 4200, _critic_prompt(atlas)),
        ("repair", 5200, _repair_prompt(atlas)),
    ):
        calls.append(
            PlannedCall(
                id=f"{len(calls)+1:02d}_{role}",
                role=role,
                model=model_pro,
                max_tokens=max_tokens,
                prompt=prompt,
            )
        )
    if plan == "standard":
        calls.append(
            PlannedCall(
                id=f"{len(calls)+1:02d}_score",
                role="score",
                model=model_pro,
                max_tokens=2600,
                prompt=_score_prompt(atlas),
            )
        )
    return calls


def estimate_calls(calls: list[PlannedCall]) -> dict[str, Any]:
    by_model: dict[str, dict[str, float]] = {}
    total = 0.0
    for call in calls:
        est = estimate_call(call)
        total += est["cost_usd"]
        row = by_model.setdefault(call.model, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
        row["calls"] += 1
        row["input_tokens"] += est["input_tokens"]
        row["output_tokens"] += est["output_tokens"]
        row["cost_usd"] += est["cost_usd"]
    return {
        "total_cost_usd_cache_miss": round(total, 4),
        "total_cost_cents_cache_miss": math.ceil(total * 100),
        "by_model": {k: {kk: round(vv, 4) for kk, vv in v.items()} for k, v in by_model.items()},
        "pricing_basis": "DeepSeek official per-1M token cache-miss input and output pricing, checked 2026-06-18",
    }


def estimate_call(call: PlannedCall) -> dict[str, Any]:
    input_tokens = _est_tokens(SYSTEM) + _est_tokens(call.prompt)
    output_tokens = call.max_tokens
    prices = PRICING_PER_1M.get(call.model, PRICING_PER_1M[MODEL_PRO])
    cost_usd = (input_tokens / 1_000_000 * prices["input_cache_miss"]) + (
        output_tokens / 1_000_000 * prices["output"]
    )
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
        "cost_cents": math.ceil(cost_usd * 100),
    }


def render_manifest(pack: dict[str, Any]) -> str:
    est = pack["estimate"]
    lines = [
        "# DeepSeek V4 World Graph Run Manifest",
        "",
        f"Created: {pack['created_at']}",
        f"Run mode: `{pack['run_mode']}`",
        f"Plan: `{pack['plan']}`",
        f"Board: `{pack['board_path']}`",
        f"Calls: {pack['call_count']}",
        f"Estimated cost, cache miss: ${est['total_cost_usd_cache_miss']:.4f}",
        "",
        "## Models",
        "",
    ]
    for model, row in est["by_model"].items():
        lines.append(
            f"- `{model}`: {int(row['calls'])} calls, ~{int(row['input_tokens'])} input tokens, "
            f"~{int(row['output_tokens'])} output tokens, ${row['cost_usd']:.4f}"
        )
    lines.extend(
        [
            "",
            "## Cost And Approval",
            "",
            "This manifest is safe to generate. Actual API execution requires `--execute`, `DEEPSEEK_API_KEY`, and cost-gate approval.",
            "",
            "## Calls",
            "",
        ]
    )
    for call in pack["calls"]:
        prompt_path = call.get("prompt_path") or f"prompts/{call['id']}.md"
        lines.append(f"- `{call['id']}` {call['role']} on `{call['model']}` -> `{prompt_path}`")
    lines.append("")
    return "\n".join(lines)


def _write_pack(out: Path, pack: dict[str, Any], calls: list[PlannedCall]) -> dict[str, Any]:
    prompt_dir = out / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    call_rows = []
    for call in calls:
        prompt_path = prompt_dir / f"{call.id}.md"
        prompt_path.write_text(call.prompt, encoding="utf-8")
        call_rows.append({**_call_meta(call), "prompt_path": str(prompt_path)})
    pack = {**pack, "calls": call_rows}
    (out / "call_plan.json").write_text(json.dumps(pack, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out / "prompts.jsonl").open("w", encoding="utf-8") as handle:
        for call in call_rows:
            handle.write(json.dumps(call, sort_keys=True) + "\n")
    (out / "RUN_MANIFEST.md").write_text(render_manifest(pack), encoding="utf-8")
    return pack


def _call_meta(call: PlannedCall) -> dict[str, Any]:
    est = estimate_call(call)
    return {
        "id": call.id,
        "role": call.role,
        "model": call.model,
        "max_tokens": call.max_tokens,
        "reasoning_effort": call.reasoning_effort,
        "estimated_input_tokens": est["input_tokens"],
        "estimated_output_tokens": est["output_tokens"],
        "estimated_cost_usd": round(est["cost_usd"], 6),
        "estimated_cost_cents": est["cost_cents"],
    }


def _agent_prompt(atlas: dict[str, Any], agent: dict[str, str]) -> str:
    return "\n\n".join(
        [
            f"Role: {agent['role']}",
            f"Mission: {agent['mission']}",
            "Input atlas summary:",
            _atlas_brief(atlas),
            "Tasks for this role:",
            _tasks_for_role(atlas, agent["id"], agent["role"]),
            "Return Markdown with: findings, proposed nodes, proposed edges, evidence needed, refutations, and next actions. Mark every proposed fact as source_verified, lead, or hypothesis.",
        ]
    )


def _forecast_prompt(atlas: dict[str, Any], fc: dict[str, Any], role: str) -> str:
    return "\n\n".join(
        [
            f"Role: {role}",
            "Forecast clause:",
            json.dumps(fc, ensure_ascii=False, sort_keys=True, indent=2),
            "Atlas context:",
            _atlas_brief(atlas),
            "Return JSON with keys: thesis_id, role, findings, proposed_nodes, proposed_edges, verification_tasks, refutations, confidence, do_not_promote.",
        ]
    )


def _integrator_prompt(atlas: dict[str, Any], plan: str) -> str:
    return "\n\n".join(
        [
            "Role: integrator",
            f"Plan: {plan}",
            "You will later receive raw role outputs from files. For now, define the integration standard and patch schema.",
            _atlas_brief(atlas),
            "Return JSON schema guidance for merging role outputs into world_graph.patch.json without promoting unverified claims.",
        ]
    )


def _critic_prompt(atlas: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            "Role: adversarial critic",
            "Audit the atlas for overclaiming, hidden missing data, already-priced assumptions, weak source discipline, and scenario monoculture.",
            _atlas_brief(atlas),
            "Return a ranked bug list and what exact evidence would fix each issue.",
        ]
    )


def _repair_prompt(atlas: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            "Role: repair planner",
            "Convert critique into a safe graph repair plan. Do not invent facts.",
            _atlas_brief(atlas),
            "Return JSON with add_nodes, add_edges, keep_unknowns, close_unknowns, new_watch_signals, and do_not_promote.",
        ]
    )


def _score_prompt(atlas: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            "Role: quality scorer",
            "Score whether this graph is ready for a serious Pope Mega or Ultra run.",
            _atlas_brief(atlas),
            "Return a 0-100 score, blockers, and the minimum next call set needed to improve it.",
        ]
    )


def _atlas_brief(atlas: dict[str, Any]) -> str:
    payload = {
        "meta": atlas["meta"],
        "summary": atlas["summary"],
        "coverage_score": atlas["coverage"]["score"],
        "coverage_gaps": [c for c in atlas["coverage"]["checks"] if c["status"] == "gap"][:20],
        "forecast_clauses": atlas["forecast_clauses"],
        "unknown_queue": atlas["unknown_queue"][:40],
        "watchlist": atlas["watchlist"],
        "node_samples": atlas["nodes"][:40],
        "edge_samples": atlas["edges"][:50],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def _tasks_for_role(atlas: dict[str, Any], agent_id: str, role: str) -> str:
    tasks = [t for t in atlas["unknown_queue"] if t.get("owner_agent") == agent_id]
    if not tasks:
        tasks = [t for t in atlas["unknown_queue"] if role.split("_")[0] in t.get("kind", "")]
    return json.dumps(tasks[:20], ensure_ascii=False, sort_keys=True, indent=2)


def _est_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
