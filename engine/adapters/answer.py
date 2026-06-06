"""Keyless agentic 'hard number' finder — multi-step when needed, single-step when not.

For SPECIFIC, settled, non-interpretive figures only: a spec, a capacity, a published count — the kind
of number that is "not up to interpretation" (Ruben's framing). NOT for forecasts, consensus, or
opinion — that reasoning stays Claude's, in-session (CLAUDE.md). This is a *lookup*, never a judge.

The loop: it searches, then the keyless LLM decides one action per step — ANSWER (it found the value),
SEARCH (reformulate and look again), or FETCH (drill into one promising source in full, incl. PDFs).
It stops the instant it can answer, so an easy question costs one round; a hard one (number buried in a
spec table or datasheet PDF) gets a few rounds. Bounded by `max_steps`. Every external call is keyless,
$0, and on the cost ledger (rule 3).

Two honesty rails, unchanged: the source URL is ALWAYS returned so the human can verify, and on no
answer / LLM down it degrades to the raw hits — it never fabricates a number.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
import urllib.request
from dataclasses import dataclass, field

from engine import cost
from engine.adapters import llm, pdf_to_text
from engine.adapters.html_to_markdown import html_to_markdown
from engine.adapters.search import search

UA = "predictthefuture research (ruben.stout@edu.escp.eu)"

_SYSTEM = (
    "You are a precise fact-lookup agent finding ONE specific factual value (a number/spec/date). "
    "You work in steps. Each step, given the evidence so far, output STRICT JSON with one action:\n"
    '  {"action":"answer","value":"<value with unit>","source_url":"<url>","confidence":"high|medium|low","quote":"<the exact sentence/row from the evidence containing the value>","note":"<brief>"}\n'
    '  {"action":"search","query":"<a refined web query>"}  — use when results are off-target\n'
    '  {"action":"fetch","url":"<one url from the evidence>"}  — use when a result (datasheet/spec page/PDF) likely STATES the value but the snippet does not show it\n'
    "CRITICAL HONESTY RULE: answer ONLY by copying a value that LITERALLY APPEARS in the EVIDENCE text "
    "above, and you must put that exact source line in 'quote'. You are FORBIDDEN from using your own "
    "prior/background knowledge. If the value is not literally present in the evidence (page empty, "
    "garbled/binary, or simply doesn't contain it), you may NOT answer it from memory — instead FETCH "
    "another source, SEARCH a sharper query (add 'specification'/'datasheet'/'rated'/units), or, when out "
    'of steps or sure it is unfindable, answer with value "NOT_FOUND". A confident-sounding number you '
    "cannot quote from the evidence is a FAILURE, not an answer."
)


@dataclass
class Answer:
    question: str
    value: str | None          # the extracted figure (with unit), or None if not found
    source_url: str | None     # the page the value came from — always set when a hit exists
    confidence: str            # high | medium | low | none (self-reported by the extractor)
    note: str
    steps: int = 0             # how many rounds it took (1 = single-pass)
    hits: list = field(default_factory=list)  # all SearchResults consulted (for verification)


def _extract_json(raw: str) -> dict | None:
    """Pull the first JSON object out of an LLM reply (tolerates code fences / prose around it)."""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _relevant_excerpt(text: str, question: str, *, budget: int = 4500) -> str:
    """Return the lines of `text` most relevant to `question` (term overlap + numbers), windowed.

    A datasheet's spec table sits deep in the doc, so naive head-truncation hides the very number we
    want — and feeding it to the LLM invites a memorized (parametric) guess. This surfaces the rows that
    actually contain the answer: score each non-empty line by how many question terms it shares + a bonus
    for containing a digit, keep a small window around the top lines (in original order), capped to budget.
    Falls back to the head if nothing scores (so an empty match never starves the model into guessing)."""
    terms = {w for w in re.findall(r"[a-z0-9]{3,}", question.lower())}
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""
    scored = []
    for i, ln in enumerate(lines):
        low = ln.lower()
        score = sum(1 for t in terms if t in low) + (0.5 if re.search(r"\d", ln) else 0.0)
        if score > 0:
            scored.append((score, i))
    if not scored:
        return text[:budget]
    # spend the budget on the HIGHEST-scoring lines first (with a ±1 window), so a deep spec row isn't
    # cut by budget filled with earlier, lower-value lines — then emit in document order for readability.
    keep: set[int] = set()
    used = 0
    for _, i in sorted(scored, reverse=True):
        for j in (i - 1, i, i + 1):
            if 0 <= j < len(lines) and j not in keep:
                keep.add(j)
                used += len(lines[j]) + 1
        if used > budget:
            break
    out, last = [], -2
    for j in sorted(keep):
        if j != last + 1:
            out.append("…")
        out.append(lines[j])
        last = j
    return "\n".join(out)[:budget]


def _fetch_full(conn: sqlite3.Connection, url: str, question: str, *, budget: int = 4500) -> str:
    """Keyless full read of one URL, returned as the excerpt most relevant to `question`. $0, gated.

    Downloads once and sniffs the bytes: a `%PDF` header routes through poppler `pdftotext -layout`
    (keeps spec-table columns); otherwise trafilatura main-content, with a tag-stripped raw-text
    fallback when the page is mostly a table (trafilatura drops tables — where specs often live).
    The full text is then relevance-filtered to `question` so the answer-bearing row is actually shown
    (not buried past a head-truncation, which is what tempts a memorized guess)."""
    cost.gate(conn, action="answer_fetch", provider="web", units=1, est_cost_cents=0)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        raw = urllib.request.urlopen(req, timeout=20).read()  # noqa: S310 keyless public URL
    except Exception:  # noqa: BLE001 — unreachable/blocked: caller treats empty as "no new evidence"
        return ""
    if raw[:5] == b"%PDF":
        if not pdf_to_text.available():
            return ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                f.write(raw)
                f.flush()
                full = pdf_to_text.pdf_to_text(f.name, layout=True)
        except Exception:  # noqa: BLE001
            return ""
        return _relevant_excerpt(full, question, budget=budget)
    html = raw.decode("utf-8", "replace")
    md = html_to_markdown(html) or ""
    if len(md) < 300:  # table-heavy/JS page: add a crude tag-stripped fallback so table numbers survive
        stripped = re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html))
        md = (md + "\n" + re.sub(r"\s+", " ", stripped)).strip()
    return _relevant_excerpt(md, question, budget=budget)


def _decide(conn: sqlite3.Connection, question: str, evidence: list[str], step: int,
            max_steps: int, proxy: str | None) -> dict | None:
    """Ask the keyless LLM for the next action. None if it is down / unparseable."""
    budget = f"(step {step}/{max_steps}; {max_steps - step} left — if 0 left you MUST answer or NOT_FOUND)"
    prompt = f"QUESTION: {question}\n\nEVIDENCE SO FAR:\n" + "\n\n".join(evidence) + f"\n\n{budget}"
    try:
        raw = llm.complete(conn, prompt, system=_SYSTEM, max_tokens=400, proxy=proxy)
    except Exception:  # noqa: BLE001 — keyless roster offline: caller degrades to hits
        return None
    return _extract_json(raw)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _grounded(value: str, quote: str, evidence: str) -> bool:
    """True iff the answer is literally present in the fetched evidence (anti-parametric-leakage check).

    Compares alphanumeric-normalized strings so '700 W' matches '700W'. Requires the VALUE (or the
    model's quoted source line) to actually appear in the text we read — a number the model 'knows' but
    cannot quote from a source is rejected as a memorized guess, not an answer."""
    ev = _norm(evidence)
    for cand in (value, quote):
        n = _norm(cand)
        if len(n) >= 2 and n in ev:
            return True
    return False


def find_number(conn: sqlite3.Connection, question: str, *, max_steps: int = 3, num_results: int = 6,
                proxy: str | None = None, log=print) -> Answer:
    """Look up one specific number for `question`, cited to its source. Agentic, keyless, $0.

    Seeds with a search on the raw question, then lets the LLM SEARCH / FETCH / ANSWER until it has the
    value or `max_steps` is spent (`max_steps=1` forces a single pass). An answer is accepted only if it
    is GROUNDED — the value literally appears in the evidence read; an ungrounded (memorized) guess is
    rejected and the next unread source is drilled instead. Always returns a source URL; degrades to the
    raw hits (value=None) when the LLM is unavailable or nothing states the value.
    """
    evidence: list[str] = []
    hits_all: list = []
    fetched: set[str] = set()
    pending: tuple[str, str] = ("search", question)

    def _next_unfetched() -> str | None:
        return next((r.url for r in hits_all if r.url not in fetched), None)

    for step in range(1, max_steps + 1):
        kind, arg = pending
        if kind == "search":
            results = search(conn, arg, num_results)
            hits_all += results
            log(f"  step {step}: search {arg!r} → {len(results)} hits")
            evidence.append(f"SEARCH RESULTS for {arg!r}:\n" + "\n".join(
                f"- {r.url} :: {(r.snippet or r.title or '')[:280]}" for r in results))
        elif kind == "fetch":
            log(f"  step {step}: fetch {arg}")
            fetched.add(arg)
            text = _fetch_full(conn, arg, question)
            evidence.append(f"FETCHED {arg}:\n{text or '(empty / unreachable)'}")
        else:
            break  # malformed action

        decision = _decide(conn, question, evidence, step, max_steps, proxy)
        if decision is None:
            return Answer(question, None, hits_all[0].url if hits_all else None, "low",
                          "keyless LLM unavailable / unparseable; returning top hits", step, hits_all)
        action = (decision.get("action") or "").lower()

        if action == "answer":
            value = (decision.get("value") or "").strip()
            quote = decision.get("quote") or ""
            src = decision.get("source_url") or (hits_all[0].url if hits_all else None)
            if not value or value.upper() == "NOT_FOUND":
                return Answer(question, None, src, "none",
                              decision.get("note") or "no source stated the value", step, hits_all)
            if _grounded(value, quote, "\n".join(evidence)):
                note = f'“{quote.strip()}”' if quote else (decision.get("note") or "")
                return Answer(question, value, src, (decision.get("confidence") or "low").lower(),
                              note, step, hits_all)
            # ungrounded → a memorized guess. Don't trust it; drill the next unread source if any left.
            log(f"  step {step}: REJECTED ungrounded answer {value!r} (not in evidence — memory guess)")
            nxt = _next_unfetched()
            if nxt and step < max_steps:
                evidence.append(f"REJECTED prior answer {value!r}: NOT found in evidence — do not answer "
                                f"from memory; ground it in a source.")
                pending = ("fetch", nxt)
                continue
            return Answer(question, None, src, "none",
                          f"model proposed {value!r} but it was not present in any fetched source "
                          f"(likely from memory) — not trusted", step, hits_all)

        nxt = decision.get("query") if action == "search" else decision.get("url")
        if action not in ("search", "fetch") or not nxt:
            break  # malformed → stop and degrade
        pending = (action, nxt)

    return Answer(question, None, hits_all[0].url if hits_all else None, "none",
                  f"no value found in {max_steps} steps; returning top hits for manual read",
                  max_steps, hits_all)
