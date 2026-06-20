export const meta = {
  name: 'forecastbench-judge',
  description: 'Claude-native judgmental research leg for ForecastBench (replaces the AWS Bedrock opus_forecaster). Stage 1: Sonnet research-forecasts every judgmental (metaculus+infer) question with web search. Stage 2: Opus 3-council re-forecasts only the edge>=weak movers (median-logit). Emits {id:{probability,edge,reasoning}} consumed by `python -m engine.forecastbench.opus_blend merge`. Input via args: the worklist rows from `opus_blend worklist`. ~100 Sonnet + ~45-90 Opus agents.',
  whenToUse: 'On the ForecastBench due date, AFTER `opus_blend worklist <qset> work.jsonl` is run and its rows are loaded. Forward rounds only (leak discipline). Pass args={questions:[...worklist rows...], council:3}.',
  phases: [
    { title: 'Triage', detail: 'Sonnet research-forecasts each judgmental question; self-assigns edge none/weak/strong', model: 'sonnet' },
    { title: 'Council', detail: 'Opus 3-council re-forecasts the edge>=weak movers; median-logit aggregate', model: 'opus' },
  ],
}

// args arrives as a JSON STRING in this harness; parse it.
const A = (() => { try { return typeof args === 'string' ? JSON.parse(args) : (args || {}) } catch { return {} } })()
const QUESTIONS = Array.isArray(A) ? A : (A.questions || [])
const COUNCIL = A.council || 1            // Opus samples per mover (1 = single pass, cheapest)
const MOVER_CAP = A.mover_cap ?? 30       // hard ceiling on Opus-councilled movers; Opus calls <= MOVER_CAP * COUNCIL

if (!QUESTIONS.length) {
  log('forecastbench-judge: no questions in args — nothing to forecast. Pass args={questions:[...worklist rows...]}.')
  return {}
}

// --- math (mirror opus_forecaster: clamp to [0.02,0.98], median-logit, median edge) ---
const EDGE_RANK = { none: 0, weak: 1, strong: 2 }
const RANK_EDGE = { 0: 'none', 1: 'weak', 2: 'strong' }
const clampP = (p) => Math.min(0.98, Math.max(0.02, Number(p)))
const logit = (p) => { const x = Math.min(Math.max(Number(p), 1e-6), 1 - 1e-6); return Math.log(x / (1 - x)) }
const sigmoid = (z) => 1 / (1 + Math.exp(-z))
const normEdge = (e) => { const v = String(e || 'none').toLowerCase().trim(); return v in EDGE_RANK ? v : 'none' }
const median = (arr) => { const s = [...arr].sort((a, b) => a - b); return s[Math.floor(s.length / 2)] }

// --- forecasting contract (matches opus_blend.py:41-47 + opus_forecaster.SYSTEM) ---
const CONTRACT = {
  type: 'object',
  additionalProperties: false,
  required: ['probability', 'edge', 'reasoning'],
  properties: {
    probability: { type: 'number', minimum: 0, maximum: 1, description: 'P(YES) as of the due date, calibrated. Never 0 or 1. Use the crowd value as your prior; only move off it for a concrete, dated, crowd-unpriced reason.' },
    edge: { type: 'string', enum: ['none', 'weak', 'strong'], description: 'real decorrelated info BEYOND the crowd price. "none" = default, no dated unpriced fact, defer to crowd. "weak" = soft directional reason. "strong" = a concrete dated fact the crowd has not priced. Claiming "strong" without a dated unpriced fact is an error.' },
    reasoning: { type: 'string', description: '<=2 sentences; cite the decisive fact + its date' },
  },
}

const GUIDE = (q) => [
  'You are Vati, a careful, calibrated probabilistic forecaster. Forecast ONE question that resolves in the future, as of the stated due date.',
  '',
  `Question: ${q.question}`,
  q.resolution_criteria ? `Resolution criteria: ${String(q.resolution_criteria).slice(0, 1200)}` : '',
  q.background ? `Background: ${String(q.background).slice(0, 800)}` : '',
  (q.crowd_value === null || q.crowd_value === undefined)
    ? 'No crowd/quant prior is available for this question (our own data did not cover it) — forecast it from your live web research, well-calibrated. Set edge="strong" if you found decisive dated facts, else "weak".'
    : `Calibrated crowd prior (P_YES): ${q.crowd_value}. Treat it as a strong prior; only move off it for a concrete dated reason the crowd plausibly has not priced.`,
  `Forecast as of: ${q.due}. Source: ${q.source}.`,
  '',
  'METHOD: Use web search (WebSearch / WebFetch) to find concrete, DATED facts relevant to resolution. Treat the crowd prior as a strong prior; only move off it for a specific dated reason the crowd plausibly has not priced. Use NOTHING published after the due date. Be calibrated; never output 0 or 1.',
  'Default edge to "none" and return the crowd prior unless you found a dated, crowd-unpriced fact. Output via the StructuredOutput tool only.',
].filter(Boolean).join('\n')

const qid = (q) => (Array.isArray(q.id) ? JSON.stringify(q.id) : q.id)

// === Stage 1: Sonnet triage, one research agent per question ===
phase('Triage')
log(`Stage 1 (Sonnet, web-researched): ${QUESTIONS.length} judgmental questions`)
const triaged = (await parallel(QUESTIONS.map((q, i) => () =>
  agent(GUIDE(q), { label: `triage:${q.source}:${i}`, phase: 'Triage', model: 'sonnet', schema: CONTRACT })
    .then(r => ({ q, p: clampP(r.probability), edge: normEdge(r.edge), reasoning: String(r.reasoning || '').slice(0, 300) }))
))).filter(Boolean)

// Movers = edge>=weak. Prioritise (strong first, then biggest departure from the crowd) and
// CAP, so Opus spend is deterministic: Opus calls <= MOVER_CAP * COUNCIL. Movers beyond the cap
// keep their Sonnet forecast (still edge-blended in opus_blend, just no Opus refinement).
const allMovers = triaged.filter(t => EDGE_RANK[t.edge] >= 1).sort((a, b) =>
  (EDGE_RANK[b.edge] - EDGE_RANK[a.edge]) ||
  (Math.abs(b.p - Number(b.q.crowd_value ?? b.p)) - Math.abs(a.p - Number(a.q.crowd_value ?? a.p))))
const movers = allMovers.slice(0, MOVER_CAP)
const capped = allMovers.length - movers.length
log(`Stage 1 done: ${triaged.length}/${QUESTIONS.length} forecast; ${allMovers.length} movers (edge>=weak)` +
    (capped > 0 ? `, capped to top ${movers.length} (${capped} keep Sonnet forecast)` : '') +
    ` -> Opus ${COUNCIL}-council = ${movers.length * COUNCIL} Opus calls`)

// === Stage 2: Opus council on movers only (flattened for full concurrency) ===
phase('Council')
const councilByMover = {}
if (movers.length) {
  const jobs = []
  movers.forEach((m, mi) => { for (let k = 0; k < COUNCIL; k++) jobs.push({ mi, k, m }) })
  const samples = await parallel(jobs.map(j => () =>
    agent(GUIDE(j.m.q), { label: `council:${j.mi}:${j.k}`, phase: 'Council', model: 'opus', schema: CONTRACT })
      .then(r => ({ mi: j.mi, p: clampP(r.probability), edge: normEdge(r.edge), reasoning: String(r.reasoning || '').slice(0, 300) }))
  ))
  for (const s of samples.filter(Boolean)) (councilByMover[s.mi] ||= []).push(s)
}

// === Assemble final map: triage default, council aggregate overrides movers ===
const final = {}
for (const t of triaged) final[qid(t.q)] = { probability: Number(clampP(t.p).toFixed(6)), edge: t.edge, reasoning: t.reasoning }
let moved = 0
movers.forEach((m, mi) => {
  const s = councilByMover[mi]
  if (!s || !s.length) return // fall back to Stage-1 forecast already in `final`
  const p = sigmoid(median(s.map(x => logit(x.p))))
  const edge = RANK_EDGE[median(s.map(x => EDGE_RANK[x.edge]))]
  const why = s.reduce((a, b) => (EDGE_RANK[b.edge] > EDGE_RANK[a.edge] ? b : a)).reasoning
  final[qid(m.q)] = { probability: Number(p.toFixed(6)), edge, reasoning: why }
  if (EDGE_RANK[edge] >= 1) moved++
})

const willMove = Object.values(final).filter(v => EDGE_RANK[v.edge] >= 1).length
log(`forecastbench-judge done: ${Object.keys(final).length} forecasts; ${willMove} carry edge>=weak (will move the crowd anchor in opus_blend)`)
return final
