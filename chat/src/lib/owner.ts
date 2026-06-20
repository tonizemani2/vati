// Owner allowlist — grants the operator's own account unlimited usage.
//
// SECURITY MODEL (read before changing):
//  - Identity is resolved ENTIRELY server-side. The only input is `userId`, which
//    callers obtain from resolveCaller()/getUserId(), i.e. a Clerk session that
//    was cryptographically verified with the secret key. We never trust an email,
//    header, cookie, or body field supplied by the client.
//  - We map that verified userId -> the user's PRIMARY and VERIFIED email via the
//    Clerk backend API, then match against an allowlist. A user can therefore only
//    be the owner if Clerk confirms they control the owner's inbox (Clerk requires
//    email verification), so the email cannot be spoofed.
//  - Fails CLOSED: any error, unverified email, or missing config -> not owner.
//  - The allowlist lives in a server-only module (never NEXT_PUBLIC, never shipped
//    to the client bundle), so the owner's address is not exposed to visitors.
//
// Optional zero-lookup fast path: set VATI_OWNER_IDS to the Clerk user id(s) and we
// skip the email lookup entirely. VATI_OWNER_EMAILS overrides the default address.
import { createClerkClient } from "@clerk/backend";

const OWNER_EMAILS = new Set(
  (process.env.VATI_OWNER_EMAILS ?? "tonizemani921@gmail.com")
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean),
);

const OWNER_IDS = new Set(
  (process.env.VATI_OWNER_IDS ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
);

let cached: ReturnType<typeof createClerkClient> | null = null;
function client() {
  if (!cached) {
    cached = createClerkClient({
      secretKey: process.env.CLERK_SECRET_KEY,
      publishableKey: process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
    });
  }
  return cached;
}

// userId -> isOwner, memoized for the worker's lifetime. The mapping is stable
// (a verified primary email rarely changes), and a stale entry can only ever
// affect the operator's own account, never a paying user's gate. Bounds the
// Clerk lookup to at most once per user per worker instance.
const ownerCache = new Map<string, boolean>();

export async function isOwner(userId: string | null | undefined): Promise<boolean> {
  // Anonymous and the local-dev "anon" identity are never the owner.
  if (!userId || userId === "anon" || userId.startsWith("anon:")) return false;

  // Fast path: explicit id allowlist, no API call.
  if (OWNER_IDS.has(userId)) return true;

  // Email path needs Clerk + a configured allowlist; otherwise fail closed.
  if (!process.env.CLERK_SECRET_KEY || OWNER_EMAILS.size === 0) return false;

  const memo = ownerCache.get(userId);
  if (memo !== undefined) return memo;

  let result = false;
  try {
    const user = await client().users.getUser(userId);
    const primary = user.emailAddresses.find(
      (e) =>
        e.id === user.primaryEmailAddressId &&
        e.verification?.status === "verified",
    );
    if (primary) {
      result = OWNER_EMAILS.has(primary.emailAddress.trim().toLowerCase());
    }
  } catch {
    result = false; // fail closed
  }
  ownerCache.set(userId, result);
  return result;
}
