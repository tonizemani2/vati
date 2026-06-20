// Credits + free-tier metering. The economics: Quick (single model) is free and
// unlimited because it costs us fractions of a cent; the multi-agent Council is where
// real compute is spent, so it carries a small monthly free allowance then bills credits.
// Credits are bought via Stripe. This is the whole margin model in one file.
import { db, dbConfigured } from "./db";
import { isOwner } from "./owner";

export const FREE_COUNCIL_PER_MONTH = Number(process.env.VATI_FREE_COUNCIL ?? 3);
export const COST_COUNCIL = Number(process.env.VATI_COST_COUNCIL ?? 1);
export const COST_DEEP = Number(process.env.VATI_COST_DEEP ?? 5);
// Capture (the value-capture play: who to call + how the call makes money) is the deepest
// surface, always paid, no free allowance. It is the conversion funnel: an anon hits the gate
// and is nudged to sign in.
export const COST_CAPTURE = Number(process.env.VATI_COST_CAPTURE ?? 5);
// Contacts ("find who to call": resolve a PURSUE play's named targets to real, verified,
// enriched people/companies). Paid, no free allowance, same conversion role as capture.
export const COST_CONTACTS = Number(process.env.VATI_COST_CONTACTS ?? 3);
// Scan ("run it yourself"): mint fresh pre-consensus structural calls for an area, grounded in the
// data layer. Generative + grounded, so it bills like Deep. Members run it from their monthly grant.
export const COST_SCAN = Number(process.env.VATI_COST_SCAN ?? 5);

export type Tier = "quick" | "council" | "deep" | "capture" | "contacts" | "scan";

export type Account = {
  credits: number;
  freeCouncilRemaining: number;
  unlimited?: boolean;
};

// Large sentinel for the owner account so any UI that ignores the `unlimited`
// flag still reads as effectively boundless rather than zero.
const UNLIMITED = 999999;

export type ConsumeResult =
  | { ok: true; mode: "free" | "credit"; account: Account }
  | { ok: false; reason: "insufficient"; account: Account };

// Ensure the row exists and roll the monthly free meter if we crossed into a new month.
async function ensureAndRoll(userId: string): Promise<void> {
  const sql = db();
  await sql`
    insert into user_credits (user_id) values (${userId})
    on conflict (user_id) do nothing
  `;
  await sql`
    update user_credits
       set free_council_used = 0,
           period_start = date_trunc('month', current_date)::date
     where user_id = ${userId}
       and period_start < date_trunc('month', current_date)::date
  `;
}

// `ignoreOwner` powers the owner's "View as user" QA mode: treat the operator as a
// normal account so the real free-meter/paywall is exercised. It can only ever DOWNGRADE
// the owner (never grant anyone unlimited), so it is safe to be driven by a client cookie.
export async function getAccount(userId: string, ignoreOwner = false): Promise<Account> {
  // Owner account: unlimited, resolved from the Clerk-verified identity. No DB row.
  if (!ignoreOwner && (await isOwner(userId))) {
    return { credits: UNLIMITED, freeCouncilRemaining: UNLIMITED, unlimited: true };
  }
  if (!dbConfigured()) return { credits: 0, freeCouncilRemaining: FREE_COUNCIL_PER_MONTH };
  await ensureAndRoll(userId);
  const sql = db();
  const rows = (await sql`
    select credits, free_council_used from user_credits where user_id = ${userId}
  `) as unknown as { credits: number; free_council_used: number }[];
  const r = rows[0] ?? { credits: 0, free_council_used: 0 };
  return {
    credits: r.credits,
    freeCouncilRemaining: Math.max(0, FREE_COUNCIL_PER_MONTH - r.free_council_used),
  };
}

// Atomically (at row scale) charge for a run. Quick is always free.
export async function consume(userId: string, tier: Tier, ignoreOwner = false): Promise<ConsumeResult> {
  if (tier === "quick" || !dbConfigured()) {
    return { ok: true, mode: "free", account: await getAccount(userId, ignoreOwner) };
  }
  // Owner bypass: unlimited Council/Deep, never charged, no ledger entry. Keyed on
  // the server-verified identity only (see lib/owner.ts), so it cannot be abused.
  // Skipped under "View as user" so the owner can test the real charge path.
  if (!ignoreOwner && (await isOwner(userId))) {
    return { ok: true, mode: "free", account: await getAccount(userId) };
  }
  await ensureAndRoll(userId);
  const sql = db();

  // Council can draw the monthly free allowance first; Deep always pays credits.
  if (tier === "council") {
    const freed = (await sql`
      update user_credits
         set free_council_used = free_council_used + 1
       where user_id = ${userId} and free_council_used < ${FREE_COUNCIL_PER_MONTH}
      returning credits, free_council_used
    `) as unknown as { credits: number; free_council_used: number }[];
    if (freed.length) {
      return {
        ok: true,
        mode: "free",
        account: {
          credits: freed[0].credits,
          freeCouncilRemaining: Math.max(0, FREE_COUNCIL_PER_MONTH - freed[0].free_council_used),
        },
      };
    }
  }

  const cost =
    tier === "deep"
      ? COST_DEEP
      : tier === "capture"
        ? COST_CAPTURE
        : tier === "contacts"
          ? COST_CONTACTS
          : tier === "scan"
            ? COST_SCAN
            : COST_COUNCIL;
  const paid = (await sql`
    update user_credits
       set credits = credits - ${cost}
     where user_id = ${userId} and credits >= ${cost}
    returning credits, free_council_used
  `) as unknown as { credits: number; free_council_used: number }[];

  if (paid.length) {
    const reason =
      tier === "deep"
        ? "deep_spend"
        : tier === "capture"
          ? "capture_spend"
          : tier === "contacts"
            ? "contacts_spend"
            : tier === "scan"
              ? "scan_spend"
              : "council_spend";
    await sql`
      insert into credit_ledger (user_id, delta, reason)
      values (${userId}, ${-cost}, ${reason})
    `;
    return {
      ok: true,
      mode: "credit",
      account: {
        credits: paid[0].credits,
        freeCouncilRemaining: Math.max(0, FREE_COUNCIL_PER_MONTH - paid[0].free_council_used),
      },
    };
  }

  return { ok: false, reason: "insufficient", account: await getAccount(userId) };
}

// Stripe webhook calls this. Idempotent on the idempotency key (session id for one-time
// packs, invoice id for subscription renewals) via the unique ledger index.
export async function addCredits(
  userId: string,
  amount: number,
  idempotencyKey: string,
  reason = "stripe_topup",
): Promise<boolean> {
  const sql = db();
  const ins = (await sql`
    insert into credit_ledger (user_id, delta, reason, stripe_session)
    values (${userId}, ${amount}, ${reason}, ${idempotencyKey})
    on conflict (stripe_session) where stripe_session is not null do nothing
    returning id
  `) as unknown as { id: number }[];
  if (!ins.length) return false; // already processed this key
  await sql`
    insert into user_credits (user_id, credits) values (${userId}, ${amount})
    on conflict (user_id) do update set credits = user_credits.credits + ${amount}
  `;
  return true;
}

// --- subscriptions ---------------------------------------------------------
export type SubRow = {
  stripe_subscription_id: string;
  user_id: string;
  stripe_customer_id: string | null;
  tier: string | null;
  status: string | null;
  credits_per_month: number;
  current_period_end: string | null;
};

// Record/refresh a subscription (called from checkout.session.completed + subscription.*).
export async function upsertSubscription(s: {
  subId: string;
  userId: string;
  customerId: string | null;
  tier: string | null;
  status: string;
  creditsPerMonth: number;
  periodEnd: Date | null;
}): Promise<void> {
  const sql = db();
  await sql`
    insert into subscriptions
      (stripe_subscription_id, user_id, stripe_customer_id, tier, status, credits_per_month, current_period_end, updated_at)
    values
      (${s.subId}, ${s.userId}, ${s.customerId}, ${s.tier}, ${s.status},
       ${s.creditsPerMonth}, ${s.periodEnd ? s.periodEnd.toISOString() : null}, now())
    on conflict (stripe_subscription_id) do update set
      status = ${s.status},
      tier = coalesce(${s.tier}, subscriptions.tier),
      credits_per_month = case when ${s.creditsPerMonth} > 0 then ${s.creditsPerMonth} else subscriptions.credits_per_month end,
      stripe_customer_id = coalesce(${s.customerId}, subscriptions.stripe_customer_id),
      current_period_end = coalesce(${s.periodEnd ? s.periodEnd.toISOString() : null}, subscriptions.current_period_end),
      updated_at = now()
  `;
}

// Renewal webhooks carry only the Stripe customer; map back to the user + monthly grant.
export async function getSubscriptionByCustomer(customerId: string): Promise<SubRow | null> {
  const sql = db();
  const rows = (await sql`
    select * from subscriptions
    where stripe_customer_id = ${customerId} and status = 'active'
    order by updated_at desc limit 1
  `) as unknown as SubRow[];
  return rows[0] ?? null;
}

// The user's current membership, for the sidebar + the credits endpoint.
export async function getActiveSubscription(userId: string): Promise<SubRow | null> {
  if (!dbConfigured()) return null;
  const sql = db();
  const rows = (await sql`
    select * from subscriptions
    where user_id = ${userId} and status = 'active'
    order by updated_at desc limit 1
  `) as unknown as SubRow[];
  return rows[0] ?? null;
}
