"""engine/metaculus/calibrate.py — leak-free aggregation calibration for the judgmental bot.

WHY this is the honest harness (and, just as important, what it is NOT):

  • You CANNOT retro-fit the keyless roster's JUDGMENT. Its ~2025 training cutoff means most resolved
    questions' outcomes are already in its weights — parametric leakage ([[parametric-leakage]]). So we
    score ONLY questions whose outcome was DETERMINED AFTER the model's MEASURED effective cutoff, using
    the exact same leakage gate as engine/holdout.py (recall_cutoff). If the gate can't certify a
    question leak-free, it is dropped — never scored.
  • We run the ensemble with RESEARCH OFF. The keyless Exa endpoint ignores date params (verified), so
    fresh research on an already-resolved question would inject post-resolution news = leakage. No-research
    is also the clean AIB / hidden-crowd regime, and exactly where the aggregation priors (extremize d,
    blind-shrink) do the most work and most need a real number.
  • Train/test split → every reported "best d / best crowd-weight" is OUT-OF-SAMPLE. We never read an
    in-sample optimum off the same data we picked it on (that would be the overfit the project forbids).

What it measures, leak-free, on the REAL competing roster:
  (a) does the ensemble beat the base rate / always-0.5,
  (b) the OOS-optimal extremize d (validates or corrects EXTREMIZE_D),
  (c) how much to weight an EARLY (leak-free) crowd anchor (validates CROWD_WEIGHT).

Leak-free question sources (the user's "generate some if Metaculus is thin" — done honestly):
  • Recently-RESOLVED binary Manifold markets (keyless): real crowd + outcome + resolution date to gate on.
  • Mechanically-generated structural questions from public dated series
    (holdout.build_structural_questions): outcome from realized data, judgment-only (no crowd).

This is a forward-equivalent backtest: the only honest retro number the leakage wall permits. The live
Metaculus Cup (future-resolving → leak-free by construction) remains the primary clock.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

from engine import db
from engine.adapters import llm  # noqa: F401  (ensures repo env / cost gate wiring is importable)
from engine.forecastbench.ensemble import _logit, _sigmoid
from engine.forecastbench.inference import ROSTER, sample_one
from engine.metaculus import forecast as fc

_UA = {"User-Agent": "Mozilla/5.0"}
_MANIFOLD = "https://api.manifold.markets/v0"


# ─────────────────────────────────────────────────────────────── leak-free question sourcing

def _get(url: str):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())


def _ms_to_date(ms) -> date | None:
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, timezone.utc).date()


# Drop pure-sports / intraday-price markets: with research OFF the ensemble has no signal on these, so
# they'd drag the extremize estimate toward "never sharpen" and don't resemble Metaculus-Cup judgmental
# questions. This filters on the QUESTION (sport keyword / short horizon), never on the outcome — so it
# introduces no selection bias on the quantity being measured (calibration).
_SPORTS = (" defeat ", " beat ", " vs ", " vs. ", "premier league", "nba ", "nfl ", " ufc ", "world cup",
           "champions league", "super bowl", "grand prix", " odds ", "leading scorer", "win the match",
           " fc ", " match ", "playoff", "wembanyama")


def fetch_manifold_resolved(n: int = 60, *, min_bettors: int = 8, min_vol: float = 200.0,
                            min_horizon_days: int = 14, scan: int = 400) -> list[dict]:
    """Recently-RESOLVED binary Manifold markets with a clean YES/NO outcome and a real crowd.

    Returns dicts: {id, title, outcome(bool), resolved_date, created_ms, resolve_ms, crowd_final,
    vol, bettors}. Filtered to liquid markets (thin = noise, not a crowd), to a minimum forecasting
    horizon (drops intraday finance + same-day sports lines), and away from pure-sports questions —
    leaving genuinely Cup-like judgmental questions. `scan` markets are pulled newest-resolved-first."""
    out: list[dict] = []
    url = (f"{_MANIFOLD}/search-markets?term=&filter=resolved&sort=resolve-date"
           f"&contractType=BINARY&limit={scan}")
    try:
        markets = _get(url)
    except Exception:
        return out
    for m in markets:
        if m.get("outcomeType") != "BINARY" or m.get("resolution") not in ("YES", "NO"):
            continue
        if (m.get("uniqueBettorCount") or 0) < min_bettors or (m.get("volume") or 0) < min_vol:
            continue
        title = m.get("question", "")
        if any(s in (" " + title.lower() + " ") for s in _SPORTS):
            continue
        cms, rms = m.get("createdTime"), m.get("resolutionTime")
        if cms and rms and (rms - cms) < min_horizon_days * 86400_000:
            continue
        rd = _ms_to_date(m.get("resolutionTime"))
        if rd is None:
            continue
        out.append({
            "id": m["id"], "title": m.get("question", ""),
            "outcome": m["resolution"] == "YES", "resolved_date": rd,
            "created_ms": m.get("createdTime"), "resolve_ms": m.get("resolutionTime"),
            "crowd_final": m.get("probability"), "vol": m.get("volume") or 0,
            "bettors": m.get("uniqueBettorCount") or 0, "src": "manifold",
        })
        if len(out) >= n:
            break
    return out


def early_crowd(market_id: str, created_ms, resolve_ms, *, lead_frac: float = 0.5) -> float | None:
    """A leak-free EARLY crowd snapshot: the market probability at `lead_frac` through its life (default
    midpoint), NOT the near-resolution price. Using the final price would make the anchor look clairvoyant
    and over-weight it; an early snapshot mirrors what the live bot actually anchors to. Best-effort —
    returns None if the bet history is unavailable."""
    if not created_ms or not resolve_ms or resolve_ms <= created_ms:
        return None
    target = created_ms + lead_frac * (resolve_ms - created_ms)
    try:
        bets = _get(f"{_MANIFOLD}/bets?contractId={urllib.parse.quote(market_id)}&limit=1000&order=asc")
    except Exception:
        return None
    best_p, best_dt = None, None
    for b in bets:
        t = b.get("createdTime")
        p = b.get("probAfter")
        if t is None or p is None or t > target:
            continue
        d = target - t
        if best_dt is None or d < best_dt:
            best_dt, best_p = d, float(p)
    return best_p


def manifold_to_q(m: dict) -> dict:
    """Shape a Manifold market into the dict forecast._prompt expects (title + resolution criteria)."""
    return {
        "title": m["title"],
        "resolution_criteria": ("Resolves YES if the described event occurs by the market's close, "
                                "NO otherwise (Manifold binary market)."),
        "fine_print": "", "description": "",
    }


# ─────────────────────────────────────────────────────────────── scoring math

def _pool_d(samples: list[float], d: float) -> float:
    """Log-odds mean of the ensemble samples, sharpened by d (d=1 → honest mean). Mirrors forecast._pool."""
    z = sum(_logit(p) for p in samples) / len(samples)
    return max(1e-4, min(1 - 1e-4, _sigmoid(d * z)))


def _brier(rows: list[dict], prob_fn) -> float:
    return sum((prob_fn(r) - (1.0 if r["outcome"] else 0.0)) ** 2 for r in rows) / len(rows)


def _best_d_cv(rows: list[dict], grid: list[float]) -> tuple[float, float, float]:
    """2-fold cross-validated extremize d. Pick d* on fold A, score it on fold B (and vice-versa); the
    reported Brier is the AVERAGE of the two held-out folds → out-of-sample, overfit-resistant.
    Returns (d_star_full, brier_oos, brier_d1_oos). The full-data d* is what we'd actually adopt; the
    OOS Brier is the honest estimate of how it performs on unseen questions."""
    fold_a = rows[0::2]
    fold_b = rows[1::2]
    oos_total, oos_d1, k = 0.0, 0.0, 0
    for train, test in ((fold_a, fold_b), (fold_b, fold_a)):
        if not train or not test:
            continue
        d_star = min(grid, key=lambda d: _brier(train, lambda r, d=d: _pool_d(r["samples"], d)))
        oos_total += _brier(test, lambda r, d=d_star: _pool_d(r["samples"], d))
        oos_d1 += _brier(test, lambda r: _pool_d(r["samples"], 1.0))
        k += 1
    d_full = min(grid, key=lambda d: _brier(rows, lambda r, d=d: _pool_d(r["samples"], d)))
    return d_full, (oos_total / k if k else float("nan")), (oos_d1 / k if k else float("nan"))


def _best_crowd_w_cv(rows: list[dict], d: float, grid: list[float]) -> tuple[float, float]:
    """2-fold CV crowd-anchor weight on the subset that has an early crowd snapshot. Blend in log-odds:
    final = sigmoid((1-w)*logit(ext) + w*logit(crowd)). Returns (w_star_full, brier_oos)."""
    cr = [r for r in rows if r.get("crowd") is not None]
    if len(cr) < 6:
        return float("nan"), float("nan")

    def blended(r, w):
        ext = _pool_d(r["samples"], d)
        return _sigmoid((1 - w) * _logit(ext) + w * _logit(max(1e-4, min(1 - 1e-4, r["crowd"]))))

    fa, fb = cr[0::2], cr[1::2]
    oos, k = 0.0, 0
    for train, test in ((fa, fb), (fb, fa)):
        if not train or not test:
            continue
        w_star = min(grid, key=lambda w: _brier(train, lambda r, w=w: blended(r, w)))
        oos += _brier(test, lambda r, w=w_star: blended(r, w_star))
        k += 1
    w_full = min(grid, key=lambda w: _brier(cr, lambda r, w=w: blended(r, w)))
    return w_full, (oos / k if k else float("nan"))


def _reliability(rows: list[dict], prob_fn, bins: int = 5) -> list[tuple]:
    """Calibration table: (bin_label, n, mean_predicted, observed_freq)."""
    buckets: list[list[dict]] = [[] for _ in range(bins)]
    for r in rows:
        p = prob_fn(r)
        buckets[min(bins - 1, int(p * bins))].append(r)
    table = []
    for i, b in enumerate(buckets):
        if not b:
            table.append((f"{i/bins:.1f}-{(i+1)/bins:.1f}", 0, None, None))
            continue
        mp = sum(prob_fn(r) for r in b) / len(b)
        of = sum(1 for r in b if r["outcome"]) / len(b)
        table.append((f"{i/bins:.1f}-{(i+1)/bins:.1f}", len(b), mp, of))
    return table


# ─────────────────────────────────────────────────────────────── the run

D_GRID = [round(0.8 + 0.05 * i, 2) for i in range(19)]          # 0.80 … 1.70
W_GRID = [round(0.05 * i, 2) for i in range(11)]                # 0.00 … 0.50

# The superforecaster framework prompt + a probability parser. We call llm.complete DIRECTLY (not
# inference.sample_one) because sample_one hardcodes est_cost_cents=0 — fine for the keyless roster but
# WRONG for a keyed provider (OpenRouter), where the cost gate must see the real estimate (rule: log
# spend before the call). This helper cost-gates correctly for both routes.
import re as _re
_SYSTEM = (
    "You are an elite calibrated superforecaster. Reason concisely in this order: (1) the reference "
    "class and its base rate, stated FIRST; (2) the binding constraint / strongest structural driver; "
    "(3) the best case for YES and for NO; (4) commit to ONE calibrated probability — avoid 0 and 1, "
    "don't anchor on 0.5 where the structure is informative. End with exactly: 'Probability: 0.NN'.")
_PROB_RE = _re.compile(r"prob(?:ability)?\s*[:=]\s*([01](?:\.\d+)?|0?\.\d+)", _re.I)


def _parse_p(txt: str) -> float | None:
    if not txt:
        return None
    ms = _PROB_RE.findall(txt)
    if not ms:
        return None
    try:
        return min(1.0, max(0.0, float(ms[-1])))
    except ValueError:
        return None


def _ensemble_samples(prompt: str, models: list, n: int, *, provider: str, est_cost_cents: int,
                      proxy: str | None) -> dict[str, list]:
    """{model: [p,...]} via llm.complete, cost-gated per call (keyless→$0/auto; keyed→est logged).
    Each call gets its own DB conn so the gate ledger write is clean."""
    out: dict[str, list] = {}
    for m in models:
        ps = []
        for _ in range(n):
            txt = None
            for _retry in range(3):
                conn = db.connect()
                try:
                    txt = llm.complete(conn, prompt, provider=provider, model=m, system=_SYSTEM,
                                       max_tokens=700, est_cost_cents=est_cost_cents,
                                       proxy=(proxy or None))
                    break
                except Exception:
                    txt = None
                finally:
                    conn.close()
            p = _parse_p(txt) if txt else None
            if p is not None:
                ps.append(p)
        if ps:
            out[m] = ps
    return out


def run(*, n_manifold: int = 30, n_samples: int = 2, proxy: str | None = None,
        min_models: int = 4, include_structural: bool = True, with_crowd: bool = True,
        lead_frac: float = 0.5, provider: str = "deepinfra_keyless", model: str | None = None,
        models: list | None = None, est_cost_cents: int = 0, bank_questions: list | None = None,
        log=print) -> dict:
    """Measure cutoff → gather leak-free gated questions → run the no-research ensemble → CV-fit the
    aggregation priors.

    provider/model/models: the forecasting brain. Default = keyless roster ($0). For the OLD-CUTOFF
    leak-free backtest pass provider='openrouter', model='openai/gpt-4-0613', est_cost_cents=<budget>;
    `models` defaults to ROSTER for keyless else [model].
    bank_questions: an explicit qbank list (already year-windowed). If given, it REPLACES the live
    Manifold fetch (the historical-backtest path). proxy routes the calls."""
    from engine import holdout
    today = date.today().isoformat()
    brain = f"{provider}:{model or 'roster'}"
    mdl_list = models or (list(ROSTER) if provider == "deepinfra_keyless" else [model])
    log(f"\n🎯 AGGREGATION CALIBRATION (leak-free, cutoff-gated, no-research) — {today} — brain={brain}")

    # STEP 1 — the validity gate: measure THIS brain's effective cutoff (non-leading recall).
    conn = db.connect()
    try:
        log("   STEP 1 — leakage gate: measuring effective cutoff (non-leading recall)…")
        eff = holdout.recall_cutoff(conn, provider=provider, model=model,
                                    est_cost_cents=est_cost_cents, proxy=proxy, log=log)
    finally:
        conn.close()
    cutoff_year = eff if eff is not None else 2021
    log(f"   measured effective cutoff ≈ {eff if eff is not None else 'pre-2022'} "
        f"→ only score questions whose outcome was determined AFTER {cutoff_year}.")

    # STEP 2 — gather + GATE the question set.
    log("   STEP 2 — gathering leak-free questions…")
    if bank_questions is not None:
        gated = [{"id": q["id"], "title": q["title"], "outcome": q["outcome"],
                  "created_ms": q.get("created_ms"), "resolve_ms": q.get("resolve_ms"),
                  "resolved_date": date.fromisoformat(q["resolved_date"])}
                 for q in bank_questions if q["resolved_year"] > cutoff_year]
        log(f"   Bank: {len(bank_questions)} supplied → {len(gated)} pass the cutoff gate "
            f"(resolved > {cutoff_year}).")
        include_structural = False
    else:
        mkts = fetch_manifold_resolved(n=n_manifold * 2)   # over-fetch; gating + samples thin it
        gated = [m for m in mkts if m["resolved_date"].year > cutoff_year][:n_manifold]
        log(f"   Manifold (live recent): {len(mkts)} fetched → {len(gated)} pass the cutoff gate.")

    struct_qs = []
    if include_structural:
        conn = db.connect()
        try:
            sq = holdout.build_structural_questions(conn, cutoff_year=str(cutoff_year),
                                                    horizons=(str(cutoff_year + 1), str(cutoff_year + 2)))
        finally:
            conn.close()
        struct_qs = [q for q in sq if q["determined"] > cutoff_year]
        log(f"   Structural (mechanical, from public series): {len(struct_qs)} leak-free questions.")

    if not gated and not struct_qs:
        log("   ⛔ INVALID — no leak-free questions for this brain (cutoff too recent / no resolutions). "
            "Honest blocker: widen the resolved window or use an older-cutoff model (see holdout.py).")
        return {"valid": False, "effective_cutoff": eff, "n": 0}

    # STEP 3 — run the ensemble (RESEARCH OFF) on each leak-free question.
    log(f"   STEP 3 — no-research forecasts: {len(mdl_list)} model(s) × {n_samples} sample(s) "
        f"on {len(gated) + len(struct_qs)} questions (the slow/costed part)…")
    rows: list[dict] = []
    for i, m in enumerate(gated, 1):
        prompt = fc._prompt(manifold_to_q(m), "(research disabled — leak-free calibration)", today, None)
        per: dict[str, list] = {}
        for _ in range(3):
            missing = [x for x in mdl_list if x not in per]
            if not missing or len(per) >= min(min_models, len(mdl_list)):
                break
            per.update(_ensemble_samples(prompt, missing, n_samples, provider=provider,
                                         est_cost_cents=est_cost_cents, proxy=proxy))
        samples = [p for ps in per.values() for p in ps]
        if not samples:
            continue
        crowd = early_crowd(m["id"], m["created_ms"], m["resolve_ms"], lead_frac=lead_frac) \
            if with_crowd else None
        rows.append({"id": m["title"][:48], "outcome": m["outcome"], "samples": samples,
                     "crowd": crowd, "src": "bank" if bank_questions is not None else "manifold"})
        if i % 10 == 0 or i <= 5:
            log(f"     [{i}/{len(gated)}] {len(per)}m {len(samples)}s "
                f"raw={_pool_d(samples,1.0):.2f} crowd={crowd if crowd is None else round(crowd,2)} "
                f"out={'Y' if m['outcome'] else 'N'} · {m['title'][:40]}")

    for q in struct_qs:
        per = {}
        for _ in range(3):
            missing = [x for x in mdl_list if x not in per]
            if not missing or len(per) >= min(min_models, len(mdl_list)):
                break
            per.update(_ensemble_samples(q["q"], missing, n_samples, provider=provider,
                                         est_cost_cents=est_cost_cents, proxy=proxy))
        samples = [p for ps in per.values() for p in ps]
        if not samples:
            continue
        rows.append({"id": q["id"][:48], "outcome": q["outcome"], "samples": samples,
                     "crowd": None, "src": "structural"})

    n = len(rows)
    if n < 8:
        log(f"   ⚠️  only {n} questions returned usable ensemble samples — too few to calibrate "
            "(raise --n-manifold / --proxy evomi for more coverage). Reporting what we have.")
    if not rows:
        return {"valid": False, "effective_cutoff": eff, "n": 0}

    # STEP 4 — score + CV-fit the priors.
    base = sum(1 for r in rows if r["outcome"]) / n
    brier_base = _brier(rows, lambda r: base)
    brier_half = _brier(rows, lambda r: 0.5)
    brier_raw = _brier(rows, lambda r: _pool_d(r["samples"], 1.0))
    brier_cur = _brier(rows, lambda r: _pool_d(r["samples"], fc.EXTREMIZE_D))
    d_star, brier_d_oos, brier_d1_oos = _best_d_cv(rows, D_GRID)
    w_star, brier_w_oos = _best_crowd_w_cv(rows, fc.EXTREMIZE_D, W_GRID) if with_crowd else (float("nan"), float("nan"))
    rel = _reliability(rows, lambda r: _pool_d(r["samples"], fc.EXTREMIZE_D))

    n_market = sum(1 for r in rows if r["src"] in ("manifold", "bank"))
    log(f"\n   ── RESULTS (N={n}; {n_market} market + "
        f"{sum(1 for r in rows if r['src']=='structural')} structural; base rate {base:.2f}) ──")
    log(f"   Brier  always-0.5     : {brier_half:.4f}")
    log(f"   Brier  always-base    : {brier_base:.4f}")
    log(f"   Brier  raw ensemble   : {brier_raw:.4f}   ({'beats' if brier_raw<brier_base else 'LOSES vs'} base)")
    log(f"   Brier  current d={fc.EXTREMIZE_D:<4}: {brier_cur:.4f}")
    log(f"   ── extremize d (2-fold CV, OUT-OF-SAMPLE) ──")
    log(f"   OOS Brier  d=1.0      : {brier_d1_oos:.4f}")
    log(f"   OOS Brier  d*={d_star:<5}   : {brier_d_oos:.4f}   ← CV-selected; "
        f"{'extremizing helps ✅' if brier_d_oos < brier_d1_oos else 'do NOT extremize (d≤1) ⚠️'}")
    if with_crowd and w_star == w_star:  # not NaN
        log(f"   ── crowd-anchor weight (early snapshot, 2-fold CV) ──")
        log(f"   OOS Brier  w*={w_star:<5}   : {brier_w_oos:.4f}   (current prior w={fc.CROWD_WEIGHT})")
    log(f"   ── calibration (predicted d={fc.EXTREMIZE_D} vs observed) ──")
    for lab, cnt, mp, of in rel:
        if cnt:
            log(f"     {lab}  n={cnt:<3} pred={mp:.2f} obs={of:.2f}")

    verdict = {
        "valid": True, "date": today, "effective_cutoff": eff, "n": n, "base_rate": base,
        "brier_half": brier_half, "brier_base": brier_base, "brier_raw": brier_raw,
        "brier_current_d": brier_cur, "current_d": fc.EXTREMIZE_D,
        "d_star": d_star, "brier_d_oos": brier_d_oos, "brier_d1_oos": brier_d1_oos,
        "crowd_w_star": w_star, "brier_w_oos": brier_w_oos, "current_w": fc.CROWD_WEIGHT,
        "brain": brain, "n_market": n_market,
        "n_structural": sum(1 for r in rows if r["src"] == "structural"),
        "reliability": [{"bin": l, "n": c, "pred": mp, "obs": of} for l, c, mp, of in rel],
    }
    _write_verdict(verdict, log=log)
    return verdict


def _write_verdict(v: dict, *, log=print) -> None:
    import os
    os.makedirs("data/metaculus", exist_ok=True)
    tag = (v.get("brain", "") or "").replace("/", "-").replace(":", "_")
    path = f"data/metaculus/calibration_{v['date']}_{tag}.json"
    with open(path, "w") as f:
        json.dump(v, f, indent=2)
    rec = []
    if v["n"] >= 12 and v["brier_d_oos"] == v["brier_d_oos"]:
        if v["brier_d_oos"] < v["brier_d1_oos"] - 1e-4:
            rec.append(f"Keep extremizing; CV-optimal d≈{v['d_star']} "
                       f"(current {v['current_d']} is {'well-placed' if abs(v['d_star']-v['current_d'])<=0.1 else 'off — consider moving toward d*'}).")
        else:
            rec.append("Extremizing did NOT help out-of-sample on this set → hold d=1.0 / be conservative.")
    else:
        rec.append("N too small for a confident prior change — treat as indicative; do NOT edit priors yet.")
    log("\n   VERDICT (no auto-edit; priors change only on a human nod, per no-overfit doctrine):")
    for r in rec:
        log(f"     • {r}")
    log(f"   saved → {path}")


# ─────────────────────────────────────────────────────────────── CLI

def _sample_bank(rows: list[dict], max_q: int) -> list[dict]:
    """Even stride-sample across the (resolution-date-sorted) bank so the subset spans all years rather
    than clustering in one. Deterministic (no RNG) → reproducible."""
    if len(rows) <= max_q:
        return rows
    step = len(rows) / max_q
    return [rows[int(i * step)] for i in range(max_q)]


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Leak-free, cutoff-gated aggregation calibration.")
    ap.add_argument("--n-manifold", type=int, default=30)
    ap.add_argument("--n", type=int, default=2, help="best-of-N samples per model")
    ap.add_argument("--proxy", default=None, help="bare provider ('evomi') to rotate IPs, or None=direct")
    ap.add_argument("--min-models", type=int, default=4)
    ap.add_argument("--no-structural", action="store_true")
    ap.add_argument("--no-crowd", action="store_true")
    ap.add_argument("--lead-frac", type=float, default=0.5)
    # OLD-CUTOFF backtest path (the leak-free historical test): point at the qbank + a keyed old model.
    ap.add_argument("--provider", default="deepinfra_keyless")
    ap.add_argument("--model", default=None, help="e.g. openai/gpt-4-0613 for the leak-free backtest")
    ap.add_argument("--est-cost-cents", type=int, default=0, help="per-call cost ceiling for keyed routes")
    ap.add_argument("--bank", action="store_true", help="use the historical qbank instead of live Manifold")
    ap.add_argument("--bank-path", default=None)
    ap.add_argument("--year-min", type=int, default=None, help="keep resolved_year > this")
    ap.add_argument("--year-max", type=int, default=None, help="keep resolved_year <= this")
    ap.add_argument("--max-q", type=int, default=120, help="cap bank questions actually run (cost control)")
    a = ap.parse_args()

    bank = None
    if a.bank:
        from engine.metaculus import qbank
        bank = qbank.load(a.bank_path or qbank.BANK_PATH,
                          resolved_after_year=a.year_min, max_resolved_year=a.year_max)
        bank = _sample_bank(bank, a.max_q)
        print(f"loaded {len(bank)} bank questions "
              f"(year window {a.year_min or '-'}..{a.year_max or 'now'}, capped at {a.max_q})")

    run(n_manifold=a.n_manifold, n_samples=a.n, proxy=a.proxy, min_models=a.min_models,
        include_structural=not a.no_structural, with_crowd=not a.no_crowd, lead_frac=a.lead_frac,
        provider=a.provider, model=a.model, est_cost_cents=a.est_cost_cents, bank_questions=bank)
