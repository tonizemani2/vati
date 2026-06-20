// Seed forward_calls in Neon from the sealed forward record.
// Run once (and after the seal changes):
//   DATABASE_URL="postgres://..." node db/seed_forward_calls.mjs
// Reads ../experiments/forward_calls_seal.jsonl. Idempotent (upsert on id).

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { neon } from "@neondatabase/serverless";

const url = process.env.DATABASE_URL;
if (!url) {
  console.error("set DATABASE_URL");
  process.exit(1);
}
const sql = neon(url);

const here = path.dirname(fileURLToPath(import.meta.url));
const sealPath = path.resolve(here, "..", "..", "experiments", "forward_calls_seal.jsonl");
const lines = fs.readFileSync(sealPath, "utf8").split("\n").filter((l) => l.trim());

let n = 0;
for (const line of lines) {
  let c;
  try {
    c = JSON.parse(line);
  } catch {
    continue;
  }
  if (!c?.id || !c?.question) continue;
  // Only seed unresolved calls (the live record); skip already-scored ones.
  if (c.outcome != null) continue;
  await sql`
    insert into forward_calls
      (id, question, rationale, probability, ci_low, ci_high, ci_unit,
       threshold, threshold_dir, resolution_date, thesis_kind, kill_criteria, implications, created_at, outcome)
    values
      (${c.id}, ${c.question}, ${c.rationale ?? null}, ${c.probability ?? null},
       ${c.ci_low ?? null}, ${c.ci_high ?? null}, ${c.ci_unit ?? null},
       ${c.threshold ?? null}, ${c.threshold_dir ?? null}, ${c.resolution_date ?? null},
       ${c.thesis_kind ?? null}, ${JSON.stringify(c.kill_criteria ?? [])},
       ${c.implications ? JSON.stringify(c.implications) : null},
       ${c.created_at ?? null}, ${c.outcome ?? null})
    on conflict (id) do update set
      question = excluded.question,
      rationale = excluded.rationale,
      probability = excluded.probability,
      ci_low = excluded.ci_low,
      ci_high = excluded.ci_high,
      ci_unit = excluded.ci_unit,
      threshold = excluded.threshold,
      threshold_dir = excluded.threshold_dir,
      resolution_date = excluded.resolution_date,
      thesis_kind = excluded.thesis_kind,
      kill_criteria = excluded.kill_criteria,
      implications = excluded.implications
  `;
  n++;
}
console.log(`seeded ${n} forward calls`);
