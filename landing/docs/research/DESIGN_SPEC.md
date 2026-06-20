# Inception design system → Vaticinus landing (design clone)

Source: https://www.inceptionlabs.ai (Framer site). We clone the **visual system** — color,
type, spacing, section rhythm, component shapes, motion — and apply Vati's own truthful content.
We do NOT copy Inception's text, logos, imagery, or fabricate social proof (honesty constraint).

## Color tokens (exact, from getComputedStyle)
- Dark field          `#041414`  rgb(4,20,20)
- Dark field alt      `#0a1414`  (hero slightly bluer black)
- Cream field         `#FAF8F0`  rgb(250,248,240)
- Ink (text on cream) `#2B2A29`  rgb(43,42,41)
- Cream (text on dark)`#FAF8F0`
- Muted on dark       `rgba(250,248,240,0.7)` / `0.4`
- Muted on cream      `rgba(43,42,41,0.62)`
- Teal accent         `#17C4C4`  rgb(23,196,196)
- Teal deep           `#159999`  rgb(21,153,153)
- Card on dark        `#182727`  rgb(24,39,39)
- Accent tint         `rgba(23,196,196,0.12)`
- Hairline on dark    `rgba(247,247,247,0.10)`
- Hairline on cream   `rgba(43,42,41,0.10)`

## Type
- Display: **"KMR Apparat Book"** (light geometric grotesque, weight **375**). Proprietary →
  free near-match **Hanken Grotesk** (variable, supports 300–500). Use weight ~340–400.
- Body / UI: **Inter** (weight 500 for small UI, 400 body).
- Mono: **Geist Mono** (numbers, code, price/spec tags).
- Scale: h1 64px / lh 64px / w375; h2 48px / lh 52.8px / w375; section eyebrow 12–13px teal,
  weight 500, slight tracking; body 14–18px Inter.
- Headings are LIGHT and large — this is the #1 visual signature (current Vati used semibold; wrong).

## Layout & spacing
- Content max-width ~1208px; wide bands 1280–1320px; side padding 56px desktop.
- Very generous vertical rhythm: section padding ~140–200px top/bottom.
- Buttons: pill. Nav links pill radius 60px, padding 0 16px, 12px. CTA pill radius 50px,
  padding 12px 20px. Subtle fills: white@8% on dark, black@5% on cream; teal-fill primary.

## Section architecture (Inception order → Vati mapping)
1. **Announcement bar** (thin, centered, dark) → "Vati is live on the Metaculus Cup → see the record"
2. **Header** — hexagon mark + "vaticinus" wordmark · pill nav · pill CTA. Transparent→tinted on scroll.
3. **Hero (dark #041414)** — light 64px heading w/ teal highlight box on one phrase; subtext;
   a *forecast-input mockup* (mirrors their chat box) with suggestion rows; right: particle/data
   canvas (dots) standing in for their world-map animation.
4. **Dark band — "From hindsight to foresight"** (mirrors "diffusion difference"): the causal spine,
   horizontal animated token/stage band.
5. **Dark band — performance** (mirrors "Blazing-fast"): ForecastBench Brier bars (honest 0.124 dataset).
6. **Cream — feature grid** (mirrors "Build the future"): 3 pillars, eyebrow + light heading + 3 cards.
7. **Cream — "Meet Vati"** (mirrors model family): model card rows — Vati 8B + spec pill tags.
8. **Cream — "Who we work with"** (mirrors researchers): two-col, light heading + teal pill | list rows.
9. **Dark — "Graded in public"** (REPLACES testimonials; NO fake quotes/logos): sealed-record proof.
10. **Dark — "Leak-free by discipline"** (mirrors enterprise/privacy band).
11. **Cream closing CTA** (mirrors "future of LLMs is here"): big light heading + teal pill.
12. **Footer (dark)**.

## Motion
- Reveal-on-scroll fade-up (already have Reveal.tsx). Header tint on scroll>24px.
- Hero: subtle particle drift canvas. Diffusion band: token cells settle L→R (CSS/JS).
- Hover: pills lift / tint; cards border brighten. Transitions ~0.2–0.3s ease.

## Honesty guardrails (project constraint)
- No fabricated testimonials, customer logos, funding, or benchmarks. The "Loved by" slot becomes
  the truthful "Graded in public" proof. Numbers shown are the real ones (8B, 0.124, 12 live, 53 sealed).
