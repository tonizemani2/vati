import { badOrigin, resolveCaller } from "@/lib/auth";
import { dbConfigured, deleteConversation, getMessages, listConversations } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  if (badOrigin(request)) return json({ ok: false, error: "bad origin" }, 403);

  const caller = await resolveCaller(request);
  const cookieHeaders = caller.setCookie ? { "Set-Cookie": caller.setCookie } : undefined;
  if (!dbConfigured()) {
    return json({ ok: true, conversations: [], messages: [] }, 200, cookieHeaders);
  }

  const url = new URL(request.url);
  const conversationId = url.searchParams.get("id");

  try {
    if (conversationId) {
      const messages = await getMessages(conversationId, caller.id);
      return json({ ok: true, messages }, 200, cookieHeaders);
    }

    const conversations = await listConversations(caller.id, 30);
    return json({ ok: true, conversations }, 200, cookieHeaders);
  } catch {
    return json({ ok: false, conversations: [], messages: [] }, 200, cookieHeaders);
  }
}

export async function DELETE(request: Request) {
  if (badOrigin(request)) return json({ ok: false, error: "bad origin" }, 403);

  const caller = await resolveCaller(request);
  if (!dbConfigured()) return json({ ok: true, deleted: false }, 200);

  const url = new URL(request.url);
  const conversationId = url.searchParams.get("id");
  if (!conversationId) return json({ ok: false, error: "missing conversation id" }, 400);

  try {
    const deleted = await deleteConversation(caller.id, conversationId);
    return json({ ok: true, deleted }, 200);
  } catch {
    return json({ ok: false, error: "delete failed" }, 500);
  }
}

function json(body: unknown, status: number, extraHeaders: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      ...extraHeaders,
    },
  });
}
