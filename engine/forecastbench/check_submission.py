"""Validate a ForecastBench submission against its question set before upload."""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

from .score import MARKET_SOURCES, single_questions
from .submit import DIRECTIONS

EXPECTED_ROOT_KEYS = {"organization", "model", "model_organization", "question_set", "forecasts"}
EXPECTED_ROW_KEYS = {"id", "source", "forecast", "resolution_date", "direction", "reasoning"}


def _key(qid):
    return tuple(qid) if isinstance(qid, list) else qid


def _qkey(source, qid):
    return source, _key(qid)


def _dir_key(direction):
    return tuple(direction) if isinstance(direction, list) else direction


def _resolution_dates(q: dict, singles_by_id: dict) -> list[str | None]:
    if q["source"] in MARKET_SOURCES:
        return [None]
    rds = q.get("resolution_dates")
    if isinstance(q.get("id"), list):
        combo = q.get("combination_of")
        if isinstance(combo, list) and len(combo) == 2:
            sub_q = (
                singles_by_id.get(_qkey(combo[0].get("source"), combo[0].get("id")))
                or singles_by_id.get(_qkey(combo[1].get("source"), combo[1].get("id")))
            )
            if sub_q:
                rds = sub_q.get("resolution_dates")
    return rds if isinstance(rds, list) and rds else [None]


def expected_forecast_keys(questions: list[dict]) -> set[tuple]:
    singles_by_id = {_qkey(q["source"], q["id"]): q for q in single_questions(questions)}
    out = set()
    for q in questions:
        qid = _key(q["id"])
        rds = _resolution_dates(q, singles_by_id)
        directions = [tuple(d) for d in DIRECTIONS] if isinstance(q["id"], list) else [None]
        for rd in rds:
            for direction in directions:
                out.add((q["source"], qid, rd, direction))
    return out


def validate(qset: dict, submission: dict, min_coverage: float = 0.95) -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warnings: list[str] = []
    questions = qset.get("questions")
    if not isinstance(questions, list) or not questions:
        errors.append("question set has no questions")
        return errors, warnings, {}

    if set(submission) != EXPECTED_ROOT_KEYS:
        errors.append(f"bad top-level keys: {sorted(submission)}")
    if submission.get("question_set") != qset.get("question_set"):
        errors.append(
            f"question_set mismatch: submission={submission.get('question_set')!r} "
            f"qset={qset.get('question_set')!r}"
        )

    rows = submission.get("forecasts")
    if not isinstance(rows, list) or not rows:
        errors.append("no forecasts in submission")
        return errors, warnings, {}

    by_id = {_qkey(q["source"], q["id"]): q for q in questions}
    expected = expected_forecast_keys(questions)
    seen = set()
    singles_seen = set()
    combo_groups = defaultdict(float)

    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"row {i} is not an object")
            continue
        missing_keys = EXPECTED_ROW_KEYS - set(row)
        if missing_keys:
            errors.append(f"row {i} missing keys: {sorted(missing_keys)}")
            continue

        source = row.get("source")
        qid = _key(row.get("id"))
        q = by_id.get((source, qid))
        if q is None:
            errors.append(f"row {i} unknown source/id: {source!r} {row.get('id')!r}")
            continue

        p = row.get("forecast")
        if isinstance(p, bool) or not isinstance(p, (int, float)) or math.isnan(float(p)) or not 0 <= float(p) <= 1:
            errors.append(f"row {i} bad probability: {p!r}")

        direction = row.get("direction")
        if isinstance(q.get("id"), list):
            if (
                not isinstance(direction, list)
                or len(direction) != 2
                or any(d not in (-1, 1) for d in direction)
            ):
                errors.append(f"row {i} bad combo direction: {direction!r}")
            direction_key = _dir_key(direction)
        else:
            if direction is not None:
                errors.append(f"row {i} single question has non-null direction: {direction!r}")
            direction_key = None
            singles_seen.add((source, qid))

        rd = row.get("resolution_date")
        allowed_rds = set(_resolution_dates(q, by_id))
        if q["source"] in MARKET_SOURCES:
            if rd is not None:
                errors.append(f"row {i} market resolution_date must be null: {rd!r}")
        elif rd not in allowed_rds:
            errors.append(f"row {i} unexpected resolution_date for {row.get('id')!r}: {rd!r}")

        fkey = (source, qid, rd, direction_key)
        if fkey in seen:
            errors.append(f"duplicate forecast key at row {i}: {fkey!r}")
        seen.add(fkey)
        if fkey not in expected:
            errors.append(f"row {i} not expected from qset: {fkey!r}")
        if isinstance(q.get("id"), list) and isinstance(direction_key, tuple) and isinstance(p, (int, float)):
            combo_groups[(source, qid, rd)] += float(p)

    missing_expected = expected - seen
    if missing_expected:
        examples = sorted(map(repr, list(missing_expected)[:5]))
        errors.append(f"missing {len(missing_expected)} expected forecast rows, examples: {examples}")

    market_singles = [q for q in single_questions(questions) if q["source"] in MARKET_SOURCES]
    dataset_singles = [q for q in single_questions(questions) if q["source"] not in MARKET_SOURCES]

    def cov(qs):
        return 1.0 if not qs else sum(1 for q in qs if _qkey(q["source"], q["id"]) in singles_seen) / len(qs)

    market_cov = cov(market_singles)
    dataset_cov = cov(dataset_singles)
    if market_cov < min_coverage:
        errors.append(f"market single coverage {market_cov:.1%} below {min_coverage:.1%}")
    if dataset_cov < min_coverage:
        errors.append(f"dataset single coverage {dataset_cov:.1%} below {min_coverage:.1%}")

    for group, total in combo_groups.items():
        if abs(total - 1.0) > 0.002:
            warnings.append(f"combo probabilities sum to {total:.6f} for {group!r}")

    summary = {
        "rows": len(rows),
        "expected_rows": len(expected),
        "market_coverage": market_cov,
        "dataset_coverage": dataset_cov,
        "market_singles": len(market_singles),
        "dataset_singles": len(dataset_singles),
    }
    return errors, warnings, summary


def validate_paths(qset_path: str | Path, submission_path: str | Path) -> tuple[list[str], list[str], dict]:
    qset = json.loads(Path(qset_path).read_text())
    submission = json.loads(Path(submission_path).read_text())
    return validate(qset, submission)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print("usage: python -m engine.forecastbench.check_submission <qset.json> <submission.json>", file=sys.stderr)
        return 2
    errors, warnings, summary = validate_paths(argv[0], argv[1])
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        "submission preflight OK: "
        f"rows={summary['rows']} expected={summary['expected_rows']} "
        f"market={summary['market_coverage']:.1%} dataset={summary['dataset_coverage']:.1%}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
