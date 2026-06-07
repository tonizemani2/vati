"""ForecastBench bot — a self-contained subsystem that competes on the
Forecasting Research Institute's ForecastBench (https://forecastbench.org).

Different game from the structural-foresight thesis: here we answer the
benchmark's 500 single (+500 combo) resolvable questions per biweekly round
and are scored by Brier. The honest edge levers, in order of payoff:
  1. dataset questions (fred/yfinance/dbnomics/acled/wikipedia) — score from
     real point-in-time time series, not LLM guesses (clean, no leakage);
  2. market questions — crowd-forecast anchor + news-retrieval LLM ensemble;
  3. calibration of the blend.

Keyless-first (CONSTITUTION rule 3): build + validate on free data; any paid
news/API spend is costed and approved before use.
"""
