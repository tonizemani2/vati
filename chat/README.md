# Vaticinus chat

A ChatGPT-style chat UI (cloned from `chatgpt.com`, then reskinned to the Vaticinus brand
from `../site`: indigo `#6d6afc`, Helvetica Neue, dark indigo "ticket" cards) wired to
**our actual forecasting engine**. Users chat; responses stream from our LLM under the
Vaticinus persona; forecastable questions render a real **forecast card** whose probability
and 80% interval are computed by `engine.forecast.mc_quantity` (the same Monte-Carlo engine
the cards use), not guessed by the LLM.

Isolated from `../site` on purpose: `site/` is a static export for Cloudflare Pages and
cannot host a streaming API. This app has live server routes, so it deploys as a Cloudflare
**Worker** via the OpenNext adapter, backed by **Neon Postgres** and gated by **Neon Auth**.

The forecast engine is pure TypeScript (`src/lib/mc.ts`, ported 1:1 from
`engine.forecast.mc_quantity`) — there is NO Python subprocess, so the app runs anywhere.

## How it ties to the backend

- **Forecast cards** — the model emits a fenced `vaticinus-forecast` spec (a Fermi
  decomposition: measurable quantity, current value, projected growth, threshold). The UI
  strips it from the prose, POSTs it to `/api/forecast`, which runs `src/lib/mc.ts`
  (Monte-Carlo, 80k samples) → engine-computed P, CI, median, histogram. Each card is also
  persisted immutably to Neon (`forecast_cards`).
- **Live record** — `/api/record` reads the `forward_calls` table in Neon (seeded from
  `../experiments/forward_calls_seal.jsonl` by `pnpm seed`). Starter chips come from these.
- **History** — `/api/chat` creates a `conversations` row + saves the user turn; the client
  saves the assistant turn via `/api/messages` once the stream finishes. Per-user when auth
  is on (`user_id` = Neon Auth id), or `anon` in open local dev.
- **Auth** — Neon Auth (Better Auth, `@neondatabase/neon-js`). Server gate in `src/lib/auth.ts`
  (`auth.getSession()`), auth proxy at `/api/auth/[...path]`, sign-in UI at `/auth/sign-in`.
  When `NEON_AUTH_BASE_URL` + `NEON_AUTH_COOKIE_SECRET` are set, `/api/chat` requires sign-in
  (keeps the paid model off the open internet). With neither, the app runs open as `anon`.

## The council + credits (the product)

A single model is a commodity. The differentiated path is the **council** (`src/lib/council.ts`,
`/api/council`): for one question it fans out 5 decorrelated analysts (supply, demand, pricing,
policy, contrarian) on `deepseek-v4-flash` in parallel, runs a **gate** (`deepseek-v4-pro`) that
checks "is this already priced in?" against a live prediction-market anchor
(`src/lib/market.ts`, keyless Manifold/Metaculus), then a **synthesis** pass that commits to one
answer and emits the same engine forecast card. All of it streams (analysts → gate verdict →
answer). The depth selector in the composer picks the tier:

- **Quick** — the single-model `/api/chat`. Free, unlimited (costs us ~nothing).
- **Council** — 5 analysts + gate. `VATI_FREE_COUNCIL` free runs/month, then 1 credit.
- **Deep** — 7 analysts, deeper prompts. 4 credits.

**Money model** (`src/lib/credits.ts`, tables `user_credits` + `credit_ledger`): Quick is the
free funnel; the council is where real compute is spent, so it meters a monthly free allowance
then bills **credits** bought via Stripe (`src/lib/stripe.ts`, `/api/checkout`,
`/api/stripe/webhook`). Credit packs are defined in `stripe.ts` (`PACKS`) using inline
`price_data`, so you do NOT pre-create products in the Stripe dashboard. The webhook grants
credits idempotently (unique on the Stripe session id). BYOK is intentionally not the default.

## Run (local)

```bash
cd chat
pnpm install                       # first time only
cp .env.example .env.local         # set DATABASE_URL (Neon); provider keys come from repo-root .env
pnpm seed                          # one time: load the forward record into Neon
pnpm dev                           # http://localhost:3000  (or PORT=3030 pnpm dev)
```

Provider keys (DEEPSEEK_API_KEY etc.) are read from the repo-root `.env` in local dev as a
convenience. `DATABASE_URL` goes in `.env.local`. Auth is OFF locally unless you set the three
Neon Auth keys, so the chat works immediately as user `anon`.

## Model backend

Default is **DeepSeek V4 Pro** (`deepseek-v4-pro`) fronted by our persona. The DeepSeek API
serves `deepseek-v4-pro` and `deepseek-v4-flash` (the old `deepseek-chat` alias is retired).
Both are reasoning models: they stream a chain-of-thought (`reasoning_content`) before the
answer, so the UI shows a live "Thinking" block, then the answer, then the engine card.

Switch with env vars (no code change):

```bash
VATI_CHAT_MODEL=deepseek-v4-flash pnpm start    # snappier (shorter reasoning)
VATI_CHAT_PROVIDER=openrouter     pnpm start    # OpenRouter (OPENROUTER_API_KEY)
VATI_CHAT_PROVIDER=minimax        pnpm start    # MiniMax (MINIMAX_API_KEY + MINIMAX_BASE_URL)
```

## Ship (Cloudflare Workers)

One-time setup, then `pnpm ship` for every deploy.

```bash
# 1. Apply schema + seed the record into Neon (once)
psql "$DATABASE_URL" -f db/schema.sql
DATABASE_URL="postgres://..." pnpm seed

# 2. Set Worker secrets (once; never commit these)
npx wrangler secret put DATABASE_URL
npx wrangler secret put DEEPSEEK_API_KEY
npx wrangler secret put NEON_AUTH_BASE_URL               # the Auth URL from Neon -> Auth tab
npx wrangler secret put NEON_AUTH_COOKIE_SECRET          # 64 hex chars: node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"

# 3. (optional) Stripe credit packs — only needed to charge money
npx wrangler secret put STRIPE_SECRET_KEY                # sk_live_... (or sk_test_... to trial)
npx wrangler secret put STRIPE_WEBHOOK_SECRET            # whsec_... from the webhook endpoint you create
npx wrangler secret put VATI_PUBLIC_ORIGIN              # https://chat.vaticinus.com (Stripe return URLs)
# In Stripe: add a webhook endpoint -> https://<your-domain>/api/stripe/webhook, event
# checkout.session.completed; paste its signing secret above. Locally: `stripe listen
# --forward-to localhost:3000/api/stripe/webhook` prints a whsec_ for .dev.vars.

# 4. Deploy
pnpm ship                                                # build + deploy the Worker
# or test the production bundle locally first:
pnpm preview
```

Without the two NEON_AUTH_* secrets the app deploys OPEN (anyone can spend your model budget).
Also add your production domain (and http://localhost:3000 for local) to the Auth "Domains"
allow-list in the Neon dashboard, or sign-in redirects are blocked.

## Layout

- `src/app/page.tsx` — chat UI (empty state + conversation + streaming fetch loop)
- `src/components/{Sidebar,Composer}.tsx` — the cloned shell
- `src/app/api/chat/route.ts` — streaming Route Handler (SSE in, token text out)
- `src/lib/model.ts` — provider table, repo `.env` loader, the forecasting persona

## Known seams / next

- **Conversation switcher:** the sidebar lists/reopens persisted threads via
  `/api/conversations`. Loaded historical turns currently restore the text + reasoning, but not
  the original forecast-card visual; cards remain persisted separately in `forecast_cards`.
- **Auth on Workers:** Neon Auth (Better Auth) is wired and verified locally (gate returns
  401, `/api/auth/get-session` proxies to Neon, sign-in UI renders) and bundles for Workers.
  Validate the Google OAuth round-trip on the first real deploy with the domain allow-listed.
- **Data-layer grounding (the next moat):** the council reasons + uses a live market anchor,
  but it does NOT yet query our Python data layer (OpenAlex citation velocity, paper->patent
  commercialization, concept graph). That needs a small Python sidecar (Modal scale-to-zero, or
  any cheap box) exposing the engine's signals; the council would call it as one more "analyst."
  This is the planned upgrade that makes the Deep tier worth its price. The "Data layer" sidebar
  item stays a placeholder until then.
