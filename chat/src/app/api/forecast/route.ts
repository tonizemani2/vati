import { runForecast, type ForecastSpec } from "@/lib/mc";
import { badOrigin, resolveCaller } from "@/lib/auth";
import { conversationOwnedBy, dbConfigured, insertForecastCard } from "@/lib/db";
import { edgeRateLimit } from "@/lib/security";

export const dynamic = "force-dynamic";

// Run the Monte-Carlo forecast on a decomposed spec. The PROBABILITY and INTERVAL are
// computed here by our engine (ported from engine.forecast.mc_quantity), not guessed by
// the LLM. Then we persist the immutable card to Neon (best-effort; never fails the card).
export async function POST(request: Request) {
  if (badOrigin(request)) return json({ ok: false, error: "bad origin" }, 403);
  const limited = await edgeRateLimit(request, {
    bucket: "api-forecast",
    limit: 60,
    windowSeconds: 600,
  });
  if (limited) return limited;
  let spec: Record<string, unknown>;
  try {
    spec = await request.json();
  } catch {
    return json({ ok: false, error: "bad json" }, 400);
  }

  let result;
  try {
    result = runForecast(spec as unknown as ForecastSpec);
  } catch (e) {
    return json({ ok: false, error: (e as Error).message }, 422);
  }

  // Persist the card to the scored record (best-effort).
  if (dbConfigured()) {
    try {
      const caller = await resolveCaller(request);
      const conversationId =
        typeof spec.conversation_id === "string" &&
        (await conversationOwnedBy(spec.conversation_id, caller.id))
          ? spec.conversation_id
          : null;
      await insertForecastCard({
        conversation_id: conversationId,
        user_id: caller.id,
        question: String(spec.question ?? ""),
        quantity_label: (spec.quantity_label as string) ?? null,
        ci_unit: (spec.ci_unit as string) ?? null,
        base_value: result.base_value,
        horizon_years: result.horizon_years,
        g_mean: (spec.g_mean as number) ?? null,
        g_sd: (spec.g_sd as number) ?? null,
        decel: (spec.decel as number) ?? null,
        threshold: result.threshold,
        threshold_dir: result.threshold_dir,
        probability: result.probability,
        median: result.median,
        ci_low: result.ci_low,
        ci_high: result.ci_high,
        resolution_date: (spec.resolution_date as string) ?? null,
        dated_metric: (spec.dated_metric as string) ?? null,
        kill_criteria: Array.isArray(spec.kill_criteria) ? (spec.kill_criteria as string[]) : null,
        already_priced: (spec.already_priced as string) ?? null,
      });
    } catch {
      // DB hiccup must not break the user's card.
    }
  }

  return json(result, 200);
}

function json(body: unknown, status: number) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}
