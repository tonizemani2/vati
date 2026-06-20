"""Submission pipeline — turn a round's question set into a valid ForecastBench
forecast file.

Singles: market = crowd anchor (calibrated), dataset = quant forecaster.
Combos:  the joint probability of the two sub-questions under independence, for
         each of the 4 directions [1,1],[1,0],[0,1],[0,0] (and each horizon for
         dataset combos), built from the single forecasts.

Output matches the FB schema:
  {organization, model, model_organization, question_set,
   forecasts:[{id, source, forecast, resolution_date, direction, reasoning}]}

Usage:
  uv run python -m engine.forecastbench.submit [--no-llm] <question_set.json> [out.json]
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from . import dataset as ds
from .market import crowd_anchor
from .score import DATA, MARKET_SOURCES, single_questions

QSET_URL = ("https://raw.githubusercontent.com/forecastingresearch/"
            "forecastbench-datasets/main/datasets/question_sets/{date}-llm.json")
LATEST_QSET_URL = ("https://raw.githubusercontent.com/forecastingresearch/"
                   "forecastbench-datasets/main/datasets/question_sets/latest-llm.json")
CONTENTS_QSET_URL = (
    "https://api.github.com/repos/forecastingresearch/forecastbench-datasets/"
    "contents/datasets/question_sets/{date}-llm.json?ref=main"
)
UNPUBLISHED_EXIT = 3


def _valid_cached_question_set(path: Path, date: str) -> bool:
    try:
        qd = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return (
        qd.get("forecast_due_date") == date
        and qd.get("question_set") == f"{date}-llm.json"
        and isinstance(qd.get("questions"), list)
        and bool(qd["questions"])
    )


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })


def _download(url: str) -> bytes:
    with urllib.request.urlopen(_request(url), timeout=60) as r:
        return r.read()


def _valid_question_set_bytes(raw: bytes, date: str) -> bytes | None:
    try:
        qd = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if (
        qd.get("forecast_due_date") == date
        and isinstance(qd.get("questions"), list)
        and bool(qd["questions"])
    ):
        qd.setdefault("question_set", f"{date}-llm.json")
        return json.dumps(qd).encode()
    return None


def _fetch_via_latest(date: str) -> bytes | None:
    """Best-effort fallback when the dated raw URL is behind the latest pointer."""
    try:
        raw = _download(LATEST_QSET_URL)
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None
    parsed = _valid_question_set_bytes(raw, date)
    if parsed is not None:
        return parsed

    pointer = raw.decode(errors="ignore").strip()
    if pointer != f"{date}-llm.json":
        return None
    try:
        raw = _download(QSET_URL.format(date=date))
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None
    return _valid_question_set_bytes(raw, date)


def _fetch_via_contents_api(date: str) -> bytes | None:
    """Fallback for the moment a file exists in GitHub API before raw catches up."""
    try:
        raw = _download(CONTENTS_QSET_URL.format(date=date))
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None
    try:
        payload = json.loads(raw)
        content = payload.get("content")
        encoding = payload.get("encoding")
        if not isinstance(content, str) or encoding != "base64":
            return None
        decoded = base64.b64decode(content)
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    return _valid_question_set_bytes(decoded, date)


def _download_question_set_bytes(date: str) -> bytes:
    try:
        raw = _download(QSET_URL.format(date=date))
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        raw = _fetch_via_latest(date)
        if raw is None:
            raw = _fetch_via_contents_api(date)
        if raw is None:
            raise e
    parsed = _valid_question_set_bytes(raw, date)
    if parsed is None:
        raise ValueError(f"downloaded question set for {date} is invalid or stale")
    return parsed


def fetch_question_set(date: str, force_refresh: bool = False) -> str:
    """Download a round's LLM question set by due date (the live workflow)."""
    out = DATA / f"q_{date}.json"
    force_refresh = force_refresh or os.getenv("FORECASTBENCH_REFRESH_QSET", "0") == "1"
    if out.exists() and not _valid_cached_question_set(out, date):
        out.unlink()
    if out.exists() and not force_refresh:
        return str(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        parsed = _download_question_set_bytes(date)
    except (urllib.error.HTTPError, urllib.error.URLError):
        if out.exists() and _valid_cached_question_set(out, date):
            print(f"WARNING: using cached question set for {date}; live refresh unavailable", file=sys.stderr)
            return str(out)
        raise
    out.write_bytes(parsed)
    return str(out)


def cached_question_set_is_current(date: str, qset_path: str | Path | None = None) -> int:
    """Exit-code helper: 0=current, 1=missing/stale, 3=live qset unavailable."""
    path = Path(qset_path) if qset_path is not None else DATA / f"q_{date}.json"
    if not path.exists() or not _valid_cached_question_set(path, date):
        print(f"cached question set missing or invalid for {date}: {path}", file=sys.stderr)
        return 1
    try:
        live = json.loads(_download_question_set_bytes(date))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"live question set for {date} is not published/currently unavailable", file=sys.stderr)
            return UNPUBLISHED_EXIT
        raise
    except urllib.error.URLError as e:
        print(f"live question set check for {date} is temporarily unavailable: {e}", file=sys.stderr)
        return UNPUBLISHED_EXIT
    cached = json.loads(path.read_text())
    if cached != live:
        print(f"cached question set differs from live question set for {date}: {path}", file=sys.stderr)
        return 1
    print(f"cached question set is current for {date}: {path}")
    return 0

DIRECTIONS = [[1, 1], [1, -1], [-1, 1], [-1, -1]]   # 1 = happens, -1 = doesn't
ORG = "Vaticinus"           # FINAL once on the leaderboard — matches the onboarding email (Jun 8)
MODEL = "vati-2.0"          # FINAL once on the leaderboard — do not rename casually


def build_single_forecasts(questions, due, use_llm=True):
    """Return ({id: {resolution_date_or_None: p}}, {id: reasoning}) for every
    single question.

    Defer-to-best: crowd anchor (market) and the quant models (dataset) win
    wherever they have a signal. The LLM leg (`llm_fill`, MiniMax-backed) is
    invoked ONLY on the residual gaps — questions with no crowd value / no
    fetchable series — i.e. the rows that would otherwise be a blind 0.5. So the
    LLM can only raise coverage quality, never override a real signal."""
    out, reasoning, gaps = {}, {}, []
    # market: crowd anchor (gap = no crowd value to anchor on)
    market = crowd_anchor(questions)
    for q in single_questions(questions):
        if q["source"] in MARKET_SOURCES:
            if q["id"] in market:
                out[q["id"]] = {None: market[q["id"]]}
            else:
                gaps.append(q)
    # dataset: quant per horizon (gap = series unfetchable -> empty forecast)
    ds.prefetch_round(questions)
    for q in single_questions(questions):
        if q["source"] not in MARKET_SOURCES:
            fc = ds.forecast_dataset_question(q, due)
            if fc:
                out[q["id"]] = {rd: p for rd, p in fc.items()}
            else:
                gaps.append(q)
    # residual gaps: LLM leg first, then honest 0.5 for anything still unfilled
    filled = {}
    if use_llm and gaps:
        from . import llm_fill
        filled = llm_fill.fill_gaps(gaps, due)
    for q in gaps:
        r = filled.get(q["id"])
        if r is None:
            out[q["id"]] = {None: 0.5}
            continue
        p, why = r
        reasoning[q["id"]] = why
        if q["source"] in MARKET_SOURCES:
            out[q["id"]] = {None: p}
        else:
            rds = q.get("resolution_dates")
            rds = rds if isinstance(rds, list) else [None]
            out[q["id"]] = {rd: p for rd in rds}
    return out, reasoning


def _sub_p(singles, sub_id, rd):
    """Single forecast for a sub-question at resolution_date rd (or None)."""
    d = singles.get(sub_id)
    if not d:
        return 0.5
    if rd in d:
        return d[rd]
    if None in d:
        return d[None]
    return next(iter(d.values()))


def build_forecasts(questions, due, use_llm=True):
    singles, reasoning = build_single_forecasts(questions, due, use_llm=use_llm)
    by_id = {q["id"]: q for q in single_questions(questions)}
    rows = []
    # single rows
    for q in single_questions(questions):
        for rd, p in singles[q["id"]].items():
            rows.append({"id": q["id"], "source": q["source"],
                         "forecast": round(float(p), 6),
                         "resolution_date": rd, "direction": None,
                         "reasoning": reasoning.get(q["id"])})
    # combo rows: 4 directions (1=happens, -1=doesn't). Same-source dataset combos
    # are correlated, so we form the joint via a Gaussian copula whose correlation
    # is estimated from the two series' own history (ds.combo_corr, 0 hyperparams,
    # leak-free). rho~0 reduces to independence -> market/non-numeric combos and
    # thin samples fall back to p1*p2 exactly.
    for q in questions:
        if not isinstance(q["id"], list):
            continue
        sub = q.get("combination_of")
        if not isinstance(sub, list) or len(sub) != 2:
            continue
        id1, id2 = sub[0]["id"], sub[1]["id"]
        # horizons: dataset combos inherit the sub-question's resolution_dates;
        # market combos resolve at a single date submitted as null (FB matches by id).
        sub_q = by_id.get(id1) or by_id.get(id2)
        rds = sub_q.get("resolution_dates") if sub_q else None
        rds = rds if isinstance(rds, list) else [None]
        is_dataset_combo = q["source"] in ds.DATASET_SOURCES
        for rd in rds:
            p1, p2 = _sub_p(singles, id1, rd), _sub_p(singles, id2, rd)
            rho = 0.0
            if is_dataset_combo and rd is not None:
                horizon = (ds._d(rd) - due).days
                rho = ds.combo_corr(sub[0], sub[1], due, horizon)
            j11 = ds.joint_up(p1, p2, rho)            # P(both happen)
            joints = {(1, 1): j11, (1, -1): p1 - j11,
                      (-1, 1): p2 - j11, (-1, -1): 1 - p1 - p2 + j11}
            for d1, d2 in DIRECTIONS:
                j = max(0.0, min(1.0, joints[(d1, d2)]))
                rows.append({"id": q["id"], "source": q["source"],
                             "forecast": round(float(j), 6),
                             "resolution_date": rd, "direction": [d1, d2],
                             "reasoning": None})
    return rows


def _coverage(questions, rows) -> dict:
    """Fraction of SINGLE market / dataset questions that got ≥1 forecast row.
    FB rule: ≥95% of each, else the set is excluded from the leaderboard."""
    forecasted = {_key_id(r["id"]) for r in rows if r["direction"] is None}
    mkt = [q for q in single_questions(questions) if q["source"] in MARKET_SOURCES]
    dat = [q for q in single_questions(questions) if q["source"] not in MARKET_SOURCES]
    def frac(qs):
        if not qs:
            return 1.0
        return sum(1 for q in qs if q["id"] in forecasted) / len(qs)
    return {"market": frac(mkt), "dataset": frac(dat),
            "n_market": len(mkt), "n_dataset": len(dat)}


def _key_id(qid):
    return tuple(qid) if isinstance(qid, list) else qid


def make_submission(qset_path: str, out_path: str | None = None, n: int = 1,
                    use_llm: bool = True):
    """Build a leaderboard-valid forecast set.

    The uploaded file MUST be named <forecast_due_date>.<organization>.<N>.json
    and contain exactly the 5 FB schema keys (no extras). N is the submission
    number for the round (1–3). Verifies ≥95% coverage of market AND dataset
    singles before writing — below that, FB drops the whole set."""
    qd = json.loads(Path(qset_path).read_text())
    questions = qd["questions"]
    due_str = qd["forecast_due_date"]
    due = datetime.strptime(due_str, "%Y-%m-%d").date()
    rows = build_forecasts(questions, due, use_llm=use_llm)
    # exactly the 5 documented root keys — no forecast_due_date (the schema has none)
    sub = {"organization": ORG, "model": MODEL, "model_organization": ORG,
           "question_set": qd["question_set"], "forecasts": rows}
    # FB upload naming: <due>.<org>.<N>.json
    out_path = out_path or f"data/forecastbench/{due_str}.{ORG}.{n}.json"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(sub))
    n_single = sum(1 for r in rows if r["direction"] is None)
    n_combo = len(rows) - n_single
    cov = _coverage(questions, rows)
    flag = "" if (cov["market"] >= 0.95 and cov["dataset"] >= 0.95) else "  ⚠ BELOW 95% — set will be EXCLUDED"
    print(f"wrote {out_path}: {len(rows)} rows ({n_single} single, {n_combo} combo)")
    print(f"  coverage: market {cov['market']:.1%} ({cov['n_market']})  "
          f"dataset {cov['dataset']:.1%} ({cov['n_dataset']}){flag}")
    return out_path


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--check-current":
        if len(argv) not in (2, 3):
            print(
                "usage: python -m engine.forecastbench.submit "
                "--check-current <YYYY-MM-DD> [qset.json]",
                file=sys.stderr,
            )
            return 2
        return cached_question_set_is_current(argv[1], argv[2] if len(argv) == 3 else None)
    use_llm = True
    force_refresh = False
    if argv and argv[0] == "--refresh-qset":
        force_refresh = True
        argv = argv[1:]
    if argv and argv[0] == "--no-llm":
        use_llm = False
        argv = argv[1:]
    elif argv and argv[0] == "--llm":
        use_llm = True
        argv = argv[1:]
    if not argv:
        print(
            "usage: python -m engine.forecastbench.submit "
            "[--refresh-qset] [--no-llm|--llm] <question_set.json|YYYY-MM-DD> [out.json]",
            file=sys.stderr,
        )
        return 2
    arg = argv[0]
    # live mode: a bare YYYY-MM-DD due date -> download the round's question set
    if len(arg) == 10 and arg[4] == "-" and not arg.endswith(".json"):
        try:
            arg = fetch_question_set(arg, force_refresh=force_refresh)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"question set for {arg} is not published yet", file=sys.stderr)
                return UNPUBLISHED_EXIT
            raise
        except urllib.error.URLError as e:
            print(f"question set fetch for {arg} is temporarily unavailable: {e}", file=sys.stderr)
            return UNPUBLISHED_EXIT
    make_submission(arg, argv[1] if len(argv) > 1 else None, use_llm=use_llm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
