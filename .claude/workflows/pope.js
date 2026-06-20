export const meta = {
  name: 'pope',
  description: 'The Pope System (standard/cheap tier): Sonnet channel miners generate disruptive pre-consensus theses, a grounded adversarial gate refutes each + scores dual probabilities, synthesis emits a renderable spec. ~15-20 agents. Horizon-aware: horizon:"long" (default, 2030-2040 structural) or horizon:"short" (3-18 month catalysts). For the deep Opus version use pope-mega.',
  whenToUse: 'On demand to predict where scarcity/value migrates next in any area, affordably. Output is a JSON spec consumed by engine/pope/render.py.',
  phases: [
    { title: 'Generate', detail: 'Sonnet channel miners read FUTURE_MAP + propose disruptive candidates' },
    { title: 'Gate+Refute', detail: 'grounded price-channel check, adversarial refute, dual-probability scoring' },
    { title: 'Synthesize', detail: 'cross-cutting read + select top theses into a renderable spec' },
    { title: 'Implications', detail: 'per surviving call: exposure, action, ROI logic, who gains/loses, what reprices, next constraint, earliest sign' },
  ],
}

// args arrives as a JSON STRING in this harness; parse it.
const A = (() => { try { return typeof args === 'string' ? JSON.parse(args) : (args || {}) } catch { return {} } })()

const domain = A.domain || 'any area, wide open across all industries'
const MODEL = A.model || 'sonnet'
const HORIZON = (A.horizon || 'long').toLowerCase()
const SHORT = HORIZON === 'short' || HORIZON === 'near' || HORIZON === 'near-term'
const perChannel = A.per_channel || 2
const topK = A.top_k || 6
const date = A.date || 'undated'

const LONG_CHANNELS = [
  { key: 'physical-limits', lens: 'a hard physical or thermodynamic limit (energy, heat, mass, rate) that forces a shift almost nobody is pricing' },
  { key: 'materials-chokepoint', lens: 'an inelastic upstream material or midstream processing chokepoint hidden beneath a popular theme; a granular sub-node nobody stockpiled' },
  { key: 'constraint-migration', lens: 'a constraint-migration cascade: once the obvious bottleneck gets funded, rent jumps one layer upstream to an unpriced node' },
  { key: 'pricing-arbitrage', lens: 'something structurally true and near-certain markets have not priced because it is boring, invisible, or hard to financialize (human capital, permits, disposal capacity)' },
  { key: 'second-order', lens: 'the second-order consequence the obvious trend forces next, which the loud first-order narrative ignores' },
  { key: 'demographic-locks', lens: 'an already-determined demographic or biological fact (cohorts already born, aging) that guarantees future demand or scarcity' },
  { key: 'policy-weaponization', lens: 'a geopolitical capture or export-control move on a specific granular sub-node, below the level of headline metals' },
  { key: 'wildcard', lens: 'a deliberately contrarian, anti-consensus, maximally disruptive call; aperture fully open (the gate keeps it honest later)' },
]
const SHORT_CHANNELS = [
  { key: 'scheduled-catalyst', lens: 'a specific DATED event in the next 3-18 months (ruling, decision, election, launch, contract/treaty expiry, print) whose outcome the market is mis-handicapping' },
  { key: 'flow-imbalance', lens: 'a near-term supply/demand or inventory imbalance (shortage or glut) that will visibly clear within months and reprice a specific input' },
  { key: 'capacity-online', lens: 'specific new capacity, a new entrant, or a ramp coming online inside the window that breaks or makes a current price' },
  { key: 'policy-pending', lens: 'a pending policy, export-control, tariff, or subsidy decision with a KNOWN decision date inside the window whose direction is underpriced' },
  { key: 'positioning-unwind', lens: 'a crowded consensus trade or narrative about to break on a near-term data print; the consensus is the mispricing' },
  { key: 'second-order-shock', lens: 'the near-term second-order consequence of a RECENT shock (last 1-6 months) the market has not yet propagated' },
  { key: 'supply-disruption', lens: 'a near-term supply disruption already in motion (outage, strike, sanction, weather) whose price bite has not yet landed' },
  { key: 'wildcard-near', lens: 'a deliberately contrarian near-term call; aperture fully open (the gate keeps it honest later)' },
]
const nCh = A.channels || 5
const CHANNELS = (SHORT ? SHORT_CHANNELS : LONG_CHANNELS).slice(0, nCh)

const RESOLVE_WINDOW = SHORT ? 'resolve in the next 3 to 18 months, with resolution dates between 2026-09-30 and 2027-12-31' : 'resolve 2030 to 2040'
const HORIZON_STR = SHORT ? 'next 3 to 18 months (through 2027)' : '2030 to 2040'
const OBJECT = SHORT
  ? 'a SPECIFIC, dated, near-certain CATALYST or clearing imbalance that forces a repricing the market has NOT yet handicapped, not a decade-scale structural lock.'
  : 'a specific BINDING CONSTRAINT (the inelastic input), not a theme.'

const GEN_SCHEMA = {
  type: 'object',
  properties: {
    theses: { type: 'array', items: { type: 'object', properties: {
      headline: { type: 'string', description: 'sharp specific claim; names the needle or catalyst, not the theme' },
      boom: { type: 'string', description: 'one line: what booms / who captures the rent' },
      domain: { type: 'string' },
      structural: { type: 'string', description: 'the mechanism that forces it, 2-4 sentences' },
      pre_consensus: { type: 'string', description: 'why still unpriced / generally unknown' },
      needle: { type: 'string', description: 'the specific inelastic input or dated catalyst that captures rent' },
      metric: { type: 'string', description: 'a dated leading metric to track it' },
      kill: { type: 'string', description: 'a concrete event that would falsify it' },
      resolves: { type: 'string', description: 'resolution date YYYY-MM-DD' },
    }, required: ['headline', 'boom', 'domain', 'structural', 'needle', 'metric', 'kill', 'resolves'] } },
  }, required: ['theses'],
}

const GATE_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['PROMOTE', 'DEMOTE'] },
    vision_p: { type: 'number', description: 'directional vision 0-100: strength of structural/catalyst case' },
    clause_p: { type: 'number', description: 'strict-clause 0-100: calibrated odds the exact dated clause resolves (<= vision_p)' },
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

const IMPL_SCHEMA = {
  type: 'object',
  properties: {
    exposed: { type: 'string', description: 'the buyer/exposed party who should care now: investor, operator, procurement desk, insurer, regulator, or strategy team' },
    action_now: { type: 'string', description: 'the practical action to consider now if this call matters to the exposed party; must be concrete, not generic monitoring' },
    decision_changed: { type: 'string', description: 'the budget, capex, procurement, portfolio, partnership, hedge, policy, or research decision this forecast changes' },
    roi_logic: { type: 'string', description: 'why acting early could be worth money or avoided loss; include asymmetry, timing, or cost-of-waiting logic' },
    rent_path: { type: 'string', description: '2-3 sentences: where the value/rent actually lands if the needle binds. Name real companies, assets, or regions, never "the industry".' },
    winners: { type: 'array', items: { type: 'object', properties: {
      who: { type: 'string', description: 'a named actor, asset, or region' },
      why: { type: 'string', description: 'one line: the mechanism by which they capture the value' } }, required: ['who', 'why'] } },
    losers: { type: 'array', items: { type: 'object', properties: {
      who: { type: 'string', description: 'whoever gets disintermediated or repriced down, named' },
      why: { type: 'string' } }, required: ['who', 'why'] } },
    reprices: { type: 'string', description: 'the specific instrument, asset, or contract that reprices and in which direction; if nothing prices it cleanly, say so plainly' },
    next_constraint: { type: 'string', description: 'the next binding constraint this call creates one layer deeper once it binds (continue the spine: rent -> constraint -> next constraint)' },
    watch: { type: 'string', description: 'the earliest concrete, observable, ideally dated marker that this cascade has begun' },
  }, required: ['exposed', 'action_now', 'decision_changed', 'roi_logic', 'rent_path', 'winners', 'losers', 'next_constraint', 'watch'],
}

const IMPL_PROMPT = (t, ground) => `You are the implications layer of the Pope System. This call already survived the adversarial gate. Your job is to work out the real-world consequences IF it resolves true, at the same rigor as the call itself. Do NOT restate or re-argue the call. Assume the needle binds.
Call:
${JSON.stringify(t)}
${ground ? 'Do ONE focused web search to anchor the named winners and losers in real, current entities (do not rabbit-hole).' : ''}
Derive, every item concrete and falsifiable:
- exposed: the buyer or stakeholder who should care now. Name the desk/function or asset owner, not "everyone".
- action_now: the practical step to consider before the market or budget cycle catches up.
- decision_changed: the concrete investment, procurement, capex, hedge, partnership, policy, or research decision this alters.
- roi_logic: why acting early could be worth money or avoided loss. Name the asymmetry, timing edge, or cost of waiting.
- rent_path: where value actually lands. Name real companies, assets, or regions, never "the industry" or "consumers".
- winners and losers: 2 to 3 each, named, each with the one-line mechanism. A loser is whoever gets disintermediated or repriced down, not a vague group.
- reprices: the specific instrument or contract that moves and the direction. If nothing prices it cleanly, say exactly that.
- next_constraint: where the binding constraint moves one layer deeper once this one binds.
- watch: the earliest observable, ideally dated, marker that the cascade has started.
No vague "could transform" or "set to reshape" language. No hedging. ${STYLE}`

const STYLE = 'Write prose in plain, human English. No em-dashes. No promotional filler. Mechanism first. Name the specific input or event, never a vague theme.'
const GROUND_LOOP = `Reason AGENTICALLY over the measured data layer — do not read one dump and free-associate. From the repo root, loop these verbs as your reasoning needs them, chaining each on the specific input you suspect:
- \`uv run python -m engine.cli world-grade "${domain}"\` — where the substrate is rich vs blind for this area; a GAP layer is either your edge or your blind spot (say which).
- \`uv run python -m engine.cli data-query depend "<input>"\` — walk the citation-dependency edges to the INELASTIC INPUT (a mid-weight draws_on with heavy inbound load). The needle is the constraint, never the curve.
- \`uv run python -m engine.cli data-query signals "<topic>"\` — the dated base rate (trends + detector fires + patent HHI); cite the specific signal you lean on.
- \`uv run python -m engine.cli data-query entities "<topic>"\` — who actually holds / operates / signed it.
- \`uv run python -m engine.cli data-query market "<topic>"\` — the priced-in gate (a liquid market near your P = PRICED; quote the gap or kill it).
(\`engine.cli ground "${domain}"\` prints all of these at once for a quick overview first.)`
const GROUND = SHORT
  ? `${GROUND_LOOP} Then Read FUTURE_MAP.md so you do not duplicate existing calls, and web-search the CURRENT state of this catalyst (latest news, live price/odds, scheduled date).`
  : `${GROUND_LOOP} Then Read FUTURE_MAP.md and skim existing calls so you do NOT duplicate them; go deeper or adjacent.`

// ---- phase 1: generate wide (grounded in FUTURE_MAP) -----------------------
phase('Generate')
log(`Pope (${MODEL}) [${SHORT ? 'SHORT/catalyst' : 'LONG/structural'}] on: ${domain} (${CHANNELS.length} channels x ${perChannel})`)
const generated = await parallel(CHANNELS.map((ch) => () =>
  agent(`You are a ${SHORT ? 'near-term catalyst forecaster' : 'pre-consensus foresight miner'} on the "${ch.key}" channel. Target area: ${domain}. Your lens: ${ch.lens}.
GROUNDING: ${GROUND}
Generate ${perChannel} of the most DISRUPTIVE, unaccounted-for, confident ${SHORT ? 'short-horizon' : 'long-horizon'} calls through this lens. Each must ${RESOLVE_WINDOW}. Be bold and non-obvious. Each must name ${OBJECT}
${SHORT ? 'State the EXACT clause that resolves YES/NO, its resolution date, and the falsifier.' : ''}
${STYLE}`, { label: `gen:${ch.key}`, phase: 'Generate', schema: GEN_SCHEMA, model: MODEL, agentType: 'general-purpose' })))

const candidates = generated.filter(Boolean).flatMap((g) => g.theses || [])
log(`generated ${candidates.length} candidates; gating + refuting`)

// ---- phase 2: grounded gate + adversarial refute + dual-probability --------
phase('Gate+Refute')
const gated = await parallel(candidates.map((c) => () =>
  agent(SHORT
    ? `You are the adversarial gate for the Pope System (SHORT-horizon / catalyst mode). Candidate:
${JSON.stringify(c)}
First run \`uv run python -m engine.cli ground "${(c.needle || c.headline || domain).replace(/"/g, '')}"\` from the repo root: its MARKET ANCHOR section is the priced-in gate (a liquid market near your clause_p = PRICED) and its SIGNALS are the measured reality to check this claim against. Then do ONE focused web search to anchor the LIVE reality: current price/odds/consensus and the scheduled date (do not rabbit-hole). Then:
1. WILL IT RESOLVE IN WINDOW: confirm it resolves within 3-18 months. If it can slip years, DEMOTE.
2. IS IT UNPRICED NOW: if already in futures, prediction-market odds, or sell-side models, lean DEMOTE.
3. ADVERSARIAL REFUTE: try to prove it is already priced OR will not resolve in window; if it survives, say why.
4. SCORE: vision_p = strength of the catalyst case. clause_p = calibrated odds the EXACT dated clause resolves YES by its date (<= vision_p; near 50 is fine). Do not inflate.
5. Tighten and echo all fields. PROMOTE only if it resolves in window, is unpriced now, and survives refute.
${STYLE}`
    : `You are the adversarial gate for the Pope System. Candidate:
${JSON.stringify(c)}
First run \`uv run python -m engine.cli ground "${(c.needle || c.headline || domain).replace(/"/g, '')}"\` from the repo root: its MARKET ANCHOR section is the priced-in gate (a liquid market near your clause_p = PRICED, so quote the gap or DEMOTE) and its SIGNALS + DEPENDENCY edges confirm whether the input is genuinely inelastic. Then do ONE focused web search to anchor a LIVE price / lead-time / funding / capacity reality for the named constraint (do not rabbit-hole). Then:
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
const spec = await agent(`You are the synthesis layer of the Pope System (${SHORT ? 'SHORT-horizon / catalyst board' : 'long-horizon structural board'}). Target area: ${domain}.
Calls that survived the adversarial gate:
${JSON.stringify(pool)}
Select the strongest ${topK} (favor diverse mechanisms and the highest, most defensible edge; drop near-duplicates). Assign ids P1..P${topK} by descending conviction. Write a one-paragraph cross-cutting synthesis naming the loudest shared shift, plus a title and an italic subtitle. Echo every selected thesis with ALL fields intact (vision_p, clause_p, price_channel, refute, why). Move borderline calls into runner_ups with a one-line why_not.
${STYLE}`, { label: 'synthesize', phase: 'Synthesize', schema: SYNTH_SCHEMA, model: MODEL })

// ---- phase 4: real-world implications, one focused pass per surviving call --
phase('Implications')
const selected = spec.theses || []
log(`deriving implications for ${selected.length} calls`)
const impls = await parallel(selected.map((t) => () =>
  agent(IMPL_PROMPT(t, false), { label: `impl:${t.id || (t.domain || 'x').slice(0, 10)}`, phase: 'Implications', schema: IMPL_SCHEMA, model: MODEL })))
const theses = selected.map((t, i) => (impls[i] ? { ...t, implications: impls[i] } : t))

return { ...spec, theses, domain, date, horizon: HORIZON_STR, regime: SHORT ? 'short' : 'long' }
