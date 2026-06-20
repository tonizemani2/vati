import { requireAdminAccess } from "@/lib/adminAccess";
import { badOrigin } from "@/lib/auth";
import { edgeRateLimit } from "@/lib/security";
import { getWebsetsCredits, getWebsetsStatus, searchWebsets, websetsEnabled } from "@/lib/websets";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  if (badOrigin(request)) return json({ ok: false, error: "bad origin" }, 403);
  const { caller, allowed } = await requireAdminAccess(request);
  if (!allowed) return json({ ok: false, error: "pin required" }, 403, caller.setCookie);

  try {
    const credits = websetsEnabled() ? await getWebsetsCredits() : null;
    return json({ ok: true, configured: websetsEnabled(), credits }, 200, caller.setCookie);
  } catch (e) {
    console.error("websets status failed", e);
    return json({ ok: true, configured: websetsEnabled(), credits: null }, 200, caller.setCookie);
  }
}

export async function POST(request: Request) {
  if (badOrigin(request)) return json({ ok: false, error: "bad origin" }, 403);
  const limited = await edgeRateLimit(request, {
    bucket: "api-admin-websets",
    limit: 20,
    windowSeconds: 600,
  });
  if (limited) return limited;

  const { caller, allowed } = await requireAdminAccess(request);
  if (!allowed) return json({ ok: false, error: "pin required" }, 403, caller.setCookie);

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return json({ ok: false, error: "bad request" }, 400, caller.setCookie);
  }

  if (!websetsEnabled()) {
    return json({ ok: false, error: "websets is not configured" }, 503, caller.setCookie);
  }

  const action = typeof body.action === "string" ? body.action : "search";
  try {
    if (action === "credits") {
      return json({ ok: true, credits: await getWebsetsCredits() }, 200, caller.setCookie);
    }

    if (action === "status") {
      const websetId = stringOr(body.webset_id, "");
      if (!websetId) return json({ ok: false, error: "missing webset_id" }, 400, caller.setCookie);
      return json({ ok: true, result: await getWebsetsStatus(websetId) }, 200, caller.setCookie);
    }

    if (action !== "search") {
      return json({ ok: false, error: "unknown action" }, 400, caller.setCookie);
    }

    const query = stringOr(body.query, "").trim();
    if (!query) return json({ ok: false, error: "empty query" }, 400, caller.setCookie);

    const entity = stringOr(body.entity, "person") === "company" ? "company" : "person";
    const count = numberOr(body.count, 5);
    const waitMs = numberOr(body.wait_ms, 90000);
    const result = await searchWebsets({ query, entity, count, waitMs });
    return json({ ok: true, result }, 200, caller.setCookie);
  } catch (e) {
    console.error("websets action failed", e);
    const message = e instanceof Error ? e.message : "websets failed";
    return json({ ok: false, error: message }, 500, caller.setCookie);
  }
}

function stringOr(value: unknown, fallback: string) {
  return typeof value === "string" ? value : fallback;
}

function numberOr(value: unknown, fallback: number) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function json(body: unknown, status: number, setCookie?: string) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...(setCookie ? { "Set-Cookie": setCookie } : {}),
    },
  });
}
