import { getUserId, badOrigin } from "@/lib/auth";
import { stripe, stripeConfigured, packById, planById, PACKS, PLANS } from "@/lib/stripe";
import { edgeRateLimit } from "@/lib/security";

export const dynamic = "force-dynamic";

// List the available memberships + top-ups (so the UI can render the buy options).
export async function GET() {
  return new Response(JSON.stringify({ configured: stripeConfigured(), plans: PLANS, packs: PACKS }), {
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

// Create a Stripe Checkout Session and return its URL.
//   { type: "pack", id }  -> one-time payment, credits granted on checkout.session.completed
//   { type: "sub",  id }  -> monthly subscription, credits granted on each paid invoice
// The user_id rides in metadata so the webhook can attribute the grant. For subscriptions we
// also stamp subscription_data.metadata so renewals are self-describing.
export async function POST(request: Request) {
  if (badOrigin(request)) return json({ error: "bad origin" }, 403);
  const limited = await edgeRateLimit(request, {
    bucket: "api-checkout",
    limit: 20,
    windowSeconds: 600,
  });
  if (limited) return limited;
  const userId = await getUserId(request);
  if (userId === null) return json({ error: "sign in first" }, 401);
  if (!stripeConfigured()) return json({ error: "billing not configured" }, 503);

  let type = "pack";
  let id = "";
  try {
    const body = await request.json();
    type = body?.type === "sub" ? "sub" : "pack";
    id = String(body?.id ?? body?.pack ?? "");
  } catch {
    return json({ error: "bad request" }, 400);
  }

  const origin =
    request.headers.get("origin") || process.env.VATI_PUBLIC_ORIGIN || new URL(request.url).origin;
  const success_url = `${origin}/?purchase=success`;
  const cancel_url = `${origin}/?purchase=cancel`;

  try {
    if (type === "sub") {
      const plan = planById(id);
      if (!plan) return json({ error: "unknown plan" }, 400);
      const session = await stripe().checkout.sessions.create({
        mode: "subscription",
        line_items: [
          {
            quantity: 1,
            price_data: {
              currency: "usd",
              unit_amount: plan.amountCents,
              recurring: { interval: "month" },
              product_data: { name: `Vaticinus ${plan.label} membership` },
            },
          },
        ],
        metadata: { user_id: userId, kind: "sub", tier: plan.id, credits: String(plan.creditsPerMonth) },
        subscription_data: {
          metadata: { user_id: userId, tier: plan.id, credits_per_month: String(plan.creditsPerMonth) },
        },
        success_url,
        cancel_url,
      });
      return json({ url: session.url });
    }

    const pack = packById(id);
    if (!pack) return json({ error: "unknown pack" }, 400);
    const session = await stripe().checkout.sessions.create({
      mode: "payment",
      line_items: [
        {
          quantity: 1,
          price_data: {
            currency: "usd",
            unit_amount: pack.amountCents,
            product_data: { name: `Vaticinus ${pack.label} top-up — ${pack.credits} credits` },
          },
        },
      ],
      metadata: { user_id: userId, kind: "pack", pack: pack.id, credits: String(pack.credits) },
      success_url,
      cancel_url,
    });
    return json({ url: session.url });
  } catch (e) {
    console.error("checkout session failed", e);
    return json({ error: "checkout is temporarily unavailable" }, 502);
  }
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}
