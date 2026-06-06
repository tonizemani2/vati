// Read-only access to the engine's SQLite DB. Server-side only.
// The engine (Python) owns writes; the cockpit only reads. Single source of truth:
// ../data/foresight.db relative to the cockpit's working dir.
import Database from "better-sqlite3";
import path from "node:path";
import fs from "node:fs";

const DB_PATH = path.join(process.cwd(), "..", "data", "foresight.db");

function open(): Database.Database | null {
  if (!fs.existsSync(DB_PATH)) return null;
  try {
    return new Database(DB_PATH, { readonly: true });
  } catch {
    return null;
  }
}

// Defensive query: if the DB or a table is missing, return [] so the cockpit
// always renders its empty states instead of crashing.
function rows<T>(sql: string): T[] {
  const db = open();
  if (!db) return [];
  try {
    return db.prepare(sql).all() as T[];
  } catch {
    return [];
  } finally {
    db.close();
  }
}

function scalar<T>(sql: string, fallback: T): T {
  const db = open();
  if (!db) return fallback;
  try {
    const r = db.prepare(sql).get() as Record<string, unknown> | undefined;
    if (!r) return fallback;
    return Object.values(r)[0] as T;
  } catch {
    return fallback;
  } finally {
    db.close();
  }
}

// --- row types (mirror engine/schemas.py) ---

export type Pillar = {
  id: number;
  name: string;
  description: string;
  ord: number;
  status: "untapped" | "in_progress" | "exhausted";
};

export type Source = {
  id: string;
  url: string;
  title: string;
  pillar_id: number;
  kind: string;
  trust_score: number;
  trust_rationale: string;
  recency: string | null;
  accessed_at: string;
  cost_cents: number;
};

export type DecisionRow = {
  id: string;
  created_at: string;
  prompt: string;
  options: string; // JSON text
  recommendation: string | null;
  status: string;
  blocks: string | null;
};

export type CostRow = {
  id: string;
  ts: string;
  action: string;
  provider: string;
  est_cost_cents: number;
  actual_cost_cents: number | null;
  approval_status: string;
};

export type ForecastRow = {
  id: string;
  question: string;
  probability: number;
  ci_low: number | null;
  ci_high: number | null;
  ci_unit: string | null;
  rationale: string;
  resolution_date: string;
  kill_criteria: string; // JSON text
  outcome: string | null;
  brier_score: number | null;
  saturation: number | null; // measured narrative-saturation at issue → the consensus-echo tag (plan.md #6)
};

// plan.md #6 — a theme the crowd already discusses is NOT a prediction. Derived from saturation so it
// can never drift from the number (mirrors engine/schemas.consensus_echo + saturation.DEMOTE_AT).
export const CONSENSUS_ECHO_AT = 0.55;
export const consensusEcho = (sat: number | null): boolean | null =>
  sat === null ? null : sat >= CONSENSUS_ECHO_AT;

export type Calibration = {
  n_resolved: number;
  brier_model: number | null;
  brier_baseline: number | null;
  points: { predicted: number; realized: number }[];
};

export type SeriesRow = {
  id: string;
  label: string;
  provider: string;
  metric: string;
  unit: string;
  domain: string | null;
  last_fired: number | null; // 1 / 0 / null (not yet run)
  last_surprise_sigma: number | null;
  // persistence annotation (redteam #1): a fire still triggers on max() (recall), but these say
  // whether it is a sustained bend or a one-point spike — so a transient can't pose as sustained.
  last_sustained_sigma: number | null; // mean held-out residual in σ
  last_n_consecutive: number | null; // longest run of held-out points above trend
  // symmetric channel (redteam #6): a constraint dissolving (downward) — the kill-signal
  last_down_surprise_sigma: number | null;
  last_dissolving: number | null; // 1 iff a sustained downturn below the established trend
  last_slope: number | null;
  last_sigma: number | null;
  last_k: number | null;
  // look-elsewhere correction (significance.py): empirical p + BH-FDR survival
  last_p_mc: number | null;
  last_p_mc_m: number | null;
  last_fdr_survive: number | null; // 1 survives multiple testing, 0 rejected, null not run
  last_fdr_q: number | null;
  n_obs: number;
  first_as_of: string | null;
  last_as_of: string | null;
  first_val: number | null;
  last_val: number | null;
  spark: string | null; // comma-joined values, ordered by as_of (for a sparkline)
};

// --- queries ---

export const getPillars = () =>
  rows<Pillar>("SELECT id, name, description, ord, status FROM pillars ORDER BY ord");

export const getSources = () =>
  rows<Source>(
    "SELECT id, url, title, pillar_id, kind, trust_score, trust_rationale, recency, accessed_at, cost_cents FROM sources ORDER BY trust_score DESC"
  );

export const getOpenDecisions = () =>
  rows<DecisionRow>(
    "SELECT id, created_at, prompt, options, recommendation, status, blocks FROM decisions WHERE status = 'open' ORDER BY created_at"
  );

export const getCostLedger = () =>
  rows<CostRow>(
    "SELECT id, ts, action, provider, est_cost_cents, actual_cost_cents, approval_status FROM cost_ledger ORDER BY ts DESC"
  );

export const getSpendCents = () =>
  scalar<number>(
    "SELECT COALESCE(SUM(COALESCE(actual_cost_cents, est_cost_cents)), 0) AS s FROM cost_ledger WHERE approval_status != 'denied'",
    0
  );

// Thesis cards only — the fast-clock LADDER rungs (redteam #3) live in their own track (getLadder),
// so they don't bury the 2 headline bets in the list or mix into the thesis calibration.
export const getForecasts = () =>
  rows<ForecastRow>(
    "SELECT id, question, probability, ci_low, ci_high, ci_unit, rationale, resolution_date, kill_criteria, outcome, brier_score, saturation FROM forecast_cards WHERE superseded_by IS NULL AND question NOT LIKE 'LADDER —%' ORDER BY created_at DESC"
  );

// Calibration scoreboard: resolved-card points + mean Brier vs the naive 0.5 base-rate baseline.
export const getCalibration = (): Calibration => {
  const resolved = rows<{ probability: number; outcome: string; brier_score: number }>(
    "SELECT probability, outcome, brier_score FROM forecast_cards WHERE outcome IS NOT NULL AND superseded_by IS NULL AND question NOT LIKE 'LADDER —%' ORDER BY resolved_at"
  );
  const n = resolved.length;
  const points = resolved.map((r) => ({
    predicted: r.probability,
    realized: r.outcome === "true" ? 1 : 0,
  }));
  const brier_model = n
    ? resolved.reduce((s, r) => s + r.brier_score, 0) / n
    : null;
  const brier_baseline = n
    ? points.reduce((s, p) => s + (0.5 - p.realized) ** 2, 0) / n
    : null;
  return { n_resolved: n, brier_model, brier_baseline, points };
};

// --- the fast-resolution ladder (component 11b, redteam #3) ---
// Short-horizon constraint-persistence micro-forecasts on the intermediate supply metrics, resolved
// from history NOW (vs the 2027-28 thesis cards) — a calibration accumulator on a fast clock. Its own
// track: tests whether the forecast machinery's PROBABILITIES are calibrated (plan.md #1).
export type LadderRow = {
  question: string;
  probability: number;
  ci_unit: string | null;
  resolution_date: string;
  outcome: string | null;
  brier_score: number | null;
};

export type LadderScore = {
  n_resolved: number;
  brier_model: number | null;
  brier_baseline: number | null; // max-entropy 0.5 — and the RANDOM-WALK baseline here (zero-drift median sits AT the threshold); beating it = calibrated
  brier_baserate: number | null; // always-guess-base-rate — beating it = discriminating
  brier_persist: number | null; // persistence ('no change' → constraint holds → P=1): the 'never relaxes' null
  logloss_model: number | null; // log loss = cross-entropy; punishes confident-wrong far harder than Brier
  logloss_baseline: number | null; // ln 2, the 0.5 / random-walk predictor
  logloss_baserate: number | null; // base-rate guesser (binary entropy)
  logloss_persist: number | null; // P=1 → a huge penalty every time a constraint fell
  auc: number | null; // rank discrimination (0.5 = no edge)
  hit_rate: number | null;
  mean_p: number | null;
  bins: { pred: number; obs: number; n: number }[];
};

// A recent SAMPLE for the detail list — the ladder now spans thousands of rungs across all pillars;
// the full set drives the score/bins (getLadderScore, unlimited), this just keeps the page light.
export const getLadder = () =>
  rows<LadderRow>(
    "SELECT question, probability, ci_unit, resolution_date, outcome, brier_score FROM forecast_cards WHERE question LIKE 'LADDER —%' AND superseded_by IS NULL ORDER BY resolution_date DESC, question LIMIT 200"
  );

export const getLadderScore = (): LadderScore => {
  const r = rows<{ probability: number; outcome: string | null; brier_score: number | null }>(
    "SELECT probability, outcome, brier_score FROM forecast_cards WHERE question LIKE 'LADDER —%' AND outcome IS NOT NULL AND superseded_by IS NULL"
  );
  const n = r.length;
  if (!n)
    return { n_resolved: 0, brier_model: null, brier_baseline: null, brier_baserate: null, brier_persist: null, logloss_model: null, logloss_baseline: null, logloss_baserate: null, logloss_persist: null, auc: null, hit_rate: null, mean_p: null, bins: [] };
  const y: number[] = r.map((x) => (x.outcome === "true" ? 1 : 0));
  const brier_model = r.reduce((s, x) => s + (x.brier_score ?? 0), 0) / n;
  const brier_baseline = y.reduce((s, v) => s + (0.5 - v) ** 2, 0) / n;
  const hit_rate = y.reduce((s, v) => s + v, 0) / n;
  const brier_baserate = hit_rate * (1 - hit_rate); // the tougher, base-rate baseline
  // persistence ('no change' → metric holds at today's level → P=1): the 'constraints never relax' null
  const brier_persist = y.reduce((s, v) => s + (1 - v) ** 2, 0) / n;
  // log loss too (plan.md #5) — clipped so a 0/1 call stays finite. Mirrors engine/ladder.ladder_score.
  const EPS = 1e-6;
  const clip = (p: number) => Math.min(1 - EPS, Math.max(EPS, p));
  const ll = (p: number, v: number) => -(v * Math.log(clip(p)) + (1 - v) * Math.log(1 - clip(p)));
  const logloss_model = r.reduce((s, x, i) => s + ll(x.probability, y[i]), 0) / n;
  const logloss_baseline = -Math.log(0.5); // ln 2, the 0.5 / random-walk predictor
  const logloss_baserate = ll(hit_rate, 1) * hit_rate + ll(hit_rate, 0) * (1 - hit_rate);
  const logloss_persist = y.reduce((s, v) => s + ll(1, v), 0) / n;
  const mean_p = r.reduce((s, x) => s + x.probability, 0) / n;
  // Mann–Whitney AUC: P(a random hold ranks above a random dissolve). 0.5 = no discrimination.
  const pos = r.filter((_, i) => y[i] === 1).map((x) => x.probability);
  const neg = r.filter((_, i) => y[i] === 0).map((x) => x.probability);
  let auc: number | null = null;
  if (pos.length && neg.length) {
    let wins = 0;
    for (const a of pos) for (const b of neg) wins += a > b ? 1 : a === b ? 0.5 : 0;
    auc = wins / (pos.length * neg.length);
  }
  const bins: { pred: number; obs: number; n: number }[] = [];
  for (let b = 0; b < 5; b++) {
    const lo = b / 5;
    const hi = (b + 1) / 5;
    const sub = r
      .map((x, i) => ({ p: x.probability, y: y[i] }))
      .filter((x) => (x.p >= lo && x.p < hi) || (b === 4 && x.p === 1.0));
    if (sub.length)
      bins.push({
        pred: sub.reduce((s, x) => s + x.p, 0) / sub.length,
        obs: sub.reduce((s, x) => s + x.y, 0) / sub.length,
        n: sub.length,
      });
  }
  return { n_resolved: n, brier_model, brier_baseline, brier_baserate, brier_persist, logloss_model, logloss_baseline, logloss_baserate, logloss_persist, auc, hit_rate, mean_p, bins };
};

// --- leading-indicator / driver tracker (component 11d, engine/indicators.py) ---
// "Forecast the drivers, not the endpoints." A thesis card resolves in 2027–28, but its dated
// kill-criteria are observable leading indicators NOW. Each card_drivers row links one kill-criterion
// to a series + a falsification threshold; status (on_track | approaching | falsified) and the
// fast-clock partial signal are COMPUTED here (not stored), mirroring indicators.driver_status —
// exactly as getLadderScore mirrors ladder_score. Observe-only: nothing here writes to a card.

export type DriverRow = {
  series_label: string;
  value: number | null;
  threshold: number;
  direction: string; // fails_below | fails_above
  confirm_dir: string; // up | down
  margin_sigma: number | null; // signed distance to threshold in annual-step units (>0 = confirming side)
  trend: string; // toward_confirm | toward_falsify | flat | n/a
  partial: number | null; // [0,1] fast-clock signal (1 = comfortably confirming & trending right)
  status: string; // on_track | approaching | falsified | no_data
  note: string;
  spark: string | null;
};

export type DriverHealth = {
  key: string; // card or hypothesis id
  kind: string; // card | hypothesis
  title: string;
  n: number;
  n_on_track: number;
  n_approaching: number;
  n_falsified: number;
  n_no_data: number;
  signal: number | null; // mean partial across drivers with data
  worst_status: string;
  drivers: DriverRow[];
};

const WORST_ORDER: Record<string, number> = { falsified: 3, approaching: 2, no_data: 1, on_track: 0 };

// Mirror of sharpen.extract (drift, vol only) — the 2 features the driver status needs. No look-ahead:
// the spark IS the full point-in-time series ordered by as_of.
function driftVol(values: number[]): { drift: number; vol: number } | null {
  const rets: number[] = [];
  for (let i = 0; i < values.length - 1; i++)
    if (values[i] > 0 && values[i + 1] > 0) rets.push(Math.log(values[i + 1] / values[i]));
  if (rets.length < 3) return null;
  const n = rets.length;
  const drift = rets.reduce((a, b) => a + b, 0) / n;
  const vol = Math.max(1e-6, Math.sqrt(rets.reduce((s, r) => s + (r - drift) ** 2, 0) / (n - 1)));
  return { drift, vol };
}

// Mirror of indicators.driver_status — trend-aware (a threshold is often a target to REACH by a
// future date, not just a floor already breached, so a wrong-side metric climbing toward it is
// *approaching*, not falsified).
function statusOf(d: {
  threshold: number; direction: string; confirm_dir: string; spark: string | null;
}): Pick<DriverRow, "value" | "margin_sigma" | "trend" | "partial" | "status"> {
  const values = d.spark ? d.spark.split(",").map(Number).filter((n) => !Number.isNaN(n)) : [];
  if (!values.length)
    return { value: null, margin_sigma: null, trend: "n/a", partial: null, status: "no_data" };
  const value = values[values.length - 1];
  const signed = d.direction === "fails_below" ? value - d.threshold : d.threshold - value;
  const dv = driftVol(values);
  let margin_sigma: number, trend_score: number, trend: string;
  if (dv) {
    const step = Math.max(Math.abs(value) * dv.vol, 1e-9);
    margin_sigma = signed / step;
    const toward = d.confirm_dir === "up" ? dv.drift : -dv.drift;
    trend_score = toward / dv.vol;
    trend = toward > dv.vol * 0.1 ? "toward_confirm" : toward < -dv.vol * 0.1 ? "toward_falsify" : "flat";
  } else {
    margin_sigma = signed / Math.max(Math.abs(value), 1e-9);
    trend_score = 0;
    trend = "n/a";
  }
  const raw = Math.max(-30, Math.min(30, 1.5 * margin_sigma + 0.8 * trend_score));
  const partial = 1 / (1 + Math.exp(-raw));
  let status: string;
  if (signed >= 0) status = margin_sigma < 1.0 && trend === "toward_falsify" ? "approaching" : "on_track";
  else status = trend === "toward_confirm" ? "approaching" : "falsified";
  return { value, margin_sigma, trend, partial, status };
}

export const getDriverHealth = (): DriverHealth[] => {
  const raw = rows<{
    card_id: string | null; hypothesis_id: string | null; title: string; kind: string;
    series_label: string; spark: string | null; threshold: number; direction: string;
    confirm_dir: string; note: string;
  }>(
    `SELECT d.card_id, d.hypothesis_id,
            COALESCE(c.question, h.title) AS title,
            CASE WHEN d.card_id IS NOT NULL THEN 'card' ELSE 'hypothesis' END AS kind,
            s.label AS series_label, s.spark AS spark,
            d.threshold, d.direction, d.confirm_dir, d.note, c.created_at AS c_created, h.created_at AS h_created
     FROM card_drivers d
     LEFT JOIN forecast_cards c ON c.id = d.card_id
     LEFT JOIN hypotheses h ON h.id = d.hypothesis_id
     LEFT JOIN series s ON s.id = d.series_id
     WHERE (d.card_id IS NULL OR c.superseded_by IS NULL)
     ORDER BY COALESCE(c.created_at, h.created_at) DESC`
  );
  const byKey = new Map<string, DriverHealth>();
  for (const r of raw) {
    const key = (r.card_id ?? r.hypothesis_id) as string;
    const st = statusOf(r);
    const driver: DriverRow = {
      series_label: r.series_label ?? "(series missing)", threshold: r.threshold,
      direction: r.direction, confirm_dir: r.confirm_dir, note: r.note, spark: r.spark, ...st,
    };
    let h = byKey.get(key);
    if (!h) {
      h = { key, kind: r.kind, title: r.title, n: 0, n_on_track: 0, n_approaching: 0,
            n_falsified: 0, n_no_data: 0, signal: null, worst_status: "on_track", drivers: [] };
      byKey.set(key, h);
    }
    h.drivers.push(driver);
  }
  const out = [...byKey.values()];
  for (const h of out) {
    h.n = h.drivers.length;
    h.n_on_track = h.drivers.filter((d) => d.status === "on_track").length;
    h.n_approaching = h.drivers.filter((d) => d.status === "approaching").length;
    h.n_falsified = h.drivers.filter((d) => d.status === "falsified").length;
    h.n_no_data = h.drivers.filter((d) => d.status === "no_data").length;
    const scored = h.drivers.filter((d) => d.partial !== null);
    h.signal = scored.length ? scored.reduce((s, d) => s + (d.partial as number), 0) / scored.length : null;
    h.worst_status = h.drivers.reduce(
      (w, d) => (WORST_ORDER[d.status] > WORST_ORDER[w] ? d.status : w), "on_track");
  }
  return out;
};

// --- supply graph (Phase 4, components 5+6) ---
// Nodes carry their supply elasticity; edges are typed causal relations. The bottleneck is NOT
// stored — the cockpit re-derives it under flow (central estimate) from these rows, mirroring the
// engine's Monte-Carlo (whose interval + P(bottleneck) live in the forecast card's rationale).

export type GraphNodeRow = {
  id: string;
  name: string;
  kind: string;
  supply_multiple_3y: number | null;
  note: string;
  trust_score: number | null; // joined from the node's Source (GIGO gate)
};

export type GraphEdgeRow = {
  src: string;
  dst: string;
  rel: string;
  weight: number;
  note: string;
};

export const SHOCK = 10;

export const getGraphNodes = (chain = "scrna_seq") =>
  rows<GraphNodeRow>(
    `SELECT n.id, n.name, n.kind, n.supply_multiple_3y, n.note, s.trust_score
     FROM graph_nodes n LEFT JOIN sources s ON s.id = n.source_id
     WHERE n.chain = '${chain}' ORDER BY n.created_at`
  );

export const getGraphEdges = (chain = "scrna_seq") =>
  rows<GraphEdgeRow>(
    `SELECT src, dst, rel, weight, note FROM graph_edges WHERE chain = '${chain}'`
  );

// --- cross-domain world graph: the chains are ONE connected world, not silos. A depends_on edge
// can cross the chain boundary (power → metals); the shock flows across it and the bottleneck is
// recomputed over the whole world. `domain_chain` tags which domain each node lives in so the view
// can show the constraint migrating ACROSS the line. The connected set is ai_power + metals.
export type WorldNodeRow = GraphNodeRow & { domain_chain: string };

export const getWorldNodes = () =>
  rows<WorldNodeRow>(
    `SELECT n.id, n.name, n.kind, n.supply_multiple_3y, n.note, s.trust_score,
            n.chain AS domain_chain
     FROM graph_nodes n LEFT JOIN sources s ON s.id = n.source_id
     WHERE n.chain IN ('ai_power','metals')
     ORDER BY COALESCE(n.layer, 99), n.created_at`
  );

export const getWorldEdges = () =>
  rows<GraphEdgeRow & { src_chain: string }>(
    `SELECT e.src, e.dst, e.rel, e.weight, e.note, e.chain AS src_chain
     FROM graph_edges e WHERE e.chain IN ('ai_power','metals')`
  );

// --- consensus / pricing overlay (Phase 5, component 7 — THE GATE) ---
// The mispricing gate: relative valuation of the inelastic consumable layer vs the elastic
// sequencer, compared to what the constraint model says the premium should be. The latest
// point-in-time read is the live verdict (edge / priced_in / inconclusive).

export type ConsensusRow = {
  chain: string;
  thesis: string;
  as_of: string;
  consumable_sym: string;
  sequencer_sym: string;
  ps_consumable: number;
  ps_sequencer: number;
  r_market: number;
  r_fair: number;
  delta_median: number;
  delta_ci_low: number;
  delta_ci_high: number;
  delta_unit: string;
  p_positive: number;
  threshold: number;
  verdict: string;
  rationale: string;
};

export const getConsensus = (chain = "scrna_seq"): ConsensusRow | null => {
  const r = rows<ConsensusRow>(
    `SELECT chain, thesis, as_of, consumable_sym, sequencer_sym, ps_consumable, ps_sequencer,
            r_market, r_fair, delta_median, delta_ci_low, delta_ci_high, delta_unit,
            p_positive, threshold, verdict, rationale
     FROM consensus WHERE chain = '${chain}' ORDER BY created_at DESC LIMIT 1`
  );
  return r[0] ?? null;
};

// --- bet / decision translator (Phase 5 half 2, component 12) ---
// The last mile: a consensus EDGE → a sized, monitorable PAPER bet. Instrument(s) + sizing +
// horizon + triggers, conditional on the open consensus Decision. The live (non-superseded) bet.

export type BetLeg = {
  sym: string;
  role: string;
  side: string;
  weight: number;
  rationale: string;
};

export type BetRow = {
  id: string;
  chain: string;
  thesis: string;
  as_of: string;
  horizon_date: string;
  direction: string;
  legs: string; // JSON text
  size_fraction: number;
  size_ci_low: number | null;
  size_ci_high: number | null;
  size_unit: string;
  kelly_full: number | null;
  kelly_fraction: number | null;
  size_cap: number | null;
  exp_return_median: number | null;
  exp_return_ci_low: number | null;
  exp_return_ci_high: number | null;
  p_win: number | null;
  entry_triggers: string; // JSON text
  exit_triggers: string; // JSON text
  kill_triggers: string; // JSON text
  rationale: string;
  status: string;
};

export const getBet = (chain = "scrna_seq"): BetRow | null => {
  const r = rows<BetRow>(
    `SELECT id, chain, thesis, as_of, horizon_date, direction, legs, size_fraction,
            size_ci_low, size_ci_high, size_unit, kelly_full, kelly_fraction, size_cap,
            exp_return_median, exp_return_ci_low, exp_return_ci_high, p_win,
            entry_triggers, exit_triggers, kill_triggers, rationale, status
     FROM bets WHERE chain = '${chain}' AND superseded_by IS NULL
     ORDER BY created_at DESC LIMIT 1`
  );
  return r[0] ?? null;
};

// --- retrodiction benchmark (Phase 6 — the "are we real" gate) ---
// Each row is one §8 corpus case + the FROZEN method's blind verdict on data ≤ signal_date.
// Capability curve = what the method judges; attention = the decoy a momentum-chaser chases.

export type RetroRow = {
  key: string;
  label: string;
  category: string; // winner | fizzle
  signal_date: string;
  consensus_date: string | null;
  capturable: number;
  cap_fired: number | null;
  cap_surprise_sigma: number | null;
  att_fired: number | null;
  att_surprise_sigma: number | null;
  predicted_p: number;
  outcome: number; // 1 winner / 0 fizzle
  correct: number;
  verdict: string; // fired | silent | not_capturable | insufficient_data
  lead_months: number | null;
  what_happened: string;
};

export const getRetroCases = () =>
  rows<RetroRow>(
    `SELECT key, label, category, signal_date, consensus_date, capturable,
            cap_fired, cap_surprise_sigma, att_fired, att_surprise_sigma,
            predicted_p, outcome, correct, verdict, lead_months, what_happened
     FROM retro_cases ORDER BY category, outcome DESC, key`
  );

// The recall probe (the §3 recall fix, VALIDATED): does a finer leading channel catch the AI-compute-
// class miss earlier than the annual curve the frozen §8 corpus judges? A diagnostic ABOUT recall —
// it never touches the frozen scoreboard. recall_gain = the fine channel fires years before the §8 signal.
export type RecallProbeRow = {
  case_key: string;
  term: string;
  channel: string;
  kind: string; // winner | fizzle | commercial_fizzle (recall attempt #3, the precision half)
  canonical_signal: number;
  consensus_year: number | null;
  first_fire_year: number | null;
  first_fire_sigma: number | null;
  lead_years: number | null;
  verdict: string; // recall_gain | no_gain | silent_correct | false_positive | research_fired | silent
  note: string;
};

export const getRecallProbe = () =>
  rows<RecallProbeRow>(
    `SELECT case_key, term, channel, kind, canonical_signal, consensus_year, first_fire_year,
            first_fire_sigma, lead_years, verdict, note
     FROM recall_probe ORDER BY CASE kind WHEN 'winner' THEN 0 WHEN 'fizzle' THEN 1 ELSE 2 END, term, channel`
  );

// The SLOW-constraint aperture (execution §7/§10 — the largest gap, opened). The acceleration detector
// is blind to constraints that bind by slowly crossing a mechanism threshold (a workforce peaking,
// water/arable per capita falling). This reads the THRESHOLD-detector verdict — years-to-bind, not σ —
// joined to the QC status (slow series tolerate older data by nature; the freshness flag stays honest).
export type SlowConstraintRow = {
  label: string;
  constraint_kind: string;
  threshold: number | null;
  direction: string;
  current_val: number;
  slope: number;
  crossed: number;
  years_to_cross: number | null;
  status: string; // binding | crossing_soon | approaching | stable
  mechanism: string;
  qc_status: string | null;
};

export const getSlowConstraints = () =>
  rows<SlowConstraintRow>(
    `SELECT sc.label, sc.constraint_kind, sc.threshold, sc.direction, sc.current_val, sc.slope,
            sc.crossed, sc.years_to_cross, sc.status, sc.mechanism, h.status AS qc_status
     FROM slow_constraints sc
     LEFT JOIN series_health h ON h.series_id = sc.series_id
     ORDER BY sc.crossed DESC, sc.years_to_cross ASC, sc.label`
  );

// The scoreboard, computed the same way engine/retro.score() does (precision/recall/specificity/
// lift/Brier vs base-rate). Kept in SQL/TS so the cockpit needs no engine round-trip.
export type RetroScore = {
  n: number;
  winners: number;
  fizzles: number;
  base_rate: number;
  precision: number;
  recall: number;
  specificity: number;
  lift: number;
  median_lead_months: number | null;
  brier_model: number | null;
  brier_base: number | null;
};

export const getRetroScore = (): RetroScore | null => {
  const cases = getRetroCases();
  const n = cases.length;
  if (!n) return null;
  const winners = cases.filter((c) => c.outcome === 1);
  const fizzles = cases.filter((c) => c.outcome === 0);
  const fired = cases.filter((c) => c.verdict === "fired");
  const tp = fired.filter((c) => c.outcome === 1).length;
  const base_rate = winners.length / n;
  const precision = fired.length ? tp / fired.length : 0;
  const recall = winners.length ? tp / winners.length : 0;
  const specificity = fizzles.length
    ? fizzles.filter((c) => c.verdict !== "fired").length / fizzles.length
    : 0;
  const leads = fired
    .filter((c) => c.outcome === 1 && c.lead_months !== null)
    .map((c) => c.lead_months as number)
    .sort((a, b) => a - b);
  const brier_model = cases.reduce((s, c) => s + (c.predicted_p - c.outcome) ** 2, 0) / n;
  const brier_base = cases.reduce((s, c) => s + (base_rate - c.outcome) ** 2, 0) / n;
  return {
    n,
    winners: winners.length,
    fizzles: fizzles.length,
    base_rate,
    precision,
    recall,
    specificity,
    lift: base_rate ? precision / base_rate : 0,
    median_lead_months: leads.length ? leads[Math.floor(leads.length / 2)] : null,
    brier_model,
    brier_base,
  };
};

// --- bias-proof universe benchmark (Phase 6+ — the survivorship-killer) ---
// One row per (OpenAlex concept × rolling origin). The candidate set is drawn by a FROZEN rule from
// data ≤ origin (nobody hand-picks the cases); the win/lose label is a FROZEN gain-of-share rule on
// data > origin (no hindsight). This is the answer to "you only tested famous cases you already knew."

export type UniverseRow = {
  concept_key: string;
  label: string;
  domain: string | null; // null | 'laggard'
  origin_year: number;
  n_known: number;
  drawn: number;
  fired: number | null;
  forecast_sigma: number | null;
  predicted_p: number | null;
  label_winner: number | null;
  share_multiple: number | null;
  lead_months: number | null;
  correct: number | null;
};

export const getUniverseCases = () =>
  rows<UniverseRow>(
    `SELECT concept_key, label, domain, origin_year, n_known, drawn, fired, forecast_sigma,
            predicted_p, label_winner, share_multiple, lead_months, correct
     FROM universe_cases ORDER BY origin_year, label`
  );

// Confusion-derived metrics, computed the same way engine/universe.score() does. The rigorous
// LOCO-Brier + Fisher-exact p live in the CLI artifact; the cockpit shows the visual headline.
type Conf = { a: number; b: number; c: number; d: number; n: number; base_rate: number; precision: number; recall: number; specificity: number; lift: number };

function confusion(rows: UniverseRow[]): Conf {
  const a = rows.filter((r) => r.fired === 1 && r.label_winner === 1).length;
  const b = rows.filter((r) => r.fired === 1 && r.label_winner === 0).length;
  const c = rows.filter((r) => r.fired === 0 && r.label_winner === 1).length;
  const d = rows.filter((r) => r.fired === 0 && r.label_winner === 0).length;
  const n = a + b + c + d;
  const base_rate = n ? (a + c) / n : 0;
  const precision = a + b ? a / (a + b) : 0;
  return {
    a, b, c, d, n, base_rate, precision,
    recall: a + c ? a / (a + c) : 0,
    specificity: b + d ? d / (b + d) : 0,
    lift: base_rate ? precision / base_rate : 0,
  };
}

export type UniverseScore = Conf & {
  drawn: number;
  median_lead_months: number | null;
  per_origin: { origin: number; drawn: number; n: number; base_rate: number; precision: number; lift: number }[];
  declustered: { n: number; base_rate: number; precision: number; lift: number };
};

export const getUniverseScore = (): UniverseScore | null => {
  const cases = getUniverseCases();
  if (!cases.length) return null;
  const scored = cases.filter((r) => r.drawn === 1 && r.fired !== null && r.label_winner !== null);
  if (!scored.length) return null;
  const pooled = confusion(scored);

  const leads = scored
    .filter((r) => r.fired === 1 && r.label_winner === 1 && r.lead_months !== null)
    .map((r) => r.lead_months as number)
    .sort((a, b) => a - b);

  const origins = [...new Set(scored.map((r) => r.origin_year))].sort((a, b) => a - b);
  const per_origin = origins.map((T) => {
    const cf = confusion(scored.filter((r) => r.origin_year === T));
    const drawn = cases.filter((r) => r.origin_year === T && r.drawn === 1).length;
    return { origin: T, drawn, n: cf.n, base_rate: cf.base_rate, precision: cf.precision, lift: cf.lift };
  });

  // de-clustered: one forecast per concept = its EARLIEST scored origin (independent, hardest call)
  const earliest = new Map<string, UniverseRow>();
  for (const r of scored) {
    const cur = earliest.get(r.concept_key);
    if (!cur || r.origin_year < cur.origin_year) earliest.set(r.concept_key, r);
  }
  const dc = confusion([...earliest.values()]);

  return {
    ...pooled,
    drawn: cases.filter((r) => r.drawn === 1).length,
    median_lead_months: leads.length ? leads[Math.floor(leads.length / 2)] : null,
    per_origin,
    declustered: { n: dc.n, base_rate: dc.base_rate, precision: dc.precision, lift: dc.lift },
  };
};

// --- entity resolution (component 2 — the spine that connects the nine pillars) ---
// An entity is one canonical real-world thing; an entity_link maps an existing row (a frontier
// series, a supply-graph node, a market ticker) to it, with a confidence + rationale (GIGO). The
// value is the CROSS-PILLAR span: one technology/firm traced from frontier signal → graph → pricing.

export type EntityLinkRow = {
  entity_id: string;
  ref_table: string;
  ref_label: string;
  pillar_id: number | null;
  confidence: number;
  rationale: string;
};

export type EntityRow = {
  id: string;
  kind: string;
  canonical_name: string;
  domain: string | null;
  aliases: string; // JSON text
  note: string;
  links: EntityLinkRow[];
  pillars: number[];
};

export const getEntities = (): EntityRow[] => {
  const ents = rows<Omit<EntityRow, "links" | "pillars">>(
    "SELECT id, kind, canonical_name, domain, aliases, note FROM entities ORDER BY kind DESC, canonical_name"
  );
  const links = rows<EntityLinkRow>(
    "SELECT entity_id, ref_table, ref_label, pillar_id, confidence, rationale FROM entity_links ORDER BY pillar_id, confidence DESC"
  );
  return ents
    .map((e) => {
      const ls = links.filter((l) => l.entity_id === e.id);
      const pillars = [...new Set(ls.map((l) => l.pillar_id).filter((p): p is number => p != null))].sort(
        (a, b) => a - b
      );
      return { ...e, links: ls, pillars };
    })
    // cross-pillar entities first (the trace is the point), then most-linked, then name
    .sort(
      (a, b) =>
        b.pillars.length - a.pillars.length ||
        b.links.length - a.links.length ||
        a.canonical_name.localeCompare(b.canonical_name)
    );
};

// Entity↔entity SUPPLIER edges (#4, the dependency half) — the supply structure between entities,
// resolved to canonical names so a constraint can be traced one hop upstream/downstream.
export type EntityEdgeRow = {
  src: string;
  dst: string;
  rel: string;
  confidence: number;
  rationale: string;
};

export const getEntityEdges = () =>
  rows<EntityEdgeRow>(
    `SELECT s.canonical_name AS src, d.canonical_name AS dst, e.rel, e.confidence, e.rationale
     FROM entity_edges e
     JOIN entities s ON s.id = e.src_entity
     JOIN entities d ON d.id = e.dst_entity
     ORDER BY e.confidence DESC, src`
  );

// --- hypothesis engine (component 8 — the generative front-end, "the oracle") ---
// Everything else DISPOSES (detector/consensus/Brier kill bad ideas); this PROPOSES. A hypothesis is
// generated in-session through a Bucket-2 lens, then forced through the same discipline a forecast
// obeys (base rate, disconfirmer-first, kill-criteria, projectibility). The gate verdict — survived /
// parked (un-falsifiable, logged not faked) / killed (refuted) — is the soul wired to the machine.

export type HypothesisRow = {
  id: string;
  title: string;
  lens: string;
  seed: string;
  claim: string;
  inelastic_layer: string;
  obvious_layer: string;
  reference_class: string;
  base_rate: number | null;
  disconfirmer: string;
  kill_criteria: string; // JSON text
  horizon: string | null;
  measurable: number; // 1/0
  refuted: number; // 1/0
  refutation: string;
  // component 9: independent multi-skeptic panel — m of n skeptics voted to refute (0 = no panel run)
  n_skeptics: number;
  n_refute: number;
  status: string; // proposed | killed | parked | survived | promoted
  note: string;
};

export const getHypotheses = () =>
  rows<HypothesisRow>(
    `SELECT id, title, lens, seed, claim, inelastic_layer, obvious_layer, reference_class,
            base_rate, disconfirmer, kill_criteria, horizon, measurable, refuted, refutation,
            n_skeptics, n_refute, status, note
     FROM hypotheses
     ORDER BY CASE status WHEN 'promoted' THEN 0 WHEN 'survived' THEN 1
                          WHEN 'parked' THEN 2 ELSE 3 END, created_at`
  );

// --- data quality / QC harness (A5, component 16) ---
// Per-series health (freshness/completeness/validity/reconciliation/provenance) + an overall score.
// The cockpit surfaces it so "no unupdated/incomplete stuff" is visible, not just enforced.

export type SeriesHealthRow = {
  series_id: string;
  label: string;
  provider: string;
  status: string; // ok | warn | fail
  days_stale: number | null;
  n_gaps: number;
  n_outliers: number;
  n_revisions: number;
  health_score: number;
  detail: string; // JSON text
};

export type DataHealth = {
  n: number;
  ok: number;
  warn: number;
  fail: number;
  score: number; // 0–100
  worst: SeriesHealthRow[];
};

export const getDataHealth = (): DataHealth => {
  const all = rows<SeriesHealthRow>(
    `SELECT h.series_id, s.label, s.provider, h.status, h.days_stale, h.n_gaps,
            h.n_outliers, h.n_revisions, h.health_score, h.detail
     FROM series_health h JOIN series s ON s.id = h.series_id
     ORDER BY CASE h.status WHEN 'fail' THEN 0 WHEN 'warn' THEN 1 ELSE 2 END, h.health_score ASC`
  );
  const n = all.length;
  const ok = all.filter((r) => r.status === "ok").length;
  const warn = all.filter((r) => r.status === "warn").length;
  const fail = all.filter((r) => r.status === "fail").length;
  const score = n ? Math.round((all.reduce((s, r) => s + r.health_score, 0) / n) * 1000) / 10 : 0;
  const worst = all.filter((r) => r.status !== "ok").slice(0, 14);
  return { n, ok, warn, fail, score, worst };
};

// Frontier time-series + the detector's latest verdict on each. Fired first, then by surprise.
// Flat read (A6): n_obs/first/last/spark are precomputed onto the series row at detect time, so
// this list view touches `observations` zero times (was 3 correlated subqueries + group_concat
// per series — a full-table scan storm at scale). Falls back to 0/null until the first detect run.
export const getSeries = () =>
  rows<SeriesRow>(
    `SELECT id, label, provider, metric, unit, domain,
            last_fired, last_surprise_sigma, last_sustained_sigma, last_n_consecutive,
            last_down_surprise_sigma, last_dissolving,
            last_slope, last_sigma, last_k,
            last_p_mc, last_p_mc_m, last_fdr_survive, last_fdr_q,
            COALESCE(n_obs, 0) AS n_obs, first_as_of, last_as_of, first_val, last_val, spark
     FROM series
     ORDER BY COALESCE(last_fired, -1) DESC, COALESCE(last_surprise_sigma, -1) DESC`
  );

// --- open discovery funnel (component 17) ---
// The autonomous scan: FDR-surviving signals across ALL feeds, plus the pre-consensus cross-reference.
// EARLY = a LEADING channel (capability/science/supply) fires FDR-clean while LAGGING channels
// (attention/capital/policy) are still flat → real + not yet priced. PRICED = lagging caught up.
// LAGGING-ONLY = attention without capability (the decoy/hype tell). Mirrors engine/discover.py exactly
// (same provider sets, same rule); retro/synthetic fixtures excluded so this is a live "where now" view.
// OpenAlex is LAGGING, not leading (2026-06-04 decoy-leak fix): every OpenAlex series is `works_per_year`,
// a raw publication COUNT — the §8-proven DECOY (mechanism-free momentum, the fizzle signature). A count
// surge alone can no longer mint an EARLY; it reads as crowding/attention. The mechanism-backed research
// lead is arXiv topic_share/talent_inflow. Kept in exact sync with engine/discover.py LEAD/LAG sets.
const LEAD_PROVIDERS = new Set(["owid", "epoch_ai", "nih_reporter", "arxiv", "fred", "un_comtrade"]);
const LAG_PROVIDERS = new Set(["openalex", "wikipedia", "sec_edgar", "federal_register", "google_patents"]);

export type DiscoverySurvivor = {
  label: string; provider: string; domain: string | null;
  sig: number; p: number | null; mm: number | null; q: number | null;
};
export type DiscoveryEntity = {
  name: string; kind: string; domain: string | null; lead_sig: number;
  verdict: "EARLY" | "PRICED" | "LAGGING-ONLY"; has_ticker: boolean;
  leads: { label: string; provider: string; sig: number }[];
  // measured narrative-saturation (engine/saturation.py): how widely the topic is already covered.
  // A 'priced/known' verdict HARD-DEMOTES an otherwise-EARLY entity to PRICED (kept in sync w/ engine).
  saturation: number | null; satTier: string; satDemoted: boolean;
};
export type Discovery = {
  survivors: DiscoverySurvivor[]; feeds: string[]; expFalse: number; q: number;
  early: DiscoveryEntity[]; priced: DiscoveryEntity[]; laggingOnly: DiscoveryEntity[];
};

export const getDiscovery = (): Discovery => {
  const survivors = rows<DiscoverySurvivor>(
    `SELECT label, provider, domain, last_surprise_sigma sig, last_p_mc p,
            last_p_mc_m mm, last_fdr_q q
     FROM series WHERE last_fired=1 AND last_fdr_survive=1
       AND provider NOT IN ('retro','synthetic')
     ORDER BY last_surprise_sigma DESC`
  );
  const feeds = [...new Set(survivors.map((s) => s.provider))].sort();
  const q = survivors[0]?.q ?? 0.1;

  const linkRows = rows<{
    eid: string; name: string; kind: string; domain: string | null;
    provider: string; slabel: string; fired: number; sig: number; fdr: number;
  }>(
    `SELECT e.id eid, e.canonical_name name, e.kind kind, e.domain domain,
            s.provider provider, s.label slabel, COALESCE(s.last_fired,0) fired,
            COALESCE(s.last_surprise_sigma,0) sig, COALESCE(s.last_fdr_survive,0) fdr
     FROM entities e
     JOIN entity_links l ON l.entity_id = e.id AND l.ref_table='series'
     JOIN series s ON s.id = l.ref_id
     WHERE s.provider NOT IN ('retro','synthetic')`
  );
  const tickers = new Set(
    rows<{ entity_id: string }>(
      "SELECT DISTINCT entity_id FROM entity_links WHERE ref_table='ticker'"
    ).map((r) => r.entity_id)
  );
  // measured pre-consensus: latest saturation read per entity (engine/saturation.py)
  const satRows = rows<{ entity_id: string; saturation: number; tier: string; verdict: string }>(
    "SELECT entity_id, saturation, tier, verdict FROM saturation WHERE entity_id IS NOT NULL"
  );
  const satByEid = new Map(satRows.map((r) => [r.entity_id, r]));

  type Acc = DiscoveryEntity & { eid: string; lead_fire: boolean; lag_fire: boolean };
  const ents = new Map<string, Acc>();
  for (const r of linkRows) {
    let e = ents.get(r.eid);
    if (!e) {
      e = { name: r.name, kind: r.kind, domain: r.domain, lead_sig: 0,
            verdict: "PRICED", has_ticker: tickers.has(r.eid), leads: [],
            saturation: null, satTier: "unmeasured", satDemoted: false,
            eid: r.eid, lead_fire: false, lag_fire: false };
      ents.set(r.eid, e);
    }
    if (LEAD_PROVIDERS.has(r.provider)) {
      if (r.fired && r.fdr) {
        e.lead_fire = true;
        e.lead_sig = Math.max(e.lead_sig, r.sig);
        e.leads.push({ label: r.slabel, provider: r.provider, sig: r.sig });
      }
    } else if (LAG_PROVIDERS.has(r.provider) && r.fired) {
      e.lag_fire = true;
    }
  }
  const early: DiscoveryEntity[] = [];
  const priced: DiscoveryEntity[] = [];
  const laggingOnly: DiscoveryEntity[] = [];
  for (const e of ents.values()) {
    const sr = satByEid.get(e.eid);
    e.saturation = sr ? sr.saturation : null;
    e.satTier = sr ? sr.tier : "unmeasured";
    const isEarly = e.lead_fire && !e.lag_fire;
    if (isEarly && sr && sr.verdict === "priced/known") {
      // HARD-DEMOTE: the trade press / regulator already covers it → not pre-consensus
      e.satDemoted = true; e.verdict = "PRICED"; priced.push(e);
    }
    else if (isEarly) { e.verdict = "EARLY"; early.push(e); }
    else if (e.lead_fire && e.lag_fire) { e.verdict = "PRICED"; priced.push(e); }
    else if (e.lag_fire && !e.lead_fire) { e.verdict = "LAGGING-ONLY"; laggingOnly.push(e); }
  }
  early.sort((a, b) => b.lead_sig - a.lead_sig);
  priced.sort((a, b) => b.lead_sig - a.lead_sig);
  return { survivors, feeds, expFalse: q * survivors.length, q, early, priced, laggingOnly };
};
