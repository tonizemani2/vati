# PEOPLE_MAP.md — who to find, why, what you give them, what unlocks them

*Last updated 2026-06-17. Pair with [funding-sequence-and-gtm], [fundraising-comps-and-strategy], [founder-control-nonnegotiable].*

## The frame (read this before the lists)

Your binding constraint is not headcount. It is **third-party belief** and **distribution**. You
are a solo technical founder with a built, dated, leak-free, scored system. Cash cannot buy
credibility quickly. The right names can. So every person below is chosen to relieve the one
thing you cannot manufacture alone: outside conviction that this is real.

The loop that runs everything:

> **proof unlocks people -> people open doors to bigger proof -> bigger proof unlocks bigger people.**

Evidence is the fuel. People are the multiplier. Do not chase a person you do not yet have the
evidence to convert. Build the evidence, then the person is cheap.

Solo is a feature here, not a bug: it is the whole pitch (one operator built a system that beats
bots and anchors institutional research). Do not dilute that story by adding warm bodies. Add
**names that lend credibility, doors, capital, or audience**, on equity or relationship, not salary.

---

## The four rings (who to find)

### Ring 1 — Advisors / credential-lenders  (currency: 0.1-1% equity, no cash)

These are people whose name on the site and the deck instantly de-risks you to a client or an
investor. The instrument is a standard advisor agreement (FAST-style): 0.25-1% vesting over ~2
years, more for active, a one-line scope, no board seat, no control given up. You want 3-5 total,
not a wall of logos.

| Archetype | What their name proves | Why it matters to you |
|---|---|---|
| **Forecasting / decision-science authority** (Good Judgment Project alumni, named superforecasters, calibration researchers in the Tetlock world) | The core claim: calibrated, falsifiable forecasting is a real discipline and you do it right | Single most credible advisor type. Validates the *method*, not the tech. |
| **Quant / trading practitioner** (ex or current DRW / Jane Street / Citadel / HRT / macro desk, or a prediction-market veteran) | The buyer side. That funds pay for an edge and yours is the kind they buy | Doubles as your first warm path into paying clients. DRW already backed Mantic, so trading firms demonstrably pay for forecasting. |
| **Applied-AI / ML credibility name** (ex-DeepMind / Anthropic / OpenAI researcher, or someone known for LLM-forecasting work) | That this is real AI, not a prompt wrapper | Directly answers your own anxiety and every serious investor's first question. The ablation ([system-vs-raw-opus-ablation]) is the evidence that earns this person. |
| **Prediction-market / platform insider** (Metaculus, Manifold, Polymarket orbit) | The benchmark proof and the community standing | Cheap to reach (they live on the same forums you compete on) and they amplify. |
| *(optional)* **GTM / research-sales operator** (someone who has sold data or research to funds) | That you can get to revenue, not just build | Add only once you have a pilot to point at. |

**Find them by:** start from anchors you already touch. The bots beating or trailing you on
ForecastBench / Metaculus FutureEval have authors with names. The Good Judgment / Tetlock world is
small and public. Use the **openalex-database** skill to rank forecasting/calibration researchers
by citation and recency, then qualify by reachability (active on X, writes a blog, replies to
cold-but-sharp DMs). The prediction-market insiders are on Manifold/Metaculus/ACX comment threads.

### Ring 2 — Clients who pay  (revenue is the strongest evidence there is)

Two tiers, straight from your own GTM:

- **High-ticket bespoke ($10-50k+):** quant funds, prop trading firms (DRW-type), macro hedge
  funds, family offices, corporate strategy / foresight units, VC firms wanting thesis support,
  reinsurance and risk desks. Target **1-3 lighthouse engagements**, not a services treadmill.
- **Low-ticket product:** chat.vaticinus.com Deep/Council tiers for individual analysts, quants,
  researchers. Volume and signal, not the headline revenue.

**The person inside a client org is not the firm, it is a human with a budget and a pain:** Head
of Research, CIO, a portfolio manager, a Chief Strategy Officer, a corporate foresight lead. They
have discretionary spend and they personally feel the "where does value migrate before it is
priced" pain. Never enter through procurement. Enter through the person who loses sleep over the
question you answer.

**Find them by:** the finance intake funnel + Cal.com booking are already live
([monetization-funnel-and-owner-bypass]) so inbound has a home. For outbound, the warmest path is
through a Ring-1 quant advisor or a Ring-3 operator-angel who already sits in that world. Cold path:
a tight, evidence-first note (here is the scored record, here is a call I made N days early, here
is the gap to the market price) to a named head of research. EDGAR 13F (you have **edgartools**)
maps which funds hold what, which tells you who has a thesis you can pressure-test.

### Ring 3 — Angels / capital  (gated by proof, not pedigree, and protect control)

- **The Mantic angel set** is the warmest cohort that exists for you: the people who funded Mantic
  ($4M pre-seed, Aug 2025, Episode 1 + DRW + Anthropic/DeepMind angels) have already decided "AI
  forecasting is fundable." You are the proof-not-pedigree version of the same bet. Find the
  individual angels on that cap table and the Episode 1 partner who led it.
- **Operator-angels in quant / fintech:** ex-founders and execs who write $10-50k checks *and*
  open fund doors. The check matters less than the door.
- **Applied-AI angels:** people who back AI-native tooling early.
- **A future pre-seed lead** (institutional, later): $2-3M, post-proof only. SAFE on a high cap
  (~$7-10M post, ~5-7% dilution), no board seat. Strongly consider **YC** as a control-preserving
  credential patch. This is the [funding-sequence-and-gtm] sequence, do not pull it forward.

**Find them by:** comparable-company cap tables (Mantic, Metaculus, Manifold, Polymarket,
Augur-era founders), who-backs-whom on the AI-forecasting and prediction-market beat, and warm
intros from Ring 1. Anchor every conversation at a high cap and take less money rather than a low
cap. Do not raise for the data layer (it is under ~$20k, self-fund it).

### Ring 4 — Amplifiers / distribution  (no equity, just relationship)

X is your credential replacement, not LinkedIn. The people here turn the scored record into reach:

- Forecasting / AI / quant voices on X with an audience who will quote-tweet a clean benchmark win.
- Newsletter and blog writers on the AI-plus-markets beat.
- Community gatekeepers: Metaculus, Manifold, LessWrong / ACX, EA-adjacent forecasting circles.
  These are the same people who can be Ring-1 advisors, so the relationship compounds.

**Find them by:** they are already in your competitive arena. Win ForecastBench, post the result,
tag the people who track that leaderboard. Show HN on a benchmark win. Open-source beyond-brier
([beyond-brier-oss]) is an amplifier magnet on its own.

---

## The evidence engine (the "undeniable evidence" you asked for)

This is the fuel. Each artifact unlocks a specific ring. Build them in this order because each one
earns the next tier of person.

| Evidence artifact | State | Unlocks |
|---|---|---|
| Dated, leak-free, Brier-scored record (37+ calls) | **have it** | baseline credibility, amplifiers |
| **ForecastBench #1-among-bots** (sprint Jun 21) | imminent | AI/forecasting advisors, angels, Show HN |
| **3-arm ablation: raw Opus vs +council vs full system** ([system-vs-raw-opus-ablation], run on/after Jun 19) | next | the "not a prompt wrapper" proof; AI-research advisors + serious investors. **Highest-leverage single artifact for credibility.** |
| Metaculus FutureEval Bot Tournament standing | open till Sept 6, not yet enrolled | public, third-party, undeniable |
| **1-3 paying pilots** | the goal | the raise trigger; the strongest evidence of all |
| Published research (Beyond Brier paper + OSS repo) | partly built | academic credibility, advisor magnet |

The raise fires when **ablation + a benchmark win + at least one pilot** are all true. Until then,
capital stays non-dilutive.

---

## Funnel math (assume ~1% cold close rate)

At a 1% close rate, this is a pipeline problem, not a hand-pick-five-names problem. The volume you
need at the top to hit a target is brutal, and it is the reason "find a lot" is correct:

| Goal | Closes needed | Cold touches @ 1% |
|---|---|---|
| 4 advisors signed | 4 | ~400 |
| 1-3 paying pilots | 1-3 | ~100-300 qualified buyers |
| ~$500k from ~$25-50k angel checks | 10-20 | ~1,000-2,000 angel touches |

Two consequences, and the second is the real lever:

1. **Top-of-funnel has to be built like a machine, not curated by hand.** The finding logic below
   must scale to *hundreds* of names per ring. Hand-picking a dozen perfect people is a rounding
   error against a 1% rate. So the deliverable is a *list-building pipeline*, not a shortlist.
2. **The cheapest way to win is to raise the rate, not just the volume.** 1% is the *cold* number.
   A warm intro closes at 10-30%, and an evidence-first opener (scored record + one early call +
   the gap to market price) closes far better than a pitch. Moving 1% -> 5% cuts the volume you
   need by 5x. This is the entire reason the evidence engine exists and why you route through
   Ring-1 advisors to reach Rings 2 and 3: **every artifact and every warm path is a close-rate
   multiplier.** Build volume, but spend equally on rate.

Practical read: build a list of 200-400 advisor candidates (the four archetypes), send
evidence-first, expect ~2-4 to sign, and use those to convert the warmer, higher-rate paths into
clients and angels. Do not burn the warm Mantic-angel cohort at cold-spray quality; those get the
1-to-1 evidence treatment.

---

## The finding logic (repeatable method, not a one-off list)

1. **Seed from anchors.** Mantic's cap table, Good Judgment alumni, the named authors of the bots
   you compete against, heads of research at funds holding theses you can pressure-test.
2. **Expand one hop.** Who backed the comparable companies, who advises them, who publishes the
   relevant research (OpenAlex), who runs research at the target funds (EDGAR 13F + their site).
3. **Qualify each name on three axes:** warm-path distance (mutual or second-degree beats cold),
   leverage (door + credibility + capital, not just one), and *which evidence artifact converts
   them* (do not approach before you hold it).
4. **Prioritize:** warmest x highest-leverage first. One quant advisor who opens a fund door beats
   five passive logos.
5. **Convert with evidence, never with a pitch.** Lead with the scored record and a specific early
   call, not adjectives. Honesty is the credential ([investor-record-framing]).

---

## Do-this-week sequence (tied to your calendar)

1. **Jun 19+:** run the ablation. This is the credibility keystone; nothing else in Ring 1/3
   converts as hard without it.
2. **Jun 21:** the ForecastBench #1 sprint + upload. The public win.
3. **Then, in parallel:** post both results on X (build-in-public), Show HN on the benchmark,
   point beyond-brier at GitHub. That is Ring 4 lighting up on its own.
4. **With those two artifacts in hand:** open Ring 1. Cold-but-sharp notes to 5 candidate advisors
   (1 forecasting authority, 1 quant, 1 AI-research name, 1 market insider, hold the GTM slot).
5. **First advisor signed -> use them to reach Ring 2 (one pilot) and Ring 3 (Mantic angel set).**

This file is the logic; the names get appended as research rounds, never rewritten.

---

## Ring 1 — named target list (research round 1, 2026-06-17)

~50 real, sourced candidates from four parallel searches (forecasting authorities, quant/trading,
applied-AI, prediction-market insiders). **Confidence marker: the count in [brackets] is how many
of the four independent searches surfaced the name.** A name found by 3-4 separate searches is the
strongest fit signal you can get for free. Tiered by validation power x reachability for a solo
founder. Lead every approach with the scored record + the ablation, not a pitch.

### Tier S — sign these first (on-thesis, reachable, high signal)

- **Eli Lifland [4]** — #1 all-time RAND Forecasting Initiative; co-founder AI Futures Project (AI 2027); Samotsvety. The single best anchor: top track record + AI-native + reachable. X @eli_lifland, foxy-scout.com.
- **Ezra Karger [3]** — Chicago Fed economist; FRI research director; **lead author of ForecastBench**. The benchmark's own creator validating your standing. ezrakarger.com (email public).
- **Danny Halawi [2]** — first author of "Approaching Human-Level Forecasting with LLMs" + ForecastBench co-author; publicly stress-tests cutoff leakage (your core discipline). X @dannyhalawi15. *His name is the answer to "are you a prompt wrapper."*
- **Nuño Sempere [3]** — Forecasting Newsletter; Samotsvety co-founder; Sentinel. Independent, builds forecasting infra, very reachable. nunosempere.com.
- **Peter Wildeford [2]** — **Metaculus board member**; IAPS co-founder; The Power Law Substack. Best validation + amplification combo. Substack/X reachable.
- **Tom Liptay [1]** — Metaculus Project Director + superforecaster; runs the AI Forecasting Benchmark Series (bots vs pros). Designs the tournament you run in. EA Forum / Metaculus.
- **Molly Hickman [1]** — Metaculus technical PM + AIB co-author + ~5th all-time RAND Samotsvety forecaster. Validates method and record. EA Forum / FAS.
- **wasabipesto [1]** — independent creator of Calibration City / brier.fyi (Brier-scores Polymarket/Kalshi/Manifold/Metaculus). The most on-thesis person in the markets segment, no gatekeeper. contact@wasabipesto.com.

### Tier A — high value (strong validator or strong amplifier)

- **Warren Hatch [3]** — CEO, Good Judgment Inc; superforecaster, ex-hedge-fund. Category brand + bridges to the funds GTM. Public CEO, podcasts.
- **Misha Yagudin [3]** — Samotsvety co-founder; co-runs Arb Research (AI/forecasting consultancy, adjacent to your bespoke GTM). EA Forum / Arb.
- **Robin Hanson [3]** — GMU economist, prediction-market pioneer (futarchy). Masthead-prestige name, replies to substantive ideas. X @robinhanson, blog.
- **Robert de Neufville [2]** — superforecaster; "Telling the Future" Substack/podcast that profiles forecasters/bots. Validation that doubles as a distribution channel.
- **Nate Silver [1]** — already advises Polymarket (exact proof-of-pattern); highest public name-weight on calibration. Silver Bulletin Substack.
- **Joey Krug [1]** — built Augur, now **Founders Fund partner** (advisor + check-writer + intros). *Two-for-one into Ring 3.*
- **Agustin Lebron [1]** — ex-Jane Street trader, author *The Laws of Trading*, runs Essilen Research. Cleanest "trading desks will take us seriously" name; advising is literally his business.
- **Corey Hoffstein [1]** — quant CIO (Newfound), host of *Flirting with Models*. Advisor relationship doubles as distribution to quant buyers.
- **Anthony Aguirre [2]** — Metaculus co-founder; FLI. Founder gravitas; warm intro preferred.
- **Jacob Steinhardt [2]** — UC Berkeley prof, senior author on the LLM-forecasting paper, designed MMLU. Heavyweight ML rigor signal; needs a warm intro.
- **Saul Munn [1]** + **Austin Chen [1]** — organize Manifest (~600-person forecasting festival) + Manifund. Highest amplification-per-equity; control the room. X @akrolsmir, saulmunn.com.
- **Dustin Gouker [1]** — "The Event Horizon," top independent Polymarket/Kalshi newsletter (~9k subs). Pure amplification. X @DustinGouker.
- **Zvi Mowshowitz [1]** — "Don't Worry About the Vase" (32k+ subs); one of the most-read AI writers. Massive reach per mention.
- **Adhi Rajaprabhakaran [1]** — ex-Kalshi; co-founder 5c(c) Capital, the prediction-market VC backed by Kalshi + Polymarket CEOs. *Two-for-one into Ring 3.*

### Tier B — secondary / situational

- **Phil Godzin (pgodzinai) [2]** and **Panshul42 [2]** — top Metaculus AIB bot builders (peer proof). *Both partly pseudonymous: confirm identity before any equity ask.*
- **Fred Zhang [2]** — DeepMind; co-author of both forecasting papers (employer constraints may apply). X @FredZhang0.
- **Josh Rosenberg [1]** — CEO of FRI; often the responsive door into FRI (and Tetlock).
- **Barbara Mellers [2]** / **Don Moore [1]** / **Lyle Ungar [1]** — Good Judgment Project co-founders / ML-aggregation brain; academic ballast for investors, warm intro preferred.
- **Pavel Atanasov [1]** — markets-vs-polls aggregation research; reachable mid-career academic.
- **Joshua D. Clinton [1]** / **TzuFeng Huang [1]** — Vanderbilt, authors of the 2026 Brier-scoring-of-markets study. Credentialed validators.
- **Kai Brusch [1]** (Head of Data, Polymarket) / **Nick Rice [1]** (Markets Lead, Polymarket) — non-founder insiders, advisor ask feasible.
- **Richard Craib [1]** (Numerai), **Wesley Gray [1]** (Alpha Architect), **James / Stephen Grugett [1]** (Manifold), **Greg Laughlin [1]** (Metaculus co-founder, market microstructure), **Michael Story [1]**, **Malcolm Murray [1]**, **Andreas Stuhlmüller [1]** (Ought/Elicit) — situational validators across quant + forecasting.
- **ForecastBench / Metaculus AIB engineers** — Houtan Bastani, Chen Yueh-Han, Ben Wilson, Ryan Beck: hands-on technical allies for benchmark integration.

### Marquee / warm-intro-only (save for a polished proof artifact)

- **Philip Tetlock [2]** — the field's namesake; FRI; recently joined ForecastEx's board, so open to the right vehicle. Route via Karger/Rosenberg.
- **Deger Turan [2]** — CEO of Metaculus (runs FutureEval); ex-hedge-fund-forecasting founder. Useful but mild conflict (platform you compete on).
- **Kalshi founders** (Tarek Mansour, Luana Lopes Lara) — marquee, heavily gatekept; completeness only.

### Conflict flags (treat as intel, not advisors)

- **Mantic** (Toby Shevlane ex-DeepMind, Ben Day) — your explicit $4M comp; direct competitor.
- **FutureSearch** (Dan Schwarz ex-Metaculus CTO, Lawrence Phillips) — adjacent competitor; possible ecosystem contact, not advisor.

### How to open Tier S (the realistic first cluster)

Karger (email) + Halawi (X) on the benchmark side, Liptay + Hickman (EA Forum) on the Metaculus
side, and one top-bot peer (Godzin/Panshul42 via GitHub) once identity is confirmed. That single
cluster answers "are we just a prompt layer?" with institutional + peer validation at once. The FRI
team tweet (x.com/Research_FRI) lists most ForecastBench authors with handles in one place.
