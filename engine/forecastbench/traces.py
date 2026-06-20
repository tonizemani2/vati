"""SFT trace generator — the quality lever (best-of-N rejection sampling, keyless / $0).

The GRPO set (trainset.py + harvest.py) is prompt+outcome. The SFT set needs *good reasoning traces*:
for each question we sample N chains-of-thought from a strong model and KEEP ONLY the ones whose final
probability beats the baseline (the Halawi/RSFT lever — distill good forecasting, not average). Output is
chat-format SFT JSONL ready for Unsloth.

Model: the keyless DeepInfra roster (Qwen3.5-397B / Gemma-4 / DeepSeek-V4 / GLM-5.1) via the gated
engine.adapters.llm — $0, auto-approved (est 0). Pass --proxy to scale past the per-IP rate limit.

LEAKAGE NOTE (honest): the trace-writer is a recent model, so on historical questions it may already
know the outcome — its traces can be confidently right without real ex-ante reasoning. That inflates the
SFT set's apparent quality but distils a good reasoning *style* into the student. The only honest verdict
on the trained model is the FORWARD / leak-gated eval ([[parametric-leakage]]) — never the train metrics.

Run:  python -m engine.forecastbench.traces --in <rows.jsonl> --out <sft.jsonl>
                                            [--n 6] [--keep 2] [--limit N] [--proxy floxy]
"""
from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from engine import db
from engine.adapters import llm

SYSTEM = (
    "You are a careful, calibrated probabilistic forecaster. You are given ONE forecasting question "
    "and the information known as of a stated date; use nothing from after that date. Reason briefly "
    "and concretely: (1) anchor on the right reference class / base rate — for a numeric series, its "
    "recent level, trend, seasonality, and volatility; for an event, how often such outcomes occur; "
    "(2) the main forces pushing the probability UP; (3) the main forces pushing it DOWN, and how far "
    "the as-of evidence should move you from the anchor; (4) reconcile into ONE calibrated probability "
    "— avoid 0 and 1, and don't be falsely confident on genuinely uncertain questions. End your answer "
    "with exactly one line: 'Probability: 0.NN'."
)


def _user(r: dict) -> str:
    parts = [f"Question: {r['question']}"]
    if r.get("resolution_criteria"):
        parts.append(f"Resolution criteria: {r['resolution_criteria'][:500]}")
    if r.get("context"):
        parts.append(f"Information as of {r.get('as_of_date')}:\n{r['context'][:1200]}")
    parts.append(f"Forecast the probability this resolves YES, as of {r.get('as_of_date')}.")
    return "\n".join(parts)


_PROB = re.compile(r"probability\s*[:=]\s*([01](?:\.\d+)?|\.\d+)", re.I)


def _parse_p(text: str):
    if not text:
        return None
    m = list(_PROB.finditer(text))
    if m:
        try:
            p = float(m[-1].group(1))
            return min(0.99, max(0.01, p))
        except ValueError:
            return None
    # fallback: last standalone float in [0,1]
    for tok in reversed(re.findall(r"\d?\.\d+", text)):
        v = float(tok)
        if 0 <= v <= 1:
            return min(0.99, max(0.01, v))
    return None


def _resolve_proxy(spec):
    """A bare provider name → a FRESH rotating proxy URL each call (dodges per-IP rate limits);
    a full URL is used as-is; None = direct."""
    if not spec:
        return None
    if "://" in spec:
        return spec
    from engine.adapters import proxy as px
    return px.proxy_url(spec)


def _one_question(r, n, keep, provider, proxy_spec):
    """Best-of-N for a single question (own DB conn → thread-safe). Returns (sft_rows, base_brier)."""
    conn = db.connect()
    try:
        outcome = r["outcome"]
        # Rejection baseline = the BEST anchor the row carries (quant model_prob for numeric, crowd_prob
        # for markets, else the reference-class base_rate, else 0.5). A trace is kept only if it BEATS
        # this — so on market rows the student must beat the CROWD, not a 0.5 strawman (§4.5.9 / the
        # mission's "keep best-of-N beating crowd/base-rate"). This is what teaches anchor→ADJUST rather
        # than anchor→copy, and it's the source of the decorrelation edge (uncorrelated, value-adding
        # adjustments). Generate from the CURATED grpo_train.jsonl so the user turn already carries the
        # structured-anchors block → the trace reasons from the same anchors the model gets at test time.
        anchors = [r.get("model_prob"), r.get("crowd_prob"), r.get("base_rate")]
        base_p = next((a for a in anchors if a is not None and 0.0 <= float(a) <= 1.0), 0.5)
        base_brier = (float(base_p) - outcome) ** 2
        cands = []
        for _ in range(n):
            txt = None
            for _retry in range(3):          # transient proxy 403/429 → fresh IP and try again
                try:
                    txt = llm.complete(conn, _user(r), provider=provider, system=SYSTEM,
                                       max_tokens=700, proxy=_resolve_proxy(proxy_spec), est_cost_cents=0)
                    break
                except Exception:
                    txt = None
            if txt is None:
                continue
            p = _parse_p(txt)
            if p is None:
                continue
            cands.append(((p - outcome) ** 2, p, txt))
        winners = sorted([c for c in cands if c[0] <= base_brier])[:keep]   # rejection filter
        out = [{
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": _user(r)},
                {"role": "assistant", "content": txt.strip()},
            ],
            "id": r["id"], "source": r["source"], "domain": r.get("domain"),
            "as_of_date": r.get("as_of_date"), "resolution_date": r.get("resolution_date"),
            "outcome": outcome, "trace_prob": p, "trace_brier": round(brier, 4),
            "leak_ok": r.get("leak_ok"),
        } for brier, p, txt in winners]
        return out, base_brier
    finally:
        conn.close()


def generate(rows, n: int, keep: int, proxy, provider="deepinfra_keyless", workers: int = 4,
             sink=None):
    """Best-of-N over all rows. If `sink` (an open file handle) is given, each question's kept
    traces are written + flushed AS the future completes — crash-resilient + live-monitorable for
    a multi-hour run; the same rows are still returned for the in-memory summary."""
    sft = []
    kept_q = brier_sum = base_sum = 0.0
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_one_question, r, n, keep, provider, proxy) for r in rows]
        for fut in as_completed(futures):
            out, base_brier = fut.result()
            if out:
                kept_q += 1
            for row in out:
                brier_sum += row["trace_brier"]
                base_sum += base_brier
                if sink is not None:
                    sink.write(json.dumps(row) + "\n")
            if out and sink is not None:
                sink.flush()
            sft.extend(out)
            done += 1
            if done % 10 == 0:
                print(f"  ...{done}/{len(rows)} questions, {len(sft)} traces kept", flush=True)
    return sft, kept_q, brier_sum, base_sum


def main():
    args = sys.argv[1:]
    def opt(flag, default=None, cast=str):
        return cast(args[args.index(flag) + 1]) if flag in args else default
    inp = Path(opt("--in", "data/forecastbench/trainset/dataset_questions.jsonl"))
    out = Path(opt("--out", "data/forecastbench/trainset/sft_traces.jsonl"))
    n = int(opt("--n", 6)); keep = int(opt("--keep", 2))
    limit = opt("--limit", None, int)
    proxy = opt("--proxy")           # bare name (floxy/evomi) → fresh rotating IP per call; or a full URL
    provider = opt("--provider", "deepinfra_keyless")
    workers = int(opt("--workers", 4))
    resume = "--resume" in args      # skip question-ids already in --out, APPEND (crash/OOM-safe)

    rows = [json.loads(l) for l in inp.open()]
    if limit:
        rows = rows[:limit]
    out.parent.mkdir(parents=True, exist_ok=True)
    mode = "w"
    if resume and out.exists():
        done_ids = {json.loads(l)["id"] for l in out.open() if l.strip()}
        before = len(rows)
        rows = [r for r in rows if r["id"] not in done_ids]
        mode = "a"
        print(f"resume: {len(done_ids)} question-ids already in {out.name}; "
              f"{before - len(rows)} skipped, {len(rows)} remain", flush=True)
    print(f"generating traces for {len(rows)} questions "
          f"(n={n}, keep={keep}, {provider}, proxy={proxy}, workers={workers}, mode={mode}) ...", flush=True)
    with out.open(mode) as sink:
        sft, kept_q, brier_sum, base_sum = generate(rows, n, keep, proxy, provider, workers, sink=sink)
    nt = len(sft)
    print(f"\n  kept {nt} traces over {kept_q}/{len(rows)} questions → {out}")
    if nt:
        print(f"  kept-trace Brier {brier_sum/nt:.4f} vs baseline {base_sum/nt:.4f} (kept = beats baseline)")


if __name__ == "__main__":
    main()
