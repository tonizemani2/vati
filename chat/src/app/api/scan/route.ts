import { runScan, type ScanEvent } from "@/lib/scan";
import { resolveCaller, badOrigin, viewAsUser } from "@/lib/auth";
import { consume } from "@/lib/credits";
import { addMessage, conversationOwnedBy, createConversation, dbConfigured } from "@/lib/db";
import { edgeRateLimit } from "@/lib/security";
import { keepAlive } from "@/lib/bg";

export const dynamic = "force-dynamic";

// "Run it yourself": mint fresh pre-consensus structural calls for an area, grounded in the data
// layer. Generative + grounded, so it is paid (no free allowance), charged upfront like Deep. Same
// streaming contract as council/capture. Runs under keepAlive so a closed browser does not abort it.
export async function POST(request: Request) {
  if (badOrigin(request)) return new Response("bad origin", { status: 403 });
  const limited = await edgeRateLimit(request, { bucket: "api-scan", limit: 8, windowSeconds: 600 });
  if (limited) return limited;
  const caller = await resolveCaller(request);
  const userId = caller.id;

  let area = "";
  let conversationId: string | null = null;
  try {
    const body = await request.json();
    area = typeof body?.area === "string" ? body.area.trim() : "";
    conversationId = typeof body?.conversation_id === "string" ? body.conversation_id : null;
  } catch {
    return new Response("bad request", { status: 400 });
  }
  if (!area) return new Response("no area", { status: 400 });

  // Credits gate. 402 = out of credits (client opens the buy-credits flow / sign-in nudge).
  const charge = await consume(userId, "scan", viewAsUser(request));
  if (!charge.ok) {
    return new Response(
      JSON.stringify({ error: "insufficient", account: charge.account, tier: "scan", anon: caller.anon }),
      {
        status: 402,
        headers: { "Content-Type": "application/json", ...(caller.setCookie ? { "Set-Cookie": caller.setCookie } : {}) },
      },
    );
  }

  // Persist the user turn (best-effort), creating a conversation if needed.
  if (dbConfigured()) {
    try {
      if (conversationId && !(await conversationOwnedBy(conversationId, userId))) conversationId = null;
      if (!conversationId) conversationId = await createConversation(userId, `Scan: ${area.slice(0, 70)}`);
      await addMessage(conversationId, "user", `[frontier scan] ${area}`);
    } catch {
      /* never block on a DB hiccup */
    }
  }

  const encoder = new TextEncoder();
  const line = (obj: unknown) => encoder.encode(JSON.stringify(obj) + "\n");

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      controller.enqueue(line({ t: "account", account: charge.account, mode: charge.mode }));
      const emit = (ev: ScanEvent) => {
        try {
          controller.enqueue(line(ev));
        } catch {
          /* controller closed */
        }
        if (ev.t === "cards" && dbConfigured() && conversationId) {
          void (async () => {
            try {
              if (await conversationOwnedBy(conversationId!, userId)) {
                await addMessage(conversationId!, "assistant", `[scan]\n${JSON.stringify(ev.specs)}`);
              }
            } catch {
              /* never block on a DB hiccup */
            }
          })();
        }
      };
      const work = (async () => {
        try {
          await runScan(area, emit);
        } catch (e) {
          emit({ t: "error", v: (e as Error).message });
        } finally {
          try {
            controller.close();
          } catch {
            /* already closed */
          }
        }
      })();
      keepAlive(work);
      await work;
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
