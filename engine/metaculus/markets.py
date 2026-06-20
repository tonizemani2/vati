"""Cross-market anchor — keyless prediction-market price for the SAME event, used as EVIDENCE only.

Why evidence-only and not the answer (the honest design, per the Polymarket question 2026-06-12):
markets are well-calibrated, so copying their price collapses our forecast onto the crowd (corr ~0.97
→ zero independent skill → the decorrelation edge dies). And most Metaculus questions have no exact
market counterpart; a near-match with different resolution criteria injects bias worse than no anchor.

So this is a CONSERVATIVE, gated lookup: it only returns a market when the title similarity clears a
high bar AND the market is liquid. The hit is surfaced as one dated snippet the forecaster WEIGHS, plus
(optionally) a LOW-weight secondary anchor — never the output. Its real value is filling the gap when
Metaculus hides its own Community Prediction (early season / the AIB bot tournament), where it's the
only crowd signal available.

Keyless: Manifold `search-markets` (real full-text), Polymarket Gamma `public-search` (best-effort).
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from difflib import SequenceMatcher

_UA = {"User-Agent": "Mozilla/5.0"}
MIN_SIM = 0.55          # title-similarity floor; hard gates below catch false positives above it
MIN_VOLUME = 150        # liquidity floor — thin markets are noise, not a crowd


def _get(url: str):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


_STOP = {"will", "the", "a", "an", "be", "by", "in", "on", "of", "to", "is", "are", "any",
         "before", "after", "than", "more", "least", "at", "for", "and", "or", "this", "that"}


def _norm(s: str) -> set:
    toks = re.findall(r"[a-z0-9]+", (s or "").lower())
    return {t for t in toks if t not in _STOP and len(t) > 1}


def _similarity(a: str, b: str) -> float:
    """Blend a token-Jaccard (catches entity overlap) with a sequence ratio (catches phrasing),
    so 'Will any World Cup match be delayed >X' matches a market about the same, and the fan-invasion
    market does not."""
    ta, tb = _norm(a), _norm(b)
    jac = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    seq = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return 0.6 * jac + 0.4 * seq


_MONTHS = {
    "jan", "january", "feb", "february", "mar", "march", "apr", "april", "may", "jun", "june",
    "jul", "july", "aug", "august", "sep", "sept", "september", "oct", "october", "nov",
    "november", "dec", "december",
}
_UP = {"above", "over", "exceed", "exceeds", "exceeding", "higher", "greater", "hit", "reach"}
_DOWN = {"below", "under", "less", "lower", "drop", "drops", "fall", "falls"}


def _years(s: str) -> set[str]:
    return set(re.findall(r"\b20\d{2}\b", s or ""))


def _months(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]+", (s or "").lower()) if t in _MONTHS}


def _money_amounts(s: str) -> list[float]:
    vals = []
    for num, suffix in re.findall(
        r"[$€£]\s*(\d+(?:,\d{3})*(?:\.\d+)?)(?:\s*(k|m|b|million|billion|thousand))?",
        s or "", re.I
    ):
        val = float(num.replace(",", ""))
        mult = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6,
                "b": 1e9, "billion": 1e9}.get(suffix.lower() if suffix else "", 1.0)
        vals.append(val * mult)
    return vals


def _percents(s: str) -> list[float]:
    vals = []
    for num in re.findall(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", s or "", re.I):
        vals.append(float(num))
    return vals


def _close_any(a: list[float], b: list[float], rel_tol: float = 0.05) -> bool:
    return any(abs(x - y) <= rel_tol * max(abs(x), abs(y), 1.0) for x in a for y in b)


def _direction(s: str) -> str | None:
    toks = _norm(s)
    if toks & _UP and not toks & _DOWN:
        return "up"
    if toks & _DOWN and not toks & _UP:
        return "down"
    return None


def _usable_match(title: str, candidate_question: str) -> tuple[bool, list[str]]:
    """Hard resolution-criteria gates for an otherwise similar market title.

    These catch the expensive failure mode: a title-similar market about the wrong
    threshold or deadline. They never look at the price or outcome.
    """
    reasons: list[str] = []
    overlap = _norm(title) & _norm(candidate_question)
    if len(overlap) < 2:
        reasons.append("too little entity/topic overlap")
    ya, yb = _years(title), _years(candidate_question)
    if ya and yb and ya.isdisjoint(yb):
        reasons.append("year mismatch")
    ma, mb = _months(title), _months(candidate_question)
    if ma and mb and ma.isdisjoint(mb):
        reasons.append("month/deadline mismatch")
    ca, cb = _money_amounts(title), _money_amounts(candidate_question)
    if ca and cb and not _close_any(ca, cb):
        reasons.append("money threshold mismatch")
    pa, pb = _percents(title), _percents(candidate_question)
    if pa and pb and not _close_any(pa, pb):
        reasons.append("percent threshold mismatch")
    da, db = _direction(title), _direction(candidate_question)
    if da and db and da != db:
        reasons.append("direction mismatch")
    return not reasons, reasons


def _manifold(title: str):
    try:
        url = ("https://api.manifold.markets/v0/search-markets?term="
               + urllib.parse.quote(title) + "&limit=6")
        for m in _get(url):
            if m.get("outcomeType") != "BINARY" or m.get("probability") is None:
                continue
            if m.get("isResolved") or (m.get("volume") or 0) < MIN_VOLUME:
                continue
            yield {"prob": float(m["probability"]), "volume": float(m.get("volume") or 0),
                   "question": m.get("question", ""), "url": m.get("url", ""), "source": "manifold"}
    except Exception:
        return


def _polymarket(title: str):
    try:
        url = ("https://gamma-api.polymarket.com/public-search?q="
               + urllib.parse.quote(title) + "&limit_per_type=6&events_status=active")
        data = _get(url)
        events = data.get("events", data) if isinstance(data, dict) else data
        for ev in (events or []):
            for mk in ev.get("markets", [ev]) if isinstance(ev, dict) else []:
                try:
                    prices = json.loads(mk.get("outcomePrices", "[]"))
                    vol = float(mk.get("volume") or ev.get("volume") or 0)
                except Exception:
                    continue
                if not prices or vol < MIN_VOLUME:
                    continue
                yield {"prob": float(prices[0]), "volume": vol,
                       "question": mk.get("question") or ev.get("title", ""),
                       "url": "https://polymarket.com/event/" + str(ev.get("slug", "")),
                       "source": "polymarket"}
    except Exception:
        return


def cross_market(title: str) -> dict | None:
    """Best liquid market matching `title` above the similarity bar, or None.
    Returns {prob, volume, question, url, source, sim}."""
    best = None
    for cand in list(_manifold(title)) + list(_polymarket(title)):
        cand["sim"] = _similarity(title, cand["question"])
        usable, reasons = _usable_match(title, cand["question"])
        cand["match_reasons"] = reasons
        if cand["sim"] >= MIN_SIM and usable and (best is None or cand["sim"] > best["sim"]):
            best = cand
    return best


def evidence_line(title: str) -> tuple[str | None, dict | None]:
    """A dated snippet for the research digest + the raw match (for an optional low-weight anchor).
    Returns (line_or_None, match_or_None)."""
    m = cross_market(title)
    if not m:
        return None, None
    line = (f"Prediction market ({m['source']}, ${m['volume']:,.0f} volume) on a closely matching "
            f"question \"{m['question'][:90]}\" currently prices YES at {m['prob']:.2f}.")
    return line, m
