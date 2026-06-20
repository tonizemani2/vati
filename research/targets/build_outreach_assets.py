#!/usr/bin/env python3
"""Build scored outreach exports from targets.json.

Outputs:
  - outreach_universe_scored.csv/json: full list with score, tier, hook, CTA.
  - top_fit_300_messages.csv: Day 0 + Day 3 one-to-one copy for top 300.
  - contactable_messages.csv: one-to-one copy for every usable-contact row.
  - email_ready_messages.csv: rows with a confirmed direct email.
  - email_enrichment_queue.csv: non-email rows with search queries and alt contacts.
  - top_fit_300.md: founder-review shortlist.
  - outreach_operating_plan.md: concrete batching plan.

No sending. Treat every auto-harvested row as verify-before-contact.
"""
import csv
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
TARGETS = HERE / "targets.json"
MESSAGES = ROOT / "outreach_messages.md"

FULL_CSV = HERE / "outreach_universe_scored.csv"
FULL_JSON = HERE / "outreach_universe_scored.json"
TOP_CSV = HERE / "top_fit_300_messages.csv"
CONTACTABLE_CSV = HERE / "contactable_messages.csv"
EMAIL_READY_CSV = HERE / "email_ready_messages.csv"
EMAIL_ENRICH_QUEUE_CSV = HERE / "email_enrichment_queue.csv"
TOP_MD = ROOT / "top_fit_300.md"
PLAN_MD = ROOT / "outreach_operating_plan.md"

RECORD_LINK = "{{record_link}}"
BOOKING_LINK = "{{cal_link}}"


def norm(name: str) -> str:
    n = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    n = re.sub(r"[^a-z0-9 ]", "", n)
    return re.sub(r"\s+", " ", n).strip()


def first_name(name: str) -> str:
    if not name:
        return ""
    return re.split(r"\s+", name.strip())[0].strip(",")


def load_targets() -> list[dict]:
    return json.loads(TARGETS.read_text())


def load_existing_messages() -> dict[str, dict]:
    if not MESSAGES.exists():
        return {}
    text = MESSAGES.read_text()
    out: dict[str, dict] = {}
    for match in re.finditer(r"^##\s+(.+?)\n(.*?)(?=^##\s+|\Z)", text, re.M | re.S):
        heading = match.group(1).strip()
        section = match.group(2)
        name = re.split(r"\s+—\s+", heading)[0].strip()
        code = re.search(r"```(?:[a-zA-Z0-9_-]+)?\n(.*?)```", section, re.S)
        subj = re.search(r"\*\*Subject:\*\*\s*(.+)", section)
        if code:
            out[norm(name)] = {
                "subject": subj.group(1).strip() if subj else "",
                "day0": code.group(1).strip(),
                "message_source": "existing_bespoke",
            }
    return out


SEGMENT_WEIGHT = {
    "benchmark-creator": 24,
    "forecasting-authority": 23,
    "market-insider": 22,
    "forecasting-community": 20,
    "forecasting-org": 20,
    "market-pioneer": 19,
    "applied-ai": 18,
    "academic": 17,
    "researcher": 6,
    "quant": 20,
    "quant-forecasting": 20,
    "quant-fund": 18,
    "prop-trading": 18,
    "macro-familyoffice": 17,
    "asset-manager": 16,
    "risk-reinsurance": 16,
    "corp-foresight": 15,
    "vc-thesis": 15,
    "ai-forecasting-investor": 20,
    "quant-fintech-angel": 18,
    "applied-ai-angel": 16,
    "media-voice": 14,
}

RING_WEIGHT = {
    "advisor": 24,
    "angel": 21,
    "client": 20,
    "client-vc": 18,
    "amplifier": 15,
}

CHANNEL_WEIGHT = {
    "email": 24,
    "x": 18,
    "substack": 15,
    "linkedin": 13,
    "web": 10,
    "orcid": 1,
    "openalex": 0,
}

CONF_WEIGHT = {"high": 25, "med": 11, "low": 2}

SENIOR_RX = re.compile(
    r"\b(founder|co[- ]?founder|partner|principal|chief|cio|cto|ceo|cso|head|director|"
    r"portfolio manager|pm\b|research lead|lead|vp|managing director|general partner|gp)\b",
    re.I,
)

BUYER_RX = re.compile(
    r"\b(research|strategy|macro|risk|foresight|portfolio|quant|trading|investment|"
    r"forecast|scenario|markets|data science)\b",
    re.I,
)


def weak_name(r: dict) -> bool:
    if r.get("tier1"):
        return False
    name = r.get("name", "").strip()
    tokens = [t.strip(" ,") for t in name.split() if t.strip(" ,")]
    full_tokens = []
    for token in tokens:
        clean = re.sub(r"[^A-Za-zÀ-ÿ'-]", "", token)
        if len(clean) > 1:
            full_tokens.append(clean)
    return len(full_tokens) < 2


def score_row(r: dict) -> int:
    role = f"{r.get('role','')} {r.get('profile','')} {r.get('title','')}"
    score = 0
    score += RING_WEIGHT.get(r.get("ring"), 8)
    score += SEGMENT_WEIGHT.get(r.get("segment"), 8)
    score += CHANNEL_WEIGHT.get(r.get("channel"), 6)
    score += CONF_WEIGHT.get(r.get("confidence"), 5)
    if r.get("tier1"):
        score += 65
    if r.get("has_message"):
        score += 20
    if SENIOR_RX.search(role):
        score += 13
    if BUYER_RX.search(role):
        score += 8
    if r.get("contact"):
        score += 5
    if not (r.get("role") or r.get("profile")):
        score -= 14
    if r.get("channel") in {"openalex", "orcid"}:
        score -= 34
    if r.get("segment") == "researcher" and r.get("channel") in {"openalex", "orcid"}:
        score -= 18
    if r.get("confidence") == "low":
        score -= 8
    if weak_name(r):
        score -= 42
    m = re.search(r"(\d+)\s+works", r.get("profile", ""))
    if m:
        score += min(int(m.group(1)), 5)
    return score


def is_contactable(r: dict) -> bool:
    return (
        bool(r.get("contact"))
        and r.get("channel") not in {"openalex", "orcid"}
        and not weak_name(r)
    )


def assign_tiers(rows: list[dict]) -> None:
    personal_rank = 0
    for overall_rank, item in enumerate(rows, 1):
        item["rank"] = overall_rank
        if item.get("tier1"):
            personal_rank += 1
            item["personal_rank"] = personal_rank
            item["priority_tier"] = "P0-founder-1to1"
            continue
        if is_contactable(item):
            personal_rank += 1
            item["personal_rank"] = personal_rank
            if personal_rank <= 75:
                item["priority_tier"] = "P0-founder-1to1"
            elif personal_rank <= 300:
                item["priority_tier"] = "P1-personal-1to1"
            elif personal_rank <= 1000:
                item["priority_tier"] = "P2-enrich-scaled"
            else:
                item["priority_tier"] = "P3-universe-hold"
        else:
            item["personal_rank"] = ""
            item["priority_tier"] = "P2-enrich-scaled" if overall_rank <= 1000 else "P3-universe-hold"


def persona_for(r: dict) -> str:
    ring = r.get("ring")
    seg = r.get("segment")
    if ring in {"angel", "client"} and seg in {"quant-fund", "prop-trading", "macro-familyoffice", "ai-forecasting-investor", "quant-fintech-angel"}:
        return "toni"
    if ring == "amplifier":
        return "vati"
    if seg in {"researcher", "academic", "forecasting-authority", "benchmark-creator", "forecasting-community"}:
        return "linda"
    return "toni"


def hook_for(r: dict) -> str:
    role = (r.get("role") or r.get("profile") or "").strip()
    seg = r.get("segment")
    if seg == "benchmark-creator":
        return "your work shaping forecasting benchmarks"
    if seg in {"forecasting-authority", "forecasting-community", "forecasting-org"}:
        return "your work in calibrated forecasting and judgmental accuracy"
    if seg in {"market-insider", "market-pioneer"}:
        return "your work around prediction markets and public scoring"
    if seg in {"applied-ai", "llm-forecasting"}:
        return "your work on whether AI systems can forecast rather than merely summarize"
    if seg == "researcher":
        m = re.search(r"\((.*?)\)", role)
        if m:
            topics = m.group(1).split(",")[0].strip()
            return f"your published work on {topics}"
        return "your forecasting and decision-science research"
    if seg in {"quant-fund", "prop-trading", "quant", "quant-forecasting"}:
        return "your work where a small information edge has to survive contact with markets"
    if seg == "macro-familyoffice":
        return "your work on macro allocation and forward-looking research"
    if seg == "asset-manager":
        return "your work translating research into investable views"
    if seg == "risk-reinsurance":
        return "your work on emerging risk and scenario discipline"
    if seg == "corp-foresight":
        return "your work on strategy, foresight, and scenario planning"
    if seg == "vc-thesis":
        return "your thesis-driven investing work"
    if seg in {"ai-forecasting-investor", "applied-ai-angel"}:
        return "your AI-native investing work"
    if seg == "quant-fintech-angel":
        return "your quant and fintech investing background"
    if seg == "media-voice":
        return "your writing for people who care about forecasts that can be checked"
    if role:
        return role[:110]
    return "your work in the market Vaticinus is built for"


def angle_for(r: dict) -> str:
    ring = r.get("ring")
    seg = r.get("segment")
    if ring == "advisor":
        return "you can tell whether the method is credible before I ask anyone else to believe it"
    if ring == "client":
        if seg in {"quant-fund", "prop-trading", "macro-familyoffice", "asset-manager"}:
            return "your desk is exactly where a dated edge should either prove useful or die quickly"
        if seg == "risk-reinsurance":
            return "your team lives with the kind of low-frequency, high-impact uncertainty this system is meant to structure"
        return "your team buys forward-looking judgment, not generic AI copy"
    if ring == "client-vc":
        return "you already reason in theses, and Vaticinus is designed to make those theses falsifiable earlier"
    if ring == "angel":
        return "you are close enough to AI, markets, or forecasting to judge the proof without needing a category explained"
    if ring == "amplifier":
        return "your audience is unusually likely to care about a public scored record instead of a private claim"
    return "there is a concrete overlap with the public record I am building"


def cta_for(r: dict) -> str:
    ring = r.get("ring")
    if ring == "advisor":
        return "Would you be open to 20 minutes to poke holes in the method?"
    if ring == "client":
        return f"Would it be worth 15 minutes to pressure-test one live question from your desk? {BOOKING_LINK}"
    if ring == "client-vc":
        return f"Would it be worth 15 minutes to test one thesis area against the record? {BOOKING_LINK}"
    if ring == "angel":
        return "Would you be open to a brief read once the ablation and benchmark result are live?"
    if ring == "amplifier":
        return "Can I send you the scored record when the benchmark result lands?"
    return "Would a short conversation be useful?"


def subject_for(r: dict) -> str:
    ring = r.get("ring")
    seg = r.get("segment")
    if ring == "advisor":
        return "Vaticinus methodology, honest fit check"
    if ring == "client":
        if seg in {"quant-fund", "prop-trading", "macro-familyoffice", "asset-manager"}:
            return "Scored forecasting record for your research desk"
        return "Dated forecasts for strategic uncertainty"
    if ring == "client-vc":
        return "Making thesis risk falsifiable earlier"
    if ring == "angel":
        return "AI forecasting system with public scored proof"
    if ring == "amplifier":
        return "Public Brier-scored AI forecasting record"
    return "Vaticinus fit check"


def generated_day0(r: dict) -> str:
    first = first_name(r.get("name", ""))
    hook = hook_for(r)
    angle = angle_for(r)
    cta = cta_for(r)
    return (
        f"Hi {first},\n\n"
        f"I found you through {hook}. I am building Vaticinus, a solo forecasting system with a public, dated, Brier-scored record. "
        f"The reason I am reaching out to you specifically is that {angle}.\n\n"
        f"I am using the current ablation and ForecastBench result as the proof gate before broader outreach. "
        f"{cta} {RECORD_LINK}\n\n"
        "Toni Zemani"
    )


def generated_day3(r: dict) -> str:
    first = first_name(r.get("name", ""))
    ring = r.get("ring")
    if ring in {"client", "client-vc"}:
        return (
            f"{first}, short nudge. If you have one unresolved market, strategy, or constraint question, "
            "I can pressure-test it against the dated record first. If it does not earn time, no call needed."
        )
    if ring == "amplifier":
        return (
            f"{first}, short nudge. The useful question is whether a public scored record is worth a look "
            "for your audience. If not, a quick pass is completely fine."
        )
    return (
        f"{first}, short nudge. The useful question is not whether this sounds interesting, "
        "it is whether the dated record clears your bar. If no, a quick pass is completely fine."
    )


def enrich(rows: list[dict]) -> list[dict]:
    existing = load_existing_messages()
    enriched = []
    for r in rows:
        item = dict(r)
        item["fit_score"] = score_row(item)
        item["persona"] = persona_for(item)
        item["specific_hook"] = hook_for(item)
        item["fit_reason"] = angle_for(item)
        item["cta"] = cta_for(item)
        item["subject"] = subject_for(item)
        msg = existing.get(norm(item.get("name", "")))
        if msg:
            item["message_source"] = msg["message_source"]
            item["subject"] = msg["subject"] or item["subject"]
            item["day0"] = msg["day0"]
        else:
            item["message_source"] = "generated_from_profile_fields"
            item["day0"] = generated_day0(item)
        item["day3"] = generated_day3(item)
        if item.get("channel") == "email" and item.get("contact"):
            item["to_email"] = item["contact"]
            item["email_status"] = "confirmed_existing"
        else:
            item["to_email"] = ""
            item["email_status"] = "needs_email_enrichment"
        item["alternate_contact"] = item.get("contact", "")
        item["email_search_query"] = (
            f'"{item.get("name", "")}" email {item.get("role") or item.get("segment") or ""}'
        ).strip()
        item["send_status"] = "hold_verify_then_send"
        enriched.append(item)
    enriched.sort(key=lambda x: (x["fit_score"], bool(x.get("tier1"))), reverse=True)
    assign_tiers(enriched)
    return enriched


FIELDS = [
    "rank", "personal_rank", "priority_tier", "fit_score", "name", "ring", "segment", "persona",
    "role", "profile", "channel", "contact", "to_email", "email_status", "alternate_contact",
    "email_search_query", "confidence", "specific_hook",
    "fit_reason", "cta", "subject", "message_source", "day0", "day3",
    "source", "query", "send_status",
]


def write_csv(path: Path, rows: list[dict], fields: list[str] = FIELDS) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_top_md(rows: list[dict]) -> None:
    top = [r for r in rows if r["priority_tier"] in {"P0-founder-1to1", "P1-personal-1to1"}][:300]
    lines = [
        "# Top 300 Vaticinus Outreach Targets",
        "",
        "Generated from `research/targets/targets.json`. `P0` is founder-led and manual. `P1` is one-to-one, review-before-send. Do not send any generated copy before verifying role/contact and replacing placeholders.",
        "",
        "| Rank | Name | Tier | Ring | Segment | Score | Channel | Hook |",
        "|---:|---|---|---|---|---:|---|---|",
    ]
    for r in top:
        hook = (r.get("specific_hook") or "").replace("|", "/")
        lines.append(
            f"| {r['rank']} | {r.get('name','')} | {r.get('priority_tier','')} | "
            f"{r.get('ring','')} | {r.get('segment','')} | {r.get('fit_score','')} | "
            f"{r.get('channel','')} | {hook} |"
        )
    TOP_MD.write_text("\n".join(lines) + "\n")


def write_plan(rows: list[dict]) -> None:
    counts = Counter(r["priority_tier"] for r in rows)
    rings = Counter(r.get("ring", "") for r in rows)
    channels = Counter(r.get("channel", "") for r in rows)
    high = sum(1 for r in rows if r.get("confidence") == "high")
    contactable = [r for r in rows if is_contactable(r)]
    direct_email = [r for r in rows if r.get("to_email")]
    p0 = [r for r in rows if r["priority_tier"] == "P0-founder-1to1"]
    p1 = [r for r in rows if r["priority_tier"] == "P1-personal-1to1"]
    lines = [
        "# Vaticinus Outreach Operating Plan",
        "",
        f"Generated target universe: **{len(rows)} people**.",
        f"High-confidence rows: **{high}**.",
        f"Contactable rows with one-to-one copy: **{len(contactable)}**.",
        f"Direct-email rows before enrichment: **{len(direct_email)}**.",
        "",
        "## Tiers",
        "",
        f"- **P0 founder 1-to-1:** {counts['P0-founder-1to1']} people. Manual send only. Use existing bespoke messages when available, otherwise rewrite the generated copy by hand.",
        f"- **P1 personal 1-to-1:** {counts['P1-personal-1to1']} people. Personal message per person, reviewed in batches of 25.",
        f"- **P2 enrich scaled:** {counts['P2-enrich-scaled']} people. Enrich role/work email or social channel, then send through low-volume campaigns once inboxes are warm.",
        f"- **P3 universe hold:** {counts['P3-universe-hold']} people. Keep for later expansion, retargeting, and network mapping.",
        "",
        "## Ring Mix",
        "",
    ]
    for key, val in rings.most_common():
        lines.append(f"- {key}: {val}")
    lines += ["", "## Channel Mix", ""]
    for key, val in channels.most_common():
        lines.append(f"- {key}: {val}")
    lines += [
        "",
        "## First 2 Weeks",
        "",
        "1. Day 0: review P0 top 25 by hand, verify contact, replace placeholders, send manually from founder identity.",
        "2. Day 1: review next P0 25. Do not touch P1 until P0 has a response-tracking sheet.",
        "3. Day 3: send same-thread nudges only to non-responders where the first message was manual and verified.",
        "4. Days 4-7: start P1 in batches of 25. Keep advisor/angel rows manual; client rows can move to staged sending only after enrichment.",
        "5. Week 2: enrich P2 for usable work emails, dedupe against responders, then promote the best 100 into P1.",
        "",
        "## Quality Gates",
        "",
        "- Never send rows with `openalex` or `orcid` contact until a real website/email/social channel is found.",
        "- Do not send generated copy as-is to marquee people. Use it as scaffolding and add one concrete sentence from their work.",
        "- Keep all cold sending below warmup limits. The list is the asset; replies are the constraint.",
        "- Replace `{{record_link}}` and `{{cal_link}}` only after the ablation and ForecastBench proof are live.",
        "",
        "## Current Top Names",
        "",
    ]
    for r in (p0 + p1)[:40]:
        lines.append(
            f"- #{r['rank']} {r.get('name')} ({r.get('ring')}/{r.get('segment')}, "
            f"{r.get('channel')}, score {r.get('fit_score')})"
        )
    PLAN_MD.write_text("\n".join(lines) + "\n")


def main() -> None:
    rows = enrich(load_targets())
    top_messages = [r for r in rows if r["priority_tier"] in {"P0-founder-1to1", "P1-personal-1to1"}][:300]
    contactable_messages = [r for r in rows if is_contactable(r)]
    email_ready_messages = [r for r in contactable_messages if r.get("to_email")]
    email_enrich_queue = [r for r in contactable_messages if not r.get("to_email")]
    FULL_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    write_csv(FULL_CSV, rows)
    write_csv(TOP_CSV, top_messages)
    write_csv(CONTACTABLE_CSV, contactable_messages)
    write_csv(EMAIL_READY_CSV, email_ready_messages)
    write_csv(EMAIL_ENRICH_QUEUE_CSV, email_enrich_queue)
    write_top_md(rows)
    write_plan(rows)
    print(f"TOTAL {len(rows)}")
    print("tiers:", dict(Counter(r["priority_tier"] for r in rows)))
    print("rings:", dict(Counter(r.get("ring", "") for r in rows)))
    print(f"wrote {FULL_CSV}")
    print(f"wrote {TOP_CSV}")
    print(f"wrote {CONTACTABLE_CSV}")
    print(f"wrote {EMAIL_READY_CSV}")
    print(f"wrote {EMAIL_ENRICH_QUEUE_CSV}")
    print(f"wrote {TOP_MD}")
    print(f"wrote {PLAN_MD}")


if __name__ == "__main__":
    main()
