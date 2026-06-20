# We fine-tuned an LLM to forecast on 30k auto-minted questions. It got worse. Here's exactly why.

*A short, honest post-mortem. Companion to [beyond-brier](https://github.com/vaticinus/beyond-brier),
the skill score that measures the same thing this finetune failed to learn: information added over a
prior, not confidence.*

## What we built

A leak-controlled training set of ~34,000 binary forecasting questions, auto-minted from real time
series and prediction markets: 20,435 supervised traces and 14,214 RL rows, each one a question with a
known resolution date, a frozen as-of anchor, and an outcome that lands strictly after the as-of date.
Every row was date-gated so the model could never see its own answer. We ran SFT then a GRPO-style pass
with a Brier reward, the same recipe that has worked publicly elsewhere.

The goal was the cheap, decorrelated ensemble member: a small model whose errors are uncorrelated with
the frontier pack because it was trained on a different data diet.

## What happened

The fine-tuned model was **worse** than the base model on Brier. Not catastrophically, but clearly, and
in a way that took a real diagnosis to understand rather than wave away.

The diagnosis is the interesting part:

- **It did not lose knowledge.** Discrimination, measured by AUC, was unchanged: 0.668 before, 0.648
  after, inside the noise. The model could still tell likely from unlikely about as well as before.
- **It lost calibration.** Training on confident, model-generated reasoning traces taught it to *sound
  certain*. Brier punishes overconfidence harder than almost anything, so a model that learned to commit
  hard on every question bled score even though its ranking of outcomes barely moved.

## The root cause was in the data, not the training

We went looking for the single feature that should have carried the signal and found it empty. The
`crowd_prob` field, the real crowd or market probability for each question, was **unpopulated on every
market row and absent on the dataset half entirely.** Only about one market row in six ever carried a
real anchor.

That field isn't a nice-to-have. It's the thing a forecasting model is supposed to learn to *beat*. At
inference time on ForecastBench you are literally handed the crowd anchor at freeze time. A model that
never saw, during training, a case where the right answer diverged from the mechanical baseline has
nothing to distill except the teacher's confidence. And the teacher here was the base model's own traces,
which carry no skill the base model didn't already have.

**You cannot distill skill the teacher does not possess.** We taught a model to be confident, because
confidence was the only thing in the traces that varied. Brier did the rest.

## Why this is a beyond-brier story

This is the same failure the [beyond-brier](https://github.com/vaticinus/beyond-brier) metric exists to
catch, viewed from the training side. A forecast that merely echoes a prior, or that is confident without
adding information over it, has zero *marginal edge* no matter how its raw score looks. Our finetune
optimized something that was not marginal edge, on data that contained almost no marginal edge to learn,
and got exactly what it optimized: louder, not righter.

If you only ever look at aggregate Brier you might conclude "the finetune is a bit worse, shrug." The AUC
versus calibration split is what tells you it is a *calibration* failure caused by a *missing anchor*, not
a knowledge failure. Measuring the right thing is half the battle, on the training side as much as the
leaderboard side.

## The fix (validated, in progress)

Train on a target that genuinely beats the prior: a real superforecaster's forecast, with the
superforecaster's own reasoning, conditioned on the same crowd anchor the model gets at test time. The
model then learns *when and which way to adjust off the crowd*, which is the discrimination the base lacks,
while the soft expert target keeps it calibrated.

The signal was already on disk, unused: 7,693 real superforecaster forecasts with reasoning over ~189
ForecastBench questions, each carrying its crowd anchor and a known outcome. Before training on it we ran
the only honest gate, does the expert aggregate actually beat the crowd anchor on Brier, and it passed
(experts add roughly +0.046 Brier of edge over the crowd anchor on the resolved market subset, the same
order of magnitude beyond-brier measures for superforecasters on the public ForecastBench round). The open
problem is scale: a few hundred anchored questions is a thin diet. That is the real lever, and it is a data
problem, not a training-tech problem.

## Why we are not open-sourcing the full dataset

Two honest reasons.

1. **It failed.** Releasing a 34k-row training set whose headline result is "this made the model worse"
   as if it were a flagship asset would be marketing a defect. The lesson is the asset, not the rows.
2. **The auto-minting pipeline is the part that took the work.** The questions are mechanically generated
   from series and markets under a leak gate; that generator is the thing worth keeping. The lesson
   generalizes; the factory does not need to be public for the lesson to be useful.

What we are sharing is this write-up and a 200-row illustrative sample
([`dataset_sample_200.jsonl`](dataset_sample_200.jsonl)) so you can see the row shape, the leak gate, and
the empty `crowd_prob` field that this whole post is about. If you are building a forecasting finetune:
populate your anchor, distill a teacher that actually beats it, and measure marginal edge, not confidence.
