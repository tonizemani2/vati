# Residual-on-prior recipe — the fix for the calibration-tax regression

*Built 2026-06-14. Supersedes the overnight imitation-on-confident-traces run that regressed on Brier.*

## Why the last run failed (diagnosed, not guessed)
The finetune lost **calibration, not knowledge** — discrimination (AUC) was unchanged (0.668→0.648,
noise); the model just learned to sound confident, and Brier punishes that. Root cause in the **data**:
`crowd_prob` was unpopulated on every market row, so the model never saw a prior anchor diverging from a
mechanical baseline. There was **no discrimination signal to distill**, and an LLM teacher can't supply
one (measured: DeepSeek-V3 given the crowd anchor scores Brier 0.132 ≈ the crowd 0.131, beats it on 25%
of rows — it hugs the crowd). Discrimination that beats the crowd lives only in **real human forecasts**
and in the **unmemorizable numeric half** where the model must read a series.

## The method
Every training row = `(point-in-time context, a PRIOR the model also gets at test time, a TARGET at least
as good as the prior, the outcome)`. The model learns to **anchor on the prior and adjust**.

| Layer | Prior | Target | Leak status | Builder |
|---|---|---|---|---|
| Numeric core (8.6k) | quant `model_prob` (AUC 0.736 > raw-8B 0.668) | OOF-isotonic calibrated value | clean by construction (unmemorizable series Qs) | `engine/forecastbench/calib.py` |
| Market policy (4.1k) | crowd anchor (`crowd.py`) | OOF-isotonic calibrated crowd | post-cutoff → eval; markets efficient so ≈prior (teaches the *policy* + decorrelation) | `engine/forecastbench/crowd.py` + `assemble.py` |
| Human gold (56) | crowd anchor | real superforecaster median (0.084 vs crowd 0.131) | real reasoning traces | `engine/forecastbench/residual.py` |

Build: `python -m engine.forecastbench.{residual,calib,assemble}` → `residual_train.jsonl` /
`residual_eval.jsonl` (leak-clean eval = market/human resolving after 2024-10-01 + id-hash hold-out for
numeric). The assembler prints the honest gate preview (target beats prior on every block).

## Training (MLX, $0, on the 8 GB M3 — Qwen3-0.6B-4bit)
Residual-on-prior makes model size secondary: the discrimination is in the **prior we feed**, so a 0.6B
only has to learn "lean on the prior, apply the calibration shift, format." That is the tiny-beats-big
thesis made literal.

```bash
# data dir: {"messages":[system,user,assistant]} from residual_train.jsonl (5% valid)
.mlx-venv/bin/python -m mlx_lm_lora.train \
  --model mlx-community/Qwen3-0.6B-4bit --train --train-mode sft --train-type lora \
  --data data/forecastbench/trainset/mlx_residual \
  --batch-size 1 --iters 1500 --max-seq-length 512 --num-layers 8 --grad-checkpoint \
  --learning-rate 1e-4 --steps-per-eval 1500 --val-batches 10 \
  --save-every 300 --adapter-path out/mlx-residual-sft
```
- **Context is hard-capped to its recent tail (~320 chars)** in `assemble.py` — keeps sequences ~400
  tokens (fast) and is correct: a 0.6B leans on the prior number, not a 600-token series.
- **Always wrap in the 8 GB memory watchdog** (kills the run if free RAM < 10%): the first optimizer
  step spikes memory once; `num-layers 8 @ seq 512` peaks ~1.8 GB and stays ~20% free thereafter.

Eval (same prompt as training — the discipline the post-mortem stressed):
```bash
.mlx-venv/bin/python training/residual_eval.py --adapter ""                 # raw baseline
.mlx-venv/bin/python training/residual_eval.py --adapter out/mlx-residual-sft   # trained
```
Reports Brier / ECE / AUC per block (numeric, human, market) vs the handed prior.

## MEASURED RESULTS (2026-06-14, leak-clean held-out n=264) — read this
| model | ALL Brier | numeric Brier | numeric ECE | numeric AUC |
|---|---|---|---|---|
| **raw 0.6B + structured prior** | **0.203** | **0.237** | 0.106 | 0.687 |
| SFT (full corpus, lr 1e-4, 1500it) | 0.216 | 0.257 | 0.143 | 0.646 |
| SFT (numeric+human, lr 3e-5, 700it) | 0.236 | 0.289 | 0.183 | 0.596 |
| *calibrated-prior ceiling (no LLM)* | *0.173* | *0.211* | *0.040* | *0.736* |

**Imitation-SFT REGRESSED, both runs.** Shallow templated traces overwrite the base's own decent
reasoning, it cannot reproduce the calibrated target number, and format reliability drops (24/264
unparseable in the gentle run). Do NOT ship an imitation-SFT 0.6B. The lessons:

1. **The data design is the edge, not the finetune.** raw-0.6B *given the structured prior* = 0.203,
   rivaling the raw-8B reference ~0.230 at $0. Feed the prior; don't imitate-train a tiny model on it.
2. **Calibration is a POST-HOC layer, not an SFT target.** The calibrated prior (0.211 / ECE 0.040 /
   AUC 0.736) beats every LLM variant on the numeric half — and needs no model. Use it directly; reserve
   the LLM for judgmental questions where no quant prior exists.
3. **Only GRPO can exceed raw**, and it is the rented-GPU/8B job (below). A 0.6B on 8 GB cannot showcase
   the method — the real artifact is Qwen3-8B + GRPO on a GPU, trained on THIS corpus.

## GRPO stage (next — the discrimination sharpener)
Run Brier-reward GRPO **only on the leak-clean numeric subset** (unmemorizable → no reward-hacking by
recall, the failure mode last night). Fix what broke: (1) `--max-completion-length` high enough that
completions don't truncate (50% were cut); (2) keep the KL term (don't let confidence drift); (3) more
iters, lower LR. Reward + parser in `training/mlx_rewards.py`. On 8 GB GRPO loads a 2nd model copy for
KL — wrap in the watchdog (group-size 2, short completions) or run the real job on a rented GPU.

## What "better than a normal 8B" honestly means here
High confidence: **calibration/ECE** (frontier models *lose* on ECE — KalshiBench) and dataset-half Brier.
Medium: market-half crowd-adjust. The durable win is being a **low-correlation ensemble member** (errors
from a structured-data diet, uncorrelated with web-text frontier models). Not "uniformly better at
everything" — that would be the overclaim that burns credibility.
