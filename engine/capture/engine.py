"""The capture engine — discover, qualify, synthesize, classify. DeepSeek-driven.

Every model call is DeepSeek via engine.adapters.llm (keyed, cost-gated, cents). The in-session
model (Opus) does NOT run here — it rates the output in the chat loop and feeds revision notes
back into synth_play(revision_note=...). Discovery is keyless Exa ($0).

Voice: Toni Zemani, evidence-first, give-before-take, never needy, NO em dashes (scrubbed).
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date

from engine.adapters import llm, search
from engine.capture.schema import Play, PlayBrief, Target, TreeNode

# DeepSeek models: flash for bulk extraction/qualify, pro (reasoner) for the synth that needs
# real-world judgment (the opener + the tree). max_tokens high enough that JSON never truncates.
_FLASH = "deepseek-v4-flash"
_PRO = "deepseek-v4-pro"

_VOICE = (
    "You write as Toni Zemani, founder of Vaticinus, an honest leak-free forecasting shop. "
    "Voice: specific, evidence-first, peer-to-peer, never needy, never salesy. You give before "
    "you take. You never ask for money or a meeting in a first touch. You sound like a sharp "
    "operator who already has an edge, not a vendor. ABSOLUTE RULE: never use em dashes or en "
    "dashes; use commas, periods, or parentheses. No corporate filler, no AI-scented phrasing "
    "(no 'I hope this finds you well', no 'I wanted to reach out', no 'leverage/synergy/excited')."
)


def _scrub(s: str) -> str:
    """Kill the AI tells we forbid: em/en dashes -> commas."""
    return s.replace(" — ", ", ").replace("—", ", ").replace("–", "-") if s else s


def _balanced_objects(s: str, start: int = 0):
    """Yield every brace-balanced {...} block at/after `start`, string- and escape-aware.
    Used to salvage a list of records when the wrapper JSON is malformed by one bad row."""
    i, n = start, len(s)
    while i < n:
        if s[i] != "{":
            i += 1
            continue
        depth, j, in_str, esc = 0, i, False, False
        while j < n:
            c = s[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        yield s[i:j + 1]
                        break
            j += 1
        i = j + 1


def _salvage_list(raw: str, key: str) -> dict:
    """Parse the records inside {"<key>":[...]} one by one, dropping any that don't parse."""
    arr = raw.find("[")
    items = []
    for blk in _balanced_objects(raw, arr if arr >= 0 else 0):
        try:
            items.append(json.loads(blk))
        except json.JSONDecodeError:
            continue
    return {key: items}


def _json(conn: sqlite3.Connection, prompt: str, *, model: str, system: str | None = None,
          max_tokens: int = 4000, est_cents: int = 1, list_key: str | None = None):
    """One DeepSeek call that must return JSON. Tolerant parse (strips ``` fences); if the whole
    document is malformed and `list_key` is set, salvage the well-formed records inside it."""
    raw = llm.complete(
        conn, prompt, provider="deepseek", model=model, system=system,
        max_tokens=max_tokens, est_cost_cents=est_cents,
        extra_body={"response_format": {"type": "json_object"}},
    )
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        if list_key:
            return _salvage_list(raw, list_key)
        # single-object shape: take the first balanced {...}
        for blk in _balanced_objects(raw):
            try:
                return json.loads(blk)
            except json.JSONDecodeError:
                continue
        # nothing balanced => truncated mid-document; best-effort close and parse
        return json.loads(_close_truncated(raw[raw.find("{"):]))


def _close_truncated(s: str) -> str:
    """Best-effort repair of a truncated JSON object: shut the open string + brackets."""
    stack, in_str, esc = [], False, False
    for c in s:
        if in_str:
            esc = (c == "\\") and not esc
            if c == '"' and not esc:
                in_str = False
        elif c == '"':
            in_str = True
        elif c in "{[":
            stack.append(c)
        elif c == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif c == "]" and stack and stack[-1] == "[":
            stack.pop()
    out = s.rstrip().rstrip(",")
    if in_str:
        out += '"'
    out += "".join("}" if b == "{" else "]" for b in reversed(stack))
    return out


# --- 1. discover ----------------------------------------------------------------------

def discover(conn: sqlite3.Connection, brief: PlayBrief, per_query: int = 8) -> list[Target]:
    """Keyless Exa over the brief's queries, then DeepSeek extracts structured target
    entities from the hits. Web discovery is noisy by design; qualify() and the rater prune."""
    hits = search.search_multi(conn, brief.discovery_queries, num_results=per_query)
    # flatten to a compact corpus the extractor can read
    lines = []
    for q, results in hits.items():
        for r in results:
            lines.append(f"- [{r.title}]({r.url}) :: {r.snippet}")
    corpus = "\n".join(lines[:120]) or "(no results)"

    prompt = (
        f"We are running a capture play.\n"
        f"OBJECTIVE: {brief.objective}\n"
        f"WHO WE WANT (target criteria): {brief.target_criteria}\n"
        f"WHAT WE WANT FROM THEM: proprietary data/access at this bottleneck.\n\n"
        f"Below are raw web search results. Extract up to 12 DISTINCT real target entities "
        f"(a named person, or a specific org + the role we'd contact) that plausibly sit at "
        f"this bottleneck and hold data worth bartering for. Skip generic listicles, news "
        f"aggregators, and giant household names that would never reply.\n\n"
        f"Return JSON: {{\"targets\": [{{\"name\":..., \"org\":..., \"role\":..., \"url\":..., "
        f"\"why_them\": <one line: why this node holds the constraint/data>, "
        f"\"what_they_have\": <the specific proprietary data/access>, "
        f"\"reachability\": <public email/handle/path if visible, else 'unknown'>}}]}}\n\n"
        f"SEARCH RESULTS:\n{corpus}"
    )
    data = _json(conn, prompt, model=_FLASH, max_tokens=4000, list_key="targets")
    out = []
    for t in data.get("targets", [])[:12]:
        out.append(Target(
            name=_scrub(t.get("name", "").strip()), org=_scrub(t.get("org", "").strip()),
            role=_scrub(t.get("role", "")), url=t.get("url", ""),
            why_them=_scrub(t.get("why_them", "")), what_they_have=_scrub(t.get("what_they_have", "")),
            reachability=t.get("reachability", "unknown"),
        ))
    return [t for t in out if t.name or t.org]


# --- 2. qualify -----------------------------------------------------------------------

def qualify(conn: sqlite3.Connection, brief: PlayBrief, targets: list[Target]) -> list[Target]:
    """DeepSeek scores each target on fit / leverage / warm-path / reach-ease (0-10).
    Blended score ranks them; the rater can override. This is the 'exactly-right, not spam' gate."""
    payload = [{"i": i, "name": t.name, "org": t.org, "role": t.role,
                "why_them": t.why_them, "what_they_have": t.what_they_have,
                "reachability": t.reachability} for i, t in enumerate(targets)]
    prompt = (
        f"OBJECTIVE: {brief.objective}\nTARGET CRITERIA: {brief.target_criteria}\n\n"
        f"Score each candidate 0-10 on:\n"
        f"- fit: do they actually sit at THIS bottleneck and hold the data we want?\n"
        f"- leverage: door + credibility + capital combined (not just one)\n"
        f"- warm_path: 10 = warm/second-degree reachable, 0 = stone cold\n"
        f"- reach_ease: how findable/contactable (10 = public email, 0 = unknown)\n\n"
        f"Be harsh. A 7+ fit should be rare. Return JSON: {{\"scores\": [{{\"i\":int, "
        f"\"fit\":int, \"leverage\":int, \"warm_path\":int, \"reach_ease\":int}}]}}\n\n"
        f"CANDIDATES:\n{json.dumps(payload, ensure_ascii=False)}"
    )
    data = _json(conn, prompt, model=_FLASH, max_tokens=3000, list_key="scores")
    by_i = {s["i"]: s for s in data.get("scores", [])}
    for i, t in enumerate(targets):
        s = by_i.get(i, {})
        t.fit = int(s.get("fit", 0)); t.leverage = int(s.get("leverage", 0))
        t.warm_path = int(s.get("warm_path", 0)); t.reach_ease = int(s.get("reach_ease", 0))
        # fit is the gate; leverage + reachability shape the rank
        t.score = round(t.fit * 0.5 + t.leverage * 0.25 + t.reach_ease * 0.15 + t.warm_path * 0.1, 2)
    return sorted(targets, key=lambda x: x.score, reverse=True)


# --- 3. synthesize the play (opener + tree) -------------------------------------------

def synth_play(conn: sqlite3.Connection, brief: PlayBrief, target: Target,
               revision_note: str | None = None) -> Play:
    """DeepSeek (pro/reasoner) drafts the hook, the opener, and a 2-3 deep decision tree.
    Pass revision_note to fold the rater's feedback into a sharper second attempt."""
    rev = f"\n\nREVISION NOTES FROM THE EDITOR (fix these specifically):\n{revision_note}\n" if revision_note else ""
    prompt = (
        f"Build a capture play for ONE target. Today is {date.today().isoformat()} (every timeframe "
        f"you mention must be in the FUTURE relative to today). Capture ladder rung {brief.rung} "
        f"(be early + useful, NEVER ask for money or a meeting in a first touch).\n\n"
        f"=== HONESTY RAILS (non-negotiable; our entire brand is leak-free honesty) ===\n"
        f"- Use ONLY facts given to you below. Invent NOTHING.\n"
        f"- NEVER fabricate: a Brier score, a number of prior calls, a specific past prediction, a "
        f"personal bio or employer, or any named third party who 'validated' us.\n"
        f"- Do NOT invent the forecast's numbers. Reference the real call by what is provided and "
        f"point to the public board via the literal token {{record_link}} for the dated, scored proof. "
        f"If you have no exact figure, describe the call qualitatively, never with a made-up %.\n"
        f"- The record speaks for itself; we describe it as 'publicly logged, dated, Brier-scored', "
        f"not with invented metrics. A fabricated proof is an instant trust-destroyer.\n\n"
        f"OBJECTIVE: {brief.objective}\n"
        f"THE LIVE FORECAST WE RIDE ON (reference it, do not embellish it): {brief.linked_forecast}\n"
        f"WHAT WE GIVE BEFORE WE TAKE: {brief.value_hook}\n\n"
        f"TARGET: {target.name} | {target.org} | {target.role}\n"
        f"WHY THEM: {target.why_them}\n"
        f"WHAT THEY HAVE WE WANT: {target.what_they_have}\n\n"
        f"Produce:\n"
        f"1. hook: the single specific, honest, valuable thing we lead with, drawn ONLY from the live "
        f"forecast above. One or two sentences.\n"
        f"2. opener: the first message (<=110 words). Lead with the real insight, not a greeting. "
        f"GIVE pure value (offer the full dated read at {{record_link}}); do NOT propose a data trade "
        f"in this first touch and do NOT ask for a meeting. End with a low-friction, generous open "
        f"(invite them to compare it against their own view).\n"
        f"3. tree: a decision tree of likely replies, 2-3 levels deep. Model how a REAL analyst at "
        f"this desk reacts (interested / skeptical / 'who are you' / 'send it' / silence). The barter "
        f"(their data for our forward calls) only surfaces AFTER they engage, never in the opener. "
        f"our_move = the exact next thing we send, honest and non-needy throughout.\n\n"
        f"Return JSON: {{\"hook\":..., \"opener\":..., \"channel\": \"email\", "
        f"\"tree\": [{{\"reply_type\":..., \"our_move\":..., \"children\":[{{\"reply_type\":..., "
        f"\"our_move\":..., \"children\":[]}}]}}]}}{rev}"
    )
    data = _json(conn, prompt, model=_PRO, system=_VOICE, max_tokens=9000, est_cents=2)
    return Play(
        target=target, rung=brief.rung,
        hook=_scrub(data.get("hook", "")), opener=_scrub(data.get("opener", "")),
        channel=data.get("channel", "email"),
        tree=[_node(n) for n in data.get("tree", [])],
    )


def _node(d: dict) -> TreeNode:
    return TreeNode(reply_type=_scrub(d.get("reply_type", "")), our_move=_scrub(d.get("our_move", "")),
                    children=[_node(c) for c in d.get("children", [])])


# --- 4. classify a real reply into a tree branch (inbox phase-2 hook) -----------------

def classify_reply(conn: sqlite3.Connection, play: Play, reply_text: str) -> dict:
    """Given a real inbound reply, pick the matching tree branch + the queued move.
    Lets the tree drive a live conversation once an inbox is wired (not wired yet)."""
    branches = [{"idx": i, "reply_type": n.reply_type, "our_move": n.our_move}
                for i, n in enumerate(play.tree)]
    prompt = (
        f"Our opener to {play.target.name} was:\n{play.opener}\n\n"
        f"They replied:\n\"\"\"{reply_text}\"\"\"\n\n"
        f"Which anticipated branch fits best? If none fit, say so and propose a fresh move.\n"
        f"Branches: {json.dumps(branches, ensure_ascii=False)}\n\n"
        f"Return JSON: {{\"branch_idx\": int or -1, \"confidence\": 0-1, "
        f"\"recommended_move\": <what to send next, in Toni voice>}}"
    )
    data = _json(conn, prompt, model=_PRO, system=_VOICE, max_tokens=8000, est_cents=1)
    data["recommended_move"] = _scrub(data.get("recommended_move", ""))
    return data
