"""Prophet Arena agent — wraps our research→ensemble→calibrate→market-anchor pipeline
into the Prophet Arena `predict(event)->dict` contract.

Recon (2026-06-12, memory: prophet-arena-target): the winnable board is the AGENT leaderboard
(web + tools allowed, 1h/event). Only agentic research harnesses beat the Kalshi market there;
every fixed-context model — including Lightning Rod's Foresight V3 (now #11/last) — loses to it.
Our edge: start from the GIVEN Kalshi price, deviate only on dated evidence, calibrate hard,
decorrelate via the keyless model roster + structured feeds. The market price maps straight onto
forecast_question's `crowd` anchor (CROWD_WEIGHT log-odds pull).
"""
