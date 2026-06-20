import { adminPinCookie, validateAdminPin } from "@/lib/adminAccess";
import { badOrigin } from "@/lib/auth";
import { edgeRateLimit } from "@/lib/security";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  if (badOrigin(request)) return json({ ok: false, error: "bad origin" }, 403);
  const limited = await edgeRateLimit(request, {
    bucket: "api-admin-pin",
    limit: 12,
    windowSeconds: 600,
  });
  if (limited) return limited;

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return json({ ok: false, error: "bad request" }, 400);
  }

  const pin = typeof body.pin === "string" ? body.pin : "";
  if (!(await validateAdminPin(pin))) {
    return json({ ok: false, error: "wrong pin" }, 401);
  }

  return json({ ok: true }, 200, await adminPinCookie());
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
