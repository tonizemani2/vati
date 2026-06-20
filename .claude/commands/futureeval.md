---
description: Forecast the currently-open FutureEval bot-tournament binary questions with an Opus subagent council ($0 under the Claude subscription — NOT the paid Bedrock API) and submit to Metaculus.
argument-hint: "[submit]  (omit = dry-run; 'submit' = post live to the vaticinus bot)"
---

# /futureeval — Opus subagent council for the Metaculus FutureEval bot tournament

Args: **$ARGUMENTS**. If it contains `submit`, post live; otherwise DRY-RUN (forecast + write the
file, do not POST). This is the **#1-among-bots** play: FutureEval hides the crowd prediction, so it
is a pure test of standalone calibrated judgment. The brain here is **Claude Code subagents = the same
Opus the session runs**, billed under the subscription, so it is $0 marginal API and spends nothing on
Bedrock. Submission is deterministic Python — never let a subagent make the API call.

## Procedure

1. **Fetch the open questions** (deterministic):
   ```bash
   uv run python data/metaculus/futureeval_dump_open.py /tmp/fe_open.json
   ```
   Read `/tmp/fe_open.json`. If it is empty (`[]`), STOP and report "no open binary questions right now
   (between daily drops)" — this is the normal state most of the day. Do not fabricate questions.

2. **Council-forecast each open question.** Cap at the **first 12** (soonest-closing; the file is already
   sorted that way) to bound subscription usage. For each question, spawn **3 parallel `general-purpose`
   subagents** (a decorrelated council) in a single message. Give each subagent the question `title`,
   `description`, `resolution_criteria`, `fine_print`, and `close_time`, and this instruction:

   > You are a calibrated superforecaster. Research this question with web search (WebSearch/WebFetch),
   > reason about base rates and the specific evidence, and return ONLY a JSON object:
   > `{"prob": <float 0.01-0.99>, "reasoning": "<=80 words"}`. The crowd prediction is hidden — do not
   > guess it; commit to your own calibrated estimate. Avoid 0.5 unless genuinely maximally uncertain.

   Aggregate the 3 subagent probabilities by **median** (robust to one outlier). That median is the
   question's forecast.

3. **Write the forecasts file** `/tmp/fe_forecasts.json` as a JSON list of
   `{"question_id": <int>, "prob": <median float>, "title": "<title>", "reasoning": "<1-line synthesis>"}`,
   one row per question you forecast. Use the `question_id` field from `/tmp/fe_open.json` (NOT `post_id`).

4. **Submit** (only if args contain `submit`):
   ```bash
   uv run python data/metaculus/futureeval_submit.py /tmp/fe_forecasts.json --submit
   ```
   Without `submit`, run it WITHOUT `--submit` to dry-print what would post.

5. **Report**: a compact table of qid · prob · title · submitted?, and the ok/err count the script prints.

## Guardrails
- Binary-only here (MC/numeric are covered by the free mechanical path in the cron wrapper).
- LEAK rule does not bite (these are open, forward, unresolved questions) — but never tune anything on
  resolved FutureEval questions; this is forward scoring only.
- If a subagent returns malformed JSON, drop that vote; if all 3 fail for a question, skip it (the free
  baseline already has it covered) rather than submitting a guess.
- Never invent question ids. Only submit ids that came from `/tmp/fe_open.json` this run.
