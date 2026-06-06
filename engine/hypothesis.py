"""Component 8 — the hypothesis engine. The generative front-end. The oracle, gated.

Everything else in this engine DISPOSES: the detector kills curves that do not accelerate, the
consensus gate kills theses already priced in, Brier kills probabilities that miss. That machinery
is excellent at saying *no* — but it can only ever judge curves we already chose to put in front of
it. Nothing in the repo PROPOSES. Nothing performs the divergent, cross-domain act the whole edge
depends on: *where should we even look?* The retrodiction benchmark passed on FAMOUS cases — and
famous is survivorship; the real rent lives in the constraint nobody has named yet. No detector
finds those. Only wild, associative, inverting, analogy-driven seeing does.

This module is that missing half — but it is soul WIRED TO THE GATE, never soul instead of it. A
hypothesis is generated in-session by Claude through a Bucket-2 lens (Goldratt's Theory of
Constraints, Perez's cycles, Helmer's 7 Powers, Arthur's increasing returns, Ricardian rent — held
as a *lens* that generates, never as truth that asserts; doctrine §0). It is then forced through the
exact discipline every forecast obeys:

  • an OUTSIDE-VIEW reference class + base rate before any inside-view story (doctrine §2.1),
  • a DISCONFIRMER sought FIRST — the strongest case against, written before asserting (§2.6),
  • KILL-CRITERIA + a horizon, or it is a story not a bet (§2.5 / rule 7),
  • a PROJECTIBILITY check — is there a point-in-time series that could test it, or is this just
    mechanism-free momentum dressed as insight? (§0.5).

`gate()` maps those fields to a status, mechanically (the judgment is explicit and stated; only the
bookkeeping is automatic):

  refuted .......... the disconfirmer won → KILLED (we murder our own seductive narratives)
  survives, but no testable series / no kill-criteria / no base rate / no horizon
                     → PARKED (a beautiful thought the cold machine refuses to let become a bet
                       until it is falsifiable — logged, not faked; the anti-astrology valve)
  survives + testable → SURVIVED (clears every bar → eligible to become a ForecastCard)
  (promote) ........ a ForecastCard was written from it → PROMOTED

The seer proposes; the cold machine disposes. $0 — no network, no LLM; the reasoning is Claude's,
in-session, exactly like entity resolution. A $0 'auto' ledger row is still logged so the cost gate
is exercised, not bypassed.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date

from engine.pillars.frontier import _log_cost
from engine.schemas import ForecastOutcome, Hypothesis, _now

# The Bucket-2 lenses (doctrine §3) — frames that GENERATE, never assert. Surfaced for the cockpit.
LENSES = {
    "toc": "Theory of Constraints (Goldratt) — the system's throughput is set by one binding constraint; find where it moves.",
    "perez": "Techno-economic cycles (Perez) — installation vs deployment; where capital floods, the constraint relocates.",
    "helmer": "7 Powers (Helmer) — which layer can actually CAPTURE the rent (moat), not merely create the value.",
    "arthur": "Increasing returns (W. Brian Arthur) — lock-in and network effects concentrate rent on a non-obvious layer.",
    "ricardian": "Ricardian rent — scarcity rent accrues to the least-elastic, least-substitutable input.",
    "inversion": "Inversion — assume the obvious answer is wrong; what would have to be the real constraint?",
    "analogy": "Cross-domain analogy — this buildout rhymes with a past one; where did the rent land THAT time?",
}


# ── base-rate reference classes (doctrine §2.1 — the outside view, made systematic) ──
# A thesis's base_rate must be ANCHORED to how often this CLASS of thing happens, not invented per
# thesis (the inside-view trap). This is the curated store: each class carries a point-in-time outside-
# view rate + where it comes from (the §8 retro / universe corpora, or a stated historical reference),
# so an author cites a class instead of guessing. Held as reference, never as truth — rates are wide.
REFERENCE_CLASSES: dict[str, dict] = {
    "capital_flooded_buildout": {"rate": 0.60, "n": "3 strong priors",
        "why": "Capital-flooded infrastructure buildouts (railroads→land, telecom→spectrum/conduit, "
               "shale→takeaway) — the terminal constraint lands on the slow physical/permission layer "
               "a majority of the time. The AI-power & MoE→memory theses sit here."},
    "wright_law_cost_curve": {"rate": 0.55, "n": "retro winners 4/5",
        "why": "A mechanism-backed cost/affordability curve on a learning (Wright's-law) trajectory — "
               "solar, lithium, genomics, shale all fired and won in the §8 corpus; the durable winner class."},
    "mechanism_free_momentum": {"rate": 0.10, "n": "retro fizzles 5/5",
        "why": "Attention/publication momentum with NO mechanism-backed capability curve — graphene, "
               "metaverse, hydrogen. The §8 DECOY class: almost always a fizzle. Anchor low."},
    "pre_pmf_next_platform_hw": {"rate": 0.20, "n": "historical, low",
        "why": "Pre-product-market-fit 'next platform' hardware (VR, humanoids, AV timelines, QEC "
               "fault-tolerance) — a LOW within-horizon hit rate; 'right but early' dominates (doctrine §2.10)."},
    "ip_defended_consumable": {"rate": 0.55, "n": "case-based",
        "why": "A patent/standard-defended consumable at an inelastic layer (scRNA droplet consumable, "
               "injection closures) — rent persists while the moat holds; resolves on substitute entry."},
    "policy_created_scarcity": {"rate": 0.50, "n": "case-based",
        "why": "Scarcity created/relaxed by decree (export ban, subsidy, re-armament procurement, "
               "nuclear restart) — binds fast but is reversible on the policy turning; coin-flip-ish on horizon."},
}


def base_rate_for(class_key: str) -> float | None:
    """The outside-view rate for a reference class, or None if the class is unknown (don't fake one)."""
    rc = REFERENCE_CLASSES.get(class_key)
    return rc["rate"] if rc else None


# ── the closed loop: MEASURED base rate by kind (the centerpiece) ──────────────
# The hand-assigned REFERENCE_CLASSES above are the anchor we START with; this is the anchor we EARN.
# Every call now carries two class tags — thesis_kind (the SHAPE of the structural call) and
# mispricing_kind (WHY consensus is wrong) — and when a promoted card resolves, its outcome flows
# back onto the hypothesis. `base_rates()` then aggregates win-rate + Brier per kind, so the oracle
# finally measures whether ITS OWN kind of call pays instead of trusting a typed-in prior.
#
# It is non-empty TODAY because the §8 retrodiction corpus is itself a set of big structural shifts
# with known outcomes — tag each by kind and we have a real, immediate base rate. The pattern the
# corpus already shows (and the external reviewer claimed): mechanism-backed cost-curve / constraint-
# migration calls with a layer-blindness mispricing WIN; hype/horizon-gap calls LOSE. Now it's measured.
THESIS_KINDS = ("constraint_migration", "regime_change", "substitution_cascade",
                "cost_curve_breakout", "policy_scarcity")
MISPRICING_KINDS = ("trough_discount", "layer_blindness", "horizon_gap", "hype_overpriced")

# The §8 corpus (engine/retro.py CASES) → (thesis_kind, mispricing_kind, outcome 1=paid/0=fizzled).
# Ground-truth historical structural calls; seeds the measured base rate before any live card resolves.
RETRO_KIND_MAP: dict[str, tuple[str, str, int]] = {
    "ai_compute":        ("constraint_migration", "layer_blindness", 1),
    "genomics":          ("cost_curve_breakout",  "layer_blindness", 1),
    "shale":             ("regime_change",        "layer_blindness", 1),
    "lithium_batteries": ("cost_curve_breakout",  "layer_blindness", 1),
    "solar":             ("cost_curve_breakout",  "layer_blindness", 1),
    "hydrogen":          ("substitution_cascade", "horizon_gap",     0),
    "graphene":          ("substitution_cascade", "hype_overpriced", 0),
    "consumer_3dprint":  ("regime_change",        "hype_overpriced", 0),
    "metaverse":         ("regime_change",        "hype_overpriced", 0),
    "theranos":          ("regime_change",        "hype_overpriced", 0),
}


def base_rates(conn: sqlite3.Connection, *, log=print) -> dict:
    """Measure the hit rate + mean Brier of each KIND of structural call (the closed loop).

    Pure read, no new table. Combines the §8 retro corpus (known outcomes, tagged in RETRO_KIND_MAP →
    non-empty now) with any resolved live ForecastCards that carry a kind tag. Reports per thesis_kind
    and per mispricing_kind. This is the thing no analyst has: not a pick, but a measured base rate of
    which kinds of where-rent-migrates call actually pay — the outside view, earned from our own record.
    """
    # (thesis_kind, mispricing_kind, outcome 0/1, brier|None, source) — one row per resolved call.
    rows: list[tuple[str | None, str | None, int, float | None, str]] = [
        (tk, mk, oc, None, "retro") for tk, mk, oc in RETRO_KIND_MAP.values()
    ]
    for r in conn.execute(
        "SELECT thesis_kind, mispricing_kind, outcome, brier_score FROM forecast_cards "
        "WHERE outcome IS NOT NULL AND superseded_by IS NULL "
        "AND (thesis_kind IS NOT NULL OR mispricing_kind IS NOT NULL)"
    ).fetchall():
        rows.append((r["thesis_kind"], r["mispricing_kind"], 1 if r["outcome"] == "true" else 0,
                     r["brier_score"], "live"))

    def _agg(axis_idx: int) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for row in rows:
            key = row[axis_idx]
            if key is None:
                continue
            a = out.setdefault(key, {"n": 0, "wins": 0, "briers": [], "n_live": 0})
            a["n"] += 1
            a["wins"] += row[2]
            if row[3] is not None:
                a["briers"].append(row[3])
            if row[4] == "live":
                a["n_live"] += 1
        for a in out.values():
            a["rate"] = a["wins"] / a["n"] if a["n"] else None
            a["mean_brier"] = sum(a["briers"]) / len(a["briers"]) if a["briers"] else None
        return out

    by_thesis, by_misprice = _agg(0), _agg(1)
    n_live = sum(1 for r in rows if r[4] == "live")
    log(f"MEASURED BASE RATE BY KIND — {len(rows)} resolved structural calls "
        f"({len(RETRO_KIND_MAP)} §8 corpus + {n_live} live). The outside view, earned not assumed:")
    log("\n  by mispricing_kind (WHY consensus is wrong):")
    for k in sorted(by_misprice, key=lambda x: by_misprice[x]["rate"] or 0, reverse=True):
        a = by_misprice[k]
        bs = f" · Brier {a['mean_brier']:.3f}" if a["mean_brier"] is not None else ""
        log(f"    {k:<18} {a['rate']:.0%} paid  (n={a['n']}, {a['n_live']} live){bs}")
    log("\n  by thesis_kind (the SHAPE of the call):")
    for k in sorted(by_thesis, key=lambda x: by_thesis[x]["rate"] or 0, reverse=True):
        a = by_thesis[k]
        bs = f" · Brier {a['mean_brier']:.3f}" if a["mean_brier"] is not None else ""
        log(f"    {k:<22} {a['rate']:.0%} paid  (n={a['n']}, {a['n_live']} live){bs}")
    log("\n  → harvestable kinds (layer_blindness / cost_curve_breakout) vs the traps "
        "(hype_overpriced / horizon_gap). Live cards re-weight this as they resolve.")
    return {"n_resolved": len(rows), "n_live": n_live,
            "by_thesis_kind": by_thesis, "by_mispricing_kind": by_misprice}


def record_outcome(conn: sqlite3.Connection, forecast_id: str, outcome: ForecastOutcome,
                   brier: float, *, log=print) -> bool:
    """Close the loop: when a promoted card resolves, write its outcome + Brier BACK to the parent
    hypothesis (found via promoted_forecast_id). No-op if the card has no parent hypothesis. This is
    the one wire that turns the oracle from a perpetual idea-generator into a scored predictor."""
    row = conn.execute(
        "SELECT id, title, mispricing_kind FROM hypotheses WHERE promoted_forecast_id=?",
        (forecast_id,)).fetchone()
    if row is None:
        return False
    conn.execute("UPDATE hypotheses SET outcome=?, brier_score=? WHERE id=?",
                 (outcome.value, brier, row["id"]))
    conn.commit()
    log(f"  loop closed: {outcome.value} (Brier {brier:.3f}) → hypothesis {row['id'][:8]} "
        f"[{row['mispricing_kind'] or 'untagged'}] {row['title'][:44]}")
    return True


# ── the gate: structured fields → a status (the discipline, made mechanical) ──


def gate(h: Hypothesis) -> str:
    """Map a hypothesis's disciplinary fields to its status. Pure; the judgment lives in the fields.

    A refuted thesis is killed. A survivor is a *bet* only if it can actually be tested and scored —
    a point-in-time series exists (projectibility, §0.5), it has kill-criteria + a horizon (§2.5),
    and an outside-view base rate (§2.1). A survivor missing any of those is real-but-unfalsifiable:
    parked, logged, never quietly promoted into a forecast it cannot earn. This is the valve that
    keeps the oracle from becoming astrology.
    """
    if h.status == "promoted":
        return "promoted"
    if h.refuted:
        return "killed"
    testable = (
        h.measurable
        and bool([k for k in h.kill_criteria if k.strip()])
        and h.base_rate is not None
        and h.horizon is not None
    )
    return "survived" if testable else "parked"


def _upsert(conn: sqlite3.Connection, h: Hypothesis) -> str:
    """Validate (the disconfirmer gate) + compute status + write. Re-seed replaces by title."""
    h.status = gate(h)
    row = conn.execute("SELECT id, promoted_forecast_id FROM hypotheses WHERE title=?", (h.title,)).fetchone()
    if row:
        # Preserve a prior promotion: never silently un-promote a thesis on re-seed.
        if row["promoted_forecast_id"]:
            h.promoted_forecast_id = row["promoted_forecast_id"]
            h.status = "promoted"
        # outcome/brier_score are deliberately NOT in the SET — they are written by the resolution
        # loop (record_outcome), and a re-seed must never clobber a real resolved outcome.
        conn.execute(
            "UPDATE hypotheses SET lens=?, seed=?, claim=?, inelastic_layer=?, obvious_layer=?, "
            "reference_class=?, base_rate=?, disconfirmer=?, kill_criteria=?, horizon=?, "
            "measurable=?, refuted=?, refutation=?, status=?, promoted_forecast_id=?, "
            "thesis_kind=?, mispricing_kind=?, horizon_years=?, note=? WHERE id=?",
            (h.lens, h.seed, h.claim, h.inelastic_layer, h.obvious_layer, h.reference_class,
             h.base_rate, h.disconfirmer, json.dumps(h.kill_criteria),
             h.horizon.isoformat() if h.horizon else None, int(h.measurable), int(h.refuted),
             h.refutation, h.status, h.promoted_forecast_id,
             h.thesis_kind, h.mispricing_kind, h.horizon_years, h.note, row["id"]),
        )
        return row["id"]
    conn.execute(
        "INSERT INTO hypotheses (id,created_at,title,lens,seed,claim,inelastic_layer,obvious_layer,"
        "reference_class,base_rate,disconfirmer,kill_criteria,horizon,measurable,refuted,refutation,"
        "status,promoted_forecast_id,thesis_kind,mispricing_kind,horizon_years,outcome,brier_score,note) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (h.id, h.created_at.isoformat(), h.title, h.lens, h.seed, h.claim, h.inelastic_layer,
         h.obvious_layer, h.reference_class, h.base_rate, h.disconfirmer,
         json.dumps(h.kill_criteria), h.horizon.isoformat() if h.horizon else None,
         int(h.measurable), int(h.refuted), h.refutation, h.status, h.promoted_forecast_id,
         h.thesis_kind, h.mispricing_kind, h.horizon_years,
         h.outcome.value if h.outcome else None, h.brier_score, h.note),
    )
    return h.id


def add(conn: sqlite3.Connection, **fields) -> Hypothesis:
    """Author a hypothesis in-session and run it through the gate. The generative seam."""
    h = Hypothesis(**fields)
    _upsert(conn, h)
    conn.commit()
    return h


# ── component 9: the independent multi-skeptic panel (§2.6) ──
# A single in-session refutation can fool itself — the same mind that loved the thesis judges it. The
# upgrade is N INDEPENDENT skeptics, each asked only to REFUTE, blind to each other. A majority-refute
# kills the thesis; the votes are recorded for audit. The skeptics themselves are run by Claude
# in-session (real adversarial subagents — the human+AI loop); this records the result and re-gates.


def record_skeptic_panel(conn: sqlite3.Connection, hypothesis_id: str, votes: list[dict],
                         *, log=print) -> dict:
    """Fold an independent skeptic panel onto a hypothesis: majority-refute → `refuted` → re-gate.

    `votes` = [{"skeptic": str, "refuted": bool, "reason": str, "confidence": float}] — each an
    INDEPENDENT pass. A strict majority to refute wins (ties do NOT refute — the thesis gets the
    benefit of the doubt, since the disconfirmer must clearly win, doctrine §2.6). The panel's
    majority verdict replaces the single in-session `refuted`; `status` is then recomputed by gate().
    """
    if not votes:
        raise ValueError("a skeptic panel needs at least one vote")
    row = conn.execute(
        "SELECT id, title, status, refutation FROM hypotheses WHERE id=? OR id LIKE ?",
        (hypothesis_id, hypothesis_id + "%")).fetchone()
    if row is None:
        raise ValueError(f"no hypothesis matching {hypothesis_id}")
    if row["status"] == "promoted":
        raise ValueError(f"hypothesis {row['id'][:8]} is already promoted to a forecast — immutable (rule 7)")

    n = len(votes)
    n_refute = sum(1 for v in votes if v.get("refuted"))
    majority_refuted = n_refute * 2 > n               # strict majority; a tie does NOT refute
    panel_lines = "; ".join(
        f"{v.get('skeptic', 's' + str(i))}: {'REFUTE' if v.get('refuted') else 'stands'} "
        f"({float(v.get('confidence', 0)):.0%}) — {v.get('reason', '').strip()[:90]}"
        for i, v in enumerate(votes))
    verdict = (f"SKEPTIC PANEL ({n_refute}/{n} refute → "
               f"{'KILLED by majority' if majority_refuted else 'SURVIVES the panel'}). {panel_lines}")

    h = _load(conn, row["id"])
    h.refuted = majority_refuted
    h.refutation = verdict
    h.skeptic_panel = json.dumps(votes)
    h.n_skeptics = n
    h.n_refute = n_refute
    h.status = gate(h)
    conn.execute(
        "UPDATE hypotheses SET refuted=?, refutation=?, skeptic_panel=?, n_skeptics=?, n_refute=?, "
        "status=? WHERE id=?",
        (int(h.refuted), h.refutation, h.skeptic_panel, h.n_skeptics, h.n_refute, h.status, row["id"]))
    conn.commit()
    mark = {"killed": "✗ KILLED", "survived": "✓ SURVIVED", "parked": "◦ PARKED"}.get(h.status, h.status)
    log(f"  [{mark}] {row['title'][:60]}  ({n_refute}/{n} refute)")
    return {"hypothesis_id": row["id"], "n_skeptics": n, "n_refute": n_refute,
            "majority_refuted": majority_refuted, "status": h.status}


def _load(conn: sqlite3.Connection, hid: str) -> Hypothesis:
    """Rehydrate a Hypothesis row (so gate() can recompute status from all its fields)."""
    r = conn.execute("SELECT * FROM hypotheses WHERE id=?", (hid,)).fetchone()
    keys = r.keys()
    return Hypothesis(
        id=r["id"], title=r["title"], lens=r["lens"], seed=r["seed"], claim=r["claim"],
        inelastic_layer=r["inelastic_layer"], obvious_layer=r["obvious_layer"],
        reference_class=r["reference_class"], base_rate=r["base_rate"], disconfirmer=r["disconfirmer"],
        kill_criteria=json.loads(r["kill_criteria"] or "[]"),
        horizon=date.fromisoformat(r["horizon"]) if r["horizon"] else None,
        measurable=bool(r["measurable"]), refuted=bool(r["refuted"]), refutation=r["refutation"],
        status=r["status"], promoted_forecast_id=r["promoted_forecast_id"],
        thesis_kind=r["thesis_kind"] if "thesis_kind" in keys else None,
        mispricing_kind=r["mispricing_kind"] if "mispricing_kind" in keys else None,
        horizon_years=r["horizon_years"] if "horizon_years" in keys else None,
        outcome=ForecastOutcome(r["outcome"]) if ("outcome" in keys and r["outcome"]) else None,
        brier_score=r["brier_score"] if "brier_score" in keys else None,
        note=r["note"])


# ── the oracle pass: three in-session hypotheses, demonstrating all three verdicts ──
# This is a real divergent sweep, not filler — and it deliberately produces one of EACH terminal
# state, because the honesty of the engine is the point: it must be able to kill its own pretty
# stories and refuse its own un-testable ones, or "more soul" is just astrology.
#   1. SURVIVED — passes every bar, eligible to become a forecast (needs Pillar-1/3 data to promote).
#   2. PARKED   — a gorgeous idea the gate refuses to let become a bet because nothing can test it yet.
#   3. KILLED   — a seductive clean narrative the in-session skeptic murders on its own disconfirmer.

SEED = [
    Hypothesis(
        title="The AI buildout's rent migrates from the GPU to the electrical interconnect",
        lens="toc",
        seed="Capital can buy GPUs, but it cannot buy a grid-interconnection permit or fast-forward a "
             "3-year-backlogged large-power transformer. Route the rent to what capital can't fast-forward.",
        claim="As compute is flooded with capital (elastic), the binding constraint on AI capacity "
              "moves downstream of the chip to POWER, and downstream of generation to the slowest "
              "physical/administrative layer: grid interconnection + large-power transformers + switchgear.",
        inelastic_layer="Large-power transformer & high-voltage switchgear manufacturing + the "
                        "multi-year grid-interconnection queue (GE Vernova, Hitachi Energy, Siemens Energy).",
        obvious_layer="The GPU / the AI accelerator (NVIDIA) — the layer everyone already prices.",
        reference_class="Capital-flooded infrastructure buildouts: railroads (rent → land/right-of-way), "
                        "telecom fiber (→ spectrum & conduit), shale (→ takeaway pipeline & sand logistics).",
        base_rate=0.6,  # in such buildouts the terminal constraint lands on the slow physical/permission layer a majority of the time
        disconfirmer="SOUGHT FIRST: hyperscalers are already routing AROUND the public-grid queue with "
                     "behind-the-meter co-located generation (gas, planned SMRs, solar+storage). If that "
                     "scales, the interconnection queue is elastic after all and the constraint dissolves. "
                     "Counter: behind-the-meter still needs transformers & switchgear — the constraint "
                     "RELOCATES within the electrical layer, it does not vanish. The thesis survives, narrowed.",
        kill_criteria=[
            "Large-power-transformer lead times FALL (vs the ~2024 ~2-year backlog) by the horizon — supply proved elastic.",
            "Median grid-interconnection queue duration shortens materially (FERC Order 2023 clears the backlog).",
            "Behind-the-meter generation becomes the dominant siting mode AND its own gear is unconstrained — "
            "the public-grid constraint never binds.",
        ],
        horizon=date(2028, 12, 31),
        measurable=True,  # transformer lead times, ISO/RTO queue durations, GE Vernova/Hitachi/Siemens-Energy backlogs are point-in-time series
        refutation="SURVIVES. The disconfirmer (behind-the-meter) is real but partial — it relocates the "
                   "constraint inside the electrical layer rather than removing it. The base rate from three "
                   "prior capital-flooded buildouts favors the slow physical layer. Mechanism-backed and "
                   "falsifiable with public series → eligible.",
        note="The flagship survivor: a genuinely pre-consensus, cross-domain (ToC + rail/telecom analogy) "
             "constraint-migration call. Not yet promoted — promotion waits on collecting the transformer-"
             "lead-time / interconnection-queue series (Pillar 1/3). Eligible, honest about the data gap.",
    ),
    Hypothesis(
        title="The binding constraint on AI agents is verification capacity, not model capability",
        lens="arthur",
        seed="Invert the obvious: as inference trends toward free, the scarce input flips to the one thing "
             "that does NOT scale with compute — trustworthy verification of autonomous output.",
        claim="Rent migrates from frontier model capability (commoditizing fast) to the capacity to "
              "VERIFY and TRUST agent output at scale — evals, audit, the institutional assurance needed "
              "to deploy autonomy where mistakes are expensive.",
        inelastic_layer="High-assurance verification / trust infrastructure (expert-in-the-loop review, "
                        "audit, liability-bearing certification of agent output).",
        obvious_layer="The frontier model / the per-token price — the layer everyone prices.",
        reference_class="Prior automation waves (mixed, weak): did rent land on the automator or the "
                        "assurance/certification layer? No clean, well-populated reference class exists.",
        base_rate=None,  # honestly undefined — the reference class is too thin to anchor a number
        disconfirmer="SOUGHT FIRST: verification may itself be automatable by the SAME models "
                     "(self-consistency, formal methods, model-graded evals). If trust scales with compute "
                     "after all, the 'inelastic' layer is elastic and the thesis is empty. This is not "
                     "clearly refuted — but it is also not clearly true.",
        kill_criteria=[],  # the fatal gap: no crisp, dated, measurable kill-criterion can be written yet
        horizon=None,
        measurable=False,  # §0.5: no point-in-time series exists for 'verification capacity' — mechanism-free momentum risk
        refutation="PARKED, not killed. Genuinely interesting and possibly right — but there is no "
                   "point-in-time series that could test it and no crisp kill-criterion with a date. By "
                   "doctrine §0.5 (projectibility) and §2.5, an un-falsifiable thesis is a story, not a bet. "
                   "The gate REFUSES to promote it. This is the engine working: the cold machine will not let "
                   "a beautiful idea become a forecast until it is measurable. Logged, surfaced, not faked.",
        note="The anti-astrology demonstration. The whole worry about 'more soul' is that it becomes "
             "mysticism; this is the valve that prevents it — soul is allowed to PROPOSE anything, but the "
             "gate parks what it cannot falsify. Revisit if a verification-capacity proxy series appears.",
    ),
    Hypothesis(
        title="Humanoid robots are next; rent migrates to precision actuators / harmonic drives",
        lens="analogy",
        seed="Embodied AI needs bodies; bodies need high-torque precision actuators; harmonic drives are "
             "precision-machined and slow to scale. A clean, compelling story.",
        claim="The next constraint is the humanoid actuator: rent migrates to harmonic-drive / precision "
              "reducer and high-torque-density motor supply as humanoid robots scale.",
        inelastic_layer="Precision strain-wave (harmonic) drives and high-torque-density actuators.",
        obvious_layer="The robot OEM / the foundation 'robot brain' model.",
        reference_class="Pre-product-market-fit 'next platform' hardware calls (VR, wearables, 3D printing, "
                        "autonomous-vehicle timelines) — historically a LOW within-horizon hit rate.",
        base_rate=0.2,  # pre-PMF 'next platform' hardware calls rarely bind within a forecast horizon
        disconfirmer="SOUGHT FIRST: (a) humanoid DEMAND at scale is unproven — no product-market fit, so the "
                     "actuator constraint may not bind for a decade ('right but early', the dominant failure, "
                     "doctrine §2.10); (b) the supposed inelastic layer is actually fairly ELASTIC — harmonic "
                     "drives are a known, scaling industry (Harmonic Drive SE + many new Chinese entrants), not "
                     "a true bottleneck; (c) the story is SEDUCTIVELY clean, which doctrine §2.9 says is evidence "
                     "of nothing and a confidence trap.",
        kill_criteria=[
            "Humanoid unit demand stays below pilot scale through the horizon — the constraint never binds.",
            "Harmonic-drive / actuator capacity expands ahead of demand (it is elastic) — no rent accrues there.",
        ],
        horizon=date(2030, 12, 31),
        measurable=True,
        refuted=True,
        refutation="KILLED. Fails on three independent counts: the demand premise is unproven (timing / "
                   "'right but early', §2.10); the claimed inelastic layer is actually elastic (harmonic "
                   "drives are a scaling, multi-vendor industry); and its persuasiveness is pure narrative "
                   "seduction (§2.9), which raises felt confidence without raising accuracy. The in-session "
                   "skeptic murders the pretty story — by design, before it could become a bet.",
        note="The self-refutation demonstration. The engine must be able to kill its OWN seductive output, "
             "not just outside claims. A clean causal story is evidence of nothing (doctrine §2.9).",
    ),
]


def seed(conn: sqlite3.Connection, *, log=print) -> dict:
    """Run the oracle pass: write the curated hypotheses, gate each, report the verdicts. Idempotent, $0."""
    _log_cost(conn, "hypothesis_generate", "in_session", float(len(SEED)))
    counts = {"survived": 0, "parked": 0, "killed": 0, "promoted": 0}
    for h in SEED:
        _upsert(conn, h)
        counts[h.status] = counts.get(h.status, 0) + 1
        mark = {"survived": "✓ SURVIVED", "parked": "◦ PARKED", "killed": "✗ KILLED",
                "promoted": "★ PROMOTED"}.get(h.status, h.status)
        log(f"  [{mark:<11}] ({h.lens}) {h.title}")
        log(f"               → {h.refutation[:96]}")
    conn.commit()
    log(f"\n  {counts['survived']} survived · {counts['parked']} parked · {counts['killed']} killed "
        f"({len(SEED)} generated) — the seer proposes, the gate disposes.")
    return {"generated": len(SEED), **counts}


def promote(conn: sqlite3.Connection, hypothesis_id: str, *, question: str, probability: float,
            resolution_date: date, ci_low: float | None = None, ci_high: float | None = None,
            ci_unit: str | None = None, seed_series_id: str | None = None,
            pillars_used: list[int] | None = None, source_ids: list[str] | None = None,
            saturation: float | None = None, log=print) -> dict:
    """Graduate a SURVIVED hypothesis into an immutable ForecastCard (rule 7). The wire to the gate.

    Refuses anything not in 'survived' state: a parked (un-falsifiable) or killed thesis cannot become
    a bet. Carries the hypothesis's kill-criteria + rationale onto the card, and stamps the link both
    ways so the forecast's provenance traces back to the divergent thesis that proposed it.
    """
    from engine import forecast

    row = conn.execute(
        "SELECT id, title, status, claim, disconfirmer, kill_criteria, refutation, "
        "thesis_kind, mispricing_kind FROM hypotheses WHERE id=? OR id LIKE ?",
        (hypothesis_id, hypothesis_id + "%")
    ).fetchone()
    if row is None:
        raise ValueError(f"no hypothesis matching {hypothesis_id}")
    if row["status"] != "survived":
        raise ValueError(
            f"hypothesis {row['id'][:8]} is '{row['status']}', not 'survived' — only a survivor that "
            f"clears every gate bar can become a forecast (parked = un-falsifiable, killed = refuted)."
        )
    kills = json.loads(row["kill_criteria"]) or []
    rationale = (f"PROMOTED FROM HYPOTHESIS '{row['title']}'. Thesis: {row['claim']} "
                 f"Disconfirmer (sought first): {row['disconfirmer']} Gate verdict: {row['refutation']}")
    card = forecast.create_card(
        conn, question=question, probability=probability, resolution_date=resolution_date,
        ci_low=ci_low, ci_high=ci_high, ci_unit=ci_unit, seed_series_id=seed_series_id,
        rationale=rationale, kill_criteria=kills, saturation=saturation,
        thesis_kind=row["thesis_kind"], mispricing_kind=row["mispricing_kind"],
        pillars_used=pillars_used or [], source_ids=source_ids or [],
    )
    conn.execute("UPDATE hypotheses SET status='promoted', promoted_forecast_id=? WHERE id=?",
                 (card.id, row["id"]))
    conn.commit()
    log(f"promoted {row['id'][:8]} → ForecastCard {card.id[:8]} (P={card.probability})")
    return {"hypothesis_id": row["id"], "forecast_id": card.id}


def list_hypotheses(conn: sqlite3.Connection, *, log=print) -> None:
    """Text view of the generated hypotheses by verdict (the cockpit is the real view)."""
    rows = conn.execute(
        "SELECT title, lens, status, base_rate, measurable, inelastic_layer, obvious_layer, refutation "
        "FROM hypotheses ORDER BY CASE status WHEN 'promoted' THEN 0 WHEN 'survived' THEN 1 "
        "WHEN 'parked' THEN 2 ELSE 3 END, title"
    ).fetchall()
    if not rows:
        log("no hypotheses yet — run: python -m engine.cli hypothesis-seed")
        return
    for r in rows:
        mark = {"survived": "✓ SURVIVED", "parked": "◦ PARKED ", "killed": "✗ KILLED ",
                "promoted": "★ PROMOTED"}.get(r["status"], r["status"])
        log(f"\n[{mark}] ({r['lens']}) {r['title']}")
        log(f"   rent moves: {r['obvious_layer'][:40]}  →  {r['inelastic_layer'][:60]}")
        log(f"   {r['refutation'][:140]}")
