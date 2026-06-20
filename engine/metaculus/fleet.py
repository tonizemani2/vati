"""engine/metaculus/fleet.py — the multi-model leak-free backtest GRID (the big feedback loop).

Insight (Ruben, 2026-06-12): there are MANY models across MANY cutoff dates. Each is leak-free on a
DIFFERENT slice of the bank — everything resolving AFTER its measured effective cutoff. So run a FLEET:
measure each model's effective cutoff with the non-leading recall probe, then score each model ONLY on
its own leak-free slice. The union is thousands of leak-free (model, question, forecast, outcome) rows:

  • ranks models by leak-free Brier → which cheap/keyless models actually forecast (ensemble members)
  • calibrates the aggregation priors (extremize d, crowd weight) on a HUGE leak-free set
  • a decorrelation view → the real ensemble edge (decorrelated members, not merely good ones)
  • training/eval data for the fine-tuned "top model"

Leak discipline is PER (model, question): keep a question for a model iff its outcome was determined
STRICTLY AFTER that model's measured effective cutoff (year granularity, conservative). Research OFF
(keyless Exa can't be date-bounded → would leak). Concurrent + resumable: append to
data/metaculus/backtest_grid.jsonl; a re-run skips any (model, qid) already scored, so the loop GROWS.
"""
from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from engine import db, holdout
from engine.adapters import llm
from engine.metaculus import calibrate as cal
from engine.metaculus import forecast as fc
from engine.metaculus import qbank

GRID_PATH = "data/metaculus/backtest_grid.jsonl"
CUTOFF_CACHE = "data/metaculus/model_cutoffs.json"

# ── the fleet: cheap, family-diverse, cutoff-diverse. `card` = the model's PUBLISHED training-cutoff year
# (conservative). The gate uses max(measured-probe-cutoff, card) so a probe false-negative (a model that
# hedges on recent facts → looks older than it is) can't admit leaky questions, while the probe still
# catches contamination ABOVE the card (e.g. gpt-3.5's RLHF knowing 2023). Both must fail to leak. ──
MODELS: list[dict] = [
    # strong + 2023 card cutoff = the gold (capable forecaster, leak-free on 2024+)
    {"provider": "openrouter", "model": "meta-llama/llama-3.3-70b-instruct", "card": 2023, "est_cents": 1},
    {"provider": "openrouter", "model": "meta-llama/llama-3.1-70b-instruct", "card": 2023, "est_cents": 1},
    {"provider": "openrouter", "model": "meta-llama/llama-3-8b-instruct", "card": 2023, "est_cents": 1},
    {"provider": "openrouter", "model": "meta-llama/llama-3.1-8b-instruct", "card": 2023, "est_cents": 1},
    {"provider": "openrouter", "model": "meta-llama/llama-3.2-3b-instruct", "card": 2023, "est_cents": 1},
    {"provider": "openrouter", "model": "openai/gpt-3.5-turbo-0613", "card": 2021, "est_cents": 1},
    # mid, diverse families, 2024 card cutoff (leak-free on 2025+)
    {"provider": "openrouter", "model": "qwen/qwen-2.5-72b-instruct", "card": 2024, "est_cents": 1},
    {"provider": "openrouter", "model": "qwen/qwen-2.5-7b-instruct", "card": 2024, "est_cents": 1},
    {"provider": "openrouter", "model": "mistralai/mistral-small-24b-instruct-2501", "card": 2024, "est_cents": 1},
    {"provider": "openrouter", "model": "mistralai/mistral-nemo", "card": 2024, "est_cents": 1},
    {"provider": "openrouter", "model": "google/gemma-3-27b-it", "card": 2024, "est_cents": 1},
    {"provider": "openrouter", "model": "google/gemma-3-12b-it", "card": 2024, "est_cents": 1},
    {"provider": "openrouter", "model": "microsoft/phi-4", "card": 2024, "est_cents": 1},
    {"provider": "openrouter", "model": "cohere/command-r7b-12-2024", "card": 2024, "est_cents": 1},
    {"provider": "openrouter", "model": "amazon/nova-lite-v1", "card": 2024, "est_cents": 1},
    {"provider": "openrouter", "model": "nousresearch/hermes-4-70b", "card": 2024, "est_cents": 1},
]

# ── recall probes (non-leading, non-guessable, dated) — 2/yr 2022→2025 → tighter effective-cutoff than
# holdout's 5-probe set. The LATEST year a model demonstrably recalls = its effective cutoff (lower bound
# on knowledge → we gate strictly later, the conservative direction for leakage). ──
FLEET_PROBES: list[dict] = [
    {"q": "Which national team won the FIFA World Cup held in Qatar at the end of 2022?",
     "year": 2022, "keys": ["argentina"]},
    {"q": "What is the name of the AI chatbot OpenAI launched to the public in November 2022?",
     "year": 2022, "keys": ["chatgpt", "chat gpt"]},
    {"q": "What did OpenAI release in March 2023 as the successor to GPT-3.5?",
     "year": 2023, "keys": ["gpt-4", "gpt 4", "gpt4"]},
    {"q": "Which militant group launched a large surprise attack on southern Israel on October 7, 2023?",
     "year": 2023, "keys": ["hamas"]},
    {"q": "What is the name of OpenAI's text-to-video model first shown in February 2024?",
     "year": 2024, "keys": ["sora"]},
    {"q": "Who won the 2024 United States presidential election (last name)?",
     "year": 2024, "keys": ["trump"]},
    {"q": "Which Chinese AI startup released the 'R1' reasoning model in January 2025?",
     "year": 2025, "keys": ["deepseek"]},
    {"q": "Which US national laboratory first achieved fusion ignition with net energy gain, announced "
          "December 2022?", "year": 2022, "keys": ["lawrence livermore", "livermore", "nif"]},
]

_grid_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────── effective-cutoff measurement (cached)

def _load_cache() -> dict:
    if os.path.exists(CUTOFF_CACHE):
        with open(CUTOFF_CACHE) as f:
            return json.load(f)
    return {}


def _save_cache(c: dict) -> None:
    os.makedirs(os.path.dirname(CUTOFF_CACHE), exist_ok=True)
    with open(CUTOFF_CACHE, "w") as f:
        json.dump(c, f, indent=2)


def measure_cutoff(model: str, provider: str, est_cents: int, *, proxy=None, log=print) -> int | None:
    """Effective cutoff = latest FLEET_PROBE year the model demonstrably recalls (None = blind to all,
    i.e. pre-2022). Cached per model in CUTOFF_CACHE so we probe once."""
    cache = _load_cache()
    key = f"{provider}:{model}"
    if key in cache:
        v = cache[key]
        return v if v is not None else None
    known = []
    conn = db.connect()
    try:
        for pr in FLEET_PROBES:
            try:
                ans = holdout._ask_recall(conn, pr["q"], provider=provider, model=model,
                                          est_cost_cents=est_cents, proxy=proxy)
            except Exception:
                ans = ""
            if any(k in ans for k in pr["keys"]):
                known.append(pr["year"])
    finally:
        conn.close()
    eff = max(known) if known else None
    cache[key] = eff
    _save_cache(cache)
    log(f"   cutoff {key:48} = {eff if eff is not None else 'pre-2022'}  (knows {sorted(set(known))})")
    return eff


# ─────────────────────────────────────────────────────────────── grid run (concurrent, resumable)

def _done_pairs(path: str) -> set:
    done = set()
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                try:
                    r = json.loads(line)
                    done.add((r["model"], r["qid"]))
                except Exception:
                    pass
    return done


def _forecast_one(task: dict, today: str, proxy) -> dict | None:
    """One (model, question) leak-free forecast. Best-of-N within the model, log-odds pooled to a single
    prob. Returns a grid row or None on total failure."""
    q = task["q"]
    prompt = fc._prompt(cal.manifold_to_q(q), "(research disabled — leak-free backtest)", today, None)
    per = cal._ensemble_samples(prompt, [task["model"]], task["n"], provider=task["provider"],
                                est_cost_cents=task["est_cents"], proxy=proxy)
    samples = [p for ps in per.values() for p in ps]
    if not samples:
        return None
    return {"model": task["model"], "provider": task["provider"], "eff_cutoff": task["eff"],
            "qid": q["id"], "resolved_year": q["resolved_year"], "title": q["title"][:80],
            "outcome": q["outcome"], "pred": cal._pool_d(samples, 1.0), "samples": samples,
            "crowd_final": q.get("crowd_final")}


def run_grid(*, models=None, n_per_model: int = 150, n_samples: int = 1, max_workers: int = 6,
             proxy=None, bank_path: str = qbank.BANK_PATH, log=print) -> dict:
    """Measure cutoffs → build the per-model leak-free task list → forecast concurrently → append to the
    grid. Resumable. cost: keyed, gate-bounded by est_cents. Set COST_AUTO_APPROVE_CENTS to clear it."""
    models = models or MODELS
    today = date.today().isoformat()
    bank = qbank.load(bank_path)
    if not bank:
        log("   ⛔ no qbank — run `python -m engine.metaculus.qbank` first.")
        return {"n": 0}
    log(f"🛰️  FLEET BACKTEST GRID — {len(models)} models × ≤{n_per_model} leak-free Qs each "
        f"(bank {len(bank)}) — {today}")

    log("\n   STEP 1 — measure each model's effective cutoff (cached); gate = max(measured, card):")
    for m in models:
        measured = measure_cutoff(m["model"], m["provider"], m["est_cents"], proxy=proxy, log=log)
        # conservative gate: never below the published card cutoff (guards probe false-negatives)
        m["eff"] = max([y for y in (measured, m.get("card")) if y is not None], default=None)

    log("\n   STEP 2 — build leak-free task list (per-model gating, conservative cutoff):")
    done = _done_pairs(GRID_PATH)
    tasks = []
    for m in models:
        eff = m["eff"]
        slice_ = [q for q in bank if (eff is None or q["resolved_year"] > eff)]
        slice_ = cal._sample_bank(slice_, n_per_model)
        new = [q for q in slice_ if (m["model"], q["id"]) not in done]
        for q in new:
            tasks.append({"model": m["model"], "provider": m["provider"], "est_cents": m["est_cents"],
                          "eff": eff, "n": n_samples, "q": q})
        log(f"   {m['model']:46} eff={str(eff):>6} slice={len(slice_):>4} new={len(new):>4}")
    if not tasks:
        log("   nothing new to run (grid already covers this config). Analyzing existing grid.")
        return analyze_grid(log=log)

    log(f"\n   STEP 3 — {len(tasks)} forecasts, {max_workers}-way concurrent (research off, gate-bounded)…")
    os.makedirs(os.path.dirname(GRID_PATH), exist_ok=True)
    n_ok = 0
    with open(GRID_PATH, "a") as gf, ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(_forecast_one, t, today, proxy) for t in tasks]
        for i, fut in enumerate(as_completed(futs), 1):
            try:
                row = fut.result()
            except Exception:
                row = None
            if row:
                with _grid_lock:
                    gf.write(json.dumps(row) + "\n")
                    gf.flush()
                n_ok += 1
            if i % 50 == 0:
                log(f"     {i}/{len(tasks)} done ({n_ok} scored)")
    log(f"   wrote {n_ok} new grid rows → {GRID_PATH}")
    return analyze_grid(log=log)


# ─────────────────────────────────────────────────────────────── analysis

def analyze_grid(*, path: str = GRID_PATH, log=print) -> dict:
    """Per-model leak-free Brier (ranked) + pooled aggregation calibration + a cross-model decorrelation
    read. Pure post-processing of the grid — no model calls."""
    if not os.path.exists(path):
        log("   no grid yet.")
        return {"n": 0}
    rows = [json.loads(l) for l in open(path)]
    log(f"\n   ── GRID ANALYSIS (N={len(rows)} leak-free forecasts across "
        f"{len({r['model'] for r in rows})} models) ──")

    # per-model leak-free Brier vs that model's own base rate
    by_model: dict[str, list] = {}
    for r in rows:
        by_model.setdefault(r["model"], []).append(r)
    log(f"   {'model':46} {'N':>4} {'cutoff':>6} {'Brier':>7} {'base':>6} {'edge':>7}")
    ranked = []
    for mdl, rs in by_model.items():
        n = len(rs)
        base = sum(1 for r in rs if r["outcome"]) / n
        brier = sum((r["pred"] - (1.0 if r["outcome"] else 0.0)) ** 2 for r in rs) / n
        bbase = sum((base - (1.0 if r["outcome"] else 0.0)) ** 2 for r in rs) / n
        ranked.append({"model": mdl, "n": n, "cutoff": rs[0]["eff_cutoff"], "brier": brier,
                       "base": bbase, "edge": bbase - brier})
    ranked.sort(key=lambda x: x["brier"])
    for x in ranked:
        log(f"   {x['model']:46} {x['n']:>4} {str(x['cutoff']):>6} {x['brier']:>7.4f} "
            f"{x['base']:>6.4f} {x['edge']:>+7.4f}")

    # pooled aggregation calibration (extremize d) on the WHOLE leak-free grid, treating each forecast
    # as one sample (a single-model pool); OOS via 2-fold CV.
    pooled = [{"outcome": r["outcome"], "samples": r["samples"], "crowd": None, "src": "grid"}
              for r in rows]
    d_star, d_oos, d1_oos = cal._best_d_cv(pooled, cal.D_GRID)
    log(f"\n   pooled extremize (OOS 2-fold): d*={d_star} Brier {d_oos:.4f} vs d=1.0 {d1_oos:.4f} "
        f"→ {'extremize helps ✅' if d_oos < d1_oos else 'hold d≈1 ⚠️'}")

    # cross-model ENSEMBLE: on questions covered by ≥3 models, does log-odds-pooling models beat the
    # best single model? (the decorrelation edge — the whole reason for a fleet)
    by_q: dict = {}
    for r in rows:
        by_q.setdefault(r["qid"], []).append(r)
    shared = {q: rs for q, rs in by_q.items() if len(rs) >= 3}
    ens_b = ind_b = 0.0
    for q, rs in shared.items():
        o = 1.0 if rs[0]["outcome"] else 0.0
        ens = cal._pool_d([r["pred"] for r in rs], 1.0)
        ens_b += (ens - o) ** 2
        ind_b += sum((r["pred"] - o) ** 2 for r in rs) / len(rs)
    if shared:
        ens_b /= len(shared); ind_b /= len(shared)
        log(f"   cross-model ensemble on {len(shared)} multi-covered Qs: "
            f"pooled Brier {ens_b:.4f} vs avg-single {ind_b:.4f} "
            f"→ {'ensemble edge ✅' if ens_b < ind_b else 'no ensemble gain'}")

    best = ranked[0] if ranked else None
    rep = {"n": len(rows), "models": len(by_model), "ranked": ranked, "d_star": d_star,
           "d_oos": d_oos, "d1_oos": d1_oos,
           "ensemble_brier": ens_b if shared else None, "single_brier": ind_b if shared else None,
           "best_model": best["model"] if best else None}
    out = f"data/metaculus/grid_report_{date.today().isoformat()}.json"
    with open(out, "w") as f:
        json.dump(rep, f, indent=2)
    log(f"   saved → {out}")
    return rep


# ─────────────────────────────────────────────────────────────── CLI

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Multi-model leak-free backtest grid (the feedback loop).")
    ap.add_argument("--n-per-model", type=int, default=150)
    ap.add_argument("--n", type=int, default=1, help="best-of-N within each model")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--proxy", default=None)
    ap.add_argument("--analyze-only", action="store_true")
    a = ap.parse_args()
    if a.analyze_only:
        analyze_grid()
    else:
        run_grid(n_per_model=a.n_per_model, n_samples=a.n, max_workers=a.workers, proxy=a.proxy)
