import { getUserId, badOrigin } from "@/lib/auth";
import { stripe, stripeConfigured } from "@/lib/stripe";
import { getActiveSubscription } from "@/lib/credits";
import { edgeRateLimit } from "@/lib/security";

export const dynamic = "force-dynamic";

// Stripe billing portal: lets a subscriber update their card or cancel. Returns a URL to
// redirect to. Requires an active subscription (we need their Stripe customer id).
export async function POST(request: Request) {
  if (badOrigin(request)) return json({ error: "bad origin" }, 403);
  const limited = await edgeRateLimit(request, {
    bucket: "api-portal",
    limit: 20,
    windowSeconds: 600,
  });
  if (limited) return limited;
  const userId = await getUserId(request);
  if (userId === null) return json({ error: "sign in first" }, 401);
  if (!stripeConfigured()) return json({ error: "billing not configured" }, 503);

  const sub = await getActiveSubscription(userId);
  if (!sub?.stripe_customer_id) return json({ error: "no active membership" }, 400);

  const origin =
    request.headers.get("origin") || process.env.VATI_PUBLIC_ORIGIN || new URL(request.url).origin;

  try {
    const portal = await stripe().billingPortal.sessions.create({
      customer: sub.stripe_customer_id,
      return_url: origin + "/",
    });
    return json({ url: portal.url });
  } catch (e) {
    console.error("billing portal failed", e);
    return json({ error: "billing portal is temporarily unavailable" }, 502);
  }
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}
