---
name: vati-distribute
description: >
  Turn a deployed Pope/Vati forecast into multi-format, multi-medium content that reads like an
  institutional research note, never AI slop. Pipeline: pull verified facts from postpack, draft in
  the research register (scientific-writing principles + VOICE.md), scrub with the humanizer skill and
  score it, then recompress into LinkedIn, X long-form, X thread, and Substack/blog. Use when the user
  wants posts, a content slate, or distribution from research/pope/*.json or the deployed forecasts in
  site/public/forecasts.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - WebSearch
  - WebFetch
---

# /vati-distribute — research-note content pipeline

The register is institutional research (sell-side desk note / arXiv), not social copy. The brand voice
lock lives in `humanizer-context.md` at the repo root; the humanizer auto-loads it. Read it once per
session. The hard ban: the antithesis punch ("X, not Y"), templated openers/closers, AI vocabulary,
em dashes. Target AI-tell score <= 15 before anything ships.

State of the record: nothing has resolved (earliest 2027). Sell the dated, killable call, never a win.

## Deployed forecasts (site/public/forecasts) -> source board

| PDF on site | Source board (research/pope) |
|---|---|
| after-ai | after-ai-2026-06-17.json |
| post-ai-world | post-ai-world-2026-06-17.json |
| ai-campus-power-claims | after-ai-2026-06-17 P1 deep-dive (.ultra) |
| catalyst | any-short-2026-06-15.json |
| structural | any-long-2026-06-15.json |
| inelastic-needles | inelastic-needles-2026-06-15.json |
| chips | chips-2026-06-14.json |
| biotech | biotech-2026-06-14.json |
| space | space-2026-06-14.json |
| long-horizon | long-horizon-2026-06-14.json |

## Pipeline (run in order, per call)

### 1. Facts — never from memory
```bash
python3 .claude/skills/vati-post/postpack.py list
python3 .claude/skills/vati-post/postpack.py rank all --opps
python3 .claude/skills/vati-post/postpack.py card <file> <Pid>
```
Every number, date, and named entity in the output must trace to the card. Missing angle -> reframe or
write it as an open question. Do not fill from memory.

### 2. Re-verify time-sensitive facts
For NEAR calls, re-check spot prices, export bans, closures with WebSearch, or label "as of <author
date>". A near-term call on a stale fact is the worst thing we can ship.

### 3. Draft in the research register
Apply the scientific-writing principle: full paragraphs, flowing prose, no bullet points in the body.
Backbone per note: a fact-led or thesis-led opening (vary it, never the "for the last few years"
template), the evidence, the mechanism in cause and effect, where value moves (winners/losers, no
advice), the dated forecast with both probabilities, the kill condition, the signal to watch. Decode
jargon the first time it appears.

### 4. Humanize and score (mandatory)
Run the draft through the humanizer skill at `~/.claude/skills/humanizer-skill`:
```
humanizer "<draft>" --mode rewrite --voice professional --purpose essay --score --iterate 2
```
It auto-loads `humanizer-context.md`. Revise until the AI-tell score is <= 15. The most common fails on
this brand: the "X, not Y" antithesis, repeated templated openers/closers, uniform sentence length.
Fix those first.

### 5. Distribute — recompress, never copy-paste across formats
From one humanized note, produce each medium in its own shape:
- LinkedIn: 4-6 short paragraphs, institutional, 0-2 plain hashtags, no emojis.
- X long-form: one ~250-word analytical note.
- X thread: 6-8 posts, each a real sentence-group, not fragments.
- Substack / blog: 600-1000 words, sectioned, opens with why it matters now, ends on watch + kill.

### 6. Integrity check per piece
Source call + authored date, resolves date, kill line present, both probabilities, no investment
advice, no track-record overclaim, time-sensitive facts flagged for live re-check.

### 7. Save
Write to `content/<board>-<date>.md`, one file per board, all formats inside. This is where content
stays. Do not scatter it.
