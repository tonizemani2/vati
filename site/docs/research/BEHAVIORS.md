# Mantic.com — Behavior Bible

All behaviors are re-implemented in `src/sections/ManticRuntime.tsx`, faithfully porting
the site's original inline scripts (recovered to `docs/research/scripts-extracted/`).

## Carousels (Swiper v12 — matches the site's version)
Three carousels, all `slidesPerView: "auto"`, `clickable` pagination + custom prev/next arrows:
- `.sampleqs-swiper` (spaceBetween 16) — example predictions
- `.solutions-swiper` (spaceBetween 20; 0 at ≥991px) — product feature cards
- `.usecase-swiper` (spaceBetween 16) — use-case checklist cards

Captured fragments contain Swiper's **post-init DOM** (stale transforms + generated
bullets); the runtime strips those before re-initializing.

## Filter tabs (click-driven)
- `.sampleqs-filter-tab` and `.usecase-filter-tab`: toggle `.is-active`, then show/hide
  cards whose `[data-filter]` tag matches the tab; `view-all-*` shows all. Calls
  `swiper.update()` after filtering.

## Modals (click-driven)
- **Contact** — any `[data-contact]` opens `#contact-modal` (`.visible` + body `.no-scroll`);
  closed by `.contact-modal-close` / `.contact-modal-bg`.
- **Sample detail** — `[data-samplemodal]` shows the matching `.sampleqs-modal-item`
  (all hidden by default) and opens `#sampleqs-modal`; close via
  `.sampleqs-modal-close / -bg / -footer`. Inner `.sampleqs-modal-accordion` items expand
  on `.sampleqs-modal-acc-que` click (animated `max-height`).
- **Video** — `[data-video]` sets the modal `<video>` src and opens `.video-modal` (`.show`);
  `.vid-modal-close` clears + closes.

## Rive animation (research "prediction engine" diagram)
- `[data-animation-type="rive"]` host → `public/rive/mantic.riv`, state machine
  "State Machine 1", artboard "main".
- **Gotchas solved during the clone:**
  1. The captured fragment embeds the original (now-empty) Rive `<canvas>` — removed before mount.
  2. The bundled `@rive-app/canvas` ESM build never initiates its wasm load under Turbopack →
     the runtime is loaded as a **self-hosted UMD script** (`public/rive/rive.js`) with the
     wasm pinned to `public/rive/rive.wasm` via `RuntimeLoader.setWasmUrl`.
  3. The diagram is gated behind state-machine triggers: fire **`start`**, then the
     viewport trigger **`desktop`** (≥992px) / **`mobile`** ~150ms later, or it stays blank.

## Nav banner
- `.nav_banner_close_wrap` dismiss persists via `sessionStorage("hide-nav-banner")`,
  adding `.hide-nav-banner` to `<html>`.

## Responsive
The vendored Webflow CSS carries all original breakpoints (≤991 / ≤767 / ≤479). Carousels,
nav (desktop/mobile variants), and grids collapse exactly as on the source site.
