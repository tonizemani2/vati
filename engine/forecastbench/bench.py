"""Benchmark-rounds harvester — the EXACT target distribution, free, from our own cache.

The highest-fidelity training data isn't more Manifold — it's ForecastBench's OWN resolved rounds. We
join the cached question sets (`q_*.json`) with the resolution files (`r_*.json`) by id and mint unified
rows. This is the only source of **Metaculus / Polymarket / INFER** market questions (variety we otherwise
lack) and **ACLED / Wikipedia** dataset question-types, and it carries the **crowd anchor**
(`freeze_datetime_value`) — the strong market-half baseline + an ensemble feature.

Leak-safe: a row exists only if the round RESOLVED (outcome known). as_of = the round's forecast_due_date;
`leak_ok` vs --cutoff. Crowd prob is kept as a FIELD, not put in the context (we want the model to reason,
not copy the crowd — though copying the crowd is the winning move on the market half at submission time).

Run:  python -m engine.forecastbench.bench [--cutoff YYYY-MM-DD] [--out PATH]
"""
from __future__ import annotations

import glob
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from .domains import tag_domain

DATA = Path(__file__).resolve().parents[2] / "data" / "forecastbench"
OUT_DEFAULT = DATA / "trainset" / "bench_questions.jsonl"
MARKET = {"manifold", "metaculus", "polymarket", "infer"}


def _questions_by_id():
    """id → (question dict, forecast_due_date of its round)."""
    out = {}
    for f in glob.glob(str(DATA / "q_*.json")):
        d = json.loads(Path(f).read_text())
        due = d.get("forecast_due_date") if isinstance(d, dict) else None
        rows = d["questions"] if isinstance(d, dict) else d
        for q in rows:
            if not isinstance(q.get("id"), list):
                out[q["id"]] = (q, due)
    return out


def _resolutions():
    out = []
    for f in glob.glob(str(DATA / "r_*.json")):
        d = json.loads(Path(f).read_text())
        for r in (d.get("resolutions") or []):
            if not isinstance(r.get("id"), list) and r.get("resolved"):
                out.append(r)
    return out


def build(cutoff):
    qbi = _questions_by_id()
    rows, drops, seen = [], Counter(), set()
    for r in _resolutions():
        q_due = qbi.get(r["id"])
        if not q_due:
            drops["no_question"] += 1
            continue
        q, due = q_due
        rd = r.get("resolution_date")
        key = (r["id"], rd)
        if key in seen:
            continue
        seen.add(key)
        rt = r.get("resolved_to")
        if rt is None:
            drops["no_outcome"] += 1
            continue
        outcome = 1 if float(rt) >= 0.5 else 0
        src = q["source"]
        is_mkt = src in MARKET
        res_date = rd if rd and rd != "N/A" else None
        leak_date = res_date or due
        leak_ok = (cutoff is None) or (leak_date and leak_date > cutoff)
        # freeze_datetime_value is a CROWD PROBABILITY only for MARKET sources (manifold/metaculus/
        # polymarket/infer, all in [0,1]). For DATASET sources it is the raw SERIES LEVEL at the freeze
        # date (e.g. PAYEMS=159000000, a yield=4.5) — NOT a probability. Storing a level as crowd_prob
        # poisoned the data: curate.py injected "P(YES)=159000000" anchors and ensemble scored a 0.47
        # Brier. Fix: crowd_prob only for market rows in [0,1]; the dataset freeze level is surfaced as a
        # plain (leak-safe, as-of) fact in context instead, where it actually helps a level/threshold Q.
        crowd = None
        level_fact = ""
        fv = q.get("freeze_datetime_value")
        if fv not in (None, "", "N/A"):
            try:
                fvf = float(fv)
                if is_mkt and 0.0 <= fvf <= 1.0:
                    crowd = round(fvf, 4)
                elif not is_mkt:
                    level_fact = f" Most recent value as of {due}: {fvf:g}."
            except (TypeError, ValueError):
                pass
        qtext = (q.get("question") or "").replace("{resolution_date}", res_date or "the resolution date") \
                                          .replace("{forecast_due_date}", due or "the due date")
        bg = (q.get("background") or "")[:500]
        rows.append({
            "id": f"bench-{r['id'][:16]}-{res_date or 'mkt'}", "source": src,
            "kind": "market" if is_mkt else "dataset", "question": qtext,
            "resolution_criteria": (q.get("resolution_criteria") or q.get("market_info_resolution_criteria")
                                    or "")[:800],
            "as_of_date": due, "resolution_date": res_date,
            "horizon_days": ((datetime.strptime(res_date, "%Y-%m-%d") - datetime.strptime(due, "%Y-%m-%d")).days
                             if (res_date and due) else None),
            "context": (f"Question from a forecasting benchmark, as of {due}.{level_fact} {bg}").strip(),
            "crowd_prob": crowd, "model_prob": None, "outcome": outcome,
            "domain": tag_domain(qtext), "base_model_cutoff": cutoff if cutoff else None,
            "leak_ok": bool(leak_ok), "trace": None,
        })
    return rows, drops


def main():
    args = sys.argv[1:]
    cutoff = args[args.index("--cutoff") + 1] if "--cutoff" in args else None
    out = Path(args[args.index("--out") + 1] if "--out" in args else OUT_DEFAULT)
    rows, drops = build(cutoff)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    bal = Counter(r["outcome"] for r in rows)
    crowd_n = sum(1 for r in rows if r["crowd_prob"] is not None)
    print(f"built {len(rows)} benchmark rows → {out}")
    print(f"  by source: {dict(Counter(r['source'] for r in rows))}")
    print(f"  market rows with crowd anchor: {crowd_n}")
    print(f"  label balance: YES={bal[1]} NO={bal[0]} | leak_ok: {sum(r['leak_ok'] for r in rows)}")
    print(f"  by domain: {dict(Counter(r['domain'] for r in rows).most_common())}")
    print(f"  dropped: {dict(drops)}")


if __name__ == "__main__":
    main()
