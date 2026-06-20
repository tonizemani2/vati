"""Live Metaculus arena bot — the judgmental forecasting pipeline (Cup + FutureEval AIB).

ForecastBench (engine/forecastbench/) wins the NUMERIC/dataset half zero-shot + series-grounded.
This package wins the JUDGMENTAL half — world-event questions whose answer lives in CURRENT news the
model's weights never saw. The architecture follows the only thing that has been shown to win this
arena (memory: forecastbench-news-layer-blocked + newbenchmarksplan.md): structured research →
reconciled keyless ensemble → extremize → crowd-anchor. Our asymmetry is cost: the research (keyless
Exa) and the ensemble (keyless DeepInfra roster) are both $0, so we sample harder than metered bots.
"""
