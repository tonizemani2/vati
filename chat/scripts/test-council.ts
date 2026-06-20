// Throwaway live test of the council against real DeepSeek. Run:
//   cd chat && npx tsx scripts/test-council.ts
import { runCouncil } from "../src/lib/council";

const q =
  process.argv.slice(2).join(" ") ||
  "Will a US grid-interconnection queue wait exceed 4 years on average by end of 2027?";

const deep = process.env.DEEP === "1" || process.env.DEEP === "true";

async function main() {
console.log("Q:", q, deep ? "  [DEEP — data layer on]" : "", "\n");
const t0 = Date.now();
let synth = "";
await runCouncil(q, (ev) => {
  if (ev.t === "member_start") console.log(`  ▸ analyst ${ev.id} working...`);
  else if (ev.t === "member_done")
    console.log(`  ✓ ${ev.id}: ${ev.stance}\n      ${ev.brief.replace(/\n/g, " ").slice(0, 140)}`);
  else if (ev.t === "ground")
    console.log(`\n  📊 DATA LAYER (our graph):\n${(ev.summary as string).split("\n").map((l) => "      " + l).join("\n").slice(0, 1400)}\n`);
  else if (ev.t === "gate")
    console.log(
      `\n  GATE: ${ev.verdict} - ${ev.priced}${ev.anchor.status === "priced" && ev.anchor.top ? `\n      anchor: ${ev.anchor.top.source} ${(ev.anchor.top.prob * 100).toFixed(0)}% (${ev.anchor.top.label})` : ev.anchor.status === "unchecked" ? " (market check unavailable)" : " (no comparable market)"}\n`,
    );
  else if (ev.t === "c") synth += ev.v;
  else if (ev.t === "error") console.log("  ‼ ", ev.v);
}, { deep });
console.log("\n=== SYNTHESIS ===\n" + synth);
console.log(`\n[done in ${((Date.now() - t0) / 1000).toFixed(1)}s]`);
}
main().catch((e) => { console.error(e); process.exit(1); });
