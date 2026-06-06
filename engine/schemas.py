"""The data contract — five models. Every field earns its place.

These Pydantic models mirror the SQLite tables in db.py one-to-one (snake_case columns),
because the cockpit reads those tables directly. If you change a field here, change db.py
and the cockpit together — they are one contract.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uid() -> str:
    return uuid4().hex


# --- enums -------------------------------------------------------------------


class PillarStatus(str, Enum):
    """Drives the strict-layering rule: exhaust one before opening the next."""

    untapped = "untapped"
    in_progress = "in_progress"
    exhausted = "exhausted"


class SourceKind(str, Enum):
    primary = "primary"        # the original source (a paper, a dataset, a regulatory text)
    filing = "filing"          # official corporate/government filing
    news = "news"
    analyst = "analyst"
    forum = "forum"
    model_output = "model_output"  # something an LLM produced — lowest default trust


class ForecastOutcome(str, Enum):
    true = "true"
    false = "false"


class ApprovalStatus(str, Enum):
    auto = "auto"          # free/keyless — logged at cost 0, no approval needed
    pending = "pending"    # waiting on the human
    approved = "approved"
    denied = "denied"


class DecisionStatus(str, Enum):
    open = "open"
    decided = "decided"
    expired = "expired"


# --- models ------------------------------------------------------------------


class Pillar(BaseModel):
    """One of the 9 data-flow layers, in causal order."""

    id: int
    name: str
    description: str
    ord: int  # display + layering order (1..9)
    status: PillarStatus = PillarStatus.untapped


class Source(BaseModel):
    """A piece of evidence. The GIGO gate lives here: no source without a trust rationale."""

    id: str = Field(default_factory=_uid)
    url: str
    title: str
    pillar_id: int
    kind: SourceKind
    trust_score: int = Field(ge=0, le=100)
    trust_rationale: str  # REQUIRED, non-empty — the stated reason this is trustworthy
    recency: date | None = None         # when the underlying content was published
    accessed_at: datetime = Field(default_factory=_now)
    cost_cents: int = 0                  # 0 for free/keyless
    content_hash: str | None = None      # point-in-time snapshot fingerprint

    @field_validator("trust_rationale")
    @classmethod
    def _rationale_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("trust_rationale is required and must be non-empty (GIGO gate)")
        return v.strip()


# Saturation at/above this reads as already-priced/known → the card is a consensus-echo (plan.md #6:
# a theme the crowd already discusses is NOT a prediction). Mirrors saturation.DEMOTE_AT; kept local
# to avoid a schema→saturation import cycle (saturation imports schemas, not the reverse).
CONSENSUS_ECHO_AT = 0.55


class ForecastCard(BaseModel):
    """Point-in-time, falsifiable, immutable. Never edited — superseded."""

    id: str = Field(default_factory=_uid)
    question: str                        # binary or quantified, with a clear resolution
    created_at: datetime = Field(default_factory=_now)
    resolution_date: date                # when we'll know
    probability: float = Field(ge=0.0, le=1.0)   # P of the binary resolving true
    # The forecast is a distribution, never a bare point (plan.md): the binary probability above
    # plus the 80% credible interval on the decomposed quantity the question is about.
    ci_low: float | None = None
    ci_high: float | None = None
    ci_unit: str | None = None
    # The numeric level the question tests + its direction. Stored so probability and the CI can be
    # checked self-consistent MECHANICALLY (the model-validator below) — the fix for the bug where P
    # came from one model and the CI from another, stapled together. Optional (old cards skip the check).
    threshold: float | None = None
    threshold_dir: str | None = None      # '>=' | '<='
    # Decompose (physical primary, financial optional): the probability above scores ONLY the physical
    # proposition (series + threshold + date). These two are NOT folded into it — they describe the
    # thesis, they don't move the number. This is the fix for blending "constraint is real" +
    # "no instrument" + "metric holds" into one meaningless P.
    securitizable: bool | None = None     # is there a clean tradeable instrument? (financial is a side-tag, never the headline)
    saturation: float | None = None       # narrative-saturation at issue (0..1) — how known the thesis already is
    # Altitude + class tags (the structural-foresight reframe). thesis_kind = the SHAPE of the call
    # (constraint_migration|regime_change|substitution_cascade|cost_curve_breakout|policy_scarcity);
    # mispricing_kind = WHY consensus is wrong (trough_discount|layer_blindness|horizon_gap|
    # hype_overpriced). These drive the measured base-rate-by-kind (hypothesis.base_rates) — they
    # describe/classify, they never move the probability (which scores only the physical proposition).
    thesis_kind: str | None = None
    mispricing_kind: str | None = None
    # The forecast WEB (plan.md — a future is a NET of linked outcomes, not one extrapolated statement).
    # A card may be one node of a scenario tree: scenario_id = the tree's ROOT card id (self for the root,
    # None for a standalone card); parent_card_id = the immediate parent outcome (None at the root). The
    # MECE children of one parent are mutually-exclusive + exhaustive, and their CONDITIONAL probabilities
    # (each card's `probability`, read as P given the parent occurred) sum to 1 — enforced at write time
    # by forecast.add_scenario_branch. The marginal P of a node = product of conditionals down its path.
    # Every node is still an individually falsifiable, Brier-scorable card; only the linkage is new.
    scenario_id: str | None = None
    parent_card_id: str | None = None
    rationale: str
    seed_series_id: str | None = None    # the detector hit (series) this forecast grew from
    pillars_used: list[int] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    kill_criteria: list[str] = Field(default_factory=list)  # FALSIFICATION: what would prove the thesis WRONG (scores Brier)
    # PREMISE-VOID (typed kill-criteria): the world changed out from under the bet (e.g. "AI capex
    # retrenches") — that voids the card, it does NOT mean we were wrong, so it must not score against
    # Brier. Kept separate so the two are never conflated (the critic's point).
    premise_void: list[str] = Field(default_factory=list)
    superseded_by: str | None = None     # id of the card that replaced this one
    outcome: ForecastOutcome | None = None
    resolved_at: datetime | None = None
    brier_score: float | None = None     # computed at resolution

    @field_validator("kill_criteria")
    @classmethod
    def _needs_a_kill(cls, v: list[str]) -> list[str]:
        if not any(s.strip() for s in v):
            raise ValueError("a forecast needs at least one kill-criterion (rule 7)")
        return [s.strip() for s in v if s.strip()]

    @field_validator("threshold_dir")
    @classmethod
    def _dir_ok(cls, v: str | None) -> str | None:
        if v is not None and v not in (">=", "<="):
            raise ValueError("threshold_dir must be '>=' or '<='")
        return v

    @model_validator(mode="after")
    def _ci_consistent(self) -> "ForecastCard":
        """Make an inconsistent (P, CI) UNREPRESENTABLE — the structural fix, no LLM watcher.

        Because ci_low/ci_high are the 10th/90th percentiles of the SAME posterior the
        probability is read off, these bounds are distribution-free and must hold. They catch
        the documented bug (P=0.588 stapled onto a band whose floor sits at the threshold, which
        implies P≈0.90). The issuance paths that derive P and CI from one sample array
        (forecast.tilt_to_probability / Quantity.prob_beyond) satisfy this by construction; this
        validator is the backstop that refuses any card where the two were produced separately.
        """
        t, lo, hi, p = self.threshold, self.ci_low, self.ci_high, self.probability
        if t is None or lo is None or hi is None:
            return self
        if hi < lo:
            raise ValueError(f"ci_high {hi} < ci_low {lo}")
        d = self.threshold_dir or ">="
        tol = 0.05                          # probability-axis slack (rounding + grid resolution)
        # Value-axis margin: only flag when the threshold sits MEANINGFULLY outside the band, so a
        # display-rounding gap (e.g. threshold 1.998 vs a CI floor rounded to 2.0) can't trip it.
        margin = 1e-9 + 0.02 * (hi - lo)
        below = (
            (p < 0.90 - tol) if d == ">=" else (p > 0.10 + tol)
        )  # threshold below the 10th pct ⇒ most mass beyond it
        above = (
            (p > 0.10 + tol) if d == ">=" else (p < 0.90 - tol)
        )  # threshold above the 90th pct ⇒ little mass beyond it
        if t < lo - margin and below:
            raise ValueError(
                f"P/CI inconsistent: threshold {t} < ci_low {lo} (10th pct) under '{d}' "
                f"⇒ P must be ~{'≥0.90' if d == '>=' else '≤0.10'}, got {p}. "
                f"P and the CI look like two different models (see forecast.tilt_to_probability)."
            )
        if t > hi + margin and above:
            raise ValueError(
                f"P/CI inconsistent: threshold {t} > ci_high {hi} (90th pct) under '{d}' "
                f"⇒ P must be ~{'≤0.10' if d == '>=' else '≥0.90'}, got {p}."
            )
        return self

    @property
    def consensus_echo(self) -> bool | None:
        """plan.md #6 — was this call ahead of, in line with, or behind public consensus? A theme
        the crowd already discusses is not a prediction (tag it consensus-echo). DERIVED from the
        measured narrative-saturation (not stored) so the tag can never drift from the number:
        None when saturation is unmeasured, True at/above the priced-in cut, else False."""
        if self.saturation is None:
            return None
        return self.saturation >= CONSENSUS_ECHO_AT


class Decision(BaseModel):
    """A pivotal human gate. Concise prompt + options + a recommendation — never a wall of text."""

    id: str = Field(default_factory=_uid)
    created_at: datetime = Field(default_factory=_now)
    prompt: str
    options: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    context_source_ids: list[str] = Field(default_factory=list)
    status: DecisionStatus = DecisionStatus.open
    chosen_option: str | None = None
    decided_at: datetime | None = None
    blocks: str | None = None  # short note: what is paused until this resolves


class CostLedgerEntry(BaseModel):
    """Every paid action, logged before it runs. The cost gate reads this."""

    id: str = Field(default_factory=_uid)
    ts: datetime = Field(default_factory=_now)
    action: str                          # e.g. "exa_paid_search", "minimax_extract"
    provider: str                        # e.g. "exa", "minimax", "openrouter", "hetzner"
    units: float = 0.0
    est_cost_cents: int = 0
    actual_cost_cents: int | None = None
    approval_status: ApprovalStatus = ApprovalStatus.pending
    approved_by: str | None = None
    funded_ref: str | None = None        # id of the Source/ForecastCard this spend funded


# --- metric / time-series store (component 3 + 4) ----------------------------
# Phase 1 grows the contract by exactly two tables: a Series is *what is measured*
# (the metric definition + provenance), an Observation is one point-in-time value.
# The detector's latest verdict is folded onto the Series row (no separate table
# until lead-time history actually earns one).


class Series(BaseModel):
    """A named metric tracked over time — e.g. yearly works on a concept.

    The detector's most recent verdict lives here (a property of the series at last
    run); we keep no detection history until lead-time scoring (scoreboard #3) needs it.
    """

    id: str = Field(default_factory=_uid)
    pillar_id: int
    source_id: str | None = None         # the Source row that provides provenance
    provider: str                        # "openalex" | "arxiv" | ...
    external_id: str                     # provider key (OpenAlex concept id, arXiv category)
    label: str                           # human name, e.g. "Transformer (machine learning)"
    metric: str                          # what is counted, e.g. "works_per_year"
    unit: str                            # e.g. "works/year"
    domain: str | None = None            # coarse bucket, e.g. "AI", "energy"
    created_at: datetime = Field(default_factory=_now)
    # latest detector verdict (null until first run)
    last_run_at: datetime | None = None
    last_slope: float | None = None          # robust (Theil–Sen) slope, units/year
    last_sigma: float | None = None          # noise floor (MAD-based σ of residuals)
    last_surprise_sigma: float | None = None  # max recent residual in units of σ — the trigger (recall)
    last_fired: bool | None = None           # did surprise cross k·σ?
    last_k: float | None = None              # the k threshold used
    # persistence annotation (redteam #1): is a fire a sustained bend or a one-point spike? Annotates,
    # never gates — the trigger above stays max() so a faint early move still fires (recall is sacred).
    last_sustained_sigma: float | None = None  # mean held-out residual in σ (whole window above trend?)
    last_n_consecutive: int | None = None      # longest run of held-out points above the trend
    # symmetric channel (redteam #6): a constraint dissolving (downward) — the kill-signal, additive.
    last_down_surprise_sigma: float | None = None  # largest downward held-out departure in σ
    last_dissolving: bool | None = None        # sustained downturn below the established trend
    # look-elsewhere correction (component 4b — significance.py): an empirical-null p-value + BH-FDR
    # survival, so a raw σ carries an honest false-positive probability AND a multiple-testing denominator
    last_p_mc: float | None = None           # empirical MC p-value (no Gaussian-tail fantasy)
    last_p_mc_m: int | None = None           # surrogates behind it (p floor = 1/(M+1))
    last_fdr_survive: bool | None = None     # clears Benjamini-Hochberg across the whole scan?
    last_fdr_q: float | None = None          # the FDR level used
    # precompute folded on at detect time (A6) — so the cockpit list view never scans observations
    n_obs: int | None = None
    first_as_of: date | None = None
    last_as_of: date | None = None
    first_val: float | None = None
    last_val: float | None = None
    spark: str | None = None                 # comma-joined values, ordered by as_of (sparkline)


class Observation(BaseModel):
    """One point-in-time measurement. No naked numbers: value + unit + uncertainty + as-of."""

    id: str = Field(default_factory=_uid)
    series_id: str
    as_of: date                          # when this value was knowable (point-in-time)
    value: float
    unit: str
    uncertainty: float                   # absolute 1σ; for counts, Poisson sqrt(n)
    created_at: datetime = Field(default_factory=_now)


# --- supply graph (components 5 + 6) -----------------------------------------
# Pillars 3-4 become a graph: nodes are the links of a value chain, edges are the typed
# causal relations. We store the nodes' *intrinsic dispositions* (how elastically supply can
# scale, what can substitute for them) — NEVER a "this is the bottleneck" label. The constraint
# is **computed under flow** by the propagation engine (execution §0.5: a constraint is relational,
# not a thing). Two tables, one DB — the minimalist resolution of the graph-store `[?]` (rule 5).


class GraphNode(BaseModel):
    """One link in a value chain (a tech/assay, a consumable, a piece of equipment, a reagent).

    `supply_multiple_3y` is the node's supply elasticity made concrete: the most its output can
    realistically scale within the ~3-year forecast horizon (a high multiple = elastic, absorbs a
    demand shock; a low multiple = inelastic, saturates). Carries a 1σ so the bottleneck comes out
    of a Monte-Carlo with an interval, never a bare point (execution §3).
    """

    id: str = Field(default_factory=_uid)
    chain: str                           # which value chain this belongs to, e.g. "scrna_seq"
    name: str
    kind: str                            # assay | consumable | equipment | reagent | prep | substitute
    domain: str | None = None
    supply_multiple_3y: float | None = None   # max achievable supply scale-up over the horizon
    supply_multiple_sd: float | None = None    # 1σ uncertainty on that
    source_id: str | None = None         # provenance for this node's parameters (GIGO gate)
    note: str = ""
    # --- cross-domain world-graph fields (additive) -----------------------------------------
    # The constraint graph is one connected WORLD, not isolated chains: a `depends_on` edge may
    # cross the chain boundary (a power node depends on a metals node), and the shock propagates
    # across it. `layer` = causal depth for drawing (0 = terminal demand at the top, larger = deeper
    # input). `demand_kind` = how this node's demand is known: 'derived' (= the measured build-out of
    # the layer above it, the default — demand-is-measurable) vs 'terminal' (top of graph, exogenous /
    # reflexive — the thin residual that stays judgment). `build_series_id` points at the measured
    # absolute-activity series (capex / MW / order book) that grounds the derived demand (NULL until
    # the deep-data drill fills it in).
    layer: int | None = None
    demand_kind: str = "derived"         # derived | terminal
    build_series_id: str | None = None   # measured build-out series grounding this node's demand
    created_at: datetime = Field(default_factory=_now)


class GraphEdge(BaseModel):
    """A typed causal relation between two nodes. Every edge carries a Source (GIGO gate, rule 1):
    we never propagate a demand shock through an unverified/hallucinated chain (execution §9)."""

    id: str = Field(default_factory=_uid)
    chain: str
    src: str                             # node id (the downstream consumer / the constrained thing)
    dst: str                             # node id (the upstream input / the substitute)
    rel: str                             # depends_on | supplied_by | constrained_by | substitutes
    weight: float = 1.0                  # depends_on: pass-through fraction; substitutes: capacity it can absorb
    weight_sd: float = 0.0               # 1σ on the weight (substitutes capacity is uncertain + moving)
    source_id: str | None = None         # the Source backing this edge — required for critical edges
    note: str = ""
    created_at: datetime = Field(default_factory=_now)


# --- consensus / pricing overlay (component 7 — THE GATE) ---------------------
# Pillar 7's one job: measure what's priced in, so we only bet where the constraint
# forecast (pillars 3-4) DIVERGES from the market. The edge IS the divergence:
# correct + already priced = zero return (execution §9 "priced-in" killer).


class ConsensusScore(BaseModel):
    """One point-in-time read of the mispricing gate for a constraint-migration thesis.

    The signal is a RELATIVE valuation: P/S of the inelastic rent-capturing layer (the consumable)
    over P/S of the elastic layer (the sequencer). `r_market` is what the market actually pays for
    the consumable's revenue vs the sequencer's — its revealed belief about where durable scarcity
    rent sits. `r_fair` is what our constraint model says that premium SHOULD be (a reference-class
    anchor, held wide — Bucket-2, not tuned). The `consensus_delta = r_fair − r_market` is the edge:
    a distribution (median + 80% CI), never a naked number (execution §3). Gate: edge only if the
    delta robustly clears the threshold.
    """

    id: str = Field(default_factory=_uid)
    chain: str                           # which value chain, e.g. "scrna_seq"
    thesis: str                          # short label for the bet being gated
    as_of: date                          # point-in-time: the price date the gate read
    consumable_sym: str                  # ticker of the inelastic layer (e.g. TXG)
    sequencer_sym: str                   # ticker of the elastic layer (e.g. ILMN)
    ps_consumable: float                 # price/sales of the consumable layer
    ps_sequencer: float                  # price/sales of the sequencer layer
    r_market: float                      # ps_consumable / ps_sequencer (what's priced in)
    r_fair: float                        # modeled fair relative premium (central)
    delta_median: float                  # consensus delta = r_fair − r_market (MC median)
    delta_ci_low: float                  # 10th percentile (80% CI)
    delta_ci_high: float                 # 90th percentile
    delta_unit: str = "x relative P/S"   # units — no naked numbers
    p_positive: float                    # P(delta > 0): model sees more premium than the market
    threshold: float                     # the edge bar the delta must clear
    verdict: str                         # edge | priced_in | inconclusive
    rationale: str
    source_ids: list[str] = Field(default_factory=list)  # market-signal Sources (GIGO)
    created_at: datetime = Field(default_factory=_now)


# --- narrative-saturation meter (component 17b — the measured pre-consensus leg) --------------
# The novelty-detection fix. discover.pre_consensus() calls a thesis EARLY when the LAGGING channels
# we INDEX (OpenAlex, SEC, patents, Federal Register, Wikipedia) are still flat — but most real-world
# coverage lives OUTSIDE those (trade press, FERC orders, national-lab reports, finance Substacks), so
# a heavily-covered theme reads as "least-seen" only because we never looked. This is the measured
# answer: a keyless web search ($0) over public coverage, scored by a TRANSPARENT formula (not an LLM
# opinion — reasoning stays explicit). High saturation HARD-DEMOTES an EARLY candidate to PRICED:
# if it's already in the trade press, it is not pre-consensus.


class SaturationScore(BaseModel):
    """One measured read of how saturated a topic's public narrative already is (0 = obscure,
    1 = everywhere). The score is a transparent blend of coverage VOLUME × source AUTHORITY ×
    RECENCY over real search hits; the hit URLs are always kept (honesty rail — cite, never assert).
    """

    id: str = Field(default_factory=_uid)
    topic: str                           # the query that was searched
    entity_id: str | None = None         # the entity this scores, if linked
    as_of: date
    saturation: float = Field(ge=0.0, le=1.0)   # higher = more widely covered → more priced/known
    tier: str                            # unmeasured | obscure | emerging | mainstream | saturated
    n_hits: int = 0
    n_authoritative: int = 0             # hits from mainstream/finance/trade/regulatory channels
    n_recent: int = 0                    # hits referencing the last ~2 years
    verdict: str                         # 'pre_consensus' | 'priced/known' — the gate call
    rationale: str
    evidence_urls: list[str] = Field(default_factory=list)  # the hits (always cited)
    created_at: datetime = Field(default_factory=_now)


# --- bet / decision translator (component 12) --------------------------------
# The last mile: a consensus EDGE is not yet a bet. This turns "where the constraint is + it's
# mispriced" into "what to do about it" — instrument(s), sizing, horizon, triggers. Paper only,
# $0 (translation, NOT execution). Immutable/supersede like a ForecastCard (rule 7). The bet is
# expressed via the most INELASTIC layer or a PAIR (§0.5 reflexivity: "right but early" is the
# dominant failure), sized small from the edge magnitude + its uncertainty (capped fractional
# Kelly), and is CONDITIONAL on the open consensus Decision (mispricing vs the market-is-right).


class BetLeg(BaseModel):
    """One instrument in the bet. Every leg carries a rationale (GIGO) — no naked tickers."""

    sym: str
    role: str                            # consumable | sequencer | substitute (where it sits)
    side: str                            # long | short
    weight: float                        # gross-exposure share of the position (legs sum to ~1)
    rationale: str


class BetCard(BaseModel):
    """A point-in-time, sized, monitorable PAPER bet mapping a constraint edge → instruments.

    Immutable: never edited, only superseded (rule 7). Sizing is a fraction of risk capital with
    its own 80% band (no naked numbers); the bet is conditional on `decision_id` and its first
    kill-trigger is that Decision resolving the other way.
    """

    id: str = Field(default_factory=_uid)
    chain: str                           # value chain, e.g. "scrna_seq"
    thesis: str                          # the central, conditional thesis (one line)
    created_at: datetime = Field(default_factory=_now)
    as_of: date                          # point-in-time: the consensus/price date this rests on
    horizon_date: date                   # tied to the forecast card's resolution date
    direction: str                       # short label, e.g. "long TXG / short ILMN (pair)"
    legs: list[BetLeg] = Field(default_factory=list)
    # sizing — value + unit + uncertainty (capped fractional Kelly)
    size_fraction: float = Field(ge=0.0, le=1.0)   # recommended fraction of risk capital
    size_ci_low: float | None = None
    size_ci_high: float | None = None
    size_unit: str = "fraction of risk capital"
    kelly_full: float | None = None      # the uncapped Kelly fraction (surfaced, not hidden)
    kelly_fraction: float | None = None  # the Kelly multiplier applied (conservative)
    size_cap: float | None = None        # the hard cap (small — the edge is contested)
    # the modeled pair payoff the size rests on (MC; never a typed number)
    exp_return_median: float | None = None
    exp_return_ci_low: float | None = None
    exp_return_ci_high: float | None = None
    p_win: float | None = None           # P(pair relative return > 0)
    entry_triggers: list[str] = Field(default_factory=list)
    exit_triggers: list[str] = Field(default_factory=list)
    kill_triggers: list[str] = Field(default_factory=list)
    rationale: str
    consensus_id: str | None = None      # the consensus read this edge came from
    forecast_card_id: str | None = None  # the live forward card it bets on
    decision_id: str | None = None       # the OPEN consensus Decision it is conditional on
    source_ids: list[str] = Field(default_factory=list)
    status: str = "paper"                # paper only — never execution ($0, no orders)
    superseded_by: str | None = None

    @field_validator("kill_triggers")
    @classmethod
    def _needs_a_kill(cls, v: list[str]) -> list[str]:
        if not any(s.strip() for s in v):
            raise ValueError("a bet needs at least one kill-trigger (rule 7)")
        return [s.strip() for s in v if s.strip()]

    @field_validator("legs")
    @classmethod
    def _needs_a_leg(cls, v: list[BetLeg]) -> list[BetLeg]:
        if not v:
            raise ValueError("a bet needs at least one instrument leg (GIGO — no empty bet)")
        return v


# --- retrodiction benchmark (Phase 6, the "are we real" gate) -----------------
# The acceptance test (plan.md scoreboard #2): run the §8 corpus point-in-time and check the
# FROZEN method both rediscovers winners AND rejects fizzles — scored on precision AND recall.
# A RetroCase is one corpus entry + the method's blind verdict. It stores NO new forecasting
# logic: the verdict is the existing detector's call on data ≤ signal_date (engine/retro.py).
# The label (winner/fizzle) is the ground truth from known history — the resolution, set after
# the cutoff, exactly like resolving a past forecast. Survivorship guard: gaps are LOGGED, not
# faked (cases we couldn't source point-in-time live in the harness's `LOGGED_GAPS`, surfaced).


class RetroCase(BaseModel):
    """One point-in-time §8 corpus case + the frozen method's blind verdict on it.

    Two evidence channels: the CAPABILITY curve (mechanism-backed — compute, cost-affordability,
    throughput, production) is what the method judges; the ATTENTION curve (publications / search)
    is the *decoy* that a naive momentum-chaser would chase. The discrimination IS the gap: a
    fizzle whose attention fires while its capability stays silent is correctly rejected
    (doctrine §0.5 projectibility — mechanism-free momentum is the fizzle signature).
    """

    id: str = Field(default_factory=_uid)
    key: str                              # stable slug, e.g. "ai_compute"
    label: str
    category: str                         # "winner" | "fizzle" — the ground truth
    signal_date: date                     # the point-in-time cutoff: method sees only as_of ≤ this
    consensus_date: date | None = None    # when the market/consensus caught up (for lead-time)
    capturable: bool = True               # is there a mechanism-backed capability curve at all?
    capability_series_id: str | None = None
    attention_series_id: str | None = None
    cap_fired: bool | None = None         # detector's blind call on the capability curve
    cap_surprise_sigma: float | None = None
    cap_sustained: bool | None = None     # was the fire a sustained bend or a 1-point spike? (redteam #1)
    cap_sustained_sigma: float | None = None  # mean held-out residual in σ (persistence magnitude)
    att_fired: bool | None = None         # detector's call on the attention decoy
    att_surprise_sigma: float | None = None
    predicted_p: float = 0.0              # P(this is a capturable winner), logistic(surprise−k)
    outcome: int = 0                      # 1 if winner else 0 (ground truth)
    correct: bool = False                 # did the method's call match the label?
    verdict: str = "silent"               # fired | silent | not_capturable | insufficient_data
    lead_months: int | None = None        # consensus_date − signal_date, for fired winners
    what_happened: str = ""               # the resolution narrative (post-cutoff, known history)
    note: str = ""
    created_at: datetime = Field(default_factory=_now)


# --- entity resolution (component 2 — the spine that connects the 9 pillars) --
# Every pillar names the same real-world things under different surface forms: OpenAlex's
# "Deep learning" concept, Epoch's compute curves, the "neural network" patent phrase and the
# §8 AI case are ONE technology; 10x Genomics is "TXG" to the market and a consumable supplier in
# the supply graph. Without resolving these, each pillar is an island and the constraint can never
# be traced frontier→graph→pricing. An Entity is the canonical node; an EntityLink maps one existing
# row (a series, a graph node, a ticker) to it — Claude-in-session judgment, every link rationaled
# (GIGO, rule 1). Two tables in the one DB (rule 5); additive — it never rewrites the linked rows.


class Entity(BaseModel):
    """A canonical real-world thing the system tracks across sources (a technology, company,
    material, organism). Resolution is as much about NOT merging distinct things (NLP ≠ deep
    learning) as about merging the same thing — so the note records what is deliberately excluded."""

    id: str = Field(default_factory=_uid)
    kind: str                            # technology | company | material | organism | person
    canonical_name: str
    domain: str | None = None            # coarse bucket, e.g. "single-cell genomics", "AI"
    aliases: list[str] = Field(default_factory=list)  # known surface forms (tickers, synonyms)
    note: str = ""                       # what this is / what was deliberately NOT merged
    created_at: datetime = Field(default_factory=_now)

    @field_validator("canonical_name")
    @classmethod
    def _name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("canonical_name is required and must be non-empty")
        return v.strip()


class EntityLink(BaseModel):
    """A resolved mapping from one existing row to an Entity. No link without a rationale (GIGO):
    rank/string-match is not identity — we state WHY this ref is this entity, and how confident."""

    id: str = Field(default_factory=_uid)
    entity_id: str
    ref_table: str                       # series | graph_nodes | ticker | consensus | bet
    ref_id: str                          # the row id, or a natural key (ticker symbol, chain)
    ref_label: str                       # human label for display
    pillar_id: int | None = None         # which pillar this link sits in (the cross-pillar span)
    confidence: float = Field(ge=0.0, le=1.0)   # 1.0 exact id, lower for synonym/adjacent
    method: str = "in_session"           # in_session (Claude) | exact_id | llm_verified
    rationale: str                       # REQUIRED — why this ref resolves to this entity
    created_at: datetime = Field(default_factory=_now)

    @field_validator("rationale")
    @classmethod
    def _rationale_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("rationale is required and must be non-empty (GIGO gate)")
        return v.strip()


class EntityEdge(BaseModel):
    """A typed relation between two canonical entities (A7) — confidence + rationale (GIGO)."""

    id: str = Field(default_factory=_uid)
    src_entity: str
    dst_entity: str
    rel: str                             # parent_of | supplies | substitutes | competes_with | enables
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    source_id: str | None = None
    created_at: datetime = Field(default_factory=_now)

    @field_validator("rationale")
    @classmethod
    def _rationale_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("rationale is required and must be non-empty (GIGO gate)")
        return v.strip()


class EntityCandidate(BaseModel):
    """A proposed entity link awaiting human/Claude verify (A7). fuzzy may PROPOSE, never COMMIT.

    `relation` lets a proposal say *how* the ref relates (same vs parent/child/sibling/distinct) so
    the over-merge error (NLP ≠ deep learning) is caught at review, not committed blindly.
    """

    id: str = Field(default_factory=_uid)
    entity_id: str | None = None         # target entity; None = propose a NEW entity
    proposed_name: str | None = None
    ref_table: str
    ref_id: str
    ref_label: str
    pillar_id: int | None = None
    generator: str                       # exact_id | string_block | llm
    relation: str = "same"               # same | parent | child | sibling | distinct
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    status: str = "proposed"             # proposed | accepted | rejected
    created_at: datetime = Field(default_factory=_now)
    decided_at: datetime | None = None

    @field_validator("rationale")
    @classmethod
    def _rationale_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("rationale is required and must be non-empty (GIGO gate)")
        return v.strip()


# --- hypothesis engine (component 8 — the generative front-end, "the oracle") ----
# Everything else in the engine DISPOSES (detector, consensus gate, Brier — it kills bad ideas).
# Nothing PROPOSES — it can only score curves we already chose to look at. This is that missing
# half: the divergent, cross-domain act of "where should we even look?" The soul, wired to the gate.
# A Hypothesis is generated in-session by Claude (a Bucket-2 lens held as a LENS, never asserted —
# doctrine §0) and is then forced through the SAME discipline every forecast obeys: an outside-view
# base rate (§2.1), a disconfirmer sought FIRST (§2.6), kill-criteria + a horizon (§2.5), and a
# projectibility check (§0.5 — is there a point-in-time series that could test it, or is it
# mechanism-free momentum?). The gate maps those fields to a status: a refuted thesis is KILLED,
# a beautiful-but-untestable one is PARKED (logged, not faked), a survivor that clears every bar is
# SURVIVED → eligible to be PROMOTED into a ForecastCard. The seer proposes; the cold machine disposes.


class Hypothesis(BaseModel):
    """One pre-consensus, divergently-generated constraint-migration thesis + the gate's verdict.

    The generative fields (lens/seed/claim/inelastic_layer/obvious_layer) are the soul; the
    disciplinary fields (reference_class/base_rate/disconfirmer/kill_criteria/horizon/measurable)
    are the gate. `refuted` is the in-session adversarial verdict (like an entity link's method =
    in_session — stated judgment, not a fake vote), and `status` is COMPUTED from these by
    hypothesis.gate() — never hand-set. A survivor with no data yet is parked at `survived` until
    promoted; promotion writes an immutable ForecastCard and stamps `promoted_forecast_id`.
    """

    id: str = Field(default_factory=_uid)
    created_at: datetime = Field(default_factory=_now)
    title: str                           # the one-line thesis name
    lens: str                            # Bucket-2 frame that generated it: toc|perez|helmer|arthur|ricardian|inversion|analogy
    seed: str                            # the divergent spark (cross-domain analogy / inversion / "what must be true")
    claim: str                           # the constraint-migration thesis (where rent moves)
    inelastic_layer: str                 # the non-obvious binding constraint where rent lands
    obvious_layer: str                   # the obvious-but-wrong endpoint everyone prices instead
    reference_class: str                 # the outside view (doctrine §2.1) — what class of thing is this?
    base_rate: float | None = None       # the class's hit rate, the anchor before any inside-view story
    disconfirmer: str                    # the strongest case AGAINST, sought FIRST (doctrine §2.6) — REQUIRED
    kill_criteria: list[str] = Field(default_factory=list)  # what, with a date, would prove it wrong (§2.5)
    horizon: date | None = None          # rough resolution horizon (a bet needs one)
    measurable: bool = False             # is there a point-in-time series that could test it? (§0.5 projectibility)
    refuted: bool = False                # adversarial verdict: did the disconfirmer win? When a skeptic
                                         # panel has run (n_skeptics>0) this is the panel MAJORITY (§2.6);
                                         # else the single in-session verdict.
    refutation: str = ""                 # the verdict's reasoning (why it survives / why it dies)
    # component 9: the independent multi-skeptic panel. N skeptics each try to REFUTE the thesis
    # independently; a majority-refute kills it. Votes are kept for audit (the cockpit shows m/n).
    skeptic_panel: str = ""              # JSON: [{"skeptic","refuted","reason","confidence"}]
    n_skeptics: int = 0                  # panel size (0 = no panel run yet)
    n_refute: int = 0                    # how many of the panel voted to refute
    status: str = "proposed"             # proposed|killed|parked|survived|promoted — COMPUTED by gate()
    promoted_forecast_id: str | None = None  # the ForecastCard it graduated into, if any
    # Altitude + class tags (the structural-foresight reframe). thesis_kind = the SHAPE of the
    # structural call; mispricing_kind = WHY consensus is wrong; horizon_years = years until the
    # constraint binds (drives the harvestability read: short-fused/single-mechanism = harvestable,
    # long-dated welded to a hot narrative = hype-over-priced, not under-priced). These feed the
    # measured base-rate-by-kind, they never move a probability.
    thesis_kind: str | None = None       # constraint_migration|regime_change|substitution_cascade|cost_curve_breakout|policy_scarcity
    mispricing_kind: str | None = None   # trough_discount|layer_blindness|horizon_gap|hype_overpriced
    horizon_years: int | None = None     # years until the structural claim binds (the harvestability axis)
    # The closed loop (centerpiece): a promoted hypothesis is no longer write-once. When its
    # ForecastCard resolves, the outcome + Brier are written BACK here (via promoted_forecast_id), so
    # the oracle finally measures whether its OWN kind of call paid — not just hand-assigned priors.
    outcome: ForecastOutcome | None = None
    brier_score: float | None = None
    note: str = ""

    @field_validator("disconfirmer")
    @classmethod
    def _must_seek_disconfirmation(cls, v: str) -> str:
        # The discipline that separates a hypothesis from a story: you must have looked for the
        # strongest reason it is wrong BEFORE it earns a row (doctrine §2.6, CONSTITUTION "be scientific").
        if not v or not v.strip():
            raise ValueError("a hypothesis needs a disconfirmer — the strongest case against, sought first (doctrine §2.6)")
        return v.strip()


# --- point-in-time integrity + provenance (A6 / A4) --------------------------


class ObservationRevision(BaseModel):
    """The old value of an (series_id, as_of) point, kept when a re-collection changes it. The
    'latest' lives in observations; this is the never-destroyed history (point-in-time integrity)."""

    id: str = Field(default_factory=_uid)
    series_id: str
    as_of: date
    old_value: float
    new_value: float
    old_uncertainty: float | None = None
    old_created_at: datetime | None = None
    revised_at: datetime = Field(default_factory=_now)
    reason: str = "collector_revision"


class RawDoc(BaseModel):
    """Index row for a content-addressed raw document on disk (data/raw/). The bytes ARE the key
    (sha256) → automatic dedupe + tamper-evidence; sources.content_hash is the FK in."""

    content_hash: str
    source_id: str | None = None
    url: str | None = None
    media_type: str | None = None
    byte_len: int
    path: str
    fetched_at: datetime = Field(default_factory=_now)


# --- data quality / QC harness (A5 — component 16) ---------------------------


class SeriesHealth(BaseModel):
    """The QC verdict for one series, folded onto a row (like the detector verdict). The hard gate
    reads `status`: a 'fail' series is skipped by the detector and refused as a forecast seed."""

    series_id: str
    status: str = "ok"                   # ok | warn | fail (worst of the checks)
    fresh_status: str | None = None
    complete_status: str | None = None
    valid_status: str | None = None
    recon_status: str | None = None
    prov_status: str | None = None
    days_stale: int | None = None
    n_gaps: int = 0
    n_outliers: int = 0
    n_revisions: int = 0
    health_score: float = 1.0
    detail: str = ""
    audited_at: datetime = Field(default_factory=_now)


class BeliefEdge(BaseModel):
    """A cross-thesis dependency edge in the belief-net: when `from_card` resolves it shifts the
    probability of `to_card` in a DIFFERENT scenario web (the two webs share an inelastic input or a
    causal coupling). Minimal + honest by design: ONE judgment number (`p_to_if_from_true` = P(to | from
    resolves TRUE)); the complement P(to | from FALSE) is DERIVED at read time to stay coherent with
    to_card's own marginal (the belief-net analogue of the MECE sum-check) — never stored, so it cannot
    drift. The edge is an immutable, falsifiable claim: `sign` is its predicted direction, `kill_criteria`
    its refutation. Deliberately NOT a CPT / propagation library — that would repeat the hand-typed-rate
    disease we already diagnosed; this is a constraint in one domain conditioning a thesis in another."""

    id: str = Field(default_factory=_uid)
    from_card_id: str
    to_card_id: str
    sign: int                            # +1 reinforcing | -1 offsetting (predicted direction)
    p_to_if_from_true: float = Field(ge=0.0, le=1.0)
    mechanism: str                       # the shared inelastic input / causal link (GIGO: non-empty)
    kill_criteria: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)

    @field_validator("mechanism")
    @classmethod
    def _mechanism_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("mechanism is required and non-empty (GIGO gate): name the shared input")
        return v.strip()

    @field_validator("kill_criteria")
    @classmethod
    def _kill_not_empty(cls, v: list[str]) -> list[str]:
        if not v or not any(s.strip() for s in v):
            raise ValueError("a belief edge is a falsifiable claim — kill_criteria required (rule 7)")
        return v

    @field_validator("sign")
    @classmethod
    def _sign_pm1(cls, v: int) -> int:
        if v not in (-1, 1):
            raise ValueError("sign must be +1 (reinforcing) or -1 (offsetting)")
        return v
