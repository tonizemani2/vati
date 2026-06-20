# humanizer-context.md — Vati brand voice lock

Auto-loaded by the humanizer skill when run from this repo. Treat this as a hard extension of the
chosen voice profile. Target AI-tell score: <= 15. Default voice: professional. Default purpose:
essay/technical.

## Register

Institutional research, the way a sell-side desk note or an arXiv paper reads. A named analyst with a
view, showing their work. Plain words, varied sentence length, specific numbers and dates. Confident
and calm. Never marketing, never chatty-blog, never a Twitter-thread cadence dressed up as analysis.

## Banned outright (these are the tells that get us caught)

- The antithesis punch: "X, not Y" / "not X but Y" / "no longer X but Y" / "isn't about X, it's Y" /
  "the asset that reprices is the site, not the processor". Never use a pithy reversal as a sentence.
  State the point in a plain clause instead.
- Templated openers: "For the last few years...", "In a world where...", "Let's talk about...",
  "Here's the thing", "Make no mistake".
- Templated closers repeated across pieces: identical "Nothing here resolves..." sign-offs. Vary or cut.
- Rule of three ("faster, cheaper, and smarter"). One- or two-item lists are fine.
- AI vocabulary: delve, leverage, landscape (abstract), underscore, robust, seamless, pivotal, crucial,
  tapestry, testament, realm, showcase, vibrant, foster, garner, intricate, multifaceted, notably,
  moreover, furthermore, "it's worth noting", "it is important to note", "at its core", "the real
  question is".
- Em dashes. Use commas, colons, periods, or parentheses.
- Copula drama: "serves as", "stands as", "represents a". Use is/are/has.
- Significance inflation: "marks a pivotal moment", "a turning point in the evolution of".
- Personality filler that pretends to be human: "I genuinely don't know how to feel", "here's what
  gets me". A view is fine; performed emotion is not.

## House rules for forecast content (non-negotiable)

- Every claim is a dated, falsifiable forecast. Never imply a past win; as of mid-2026 nothing has
  resolved (earliest resolution 2027).
- Show both probabilities when the call has them (direction / strict clause). State the gap plainly,
  without apologizing for it.
- Always include the kill condition: the specific thing that would prove the call wrong.
- Map where value moves. Name winners and losers structurally. Never give buy/sell advice.
- Time-sensitive facts (spot prices, export bans, strait closures) are snapshots. Label "as of <date>"
  or have them re-verified before publishing.
- Numbers and named entities come only from the postpack card. Never invent a figure.

## Good vs bad (same fact)

Bad: "The asset that reprices is the site, not the processor."
Good: "Once power is the gate, the value of a data center comes down to one question: can the site
generate its own electricity."

Bad: "AI is undergoing a pivotal shift that underscores the evolving infrastructure landscape."
Good: "By May 2026 the wait for a large grid transformer in the US was about four years. That one
number is changing where AI gets built."
