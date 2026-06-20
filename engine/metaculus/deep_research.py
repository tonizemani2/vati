"""Deep agentic research — the lever that separates top bots (Mantic/AIA) from snippet-scrapers.

A single keyless snippet pass (research.gather) is shallow. The winning shape is an AGENTIC loop:
decompose the question into angles, READ the live web per angle (full page text, not a 300-char
teaser), notice what's still missing, search again, then hand the forecaster a dated evidence DOSSIER
(raw extracted facts, never a probability — the forecaster still reasons, so independent skill lives).

Cost-shaped so Opus only does what justifies it:
  Opus     — decompose into research angles + gap-analysis (high-value reasoning)
  Exa      — keyless ($0) web search returning full indexed page TEXT
  DeepSeek — cheap reader: extract the dated decision-relevant facts from each angle's pages

Flow:  question → Opus drafts N angles → Exa reads each (full text) → DeepSeek extracts facts (∥) →
       Opus names the 2-3 missing facts → Exa+DeepSeek fill them (∥) → assemble dated dossier + URLs.
"""
from __future__ import annotations

import concurrent.futures as cf
import re

from engine import db
from engine.adapters import llm, search

OPUS = "us.anthropic.claude-opus-4-8"
# Fact-extractor. Cost is no-object (Ruben 2026-06-16) → Opus on Bedrock for max-faithful extraction,
# no DeepSeek. Whole deep loop is now Opus/Bedrock end-to-end (the cron can't use the interactive sub).
READER = ("bedrock", OPUS)

_DECOMPOSE_SYS = (
    "You plan the research for a forecasting question. Output 4-6 specific, decision-relevant research "
    "questions (one per line, no numbering) that, answered with CURRENT facts, would let a "
    "superforecaster set a calibrated probability. Cover: (a) the latest status/news, (b) the exact "
    "actors/numbers/thresholds in the resolution criteria, (c) base rate / historical precedent, "
    "(d) the strongest concrete driver toward YES, (e) the strongest toward NO. Be concrete, not vague."
)
_GAP_SYS = (
    "You are auditing partial research for a forecast. Given the question and what was found so far, "
    "name the 2-3 MOST decision-relevant facts that are still missing, uncertain, or out of date. "
    "Output them as specific follow-up research questions, one per line, no numbering."
)
_READER_SYS = (
    "Extract decision-relevant facts from the web excerpts for the research question. Output 3-6 "
    "bullet points, each a SPECIFIC, DATED fact or number, with its source URL in parentheses. Use "
    "ONLY facts present in the excerpts; prefer the most recent. If nothing relevant, output exactly "
    "'NOTHING RELEVANT'."
)


def _lines(txt: str, k: int) -> list[str]:
    out = [re.sub(r'^[\s\-\d\.\)"*]+', "", ln).strip().strip('"') for ln in (txt or "").splitlines()]
    return [x for x in out if len(x) > 10][:k]


def _orch_model(provider: str, model: str | None) -> str | None:
    if model:
        return model
    return OPUS if provider == "bedrock" else None  # keyed/free providers pick their own roster


def _decompose(conn, q, today, provider, model, breadth) -> list[str]:
    prompt = (f"Today is {today}.\nQuestion: {q['title']}\n"
              f"Resolution criteria: {(q.get('resolution_criteria') or '')[:700]}\n"
              f"Background: {(q.get('description') or '')[:400]}\n\nWrite the research questions.")
    try:
        txt = llm.complete(conn, prompt, provider=provider, model=_orch_model(provider, model),
                           system=_DECOMPOSE_SYS, max_tokens=400, est_cost_cents=5)
    except Exception:
        txt = ""
    return _lines(txt, breadth) or [q["title"]]


def _read_angle(subq: str, hits: list, today: str) -> str | None:
    excerpts = "\n\n".join(f"[{h.source}] {h.title} ({h.url})\n{(h.snippet or '')[:1800]}"
                           for h in hits[:5] if (h.snippet or h.title))
    if not excerpts.strip():
        return None
    conn = db.connect()
    try:
        return llm.complete(conn, f"Today is {today}. Research question: {subq}\n\nWeb excerpts:\n"
                            f"{excerpts[:7000]}\n\nExtract the facts.",
                            provider=READER[0], model=READER[1], system=_READER_SYS,
                            max_tokens=350, est_cost_cents=1)
    except Exception:
        return None
    finally:
        conn.close()


def _search_and_read(subqs: list[str], today: str, conn, num: int = 5) -> tuple[list, list[str]]:
    results = search.search_multi(conn, subqs, num_results=num, text_chars=2000)  # keyless, $0
    urls = [h.url for hits in results.values() for h in hits if h.url]
    findings = []
    with cf.ThreadPoolExecutor(max_workers=min(6, max(1, len(subqs)))) as ex:
        for sq, facts in ex.map(lambda s: (s, _read_angle(s, results.get(s, []), today)), subqs):
            if facts and facts.strip() and "NOTHING RELEVANT" not in facts.upper():
                findings.append((sq, facts.strip()))
    return findings, urls


def _gap(conn, q, today, findings, provider, model, k) -> list[str]:
    ev = "\n\n".join(f"Researched: {sq}\nFound:\n{a[:500]}" for sq, a in findings)
    prompt = (f"Today is {today}.\nQuestion: {q['title']}\n"
              f"Resolution criteria: {(q.get('resolution_criteria') or '')[:500]}\n\n"
              f"Research so far:\n{ev[:5000]}\n\nName the follow-up research questions.")
    try:
        txt = llm.complete(conn, prompt, provider=provider, model=_orch_model(provider, model),
                           system=_GAP_SYS, max_tokens=300, est_cost_cents=5)
    except Exception:
        txt = ""
    return _lines(txt, k)


def deep_gather(q: dict, today: str, *, provider: str = "bedrock", model: str | None = None,
                breadth: int = 6, follow: int = 3, rounds: int = 2,
                conn=None) -> tuple[str, list[dict]]:
    """Agentic research dossier for one question. Returns (digest_text, sources) like research.gather.
    `provider`/`model` drive the Opus orchestration (decompose + gap); Exa+DeepSeek do retrieval/read."""
    own = conn is None
    conn = conn or db.connect()
    all_urls: list[str] = []
    try:
        subqs = _decompose(conn, q, today, provider, model, breadth)
        findings, urls = _search_and_read(subqs, today, conn)
        all_urls += urls
        if rounds >= 2 and findings:
            gaps = _gap(conn, q, today, findings, provider, model, follow)
            if gaps:
                more, urls2 = _search_and_read(gaps, today, conn)
                findings += more
                all_urls += urls2
    finally:
        if own:
            conn.close()

    if not findings:
        return "(deep research returned no findings)", []

    blocks = [f"Deep research dossier as of {today} (live web; current facts, may conflict — you weigh them):"]
    for i, (sq, facts) in enumerate(findings, 1):
        blocks.append(f"\n[{i}] On \"{sq}\":\n{facts[:900]}")
    seen, sources = set(), []
    for u in all_urls:
        u = u.rstrip(".,);]")
        if u and u not in seen:
            seen.add(u)
            sources.append({"title": "", "url": u, "snippet": "", "source": "exa", "query": "deep"})
    return "\n".join(blocks), sources[:25]
