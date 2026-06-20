# Forecast System Control Plane

Implemented changes:

- Append-only decision ledger at `data/forecasting/decisions.jsonl` via
  `engine.forecasting.ledger.append_decision`.
- Binary shadow forecasts for Metaculus decisions: raw ensemble, extremized,
  crowd-only, no-crowd, and blind-shrink variants where applicable.
- Shadow Brier scorer via `engine.forecasting.ledger.score_binary_shadows` for
  resolved binary records.
- Calibration artifact guard via `engine.forecasting.calibration.check_artifact`
  so tiny or malformed calibration runs cannot be treated as decision-grade.
- Stricter cross-market anchor gate in `engine.metaculus.markets`: title
  similarity alone is no longer enough when thresholds, deadlines, years, or
  directions disagree.
- FutureEval now writes every dry-run/live decision to the central ledger without
  needing Opus/Bedrock for the logging layer.
- External market anchors are logging/shadow-only by default in FutureEval. Set
  `FE_USE_EXTERNAL_ANCHOR=1` only after live shadow scoring proves they improve
  submitted Brier.
- `python -m engine.forecasting.eval_anchor_gate` reproduces the historical
  qbank simulation used to decide the external-anchor default.
- Saved result: `data/forecasting/anchor_gate_eval_2026-06-17.json`.

Local improvement test:

- The old title-similarity gate would accept:
  - `Bitcoin exceeds $100,000 before August 1, 2025?` as a match for a
    `$138,000` question.
  - `Bitcoin exceeds $138,000 before December 31, 2025?` as a match for an
    `August 1, 2025` question.
- The new hard gate rejects both while still accepting an exact China/Taiwan
  deadline match.

Verification:

- `python -m unittest discover -s tests`
- `python -m py_compile engine/forecasting/__init__.py engine/forecasting/calibration.py engine/forecasting/ledger.py engine/metaculus/markets.py engine/metaculus/forecast.py data/metaculus/futureeval_update.py tests/test_forecasting_control_plane.py`
- `python -m engine.forecasting.eval_anchor_gate`
