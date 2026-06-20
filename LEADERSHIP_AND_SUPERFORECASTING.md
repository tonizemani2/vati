# Leadership, Superforecasters, and the LLM Translation

*Written 2026-06-14. Three questions: what should "leadership in forecasting" actually mean, how do superforecasters get their edge, and how do we build each of those habits into the bot.*

---

## 1. Would I change what "leadership" is? Yes.

My first cut was "a dated, leak-free, resolved, public Brier record." That is necessary but it is a weak definition, because Brier rewards the wrong thing. A bot that answers mostly short-horizon, data-rich questions posts a great Brier without any skill. The questions resolved on ForecastBench so far skew exactly that way, which is why four DeepMind models briefly sat above the superforecaster median in March 2026 and then fell back. On the questions that actually separate skill, the market questions and the long horizons, superforecasters still lead by almost 50% (0.40 vs 0.59 Brier vs the nearest AI). Low Brier on easy questions is not leadership. It is question selection.

So here is the sharper definition. **Leadership in forecasting is the largest durable edge over the best cheap alternative, on questions that matter, proven forward.** Four parts, each a real bar:

1. **Edge over the best cheap alternative, not over a naive baseline.** The cheap alternative is the market price or the crowd aggregate. Being "accurate" on something already priced is zero edge (correct + already priced = zero). The honest metric is contribution-beyond-price: how many nats of information you add on top of the market. This is exactly what the Beyond Brier work measures, and it is brutal: humans survive that correction at about 0.09 nats, LLMs at about 0.001. That ~75x gap is the real leaderboard, and almost nobody reports it.

2. **Calibrated AND discriminating, scored forward, leak-free.** Calibration alone is trivial (always say the base rate). Discrimination alone is reckless. You need both, on questions whose answers were unknown to the model at forecast time. Retro-scores prove the harness, not the judgment.

3. **On questions that matter.** Long horizon, decision-relevant, market-beating. The hard half, not the data-rich half.

4. **Reproducible and influential.** A method, not a streak. The terminal marker of leadership is that the field defers to your number: it gets cited, it moves others. That is downstream of 1-3 but it is the thing people actually mean by "leader."

The practical consequence for us: stop optimizing aggregate Brier. Optimize **contribution-beyond-market on the hard half**, and report it forward, wins and kills alike. That is a bar we can lead on and that the field does not yet hold itself to.

---

## 2. How superforecasters actually do it

Tetlock's Good Judgment Project is the canonical evidence. The headline finding is that superforecasters are *made, not born*: the single strongest predictor of accuracy is "perpetual beta," the commitment to keep updating one's own method. Below is the working toolbox, compressed from the Ten Commandments and the GJP findings.

1. **Triage.** Spend effort in the Goldilocks zone. Skip questions that are trivial (already determined) or effectively random (genuinely chaotic). Edge lives in the middle band of difficulty.

2. **Fermi-ize.** Break an intractable question into knowable and unknowable sub-parts. Flush ignorance into the open, expose every assumption, estimate each piece, recombine. This converts "will X happen?" into arithmetic over things you can actually anchor.

3. **Outside view first, then inside view.** Start from the base rate of the reference class, then adjust for the specifics of this case, cautiously. The base rate is the anchor; the case details are corrections, not the starting point. Most amateurs invert this and over-weight the vivid specifics.

4. **Update incrementally and often.** Bayesian belief revision. Many small updates as evidence trickles in, occasional large ones when the evidence is decisive. Frequency of updating correlates with accuracy. The failure modes are both under-reaction (anchoring) and over-reaction (chasing noise).

5. **Dragonfly eye.** Synthesize many independent perspectives and the clashing causal forces in a question. Foxes (many small models) beat hedgehogs (one big idea). Actively seek the views that would prove you wrong.

6. **Granularity.** Distinguish as many degrees of doubt as the question allows. 63%, not "likely." The supers who used finer-grained probabilities scored measurably better; rounding their forecasts to coarser buckets destroyed accuracy.

7. **Balance confidence.** Between under- and over-confidence, prudence and decisiveness. Calibration is a learned muscle, not a personality trait.

8. **Post-mortems without hindsight bias.** Look for the actual error behind each miss, and beware of rewriting history to feel less wrong. Score yourself honestly and learn from the score.

9. **Teams and aggregation.** GJP teams beat individuals. Aggregating many forecasts, then *extremizing* the aggregate (pushing it toward 0 or 1, because averaging under-weights shared private signal), improved accuracy by double-digit percentages.

10. **Perpetual beta.** Treat your own method as the thing under test. Practice with feedback. This habit, more than intelligence or topic knowledge, is what made the supers.

The through-line: active open-mindedness (beliefs are hypotheses to test, not possessions to defend), numeracy, and relentless feedback-driven iteration.

---

## 3. The LLM translation: turning each habit into a mechanism

This is the point of the doc. Each superforecaster habit maps to a concrete thing the bot can do. The research is encouraging: Halawi et al. (2024) hit a Brier of 0.240 vs the human crowd's 0.247 using retrieval + reasoning + ensembling, and matched human calibration. The 2026 agentic work pushes further with sequential Bayesian updating of beliefs expressed in language. None of this is magic; it is the toolbox above, mechanized.

| Superforecaster habit | LLM mechanism | Where we stand |
| --- | --- | --- |
| Triage | Route questions by class. Mechanical/structural to the cheap path; judgmental/long-horizon to the deep council. Don't spend Opus on questions the base rate already answers. | We have the domain gate and question-class routing. Tighten the triage so effort tracks the Goldilocks band. |
| Fermi-ize | Decomposition prompt: force the model to break the question into sub-estimands, estimate each, recombine. Scratchpad reasoning, not a one-shot probability. | Partially present in the council. Make explicit decomposition a required step, not emergent. |
| Outside view first | Reference-class / base-rate-first prompting: retrieve or compute the base rate before any case reasoning, and make the case reasoning an explicit adjustment off it. | This is a known LLM weakness (they leap to the vivid inside view). We have base-rate stores; wire them in as the mandatory anchor. |
| Incremental updating | Sequential Bayesian updating: the agent forms an initial linguistic belief, searches, updates in small steps per evidence item, then quantifies. This is the 2026 agentic-forecasting method and it beats one-shot prompting. | This is the highest-value new lever for the deep path. Build the search-evaluate-update loop instead of one-shot research-then-answer. |
| Dragonfly eye | Decorrelated ensemble: many models / many prompt personas / many feeds, deliberately independent, including a member prompted to argue the opposite. Foxes beat hedgehogs. | We have the council and decorrelated feeds. The open lever is a *structurally decorrelated* member that adds info beyond the market, not just another correlated frontier model (the ensemble is dead when members correlate ~0.6). |
| Granularity | Output fine-grained probabilities and full distributions for numeric questions, not coarse buckets. Penalize rounding. | Present. Keep the CDF discipline (the numeric.py fixes). |
| Balance confidence | Post-hoc recalibration (Platt / isotonic) on a leak-free holdout. LLMs are systematically overconfident; recalibration is the cheapest single Brier win, and it is how Halawi closed the calibration gap. | We have the calibration gate. This is our measured strength: we already beat frontier LLMs ~6x on ECE on KalshiBench. Keep it. |
| Post-mortems | Resolve every call, score it, and feed the misses back. An automated post-mortem agent that asks "what did the model over/under-weight?" and writes the lesson. | We have the scored-record discipline in doctrine. Build the loop that actually closes: resolved Brier to lesson to prompt change. |
| Teams + extremizing | Trimmed-mean or extremized aggregation across the ensemble (extremizing because members share signal). Halawi used trimmed mean; GJP showed extremizing adds double digits. | We aggregate. Test extremizing the aggregate explicitly and measure the lift. |
| Perpetual beta | The whole stack treated as under test: forward scoring, ablations, and a standing eval that is the only honest gate. | This is the doctrine. The discipline holds; the missing piece is *resolved* scores, not projected ones. |

### What this says to prioritize

The bot already has the calibration and aggregation halves of the superforecaster toolbox, and that is genuinely where we beat frontier models. The two habits we under-implement are exactly the two that generate edge rather than just avoiding error:

1. **Sequential Bayesian updating on the deep path** (incremental updating + Fermi decomposition). One-shot "research then answer" leaves information on the table. The 2026 agentic method and the supers both say: search, update small, repeat, then quantify.

2. **A genuinely decorrelated member that adds information beyond the market** (dragonfly eye, aimed at contribution-beyond-price). Another correlated frontier model adds nothing. A structurally different member, structural-constraint reasoning that the market under-weights, is the path to positive nats-beyond-price, which is the only definition of leadership that holds up.

Calibration keeps us from losing. These two are how we win.

---

## Sources

- [Ten Commandments for Aspiring Superforecasters (fs.blog)](https://fs.blog/ten-commandments-for-superforecasters/)
- [Evidence on good forecasting practices from the Good Judgment Project (AI Impacts)](https://aiimpacts.org/evidence-on-good-forecasting-practices-from-the-good-judgment-project/)
- [Superforecasters' Toolbox: Fermi-ization (Good Judgment)](https://goodjudgment.com/superforecasters-toolbox-fermi-ization-in-forecasting/)
- [Approaching Human-Level Forecasting with Language Models, Halawi et al. 2024 (arXiv 2402.18563)](https://arxiv.org/abs/2402.18563)
- [Agentic Forecasting using Sequential Bayesian Updating of Linguistic Beliefs, 2026 (arXiv 2604.18576)](https://arxiv.org/pdf/2604.18576)
- [ForecastBench: A Dynamic Benchmark of AI Forecasting (Wharton)](https://faculty.wharton.upenn.edu/wp-content/uploads/2026/02/ForecastBench_A_Dynamic_.pdf)
- [What ForecastBench Doesn't Measure Yet (Good Judgment)](https://goodjudgment.com/what-forecastbench-doesnt-measure/)
- [What Superforecasters Actually Said About ForecastBench (Good Judgment)](https://goodjudgment.substack.com/p/what-superforecasters-actually-said)
