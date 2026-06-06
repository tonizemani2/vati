// Bias-proof universe benchmark (Phase 6+ — the survivorship-killer). Server-rendered, no client JS.
// The retrodiction test proves the method on 10 famous cases; the fair objection is "you picked the
// ones you knew." Here the candidate set is DRAWN BY RULE from the OpenAlex concept pool (data ≤ each
// origin) and the win/lose label is a RULE (gain-of-share, data > origin) — nobody chose the cases or
// the outcomes. Pooled + de-clustered confusion, per-origin consistency, lift over a true base rate.
import type { UniverseScore } from "@/lib/db";

function pct(x: number) {
  return `${Math.round(x * 100)}%`;
}

export function UniverseBenchmark({ score }: { score: UniverseScore | null }) {
  if (!score)
    return (
      <div className="flex min-h-24 items-center justify-center rounded-md border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
        No universe run yet. Run: python -m engine.cli universe-run
      </div>
    );

  const Cell = ({ n, label, good }: { n: number; label: string; good: boolean }) => (
    <div
      className={`rounded-md border p-3 text-center ${
        good ? "border-emerald-500/30 bg-emerald-500/5" : "border-amber-500/30 bg-amber-500/5"
      }`}
    >
      <div className={`font-mono text-2xl ${good ? "text-emerald-400" : "text-amber-400"}`}>{n}</div>
      <div className="text-[11px] leading-tight text-muted-foreground">{label}</div>
    </div>
  );

  return (
    <div className="space-y-5">
      {/* headline scoreboard */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          ["Lift", `${score.lift.toFixed(2)}×`, "precision ÷ base rate", score.lift > 1],
          ["Precision", pct(score.precision), "winner | fired", score.lift > 1],
          ["Recall", pct(score.recall), "fired | winner", score.recall >= 0.6],
          ["Specificity", pct(score.specificity), "reject | loser", score.specificity >= 0.6],
        ].map(([k, v, sub, good]) => (
          <div key={k as string} className="rounded-md border p-3">
            <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
              {k as string}
            </div>
            <div className={`font-mono text-2xl ${good ? "text-emerald-400" : "text-foreground"}`}>
              {v as string}
            </div>
            <div className="text-[11px] text-muted-foreground">{sub as string}</div>
          </div>
        ))}
      </div>

      {/* the honest numbers: a TRUE low base rate, lift held at every origin, the conservative
          de-clustered lift, and lead-time. The de-clustered number is the one to trust. */}
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
        <span>
          base rate <span className="font-mono text-foreground">{pct(score.base_rate)}</span> (
          {score.a + score.c}/{score.n})
        </span>
        <span>
          pooled lift{" "}
          <span className={`font-mono ${score.lift > 1 ? "text-emerald-400" : "text-foreground"}`}>
            {score.lift.toFixed(2)}×
          </span>{" "}
          · {score.n} forecasts
        </span>
        <span>
          de-clustered{" "}
          <span
            className={`font-mono ${score.declustered.lift > 1 ? "text-emerald-400" : "text-foreground"}`}
          >
            {score.declustered.lift.toFixed(2)}×
          </span>{" "}
          (n={score.declustered.n}, 1/concept — the conservative number)
        </span>
        {score.median_lead_months !== null && (
          <span>
            median lead{" "}
            <span className="font-mono text-foreground">{score.median_lead_months}mo</span>
          </span>
        )}
      </div>

      {/* confusion 2×2 — the true-negative mass (silent & lost) is the whole point: most of a neutral
          universe goes nowhere, and the method stays quiet on it. */}
      <div>
        <div className="mb-2 grid grid-cols-[5rem_1fr_1fr] gap-2 text-[11px] text-muted-foreground">
          <span />
          <span className="text-center">gained share</span>
          <span className="text-center">flat / lost share</span>
        </div>
        <div className="grid grid-cols-[5rem_1fr_1fr] gap-2">
          <span className="flex items-center text-[11px] text-muted-foreground">⚡ fired</span>
          <Cell n={score.a} label="called the migration" good={score.a > 0} />
          <Cell n={score.b} label="false positives" good={score.b <= score.a} />
          <span className="flex items-center text-[11px] text-muted-foreground">silent</span>
          <Cell n={score.c} label="missed (recall gap)" good={false} />
          <Cell n={score.d} label="correctly stayed quiet" good={score.d > 0} />
        </div>
      </div>

      {/* per-origin: does the edge hold at EVERY rolling origin, or one lucky year? */}
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-sm">
          <thead className="bg-card text-xs text-muted-foreground">
            <tr className="border-b">
              <th className="px-3 py-2 text-left font-medium">origin</th>
              <th className="px-3 py-2 text-right font-medium">|U(T)| drawn</th>
              <th className="px-3 py-2 text-right font-medium">scored</th>
              <th className="px-3 py-2 text-right font-medium">base rate</th>
              <th className="px-3 py-2 text-right font-medium">precision</th>
              <th className="px-3 py-2 text-right font-medium">lift</th>
            </tr>
          </thead>
          <tbody>
            {score.per_origin.map((r) => (
              <tr key={r.origin} className="border-b last:border-0">
                <td className="px-3 py-2 font-mono text-xs">{r.origin}</td>
                <td className="px-3 py-2 text-right font-mono text-xs text-muted-foreground">
                  {r.drawn}
                </td>
                <td className="px-3 py-2 text-right font-mono text-xs text-muted-foreground">
                  {r.n}
                </td>
                <td className="px-3 py-2 text-right font-mono text-xs text-muted-foreground">
                  {pct(r.base_rate)}
                </td>
                <td className="px-3 py-2 text-right font-mono text-xs">{pct(r.precision)}</td>
                <td
                  className={`px-3 py-2 text-right font-mono text-xs ${
                    r.lift > 1 ? "text-emerald-400" : "text-amber-400"
                  }`}
                >
                  {r.lift.toFixed(2)}×
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs leading-relaxed text-muted-foreground">
        Every OpenAlex concept clearing a{" "}
        <span className="text-foreground">frozen draw rule</span> (counts resolvable above their own
        Poisson noise — median √y ≥ k, the detector&apos;s own threshold, no magic level floor — and
        ≥8 points) at each origin is forecast — winners and known laggards on identical footing, so
        nobody picked the cases. The label is a <span className="text-foreground">frozen gain-of-share rule</span>{" "}
        (zero-sum across the cohort, so it can&apos;t ride a rising tide), assigned only from data{" "}
        <span className="text-foreground">after</span> the origin. The honest soft spot is{" "}
        <span className="text-foreground">recall</span>: the method is a precise filter, not a wide
        net — it stays silent on winners still flat at the cutoff. Named ceiling, not hidden: the
        label is share within OpenAlex&apos;s own counts, not a feed independent of the detector&apos;s
        input — a cross-feed label (grant / patent / market share) is the next upgrade. Rigorous
        LOCO-Brier + Fisher-exact p are in the CLI artifact.
      </p>
    </div>
  );
}
