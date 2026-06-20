import { runCouncil, classifyIntent, runPlainAnswer, type CouncilEvent } from "@/lib/council";
import { resolveCaller, badOrigin, viewAsUser } from "@/lib/auth";
import { consume, getAccount, type Tier } from "@/lib/credits";
import { addMessage, conversationOwnedBy, createConversation, dbConfigured } from "@/lib/db";
import { edgeRateLimit } from "@/lib/security";

export const dynamic = "force-dynamic";

// The multi-agent path. Same streaming contract as /api/chat (tagged NDJSON {t,...}) but
// with extra council events (member_start/member_done/gate) before the synthesis tokens.
// Open front door: signed-out visitors get a per-browser anon id and draw the same 3 free
// Council runs / month before the credits gate. Deep + paid credits still need an account
// (anon starts at 0 credits), so a 402 on the anon path is the nudge to sign in.
export async function POST(request: Request) {
  if (badOrigin(request)) return new Response("bad origin", { status: 403 });
  const limited = await edgeRateLimit(request, {
    bucket: "api-council",
    limit: 10,
    windowSeconds: 600,
  });
  if (limited) return limited;
  const caller = await resolveCaller(request);
  const userId = caller.id;

  let question = "";
  let tier: Tier = "council";
  let conversationId: string | null = null;
  try {
    const body = await request.json();
    question = typeof body?.question === "string" ? body.question.trim() : "";
    if (body?.tier === "deep") tier = "deep";
    conversationId = typeof body?.conversation_id === "string" ? body.conversation_id : null;
  } catch {
    return new Response("bad request", { status: 400 });
  }
  if (!question) return new Response("no question", { status: 400 });

  // Intelligence gate: only spin up the multi-agent council (and charge for it) when the question
  // genuinely warrants it. Ordinary conversation, meta ("what can you do"), definitions, and coding
  // get a normal direct answer for free instead of a wasted council run.
  const intent = await classifyIntent(question);

  // Persist the user turn (best-effort), creating a conversation if needed. Shared by both paths.
  if (dbConfigured()) {
    try {
      if (conversationId && !(await conversationOwnedBy(conversationId, userId))) {
        conversationId = null;
      }
      if (!conversationId) conversationId = await createConversation(userId, question.slice(0, 80));
      await addMessage(conversationId, "user", question);
    } catch {
      /* never block the run on a DB hiccup */
    }
  }

  const encoder = new TextEncoder();
  const line = (obj: unknown) => encoder.encode(JSON.stringify(obj) + "\n");
  const headers = {
    "Content-Type": "text/plain; charset=utf-8",
    "Cache-Control": "no-cache, no-transform",
    "X-Content-Type-Options": "nosniff",
    ...(conversationId ? { "X-Conversation-Id": conversationId } : {}),
    ...(caller.setCookie ? { "Set-Cookie": caller.setCookie } : {}),
  };

  // --- conversational turn: free, no council, no charge -----------------------------------------
  if (intent === "chat") {
    const account = await getAccount(userId).catch(() => null);
    const stream = new ReadableStream<Uint8Array>({
      async start(controller) {
        if (account) controller.enqueue(line({ t: "account", account, mode: "free" }));
        const emit = (ev: CouncilEvent) => {
          try {
            controller.enqueue(line(ev));
          } catch {
            /* controller closed */
          }
        };
        try {
          await runPlainAnswer(question, emit);
        } catch (e) {
          emit({ t: "error", v: (e as Error).message });
        } finally {
          controller.close();
        }
      },
    });
    return new Response(stream, { headers });
  }

  // --- forecast turn: the real council, billed --------------------------------------------------
  // viewAsUser lets the owner exercise the real charge path for QA (safe: downgrade only).
  const charge = await consume(userId, tier, viewAsUser(request));
  if (!charge.ok) {
    return new Response(
      JSON.stringify({ error: "insufficient", account: charge.account, tier, anon: caller.anon }),
      {
        status: 402,
        headers: {
          "Content-Type": "application/json",
          ...(caller.setCookie ? { "Set-Cookie": caller.setCookie } : {}),
        },
      },
    );
  }

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      // Tell the client its new balance immediately so the badge updates.
      controller.enqueue(line({ t: "account", account: charge.account, mode: charge.mode }));
      const emit = (ev: CouncilEvent) => {
        try {
          controller.enqueue(line(ev));
        } catch {
          /* controller closed */
        }
      };
      try {
        await runCouncil(question, emit, { deep: tier === "deep" });
      } catch (e) {
        emit({ t: "error", v: (e as Error).message });
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, { headers });
}
