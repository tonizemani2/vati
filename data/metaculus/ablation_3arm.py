"""3-arm system ablation: does Vati's system beat raw Opus? ("are you just a prompt layer?")

This decomposes the REAL ForecastBench judgmental pipeline into its three layers and scores
each on the same leak-light panel, so the answer is a number, not a claim:

  Arm A  RAW OPUS      one Opus call, naive prompt (no crowd prior, no edge discipline,
                       no aggregation). This is "just the LLM."
  Arm B  + COUNCIL     K independent Opus calls with the disciplined system prompt
                       (crowd-as-prior + self-assigned edge), median-logit aggregate.
                       Mirrors engine.forecastbench.opus_forecaster._stage2. Isolates the
                       prompt-discipline + decorrelated-aggregation leg.
  Arm C  + FULL SYSTEM Arm B then the edge-weighted crowd-anchor blend
                       (engine.forecastbench.opus_blend.blend, crowd keeps >=60% logit
                       weight). Isolates the bounded crowd re-anchoring leg.

Reference: the crowd alone. The strong, hard-to-dismiss result is Arm C beating BOTH raw
Opus AND the crowd on Brier, with the gap surviving a bootstrap over questions.

PANEL = qbank Manifold questions RESOLVED IN 2026 (postdate model cutoffs -> leak-light),
filtered to genuinely-uncertain (crowd_final in [0.15,0.85]) so there is signal to
discriminate. Same loader as config_bakeoff.py.

LEAK CAVEAT (the one honest read). Opus's cutoff postdates some of these resolutions, so
ABSOLUTE Brier is leak-optimistic. But the leak is COMMON-MODE across all three arms (same
model, same cutoff), so the RELATIVE ordering C < B < A and the pairwise gaps are the
trustworthy reads — exactly the comparison this harness exists to make. Do NOT tune
anything on this set; report the ordering, not the level.

  paid artifact:
    uv run python data/metaculus/ablation_3arm.py --n 40 --council 4

  free smoke / harness check:
    uv run python data/metaculus/ablation_3arm.py --n 3 --council 1 \
      --provider openrouter_free --model openai/gpt-oss-20b:free \
      --out /tmp/ablation_3arm_smoke.jsonl
"""
import json
import math
import random
import statistics as st
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from engine import db
from engine.adapters import llm
from engine.forecastbench.opus_blend import blend
from engine.forecastbench.opus_forecaster import _parse  # disciplined-JSON parser (p, edge, why)

# Arm B/C use the real system's forecaster prompt + the real Opus model.
from engine.forecastbench.opus_forecaster import SYSTEM as COUNCIL_SYSTEM
from engine.forecastbench.opus_blend import EDGE_WEIGHT

OPUS = ("bedrock", "us.anthropic.claude-opus-4-8")
FREE_PROVIDERS = {"openrouter_free"}
ALLOWED_PROVIDERS = {OPUS[0], *FREE_PROVIDERS}
EDGE_RANK = {"none": 0, "weak": 1, "strong": 2}
_RANK_EDGE = {v: k for k, v in EDGE_RANK.items()}

RAW_SYSTEM = (
    "You are a forecaster. Give a probability the question resolves YES. Reason in 1-2 "
    "sentences, then end with a final line exactly: PROB: <0..1>."
)


def n_arg(flag, default):
    if flag in sys.argv:
        try:
            return int(sys.argv[sys.argv.index(flag) + 1])
        except (ValueError, IndexError):
            pass
    return default


def s_arg(flag, default=None):
    if flag in sys.argv:
        try:
            return sys.argv[sys.argv.index(flag) + 1]
        except IndexError:
            pass
    return default


def usage():
    return (
        "usage: uv run python data/metaculus/ablation_3arm.py "
        "[--n N] [--council K] [--provider bedrock|openrouter_free] "
        "[--model MODEL] [--out PATH]\n"
        "\n"
        "Default is the paid Opus artifact path. Use --provider openrouter_free "
        "--model <free-model> for a $0 smoke run."
    )


def provider_args():
    provider = s_arg("--provider", OPUS[0])
    if provider not in ALLOWED_PROVIDERS:
        raise SystemExit(
            f"unsupported --provider {provider!r}; allowed: {sorted(ALLOWED_PROVIDERS)}. "
            "This harness intentionally exposes only paid Opus and the $0 OpenRouter-free smoke path."
        )
    model = s_arg("--model", OPUS[1] if provider == OPUS[0] else None)
    return provider, model


def est_cost(provider, billed_default):
    """Keep free smoke runs at $0; let paid/keyed routes trip the repo cost gate."""
    return 0 if provider in FREE_PROVIDERS else billed_default


def load_panel(n):
    """qbank: uncertain 2026-resolved questions, deterministic stride sample (matches config_bakeoff)."""
    rows = []
    for l in open("data/metaculus/qbank.jsonl"):
        d = json.loads(l)
        if d.get("resolved_year") != 2026:
            continue
        oc = str(d.get("outcome"))
        if oc not in ("True", "False", "YES", "NO"):
            continue
        try:
            crowd = float(d["crowd_final"])
        except (KeyError, ValueError, TypeError):
            continue
        if not (0.15 <= crowd <= 0.85):
            continue
        d["_y"] = 1.0 if oc in ("True", "YES") else 0.0
        d["_crowd"] = crowd
        rows.append(d)
    rows.sort(key=lambda r: r["id"])
    step = max(1, len(rows) // n)
    return rows[::step][:n]


def _logit(p):
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(z):
    return 1 / (1 + math.exp(-z))


def parse_raw(txt):
    """PROB: parser for the naive raw arm."""
    import re
    if not txt:
        return None
    m = re.findall(r"PROB:\s*([01]?\.\d+|[01](?:\.0+)?)", txt)
    cands = m or re.findall(r"\b(0?\.\d+)\b", txt)
    if cands:
        try:
            return min(0.98, max(0.02, float(cands[-1])))
        except ValueError:
            pass
    return None


def parse_council(txt):
    """JSON parser for Arm B, with a narrow PROB fallback for non-Opus smoke models."""
    r = _parse(txt)
    if r is not None:
        return r
    if txt and "PROB:" in txt:
        p = parse_raw(txt)
        if p is not None:
            return p, "none", "fallback PROB parser"
    return None


def brier(p, y):
    return (p - y) ** 2


def _raw_prompt(q):
    return (f"Question (resolves YES/NO): {q['title']}\n"
            f"Context: a real prediction-market question, created {q.get('created_date')}.\n"
            "Give your probability it resolved YES.")


def _council_prompt(q):
    """Disciplined prompt: crowd value as a prior, JSON+edge contract (mirrors opus_forecaster._prompt)."""
    return (f"Question: {q['title']}\n"
            f"Calibrated crowd prior: {q['_crowd']:.3f}\n"
            f"Context: a real prediction-market question, created {q.get('created_date')}.\n"
            "Return the JSON object only.")


def arm_a_raw(q, provider, model):
    """One naive model call."""
    c = db.connect()
    try:
        out = llm.complete(c, _raw_prompt(q), provider=provider, model=model,
                           system=RAW_SYSTEM, max_tokens=220,
                           est_cost_cents=est_cost(provider, 2))
    except Exception:
        return None
    finally:
        c.close()
    return parse_raw(out)


def arm_b_council(q, council, provider, model):
    """K disciplined samples -> (median-logit p, median edge). Mirrors _stage2."""
    c = db.connect()
    samples = []
    try:
        for _ in range(council):
            try:
                txt = llm.complete(c, _council_prompt(q), provider=provider, model=model,
                                   system=COUNCIL_SYSTEM, max_tokens=1200,
                                   est_cost_cents=est_cost(provider, 4))
            except Exception:
                continue
            r = parse_council(txt)
            if r is not None:
                samples.append(r)
    finally:
        c.close()
    if not samples:
        return None, "none"
    logits = sorted(_logit(p) for p, _, _ in samples)
    p_b = _sigmoid(logits[len(logits) // 2])
    ranks = sorted(EDGE_RANK[e] for _, e, _ in samples)
    edge = _RANK_EDGE[ranks[len(ranks) // 2]]
    return p_b, edge


def bootstrap_gap(rows, key1, key2, iters=2000):
    """Bootstrap 95% CI for mean(brier[key1]) - mean(brier[key2]) over questions.
    Positive gap = key2 is better (lower Brier). Deterministic seed for reproducibility."""
    rng = random.Random(12345)
    diffs = []
    idx = list(range(len(rows)))
    for _ in range(iters):
        sample = [rows[rng.choice(idx)] for _ in idx]
        d = st.mean(r[key1] for r in sample) - st.mean(r[key2] for r in sample)
        diffs.append(d)
    diffs.sort()
    lo, hi = diffs[int(0.025 * iters)], diffs[int(0.975 * iters)]
    point = st.mean(r[key1] for r in rows) - st.mean(r[key2] for r in rows)
    return point, lo, hi


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(usage())
        return
    n = n_arg("--n", 40)
    council = n_arg("--council", 4)
    out_path = s_arg("--out", "data/metaculus/ablation_3arm_raw.jsonl")
    provider, model = provider_args()
    panel = load_panel(n)
    est_calls = len(panel) * (1 + council)
    target = f"{provider}/{model or 'provider-default-or-roster'}"
    cost_note = ("Bedrock, BILLED" if provider == "bedrock"
                 else "$0/free route" if provider in FREE_PROVIDERS
                 else "cost-gated paid/keyed route")
    print(f"panel: {len(panel)} uncertain 2026-resolved questions | council={council} | "
          f"~{est_calls} calls via {target} ({cost_note})\n", file=sys.stderr)
    if provider == "openrouter_free" and model is None:
        print("NOTE: openrouter_free without --model shuffles the free roster; good for wiring "
              "smoke, not a controlled model ablation.\n", file=sys.stderr)

    recs = []
    for i, q in enumerate(panel, 1):
        if provider in FREE_PROVIDERS:
            # Free routes are rate-limited per model; sequential smoke avoids false skips.
            p_a = arm_a_raw(q, provider, model)
            p_b, edge_b = arm_b_council(q, council, provider, model)
        else:
            # Arm A and the K council samples are independent -> run concurrently.
            with ThreadPoolExecutor(max_workers=2) as ex:
                fa = ex.submit(arm_a_raw, q, provider, model)
                fb = ex.submit(arm_b_council, q, council, provider, model)
                p_a = fa.result()
                p_b, edge_b = fb.result()
        if p_a is None or p_b is None:
            print(f"[{i:2}/{len(panel)}] SKIP (no forecast)  {q['title'][:40]}", file=sys.stderr)
            continue
        p_c = blend(q["_crowd"], p_b, edge_b)
        y = q["_y"]
        rec = {"id": q["id"], "title": q["title"][:70], "provider": provider,
               "model": model or "", "y": y, "crowd": q["_crowd"],
               "p_a": p_a, "p_b": p_b, "edge_b": edge_b, "p_c": p_c,
               "b_raw": brier(p_a, y), "b_council": brier(p_b, y),
               "b_full": brier(p_c, y), "b_crowd": brier(q["_crowd"], y)}
        recs.append(rec)
        print(f"[{i:2}/{len(panel)}] y={y:.0f} crowd={q['_crowd']:.2f} "
              f"raw={p_a:.2f} council={p_b:.2f}({edge_b}) full={p_c:.2f}  {q['title'][:34]}",
              file=sys.stderr)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    print(f"wrote raw rows -> {out_path}", file=sys.stderr)

    if not recs:
        print("no forecasts collected", file=sys.stderr)
        return

    base = st.mean(r["y"] for r in recs)
    print(f"\n=== 3-arm ablation: n={len(recs)} | base rate={base:.2f} ===")
    print(f"{'arm':<22}{'Brier':>9}{'mean_p':>9}")
    model_name = "Opus" if provider == OPUS[0] and (model or "").endswith("opus-4-8") else "model"
    for label, k, pk in [(f"A raw {model_name}", "b_raw", "p_a"),
                         ("B + council", "b_council", "p_b"),
                         ("C + full system", "b_full", "p_c"),
                         ("ref: crowd alone", "b_crowd", "crowd")]:
        b = st.mean(r[k] for r in recs)
        mp = st.mean(r[pk] for r in recs)
        print(f"{label:<22}{b:>9.4f}{mp:>9.2f}")

    print("\n=== bootstrap gaps (positive => second arm better; 95% CI excludes 0 => significant) ===")
    for a, c, name in [("b_raw", "b_council", "raw -> council"),
                       ("b_council", "b_full", "council -> full"),
                       ("b_raw", "b_full", "raw -> FULL SYSTEM"),
                       ("b_crowd", "b_full", "crowd -> FULL SYSTEM")]:
        point, lo, hi = bootstrap_gap(recs, a, c)
        sig = "SIGNIFICANT" if (lo > 0 or hi < 0) else "ns"
        print(f"{name:<22} ΔBrier={point:+.4f}  95%CI[{lo:+.4f},{hi:+.4f}]  {sig}")
    print("\nNOTE: absolute Brier is leak-optimistic (Opus cutoff postdates some resolutions); "
          "the RELATIVE ordering + gaps are the trustworthy reads.", file=sys.stderr)


if __name__ == "__main__":
    main()
