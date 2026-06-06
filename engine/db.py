"""Thin SQLite layer. No ORM. The DDL here is the source of truth for table shape;
schemas.py mirrors it, and the cockpit reads these tables directly.

Lists (pillars_used, source_ids, kill_criteria, options, ...) are stored as JSON text.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# data/foresight.db at the repo root, regardless of CWD.
REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "foresight.db"

# The five tables. Snake_case columns == schemas.py field names == cockpit reads.
SCHEMA = """
CREATE TABLE IF NOT EXISTS pillars (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    ord         INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'untapped'
);

CREATE TABLE IF NOT EXISTS sources (
    id              TEXT PRIMARY KEY,
    url             TEXT NOT NULL,
    title           TEXT NOT NULL,
    pillar_id       INTEGER NOT NULL REFERENCES pillars(id),
    kind            TEXT NOT NULL,
    trust_score     INTEGER NOT NULL CHECK (trust_score BETWEEN 0 AND 100),
    trust_rationale TEXT NOT NULL CHECK (length(trim(trust_rationale)) > 0),
    recency         TEXT,
    accessed_at     TEXT NOT NULL,
    cost_cents      INTEGER NOT NULL DEFAULT 0,
    content_hash    TEXT
);

CREATE TABLE IF NOT EXISTS forecast_cards (
    id              TEXT PRIMARY KEY,
    question        TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    resolution_date TEXT NOT NULL,
    probability     REAL NOT NULL CHECK (probability BETWEEN 0 AND 1),
    ci_low          REAL,
    ci_high         REAL,
    ci_unit         TEXT,
    threshold       REAL,                 -- the numeric level the question tests ("does X stay {dir} threshold")
    threshold_dir   TEXT,                 -- '>=' | '<=' — so P and the CI can be checked self-consistent
    securitizable   INTEGER,              -- is there a clean tradeable instrument? (financial = side-tag, not headline)
    saturation      REAL,                 -- narrative-saturation at issue (0..1) — how known the thesis already is
    premise_void    TEXT NOT NULL DEFAULT '[]',  -- typed kill: world-changed conditions that VOID (not score) the card
    rationale       TEXT NOT NULL,
    seed_series_id  TEXT REFERENCES series(id),
    pillars_used    TEXT NOT NULL DEFAULT '[]',
    source_ids      TEXT NOT NULL DEFAULT '[]',
    kill_criteria   TEXT NOT NULL DEFAULT '[]',
    superseded_by   TEXT REFERENCES forecast_cards(id),
    outcome         TEXT,
    resolved_at     TEXT,
    brier_score     REAL
);

CREATE TABLE IF NOT EXISTS decisions (
    id                 TEXT PRIMARY KEY,
    created_at         TEXT NOT NULL,
    prompt             TEXT NOT NULL,
    options            TEXT NOT NULL DEFAULT '[]',
    recommendation     TEXT,
    context_source_ids TEXT NOT NULL DEFAULT '[]',
    status             TEXT NOT NULL DEFAULT 'open',
    chosen_option      TEXT,
    decided_at         TEXT,
    blocks             TEXT
);

CREATE TABLE IF NOT EXISTS cost_ledger (
    id                TEXT PRIMARY KEY,
    ts                TEXT NOT NULL,
    action            TEXT NOT NULL,
    provider          TEXT NOT NULL,
    units             REAL NOT NULL DEFAULT 0,
    est_cost_cents    INTEGER NOT NULL DEFAULT 0,
    actual_cost_cents INTEGER,
    approval_status   TEXT NOT NULL DEFAULT 'pending',
    approved_by       TEXT,
    funded_ref        TEXT
);

-- metric / time-series store (Phase 1): a series is WHAT is measured,
-- an observation is one point-in-time value. Detector verdict folded onto series.
CREATE TABLE IF NOT EXISTS series (
    id                  TEXT PRIMARY KEY,
    pillar_id           INTEGER NOT NULL REFERENCES pillars(id),
    source_id           TEXT REFERENCES sources(id),
    provider            TEXT NOT NULL,
    external_id         TEXT NOT NULL,
    label               TEXT NOT NULL,
    metric              TEXT NOT NULL,
    unit                TEXT NOT NULL,
    domain              TEXT,
    created_at          TEXT NOT NULL,
    last_run_at         TEXT,
    last_slope          REAL,
    last_sigma          REAL,
    last_surprise_sigma REAL,
    last_fired          INTEGER,
    last_k              REAL,
    last_sustained_sigma REAL,            -- mean held-out residual in σ (persistence, redteam #1)
    last_n_consecutive  INTEGER,          -- longest run of held-out points above trend
    last_down_surprise_sigma REAL,        -- largest DOWNWARD departure (constraint dissolving, redteam #6)
    last_dissolving     INTEGER,          -- sustained downturn below trend = the kill-signal
    UNIQUE (provider, external_id, metric)
);

CREATE TABLE IF NOT EXISTS observations (
    id          TEXT PRIMARY KEY,
    series_id   TEXT NOT NULL REFERENCES series(id),
    as_of       TEXT NOT NULL,
    value       REAL NOT NULL,
    unit        TEXT NOT NULL,
    uncertainty REAL NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE (series_id, as_of)
);

-- supply graph (Phase 4, components 5+6): nodes = value-chain links (with their supply
-- elasticity), edges = typed causal relations. The bottleneck is NOT stored — it is computed
-- under flow by the propagation engine. Two tables in the one DB resolves the graph-store [?].
CREATE TABLE IF NOT EXISTS graph_nodes (
    id                 TEXT PRIMARY KEY,
    chain              TEXT NOT NULL,
    name               TEXT NOT NULL,
    kind               TEXT NOT NULL,
    domain             TEXT,
    supply_multiple_3y REAL,
    supply_multiple_sd REAL,
    source_id          TEXT REFERENCES sources(id),
    note               TEXT NOT NULL DEFAULT '',
    layer              INTEGER,             -- causal depth (0 = terminal demand, larger = deeper input)
    demand_kind        TEXT NOT NULL DEFAULT 'derived',  -- derived (measured upstream build) | terminal
    build_series_id    TEXT REFERENCES series(id),       -- measured build-out grounding derived demand
    created_at         TEXT NOT NULL,
    UNIQUE (chain, name)
);

CREATE TABLE IF NOT EXISTS graph_edges (
    id          TEXT PRIMARY KEY,
    chain       TEXT NOT NULL,
    src         TEXT NOT NULL REFERENCES graph_nodes(id),
    dst         TEXT NOT NULL REFERENCES graph_nodes(id),
    rel         TEXT NOT NULL,
    weight      REAL NOT NULL DEFAULT 1.0,
    weight_sd   REAL NOT NULL DEFAULT 0.0,
    source_id   TEXT REFERENCES sources(id),
    note        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    UNIQUE (chain, src, dst, rel)
);

-- consensus / pricing overlay (Phase 5, component 7 — THE GATE): one point-in-time read of
-- whether a constraint-migration thesis is already priced in. The signal is a relative valuation
-- (consumable P/S ÷ sequencer P/S) vs what the constraint model says the premium SHOULD be; the
-- consensus_delta is the edge. Many runs allowed (point-in-time history) — superseded by recency.
CREATE TABLE IF NOT EXISTS consensus (
    id              TEXT PRIMARY KEY,
    chain           TEXT NOT NULL,
    thesis          TEXT NOT NULL,
    as_of           TEXT NOT NULL,
    consumable_sym  TEXT NOT NULL,
    sequencer_sym   TEXT NOT NULL,
    ps_consumable   REAL NOT NULL,
    ps_sequencer    REAL NOT NULL,
    r_market        REAL NOT NULL,
    r_fair          REAL NOT NULL,
    delta_median    REAL NOT NULL,
    delta_ci_low    REAL NOT NULL,
    delta_ci_high   REAL NOT NULL,
    delta_unit      TEXT NOT NULL,
    p_positive      REAL NOT NULL,
    threshold       REAL NOT NULL,
    verdict         TEXT NOT NULL,
    rationale       TEXT NOT NULL,
    source_ids      TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT NOT NULL,
    UNIQUE (chain, as_of)
);

-- bet / decision translator (Phase 5 half 2, component 12): turns a consensus EDGE into a sized,
-- monitorable PAPER bet — instrument(s) + sizing + horizon + triggers. Immutable/supersede like a
-- forecast card (rule 7). Paper only ($0, no execution). Conditional on the open consensus Decision.
CREATE TABLE IF NOT EXISTS bets (
    id                TEXT PRIMARY KEY,
    chain             TEXT NOT NULL,
    thesis            TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    as_of             TEXT NOT NULL,
    horizon_date      TEXT NOT NULL,
    direction         TEXT NOT NULL,
    legs              TEXT NOT NULL DEFAULT '[]',
    size_fraction     REAL NOT NULL CHECK (size_fraction BETWEEN 0 AND 1),
    size_ci_low       REAL,
    size_ci_high      REAL,
    size_unit         TEXT NOT NULL DEFAULT 'fraction of risk capital',
    kelly_full        REAL,
    kelly_fraction    REAL,
    size_cap          REAL,
    exp_return_median REAL,
    exp_return_ci_low REAL,
    exp_return_ci_high REAL,
    p_win             REAL,
    entry_triggers    TEXT NOT NULL DEFAULT '[]',
    exit_triggers     TEXT NOT NULL DEFAULT '[]',
    kill_triggers     TEXT NOT NULL DEFAULT '[]',
    rationale         TEXT NOT NULL,
    consensus_id      TEXT REFERENCES consensus(id),
    forecast_card_id  TEXT REFERENCES forecast_cards(id),
    decision_id       TEXT REFERENCES decisions(id),
    source_ids        TEXT NOT NULL DEFAULT '[]',
    status            TEXT NOT NULL DEFAULT 'paper',
    superseded_by     TEXT REFERENCES bets(id)
);

-- retrodiction benchmark (Phase 6, the "are we real" gate): one §8 corpus case + the FROZEN
-- method's blind verdict on data ≤ signal_date. The capability series is what the method judges;
-- the attention series is the decoy. Reuses the detector verbatim — no new forecasting logic.
-- Re-run replaces rows by key (the harness is deterministic; the corpus is the held-out test set).
CREATE TABLE IF NOT EXISTS retro_cases (
    id                   TEXT PRIMARY KEY,
    key                  TEXT NOT NULL UNIQUE,
    label                TEXT NOT NULL,
    category             TEXT NOT NULL,
    signal_date          TEXT NOT NULL,
    consensus_date       TEXT,
    capturable           INTEGER NOT NULL DEFAULT 1,
    capability_series_id TEXT REFERENCES series(id),
    attention_series_id  TEXT REFERENCES series(id),
    cap_fired            INTEGER,
    cap_surprise_sigma   REAL,
    cap_sustained        INTEGER,             -- fire was a sustained bend vs a 1-point spike (redteam #1)
    cap_sustained_sigma  REAL,
    att_fired            INTEGER,
    att_surprise_sigma   REAL,
    predicted_p          REAL NOT NULL DEFAULT 0,
    outcome              INTEGER NOT NULL DEFAULT 0,
    correct              INTEGER NOT NULL DEFAULT 0,
    verdict              TEXT NOT NULL DEFAULT 'silent',
    lead_months          INTEGER,
    what_happened        TEXT NOT NULL DEFAULT '',
    note                 TEXT NOT NULL DEFAULT '',
    created_at           TEXT NOT NULL
);

-- bias-proof universe benchmark (Phase 6+, the survivorship-killer): one row per (OpenAlex
-- concept × rolling origin year). The candidate set is drawn by a FROZEN rule from data ≤ origin
-- (no hand-picking), the outcome is labelled by a FROZEN gain-of-share rule from data > origin
-- (no hindsight), and the FROZEN detector calls each one blind. Mirrors retro_cases but keys on
-- (concept, origin) since each concept recurs across origins. Re-run replaces rows (deterministic).
CREATE TABLE IF NOT EXISTS universe_cases (
    id                TEXT PRIMARY KEY,
    series_id         TEXT NOT NULL REFERENCES series(id),
    concept_key       TEXT NOT NULL,        -- series.external_id (OpenAlex concept id)
    label             TEXT NOT NULL,
    domain            TEXT,                  -- NULL | 'laggard' — audit tag only, never a filter
    origin_year       INTEGER NOT NULL,      -- T (the point-in-time cutoff)
    n_known           INTEGER NOT NULL,      -- obs with year ≤ T (the draw-rule input size)
    n_future          INTEGER NOT NULL,
    drawn             INTEGER NOT NULL,      -- 1 iff it cleared the FROZEN draw rule at T
    fired             INTEGER,               -- COUNT channel verdict on data ≤ T (NULL if not detectable)
    forecast_sigma    REAL,
    predicted_p       REAL,                  -- logistic(surprise − k), unfitted
    diff_fired        INTEGER,               -- DIFFUSION channel verdict (cross-field spread) ≤ T (NULL if absent)
    diff_sigma        REAL,                  -- the orthogonal channel's surprise — fires on breadth, not volume
    label_winner      INTEGER,               -- gain-of-share outcome on data > T (NULL if undecidable)
    share_multiple    REAL,
    lead_months       INTEGER,
    correct           INTEGER,               -- fired == winner (NULL if either side undecidable)
    created_at        TEXT NOT NULL,
    UNIQUE (concept_key, origin_year)
);

-- narrative-saturation meter (component 17b — the MEASURED pre-consensus leg): one keyless-search
-- read of how widely a topic is already covered (trade press / regulatory / finance), scored by a
-- transparent volume×authority×recency formula. High saturation hard-demotes an EARLY discovery to
-- PRICED — "if it's in the trade press it is not pre-consensus." Latest read per topic wins (REPLACE).
CREATE TABLE IF NOT EXISTS saturation (
    id              TEXT PRIMARY KEY,
    topic           TEXT NOT NULL,
    entity_id       TEXT REFERENCES entities(id),
    as_of           TEXT NOT NULL,
    saturation      REAL NOT NULL CHECK (saturation BETWEEN 0 AND 1),
    tier            TEXT NOT NULL,        -- unmeasured | obscure | emerging | mainstream | saturated
    n_hits          INTEGER NOT NULL DEFAULT 0,
    n_authoritative INTEGER NOT NULL DEFAULT 0,
    n_recent        INTEGER NOT NULL DEFAULT 0,
    verdict         TEXT NOT NULL,        -- pre_consensus | priced/known
    rationale       TEXT NOT NULL,
    evidence_urls   TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT NOT NULL,
    UNIQUE (topic)
);

-- entity resolution (component 2 — the spine): an entity is one canonical real-world thing
-- (a technology, company, material); an entity_link maps an existing row (a series, a graph node,
-- a ticker) to it, with a confidence + a rationale (GIGO). Additive — it never rewrites the linked
-- rows. Two tables in the one DB (rule 5). This is what lets the constraint be traced across pillars.
CREATE TABLE IF NOT EXISTS entities (
    id             TEXT PRIMARY KEY,
    kind           TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    domain         TEXT,
    aliases        TEXT NOT NULL DEFAULT '[]',
    note           TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL,
    UNIQUE (kind, canonical_name)
);

CREATE TABLE IF NOT EXISTS entity_links (
    id          TEXT PRIMARY KEY,
    entity_id   TEXT NOT NULL REFERENCES entities(id),
    ref_table   TEXT NOT NULL,
    ref_id      TEXT NOT NULL,
    ref_label   TEXT NOT NULL,
    pillar_id   INTEGER,
    confidence  REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    method      TEXT NOT NULL DEFAULT 'in_session',
    rationale   TEXT NOT NULL CHECK (length(trim(rationale)) > 0),
    created_at  TEXT NOT NULL,
    UNIQUE (entity_id, ref_table, ref_id)
);

-- entity↔entity edges (A7): the typed relations between canonical entities (10x SUPPLIES the
-- consumable node's tech, NLP is a CHILD-of-not-equal deep learning). Same GIGO discipline as
-- graph_edges — confidence + rationale, optional Source. Makes implicit cross-entity links explicit.
CREATE TABLE IF NOT EXISTS entity_edges (
    id          TEXT PRIMARY KEY,
    src_entity  TEXT NOT NULL REFERENCES entities(id),
    dst_entity  TEXT NOT NULL REFERENCES entities(id),
    rel         TEXT NOT NULL,   -- parent_of | supplies | substitutes | competes_with | enables
    confidence  REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    rationale   TEXT NOT NULL CHECK (length(trim(rationale)) > 0),
    source_id   TEXT REFERENCES sources(id),
    created_at  TEXT NOT NULL,
    UNIQUE (src_entity, dst_entity, rel)
);

-- entity-resolution candidate queue (A7): proposed links awaiting verify. Candidate generation
-- (exact-id / string-blocking / LLM adjudication) writes 'proposed' rows here; a human/Claude
-- accepts→promotes to entity_links, or rejects. fuzzy may PROPOSE but never COMMIT (§9). The
-- CLUSTERS gold seed in entity.py is never touched by this — it only ADDS.
CREATE TABLE IF NOT EXISTS entity_candidates (
    id            TEXT PRIMARY KEY,
    entity_id     TEXT REFERENCES entities(id),   -- target entity (NULL = propose a NEW entity)
    proposed_name TEXT,                            -- for a new-entity proposal
    ref_table     TEXT NOT NULL,
    ref_id        TEXT NOT NULL,
    ref_label     TEXT NOT NULL,
    pillar_id     INTEGER,
    generator     TEXT NOT NULL,   -- exact_id | string_block | llm
    relation      TEXT NOT NULL DEFAULT 'same',    -- same | parent | child | sibling | distinct
    confidence    REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    rationale     TEXT NOT NULL CHECK (length(trim(rationale)) > 0),
    status        TEXT NOT NULL DEFAULT 'proposed', -- proposed | accepted | rejected
    created_at    TEXT NOT NULL,
    decided_at    TEXT,
    UNIQUE (entity_id, ref_table, ref_id, generator)
);

-- hypothesis engine (component 8 — the generative front-end, "the oracle"): one divergently-
-- generated, pre-consensus constraint-migration thesis + the gate's verdict. The generative columns
-- (lens/seed/claim/inelastic_layer/obvious_layer) are the soul; the rest are the SAME discipline a
-- forecast obeys (base rate, disconfirmer, kill-criteria, horizon, projectibility). `status` is
-- COMPUTED by hypothesis.gate(): killed (refuted) | parked (survives but untestable, logged not
-- faked) | survived (clears every bar → eligible) | promoted (became a ForecastCard). The seer
-- proposes; the cold machine disposes. Re-seed replaces the curated rows by title (deterministic).
CREATE TABLE IF NOT EXISTS hypotheses (
    id                   TEXT PRIMARY KEY,
    created_at           TEXT NOT NULL,
    title                TEXT NOT NULL UNIQUE,
    lens                 TEXT NOT NULL,
    seed                 TEXT NOT NULL,
    claim                TEXT NOT NULL,
    inelastic_layer      TEXT NOT NULL,
    obvious_layer        TEXT NOT NULL,
    reference_class      TEXT NOT NULL,
    base_rate            REAL,
    disconfirmer         TEXT NOT NULL CHECK (length(trim(disconfirmer)) > 0),
    kill_criteria        TEXT NOT NULL DEFAULT '[]',
    horizon              TEXT,
    measurable           INTEGER NOT NULL DEFAULT 0,
    refuted              INTEGER NOT NULL DEFAULT 0,
    refutation           TEXT NOT NULL DEFAULT '',
    status               TEXT NOT NULL DEFAULT 'proposed',
    promoted_forecast_id TEXT REFERENCES forecast_cards(id),
    note                 TEXT NOT NULL DEFAULT ''
);

-- observation revision log (A6 — point-in-time integrity): before any upsert CHANGES an existing
-- (series_id, as_of) value, the OLD value is appended here. The observations row stays 'latest';
-- history is never destroyed (a 2019 count read in 2024 may differ from one read in 2026 — the
-- backtest at as_of must be able to know which was knowable when). Additive; mirrors supersede.
CREATE TABLE IF NOT EXISTS observation_revisions (
    id           TEXT PRIMARY KEY,
    series_id    TEXT NOT NULL REFERENCES series(id),
    as_of        TEXT NOT NULL,
    old_value    REAL NOT NULL,
    new_value    REAL NOT NULL,
    old_uncertainty REAL,
    old_created_at  TEXT,
    revised_at   TEXT NOT NULL,
    reason       TEXT NOT NULL DEFAULT 'collector_revision'
);

-- content-addressed raw-document store index (A4): the bytes live at data/raw/<sha[:2]>/<sha>.<ext>;
-- this table is the index from content_hash → provenance. sources.content_hash is the FK in, so a
-- Source → its exact fetched bytes. Re-extraction reads local bytes ($0, no re-fetch, PIT-exact).
CREATE TABLE IF NOT EXISTS raw_docs (
    content_hash TEXT PRIMARY KEY,
    source_id    TEXT REFERENCES sources(id),
    url          TEXT,
    media_type   TEXT,
    byte_len     INTEGER NOT NULL,
    path         TEXT NOT NULL,
    fetched_at   TEXT NOT NULL
);

-- per-series data-health (A5 — the QC verdict, folded onto a row like the detector verdict).
-- Replaced each `data-audit` run (deterministic). The hard gate reads `status`: a 'fail' series is
-- skipped by the detector and refused as a forecast seed — stale/incomplete data cannot feed a bet.
CREATE TABLE IF NOT EXISTS series_health (
    series_id        TEXT PRIMARY KEY REFERENCES series(id),
    status           TEXT NOT NULL DEFAULT 'ok',   -- ok | warn | fail
    fresh_status     TEXT,
    complete_status  TEXT,
    valid_status     TEXT,
    recon_status     TEXT,
    prov_status      TEXT,
    days_stale       INTEGER,
    n_gaps           INTEGER NOT NULL DEFAULT 0,
    n_outliers       INTEGER NOT NULL DEFAULT 0,
    n_revisions      INTEGER NOT NULL DEFAULT 0,
    health_score     REAL NOT NULL DEFAULT 1.0,
    detail           TEXT NOT NULL DEFAULT '',
    audited_at       TEXT NOT NULL
);

-- fine-grained research substrate (Pillar 1, engine/pillars/research.py): one row per harvested
-- paper. This is the GRAIN the coarse-counts blind spot was missing (goal.md #2) — we keep the raw
-- record so the leading signals (topic-share acceleration, cross-field diffusion, talent inflow) can
-- be (re)computed over time WITHOUT re-harvesting (data is the binding constraint — keep it; A4 spirit).
-- `published` is the first-submission date = a fixed point-in-time fact, so bucketing by it can never
-- look ahead. provider is generic ('arxiv' now; google_scholar / others slot in here later).
CREATE TABLE IF NOT EXISTS papers (
    id               TEXT PRIMARY KEY,
    provider         TEXT NOT NULL,            -- 'arxiv' | 'google_scholar' | ...
    external_id      TEXT NOT NULL,            -- provider key (arXiv id, e.g. '2301.00001')
    published        TEXT NOT NULL,            -- first-submission date (point-in-time clean)
    updated          TEXT,                     -- last revision date (if any)
    primary_category TEXT,                     -- e.g. 'cs.LG'
    categories       TEXT NOT NULL DEFAULT '', -- space-joined category list
    title            TEXT NOT NULL DEFAULT '',
    abstract         TEXT NOT NULL DEFAULT '',
    authors          TEXT NOT NULL DEFAULT '', -- '; '-joined author names
    n_authors        INTEGER NOT NULL DEFAULT 0,
    content_hash     TEXT,
    fetched_at       TEXT NOT NULL,
    UNIQUE (provider, external_id)
);

-- recall probe (the §3 recall fix, validated): does a FINER leading channel (monthly arXiv
-- talent-inflow / topic-share, research.py) catch the AI-compute-class miss EARLIER than the annual
-- capability curve the frozen §8 corpus judges? Each row = one (case × term × channel) rolled-back
-- point-in-time test. This is a DIAGNOSTIC about the method's recall — it never touches the frozen
-- retro_cases scoreboard (that would be tuning on the corpus, §9).
CREATE TABLE IF NOT EXISTS recall_probe (
    id               TEXT PRIMARY KEY,
    case_key         TEXT NOT NULL,        -- the §8 case probed (e.g. 'ai_compute')
    term             TEXT NOT NULL,        -- the arXiv research term (e.g. 'deep learning')
    channel          TEXT NOT NULL,        -- 'talent_inflow' | 'topic_share'
    canonical_signal INTEGER NOT NULL,     -- the §8 fixed signal year (annual curve silent there)
    consensus_year   INTEGER,              -- consensus year (for the lead-time framing)
    first_fire_year  INTEGER,              -- earliest cutoff at which this channel fires (NULL=never)
    first_fire_sigma REAL,                 -- surprise σ at first fire
    lead_years       INTEGER,              -- canonical_signal − first_fire_year (recall gain; NULL=none)
    per_cutoff       TEXT NOT NULL,        -- JSON {year:{fired,sigma}} — the full roll-back trace
    verdict          TEXT NOT NULL,        -- 'recall_gain' | 'no_gain'
    note             TEXT,
    created_at       TEXT NOT NULL,
    UNIQUE (case_key, term, channel)
);

-- slow-constraint aperture (execution §7/§10 — the largest gap, opened 2026-06-04). The acceleration
-- detector is blind to constraints that bind by SLOWLY crossing a mechanism threshold (a workforce
-- peaking, water/arable per capita falling, aging rising). This holds the threshold-detector verdict
-- per slow series — years-to-bind, not σ — so the cockpit surfaces where a slow constraint is binding.
CREATE TABLE IF NOT EXISTS slow_constraints (
    id              TEXT PRIMARY KEY,
    series_id       TEXT NOT NULL,
    label           TEXT NOT NULL,
    constraint_kind TEXT NOT NULL,    -- 'demographics' | 'water' | 'land' | 'aging'
    threshold       REAL,             -- the mechanism binding level (NULL for a 'peak' constraint)
    direction       TEXT NOT NULL,    -- 'falling' | 'rising' | 'peak'
    current_val     REAL NOT NULL,
    slope           REAL NOT NULL,    -- units/year over the recent window
    crossed         INTEGER NOT NULL, -- 1 = binding NOW
    years_to_cross  REAL,             -- years until it binds (NULL if crossed / moving away)
    status          TEXT NOT NULL,    -- binding | crossing_soon | approaching | stable
    mechanism       TEXT NOT NULL,    -- the sourced 'why' it binds (GIGO)
    updated_at      TEXT NOT NULL,
    UNIQUE (series_id)
);

-- leading-indicator / driver tracker (engine/indicators.py — "forecast the drivers, not the
-- endpoints"). A thesis card / hypothesis resolves in 2027–28, so its scored record stays empty for
-- years. But its dated kill-criteria ARE observable leading indicators NOW. This sidecar makes a
-- subset machine-readable: it maps a card (or hypothesis) → an existing series + the falsification
-- threshold/direction taken from one kill-criterion. It stores NO observed values (those stay in
-- `observations`, the single source of truth) and NEVER edits the card (rule 7) — the link is one-way
-- and additive, exactly like entity_links / series_health fold a verdict onto an existing row. Status
-- (on_track | approaching | falsified) + the fast-clock partial signal are COMPUTED on read, so they
-- can never go stale. Exactly one of card_id / hypothesis_id is set per row.
CREATE TABLE IF NOT EXISTS card_drivers (
    id            TEXT PRIMARY KEY,
    card_id       TEXT REFERENCES forecast_cards(id),     -- nullable (driver may hang off a hypothesis)
    hypothesis_id TEXT REFERENCES hypotheses(id),          -- nullable; exactly one of the two is set
    series_id     TEXT NOT NULL REFERENCES series(id),     -- the leading-indicator time-series
    kill_index    INTEGER,                                  -- which kill_criteria[i] this proxies (provenance only)
    threshold     REAL NOT NULL,                            -- the falsification level
    direction     TEXT NOT NULL,                            -- 'fails_below' | 'fails_above': which way trips the kill-criterion
    confirm_dir   TEXT NOT NULL,                            -- 'up' | 'down': which trend direction moves TOWARD confirmation
    note          TEXT NOT NULL DEFAULT '',                 -- why this series proxies this kill-criterion (GIGO)
    created_at    TEXT NOT NULL,
    UNIQUE (card_id, hypothesis_id, series_id, kill_index)
);

-- indices for scale (A6): the cockpit no longer scans observations for the list view, but the
-- detector + QC + reconciliation read per-series; these keep those O(log n).
CREATE INDEX IF NOT EXISTS idx_obs_series_asof ON observations(series_id, as_of);
CREATE INDEX IF NOT EXISTS idx_series_pillar ON series(pillar_id);
CREATE INDEX IF NOT EXISTS idx_series_provider ON series(provider);
CREATE INDEX IF NOT EXISTS idx_entity_links_entity ON entity_links(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_links_ref ON entity_links(ref_table, ref_id);
CREATE INDEX IF NOT EXISTS idx_obs_rev_series ON observation_revisions(series_id, as_of);
CREATE INDEX IF NOT EXISTS idx_papers_published ON papers(published);
CREATE INDEX IF NOT EXISTS idx_papers_primary_cat ON papers(primary_category);
CREATE INDEX IF NOT EXISTS idx_card_drivers_card ON card_drivers(card_id);
CREATE INDEX IF NOT EXISTS idx_card_drivers_hyp ON card_drivers(hypothesis_id);

-- belief-net: cross-thesis dependency edges over the forest of scenario webs. An edge says one web's
-- node, when it resolves, shifts the probability of a node in a DIFFERENT web (shared inelastic input).
-- ONE number stored (p_to_if_from_true); the complement is derived at read time to stay coherent with
-- the target's own marginal, so it can't drift. Immutable, falsifiable (kill_criteria). Pure-read
-- propagation in forecast.py — no CPTs, no BP library.
CREATE TABLE IF NOT EXISTS belief_edges (
    id                TEXT PRIMARY KEY,
    from_card_id      TEXT NOT NULL REFERENCES forecast_cards(id),
    to_card_id        TEXT NOT NULL REFERENCES forecast_cards(id),
    sign              INTEGER NOT NULL CHECK (sign IN (-1, 1)),
    p_to_if_from_true REAL NOT NULL CHECK (p_to_if_from_true BETWEEN 0 AND 1),
    mechanism         TEXT NOT NULL CHECK (length(trim(mechanism)) > 0),
    kill_criteria     TEXT NOT NULL,   -- JSON array
    created_at        TEXT NOT NULL,
    UNIQUE (from_card_id, to_card_id)
);

-- The anti-overfitting ledger (engine/experiment.py). One row per (protocol, split, config) tried.
-- n_configs_seen = COUNT(DISTINCT config_json) in this protocol = the multiple-testing denominator
-- the headline p is deflated by. The UNIQUE key means re-running a config OVERWRITES (never inflates
-- the count). is_test_reveal=1 marks the one-time sealed-TEST score; the seal is the git commit of
-- experiments/protocol_vN.yaml, which must predate this row.
CREATE TABLE IF NOT EXISTS experiment_ledger (
    id                TEXT PRIMARY KEY,
    protocol_version  INTEGER NOT NULL,
    split             TEXT NOT NULL,            -- train | validation | test
    config_json       TEXT NOT NULL,            -- {"k":..,"gain_margin":..,"channels":..}
    n_scored          INTEGER NOT NULL,
    lift              REAL,                      -- pooled (optimistic)
    lift_declustered  REAL,                      -- the primary metric (headline)
    p_fisher          REAL,                      -- de-clustered Fisher (kept for contrast)
    p_block           REAL,                      -- de-clustered block-permutation (honest)
    lift_ci_low       REAL,
    lift_ci_high      REAL,
    brier_model       REAL,
    brier_base        REAL,
    n_configs_seen    INTEGER,                   -- distinct configs tried in this protocol so far
    p_deflated        REAL,                      -- p_block * n_configs (Bonferroni, capped 1.0)
    is_test_reveal    INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL,
    UNIQUE (protocol_version, split, config_json)
);

-- The mechanical constraint-locator backtest (engine/locator.py, Stage 2). One row per
-- (chain, origin): which layer the FROZEN measured rule located as the inelastic binding constraint,
-- which layer actually captured the rent (zero-sum chain share), and the contaminated graph-prior's
-- pick as a control arm. Point-in-time; the locator never sees as_of > origin_year.
CREATE TABLE IF NOT EXISTS locator_cases (
    id                TEXT PRIMARY KEY,
    chain             TEXT NOT NULL,
    origin_year       INTEGER NOT NULL,
    located_layer     TEXT,                      -- argmax inelastic_score (the mechanical pick)
    located_score     REAL,
    winner_layer      TEXT,                      -- max share-gain layer over the next window (label)
    obvious_layer     TEXT,                      -- the naive end-product layer (for contrast)
    share_multiple    REAL,
    correct           INTEGER,                   -- located == winner
    graph_pick        TEXT,                      -- graph.propagate bottleneck (contaminated control)
    graph_correct     INTEGER,
    note              TEXT,
    created_at        TEXT NOT NULL,
    UNIQUE (chain, origin_year)
);
"""


def connect() -> sqlite3.Connection:
    """Open the DB with WAL (safe concurrent read from the cockpit) and FKs on."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")  # safe with WAL; better bulk-write throughput
    conn.execute("PRAGMA busy_timeout = 60000")  # wait out a concurrent writer instead of erroring
    return conn


# New forecast columns added after Phase 0 (intervals + seed-series link). Listed here so an
# existing DB is migrated in place — CREATE TABLE IF NOT EXISTS never alters an existing table.
_FORECAST_ADDED_COLUMNS = {
    "ci_low": "REAL",
    "ci_high": "REAL",
    "ci_unit": "TEXT",
    "seed_series_id": "TEXT",
}

# Series precompute columns (A6): the detector reads every point already, so it folds the
# sparkline + endpoints onto the series row. The cockpit list view then never scans observations.
_SERIES_ADDED_COLUMNS = {
    "n_obs": "INTEGER",
    "first_as_of": "TEXT",
    "last_as_of": "TEXT",
    "first_val": "REAL",
    "last_val": "REAL",
    "spark": "TEXT",            # comma-joined values ordered by as_of
}

# Universe diffusion channel (the orthogonal early signal): the cross-field-spread verdict folded
# onto each (concept × origin) row alongside the count-channel verdict, so OR-recall is auditable.
_UNIVERSE_ADDED_COLUMNS = {
    "diff_fired": "INTEGER",
    "diff_sigma": "REAL",
}

# Look-elsewhere correction (component 4b, engine/significance.py): the empirical-null p-value + the
# BH-FDR survival flag folded onto each series row alongside the detector verdict. Turns a raw σ
# (no null, no denominator) into an honest p with a false-positive denominator across the scan.
_SERIES_SIGNIFICANCE_COLUMNS = {
    "last_p_mc": "REAL",         # empirical Monte-Carlo p-value (1+#null≥obs)/(M+1)
    "last_p_mc_m": "INTEGER",    # M surrogates the p rests on (its resolution floor is 1/(M+1))
    "last_fdr_survive": "INTEGER",  # 1 iff it clears Benjamini-Hochberg across the whole scan
    "last_fdr_q": "REAL",        # the FDR level used (e.g. 0.10)
}

# Persistence annotation (redteam #1, engine/detector.py): the fire still triggers on max() (recall),
# but these say whether that fire is a SUSTAINED bend or a one-point spike — so a transient can't pose
# as a sustained acceleration downstream. Annotation only; never gates the verdict.
_SERIES_PERSISTENCE_COLUMNS = {
    "last_sustained_sigma": "REAL",      # mean held-out residual in σ (whole window above trend?)
    "last_n_consecutive": "INTEGER",     # longest run of held-out points above the trend
    # symmetric channel (redteam #6): a constraint DISSOLVING (downward), the natural kill-signal.
    "last_down_surprise_sigma": "REAL",  # largest downward held-out departure in σ
    "last_dissolving": "INTEGER",        # 1 iff a sustained downturn below the established trend
}


def _migrate_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    """Add any missing columns in place (CREATE TABLE IF NOT EXISTS never alters an existing table)."""
    have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    for col, typ in columns.items():
        if col not in have:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")


# Persistence annotation on the retro corpus (redteam #1): whether each fired §8 case was a sustained
# bend or a one-point spike. Annotation only — the frozen retro verdict is unchanged.
_RETRO_PERSISTENCE_COLUMNS = {
    "cap_sustained": "INTEGER",
    "cap_sustained_sigma": "REAL",
}


_GRAPH_NODE_ADDED_COLUMNS = {
    "layer": "INTEGER",                          # causal depth for the cross-domain world view
    "demand_kind": "TEXT NOT NULL DEFAULT 'derived'",  # derived (measured upstream build) | terminal
    "build_series_id": "TEXT",                   # measured build-out series grounding derived demand
}


# Component 9 — the independent multi-skeptic panel (§2.6). `refuted`/`status` stay computed by
# hypothesis.gate(); these record the panel that produced the majority verdict (audit + cockpit).
_HYPOTHESIS_ADDED_COLUMNS = {
    "skeptic_panel": "TEXT NOT NULL DEFAULT ''",  # JSON list of independent skeptic votes
    "n_skeptics": "INTEGER NOT NULL DEFAULT 0",
    "n_refute": "INTEGER NOT NULL DEFAULT 0",
}

# Structural-foresight reframe + the closed outcome loop. thesis_kind/mispricing_kind/horizon_years
# classify the call (the SHAPE + WHY-consensus-is-wrong + when it binds) so base-rate-by-kind can be
# MEASURED; outcome/brier_score are written back when the promoted card resolves (the loop that lets
# the oracle finally score its own kinds of call instead of trusting hand-assigned priors).
_HYPOTHESIS_FORESIGHT_COLUMNS = {
    "thesis_kind": "TEXT",
    "mispricing_kind": "TEXT",
    "horizon_years": "INTEGER",
    "outcome": "TEXT",
    "brier_score": "REAL",
}

# The same class tags carried onto a promoted ForecastCard, so the scored record aggregates by kind.
_FORECAST_FORESIGHT_COLUMNS = {
    "thesis_kind": "TEXT",
    "mispricing_kind": "TEXT",
}


# Recall attempt #3 (the precision half): the probe now carries WINNERS (the channel should fire
# early) AND fizzle CONTROLS (it should stay silent) — so it scores recall AND precision, not just
# recall. `kind` = winner | fizzle | commercial_fizzle (the graphene edge case).
_RECALL_PROBE_ADDED_COLUMNS = {
    "kind": "TEXT NOT NULL DEFAULT 'winner'",
}


# Number-integrity fix (the P/CI-consistency bug): store the numeric threshold the question tests
# + its direction, so a card's probability and its credible interval can be checked self-consistent
# MECHANICALLY (forecast.ForecastCard model-validator) instead of being two unconnected models
# stapled together — no LLM watcher. Old cards (threshold NULL) skip the check; new ones carry it.
_FORECAST_THRESHOLD_COLUMNS = {
    "threshold": "REAL",
    "threshold_dir": "TEXT",        # '>=' | '<='
}

# Decompose (physical primary, financial optional) + typed kill-criteria. securitizable/saturation
# describe the thesis WITHOUT moving the probability (which scores only the physical proposition);
# premise_void holds world-changed conditions that VOID rather than score the card.
_FORECAST_DECOMPOSE_COLUMNS = {
    "securitizable": "INTEGER",
    "saturation": "REAL",
    "premise_void": "TEXT NOT NULL DEFAULT '[]'",
}

# The forecast WEB (a future is a net of linked outcomes, not one extrapolated statement). A card may
# be a node in a scenario tree: `scenario_id` = the id of the tree's ROOT card (self for the root, NULL
# for a standalone card); `parent_card_id` = the immediate parent outcome (NULL at the root). The MECE
# children of one parent are mutually-exclusive, exhaustive outcomes whose CONDITIONAL probabilities
# (P given the parent occurred) sum to 1 — enforced at write time by forecast.add_scenario_branch.
# Every node stays an individually falsifiable, Brier-scorable card; only the linkage is new.
_FORECAST_SCENARIO_COLUMNS = {
    "scenario_id": "TEXT",       # root card id of the tree this node belongs to (self if root)
    "parent_card_id": "TEXT",    # immediate parent outcome (NULL = root); child P is conditional on it
}


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _migrate_columns(conn, "forecast_cards", _FORECAST_ADDED_COLUMNS)
    _migrate_columns(conn, "series", _SERIES_ADDED_COLUMNS)
    _migrate_columns(conn, "series", _SERIES_SIGNIFICANCE_COLUMNS)
    _migrate_columns(conn, "series", _SERIES_PERSISTENCE_COLUMNS)
    _migrate_columns(conn, "universe_cases", _UNIVERSE_ADDED_COLUMNS)
    _migrate_columns(conn, "retro_cases", _RETRO_PERSISTENCE_COLUMNS)
    _migrate_columns(conn, "graph_nodes", _GRAPH_NODE_ADDED_COLUMNS)
    _migrate_columns(conn, "hypotheses", _HYPOTHESIS_ADDED_COLUMNS)
    _migrate_columns(conn, "hypotheses", _HYPOTHESIS_FORESIGHT_COLUMNS)
    _migrate_columns(conn, "recall_probe", _RECALL_PROBE_ADDED_COLUMNS)
    _migrate_columns(conn, "forecast_cards", _FORECAST_THRESHOLD_COLUMNS)
    _migrate_columns(conn, "forecast_cards", _FORECAST_DECOMPOSE_COLUMNS)
    _migrate_columns(conn, "forecast_cards", _FORECAST_FORESIGHT_COLUMNS)
    _migrate_columns(conn, "forecast_cards", _FORECAST_SCENARIO_COLUMNS)
    conn.commit()


def table_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]
