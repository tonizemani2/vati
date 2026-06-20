export const meta = {
  name: 'pope-capture',
  description: 'Pope CAPTURE (the "Ultra 2" value-capture layer): takes surviving Pope theses and turns each into a concrete agentic value-capture plan — named company, the role/person to contact, exactly what to say, and HOW value is actually captured (advisory, offtake, position, intel sale, brokered intro). Grounded in the entity graph (`engine.cli ground`) + live web search. ~1 reader + 1 capture agent per call (Opus). Run AFTER /pope or /pope-mega on the calls worth pursuing.',
  whenToUse: 'You have a board of structural calls and want the practical "so who do I call and how do I make money from this" plan, not just the thesis. The bridge from forecast to revenue.',
  phases: [
    { title: 'Resolve', detail: 'load the calls to work (from args.calls, a single thesis, or a board file)' },
    { title: 'Capture', detail: 'per call: walk the data layer (entities + dependency) + web search -> named targets, the ask, the value-capture mechanism, first move', model: 'opus' },
    { title: 'Refute', detail: 'per call: adversarial money-path test - is the payer real/budgeted, the ask reachable, is there a cleaner instrument; harden or PASS', model: 'opus' },
    { title: 'Prioritize', detail: 'rank the hardened capture plans by expected value and effort; emit the do-this-week shortlist', model: 'opus' },
  ],
}

const A = (() => { try { return typeof args === 'string' ? JSON.parse(args) : (args || {}) } catch { return {} } })()
const STYLE = 'Write in plain, direct English. No em-dashes. No vague "engage stakeholders" or "explore opportunities". Name the real org, the real role, the real money path. If something is unknown, say so and make finding it the first move.'

// ---- Resolve the calls to work on ------------------------------------------
phase('Resolve')
let calls = []
if (Array.isArray(A.calls) && A.calls.length) {
  calls = A.calls
} else if (A.headline || A.needle || A.thesis) {
  calls = [{ headline: A.headline || A.thesis, needle: A.needle || A.thesis, domain: A.domain || '', boom: A.boom || '' }]
} else if (A.board) {
  // a board file path: an agent reads it (workflow scripts have no fs) and returns the calls array
  const READ_SCHEMA = { type: 'object', properties: { calls: { type: 'array', items: { type: 'object', properties: {
    headline: { type: 'string' }, needle: { type: 'string' }, domain: { type: 'string' }, boom: { type: 'string' },
  }, required: ['headline'] } } }, required: ['calls'] }
  const r = await agent(`Read the Pope board JSON at ${A.board} (repo-relative is fine). Return its theses as a "calls" array, each with headline, needle (the specific inelastic input or dated catalyst), domain, and boom (the one-line claim). Keep every thesis.`,
    { label: 'read-board', phase: 'Resolve', schema: READ_SCHEMA, agentType: 'general-purpose' })
  calls = (r && r.calls) || []
}
calls = calls.filter(Boolean).slice(0, A.max || 12)
if (!calls.length) {
  log('No calls to work on. Pass {calls:[...]}, a single {headline,needle}, or {board:"path/to/board.json"}.')
  return { error: 'no_calls', hint: 'pass calls[], a single thesis, or a board path' }
}
log(`Pope CAPTURE on ${calls.length} call(s): turning theses into named targets + value-capture plans`)

// ---- Capture: per call, the agentic value-capture brief --------------------
phase('Capture')
const CAPTURE_SCHEMA = {
  type: 'object',
  properties: {
    headline: { type: 'string' },
    verdict: { type: 'string', enum: ['PURSUE', 'PASS'], description: 'is there a real, reachable value-capture path for a sharp independent forecasting shop?' },
    why: { type: 'string', description: 'one paragraph: why this is or is not capturable now, and by whom' },
    targets: { type: 'array', description: '2-4 named real-world targets who would pay for or act on this edge', items: { type: 'object', properties: {
      org: { type: 'string', description: 'the NAMED company, fund, agency, or operator (real, verified by search)' },
      role: { type: 'string', description: 'the specific role/desk to contact (e.g. Head of Procurement, CIO, Director of Critical Minerals Strategy)' },
      person: { type: 'string', description: 'the named individual in that role if findable by search, else "" and make finding them a first move' },
      care_about: { type: 'string', description: 'the specific reason THIS org cares: the exposure, the decision, the risk or upside this thesis hands them' },
      reach: { type: 'string', description: 'the concrete path to reach them: a warm intro route, a conference, a public RFP, a cold-email angle that would actually land' },
    }, required: ['org', 'role', 'care_about', 'reach'] } },
    the_ask: { type: 'string', description: 'exactly what to propose in the first conversation. Concrete, not "discuss a partnership".' },
    value_mechanism: { type: 'string', description: 'HOW value is actually captured: advisory retainer, paid research/intel, an offtake or supply position, equity/warrants, a brokered introduction fee, a trade/position we take ourselves, a data licence. Pick the realest one.' },
    who_pays: { type: 'string', description: 'who pays, for what, and a rough ticket size or position size; if we take a position instead, say the instrument and direction' },
    our_angle: { type: 'string', description: 'why a small, sharp, independent forecasting shop is credible to them on THIS: the specific proof/edge to lead with' },
    proof_to_show: { type: 'string', description: 'the specific Vaticinus artifact to put in front of them (a scored call, the dependency-graph read, the leak-free record, a dated pre-consensus call that already moved)' },
    instrument: { type: 'string', description: 'if there is a clean financial instrument to express this directly, name it and the direction; else "no clean instrument, value is in the relationship/advisory"' },
    first_move: { type: 'string', description: 'the single most leveraged action to take THIS WEEK. An email, a one-pager, a data pull, a specific person to find.' },
    checkpoints: { type: 'array', items: { type: 'string' }, description: '2-3 dated, observable near-term markers that this path is opening or closing' },
    disqualifier: { type: 'string', description: 'what you would see that means drop this and move on' },
    confidence: { type: 'string', enum: ['low', 'medium', 'high'] },
  },
  required: ['headline', 'verdict', 'why', 'targets', 'the_ask', 'value_mechanism', 'who_pays', 'first_move', 'confidence'],
}

const CAPTURE_PROMPT = (c) => `You are the value-capture layer of the Pope System. A structural forecast already survived the adversarial gate. Your job is NOT to re-argue it. Your job is to answer: who do we call, what do we say, and how do we actually make money from this edge.

THE CALL:
${JSON.stringify(c)}

STEP 1 — walk our data layer agentically (do not guess targets). From the repo root, on the needle "${(c.needle || c.headline || '').replace(/"/g, '')}":
- \`uv run python -m engine.cli data-query entities "${(c.needle || c.headline || '').replace(/"/g, '')}"\` — the NAMED REAL-WORLD MATCHES (actual permit holders, operators, contract signatories, projects, companies) in our entity graph. These are your candidate targets and proof we can name the real players.
- \`uv run python -m engine.cli data-query depend "${(c.needle || c.headline || '').replace(/"/g, '')}"\` — walk the dependency edges to the inelastic input, so you target the org that owns the REAL chokepoint, not the obvious name.
- \`uv run python -m engine.cli data-query market "${(c.needle || c.headline || '').replace(/"/g, '')}"\` — if it is already priced, a fund that trades it may be a better buyer than an operator.

STEP 2 — find the real people and orgs. Do focused web searches to: (a) confirm the named entities are real and current, (b) identify 2-4 specific organizations that are MOST EXPOSED to this thesis (they win big or lose big if the needle binds), and (c) find the actual role and, where possible, the named decision-maker to contact at each.

STEP 3 — design the capture. For each target, work out exactly why they care, what to propose, and how value is captured. Be concrete about the money: a retainer, an offtake position, equity, a paid intel feed, a brokered intro, or a position we take ourselves. Name who pays and roughly how much, or the instrument and direction if we express it as a trade.

Rules:
- Real named orgs and roles only, verified by search. A named individual where findable; otherwise set person to "" and make "find the decision-maker at X" a first move.
- The value mechanism must be real and specific. How does the dollar actually arrive.
- Lead with our credible edge: a leak-free scored record, the measured dependency-graph read, a dated pre-consensus call. Name the exact proof in proof_to_show.
- Set verdict PASS if there is genuinely no reachable capture path (too diffuse, too slow, no payer); say why in one line and stop. Better an honest PASS than a fantasy deal.
${STYLE}`

// ---- Refute: the adversarial money-path test (mega-style per-call hardening) -
const REFUTE_SCHEMA = {
  type: 'object',
  properties: {
    money_path_holds: { type: 'boolean', description: 'after a hard skeptical look, does the dollar actually arrive as described?' },
    refutation: { type: 'string', description: 'the single strongest case that the money path fails: payer not real/budgeted, ask unreachable, they would do it in-house or for free, edge not differentiated, too slow' },
    fixes: { type: 'string', description: 'how to fix it - a cheaper pilot, a better-fit buyer (e.g. a fund that trades it vs an operator), a tighter ask - or, if unfixable, why it dies' },
    hardened_ask: { type: 'string', description: 'the tightened, more landable ask after the test (often a cheap paid pilot before the retainer)' },
    realistic_ticket: { type: 'string', description: 'the honest revised ticket / position size after the test' },
    revised_verdict: { type: 'string', enum: ['PURSUE', 'PASS'], description: 'PURSUE only if the money path survives the refutation or is cleanly fixable' },
    revised_confidence: { type: 'string', enum: ['low', 'medium', 'high'] },
  },
  required: ['money_path_holds', 'refutation', 'revised_verdict', 'revised_confidence'],
}
const REFUTE_PROMPT = (plan) => `You are the adversarial money-path auditor for the Pope CAPTURE layer. A capture plan has been drafted. Your ONLY job is to try hard to break the MONEY PATH (not the forecast). Default to skeptical.

THE PLAN:
${JSON.stringify(plan)}

Attack it on every axis where the dollar fails to arrive:
- Is the payer a REAL, budgeted buyer for this, or a fantasy? Do they have discretionary spend for outside intel/advisory at this ticket?
- Would they actually pay, or run this in-house, get it free, or ignore a small unknown shop?
- Is the ask reachable as written, or does it assume access we do not have?
- Is there a CLEANER path: a better-fit buyer (a fund that trades the complex vs an operator), a cheaper paid pilot first, a position we take ourselves?
- Is our edge genuinely differentiated to THIS buyer, or generic?
Run ONE focused web search only if a load-bearing fact (budget, who-buys-intel, a named buyer) needs checking. Then either HARDEN the plan (tighter ask, better buyer, cheap pilot, honest ticket) and keep PURSUE, or set revised_verdict PASS with the reason. An honest PASS beats a fantasy deal. ${STYLE}`

const hardened = await pipeline(
  calls,
  (c) => agent(CAPTURE_PROMPT(c), { label: `capture:${(c.headline || 'call').slice(0, 22)}`, phase: 'Capture', schema: CAPTURE_SCHEMA, agentType: 'general-purpose' }),
  (plan, c) => {
    if (!plan) return null
    return agent(REFUTE_PROMPT(plan), { label: `refute:${(plan.headline || c.headline || 'call').slice(0, 22)}`, phase: 'Refute', schema: REFUTE_SCHEMA, agentType: 'general-purpose' })
      .then((ref) => ({ ...plan, refute: ref || null, verdict: (ref && ref.revised_verdict) || plan.verdict }))
  },
)

const plans = hardened.filter(Boolean)
const pursue = plans.filter((p) => p.verdict === 'PURSUE')
log(`${pursue.length}/${plans.length} calls survive the money-path refutation with a real capture path`)

// ---- Prioritize: the do-this-week shortlist --------------------------------
phase('Prioritize')
const PRIORITIZE_SCHEMA = {
  type: 'object',
  properties: {
    synthesis: { type: 'string', description: 'one paragraph: the single most valuable, most reachable capture opportunity on this board and why' },
    shortlist: { type: 'array', description: 'the ranked do-this-week shortlist', items: { type: 'object', properties: {
      rank: { type: 'number' }, headline: { type: 'string' }, target_org: { type: 'string' },
      first_move: { type: 'string' }, value_mechanism: { type: 'string' },
      expected_value: { type: 'string', description: 'rough size of the prize and the odds of landing it' },
      effort: { type: 'string', enum: ['low', 'medium', 'high'] },
    }, required: ['rank', 'headline', 'target_org', 'first_move', 'expected_value', 'effort'] } },
    this_week: { type: 'array', items: { type: 'string' }, description: '3-5 concrete actions to take in the next 7 days, in order' },
  },
  required: ['synthesis', 'shortlist', 'this_week'],
}
const board = await agent(`You are the value-capture prioritizer for the Pope System. Here are the capture plans for the surviving calls:
${JSON.stringify(pursue.length ? pursue : plans)}
Rank them by expected value against effort and reachability for a small, sharp, independent forecasting shop with a leak-free scored record but no big team. Favor the ones where (a) the payer is obvious and reachable, (b) our edge is genuinely differentiated, and (c) the first move is cheap. Write a one-paragraph synthesis naming the single best opportunity, the ranked shortlist, and the 3-5 concrete actions to take in the next 7 days, in order. ${STYLE}`,
  { label: 'prioritize', phase: 'Prioritize', schema: PRIORITIZE_SCHEMA })

return { ...board, plans, n_pursue: pursue.length, n_total: plans.length }
