# Mantic.com — Page Topology & Clone Architecture

Single long landing page (Webflow-built). Cloned into Next.js 16 by **vendoring the
real Webflow stylesheet** (`src/styles/mantic.webflow.css`, asset URLs localized) and
rendering each section from its **exact localized HTML fragment**
(`src/sections/fragments/*.html`, `<script>` stripped), then re-implementing all JS
behavior in one client runtime (`src/sections/ManticRuntime.tsx`). This guarantees
pixel-fidelity (the fluid `clamp()` token system, theme classes, and grid come from the
original CSS) while keeping a clean React structure.

## Flow sections (top → bottom)
| # | Section | Fragment | Theme | Notes |
|---|---------|----------|-------|-------|
| 0 | Nav | `nav` | dark | Blue announcement banner + sticky black bar; logo, links, Book-a-demo / Contact-us pills |
| 1 | Hero | `hero` | black | Headline + 2 buttons over a faded media-tile collage |
| 2 | Example predictions | `sampleqs` | white | Filter tabs + **Swiper** of prediction cards → open detail **modal** |
| 3 | Research | `research` | cream | "A new kind of foresight" + **Rive** diagram, edge copy, interview `<video>`, tournament result cards, China-PV chart |
| 4 | Product / Solutions | `solutions` | #202020 | Vector-grid bg; 3 feature cards + 3 blue cards + **Swiper** |
| 5 | Use cases | `usecases` | cream | Filter tabs (All/Corporate/Finance/Government) + **Swiper** of dark checklist cards |
| 6 | Forecasting tool | `product` | cream | Heading + product screenshot **video** + Book-a-demo |
| 7 | About | `about` | #202020 | Full-bleed office photo bg + funding copy |
| 8 | Mission | `mission` | #202020 | Annotated sentence: colored highlight boxes + dotted-line mono annotations |
| 9 | Team | `team` | #202020 | "Our Team" — 2 leaders + 8 member cards |
| 10 | Footer | `footer` | cream | Logo, "A new kind of foresight" CTA, contact info |

## Overlays (appended after `<main>` in `page.tsx`)
- `contactModal` — "How can we help?" form (`.visible` toggles)
- `sampleqsModal` — per-question detail (image header + accordions; `.visible` toggles)
- `videoModal` — full-screen video player (`.show` toggles)

## Design tokens (from the Webflow CSS)
- Cream `#f3f2f0` · text `#343434` · dark `#202020` · hero black `#000` · brand blue `#3f66fe`
- Fonts: GT Standard 400/500 + GT Standard Mono 500 (self-hosted woff2 in `public/fonts`)

See `BEHAVIORS.md` for the interaction model of each interactive section.
