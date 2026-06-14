# The Pope System

On-demand engine for predicting where scarcity and value migrate next. Generate
wide and disruptive across any area, harden each call through an adversarial gate,
render a professional PDF. Built to be run many times.

## The loop

```
  /pope <area>
      │
      ▼
  [1] GENERATE      10 orthogonal channel miners (Opus, parallel)
      │             physical limits · demographics · materials · constraint-migration ·
      │             methods-diffusion · policy · pricing-arbitrage · patents · 2nd-order · wildcard
      ▼
  [2] GATE+REFUTE   one adversary per candidate: price-channel check, supply-elasticity
      │             test, try to prove it's already priced, score TWO probabilities
      ▼
  [3] SYNTHESIZE    pick top-K, cross-cutting read, emit a renderable spec (JSON)
      │
      ▼
  render.py  ──►  <slug>.html  +  <slug>.pdf   (deterministic, headless Chrome)
```

`.claude/workflows/pope.js` is steps 1-3 (the multi-agent engine).
`engine/pope/render.py` is the deterministic spec -> PDF step.
`.claude/commands/pope.md` is the on-demand `/pope` entry point that ties them together.

## Run it

On demand (preferred):
```
/pope water
/pope "any"            # wide open, all industries
/pope biotech 12       # ask for 12 survivors
```

Render a spec you already have (skips the LLM step):
```
python3 -m engine.pope.render research/pope/water-2026-06-14.json research/pope/water-2026-06-14
```

Recurring / scheduled: wrap `/pope any` in the `/schedule` skill (cron cloud agent)
or `/loop` to mint a fresh board on a cadence. Each run is self-contained.

## The two-probability rule (the honesty spine)

Every call carries two numbers, never one:

- **Vision P** — how strong the structural case is. Can be high (70-90%).
- **Clause P** — calibrated odds the *exact dated, mechanically checkable clause*
  resolves true. Lower, because it pays the timing tax and the measurement tax.
  This is the number scored with Brier at resolution. `clause_p <= vision_p` always.

The gap is honest uncertainty on a tight clause, not timidity. Inflating clause_p
to look bold loses points at resolution and corrodes the calibrated record, which
is the only real asset. A 50% that resolves 50% of the time beats an 80% that doesn't.

## Spec JSON contract (what render.py consumes)

```jsonc
{
  "title": "...", "subtitle": "...",
  "domain": "water", "date": "2026-06-14", "horizon": "2030 to 2040",
  "synthesis": "one cross-cutting paragraph",
  "theses": [{
    "id": "P1",
    "headline": "...",          // names the needle, not the theme
    "boom": "...",              // what booms / who captures the rent
    "domain": "...",
    "vision_p": 80, "clause_p": 45, "resolves": "2033-12-31",
    "structural": "...",        // the physical/demographic mechanism that forces it
    "pre_consensus": "...",     // why still unpriced
    "price_channel": "...",     // honest live-anchor check (optional)
    "needle": "...",            // the inelastic input that captures rent
    "metric": "...",            // dated leading metric to track
    "kill": "...",              // what falsifies it
    "refute": "...",            // why it survived the adversary (optional)
    "why": "..."                // why this call over the obvious alternative
  }],
  "runner_ups": [{"seed": "...", "case": "...", "why_not": "..."}]
}
```

Prose fields render with a tiny markdown subset: `**bold**` and `*italic*`.
Output styling matches the research-note house style (`research/long-horizon-theses.pdf`).

## Doctrine rails (inherited)

- Leak-free: long-horizon forward calls, no retro-fitting to known outcomes.
- Generate wide, graduate strict: generation is bold; only the gate promotes.
- Forecasts are immutable: resolution date + kill-criterion fixed at creation;
  supersede, never edit; Brier at resolution.
- Physical-primary, name the needle, check the price channel with a live anchor.
