"""Judgmental forecast pipeline — research → keyless best-of-N ensemble → extremize → crowd-anchor.

This is the architecture that wins the live arena (newbenchmarksplan.md). Each lever is the cheap,
keyless version of what the leaderboard bots pay for:

  • research digest (research.py)        — current evidence the stale weights lack
  • best-of-N across the frontier ROSTER — Grok-4.20/AIA/Cassi all generate-many → aggregate; we do it
    across SEVERAL keyless models (family diversity = decorrelated errors = the real ensemble math)
  • log-odds pool + extremize            — the correct aggregator for independent forecasters; the
    ensemble mean is underconfident, so a mild d>1 sharpen is the cheapest Brier gain
  • crowd-anchor                         — showing the community median lifts LLM forecasts 17–28%
    (Schoenegger); a modest log-odds pull toward it caps overconfidence and is the Cup safety rail

NO-OVERFIT: extremize d and crowd weight are FIXED, conservative priors — never fit on the scored
set. They get re-fit OUT-OF-SAMPLE on MiniBench (held-out) later, per the plan's guardrails.
"""
from __future__ import annotations

import hashlib
import os
from datetime import date

from engine import db
from engine.adapters.llm import OPENROUTER_FREE_LEADERS
from engine.forecasting.calibration import calibration_tag
from engine.forecastbench.ensemble import _logit, _sigmoid
from engine.forecastbench.inference import ROSTER, sample_one
from engine.metaculus import research

# Fixed priors. Re-fit OUT-OF-SAMPLE on the leak-free backtest (engine/metaculus/fleet.py +
# calibrate.py), NEVER on the scored season. 2026-06-12 recalibration on 2260 leak-free forecasts:
#   • crowd anchor was the biggest lever (OOS Brier 0.202→0.137 at w≈0.5) → raised 0.30→0.40 (conservative
#     vs the 0.5 optimum, which was fit on a weak model that should defer more than a research ensemble).
#   • extremizing OVERCONFIDENT no-research forecasts HURT (OOS d*=0.8); the old 1.15 sharpen was an
#     unvalidated guess → set to neutral 1.0 until a FORWARD signal justifies sharpening.
EXTREMIZE_D = 1.0       # neutral: log-odds mean, no unvalidated sharpen (backtest: sharpening hurt)
CROWD_WEIGHT = 0.40     # log-odds pull toward the community median when it is visible (backtest: underweighted)
BLIND_SHRINK = 0.55     # toward-0.5 shrink when we have NO evidence and NO crowd (abstain-ish)
NATIVE_CROWD_WEIGHT_CAP = 0.70  # never collapse fully onto the crowd; keep independent signal alive
LOW_COVERAGE_CROWD_BONUS = 0.08
VERY_LOW_COVERAGE_CROWD_BONUS = 0.15
NO_EVIDENCE_CROWD_BONUS = 0.10
LOW_COVERAGE_BLIND_SHRINK = 0.45
VERY_LOW_COVERAGE_BLIND_SHRINK = 0.35
CALIBRATION = {
    "extremize_d": EXTREMIZE_D,
    "crowd_weight": CROWD_WEIGHT,
    "blind_shrink": BLIND_SHRINK,
    "native_crowd_weight_cap": NATIVE_CROWD_WEIGHT_CAP,
    "source": "fixed-conservative-2026-06-12",
}
CALIBRATION["tag"] = calibration_tag(CALIBRATION)

SYSTEM = (
    "You are a superforecaster: calibrated, decisive, and grounded in the evidence provided. You are "
    "given a question, its exact resolution criteria, and dated evidence retrieved today. Reason "
    "concretely: (1) the reference class and base rate; (2) what the CURRENT evidence says and how it "
    "moves you; (3) the strongest case for YES and for NO; (4) time left until resolution. Then commit "
    "to ONE calibrated probability — avoid 0 and 1, don't hedge to 0.5 on questions the evidence "
    "actually informs, and don't be falsely confident on genuinely uncertain ones. End with exactly "
    "one line: 'Probability: 0.NN'."
)


def _prompt(
    q: dict,
    digest: str,
    today: str,
    crowd: float | None,
    *,
    world_state_block: str | None = None,
) -> str:
    parts = [f"Today is {today}.",
             f"Question: {q['title']}"]
    if q.get("resolution_criteria"):
        parts.append(f"Resolution criteria: {q['resolution_criteria'][:800]}")
    if q.get("fine_print"):
        parts.append(f"Fine print: {q['fine_print'][:400]}")
    if q.get("description"):
        parts.append(f"Background: {q['description'][:600]}")
    parts.append("\n" + digest)
    if crowd is not None:
        parts.append(f"\nThe current community/crowd probability is {crowd:.2f}. Treat it as an "
                     "informed prior; adjust only where your evidence gives a concrete reason.")
    if world_state_block is not None:
        block = world_state_block
        if block:
            parts.append(block)
    elif _world_state_enabled():
        block = _world_state_block(q, today)
        if block:
            parts.append(block)
    parts.append("\nForecast the probability this question resolves YES.")
    return "\n".join(parts)


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
    out["gate_rule"] = proof.get("gate_rule")
    return out


def _world_state_context(q: dict, today: str) -> dict:
    try:
        from engine import world_state

        topic = str(q.get("title") or q.get("question") or "").strip()
        if not topic:
            return {"block": "", "metadata": None}
        conn = db.connect()
        db.init_db(conn)
        if _world_state_proof_enabled():
            proof = world_state.state_proof(topic, today, conn=conn)
            conn.close()
            return {
                "block": "\nFrozen world-state proof:\n" + world_state.format_proof(proof)[:2200],
                "metadata": _world_state_metadata_from_proof(proof),
            }
        pack = world_state.state_pack(topic, today, conn=conn, record=False)
        conn.close()
        return {
            "block": "\nFrozen world-state context:\n" + world_state.format_pack(pack)[:2200],
            "metadata": _world_state_metadata_from_pack(pack, mode="pack"),
        }
    except Exception:
        return {"block": "", "metadata": None}


def _world_state_block(q: dict, today: str) -> str:
    return str(_world_state_context(q, today).get("block") or "")


def _pool(samples: list[float], d: float) -> float:
    z = sum(_logit(p) for p in samples) / len(samples)
    return _sigmoid(d * z)


def _coverage_ratio(n_models: int, need: int) -> float:
    if need <= 0:
        return 1.0
    return max(0.0, min(1.0, n_models / need))


def _adaptive_native_crowd_weight(*, base: float, coverage: float, have_evidence: bool) -> float:
    """Use more of the exact native crowd only when our independent signal is lower quality.

    This is intentionally not applied to caller-supplied external/fuzzy anchors: those already arrive
    with a match-risk-adjusted weight from the caller.
    """
    w = base
    if not have_evidence:
        w += NO_EVIDENCE_CROWD_BONUS
    if coverage < 0.50:
        w += VERY_LOW_COVERAGE_CROWD_BONUS
    elif coverage < 0.85:
        w += LOW_COVERAGE_CROWD_BONUS
    return min(NATIVE_CROWD_WEIGHT_CAP, max(0.0, w))


def _adaptive_blind_shrink(*, coverage: float) -> float:
    """When there is no crowd and no evidence, thin councils should abstain harder."""
    if coverage < 0.50:
        return VERY_LOW_COVERAGE_BLIND_SHRINK
    if coverage < 0.85:
        return LOW_COVERAGE_BLIND_SHRINK
    return BLIND_SHRINK


def forecast_question(q: dict, *, today: str | None = None, crowd: float | None = None,
                      crowd_weight: float | None = None,
                      n: int = 2, proxy: str | None = None, do_research: bool = True,
                      with_markets: bool = False, ensemble_proxy: str | None = "",
                      min_models: int = 6, fill_passes: int = 3,
                      provider: str = "openrouter_free",
                      research_provider: str | None = None,
                      deep_research: bool = False,
                      ensemble_models: list | None = None) -> dict:
    """Full pipeline for one binary question. `q` = api.question_text(post).

    `proxy` routes the RESEARCH (Exa) calls. `ensemble_proxy` routes the LLM ensemble separately —
    default "" means "same as research"; pass None to force the ensemble DIRECT (on this resi Mac the
    home IP gets ~9/13 models vs ~2-7 through the proxy, so direct is the better ensemble default).
    Coverage-fill: re-sample only the still-missing models up to `fill_passes` times until we have
    `min_models` (the multi-pass pattern that beats keyless per-model rate limits).

    Returns {prob, n_models, n_samples, crowd, raw_ensemble, sources, reasoning}. prob is the final
    submittable probability_yes; reasoning is a short audit string (also postable as a comment)."""
    today = today or date.today().isoformat()
    ens_proxy = proxy if ensemble_proxy == "" else ensemble_proxy

    # Research. deep_research=True runs the agentic loop (Opus decompose+gap, Sonar live web) — the
    # top-bot lever; orchestration runs on `provider` (Opus is justified there). Otherwise the shallow
    # snippet pass on a CHEAP `research_provider`, reserving the ensemble model for the forecast.
    if not do_research:
        digest, sources = ("(research disabled)", [])
    elif deep_research:
        from engine.metaculus import deep_research as _dr
        ens0 = (ensemble_models or [None])[0]
        digest, sources = _dr.deep_gather(q, today, provider=provider, model=ens0)
    else:
        digest, sources = research.gather(q, today, proxy=proxy, with_markets=with_markets,
                                          provider=research_provider or provider)
    world_state_ctx = _world_state_context(q, today) if _world_state_enabled() else {"block": "", "metadata": None}
    world_state_meta = world_state_ctx.get("metadata")
    prompt = _prompt(q, digest, today, crowd, world_state_block=str(world_state_ctx.get("block") or ""))
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]

    # The old `deepinfra_keyless` web-embed route is DEAD (patched 2026-06-12); openrouter_free is the
    # live $0 replacement. Pick the roster + transport that matches the provider — openrouter is keyed
    # and direct (ignores the proxy), so a coarse multi-model loop on dead models can no longer hang us.
    if provider == "openrouter_free":
        roster, ens_spec = list(ensemble_models or OPENROUTER_FREE_LEADERS), None
    else:
        roster, ens_spec = list(ensemble_models or ROSTER), ens_proxy
    need = min(min_models, len(roster))

    per_model: dict[str, list] = {}
    for _ in range(max(1, fill_passes)):
        missing = [m for m in roster if m not in per_model]
        if not missing or len(per_model) >= need:
            break
        got = sample_one(prompt, missing, n, provider=provider, proxy_spec=ens_spec)
        per_model.update(got)
    samples = [p for ps in per_model.values() for p in ps]

    if not samples:
        # total ensemble failure → fall back to crowd if any, else true abstain
        prob = crowd if crowd is not None else 0.5
        out = {"prob": round(prob, 3), "n_models": 0, "n_samples": 0, "crowd": crowd,
               "raw_ensemble": None, "sources": sources,
               "prompt_hash": prompt_hash, "calibration": CALIBRATION,
               "quality_flags": ["no_parseable_model_samples"],
               "shadows": {"crowd_only": round(crowd, 3)} if crowd is not None else {"abstain": 0.5},
               "reasoning": "Ensemble returned no parseable samples; fell back to crowd/0.5."}
        if world_state_meta:
            out["world_state"] = world_state_meta
        return out

    raw = _pool(samples, d=1.0)                       # honest ensemble mean
    ext = _pool(samples, d=EXTREMIZE_D)               # sharpened

    have_evidence = bool(sources)
    coverage = _coverage_ratio(len(per_model), need)
    shadows = {"raw_ensemble": raw, "extremized": ext}
    quality_flags = []
    if len(per_model) < need:
        quality_flags.append(f"low_model_coverage:{len(per_model)}/{need}")
    if not have_evidence:
        quality_flags.append("no_retrieved_evidence")
    # CROWD_WEIGHT (0.40) is OOS-validated for the EXACT-match native community prediction. An external
    # fuzzy-matched market anchor (FutureEval, where the native CP is hidden) carries match risk → the
    # caller passes a lower crowd_weight so we lean on it without collapsing onto a possibly-wrong price.
    if crowd_weight is None:
        cw = _adaptive_native_crowd_weight(
            base=CROWD_WEIGHT,
            coverage=coverage,
            have_evidence=have_evidence,
        )
    else:
        cw = max(0.0, min(0.95, crowd_weight))
    applied_calibration = dict(CALIBRATION, model_coverage=round(coverage, 3))
    if crowd is not None:
        final = _sigmoid((1 - cw) * _logit(ext) + cw * _logit(crowd))
        shadows["crowd_only"] = crowd
        shadows["no_crowd"] = ext
        applied_calibration["applied_crowd_weight"] = round(cw, 3)
    elif not have_evidence:
        blind_shrink = _adaptive_blind_shrink(coverage=coverage)
        final = _sigmoid(blind_shrink * _logit(ext))  # blind → pull toward 0.5
        shadows["no_blind_shrink"] = ext
        shadows["blind_shrunk"] = final
        applied_calibration["applied_blind_shrink"] = round(blind_shrink, 3)
    else:
        final = ext

    final = max(0.02, min(0.98, final))
    shadows = {k: round(max(0.0, min(1.0, float(v))), 3) for k, v in shadows.items()}
    reasoning = (f"Ensemble of {len(per_model)} keyless models × {n} samples "
                 f"(raw {raw:.2f} → extremized {ext:.2f}"
                 + (f" → crowd-anchored {final:.2f} [crowd {crowd:.2f}, w={cw:.2f}]"
                    if crowd is not None
                    else f" → {final:.2f}")
                 + f"). {len(sources)} sources retrieved.")
    out = {"prob": round(final, 3), "n_models": len(per_model), "n_samples": len(samples),
           "crowd": crowd, "raw_ensemble": round(raw, 3), "sources": sources,
           "prompt_hash": prompt_hash, "calibration": applied_calibration,
           "quality_flags": quality_flags, "shadows": shadows,
           "reasoning": reasoning}
    if world_state_meta:
        out["world_state"] = world_state_meta
    return out
