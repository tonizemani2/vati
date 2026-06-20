// One seam every API route uses to identify the caller.
//   - auth not configured (local dev, no Clerk keys): returns 'anon' so everything works.
//   - auth configured + signed in: returns the Clerk user id.
//   - auth configured + NOT signed in: returns null (the route should 401).
//
// We verify the Clerk session DIRECTLY from the request with @clerk/backend, NOT via
// clerkMiddleware/auth(). Reason: Next 16 runs proxy/middleware on the Node.js runtime,
// which OpenNext on Cloudflare Workers cannot bundle. authenticateRequest works on the edge
// and needs no middleware, so there is no proxy.ts.
import { createClerkClient } from "@clerk/backend";

export function authEnabled(): boolean {
  return Boolean(process.env.CLERK_SECRET_KEY);
}

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

export async function getUserId(req: Request): Promise<string | null> {
  if (!authEnabled()) return "anon";
  try {
    const state = await client().authenticateRequest(req, {
      authorizedParties: [
        "https://chat.vaticinus.com",
        "http://localhost:3000",
      ],
    });
    return state.toAuth()?.userId ?? null;
  } catch {
    return null;
  }
}

// "Open front door": a signed-out visitor still gets an identity so the free tiers work
// without a wall. Signed-in -> the Clerk user id. Signed-out -> a stable anonymous id.
// Paid credits + Deep still require a real account because anon starts at 0 credits.
export type Caller = { id: string; anon: boolean; setCookie?: string };

function readCookie(req: Request, name: string): string | null {
  const raw = req.headers.get("cookie") ?? "";
  const m = raw.match(new RegExp(`(?:^|;\\s*)${name}=([^;]+)`));
  return m ? decodeURIComponent(m[1]) : null;
}

// Owner-only "View as user" QA flag. Set by the client (CreditsPanel toggle). Safe to be
// client-driven: it can only DOWNGRADE the owner to a normal account (exercise the real
// paywall), never grant unlimited to anyone. Non-owners setting it has no effect.
export function viewAsUser(req: Request): boolean {
  return readCookie(req, "vati_as_user") === "1";
}

async function sha256Hex(s: string): Promise<string> {
  const data = new TextEncoder().encode(s);
  const buf = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// The free-Council meter must NOT be rotatable by the client, or anyone can refarm the 3
// free runs forever by clearing a cookie. So the anonymous identity is anchored to the
// Cloudflare-verified client IP (+ coarse UA), NOT to a client-controlled cookie. Clearing
// cookies no longer mints a fresh free bucket; only a new IP does (proxy rotation), which
// raises abuse cost from "free forever" to "needs rotating IPs". Shared-NAT visitors share a
// bucket, an acceptable trade for a free tier. The cookie is kept only as a convenience id
// for grouping a visitor's conversations, never as the meter key.
export async function resolveCaller(req: Request): Promise<Caller> {
  const uid = await getUserId(req);
  if (uid && uid !== "anon") return { id: uid, anon: false }; // signed-in Clerk user
  if (uid === "anon") return { id: "anon", anon: false }; // auth disabled (local dev): fully open

  // Clerk is on but the caller is signed out: derive a stable, non-rotatable anon id.
  const ip =
    req.headers.get("CF-Connecting-IP") ||
    req.headers.get("x-real-ip") ||
    (req.headers.get("x-forwarded-for") || "").split(",")[0].trim() ||
    "0.0.0.0";
  const ua = (req.headers.get("user-agent") || "").slice(0, 40);
  const id = `anon:${await sha256Hex(`${ip}|${ua}`)}`;
  const existing = readCookie(req, "vati_anon");
  return {
    id,
    anon: true,
    setCookie: existing
      ? undefined
      : `vati_anon=${id.slice(5, 21)}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Lax; Secure`,
  };
}

// Defense-in-depth CSRF guard for state-changing POSTs. Same-origin requests send no Origin
// header (or our own); anything else is rejected. SameSite=Lax + Clerk authorizedParties
// already block the realistic cross-site paths; this closes the gap explicitly.
const ALLOWED_ORIGINS = new Set([
  "https://chat.vaticinus.com",
  "http://localhost:3000",
]);

export function badOrigin(req: Request): boolean {
  const origin = req.headers.get("origin");
  if (!origin) return false; // same-origin / server-to-server / curl: not a browser CSRF vector
  try {
    const url = new URL(origin);
    if (
      url.protocol === "http:" &&
      (url.hostname === "localhost" ||
        url.hostname === "127.0.0.1" ||
        url.hostname === "::1" ||
        url.hostname === "[::1]")
    ) {
      return false;
    }
  } catch {
    return true;
  }
  return !ALLOWED_ORIGINS.has(origin);
}
