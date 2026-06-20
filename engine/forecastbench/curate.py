"""Curate + structurally enrich the GRPO corpus — the $0 'win on data, not money' pass.

The raw merged corpus (corpus.py) is 68% Manifold with forecasting-useless context, the numeric
calibration edge swamped 2:1, base_rate never populated, crowd_prob thrown away, ~34% near-duplicates,
and label-degenerate micro-sources the model can shortcut. That is a low-signal RL diet. This pass
makes the training distribution earn its compute, and grounds every row in STRUCTURED priors so the
fine-tuned model reasons from reference-class anchors (decorrelated from frontier parametric recall)
rather than vibes — the marginal-ensemble-value edge that 120B-on-a-node can't buy with money.

Two jobs:

  1. CURATE (TRAIN only — EVAL stays a faithful mirror of the real ForecastBench distribution):
     • drop empty/outcome-less rows and label-degenerate micro-sources (acled 0% YES, metaculus 100% …)
     • near-dup dedup by (source, domain, question-signature), keeping the richest copy
     • rebalance Manifold down to the numeric count so it's ~50/50 market:numeric (the §4.4 mix),
       preferring high-liquidity (forecaster-count) markets and holding outcomes near 50/50

  2. ENRICH (TRAIN + EVAL — leak-safe):
     • compute reference-class base rates from PRE-CUTOFF rows only (an aggregate prior over the past,
       never the row's own future outcome) and write the `base_rate` field
     • append a STRUCTURED ANCHORS block to `context` so common.user_prompt surfaces it unchanged:
         - numeric rows → the frozen-series quant estimate (`model_prob`, computed ≤ as_of)
         - market rows  → the crowd/market probability (`crowd_prob`, the freeze-time value) when present
         - always       → the reference-class base rate
       All three are inputs a calibrated forecaster is SUPPOSED to anchor on, and all three are exactly
       what our own submission pipeline can compute at test time → in-distribution, not leakage.

Overwrites grpo_train.jsonl / grpo_eval.jsonl in place after backing up the originals ONCE to
*_raw.jsonl, so the existing run scripts pick up the curated data with no path changes.

Run:  python -m engine.forecastbench.curate            (reads/writes data/forecastbench/trainset/)
      python -m engine.forecastbench.curate --dry-run  (report only, write nothing)
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

DIR = Path(__file__).resolve().parents[2] / "data" / "forecastbench" / "trainset"
NUMERIC_SOURCES = {"fred", "dbnomics", "yfinance", "wikipedia", "acled"}  # the 'dataset' / calibration half
_FORECASTERS = re.compile(r"([\d,]+)\s+forecasters")


def _load(name):
    f = DIR / name
    return [json.loads(l) for l in f.open() if l.strip()] if f.exists() else []


def _sig(r):
    """Market re-ingestion signature: the SAME market harvested under different seed terms → one row.
    Numbers/dates are KEPT (they distinguish genuinely different markets); only exact re-ingests of the
    same question text collapse. NEVER applied to numeric rows — their multi-horizon / multi-anchor
    ladder (same series, different threshold/horizon/as_of) is intentional variety (§4.3), not duplication."""
    q = re.sub(r"[^a-z0-9 ]+", " ", (r.get("question") or "").lower())
    return (r.get("domain"), re.sub(r"\s+", " ", q).strip())


def _richness(r):
    """Prefer the copy carrying the most signal when collapsing near-dups."""
    return ((r.get("model_prob") is not None) + (r.get("crowd_prob") is not None),
            len(str(r.get("context") or "")), len(str(r.get("resolution_criteria") or "")))


def _forecasters(r):
    m = _FORECASTERS.search(str(r.get("context") or ""))
    return int(m.group(1).replace(",", "")) if m else 0


def _dedup_market(rows):
    """Dedup MARKET rows only (numeric multi-horizon ladder is intentional → passed through untouched)."""
    numeric = [r for r in rows if r.get("source") in NUMERIC_SOURCES]
    best = {}
    for r in rows:
        if r.get("source") in NUMERIC_SOURCES:
            continue
        s = _sig(r)
        if s not in best or _richness(r) > _richness(best[s]):
            best[s] = r
    return numeric + list(best.values())


def _balanced_cap(rows, cap):
    """Keep `cap` rows at ~50/50 outcome, preferring high-forecaster-count (liquid) markets."""
    pos = sorted((r for r in rows if r["outcome"] == 1), key=_forecasters, reverse=True)
    neg = sorted((r for r in rows if r["outcome"] == 0), key=_forecasters, reverse=True)
    half = cap // 2
    return pos[:half] + neg[:cap - half]


def _ref_base_rates(train):
    """Leak-safe reference-class priors: YES-rate by (source,domain) over PRE-CUTOFF rows only.
    An aggregate over the past — the literal base rate a forecaster anchors on — never a row's own
    outcome. Smoothed (Laplace) and only kept where the class has enough support to mean something."""
    agg = defaultdict(lambda: [0, 0])           # key -> [n, yes]
    for r in train:
        agg[(r.get("source"), r.get("domain"))][0] += 1
        agg[(r.get("source"), r.get("domain"))][1] += int(r["outcome"])
    rates = {}
    for k, (n, y) in agg.items():
        if n >= 25:                             # below this the prior is noise, skip
            rates[k] = (y + 1) / (n + 2)
    # domain-level fallback (pooled across sources) for thin (source,domain) cells
    dom = defaultdict(lambda: [0, 0])
    for r in train:
        dom[r.get("domain")][0] += 1
        dom[r.get("domain")][1] += int(r["outcome"])
    dom_rates = {d: (y + 1) / (n + 2) for d, (n, y) in dom.items() if n >= 25}
    return rates, dom_rates


def _enrich(rows, rates, dom_rates):
    """Write base_rate + append a STRUCTURED ANCHORS block to context. Leak-safe (all ≤ as_of)."""
    for r in rows:
        br = rates.get((r.get("source"), r.get("domain"))) or dom_rates.get(r.get("domain"))
        if br is not None:
            r["base_rate"] = round(br, 3)
        anchors = []
        mp, cp = r.get("model_prob"), r.get("crowd_prob")
        if mp is not None and 0.0 <= float(mp) <= 1.0:
            anchors.append(f"Quant reference estimate from the frozen series (as of {r.get('as_of_date')}): "
                           f"P(YES)={float(mp):.2f}")
        # GUARD: only inject crowd as a probability when it actually IS one ([0,1]). Dataset sources
        # carry a series LEVEL in freeze_datetime_value, never a prob — injecting "P(YES)=159000000"
        # poisoned the anchor block (the 0.47-Brier bug). bench.py now nulls those, this is depth.
        if cp is not None and 0.0 <= float(cp) <= 1.0:
            anchors.append(f"Market/crowd probability at the forecast date: P(YES)={float(cp):.2f}")
        # Only surface the base rate when the reference class is genuinely SKEWED. Our corpus is
        # balance-minted to ~50/50, so most (source,domain) rates sit at 0.50 — injecting "base rate
        # 0.50" everywhere would teach the exact hedge-to-0.5 collapse §5.3 warns against. Skip it
        # unless |br - 0.5| > 0.1, where it carries real prior signal. (Field is still set below.)
        if br is not None and abs(br - 0.5) > 0.10:
            anchors.append(f"Reference-class base rate for {r.get('domain')} questions of this kind: "
                           f"{br:.2f}")
        if anchors:
            # PREPEND, not append: common.user_prompt truncates context to ~1200 chars, so anchors at the
            # END of a long numeric series would be truncated AWAY (the model never sees them). Anchor-first
            # always survives, and the quant anchor distils the whole series anyway, so it stays informative
            # even if older series points get cut. Also the right reading order: anchor → evidence → adjust.
            tag = "Structured anchors (calibrate from these, then adjust for the specifics):\n- " \
                  + "\n- ".join(anchors)
            base = str(r.get("context") or "").lstrip()
            if "Structured anchors" not in base:        # idempotent: don't double-prepend on re-runs
                r["context"] = (tag + "\n\n" + base) if base else tag
    return rows


def _report(tag, rows):
    n = len(rows) or 1
    src = Counter(r.get("source") for r in rows)
    num = sum(1 for r in rows if r.get("source") in NUMERIC_SOURCES)
    yes = sum(int(r["outcome"]) for r in rows)
    print(f"  {tag}: {len(rows)} rows | numeric {num} ({num/n:.0%}) market {len(rows)-num} "
          f"| YES {yes/n:.0%} | base_rate set {sum(r.get('base_rate') is not None for r in rows)} "
          f"| sources {dict(src.most_common(6))}")


def main():
    dry = "--dry-run" in sys.argv
    train, evalset = _load("grpo_train.jsonl"), _load("grpo_eval.jsonl")
    if not train:
        print("no grpo_train.jsonl — run corpus.py first"); return
    print(f"raw: train {len(train)} | eval {len(evalset)}")

    # ---- CURATE train ----
    train = [r for r in train if (r.get("question") and r.get("outcome") in (0, 1))]
    src_bal = defaultdict(lambda: [0, 0])
    for r in train:
        src_bal[r.get("source")][0] += 1; src_bal[r.get("source")][1] += int(r["outcome"])
    degen = {s for s, (n, y) in src_bal.items() if n < 30 and (y / n > 0.85 or y / n < 0.15)}
    if degen:
        train = [r for r in train if r.get("source") not in degen]
        print(f"  dropped label-degenerate micro-sources: {sorted(degen)}")

    before = len(train)
    train = _dedup_market(train)
    print(f"  market re-ingest dedup: {before} → {len(train)} (dropped {before - len(train)}; numeric kept whole)")

    numeric = [r for r in train if r.get("source") in NUMERIC_SOURCES]
    market = [r for r in train if r.get("source") not in NUMERIC_SOURCES]
    cap = max(len(numeric), 4000)               # ~50/50 numeric:market, floor so markets aren't starved
    if len(market) > cap:
        market = _balanced_cap(market, cap)
        print(f"  rebalanced market half → {len(market)} (≈50/50 with {len(numeric)} numeric)")
    train = numeric + market

    # ---- ENRICH (leak-safe priors from the curated TRAIN only; applied to both splits) ----
    rates, dom_rates = _ref_base_rates(train)
    print(f"  reference-class priors: {len(rates)} (source,domain) cells + {len(dom_rates)} domain fallbacks")
    train = _enrich(train, rates, dom_rates)
    evalset = _enrich(evalset, rates, dom_rates)  # EVAL gets the same past-derived priors; never rebalanced

    print("\nCURATED:")
    _report("TRAIN", train)
    _report("EVAL ", evalset)

    if dry:
        print("\n--dry-run: nothing written"); return
    for name, rows in (("grpo_train.jsonl", train), ("grpo_eval.jsonl", evalset)):
        raw = DIR / name.replace(".jsonl", "_raw.jsonl")
        if not raw.exists():                    # back up the originals ONCE
            raw.write_text("".join(json.dumps(r) + "\n" for r in _load(name)))
        (DIR / name).write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"\nwrote curated grpo_train.jsonl + grpo_eval.jsonl (originals → *_raw.jsonl)")


if __name__ == "__main__":
    main()
