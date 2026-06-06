# CONSTITUTION.md — How We Work

The durable principles for this project. `plan.md` is the goal; this is the discipline that gets us there.
Every AI coding session reads `CLAUDE.md`, which enforces these rules operationally.

These 8 rules are deliberately few. If a decision isn't covered here, default to: **less code, more thinking, ask the human.**

---

### 1. GIGO gate — trust is earned, not ranked
No `Source` enters the system without a non-empty `trust_rationale` and a `trust_score`. Trust means a *strong, stated reason*: primary/authoritative origin, verifiable, named methodology. **Search-engine rank is not trust.** Garbage in, garbage out — so we gate the input.

### 2. Strict layering — exhaust before advancing
The pillars are data-flow layers in causal order (Frontier → Curves → Dependency graph → Supply elasticity → Demand → Capital → Pricing → Policy/geo → Outcomes). **Fully exhaust the current layer before opening the next.** Never go 50/70/90% and jump ahead. The only exception is an explicit Decision that says "park this, come back later."

### 3. Cost gate — free first, ask before spending
Default to free/keyless paths always. Any action that costs money logs a `CostLedgerEntry` *before* it runs, and any spend above the auto-approve threshold (default **$0**) blocks on the human's explicit approval. No silent spend, ever.

### 4. Ask, don't assume — pivotal choices are concise Decisions
When a fork genuinely changes direction, create a `Decision`: a *short* prompt + options + a recommendation. Never a wall of text, never silently chosen by the AI. The human steers; the AI proposes.

### 5. Minimalism — earn your place
No new dependency, service, or abstraction without justifying it against what already exists. Prefer deleting code to adding it. Two folders (`engine/`, `cockpit/`), one DB. Periodically ask of every file and feature: **"does this deserve its place here?"** If not, cut it.

### 6. Vendored isolation — never leak secrets, never couple
Code derived from `orca97-v2` lives *only* in `engine/adapters/_vendor/`, is never edited in place, and **never reads another repo's `.env`**. Everything else imports only the typed wrappers in `engine/adapters/`. This repo reads secrets from its own env or nowhere.

### 7. Forecasts are immutable + falsifiable
Every `ForecastCard` has a resolution date and explicit kill-criteria. You never edit a card — you `supersede` it (the old one stays for the track record). Brier score is computed at resolution. A forecast without a kill-condition and a resolution date is a story, not a bet.

### 8. Visual-first — if the human can't see it, it doesn't exist
Every capability surfaces in the cockpit (at minimum an empty state) before it's considered done. The system is a human + AI thinking loop; the cockpit is how the human stays in the loop and steers.

---

### Reasoning vs. scale
The high-value reasoning is done by **Claude in-session (human + Claude)** by default. Other providers (MiniMax, DeepInfra keyless, OpenRouter) are **only for scale** — bulk extraction, OCR, high-volume passes — and always pass rules 3 and 6.

### The one risk we actively guard against
Re-growing `orca97-v2`: turning a thinking aid into an ops platform (plugin pipelines, schedulers, an API server, automated source discovery). If `engine/` ever needs its own architecture diagram, we've already lost.
