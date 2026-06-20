// POST /api/contact  — handles the "Get in touch" form.
// Bot defences (no user friction): same-origin check, honeypot field,
// time-trap (a human takes more than a couple of seconds to fill the form),
// field validation, and a light per-IP rate limit via the Cache API.
// Delivery goes through Resend (see ./_resend).

import { sendEmail } from "./_resend";

type Env = {
  RESEND_API_KEY?: string;
  CONTACT_TO?: string; // defaults to toni@vaticinus.com
  CONTACT_FROM?: string; // must be on a Resend-verified domain
  TURNSTILE_SECRET_KEY?: string;
};

const ALLOWED_HOSTS = ["vaticinus.com", "www.vaticinus.com"];
const ALLOWED_PREVIEW_SUFFIX = ".vaticinus.pages.dev";
const MIN_FILL_MS = 2500; // faster than a human realistically fills the form
const MAX_FILL_MS = 1000 * 60 * 60 * 6; // stale/replayed token

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });

function isValidEmail(s: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s) && s.length <= 254;
}

function originAllowed(request: Request): boolean {
  const ref = request.headers.get("Origin") || request.headers.get("Referer");
  if (!ref) return false; // same-origin browser POSTs always send one of these
  try {
    const host = new URL(ref).hostname;
    return (
      ALLOWED_HOSTS.includes(host) ||
      host === "localhost" ||
      host === "127.0.0.1" ||
      host.endsWith(ALLOWED_PREVIEW_SUFFIX) // project-scoped preview deployments
    );
  } catch {
    return false;
  }
}

type TurnstileSiteverify = {
  success?: boolean;
  hostname?: string;
  "error-codes"?: string[];
};

function hostnameAllowed(hostname: string | undefined, requestHost: string) {
  if (!hostname) return true;
  return (
    hostname === requestHost ||
    ALLOWED_HOSTS.includes(hostname) ||
    hostname.endsWith(ALLOWED_PREVIEW_SUFFIX) ||
    hostname === "localhost" ||
    hostname === "127.0.0.1"
  );
}

async function verifyTurnstile(
  token: string,
  request: Request,
  env: Env,
): Promise<boolean> {
  if (!env.TURNSTILE_SECRET_KEY) return true;
  if (!token) return false;

  const body = new FormData();
  body.set("secret", env.TURNSTILE_SECRET_KEY);
  body.set("response", token);
  body.set("idempotency_key", crypto.randomUUID());

  const ip = request.headers.get("CF-Connecting-IP");
  if (ip) body.set("remoteip", ip);

  const res = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
    method: "POST",
    body,
  });
  if (!res.ok) return false;

  const result = (await res.json()) as TurnstileSiteverify;
  const requestHost = new URL(request.url).hostname;
  if (!hostnameAllowed(result.hostname, requestHost)) {
    console.warn("turnstile hostname mismatch:", result.hostname, requestHost);
    return false;
  }
  if (!result.success) {
    console.warn("turnstile rejected:", result["error-codes"]?.join(",") || "unknown");
  }
  return Boolean(result.success);
}

// Best-effort per-IP throttle: 5 submissions / 10 min. Uses the edge Cache as a
// tiny counter store; not bulletproof across colos but stops trivial flooding.
async function rateLimited(request: Request): Promise<boolean> {
  const ip = request.headers.get("CF-Connecting-IP") || "anon";
  const key = new Request(`https://ratelimit.local/contact/${ip}`);
  // @ts-expect-error caches.default exists in the Workers runtime
  const cache = caches.default as Cache;
  const hit = await cache.match(key);
  const count = hit ? parseInt(await hit.text(), 10) || 0 : 0;
  if (count >= 5) return true;
  await cache.put(
    key,
    new Response(String(count + 1), {
      headers: { "Cache-Control": "max-age=600" },
    }),
  );
  return false;
}

export const onRequestPost: (ctx: {
  request: Request;
  env: Env;
}) => Promise<Response> = async ({ request, env }) => {
  if (!originAllowed(request)) return json(403, { error: "forbidden" });

  let data: Record<string, unknown>;
  try {
    const ct = request.headers.get("Content-Type") || "";
    if (ct.includes("application/json")) {
      data = await request.json();
    } else {
      const form = await request.formData();
      data = Object.fromEntries(form.entries());
    }
  } catch {
    return json(400, { error: "invalid body" });
  }

  const str = (v: unknown) => (typeof v === "string" ? v.trim() : "");
  const name = str(data.name).slice(0, 200);
  const email = str(data.email);
  const organisation = str(data.Organisation).slice(0, 200);
  const role = str(data.role).slice(0, 100);
  const timeline = str(data.timeline).slice(0, 100);
  const message = str(data.Message).slice(0, 5000);
  const honeypot = str(data.hp_company);
  const turnstileToken = str(data["cf-turnstile-response"]);
  const ts = parseInt(str(data.ts), 10);

  // Honeypot + time-trap: bots fill hidden fields and submit instantly.
  // Respond 200 so they get no signal that they were caught.
  const elapsed = Number.isFinite(ts) ? Date.now() - ts : -1;
  const looksLikeBot =
    honeypot.length > 0 || elapsed < MIN_FILL_MS || elapsed > MAX_FILL_MS;
  if (looksLikeBot) return json(200, { ok: true });

  if (!(await verifyTurnstile(turnstileToken, request, env))) {
    return json(403, { error: "security check failed" });
  }

  if (!isValidEmail(email)) return json(400, { error: "valid email required" });
  if (message.length < 2) return json(400, { error: "message required" });

  if (await rateLimited(request)) return json(429, { error: "slow down" });

  const to = env.CONTACT_TO || "toni@vaticinus.com";
  const from = env.CONTACT_FROM || "Vaticinus <contact@vaticinus.com>";
  const lines = [
    `Name: ${name || "(not given)"}`,
    `Email: ${email}`,
    `Firm: ${organisation || "(not given)"}`,
    `Role: ${role || "(not given)"}`,
    `Timeline: ${timeline || "(not given)"}`,
    "",
    "What they want pointed at:",
    message,
  ].join("\n");

  const result = await sendEmail(env.RESEND_API_KEY, {
    from,
    to,
    replyTo: email,
    subject: `Work-with-us enquiry from ${name || email}${organisation ? ` · ${organisation}` : ""}`,
    text: lines,
  });

  if (!result.ok) {
    console.error("contact send failed:", result.error);
    return json(502, { error: "could not send message" });
  }
  return json(200, { ok: true });
};
// Non-POST methods get an automatic 405 from Pages (only onRequestPost is exported).
