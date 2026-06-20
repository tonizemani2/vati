"""Claude-native, web-researching gap fill for ForecastBench.

The mechanical pipeline (submit.build_single_forecasts) covers market questions with the
crowd anchor and dataset questions with the quant models. Anything it CANNOT cover -- a
market question with no crowd value, or a dataset question whose series is unfetchable --
currently falls back to a BLIND 0.5. The Bedrock `llm_fill` leg can fill those, but it
forecasts from model memory with NO live data access.

This module is the Claude-native replacement Ruben asked for ("if we don't have the data,
web-browse to get it"): it
  1. `scan`s a qset for the exact gap questions, emitting a worklist the `forecastbench-judge`
     Claude workflow can WEB-RESEARCH (the workflow agents do live WebSearch/WebFetch), and
  2. `overlay`s the researched forecasts onto the mechanical submission so a gap is never a
     blind 0.5.
It does NOT touch the quant or crowd signals (defer-to-best) -- it only replaces would-be-0.5
rows. Leak-safe on forward rounds (the agent researches as of the due date). No AWS.

  python -m engine.forecastbench.gap_claude scan    <qset.json> <gaps.jsonl>
  python -m engine.forecastbench.gap_claude overlay <qset.json> <mechanical.json> <gap_forecasts.json> <out.json>

Runbook (only needed if `scan` finds gaps > 0; on recent rounds coverage is 100% so it is a no-op):
  1. scan q_<due>.json /tmp/fb_gaps.jsonl
  2. feed the rows to the forecastbench-judge workflow (args={questions:[...], council:1}); save -> /tmp/gap_fc.json
  3. overlay q_<due>.json <mechanical .1.json> /tmp/gap_fc.json <mechanical .1.json>   (then re-run check_submission)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from . import dataset as ds
from .market import crowd_anchor
from .score import MARKET_SOURCES, single_questions


def find_gaps(questions, due):
    """The single questions the mechanical pipeline cannot cover (would be a blind 0.5)."""
    market = crowd_anchor(questions)
    ds.prefetch_round(questions)
    gaps = []
    for q in single_questions(questions):
        if q["source"] in MARKET_SOURCES:
            covered = q["id"] in market
        else:
            covered = bool(ds.forecast_dataset_question(q, due))
        if not covered:
            gaps.append(q)
    return gaps


def scan(qset_path, out_path=None):
    qd = json.loads(Path(qset_path).read_text())
    questions = qd["questions"]
    due = datetime.strptime(qd["forecast_due_date"], "%Y-%m-%d").date()
    gaps = find_gaps(questions, due)
    rows = []
    for q in gaps:
        rows.append({
            "id": q["id"],
            "source": q["source"],
            "due": qd["forecast_due_date"],
            "question": (q.get("question") or "").strip(),
            "resolution_criteria": str(q.get("resolution_criteria")
                                       or q.get("market_info_resolution_criteria") or "").strip()[:1200],
            "background": str(q.get("background") or "").strip()[:800],
            "crowd_value": None,   # gap => no usable crowd/quant signal; research from scratch
            "resolution_dates": q.get("resolution_dates"),
        })
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text("".join(json.dumps(r) + "\n" for r in rows))
    n_singles = len(single_questions(questions))
    print(f"gap scan: {len(rows)} uncovered of {n_singles} single questions"
          + (f" -> {out_path}" if out_path else "")
          + ("  (coverage is complete; nothing to web-fill)" if not rows else ""))
    return rows


def _key(qid):
    return tuple(qid) if isinstance(qid, list) else qid


def load_forecasts(path):
    """Accept {id:{probability,...}} dict / list / JSONL (like opus_blend.load_opus)."""
    txt = Path(path).read_text().strip()
    out = {}
    if not txt:
        return out
    try:
        obj = json.loads(txt)
        rows = ([{**v, "id": v.get("id", k)} for k, v in obj.items()] if isinstance(obj, dict)
                else obj if isinstance(obj, list) else [])
    except json.JSONDecodeError:
        rows = [json.loads(line) for line in txt.splitlines() if line.strip()]
    for r in rows:
        try:
            p = float(r["probability"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0.0 <= p <= 1.0:
            out[_key(r["id"])] = min(0.98, max(0.02, p))
    return out


def overlay(qset_path, mech_path, forecasts_path, out_path):
    """Replace the blind-0.5 gap rows in a mechanical submission with researched
    probabilities. Only rows for gap questions are touched; combos are left alone."""
    qd = json.loads(Path(qset_path).read_text())
    questions = qd["questions"]
    due = datetime.strptime(qd["forecast_due_date"], "%Y-%m-%d").date()
    gap_ids = {_key(q["id"]) for q in find_gaps(questions, due)}
    fc = load_forecasts(forecasts_path)

    sub = json.loads(Path(mech_path).read_text())
    moved = 0
    for row in sub["forecasts"]:
        if row.get("direction") is not None:   # singles only; combos untouched
            continue
        k = _key(row["id"])
        if k in gap_ids and k in fc:
            if abs(float(row["forecast"]) - fc[k]) > 1e-9:
                moved += 1
            row["forecast"] = round(fc[k], 6)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(sub))
    filled = len([k for k in gap_ids if k in fc])
    print(f"overlay: {len(gap_ids)} gap(s); filled {filled} with research; "
          f"moved {moved} rows off 0.5 -> {out_path}")
    return out_path


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "scan":
        scan(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "overlay":
        overlay(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    else:
        print(__doc__)
        sys.exit(1)
