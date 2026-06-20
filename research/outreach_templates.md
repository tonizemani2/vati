# Outreach templates — Ring 1 advisors

*2026-06-17. Built for Instantly (uses {{variables}} + a step-2 follow-up). Written to the humanizer
ruleset: no em dashes, no AI tells, no rule-of-three, plain and direct. Three segment variants
because a cold-email tool runs by list. Fill the {{personal_line}} per person by hand. Lead with
the record, never a pitch.*

**Before sending:** the record link + the ablation result + the ForecastBench number are the whole
credibility play. Do not send the sequence until those artifacts are live (Jun 19-21). A cold email
from a solo founder with a dated scored record attached closes far above one without.

---

## Segment A — benchmark / AI-forecasting peers
*(Karger, Halawi, Liptay, Hickman, Sempere, Godzin, Panshul42, Fred Zhang, Wildeford)*

**Subject:** a leak-free bot record + an ablation I want you to break

```
{{first_name}}, {{personal_line}}

I built Vaticinus, an LLM forecasting system with a dated, leak-free, Brier-scored
record. It's tracking near the top among bots on the ForecastBench dataset half.
Right now I'm running a 3-arm ablation, raw model vs a council layer vs the full
system, to check the lift is real and not just prompt-wrapping.

I'm a solo founder putting together a small advisory bench of people who'd actually
catch what I can't. You're high on that list. Could I get 20 minutes to have you pull
the method apart? It isn't a pitch. I want it stress-tested by someone who would spot
the hole.

Here's the record so you can judge before you reply: {{record_link}}

{{your_name}}
```

*Example {{personal_line}}: for Karger, "Your ForecastBench paper is the reason I'm this careful about leakage in my eval." For Halawi, "Your work on knowledge-cutoff leakage is exactly the failure mode I built the eval around."*

---

## Segment B — senior academics / forecasting science
*(Mellers, Moore, Ungar, Steinhardt, Hanson, Atanasov; Tetlock via Rosenberg)*

**Subject:** a calibration question from a solo builder

```
Professor {{last_name}}, {{personal_line}}

I've built a forecasting system I'm trying to hold to a real standard: every call
dated, leak-free, and scored at resolution. {{your_work}} is part of why I take
calibration seriously instead of chasing raw accuracy.

I'd value 20 minutes to hear where you think the method is weakest, and whether the
way I separate genuine skill from a model that already knows the answer holds up. I'd
send the scored record ahead so the call is spent on substance.

Would a short call be possible in the next few weeks?

{{your_name}}
```

---

## Segment C — quant / markets + amplifiers
*(Silver, Lebron, Hoffstein, de Neufville, Gouker, Hatch, Krug, Rajaprabhakaran)*

**Subject:** forecasting with the receipts

```
{{first_name}}, {{personal_line}}

I run Vaticinus, a forecasting system with a public, dated, Brier-scored record, built
to call where value moves before it gets priced in. It's competing near the top among
bots on ForecastBench.

I'm a solo founder lining up a few advisors who know the buyer side and the market side
cold. Given {{their_thing}}, you're someone I'd want in the room. Open to 20 minutes?
I'll send the record first so you can decide if it's worth your time.

{{your_name}}
```

---

## Step 2 follow-up (all segments, +3 days, same thread)

**Subject:** (leave blank so it threads under the original)

```
{{first_name}}, quick nudge in case this slipped. The one thing I'd most value your
read on: {{specific_question}}. Even a two-line reaction helps. Record is here if
it's useful: {{record_link}}. Either way, the work you've put out shaped how I built
this, so thank you for that.

{{your_name}}
```

---

## Variables to fill per person
- `{{first_name}}` / `{{last_name}}`
- `{{personal_line}}` — the one specific, true reason you are writing THEM. This is the whole email.
- `{{your_work}}` (Segment B) — the paper/result of theirs you are reacting to.
- `{{their_thing}}` (Segment C) — their fund / podcast / newsletter / track record.
- `{{specific_question}}` — the single sharpest doubt you want them to resolve.
- `{{record_link}}` — the public scored record.
- `{{your_name}}` — Toni Zemani, founder, Vaticinus, + the bare URL.

## Sending notes
- Keep it to one list-segment per Instantly campaign so the {{personal_line}} stays honest.
- For the academics and the marquee names (Tetlock, Mellers, Aguirre), prefer a warm intro over
  cold send. Route Tetlock through Karger or Josh Rosenberg.
- Do not run the warm, high-value people (a future angel, a Metaculus board member) through a bulk
  sequence. Those get a hand-written 1-to-1.
