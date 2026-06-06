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

import json
import re
import sqlite3
from pathlib import Path

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
    """Ask the model for a calibrated P(yes) on a binary question, blind to the outcome. Returns the
    parsed probability in [0,1], or None if it couldn't be parsed."""
    system = ("You are a careful forecaster. Give your honest probability that the statement will be "
              "TRUE, based only on what you know. Reason in one or two sentences, then end with a line "
              "exactly like 'PROBABILITY: 0.NN' (a number between 0 and 1).")
    out = llm.complete(conn, q, provider=provider, model=model, system=system,
                       est_cost_cents=est_cost_cents, max_tokens=256, proxy=proxy)
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
    log(f"   STEP 1 — leakage probe (the validity gate):")
    eff, _probe_rows = effective_cutoff(conn, provider=provider, model=model,
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


# ── EXTERNAL BENCHMARK: the defensible upgrade ────────────────────────────────────────────────────
# The hand-authored HOLDOUT_QUESTIONS above invite two fair critiques: N=7, and "you wrote the
# questions knowing the answers." This path removes both — it scores the model on EXTERNALLY-authored,
# already-resolved binary questions pulled from ForecastBench (Polymarket/Manifold/Metaculus/Infer
# markets), and uses a NON-LEADING recall probe so the leakage gate is honest (the original probe
# STATED the event, which a weak model would just agree with → an inflated cutoff). Same leakage gate,
# same Brier-vs-base-rate scoring. Questions resolve years after the 2021 cutoff (ForecastBench began
# 2024) → leak-free by construction, but also a HARD long-horizon test of a deliberately-dumb model;
# read the number as a leak-free floor, not a ceiling.

QUESTIONS_PATH = Path(__file__).resolve().parent.parent / "experiments" / "holdout_questions.jsonl"

# Non-leading recall probes: open questions whose correct answer requires post-cutoff knowledge AND is
# NOT guessable (so a model cannot luck into "knowing"). The latest year it correctly recalls = its
# effective cutoff (a lower bound). Fixes the leading-question weakness of LEAKAGE_PROBES.
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


def run_external(conn: sqlite3.Connection, *, provider: str = "openrouter", model: str | None = None,
                 est_cost_cents: int = 0, proxy: str | None = None,
                 path: Path = QUESTIONS_PATH, log=print) -> dict:
    """Score the model on EXTERNALLY-authored, already-resolved ForecastBench questions, leakage-gated
    by the non-leading recall probe. The defensible answer to 'N=7 / self-authored'."""
    if not path.is_file():
        log(f"   no question set at {path} — fetch it first (see scripts/build the holdout set).")
        return {"valid": False, "n": 0}
    qs = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    log(f"\n🌐  EXTERNAL HOLDOUT (ForecastBench) — provider={provider} model={model or 'roster'}")
    log(f"   {len(qs)} externally-authored resolved binary questions "
        f"({min(q['resolution_date'] for q in qs)}…{max(q['resolution_date'] for q in qs)})")
    log(f"   STEP 1 — non-leading recall probe (the validity gate):")
    eff = recall_cutoff(conn, provider=provider, model=model, est_cost_cents=est_cost_cents,
                        proxy=proxy, log=log)
    log(f"\n   effective cutoff = {eff if eff is not None else 'pre-2022 (blind to all probes)'}")

    def determined(q: dict) -> int:
        return int(str(q["resolution_date"])[:4])

    leakfree = [q for q in qs if eff is None or eff < determined(q)]
    leaked = [q for q in qs if not (eff is None or eff < determined(q))]
    if leaked:
        log(f"   ⛔ {len(leaked)} excluded (outcome determined ≤ cutoff).")
    if not leakfree:
        log("   ⛔ INVALID — no leak-free questions for this model.")
        return {"valid": False, "effective_cutoff": eff, "n": 0}

    log(f"\n   STEP 2 — blind forecasts on {len(leakfree)} leak-free questions:")
    scored, sq, n_skipped = [], 0.0, 0
    for q in leakfree:
        try:
            p = _ask_probability(conn, q["question"], provider=provider, model=model,
                                 est_cost_cents=est_cost_cents, proxy=proxy)
        except Exception as e:
            n_skipped += 1  # provider content-filter / transient error — skip, don't crash the run
            continue
        if p is None:
            n_skipped += 1
            continue
        o = 1.0 if q["outcome"] else 0.0
        brier = (p - o) ** 2
        sq += brier
        scored.append({"p": p, "outcome": q["outcome"], "brier": brier})
    n = len(scored)
    if not n:
        log("   ⚠️  no parseable probabilities returned.")
        return {"valid": True, "n": 0}
    brier = sq / n
    hits = sum(1 for s in scored if (s["p"] >= 0.5) == bool(s["outcome"]))
    base = sum(1 for s in scored if s["outcome"]) / n
    brier_base = sum((base - (1.0 if s["outcome"] else 0.0)) ** 2 for s in scored) / n
    # the trivial constant-0.5 baseline too, so the skewed-base-rate caveat is explicit
    brier_half = sum((0.5 - (1.0 if s["outcome"] else 0.0)) ** 2 for s in scored) / n
    beat = brier < brier_base
    log(f"\n   N={n} scored ({n_skipped} skipped — provider content-filter/errors) · "
        f"Brier {brier:.3f}  vs  always-base-rate({base:.2f}) {brier_base:.3f}  vs  always-0.5 {brier_half:.3f}")
    log(f"   → {'BEATS the base-rate baseline ✅' if beat else 'does NOT beat base rate ❌'} · "
        f"hit-rate {hits}/{n} = {hits/n*100:.0f}%")
    log("   Externally-authored + leak-gated → immune to the 'self-authored / N=7' critiques. Long "
        "horizon (resolves years past a 2021 cutoff) makes this a hard FLOOR, not the method's ceiling.")
    return {"valid": True, "effective_cutoff": eff, "n": n, "n_skipped": n_skipped, "brier": brier,
            "brier_base": brier_base, "brier_half": brier_half, "hits": hits, "hit_rate": hits / n,
            "base_rate": base}
