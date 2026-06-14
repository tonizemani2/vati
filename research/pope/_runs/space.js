export const meta = {
  name: 'pope-pro-space',
  description: 'Pope PRO, domain BAKED IN (space). Opus ideation+synthesis, Sonnet gate. Domain hardcoded because the launcher drops args; channels trimmed to 5.',
  phases: [
    { title: 'Generate', detail: 'Opus channel miners (space)', model: 'opus' },
    { title: 'Gate+Refute', detail: 'Sonnet adversarial gate + dual-probability scoring' },
    { title: 'Synthesize', detail: 'Opus synthesis into renderable spec', model: 'opus' },
  ],
}

const domain = 'space and the space economy (launch vehicles and propulsion, satellites and constellations, in-orbit infrastructure and servicing, lunar and cislunar, space materials and manufacturing, ground segment and spectrum)'
const GEN_MODEL = 'opus', GATE_MODEL = 'sonnet', SYNTH_MODEL = 'opus'
const perChannel = 2, topK = 6, date = '2026-06-14'

const ALL_CHANNELS = [
  { key: 'physical-limits', lens: 'a hard physical or thermodynamic limit (energy, heat, mass, rate, orbital mechanics, radiation) that forces a shift almost nobody is pricing' },
  { key: 'materials-chokepoint', lens: 'an inelastic upstream material or midstream processing chokepoint hidden beneath a popular theme; a granular sub-node nobody stockpiled' },
  { key: 'constraint-migration', lens: 'a constraint-migration cascade: once the obvious bottleneck gets funded, rent jumps one layer upstream to an unpriced node' },
  { key: 'pricing-arbitrage', lens: 'something structurally true and near-certain markets have not priced because it is boring, invisible, or hard to financialize (human capital, permits, spectrum, range capacity)' },
  { key: 'second-order', lens: 'the second-order consequence the obvious trend (cheap launch, proliferated LEO) forces next, which the loud first-order narrative ignores' },
  { key: 'wildcard', lens: 'a deliberately contrarian, anti-consensus, maximally disruptive space call; aperture fully open (the gate keeps it honest later)' },
]
const CHANNELS = ALL_CHANNELS.slice(0, 5)

const GEN_SCHEMA = { type: 'object', properties: { theses: { type: 'array', items: { type: 'object', properties: {
  headline: { type: 'string' }, boom: { type: 'string' }, domain: { type: 'string' }, structural: { type: 'string' },
  pre_consensus: { type: 'string' }, needle: { type: 'string' }, metric: { type: 'string' }, kill: { type: 'string' }, resolves: { type: 'string' },
}, required: ['headline','boom','domain','structural','needle','metric','kill','resolves'] } } }, required: ['theses'] }
const GATE_SCHEMA = { type: 'object', properties: {
  verdict: { type: 'string', enum: ['PROMOTE','DEMOTE'] }, vision_p: { type: 'number' }, clause_p: { type: 'number' },
  price_channel: { type: 'string' }, refute: { type: 'string' }, headline: { type: 'string' }, boom: { type: 'string' }, domain: { type: 'string' },
  structural: { type: 'string' }, pre_consensus: { type: 'string' }, needle: { type: 'string' }, metric: { type: 'string' }, kill: { type: 'string' }, resolves: { type: 'string' }, why: { type: 'string' },
}, required: ['verdict','vision_p','clause_p','refute','headline','boom','needle','kill','resolves','why'] }
const SYNTH_SCHEMA = { type: 'object', properties: {
  title: { type: 'string' }, subtitle: { type: 'string' }, synthesis: { type: 'string' },
  theses: { type: 'array', items: { type: 'object', properties: {
    id: { type: 'string' }, headline: { type: 'string' }, boom: { type: 'string' }, domain: { type: 'string' }, vision_p: { type: 'number' }, clause_p: { type: 'number' }, resolves: { type: 'string' },
    structural: { type: 'string' }, pre_consensus: { type: 'string' }, price_channel: { type: 'string' }, needle: { type: 'string' }, metric: { type: 'string' }, kill: { type: 'string' }, refute: { type: 'string' }, why: { type: 'string' },
  }, required: ['id','headline','boom','vision_p','clause_p','resolves','structural','needle','kill','why'] } },
  runner_ups: { type: 'array', items: { type: 'object', properties: { seed: { type: 'string' }, case: { type: 'string' }, why_not: { type: 'string' } }, required: ['seed','case','why_not'] } },
}, required: ['title','subtitle','synthesis','theses'] }

const STYLE = 'Write prose in plain, human English. No em-dashes. No promotional filler. Physical/demographic mechanism first. Name the inelastic needle, never a vague theme.'

phase('Generate')
log(`Pope PRO (BAKED) on: ${domain}`)
const generated = await parallel(CHANNELS.map((ch) => () =>
  agent(`You are a pre-consensus foresight miner on the "${ch.key}" channel. Target area: ${domain}. Your lens: ${ch.lens}.
GROUNDING: first Read FUTURE_MAP.md in the repo root and skim existing calls in or near this area (it has a defense-space-dualuse channel), so you do NOT duplicate them. Go deeper or adjacent.
Generate ${perChannel} of the most DISRUPTIVE, unaccounted-for, confident long-horizon (resolve 2030-2040) structural calls through this lens. Be bold and non-obvious. Each must name a specific BINDING CONSTRAINT (the inelastic input), not a theme.
${STYLE}`, { label: `gen:${ch.key}`, phase: 'Generate', schema: GEN_SCHEMA, model: GEN_MODEL, agentType: 'general-purpose' })))
const candidates = generated.filter(Boolean).flatMap((g) => g.theses || [])
log(`generated ${candidates.length} candidates`)

phase('Gate+Refute')
const gated = await parallel(candidates.map((c) => () =>
  agent(`You are the adversarial gate for the Pope System. Candidate:
${JSON.stringify(c)}
Do ONE focused web search to anchor a LIVE price / lead-time / funding / capacity reality (do not rabbit-hole). Then:
1. PRE-CONSENSUS + PRICE CHANNEL: narrative-obscure != unpriced. If already in spot prices / equity coverage / sell-side, lean DEMOTE.
2. SUPPLY ELASTICITY: confirm genuinely inelastic. If elastic, DEMOTE.
3. ADVERSARIAL REFUTE: try to prove it wrong or already priced; if it survives, say why.
4. SCORE: vision_p (strength of structural case, can be high) and clause_p (calibrated odds the exact dated clause resolves, <= vision_p, near 50 ok). Do not inflate.
5. Tighten and echo all fields. PROMOTE only if pre-consensus, inelastic, survives refute.
${STYLE}`, { label: `gate:${(c.domain||'x').slice(0,16)}`, phase: 'Gate+Refute', schema: GATE_SCHEMA, model: GATE_MODEL, agentType: 'general-purpose' })))
const promoted = gated.filter(Boolean).filter((g) => g.verdict === 'PROMOTE')
log(`${promoted.length}/${candidates.length} promoted`)

phase('Synthesize')
const pool = promoted.length ? promoted : gated.filter(Boolean)
const spec = await agent(`You are the synthesis layer of the Pope System. Target area: ${domain}.
Survivors:
${JSON.stringify(pool)}
Select the strongest ${topK} (diverse mechanisms, highest defensible edge, drop near-duplicates). Assign ids P1..P${topK} by descending conviction. Write a one-paragraph cross-cutting synthesis, a title, and an italic subtitle. Echo every selected thesis with ALL fields intact. Move borderline calls to runner_ups with a one-line why_not.
${STYLE}`, { label: 'synthesize', phase: 'Synthesize', schema: SYNTH_SCHEMA, model: SYNTH_MODEL })

return { ...spec, domain, date, horizon: '2030 to 2040' }
