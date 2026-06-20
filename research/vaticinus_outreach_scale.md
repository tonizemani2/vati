# Vaticinus scaled cold-outreach spec (Ring-2 engine)

Status: build spec for the 42-inbox warming stack. Sending HELD until warmup matures (~2-3 wks).
This is the SCALED motion (Ring 2 paying clients via Exa + Instantly), distinct from the hand-picked
Ring-1 founder→peer advisory emails in `outreach_messages.md`. Same voice, different CTA.

## ICP (who Exa hunts)

Primary = **Ring 2 paying clients**: people who buy an information edge.
- Titles: Head of Research, Director of Research, CIO, PM / Portfolio Manager, Quant Researcher,
  Chief Strategy Officer, Head of Macro, Head of Forecasting/Foresight, Risk/Scenario lead.
- Firm types: quant funds, prop/trading firms (DRW-type), global-macro hedge funds, multi-strat,
  family offices, corporate strategy/foresight units, reinsurance/risk desks, thesis-driven VC.
- Signal: people who already pay for differentiated research/data and reason about where value
  migrates before it is priced. Bonus signal: posts/writes about forecasting, calibration,
  prediction markets, scenario planning.
- Exclude: retail traders, pure SaaS marketers, students, generic "AI enthusiasts", recruiters,
  anyone at the mining-terminal ICP (that's a different product).

Secondary (later waves): Ring 3 angels (fintech/AI/quant-adjacent), Ring 4 amplifiers
(forecasting/markets newsletters + community gatekeepers).

## Personas (PROPOSED — rename/reassign freely; these are the 3 sending identities per domain)

The three inboxes exist for volume distribution + angle. All stay on the honest, record-led voice.
- **toni@** — Toni Zemani · founder/outreach voice. The direct "I built this, here's the scored
  record, does it clear your bar" angle. Carries Segment C (quant/markets) + high-conviction names.
- **linda@** — Linda Zemani · research/partnerships voice. Slightly warmer, "your work shaped how
  I built this" angle. Carries Segment B (research/forecasting-science leaning buyers).
- **vati@** — Vaticinus (brand/product) · used for amplifier/Ring-4 + lighter "thought it'd be
  useful to your desk" angle. Carries Segment A (peers/benchmark-adjacent) + newsletters.

Rotation: each prospect is assigned ONE persona by segment; never email the same person from two.

## Voice rules (hard constraints for the Sonnet generator)

- Lead with the scored record, never a pitch. Concrete: dated calls, Brier-scored at resolution,
  leak-free, ForecastBench dataset-half standing, 3-arm ablation. Include {{record_link}}.
- One hyper-specific hook per prospect drawn from THEIR own work/firm/post. No generic flattery.
- No hype, no AI-marketing language, no exclamation points, NO em-dashes (Toni's hard rule).
- 70-130 words, short high-signal sentences. Plain. Final humanizer pass.
- CTA (Ring 2): low-friction, value-first — "worth 15 minutes for your desk?" / book link
  (Cal.com vaticinus/30min). NOT the advisor "clear your bar" ask (that's Ring 1).
- Two steps: Day 0 + Day 3 same-thread nudge (subject blank to thread). Step 2 = 40-60 words.

## Exa Websets query set (Ring 2)

Person queries (entity=person), enrich: work email + title + company + linkedin:
- Q1 Head of Research / Director of Research at quantitative hedge funds
- Q2 Portfolio managers at global macro hedge funds
- Q3 Quant researchers / strategists at proprietary trading firms
- Q4 Chief Investment Officers at multi-strategy or macro funds
- Q5 Heads of corporate strategy / corporate foresight at large enterprises
- Q6 Research leads at family offices investing across macro themes
- Q7 Partners at thesis-driven / deep-tech VC firms who publish market theses
- Q8 Heads of scenario planning / strategic risk at reinsurers and risk desks
- Q9 People who write publicly about forecasting, calibration, or prediction markets and work in finance
- Q10 Macro strategists at asset managers who publish forward-looking research

Run each at count 25-50, dedupe against existing lead DBs, keep only rows with a usable work email.

## Pipeline (all message-gen on Sonnet; sending staged, not fired)

1. Sonnet: expand the 10 queries into precise Websets phrasings + per-query enrichments.
2. Exa Websets (Evomi proxy, free-account engine): pull + enrich → prospects.csv.
3. Sonnet (fan-out, 1 per prospect): segment-assign + persona-assign + write Day0 + Day3 copy
   with a specific hook, obeying the voice rules. Output per-lead custom vars.
4. Load into Instantly as campaign(s) mapped to toni/linda/vati inboxes, status = NOT sending.
5. Ignite low-and-slow only after warmup matures.

## Current generated assets (2026-06-17)

Built from the existing curated Round-1 list, public web harvest, OpenAlex researcher harvest, and
salvaged angel list.

- `research/targets/outreach_universe_scored.csv` / `.json` — **3,498** scored people total.
- `research/targets/top_fit_300_messages.csv` — **300** contactable P0/P1 targets with Day 0 and
  Day 3 copy. First 33 reuse the hand-written bespoke messages from `outreach_messages.md`; the
  rest are generated from profile fields and must be reviewed before sending.
- `research/targets/contactable_messages.csv` — **1,045** usable-contact rows with one-to-one copy.
- `research/targets/email_enrichment_queue.csv` — **1,026** rows that need direct-email enrichment.
- `research/targets/public_email_enrichment_top300.csv` — public-email enrichment attempts for the
  top queue: **25** strict email-ready rows, **82** possible/manual-review candidates, **212** not
  found.
- `research/targets/email_campaign_ready_strict.csv` — normalized email-campaign import file for the
  **25** strict email-ready rows. Status remains hold/final-verify, not send.
- `research/top_fit_300.md` — founder-review shortlist view.
- `research/outreach_operating_plan.md` — batching, quality gates, and first two-week sequence.
- `research/targets_panel.html` — browsable/filterable full universe.

Tiering rule: OpenAlex/ORCID-only rows are enrichment/hold rows, not personal-send rows. P0/P1 only
include contactable rows (email, X, LinkedIn, web/Substack) plus the existing curated targets.
Email rule: `found_public_possible` rows are research leads only. Only `confirmed_existing` and
`found_public_high` rows enter the strict campaign-ready export.
