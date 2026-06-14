export const meta = {
  name: 'pope',
  description: 'The Pope System (standard/cheap tier): Sonnet channel miners generate disruptive pre-consensus theses, a grounded adversarial gate refutes each + scores dual probabilities, synthesis emits a renderable spec. ~15-20 agents. For the deep Opus version use pope-mega.',
  whenToUse: 'On demand to predict where scarcity/value migrates next in any area, affordably. Output is a JSON spec consumed by engine/pope/render.py.',
  phases: [
    { title: 'Generate', detail: 'Sonnet channel miners read FUTURE_MAP + propose disruptive candidates' },
    { title: 'Gate+Refute', detail: 'grounded price-channel check, adversarial refute, dual-probability scoring' },
    { title: 'Synthesize', detail: 'cross-cutting read + select top theses into a renderable spec' },
  ],
}

// ---- inputs (all optional) -------------------------------------------------
const domain = (args && args.domain) || 'any area, wide open across all industries'
const MODEL = (args && args.model) || 'sonnet'
const perChannel = (args && args.per_channel) || 2
const topK = (args && args.top_k) || 6
const date = (args && args.date) || 'undated'

// orthogonal channels; cheap tier uses a subset (default 5)
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
const nCh = (args && args.channels) || 5
const CHANNELS = ALL_CHANNELS.slice(0, nCh)

const GEN_SCHEMA = {
  type: 'object',
  properties: {
    theses: { type: 'array', items: { type: 'object', properties: {
      headline: { type: 'string', description: 'sharp specific claim; names the needle not the theme' },
      boom: { type: 'string', description: 'one line: what booms / who captures the rent' },
      domain: { type: 'string' },
      structural: { type: 'string', description: 'the physical/demographic mechanism that forces it, 2-4 sentences' },
      pre_consensus: { type: 'string', description: 'why still unpriced / generally unknown' },
      needle: { type: 'string', description: 'the specific inelastic input that captures rent' },
      metric: { type: 'string', description: 'a dated leading metric to track it' },
      kill: { type: 'string', description: 'a concrete event that would falsify it' },
      resolves: { type: 'string', description: 'resolution date YYYY-MM-DD, long horizon' },
    }, required: ['headline', 'boom', 'domain', 'structural', 'needle', 'metric', 'kill', 'resolves'] } },
  }, required: ['theses'],
}

const GATE_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['PROMOTE', 'DEMOTE'] },
    vision_p: { type: 'number', description: 'directional vision 0-100: strength of structural case' },
    clause_p: { type: 'number', description: 'strict-clause 0-100: calibrated odds the exact dated clause resolves (timing+measurement tax, <= vision_p)' },
    price_channel: { type: 'string', description: 'honest live price/anchor check from the web search' },
    refute: { type: 'string', description: 'result of trying to prove it already priced; if survives, why' },
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

// ---- phase 1: generate wide (grounded in FUTURE_MAP) -----------------------
phase('Generate')
log(`Pope (${MODEL}) on: ${domain} (${CHANNELS.length} channels x ${perChannel})`)
const generated = await parallel(CHANNELS.map((ch) => () =>
  agent(`You are a pre-consensus foresight miner on the "${ch.key}" channel. Target area: ${domain}. Your lens: ${ch.lens}.
GROUNDING: first Read FUTURE_MAP.md in the repo root and skim any existing calls in or near this area, so you do NOT duplicate them. Go deeper or adjacent.
Generate ${perChannel} of the most DISRUPTIVE, unaccounted-for, confident long-horizon (resolve 2030-2040) structural calls through this lens. Be bold and non-obvious. Each must name a specific BINDING CONSTRAINT (the inelastic input), not a theme.
${STYLE}`, { label: `gen:${ch.key}`, phase: 'Generate', schema: GEN_SCHEMA, model: MODEL, agentType: 'general-purpose' })))

const candidates = generated.filter(Boolean).flatMap((g) => g.theses || [])
log(`generated ${candidates.length} candidates; gating + refuting`)

// ---- phase 2: grounded gate + adversarial refute + dual-probability --------
phase('Gate+Refute')
const gated = await parallel(candidates.map((c) => () =>
  agent(`You are the adversarial gate for the Pope System. Candidate:
${JSON.stringify(c)}
Do ONE focused web search to anchor a LIVE price / lead-time / funding / capacity reality for the named constraint (do not rabbit-hole). Then:
1. PRE-CONSENSUS + PRICE CHANNEL: narrative-obscure does not mean unpriced. If already reflected in spot prices, equity coverage, or sell-side models, lean DEMOTE.
2. SUPPLY ELASTICITY: confirm the input is genuinely inelastic (cannot be expanded with capital on the horizon). If elastic, DEMOTE.
3. ADVERSARIAL REFUTE: actively try to prove it wrong or already priced; if it survives, say precisely why.
4. SCORE: vision_p = strength of structural case (can be high). clause_p = calibrated odds the EXACT dated clause resolves true after the timing and measurement tax (must be <= vision_p; near 50 is fine). Do not inflate to look bold.
5. Tighten and echo all fields. PROMOTE only if genuinely pre-consensus, inelastic, and it survives refute.
${STYLE}`, { label: `gate:${(c.domain || 'x').slice(0, 16)}`, phase: 'Gate+Refute', schema: GATE_SCHEMA, model: MODEL, agentType: 'general-purpose' })))

const promoted = gated.filter(Boolean).filter((g) => g.verdict === 'PROMOTE')
log(`${promoted.length}/${candidates.length} promoted (survived refute)`)

// ---- phase 3: synthesize into a renderable spec ----------------------------
phase('Synthesize')
const pool = promoted.length ? promoted : gated.filter(Boolean)
const spec = await agent(`You are the synthesis layer of the Pope System. Target area: ${domain}.
Calls that survived the adversarial gate:
${JSON.stringify(pool)}
Select the strongest ${topK} (favor diverse mechanisms and the highest, most defensible edge; drop near-duplicates). Assign ids P1..P${topK} by descending conviction. Write a one-paragraph cross-cutting synthesis naming the loudest shared shift, plus a title and an italic subtitle. Echo every selected thesis with ALL fields intact (vision_p, clause_p, price_channel, refute, why). Move borderline calls into runner_ups with a one-line why_not.
${STYLE}`, { label: 'synthesize', phase: 'Synthesize', schema: SYNTH_SCHEMA, model: MODEL })

return { ...spec, domain, date, horizon: '2030 to 2040' }
