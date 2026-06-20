"""Brier reward for the Mac GRPO smoke test (mlx-lm-lora v1.0.0), reusing the PRODUCTION parser.

Registered into mlx-lm-lora's global REWARD_REGISTRY via its decorator; pass on the CLI with:
    --reward-functions-file training/mlx_rewards.py \
    --reward-functions "brier_reward,format_reward" --reward-weights "[1.0,0.2]"

brier_reward mirrors training/grpo.py exactly: 1 - (p - outcome)^2, strictly proper, bounded;
unparseable → -1 (format penalty). The point of the smoke test is to prove THIS parser + THIS
reward fire correctly on real tiny-model output before the same contract runs on the 8B.

v1.0.0 contract (verified against the installed source): reward funcs are BATCHED —
    def f(prompts: list[str], completions: list[str], answer: list[str], types=None) -> list[float]
`completions` are decoded strings; `answer` is the data's "answer" field (our str(outcome)).
"""
from __future__ import annotations

from common import parse_prob

try:  # importable for a quick logic check even when the package isn't installed
    from mlx_lm_lora.trainer.grpo_reward_functions import register_reward_function
except Exception:  # pragma: no cover
    def register_reward_function(*_a, **_k):
        def deco(fn):
            return fn
        return deco


@register_reward_function()
def brier_reward(prompts, completions, answer, types=None):
    """1 - Brier on the parsed probability vs the resolved outcome. Strictly proper, bounded."""
    out = []
    for comp, a in zip(completions, answer):
        p = parse_prob(comp if isinstance(comp, str) else "")
        if p is None:
            out.append(-1.0)
            continue
        try:
            y = float(a)
        except (TypeError, ValueError):
            out.append(-1.0)
            continue
        out.append(1.0 - (p - y) ** 2)
    return out


@register_reward_function()
def format_reward(prompts, completions, answer, types=None):
    """Small bonus for a parseable 'Probability:' line — bootstraps the output contract."""
    return [0.2 if parse_prob(c if isinstance(c, str) else "") is not None else 0.0
            for c in completions]
