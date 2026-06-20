"""Multi-model inference bank — the LLM ensemble leg, run at a sampling scale others can't afford.

The current top ForecastBench AI bots (Grok 4.20, AIA, Cassi) don't fine-tune — they
generate-many → aggregate → calibrate. Our asymmetry is that our frontier calls are FREE
(keyless DeepInfra roster, engine.adapters.llm), so we can do that harder: instead of 8 samples
from ONE model, we sample N from EACH of several frontier models. More models = more decorrelation,
which is the literal ensemble-value math (error variance ∝ 1/N only when the errors are
independent — ensemble.py §0). This module produces the raw material; ensemble.py measures the
decorrelation and fits the extremized pool.

What it emits: one `--pred name=path.jsonl` file per model (id→mean-of-N prob) plus a pooled file
(equal-logit mean across all samples). Those plug STRAIGHT into ensemble.py's --pred hook, so the
moment this runs we get a real, leak-free decorrelation + marginal-value number off the keyless
roster — no GPU, no fine-tune, $0.

LEAKAGE NOTE (honest, the same caveat as traces.py / [[parametric-leakage]]): the roster models are
recent, so on HISTORICAL eval/backtest rows they may already know the outcome — their absolute Brier
here is an OPTIMISTIC upper bound, NOT proof of forward skill. Two things are still honestly
measurable on the past: (1) the DECORRELATION STRUCTURE between models and against the crowd/base-rate
(memorization doesn't make errors correlated in a way that flatters the ensemble), and (2) the
mechanics of aggregation+extremization. The real verdict on the LLM leg is FORWARD (a live round
whose outcome the models cannot have seen). Build it, measure decorrelation now, trust it forward.

PROXY (critical, verified 2026-06-11): DeepInfra's keyless route 403-BLOCKS datacenter IPs, so
`--proxy floxy` (DC) returns HTTP 403 on every call (this caused a silent 0%-coverage run). Use
`--proxy evomi` (RESIDENTIAL) or run direct (this Mac is resi). The 429s that remain are PER-MODEL
on the hot models (DeepSeek/Kimi/GLM-5) — the roster spread + `--resume` (fill misses across passes)
handle those. See [[llm-inference-bank-and-data-fleet]].

Run (decorrelation measurement on the leak-gated eval set — the number today):
  python -m engine.forecastbench.inference --eval --limit 400 --n 3 --proxy evomi --resume
  # then it prints the exact ensemble.py command to score what it wrote.

Run (forward/backtest submission preds for a round's question set):
  python -m engine.forecastbench.inference --qset 2026-06-14 --n 3 --proxy evomi --resume
"""
from __future__ import annotations

import json
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from engine import db
from engine.adapters import llm

from .ensemble import _logit, _sigmoid
from .traces import SYSTEM, _parse_p, _resolve_proxy, _user

# Verified keyless-OK via the DeepInfra web-embed route (live-probed against the catalog 2026-06-11).
# A DIVERSE frontier slate across 6 model FAMILIES (DeepSeek/Moonshot/Qwen/Z-ai/Xiaomi/NVIDIA) —
# family diversity is what makes the errors decorrelated, which IS the ensemble's whole edge. Sampling
# from EACH (not the adapter's shuffle) gives every model its own scored --pred column. The premium
# frontier (Qwen3-Max/3.7-Max, gemini-3.x, claude-4.x, ByteDance-Seed, MiniMax-M2.7) is keyless-403
# (paid only — cheap if ever keyed: ~$0.15–1.50/Mtok). 429-throttled-but-live models kept as a tail.
ROSTER = [
    "deepseek-ai/DeepSeek-V4-Pro",                # DeepSeek
    "moonshotai/Kimi-K2.6",                       # Moonshot
    "Qwen/Qwen3.5-397B-A17B",                     # Qwen flagship MoE
    "Qwen/Qwen3.6-35B-A3B",                       # Qwen (smaller, fast)
    "Qwen/Qwen3.5-122B-A10B",                     # Qwen (mid MoE)
    "zai-org/GLM-5.1",                            # Zhipu
    "XiaomiMiMo/MiMo-V2.5-Pro",                   # Xiaomi
    "nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B",   # NVIDIA 550B
    "MiniMaxAI/MiniMax-M2.5",                     # MiniMax — 7th family, max decorrelation
    "moonshotai/Kimi-K2-Thinking",                # Moonshot (reasoning variant)
    "deepseek-ai/DeepSeek-V3.2", "moonshotai/Kimi-K2.5", "zai-org/GLM-5",  # live-but-throttled tail
]

PRED_DIR = Path(__file__).resolve().parents[2] / "data" / "forecastbench" / "preds"


def _slug(model: str) -> str:
    return model.split("/")[-1].replace(".", "").replace("-", "").lower()


def _pick_proxy(spec):
    """Rotate across a comma-list of proxy providers (e.g. 'evomi,floxy') — a fresh provider+IP per
    call widens the keyless rate ceiling. DeepInfra flags a single pool's IPs under sustained load
    (the crowd-blind run hit 0% after ~2,500 calls burned the floxy pool), so spreading across Evomi
    (resi, rarely blocked) + Floxy (DC) multiplies headroom. A bare name or full URL passes through."""
    if spec and "," in spec:
        return random.choice([s.strip() for s in spec.split(",") if s.strip()])
    return spec


def pool_logodds(probs, d: float = 1.0):
    """Equal-logit (geometric) mean of probabilities, optionally extremized by d>1.

    The geometric/log-odds mean is the right pool for independent forecasters; d>1 sharpens an
    under-confident average (the cheapest Brier gain on the board). d=1 here is the honest default —
    ensemble.py FITS d on a held-out half so it is never fit-on-itself; this standalone pool stays
    un-extremized so the downstream harness owns the calibration."""
    ps = [p for p in probs if p is not None]
    if not ps:
        return None
    z = sum(_logit(p) for p in ps) / len(ps)
    return _sigmoid(d * z)


def _data_block(q: dict, due) -> str:
    """Leak-safe DATA context for a dataset question: the recent point-in-time series values plus the
    quant base-rate model's P(higher) as an anchor. Turns the LLM from a blind guesser into an
    anchor-adjuster (the Halawi recipe) — it can reason over the actual numbers, and decorrelated
    value (if any) comes from the *adjustment*. Pre-freeze only, so no leakage."""
    from . import dataset as ds
    src = q.get("source")
    try:
        if src == "fred":
            hist = ds.fetch_fred(q["id"])
        elif src == "yfinance":
            hist = ds.fetch_yahoo(q["id"])
        elif src == "dbnomics":
            hist = ds.fetch_dbnomics(q.get("url", ""))
        else:
            return ""
        h = [(d, v) for d, v in hist if d <= due][-12:]
        if not h:
            return ""
        recent = "; ".join(f"{d.isoformat()}={v:g}" for d, v in h)
        qp = ds.forecast_dataset_question(q, due)
        anchor = next((p for p in qp.values() if p is not None), None) if qp else None
        block = f"\nRecent point-in-time values of this series (≤{due}): {recent}."
        if anchor is not None:
            block += (f"\nA leak-free statistical model estimates P(higher at the horizon) = {anchor:.2f}. "
                      "Anchor on that estimate; adjust only if the data gives you a concrete reason.")
        return block
    except Exception:
        return ""


def _qset_prompt(q: dict, due, crowd_blind: bool = False, with_data: bool = False) -> str:
    return _qset_prompt_with_metadata(q, due, crowd_blind=crowd_blind, with_data=with_data)[0]


def _qset_prompt_with_metadata(
    q: dict,
    due,
    crowd_blind: bool = False,
    with_data: bool = False,
) -> tuple[str, dict | None]:
    """Forecasting prompt from a live ForecastBench question (the submission schema), in the same
    Probability-line format traces._parse_p expects. (traces._user is for training rows that carry a
    `context` block; FB round questions carry market metadata instead.)

    crowd_blind: for a MARKET question, the freeze value IS the crowd probability — feeding it makes
    the bank a crowd-follower (forward run 2026-06-07: corr 0.966 with crowd). Suppressing it tests
    the bank's INDEPENDENT skill — the decorrelation moat. For a DATASET question the freeze value is
    the current series LEVEL (legitimate, never a crowd prob), so it is always kept."""
    from .score import MARKET_SOURCES
    parts = [f"Question: {(q.get('question') or '').strip()}"]
    rc = q.get("resolution_criteria") or q.get("market_info_resolution_criteria")
    if rc:
        parts.append(f"Resolution criteria: {str(rc).strip()[:600]}")
    if q.get("background"):
        parts.append(f"Background: {str(q['background']).strip()[:500]}")
    fv = q.get("freeze_datetime_value")
    is_market = q.get("source") in MARKET_SOURCES
    if fv not in (None, "") and not (is_market and crowd_blind):
        label = "Current/crowd value" if is_market else "Current value"
        parts.append(f"{label} as of {due}: {fv}")
    if with_data and not is_market:                # give the LLM the series + quant anchor to reason from
        parts.append(_data_block(q, due))
    world_state_meta = None
    if _world_state_enabled():
        ctx = _world_state_context(q, due)
        if ctx["block"]:
            parts.append(ctx["block"])
        world_state_meta = ctx["metadata"]
    parts.append(f"Forecast the probability this resolves YES, as of {due}. Source: {q.get('source')}.")
    return "\n".join(p for p in parts if p), world_state_meta


def _world_state_enabled() -> bool:
    mode = os.getenv("WORLD_STATE_PACK", "").strip().lower()
    return mode in {"1", "true", "yes", "proof"} or _world_state_proof_enabled()


def _world_state_proof_enabled() -> bool:
    return (
        os.getenv("WORLD_STATE_PROOF", "").strip().lower() in {"1", "true", "yes"}
        or os.getenv("WORLD_STATE_PACK", "").strip().lower() == "proof"
    )


def _world_state_metadata_from_pack(pack: dict, *, mode: str) -> dict:
    snap = pack.get("snapshot") or {}
    facts = pack.get("facts") or []
    sources = pack.get("sources") or []
    return {
        "mode": mode,
        "topic": pack.get("topic"),
        "as_of": pack.get("as_of"),
        "snapshot_hash": snap.get("snapshot_hash"),
        "fact_count": snap.get("fact_count", len(facts)),
        "source_count": snap.get("source_count", len(sources)),
        "facts": [
            {
                "id": f.get("id"),
                "predicate": f.get("predicate"),
                "source_id": f.get("source_id"),
                "content_hash": f.get("content_hash"),
                "raw_doc_status": f.get("raw_doc_status"),
                "raw_doc_remote_uri": f.get("raw_doc_remote_uri"),
            }
            for f in facts
        ],
        "sources": [
            {
                "id": s.get("id"),
                "title": s.get("title"),
                "url": s.get("url"),
                "content_hash": s.get("content_hash"),
                "raw_doc_status": s.get("raw_doc_status"),
                "raw_doc_remote_uri": s.get("raw_doc_remote_uri"),
            }
            for s in sources
        ],
    }


def _world_state_metadata_from_proof(proof: dict) -> dict:
    out = _world_state_metadata_from_pack(proof, mode="proof")
    out["all_visible_as_of_proven"] = proof.get("all_visible_as_of_proven")
    return out


def _world_state_context(q: dict, due) -> dict:
    """Feature-flagged frozen context. Failure degrades to no block, never to a live spend."""
    try:
        from engine import world_state

        topic = str(q.get("question") or q.get("title") or "").strip()
        if not topic:
            return {"block": "", "metadata": None}
        conn = db.connect()
        db.init_db(conn)
        if _world_state_proof_enabled():
            proof = world_state.state_proof(topic, due, conn=conn)
            conn.close()
            text = world_state.format_proof(proof)
            return {
                "block": "\nFrozen world-state proof:\n" + text[:2200],
                "metadata": _world_state_metadata_from_proof(proof),
            }
        pack = world_state.state_pack(topic, due, conn=conn, record=False)
        conn.close()
        text = world_state.format_pack(pack)
        return {
            "block": "\nFrozen world-state context:\n" + text[:2200],
            "metadata": _world_state_metadata_from_pack(pack, mode="pack"),
        }
    except Exception:
        return {"block": "", "metadata": None}


def _world_state_block(q: dict, due) -> str:
    return str(_world_state_context(q, due).get("block") or "")


def sample_one(prompt: str, models, n: int, provider: str, proxy_spec):
    """Best-of-N per model for one prompt (own DB conn → thread-safe).
    Returns {model: [prob, ...]} keeping only samples that parsed a probability."""
    conn = db.connect()
    try:
        out: dict[str, list] = {}
        for m in models:
            ps = []
            for _ in range(n):
                txt = None
                for _retry in range(3):       # transient proxy 403/429 → fresh IP, retry
                    try:
                        txt = llm.complete(conn, prompt, provider=provider, system=SYSTEM,
                                           model=m, max_tokens=700,
                                           proxy=_resolve_proxy(_pick_proxy(proxy_spec)),
                                           est_cost_cents=0)
                        break
                    except Exception:
                        txt = None
                if txt is None:
                    continue
                p = _parse_p(txt)
                if p is not None:
                    ps.append(p)
            if ps:
                out[m] = ps
        return out
    finally:
        conn.close()


def run(items, models, n, provider, proxy, workers, label="rows"):
    """Sample every item (each carries an id + a built prompt) across the roster.

    Returns ({model_slug: {id: mean_prob}}, {id: pool_prob}). Threaded over items; each item does its
    own per-model best-of-N. `items` = list of (id, prompt)."""
    per_model: dict[str, dict] = {_slug(m): {} for m in models}
    pooled: dict = {}
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(sample_one, prompt, models, n, provider, proxy): qid
                for qid, prompt in items}
        for fut in as_completed(futs):
            qid = futs[fut]
            res = fut.result()
            all_samples = []
            for m, ps in res.items():
                per_model[_slug(m)][_keyable(qid)] = pool_logodds(ps)
                all_samples.extend(ps)
            if all_samples:
                pooled[_keyable(qid)] = pool_logodds(all_samples)
            done += 1
            if done % 25 == 0:
                print(f"  ...{done}/{len(items)} {label}, pooled {len(pooled)}", flush=True)
    return per_model, pooled


def _keyable(qid):
    """ForecastBench combo ids are lists (unhashable) — JSON-encode them so they round-trip as
    --pred keys, matching how ensemble.py reads r['id'] verbatim from the same source rows."""
    return json.dumps(qid) if isinstance(qid, list) else qid


def _read_pred(path) -> dict:
    """Existing {id: prob} from a pred file (for --resume merge)."""
    out = {}
    if path.exists():
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    out[r["id"]] = r["prob"]
                except Exception:
                    pass
    return out


def _world_state_sidecar_path(tag: str) -> Path:
    return PRED_DIR / f"world_state_{tag}.jsonl"


def _read_world_state_metadata(path: Path) -> dict:
    out = {}
    if path.exists():
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    out[_keyable(r["id"])] = r
                except Exception:
                    pass
    return out


def _world_state_sidecar_row(qid, meta: dict) -> dict:
    row = {
        "id": _keyable(qid),
        "topic": meta.get("topic"),
        "as_of": meta.get("as_of"),
        "mode": meta.get("mode"),
        "snapshot_hash": meta.get("snapshot_hash"),
        "fact_count": meta.get("fact_count"),
        "source_count": meta.get("source_count"),
        "facts": meta.get("facts") or [],
        "sources": meta.get("sources") or [],
    }
    if "all_visible_as_of_proven" in meta:
        row["all_visible_as_of_proven"] = meta.get("all_visible_as_of_proven")
    return row


def _write_world_state_metadata(rows, tag: str, resume: bool = False):
    """Write the frozen context sidecar for qset preds.

    On resume, keep existing rows for already-predicted ids: their prompts may have
    used an older DB state, so overwriting would blur provenance.
    """
    path = _world_state_sidecar_path(tag)
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    merged = _read_world_state_metadata(path) if resume else {}
    for qid, meta in rows:
        if not meta:
            continue
        key = _keyable(qid)
        if resume and key in merged:
            continue
        merged[key] = _world_state_sidecar_row(qid, meta)
    if not merged:
        return path, 0
    with path.open("w") as f:
        for key in sorted(merged, key=lambda k: str(k)):
            f.write(json.dumps(merged[key], sort_keys=True) + "\n")
    return path, len(merged)


def _write_preds(per_model, pooled, tag, resume=False):
    """Write per-model + pooled --pred files. With resume=True, MERGE onto whatever a prior pass
    already wrote (the multi-pass coverage fill — each pass adds the ids the rate limit dropped)."""
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for slug, m in per_model.items():
        path = PRED_DIR / f"llm_{slug}_{tag}.jsonl"
        merged = _read_pred(path) if resume else {}
        merged.update({k: v for k, v in m.items() if v is not None})
        if not merged:
            continue
        with path.open("w") as f:
            for qid, p in merged.items():
                f.write(json.dumps({"id": qid, "prob": p}) + "\n")
        written.append((slug, path, len(merged)))
    pool_path = PRED_DIR / f"llm_pool_{tag}.jsonl"
    merged_pool = _read_pred(pool_path) if resume else {}
    merged_pool.update({k: v for k, v in pooled.items() if v is not None})
    with pool_path.open("w") as f:
        for qid, p in merged_pool.items():
            f.write(json.dumps({"id": qid, "prob": p}) + "\n")
    return written, pool_path, len(merged_pool)


def main():
    args = sys.argv[1:]
    def opt(flag, default=None, cast=str):
        return cast(args[args.index(flag) + 1]) if flag in args else default

    n = int(opt("--n", 3))
    limit = opt("--limit", None, int)
    proxy = opt("--proxy")
    provider = opt("--provider", "deepinfra_keyless")
    workers = int(opt("--workers", 4))
    resume = "--resume" in args
    models = ROSTER if "--model" not in args else [opt("--model")]
    world_state_rows = []

    if "--qset" in args:
        # Forward / backtest submission preds for a round's question set.
        from .score import single_questions
        from .submit import fetch_question_set
        from datetime import datetime
        arg = opt("--qset")
        path = fetch_question_set(arg) if (len(arg) == 10 and arg[4] == "-") else arg
        qd = json.loads(Path(path).read_text())
        due = datetime.strptime(qd["forecast_due_date"], "%Y-%m-%d").date()
        qs = single_questions(qd["questions"])
        from .score import MARKET_SOURCES
        if "--market-only" in args:
            qs = [q for q in qs if q.get("source") in MARKET_SOURCES]
        if "--dataset-only" in args:
            qs = [q for q in qs if q.get("source") not in MARKET_SOURCES]
        if limit:
            qs = qs[:limit]
        cb = "--crowd-blind" in args
        wd = "--with-data" in args
        if wd:                                     # warm the series cache so _data_block reads cache, not 250 live fetches
            from . import dataset as ds
            ds.prefetch_round(qd["questions"])
        prompt_rows = []
        for q in qs:
            prompt, meta = _qset_prompt_with_metadata(q, due, crowd_blind=cb, with_data=wd)
            prompt_rows.append((q["id"], prompt, meta))
            if meta:
                world_state_rows.append((q["id"], meta))
        items = [(qid, prompt) for qid, prompt, _meta in prompt_rows]
        tag = (f"qset_{qd['forecast_due_date']}" + ("_blind" if cb else "") + ("_data" if wd else ""))
        if resume:
            done = set(_read_pred(PRED_DIR / f"llm_pool_{tag}.jsonl"))
            before = len(items)
            items = [it for it in items if _keyable(it[0]) not in done]
            print(f"resume: {len(done)} ids already done, {before - len(items)} skipped, "
                  f"{len(items)} to do", flush=True)
    else:
        # Decorrelation measurement on the leak-gated eval set (the honest number today).
        data = Path(opt("--data", str(PRED_DIR.parent / "trainset" / "grpo_eval.jsonl")))
        rows = [json.loads(l) for l in data.open() if l.strip()]
        if limit:
            rows = rows[:limit]
        items = [(r["id"], _user(r)) for r in rows]
        tag = "eval"
        if resume:
            done = set(_read_pred(PRED_DIR / f"llm_pool_{tag}.jsonl"))
            before = len(items)
            items = [it for it in items if _keyable(it[0]) not in done]
            print(f"resume: {len(done)} ids already done, {before - len(items)} skipped, "
                  f"{len(items)} to do", flush=True)

    print(f"sampling {len(items)} items × {len(models)} models × n={n} "
          f"({provider}, proxy={proxy}, workers={workers}) ...", flush=True)
    per_model, pooled = run(items, models, n, provider, proxy, workers, label=tag)
    written, pool_path, n_pool = _write_preds(per_model, pooled, tag, resume=resume)
    if world_state_rows:
        ws_path, n_ws = _write_world_state_metadata(world_state_rows, tag, resume=resume)
        print(f"wrote world-state sidecar ({n_ws} ids) -> {ws_path.name}")

    print(f"\nwrote {len(written)} per-model pred files + pool ({n_pool} ids total) → {PRED_DIR}")
    for slug, path, k in written:
        print(f"  {slug:24s} {k:5d} ids  {path.name}")
    if tag == "eval" and written:
        preds = " ".join(f"--pred {slug}={path}" for slug, path, _ in written)
        print("\nNow score decorrelation + marginal value:")
        print(f"  python -m engine.forecastbench.ensemble --all "
              f"--pred pool={pool_path} {preds}")


if __name__ == "__main__":
    main()
