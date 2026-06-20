"""engine/forecastbench/edge_gate.py — does adding our structural features beat the crowd? (paid, cents)

The gate that decides whether the edge dataset is worth finetuning on. For each FEATURED row we ask
DeepSeek V4 to forecast TWICE: once on the question alone (base), once with the leak-free features
appended (featured). We score Brier for three forecasters:

    • crowd_prob_at_T   — the free prior (the bar to beat)
    • base              — DeepSeek, question only
    • featured          — DeepSeek + our structural features

Read the DELTAS, not the absolute levels. DeepSeek's parametric knowledge can leak the outcome of old
questions, but that leak is SHARED by base and featured, so (base − featured) isolates what the FEATURES
add. (crowd − featured) shows total marginal edge over the free prior. A fully leak-free confirmation
only comes later from the temporal-holdout finetune — this is the cheap pre-check that says whether that
run is even worth the GPU.

Cost: two V4 calls/row (~$0.002/row on V4-Pro, less on V4-Flash). 200 rows ≈ $0.40. Uses
DEEPSEEK_API_KEY from .env via engine.adapters.llm.complete (cost-gated; sub-cent calls auto-approve).

CLI:
    uv run python -m engine.forecastbench.edge_gate --model deepseek-v4-pro --limit 200
"""
from __future__ import annotations

import argparse
import json
import re

from engine.adapters import llm
from engine.db import connect
from engine.forecastbench.edge_dataset import OUT_PATH

SYSTEM = (
    "You are a careful, calibrated forecaster. Think briefly, then end your reply with EXACTLY one "
    "line in this format:\nProbability: 0.NN\nwhere 0.NN is your probability (between 0 and 1) that "
    "the question resolves YES. Do not hedge to 0.50 without reason."
)

_PROB = re.compile(r"[Pp]robability:\s*\*{0,2}\s*(\d*\.?\d+)\s*(%?)")


def parse_prob(text: str) -> float | None:
    """Pull the LAST 'Probability: 0.NN' (or percent) from the reply; clamp to [0.01, 0.99]."""
    matches = list(_PROB.finditer(text or ""))
    if matches:
        m = matches[-1]
        v = float(m.group(1))
        if m.group(2) == "%" or v > 1.5:
            v /= 100.0
    else:
        nums = re.findall(r"\b(0?\.\d+|1\.0+)\b", text or "")
        if not nums:
            return None
        v = float(nums[-1])
    return min(0.99, max(0.01, v))


def _feat_block(feats: list[dict]) -> str:
    lines = []
    for f in feats:
        if f["name"] == "arxiv_share_velocity":
            lines.append(
                f"- Research front (arXiv share-of-literature for: {', '.join(f['terms'])}): "
                f"{f['share_ppm_y2']} ppm of world literature in {f['complete_years'][-1]}; "
                f"year-over-year share growth {f['yoy_share_growth']}x; "
                f"acceleration {f['accel']:+.3f} (positive = the research front is accelerating into "
                f"this topic, negative = decelerating)."
            )
        else:
            keep = {k: v for k, v in f.items() if k not in ("name", "source", "source_date", "terms")}
            lines.append(f"- {f['name']}: {json.dumps(keep)}")
    return "\n".join(lines)


def _ask(conn, question: str, as_of: str, feats: list[dict], model: str) -> tuple[float | None, float | None]:
    base_prompt = (
        f"Question: {question}\n"
        f"Forecast as of {as_of} (reason only from what was knowable on that date).\n"
        f"What is the probability this resolves YES?"
    )
    feat_prompt = base_prompt + "\n\nStructural signals known as of the cutoff:\n" + _feat_block(feats)
    pb = parse_prob(llm.complete(conn, base_prompt, provider="deepseek", model=model,
                                 system=SYSTEM, max_tokens=500, est_cost_cents=0))
    pf = parse_prob(llm.complete(conn, feat_prompt, provider="deepseek", model=model,
                                 system=SYSTEM, max_tokens=500, est_cost_cents=0))
    return pb, pf


def run(*, path: str = OUT_PATH, model: str = "deepseek-v4-pro", limit: int = 200, log=print) -> dict:
    with open(path) as f:
        rows = [json.loads(line) for line in f]
    feat_rows = [r for r in rows if r.get("features")][:limit]
    if not feat_rows:
        log("no featured rows in the dataset — build it first (engine.forecastbench.edge_dataset).")
        return {}
    conn = connect()
    scored: list[dict] = []
    log(f"🧪 edge gate: {len(feat_rows)} featured rows · model={model} · 2 calls/row")
    for i, r in enumerate(feat_rows, 1):
        try:
            pb, pf = _ask(conn, r["question"], r["T"], r["features"], model)
        except Exception as e:
            log(f"   [{i}/{len(feat_rows)}] skip ({type(e).__name__}: {str(e)[:80]})")
            continue
        if pb is None or pf is None:
            log(f"   [{i}/{len(feat_rows)}] unparseable forecast")
            continue
        s = {"c": r["crowd_prob_at_T"], "pb": pb, "pf": pf, "o": r["outcome"]}
        scored.append(s)
        log(f"   [{i}/{len(feat_rows)}] crowd={s['c']:.2f} base={pb:.2f} feat={pf:.2f} → {s['o']}  {r['question'][:48]}")
    return _report(scored, model, log)


def _brier(scored: list[dict], key: str) -> float | None:
    return sum((s[key] - s["o"]) ** 2 for s in scored) / len(scored) if scored else None


def _report(scored: list[dict], model: str, log) -> dict:
    n = len(scored)
    if not n:
        log("nothing scored.")
        return {}
    bc, bb, bf = _brier(scored, "c"), _brier(scored, "pb"), _brier(scored, "pf")
    log(f"\n── edge gate ({model}, n={n}) ──────────────────────")
    log(f"   crowd_prob_at_T   Brier : {bc:.4f}   (the free prior — the bar to beat)")
    log(f"   DeepSeek base     Brier : {bb:.4f}")
    log(f"   DeepSeek+features Brier : {bf:.4f}")
    log(f"   marginal edge vs crowd  : {bc - bf:+.4f}   (positive ⇒ features beat the free prior)")
    log(f"   feature contribution    : {bb - bf:+.4f}   (positive ⇒ features beat the SAME model without them)")
    log(f"   est spend               : ~${n * 2 * 0.002:.2f}")
    verdict = ("ALIVE — features add edge; the finetune is worth running."
               if (bc - bf) > 0.005 and (bb - bf) > 0.002
               else "WEAK — features don't clearly help here; fix features/sources before any GPU spend.")
    log(f"   verdict                 : {verdict}")
    return {"n": n, "crowd": bc, "base": bb, "feat": bf,
            "edge_vs_crowd": bc - bf, "feat_contrib": bb - bf}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Edge gate: do structural features beat the crowd? (paid, cents)")
    ap.add_argument("--model", default="deepseek-v4-pro")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--path", default=OUT_PATH)
    a = ap.parse_args()
    run(path=a.path, model=a.model, limit=a.limit)
