import { getUserId, viewAsUser } from "@/lib/auth";
import { isOwner } from "@/lib/owner";
import {
  getAccount,
  getActiveSubscription,
  FREE_COUNCIL_PER_MONTH,
  COST_COUNCIL,
  COST_DEEP,
} from "@/lib/credits";

export const dynamic = "force-dynamic";

// Balance for the sidebar badge: free-council allowance + paid credits + current membership.
export async function GET(request: Request) {
  const userId = await getUserId(request);
  if (userId === null) {
    return json({ signedIn: false, credits: 0, freeCouncilRemaining: 0, plan: null });
  }
  const asUser = viewAsUser(request);
  // Real owner status is reported independently of the view so the client can show the
  // "View as user" toggle even while the account is being rendered as a normal user.
  const [owner, account, sub] = await Promise.all([
    isOwner(userId),
    getAccount(userId, asUser),
    getActiveSubscription(userId),
  ]);
  return json({
    signedIn: true,
    ...account,
    owner,
    viewAsUser: asUser && owner,
    plan: sub ? { tier: sub.tier, creditsPerMonth: sub.credits_per_month } : null,
    policy: { freePerMonth: FREE_COUNCIL_PER_MONTH, costCouncil: COST_COUNCIL, costDeep: COST_DEEP },
  });
}

function json(body: unknown) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}
