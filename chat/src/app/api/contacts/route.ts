import { runFindContacts, contactsEnabled, type ContactsEvent } from "@/lib/contacts";
import type { CapturePlan } from "@/lib/capture";
import { resolveCaller, badOrigin, viewAsUser } from "@/lib/auth";
import { consume } from "@/lib/credits";
import { addMessage, conversationOwnedBy, dbConfigured } from "@/lib/db";
import { edgeRateLimit } from "@/lib/security";
import { keepAlive } from "@/lib/bg";

export const dynamic = "force-dynamic";

// "Find who to call": Rung 3. Takes a PURSUE value-capture play and resolves its named targets to
// real, verified, enriched contacts. Same streaming contract as /api/capture (tagged NDJSON
// {t,...}): phase heartbeats, then a single {t:"contacts"}. Paid, no free allowance. We check the
// finder is configured AND the play is a real PURSUE with targets BEFORE charging, so a caller is
// never billed for a run that cannot produce contacts.
export async function POST(request: Request) {
  if (badOrigin(request)) return new Response("bad origin", { status: 403 });
  const limited = await edgeRateLimit(request, {
    bucket: "api-contacts",
    limit: 8,
    windowSeconds: 600,
  });
  if (limited) return limited;
  const caller = await resolveCaller(request);
  const userId = caller.id;

  let question = "";
  let plan: CapturePlan | null = null;
  let conversationId: string | null = null;
  try {
    const body = await request.json();
    question = typeof body?.question === "string" ? body.question.trim() : "";
    plan = body?.plan && typeof body.plan === "object" ? (body.plan as CapturePlan) : null;
    conversationId = typeof body?.conversation_id === "string" ? body.conversation_id : null;
  } catch {
    return new Response("bad request", { status: 400 });
  }
  if (!plan) return new Response("no play", { status: 400 });
  if (plan.verdict === "PASS") return new Response("play is a pass; no contacts to source", { status: 400 });
  if (!(plan.targets ?? []).some((t) => t?.org || t?.person)) {
    return new Response("play has no named targets", { status: 400 });
  }
  if (!contactsEnabled()) {
    // Do not charge for a tool the deployment cannot run.
    return new Response(JSON.stringify({ error: "unconfigured" }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Credits gate. 402 = out of credits (client opens the buy-credits flow / sign-in nudge).
  const charge = await consume(userId, "contacts", viewAsUser(request));
  if (!charge.ok) {
    return new Response(
      JSON.stringify({ error: "insufficient", account: charge.account, tier: "contacts", anon: caller.anon }),
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
      const emit = (ev: ContactsEvent) => {
        try {
          controller.enqueue(line(ev));
        } catch {
          /* controller closed */
        }
        // Persist the contact list as an assistant turn (best-effort), so it survives a reload.
        if (ev.t === "contacts" && dbConfigured() && conversationId) {
          void (async () => {
            try {
              if (await conversationOwnedBy(conversationId!, userId)) {
                await addMessage(conversationId!, "assistant", `[contacts]\n${JSON.stringify(ev.contacts)}`);
              }
            } catch {
              /* never block on a DB hiccup */
            }
          })();
        }
      };
      // Run under keepAlive so a closed browser does not abort the search: it finishes and the
      // emit persists the contacts, so they are waiting when the user returns. The stream awaits
      // the same work to relay events while the client is still connected.
      const work = (async () => {
        try {
          await runFindContacts(question, plan!, emit);
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
