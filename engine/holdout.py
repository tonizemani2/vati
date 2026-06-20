"""engine/holdout.py — Stage 3: the older-model temporal holdout (the ONLY honest test of JUDGMENT).

Parametric leakage ([[parametric-leakage]]) means an LLM's *judgment* can never be retro-validated by
replay: the outcomes are already in its weights. The one escape is a model whose training cutoff
PRECEDES the question's resolution. Then the model makes a genuine ex-ante forecast (the outcome is not
in its weights) while WE, today, already know the outcome (it resolved before now) — so we can score it
leakage-free. This module is that test.

THE GATE THAT MAKES IT HONEST — the LEAKAGE PROBE. We never trust a model's *claimed* cutoff. Before
scoring any forecast we probe the model with dated events and measure the latest one it demonstrably
knows = its EFFECTIVE cutoff (a lower bound). The holdout is VALID only if that effective cutoff is
strictly BEFORE the earliest question's resolution. If the model knows any outcome it's about to
"forecast," the run is INVALID and we refuse to report a foresight score (reporting one would be the
exact leakage the whole project exists to avoid — GIGO, rule 1).

MODEL REQUIREMENT (the hard constraint). This needs a genuinely OLD model — GPT-3.5-turbo-0613
(cutoff ~2021-09) or Llama-2 (~2022-09), reachable via OpenRouter. The keyless DeepInfra roster and the
keyed MiniMax model are all RECENT (2025 cutoffs) → they will FAIL the leakage probe on these questions,
and the gate will (correctly) refuse to score them. That refusal is the honest finding until an
old-cutoff model is wired (set OPENROUTER_API_KEY; pass --provider openrouter --model openai/gpt-3.5-turbo-0613).

Cost: every model call goes through engine.cost.gate FIRST (rule 3). Keyless = $0/auto; keyed routes
log est_cost and block above the threshold until approved.
"""

from __future__ import annotations

import re
import sqlite3

from engine.adapters import llm

# ── the leakage probe: dated events; the model's effective cutoff = latest it provably knows ──────────
# Each probe is an objective, well-known dated event. We ask the model whether it knows the event
# happened (and when). The LATEST year it correctly affirms is its effective-cutoff lower bound.
LEAKAGE_PROBES: list[dict] = [
    {"event": "OpenAI publicly released ChatGPT to the general public", "year": 2022},
    {"event": "OpenAI released GPT-4", "year": 2023},
    {"event": "Silicon Valley Bank collapsed and was taken over by the FDIC", "year": 2023},
    {"event": "China imposed export controls on gallium and germanium", "year": 2023},
    {"event": "the winner of the 2024 United States presidential election was decided", "year": 2024},
    {"event": "DeepSeek released its R1 reasoning model", "year": 2025},
]

# ── the holdout questions: binary, objective, KNOWN outcome, constraint-migration flavored, resolving
# 2023–2024 (so any model with a < 2023 cutoff is leakage-free). outcome = the realized truth WE know
# today; rationale = the checkable fact. A balanced set (real migrations + hyped non-events). ───────────
# `determined` = the year the outcome became KNOWABLE (a positive event's date; a non-event's deadline).
# A question is leak-free for a model only if the model's effective cutoff is strictly BEFORE
# `determined` — else the outcome may already be in its weights. (Year granularity; conservative.)
HOLDOUT_QUESTIONS: list[dict] = [
    {"id": "xfmr_price", "resolves": 2024, "determined": 2024, "outcome": True,
     "q": "By end-2024, will US producer prices for large-power transformers be at least 50% higher "
          "than their 2020 level?",
     "rationale": "BLS PPI for power/distribution transformers rose ~255 (2020) → ~430 (2024), +~70%."},
    {"id": "gpu_leadtime", "resolves": 2024, "determined": 2024, "outcome": True,
     "q": "By end-2024, will high-end AI accelerator (e.g. NVIDIA H100-class) demand outstrip supply "
          "enough to create multi-month lead times?",
     "rationale": "H100 lead times ran 6–12+ months through 2023–2024; data-center GPU shortage widely documented."},
    {"id": "glp1_shortage", "resolves": 2024, "determined": 2024, "outcome": True,
     "q": "By end-2024, will GLP-1 drugs (semaglutide/tirzepatide) be in sustained FDA-listed shortage "
          "driven by demand?",
     "rationale": "Semaglutide & tirzepatide were on the FDA drug-shortage list through 2023–2024."},
    {"id": "graphite_control", "resolves": 2024, "determined": 2023, "outcome": True,
     "q": "By end-2024, will China have imposed export controls/licensing on natural graphite?",
     "rationale": "China announced graphite export permitting effective Dec 2023 → determined in 2023."},
    {"id": "ssb_mass", "resolves": 2024, "determined": 2024, "outcome": False,
     "q": "By end-2024, will solid-state EV batteries reach mass-market commercial deployment in "
          "volume passenger vehicles?",
     "rationale": "Still pre-commercial at end-2024; only pilot/sample lines, no mass-market SSB EVs."},
    {"id": "fusion_grid", "resolves": 2024, "determined": 2024, "outcome": False,
     "q": "By end-2024, will any nuclear-fusion plant deliver sustained net-energy power to an "
          "electricity grid?",
     "rationale": "No grid-connected net-energy fusion by end-2024 (NIF was a lab ignition shot, not grid power)."},
    {"id": "green_h2_parity", "resolves": 2024, "determined": 2024, "outcome": False,
     "q": "By end-2024, will green hydrogen reach unsubsidized cost parity with grey hydrogen at scale?",
     "rationale": "Green H2 remained materially more expensive than grey at end-2024."},
    {"id": "quantum_rsa", "resolves": 2024, "determined": 2024, "outcome": False,
     "q": "By end-2024, will a quantum computer have factored an RSA-2048 key?",
     "rationale": "No quantum machine has broken RSA-2048 (far from the required scale)."},
]

_PROB_RE = re.compile(r"PROBABILITY\s*[:=]\s*([01](?:\.\d+)?|0?\.\d+)", re.I)
_YEAR_RE = re.compile(r"\b(20\d{2})\b")


def _ask_probability(conn: sqlite3.Connection, q: str, *, provider: str, model: str | None,
                     est_cost_cents: int, proxy: str | None) -> float | None:
    """Run THE FRAMEWORK (the 6-step superforecaster method, VATI §20b) to get a calibrated P(yes),
    blind to the outcome. This is the real instrument — structural decomposition + outside-view base
    rate + inside-view binding-constraint adjustment + deliberate consensus divergence — NOT a one-line
    'give me a probability' prompt. Returns the parsed probability in [0,1], or None if unparseable."""
    system = (
        "You are an elite calibrated forecaster. Work the SUPERFORECASTER METHOD explicitly and "
        "concisely, in this order:\n"
        "1. DECOMPOSE the question into its key causal drivers.\n"
        "2. OUTSIDE VIEW — state the base rate for this reference class FIRST, before any specifics.\n"
        "3. INSIDE VIEW — adjust for the binding physical constraint: the slowest-moving stock that "
        "gates the outcome (lead times, capacity build-out, supply elasticity, depletion). Value and "
        "scarcity migrate to whatever saturates first and can't be substituted.\n"
        "4. CONSENSUS — state what the consensus expects, then where the STRUCTURAL evidence justifies "
        "diverging from it (the only part that carries information).\n"
        "5. Combine into ONE calibrated probability. Avoid 0 and 1; do not anchor on 0.5; be decisive "
        "where the structure is clear.\n"
        "End with a line EXACTLY like 'PROBABILITY: 0.NN' (a number between 0 and 1).")
    out = llm.complete(conn, q, provider=provider, model=model, system=system,
                       est_cost_cents=est_cost_cents, max_tokens=700, proxy=proxy)
    m = _PROB_RE.search(out or "")
    if not m:
        return None
    try:
        p = float(m.group(1))
    except ValueError:
        return None
    return min(1.0, max(0.0, p))


def _ask_probe(conn: sqlite3.Connection, event: str, *, provider: str, model: str | None,
               est_cost_cents: int, proxy: str | None) -> int | None:
    """Ask whether the model knows a dated event occurred. Returns the year it affirms (leakage
    evidence), or None if it disclaims knowledge / can't be parsed."""
    system = ("Answer ONLY from your training knowledge. If you KNOW the event occurred and roughly "
              "when, reply 'KNOWN <year>'. If you have no knowledge that it occurred, reply 'UNKNOWN'. "
              "Do not guess.")
    prompt = f"Event: {event}. Has this occurred, according to your training knowledge?"
    out = llm.complete(conn, prompt, provider=provider, model=model, system=system,
                       est_cost_cents=est_cost_cents, max_tokens=64, proxy=proxy)
    if not out or "UNKNOWN" in out.upper() and "KNOWN" not in out.upper().replace("UNKNOWN", ""):
        return None
    if "KNOWN" not in out.upper():
        return None
    m = _YEAR_RE.search(out)
    return int(m.group(1)) if m else None


def effective_cutoff(conn: sqlite3.Connection, *, provider: str, model: str | None,
                     est_cost_cents: int, proxy: str | None, log=print) -> tuple[int | None, list]:
    """Probe the model with dated events; return (effective_cutoff_year, probe_rows). The effective
    cutoff is the LATEST event-year the model demonstrably knows — a lower bound on its true cutoff."""
    rows = []
    known_years = []
    for pr in LEAKAGE_PROBES:
        yr = _ask_probe(conn, pr["event"], provider=provider, model=model,
                        est_cost_cents=est_cost_cents, proxy=proxy)
        knows = yr is not None and yr >= pr["year"] - 1   # affirmed at/near the true year = knows it
        if knows:
            known_years.append(pr["year"])
        rows.append({"event": pr["event"], "true_year": pr["year"], "model_year": yr, "knows": knows})
        log(f"   probe {pr['year']}  {'KNOWS' if knows else 'blind'}  · {pr['event'][:54]}")
    return (max(known_years) if known_years else None), rows


def run(conn: sqlite3.Connection, *, provider: str = "deepinfra_keyless", model: str | None = None,
        est_cost_cents: int = 0, proxy: str | None = None, log=print) -> dict:
    """Run the older-model temporal holdout: probe leakage, gate on it, then (only if leak-free) score
    the model's blind forecasts against the known outcomes. cost: $0 keyless; keyed routes cost-gated."""
    log(f"\n🕰️  OLDER-MODEL TEMPORAL HOLDOUT (Stage 3) — provider={provider} model={model or 'roster'}")
    log(f"   {len(HOLDOUT_QUESTIONS)} binary questions, determined "
        f"{min(q['determined'] for q in HOLDOUT_QUESTIONS)}–{max(q['determined'] for q in HOLDOUT_QUESTIONS)} "
        f"(outcomes known to us today)")
    rigorous = provider != "deepinfra_keyless" and bool(model)
    if not rigorous:
        log("   ⚠️  INDICATIVE ONLY — a rigorous run needs ONE PINNED old-cutoff model. The keyless route "
            "ROTATES its roster (the probe model may differ from the scoring model) and/or has a fuzzy/"
            "recent cutoff. Treat any score below as a harness smoke-test, not a validated result.")
    log(f"   STEP 1 — leakage probe (the validity gate, non-leading recall):")
    eff = recall_cutoff(conn, provider=provider, model=model,
                        est_cost_cents=est_cost_cents, proxy=proxy, log=log)

    # PER-QUESTION GATE: a question is scorable only if the model's effective cutoff is strictly BEFORE
    # the year its outcome was determined. eff=None (model blind to all probes) → everything leak-free.
    leakfree = [q for q in HOLDOUT_QUESTIONS if eff is None or eff < q["determined"]]
    leaked = [q for q in HOLDOUT_QUESTIONS if not (eff is None or eff < q["determined"])]
    log(f"\n   effective cutoff = {eff if eff is not None else 'pre-2022 (blind to all probes)'}")
    if leaked:
        log(f"   ⛔ {len(leaked)} question(s) EXCLUDED — outcome determined ≤ cutoff (leakage): "
            f"{', '.join(q['id'] for q in leaked)}")
    if not leakfree:
        log(f"\n   ⛔ INVALID — every question's outcome is in the model's knowledge. No foresight score.")
        log(f"   Honest blocker: no leak-free old model is reachable on current credentials (keyless "
            f"roster + MiniMax are ~2025-cutoff). To run a VALID holdout, wire an old-cutoff model:")
        log(f"     set OPENROUTER_API_KEY in .env, then: holdout-run --provider openrouter "
            f"--model openai/gpt-3.5-turbo-0613 --est-cost-cents <budget>")
        return {"valid": False, "effective_cutoff": eff, "n_leaked": len(leaked), "n_leakfree": 0}

    log(f"\n   STEP 2 — blind forecasts on {len(leakfree)} leak-free question(s) vs known outcomes:")
    scored, sq = [], 0.0
    for q in leakfree:
        p = _ask_probability(conn, q["q"], provider=provider, model=model,
                             est_cost_cents=est_cost_cents, proxy=proxy)
        if p is None:
            log(f"   · {q['id']:<16} (no parseable probability — skipped)")
            continue
        o = 1.0 if q["outcome"] else 0.0
        brier = (p - o) ** 2
        sq += brier
        scored.append({"id": q["id"], "p": p, "outcome": q["outcome"], "brier": brier})
        hit = "✅" if (p >= 0.5) == q["outcome"] else "· "
        log(f"   {hit} {q['id']:<16} P(yes)={p:.2f}  outcome={'TRUE' if q['outcome'] else 'FALSE':<5}  brier={brier:.3f}")

    n = len(scored)
    if not n:
        log("\n   ⚠️  no questions scored (model returned no parseable probabilities).")
        return {"valid": True, "n": 0}
    brier = sq / n
    hits = sum(1 for s in scored if (s["p"] >= 0.5) == bool(s["outcome"]))
    lf_pos = sum(1 for q in leakfree if q["outcome"])
    base_rate = lf_pos / len(leakfree)
    brier_base = sum((base_rate - (1.0 if q["outcome"] else 0.0)) ** 2 for q in leakfree) / len(leakfree)
    tag = "" if rigorous else "  [INDICATIVE — unpinned/rotating model, not a validated result]"
    log(f"\n   N={n} leak-free forecasts · Brier {brier:.3f} vs always-base-rate {brier_base:.3f} "
        f"({'beats baseline ✅' if brier < brier_base else 'no better than base ❌'}) · hit-rate {hits}/{n} = {hits/n*100:.0f}%{tag}")
    log("   A leakage-bounded estimate of JUDGMENT quality — the only retro number the parametric-leakage")
    log("   wall permits. Forward forecasting (the ladder) remains the primary, fully-clean clock.")
    return {"valid": True, "effective_cutoff": eff, "n": n, "brier": brier, "brier_base": brier_base,
            "hits": hits, "hit_rate": hits / n, "rigorous": rigorous, "n_leaked": len(leaked)}


# ── the cutoff probe (the validity gate) ──────────────────────────────────────────────────────────
# Non-leading recall probes: open questions whose correct answer requires post-cutoff knowledge AND is
# NOT guessable (so a model cannot luck into "knowing"). The latest year it correctly recalls = its
# effective cutoff (a lower bound). Non-leading beats the old STATED-event probe (which a weak model
# would just agree with → an inflated cutoff), so `run` uses this as the gate.
RECALL_PROBES: list[dict] = [
    {"q": "What is the name of the AI chatbot OpenAI launched to the public in late 2022?",
     "year": 2022, "keys": ["chatgpt"]},
    {"q": "What is the name of the language model OpenAI released in March 2023, the successor to GPT-3.5?",
     "year": 2023, "keys": ["gpt-4", "gpt 4", "gpt4"]},
    {"q": "Which US bank, a major lender to technology startups, collapsed and was taken over by the "
          "FDIC in March 2023?", "year": 2023, "keys": ["silicon valley", "svb"]},
    {"q": "What is the name of OpenAI's text-to-video generation model unveiled in 2024?",
     "year": 2024, "keys": ["sora"]},
    {"q": "Which Chinese AI startup released the 'R1' reasoning model in early 2025?",
     "year": 2025, "keys": ["deepseek"]},
]


def _ask_recall(conn: sqlite3.Connection, q: str, *, provider: str, model: str | None,
                est_cost_cents: int, proxy: str | None) -> str:
    """Open recall question; the model answers from memory or says it doesn't know. Returns lower-cased
    text (we check for the non-guessable answer keyword)."""
    system = ("Answer the question in a few words, from your training knowledge only. If you do not "
              "know, reply exactly \"I don't know\". Do not guess.")
    out = llm.complete(conn, q, provider=provider, model=model, system=system,
                       est_cost_cents=est_cost_cents, max_tokens=40, proxy=proxy)
    return (out or "").lower()


def recall_cutoff(conn: sqlite3.Connection, *, provider: str, model: str | None,
                  est_cost_cents: int, proxy: str | None, log=print) -> int | None:
    """Non-leading effective cutoff: the latest year whose non-guessable fact the model correctly
    recalls. None = blind to all probes (cutoff before the earliest probe year)."""
    known = []
    for pr in RECALL_PROBES:
        try:
            ans = _ask_recall(conn, pr["q"], provider=provider, model=model,
                              est_cost_cents=est_cost_cents, proxy=proxy)
        except Exception:
            ans = ""  # a filtered/errored probe → treat as blind (conservative: never over-claims cutoff)
        hit = any(k in ans for k in pr["keys"])
        if hit:
            known.append(pr["year"])
        log(f"   recall {pr['year']}  {'KNOWS' if hit else 'blind'}  · {pr['q'][:52]}")
    return max(known) if known else None


# ── STRUCTURAL BENCH: mechanically-built, externally-grounded Class-1 questions ──────────────────────
# Kills the "self-authored / N-too-small" critique. Each question is a MECHANICAL function of a public,
# dated series the engine already collected (FRED PPIs, China/world trade values, demographics, energy,
# compute) under a FIXED rule + threshold — not a hand-written narrative. Outcome is the realized value
# in the DB; leak-free because the horizon value is determined AFTER the model's MEASURED cutoff.
# Rule: "as of end-CUTOFF, will <series> be ≥ (1+threshold)× its end-CUTOFF level by end-HORIZON?"
# Pre-registered in experiments/protocol_structbench.yaml (commit = the seal).
STRUCT_PROVIDERS = ("fred", "comtrade_china", "un_comtrade", "owid", "world_bank", "epoch_ai")


def build_structural_questions(conn: sqlite3.Connection, *, cutoff_year: str = "2023",
                               horizons: tuple[str, ...] = ("2024", "2025"), threshold: float = 0.05,
                               providers: tuple[str, ...] = STRUCT_PROVIDERS) -> list[dict]:
    """Mechanically derive binary questions from the engine's public dated series. One question per
    (series, horizon) where both an end-cutoff and an end-horizon observation exist. No hand-picking."""
    cur = conn.cursor()
    placeholders = ",".join("?" * len(providers))
    rows = cur.execute(
        f"SELECT id, label, unit, provider FROM series WHERE provider IN ({placeholders})",
        providers).fetchall()
    qs: list[dict] = []
    for sid, label, unit, provider in rows:
        by_year: dict[str, float] = {}
        for as_of, val in cur.execute(
                "SELECT as_of, value FROM observations WHERE series_id=? ORDER BY as_of", (sid,)):
            by_year[as_of[:4]] = val  # last obs in each year (Dec) wins
        v0 = by_year.get(cutoff_year)
        if v0 is None or v0 <= 0:
            continue
        for h in horizons:
            vh = by_year.get(h)
            if vh is None:
                continue
            outcome = bool(vh >= v0 * (1.0 + threshold))
            qs.append({
                "id": f"{provider}:{label[:28]}:{h}",
                "determined": int(h),
                "outcome": outcome,
                "q": (f"As of end-{cutoff_year}, will the metric \"{label}\" ({unit}) be at least "
                      f"{threshold:.0%} ABOVE its end-{cutoff_year} level by end-{h}? "
                      f"(At end-{cutoff_year} it was {v0:.4g} {unit}.)"),
                "rationale": (f"{label}: {v0:.4g} (end-{cutoff_year}) → {vh:.4g} (end-{h}); "
                              f"{'rose' if outcome else 'did NOT rise'} ≥ {threshold:.0%}."),
            })
    return sorted(qs, key=lambda q: q["id"])


def run_structural(conn: sqlite3.Connection, *, provider: str = "openrouter", model: str | None = None,
                   est_cost_cents: int = 0, proxy: str | None = None, cutoff_year: str = "2023",
                   threshold: float = 0.05, log=print) -> dict:
    """Run THE FRAMEWORK on mechanically-built, externally-grounded structural questions, leak-gated.
    The defensible retro number: immune to 'self-authored / N=7'. cost-gated (rule 3)."""
    questions = build_structural_questions(conn, cutoff_year=cutoff_year, threshold=threshold)
    log(f"\n📈  STRUCTURAL BENCH (the framework on public structural series) — provider={provider} "
        f"model={model or 'roster'}")
    log(f"   {len(questions)} mechanically-built questions · rule: ≥ +{threshold:.0%} vs end-{cutoff_year}"
        f" · outcomes resolved from realized DB values")
    if not questions:
        log("   no eligible series (need an end-cutoff AND a horizon observation).")
        return {"valid": False, "n": 0}
    log(f"   STEP 1 — non-leading recall probe (the validity gate):")
    eff = recall_cutoff(conn, provider=provider, model=model, est_cost_cents=est_cost_cents,
                        proxy=proxy, log=log)
    log(f"\n   effective cutoff = {eff if eff is not None else 'pre-2022 (blind to all probes)'}")
    leakfree = [q for q in questions if eff is None or eff < q["determined"]]
    leaked = [q for q in questions if not (eff is None or eff < q["determined"])]
    if leaked:
        log(f"   ⛔ {len(leaked)} excluded — outcome determined ≤ cutoff (leakage).")
    if not leakfree:
        log("   ⛔ INVALID — no leak-free questions for this model.")
        return {"valid": False, "effective_cutoff": eff, "n": 0}
    log(f"\n   STEP 2 — framework forecasts on {len(leakfree)} leak-free questions:")
    scored, sq, n_skip = [], 0.0, 0
    for q in leakfree:
        try:
            p = _ask_probability(conn, q["q"], provider=provider, model=model,
                                 est_cost_cents=est_cost_cents, proxy=proxy)
        except Exception:
            n_skip += 1
            continue
        if p is None:
            n_skip += 1
            continue
        o = 1.0 if q["outcome"] else 0.0
        brier = (p - o) ** 2
        sq += brier
        scored.append({"id": q["id"], "p": p, "outcome": q["outcome"], "brier": brier})
        hit = "✅" if (p >= 0.5) == q["outcome"] else "· "
        log(f"   {hit} {q['id'][:36]:<36} P={p:.2f} outcome={'YES' if q['outcome'] else 'NO ':<3} brier={brier:.3f}")
    n = len(scored)
    if not n:
        log("   ⚠️  no parseable probabilities returned.")
        return {"valid": True, "n": 0}
    brier = sq / n
    hits = sum(1 for s in scored if (s["p"] >= 0.5) == bool(s["outcome"]))
    base = sum(1 for s in scored if s["outcome"]) / n
    brier_base = sum((base - (1.0 if s["outcome"] else 0.0)) ** 2 for s in scored) / n
    brier_half = sum((0.5 - (1.0 if s["outcome"] else 0.0)) ** 2 for s in scored) / n
    beat = brier < brier_base
    log(f"\n   N={n} ({n_skip} skipped) · Brier {brier:.3f}  vs  base-rate({base:.2f}) {brier_base:.3f}"
        f"  vs  always-0.5 {brier_half:.3f}")
    log(f"   → {'BEATS the base-rate baseline ✅' if beat else 'does NOT beat base rate ❌'} · "
        f"hit-rate {hits}/{n} = {hits/n*100:.0f}%")
    log("   Mechanically built from public dated series + leak-gated → immune to 'self-authored / N=7'. "
        "An OLD brain here is a leak-free FLOOR; Claude (validated forward) should beat it.")
    return {"valid": True, "effective_cutoff": eff, "n": n, "brier": brier, "brier_base": brier_base,
            "brier_half": brier_half, "hits": hits, "hit_rate": hits / n, "base_rate": base}
