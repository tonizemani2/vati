import { resolveProvider, SYSTEM_PROMPT, type ChatMessage } from "@/lib/model";
import { resolveCaller, badOrigin } from "@/lib/auth";
import { addMessage, conversationOwnedBy, createConversation, dbConfigured } from "@/lib/db";
import { edgeRateLimit } from "@/lib/security";

// Always run on the server at request time (never prerendered/cached).
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  if (badOrigin(request)) return new Response("bad origin", { status: 403 });
  const limited = await edgeRateLimit(request, {
    bucket: "api-chat",
    limit: 30,
    windowSeconds: 600,
  });
  if (limited) return limited;
  // Open front door: Quick is free for everyone, signed in or not. Signed-out callers get a
  // per-browser anonymous id (cookie) so their turns still persist to a conversation.
  const caller = await resolveCaller(request);
  const userId = caller.id;

  let messages: ChatMessage[];
  let conversationId: string | null = null;
  try {
    const body = await request.json();
    messages = Array.isArray(body?.messages) ? body.messages : [];
    conversationId = typeof body?.conversation_id === "string" ? body.conversation_id : null;
  } catch {
    return new Response("bad request", { status: 400 });
  }
  if (messages.length === 0) return new Response("no messages", { status: 400 });

  let provider;
  try {
    provider = resolveProvider();
  } catch (e) {
    console.error("provider not configured", e); // detail stays server-side
    return new Response("Vaticinus backend is temporarily unavailable.", { status: 503 });
  }

  // Persist the incoming user turn (best-effort; create a conversation if needed).
  const lastUser = [...messages].reverse().find((m) => m.role === "user");
  if (dbConfigured()) {
    try {
      if (conversationId && !(await conversationOwnedBy(conversationId, userId))) {
        conversationId = null;
      }
      if (!conversationId) {
        const title = (lastUser?.content || "New forecast").slice(0, 80);
        conversationId = await createConversation(userId, title);
      }
      if (lastUser) await addMessage(conversationId, "user", lastUser.content);
    } catch {
      conversationId = conversationId ?? null;
    }
  }

  const upstream = await fetch(provider.url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${provider.key}`,
      "Content-Type": "application/json",
      ...(provider.extraHeaders || {}),
    },
    body: JSON.stringify({
      model: provider.model,
      stream: true,
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        ...messages.map((m) => ({ role: m.role, content: m.content })),
      ],
    }),
  });

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.text().catch(() => "");
    console.error(`model upstream error ${upstream.status}: ${detail.slice(0, 300)}`);
    return new Response("The forecasting model is temporarily unavailable.", { status: 502 });
  }

  // DeepSeek V4 streams `reasoning_content` (chain of thought) before `content`. We re-emit
  // BOTH as tagged NDJSON ({"t":"r"|"c","v":"..."}) so the client shows live reasoning then the
  // answer. The assistant turn is persisted by the client (POST /api/messages) once the stream
  // completes — reliable across runtimes, since a streamed response outlives the request scope.
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();
  const reader = upstream.body.getReader();
  let buffer = "";

  const emit = (controller: ReadableStreamDefaultController<Uint8Array>, t: string, v: string) =>
    controller.enqueue(encoder.encode(JSON.stringify({ t, v }) + "\n"));

  const stream = new ReadableStream<Uint8Array>({
    async pull(controller) {
      const { done, value } = await reader.read();
      if (done) {
        controller.close();
        return;
      }
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const raw of lines) {
        const line = raw.trim();
        if (!line.startsWith("data:")) continue;
        const data = line.slice(5).trim();
        if (data === "[DONE]") {
          controller.close();
          return;
        }
        try {
          const delta = JSON.parse(data)?.choices?.[0]?.delta;
          if (delta?.reasoning_content) emit(controller, "r", delta.reasoning_content);
          if (delta?.content) emit(controller, "c", delta.content);
        } catch {
          // partial JSON across chunks: ignore, the next pull completes it
        }
      }
    },
    cancel() {
      reader.cancel().catch(() => {});
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "X-Content-Type-Options": "nosniff",
      ...(conversationId ? { "X-Conversation-Id": conversationId } : {}),
      ...(caller.setCookie ? { "Set-Cookie": caller.setCookie } : {}),
    },
  });
}
