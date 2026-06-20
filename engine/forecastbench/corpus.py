"""Corpus assembler — merge the minted + harvested rows into one deduped, leak-split GRPO corpus.

trainset.py (numeric) and harvest.py (markets) each emit the same unified schema. This concatenates
them, dedups by id, and makes the clean TEMPORAL split that the leak discipline demands:

  • EVAL  = leak_ok True  → resolution date AFTER the base-model cutoff. The model could NOT have known
            the outcome → the only honest test of forecasting skill (forward / leak-free).
  • TRAIN = leak_ok False → resolution at/before the cutoff. Fine to learn the behavior on; never scored.

The split is by `leak_ok` (computed against --cutoff at mint/harvest time), so train and eval are disjoint
in time and outcome-knowledge. Also reports source/domain coverage so we can see the variety at a glance.

Run:  python -m engine.forecastbench.corpus   (reads data/forecastbench/trainset/*.jsonl)
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

DIR = Path(__file__).resolve().parents[2] / "data" / "forecastbench" / "trainset"
GRPO_INPUTS = ["dataset_questions.jsonl", "market_questions.jsonl", "bench_questions.jsonl"]


def _load(name):
    f = DIR / name
    if not f.exists():
        return []
    return [json.loads(l) for l in f.open() if l.strip()]


def _report(tag, rows):
    n = len(rows)
    if not n:
        print(f"  {tag}: 0 rows"); return
    bal = Counter(r["outcome"] for r in rows)
    print(f"  {tag}: {n} rows | YES {bal[1]} ({bal[1]/n:.0%}) NO {bal[0]} "
          f"| sources {dict(Counter(r['source'] for r in rows))}")
    dom = Counter(r.get("domain") for r in rows)
    print(f"      domains ({len(dom)}): {dict(dom.most_common())}")


def _cap_domain(rows, domain, cap):
    """Downsample one domain to `cap` rows (deterministic stride) — used to stop the low-signal
    'other' market bucket (niche/personal Manifold markets) from dominating. Keeps label balance."""
    keep = [r for r in rows if r.get("domain") != domain]
    sub = [r for r in rows if r.get("domain") == domain]
    if len(sub) <= cap:
        return rows
    pos = [r for r in sub if r["outcome"] == 1]
    neg = [r for r in sub if r["outcome"] == 0]
    half = cap // 2
    def stride(xs, k):
        if k <= 0 or not xs:
            return []
        s = len(xs) / k
        return [xs[int(j * s)] for j in range(min(k, len(xs)))]
    return keep + stride(pos, half) + stride(neg, half)


def main():
    import sys
    cap_other = 5000
    if "--cap-other" in sys.argv:
        cap_other = int(sys.argv[sys.argv.index("--cap-other") + 1])

    rows, seen = [], set()
    for name in GRPO_INPUTS:
        for r in _load(name):
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            rows.append(r)
    if not rows:
        print("no GRPO rows found — run trainset.py / harvest.py first"); return

    before = len(rows)
    rows = _cap_domain(rows, "other", cap_other)      # trim the low-signal bucket
    if len(rows) != before:
        print(f"capped 'other' domain → dropped {before - len(rows)} low-signal market rows")

    train = [r for r in rows if not r.get("leak_ok")]
    evalset = [r for r in rows if r.get("leak_ok")]
    (DIR / "grpo_train.jsonl").write_text("".join(json.dumps(r) + "\n" for r in train))
    (DIR / "grpo_eval.jsonl").write_text("".join(json.dumps(r) + "\n" for r in evalset))

    print(f"merged {len(rows)} deduped GRPO rows → grpo_train.jsonl + grpo_eval.jsonl")
    _report("TRAIN (pre-cutoff)", train)
    _report("EVAL  (post-cutoff, leak-free)", evalset)
    # Merge every SFT shard (sft_market*.jsonl, sft_dataset*.jsonl, ...) → one sft_all.jsonl that
    # sft.py trains on. Dedup by (id, exact trace text) so re-runs don't double-count, while two
    # genuinely different reasoning traces for the same question (even at the same prob) both survive.
    def _trace_text(r):
        msgs = r.get("messages") or []
        return msgs[-1].get("content", "") if msgs else ""
    sft, sft_seen = [], set()
    for f in sorted(DIR.glob("sft_*.jsonl")):
        if f.name == "sft_all.jsonl":
            continue
        for r in _load(f.name):
            k = (r.get("id"), _trace_text(r))
            if k in sft_seen:
                continue
            sft_seen.add(k)
            sft.append(r)
    if sft:
        (DIR / "sft_all.jsonl").write_text("".join(json.dumps(r) + "\n" for r in sft))
        sb = Counter(r.get("domain") for r in sft)
        kb = Counter(("dataset" if r.get("source") in
                      ("fred", "dbnomics", "acled", "wikipedia", "yfinance") else "market")
                     for r in sft)
        print(f"  SFT traces: {len(sft)} → sft_all.jsonl | kind {dict(kb)} | domains {dict(sb.most_common())}")


if __name__ == "__main__":
    main()
