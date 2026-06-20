import { dbConfigured, getForwardCalls } from "@/lib/db";

export const dynamic = "force-dynamic";

// The live forward record: our sealed, dated, leak-free forward calls, served from Neon
// (seeded from experiments/forward_calls_seal.jsonl by db/seed_forward_calls.mjs). Read-only.
export async function GET() {
  if (!dbConfigured()) {
    return json({ ok: false, error: "DATABASE_URL not set", calls: [] });
  }
  try {
    const rows = await getForwardCalls(60);
    const calls = rows.map((c) => ({
      question: c.question,
      probability: c.probability,
      ci_low: c.ci_low,
      ci_high: c.ci_high,
      ci_unit: c.ci_unit,
      threshold: c.threshold,
      threshold_dir: c.threshold_dir,
      resolution_date: c.resolution_date,
      thesis_kind: c.thesis_kind,
      kill_criteria: c.kill_criteria,
      rationale: c.rationale,
      implications: c.implications,
    }));
    return json({ ok: true, n: calls.length, calls });
  } catch (e) {
    console.error("forward record query failed", e);
    return json({ ok: false, error: "record temporarily unavailable", calls: [] });
  }
}

function json(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}
