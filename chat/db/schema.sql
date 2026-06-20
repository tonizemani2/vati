-- Vaticinus chat — Neon Postgres schema.
-- Single source of truth for the deployed chat app. Apply with:
--   psql "$DATABASE_URL" -f db/schema.sql
-- Idempotent: safe to re-run.

-- The sealed forward record (seeded from experiments/forward_calls_seal.jsonl by
-- db/seed_forward_calls.mjs). Read-only at runtime — on Cloudflare Workers we cannot
-- read the repo seal file, so it lives here.
create table if not exists forward_calls (
  id             text primary key,
  question       text not null,
  rationale      text,
  probability    double precision,
  ci_low         double precision,
  ci_high        double precision,
  ci_unit        text,
  threshold      double precision,
  threshold_dir  text,
  resolution_date text,
  thesis_kind    text,
  kill_criteria  jsonb,
  implications   jsonb,
  created_at     timestamptz,
  outcome        text
);

-- Per-user chat threads. user_id is the Neon Auth (Stack) user id, or 'anon' when
-- auth is not configured (local dev).
create table if not exists conversations (
  id          uuid primary key default gen_random_uuid(),
  user_id     text not null,
  title       text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- Chat turns. reasoning holds the model's streamed chain-of-thought (nullable).
create table if not exists messages (
  id              bigserial primary key,
  conversation_id uuid not null references conversations(id) on delete cascade,
  role            text not null check (role in ('user','assistant')),
  content         text not null,
  reasoning       text,
  created_at      timestamptz not null default now()
);

-- Immutable engine-computed forecast cards minted from chat (doctrine: forecasts are
-- immutable + falsifiable + scored). The probability/CI are the Monte-Carlo engine's,
-- never the model's prose.
create table if not exists forecast_cards (
  id              uuid primary key default gen_random_uuid(),
  conversation_id uuid references conversations(id) on delete set null,
  user_id         text,
  question        text not null,
  quantity_label  text,
  ci_unit         text,
  base_value      double precision,
  horizon_years   integer,
  g_mean          double precision,
  g_sd            double precision,
  decel           double precision,
  threshold       double precision,
  threshold_dir   text,
  probability     double precision,
  median          double precision,
  ci_low          double precision,
  ci_high         double precision,
  resolution_date text,
  dated_metric    text,
  kill_criteria   jsonb,
  already_priced  text,
  created_at      timestamptz not null default now()
);

create index if not exists idx_conversations_user on conversations(user_id, updated_at desc);
create index if not exists idx_messages_conv on messages(conversation_id, id);
create index if not exists idx_cards_user on forecast_cards(user_id, created_at desc);

-- Per-user credits + free-tier meter. Quick (single model) is free unlimited; Council
-- gets a monthly free allowance then costs credits; Deep always costs credits. Credits
-- are bought via Stripe (credit_ledger is the audit trail).
create table if not exists user_credits (
  user_id            text primary key,
  credits            integer not null default 0,
  free_council_used  integer not null default 0,
  period_start       date not null default date_trunc('month', current_date)::date,
  created_at         timestamptz not null default now()
);

create table if not exists credit_ledger (
  id             bigserial primary key,
  user_id        text not null,
  delta          integer not null,          -- +topup / -spend
  reason         text not null,             -- 'council_spend' | 'deep_spend' | 'stripe_topup' | 'signup_grant'
  stripe_session text,                      -- idempotency key for webhooks
  created_at     timestamptz not null default now()
);
create unique index if not exists idx_ledger_session on credit_ledger(stripe_session) where stripe_session is not null;
create index if not exists idx_ledger_user on credit_ledger(user_id, created_at desc);

-- Monthly memberships. A subscription grants credits_per_month on every paid invoice
-- (first month at checkout, renewals via invoice.paid). The customer<->user mapping lets
-- renewal webhooks (which carry only the Stripe customer) find the user.
create table if not exists subscriptions (
  stripe_subscription_id text primary key,
  user_id                text not null,
  stripe_customer_id     text,
  tier                   text,
  status                 text,            -- active | canceled | past_due | ...
  credits_per_month      integer not null default 0,
  current_period_end     timestamptz,
  updated_at             timestamptz not null default now()
);
create index if not exists idx_subs_user on subscriptions(user_id, updated_at desc);
create index if not exists idx_subs_customer on subscriptions(stripe_customer_id);
