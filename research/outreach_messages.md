# Outreach messages — one per person (research round 1, 2026-06-17)

*Written by Sonnet, one bespoke message per target (not a template). Email or DM format per the
person's channel (see contacts.md). Humanizer ruleset: no em dashes, no AI tells. `{{record_link}}`
is a placeholder for your public scored record. DO NOT SEND until the ablation + ForecastBench
upload are live (Jun 19-21) so the record link carries real weight. Final humanizer pass before
shipping. Replace "Toni Zemani" sign-off with your standard signature/footer.*

---

# Phase 1 — peer cluster

## Eli Lifland — X DM

```
Your AI 2027 report is one of the few forecasting artifacts that actually commits to a mechanism, not
just a number. I'm building Vaticinus, a solo AI forecasting system making pre-consensus structural
calls, all dated and Brier-scored as a public record. I'm running a 3-arm ablation right now (raw
model / council / full system) to prove the edge is real. If you'd be open to a 20-min call to poke
holes in the methodology, I'd genuinely value your read. {{record_link}}

Toni Zemani
```

## Ezra Karger — email

**Subject:** ForecastBench bot + a leakage question from a current competitor

```
Your leakage section in ForecastBench is the sharpest treatment of that problem I've seen in any
benchmark paper. I built a bot, Vaticinus, that competes on the dataset half and is currently
tracking near the top among bots. The whole system is built around one discipline: a call is never
scored on an outcome the model could already know parametrically. I'm running a 3-arm ablation now
to close the "prompt wrapper" objection.

I'd appreciate 20 minutes to talk ForecastBench design and whether what I'm doing is valid from
your vantage point.

Toni Zemani / Vaticinus / {{record_link}}
```

## Danny Halawi — email

**Subject:** Your cutoff-leakage work and a forecasting system built around it

```
The knowledge-cutoff section in "Approaching Human-Level Forecasting with LLMs" identified the
exact failure mode I spent months trying to close. Vaticinus treats a call as void if the model's
training cutoff could have baked in the outcome. Every forecast is dated, every resolution is
Brier-scored against that date, public record.

I'm now running a 3-arm ablation (raw model / council layer / full system) to measure whether the
engineering actually adds signal. You'd be a rare person who could tell me if the design is sound
or if I'm still fooling myself.

Would you take a look? Toni Zemani / Vaticinus / {{record_link}}
```

## Nuño Sempere — email

**Subject:** Vaticinus forecasting system, honest ask for your read

```
Your Forecasting Newsletter writeups on what separates real forecasting systems from posturing ones
are the clearest public writing on that question. I built Vaticinus solo: a leak-free, Brier-scored
structural forecasting system that makes pre-consensus calls on where value migrates across
industries. The whole record is public and dated, and I'm mid-ablation right now trying to prove the
council layer adds something a raw model doesn't.

I'd find your read on the architecture genuinely useful, not just a thumbs-up. Would you be open to
a short call?

Toni Zemani / Vaticinus / {{record_link}}
```

## Peter Wildeford — email

**Subject:** Vaticinus bot scoring on Metaculus, honest ask for advisor input

```
Your Power Law piece on what prediction markets actually measure is the frame I keep coming back
to when I'm deciding whether a call has real information content. I've built Vaticinus, a solo AI
forecasting system with a public, Brier-scored structural record now active on Metaculus. Given
your board position there and your forecasting track record, your read on the methodology would
carry real weight.

I'm not asking for a promotional push. I want to know where the system fails. Would you be open to
a short call?

Toni Zemani / Vaticinus / {{record_link}}
```

## Tom Liptay — X DM

```
You ran AIB as cleanly as any bot evaluation I've seen, strict separation between method and
self-report. I built Vaticinus, a solo AI forecasting system now scoring on Metaculus. I'd be
genuinely curious whether the design passes your bar from the AIB perspective, and whether there's
a way to get it into a future scoring run at FutureSearch. Builder-to-evaluator, honest
conversation. {{record_link}}

Toni Zemani
```

## Molly Hickman — X DM

```
You're probably one of three people who can critique a forecasting bot both on method and on whether
the Metaculus scoring setup is actually fair. I built Vaticinus solo. It makes pre-consensus
structural calls, every one dated and Brier-scored, and it's running on Metaculus now. The ablation
to separate real signal from prompt noise is live. I'd value your honest read on whether the
methodology holds up before I make any public claims about it. {{record_link}}

Toni Zemani
```

## wasabipesto — email

**Subject:** Would Vaticinus fit in Calibration City's scoring?

```
Calibration City is the only public tool I've found that scores across Polymarket, Kalshi, Manifold,
and Metaculus with consistent methodology. I built Vaticinus, a solo AI forecasting system with a
public Brier-scored structural record, currently active on Metaculus. Getting it into your
cross-platform scoring would be the most honest external validation I could ask for.

I don't know if your data pipeline handles bot accounts or structural forecast types. Would you be
open to a quick conversation about whether it's feasible?

Toni Zemani / Vaticinus / {{record_link}}
```

## Phil Godzin — X DM
*(confirm real identity before any equity-level ask)*

```
pgodzinai's AIB results are the benchmark I've actually been watching. I built Vaticinus, different
approach: structural macro calls rather than broad-question coverage, fully Brier-scored public
record, leak discipline baked in at the design level. Running a 3-arm ablation now to prove the
council layer isn't just wrapping a raw model. Builder-to-builder, I'd be curious what you think
the real leverage points are. {{record_link}}

Toni Zemani
```

---

# Amplifiers (relationship / feature, not an equity ask)

## Robert de Neufville — Substack message / Bluesky

```
Your Telling the Future episode with the Good Judgment Open team made me think you'd find
this interesting. I've built a solo AI forecasting system called Vaticinus. The angle that
seems genuinely different: every call is dated on the day it's made, Brier-scored at
resolution, and the record is fully public. No cherry-picking, no retroactive framing.

I'm also running a 3-arm ablation right now to check whether the engineering actually adds
anything over a raw frontier model. Happy to share results when they land, or to talk
through the setup if it's useful for an episode.

Toni Zemani / Vaticinus / {{record_link}}
```

## Dustin Gouker — X DM

```
Your Event Horizon coverage of the Kalshi/Polymarket data was exactly the kind of
thing I want to give you a first look at: a leak-free Brier-scored AI forecasting record,
and a live ablation comparing raw Opus vs. a full system to test whether the engineering
is real or just prompt-wrapping. ~37 dated public calls, ForecastBench submission in.
Worth a paragraph if the result is interesting. Toni Zemani / Vaticinus / {{record_link}}
```

## Zvi Mowshowitz — X DM

```
You've flagged in your AI roundups that most AI forecasting claims are hard to verify.
I've tried to build the thing you'd want to see: every call dated, falsifiable, Brier-scored
at resolution, public record. No post-hoc dating. There's also a 3-arm ablation running
(raw model vs. council vs. full system) to answer whether it's real signal or just a better
prompt. If the result is worth a line in your next roundup, I'll send it when it lands.
Toni Zemani / Vaticinus / {{record_link}}
```

## Saul Munn — X DM

```
Manifest is the one place I'd actually want to show this work. I've built a solo AI forecasting
system with a fully public scored record, currently running a Brier ablation to test whether
the engineering contributes beyond the base model. If there's a demo slot, lightning talk, or
even a hallway conversation that makes sense for a builder at this stage, I'd love to be in
the room. Happy to send the record and the ablation setup if that's useful context.
Toni Zemani / Vaticinus / {{record_link}}
```

## Austin Chen — email

**Subject:** Manifund fit check + a forecasting system with a public scored record

```
Austin,

Manifold's public resolution data is part of what made building Vaticinus honest. Every
call I make is dated, falsifiable, and Brier-scored at resolution against a public record.
I'm also submitting to ForecastBench this round and running a calibration ablation to
check whether the system adds real signal over a raw frontier model.

Two questions: does a Manifund grant fit this kind of infrastructure work, and would you
be willing to take a look at the record and tell me where the argument breaks? Either way,
genuinely useful to get your read.

Toni Zemani / Vaticinus / {{record_link}}
```

## Panshul42 — short (Metaculus / GitHub)
*(pseudonymous; keep it peer-level)*

```
Congrats on the Q2 AI Benchmark win. I've been building in a similar direction, a system
called Vaticinus that uses a crowd-anchored quant leg plus a council research layer for
the residual questions the dataset can't price. Running a Brier ablation now to see where
the engineering actually earns its keep. Would be curious how you handled the numeric
question type in your open-sourced bot. Toni Zemani / {{record_link}}
```

---

# Phase 2 — buyer side + capital

## Warren Hatch — LinkedIn DM

```
Warren, Good Judgment is the proof that calibrated forecasting sells to serious institutions, which
is exactly the market I built Vaticinus for. It is a solo AI forecasting system with a dated,
leak-free, Brier-scored public record, around 37 calls, tracking near the top among bots on
ForecastBench. I am lining up a small advisory bench and would value someone who has taken this
from research into the enterprise. Open to a short call? {{record_link}}

Toni Zemani / Vaticinus
```

## Agustin Lebron — X DM

```
Agustin, your law on edge in The Laws of Trading, that every profitable trade rests on a fact about
the world the marginal participant can't understand or can't act on, is almost word-for-word the
thesis I built Vaticinus on. Every call ships with a dated constraint metric, a kill-criterion, and
a pre-consensus check so the "who's on the other side" question is answered up front.

37+ Brier-scored calls, all public, no retro-fits. Tracking near the top among bots on ForecastBench.
High-ticket plan is bespoke constraint-forecasting for trading desks. Would value your read on
whether that framing lands. {{record_link}}

Toni Zemani / Vaticinus
```

## Corey Hoffstein — X DM

```
Corey, your "Rebalancing Timing Luck" paper, where calendar-year return spreads above 40% came
purely from rebalance schedule, has stuck with me as the cleanest case for why attribution needs a
record you can't fudge after the fact. That's the whole design of Vaticinus: dated, immutable,
leak-free structural forecasts, each Brier-scored at resolution. 37+ on the public record.

Tracking near the top among bots on ForecastBench's dataset half, with a 3-arm ablation running now
to separate engineering from the base model. Would love a quick chat if it lands. {{record_link}}

Toni Zemani / Vaticinus
```

## Misha Yagudin — email
**Subject:** Vaticinus, and where Arb's work overlaps

```
Misha, Arb Research sits right where I have been working, elite human forecasting meeting machine
evals. I built Vaticinus solo: dated, leak-free, Brier-scored structural calls, around 37 on the
public record, tracking near the top among bots on the ForecastBench dataset half. A 3-arm ablation
is running to show the council layer adds real signal over a raw model.

I would value your read on the method, and a conversation about where the bespoke side could go.

Toni Zemani / Vaticinus / {{record_link}}
```

## Robin Hanson — email
**Subject:** A pre-consensus gate, built from idea futures

```
Robin, your idea-futures argument, that the test of a forecast is whether it moves a price the
consensus has not yet absorbed, is built into Vaticinus as a hard gate: a call only counts if it is
both correct and not already priced in. It is a solo AI forecasting system with a dated, leak-free,
Brier-scored public record.

I am not pitching anything commercial. I would value your read on whether the pre-consensus gate is
sound, and I would be glad to have your name near the work if it holds up.

Toni Zemani / Vaticinus / {{record_link}}
```

## Nate Silver — email
**Subject:** You advise Polymarket; here is a record built to be scored

```
Nate, you took the Polymarket advisor seat because the pricing was getting uncannily good, and that
same standard is the one I hold Vaticinus to: every call dated, leak-free, Brier-scored at
resolution, nothing graded on what the model already knew. Around 37 on the public record, tracking
near the top among bots on ForecastBench.

I am a solo founder building a small advisory bench. Would you take a look and tell me if the record
clears your bar?

Toni Zemani / Vaticinus / {{record_link}}
```

## Joey Krug — email
**Subject:** From Augur to a forecasting system with the receipts

```
Joey, you built Augur because someone had to make a market that actually prices the future. I am
coming at the same goal from the model side. Vaticinus is a solo AI forecasting system with a dated,
leak-free, Brier-scored public record, around 37 calls, near the top among bots on ForecastBench.

I am building a small advisory bench and starting to think about a raise. Given Augur and your seat
at Founders Fund, your read on both the method and the path would be worth a lot. Open to 20 minutes?

Toni Zemani / Vaticinus / {{record_link}}
```

## Adhi Rajaprabhakaran — X DM

```
Adhi, a fund built specifically for the second-order effects of prediction markets is exactly the
thesis I have been building toward. Vaticinus is a solo AI forecasting system with a dated,
leak-free, Brier-scored public record, near the top among bots on ForecastBench. I am lining up
advisors who know this space and starting to think about capital. Would value your read on the work,
and whether 5c(c) ever looks at something like this. {{record_link}}

Toni Zemani / Vaticinus
```

---

# Phase 3 — academics + warm-intro validators
*(prefer a warm intro from a signed advisor; cold only if no path exists)*

## Barbara Mellers — email
**Subject:** A leak-free scored record, and a calibration question for you

```
Professor Mellers,

The Good Judgment Project's finding that taught me the most is the one founders skip: probability training and tracking moved calibration, not just access to information. Most "AI forecaster" pitches ignore that and report accuracy with no calibration curve.

I built Vaticinus solo. It makes dated, pre-consensus structural forecasts about where value moves across industries, around 37 so far, each scored only on outcomes the model could not already know, Brier-scored at resolution. A 3-arm ablation is running now to separate real skill from prompt-wrapping.

I would value your read on whether the method holds up as calibration, not theater. Open to an advisory relationship if it does.

Toni Zemani / Vaticinus / {{record_link}}
```

## Don Moore — email
**Subject:** "they don't know what to do about it" — a system that tries to

```
Professor Moore,

Your 2025 Management Science paper put a name to the thing I keep running into: people know they don't know, but they don't know what to do about it. The gap between feeling uncertain and expressing that uncertainty as a calibrated distribution is exactly where most forecasting tools fail quietly.

I spent the last months building Vaticinus, a forecasting system I made alone. It produces dated, leak-free structural calls, scored only on outcomes it could not have known in advance, then Brier-scored when they resolve. Roughly 37 on the public record. I am running a 3-arm ablation to check whether the system adds skill or just wrapping.

Would you look at the method and tell me where it fools itself? An advisory tie would mean a lot.

Toni Zemani / Vaticinus / {{record_link}}
```

## Lyle Ungar — email
**Subject:** When does adding the next model add noise instead of signal?

```
Professor Ungar,

"Wisdom of the silicon crowd" is the paper I argue with most. The ensemble landing indistinguishable from 925 humans was striking, but the part that stuck was the 17 to 28 percent jump once the models saw the median human prediction. It raised a question I cannot answer cleanly yet: at what point does adding another model stop adding signal and start adding correlated noise?

I built Vaticinus solo, a forecasting system making dated, leak-free structural calls, scored only on outcomes it could not already know, Brier-scored at resolution. About 37 on record. I am running a 3-arm ablation right now, partly to test exactly that diminishing-returns question.

I would value your read on the method, and your help thinking about the ensemble limit.

Toni Zemani / Vaticinus / {{record_link}}
```

## Jacob Steinhardt — email
**Subject:** Ablating what actually drives forecast skill

```
Professor Steinhardt,

"Approaching Human-Level Forecasting with LLMs" showed the gap closes with structured retrieval, but the question it left me with is the one you tend to ask anyway: which part of the pipeline is doing the work? Retrieval, aggregation, or the base model. The same instinct that made MMLU a real eval and not a vanity number.

I built Vaticinus alone. It makes dated, leak-free structural forecasts about where value migrates, scored only on outcomes the model could not have seen, Brier-scored when they resolve. Around 37 public calls. I am running a 3-arm ablation now, raw model versus council versus full system, to separate skill from prompt-wrapping.

I would value your technical read on whether the ablation is honest. Open to advising if it interests you.

Toni Zemani / Vaticinus / {{record_link}}
```

## Pavel Atanasov — email
**Subject:** Skill over aggregation method — testing it on a live system

```
Professor Atanasov,

Your crowd-prediction work made one point I keep coming back to: once you match forecaster skill, the market and the team poll basically tie, and small elite crowds beat larger ones. The aggregation method matters far less than people selling aggregation want to admit.

I built Vaticinus solo, a forecasting system that makes dated, pre-consensus structural calls, scored only on outcomes it could not already know, then Brier-scored at resolution. About 37 on the public record, tracking near the top among bots on the ForecastBench dataset half. A 3-arm ablation is running to see whether the structure adds skill or just dressing.

I would value your read on whether this is real skill or clever aggregation. An advisory relationship would be welcome.

Toni Zemani / Vaticinus / {{record_link}}
```

## Joshua D. Clinton — email
**Subject:** Brier across 2,500 markets, and one built to be scored that way

```
Professor Clinton,

Your study scoring Polymarket, Kalshi, and PredictIt across 2,500-plus markets did something rare: it judged markets by Brier and log loss instead of vibes, and the result that PredictIt led on election eve despite the smallest volume cuts against the bigger-is-better story everyone repeats.

I built Vaticinus solo. It makes dated, leak-free structural forecasts about where value moves across industries, scored only on outcomes the model could not already know, then Brier-scored at resolution. Around 37 on the public record. I am running a 3-arm ablation to check whether the system adds skill or just prompt-wrapping.

Since you score forecasters the way I want mine judged, I would value your read on the method. Open to advising.

Toni Zemani / Vaticinus / {{record_link}}
```

## Anthony Aguirre — email
**Subject:** A dated, leak-free record, built in the Metaculus discipline

```
Anthony,

Metaculus is the reason I hold one rule above all others: a forecast is only worth anything if it is dated, immutable, and scored on outcomes the forecaster could not already know. You built the infrastructure that made that discipline normal. Most AI forecasting demos still quietly break it.

I built Vaticinus solo, a system that makes pre-consensus structural calls about where value migrates across industries. Around 37 on the public record, each dated and leak-free, Brier-scored at resolution, tracking near the top among bots on the ForecastBench dataset half. A 3-arm ablation is running to separate skill from prompt-wrapping.

I would value your read on whether the record meets the bar you set. If it does, I would welcome you as an advisor.

Toni Zemani / Vaticinus / {{record_link}}
```

## Josh Rosenberg — email
**Subject:** Ablation data on the AI-vs-superforecaster gap

```
Josh,

FRI is one of the few groups actually measuring when AI forecasters catch superforecasters instead of just asserting it. That question is the spine of what I have been building, so your work reads less like background and more like the scoreboard.

I built Vaticinus alone. It makes dated, leak-free structural forecasts, scored only on outcomes the model could not already know, then Brier-scored at resolution. Around 37 on the public record, tracking near the top among bots on the ForecastBench dataset half. Right now I am running a 3-arm ablation, raw model versus council versus full system, which is exactly the kind of data the AI-vs-human-gap question needs.

I would value FRI's read on the method, and a path to sharing the ablation results when they land.

Toni Zemani / Vaticinus / {{record_link}}
```

## Richard Craib — X DM

```
Richard, Numerai's whole bet is that you find signal by scoring models on held-out reality, not on how clever they sound. That is the same discipline I built Vaticinus on, solo.

It makes dated, leak-free structural forecasts, scored only on outcomes the model could not already know, Brier-scored at resolution. About 37 on the public record, near the top among bots on ForecastBench. A 3-arm ablation is running to separate real skill from prompt-wrapping.

Would value your read on the method, and on the go-to-market.

Toni Zemani / Vaticinus / {{record_link}}
```

## Andreas Stuhlmüller — email
**Subject:** Factored cognition under a forecasting pipeline

```
Andreas,

Elicit's bet, that you get reliable answers to hard questions by decomposing them into sub-questions a model can actually handle, is the same structure I lean on under the hood of a forecasting pipeline. A structural call about where value moves is just a stack of smaller, checkable sub-forecasts.

I built Vaticinus solo. It makes dated, leak-free forecasts, scored only on outcomes the model could not already know, Brier-scored at resolution. Around 37 on the public record. A 3-arm ablation is running now to see whether the decomposition adds skill or just steps.

I would value your technical read on whether the factoring is doing real work here. Open to an advisory relationship if it is useful.

Toni Zemani / Vaticinus / {{record_link}}
```
