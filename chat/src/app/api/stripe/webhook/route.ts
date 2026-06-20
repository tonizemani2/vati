import { stripe, stripeConfigured } from "@/lib/stripe";
import { addCredits, upsertSubscription, getSubscriptionByCustomer } from "@/lib/credits";

export const dynamic = "force-dynamic";

// Stripe events. We verify the signature (async variant, required on Workers), then:
//   checkout.session.completed (payment)      -> grant pack credits
//   checkout.session.completed (subscription) -> record sub + grant FIRST month
//   invoice.paid (subscription_cycle)         -> grant renewal credits
//   customer.subscription.updated/deleted     -> track status (stop renewals on cancel)
// All grants are idempotent (unique on the ledger key) so Stripe retries never double-credit.
export async function POST(request: Request) {
  if (!stripeConfigured()) return new Response("billing not configured", { status: 503 });
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!secret) return new Response("no webhook secret", { status: 503 });

  const sig = request.headers.get("stripe-signature");
  if (!sig) return new Response("no signature", { status: 400 });

  const raw = await request.text();
  let event;
  try {
    event = await stripe().webhooks.constructEventAsync(raw, sig, secret);
  } catch (e) {
    return new Response(`bad signature: ${(e as Error).message}`, { status: 400 });
  }

  try {
    switch (event.type) {
      case "checkout.session.completed": {
        const s = event.data.object as {
          id: string;
          mode?: string;
          customer?: string | null;
          subscription?: string | null;
          metadata?: { user_id?: string; tier?: string; credits?: string };
        };
        const userId = s.metadata?.user_id;
        const credits = Number(s.metadata?.credits ?? 0);
        if (!userId) break;

        if (s.mode === "subscription" && s.subscription) {
          // Record the membership (maps customer -> user for renewals) and grant month 1.
          await upsertSubscription({
            subId: s.subscription,
            userId,
            customerId: (s.customer as string) ?? null,
            tier: s.metadata?.tier ?? null,
            status: "active",
            creditsPerMonth: credits,
            periodEnd: null,
          });
          if (credits > 0) await addCredits(userId, credits, s.id, "subscription_start");
        } else if (credits > 0) {
          await addCredits(userId, credits, s.id, "stripe_topup"); // one-time pack
        }
        break;
      }

      case "invoice.paid": {
        const inv = event.data.object as {
          id: string;
          customer?: string | null;
          billing_reason?: string;
        };
        // Only renewals here; the first invoice's credits were granted at checkout.
        if (inv.billing_reason === "subscription_cycle" && inv.customer) {
          const sub = await getSubscriptionByCustomer(inv.customer as string);
          if (sub && sub.credits_per_month > 0) {
            await addCredits(sub.user_id, sub.credits_per_month, inv.id, "subscription_renewal");
          }
        }
        break;
      }

      case "customer.subscription.updated":
      case "customer.subscription.deleted": {
        const sub = event.data.object as {
          id: string;
          customer?: string | null;
          status?: string;
          current_period_end?: number | null;
          metadata?: { user_id?: string; tier?: string; credits_per_month?: string };
        };
        const userId = sub.metadata?.user_id;
        if (userId) {
          await upsertSubscription({
            subId: sub.id,
            userId,
            customerId: (sub.customer as string) ?? null,
            tier: sub.metadata?.tier ?? null,
            status: event.type === "customer.subscription.deleted" ? "canceled" : sub.status ?? "active",
            creditsPerMonth: Number(sub.metadata?.credits_per_month ?? 0),
            periodEnd: sub.current_period_end ? new Date(sub.current_period_end * 1000) : null,
          });
        }
        break;
      }
    }
  } catch (e) {
    // 500 makes Stripe retry, which is what we want on a transient DB error.
    return new Response(`handler failed: ${(e as Error).message}`, { status: 500 });
  }

  return new Response(JSON.stringify({ received: true }), {
    headers: { "Content-Type": "application/json" },
  });
}
