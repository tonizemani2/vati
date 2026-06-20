#!/usr/bin/env python3
"""Pope Ultra: compile Pope forecast boards into execution dossiers.

Ultra is deliberately more operational than Pope Mega. It does not invent facts.
It preserves the scored forecast, then creates a truth-seeking task graph for
named permits, projects, companies, labs, people, contacts, budgets, and watch
signals. Unknowns become tasks with source requirements.

Usage:
    python3 -m engine.pope.ultra research/pope/after-ai-2026-06-17.json \
      --out-dir research/pope/after-ai-2026-06-17.ultra
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


TRUTH_STATUSES = [
    "unverified",
    "lead",
    "source_verified",
    "primary_verified",
    "contact_confirmed",
    "refuted",
]

SOURCE_TIERS = {
    "primary": [
        "permit docket",
        "regulator record",
        "official company page",
        "SEC or statutory filing",
        "grant award database",
        "procurement portal",
        "university lab page",
        "standards-body publication",
    ],
    "official": [
        "company newsroom",
        "public agency page",
        "utility or ISO/RTO queue",
        "university directory",
        "conference speaker page",
    ],
    "secondary": [
        "reputable trade press",
        "credible analyst note",
        "local reporting",
        "industry association page",
    ],
    "lead_only": [
        "search result snippet",
        "uncorroborated database row",
        "social profile",
        "LLM-generated candidate",
    ],
}


@dataclass(frozen=True)
class PacketTemplate:
    kind: str
    name: str
    why: str
    required_fields: list[str]
    source_priority: list[str]
    query_templates: list[str]
    deliverable: str
    truth_floor: str = "primary_verified"


BASE_PACKETS = [
    PacketTemplate(
        kind="permit_docket",
        name="Permits, dockets, queues, and local approvals",
        why="The forecast only becomes actionable when the legal/permission path is named and current.",
        required_fields=[
            "permit_or_docket_name",
            "jurisdiction",
            "applicant",
            "project_or_asset",
            "status",
            "filed_date",
            "next_hearing_or_deadline",
            "capacity_or_scope",
            "source_url",
            "quote_or_table_row",
        ],
        source_priority=[
            "county or municipal planning agenda",
            "state public utility commission docket",
            "FERC eLibrary or federal docket",
            "ISO/RTO interconnection queue",
            "EPA, state environmental, water, or air permit database",
            "company filing that names the permit or project",
        ],
        query_templates=[
            '"{needle}" "{domain}" permit docket',
            '"{headline}" permit OR docket OR interconnection',
            '"{action_now}" site permit',
            '"{metric}" "queue" "status"',
        ],
        deliverable="A table of named permits/dockets with current status and next check date.",
    ),
    PacketTemplate(
        kind="project_asset",
        name="Named projects, assets, sites, and physical bottlenecks",
        why="Buyers need named assets, not a category. The asset map says what can actually be bought, reserved, funded, or avoided.",
        required_fields=[
            "project_name",
            "asset_owner",
            "location",
            "capacity_or_volume",
            "timeline",
            "constraint_link",
            "commercial_status",
            "source_url",
            "quote_or_table_row",
        ],
        source_priority=[
            "official project page",
            "developer announcement",
            "permit filing",
            "utility interconnection queue",
            "investor presentation",
            "local planning record",
        ],
        query_templates=[
            '"{needle}" "{domain}" project',
            '"{boom}" developer site project',
            '"{rent_path}" project capacity timeline',
            '"{watch}" announced project',
        ],
        deliverable="A ranked map of named projects/assets with why each matters to the constraint.",
    ),
    PacketTemplate(
        kind="company_supplier",
        name="Companies, suppliers, buyers, and counterparties",
        why="The forecast turns commercial when it names who can capture, relieve, or suffer the constraint.",
        required_fields=[
            "organization",
            "role",
            "evidence_of_role",
            "product_or_asset",
            "buyer_or_supplier_link",
            "public_contact_path",
            "source_url",
            "quote_or_table_row",
        ],
        source_priority=[
            "official company page",
            "10-K, S-1, 8-K, annual report, or statutory filing",
            "procurement portal",
            "customer announcement",
            "trade association member page",
        ],
        query_templates=[
            '"{needle}" supplier company',
            '"{boom}" "{domain}" company',
            '"{rent_path}" "customer" OR "supplier"',
            '"{exposed}" "{needle}"',
        ],
        deliverable="A counterparty table with role, proof, and public contact path.",
    ),
    PacketTemplate(
        kind="research_lab",
        name="Universities, labs, grants, and research groups",
        why="Some constraints are solved first in labs. This packet finds who is already doing the hard part.",
        required_fields=[
            "institution",
            "lab_or_center",
            "principal_investigator_or_team",
            "research_topic",
            "grant_or_publication",
            "evidence_span",
            "public_contact_path",
            "source_url",
        ],
        source_priority=[
            "university lab page",
            "grant award database",
            "OpenAlex, Crossref, PubMed, arXiv, or patent record",
            "conference program",
            "technology-transfer page",
        ],
        query_templates=[
            '"{needle}" university lab',
            '"{metric}" "NSF" OR "DOE" OR "NIH" grant',
            '"{domain}" "{needle}" principal investigator',
            '"{next_constraint}" research group',
        ],
        deliverable="A lab map with named people or groups and what question to ask them.",
    ),
    PacketTemplate(
        kind="person_contact",
        name="People and public contact paths",
        why="Agentic work needs who to call, but contact data must be public and verified.",
        required_fields=[
            "person_or_role",
            "organization",
            "why_relevant",
            "authority_or_expertise",
            "public_contact_path",
            "contact_source_url",
            "do_not_guess_email",
        ],
        source_priority=[
            "official leadership page",
            "public agency staff directory",
            "university directory",
            "permit filing contact page",
            "conference speaker bio",
            "company investor-relations or media contact page",
        ],
        query_templates=[
            '"{needle}" "{domain}" "vice president" OR director',
            '"{headline}" "speaker" OR "principal investigator"',
            '"{exposed}" "{action_now}" contact',
            '"{metric}" regulator contact OR staff',
        ],
        deliverable="A public-contact task list with question scripts, not guessed emails.",
        truth_floor="contact_confirmed",
    ),
    PacketTemplate(
        kind="capital_operation",
        name="Capital, procurement, and operating action",
        why="This is the bridge from interesting forecast to 'put this much money into this operation'.",
        required_fields=[
            "action",
            "amount_range",
            "unit_cost_basis",
            "counterparty_or_asset",
            "first_tranche_trigger",
            "next_tranche_trigger",
            "expected_roi_or_loss_avoided",
            "reversibility",
            "kill_condition",
            "owner",
            "source_url",
        ],
        source_priority=[
            "vendor quote or rate card",
            "filing with capex or contract data",
            "public procurement award",
            "project finance document",
            "market price series",
            "buyer-provided internal number",
        ],
        query_templates=[
            '"{needle}" cost per MW OR capex OR contract',
            '"{action_now}" budget procurement',
            '"{decision_changed}" capex amount',
            '"{reprices}" price contract premium',
        ],
        deliverable="A trancheable action memo with amount, trigger, owner, ROI logic, and stop condition.",
    ),
    PacketTemplate(
        kind="watch_signal",
        name="Watch signals and kill checks",
        why="A forecast without monitoring is a memo. Ultra makes it a live operating system.",
        required_fields=[
            "signal",
            "source",
            "cadence",
            "threshold",
            "owner",
            "escalation_rule",
            "kill_or_premise_void",
            "source_url",
        ],
        source_priority=[
            "official time series",
            "permit docket updates",
            "interconnection queue",
            "filing feed",
            "grant/publication/patent feed",
            "price series",
        ],
        query_templates=[
            '"{metric}" data source',
            '"{kill}" evidence',
            '"{watch}" source',
            '"{next_constraint}" watch signal',
        ],
        deliverable="A monitoring table with cadence, threshold, and escalation rule.",
    ),
]


DOMAIN_PACKETS: dict[str, list[PacketTemplate]] = {
    "ai_power": [
        PacketTemplate(
            kind="interconnection_power",
            name="Power interconnection and behind-the-meter viability",
            why="For AI infrastructure, the make-or-break fact is often whether power can be energized on the underwriting timeline.",
            required_fields=[
                "site_or_project",
                "utility_or_iso",
                "queue_position_or_docket",
                "mw",
                "expected_in_service_date",
                "behind_the_meter_claim",
                "transformer_or_switchgear_dependency",
                "water_or_cooling_permit",
                "source_url",
            ],
            source_priority=[
                "PJM, ERCOT, MISO, CAISO, SPP, NYISO, ISO-NE queue",
                "utility interconnection filing",
                "county planning and zoning agenda",
                "state PUC docket",
                "EIA plant or generator data",
                "developer or hyperscaler announcement",
            ],
            query_templates=[
                '"data center" "behind-the-meter" "{needle}"',
                '"hyperscaler" "interconnection" "data center" "{domain}"',
                '"geothermal" "data center" "power purchase agreement"',
                '"data center" "transformer" "lead time" permit',
                '"PJM" "data center" interconnection queue "{watch}"',
            ],
            deliverable="A site-by-site power realism table for time-to-energize.",
        ),
    ],
    "robotics": [
        PacketTemplate(
            kind="safety_deployment",
            name="Safety certification, integrators, and deployment labor",
            why="For physical AI, the bottleneck often sits in certified deployment, commissioning, and safety case ownership.",
            required_fields=[
                "standard_or_certification",
                "integrator_or_oem",
                "deployment_site",
                "commissioning_time",
                "safety_owner",
                "evidence_source",
                "public_contact_path",
            ],
            source_priority=[
                "ANSI/RIA, ISO, OSHA, or standards body page",
                "integrator case study",
                "robot OEM deployment note",
                "customer press release",
                "job posting for deployment/safety role",
            ],
            query_templates=[
                '"robot" "commissioning time" integrator',
                '"physical AI" safety certification deployment',
                '"robotics integrator" "{needle}"',
                '"{domain}" "ANSI/RIA" OR "ISO 10218"',
            ],
            deliverable="A deployment bottleneck map with standards, integrators, and labor proof.",
        ),
    ],
    "science": [
        PacketTemplate(
            kind="experimental_throughput",
            name="Assay, lab automation, and verification throughput",
            why="In AI-for-science, the model is not the bottleneck if experiments cannot be run, trusted, and repeated.",
            required_fields=[
                "assay_or_instrument",
                "lab_or_company",
                "throughput_metric",
                "bottleneck_step",
                "data_rights",
                "grant_or_publication",
                "public_contact_path",
            ],
            source_priority=[
                "NIH, NSF, DOE, CORDIS, or SBIR award",
                "lab automation vendor page",
                "university lab page",
                "peer-reviewed paper",
                "clinical/preclinical pipeline disclosure",
            ],
            query_templates=[
                '"self-driving lab" "{needle}" grant',
                '"assay throughput" "{domain}" "AI"',
                '"{next_constraint}" university lab automation',
                '"{metric}" "principal investigator"',
            ],
            deliverable="An experimental-throughput map with who owns the bottleneck and what to fund.",
        ),
    ],
}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = (
        text.replace("\u2014", " - ")
        .replace("\u2013", "-")
        .replace("\u2011", "-")
        .replace("\u2212", "-")
        .replace("\u2026", "...")
    )
    return re.sub(r"\s+", " ", text).strip()


def _query_phrase(value: Any, *, max_words: int = 12, max_chars: int = 120) -> str:
    """Compress a prose field into a web-search-friendly phrase."""
    text = _clean_text(value)
    if not text:
        return ""
    text = re.split(r"[.;:]", text, maxsplit=1)[0]
    text = re.split(r"\s+-\s+|\s+not\s+|\s+rather than\s+", text, maxsplit=1, flags=re.I)[0]
    words = text.split()
    text = " ".join(words[:max_words])
    return text[:max_chars].strip(" ,")


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:64] or "pope-ultra"


def _fmt(template: str, thesis: dict[str, Any]) -> str:
    im = thesis.get("implications") if isinstance(thesis.get("implications"), dict) else {}
    ctx = {
        "id": _query_phrase(thesis.get("id", "")),
        "headline": _query_phrase(thesis.get("headline", ""), max_words=14),
        "boom": _query_phrase(thesis.get("boom", ""), max_words=14),
        "domain": _query_phrase(thesis.get("domain", ""), max_words=8),
        "needle": _query_phrase(thesis.get("needle", ""), max_words=10),
        "metric": _query_phrase(thesis.get("metric", ""), max_words=12),
        "kill": _query_phrase(thesis.get("kill", ""), max_words=12),
        "watch": _query_phrase(im.get("watch", ""), max_words=12),
        "exposed": _query_phrase(im.get("exposed", ""), max_words=10),
        "action_now": _query_phrase(im.get("action_now", ""), max_words=10),
        "decision_changed": _query_phrase(im.get("decision_changed", ""), max_words=10),
        "rent_path": _query_phrase(im.get("rent_path", ""), max_words=12),
        "reprices": _query_phrase(im.get("reprices", ""), max_words=12),
        "next_constraint": _query_phrase(im.get("next_constraint", ""), max_words=12),
    }
    return _clean_text(template.format(**ctx))


def _infer_domain_tags(thesis: dict[str, Any]) -> list[str]:
    blob = " ".join(
        _clean_text(thesis.get(k, ""))
        for k in ("headline", "boom", "domain", "needle", "metric", "structural")
    ).lower()
    tags = []
    if any(w in blob for w in ("data center", "datacenter", "power", "grid", "interconnection", "transformer", "geothermal")):
        tags.append("ai_power")
    if any(w in blob for w in ("robot", "humanoid", "automation", "commissioning", "safety certification")):
        tags.append("robotics")
    if any(w in blob for w in ("lab", "assay", "science", "pharma", "biotech", "materials", "catalyst", "experiment")):
        tags.append("science")
    return tags


def _packets_for(thesis: dict[str, Any]) -> list[PacketTemplate]:
    packets = list(BASE_PACKETS)
    for tag in _infer_domain_tags(thesis):
        packets.extend(DOMAIN_PACKETS[tag])
    return packets


def _make_packet(thesis: dict[str, Any], template: PacketTemplate) -> dict[str, Any]:
    tid = _clean_text(thesis.get("id", "P?"))
    return {
        "id": f"{tid}-{template.kind}",
        "kind": template.kind,
        "name": template.name,
        "why": template.why,
        "truth_status": "unverified",
        "truth_floor": template.truth_floor,
        "required_fields": template.required_fields,
        "source_priority": template.source_priority,
        "seed_queries": [_fmt(q, thesis) for q in template.query_templates],
        "deliverable": template.deliverable,
        "candidate_records": [],
        "promotion_rule": (
            f"Do not promote this packet above '{template.truth_floor}' until every named "
            "record has source_url, retrieved_at, quote_or_table_row, and a non-empty "
            "field set matching required_fields."
        ),
    }


def _layers(thesis: dict[str, Any]) -> list[dict[str, str]]:
    tid = _clean_text(thesis.get("id", "P?"))
    return [
        {
            "id": f"{tid}-L0",
            "name": "Claim integrity",
            "question": "What exactly is scored, and what would kill it?",
            "output": "Original dated clause, probability, metric, resolution, and kill condition preserved.",
        },
        {
            "id": f"{tid}-L1",
            "name": "Decision surface",
            "question": "Which decision changes if the claim is true?",
            "output": "A named capex, procurement, siting, research, hiring, policy, portfolio, or partnership decision.",
        },
        {
            "id": f"{tid}-L2",
            "name": "Named world map",
            "question": "Which permits, projects, companies, labs, people, and contact paths exist in the real world?",
            "output": "A source-verified map of named objects, not categories.",
        },
        {
            "id": f"{tid}-L3",
            "name": "Verification ledger",
            "question": "What is primary-verified, what is only a lead, and what is refuted?",
            "output": "Status, source tier, URL, retrieved date, quote/span, and open questions for each named record.",
        },
        {
            "id": f"{tid}-L4",
            "name": "Action economics",
            "question": "How much money goes into what operation, under which trigger and kill condition?",
            "output": "A trancheable amount/action memo with ROI logic, reversibility, and owner.",
        },
        {
            "id": f"{tid}-L5",
            "name": "Outreach",
            "question": "Who should be contacted and what answer would change the decision?",
            "output": "Public contact paths, question scripts, and evidence attachments.",
        },
        {
            "id": f"{tid}-L6",
            "name": "Monitoring",
            "question": "How does the dossier stay alive?",
            "output": "Cadence, watch signal, escalation threshold, and stop condition.",
        },
    ]


def _action_axes(thesis: dict[str, Any]) -> list[dict[str, str]]:
    im = thesis.get("implications") if isinstance(thesis.get("implications"), dict) else {}
    action_now = _clean_text(im.get("action_now"))
    decision = _clean_text(im.get("decision_changed"))
    kill = _clean_text(thesis.get("kill"))
    metric = _clean_text(thesis.get("metric"))
    return [
        {
            "axis": "capital",
            "question": "What capital allocation changes before consensus catches up?",
            "ultra_output": "Amount range, instrument or asset, timing trigger, downside, and benchmark.",
        },
        {
            "axis": "capex_siting",
            "question": "Which physical site, asset, equipment, or capacity should be reserved or avoided?",
            "ultra_output": action_now or "A named asset/site action with source-verified constraints.",
        },
        {
            "axis": "procurement",
            "question": "Which scarce input should be contracted, dual-sourced, or monitored for lead-time blowout?",
            "ultra_output": "Supplier list, lead-time source, quote/procurement evidence, and fallback.",
        },
        {
            "axis": "research",
            "question": "Which lab, method, or technical bottleneck should be funded or partnered with?",
            "ultra_output": "Named labs, grants, PIs, papers, patents, and contact questions.",
        },
        {
            "axis": "talent",
            "question": "Which skill becomes scarce if the thesis is true?",
            "ultra_output": "Role taxonomy, training path, hiring targets, salary/availability signals.",
        },
        {
            "axis": "policy",
            "question": "Which regulator, permit, standard, or public rule gates the outcome?",
            "ultra_output": "Named docket/permit/standard with status and next hearing or deadline.",
        },
        {
            "axis": "founder_product",
            "question": "What company or tool should exist because this bottleneck appears?",
            "ultra_output": "Pain owner, workflow, first buyer, wedge feature, and proof data.",
        },
        {
            "axis": "monitoring",
            "question": "Which signal changes the view fastest?",
            "ultra_output": metric or kill or decision or "Named signal, source, cadence, and threshold.",
        },
    ]


def _agent_brief(thesis: dict[str, Any]) -> list[str]:
    tid = _clean_text(thesis.get("id", "P?"))
    return [
        f"Start from {tid}; do not alter its scored probability, resolution date, metric, or kill condition.",
        "Promote named facts only when they are source-verified; otherwise keep them as leads or tasks.",
        "Prefer primary sources: permits, dockets, filings, official project pages, grant records, regulator pages, and procurement portals.",
        "For people and contacts, use official public business contact paths only. Never infer emails.",
        "For each action, produce amount range, funded operation, trigger, next tranche trigger, reversibility, ROI/loss logic, owner, and kill condition.",
        "If evidence contradicts the thesis, mark the relevant record refuted and surface it before polishing the memo.",
    ]


def build_dossier(board: dict[str, Any], source_path: str, thesis_filter: str | None = None) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    theses = board.get("theses") or []
    if thesis_filter:
        wanted = thesis_filter.upper()
        theses = [t for t in theses if _clean_text(t.get("id")).upper() == wanted]
        if not theses:
            raise SystemExit(f"No thesis id {thesis_filter!r} found")

    dossiers = []
    task_queue = []
    contact_tasks = []

    for thesis in theses:
        tid = _clean_text(thesis.get("id", "P?"))
        im = thesis.get("implications") if isinstance(thesis.get("implications"), dict) else {}
        packets = [_make_packet(thesis, p) for p in _packets_for(thesis)]
        dossier = {
            "thesis_id": tid,
            "headline": _clean_text(thesis.get("headline")),
            "domain": _clean_text(thesis.get("domain")),
            "scored_claim": {
                "vision_p": thesis.get("vision_p"),
                "clause_p": thesis.get("clause_p"),
                "resolves": thesis.get("resolves"),
                "metric": _clean_text(thesis.get("metric")),
                "kill": _clean_text(thesis.get("kill")),
                "source_thesis_truth_status": "source_verified",
            },
            "decision_core": {
                "exposed": _clean_text(im.get("exposed")),
                "action_now": _clean_text(im.get("action_now")),
                "decision_changed": _clean_text(im.get("decision_changed")),
                "roi_logic": _clean_text(im.get("roi_logic")),
                "watch": _clean_text(im.get("watch")),
            },
            "layers": _layers(thesis),
            "action_axes": _action_axes(thesis),
            "execution_packets": packets,
            "agent_brief": _agent_brief(thesis),
        }
        dossiers.append(dossier)

        for packet in packets:
            task = {
                "thesis_id": tid,
                "packet_id": packet["id"],
                "kind": packet["kind"],
                "task": packet["deliverable"],
                "truth_floor": packet["truth_floor"],
                "first_query": packet["seed_queries"][0] if packet["seed_queries"] else "",
                "source_priority": "; ".join(packet["source_priority"][:3]),
                "required_fields": "; ".join(packet["required_fields"]),
                "status": "unverified",
            }
            task_queue.append(task)
            if packet["kind"] == "person_contact":
                contact_tasks.append(task)

    return {
        "title": f"Pope Ultra - {board.get('title', 'Untitled Board')}",
        "source_board": source_path,
        "source_board_date": board.get("date"),
        "generated_at": now,
        "run_mode": "deterministic_ultra_scaffold",
        "truth_statuses": TRUTH_STATUSES,
        "source_tiers": SOURCE_TIERS,
        "truth_rules": [
            "Do not invent named permits, people, contacts, projects, companies, labs, or amounts.",
            "Unknowns become tasks. Leads become decision-grade only after source verification.",
            "Primary sources outrank polished secondary summaries.",
            "Contact paths must be public business routes from official sources; never infer emails.",
            "A money recommendation needs amount range, unit-cost basis, trigger, next tranche trigger, downside, and kill condition.",
        ],
        "dossiers": dossiers,
        "task_queue": task_queue,
        "contact_tasks": contact_tasks,
    }


def _pct(value: Any) -> str:
    if value is None or value == "":
        return "-"
    try:
        n = float(value)
    except (TypeError, ValueError):
        return str(value)
    if n <= 1:
        n *= 100
    return f"{round(n):.0f}%"


def render_markdown(ultra: dict[str, Any]) -> str:
    lines = [
        f"# {ultra['title']}",
        "",
        f"- Source board: `{ultra['source_board']}`",
        f"- Generated: {ultra['generated_at']}",
        f"- Run mode: `{ultra['run_mode']}`",
        "",
        "## Truth Rules",
        "",
    ]
    lines.extend(f"- {rule}" for rule in ultra["truth_rules"])
    lines.append("")

    for dossier in ultra["dossiers"]:
        claim = dossier["scored_claim"]
        decision = dossier["decision_core"]
        lines.extend(
            [
                f"## {dossier['thesis_id']} - {dossier['headline']}",
                "",
                f"- Domain: {dossier['domain']}",
                f"- Vision P: {_pct(claim.get('vision_p'))}",
                f"- Clause P: {_pct(claim.get('clause_p'))}",
                f"- Resolves: {claim.get('resolves') or '-'}",
                f"- Metric: {claim.get('metric') or '-'}",
                f"- Kill: {claim.get('kill') or '-'}",
                "",
                "### Decision Core",
                "",
                f"- Exposed: {decision.get('exposed') or '-'}",
                f"- Action now: {decision.get('action_now') or '-'}",
                f"- Decision changed: {decision.get('decision_changed') or '-'}",
                f"- ROI logic: {decision.get('roi_logic') or '-'}",
                f"- Watch: {decision.get('watch') or '-'}",
                "",
                "### Layers",
                "",
            ]
        )
        for layer in dossier["layers"]:
            lines.append(f"- **{layer['name']}**: {layer['question']} -> {layer['output']}")
        lines.extend(["", "### Action Axes", ""])
        for axis in dossier["action_axes"]:
            lines.append(f"- **{axis['axis']}**: {axis['question']} -> {axis['ultra_output']}")
        lines.extend(["", "### Execution Packets", ""])
        for packet in dossier["execution_packets"]:
            lines.extend(
                [
                    f"#### {packet['name']}",
                    "",
                    f"- Kind: `{packet['kind']}`",
                    f"- Truth floor: `{packet['truth_floor']}`",
                    f"- Why: {packet['why']}",
                    f"- Deliverable: {packet['deliverable']}",
                    f"- Promotion rule: {packet['promotion_rule']}",
                    "- Seed queries:",
                ]
            )
            lines.extend(f"  - `{q}`" for q in packet["seed_queries"])
            lines.append("- Source priority:")
            lines.extend(f"  - {s}" for s in packet["source_priority"])
            lines.append("- Required fields:")
            lines.extend(f"  - `{f}`" for f in packet["required_fields"])
            lines.append("")
        lines.extend(["### Agent Brief", ""])
        lines.extend(f"- {item}" for item in dossier["agent_brief"])
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(ultra: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ultra.json").write_text(json.dumps(ultra, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    (out_dir / "ultra.md").write_text(render_markdown(ultra), encoding="utf-8")
    _write_csv(out_dir / "task_queue.csv", ultra["task_queue"])
    _write_csv(out_dir / "contacts_seed.csv", ultra["contact_tasks"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile a Pope board into Pope Ultra execution dossiers.")
    parser.add_argument("board", help="Path to Pope board JSON")
    parser.add_argument("--out-dir", help="Output directory. Defaults to <board-stem>.ultra")
    parser.add_argument("--thesis", help="Optional thesis id, e.g. P1")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    board_path = Path(args.board)
    board = json.loads(board_path.read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir) if args.out_dir else board_path.with_suffix(".ultra")
    ultra = build_dossier(board, str(board_path), thesis_filter=args.thesis)
    write_outputs(ultra, out_dir)
    print(f"wrote {out_dir / 'ultra.json'}")
    print(f"wrote {out_dir / 'ultra.md'}")
    print(f"wrote {out_dir / 'task_queue.csv'}")
    if ultra["contact_tasks"]:
        print(f"wrote {out_dir / 'contacts_seed.csv'}")
    print(f"dossiers: {len(ultra['dossiers'])}; tasks: {len(ultra['task_queue'])}")


if __name__ == "__main__":
    main()
