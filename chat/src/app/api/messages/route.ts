import { badOrigin, resolveCaller } from "@/lib/auth";
import { addMessage, conversationOwnedBy, dbConfigured } from "@/lib/db";
import { edgeRateLimit } from "@/lib/security";

export const dynamic = "force-dynamic";

// Persist the assistant turn after the stream completes (the chat route only saves the user
// turn, since a streamed response outlives the request scope). Best-effort: a save failure
// must never surface to the user.
export async function POST(request: Request) {
  if (badOrigin(request)) return new Response("bad origin", { status: 403 });
  const limited = await edgeRateLimit(request, {
    bucket: "api-messages",
    limit: 80,
    windowSeconds: 600,
  });
  if (limited) return limited;
  const caller = await resolveCaller(request);
  const userId = caller.id;
  if (!dbConfigured()) return new Response(JSON.stringify({ ok: true }), { status: 200 });

  let body: { conversation_id?: string; content?: string; reasoning?: string | null };
  try {
    body = await request.json();
  } catch {
    return new Response("bad json", { status: 400 });
  }
  const { conversation_id, content } = body;
  if (!conversation_id || !content) {
    return new Response(JSON.stringify({ ok: false }), { status: 200 });
  }
  try {
    // Only persist into a conversation the caller actually owns (write-IDOR guard). A soft
    // 200 keeps the best-effort contract while silently dropping cross-tenant writes.
    if (await conversationOwnedBy(conversation_id, userId)) {
      await addMessage(conversation_id, "assistant", content, body.reasoning ?? null);
    }
  } catch {
    // best-effort
  }
  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      ...(caller.setCookie ? { "Set-Cookie": caller.setCookie } : {}),
    },
  });
}
