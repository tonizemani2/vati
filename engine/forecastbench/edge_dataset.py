"""engine/forecastbench/edge_dataset.py — manufacture the leak-free edge dataset (Lane A).

The negative finetune result (NEGATIVE_RESULT_FINETUNE.md) failed for one reason: the teacher data
had no edge over the free prior. This module builds the opposite on purpose — rows of the shape

    (structural features knowable at T)  ->  (outcome at T+k)

with a REAL crowd prior at T to beat, and a hard leak audit on every feature. Plan: EDGE_DATASET_PLAN.md.

Lane A (this file) is fully deterministic — NO LLM touches the numbers, so no parametric leak is possible:
  • labels + outcome:  resolved Manifold markets from the leak-free qbank (engine/metaculus/qbank.py).
  • crowd prior at T:   reconstructed from Manifold BET HISTORY (the price as it actually stood at T),
                        not the leaked `crowd_final` (which is the answer).
  • features at T:      arXiv research velocity/acceleration computed from the `papers` table filtered
                        to published <= T. `papers.published` is the first-submission date — a fixed
                        point-in-time fact (db.py:498), so bucketing by it can never look ahead.

Every feature carries a `source_date`; build_row asserts max(source_date) <= T or drops the row.
The cutoff T is chosen partway into each market's life (default 25%) so there is a genuine forecasting
horizon ahead AND a real crowd price to measure edge against.

This is the $0 core. The DeepSeek edge-gate (does base+features beat the crowd in-context?) and the
finetune are separate, gated steps — run only after this proves the features carry signal.

CLI:
    uv run python -m engine.forecastbench.edge_dataset --n 30 --frac 0.25
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import numpy as np

from engine.db import connect
from engine.metaculus.qbank import load as load_qbank

_UA = {"User-Agent": "Mozilla/5.0"}
_MANIFOLD = "https://api.manifold.markets/v0"
OUT_PATH = "data/forecastbench/trainset/edge_v0.jsonl"

# words too generic to be a useful arXiv search term
_STOP = {
    "will", "the", "a", "an", "by", "be", "in", "on", "of", "to", "for", "and", "or", "at", "is",
    "are", "was", "were", "this", "that", "with", "from", "before", "after", "than", "any", "have",
    "has", "had", "more", "less", "least", "most", "first", "next", "new", "end", "year", "years",
    "month", "months", "day", "days", "week", "date", "time", "over", "under", "between", "during",
    "win", "reach", "hit", "above", "below", "another", "their", "there", "what", "when", "who",
    "how", "into", "out", "up", "down", "get", "make", "made", "would", "could", "should", "2024",
    "2025", "2026", "2027", "2028", "us", "usa", "u.s", "his", "her",
}


def _get(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


# ── crowd prior at T (leak-free: the price as it stood at T, not the final price) ──────────────────

def _all_bets(contract_id: str, *, max_pages: int = 6, page: int = 1000) -> list[dict]:
    """Page Manifold bet history newest-first via the `before` cursor. Liquid markets are usually one
    page; we cap at max_pages so a hyper-active market can't stall the build."""
    out: list[dict] = []
    before = None
    for _ in range(max_pages):
        url = f"{_MANIFOLD}/bets?contractId={contract_id}&limit={page}"
        if before:
            url += f"&before={before}"
        try:
            chunk = _get(url)
        except Exception:
            break
        if not chunk:
            break
        out.extend(chunk)
        if len(chunk) < page:
            break
        before = chunk[-1]["id"]
    return out


def crowd_prob_at_T(contract_id: str, T_ms: int) -> float | None:
    """The market's probability as it stood at time T — the LAST bet's probAfter at/just before T.
    If T precedes the first bet, fall back to that bet's probBefore (the opening price). None if no
    usable bet history. This is the leak-free prior to beat (never `crowd_final`)."""
    bets = _all_bets(contract_id)
    if not bets:
        return None
    prior = [b for b in bets if b.get("createdTime", 0) <= T_ms and b.get("probAfter") is not None]
    if prior:
        last = max(prior, key=lambda b: b["createdTime"])
        return float(last["probAfter"])
    # T is before any trade: use the opening price (probBefore of the earliest bet)
    earliest = min(bets, key=lambda b: b.get("createdTime", 0))
    pb = earliest.get("probBefore")
    return float(pb) if pb is not None else None


# ── features at T (leak-free: papers.published <= T) ───────────────────────────────────────────────

def keywords(title: str, *, cap: int = 3) -> list[str]:
    """Pull the most specific content words from a question title for an arXiv term search."""
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", title.lower())
    seen: list[str] = []
    for w in sorted({w for w in words if w not in _STOP and len(w) >= 4}, key=len, reverse=True):
        seen.append(w)
        if len(seen) >= cap:
            break
    return seen


def _yearly_paper_counts(conn, terms: list[str], T_date: str) -> tuple[dict[int, int], dict[int, int]]:
    """Per publication-year, for arXiv papers matching ANY term (title OR abstract) with
    published <= T_date: (works {year: count}, breadth {year: distinct primary_category count}).
    Both come from ONE scan. Leak-free by the WHERE (published is point-in-time clean)."""
    if not terms:
        return {}, {}
    like = " OR ".join(["title LIKE ? OR abstract LIKE ?" for _ in terms])
    params: list[str] = []
    for t in terms:
        params += [f"%{t}%", f"%{t}%"]
    sql = ("SELECT substr(published,1,4) AS yr, COUNT(DISTINCT id) AS n, "
           "COUNT(DISTINCT primary_category) AS ncat "
           "FROM papers WHERE substr(published,1,10) <= ? AND (" + like + ") GROUP BY yr")
    rows = conn.execute(sql, [T_date, *params]).fetchall()
    works, cats = {}, {}
    for r in rows:
        if r["yr"] and r["yr"].isdigit():
            works[int(r["yr"])] = r["n"]
            cats[int(r["yr"])] = r["ncat"]
    return works, cats


_TOTAL_BY_YEAR: dict[int, int] | None = None


def _total_by_year(conn) -> dict[int, int]:
    """All arXiv papers per year (computed once, cached). The denominator for share-of-literature —
    this is what removes the 'all of arXiv grows' confound that raw counts suffer from."""
    global _TOTAL_BY_YEAR
    if _TOTAL_BY_YEAR is None:
        rows = conn.execute("SELECT substr(published,1,4) AS yr, COUNT(*) AS n FROM papers GROUP BY yr").fetchall()
        _TOTAL_BY_YEAR = {int(r["yr"]): r["n"] for r in rows if r["yr"] and r["yr"].isdigit()}
    return _TOTAL_BY_YEAR


def _surprise_sigma(years: list[int], log_shares: list[float]) -> float:
    """The repo's detector signal: fit a robust linear trend on the log-share series EXCLUDING the
    last complete year, predict it, and report the residual in in-sample-σ units. High = the front
    bent up faster than its own trend (the leading 'acceleration' the count-velocity misses)."""
    if len(years) < 4:
        return 0.0
    x = np.array(years[:-1], dtype=float)
    y = np.array(log_shares[:-1], dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    resid_in = y - (slope * x + intercept)
    s = float(resid_in.std()) or 1e-6
    pred_last = slope * years[-1] + intercept
    return float((log_shares[-1] - pred_last) / s)


def research_velocity(conn, title: str, T_date: str) -> dict | None:
    """Leak-free arXiv structural feature bundle, computed from data <= T (complete years only — the
    partial T-year is dropped, so no look-ahead). All normalized by total arXiv volume per year (share
    of world literature, ppm) to kill the 'all of arXiv grows' confound. Three leading channels, the
    repo's proven shapes:
      • share velocity / accel — change in YoY share growth
      • surprise_sigma         — detrended bend vs the field's own log-share trend (concept_emergence)
      • diffusion              — cross-category breadth + its growth (fires on spread, not volume)
    """
    terms = keywords(title)
    if not terms:
        return None
    counts, cats = _yearly_paper_counts(conn, terms, T_date)
    total_lifetime = sum(counts.values())
    if total_lifetime < 20:  # too thin to be a real signal — leave the row feature-less (honest coverage)
        return None
    totals = _total_by_year(conn)
    T = datetime.fromisoformat(T_date)
    y2, y1, y0 = T.year - 1, T.year - 2, T.year - 3  # last three COMPLETE years before T

    def share_ppm(y: int) -> float:
        tot = totals.get(y, 0)
        return (counts.get(y, 0) / tot * 1e6) if tot else 0.0

    s2, s1, s0 = share_ppm(y2), share_ppm(y1), share_ppm(y0)
    if s2 == 0 and s1 == 0:
        return None  # no signal in the recent complete years
    eps = 1e-6
    growth_recent = (s2 + eps) / (s1 + eps)
    growth_prev = (s1 + eps) / (s0 + eps)
    accel = growth_recent - growth_prev
    # detrended surprise over up to 6 complete years before T
    cy = [y for y in range(T.year - 6, T.year) if share_ppm(y) > 0]
    sigma = _surprise_sigma(cy, [math.log(share_ppm(y) + eps) for y in cy]) if len(cy) >= 4 else 0.0
    # diffusion: cross-category breadth and its growth
    b2, b1 = cats.get(y2, 0), cats.get(y1, 0)
    diffusion_growth = (b2 + 1) / (b1 + 1)
    return {
        "name": "arxiv_share_velocity",
        "terms": terms,
        "share_ppm_y2": round(s2, 2),
        "yoy_share_growth": round(growth_recent, 3),
        "accel": round(accel, 3),
        "surprise_sigma": round(sigma, 3),
        "diffusion_breadth": b2,
        "diffusion_growth": round(diffusion_growth, 3),
        "works_y2": counts.get(y2, 0),
        "lifetime_works_to_T": total_lifetime,
        "complete_years": [y0, y1, y2],
        "source": "arxiv/papers (share-of-literature)",
        "source_date": f"{y2}-12-31",  # only complete-year data through y2 is used (< T)
    }


# ── row assembly + leak audit ──────────────────────────────────────────────────────────────────────

# Science/tech question filter — the ONLY domain where an arXiv research-front signal is causally
# relevant. A leak-free feature attaching to "nuclear war" or "recession" is spurious noise; quality
# means scoping the set to questions the feature can actually inform (AI/compute/bio/space/energy).
_SCITECH = re.compile(
    r"\b(ai|a\.i|agi|gpt|chatgpt|openai|anthropic|claude|gemini|deepmind|llm|llms|language model|"
    r"machine learning|deep learning|neural|transformer|chip|chips|semiconductor|gpu|gpus|nvidia|tsmc|"
    r"quantum|fusion|reactor|vaccine|drug|fda|clinical trial|rocket|launch|spacex|starship|falcon|"
    r"satellite|battery|batteries|solar|self-driving|autonomous|robot|robots|robotaxi|waymo|crispr|"
    r"gene|genome|protein|alphafold|superconductor|lk-99|mrna|antibody|reusable|orbit)\b",
    re.IGNORECASE,
)


def is_scitech(title: str) -> bool:
    return bool(_SCITECH.search(title or ""))


def cutoff(q: dict, frac: float) -> tuple[int, str]:
    """Pick the leak cutoff T at `frac` of the way through the market's life (default 25%)."""
    T_ms = int(q["created_ms"] + frac * (q["resolve_ms"] - q["created_ms"]))
    T_date = datetime.fromtimestamp(T_ms / 1000, timezone.utc).date().isoformat()
    return T_ms, T_date


def build_row(conn, q: dict, frac: float) -> dict | None:
    T_ms, T_date = cutoff(q, frac)
    crowd = crowd_prob_at_T(q["id"], T_ms)
    if crowd is None:
        return None  # no leak-free prior => not a usable training row
    feats: list[dict] = []
    rv = research_velocity(conn, q["title"], T_date)
    if rv:
        feats.append(rv)
    # leak audit: every feature's source_date must be <= T (knowable at T)
    src_dates = [f["source_date"] for f in feats if f.get("source_date")]
    max_src = max(src_dates) if src_dates else None
    if max_src is not None and max_src > T_date:
        return None  # leak — drop
    outcome = 1 if q["outcome"] else 0
    return {
        "qid": f"manifold:{q['id']}",
        "question": q["title"],
        "T": T_date,
        "horizon_days_remaining": round((q["resolve_ms"] - T_ms) / 86400_000),
        "crowd_prob_at_T": round(crowd, 4),
        "features": feats,
        "leak_audit": {"max_source_date": max_src, "T": T_date,
                       "passes": (max_src is None or max_src <= T_date)},
        "outcome": outcome,
        "resolved_date": q["resolved_date"],
        "url": q["url"],
        # crowd_final kept ONLY for diagnostics — never a training input (it is the leaked answer)
        "_crowd_final_LEAKED": q.get("crowd_final"),
    }


def build(*, n: int = 30, frac: float = 0.25, out_path: str = OUT_PATH,
          resolved_after_year: int | None = 2022, scitech: bool = False, log=print) -> dict:
    """Build the Lane-A slice and report coverage + free signal diagnostics. $0 — no LLM, no GPU."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    qs = load_qbank(resolved_after_year=resolved_after_year)
    if not qs:
        log("⚠️  qbank empty — run `python -m engine.metaculus.qbank` first.")
        return {"n": 0}
    if scitech:
        before = len(qs)
        qs = [q for q in qs if is_scitech(q["title"])]
        log(f"   scitech filter: {len(qs)}/{before} questions kept (arXiv signal is only relevant here)")
    qs = qs[:n]
    conn = connect()
    rows: list[dict] = []
    log(f"🏗️  building edge dataset: {len(qs)} questions, cutoff at {frac:.0%} of market life → {out_path}")
    for i, q in enumerate(qs, 1):
        try:
            r = build_row(conn, q, frac)
        except Exception as e:
            log(f"   [{i}/{len(qs)}] skip ({type(e).__name__}: {e})")
            continue
        if r:
            rows.append(r)
            tag = "feat" if r["features"] else "----"
            log(f"   [{i}/{len(qs)}] {tag} crowd@T={r['crowd_prob_at_T']:.2f} → {r['outcome']}  {r['question'][:60]}")
    with open(out_path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return _report(rows, out_path, log)


def _brier(rows: list[dict], key: str) -> float | None:
    vals = [(r[key], r["outcome"]) for r in rows if r.get(key) is not None]
    return sum((p - o) ** 2 for p, o in vals) / len(vals) if vals else None


def _report(rows: list[dict], out_path: str, log) -> dict:
    n = len(rows)
    with_feat = [r for r in rows if r["features"]]
    log("\n── coverage ─────────────────────────────────────────")
    log(f"   rows written          : {n} → {out_path}")
    log(f"   with leak-free features: {len(with_feat)} ({(len(with_feat)/n*100 if n else 0):.0f}%)")
    log(f"   leak audit pass        : {sum(r['leak_audit']['passes'] for r in rows)}/{n}")
    bc = _brier(rows, "crowd_prob_at_T")
    log("\n── free signal diagnostics (no LLM) ─────────────────")
    if bc is not None:
        log(f"   crowd-prior-at-T Brier : {bc:.4f}  (the bar the features must beat)")
    # crude $0 edge check: do high-acceleration rows resolve YES more than low? (signal in features?)
    acc = [(r["features"][0]["accel"], r["outcome"]) for r in with_feat
           if r["features"][0]["name"] == "arxiv_share_velocity"]
    if len(acc) >= 6:
        acc.sort(key=lambda x: x[0])
        half = len(acc) // 2
        lo_rate = sum(o for _, o in acc[:half]) / half
        hi_rate = sum(o for _, o in acc[half:]) / (len(acc) - half)
        log(f"   YES-rate low-accel half : {lo_rate:.2f}")
        log(f"   YES-rate high-accel half: {hi_rate:.2f}  (gap hints features carry signal)")
    else:
        log("   (too few feature rows for the accel/outcome split — widen --n)")
    log("\n   NEXT: run the DeepSeek edge-gate (paid, ~cents) only if features look alive here.")
    return {"n": n, "with_features": len(with_feat), "crowd_brier": bc, "path": out_path}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build the leak-free edge dataset (Lane A, $0).")
    ap.add_argument("--n", type=int, default=30, help="questions to attempt")
    ap.add_argument("--frac", type=float, default=0.25, help="cutoff T as fraction of market life")
    ap.add_argument("--out", default=OUT_PATH)
    ap.add_argument("--after-year", type=int, default=2022, help="only questions resolving after this year")
    ap.add_argument("--scitech", action="store_true", help="keep only science/tech questions (where the arXiv signal is causally relevant)")
    a = ap.parse_args()
    build(n=a.n, frac=a.frac, out_path=a.out, resolved_after_year=a.after_year, scitech=a.scitech)
