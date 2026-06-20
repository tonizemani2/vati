"""Keyless-council numeric / multiple-choice forecaster.

binary lives in forecast.py (ensemble → extremize → crowd-anchor). The numeric & MC questions that
make up most of a Metaculus tournament were, until now, hand-authored percentiles — judgment with no
research and no ensemble. This module closes that gap with the SAME architecture as the binary leg:

    research digest (research.gather)  →  free-roster council each emits a quantile band / option
    distribution  →  aggregate (median per quantile, mean per option) → numeric.py CDF / vector.

The aggregation is the decorrelation math: independent keyless models disagree, the median quantile
band is robust to any one model's tail blow-up, and the spread of their medians IS the calibrated
uncertainty. Everything is $0 (openrouter_free) and leak-free (research is dated, today-stamped).
"""
from __future__ import annotations

import re
from datetime import date

import numpy as np

from engine import db
from engine.adapters import llm
from engine.adapters.llm import OPENROUTER_FREE_LEADERS
from engine.metaculus import api
from engine.metaculus import numeric as N
from engine.metaculus import research

QUANTILES = (0.05, 0.25, 0.5, 0.75, 0.95)

_NUM_SYSTEM = (
    "You are a superforecaster producing a CALIBRATED predictive distribution for a numeric quantity. "
    "Reason briefly: the reference class, what the dated evidence implies for the level and the trend, "
    "and how wide the genuine uncertainty is (do NOT output a near-point estimate — real outcomes "
    "surprise). Then give five percentiles of your predictive distribution. They must be strictly "
    "increasing. End with EXACTLY one line, numbers only, no units, no commas:\n"
    "PCTILES: 5=<v>; 25=<v>; 50=<v>; 75=<v>; 95=<v>"
)

_MC_SYSTEM = (
    "You are a superforecaster assigning probabilities across the EXACT listed options of a "
    "multiple-choice question. Reason briefly over the dated evidence, then give a probability to each "
    "option; they must sum to 1 and none should be 0 or 1. End with EXACTLY one line listing every "
    "option label verbatim:\nDIST: <label>=<p>; <label>=<p>; ..."
)


def _num_prompt(meta: dict, digest: str, today: str) -> str:
    lo, hi, unit = meta.get("range_min"), meta.get("range_max"), meta.get("unit") or ""
    parts = [f"Today is {today}.", f"Question: {meta['title']}"]
    if meta.get("resolution_criteria"):
        parts.append(f"Resolution criteria: {meta['resolution_criteria'][:800]}")
    if meta.get("description"):
        parts.append(f"Background: {meta['description'][:500]}")
    span = []
    if lo is not None and hi is not None:
        span.append(f"The question's plausible range is about {lo:g} to {hi:g} {unit}".rstrip())
    if meta.get("open_lower_bound"):
        span.append("values BELOW the range are allowed")
    if meta.get("open_upper_bound"):
        span.append("values ABOVE the range are allowed")
    if span:
        parts.append("; ".join(span) + ".")
    parts.append("\n" + digest)
    parts.append("\nGive your five calibrated percentiles for the resolved value.")
    return "\n".join(parts)


def _mc_prompt(meta: dict, digest: str, today: str) -> str:
    opts = "; ".join(str(o) for o in (meta.get("options") or []))
    parts = [f"Today is {today}.", f"Question: {meta['title']}"]
    if meta.get("resolution_criteria"):
        parts.append(f"Resolution criteria: {meta['resolution_criteria'][:800]}")
    if meta.get("description"):
        parts.append(f"Background: {meta['description'][:500]}")
    parts.append(f"Options (use these labels verbatim): {opts}")
    parts.append("\n" + digest)
    parts.append("\nGive a probability to every option.")
    return "\n".join(parts)


def _parse_pctiles(txt: str) -> dict | None:
    """Pull `PCTILES: 5=..; 25=..; ...` (or a loose `q=value` scatter) into {quantile: value}."""
    if not txt:
        return None
    line = ""
    for ln in txt.splitlines():
        if "PCTILES" in ln.upper():
            line = ln
            break
    hay = line or txt
    found = {}
    for q, v in re.findall(r'(\d{1,2})\s*=\s*(-?\d[\d,]*\.?\d*)', hay):
        qf = int(q) / 100.0
        if qf in QUANTILES:
            try:
                found[qf] = float(v.replace(",", ""))
            except ValueError:
                pass
    return found if len(found) >= 4 else None


def _parse_dist(txt: str, options: list) -> dict | None:
    """Map a `DIST: label=p; ...` line onto the exact option labels (case/space-insensitive match)."""
    if not txt:
        return None
    line = next((ln for ln in txt.splitlines() if "DIST" in ln.upper()), txt)

    def norm(s):
        return re.sub(r"\s+", " ", str(s).strip().lower())

    canon = {norm(o): o for o in options}
    out = {}
    for label, p in re.findall(r'([^=;:]+?)\s*=\s*(0?\.\d+|\d\.?\d*|1\.0+|0|1)', line):
        o = canon.get(norm(label))
        if o is not None:
            try:
                out[o] = float(p)
            except ValueError:
                pass
    return out if len(out) >= max(2, len(options) - 1) else None


def _council(prompt: str, system: str, models, n: int, provider: str) -> list[str]:
    """Raw completions from each model × n samples (keyless, $0). Returns the text blocks that came back."""
    conn = db.connect()
    texts = []
    try:
        for m in models:
            for _ in range(n):
                for _retry in range(2):
                    try:
                        txt = llm.complete(conn, prompt, provider=provider, system=system,
                                           model=m, max_tokens=700, est_cost_cents=0)
                        if txt:
                            texts.append(txt)
                        break
                    except Exception:
                        continue
    finally:
        conn.close()
    return texts


def forecast_numeric(meta: dict, *, today: str | None = None, proxy: str | None = None,
                     n: int = 1, provider: str = "openrouter_free",
                     models=None) -> dict | None:
    """Council → aggregated percentile band → valid Metaculus CDF. Returns {cdf, percentiles, n_models}."""
    today = today or date.today().isoformat()
    models = list(models or OPENROUTER_FREE_LEADERS)
    digest, sources = research.gather(meta, today, proxy=proxy, with_markets=True, provider=provider)
    prompt = _num_prompt(meta, digest, today)
    bands = [b for b in (_parse_pctiles(t) for t in _council(prompt, _NUM_SYSTEM, models, n, provider)) if b]
    if not bands:
        return None
    # median per quantile across the council, then enforce strictly-increasing values
    agg = {}
    for q in QUANTILES:
        vals = [b[q] for b in bands if q in b]
        if vals:
            agg[q] = float(np.median(vals))
    qs = sorted(agg)
    vs = np.maximum.accumulate([agg[q] for q in qs])
    # nudge any tie up so percentiles_to_cdf sees strictly-increasing anchors
    for i in range(1, len(vs)):
        if vs[i] <= vs[i - 1]:
            vs[i] = vs[i - 1] + max(1e-6, abs(vs[i - 1]) * 1e-4)
    pct = {q: float(v) for q, v in zip(qs, vs)}
    cdf = N.percentiles_to_cdf(pct, meta["continuous_range"],
                               meta["open_lower_bound"], meta["open_upper_bound"])
    return {"cdf": cdf, "percentiles": pct, "n_models": len(bands),
            "n_sources": len(sources)}


def forecast_mc(meta: dict, *, today: str | None = None, proxy: str | None = None,
                n: int = 1, provider: str = "openrouter_free", models=None) -> dict | None:
    """Council → mean option distribution → normalized Metaculus category vector."""
    today = today or date.today().isoformat()
    models = list(models or OPENROUTER_FREE_LEADERS)
    options = meta["options"]
    digest, sources = research.gather(meta, today, proxy=proxy, with_markets=True, provider=provider)
    prompt = _mc_prompt(meta, digest, today)
    dists = [d for d in (_parse_dist(t, options) for t in _council(prompt, _MC_SYSTEM, models, n, provider)) if d]
    if not dists:
        return None
    agg = {}
    for o in options:
        ps = [d[o] for d in dists if o in d]
        agg[o] = float(np.mean(ps)) if ps else 0.0
    vec = N.options_to_vector(agg, options)
    return {"vector": vec, "raw": agg, "n_models": len(dists), "n_sources": len(sources)}


# ───────────────────────────────────────────────────────── orchestrator (mirrors run.py)

def main():
    """Fill a tournament's open numeric + multiple-choice questions. Safe by default (dry-run prints,
    submits NOTHING) unless --submit is passed. Idempotent: a per-tournament log skips done qids.

    Usage:
      python -m engine.metaculus.numeric_forecast --tournament metaculus-cup-summer-2026          # dry
      python -m engine.metaculus.numeric_forecast --tournament metaculus-cup-summer-2026 --submit  # live
    """
    import json
    import sys
    import time
    from datetime import datetime, timezone
    from pathlib import Path

    args = sys.argv[1:]

    def opt(flag, default=None):
        return args[args.index(flag) + 1] if flag in args else default

    tournament = opt("--tournament")
    if not tournament:
        print("need --tournament <slug|id>"); sys.exit(2)
    do_submit = "--submit" in args
    n = int(opt("--n", "1"))
    proxy = opt("--proxy")
    today = date.today().isoformat()

    log_dir = Path(__file__).resolve().parents[2] / "data" / "metaculus"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / f"nonbinary_{tournament}.jsonl"
    done = set()
    if log.exists():
        done = {json.loads(l)["question_id"] for l in log.open() if l.strip()
                and json.loads(l).get("submitted")}

    posts = api.list_open_questions(tournament, forecast_type="binary,multiple_choice,numeric")
    nonbin = [p for p in posts if not api.binary_question(p)]
    print(f"{tournament}: {len(nonbin)} non-binary open "
          f"({'SUBMIT' if do_submit else 'DRY-RUN'})", flush=True)

    for i, p in enumerate(nonbin, 1):
        m = N.question_meta(p)
        qid = m["question_id"]
        if qid in done:
            print(f"[{i}/{len(nonbin)}] skip (done): {m['title'][:60]}"); continue
        try:
            if m["type"] == "multiple_choice":
                r = forecast_mc(m, today=today, proxy=proxy, n=n)
                payload = r and {"vector": r["vector"]}
            else:
                r = forecast_numeric(m, today=today, proxy=proxy, n=n)
                if r:
                    ok, msg = N.validate_cdf(r["cdf"], len(m["continuous_range"]))
                    if not ok:
                        print(f"[{i}/{len(nonbin)}] INVALID cdf ({msg}): {m['title'][:50]}"); continue
                payload = r and {"cdf": r["cdf"]}
        except Exception as e:
            print(f"[{i}/{len(nonbin)}] ERROR {str(e)[:90]}: {m['title'][:45]}"); continue
        if not r:
            print(f"[{i}/{len(nonbin)}] council empty: {m['title'][:55]}"); continue

        summary = (str({k: round(v, 2) for k, v in r["percentiles"].items()}) if "percentiles" in r
                   else str({k: round(v, 3) for k, v in r["vector"].items()}))
        print(f"[{i}/{len(nonbin)}] {m['type']:15s} models={r['n_models']} src={r['n_sources']} "
              f"{summary[:70]} | {m['title'][:42]}", flush=True)

        rec = {"question_id": qid, "post_id": m["post_id"], "type": m["type"],
               "title": m["title"], "n_models": r["n_models"],
               "at": datetime.now(timezone.utc).isoformat()}
        if do_submit:
            try:
                if "cdf" in payload:
                    N.submit_cdf(qid, payload["cdf"])
                else:
                    N.submit_multiple_choice(qid, payload["vector"])
                rec["submitted"] = True
                print("        submitted ✓", flush=True)
            except Exception as e:
                rec["submitted"] = False
                rec["error"] = str(e)[:300]
                print(f"        submit FAILED: {rec['error']}", flush=True)
            time.sleep(8)   # Cloudflare rate-limit pace
        with log.open("a") as f:
            f.write(json.dumps(rec) + "\n")

    print(f"\nlog → {log}")


if __name__ == "__main__":
    main()
