export const meta = {
  name: 'pope-mega',
  description: 'Pope MEGA: the premium tier. 10 Opus channel miners x3 + per-candidate adversarial Opus gate + synthesis (~40 agents, ~2M tokens). Maximum coverage and depth. Use when budget allows; otherwise use the cheaper /pope.',
  whenToUse: 'High-stakes, comprehensive board where you want maximum disruptive coverage and the deepest adversarial refute. Expensive.',
  phases: [
    { title: 'Generate', detail: '10 orthogonal Opus channel miners propose disruptive candidates', model: 'opus' },
    { title: 'Gate+Refute', detail: 'per-candidate adversarial Opus refute + dual-probability scoring', model: 'opus' },
    { title: 'Synthesize', detail: 'cross-cutting read + select top theses into a renderable spec', model: 'opus' },
  ],
}

const domain = (args && args.domain) || 'any area, wide open across all industries'
const perChannel = (args && args.per_channel) || 3
const topK = (args && args.top_k) || 8
const date = (args && args.date) || 'undated'

const CHANNELS = [
  { key: 'physical-limits', lens: 'a hard physical or thermodynamic limit (energy, heat, mass, rate, conservation law) that forces a shift almost nobody is pricing' },
  { key: 'demographic-locks', lens: 'an already-determined demographic or biological fact (cohorts already born, aging, fixed fertility) that guarantees future demand or scarcity' },
  { key: 'materials-chokepoint', lens: 'an inelastic upstream material or midstream processing chokepoint hidden beneath a popular theme; a granular sub-node nobody stockpiled' },
  { key: 'constraint-migration', lens: 'a constraint-migration cascade: once the obvious bottleneck gets funded, rent jumps one layer upstream to an unpriced node' },
  { key: 'methods-diffusion', lens: 'a research method or technique quietly crossing from one field into another and repricing the scarce input (data, verifier, reference set)' },
  { key: 'policy-weaponization', lens: 'a geopolitical capture or export-control / licensing move on a specific granular sub-node, below the level of headline metals' },
  { key: 'pricing-arbitrage', lens: 'something structurally true and near-certain that markets have not priced because it is boring, invisible, or hard to financialize (human capital, permits, disposal capacity)' },
  { key: 'patent-tell', lens: 'a tight cluster of <6 assignees fencing IP around an inelastic node, an early tell of where rent will concentrate' },
  { key: 'second-order', lens: 'the second-order consequence the obvious trend forces next, which the loud first-order narrative ignores' },
  { key: 'wildcard', lens: 'a deliberately contrarian, anti-consensus, maximally disruptive call; aperture fully open, generate boldly (the gate will keep it honest later)' },
]

const GEN_SCHEMA = {
  type: 'object',
  properties: {
    theses: { type: 'array', items: { type: 'object', properties: {
      headline: { type: 'string' }, boom: { type: 'string' }, domain: { type: 'string' },
      structural: { type: 'string' }, pre_consensus: { type: 'string' }, needle: { type: 'string' },
      metric: { type: 'string' }, kill: { type: 'string' }, resolves: { type: 'string' },
    }, required: ['headline', 'boom', 'domain', 'structural', 'needle', 'metric', 'kill', 'resolves'] } },
  }, required: ['theses'],
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
const GROUND = 'First Read FUTURE_MAP.md in the repo root and skim existing calls in or near this area so you do NOT duplicate them; go deeper or adjacent. Where useful, do a quick web search to ground a real number (price, lead time, funding, capacity).'

phase('Generate')
log(`Pope MEGA on: ${domain} (${CHANNELS.length} Opus channels x ${perChannel})`)
const generated = await parallel(CHANNELS.map((ch) => () =>
  agent(`You are a pre-consensus foresight miner on the "${ch.key}" channel. Target area: ${domain}. Your lens: ${ch.lens}.
${GROUND}
Generate ${perChannel} of the most DISRUPTIVE, unaccounted-for, confident long-horizon (resolve 2030-2040) structural calls through this lens. Be bold and non-obvious. Each must name a specific BINDING CONSTRAINT (the inelastic input), not a theme.
${STYLE}`, { label: `gen:${ch.key}`, phase: 'Generate', schema: GEN_SCHEMA, agentType: 'general-purpose' })))

const candidates = generated.filter(Boolean).flatMap((g) => g.theses || [])
log(`generated ${candidates.length} candidates; gating + refuting`)

phase('Gate+Refute')
const gated = await parallel(candidates.map((c) => () =>
  agent(`You are the adversarial gate for the Pope System. Candidate:
${JSON.stringify(c)}
Do a web search to anchor a LIVE price / lead-time / funding / capacity reality for the named constraint. Then:
1. PRE-CONSENSUS + PRICE CHANNEL: narrative-obscure != unpriced. If already in spot prices / equity coverage / sell-side models, lean DEMOTE.
2. SUPPLY ELASTICITY: confirm the input is genuinely inelastic. If elastic, DEMOTE.
3. ADVERSARIAL REFUTE: actively try to prove it wrong or already priced; if it survives, say precisely why.
4. SCORE: vision_p = strength of structural case (can be high). clause_p = calibrated odds the EXACT dated clause resolves (timing+measurement tax, <= vision_p, near 50 is fine). Do not inflate.
5. Tighten and echo all fields. PROMOTE only if pre-consensus, inelastic, and survives refute.
${STYLE}`, { label: `gate:${(c.domain || 'x').slice(0, 18)}`, phase: 'Gate+Refute', schema: GATE_SCHEMA, agentType: 'general-purpose' })))

const promoted = gated.filter(Boolean).filter((g) => g.verdict === 'PROMOTE')
log(`${promoted.length}/${candidates.length} promoted`)

phase('Synthesize')
const spec = await agent(`You are the synthesis layer of the Pope System. Target area: ${domain}.
Survivors of the adversarial gate:
${JSON.stringify(promoted)}
Select the strongest ${topK} (favor diverse mechanisms and the highest, most defensible edge; drop near-duplicates). Assign ids P1..P${topK} by descending conviction. Write a one-paragraph cross-cutting synthesis, a title, and an italic subtitle. Echo every selected thesis with ALL fields intact. Move borderline calls into runner_ups with a one-line why_not.
${STYLE}`, { label: 'synthesize', phase: 'Synthesize', schema: SYNTH_SCHEMA })

return { ...spec, domain, date, horizon: '2030 to 2040' }
