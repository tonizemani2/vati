import { runCapture, type CaptureEvent } from "@/lib/capture";
import { resolveCaller, badOrigin, viewAsUser } from "@/lib/auth";
import { consume } from "@/lib/credits";
import { addMessage, conversationOwnedBy, dbConfigured } from "@/lib/db";
import { edgeRateLimit } from "@/lib/security";
import { keepAlive } from "@/lib/bg";

export const dynamic = "force-dynamic";

// The value-capture path. Takes a forecast we have already produced and turns it into a
// concrete play (named targets, the ask, the value mechanism, who pays). Same streaming
// contract as /api/council (tagged NDJSON {t,...}): phase events while it works, then a single
// {t:"plan"} with the structured play. Always paid (no free allowance), so an anon caller hits
// the 402 gate and is nudged to sign in.
export async function POST(request: Request) {
  if (badOrigin(request)) return new Response("bad origin", { status: 403 });
  const limited = await edgeRateLimit(request, {
    bucket: "api-capture",
    limit: 8,
    windowSeconds: 600,
  });
  if (limited) return limited;
  const caller = await resolveCaller(request);
  const userId = caller.id;

  let question = "";
  let context = "";
  let conversationId: string | null = null;
  try {
    const body = await request.json();
    question = typeof body?.question === "string" ? body.question.trim() : "";
    context = typeof body?.context === "string" ? body.context.trim() : "";
    conversationId = typeof body?.conversation_id === "string" ? body.conversation_id : null;
  } catch {
    return new Response("bad request", { status: 400 });
  }
  if (!question) return new Response("no question", { status: 400 });

  // Credits gate. 402 = out of credits (client opens the buy-credits flow / sign-in nudge).
  const charge = await consume(userId, "capture", viewAsUser(request));
  if (!charge.ok) {
    return new Response(
      JSON.stringify({ error: "insufficient", account: charge.account, tier: "capture", anon: caller.anon }),
      {
        status: 402,
        headers: {
          "Content-Type": "application/json",
          ...(caller.setCookie ? { "Set-Cookie": caller.setCookie } : {}),
        },
      },
    );
  }

  const encoder = new TextEncoder();
  const line = (obj: unknown) => encoder.encode(JSON.stringify(obj) + "\n");

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      controller.enqueue(line({ t: "account", account: charge.account, mode: charge.mode }));
      const emit = (ev: CaptureEvent) => {
        try {
          controller.enqueue(line(ev));
        } catch {
          /* controller closed */
        }
        // Persist the play as an assistant turn (best-effort), so it survives a reload.
        if (ev.t === "plan" && dbConfigured() && conversationId) {
          void (async () => {
            try {
              if (await conversationOwnedBy(conversationId!, userId)) {
                await addMessage(conversationId!, "assistant", `[capture plan]\n${JSON.stringify(ev.plan)}`);
              }
            } catch {
              /* never block on a DB hiccup */
            }
          })();
        }
      };
      // Run under keepAlive so a closed browser does not abort the build: it finishes and the
      // emit persists the play, so it is waiting when the user returns.
      const work = (async () => {
        try {
          await runCapture(question, context, emit);
        } catch (e) {
          emit({ t: "error", v: (e as Error).message });
        } finally {
          try {
            controller.close();
          } catch {
            /* already closed (client gone) */
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
      ...(caller.setCookie ? { "Set-Cookie": caller.setCookie } : {}),
    },
  });
}
