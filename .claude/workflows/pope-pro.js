export const meta = {
  name: 'pope-pro',
  description: 'The Pope System (PRO / in-between tier): OPUS does the irreplaceable work (disruptive ideation + final selection/synthesis), SONNET does the high-volume adversarial gate. ~7 Opus + ~12 Sonnet agents. Keeps Opus smartness where it is unmatched, cuts Opus draw ~5-6x vs pope-mega.',
  whenToUse: 'When you want Opus-grade ideation without the full pope-mega Opus quota. The default serious tier.',
  phases: [
    { title: 'Generate', detail: 'Opus channel miners read FUTURE_MAP + propose disruptive candidates', model: 'opus' },
    { title: 'Gate+Refute', detail: 'Sonnet: grounded price-channel check, adversarial refute, dual-probability scoring' },
    { title: 'Synthesize', detail: 'Opus: cross-cutting read + select top theses into a renderable spec', model: 'opus' },
  ],
}

// ---- inputs (all optional) -------------------------------------------------
const domain = (args && args.domain) || 'any area, wide open across all industries'
const GEN_MODEL = (args && args.gen_model) || 'opus'     // ideation: keep Opus
const GATE_MODEL = (args && args.gate_model) || 'sonnet' // volume: Sonnet
const SYNTH_MODEL = (args && args.synth_model) || 'opus' // judgment: Opus (1 agent)
const perChannel = (args && args.per_channel) || 2
const topK = (args && args.top_k) || 6
const date = (args && args.date) || 'undated'

const ALL_CHANNELS = [
  { key: 'physical-limits', lens: 'a hard physical or thermodynamic limit (energy, heat, mass, rate) that forces a shift almost nobody is pricing' },
  { key: 'materials-chokepoint', lens: 'an inelastic upstream material or midstream processing chokepoint hidden beneath a popular theme; a granular sub-node nobody stockpiled' },
  { key: 'constraint-migration', lens: 'a constraint-migration cascade: once the obvious bottleneck gets funded, rent jumps one layer upstream to an unpriced node' },
  { key: 'pricing-arbitrage', lens: 'something structurally true and near-certain markets have not priced because it is boring, invisible, or hard to financialize (human capital, permits, disposal capacity)' },
  { key: 'second-order', lens: 'the second-order consequence the obvious trend forces next, which the loud first-order narrative ignores' },
  { key: 'demographic-locks', lens: 'an already-determined demographic or biological fact (cohorts already born, aging) that guarantees future demand or scarcity' },
  { key: 'policy-weaponization', lens: 'a geopolitical capture or export-control move on a specific granular sub-node, below the level of headline metals' },
  { key: 'wildcard', lens: 'a deliberately contrarian, anti-consensus, maximally disruptive call; aperture fully open (the gate keeps it honest later)' },
]
const nCh = (args && args.channels) || 6
const CHANNELS = ALL_CHANNELS.slice(0, nCh)

const GEN_SCHEMA = {
  type: 'object',
  properties: { theses: { type: 'array', items: { type: 'object', properties: {
    headline: { type: 'string' }, boom: { type: 'string' }, domain: { type: 'string' },
    structural: { type: 'string' }, pre_consensus: { type: 'string' }, needle: { type: 'string' },
    metric: { type: 'string' }, kill: { type: 'string' }, resolves: { type: 'string' },
  }, required: ['headline', 'boom', 'domain', 'structural', 'needle', 'metric', 'kill', 'resolves'] } } },
  required: ['theses'],
}
const GATE_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['PROMOTE', 'DEMOTE'] },
    vision_p: { type: 'number' }, clause_p: { type: 'number' },
    price_channel: { type: 'string' }, refute: { type: 'string' },
    headline: { type: 'string' }, boom: { type: 'string' }, domain: { type: 'string' },
    structural: { type: 'string' }, pre_consensus: { type: 'string' }, needle: { type: 'string' },
    metric: { type: 'string' }, kill: { type: 'string' }, resolves: { type: 'string' }, why: { type: 'string' },
  }, required: ['verdict', 'vision_p', 'clause_p', 'refute', 'headline', 'boom', 'needle', 'kill', 'resolves', 'why'],
}
const SYNTH_SCHEMA = {
  type: 'object',
  properties: {
    title: { type: 'string' }, subtitle: { type: 'string' }, synthesis: { type: 'string' },
    theses: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, headline: { type: 'string' }, boom: { type: 'string' }, domain: { type: 'string' },
      vision_p: { type: 'number' }, clause_p: { type: 'number' }, resolves: { type: 'string' },
      structural: { type: 'string' }, pre_consensus: { type: 'string' }, price_channel: { type: 'string' },
      needle: { type: 'string' }, metric: { type: 'string' }, kill: { type: 'string' }, refute: { type: 'string' }, why: { type: 'string' },
    }, required: ['id', 'headline', 'boom', 'vision_p', 'clause_p', 'resolves', 'structural', 'needle', 'kill', 'why'] } },
    runner_ups: { type: 'array', items: { type: 'object', properties: {
      seed: { type: 'string' }, case: { type: 'string' }, why_not: { type: 'string' } }, required: ['seed', 'case', 'why_not'] } },
  }, required: ['title', 'subtitle', 'synthesis', 'theses'],
}

const STYLE = 'Write prose in plain, human English. No em-dashes. No promotional filler. Physical/demographic mechanism first. Name the inelastic needle, never a vague theme.'

phase('Generate')
log(`Pope PRO on: ${domain} (gen=${GEN_MODEL}, gate=${GATE_MODEL}, synth=${SYNTH_MODEL}; ${CHANNELS.length} channels x ${perChannel})`)
const generated = await parallel(CHANNELS.map((ch) => () =>
  agent(`You are a pre-consensus foresight miner on the "${ch.key}" channel. Target area: ${domain}. Your lens: ${ch.lens}.
GROUNDING: first Read FUTURE_MAP.md in the repo root and skim any existing calls in or near this area, so you do NOT duplicate them. Go deeper or adjacent.
Generate ${perChannel} of the most DISRUPTIVE, unaccounted-for, confident long-horizon (resolve 2030-2040) structural calls through this lens. Be bold and non-obvious. Each must name a specific BINDING CONSTRAINT (the inelastic input), not a theme.
${STYLE}`, { label: `gen:${ch.key}`, phase: 'Generate', schema: GEN_SCHEMA, model: GEN_MODEL, agentType: 'general-purpose' })))

const candidates = generated.filter(Boolean).flatMap((g) => g.theses || [])
log(`generated ${candidates.length} candidates; gating + refuting (sonnet)`)

phase('Gate+Refute')
const gated = await parallel(candidates.map((c) => () =>
  agent(`You are the adversarial gate for the Pope System. Candidate:
${JSON.stringify(c)}
Do ONE focused web search to anchor a LIVE price / lead-time / funding / capacity reality for the named constraint (do not rabbit-hole). Then:
1. PRE-CONSENSUS + PRICE CHANNEL: narrative-obscure does not mean unpriced. If already in spot prices / equity coverage / sell-side models, lean DEMOTE.
2. SUPPLY ELASTICITY: confirm the input is genuinely inelastic. If elastic, DEMOTE.
3. ADVERSARIAL REFUTE: actively try to prove it wrong or already priced; if it survives, say precisely why.
4. SCORE: vision_p = strength of structural case (can be high). clause_p = calibrated odds the EXACT dated clause resolves after the timing and measurement tax (<= vision_p; near 50 is fine). Do not inflate.
5. Tighten and echo all fields. PROMOTE only if genuinely pre-consensus, inelastic, and survives refute.
${STYLE}`, { label: `gate:${(c.domain || 'x').slice(0, 16)}`, phase: 'Gate+Refute', schema: GATE_SCHEMA, model: GATE_MODEL, agentType: 'general-purpose' })))

const promoted = gated.filter(Boolean).filter((g) => g.verdict === 'PROMOTE')
log(`${promoted.length}/${candidates.length} promoted (survived refute)`)

phase('Synthesize')
const pool = promoted.length ? promoted : gated.filter(Boolean)
const spec = await agent(`You are the synthesis layer of the Pope System. Target area: ${domain}.
Calls that survived the adversarial gate:
${JSON.stringify(pool)}
Select the strongest ${topK} (favor diverse mechanisms and the highest, most defensible edge; drop near-duplicates). Assign ids P1..P${topK} by descending conviction. Write a one-paragraph cross-cutting synthesis naming the loudest shared shift, plus a title and an italic subtitle. Echo every selected thesis with ALL fields intact (vision_p, clause_p, price_channel, refute, why). Move borderline calls into runner_ups with a one-line why_not.
${STYLE}`, { label: 'synthesize', phase: 'Synthesize', schema: SYNTH_SCHEMA, model: SYNTH_MODEL })

return { ...spec, domain, date, horizon: '2030 to 2040' }
