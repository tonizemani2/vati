// Stripe, configured to run on the edge (Cloudflare Workers): the default Node http
// client uses APIs Workers don't have, so we use the fetch http client + Web Crypto.
// Webhook signatures MUST be verified with constructEventAsync (the sync variant uses
// Node crypto and throws on Workers).
import Stripe from "stripe";

let cached: Stripe | null = null;

export function stripe(): Stripe {
  if (cached) return cached;
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) throw new Error("STRIPE_SECRET_KEY not set");
  cached = new Stripe(key, {
    // apiVersion omitted on purpose: use the account default so we don't pin to a
    // version the installed SDK type doesn't know about.
    httpClient: Stripe.createFetchHttpClient(),
  });
  return cached;
}

export function stripeConfigured(): boolean {
  return Boolean(process.env.STRIPE_SECRET_KEY);
}

// Credit packs. We use inline price_data so you do NOT have to pre-create products in the
// Stripe dashboard — the pack id, price, and credit grant all live here. amountCents is
// what the user pays; credits is what they receive (metadata carries it to the webhook).
export type Pack = { id: string; label: string; credits: number; amountCents: number };

// One-time top-up — the single low-commitment on-ramp for someone who wants to run a few
// Deep/Capture forecasts without a subscription. Deliberately ONE option (kept simple) and
// priced above the per-credit membership rate, so it nudges toward a membership.
export const PACKS: Pack[] = [
  { id: "topup", label: "Top-up", credits: 150, amountCents: 2000 },
];

export function packById(id: string): Pack | undefined {
  return PACKS.find((p) => p.id === id);
}

// Monthly memberships. credits replenish on every paid invoice. Two tiers only — the
// individual forecaster and the desk — kept deliberately simple. Per-credit rate improves
// with the tier, and both beat the one-time top-up. Anything bigger (a fund mandate) is a
// booked conversation, not a self-serve tier.
export type Plan = { id: string; label: string; creditsPerMonth: number; amountCents: number };

// Grants sized so margin stays >=70% even under worst-case heavy use (every run a heavy
// Council, ~$0.026 cost/credit) — see the run-cost analysis. Real margin runs far higher
// (breakage, the gate firing <100% of the time, average synthesis well under the cap).
// 1 credit ~= $0.10 of value; Council = 1 credit, Deep = 5.
export const PLANS: Plan[] = [
  { id: "analyst", label: "Analyst", creditsPerMonth: 500, amountCents: 5000 },
  { id: "desk", label: "Desk", creditsPerMonth: 2200, amountCents: 20000 },
];

export function planById(id: string): Plan | undefined {
  return PLANS.find((p) => p.id === id);
}
