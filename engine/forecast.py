"""Components 10 + 11 — the forecast registry and its calibration.

A forecast here is never "X booms." It is a point-in-time, falsifiable bet on where a
*constraint* migrates, output as a distribution: a binary probability **plus** the 80%
credible interval on the decomposed quantity (plan.md — a bare point is a story, not a bet).

The pipeline, end to end:
  1. A detector hit (a `series` that surprised past k·σ) is the seed.
  2. We Fermi-decompose the question, put a distribution on each factor, and Monte-Carlo it
     (`mc_quantity` — stdlib `random`, $0). The probability and the interval *fall out* of the
     samples; we never hand-type a number (doctrine §2.2/§2.12, execution §3).
  3. The card is written immutable. You never edit one — you `supersede` it (rule 7).
  4. At resolution we score it: Brier = (p − outcome)², against a naive 0.5 base-rate baseline.

Pure-ish: the only I/O is SQLite. No network, no LLM — the reasoning is Claude's, in-session.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from engine.schemas import BeliefEdge, ForecastCard, ForecastOutcome, _now

# The naive baseline every forecast must beat to earn its keep: max-entropy on a binary.
BASELINE_P = 0.5
MC_N = 300_000


# --- the Monte-Carlo Fermi engine --------------------------------------------


@dataclass
class Quantity:
    """The distribution of a forecast's central quantity, summarized."""

    samples: list[float]
    median: float
    ci_low: float       # 10th percentile (80% credible interval)
    ci_high: float      # 90th percentile

    def prob_at_least(self, threshold: float) -> float:
        return sum(1 for v in self.samples if v >= threshold) / len(self.samples)

    def prob_beyond(self, threshold: float, direction: str = ">=") -> float:
        """P(value `direction` threshold) read off the SAME samples the CI comes from."""
        if direction == "<=":
            return sum(1 for v in self.samples if v <= threshold) / len(self.samples)
        return self.prob_at_least(threshold)


# --- one-posterior consistency: derive P and CI from a single sample array ----
# The fix for the calibration bug (a card's P from one model, its CI from another, stapled at
# write-time). A compact quantile grid summarizes a posterior cheaply (no storing 300k samples per
# rung); `tilt_to_probability` shifts that posterior's LOCATION so its P(beyond threshold) equals a
# target probability (e.g. a discrimination model's output), then reads the CI off the SAME shifted
# posterior — so P and the CI can never disagree, while the distribution's WIDTH (honest tails) is
# untouched. Location-only is the right move: "the model says it reverts" should lower the whole
# distribution, not just a scalar P.


def quantile_grid(samples_sorted: list[float], n: int = 1001) -> list[float]:
    """Compact CDF summary: n evenly-spaced order statistics of an already-sorted sample array."""
    m = len(samples_sorted)
    if m == 0:
        return []
    return [samples_sorted[min(m - 1, (i * m) // (n - 1) if i < n - 1 else m - 1)] for i in range(n)]


def _grid_quantile(grid: list[float], p: float) -> float:
    """Read the p-quantile (0..1) off a quantile grid."""
    n = len(grid)
    return grid[min(n - 1, max(0, round(p * (n - 1))))]


def tilt_to_probability(
    grid: list[float], ci_low: float, ci_high: float, threshold: float,
    target_p: float, direction: str = ">=",
) -> tuple[float, float, float]:
    """Shift a posterior (quantile grid + its 10th/90th pctiles) so P(value `direction` threshold)
    == target_p. Returns (probability, new_ci_low, new_ci_high), all from the one shifted array.

    A uniform shift δ moves every percentile by δ, so the CI shifts with the probability and the two
    stay coherent. For '>=' we want frac(samples+δ ≥ threshold)=target_p ⇒ δ = threshold − Q(1−p);
    for '<=' ⇒ δ = threshold − Q(p)."""
    q = (1.0 - target_p) if direction == ">=" else target_p
    delta = threshold - _grid_quantile(grid, q)
    return target_p, ci_low + delta, ci_high + delta


def mc_quantity(
    base_val: float,
    horizon_years: int,
    *,
    g_mean: float,
    g_sd: float,
    decel: float = 0.0,
    seed: int,
    n: int = MC_N,
) -> Quantity:
    """Project a compounding count `horizon_years` ahead under uncertain annual growth.

    Each simulation draws a growth factor per year from Normal(g_mean − decel·year, g_sd)
    (so a maturing field can be modelled as a year-on-year *deceleration*), multiplies them,
    then adds Poisson-style √n count noise. `seed` fixes it so a card reproduces exactly.
    """
    rng = random.Random(seed)
    out: list[float] = []
    for _ in range(n):
        v = base_val
        for h in range(horizon_years):
            g = max(rng.gauss(g_mean - decel * h, g_sd), 0.85)
            v *= g
        v = rng.gauss(v, v ** 0.5)
        out.append(v)
    out.sort()
    pct = lambda p: out[int(p * len(out))]
    return Quantity(samples=out, median=pct(0.5), ci_low=pct(0.10), ci_high=pct(0.90))


# --- the immutable write path -------------------------------------------------


def _insert(conn: sqlite3.Connection, card: ForecastCard) -> str:
    conn.execute(
        "INSERT INTO forecast_cards "
        "(id, question, created_at, resolution_date, probability, ci_low, ci_high, ci_unit, "
        " threshold, threshold_dir, securitizable, saturation, thesis_kind, mispricing_kind, "
        " scenario_id, parent_card_id, "
        " premise_void, rationale, seed_series_id, pillars_used, source_ids, kill_criteria, "
        " superseded_by, outcome, resolved_at, brier_score) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            card.id, card.question, card.created_at.isoformat(),
            card.resolution_date.isoformat(), card.probability,
            card.ci_low, card.ci_high, card.ci_unit, card.threshold, card.threshold_dir,
            None if card.securitizable is None else int(card.securitizable), card.saturation,
            card.thesis_kind, card.mispricing_kind,
            card.scenario_id, card.parent_card_id,
            json.dumps(card.premise_void), card.rationale, card.seed_series_id,
            json.dumps(card.pillars_used), json.dumps(card.source_ids),
            json.dumps(card.kill_criteria), card.superseded_by,
            card.outcome.value if card.outcome else None,
            card.resolved_at.isoformat() if card.resolved_at else None,
            card.brier_score,
        ),
    )
    conn.commit()
    return card.id


def _assert_seed_qc(conn: sqlite3.Connection, seed_series_id: str | None) -> None:
    """QC gate (A5): a forecast cannot be seeded by a series that failed data-audit — stale or
    incomplete data must not reach a bet. Unaudited is allowed (warns at detect time); only a
    recorded 'fail' is refused."""
    if not seed_series_id:
        return
    row = conn.execute(
        "SELECT status, detail FROM series_health WHERE series_id=?", (seed_series_id,)
    ).fetchone()
    if row and row["status"] == "fail":
        raise ValueError(
            f"forecast refused: seed series {seed_series_id} failed data-audit ({row['detail']}). "
            f"Fix/refresh the data and re-run `data-audit`, or pick a healthy seed (QC gate, A5)."
        )


# Altitude guard (the structural-foresight reframe, made enforceable). The schema already gives a
# `securitizable` side-tag so the instrument is a footnote, never the headline — but nothing stopped a
# headline question from BEING a single company's P&L. The 2026-06-06 forward batch regressed exactly
# this way (6/12 calls were "<Company> (TICKER) revenue > $X"), trading the hard-won physical-primary
# altitude for the easiest-to-resolve number. This refuses it at authoring: a forecast scores a PHYSICAL
# constraint metric (lead-time, capacity, price, share), not an equity's revenue/EPS/price. The instrument
# goes in `securitizable`/rationale. Escape hatch `allow_instrument_headline=True` only when the traded
# instrument genuinely IS the constraint metric (rare).
_TICKER_RE = re.compile(r"\([A-Z]{2,5}\)")
_PNL_RE = re.compile(
    r"\b(revenue|revenues|EPS|earnings per share|net income|gross margin|share price|stock price|market cap)\b",
    re.IGNORECASE,
)


def _assert_altitude(question: str) -> None:
    if _TICKER_RE.search(question) and _PNL_RE.search(question):
        raise ValueError(
            "altitude: a forecast's headline question must score a PHYSICAL constraint metric "
            "(lead-time, capacity, price, share), not a single company's P&L — found a (TICKER)+"
            "financials in the question. Put the instrument in `securitizable`/rationale and ask the "
            "physical question. Pass allow_instrument_headline=True only if the traded instrument truly "
            "IS the constraint metric (physical-primary, financial-optional — the structural-foresight reframe)."
        )


def create_card(conn: sqlite3.Connection, **fields) -> ForecastCard:
    """Validate (GIGO + rule-7 kill-criteria + QC seed gate + altitude gate) and write a new immutable card."""
    if not fields.pop("allow_instrument_headline", False):
        _assert_altitude(fields.get("question", ""))
    _assert_seed_qc(conn, fields.get("seed_series_id"))
    card = ForecastCard(**fields)
    _insert(conn, card)
    return card


def supersede(conn: sqlite3.Connection, old_id: str, **fields) -> ForecastCard:
    """Replace a card with a new one — never edit the old (rule 7).

    The old card is retained verbatim for the track record; we only stamp its `superseded_by`
    pointer. The new card is the live one.
    """
    row = conn.execute("SELECT id, superseded_by FROM forecast_cards WHERE id=?", (old_id,)).fetchone()
    if row is None:
        raise ValueError(f"no forecast card {old_id}")
    if row["superseded_by"]:
        raise ValueError(f"card {old_id} is already superseded by {row['superseded_by']}")
    new = create_card(conn, **fields)
    conn.execute("UPDATE forecast_cards SET superseded_by=? WHERE id=?", (new.id, old_id))
    conn.commit()
    return new


# --- the forecast WEB: scenario trees of linked, conditional outcomes ----------
# A future is a NET of outcomes with confidences, not one extrapolated statement (plan.md). A scenario
# tree is: a binary ROOT card (does a binding constraint / regime shift occur at all?) → a MECE set of
# child outcomes (which way it resolves), each child's `probability` read as the CONDITIONAL P given the
# parent occurred, the set summing to 1. Children can branch again. Every node is a normal immutable,
# falsifiable, Brier-scorable ForecastCard; the tree only adds the (scenario_id, parent_card_id) linkage.

SCENARIO_SUM_TOL = 0.005  # MECE children's conditional probabilities must sum to 1 within this


def create_root_card(conn: sqlite3.Connection, **fields) -> ForecastCard:
    """Write a scenario-tree ROOT (a standalone falsifiable card whose scenario_id points at itself)."""
    card = create_card(conn, **fields)
    conn.execute("UPDATE forecast_cards SET scenario_id=? WHERE id=?", (card.id, card.id))
    conn.commit()
    card.scenario_id = card.id
    return card


def add_scenario_branch(
    conn: sqlite3.Connection, scenario_id: str, parent_card_id: str, children: list[dict],
) -> list[ForecastCard]:
    """Write a MECE set of child outcomes under one parent. The children are mutually exclusive and
    exhaustive: their `probability` (each read as P(child | parent)) MUST sum to 1 — refused otherwise,
    so an incoherent web is unrepresentable (the structural analogue of the P/CI consistency check)."""
    if not children:
        raise ValueError("a scenario branch needs at least one child outcome")
    total = sum(c["probability"] for c in children)
    if abs(total - 1.0) > SCENARIO_SUM_TOL:
        raise ValueError(
            f"MECE children must be mutually-exclusive + exhaustive: conditional probabilities sum to "
            f"{total:.4f}, not 1.0 (tol {SCENARIO_SUM_TOL}). Add the residual 'none of these' outcome "
            f"or fix the splits — a scenario web that doesn't sum to 1 is incoherent."
        )
    if conn.execute("SELECT 1 FROM forecast_cards WHERE id=?", (parent_card_id,)).fetchone() is None:
        raise ValueError(f"no parent card {parent_card_id}")
    out = []
    for c in children:
        out.append(create_card(conn, scenario_id=scenario_id, parent_card_id=parent_card_id, **c))
    return out


def scenario_tree(conn: sqlite3.Connection, scenario_id: str) -> dict:
    """Read a whole tree back as nested nodes, each annotated with its MARGINAL probability
    (= product of conditional probabilities down its path from the root). Skips superseded cards."""
    rows = conn.execute(
        "SELECT id, question, probability, resolution_date, parent_card_id, outcome, brier_score "
        "FROM forecast_cards WHERE scenario_id=? AND superseded_by IS NULL", (scenario_id,)
    ).fetchall()
    by_parent: dict[str | None, list] = {}
    root = None
    for r in rows:
        if r["id"] == scenario_id:
            root = r
        by_parent.setdefault(r["parent_card_id"], []).append(r)

    def build(r, marginal_parent: float) -> dict:
        cond = r["probability"]
        marginal = marginal_parent * cond
        kids = sorted(by_parent.get(r["id"], []), key=lambda k: -k["probability"])
        return {
            "id": r["id"], "question": r["question"], "conditional_p": cond,
            "marginal_p": marginal, "resolution_date": r["resolution_date"],
            "outcome": r["outcome"], "brier": r["brier_score"],
            "children": [build(k, marginal) for k in kids],
        }

    if root is None:
        raise ValueError(f"no scenario root {scenario_id}")
    return build(root, 1.0)


def resolve(conn: sqlite3.Connection, card_id: str, outcome: ForecastOutcome) -> float:
    """Resolve a card and compute its Brier score = (probability − outcome)². Returns the Brier."""
    row = conn.execute(
        "SELECT probability, outcome, parent_card_id FROM forecast_cards WHERE id=?", (card_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"no forecast card {card_id}")
    if row["outcome"] is not None:
        raise ValueError(f"card {card_id} already resolved ({row['outcome']})")
    # Conditional-branch voiding: a child's probability is P(this | parent occurred). If the parent
    # resolved FALSE, the premise is void — the conditional bet never came live, so it must NOT be
    # Brier-scored (the structural analogue of premise_void). Refuse rather than score a dead branch.
    if row["parent_card_id"]:
        par = conn.execute(
            "SELECT outcome FROM forecast_cards WHERE id=?", (row["parent_card_id"],)
        ).fetchone()
        if par and par["outcome"] == ForecastOutcome.false.value:
            raise ValueError(
                f"card {card_id} is a conditional branch whose parent {row['parent_card_id']} resolved "
                f"FALSE — its premise is void, so it does not score (do not resolve it)."
            )
    actual = 1.0 if outcome is ForecastOutcome.true else 0.0
    brier = (row["probability"] - actual) ** 2
    conn.execute(
        "UPDATE forecast_cards SET outcome=?, resolved_at=?, brier_score=? WHERE id=?",
        (outcome.value, _now().isoformat(), brier, card_id),
    )
    conn.commit()
    # Close the loop (the centerpiece): if this card was promoted from a hypothesis, write the
    # outcome + Brier back onto it so base_rates() measures whether that KIND of structural call
    # paid. Local import avoids a forecast↔hypothesis cycle.
    from engine import hypothesis
    hypothesis.record_outcome(conn, card_id, outcome, brier)
    return brier


# --- calibration (component 11) -----------------------------------------------


def calibration(conn: sqlite3.Connection) -> dict:
    """Resolved-card scoreboard: per-card points + mean Brier vs the naive base-rate baseline."""
    # Exclude the fast-resolution LADDER rungs (component 11b) — they are a SEPARATE calibration track
    # (engine/ladder.py); the thesis calibration here stays the hand-/graph-authored bets only.
    rows = conn.execute(
        "SELECT id, question, probability, outcome, brier_score FROM forecast_cards "
        "WHERE outcome IS NOT NULL AND superseded_by IS NULL AND question NOT LIKE 'LADDER —%' "
        "ORDER BY resolved_at"
    ).fetchall()
    points = [
        {"id": r["id"], "predicted": r["probability"],
         "realized": 1.0 if r["outcome"] == "true" else 0.0,
         "brier": r["brier_score"]}
        for r in rows
    ]
    n = len(points)
    brier_model = sum(p["brier"] for p in points) / n if n else None
    brier_baseline = (
        sum((BASELINE_P - p["realized"]) ** 2 for p in points) / n if n else None
    )
    return {"n_resolved": n, "points": points,
            "brier_model": brier_model, "brier_baseline": brier_baseline}


# --- the SEAL: an un-backdateable snapshot of the live forward record ----------
# The moat is TIME (VATI §6): a sealed, leak-free track record can't be back-dated, so a competitor
# starting later is permanently behind. But the cards live in the GITIGNORED DB (local state) — nothing
# proves WHEN a call was made. This exports the LIVE forward calls to a deterministic, committable
# manifest + its sha256; a `git commit` (append-only, timestamped, pushable to GitHub) is the seal, and
# `ots stamp` on the hash later adds a blockchain-anchored proof. Deterministic (rows sorted by id, keys
# sorted) → re-sealing an unchanged record is byte-identical (no spurious diffs); the hash moves ONLY
# when the calls change. The mechanical LADDER rungs are excluded (no thesis_kind) — this is the
# human+AI structural record, the thing the moat is actually made of.

SEAL_PATH = Path(__file__).resolve().parent.parent / "experiments" / "forward_calls_seal.jsonl"

# Only the fields that constitute the PREDICTION (immutable claim) — never the resolution fields
# (outcome/brier are null on a live call and would let a later edit masquerade as the original seal).
_SEAL_FIELDS = (
    "id", "created_at", "question", "resolution_date", "probability",
    "ci_low", "ci_high", "ci_unit", "threshold", "threshold_dir",
    "thesis_kind", "mispricing_kind", "scenario_id", "parent_card_id",
    "premise_void", "kill_criteria", "rationale",
)


def live_forward_calls(conn: sqlite3.Connection) -> list[dict]:
    """The forward PREDICTION record: every live (unresolved, non-superseded) STRUCTURAL call —
    thesis_kind set, so the mechanical calibration-ladder rungs are excluded. Sorted by id so the
    export is deterministic."""
    rows = conn.execute(
        "SELECT * FROM forecast_cards WHERE outcome IS NULL AND superseded_by IS NULL "
        "AND thesis_kind IS NOT NULL AND thesis_kind != '' ORDER BY id"
    ).fetchall()
    out: list[dict] = []
    for r in rows:
        d: dict = {}
        for f in _SEAL_FIELDS:
            v = r[f]
            if f in ("premise_void", "kill_criteria"):
                v = json.loads(v) if v else []
            d[f] = v
        out.append(d)
    return out


def export_seal(conn: sqlite3.Connection, *, path: Path = SEAL_PATH) -> dict:
    """Write the live forward record to a deterministic JSONL manifest + a sha256 sidecar. Returns
    {n_calls, sha256, path, sha_path}. Committing the two files is the seal (the git timestamp can't be
    back-dated once pushed); recomputing sha256(manifest) verifies the record was never altered."""
    calls = live_forward_calls(conn)
    body = "".join(json.dumps(c, sort_keys=True, ensure_ascii=False) + "\n" for c in calls)
    path.write_text(body, encoding="utf-8")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    sha_path = path.with_suffix(".sha256")
    sha_path.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return {"n_calls": len(calls), "sha256": digest, "path": str(path), "sha_path": str(sha_path)}


# --- the doctrine-reasoned seed (the first real ForecastCard) -----------------
# Seed = single-cell RNA-seq, the NIH-grant detector hit (30σ). Chosen over the mRNA-vaccine
# hit because mRNA's inflection is an *exogenous* COVID shock (plan.md excludes those), whereas
# scRNA-seq is a clean, mechanism-backed acceleration: falling $/cell + droplet microfluidics
# (10x Genomics, commercial 2016) made per-cell transcriptomics routine. doctrine §2: trust
# accelerations with a mechanism, not bare momentum.

SEED_LABEL = "single cell rna sequencing (NIH grants)"


def _seed_series(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, source_id FROM series WHERE label=?", (SEED_LABEL,)
    ).fetchone()


def seed_forecasts(conn: sqlite3.Connection, *, log=print) -> dict:
    """Write the project's first two ForecastCards from the scRNA-seq detector hit.

    Both are reasoned in-session, point-in-time, and framed as *constraint migration*:
      • RETRO (as-of FY2017): a 2× "real-takeoff" bet, resolution already past → gives the first
        real Brier point. Directionally right & beats baseline, but the realized count blew past
        the 80% CI — an honest, logged lesson in underconfidence about how far an acceleration runs.
      • FORWARD (as-of FY2023): the live bet — growth continues but *decelerates* (S-curve onset;
        recent YoY 1.34→1.22→1.20) as the method commoditizes and rent migrates off the (elastic)
        sequencer onto the (inelastic) single-cell partitioning consumable layer.
    Idempotent: skips a card whose question already exists.
    """
    s = _seed_series(conn)
    if s is None:
        log("seed series not found — run collect-frontier first. nothing written.")
        return {"created": 0, "resolved": 0}
    series_id, source_id = s["id"], s["source_id"]
    src_ids = [source_id] if source_id else []

    def exists(q: str) -> bool:
        return conn.execute("SELECT 1 FROM forecast_cards WHERE question=?", (q,)).fetchone() is not None

    created = resolved = 0

    # --- RETRO: point-in-time as of end-FY2017 (uses only the ≤2017 series: 60→706 awards/yr).
    # A 2017 fox mean-regresses the noisy recent pace (YoY 1.65,1.24,1.40 → g≈1.33), widely (σ=0.16),
    # with mild further regression (decel 0.03). Question: does it sustain a 2× takeoff to FY2020?
    retro_q = ("By FY2020, do NIH grant awards mentioning single-cell RNA-seq reach >=1,412 "
               "(a 2x takeoff from the 706 awarded in FY2017)? [point-in-time as-of 2017-12-31]")
    if not exists(retro_q):
        q = mc_quantity(706, 3, g_mean=1.33, g_sd=0.16, decel=0.03, seed=7)
        p = q.prob_at_least(1412)
        retro = create_card(
            conn,
            question=retro_q,
            resolution_date=date(2020, 12, 31),
            probability=round(p, 3),
            ci_low=round(q.ci_low), ci_high=round(q.ci_high), ci_unit="awards/year",
            threshold=1412, threshold_dir=">=",
            seed_series_id=series_id,
            pillars_used=[1, 2],
            source_ids=src_ids,
            rationale=(
                "CONSTRAINT-MIGRATION THESIS: scRNA-seq is crossing from frontier to routine "
                "(droplet microfluidics; 10x Genomics commercial 2016) — a mechanism-backed "
                "acceleration, not bare momentum (doctrine §2). OUTSIDE VIEW: hot, well-funded "
                "biomedical methods on a strong uptrend rarely halt within 3 years, so a mere "
                "doubling has a high base rate. FERMI/MC: 706 awards compounded 3y under uncertain "
                f"growth g~N(1.33,0.16) decelerating → median {q.median:.0f}/yr, 80% CI "
                f"[{q.ci_low:.0f},{q.ci_high:.0f}]; P(>=1,412) = {p:.2f}. The probability and "
                "interval are MC outputs, not guesses (execution §3)."
            ),
            kill_criteria=[
                "FY2020 awards < 1,412 — the acceleration stalled within 3 years (thesis wrong).",
                "FY2020 awards collapse below the FY2017 level (706) — the method was a fad, not a takeoff.",
            ],
        )
        created += 1
        log(f"RETRO created {retro.id}  P={retro.probability}  CI[{retro.ci_low:.0f},{retro.ci_high:.0f}]")
        # Resolve against the recorded FY2020 observation on the seed series itself.
        fy2020 = conn.execute(
            "SELECT value FROM observations WHERE series_id=? AND as_of LIKE '2020%'", (series_id,)
        ).fetchone()
        actual = fy2020["value"] if fy2020 else None
        if actual is not None:
            outcome = ForecastOutcome.true if actual >= 1412 else ForecastOutcome.false
            brier = resolve(conn, retro.id, outcome)
            resolved += 1
            note = ""
            if outcome is ForecastOutcome.true and actual > retro.ci_high:
                note = (f"  (HONEST CAVEAT: realized {actual:.0f} exceeded the 80% CI upper "
                        f"{retro.ci_high:.0f} — right direction & beat baseline, but UNDERconfident "
                        f"on magnitude; logged lesson, not tuned away.)")
            log(f"RETRO resolved {outcome.value} (actual FY2020={actual:.0f}) → Brier={brier:.3f}"
                f" vs naive 0.5 baseline {((BASELINE_P-1)**2):.3f}{note}")

    # --- FORWARD: point-in-time as of end-FY2023 (full series 60→5,567). Recent YoY 1.34→1.22→1.20
    # → maturing; model continued-but-decelerating growth g~N(1.155,0.07), decel 0.02.
    fwd_q = ("By FY2026, do NIH grant awards mentioning single-cell RNA-seq reach >=8,000 "
             "(vs 5,567 in FY2023)? [point-in-time as-of 2023-12-31]")
    if not exists(fwd_q):
        q = mc_quantity(5567, 3, g_mean=1.155, g_sd=0.07, decel=0.02, seed=42)
        p = q.prob_at_least(8000)
        fwd = create_card(
            conn,
            question=fwd_q,
            resolution_date=date(2027, 6, 30),  # FY2026 ends 2026-09-30; allow RePORTER load-lag to settle
            probability=round(p, 3),
            ci_low=round(q.ci_low), ci_high=round(q.ci_high), ci_unit="awards/year",
            threshold=8000, threshold_dir=">=",
            seed_series_id=series_id,
            pillars_used=[1, 2],
            source_ids=src_ids,
            rationale=(
                "CONSTRAINT-MIGRATION THESIS: scRNA-seq has commoditized — the binding constraint "
                "(and the rent) is leaving the now-elastic short-read sequencer and concentrating in "
                "the least-substitutable upstream input: the single-cell partitioning consumable "
                "(droplet chips + barcoded beads, patent-protected). The DEMAND leg, testable now: "
                "grant velocity keeps compounding but DECELERATES as the field matures (YoY 1.34→1.22→"
                f"1.20). FERMI/MC: 5,567 compounded 3y under g~N(1.155,0.07) decelerating → median "
                f"{q.median:.0f}/yr, 80% CI [{q.ci_low:.0f},{q.ci_high:.0f}]; P(>=8,000) = {p:.2f} — "
                "deliberately near coin-flip (honest granularity, doctrine §2.3)."
            ),
            kill_criteria=[
                "FY2026 awards < 6,500 — demand acceleration stalled earlier than modelled (S-curve topped out).",
                "FY2026 awards > 11,000 — a naive RE-acceleration, not the decelerating-maturity path the thesis predicts.",
                "A non-10x / open-source droplet-partitioning method (or expired-patent generic) takes the "
                "dominant share of new scRNA-seq methods by resolution — the consumable layer was elastic, "
                "rent dissipated, the constraint did not bind where claimed (needs Pillar-3/5 data; Phase 4+).",
            ],
        )
        created += 1
        log(f"FORWARD created {fwd.id}  P={fwd.probability}  CI[{fwd.ci_low:.0f},{fwd.ci_high:.0f}]  (open, resolves 2027-06-30)")

    return {"created": created, "resolved": resolved}


# --- the first worked forecast WEB (the structural-net deliverable) -----------
# Retrofits the binary cable-lay card into a scenario tree: instead of one statement ("cable-lay is the
# binding pace-setter, P 0.55"), the future is a NET of linked, confidence-weighted outcomes. ROOT asks
# the binary that gates everything (does HVDC deployment hit a single binding pace-setter at all?); its
# MECE children split WHICH layer paces the build (conditional on a constraint binding, summing to 1);
# the vessels branch splits again on HOW TIGHT it stays. Every node is its own falsifiable Brier card.
# Idempotent; supersedes the old binary cable-lay card (rule 7 — never edit) into the vessels node.

_HVDC_ROOT_Q = (
    "Through 2029-12-31, does grid + offshore HVDC link deployment hit a BINDING supply constraint — a "
    "single first-saturating layer that demonstrably paces installed link-km below the announced "
    "pipeline — rather than scaling elastically across all layers? [structural root, as-of 2026-06-05]"
)
_OLD_CABLELAY_CARD_PREFIX = "By 2029-12-31, do independent vessel-market data show subsea cable-lay"


def seed_hvdc_scenario(conn: sqlite3.Connection, *, log=print) -> dict:
    """Author the HVDC-deployment scenario web: 1 binary root → 4 MECE binding-layer outcomes →
    a 2-way intensity split under the vessels layer. All conditional probabilities are in-session
    judgment (the human+AI loop); the MACHINE enforces that each MECE set sums to 1. $0, idempotent."""
    if conn.execute("SELECT 1 FROM forecast_cards WHERE question=?", (_HVDC_ROOT_Q,)).fetchone():
        log("HVDC scenario already authored — skipping.")
        return {"created": 0}

    root = create_root_card(
        conn,
        question=_HVDC_ROOT_Q,
        resolution_date=date(2029, 12, 31),
        probability=0.85,
        thesis_kind="constraint_migration", mispricing_kind="layer_blindness",
        pillars_used=[3, 4],
        rationale=(
            "STRUCTURAL ROOT (binary gate of the web). Announced HVDC pipelines (European offshore "
            "grid, interconnectors, China UHV) imply a step-change in annual link-km; the four enabling "
            "layers below have very different elasticities, so it is near-certain (~0.85) that at least "
            "ONE saturates first and paces the rest. The residual ~0.15 = the bullish-elastic world "
            "where capacity is added fast enough everywhere that no single layer binds. The WHICH-layer "
            "question is answered by the MECE children, conditional on this resolving TRUE."
        ),
        kill_criteria=[
            "By 2029, installed HVDC link-km tracks the 2025-announced pipeline within ~10% with no "
            "layer sustaining >90% utilisation / multi-year backlog — capacity scaled elastically, no "
            "binding pace-setter (root FALSE → all conditional children are voided, not scored).",
        ],
    )
    log(f"ROOT created {root.id}  P={root.probability}")

    # MECE children: WHICH layer is the binding pace-setter, conditional on the root being TRUE.
    children = [
        dict(
            question=("Given a binding HVDC constraint, is subsea cable-LAY INSTALLATION (CLV fleet "
                      "utilisation + multi-year booking backlog) the binding pace-setter through 2029?"),
            resolution_date=date(2029, 12, 31), probability=0.50,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("The installation vessels (cable-lay + heavy-transport) are the least-elastic "
                       "link: a new CLV is a ~3-4y, ~$300M+ newbuild and the global fleet is tiny, so "
                       "utilisation + backlog saturate before factory output does. Highest-conviction "
                       "leg (0.50)."),
            kill_criteria=["CLV fleet utilisation stays <85% with available 2027-29 slots while another "
                           "layer is the cited bottleneck — vessels were not the pace-setter."],
        ),
        dict(
            question=("Given a binding HVDC constraint, is subsea HVDC CABLE MANUFACTURING (XLPE / "
                      "mass-impregnated extrusion + offshore qualification) the binding pace-setter "
                      "through 2029?"),
            resolution_date=date(2029, 12, 31), probability=0.27,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("Cable factories ARE being expanded (Nexans, Prysmian, NKT, LS) but each line is "
                       "a multi-year capex with long qualification — plausible binder (0.27) if vessel "
                       "newbuilds arrive faster than extrusion capacity."),
            kill_criteria=["Cable order books clear within quoted lead times while installation slots are "
                           "the cited constraint — factory output was elastic enough."],
        ),
        dict(
            question=("Given a binding HVDC constraint, are HVDC CONVERTER STATIONS (valve-hall power "
                      "electronics + large power transformers) the binding pace-setter through 2029?"),
            resolution_date=date(2029, 12, 31), probability=0.15,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("Large power transformers + IGBT/valve supply already show multi-year lead times; "
                       "could bind (0.15) but more substitutable across vendors than the marine layers."),
            kill_criteria=["Converter/transformer lead times stay flat while a marine layer is the cited "
                           "bottleneck — converters were not the pace-setter."],
        ),
        dict(
            question=("Given a binding HVDC constraint, is PERMITTING / interconnection-queue / seabed "
                      "consenting the binding pace-setter on commissioned link-km through 2029?"),
            resolution_date=date(2029, 12, 31), probability=0.08,
            thesis_kind="policy_scarcity", mispricing_kind="horizon_gap", pillars_used=[3, 8],
            rationale=("Consenting is slow but largely PRECEDES the 2025-29 build window for projects "
                       "already in construction, so it is the least likely binder ON COMMISSIONED km in "
                       "this window (0.08) — it bites the post-2029 cohort more."),
            kill_criteria=["Projects with secured supply slip purely on permitting/consent in 2026-29 — "
                           "consenting was the live pace-setter after all."],
        ),
    ]
    kids = add_scenario_branch(conn, root.id, root.id, children)
    log(f"  4 MECE binding-layer children written (conditional P sums to 1.00)")

    # Depth-2: under the VESSELS layer, split on HOW TIGHT it stays (the old binary card's content).
    vessels = kids[0]
    add_scenario_branch(conn, root.id, vessels.id, [
        dict(
            question=("Given cable-lay vessels are the binding pace-setter, does CLV utilisation stay "
                      ">90% with 12+ month booking lead times SUSTAINED through 2029 (rent does not "
                      "dissipate as newbuilds deliver)?"),
            resolution_date=date(2029, 12, 31), probability=0.70,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("Newbuild CLVs ordered now mostly deliver 2028+, so the tight regime likely holds "
                       "most of the window (0.70). This is the harvestable, short-fused leg."),
            kill_criteria=["CLV utilisation falls below 90% before 2028 as newbuilds enter — the rent "
                           "dissipated faster than modelled."],
        ),
        dict(
            question=("Given cable-lay vessels are the binding pace-setter, does the constraint EASE "
                      "before 2029 (utilisation <90% / lead times <12mo) as newbuild CLVs deliver?"),
            resolution_date=date(2029, 12, 31), probability=0.30,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("The elastic-relief tail (0.30): enough CLV newbuild + conversion capacity lands "
                       "in-window to loosen the bottleneck before resolution."),
            kill_criteria=["Utilisation stays >90% through 2029 — the constraint did not ease in-window."],
        ),
    ])
    log(f"  vessels branch split 0.70 / 0.30 (sustained vs eases)")

    # Rule 7: supersede the old binary cable-lay card into the vessels node (never edit). The marginal
    # of the vessels node (0.85 × 0.50 = 0.425) is the web's coherent restatement of that lone P-0.55 call.
    old = conn.execute(
        "SELECT id, superseded_by FROM forecast_cards WHERE question LIKE ? AND scenario_id IS NULL",
        (_OLD_CABLELAY_CARD_PREFIX + "%",),
    ).fetchone()
    if old and not old["superseded_by"]:
        conn.execute("UPDATE forecast_cards SET superseded_by=? WHERE id=?", (vessels.id, old["id"]))
        conn.commit()
        log(f"  superseded old binary cable-lay card {old['id']} → vessels node {vessels.id}")

    return {"created": 1 + len(kids) + 2}


# --- second forecast WEB: the injectable-delivery (GLP-1 / biologics) chain ----
# Same shape as HVDC, different industry. The standing binary fill-finish card asked ONE statement
# ("contract sterile fill-finish stays >90% utilised, P 0.62"). The web reframes it: GLP-1 + biologics
# demand is exploding, but WHICH layer of the injectable-delivery chain (downstream of the molecule)
# is the binding pace-setter on dose output? MECE over the four sequential layers + a residual-elastic
# world. The fill-finish node branches again on intensity (the old card's content). The device-assembly
# and borosilicate-tubing nodes are NEW forward calls never carded before. Idempotent; supersedes the
# old binary fill-finish card (rule 7) into the fill-finish-capacity node.

_FILLFINISH_ROOT_Q = (
    "Through 2028-12-31, does the injectable-biologics delivery buildout (GLP-1 pens/autoinjectors + "
    "mAb/biologic prefilled syringes) hit a BINDING supply constraint — a single first-saturating layer "
    "DOWNSTREAM of the drug substance that demonstrably paces finished-dose output below demand — rather "
    "than scaling elastically across fill-finish, components, assembly and glass? [structural root, as-of 2026-06-05]"
)
_OLD_FILLFINISH_CARD_PREFIX = "By 2028-12-31, do independent industry reports show contract sterile fill-finish"


def seed_fillfinish_scenario(conn: sqlite3.Connection, *, log=print) -> dict:
    """Author the injectable-delivery scenario web: 1 binary root → 4 MECE binding-layer outcomes →
    a 2-way intensity split under the fill-finish layer. Conditional probabilities are in-session
    judgment; the MACHINE enforces each MECE set sums to 1. $0, idempotent."""
    if conn.execute("SELECT 1 FROM forecast_cards WHERE question=?", (_FILLFINISH_ROOT_Q,)).fetchone():
        log("fill-finish scenario already authored — skipping.")
        return {"created": 0}

    root = create_root_card(
        conn,
        question=_FILLFINISH_ROOT_Q,
        resolution_date=date(2028, 12, 31),
        probability=0.80,
        thesis_kind="constraint_migration", mispricing_kind="layer_blindness",
        pillars_used=[3, 4, 5],
        rationale=(
            "STRUCTURAL ROOT (binary gate). GLP-1 (Novo/Lilly) + the mAb/biologic wave imply a step-change "
            "in injectable finished-dose demand; the four enabling layers downstream of the molecule "
            "(aseptic fill-finish, primary containers, device/combination assembly, specialty glass) each "
            "carry multi-year capex + regulatory qualification, so it is highly likely (~0.80) at least ONE "
            "saturates first and paces the rest — the visible 2023-25 pen shortages were delivery-chain, not "
            "API. The residual ~0.20 = the elastic world where CDMO + component capex lands fast enough that "
            "no single layer binds. WHICH layer is answered by the MECE children, conditional on TRUE."
        ),
        kill_criteria=[
            "By 2028, injectable finished-dose output tracks demand with no layer sustaining >90% "
            "utilisation / 12+ month lead times — capacity scaled elastically, no binding pace-setter "
            "(root FALSE → all conditional children voided, not scored).",
        ],
    )
    log(f"ROOT created {root.id}  P={root.probability}")

    # MECE children: WHICH layer paces finished-dose output, conditional on the root being TRUE.
    children = [
        dict(
            question=("Given a binding injectable-delivery constraint, is contract STERILE FILL-FINISH "
                      "capacity (aseptic isolator/RABS lines, CDMO) the binding pace-setter through 2028 "
                      "— sustained >90% utilisation with 12+ month lead times?"),
            resolution_date=date(2028, 12, 31), probability=0.45,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("The original thesis + highest-conviction leg (0.45): aseptic filling capacity is "
                       "capital-heavy, slow to qualify, and CDMO lead times already stretch 12-18mo. Most "
                       "directly cited as the GLP-1/biologics bottleneck."),
            kill_criteria=["Contract sterile fill-finish utilisation falls below 85% with open near-term "
                           "slots while another layer is the cited bottleneck — fill-finish was elastic."],
        ),
        dict(
            question=("Given a binding injectable-delivery constraint, is DEVICE / COMBINATION-PRODUCT "
                      "ASSEMBLY (automated autoinjector + pen final assembly / labelling / packaging) the "
                      "binding pace-setter through 2028?"),
            resolution_date=date(2028, 12, 31), probability=0.27,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("NEW leg, the live GLP-1 tell (0.27): Novo/Lilly were constrained on PEN assembly "
                       "throughput, not molecule — high-speed automated combination-assembly lines are "
                       "scarce, bespoke, and slow to commission. Plausibly the true pace-setter for pens."),
            kill_criteria=["Autoinjector/pen assembly throughput keeps pace (no assembly-line backlog "
                           "cited) while another layer binds — assembly was not the pace-setter."],
        ),
        dict(
            question=("Given a binding injectable-delivery constraint, are PRIMARY CONTAINER COMPONENTS "
                      "(prefilled-syringe glass barrels, cartridges, elastomer stoppers/plungers) the "
                      "binding pace-setter through 2028?"),
            resolution_date=date(2028, 12, 31), probability=0.18,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("Component makers (Gerresheimer, SCHOTT, Stevanato, West, Datwyler) are expanding "
                       "but PFS + elastomer qualification is multi-year and oligopolistic — plausible "
                       "binder (0.18) if filling/assembly capacity arrives faster than components."),
            kill_criteria=["PFS/cartridge/stopper order books clear within quoted lead times while another "
                           "layer is the cited constraint — components were elastic enough."],
        ),
        dict(
            question=("Given a binding injectable-delivery constraint, is SPECIALTY BOROSILICATE (Type I) "
                      "GLASS TUBING — the deepest input under every glass container — the binding "
                      "pace-setter through 2028?"),
            resolution_date=date(2028, 12, 31), probability=0.10,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("The deepest one-layer-down input (0.10): pharma-grade borosilicate tubing is made "
                       "by very few (SCHOTT, Corning Valor, Nipro, NEG) on furnaces that take years to "
                       "build. Least likely to bind FIRST (converters draw down inventory) but the highest-"
                       "rent leg IF it does — the razor under the razor."),
            kill_criteria=["Borosilicate tubing supply stays ample (no tubing allocation cited) while a "
                           "downstream layer binds — tubing was not the pace-setter in this window."],
        ),
    ]
    kids = add_scenario_branch(conn, root.id, root.id, children)
    log(f"  4 MECE binding-layer children written (conditional P sums to 1.00)")

    # Depth-2: under the FILL-FINISH layer, split on HOW TIGHT it stays (the old binary card's content).
    ff = kids[0]
    add_scenario_branch(conn, root.id, ff.id, [
        dict(
            question=("Given fill-finish is the binding pace-setter, does contract sterile fill-finish stay "
                      ">90% utilised with 12+ month lead times SUSTAINED through 2028 (rent does not "
                      "dissipate as CDMO capex lands)?"),
            resolution_date=date(2028, 12, 31), probability=0.65,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("Announced aseptic-capacity capex mostly commissions + qualifies 2027+, so the tight "
                       "regime likely holds most of the window (0.65). The harvestable, short-fused leg."),
            kill_criteria=["Fill-finish utilisation falls below 90% before 2028 as new lines qualify — the "
                           "rent dissipated faster than modelled."],
        ),
        dict(
            question=("Given fill-finish is the binding pace-setter, does the constraint EASE before 2028 "
                      "(utilisation <90% / lead times <12mo) as new CDMO aseptic capacity qualifies?"),
            resolution_date=date(2028, 12, 31), probability=0.35,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("The elastic-relief tail (0.35): enough aseptic-line capex qualifies in-window to "
                       "loosen the bottleneck before resolution — faster than the marine-vessel analogue "
                       "because filling lines commission quicker than a CLV newbuild."),
            kill_criteria=["Utilisation stays >90% through 2028 — the constraint did not ease in-window."],
        ),
    ])
    log(f"  fill-finish branch split 0.65 / 0.35 (sustained vs eases)")

    # Rule 7: supersede the old binary fill-finish card into the fill-finish node (never edit).
    old = conn.execute(
        "SELECT id, superseded_by FROM forecast_cards WHERE question LIKE ? AND scenario_id IS NULL",
        (_OLD_FILLFINISH_CARD_PREFIX + "%",),
    ).fetchone()
    if old and not old["superseded_by"]:
        conn.execute("UPDATE forecast_cards SET superseded_by=? WHERE id=?", (ff.id, old["id"]))
        conn.commit()
        log(f"  superseded old binary fill-finish card {old['id']} → fill-finish node {ff.id}")

    return {"created": 1 + len(kids) + 2}


# --- declarative webs: HVDC + fill-finish above were the two bespoke pioneers; every web after them is
# pure DATA (a root + MECE children + optional depth-2 branches) authored through one generic seeder, so
# forecast.py stays thin (rule 5) — adding web #5 is a dict, not a 120-line function. No supersede arm
# here: these webs have no prior binary card to retire (unlike the two pioneers).

def seed_web(conn: sqlite3.Connection, spec: dict, *, log=print) -> dict:
    """Author one declarative scenario web. `spec` = {key, root{...}, children[...], branches[...]}.
    Each `branches` entry = {under: <child index>, children: [...]}. The machine enforces every MECE
    set sums to 1 (`add_scenario_branch`). Idempotent on the root question. $0."""
    root_fields = spec["root"]
    if conn.execute("SELECT 1 FROM forecast_cards WHERE question=?", (root_fields["question"],)).fetchone():
        log(f"{spec['key']} scenario already authored — skipping.")
        return {"created": 0}
    root = create_root_card(conn, **root_fields)
    log(f"ROOT created {root.id}  P={root.probability}  [{spec['key']}]")
    kids = add_scenario_branch(conn, root.id, root.id, spec["children"])
    log(f"  {len(kids)} MECE binding-layer children written (conditional P sums to 1.00)")
    created = 1 + len(kids)
    for br in spec.get("branches", []):
        bk = add_scenario_branch(conn, root.id, kids[br["under"]].id, br["children"])
        created += len(bk)
        log(f"  depth-2 split under child {br['under']} ({len(bk)} outcomes)")
    return {"created": created}


_RAREEARTH_WEB = {
    "key": "rare-earth",
    "root": dict(
        question=(
            "Through 2029-12-31, does allied (ex-China) supply of export-controlled critical inputs "
            "(heavy rare earths, gallium, germanium, anode graphite) hit a BINDING constraint — a single "
            "first-saturating non-China layer that demonstrably paces qualified Western availability below "
            "demand — rather than scaling elastically across mining, separation/refining and magnet/metal "
            "making? [structural root, as-of 2026-06-05]"
        ),
        resolution_date=date(2029, 12, 31), probability=0.82,
        thesis_kind="policy_scarcity", mispricing_kind="layer_blindness", pillars_used=[3, 4, 8],
        premise_void=[
            "A Chinese rescission / material relaxation of the export controls before 2029 removes the "
            "decreed scarcity — resolve PREMISE-VOID (not Brier-wrong); the web scores only while controls "
            "persist."
        ],
        rationale=(
            "STRUCTURAL ROOT (binary gate). With export controls escalating (a POLITICS force = decreed "
            "scarcity), the binding constraint on allied supply migrates OFF mine output. The midstream "
            "layers (separation/refining, metal+magnet making) are permitting + tacit-metallurgical-know-"
            "how + offtake gated and multi-year to stand up, so it is highly likely (~0.82) that ONE "
            "ex-China layer saturates first and paces the rest. The residual ~0.18 = the elastic world "
            "where subsidised refining (US DPA/IRA, Australia, EU) + thrifting + stockpiles close the gap "
            "in-window. WHICH layer binds is answered by the MECE children, conditional on TRUE."
        ),
        kill_criteria=[
            "By 2029, ex-China qualified availability of the controlled inputs tracks demand with no "
            "midstream layer sustaining an origin premium / allocation — capacity scaled elastically, no "
            "binding pace-setter (root FALSE → conditionals voided, not scored).",
            "A Chinese rescission of the controls before 2029 = premise-void (see premise_void), not FALSE.",
        ],
    ),
    "children": [
        dict(
            question=("Given a binding ex-China constraint, is SEPARATION / REFINING capacity "
                      "(solvent-extraction oxide separation — especially heavy rare earths — and "
                      "metal-grade purification) the binding pace-setter through 2029?"),
            resolution_date=date(2029, 12, 31), probability=0.46,
            thesis_kind="policy_scarcity", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("Highest-conviction leg (0.46): ex-China separation — especially heavy-REE (Dy/Tb) "
                       "solvent extraction — is near-absent, permitting + tacit-know-how gated, multi-year "
                       "to qualify. Lynas/MP/Solvay/Vietnam ramp from ~zero on the heavy fraction."),
            kill_criteria=["By 2028, USGS/industry data show ex-China separated/refined output share for "
                           "the controlled inputs rising >10pp toward parity while another layer is the "
                           "cited bottleneck — separation was not the pace-setter."],
        ),
        dict(
            question=("Given a binding ex-China constraint, is METAL / ALLOY + SINTERED-MAGNET "
                      "MANUFACTURING (rare-earth metallization and NdFeB magnet capacity) the binding "
                      "pace-setter through 2029?"),
            resolution_date=date(2029, 12, 31), probability=0.30,
            thesis_kind="policy_scarcity", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("The downstream chokepoint (0.30): even with oxide, ex-China metallization + "
                       "sintered-NdFeB capacity (VAC, MP Texas, Less Common Metals) is tiny and slow to "
                       "qualify to automotive/defence spec — plausibly the true binder on finished magnets."),
            kill_criteria=["Ex-China magnet/metal output scales to contracted EV/wind/defence demand on "
                           "schedule while another layer is cited — magnet-making was elastic."],
        ),
        dict(
            question=("Given a binding ex-China constraint, is MINE / CONCENTRATE feedstock supply the "
                      "binding pace-setter through 2029 (the obvious-but-the-thesis-says-wrong layer)?"),
            resolution_date=date(2029, 12, 31), probability=0.12,
            thesis_kind="policy_scarcity", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("The layer-blindness control (0.12): consensus over-funds mining, but ex-China mine "
                       "projects are comparatively plentiful — the thesis is that mines are NOT the binder. "
                       "Low conditional P encodes that; if it DOES bind, the layer-blindness call was wrong."),
            kill_criteria=["A mine/concentrate shortfall (not midstream) is the cited Western constraint in "
                           "2026-29 — the layer-blindness thesis (mines aren't the binder) was wrong."],
        ),
        dict(
            question=("Given a binding ex-China constraint, is HEAVY-RARE-EARTH (Dy/Tb) FEEDSTOCK "
                      "specifically — distinct from light Nd/Pr — the binding pace-setter on "
                      "high-temperature magnets through 2029?"),
            resolution_date=date(2029, 12, 31), probability=0.12,
            thesis_kind="policy_scarcity", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("The razor under the razor (0.12): light-REE (Nd/Pr) ex-China builds out, but Dy/Tb "
                       "for grain-boundary-diffusion high-temp magnets comes almost solely from "
                       "China/Myanmar ionic clays — a separate, tighter chokepoint that can bind even if "
                       "light-REE separation relieves."),
            kill_criteria=["High-temp-magnet makers secure non-China Dy/Tb feedstock within window — the "
                           "heavy-REE-specific chokepoint did not bind."],
        ),
    ],
    "branches": [
        {"under": 0, "children": [
            dict(
                question=("Given ex-China separation is the binding pace-setter, does the ex-China-origin "
                          "price premium / allocation on the controlled inputs PERSIST (ex-China separated "
                          "share staying a minority of allied demand) sustained through 2029?"),
                resolution_date=date(2029, 12, 31), probability=0.62,
                thesis_kind="policy_scarcity", mispricing_kind="layer_blindness", pillars_used=[3, 4],
                rationale=("Separation capacity ordered now mostly qualifies 2028+, so the premium likely "
                           "holds most of the window (0.62). The harvestable leg."),
                kill_criteria=["The ex-China-origin price premium falls below ~15% while controls persist "
                               "before 2029 — the separation constraint dissolved faster than predicted."],
            ),
            dict(
                question=("Given ex-China separation is the binding pace-setter, does the constraint EASE "
                          "before 2029 (origin premium <15%, ex-China share rising toward parity) as "
                          "subsidised refining qualifies?"),
                resolution_date=date(2029, 12, 31), probability=0.38,
                thesis_kind="policy_scarcity", mispricing_kind="layer_blindness", pillars_used=[3, 4],
                rationale=("Elastic-relief tail (0.38): DPA/IRA + Australia/EU subsidised separation + "
                           "recycling qualify fast enough to compress the premium before resolution."),
                kill_criteria=["Origin premium stays >15% through 2029 — the constraint did not ease."],
            ),
        ]},
    ],
}


_ELECTRIFICATION_WEB = {
    "key": "electrification-labour",
    "root": dict(
        question=(
            "Through 2028-12-31, does the US electrification buildout hit a BINDING constraint whose binder "
            "is a NON-equipment layer — a single first-saturating input (skilled labour, interconnection, or "
            "capital) that demonstrably paces project completion below the announced pipeline — rather than "
            "large-power transformers / switchgear remaining the binding equipment layer? "
            "[structural root, as-of 2026-06-05]"
        ),
        resolution_date=date(2028, 12, 31), probability=0.78,
        thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[4, 5, 8],
        rationale=(
            "STRUCTURAL ROOT (binary gate). Equipment (transformers/HV switchgear) is the priced, hot "
            "constraint today; the thesis is the binder MIGRATES off equipment to a harder-to-scale layer "
            "over ~4y. It is likely (~0.78) that as equipment capex lands, a non-equipment input "
            "(apprenticeship-gated trades labour, interconnection queue, or capital) becomes the pace-"
            "setter. The residual ~0.22 = equipment stays the binder through 2028 (capex didn't catch up) "
            "OR the buildout scales elastically. WHICH non-equipment layer binds is the MECE children."
        ),
        kill_criteria=[
            "By 2028, equipment (transformer/switchgear) lead-times remain the single cited bottleneck and "
            "no non-equipment layer paces completion — the migration thesis was wrong / premature (root "
            "FALSE → conditionals voided, not scored).",
        ],
    ),
    "children": [
        dict(
            question=("Given the binder has migrated off equipment, is LICENSED ELECTRICAL-TRADES LABOUR "
                      "(journeyman electricians SOC 47-2111, linemen 49-9051, HV commissioning techs) the "
                      "binding pace-setter on US electrification through 2028?"),
            resolution_date=date(2028, 12, 31), probability=0.50,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[5],
            rationale=("The thesis + highest-conviction leg (0.50): licensed trades are apprenticeship-"
                       "gated (~4-5y to journeyman), demographically aging, non-importable at scale — "
                       "supply can't scale on capex. Most likely the migrated binder."),
            kill_criteria=["By 2028-12-31, real wage growth for electricians (BLS CES/OES 47-2111) does NOT "
                           "exceed large-power-transformer PPI growth over 2025-2028 — the labour layer is "
                           "not the tighter constraint."],
        ),
        dict(
            question=("Given the binder has migrated off equipment, is INTERCONNECTION-QUEUE / "
                      "transmission-permitting throughput the binding pace-setter on energized capacity "
                      "through 2028?"),
            resolution_date=date(2028, 12, 31), probability=0.27,
            thesis_kind="policy_scarcity", mispricing_kind="layer_blindness", pillars_used=[8],
            rationale=("Strong alternative (0.27): interconnection-queue durations (years) + transmission "
                       "permitting can pace energized MW independent of equipment or labour — the FERC/"
                       "queue layer."),
            kill_criteria=["Median interconnection-queue duration falls / projects energize on schedule "
                           "while another layer is cited — the queue was not the pace-setter."],
        ),
        dict(
            question=("Given the binder has migrated off equipment, is CAPITAL / FINANCING (rate-driven "
                      "cost of capital on capex-heavy grid + generation projects) the binding pace-setter "
                      "through 2028?"),
            resolution_date=date(2028, 12, 31), probability=0.13,
            thesis_kind="regime_change", mispricing_kind="horizon_gap", pillars_used=[6],
            rationale=("The macro leg (0.13): a higher-for-longer rate regime can gate completion on "
                       "financeability rather than any physical input."),
            kill_criteria=["Projects proceed at pace despite the rate environment while a physical layer is "
                           "cited — capital was not the binder."],
        ),
        dict(
            question=("Given the binder has migrated off equipment-supply, is specialised EPC / "
                      "heavy-construction CAPACITY (cranes, bucket trucks, substation EPC firms) the "
                      "binding pace-setter through 2028?"),
            resolution_date=date(2028, 12, 31), probability=0.10,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[4],
            rationale=("The execution-capacity leg (0.10): even with labour and equipment, the EPC / "
                       "heavy-construction firm capacity that assembles substations is finite and slow to "
                       "scale."),
            kill_criteria=["Substation EPC throughput keeps pace while another layer is cited — EPC "
                           "capacity was not the pace-setter."],
        ),
    ],
    "branches": [
        {"under": 0, "children": [
            dict(
                question=("Given trades labour is the binding pace-setter, does the electrician wage "
                          "premium over equipment PPI PERSIST / widen through 2028 (apprenticeship "
                          "pipeline does not close the gap)?"),
                resolution_date=date(2028, 12, 31), probability=0.65,
                thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[5],
                rationale=("Apprenticeship completions lag ~4-5y, so the wage gap likely persists most of "
                           "the window (0.65). Harvestable."),
                kill_criteria=["Registered electrician apprenticeship completions (DOL RAPIDS) rise >25% "
                               "vs 2024 and close the wage gap before 2028 — the labour cap relaxed."],
            ),
            dict(
                question=("Given trades labour is the binding pace-setter, does the constraint EASE before "
                          "2028 (wage gap closes) as prefab/modular construction + apprenticeship "
                          "expansion shift hours out of the licensed field?"),
                resolution_date=date(2028, 12, 31), probability=0.35,
                thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[5],
                rationale=("Relief tail (0.35): factory-skid substations + datacenter prefab + "
                           "immigration/visa expansion move hours out of the licensed field faster than "
                           "modelled."),
                kill_criteria=["The electrician wage premium over transformer PPI persists through 2028 — "
                               "the labour constraint did not ease."],
            ),
        ]},
    ],
}

_DECLARATIVE_WEBS = [_RAREEARTH_WEB, _ELECTRIFICATION_WEB]


def seed_all_webs(conn: sqlite3.Connection, *, log=print) -> dict:
    """Author every forecast web idempotently, then upgrade to the review-corrected v2 set. The v1
    pioneers + declarative webs are authored first (history), then `rebuild_v2` authors the corrected
    webs (re-priced / MECE-fixed) + the SiC hub, supersedes the v1 trees, and re-points the belief-net.
    Net active state = the 5 v2 webs. Idempotent, $0."""
    total = seed_hvdc_scenario(conn, log=log)["created"]
    total += seed_fillfinish_scenario(conn, log=log)["created"]
    for spec in _DECLARATIVE_WEBS:
        total += seed_web(conn, spec, log=log)["created"]
    total += rebuild_v2(conn, log=log)["webs_created"]
    return {"created": total}


# --- the BELIEF-NET: cross-thesis dependency edges over the forest of webs ------
# Within a web the tree already encodes dependency (root → MECE children). The belief-net adds the
# CROSS-web layer ("one call's resolution shifting another's P") for webs that share an inelastic input.
# Deliberately NOT a Bayesian-propagation engine with hand-typed CPTs — that repeats the disease we
# diagnosed (hand-typed rates nothing updates). Each edge is ONE coherent conditional + a falsifiable
# direction; propagation is a PURE READ over the immutable cards (it never writes a P back — rule 7).

def card_marginal(conn: sqlite3.Connection, card_id: str) -> float:
    """Marginal P of a node = product of probabilities from it up to its scenario root."""
    p, cur = 1.0, card_id
    while cur is not None:
        row = conn.execute(
            "SELECT probability, parent_card_id FROM forecast_cards WHERE id=?", (cur,)
        ).fetchone()
        if row is None:
            raise ValueError(f"no card {cur}")
        p *= row["probability"]
        cur = row["parent_card_id"]
    return p


def _p_to_if_false(p_to_marg: float, p_from_marg: float, p_to_if_true: float) -> float:
    """Derive P(to | from=FALSE) so the conditional pair marginalises back to to_card's own P:
    to_marg = p_if_true·P(from) + p_if_false·(1−P(from)). The coherence identity (sum-check analogue)."""
    return (p_to_marg - p_to_if_true * p_from_marg) / (1.0 - p_from_marg)


def add_belief_edge(conn: sqlite3.Connection, *, from_card_id: str, to_card_id: str, sign: int,
                    p_to_if_from_true: float, mechanism: str, kill_criteria: list[str]) -> BeliefEdge:
    """Author a cross-web belief edge. Refuses: a within-web pair (that is the tree); an incoherent
    lift (derived P(to|from=false) outside [0,1] — the sum-check analogue); a sign that contradicts the
    asserted direction. Immutable + GIGO (mechanism + kill_criteria required by the model)."""
    fr = conn.execute("SELECT scenario_id FROM forecast_cards WHERE id=?", (from_card_id,)).fetchone()
    to = conn.execute("SELECT scenario_id FROM forecast_cards WHERE id=?", (to_card_id,)).fetchone()
    if fr is None or to is None:
        raise ValueError("both endpoints must be existing forecast cards")
    if fr["scenario_id"] and fr["scenario_id"] == to["scenario_id"]:
        raise ValueError("belief edges are CROSS-web — within-web dependency is the tree itself")
    p_from = card_marginal(conn, from_card_id)
    p_to = card_marginal(conn, to_card_id)
    p_false = _p_to_if_false(p_to, p_from, p_to_if_from_true)
    if not (0.0 <= p_false <= 1.0):
        raise ValueError(
            f"incoherent edge: P(to|from=true)={p_to_if_from_true:.3f} with to-marginal {p_to:.3f} and "
            f"from-marginal {p_from:.3f} implies P(to|from=false)={p_false:.3f} ∉ [0,1]. Soften the lift "
            f"— an edge must marginalise back to the target's own P (the belief-net sum-check)."
        )
    if (p_to_if_from_true > p_to and sign != 1) or (p_to_if_from_true < p_to and sign != -1):
        raise ValueError("sign must match direction: +1 if from=TRUE raises to, −1 if it lowers it")
    edge = BeliefEdge(from_card_id=from_card_id, to_card_id=to_card_id, sign=sign,
                      p_to_if_from_true=p_to_if_from_true, mechanism=mechanism, kill_criteria=kill_criteria)
    conn.execute(
        "INSERT INTO belief_edges (id, from_card_id, to_card_id, sign, p_to_if_from_true, mechanism, "
        "kill_criteria, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (edge.id, edge.from_card_id, edge.to_card_id, edge.sign, edge.p_to_if_from_true, edge.mechanism,
         json.dumps(edge.kill_criteria), edge.created_at.isoformat()),
    )
    conn.commit()
    return edge


def _short(q: str, n: int = 64) -> str:
    return (q or "")[:n]


def belief_net(conn: sqlite3.Connection, resolved: dict | None = None) -> dict:
    """Read the belief-net: every edge with its baseline + the conditional VIEW of the target given the
    source's state. `resolved` = {from_card_id (or unique prefix): bool}; for a resolved source the
    target's view jumps to the matching conditional. Pure read — never mutates a card. Also reports
    which webs are ISLANDS (touched by no edge) — honest, not every web couples."""
    resolved = _resolve_prefixes(conn, resolved or {})
    rows = conn.execute("SELECT * FROM belief_edges ORDER BY created_at").fetchall()
    edges, touched = [], set()
    for r in rows:
        p_from = card_marginal(conn, r["from_card_id"])
        p_to = card_marginal(conn, r["to_card_id"])
        p_true = r["p_to_if_from_true"]
        p_false = _p_to_if_false(p_to, p_from, p_true)
        view, state = p_to, "prior"
        if r["from_card_id"] in resolved:
            is_true = resolved[r["from_card_id"]]
            view, state = (p_true if is_true else p_false), ("from=TRUE" if is_true else "from=FALSE")
        fq = conn.execute("SELECT question, scenario_id FROM forecast_cards WHERE id=?", (r["from_card_id"],)).fetchone()
        tq = conn.execute("SELECT question, scenario_id FROM forecast_cards WHERE id=?", (r["to_card_id"],)).fetchone()
        touched.update([fq["scenario_id"], tq["scenario_id"]])
        edges.append({
            "from_id": r["from_card_id"], "to_id": r["to_card_id"], "sign": r["sign"],
            "from_q": _short(fq["question"]), "to_q": _short(tq["question"]),
            "p_from": p_from, "p_to_baseline": p_to, "p_if_true": p_true, "p_if_false": p_false,
            "view": view, "state": state, "mechanism": r["mechanism"],
            "kill_criteria": json.loads(r["kill_criteria"]),
        })
    all_roots = [row["id"] for row in conn.execute(
        "SELECT id FROM forecast_cards WHERE id=scenario_id AND superseded_by IS NULL")]
    islands = []
    for root in all_roots:
        if root not in touched:
            q = conn.execute("SELECT question FROM forecast_cards WHERE id=?", (root,)).fetchone()
            islands.append({"root_id": root, "q": _short(q["question"])})
    return {"edges": edges, "islands": islands}


def _resolve_prefixes(conn: sqlite3.Connection, resolved: dict) -> dict:
    """Map {id-or-unique-prefix: bool} to full card ids (ergonomics for the CLI)."""
    out = {}
    for key, val in resolved.items():
        row = conn.execute("SELECT id FROM forecast_cards WHERE id=?", (key,)).fetchone()
        if row is None:
            hits = conn.execute("SELECT id FROM forecast_cards WHERE id LIKE ?", (key + "%",)).fetchall()
            if len(hits) != 1:
                raise ValueError(f"'{key}' matched {len(hits)} cards — use a unique id/prefix")
            row = hits[0]
        out[row["id"]] = val
    return out


def seed_belief_edges(conn: sqlite3.Connection, *, log=print) -> dict:
    """Author the cross-thesis belief edges (question-based, against the active cards). Delegates to
    `rebuild_belief_edges` — see `_ACTIVE_BELIEF_EDGES` for the surviving review-checked edges and the
    record of the two killed ones. $0."""
    return rebuild_belief_edges(conn, log=log)


# --- v2 rebuild: act on the 44/100 external review (2026-06-05) -----------------
# The killed magnet edges (REVIEW 2026-06-05) are recorded in `_v2_specs`' comment + doctrine §1.6:
#   • REE magnets → electrification root (was −0.68): CATEGORY ERROR — transformers/switchgear are
#     grain-oriented electrical steel + copper, NOT NdFeB; magnets bind motors/generators. No channel.
#   • REE magnets → HVDC root (was +0.88): MIS-SIGNED — magnet-starved wind → fewer turbines → LESS
#     HVDC-link demand → eases. Do NOT re-add a magnet edge without a real physical channel.
# Supersede the four v1 webs with corrected versions (re-priced roots; HVDC split flipped; GLP-1
# re-priced + oral-GLP-1 premise-void + tubing un-nested; rare-earth Dy/Tb folded into separation as a
# locus not a sibling) and add the SiC / power-semiconductor web — the genuine cross-vertical hub the
# reviewer pointed to. The webs are immutable (rule 7): we author the v2 trees fresh and stamp the v1
# cards superseded_by the v2 root. Belief edges are re-pointed by QUESTION (resilient to the new ids).

_SIC_WEB = {
    "key": "power-semi-sic",
    "root": dict(
        question=(
            "Through 2029-12-31, does the high-voltage power-electronics buildout (HVDC converters, "
            "grid/solar inverters, EV traction, data-centre power) hit a BINDING silicon-carbide / "
            "power-semiconductor constraint that paces deployment — rather than scaling elastically or "
            "staying adequately served by silicon IGBTs? [structural root, as-of 2026-06-05]"
        ),
        resolution_date=date(2029, 12, 31), probability=0.55,
        thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[2, 3, 4],
        rationale=(
            "STRUCTURAL ROOT (binary gate). The reviewer's call: power conversion is migrating from "
            "iron-and-copper + silicon toward wide-bandgap SiC, and the SiC supply chain is the genuine "
            "INELASTIC INPUT shared across four verticals (HVDC converters ↔ inverters ↔ EV traction ↔ "
            "data-centre power) — less desk-consensus than cable/fill-finish/separation. Root held to 0.55 "
            "(NOT inflated): SiC-vs-Si-IGBT substitution is contested and capacity is ramping hard "
            "(Wolfspeed/Coherent/Resonac/SICC/Infineon 200mm), so the elastic / stays-on-IGBT world is a "
            "real ~0.45. WHICH layer binds is the MECE children, conditional on TRUE."
        ),
        kill_criteria=[
            "By 2029, SiC substrate + device capacity clears power-electronics demand within quoted lead "
            "times with no allocation, and Si IGBT covers the rest — elastic, no binding pace-setter "
            "(root FALSE → conditionals voided, not scored).",
        ],
    ),
    "children": [
        dict(
            question=("Given a binding power-semiconductor constraint, is SiC SUBSTRATE / WAFER supply "
                      "(boule crystal growth + the 150→200mm transition) the binding pace-setter through 2029?"),
            resolution_date=date(2029, 12, 31), probability=0.40,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3],
            rationale=("Deepest, slowest input (0.40): SiC boule growth is slow and low-yield, the 200mm "
                       "transition is hard, and qualified substrate makers are few (Wolfspeed, Coherent, "
                       "Resonac, SICC). The razor under every SiC device."),
            kill_criteria=["SiC wafer lead times stay flat / allocation lifts while another layer is the "
                           "cited bottleneck — substrate was not the pace-setter."],
        ),
        dict(
            question=("Given a binding power-semiconductor constraint, is SiC DEVICE FAB (MOSFET die + "
                      "power-module fabrication + yield) the binding pace-setter through 2029?"),
            resolution_date=date(2029, 12, 31), probability=0.30,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("Fab + yield leg (0.30): even with wafers, qualified automotive/grid-grade SiC "
                       "MOSFET + module fab capacity is scarce and yield-limited."),
            kill_criteria=["SiC device fab output clears module demand on schedule while another layer "
                           "binds — fab was elastic."],
        ),
        dict(
            question=("Given a binding power-semiconductor constraint, is ADVANCED POWER PACKAGING "
                      "(sintered-die, double-sided-cooled modules, substrates) the binding pace-setter "
                      "through 2029?"),
            resolution_date=date(2029, 12, 31), probability=0.18,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("The module-assembly leg (0.18): high-power SiC modules need advanced sintered-die "
                       "packaging + ceramic substrates (AMB), a specialised, capacity-limited step."),
            kill_criteria=["Power-module packaging keeps pace while another layer is cited — packaging was "
                           "not the pace-setter."],
        ),
        dict(
            question=("Given a binding power-semiconductor constraint, does the bottleneck stay in SILICON "
                      "IGBT capacity instead (SiC substitution stalls and high-power conversion remains "
                      "IGBT-paced) through 2029?"),
            resolution_date=date(2029, 12, 31), probability=0.12,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("The substitution-stall leg (0.12): if SiC stays too costly at the highest power "
                       "ratings, the binder remains in legacy Si IGBT/IGCT fab capacity — the constraint "
                       "did not migrate to SiC after all."),
            kill_criteria=["High-power conversion moves decisively to SiC while IGBT supply is ample — the "
                           "bottleneck migrated, IGBT was not the binder."],
        ),
    ],
    "branches": [
        {"under": 0, "children": [
            dict(
                question=("Given SiC substrate is the binding pace-setter, does the 200mm-wafer shortage "
                          "stay TIGHT (allocation / >26-week lead times) sustained through 2029?"),
                resolution_date=date(2029, 12, 31), probability=0.58,
                thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3],
                rationale=("200mm yields ramp slowly and demand front-runs, so the tight regime likely "
                           "holds most of the window (0.58). Harvestable."),
                kill_criteria=["SiC 200mm wafer lead times fall below ~26 weeks before 2029 as yields "
                               "ramp — the substrate constraint eased."],
            ),
            dict(
                question=("Given SiC substrate is the binding pace-setter, does the constraint EASE before "
                          "2029 as 200mm capacity + yields ramp (Wolfspeed/Coherent/Infineon/SICC)?"),
                resolution_date=date(2029, 12, 31), probability=0.42,
                thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3],
                rationale=("Relief tail (0.42): aggressive 200mm capex lands in-window and loosens the "
                           "bottleneck before resolution."),
                kill_criteria=["SiC wafer allocation persists through 2029 — the constraint did not ease."],
            ),
        ]},
    ],
}


def _v2_specs() -> list[dict]:
    """The four corrected webs (re-priced / MECE-fixed) authored fresh to supersede their v1 trees."""
    hvdc = {
        "key": "hvdc-v2",
        "root": dict(
            question=("Through 2029-12-31, does grid + offshore HVDC link deployment hit a BINDING supply "
                      "constraint — a single first-saturating layer that paces installed link-km below the "
                      "announced pipeline — rather than scaling elastically? [structural root v2, "
                      "re-priced 0.85→0.72 on review 2026-06-05]"),
            resolution_date=date(2029, 12, 31), probability=0.72,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
            rationale=("Re-priced 0.85→0.72 (review): multi-constraint is the base rate — a 12-yr cable "
                       "backlog AND a ~60-vessel fleet AND converter queues can co-bind, so 'a SINGLE "
                       "binder' is less certain. Residual ~0.28 = elastic / multi-constraint with no single "
                       "pace-setter. WHICH layer is the MECE children."),
            kill_criteria=["By 2029, installed HVDC link-km tracks the pipeline within ~10% with no layer "
                           "sustaining >90% util / multi-year backlog (root FALSE → conditionals voided)."],
        ),
        "children": [
            dict(question=("Given a binding HVDC constraint, is subsea HVDC CABLE MANUFACTURING (XLPE / "
                           "mass-impregnated extrusion + offshore qualification) the binding pace-setter "
                           "through 2029?"),
                 resolution_date=date(2029, 12, 31), probability=0.38,
                 thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
                 rationale=("Re-weighted UP 0.27→0.38 (review): a reported ~12-yr cable-manufacturing "
                            "backlog + the Prysmian/Nexans/NKT ~75% oligopoly is the HARDER wall — likely "
                            "the truer binder, co-leading with vessels."),
                 kill_criteria=["Cable order books clear within quoted lead times while installation is the "
                                "cited constraint — factory output was elastic."]),
            dict(question=("Given a binding HVDC constraint, is subsea cable-LAY INSTALLATION (CLV fleet "
                           "utilisation + multi-year booking backlog) the binding pace-setter through 2029?"),
                 resolution_date=date(2029, 12, 31), probability=0.38,
                 thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
                 rationale=("Re-weighted DOWN 0.50→0.38 (review): the ~60-vessel fleet is tight, but "
                            "newbuilds are arriving (Prysmian unveiled a new CLV Oct-2025), so not above "
                            "manufacturing."),
                 kill_criteria=["CLV utilisation stays <85% with open 2027-29 slots while another layer is "
                                "the cited bottleneck — vessels were not the pace-setter."]),
            dict(question=("Given a binding HVDC constraint, are HVDC CONVERTER STATIONS (valve-hall power "
                           "semiconductors + large power transformers) the binding pace-setter through 2029?"),
                 resolution_date=date(2029, 12, 31), probability=0.16,
                 thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
                 rationale=("Converters draw on power-semiconductor + large-transformer supply (0.16) — the "
                            "node the SiC web's belief edge attaches to."),
                 kill_criteria=["Converter/transformer lead times stay flat while a marine layer is the "
                                "cited bottleneck — converters were not the pace-setter."]),
            dict(question=("Given a binding HVDC constraint, is PERMITTING / interconnection-queue / seabed "
                           "consenting the binding pace-setter on commissioned link-km through 2029?"),
                 resolution_date=date(2029, 12, 31), probability=0.08,
                 thesis_kind="policy_scarcity", mispricing_kind="horizon_gap", pillars_used=[3, 8],
                 rationale=("Consenting largely precedes the 2025-29 build window for in-construction "
                            "projects, so least likely to bind ON COMMISSIONED km here (0.08)."),
                 kill_criteria=["Projects with secured supply slip purely on permitting in 2026-29 — "
                                "consenting was the live pace-setter."]),
        ],
        "branches": [{"under": 1, "children": [  # intensity split under vessels, re-priced 0.70→0.50
            dict(question=("Given cable-lay vessels are the binding pace-setter, does CLV utilisation stay "
                           ">90% with 12+ month lead times SUSTAINED through 2029?"),
                 resolution_date=date(2029, 12, 31), probability=0.50,
                 thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
                 rationale=("Re-priced 0.70→0.50 (review): newbuild CLVs delivering 2026-28 ease "
                            "utilisation; demand growth offsets — roughly even odds."),
                 kill_criteria=["CLV utilisation falls below 90% before 2028 as newbuilds enter."]),
            dict(question=("Given cable-lay vessels are the binding pace-setter, does the constraint EASE "
                           "before 2029 (utilisation <90%) as newbuild CLVs deliver?"),
                 resolution_date=date(2029, 12, 31), probability=0.50,
                 thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
                 rationale=("Relief tail re-priced UP 0.30→0.50: enough CLV newbuild + conversion lands "
                            "in-window to loosen the bottleneck."),
                 kill_criteria=["Utilisation stays >90% through 2029 — the constraint did not ease."]),
        ]}],
    }
    glp1 = {
        "key": "injectable-v2",
        "root": dict(
            question=("Through 2028-12-31, does the injectable-biologics delivery buildout (GLP-1 pens + "
                      "mAb prefilled syringes) hit a BINDING supply layer downstream of the molecule that "
                      "paces finished-dose output below demand — rather than scaling elastically OR being "
                      "ROUTED AROUND by oral GLP-1? [structural root v2, re-priced 0.80→0.60 + oral "
                      "substitution 2026-06-05]"),
            resolution_date=date(2028, 12, 31), probability=0.60,
            thesis_kind="constraint_migration", mispricing_kind="hype_overpriced", pillars_used=[3, 4, 5],
            premise_void=[
                "Oral GLP-1 (e.g. orforglipron) scaling to route a material share of dose demand AROUND "
                "injectable fill-finish before 2028 = substitution-cascade premise-void: the injectable "
                "chain stops being the pace-setter (the constraint was bypassed, not wrong)."
            ],
            rationale=("Re-priced 0.80→0.60 (review): the fill-finish bottleneck is PRICED (Novo's $11.7bn "
                       "Catalent buy IS the consensus) AND decaying (shortages resolving; capex flooding "
                       "2027-28; oral GLP-1 routing around injectables). mispricing_kind flipped to "
                       "hype_overpriced. Residual ~0.40 = elastic capex + the oral-bypass world."),
            kill_criteria=["By 2028, injectable dose output tracks demand with no layer sustaining >90% "
                           "util / 12+ mo lead times (root FALSE → conditionals voided).",
                           "Oral GLP-1 takes material dose share, bypassing injectable fill-finish (premise-void)."],
        ),
        "children": [
            dict(question=("Given a binding injectable-delivery constraint, is contract STERILE FILL-FINISH "
                           "capacity (aseptic isolator/RABS lines, CDMO) the binding pace-setter through "
                           "2028 — >90% util with 12+ month lead times?"),
                 resolution_date=date(2028, 12, 31), probability=0.45,
                 thesis_kind="constraint_migration", mispricing_kind="hype_overpriced", pillars_used=[3, 4],
                 rationale=("Still the highest-conviction leg (0.45) but priced + decaying — see root."),
                 kill_criteria=["Contract sterile fill-finish utilisation falls below 85% with open slots "
                                "while another layer is cited — fill-finish was elastic."]),
            dict(question=("Given a binding injectable-delivery constraint, is DEVICE / COMBINATION-PRODUCT "
                           "ASSEMBLY (automated autoinjector + pen final assembly) the binding pace-setter "
                           "through 2028?"),
                 resolution_date=date(2028, 12, 31), probability=0.30,
                 thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
                 rationale=("The live GLP-1 tell (0.30): Novo/Lilly were constrained on PEN assembly "
                            "throughput, not molecule."),
                 kill_criteria=["Autoinjector/pen assembly keeps pace while another layer binds."]),
            dict(question=("Given a binding injectable-delivery constraint, is the PRIMARY-CONTAINER + GLASS "
                           "SUPPLY CHAIN (prefilled-syringe / cartridge forming, elastomer, and the "
                           "borosilicate tubing beneath them) the binding pace-setter through 2028?"),
                 resolution_date=date(2028, 12, 31), probability=0.25,
                 thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
                 rationale=("MECE FIX (review): the old web double-counted 'components' and 'tubing' as "
                            "siblings though tubing is the feedstock OF the containers. Now ONE container "
                            "+glass-chain layer (0.25), split by depth below into forming vs tubing."),
                 kill_criteria=["Container + glass supply clears within quoted lead times while another "
                                "layer binds — the glass chain was elastic."]),
        ],
        "branches": [
            {"under": 0, "children": [  # fill-finish intensity, re-priced 0.65→0.45
                dict(question=("Given fill-finish is the binding pace-setter, does it stay >90% util with "
                               "12+ month lead times SUSTAINED through 2028?"),
                     resolution_date=date(2028, 12, 31), probability=0.45,
                     thesis_kind="constraint_migration", mispricing_kind="hype_overpriced", pillars_used=[3, 4],
                     rationale=("Re-priced 0.65→0.45 (review): aseptic capex commissions 2027-28 and oral "
                                "GLP-1 saps demand — more likely to ease than hold."),
                     kill_criteria=["Fill-finish utilisation falls below 90% before 2028 as lines qualify."]),
                dict(question=("Given fill-finish is the binding pace-setter, does the constraint EASE "
                               "before 2028 as CDMO aseptic capacity qualifies / oral GLP-1 saps demand?"),
                     resolution_date=date(2028, 12, 31), probability=0.55,
                     thesis_kind="constraint_migration", mispricing_kind="hype_overpriced", pillars_used=[3, 4],
                     rationale=("Now the LIKELIER leg (0.55): capex + oral substitution loosen it in-window."),
                     kill_criteria=["Utilisation stays >90% through 2028 — did not ease."]),
            ]},
            {"under": 2, "children": [  # the un-nested glass sub-layer: forming vs tubing (the MECE fix)
                dict(question=("Given the container+glass chain is the binding pace-setter, is the binding "
                               "in BARREL/CARTRIDGE FORMING + finishing capacity (the container fabrication "
                               "step) through 2028?"),
                     resolution_date=date(2028, 12, 31), probability=0.55,
                     thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
                     rationale=("Forming/finishing (Gerresheimer/SCHOTT/Stevanato/West) is the nearer wall "
                                "(0.55) — PFS forming + siliconization + stoppers."),
                     kill_criteria=["Container forming clears while upstream tubing is the cited bind."]),
                dict(question=("Given the container+glass chain is the binding pace-setter, is the binding "
                               "deeper, in BOROSILICATE TYPE-I TUBING draw (the glass feedstock) through 2028?"),
                     resolution_date=date(2028, 12, 31), probability=0.45,
                     thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[3, 4],
                     rationale=("The razor under the razor (0.45): pharma-grade borosilicate tubing (SCHOTT/"
                                "Corning/Nipro/NEG) on multi-year furnaces — now correctly NESTED as the "
                                "deeper sub-layer, not a sibling of its own output."),
                     kill_criteria=["Tubing supply stays ample while forming is the cited bind."]),
            ]},
        ],
    }
    rare = {
        "key": "rare-earth-v2",
        "root": dict(
            question=("Through 2029-12-31, does allied (ex-China) supply of export-controlled critical "
                      "inputs hit a BINDING non-China LAYER (single-axis: mine vs separation vs "
                      "magnet-making) that paces qualified Western availability below demand? [structural "
                      "root v2, MECE single-axis fix 2026-06-05; PREMISE-VOID on a China rescind]"),
            resolution_date=date(2029, 12, 31), probability=0.82,
            thesis_kind="policy_scarcity", mispricing_kind="layer_blindness", pillars_used=[3, 4, 8],
            premise_void=["A Chinese rescission / relaxation of the export controls before 2029 removes the "
                          "decreed scarcity — resolve PREMISE-VOID, not Brier-wrong."],
            rationale=("Root P held at 0.82 (review agreed this one is right). MECE FIX: dropped the "
                       "'heavy-REE Dy/Tb' child — it mixed an ELEMENT axis with the LAYER axis. Heavy-REE "
                       "is now a LOCUS WITHIN separation, named in that child's rationale, not a sibling. "
                       "Clean single-axis layers: mine / separation / magnet-making."),
            kill_criteria=["By 2029, ex-China qualified availability tracks demand with no midstream layer "
                           "sustaining an origin premium (root FALSE → voided).",
                           "A Chinese rescission before 2029 = premise-void, not FALSE."],
        ),
        "children": [
            dict(question=("Given a binding ex-China constraint, is SEPARATION / REFINING capacity "
                           "(solvent-extraction oxide separation, with the heavy-REE Dy/Tb fraction the "
                           "tightest locus within it) the binding pace-setter through 2029?"),
                 resolution_date=date(2029, 12, 31), probability=0.52,
                 thesis_kind="policy_scarcity", mispricing_kind="layer_blindness", pillars_used=[3, 4],
                 rationale=("Highest-conviction (0.52, absorbs the old Dy/Tb weight): ex-China separation — "
                            "especially the heavy-REE Dy/Tb fraction (the locus, not a separate layer) — is "
                            "near-absent and know-how gated."),
                 kill_criteria=["By 2028, ex-China separated/refined output share rises >10pp toward parity "
                                "while another layer is cited — separation was not the pace-setter."]),
            dict(question=("Given a binding ex-China constraint, is METAL / ALLOY + SINTERED-MAGNET "
                           "MANUFACTURING (metallization + NdFeB magnet capacity) the binding pace-setter "
                           "through 2029?"),
                 resolution_date=date(2029, 12, 31), probability=0.34,
                 thesis_kind="policy_scarcity", mispricing_kind="layer_blindness", pillars_used=[3, 4],
                 rationale=("Downstream chokepoint (0.34): ex-China metallization + sintered-NdFeB capacity "
                            "(VAC, MP Texas) is tiny and slow to qualify."),
                 kill_criteria=["Ex-China magnet output scales to demand on schedule while another binds."]),
            dict(question=("Given a binding ex-China constraint, is MINE / CONCENTRATE feedstock supply the "
                           "binding pace-setter through 2029 (the layer-blindness control)?"),
                 resolution_date=date(2029, 12, 31), probability=0.14,
                 thesis_kind="policy_scarcity", mispricing_kind="layer_blindness", pillars_used=[3, 4],
                 rationale=("The control (0.14): consensus over-funds mining but ex-China mine projects are "
                            "plentiful — the thesis is mines are NOT the binder."),
                 kill_criteria=["A mine/concentrate shortfall (not midstream) is the cited Western "
                                "constraint — the layer-blindness thesis was wrong."]),
        ],
        "branches": [{"under": 0, "children": [
            dict(question=("Given ex-China separation is the binding pace-setter, does the ex-China-origin "
                           "price premium PERSIST sustained through 2029?"),
                 resolution_date=date(2029, 12, 31), probability=0.62,
                 thesis_kind="policy_scarcity", mispricing_kind="layer_blindness", pillars_used=[3, 4],
                 rationale=("Separation capacity qualifies 2028+, so the premium likely holds (0.62). "
                            "Harvestable."),
                 kill_criteria=["The ex-China-origin premium falls below ~15% while controls persist "
                                "before 2029 — the constraint dissolved faster than predicted."]),
            dict(question=("Given ex-China separation is the binding pace-setter, does the constraint EASE "
                           "before 2029 (premium <15%) as subsidised refining qualifies?"),
                 resolution_date=date(2029, 12, 31), probability=0.38,
                 thesis_kind="policy_scarcity", mispricing_kind="layer_blindness", pillars_used=[3, 4],
                 rationale=("Relief tail (0.38): DPA/IRA + Australia/EU + recycling compress the premium."),
                 kill_criteria=["Origin premium stays >15% through 2029 — did not ease."]),
        ]}],
    }
    elec = {
        "key": "electrification-v2",
        "root": dict(
            question=("Through 2028-12-31, does the US electrification binder migrate OFF equipment "
                      "(transformers/switchgear) to a non-equipment layer that paces project completion? "
                      "[structural root v2, re-priced 0.78→0.68 on review 2026-06-05]"),
            resolution_date=date(2028, 12, 31), probability=0.68,
            thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[4, 5, 8],
            rationale=("Re-priced 0.78→0.68 (review): as of mid-2026 transformer lead times are STILL "
                       "rising (~128 weeks), so betting the binder has fully migrated off equipment by "
                       "2028 is less certain — the migration may be mid-flight at resolution. Residual "
                       "~0.32 = equipment stays the binder / elastic."),
            kill_criteria=["By 2028, equipment lead-times remain the single cited bottleneck and no "
                           "non-equipment layer paces completion (root FALSE → voided)."],
        ),
        "children": [
            dict(question=("Given the binder has migrated off equipment, is LICENSED ELECTRICAL-TRADES "
                           "LABOUR (electricians SOC 47-2111, linemen 49-9051, HV commissioning) the "
                           "binding pace-setter on US electrification through 2028?"),
                 resolution_date=date(2028, 12, 31), probability=0.50,
                 thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[5],
                 rationale=("Highest-conviction (0.50) + the only genuinely pre-consensus metric in the "
                            "set (per review): apprenticeship-gated (~4-5y), aging, non-importable."),
                 kill_criteria=["By 2028, real electrician wage growth (BLS CES/OES 47-2111) does NOT "
                                "exceed large-power-transformer PPI growth over 2025-2028 — labour is not "
                                "the tighter constraint."]),
            dict(question=("Given the binder has migrated off equipment, is INTERCONNECTION-QUEUE / "
                           "transmission-permitting throughput the binding pace-setter through 2028?"),
                 resolution_date=date(2028, 12, 31), probability=0.27,
                 thesis_kind="policy_scarcity", mispricing_kind="layer_blindness", pillars_used=[8],
                 rationale=("Strong alternative (0.27): interconnection-queue durations can pace energized "
                            "MW independent of labour."),
                 kill_criteria=["Median interconnection-queue duration falls while another layer is cited."]),
            dict(question=("Given the binder has migrated off equipment, is CAPITAL / FINANCING (rate-"
                           "driven cost of capital) the binding pace-setter through 2028?"),
                 resolution_date=date(2028, 12, 31), probability=0.13,
                 thesis_kind="regime_change", mispricing_kind="horizon_gap", pillars_used=[6],
                 rationale=("The macro leg (0.13): a higher-for-longer regime can gate financeability."),
                 kill_criteria=["Projects proceed despite the rate environment while a physical layer is cited."]),
            dict(question=("Given the binder has migrated off equipment-supply, is specialised EPC / "
                           "heavy-construction CAPACITY the binding pace-setter through 2028?"),
                 resolution_date=date(2028, 12, 31), probability=0.10,
                 thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[4],
                 rationale=("Execution-capacity leg (0.10): substation EPC firm capacity is finite."),
                 kill_criteria=["Substation EPC throughput keeps pace while another layer is cited."]),
        ],
        "branches": [{"under": 0, "children": [
            dict(question=("Given trades labour is the binding pace-setter, does the electrician wage "
                           "premium over equipment PPI PERSIST / widen through 2028?"),
                 resolution_date=date(2028, 12, 31), probability=0.65,
                 thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[5],
                 rationale=("Apprenticeship completions lag ~4-5y, so the gap likely persists (0.65). "
                            "Harvestable."),
                 kill_criteria=["Registered electrician apprenticeship completions (DOL RAPIDS) rise >25% "
                                "vs 2024 and close the wage gap before 2028."]),
            dict(question=("Given trades labour is the binding pace-setter, does the constraint EASE before "
                           "2028 as prefab/modular shifts hours out of the licensed field?"),
                 resolution_date=date(2028, 12, 31), probability=0.35,
                 thesis_kind="constraint_migration", mispricing_kind="layer_blindness", pillars_used=[5],
                 rationale=("Relief tail (0.35): factory-skid substations + prefab + visa expansion."),
                 kill_criteria=["The electrician wage premium over transformer PPI persists through 2028."]),
        ]}],
    }
    return [hvdc, glp1, rare, elec, _SIC_WEB]


_V1_ROOTS_TO_RETIRE = [_HVDC_ROOT_Q, _FILLFINISH_ROOT_Q,
                       _RAREEARTH_WEB["root"]["question"], _ELECTRIFICATION_WEB["root"]["question"]]
# v2 root questions, in the same order as _V1_ROOTS_TO_RETIRE, so each v1 web is superseded into its v2.
_V1_TO_V2 = [(0, "hvdc-v2"), (1, "injectable-v2"), (2, "rare-earth-v2"), (3, "electrification-v2")]


def _active_card_by_q(conn: sqlite3.Connection, like: str) -> str:
    row = conn.execute(
        "SELECT id FROM forecast_cards WHERE question LIKE ? AND superseded_by IS NULL", (like + "%",)
    ).fetchall()
    if len(row) != 1:
        raise ValueError(f"'{like[:40]}' matched {len(row)} active cards — need exactly 1")
    return row[0]["id"]


def rebuild_v2(conn: sqlite3.Connection, *, log=print) -> dict:
    """Act on the 44/100 review: author the 4 corrected webs + SiC, supersede the v1 webs, re-point the
    belief-net by question. Idempotent — once v2 exists and v1 is retired, re-running is a no-op. $0."""
    specs = _v2_specs()
    by_key = {s["key"]: s for s in specs}
    made = 0
    for s in specs:
        made += seed_web(conn, s, log=log)["created"]

    # supersede each v1 web into its v2 root (rule 7 — the v1 cards stay, stamped superseded_by).
    for v1_idx, v2_key in _V1_TO_V2:
        v1_root_q = _V1_ROOTS_TO_RETIRE[v1_idx]
        v1 = conn.execute("SELECT id FROM forecast_cards WHERE question=? AND id=scenario_id", (v1_root_q,)).fetchone()
        v2 = conn.execute("SELECT id FROM forecast_cards WHERE question=? AND id=scenario_id",
                          (by_key[v2_key]["root"]["question"],)).fetchone()
        if v1 and v2:
            n = conn.execute(
                "UPDATE forecast_cards SET superseded_by=? WHERE scenario_id=? AND superseded_by IS NULL",
                (v2["id"], v1["id"]),
            ).rowcount
            if n:
                log(f"retired v1 web {v1['id'][:8]} ({n} cards) → v2 {v2['id'][:8]} [{v2_key}]")
    conn.commit()

    e_made = rebuild_belief_edges(conn, log=log)["created"]
    return {"webs_created": made, "edges": e_made}


# The belief-net edges, by QUESTION (resilient to the v2 re-author). Two survive the review: the
# trades-labour→converters edge (trimmed) and the SiC→converters HUB edge (a physically-real shared
# input, unlike the killed magnet edges). Endpoints resolve to whichever card is ACTIVE.
_ACTIVE_BELIEF_EDGES = [
    dict(from_like="Given the binder has migrated off equipment, is LICENSED ELECTRICAL-TRADES LABOUR",
         to_like="Given a binding HVDC constraint, are HVDC CONVERTER STATIONS",
         sign=1, p_to_if_from_true=0.16,
         mechanism=("HVDC converter stations are commissioned partly by the same licensed HV electricians "
                    "the electrification web names as the binding US input (though much is specialised OEM "
                    "teams — a modest lift). The surviving review-checked labour edge."),
         kill_criteria=["US HVDC converters are delivered on schedule while US trades labour is the cited "
                        "electrification bottleneck — pools not co-binding."]),
    dict(from_like="Through 2029-12-31, does the high-voltage power-electronics buildout",  # SiC root
         to_like="Given a binding HVDC constraint, are HVDC CONVERTER STATIONS",
         sign=1, p_to_if_from_true=0.20,
         mechanism=("REAL shared inelastic input (the reviewer's hub): HVDC converter stations are built "
                    "from high-power semiconductor modules (Si IGBT today, migrating to SiC). If the "
                    "power-semiconductor buildout hits a binding constraint, the semiconductor-intensive "
                    "converter layer is more likely to bind. A physically-grounded channel, unlike the "
                    "killed magnet edges."),
         kill_criteria=["The power-semiconductor buildout binds while HVDC converters are delivered on "
                        "schedule — converters were not semiconductor-paced, the channel was wrong."]),
]


def rebuild_belief_edges(conn: sqlite3.Connection, *, log=print) -> dict:
    """Re-point the belief-net against the currently-ACTIVE cards (resolve endpoints by question).
    Drops all edges and re-adds — so it self-heals after a web re-author. $0."""
    conn.execute("DELETE FROM belief_edges")
    conn.commit()
    made = 0
    for e in _ACTIVE_BELIEF_EDGES:
        fid = _active_card_by_q(conn, e["from_like"])
        tid = _active_card_by_q(conn, e["to_like"])
        add_belief_edge(conn, from_card_id=fid, to_card_id=tid, sign=e["sign"],
                        p_to_if_from_true=e["p_to_if_from_true"], mechanism=e["mechanism"],
                        kill_criteria=e["kill_criteria"])
        made += 1
        log(f"belief edge {fid[:8]}→{tid[:8]} sign {e['sign']:+d}")
    return {"created": made}


# --- the forward batch: a dozen standalone structural calls (the starved instrument) ----------
# The repo was over-built and starved of calls. This is the deliverable the Definition-of-Done wants:
# a dozen FORWARD, falsifiable, physical-primary, one-layer-deeper structural calls — each with P + an
# 80% interval + a dated resolution metric + kill-criteria, adversarially challenged in-session (the
# disconfirmer lives in each rationale, doctrine §2.6). Reasoning is Claude's (in-session); the machine
# only records + later scores. Several resolve on REAL series already in the DB (so driver-status can
# track them NOW); others resolve on a named public metric. Idempotent on the question. $0.
#
# Calibration stance: probabilities are deliberately humble (0.5–0.72). The edge is the LAYER (where
# rent lands), not certainty about the level. A contrarian call (hype_overpriced) gets its value from
# DIRECTION against consensus, not from obscurity.

_FORWARD_BATCH: list[dict] = [
    # 1 — GOES electrical steel is the binding layer of electrification, not transformers.
    dict(
        question=("By 2028-12-31, does US grain-oriented electrical-steel (GOES) import partner-"
                  "concentration (HHI) stay ≥ 0.55 — rent of electrification lands on the concentrated "
                  "steel layer, not the diversified transformer-assembly layer?"),
        resolution_date=date(2028, 12, 31), probability=0.72,
        ci_low=0.50, ci_high=0.70, ci_unit="import HHI", threshold=0.55, threshold_dir=">=",
        thesis_kind="constraint_migration", mispricing_kind="layer_blindness",
        seed_series_id="502ff7264a694f9387257835a2bc8a3e", pillars_used=[3, 4], saturation=0.30,
        rationale=(
            "OBVIOUS/PRICED: the transformer shortage (transformer-PPI already elevated; transformer "
            "import HHI is LOW ~0.09 = many suppliers = elastic). DEEPER: GOES is the inelastic input — "
            "import HHI 0.615, one US producer (Cleveland-Cliffs), multi-year qualification. Rent lands "
            "on the steel, not the assemblers. DISCONFIRMER: a new GOES line (India/Korea) or amorphous-"
            "metal substitution could diversify supply — but both are >3y out. Base rate for a single-"
            "producer, slow-to-qualify material staying concentrated over 2y is high."),
        kill_criteria=["GOES import HHI falls below 0.55 by 2028 (supply diversified — steel was not "
                       "the binding layer)."],
        premise_void=["A demand collapse in grid/transformer build (AI capex retrenchment) shrinks GOES "
                      "demand so concentration is moot — premise void, not wrong."],
    ),
    # 2 — heavy-duty gas turbines pace AI/datacenter firm power (PHYSICAL: slot lead-time, not GEV revenue).
    dict(
        question=("By 2027-12-31, does the quoted delivery lead-time for a new heavy-duty (≥100 MW, F/H-"
                  "class) gas turbine remain ≥ 3 years (next available OEM slot in 2030+) — turbine SLOTS, "
                  "not generation broadly, are the binding pace-setter for AI firm power?"),
        resolution_date=date(2027, 12, 31), probability=0.72,
        ci_low=2.5, ci_high=5.0, ci_unit="years delivery lead-time", threshold=3.0, threshold_dir=">=",
        thesis_kind="constraint_migration", mispricing_kind="layer_blindness",
        pillars_used=[4, 6], saturation=0.42, securitizable=True,
        rationale=(
            "OBVIOUS/PRICED: 'AI needs power' (IEA/banks already forecast datacenter load). DEEPER: the "
            "binding input is FIRM dispatchable power = heavy-duty gas turbines, and the big-three (GE "
            "Vernova, Siemens Energy, Mitsubishi) are booked to ~2028-2029 — turbine SLOTS, not MW in the "
            "abstract, are the constraint. PHYSICAL METRIC: the delivery lead-time / next-available-slot "
            "year (OEM disclosures + trade press: Reuters, S&P Global), NOT any one OEM's revenue (which "
            "blends share, pricing, execution). Instrument = GEV/Siemens Energy/Mitsubishi (side-tag). "
            "DISCONFIRMER: behind-the-meter solar+storage or SMRs could substitute — but neither delivers "
            "24/7 firm power at datacenter scale this decade."),
        kill_criteria=["Heavy-duty gas-turbine lead-time falls below 3 years (slots open up) — turbine "
                       "supply was elastic, not the binding pace-setter."],
        premise_void=["A sharp AI-capex retrenchment cancels datacenter power orders — premise void."],
        supersedes_question=("By FY2027, does GE Vernova (GEV) Power-segment revenue exceed $20B — heavy-duty gas "
                  "turbines, not generation broadly, are the binding pace-setter for AI firm power?"),
    ),
    # 3 — ex-China NdFeB magnet MAKING is the binding layer; China export controls are its footprint.
    dict(
        question=("By 2028-12-31, has China's permanent-magnet (NdFeB) export VALUE fallen ≥ 25% below "
                  "its 2023 level — Oct-2025 export controls + decoupling making ex-China magnet-MAKING "
                  "(not ore, not oxides) the binding constraint?"),
        resolution_date=date(2028, 12, 31), probability=0.60,
        ci_low=-0.55, ci_high=0.05, ci_unit="Δ vs 2023 China magnet-export value (fraction)",
        threshold=-0.25, threshold_dir="<=",
        thesis_kind="policy_scarcity", mispricing_kind="layer_blindness",
        seed_series_id="f2edb9864f8f481da35007386a337460", pillars_used=[3, 8], saturation=0.45,
        rationale=(
            "OBVIOUS/PRICED: rare-earth ORE / mining (MP Materials repriced after the Oct-2025 China "
            "megacontrol). DEEPER: China makes ~90% of SINTERED NdFeB magnets — the binding layer is "
            "magnet FABRICATION ex-China, not the element. The realized footprint of that chokepoint is "
            "China's own magnet exports declining as it weaponizes the cornered step. DISCONFIRMER: China "
            "could keep exporting magnets (rents from selling finished goods) while restricting only ore — "
            "then exports DON'T fall. Genuinely two-sided; hence P 0.60, not higher."),
        kill_criteria=["China magnet-export value is within 25% of (or above) its 2023 level at 2028 — "
                       "the chokepoint did not bind exports."],
        premise_void=["China fully rescinds the Oct-2025 controls (policy reversal) — premise void, not "
                      "a wrong read of the constraint."],
    ),
    # 4 — CONTRARIAN: SiC substrate rent is hype-overpriced (PHYSICAL: substrate ASP, not WOLF revenue).
    dict(
        question=("By 2026-12-31, is the 150mm SiC substrate average selling price ≥ 20% BELOW its 2023 "
                  "level (Yole/TrendForce) — substrate is over-supplied and the rent fails to materialize, "
                  "so the 2021-23 'SiC is THE EV bottleneck' narrative was hype-overpriced?"),
        resolution_date=date(2026, 12, 31), probability=0.68,
        ci_low=-0.45, ci_high=0.00, ci_unit="Δ 150mm SiC substrate ASP vs 2023 (fraction)",
        threshold=-0.20, threshold_dir="<=",
        thesis_kind="substitution_cascade", mispricing_kind="hype_overpriced",
        pillars_used=[2, 5], saturation=0.40, securitizable=True,
        rationale=(
            "The 'cuts both ways' call: a LONG-DATED, HOT narrative is over-priced, not under-priced. SiC "
            "substrate was hyped as THE EV-electrification bottleneck (2021-23). REALITY: EV demand "
            "decelerated, 200mm capacity flooded in, silicon IGBT + GaN substitute at lower voltages — so "
            "the price of the supposed chokepoint FALLS, the scarcity signal of an over-supplied layer. "
            "PHYSICAL METRIC: 150mm substrate ASP (Yole/TrendForce wafer-price tracking), NOT Wolfspeed's "
            "revenue (an idiosyncratic near-insolvency story). Instrument = WOLF (side-tag, distressed). "
            "DISCONFIRMER: an EV reacceleration + 800V adoption could tighten SiC again — possible, hence "
            "P 0.68 not 0.9."),
        kill_criteria=["150mm SiC substrate ASP holds within 20% of (or above) its 2023 level — substrate "
                       "scarcity was real; the bottleneck thesis held."],
        supersedes_question=("By FY2027, does Wolfspeed (WOLF) annual revenue stay BELOW $1.2B — silicon-carbide "
                  "substrate rent fails to materialize as the 2021-23 narrative claimed (hype-overpriced)?"),
    ),
    # 5 — medical isotope supply binds radioligand therapy (PHYSICAL: Ac-225 supply still rationed, not "cited").
    dict(
        question=("By 2029-12-31, does global actinium-225 (Ac-225) supply remain allocation-constrained — "
                  "no new high-volume route (DOE tri-lab accelerator, SHINE, TRIUMF) has reached routine "
                  "multi-Curie commercial supply that ends clinical dose-rationing (DOE/IAEA reporting) — "
                  "confirming the isotope layer, not the targeting molecule, is the binding constraint on "
                  "radioligand therapy?"),
        resolution_date=date(2029, 12, 31), probability=0.60,
        thesis_kind="constraint_migration", mispricing_kind="layer_blindness",
        pillars_used=[3, 5], saturation=0.35, securitizable=False,
        rationale=(
            "OBVIOUS/PRICED: the radioligand boom (Novartis Pluvicto/Lutathera). DEEPER: global Ac-225 "
            "supply is single-grams/year (a handful of legacy Th-229 sources) and Lu-177 reactor capacity "
            "is tight — the isotope, not the antibody/peptide, is the inelastic razor-blade. PHYSICAL "
            "METRIC: whether a new route reaches routine multi-Curie supply that ends allocation (an "
            "observable DOE/IAEA status), NOT the vague 'is it still cited' of the prior wording — and not "
            "a drug-maker's revenue. DISCONFIRMER: DOE's Ac-225 tri-lab program + new accelerator routes "
            "(TRIUMF, SHINE) could relieve it by 2029 — a real path, hence P 0.60."),
        kill_criteria=["A new Ac-225 (or Lu-177) production route reaches routine multi-Curie commercial "
                       "supply that ends dose-rationing by 2029 — the isotope no longer paces therapy launches."],
        supersedes_question=("By 2029-12-31, is medical-isotope production (actinium-225 / lutetium-177) still the "
                  "cited binding constraint on radioligand-therapy scale-up — rent on the isotope layer, "
                  "not the targeting molecule?"),
    ),
    # 6 — narrow-body aero-engine MRO + spares binds, not new aircraft (PHYSICAL: fleet age, not GE revenue).
    dict(
        question=("By 2027-12-31, does the global commercial passenger-jet fleet average age remain ≥ 12.0 "
                  "years (Cirium) — delivery shortfalls force airlines to fly older fleets longer, so engine "
                  "shop-visit & spare-parts capacity (the aftermarket), not new-aircraft delivery, is where "
                  "capacity binds?"),
        resolution_date=date(2027, 12, 31), probability=0.66,
        ci_low=11.5, ci_high=13.0, ci_unit="years avg fleet age", threshold=12.0, threshold_dir=">=",
        thesis_kind="constraint_migration", mispricing_kind="layer_blindness",
        pillars_used=[5, 6], saturation=0.45, securitizable=True,
        rationale=(
            "OBVIOUS/PRICED: the Boeing/Airbus delivery shortfall. DEEPER: with new jets scarce and LEAP/"
            "GTF showing premature blade/coating wear, airlines fly OLD fleets longer → engine shop-visit "
            "and spare-parts capacity bind, and the OEM aftermarket (GE Aerospace, RTX) captures the rent. "
            "PHYSICAL METRIC: the fleet's average AGE (Cirium) — the direct symptom of the binding "
            "aftermarket — not any OEM's revenue. Instrument = GE Aerospace / RTX (side-tag). DISCONFIRMER: "
            "a delivery catch-up at Boeing/Airbus would let airlines retire old jets and lower fleet age — "
            "but their ramps keep slipping. P 0.66."),
        kill_criteria=["Global fleet average age falls below 12.0 years by 2027 — deliveries caught up and "
                       "the aftermarket was not the binding layer."],
        supersedes_question=("By FY2027, does GE Aerospace (GE) total revenue exceed $45B with commercial SERVICES "
                  "the majority — aftermarket/spares rent from the aging + LEAP/GTF-durability fleet, "
                  "not new-aircraft delivery, is where capacity binds?"),
    ),
    # 7 — datacenter liquid cooling (PHYSICAL: attach-rate on new AI servers, not Vertiv revenue).
    dict(
        question=("By 2027-12-31, does the liquid-cooling attach rate on new AI-accelerator server "
                  "deployments exceed 40% (Dell'Oro/IDC) — >100 kW racks force direct-to-chip liquid "
                  "cooling, so the thermal layer becomes mandatory datacenter infrastructure?"),
        resolution_date=date(2027, 12, 31), probability=0.62,
        ci_low=0.25, ci_high=0.60, ci_unit="liquid-cooling attach rate (fraction)",
        threshold=0.40, threshold_dir=">=",
        thesis_kind="constraint_migration", mispricing_kind="layer_blindness",
        seed_series_id="9cf3bd9af6424706889902aebfce25b5", pillars_used=[4, 6], saturation=0.52,
        securitizable=True,
        rationale=(
            "OBVIOUS/PRICED: GPUs (NVDA). DEEPER: GB200-class racks (>100 kW) make air cooling physically "
            "impossible → direct-to-chip liquid cooling + CDUs become mandatory infrastructure. PHYSICAL "
            "METRIC: the liquid-cooling ATTACH RATE on new AI servers (Dell'Oro/IDC) — the adoption of the "
            "mandatory layer itself — not Vertiv's revenue (which blends pricing/share/segments). HONEST: "
            "this layer is now WELL-COVERED (saturation 0.52 — the cooling names re-rated hard), so it is "
            "PARTLY priced; the call is whether adoption goes mainstream. Instrument = Vertiv et al. "
            "(side-tag). DISCONFIRMER: cheaper rear-door heat-exchangers or hyperscaler in-housing could "
            "slow direct-to-chip attach. P 0.62."),
        kill_criteria=["Liquid-cooling attach rate on new AI servers stays below 30% through 2027 — air "
                       "cooling held; the thermal layer was not the binding mandatory infrastructure."],
        supersedes_question=("By FY2027, does Vertiv (VRT) annual revenue exceed $12B — rising rack power density "
                  "(>100 kW) forces liquid cooling, and the thermal layer captures durable datacenter rent?"),
    ),
    # 8 — electrical-trades LABOUR binds US electrification, not equipment.
    dict(
        question=("By 2028, does US electrician (BLS SOC 47-2111) median-wage growth over 2024→2028 "
                  "exceed the growth in the power-&-distribution-transformer PPI over the same window — "
                  "skilled LABOUR, not equipment, is the binding electrification cost?"),
        resolution_date=date(2028, 12, 31), probability=0.58,
        thesis_kind="constraint_migration", mispricing_kind="layer_blindness",
        seed_series_id="fc04fb798c1e42409222408439f0b618", pillars_used=[4, 5], saturation=0.30,
        rationale=(
            "OBVIOUS/PRICED: equipment shortages (transformers, switchgear). DEEPER: you cannot install "
            "the grid without electricians + linemen, an aging trade with a thin apprenticeship pipeline "
            "and no import substitute (labour is the most inelastic input of all). As equipment PPI "
            "eventually mean-reverts (capacity is being added), WAGE growth persists. DISCONFIRMER: a "
            "construction-demand recession would slacken trades wages faster than equipment — possible, "
            "hence a humble P 0.58."),
        kill_criteria=["Electrician median-wage growth lags transformer-PPI growth over 2024→2028 — "
                       "equipment, not labour, stayed the binding cost."],
    ),
    # 9 — the interconnection QUEUE, not generation hardware, paces US power deployment.
    dict(
        question=("By 2028-12-31, does the median US interconnection-queue duration for completed "
                  "projects remain ≥ 4 years (LBNL/Berkeley-Lab data) — the QUEUE + transmission, not "
                  "panels/turbines, is the binding constraint on new power?"),
        resolution_date=date(2028, 12, 31), probability=0.70,
        ci_low=3.0, ci_high=6.0, ci_unit="years median queue duration", threshold=4.0, threshold_dir=">=",
        thesis_kind="policy_scarcity", mispricing_kind="layer_blindness",
        pillars_used=[4, 8], saturation=0.40,
        rationale=(
            "OBVIOUS/PRICED: the clean-energy + datacenter buildout (generation hardware). DEEPER: ~2.6 TW "
            "sits in interconnection queues and the median completed project now waits ~5 years; the "
            "binding constraint is the QUEUE / transmission / study process, not the panels or turbines. "
            "FERC Order 2023 aims to speed it. DISCONFIRMER: queue reform + cluster studies could cut "
            "durations below 4y by 2028 — a real reform path, hence P 0.70 not higher."),
        kill_criteria=["Median completed-project queue duration falls below 4 years by 2028 — the "
                       "process bottleneck was relieved."],
    ),
    # 10 — HALEU domestic enrichment binds the advanced-reactor rollout (PHYSICAL: HALEU kg/yr, not LEU revenue).
    dict(
        question=("By 2029-12-31, does US domestic HALEU (high-assay low-enriched uranium) annual "
                  "production remain below 2,000 kg/yr (DOE/Centrus reporting) — domestic enrichment "
                  "capacity, not reactor designs, stays the binding constraint on advanced nuclear?"),
        resolution_date=date(2029, 12, 31), probability=0.55,
        ci_low=600.0, ci_high=3000.0, ci_unit="kg/yr US HALEU production", threshold=2000.0,
        threshold_dir="<=",
        thesis_kind="constraint_migration", mispricing_kind="horizon_gap",
        seed_series_id="42060cb51a20482380f1c9da6faacc4e", pillars_used=[3, 8], saturation=0.42,
        securitizable=True,
        rationale=(
            "OBVIOUS/PRICED: the SMR / nuclear-renaissance narrative (hot, long-dated). DEEPER: advanced "
            "reactors need HALEU (19.75% enriched); Centrus is the ONLY licensed US producer and Russia "
            "was the dominant supplier (now sanctioned). PHYSICAL METRIC: domestic HALEU OUTPUT in kg/yr "
            "(DOE/Centrus) — the enrichment capacity itself — not Centrus's revenue. The binding-constraint "
            "claim = the scale-up STAYS short of the announced fleet's need through 2029. HORIZON-GAP: the "
            "reactors are 2030s, so enrichment is the near-term binding step. DISCONFIRMER: a DOE-funded "
            "ramp could push output past 2,000 kg/yr — genuine, hence P 0.55."),
        kill_criteria=["US domestic HALEU production exceeds 2,000 kg/yr by 2029 — enrichment scaled and "
                       "was not the binding constraint."],
        premise_void=["Advanced-reactor demand itself slips so HALEU is never drawn down — the enrichment "
                      "constraint is untested, premise void, not a wrong read."],
        supersedes_question=("By 2029-12-31, does Centrus (LEU) annual revenue exceed $1B — domestic HALEU / "
                  "enrichment capacity, not reactor designs, is the binding constraint on advanced nuclear?"),
    ),
    # 11 — CONTRARIAN: copper is over-priced vs the deeper electrical-steel layer (ties to the locator finding).
    dict(
        question=("By 2028-12-31, does US copper mill-products PPI stay BELOW 175 — refined-copper rent "
                  "stays bounded; the 'copper is THE metal of electrification' supercycle is over-priced "
                  "relative to the deeper electrical-steel/equipment layer?"),
        resolution_date=date(2028, 12, 31), probability=0.55,
        ci_low=130.0, ci_high=190.0, ci_unit="copper mill-products PPI", threshold=175.0, threshold_dir="<=",
        thesis_kind="cost_curve_breakout", mispricing_kind="hype_overpriced",
        seed_series_id="ef2233d8714d4f7baeb3496f802135f2", pillars_used=[3, 4], saturation=0.55,
        rationale=(
            "Grounded in the repo's OWN locator finding: copper accelerated PRE-2016 (already in the trend "
            "= priced), while the post-2021 rent landed on GOES electrical steel (the regime change). "
            "CONSENSUS: a copper supercycle (datacenters + EVs + grid). CLAIM: copper supply is more "
            "elastic than the bulls think (scrap, substitution to aluminium in wire, new mine supply) and "
            "copper-PPI rent stays bounded relative to the truly inelastic electrical-steel layer. "
            "DISCONFIRMER: a genuine mine-supply shortfall + grid demand could break copper out above 175 "
            "— a real risk, hence a near-coin-flip P 0.55. This is the honest contrarian leg."),
        kill_criteria=["Copper mill-products PPI breaks above 175 by 2028 — the copper supercycle was "
                       "real and not over-priced."],
        premise_void=["A global recession collapses BOTH copper and electrical-steel demand — the "
                      "relative-layer claim is untestable, premise void."],
    ),
    # 12 — natural gas keeps a structural floor under US generation (regime, contra 'gas peaked').
    dict(
        question=("By 2028-12-31, does natural gas remain ≥ 38% of US electricity generation (EIA) — "
                  "AI firm-power demand + coal retirements keep gas elevated, against the 'gas has peaked' "
                  "consensus?"),
        resolution_date=date(2028, 12, 31), probability=0.68,
        ci_low=0.34, ci_high=0.43, ci_unit="gas share of US generation", threshold=0.38, threshold_dir=">=",
        thesis_kind="regime_change", mispricing_kind="horizon_gap",
        pillars_used=[4, 5], saturation=0.48,
        rationale=(
            "CONSENSUS (transition narrative): renewables displace gas; gas share peaks and declines. "
            "DEEPER/STRUCTURAL: AI datacenters need FIRM 24/7 power, coal keeps retiring, and nuclear/"
            "storage cannot fill the gap by 2028 → gas is the swing firm-power source and its share holds "
            "≥ ~38% (it has been ~40-43%). The horizon-gap: renewables win the DECADE but not the next "
            "2-3 years. DISCONFIRMER: a fast solar+storage ramp + mild load growth could push gas below "
            "38% — possible in a low-demand year, hence P 0.68."),
        kill_criteria=["Gas share of US generation falls below 38% in 2028 (EIA) — renewables displaced it "
                       "faster than the firm-power thesis expected."],
        premise_void=["A demand collapse (recession / AI-capex retrenchment) cuts total load so the SHARE "
                      "mix is driven by demand not the firm-power constraint — premise void."],
    ),
    # 13 — gas PIPELINE TAKEAWAY, not gas supply, is the binding layer feeding AI firm power.
    dict(
        question=("By 2028-12-31, does the Appalachian (Eastern Gas South / Dominion South) natural-gas "
                  "basis DISCOUNT to Henry Hub stay ≥ $0.40/MMBtu — interstate pipeline TAKEAWAY + "
                  "permitting, not gas supply, is the binding layer getting molecules to datacenter load?"),
        resolution_date=date(2028, 12, 31), probability=0.62,
        ci_low=0.20, ci_high=1.00, ci_unit="$/MMBtu Appalachian basis discount to Henry Hub",
        threshold=0.40, threshold_dir=">=",
        thesis_kind="constraint_migration", mispricing_kind="layer_blindness",
        pillars_used=[3, 4], saturation=0.35, securitizable=False,
        rationale=(
            "OBVIOUS/PRICED: 'AI needs gas' (priced via producers + turbines, see the firm-power calls). "
            "DEEPER: the cheapest US molecules sit STRANDED in Appalachia — the binding step is interstate "
            "pipeline TAKEAWAY + FERC permitting (Mountain Valley took ~a decade), and PJM datacenter load "
            "is far from the wellhead. PHYSICAL METRIC: the Appalachian basis DISCOUNT (the realized "
            "stranded-gas signal) — wide discount = takeaway-constrained — not any producer's revenue. "
            "DISCONFIRMER: a permitting-reform wave or datacenters siting AT the wellhead (behind-the-meter) "
            "would narrow the basis. P 0.62."),
        kill_criteria=["Appalachian basis discount narrows below $0.40/MMBtu through 2028 — takeaway got "
                       "built (or sited around); pipeline was not the binding layer."],
        premise_void=["An AI-capex / gas-demand collapse slackens the whole basin so basis is demand-driven "
                      "— premise void, not a wrong read of the constraint."],
    ),
    # 14 — munitions ENERGETICS (propellant), not shell-body forging, binds the Western rearmament surge.
    dict(
        question=("By 2027-12-31, does US 155mm artillery-shell production remain below 80,000 rounds/month "
                  "— the binding constraint on the Western munitions surge is ENERGETICS/propellant "
                  "(nitrocellulose, TNT, RDX) capacity, not shell-body forging?"),
        resolution_date=date(2027, 12, 31), probability=0.55,
        ci_low=40000.0, ci_high=110000.0, ci_unit="US 155mm rounds/month", threshold=80000.0,
        threshold_dir="<=",
        thesis_kind="policy_scarcity", mispricing_kind="layer_blindness",
        pillars_used=[8, 3], saturation=0.30, securitizable=False,
        rationale=(
            "OBVIOUS/PRICED: the shell shortage / rearmament (broadly reported). DEEPER: the West let its "
            "ENERGETICS base atrophy — no domestic TNT producer (import-reliant), thin nitrocellulose + RDX "
            "— and a shell is inert without filler; energetics, not the steel body, is the binding sub-layer. "
            "PHYSICAL METRIC: monthly 155mm OUTPUT (the realized footprint of the energetics bottleneck), "
            "DoD-reported. DISCONFIRMER: the Army's Holston/Radford modernization + a new TNT line could "
            "clear it by 2027; defense data is partly opaque. Honest near-coin-flip P 0.55."),
        kill_criteria=["US 155mm output exceeds 80,000 rounds/month by 2027 — the energetics base scaled; "
                       "it was not the binding constraint."],
        premise_void=["A Ukraine ceasefire collapses demand so the line is never pushed to capacity — "
                      "premise void, not a wrong read."],
    ),
    # 15 — uranium CONVERSION (UF6), not mined uranium, is the binding layer of the nuclear-fuel revival.
    dict(
        question=("By 2027-12-31, does the uranium CONVERSION spot price (UF6, $/kgU) stay ≥ $40 — the "
                  "binding layer of the nuclear-fuel revival is conversion capacity (a 3-plant Western "
                  "oligopoly), not mined uranium?"),
        resolution_date=date(2027, 12, 31), probability=0.62,
        ci_low=28.0, ci_high=72.0, ci_unit="$/kgU UF6 conversion spot", threshold=40.0, threshold_dir=">=",
        thesis_kind="policy_scarcity", mispricing_kind="layer_blindness",
        pillars_used=[3, 8], saturation=0.38, securitizable=True,
        rationale=(
            "OBVIOUS/PRICED: the uranium bull market / nuclear revival (priced via miners + uranium ETFs). "
            "DEEPER: between the mine and enrichment sits CONVERSION (U3O8→UF6) — a Western 3-plant "
            "oligopoly (Cameco Port Hope, Orano, ConverDyn restarting) structurally short after a decade of "
            "underinvestment, with Rosatom supply at geopolitical risk; conversion price rose MORE than "
            "uranium itself (~$6→$40+/kgU). PHYSICAL METRIC: conversion spot ($/kgU, UxC), not a miner's "
            "revenue. DISCONFIRMER: ConverDyn's Metropolis restart + Russian conversion re-entering could "
            "soften it below $40 by 2027. P 0.62."),
        kill_criteria=["UF6 conversion spot falls below $40/kgU by 2027 — conversion capacity caught up; "
                       "it was not the binding layer."],
    ),
    # 16 — HVDC CONVERTER STATIONS (the valve-hall oligopoly), not cable or towers, bind the grid buildout.
    dict(
        question=("By 2028-12-31, does the quoted lead-time for a new HVDC converter station / valve hall "
                  "remain ≥ 4 years — the binding layer of the transmission + offshore-wind buildout is the "
                  "converter-valve oligopoly (Hitachi Energy, Siemens Energy, GE Vernova), not cable or towers?"),
        resolution_date=date(2028, 12, 31), probability=0.68,
        ci_low=3.0, ci_high=6.5, ci_unit="years HVDC converter-station lead-time", threshold=4.0,
        threshold_dir=">=",
        thesis_kind="constraint_migration", mispricing_kind="layer_blindness",
        pillars_used=[4, 6], saturation=0.40, securitizable=True,
        rationale=(
            "OBVIOUS/PRICED: the grid / transmission buildout (broad; see the interconnection-queue call). "
            "DEEPER: long-distance + offshore-wind + grid interties increasingly need HVDC, and the converter "
            "STATIONS / valve halls (high-power IGBT/thyristor valves) are a 3-firm oligopoly booked to "
            "~2030 (TenneT's multi-€10B framework went straight to the big-three) — the binding node, not "
            "the cable or the steel towers. PHYSICAL METRIC: converter-station lead-time (OEM + utility "
            "framework disclosures), not an OEM's revenue. DISCONFIRMER: capacity additions by the big-three "
            "or non-Western (Chinese) suppliers could shorten lead-times. P 0.68."),
        kill_criteria=["HVDC converter-station lead-time falls below 4 years by 2028 — the valve-hall "
                       "oligopoly added capacity; it was not the binding layer."],
    ),
]


def seed_forward_batch(conn: sqlite3.Connection, *, log=print) -> dict:
    """Author the dozen forward structural calls (the starved instrument's deliverable).

    Each call is a big, one-layer-deeper, physical-primary structural forecast with P + 80% interval +
    a dated resolution metric + kill-criteria, adversarially challenged in-session. Idempotent: a call
    whose question already exists is skipped. $0."""
    created = skipped = superseded = 0
    for spec in _FORWARD_BATCH:
        spec = {**spec}
        # A corrected (physical-primary) spec carries the OLD stock-pick question it replaces. If that
        # regressed card is live, supersede it (rule 7 — never edit, retain it with a superseded_by
        # pointer) so the track record honestly shows the altitude regression caught + fixed.
        old_q = spec.pop("supersedes_question", None)
        if conn.execute("SELECT 1 FROM forecast_cards WHERE question=?", (spec["question"],)).fetchone():
            skipped += 1
            continue
        # Don't fail the seed if a referenced series isn't present in this DB — drop the seed link.
        if spec.get("seed_series_id") and not conn.execute(
                "SELECT 1 FROM series WHERE id=?", (spec["seed_series_id"],)).fetchone():
            spec["seed_series_id"] = None
        old_row = conn.execute(
            "SELECT id FROM forecast_cards WHERE question=? AND superseded_by IS NULL", (old_q,)
        ).fetchone() if old_q else None
        if old_row:
            card = supersede(conn, old_row["id"], **spec)
            superseded += 1
            log(f"  ⤳card {card.id[:8]}  P={card.probability:.2f}  (superseded {old_row['id'][:8]} — "
                f"physical-primary)  {card.question[:52]}…")
        else:
            card = create_card(conn, **spec)
            created += 1
            log(f"  +card {card.id[:8]}  P={card.probability:.2f}  {card.thesis_kind}/{card.mispricing_kind}"
                f"  {card.question[:60]}…")
    log(f"forward batch: {created} created, {superseded} superseded, {skipped} already present.")
    return {"created": created, "superseded": superseded, "skipped": skipped}
