"""Before/after eval: does TimesFM improve the dataset half? — leak-free, no-overfit.

For the three numeric dataset sources (fred, dbnomics, yfinance), score, per source,
on every resolved row of every past round:

  incumbent : dataset.forecast_dataset_question (the model as submitted, calibrated)
  timesfm   : timesfm_model.p_higher_timesfm     (raw quantile -> P(higher))
  blend     : 0.5*incumbent + 0.5*timesfm        (where timesfm is available)

TimesFM only covers horizons that fit its compiled window, so we report two views:
  - HEAD-TO-HEAD on the TimesFM-covered subset (apples-to-apples on the same rows)
  - WHOLE SOURCE: incumbent-everywhere vs blend-where-available (the real adoption number)

Leak-free: TimesFM is fed only point-in-time-truncated numbers (no dates/ids), and the
incumbent already truncates to <= due. Built once, scored on rounds it never saw.

Run: uv run python -m engine.forecastbench.timesfm_eval [--sources fred,dbnomics] [--rounds N] [--limit K]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from . import dataset as ds
from . import timesfm_model as tfm
from .score import DATA, load_round, resolved_rows, single_questions

NUMERIC_SOURCES = ("fred", "dbnomics", "yfinance")
OUT_JSON = DATA / "timesfm_eval.json"
OUT_MD = Path(__file__).resolve().parents[2] / "experiments" / "timesfm_dataset_eval.md"


def _freeze(q):
    try:
        return float(q.get("freeze_datetime_value"))
    except (TypeError, ValueError):
        return None


def _history(q):
    """Point-in-time-safe fetch via the existing cached fetchers (cache-only friendly)."""
    try:
        src = q["source"]
        if src == "yfinance":
            return ds.fetch_yahoo(q["id"])
        if src == "fred":
            return ds.fetch_fred(q["id"])
        if src == "dbnomics":
            return ds.fetch_dbnomics(q["url"])
    except Exception:
        return None
    return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default=",".join(NUMERIC_SOURCES),
                    help="comma list of numeric sources to evaluate")
    ap.add_argument("--rounds", type=int, default=0,
                    help="only the most recent N resolved rounds (0 = all)")
    ap.add_argument("--limit", type=int, default=0,
                    help="cap questions per source per round (0 = no cap) — for a fast smoke run")
    args = ap.parse_args(argv)
    sources = tuple(s.strip() for s in args.sources.split(",") if s.strip())

    if not tfm.available():
        print("TimesFM model unavailable — aborting (install timesfm[torch]).")
        sys.exit(1)

    rounds = sorted(p.name[2:12] for p in Path(DATA).glob("q_*.json")
                    if len(p.name) == len("q_YYYY-MM-DD.json")
                    and (DATA / f"r_{p.name[2:12]}.json").exists())
    if args.rounds:
        rounds = rounds[-args.rounds:]

    # per-source accumulators
    # subset = rows where TimesFM produced a value (head-to-head)
    # all    = every resolved row of the source (whole-source adoption)
    sub = defaultdict(lambda: {"inc": 0.0, "tfm": 0.0, "blend": 0.0, "n": 0})
    allr = defaultdict(lambda: {"inc": 0.0, "blend": 0.0, "n": 0})

    for dt in rounds:
        try:
            questions, resolutions = load_round(dt)
        except FileNotFoundError:
            continue
        due = datetime.strptime(dt, "%Y-%m-%d").date()
        rows = resolved_rows(resolutions, sources=set(sources))
        if not rows:
            continue
        ds.prefetch_round(questions, sources=set(sources))

        # forecasts keyed by (id, rd): incumbent + timesfm
        inc_fc, tfm_fc = {}, {}
        per_src_count = defaultdict(int)
        for q in single_questions(questions):
            src = q["source"]
            if src not in sources:
                continue
            if args.limit and per_src_count[src] >= args.limit:
                continue
            per_src_count[src] += 1
            for rd, p in ds.forecast_dataset_question(q, due).items():
                inc_fc[(q["id"], rd)] = p
            hist = _history(q)
            if hist:
                res_dates = q.get("resolution_dates") or []
                for rd, p in tfm.p_higher_timesfm(hist, due, res_dates, freeze=_freeze(q)).items():
                    tfm_fc[(q["id"], rd)] = p

        for x in rows:
            src, rd, y = x["source"], x["resolution_date"], x["resolved_to"]
            key = (x["id"], rd)
            pi = inc_fc.get(key)
            if pi is None:
                pi = 0.5
            pt = tfm_fc.get(key)
            a = allr[src]
            a["n"] += 1
            a["inc"] += (pi - y) ** 2
            blend_all = pi if pt is None else 0.5 * pi + 0.5 * pt
            a["blend"] += (blend_all - y) ** 2
            if pt is not None:
                s = sub[src]
                s["n"] += 1
                s["inc"] += (pi - y) ** 2
                s["tfm"] += (pt - y) ** 2
                s["blend"] += (0.5 * pi + 0.5 * pt - y) ** 2
        print(f"  scored round {dt}", flush=True)

    # ---- report ----
    lines = []
    lines.append("# TimesFM vs incumbent — dataset-half Brier (leak-free backtest)\n")
    lines.append(f"_rounds: {len(rounds)} | sources: {', '.join(sources)} | "
                 f"generated {date.today().isoformat()}_\n")
    lines.append("## Head-to-head on the TimesFM-covered subset (same rows)\n")
    lines.append("| source | n | incumbent | timesfm | blend | best | Δ(blend−inc) |")
    lines.append("|---|---:|---:|---:|---:|---|---:|")
    result = {"rounds": rounds, "sources": list(sources), "subset": {}, "whole": {}}
    for src in sources:
        s = sub[src]
        if not s["n"]:
            lines.append(f"| {src} | 0 | — | — | — | — | — |")
            continue
        bi, bt, bb, n = s["inc"]/s["n"], s["tfm"]/s["n"], s["blend"]/s["n"], s["n"]
        best = min((bi, "incumbent"), (bt, "timesfm"), (bb, "blend"))[1]
        lines.append(f"| {src} | {n} | {bi:.4f} | {bt:.4f} | {bb:.4f} | **{best}** | {bb-bi:+.4f} |")
        result["subset"][src] = {"n": n, "incumbent": bi, "timesfm": bt, "blend": bb, "best": best}

    lines.append("\n## Whole source: incumbent-everywhere vs blend-where-available (adoption number)\n")
    lines.append("| source | n | coverage | incumbent | blend | Δ |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    tot_inc = tot_blend = tot_n = 0
    for src in sources:
        a = allr[src]
        if not a["n"]:
            continue
        bi, bb, n = a["inc"]/a["n"], a["blend"]/a["n"], a["n"]
        cov = sub[src]["n"] / n if n else 0.0
        tot_inc += a["inc"]; tot_blend += a["blend"]; tot_n += n
        lines.append(f"| {src} | {n} | {cov*100:.0f}% | {bi:.4f} | {bb:.4f} | {bb-bi:+.4f} |")
        result["whole"][src] = {"n": n, "coverage": cov, "incumbent": bi, "blend": bb, "delta": bb-bi}
    if tot_n:
        lines.append(f"| **pooled** | {tot_n} | | {tot_inc/tot_n:.4f} | {tot_blend/tot_n:.4f} | "
                     f"{(tot_blend-tot_inc)/tot_n:+.4f} |")
        result["pooled"] = {"n": tot_n, "incumbent": tot_inc/tot_n, "blend": tot_blend/tot_n,
                            "delta": (tot_blend-tot_inc)/tot_n}

    lines.append("\n_Lower Brier = better. 'blend' = 0.5·incumbent + 0.5·timesfm where TimesFM "
                 "covered the horizon, else incumbent. Negative Δ = TimesFM helps._\n")

    report = "\n".join(lines)
    print("\n" + report)
    OUT_JSON.write_text(json.dumps(result, indent=2))
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(report)
    print(f"\nsaved -> {OUT_JSON}\nsaved -> {OUT_MD}")


if __name__ == "__main__":
    main()
